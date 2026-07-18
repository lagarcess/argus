"""#240 — the production Supabase path for the turn lifecycle is real.

The route hooks must invoke concrete gateway operations in Supabase mode;
optional-attribute fallbacks that silently skip are the defect under test.
Real-database proof stays an external gate; these tests pin the wiring.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from argus.api import state as api_state
from argus.api.chat import turn_lifecycle_hooks
from argus.domain.supabase_gateway import SupabaseGateway


@pytest.fixture()
def gateway_client() -> MagicMock:
    client = MagicMock()
    table = MagicMock()
    client.table.return_value = table
    for chained in ("select", "eq", "in_", "or_", "order", "limit", "upsert", "insert"):
        getattr(table, chained).return_value = table
    table.execute.return_value = SimpleNamespace(data=[])
    client.rpc.return_value.execute.return_value = SimpleNamespace(
        data={"outcome": "applied", "row": {"turn_id": "turn-1"}}
    )
    return client


def test_gateway_create_upserts_the_accepted_row(gateway_client: MagicMock) -> None:
    gateway = SupabaseGateway(client=gateway_client)
    gateway.create_chat_turn_lifecycle(
        turn_id="turn-1",
        user_id="user-1",
        conversation_id="conv-1",
        request_id="req-1",
    )

    gateway_client.table.assert_any_call("chat_turn_lifecycles")
    upsert_args = gateway_client.table.return_value.upsert.call_args
    assert upsert_args is not None
    payload = upsert_args.args[0]
    assert payload["turn_id"] == "turn-1"
    assert payload["status"] == "accepted"
    assert upsert_args.kwargs.get("on_conflict") == "turn_id"


def test_gateway_transition_calls_the_cas_function(gateway_client: MagicMock) -> None:
    gateway = SupabaseGateway(client=gateway_client)
    result = gateway.transition_chat_turn_lifecycle(
        turn_id="turn-1",
        to_status="completed",
        assistant_message_id="assistant-1",
    )

    gateway_client.rpc.assert_called_once()
    name, params = gateway_client.rpc.call_args.args
    assert name == "transition_chat_turn_lifecycle"
    assert params["p_turn_id"] == "turn-1"
    assert params["p_to_status"] == "completed"
    assert params["p_assistant_message_id"] == "assistant-1"
    assert result["outcome"] == "applied"


def test_gateway_find_active_turn_selects_accepted_or_running(
    gateway_client: MagicMock,
) -> None:
    table = gateway_client.table.return_value
    table.execute.return_value = SimpleNamespace(
        data=[{"turn_id": "turn-1", "status": "accepted"}]
    )
    gateway = SupabaseGateway(client=gateway_client)

    row = gateway.find_active_chat_turn(
        conversation_id="conv-1",
        request_id="req-1",
        user_id="user-1",
    )

    assert row == {"turn_id": "turn-1", "status": "accepted"}
    table.eq.assert_any_call("user_id", "user-1")
    table.in_.assert_any_call("status", ["accepted", "running"])


def test_gateway_accept_chat_turn_calls_the_atomic_function(
    gateway_client: MagicMock,
) -> None:
    gateway_client.rpc.return_value.execute.return_value = SimpleNamespace(
        data={
            "id": "message-1",
            "conversation_id": "conv-1",
            "role": "user",
            "content": "test AAPL",
            "created_at": "2026-07-18T00:00:00+00:00",
            "metadata": {},
        }
    )
    gateway = SupabaseGateway(client=gateway_client)

    row = gateway.accept_chat_turn(
        user_id="user-1",
        conversation_id="conv-1",
        role="user",
        content="test AAPL",
        metadata={},
        request_id="req-1",
    )

    name, params = gateway_client.rpc.call_args.args
    assert name == "accept_chat_turn"
    assert params["p_user_id"] == "user-1"
    assert params["p_request_id"] == "req-1"
    # Composing the canonical append boundary requires the writer's full
    # identity inputs: message id, created_at, and the computed preview.
    assert params["p_message_id"]
    assert params["p_created_at"]
    assert params["p_preview"] == "test AAPL"
    assert row["id"] == "message-1"


def test_gateway_lists_projectable_turns_scoped_to_the_page(
    gateway_client: MagicMock,
) -> None:
    """Projection truth is owner-scoped and keyed by the read's message ids —
    abandoned rows via turn_id, reconciled rows via assistant_message_id —
    with terminal statuses only and no historical row cap."""

    table = gateway_client.table.return_value
    table.execute.return_value = SimpleNamespace(
        data=[{"turn_id": "turn-1", "status": "abandoned"}]
    )
    gateway = SupabaseGateway(client=gateway_client)

    rows = gateway.list_projectable_chat_turns(
        conversation_id="conv-1",
        user_id="user-1",
        message_ids=["msg-1", "msg-2"],
    )

    assert rows == [{"turn_id": "turn-1", "status": "abandoned"}]
    table.eq.assert_any_call("user_id", "user-1")
    table.in_.assert_any_call("status", ["abandoned", "reconciled"])
    table.or_.assert_any_call(
        "turn_id.in.(msg-1,msg-2),assistant_message_id.in.(msg-1,msg-2)"
    )
    table.limit.assert_not_called()


# ── Hook wiring: Supabase mode must hit the production gateway path ──────────


def test_accept_turn_invokes_the_production_gateway(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = MagicMock(spec=SupabaseGateway)
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)

    turn_lifecycle_hooks.accept_turn(
        turn_id="turn-1",
        user_id="user-1",
        conversation_id="conv-1",
        request_id="req-1",
    )

    gateway.create_chat_turn_lifecycle.assert_called_once_with(
        turn_id="turn-1",
        user_id="user-1",
        conversation_id="conv-1",
        request_id="req-1",
    )


def test_transition_turn_invokes_the_production_gateway(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = MagicMock(spec=SupabaseGateway)
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)

    turn_lifecycle_hooks.transition_turn(
        turn_id="turn-1",
        to_status="completed",
        assistant_message_id="assistant-1",
    )

    gateway.transition_chat_turn_lifecycle.assert_called_once_with(
        turn_id="turn-1",
        to_status="completed",
        assistant_message_id="assistant-1",
        failure_code=None,
        retryable=None,
    )


def test_reconcile_hook_invokes_the_production_gateway(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = MagicMock(spec=SupabaseGateway)
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)

    turn_lifecycle_hooks.reconcile_conversation_turns(
        conversation_id="conv-1",
        user_id="user-1",
    )

    gateway.reconcile_stale_chat_turns.assert_called_once_with(
        conversation_id="conv-1",
        user_id="user-1",
    )


def test_terminal_metadata_enrichment_uses_the_production_finder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api.message_store import _attach_turn_lifecycle_identity

    gateway = MagicMock(spec=SupabaseGateway)
    gateway.find_active_chat_turn.return_value = {
        "turn_id": "turn-9",
        "user_id": "user-1",
    }
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)

    enriched = _attach_turn_lifecycle_identity(
        user_id="user-1",
        conversation_id="conv-1",
        role="assistant",
        metadata={
            "agent_runtime_turn": {
                "status": "succeeded",
                "terminal": True,
                "request_id": "req-9",
            }
        },
    )

    gateway.find_active_chat_turn.assert_called_once_with(
        conversation_id="conv-1", request_id="req-9", user_id="user-1"
    )
    assert enriched["agent_runtime_turn"]["turn_id"] == "turn-9"
