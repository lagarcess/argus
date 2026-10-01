"""Fixtures for household API acceptance with two registered identities."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from argus.api import state as api_state
from argus.api.main import app
from argus.api.schemas import OnboardingState, User
from argus.domain.guest_workspaces import GuestWorkspace
from argus.domain.store import utcnow
from argus.domain.supabase_gateway import SupabaseGateway
from fastapi.testclient import TestClient

ALICE = "registered-alice"
BOB = "registered-bob"
GUEST = "guest-gina"
TOKENS = (ALICE, BOB, GUEST)


def _profile(user_id: str, email: str | None) -> User:
    now = utcnow()
    return User(
        id=user_id,
        email=email,
        username=None,
        display_name=None,
        language="en",
        locale="en-US",
        is_admin=False,
        onboarding=OnboardingState(),
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def identities() -> dict[str, dict[str, Any]]:
    users = {}
    for token in TOKENS:
        anonymous = token.startswith("guest")
        users[token] = {
            "id": str(uuid4()),
            "email": None if anonymous else f"{token}@example.test",
            "is_anonymous": anonymous,
        }
    return users


@pytest.fixture
def gateway(identities: dict[str, dict[str, Any]]) -> MagicMock:
    by_id = {user["id"]: user for user in identities.values()}

    def auth_user(token: str) -> dict[str, Any]:
        if token not in identities:
            raise RuntimeError("Invalid or missing user in token response.")
        return dict(identities[token])

    def profile(auth_user: dict[str, Any]) -> User:
        return _profile(auth_user["id"], auth_user.get("email"))

    def workspace(*, user_id: str, at):  # noqa: ANN001
        if not by_id[user_id]["is_anonymous"]:
            return None
        return GuestWorkspace(
            user_id=user_id,
            conversation_id=str(uuid4()),
            status="active",
            created_at=at - timedelta(minutes=1),
            expires_at=at + timedelta(days=7),
            claimed_by=None,
            claimed_at=None,
            updated_at=at - timedelta(minutes=1),
        )

    mock = MagicMock(spec=SupabaseGateway)
    mock.get_auth_user_from_token.side_effect = auth_user
    mock.get_or_create_profile_for_auth_user.side_effect = profile
    mock.get_active_guest_workspace.side_effect = workspace
    mock.private_alpha_email_disabled.return_value = False
    mock.private_alpha_email_allowed.return_value = True
    return mock


@pytest.fixture
def surface_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARGUS_FINANCIAL_ACCOUNTS_ENABLED", "true")
    monkeypatch.setenv("ARGUS_HOUSEHOLDS_ENABLED", "true")
    monkeypatch.setenv("ARGUS_GUEST_ACCESS_ENABLED", "true")
    monkeypatch.setenv("NEXT_PUBLIC_GUEST_ACCESS_ENABLED", "true")
    monkeypatch.setenv("ARGUS_PUBLIC_ACCOUNT_ACCESS_ENABLED", "true")
    monkeypatch.setenv("NEXT_PUBLIC_MOCK_AUTH", "false")
    monkeypatch.setenv("ARGUS_MOCK_AUTH", "false")


@pytest.fixture
def client(surface_env: None, gateway: MagicMock) -> Iterator[TestClient]:
    assert api_state.PERSISTENCE_MODE == "memory"
    with (
        patch.object(api_state, "supabase_gateway", gateway),
        patch("argus.api.dependencies.auth_session_is_active", return_value=True),
        TestClient(app) as test_client,
    ):
        yield test_client


class HouseholdApi:
    def __init__(self, client: TestClient, token: str, user_id: str) -> None:
        self._client = client
        self.user_id = user_id
        self._headers = {"Authorization": f"Bearer {token}"}

    def create_household(self, body: dict | None = None):
        return self._client.post(
            "/api/v1/households", json=body or {}, headers=self._headers
        )

    def list_households(self):
        return self._client.get("/api/v1/households", headers=self._headers)

    def get_household(self, household_id: str):
        return self._client.get(
            f"/api/v1/households/{household_id}", headers=self._headers
        )

    def invite(self, household_id: str):
        return self._client.post(
            f"/api/v1/households/{household_id}/invitations", headers=self._headers
        )

    def revoke_invite(self, household_id: str, invitation_id: str):
        return self._client.post(
            f"/api/v1/households/{household_id}/invitations/{invitation_id}/revoke",
            headers=self._headers,
        )

    def accept(self, token: str):
        return self._client.post(
            "/api/v1/household-invitations/accept",
            json={"token": token},
            headers=self._headers,
        )

    def leave(self, household_id: str):
        return self._client.post(
            f"/api/v1/households/{household_id}/leave", headers=self._headers
        )

    def remove(self, household_id: str, member_user_id: str):
        return self._client.post(
            f"/api/v1/households/{household_id}/members/{member_user_id}/remove",
            headers=self._headers,
        )

    def transfer_admin(self, household_id: str, user_id: str):
        return self._client.post(
            f"/api/v1/households/{household_id}/transfer-admin",
            json={"user_id": user_id},
            headers=self._headers,
        )

    def close(self, household_id: str):
        return self._client.post(
            f"/api/v1/households/{household_id}/close", headers=self._headers
        )

    def share(self, household_id: str, account_id: str, permission: str = "view"):
        return self._client.post(
            f"/api/v1/households/{household_id}/account-grants",
            json={"account_id": account_id, "permission": permission},
            headers=self._headers,
        )

    def update_grant(self, household_id: str, grant_id: str, permission: str):
        return self._client.patch(
            f"/api/v1/households/{household_id}/account-grants/{grant_id}",
            json={"permission": permission},
            headers=self._headers,
        )

    def revoke_grant(self, household_id: str, grant_id: str):
        return self._client.delete(
            f"/api/v1/households/{household_id}/account-grants/{grant_id}",
            headers=self._headers,
        )

    def shared_accounts(self, household_id: str):
        return self._client.get(
            f"/api/v1/households/{household_id}/accounts", headers=self._headers
        )

    def create_account(self, body: dict, *, key: str | None = None):
        headers = dict(self._headers)
        headers["Idempotency-Key"] = key or str(uuid4())
        return self._client.post(
            "/api/v1/financial-accounts", json=body, headers=headers
        )


@pytest.fixture
def alice(client: TestClient, identities: dict[str, dict[str, Any]]) -> HouseholdApi:
    return HouseholdApi(client, ALICE, identities[ALICE]["id"])


@pytest.fixture
def bob(client: TestClient, identities: dict[str, dict[str, Any]]) -> HouseholdApi:
    return HouseholdApi(client, BOB, identities[BOB]["id"])
