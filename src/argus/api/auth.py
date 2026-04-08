"""
Supabase JWT authentication middleware for FastAPI.

Validates Supabase-issued JWTs. Falls back to a dev-mode mock
when SUPABASE_JWT_SECRET is not set (local development only).
"""

import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger

from argus.config import get_settings
from argus.domain.schemas import User
from argus.supabase import supabase_client

security = HTTPBearer(auto_error=False)

# Rate limiting constants
FREE_TIER_MONTHLY_LIMIT = 10

# Supabase signs JWTs with the project JWT secret
_settings = get_settings()
_SUPABASE_JWT_SECRET: Optional[str] = _settings.SUPABASE_JWT_SECRET
_DEV_MODE = _settings.APP_ENV != "PROD"


class UserCache:
    """Simple TTL-based cache for user profiles."""

    def __init__(self, ttl_seconds: int = 300):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl = ttl_seconds

    def get(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get cached subscription tier if not expired."""
        if user_id in self.cache:
            entry = self.cache[user_id]
            if time.time() - entry["timestamp"] < self.ttl:
                return {"tier": entry["tier"], "is_admin": entry.get("is_admin", False)}
            del self.cache[user_id]
        return None

    def set(self, user_id: str, tier: str, is_admin: bool = False) -> None:
        """Cache the subscription tier."""
        self.cache[user_id] = {
            "tier": tier,
            "is_admin": is_admin,
            "timestamp": time.time(),
        }


_user_cache = UserCache()


def _decode_supabase_jwt(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate a Supabase JWT."""
    try:
        payload = jwt.decode(
            token,
            _SUPABASE_JWT_SECRET,  # type: ignore[arg-type]
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token has expired")
        return None
    except jwt.InvalidTokenError:
        logger.warning("Invalid authentication token")
        return None


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),  # noqa: B008
) -> Optional[Dict[str, Any]]:
    """
    FastAPI dependency: validates Bearer token and returns user payload.

    In dev mode (no SUPABASE_JWT_SECRET), accepts any token and returns
    a synthetic user dict — never use in production.
    Returns None if missing or invalid token.
    """
    if _DEV_MODE:
        if credentials is None:
            # In dev, allow unauthenticated access with a synthetic anon user
            logger.warning(
                "DEV MODE: No auth token provided. Using anonymous dev user. "
                "Set SUPABASE_JWT_SECRET to enforce auth."
            )
            return {
                "sub": "dev-anon-user",
                "email": "dev@argus.local",
                "role": "authenticated",
            }
        logger.warning(
            "DEV MODE: Skipping JWT signature verification. "
            "Set SUPABASE_JWT_SECRET for production."
        )
        # Still decode but without signature verification for dev convenience
        try:
            payload = jwt.decode(
                credentials.credentials,
                options={"verify_signature": False},
                algorithms=["HS256"],
            )
            return payload
        except Exception:  # noqa: BLE001
            return {
                "sub": "dev-anon-user",
                "email": "dev@argus.local",
                "role": "authenticated",
            }

    if credentials is None:
        return None

    return _decode_supabase_jwt(credentials.credentials)


def auth_required(
    payload: Optional[Dict[str, Any]] = Depends(get_current_user),  # noqa: B008
) -> User:
    """
    Enforcer dependency: Calls get_current_user. If None, raises 401.
    If valid, fetches subscription_tier from Supabase profiles table
    and returns a User model.
    """
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid authentication credentials required",
        )

    user_id = payload.get("sub")
    email = payload.get("email", "")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload: missing sub",
        )

    # 1. Check cache first
    cached_data = _user_cache.get(user_id)
    if cached_data:
        return User(
            user_id=user_id,
            email=email,
            subscription_tier=cached_data["tier"],
            is_admin=cached_data["is_admin"],
        )

    # 2. Fetch from DB if not in cache
    subscription_tier = "free"
    is_admin = False
    if supabase_client:
        try:
            res = (
                supabase_client.table("profiles")
                .select("subscription_tier, is_admin")
                .eq("id", user_id)
                .single()
                .execute()
            )
            if res.data and isinstance(res.data, dict):
                val = res.data.get("subscription_tier")
                subscription_tier = str(val) if val is not None else "free"
                is_admin = bool(res.data.get("is_admin", False))
        except Exception as e:
            # If profile not found or other db error, default to free
            logger.info(
                f"Failed to fetch profile for user {user_id}, defaulting to free tier: {e}"
            )

    # 3. Cache result
    _user_cache.set(user_id, subscription_tier, is_admin)

    return User(
        user_id=user_id,
        email=email,
        subscription_tier=subscription_tier,
        is_admin=is_admin,
    )


def check_rate_limit(
    user: User = Depends(auth_required),  # noqa: B008
) -> User:
    """
    FastAPI dependency: checks if user has exceeded their monthly usage limit.
    Free tier allows FREE_TIER_MONTHLY_LIMIT simulations per calendar month.
    """
    user_id = str(user.user_id)

    # In dev mode with synthetic user, bypass rate limit
    if _DEV_MODE and user_id == "dev-anon-user":
        return user

    # Pro tier is unlimited
    if user.subscription_tier == "pro":
        return user

    if not supabase_client:
        logger.warning("Supabase client not configured. Skipping rate limit check.")
        return user

    try:
        # Free tier limit check using current calendar month
        now = datetime.now(timezone.utc)
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Count simulations for current month using Service Role client (bypasses RLS)
        count_res = (
            supabase_client.table("simulation_logs")
            .select("id", count="exact")  # type: ignore[arg-type]
            .eq("user_id", user_id)
            .gte("created_at", start_of_month.isoformat())
            .execute()
        )

        count = count_res.count if count_res.count else 0

        if count >= FREE_TIER_MONTHLY_LIMIT:
            logger.info(
                f"User {user_id} reached monthly limit: {count}/{FREE_TIER_MONTHLY_LIMIT}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "Monthly limit reached",
                    "message": f"Free tier is limited to {FREE_TIER_MONTHLY_LIMIT} simulations per month.",
                    "upgrade_url": "/settings",
                },
            )

        return user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking rate limits for {user_id}: {e}")
        # Fail open for UX if DB fails but auth succeeded
        return user


# Asset search rate limits
ASSET_SEARCH_RATE_LIMIT = 100
ASSET_SEARCH_RATE_LIMIT_WINDOW = 60  # seconds
_asset_search_rate_limits: Dict[str, list[float]] = {}


def check_asset_search_rate_limit(
    user: User = Depends(auth_required),  # noqa: B008
) -> Dict[str, Any]:
    """
    Rate limiter for the GET /assets endpoint.
    Allows 100 searches per minute. Bypassed for admins.
    Returns headers to be appended to the response.
    """
    if user.is_admin:
        return {
            "X-RateLimit-Limit": str(ASSET_SEARCH_RATE_LIMIT),
            "X-RateLimit-Remaining": str(ASSET_SEARCH_RATE_LIMIT),
            "X-RateLimit-Reset": "0",
            "Retry-After": "0",
        }

    now = time.time()
    user_id = str(user.user_id)

    if user_id not in _asset_search_rate_limits:
        _asset_search_rate_limits[user_id] = []

    # Clean up old timestamps
    _asset_search_rate_limits[user_id] = [
        t
        for t in _asset_search_rate_limits[user_id]
        if now - t < ASSET_SEARCH_RATE_LIMIT_WINDOW
    ]

    current_requests = len(_asset_search_rate_limits[user_id])
    remaining = max(0, ASSET_SEARCH_RATE_LIMIT - current_requests)

    # Calculate reset time (when the oldest request in the window falls out)
    if current_requests > 0:
        reset_time = int(
            _asset_search_rate_limits[user_id][0] + ASSET_SEARCH_RATE_LIMIT_WINDOW
        )
    else:
        reset_time = int(now + ASSET_SEARCH_RATE_LIMIT_WINDOW)

    if remaining == 0:
        retry_after = reset_time - int(now)
        logger.warning(f"User {user_id} exceeded asset search rate limit.")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many asset searches. Please try again later.",
            headers={
                "X-RateLimit-Limit": str(ASSET_SEARCH_RATE_LIMIT),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset_time),
                "Retry-After": str(retry_after),
            },
        )

    # Record the new request
    _asset_search_rate_limits[user_id].append(now)
    remaining -= 1

    return {
        "X-RateLimit-Limit": str(ASSET_SEARCH_RATE_LIMIT),
        "X-RateLimit-Remaining": str(remaining),
        "X-RateLimit-Reset": str(reset_time),
        "Retry-After": "0",
    }
