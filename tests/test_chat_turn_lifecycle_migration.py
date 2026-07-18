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


BOUNDARIES_MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "supabase"
    / "migrations"
    / "20260718000003_chat_turn_acceptance_and_reconciliation.sql"
)


def _boundaries_text() -> str:
    return BOUNDARIES_MIGRATION.read_text(encoding="utf-8")


def test_acceptance_is_one_database_owned_transaction() -> None:
    text = _boundaries_text()
    assert "create or replace function public.accept_chat_turn" in text
    assert "insert into public.chat_turn_lifecycles" in text
    assert "revoke all on function public.accept_chat_turn" in text
    assert "to service_role" in text


def test_acceptance_composes_the_canonical_append_boundary() -> None:
    """The accepted user message persists through append_conversation_message
    (identity, user_id, monotonic created_at, preview, conversation
    updated_at, replay) — never a second messages writer — and the lifecycle
    row lands in the same transaction, idempotent per turn."""

    text = _boundaries_text()
    assert "from public.append_conversation_message(" in text
    assert "insert into public.messages" not in text
    assert text.index("public.append_conversation_message(") < text.index(
        "insert into public.chat_turn_lifecycles"
    )
    assert "on conflict (turn_id) do nothing" in text


def test_reconciliation_boundary_is_database_owned() -> None:
    text = _boundaries_text()
    assert "create or replace function public.reconcile_stale_chat_turns" in text
    assert "interval '15 minutes'" in text
    assert "order by coalesce(running_at, accepted_at) asc, turn_id asc" in text
    assert "limit 20" in text
    assert "for update" in text
    # Post-lock stale recheck spares a freshly running turn.
    assert "coalesce(v_row.running_at, v_row.accepted_at) > v_cutoff" in text
    # Complete evidence predicate: owner join, turn/request identity, terminal.
    assert "join public.conversations c on c.id = m.conversation_id" in text
    assert "c.user_id = v_row.user_id" in text
    assert "m.metadata->'agent_runtime_turn'->>'turn_id' = v_row.turn_id::text" in text
    assert (
        "m.metadata->'agent_runtime_turn'->>'request_id' = v_row.request_id" in text
    )
    assert "(m.metadata->'agent_runtime_turn'->>'terminal')::boolean is true" in text
    # Failure precedence on equal timestamps, then id.
    assert "in ('recoverable_failed', 'failed') then 0 else 1 end asc" in text
    assert "'turn_abandoned'" in text
    assert "revoke all on function public.reconcile_stale_chat_turns" in text


def test_stale_index_matches_the_reconciliation_order() -> None:
    text = _text()
    assert "coalesce(running_at, accepted_at) asc, turn_id asc" in text
    assert "where status in ('accepted', 'running')" in text
