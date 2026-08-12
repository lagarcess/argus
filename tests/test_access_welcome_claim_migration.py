"""Static contract proof for the durable access-welcome claim migration."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _normalized_sql() -> str:
    migrations = sorted(
        (ROOT / "supabase" / "migrations").glob("*_claim_access_welcome_delivery.sql")
    )
    assert len(migrations) == 1
    return re.sub(r"\s+", " ", migrations[0].read_text()).strip().lower()


def test_claim_migration_is_private_fixed_and_service_owned() -> None:
    sql = _normalized_sql()

    assert "create table public.private_alpha_access_welcome_claims" in sql
    assert "recipient_email text primary key" in sql
    assert "claim_token uuid not null unique" in sql
    assert "claimed_at timestamptz not null default now()" in sql
    assert "consumed_at timestamptz" in sql
    assert "content_version = 'private-alpha-access-welcome/v1'" in sql
    assert "enable row level security" in sql
    assert "from public, anon, authenticated, service_role" in sql
    assert "create policy" not in sql
    assert (
        "grant select"
        not in sql.split(
            "create or replace function public.claim_private_alpha_access_welcome", 1
        )[0]
    )


def test_claim_rpc_locks_and_revalidates_before_allowing_send() -> None:
    sql = _normalized_sql()
    function_sql = sql.split(
        "create or replace function public.claim_private_alpha_access_welcome", 1
    )[1].split("revoke all on function", 1)[0]

    assert "security definer" in function_sql
    assert "set search_path = ''" in function_sql
    assert "from public.private_alpha_allowlist" in function_sql
    assert "for update" in function_sql
    assert "v_role is distinct from 'requested'" in function_sql
    assert "v_disabled_at is not null" in function_sql
    assert "p_language is distinct from v_language" in function_sql
    assert "interval '24 hours'" in function_sql
    assert "claim_token" in function_sql
    assert "claimed_at" in function_sql


def test_completion_requires_and_consumes_claim_in_atomic_transition() -> None:
    sql = _normalized_sql()
    function_sql = sql.split(
        "create or replace function public.complete_private_alpha_access_welcome", 1
    )[1].split("revoke all on function", 1)[0]

    assert "p_claim_token uuid" in function_sql
    assert "for update" in function_sql
    assert "insert into public.private_alpha_access_welcome_deliveries" in function_sql
    assert "update public.private_alpha_access_welcome_claims" in function_sql
    assert "set consumed_at = now()" in function_sql
    assert "update public.private_alpha_allowlist" in function_sql
    insert_index = function_sql.index(
        "insert into public.private_alpha_access_welcome_deliveries"
    )
    first_send_consumption_index = function_sql.rindex("set consumed_at = now()")
    assert insert_index < first_send_consumption_index
    assert first_send_consumption_index < function_sql.index(
        "update public.private_alpha_allowlist"
    )


def test_pending_claim_freezes_allowlist_and_old_completion_is_removed() -> None:
    sql = _normalized_sql()

    assert "guard_private_alpha_access_welcome_claim" in sql
    assert "before update or delete on public.private_alpha_allowlist" in sql
    assert "consumed_at is null" in sql
    assert (
        "drop function public.complete_private_alpha_access_welcome( "
        "text, text, text, text, text )"
    ) in sql
    assert (
        "grant execute on function public.claim_private_alpha_access_welcome( "
        "text, text, text, text ) to service_role"
    ) in sql
    assert (
        "grant execute on function public.complete_private_alpha_access_welcome( "
        "text, text, text, text, text, uuid ) to service_role"
    ) in sql
