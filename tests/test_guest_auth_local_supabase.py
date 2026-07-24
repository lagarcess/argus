"""Local-Supabase proof for real anonymous Auth identity persistence."""

from __future__ import annotations

import os
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import psycopg
import pytest
from argus.api import state as api_state
from argus.api.main import app
from argus.api.routers import auth as auth_router
from argus.domain.guest_cleanup import cleanup_expired_guest_workspaces
from argus.domain.supabase_gateway import SupabaseGateway
from fastapi.testclient import TestClient
from supabase_auth.errors import AuthApiError

from supabase import create_client

LOCAL_URL = os.getenv("ARGUS_LOCAL_SUPABASE_URL", "").strip()
LOCAL_ANON_KEY = os.getenv("ARGUS_LOCAL_SUPABASE_ANON_KEY", "").strip()
LOCAL_SERVICE_KEY = os.getenv("ARGUS_LOCAL_SUPABASE_SERVICE_ROLE_KEY", "").strip()
LOCAL_DATABASE_URL = os.getenv("ARGUS_DISPOSABLE_DATABASE_URL", "").strip()

pytestmark = pytest.mark.skipif(
    not all((LOCAL_URL, LOCAL_ANON_KEY, LOCAL_SERVICE_KEY, LOCAL_DATABASE_URL)),
    reason="local Supabase Auth proof is not configured",
)


def _gateway() -> SupabaseGateway:
    return SupabaseGateway(
        client=create_client(LOCAL_URL, LOCAL_SERVICE_KEY),
        auth_client=create_client(LOCAL_URL, LOCAL_ANON_KEY),
    )


def test_real_anonymous_identity_survives_reload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auth_router.reset_auth_attempt_limiter_for_tests()
    monkeypatch.setenv("ARGUS_GUEST_ACCESS_ENABLED", "true")
    monkeypatch.setenv("NEXT_PUBLIC_GUEST_ACCESS_ENABLED", "true")
    monkeypatch.setenv("ARGUS_PUBLIC_ACCOUNT_ACCESS_ENABLED", "false")
    monkeypatch.setenv("NEXT_PUBLIC_MOCK_AUTH", "false")
    monkeypatch.setenv("ARGUS_MOCK_AUTH", "false")
    gateway = _gateway()

    user_id: str | None = None
    try:
        with (
            patch.object(api_state, "supabase_gateway", gateway),
            patch.object(api_state, "DATABASE_URL", LOCAL_DATABASE_URL),
            TestClient(app) as client,
        ):
            created = client.post(
                "/api/v1/auth/guest",
                json={"captcha_token": "local-captcha-proof", "language": "en"},
                headers={"origin": "http://localhost:3000"},
            )
            assert created.status_code == 200
            user = created.json()["user"]
            user_id = str(user["id"])
            assert user["is_anonymous"] is True
            assert user.get("email") in {None, ""}
            assert client.cookies.get("sb-auth-token")

            reloaded = client.post(
                "/api/v1/auth/guest",
                json={"captcha_token": "local-captcha-proof", "language": "en"},
                headers={"origin": "http://localhost:3000"},
            )
            assert reloaded.status_code == 200
            assert reloaded.json()["reused"] is True
            assert reloaded.json()["user"]["id"] == user_id

            profile = gateway.get_user(user_id=user_id)
            workspace = gateway.get_active_guest_workspace(
                user_id=user_id,
                at=profile.created_at,
            )
            assert profile.email is None
            assert workspace is not None
            assert workspace.user_id == user_id
    finally:
        if user_id:
            gateway.delete_auth_user(user_id)


def test_expired_real_anonymous_session_renews_with_fresh_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auth_router.reset_auth_attempt_limiter_for_tests()
    monkeypatch.setenv("ARGUS_GUEST_ACCESS_ENABLED", "true")
    monkeypatch.setenv("NEXT_PUBLIC_GUEST_ACCESS_ENABLED", "true")
    monkeypatch.setenv("ARGUS_PUBLIC_ACCOUNT_ACCESS_ENABLED", "false")
    monkeypatch.setenv("NEXT_PUBLIC_MOCK_AUTH", "false")
    monkeypatch.setenv("ARGUS_MOCK_AUTH", "false")
    gateway = _gateway()
    expired_user_id: str | None = None
    renewed_user_id: str | None = None
    try:
        expired_auth = gateway.sign_in_anonymously(
            captcha_token="local-captcha-proof",
            language="en",
        )
        expired_user = expired_auth["user"]
        expired_user_id = str(expired_user["id"])
        expired_profile = gateway.get_or_create_profile_for_auth_user(expired_user)
        created_at = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(days=8)
        gateway.client.table("guest_workspaces").insert(
            {
                "user_id": expired_profile.id,
                "created_at": created_at.isoformat(),
            }
        ).execute()
        access_token = str(expired_auth["session"]["access_token"])

        with (
            patch.object(api_state, "supabase_gateway", gateway),
            patch.object(api_state, "DATABASE_URL", LOCAL_DATABASE_URL),
            TestClient(app) as client,
        ):
            client.cookies.set("sb-auth-token", access_token)
            renewed = client.post(
                "/api/v1/auth/guest",
                json={"captcha_token": "local-captcha-proof", "language": "en"},
                headers={"origin": "http://localhost:3000"},
            )

        assert renewed.status_code == 200
        assert renewed.json()["reused"] is False
        renewed_user = renewed.json()["user"]
        renewed_user_id = str(renewed_user["id"])
        assert renewed_user_id != expired_user_id
        assert renewed_user["is_anonymous"] is True
        assert renewed_user.get("email") in {None, ""}
        workspace = gateway.get_active_guest_workspace(
            user_id=renewed_user_id,
            at=datetime.now(timezone.utc),
        )
        assert workspace is not None
    finally:
        for user_id in (expired_user_id, renewed_user_id):
            if user_id:
                with suppress(Exception):
                    gateway.delete_auth_user(user_id)


def test_cleanup_deletes_real_anonymous_auth_user_through_admin() -> None:
    gateway = _gateway()
    auth_user_id: str | None = None
    aggregate_id: str | None = None
    try:
        auth_result = gateway.sign_in_anonymously(
            captcha_token="local-captcha-proof",
            language="en",
        )
        auth_user = auth_result["user"]
        auth_user_id = str(auth_user["id"])
        profile = gateway.get_or_create_profile_for_auth_user(auth_user)
        conversation = gateway.create_conversation(
            user_id=profile.id,
            title="expired guest proof",
            title_source="system_default",
            language="en",
        )
        gateway.client.table("messages").insert(
            {
                "conversation_id": conversation.id,
                "user_id": profile.id,
                "role": "user",
                "content": "private cleanup proof",
            }
        ).execute()
        gateway.client.table("backtest_runs").insert(
            {
                "user_id": profile.id,
                "conversation_id": conversation.id,
                "status": "completed",
                "asset_class": "equity",
                "symbols": ["AAPL"],
                "benchmark_symbol": "SPY",
                "config_snapshot": {},
            }
        ).execute()
        aggregate = (
            gateway.client.table("cost_ledger_entries")
            .insert(
                {
                    "source": "api_turn",
                    "service": "local-proof",
                    "provider": "local-proof",
                    "feature_area": "guest_cleanup",
                    "user_id": profile.id,
                    "conversation_id": conversation.id,
                    "correlation_id": f"guest-cleanup-{profile.id}",
                    "billable_unit": "unknown",
                    "status": "succeeded",
                }
            )
            .execute()
            .data[0]
        )
        aggregate_id = str(aggregate["id"])
        created_at = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(days=8)
        gateway.client.table("guest_workspaces").insert(
            {
                "user_id": profile.id,
                "conversation_id": conversation.id,
                "created_at": created_at.isoformat(),
                "expires_at": (created_at + timedelta(days=7)).isoformat(),
            }
        ).execute()

        result = cleanup_expired_guest_workspaces(
            gateway,
            limit=100,
            dry_run=False,
        )

        assert result.auth_deleted >= 1
        with pytest.raises(AuthApiError):
            gateway.client.auth.admin.get_user_by_id(auth_user_id)
        assert gateway.get_user(user_id=auth_user_id) is None
        for table in (
            "conversations",
            "messages",
            "backtest_runs",
            "guest_workspaces",
        ):
            assert (
                gateway.client.table(table)
                .select("*")
                .eq("user_id", auth_user_id)
                .execute()
                .data
                == []
            )
        preserved_aggregate = (
            gateway.client.table("cost_ledger_entries")
            .select("user_id,conversation_id")
            .eq("id", aggregate["id"])
            .single()
            .execute()
            .data
        )
        assert preserved_aggregate == {"user_id": None, "conversation_id": None}
    finally:
        if auth_user_id:
            with suppress(Exception):
                gateway.delete_auth_user(auth_user_id)
        if aggregate_id:
            with psycopg.connect(LOCAL_DATABASE_URL, autocommit=True) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "delete from public.cost_ledger_entries where id = %s",
                        (aggregate_id,),
                    )
