"""Theme is a browser preference, and the account does not hold one.

next-themes keeps the choice in the browser under `argus-theme`, and
`profiles` has no `theme` column.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import yaml
from argus.api import state as api_state
from argus.api.main import app
from argus.api.schemas import GuestUser, ProfilePatch, User
from argus.domain.supabase_gateway import SupabaseGateway
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
PROFILE_MODELS = (User, GuestUser, ProfilePatch)


@pytest.fixture(autouse=True)
def _memory_store(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(api_state, "supabase_gateway", None)
    yield


def _client() -> TestClient:
    client = TestClient(app)
    client.post("/api/v1/dev/reset")
    return client


def _row(user_id: str) -> dict[str, object]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": user_id,
        "email": "a@b.c",
        "created_at": now,
        "updated_at": now,
    }


@pytest.mark.parametrize("model", PROFILE_MODELS, ids=lambda model: model.__name__)
def test_no_profile_model_declares_a_theme(model: type) -> None:
    assert "theme" not in model.model_fields


def test_the_contract_declares_no_theme() -> None:
    schemas = yaml.safe_load(
        (ROOT / "docs" / "api" / "openapi.yaml").read_text(encoding="utf-8")
    )["components"]["schemas"]

    for model in PROFILE_MODELS:
        assert "theme" not in schemas[model.__name__]["properties"]


def test_patch_me_ignores_a_theme_and_saves_the_rest() -> None:
    # Ignored like any field the patch does not declare, so a tab loaded before
    # this change keeps saving instead of meeting a 422.
    client = _client()

    alone = client.patch("/api/v1/me", json={"theme": "light"})
    assert alone.status_code == 200
    assert "theme" not in alone.json()["user"]

    mixed = client.patch(
        "/api/v1/me",
        json={"theme": "light", "language": "es-419", "locale": "es-419"},
    )
    assert mixed.status_code == 200
    assert mixed.json()["user"]["language"] == "es-419"
    assert "theme" not in mixed.json()["user"]
    assert "theme" not in client.get("/api/v1/me").json()["user"]


def test_a_new_profile_is_created_without_a_theme() -> None:
    client = MagicMock()
    client.table.return_value.upsert.return_value.execute.return_value = SimpleNamespace(
        data=[_row("user-9")]
    )
    gateway = SupabaseGateway(client=client)
    gateway.private_alpha_role_for_email = MagicMock(return_value="user")
    gateway.get_user = MagicMock(return_value=None)

    gateway.get_or_create_profile_for_auth_user({"id": "user-9", "email": "a@b.c"})

    assert "theme" not in client.table.return_value.upsert.call_args.args[0]


def test_the_mock_user_is_created_without_a_theme() -> None:
    client = MagicMock()
    client.auth.admin.create_user.return_value = SimpleNamespace(
        user=SimpleNamespace(id="user-9")
    )
    profiles = client.table.return_value
    lookup = profiles.select.return_value.eq.return_value
    lookup.limit.return_value.execute.return_value = SimpleNamespace(data=[])
    lookup.single.return_value.execute.return_value = SimpleNamespace(data=_row("user-9"))
    gateway = SupabaseGateway(
        client=client,
        mock_user_email="developer@argus.local",
        mock_user_password="password",
    )

    gateway.get_or_create_mock_user()

    assert "theme" not in profiles.upsert.call_args.args[0]
