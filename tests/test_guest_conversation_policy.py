from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from argus.api import state as api_state
from argus.api.main import app
from argus.api.schemas import Conversation, OnboardingState, User
from argus.domain.guest_workspaces import GuestWorkspace
from argus.domain.store import utcnow
from argus.domain.supabase_gateway import SupabaseGateway
from fastapi.testclient import TestClient

USER_ID = "00000000-0000-0000-0000-000000000061"
CONVERSATION_ID = "00000000-0000-0000-0000-000000000062"


def _profile() -> User:
    now = utcnow()
    return User(
        id=USER_ID,
        email=None,
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


def _conversation() -> Conversation:
    now = utcnow()
    return Conversation(
        id=CONVERSATION_ID,
        title="Temporary idea",
        title_source="system_default",
        language="en",
        pinned=False,
        archived=False,
        deleted_at=None,
        last_message_preview=None,
        created_at=now,
        updated_at=now,
    )


def test_guest_create_conversation_reuses_the_single_bound_conversation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_GUEST_ACCESS_ENABLED", "true")
    monkeypatch.setenv("NEXT_PUBLIC_GUEST_ACCESS_ENABLED", "true")
    monkeypatch.setenv("NEXT_PUBLIC_MOCK_AUTH", "false")
    monkeypatch.setenv("ARGUS_MOCK_AUTH", "false")
    profile = _profile()
    conversation = _conversation()
    workspace = GuestWorkspace(
        user_id=USER_ID,
        conversation_id=CONVERSATION_ID,
        status="active",
        created_at=profile.created_at,
        expires_at=profile.created_at + timedelta(days=7),
        claimed_by=None,
        claimed_at=None,
        updated_at=profile.created_at,
    )
    gateway = MagicMock(spec=SupabaseGateway)
    gateway.get_auth_user_from_token.return_value = {
        "id": USER_ID,
        "email": None,
        "is_anonymous": True,
    }
    gateway.get_or_create_profile_for_auth_user.return_value = profile
    gateway.get_active_guest_workspace.return_value = workspace
    gateway.get_conversation.return_value = conversation

    with (
        patch.object(api_state, "supabase_gateway", gateway),
        patch("argus.api.dependencies.auth_session_is_active", return_value=True),
        TestClient(app) as client,
    ):
        response = client.post(
            "/api/v1/conversations",
            json={"title": "Ignored second title", "language": "en"},
            headers={"Authorization": "Bearer verified-guest"},
        )

    assert response.status_code == 200
    assert response.json()["conversation"]["id"] == CONVERSATION_ID
    gateway.create_conversation.assert_not_called()
