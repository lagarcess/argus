from __future__ import annotations

import atexit
from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from uuid import UUID

import jwt
from loguru import logger
from psycopg_pool import ConnectionPool

_AUTH_SESSION_CONNECTION_TIMEOUT_SECONDS = 2.0
_AUTH_SESSION_POOL_SIZE = 5


class AuthSessionVerificationUnavailable(RuntimeError):
    """Raised when Argus cannot safely determine whether a session is active."""


@dataclass(frozen=True)
class AuthSessionVerifier:
    pool: Any

    def is_active(self, *, token: str, user_id: str) -> bool:
        identity = _session_identity(token=token, user_id=user_id)
        if identity is None:
            return False
        session_id, auth_user_id = identity

        with self.pool.connection(
            timeout=_AUTH_SESSION_CONNECTION_TIMEOUT_SECONDS
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select exists (
                        select 1
                        from auth.sessions
                        where id = %s and user_id = %s
                    )
                    """,
                    (session_id, auth_user_id),
                )
                row = cursor.fetchone()
        return bool(row and row[0])


def auth_session_is_active(*, database_url: str, token: str, user_id: str) -> bool:
    if not database_url:
        raise AuthSessionVerificationUnavailable
    try:
        return _auth_session_verifier(database_url).is_active(
            token=token,
            user_id=user_id,
        )
    except AuthSessionVerificationUnavailable:
        raise
    except Exception as exc:
        logger.warning("Auth session verification failed: {}", type(exc).__name__)
        raise AuthSessionVerificationUnavailable from exc


def _session_identity(*, token: str, user_id: str) -> tuple[UUID, UUID] | None:
    try:
        claims = jwt.decode(
            token,
            options={"verify_signature": False, "verify_exp": False},
            algorithms=["HS256", "RS256", "ES256"],
        )
        session_id = UUID(str(claims.get("session_id") or ""))
        token_user_id = UUID(str(claims.get("sub") or ""))
        expected_user_id = UUID(user_id)
    except (TypeError, ValueError, jwt.PyJWTError):
        return None
    if token_user_id != expected_user_id:
        return None
    return session_id, expected_user_id


@lru_cache(maxsize=2)
def _auth_session_verifier(database_url: str) -> AuthSessionVerifier:
    pool = ConnectionPool(
        conninfo=database_url,
        kwargs={"autocommit": True},
        min_size=0,
        max_size=_AUTH_SESSION_POOL_SIZE,
        open=True,
        timeout=_AUTH_SESSION_CONNECTION_TIMEOUT_SECONDS,
        name="argus-auth-sessions",
    )
    atexit.register(pool.close)
    return AuthSessionVerifier(pool)
