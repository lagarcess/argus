"""#240 — contract guards for the chat_turn_lifecycles migration."""

from __future__ import annotations

from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "supabase"
    / "migrations"
    / "20260718000002_add_chat_turn_lifecycles.sql"
)


def _text() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_lifecycle_table_owns_the_six_states() -> None:
    text = _text()
    for state in (
        "'accepted'",
        "'running'",
        "'completed'",
        "'recoverable_failed'",
        "'abandoned'",
        "'reconciled'",
    ):
        assert state in text
    assert "reconciled_outcome in ('completed', 'recoverable_failed')" in text


def test_lifecycle_rows_are_owner_readable_and_service_writable() -> None:
    text = _text()
    assert "enable row level security" in text
    assert "chat_turn_lifecycles_select_own" in text
    assert "auth.uid() = user_id" in text
    assert "revoke insert, update, delete on public.chat_turn_lifecycles" in text


def test_cas_function_verifies_source_state_and_is_service_role_only() -> None:
    text = _text()
    assert "create or replace function public.transition_chat_turn_lifecycle" in text
    assert "for update" in text
    assert "'noop'" in text and "'conflict'" in text and "'invalid'" in text
    assert "revoke all on function public.transition_chat_turn_lifecycle" in text
    assert "to service_role" in text


def test_stale_index_matches_the_reconciliation_order() -> None:
    text = _text()
    assert "coalesce(running_at, accepted_at) asc, turn_id asc" in text
    assert "where status in ('accepted', 'running')" in text
