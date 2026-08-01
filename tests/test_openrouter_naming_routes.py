from __future__ import annotations

from datetime import timedelta
from typing import Literal
from unittest.mock import MagicMock, patch

import pytest
from argus.api import state as api_state
from argus.api.main import app
from argus.api.routers import collections as collections_router
from argus.api.routers import strategies as strategies_router
from argus.api.schemas import Collection, Strategy, User
from argus.domain.guest_workspaces import GuestWorkspace
from argus.domain.store import utcnow
from argus.domain.supabase_gateway import SupabaseGateway
from argus.llm.openrouter_key_policy import resolve_openrouter_api_key
from fastapi.testclient import TestClient

USER_ID = "00000000-0000-0000-0000-000000000091"


def _profile(*, account_kind: Literal["guest", "registered"]) -> User:
    now = utcnow()
    return User(
        id=USER_ID,
        email=None if account_kind == "guest" else "member@example.com",
        username=None,
        display_name=None,
        language="en",
        locale="en-US",
        theme="dark",
        is_admin=False,
        created_at=now,
        updated_at=now,
    )


def _workspace(profile: User) -> GuestWorkspace:
    return GuestWorkspace(
        user_id=profile.id,
        conversation_id=None,
        status="active",
        created_at=profile.created_at,
        expires_at=profile.created_at + timedelta(days=7),
        claimed_by=None,
        claimed_at=None,
        updated_at=profile.created_at,
    )


def _gateway(
    *,
    account_kind: Literal["guest", "registered"],
    profile: User,
) -> MagicMock:
    gateway = MagicMock(spec=SupabaseGateway)
    gateway.get_auth_user_from_token.return_value = {
        "id": profile.id,
        "email": profile.email,
        "is_anonymous": account_kind == "guest",
    }
    gateway.get_or_create_profile_for_auth_user.return_value = profile
    gateway.get_active_guest_workspace.return_value = (
        _workspace(profile) if account_kind == "guest" else None
    )
    gateway.private_alpha_email_allowed.return_value = True

    def _create_collection(*, payload: dict[str, object], **_: object) -> Collection:
        now = utcnow()
        return Collection(
            id="collection-1",
            name=str(payload["name"]),
            name_source=str(payload["name_source"]),  # type: ignore[arg-type]
            created_at=now,
            updated_at=now,
        )

    def _create_strategy(*, payload: dict[str, object], **_: object) -> Strategy:
        now = utcnow()
        return Strategy(
            id="strategy-1",
            name=str(payload["name"]),
            name_source=str(payload["name_source"]),  # type: ignore[arg-type]
            template=str(payload["template"]),  # type: ignore[arg-type]
            asset_class=str(payload["asset_class"]),  # type: ignore[arg-type]
            symbols=list(payload["symbols"]),  # type: ignore[arg-type]
            parameters=dict(payload["parameters"]),  # type: ignore[arg-type]
            metrics_preferences=list(payload["metrics_preferences"]),  # type: ignore[arg-type]
            benchmark_symbol=str(payload.get("benchmark_symbol") or "SPY"),
            created_at=now,
            updated_at=now,
        )

    gateway.create_collection.side_effect = _create_collection
    gateway.create_strategy.side_effect = _create_strategy
    return gateway


@pytest.mark.parametrize("account_kind", ["guest", "registered"])
@pytest.mark.parametrize("entity_type", ["collection", "strategy"])
def test_hosted_entity_naming_uses_verified_account_traffic_scope(
    monkeypatch: pytest.MonkeyPatch,
    account_kind: Literal["guest", "registered"],
    entity_type: Literal["collection", "strategy"],
) -> None:
    profile = _profile(account_kind=account_kind)
    gateway = _gateway(account_kind=account_kind, profile=profile)
    observed_keys: list[str] = []
    expected_name = f"Scoped {entity_type}"

    def _suggest_name(**_: object) -> str:
        observed_keys.append(resolve_openrouter_api_key())
        return expected_name

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("NEXT_PUBLIC_MOCK_AUTH", "false")
    monkeypatch.setenv("ARGUS_MOCK_AUTH", "false")
    monkeypatch.setenv("OPENROUTER_API_KEY", "dev-only")
    monkeypatch.setenv("ARGUS_PROD_OPENROUTER_API_KEY", "registered-key")
    monkeypatch.setenv("ARGUS_GUEST_ACCESS_OPENROUTER_API_KEY", "guest-key")
    router_module = (
        collections_router if entity_type == "collection" else strategies_router
    )
    monkeypatch.setattr(router_module, "suggest_entity_name", _suggest_name)

    with (
        patch.object(api_state, "supabase_gateway", gateway),
        patch("argus.api.dependencies.auth_session_is_active", return_value=True),
    ):
        client = TestClient(app)
        if entity_type == "collection":
            response = client.post(
                "/api/v1/collections",
                json={},
                headers={"Authorization": "Bearer verified-token"},
            )
            entity = response.json().get("collection", {})
        else:
            response = client.post(
                "/api/v1/strategies",
                json={
                    "template": "buy_and_hold",
                    "asset_class": "equity",
                    "symbols": ["AAPL"],
                    "parameters": {},
                },
                headers={"Authorization": "Bearer verified-token"},
            )
            entity = response.json().get("strategy", {})

    assert response.status_code == 200, response.text
    assert entity["name"] == expected_name
    assert entity["name_source"] == "ai_generated"
    assert observed_keys == ["guest-key" if account_kind == "guest" else "registered-key"]
