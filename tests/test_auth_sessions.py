from __future__ import annotations

from contextlib import contextmanager
from uuid import UUID, uuid4

import jwt


class _FakeCursor:
    def __init__(self, *, active: bool) -> None:
        self.active = active
        self.query: str | None = None
        self.params: tuple[UUID, UUID] | None = None

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, query: str, params: tuple[UUID, UUID]) -> None:
        self.query = query
        self.params = params

    def fetchone(self) -> tuple[bool]:
        return (self.active,)


class _FakeConnection:
    def __init__(self, cursor: _FakeCursor) -> None:
        self._cursor = cursor

    def cursor(self) -> _FakeCursor:
        return self._cursor


class _FakePool:
    def __init__(self, *, active: bool) -> None:
        self.cursor = _FakeCursor(active=active)

    @contextmanager
    def connection(self, *, timeout: float):
        assert timeout > 0
        yield _FakeConnection(self.cursor)


def _token(*, session_id: UUID, user_id: UUID) -> str:
    return jwt.encode(
        {"session_id": str(session_id), "sub": str(user_id)},
        "test-secret",
        algorithm="HS256",
    )


def test_auth_session_verifier_accepts_matching_active_session() -> None:
    from argus.api.auth_sessions import AuthSessionVerifier

    session_id = uuid4()
    user_id = uuid4()
    pool = _FakePool(active=True)

    assert AuthSessionVerifier(pool).is_active(
        token=_token(session_id=session_id, user_id=user_id),
        user_id=str(user_id),
    )
    assert "auth.sessions" in str(pool.cursor.query)
    assert pool.cursor.params == (session_id, user_id)


def test_auth_session_verifier_rejects_revoked_session() -> None:
    from argus.api.auth_sessions import AuthSessionVerifier

    user_id = uuid4()

    assert not AuthSessionVerifier(_FakePool(active=False)).is_active(
        token=_token(session_id=uuid4(), user_id=user_id),
        user_id=str(user_id),
    )


def test_auth_session_verifier_rejects_missing_or_mismatched_claims() -> None:
    from argus.api.auth_sessions import AuthSessionVerifier

    user_id = uuid4()
    verifier = AuthSessionVerifier(_FakePool(active=True))
    missing_session = jwt.encode({"sub": str(user_id)}, "test-secret", algorithm="HS256")

    assert not verifier.is_active(token=missing_session, user_id=str(user_id))
    assert not verifier.is_active(
        token=_token(session_id=uuid4(), user_id=uuid4()),
        user_id=str(user_id),
    )
