"""
Supabase JWT authentication middleware for FastAPI.

Validates Supabase-issued JWTs. Falls back to a dev-mode mock
when SUPABASE_JWT_SECRET is not set (local development only).
"""

from typing import Any, Dict, Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger

from argus.config import get_settings

security = HTTPBearer(auto_error=False)

# Supabase signs JWTs with the project JWT secret
_settings = get_settings()
_SUPABASE_JWT_SECRET: Optional[str] = _settings.SUPABASE_JWT_SECRET
_DEV_MODE = _SUPABASE_JWT_SECRET is None


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
