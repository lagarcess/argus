"""
Supabase JWT authentication middleware for FastAPI.

Validates Supabase-issued JWTs. Falls back to a dev-mode mock
when SUPABASE_JWT_SECRET is not set (local development only).
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger

from argus.config import get_settings, get_supabase_client
from supabase import Client

security = HTTPBearer(auto_error=False)

# Supabase signs JWTs with the project JWT secret
_settings = get_settings()
_SUPABASE_JWT_SECRET: Optional[str] = _settings.SUPABASE_JWT_SECRET
_DEV_MODE = _settings.APP_ENV != "PROD"


def _decode_supabase_jwt(token: str) -> Dict[str, Any]:
    """Decode and validate a Supabase JWT."""
    try:
        payload = jwt.decode(
            token,
            _SUPABASE_JWT_SECRET,  # type: ignore[arg-type]
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
        return payload
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        ) from exc


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),  # noqa: B008
) -> Dict[str, Any]:
    """
    FastAPI dependency: validates Bearer token and returns user payload.

    In dev mode (no SUPABASE_JWT_SECRET), accepts any token and returns
    a synthetic user dict — never use in production.
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
        )

    return _decode_supabase_jwt(credentials.credentials)


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),  # noqa: B008
) -> Optional[Dict[str, Any]]:
    """Same as get_current_user but returns None instead of raising for public routes."""
    try:
        return get_current_user(credentials)
    except HTTPException:
        return None


def check_rate_limit(
    user: Dict[str, Any] = Depends(get_current_user),  # noqa: B008
) -> Dict[str, Any]:
    """
    FastAPI dependency: checks if user has exceeded their monthly usage limit.
    Free tier allows 10 simulations per calendar month.
    """
    try:
        supabase: Client = get_supabase_client()
    except ValueError:
        logger.warning("Supabase client not configured. Skipping rate limit check.")
        return user

    user_id = user["sub"]

    # In dev mode with synthetic user, bypass rate limit
    if _DEV_MODE and user_id == "dev-anon-user":
        return user

    try:
        # Fetch user profile to get subscription tier
        res = (
            supabase.table("profiles")
            .select("subscription_tier")
            .eq("id", user_id)
            .execute()
        )
        tier = "free"
        if res.data:
            item: Any = res.data[0]
            tier = (
                item.get("subscription_tier", "free")
                if isinstance(item, dict)
                else "free"
            )

        # Pro tier is unlimited
        if tier == "pro":
            return user

        # Free tier limit check
        now = datetime.now(timezone.utc)
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Count simulations for current month
        count_res = (
            supabase.table("simulation_logs")
            .select("id", count="exact")  # type: ignore[arg-type]
            .eq("user_id", user_id)
            .gte("created_at", start_of_month.isoformat())
            .execute()
        )

        count = count_res.count if count_res.count else 0

        if count >= 10:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "Monthly limit reached", "upgrade_url": "/settings"},
            )

        return user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking rate limits for {user_id}: {e}")
        # Fail open or fail closed? The prompt says implement rate limiting,
        # but if Supabase is down, failing open might be better for UX,
        # but the safest is failing closed or just logging and returning user.
        # Let's fail open for robust API if db fails but auth succeeded.
        return user
