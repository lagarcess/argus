"""
Supabase JWT authentication middleware for FastAPI.

Validates Supabase-issued JWTs from httpOnly cookies.
Falls back to a dev-mode mock when SUPABASE_JWT_SECRET is not set.
"""

import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from loguru import logger

from argus.config import get_settings
from argus.domain.schemas import UserResponse
from argus.supabase import supabase_client

# Supabase signs JWTs with the project JWT secret
_settings = get_settings()
_SUPABASE_JWT_SECRET: Optional[str] = _settings.SUPABASE_JWT_SECRET
_DEV_MODE = _settings.APP_ENV != "PROD"


class UserCache:
    """Simple TTL-based cache for user profiles."""

    def __init__(self, ttl_seconds: int = 300):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl = ttl_seconds

    def get(self, user_id: str) -> Optional[UserResponse]:
        """Get cached UserResponse if not expired."""
        if user_id in self.cache:
            entry = self.cache[user_id]
            if time.time() - entry["timestamp"] < self.ttl:
                return entry["user"]
            del self.cache[user_id]
        return None

    def set(self, user_id: str, user: UserResponse) -> None:
        """Cache the UserResponse."""
        self.cache[user_id] = {"user": user, "timestamp": time.time()}

    def invalidate(self, user_id: str) -> None:
        """Invalidate the cache for a specific user."""
        if user_id in self.cache:
            del self.cache[user_id]


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
    request: Request,
) -> Optional[Dict[str, Any]]:
    """
    FastAPI dependency: validates token from httpOnly cookie and returns user payload.
    In dev mode (no SUPABASE_JWT_SECRET), accepts any token and returns
    a synthetic user dict — never use in production.
    Returns None if missing or invalid token.
    """
    token = request.cookies.get("sb-access-token")

    if _DEV_MODE:
        if not token:
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
                token,
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

    if not token:
        return None

    return _decode_supabase_jwt(token)


def auth_required(
    payload: Optional[Dict[str, Any]] = Depends(get_current_user),  # noqa: B008
) -> UserResponse:
    """
    Enforcer dependency: Calls get_current_user. If None, raises 401.
    If valid, fetches profile fields from Supabase profiles table
    and returns a UserResponse model.
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

    # 1. Check cache first to avoid DB calls on every request
    cached_user = _user_cache.get(user_id)
    if cached_user:
        logger.debug(f"UserCache hit for user_id: {user_id}")
        return cached_user

    logger.debug(f"UserCache miss for user_id: {user_id}")

    is_admin = False
    subscription_tier = "free"
    theme = "dark"
    lang = "en"
    backtest_quota = 50
    remaining_quota = 50
    last_quota_reset = None
    feature_flags = {}

    # For dev-anon-user
    if user_id == "dev-anon-user":
        return UserResponse(
            user_id=user_id,
            id=user_id,
            email=email,
            is_admin=True,
            subscription_tier="max",
            backtest_quota=999999,
            remaining_quota=999999,
            feature_flags={"multi_asset_beta": True},
        )

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
                data = res.data
                subscription_tier = str(data.get("subscription_tier", "free"))
                is_admin = bool(data.get("is_admin", False))
                theme = str(data.get("theme", "dark"))
                lang = str(data.get("lang", "en"))
                backtest_quota = int(data.get("backtest_quota", 50))
                last_quota_reset_str = data.get("last_quota_reset")
                feature_flags = data.get("feature_flags", {})

                if last_quota_reset_str:
                    try:
                        # Convert Supabase timestamp (e.g. 2026-04-01T00:00:00+00:00) to python datetime
                        last_quota_reset = datetime.fromisoformat(
                            last_quota_reset_str.replace("Z", "+00:00")
                        )
                    except Exception:
                        pass
        except Exception as e:
            logger.info(
                f"Failed to fetch profile for user {user_id}, defaulting to free tier: {e}"
            )

    remaining_quota = backtest_quota

    if is_admin or subscription_tier in ["pro", "max"]:
        remaining_quota = 999999
        backtest_quota = 999999
    elif supabase_client:
        try:
            now = datetime.now(timezone.utc)
            start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            count_res = (
                supabase_client.table("simulation_logs")
                .select("id", count="exact")  # type: ignore[arg-type]
                .eq("user_id", user_id)
                .gte("created_at", start_of_month.isoformat())
                .execute()
            )
            count = count_res.count if count_res.count else 0
            remaining_quota = max(0, backtest_quota - count)
        except Exception as e:
            logger.info(f"Failed to fetch quota usage: {e}")

    user = UserResponse(
        user_id=user_id,
        id=user_id,
        email=email,
        is_admin=is_admin,
        subscription_tier=subscription_tier,
        theme=theme,
        lang=lang,
        backtest_quota=backtest_quota,
        remaining_quota=remaining_quota,
        last_quota_reset=last_quota_reset,
        feature_flags=feature_flags,
    )

    _user_cache.set(user_id, user)
    return user


def check_rate_limit(
    user: UserResponse = Depends(auth_required),  # noqa: B008
) -> UserResponse:
    """
    FastAPI dependency: checks if user has exceeded their monthly usage limit.
    Admins bypass all rate limits.
    """
    if user.is_admin:
        return user

    if user.subscription_tier in ["pro", "max"]:
        return user

    if user.remaining_quota <= 0:
        # Generate the first day of next month
        now = datetime.now(timezone.utc)
        if now.month == 12:
            next_reset = now.replace(
                year=now.year + 1,
                month=1,
                day=1,
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
        else:
            next_reset = now.replace(
                month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0
            )

        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "QUOTA_EXCEEDED",
                "message": "You have 0 backtests remaining this month.",
                "details": {"next_reset": next_reset.isoformat()},
            },
        )

    return user
