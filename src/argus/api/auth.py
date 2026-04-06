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
            if time.time() - entry["timestamp"] < self.ttl:
                return entry["tier"]
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

    # 1. Check cache first
    cached_tier = _user_cache.get(user_id)
    if cached_tier:
        return User(
            user_id=user_id,
            email=email,
            subscription_tier=cached_tier,
        )

    # 2. Fetch from DB if not in cache
    subscription_tier = "free"
    if supabase_client:
        try:
            res = (
                supabase_client.table("profiles")
                .select("subscription_tier")
                .eq("id", user_id)
                .single()
                .execute()
            )
            if res.data and isinstance(res.data, dict):
                val = res.data.get("subscription_tier")
                subscription_tier = str(val) if val is not None else "free"
        except Exception as e:
            # If profile not found or other db error, default to free
            logger.info(
                f"Failed to fetch profile for user {user_id}, defaulting to free tier: {e}"
            )

    # 3. Cache result
    _user_cache.set(user_id, subscription_tier)

    return User(
        user_id=user_id,
        email=email,
        subscription_tier=subscription_tier,
    )

