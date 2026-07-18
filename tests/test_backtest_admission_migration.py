"""#230 — contract guards for the atomic admission migration."""

from __future__ import annotations

from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "supabase"
    / "migrations"
    / "20260718000001_atomic_backtest_admission.sql"
)


def _text() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_migration_adds_reservation_identity_columns() -> None:
    text = _text()
    assert "add column if not exists operation_scope" in text
    assert "'chat.run_backtest'" in text and "'backtests.run'" in text
    assert "add column if not exists identity_hash" in text
    assert "alter column conversation_id drop not null" in text


def test_migration_owns_the_unique_reservation_boundary() -> None:
    text = _text()
    assert "drop index if exists idx_backtest_jobs_user_idempotency_key" in text
    assert "create unique index if not exists backtest_jobs_reservation_idx" in text
    assert "(user_id, operation_scope, idempotency_key)" in text


def test_admission_function_serializes_and_orders_decisions() -> None:
    text = _text()
    assert "create or replace function public.admit_backtest_job" in text
    assert "pg_advisory_xact_lock" in text

    replay = text.index("'replay'")
    conflict = text.index("'conflict'")
    allowance = text.index("'allowance_exhausted'")
    per_user = text.index("'per_user_capacity'")
    global_cap = text.index("'global_capacity'")
    admitted = text.index("'admitted'")
    assert replay < conflict < allowance < per_user < global_cap < admitted


def test_admission_function_charges_allowance_with_insert() -> None:
    text = _text()
    insert_job = text.index("insert into public.backtest_jobs")
    charge = text.index("insert into public.usage_counters")
    returning = text.index("'admitted'")
    assert insert_job < charge < returning
    assert "used_count = public.usage_counters.used_count + 1" in text


def test_admission_function_reconciles_stale_direct_jobs_bounded() -> None:
    text = _text()
    assert "interval '15 minutes'" in text
    assert "limit 20" in text
    assert "'direct_execution_abandoned'" in text
    assert "'execution_interrupted'" in text
    assert "order by started_at asc, id asc" in text


def test_admission_function_is_service_role_only() -> None:
    text = _text()
    assert "revoke all on function public.admit_backtest_job" in text
    assert "from public, anon, authenticated" in text
    assert "to service_role" in text
