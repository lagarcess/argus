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


def test_lifecycle_table_matches_the_data_model() -> None:
    """DATA_MODEL 8.1: turn_id references the accepted messages.id; one
    terminal assistant message cannot settle two turns; retryable is
    non-null defaulting false; reconciled_outcome exists exactly for
    reconciled; abandoned has no assistant link; the approved timestamp
    fields are terminal_at/reconciled_at, never finished_at."""

    text = _text()
    assert "turn_id uuid primary key references public.messages(id)" in text
    assert "create unique index" in text
    assert "assistant_message_id" in text
    assert "where assistant_message_id is not null" in text
    assert "retryable boolean not null default false" in text
    assert "(status = 'reconciled') = (reconciled_outcome is not null)" in text
    assert "status <> 'abandoned' or assistant_message_id is null" in text
    assert "terminal_at timestamptz" in text
    assert "reconciled_at timestamptz" in text
    assert "finished_at" not in text


def test_boundaries_use_the_approved_timestamp_fields() -> None:
    text = _boundaries_text()
    assert "finished_at" not in text
    assert "terminal_at = v_now" in text
    assert "reconciled_at = v_now" in text


def test_cas_function_verifies_source_state_and_is_service_role_only() -> None:
    text = _text()
    assert "create or replace function public.transition_chat_turn_lifecycle" in text
    assert "for update" in text
    assert "'noop'" in text and "'conflict'" in text and "'invalid'" in text
    assert "revoke all on function public.transition_chat_turn_lifecycle" in text
    assert "to service_role" in text


def test_cas_noop_comparison_includes_failure_evidence() -> None:
    """DATA_MODEL: the same-transition no-op comparison covers the assistant
    link, reconciliation outcome, failure code, and retryable — different
    terminal failure truth conflicts."""

    text = _text()
    noop_start = text.index("if v_row.status = p_to_status")
    noop_block = text[noop_start : text.index("'noop'", noop_start)]
    assert "assistant_message_id" in noop_block
    assert "reconciled_outcome" in noop_block
    # Exact null-safe truth, never omitted-value wildcards: failure_code
    # compares IS NOT DISTINCT FROM and retryable compares effective false.
    assert "p_failure_code is not distinct from v_row.failure_code" in noop_block
    assert (
        "coalesce(p_retryable, false) = coalesce(v_row.retryable, false)"
        in noop_block
    )
    assert "p_failure_code is null\n" not in noop_block


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


def test_reconciliation_is_owner_scoped() -> None:
    """#240: the RPC carries the requesting user, rejects an unowned
    conversation before touching any row, scopes stale selection to the
    owner, and requires the evidence message's own user_id to match."""

    text = _boundaries_text()
    start = text.index("create or replace function public.reconcile_stale_chat_turns")
    body = text[start:]
    assert "p_user_id uuid" in body
    assert "conversation is not owned by the reconciling user" in body
    assert "and user_id = p_user_id" in body
    assert "m.user_id = v_row.user_id" in body


def test_reconciliation_copies_failure_evidence() -> None:
    """A reconciled recoverable failure carries the winning message's
    canonical failure_code and retryable evidence onto the lifecycle row."""

    text = _boundaries_text()
    evidence_start = text.index(
        "m.metadata->'agent_runtime_turn'->>'status' as turn_status"
    )
    reconciled_update = text.index("set status = 'reconciled'")
    assert "failure_code" in text[evidence_start:reconciled_update]
    reconciled_block = text[
        reconciled_update : text.index("returning * into v_row", reconciled_update)
    ]
    assert "failure_code = case" in reconciled_block
    assert "retryable = case" in reconciled_block
    assert "v_evidence.failure_code" in reconciled_block
    assert "v_evidence.retryable" in reconciled_block


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
