"""The account deletion route (Lane 6, part B): flag, auth order, mapping."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from argus.api.guest_access import (
    AccountContext,
    guest_capabilities,
    registered_account_context,
    store_account_context,
)
from argus.api.main import app
from argus.api.routers import account as account_route
from argus.api.schemas import User
from argus.domain.account_deletion.service import (
    AccountDeletionIncomplete,
    AccountDeletionRejected,
    DeletionOutcome,
)
from fastapi.testclient import TestClient

client = TestClient(app)
USER_ID = "00000000-0000-0000-0000-0000000000d1"
URL = "/api/v1/account/delete"


_NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)


def _user(email: str | None) -> User:
    return User(id=USER_ID, email=email, created_at=_NOW, updated_at=_NOW)


def _registered(request):  # noqa: ANN001, ANN202
    store_account_context(request, registered_account_context(USER_ID))
    return _user("person@example.com")


def _guest(request):  # noqa: ANN001, ANN202
    store_account_context(
        request,
        AccountContext(
            kind="guest",
            user_id=USER_ID,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            capabilities=guest_capabilities(),
        ),
    )
    return _user(None)


@pytest.fixture
def enabled(monkeypatch):  # noqa: ANN001, ANN201
    monkeypatch.setenv(account_route.FLAG, "true")


def test_off_by_default_answers_404_before_auth(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.delenv(account_route.FLAG, raising=False)
    auth = MagicMock(side_effect=AssertionError("auth must not run"))
    with patch.object(account_route, "current_user", auth):
        response = client.post(URL, json={"confirm": True})
    assert response.status_code == 404
    auth.assert_not_called()


def test_requires_a_session(enabled) -> None:  # noqa: ANN001
    response = client.post(URL, json={"confirm": True})
    # No credentials: refused by authentication (401, or 5xx where this
    # process has no auth backend). Never reaches the command.
    assert response.status_code in {401, 500, 503}


def test_deletes_the_session_user_only(enabled) -> None:  # noqa: ANN001
    service = MagicMock()
    service.delete_account.return_value = DeletionOutcome(
        status="auth_deleted", pending=["gmail", "apple"]
    )
    with (
        patch.object(account_route, "current_user", _registered),
        patch.object(account_route, "account_deletion_service", return_value=service),
    ):
        response = client.post(URL, json={"confirm": True})
    assert response.status_code == 200
    assert response.json() == {"status": "auth_deleted", "pending": ["apple", "gmail"]}
    service.delete_account.assert_called_once_with(user_id=USER_ID)


@pytest.mark.parametrize(
    "body",
    [{}, {"confirm": False}, {"confirm": True, "user_id": "someone-else"}],
)
def test_body_is_only_a_confirmation(enabled, body) -> None:  # noqa: ANN001
    service = MagicMock()
    with (
        patch.object(account_route, "current_user", _registered),
        patch.object(account_route, "account_deletion_service", return_value=service),
    ):
        response = client.post(URL, json=body)
    assert response.status_code == 422
    service.delete_account.assert_not_called()


def test_form_post_is_refused(enabled) -> None:  # noqa: ANN001
    service = MagicMock()
    with (
        patch.object(account_route, "current_user", _registered),
        patch.object(account_route, "account_deletion_service", return_value=service),
    ):
        response = client.post(URL, data={"confirm": "true"})
    assert response.status_code == 422
    service.delete_account.assert_not_called()


def test_a_guest_is_deleted_by_the_same_command(enabled) -> None:  # noqa: ANN001
    service = MagicMock()
    service.delete_account.return_value = DeletionOutcome(status="done", pending=[])
    with (
        patch.object(account_route, "current_user", _guest),
        patch.object(account_route, "account_deletion_service", return_value=service),
    ):
        response = client.post(URL, json={"confirm": True})
    assert response.status_code == 200
    assert response.json() == {"status": "done", "pending": []}
    service.delete_account.assert_called_once_with(user_id=USER_ID)


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (AccountDeletionRejected("placeholder"), 403, "account_deletion_not_allowed"),
        (AccountDeletionIncomplete("units_changed"), 503, "account_deletion_incomplete"),
        (RuntimeError("boom"), 503, "account_deletion_incomplete"),
    ],
)
def test_failures_map_to_problems(enabled, error, status, code) -> None:  # noqa: ANN001
    service = MagicMock()
    service.delete_account.side_effect = error
    with (
        patch.object(account_route, "current_user", _registered),
        patch.object(account_route, "account_deletion_service", return_value=service),
    ):
        response = client.post(URL, json={"confirm": True})
    assert response.status_code == status
    assert response.json()["code"] == code
    assert USER_ID not in response.text


def test_unavailable_without_postgres_surfaces(enabled) -> None:  # noqa: ANN001
    with (
        patch.object(account_route, "current_user", _registered),
        patch.object(account_route, "account_deletion_service", return_value=None),
    ):
        response = client.post(URL, json={"confirm": True})
    assert response.status_code == 503
    assert response.json()["code"] == "account_deletion_unavailable"


def test_feedback_no_longer_takes_deletion_requests() -> None:
    from argus.api.schemas import FeedbackRequest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        FeedbackRequest(type="account_deletion_request", message="delete me")
