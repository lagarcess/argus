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


def test_stale_reconciliation_checks_the_finalized_tuple_first() -> None:
    text = _text()
    assert "create or replace function public.finalized_direct_run_id" in text
    assert "uuid_generate_v5" in text
    assert "'https://argus.app/backtest-finalization/'" in text
    assert "'/api/v1/backtests/run:'" in text

    # Both stale paths resolve the finalized tuple before any abandon update.
    replay_branch = text.index("Evidence order: the finalized Run/evidence tuple")
    replay_lookup = text.index("public.finalized_direct_run_id(", replay_branch)
    replay_abandon = text.index("'direct_execution_abandoned'", replay_branch)
    assert replay_lookup < replay_abandon

    bounded_pass = text.index("select public.finalized_direct_run_id(j.user_id")
    bounded_abandon = text.index("'direct_execution_abandoned'", bounded_pass)
    assert bounded_pass < bounded_abandon
    assert text.count("status = 'succeeded'") >= 2


def test_admission_function_is_service_role_only() -> None:
    text = _text()
    assert "revoke all on function public.admit_backtest_job" in text
    assert "from public, anon, authenticated" in text
    assert "to service_role" in text


SUCCESS_MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "supabase"
    / "migrations"
    / "20260718000004_finalize_direct_backtest_success.sql"
)


def _success_text() -> str:
    return SUCCESS_MIGRATION.read_text(encoding="utf-8")


def test_direct_success_finalization_is_one_locked_transaction() -> None:
    """#230: lock and verify the owner-scoped job, branch on its state, then
    compose the canonical tuple writer and succeed the job in one function."""

    text = _success_text()
    assert "create or replace function public.finalize_direct_backtest_success" in text
    lock = text.index("for update")
    missing = text.index("'missing'")
    superseded = text.index("'superseded'")
    compose = text.index("from public.finalize_backtest_completion(")
    succeed = text.index("set status = 'succeeded'")
    assert lock < missing < superseded < compose < succeed
    # The owner scope is part of the locked lookup, not a later filter.
    assert text.index("and user_id = p_user_id") < lock


def test_direct_success_terminal_branch_creates_nothing() -> None:
    text = _success_text()
    superseded = text.index("'superseded'")
    compose = text.index("from public.finalize_backtest_completion(")
    # The superseded return precedes tuple creation: reconciliation's win
    # yields the terminal job untouched and no Run.
    assert superseded < compose
    assert "status not in ('queued', 'running')" in text


def test_direct_success_function_is_service_role_only() -> None:
    text = _success_text()
    assert (
        "revoke all on function public.finalize_direct_backtest_success" in text
    )
    assert "from public, anon, authenticated" in text
    assert "to service_role" in text
