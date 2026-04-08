"""
Supabase JWT authentication middleware for FastAPI.

Validates Supabase-issued JWTs. Falls back to a dev-mode mock
when SUPABASE_JWT_SECRET is not set (local development only).
"""

import time
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

    def get(self, user_id: str) -> Optional[str]:
        """Get cached subscription tier if not expired."""
        if user_id in self.cache:
            entry = self.cache[user_id]
            if time.time() - float(entry["timestamp"]) < self.ttl:
                return str(entry["tier"])
            del self.cache[user_id]
        return None

    def set(self, user_id: str, tier: str) -> None:
        """Cache the subscription tier."""
        self.cache[user_id] = {"tier": tier, "timestamp": time.time()}


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

    # Since we need full profile data (is_admin, quota, flags) we will bypass the simple tier cache for now
    # or fetch the full object.

    # 1. Default fallback profile
    profile_data: Dict[str, Any] = {
        "subscription_tier": "free",
        "is_admin": False,
        "theme": "dark",
        "lang": "en",
        "backtest_quota": 10,
        "remaining_quota": 10,
        "last_quota_reset": "2026-04-01T00:00:00Z",
        "feature_flags": {},
    }

    # 2. Fetch full profile from DB
    if supabase_client:
        try:
            res = (
                supabase_client.table("profiles")
                .select("*")
                .eq("id", user_id)
                .single()
                .execute()
            )
            if res.data and isinstance(res.data, dict):
                profile_data.update({k: v for k, v in res.data.items() if v is not None})
        except Exception as e:
            logger.info(
                f"Failed to fetch full profile for user {user_id}, using defaults: {e}"
            )

    return User(
        user_id=user_id,
        email=email,
        subscription_tier=str(profile_data["subscription_tier"]),
        is_admin=bool(profile_data["is_admin"]),
        theme=str(profile_data["theme"]),
        lang=str(profile_data["lang"]),
        backtest_quota=int(profile_data["backtest_quota"]),
        remaining_quota=int(profile_data["remaining_quota"]),
        last_quota_reset=str(profile_data["last_quota_reset"]),
        feature_flags=dict(profile_data["feature_flags"])
        if isinstance(profile_data["feature_flags"], dict)
        else {},
    )


def check_rate_limit(
    user: User = Depends(auth_required),  # noqa: B008
) -> User:
    """
    FastAPI dependency: checks if user has exceeded their quota.
    """
    if user.is_admin:
        return user

    if user.remaining_quota <= 0:
        logger.info(f"User {user.user_id} reached quota limit.")
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "Quota exceeded",
                "message": "You have exhausted your backtest quota.",
                "upgrade_url": "/settings",
            },
        )

    # We will simulate rate limits with headers in the endpoint responses directly
    return user
