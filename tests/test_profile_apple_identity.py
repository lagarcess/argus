from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from argus.api import state as api_state
from argus.api.guest_access import registered_account_context
from argus.api.routers import profile
from argus.domain.apple_sign_in.identity import (
    AppleIdentityUnavailable,
    LinkedAppleIdentity,
)
from fastapi import HTTPException
from starlette.requests import Request

from tests.apple_sign_in_support import SUBJECT


@pytest.fixture
def owner(monkeypatch):
    user = api_state.store.get_or_create_dev_user()
    request = Request({"type": "http"})
    request.state.request_id = "synthetic-profile-read"
    monkeypatch.setattr(api_state, "supabase_gateway", None)
    monkeypatch.setattr(
        api_state, "DATABASE_URL", "postgresql://synthetic.invalid/unused"
    )
    monkeypatch.setattr(
        profile, "account_context", lambda _: registered_account_context(user.id)
    )
    return user, request


def test_registered_me_projects_identity_beside_user(owner, monkeypatch):
    user, request = owner
    read = MagicMock(return_value=LinkedAppleIdentity(SUBJECT))
    monkeypatch.setattr(profile, "_apple_identity", read, raising=False)
    result = profile.get_me(request, user).model_dump()
    assert result["apple_identity"] == {"subject": SUBJECT}
    assert "apple_identity" not in result["user"]
    read.assert_called_once_with(request, user.id)


def test_registered_me_projects_confirmed_absence(owner, monkeypatch):
    user, request = owner
    monkeypatch.setattr(profile, "_apple_identity", lambda *_: None, raising=False)
    assert profile.get_me(request, user).model_dump()["apple_identity"] is None


@pytest.mark.parametrize(
    "error",
    [
        AppleIdentityUnavailable("malformed"),
        AppleIdentityUnavailable("conflicting"),
        OSError("unreachable"),
    ],
)
def test_identity_read_failure_is_not_absence(owner, monkeypatch, error):
    user, request = owner
    connection = MagicMock()
    connection.__enter__.return_value = connection
    monkeypatch.setattr(
        profile, "connect", MagicMock(return_value=connection), raising=False
    )
    monkeypatch.setattr(
        profile, "linked_apple_identity", MagicMock(side_effect=error), raising=False
    )
    with pytest.raises(HTTPException) as raised:
        profile.get_me(request, user)
    assert raised.value.status_code == 503
    assert raised.value.detail["code"] == "apple_identity_unavailable"
    assert SUBJECT not in str(raised.value.detail)


def test_guest_never_reads_or_exposes_apple_identity(owner, monkeypatch):
    from dataclasses import replace

    user, request = owner
    context = replace(
        registered_account_context(user.id),
        kind="guest",
        expires_at=datetime.now(timezone.utc),
    )
    monkeypatch.setattr(profile, "account_context", lambda _: context)
    read = MagicMock(side_effect=AssertionError("guest identity read"))
    monkeypatch.setattr(profile, "_apple_identity", read, raising=False)
    assert profile.get_me(request, user).model_dump()["apple_identity"] is None
    read.assert_not_called()


def test_missing_database_is_only_absent_for_explicit_memory_mock(owner, monkeypatch):
    user, request = owner
    monkeypatch.setattr(api_state, "DATABASE_URL", "")
    assert profile.get_me(request, user).model_dump()["apple_identity"] is None
    monkeypatch.setenv("NEXT_PUBLIC_MOCK_AUTH", "false")
    monkeypatch.setenv("ARGUS_MOCK_AUTH", "false")
    with pytest.raises(HTTPException) as raised:
        profile.get_me(request, user)
    assert raised.value.status_code == 503


def test_identity_read_uses_owner_and_read_only_connection(owner, monkeypatch):
    user, request = owner
    connection = MagicMock()
    connection.__enter__.return_value = connection
    connect = MagicMock(return_value=connection)
    read = MagicMock(return_value=LinkedAppleIdentity(SUBJECT))
    monkeypatch.setattr(profile, "connect", connect)
    monkeypatch.setattr(profile, "linked_apple_identity", read)
    assert profile.get_me(request, user).apple_identity.subject == SUBJECT
    read.assert_called_once_with(connection, user.id)
    assert "default_transaction_read_only=on" in connect.call_args.kwargs["options"]
    connection.__exit__.assert_called_once()


def test_guest_schema_redacts_supplied_identity(owner):
    from dataclasses import replace

    user, _ = owner
    context = replace(
        registered_account_context(user.id),
        kind="guest",
        expires_at=datetime.now(timezone.utc),
    )
    response = profile._user_response(user, context, LinkedAppleIdentity(SUBJECT))
    assert response.apple_identity is None
    assert SUBJECT not in response.model_dump_json()
