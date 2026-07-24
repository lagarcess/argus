from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from argus.api import state as api_state
from argus.api.guest_access import (
    guest_account_context,
    registered_account_context,
    store_account_context,
)
from argus.api.main import app
from argus.api.schemas import (
    GuestHandoffCreateRequest,
    GuestIdentityLinkRequest,
    OnboardingState,
    User,
)
from argus.domain.guest_workspaces import GuestWorkspace
from argus.domain.store import utcnow
from argus.domain.supabase_gateway import SupabaseGateway
from fastapi import Request
from fastapi.testclient import TestClient

GUEST_ID = "00000000-0000-0000-0000-000000000301"
REGISTERED_ID = "00000000-0000-0000-0000-000000000302"
CONVERSATION_ID = "00000000-0000-0000-0000-000000000303"
HANDOFF_ID = "00000000-0000-0000-0000-000000000304"


def _profile(*, user_id: str, email: str | None) -> User:
    now = utcnow()
    return User(
        id=user_id,
        email=email,
        username=None,
        display_name=None,
        language="en",
        locale="en-US",
        theme="dark",
        is_admin=False,
        onboarding=OnboardingState(),
        created_at=now,
        updated_at=now,
    )


def _workspace() -> GuestWorkspace:
    now = utcnow()
    return GuestWorkspace(
        user_id=GUEST_ID,
        conversation_id=CONVERSATION_ID,
        status="active",
        created_at=now,
        expires_at=now + timedelta(days=7),
        claimed_by=None,
        claimed_at=None,
        updated_at=now,
    )


@pytest.fixture(autouse=True)
def _conversion_environment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ARGUS_GUEST_ACCESS_ENABLED", "true")
    monkeypatch.setenv("NEXT_PUBLIC_GUEST_ACCESS_ENABLED", "true")
    monkeypatch.setenv("NEXT_PUBLIC_MOCK_AUTH", "false")
    monkeypatch.setenv("ARGUS_MOCK_AUTH", "false")
    monkeypatch.delenv("ARGUS_PUBLIC_ACCOUNT_ACCESS_ENABLED", raising=False)


def _guest_dependency(request: Request) -> User:
    profile = _profile(user_id=GUEST_ID, email=None)
    store_account_context(request, guest_account_context(_workspace()))
    return profile


def _registered_dependency(request: Request) -> User:
    profile = _profile(user_id=REGISTERED_ID, email="member@example.com")
    store_account_context(request, registered_account_context(REGISTERED_ID))
    return profile


def test_conversion_contract_rejects_untyped_or_cross_conversation_actions() -> None:
    request = GuestHandoffCreateRequest.model_validate(
        {
            "destination_email": "member@example.com",
            "source_conversation_id": CONVERSATION_ID,
            "pending_action": {
                "reason": "save_decision",
                "conversation_id": CONVERSATION_ID,
                "artifact_id": "00000000-0000-0000-0000-000000000305",
                "action_id": "decision-action-1",
            },
        }
    )
    assert request.pending_action is not None
    assert request.pending_action.reason == "save_decision"

    with pytest.raises(ValueError):
        GuestHandoffCreateRequest.model_validate(
            {
                "destination_email": "member@example.com",
                "source_conversation_id": CONVERSATION_ID,
                "pending_action": {
                    "reason": "invented_action",
                    "conversation_id": CONVERSATION_ID,
                    "action_id": "bad-action",
                },
            }
        )
    with pytest.raises(ValueError):
        GuestHandoffCreateRequest.model_validate(
            {
                "destination_email": "member@example.com",
                "source_conversation_id": CONVERSATION_ID,
                "pending_action": {
                    "reason": "keep_history",
                    "conversation_id": REGISTERED_ID,
                    "action_id": "cross-conversation",
                },
            }
        )


def test_guest_identity_link_contract_requires_a_real_email_and_strong_password() -> None:
    request = GuestIdentityLinkRequest(
        email="new-member@example.com",
        password="strong-password",
    )
    assert request.email == "new-member@example.com"

    with pytest.raises(ValueError):
        GuestIdentityLinkRequest(email="not-an-email", password="strong-password")
    with pytest.raises(ValueError):
        GuestIdentityLinkRequest(email="new-member@example.com", password="short")


def test_guest_creates_http_only_destination_bound_handoff_without_exposing_secret() -> (
    None
):
    gateway = MagicMock(spec=SupabaseGateway)
    gateway.resolve_permanent_auth_user_id.return_value = REGISTERED_ID
    gateway.create_guest_workspace_handoff.return_value = {
        "id": HANDOFF_ID,
        "expires_at": utcnow() + timedelta(minutes=10),
        "opaque_secret": "opaque-cookie-secret",
    }
    app.dependency_overrides.clear()
    from argus.api.dependencies import current_user

    app.dependency_overrides[current_user] = _guest_dependency
    try:
        with (
            patch.object(api_state, "supabase_gateway", gateway),
            TestClient(app, base_url="http://localhost:3000") as client,
        ):
            response = client.post(
                "/api/v1/auth/guest/handoffs",
                json={
                    "destination_email": "member@example.com",
                    "source_conversation_id": CONVERSATION_ID,
                    "pending_action": {
                        "reason": "keep_history",
                        "conversation_id": CONVERSATION_ID,
                        "action_id": "new-chat-1",
                    },
                },
                headers={
                    "Authorization": "Bearer guest-token",
                    "origin": "http://localhost:3000",
                    "x-forwarded-proto": "https",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["handoff_id"] == HANDOFF_ID
    assert "secret" not in response.json()
    set_cookie = response.headers["set-cookie"]
    assert "argus-guest-handoff=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie
    assert "SameSite=lax" in set_cookie
    gateway.resolve_permanent_auth_user_id.assert_called_once_with("member@example.com")
    gateway.create_guest_workspace_handoff.assert_called_once()
    call = gateway.create_guest_workspace_handoff.call_args.kwargs
    assert call["source_user_id"] == GUEST_ID
    assert call["destination_user_id"] == REGISTERED_ID
    assert call["source_conversation_id"] == CONVERSATION_ID
    assert "secret" not in call["pending_action"]


def test_registered_claim_uses_cookie_secret_and_returns_the_bound_pending_action() -> (
    None
):
    gateway = MagicMock(spec=SupabaseGateway)
    gateway.claim_guest_workspace_handoff.return_value = {
        "source_user_id": GUEST_ID,
        "destination_user_id": REGISTERED_ID,
        "conversation_id": CONVERSATION_ID,
        "pending_action": {
            "reason": "save_decision",
            "conversation_id": CONVERSATION_ID,
            "artifact_id": "00000000-0000-0000-0000-000000000305",
            "action_id": "decision-action-1",
        },
    }
    app.dependency_overrides.clear()
    from argus.api.dependencies import current_user

    app.dependency_overrides[current_user] = _registered_dependency
    try:
        with (
            patch.object(api_state, "supabase_gateway", gateway),
            TestClient(app, base_url="http://localhost:3000") as client,
        ):
            client.cookies.set("argus-guest-handoff", "opaque-cookie-secret")
            response = client.post(
                f"/api/v1/auth/guest/handoffs/{HANDOFF_ID}/claim",
                headers={
                    "origin": "http://localhost:3000",
                    "x-forwarded-proto": "https",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["conversation_id"] == CONVERSATION_ID
    assert response.json()["pending_action"]["action_id"] == "decision-action-1"
    gateway.claim_guest_workspace_handoff.assert_called_once_with(
        handoff_id=HANDOFF_ID,
        opaque_secret="opaque-cookie-secret",
        destination_user_id=REGISTERED_ID,
    )
    gateway.delete_anonymous_auth_user.assert_called_once_with(GUEST_ID)
    assert "Max-Age=0" in response.headers["set-cookie"]


def test_public_account_flag_owns_in_place_link_and_provider_failure_is_non_mutating(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = MagicMock(spec=SupabaseGateway)
    gateway.link_anonymous_identity.side_effect = RuntimeError("provider rejected")
    app.dependency_overrides.clear()
    from argus.api.dependencies import current_user

    app.dependency_overrides[current_user] = _guest_dependency
    try:
        with (
            patch.object(api_state, "supabase_gateway", gateway),
            TestClient(app) as client,
        ):
            client.cookies.set("sb-refresh-token", "guest-refresh-token")
            disabled = client.post(
                "/api/v1/auth/guest/link",
                json={
                    "email": "new-member@example.com",
                    "password": "strong-password",
                },
                headers={"Authorization": "Bearer guest-token"},
            )
            monkeypatch.setenv("ARGUS_PUBLIC_ACCOUNT_ACCESS_ENABLED", "true")
            failed = client.post(
                "/api/v1/auth/guest/link",
                json={
                    "email": "new-member@example.com",
                    "password": "strong-password",
                },
                headers={"Authorization": "Bearer guest-token"},
            )
    finally:
        app.dependency_overrides.clear()

    assert disabled.status_code == 403
    assert disabled.json()["code"] == "public_account_access_unavailable"
    assert failed.status_code == 400
    assert failed.json()["code"] == "guest_identity_link_failed"
    gateway.link_anonymous_identity.assert_called_once()
    gateway.mark_guest_identity_linked.assert_not_called()
