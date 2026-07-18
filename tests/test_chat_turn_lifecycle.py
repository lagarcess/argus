"""#240 — durable chat-turn lifecycle: CAS semantics and reconciliation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from argus.api import state as api_state
from argus.api.main import app
from argus.api.message_store import memory_conversation, memory_message
from argus.domain import chat_turn_lifecycle as lifecycle
from argus.domain.store import AlphaStore
from fastapi.testclient import TestClient


def _accept(
    store: AlphaStore,
    *,
    turn_id: str = "turn-1",
    conversation_id: str = "conv-1",
    request_id: str = "req-1",
    accepted_ago_minutes: float = 0,
) -> dict:
    row = lifecycle.create_accepted_memory(
        store,
        turn_id=turn_id,
        user_id="user-1",
        conversation_id=conversation_id,
        request_id=request_id,
        now=datetime.now(timezone.utc) - timedelta(minutes=accepted_ago_minutes),
    )
    return row


def test_acceptance_is_idempotent_per_turn_id() -> None:
    store = AlphaStore()
    first = _accept(store)
    second = _accept(store)
    assert first["turn_id"] == second["turn_id"]
    assert len(store.chat_turn_lifecycles) == 1


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (("running",), "applied"),
        (("running", "completed"), "applied"),
        (("completed",), "applied"),
        (("recoverable_failed",), "applied"),
        (("running", "abandoned"), "applied"),
    ],
)
def test_allowed_transition_paths(path: tuple[str, ...], expected: str) -> None:
    store = AlphaStore()
    _accept(store)
    result = None
    for to_status in path:
        result = lifecycle.transition_memory(store, turn_id="turn-1", to_status=to_status)
    assert result is not None and result.outcome == expected


def test_terminal_rows_reject_conflicting_transitions() -> None:
    store = AlphaStore()
    _accept(store)
    lifecycle.transition_memory(store, turn_id="turn-1", to_status="recoverable_failed")

    late_success = lifecycle.transition_memory(
        store, turn_id="turn-1", to_status="completed"
    )
    assert late_success.outcome == "conflict"
    assert store.chat_turn_lifecycles["turn-1"]["status"] == "recoverable_failed"


def test_repeating_same_transition_with_same_links_is_noop() -> None:
    store = AlphaStore()
    _accept(store)
    first = lifecycle.transition_memory(
        store,
        turn_id="turn-1",
        to_status="completed",
        assistant_message_id="assistant-1",
    )
    replay = lifecycle.transition_memory(
        store,
        turn_id="turn-1",
        to_status="completed",
        assistant_message_id="assistant-1",
    )
    conflicting = lifecycle.transition_memory(
        store,
        turn_id="turn-1",
        to_status="completed",
        assistant_message_id="assistant-2",
    )
    assert first.outcome == "applied"
    assert replay.outcome == "noop"
    assert conflicting.outcome == "conflict"


def test_reconciled_requires_a_valid_outcome() -> None:
    store = AlphaStore()
    _accept(store)
    invalid = lifecycle.transition_memory(
        store, turn_id="turn-1", to_status="reconciled", reconciled_outcome="abandoned"
    )
    assert invalid.outcome == "invalid"


def _seed_conversation(store: AlphaStore, *, conversation_id: str = "conv-1") -> None:
    store.messages.setdefault(conversation_id, [])


class _Msg:
    def __init__(
        self,
        *,
        message_id: str,
        conversation_id: str,
        turn_id: str,
        request_id: str,
        status: str,
        created_at: datetime,
        terminal: bool = True,
    ) -> None:
        self.id = message_id
        self.conversation_id = conversation_id
        self.role = "assistant"
        self.created_at = created_at
        self.metadata = {
            "agent_runtime_turn": {
                "turn_id": turn_id,
                "request_id": request_id,
                "terminal": terminal,
                "status": status,
            }
        }


def test_reconciliation_prefers_failure_on_equal_timestamps() -> None:
    store = AlphaStore()
    _seed_conversation(store)
    _accept(store, accepted_ago_minutes=20)
    moment = datetime.now(timezone.utc)
    store.messages["conv-1"] = [
        _Msg(
            message_id="assistant-success",
            conversation_id="conv-1",
            turn_id="turn-1",
            request_id="req-1",
            status="succeeded",
            created_at=moment,
        ),
        _Msg(
            message_id="assistant-failure",
            conversation_id="conv-1",
            turn_id="turn-1",
            request_id="req-1",
            status="failed",
            created_at=moment,
        ),
    ]

    reconciled = lifecycle.reconcile_stale_turns_memory(store, conversation_id="conv-1")

    assert len(reconciled) == 1
    row = reconciled[0]
    assert row["status"] == "reconciled"
    assert row["reconciled_outcome"] == "recoverable_failed"
    assert row["assistant_message_id"] == "assistant-failure"


def test_reconciliation_ignores_other_turns_and_requests() -> None:
    store = AlphaStore()
    _seed_conversation(store)
    _accept(store, accepted_ago_minutes=20)
    moment = datetime.now(timezone.utc)
    store.messages["conv-1"] = [
        _Msg(
            message_id="assistant-other-turn",
            conversation_id="conv-1",
            turn_id="turn-OTHER",
            request_id="req-1",
            status="succeeded",
            created_at=moment,
        ),
        _Msg(
            message_id="assistant-other-request",
            conversation_id="conv-1",
            turn_id="turn-1",
            request_id="req-OTHER",
            status="succeeded",
            created_at=moment,
        ),
    ]

    reconciled = lifecycle.reconcile_stale_turns_memory(store, conversation_id="conv-1")

    assert len(reconciled) == 1
    row = reconciled[0]
    assert row["status"] == "abandoned"
    assert row["failure_code"] == "turn_abandoned"
    assert row["retryable"] is True


def test_fresh_rows_are_not_reconciled() -> None:
    store = AlphaStore()
    _seed_conversation(store)
    _accept(store, accepted_ago_minutes=5)
    reconciled = lifecycle.reconcile_stale_turns_memory(store, conversation_id="conv-1")
    assert reconciled == []
    assert store.chat_turn_lifecycles["turn-1"]["status"] == "accepted"


def test_reconciliation_batch_is_bounded_and_deterministic() -> None:
    store = AlphaStore()
    _seed_conversation(store)
    for index in range(25):
        _accept(
            store,
            turn_id=f"turn-{index:02d}",
            request_id=f"req-{index:02d}",
            accepted_ago_minutes=30 + index,
        )

    reconciled = lifecycle.reconcile_stale_turns_memory(store, conversation_id="conv-1")

    assert len(reconciled) == lifecycle.STALE_TURN_BATCH
    remaining = [
        row for row in store.chat_turn_lifecycles.values() if row["status"] == "accepted"
    ]
    assert len(remaining) == 5
    # Oldest stale_since first: the five freshest stale rows remain.
    assert sorted(row["turn_id"] for row in remaining) == [
        "turn-00",
        "turn-01",
        "turn-02",
        "turn-03",
        "turn-04",
    ]


# ── Choke-point wiring (memory mode) ──────────────────────────────────────────


@pytest.fixture()
def _memory_mode(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(api_state, "supabase_gateway", None)
    api_state.store.reset()
    yield


def test_user_message_acceptance_creates_lifecycle_row(_memory_mode) -> None:
    user_id = api_state.store.get_or_create_dev_user().id
    conversation = memory_conversation(
        user_id=user_id,
        title="Turn lane",
        title_source="system_default",
        language="en",
    )
    from argus.api.message_store import create_message

    message = create_message(
        user_id=user_id,
        conversation_id=conversation.id,
        role="user",
        content="test AAPL",
        metadata={
            "agent_runtime_turn": {
                "status": "started",
                "conversation_id": conversation.id,
                "request_id": "req-accept",
            }
        },
    )

    row = api_state.store.chat_turn_lifecycles.get(message.id)
    assert row is not None
    assert row["status"] == "accepted"
    assert row["request_id"] == "req-accept"


def test_run_backtest_actions_are_excluded_from_the_lifecycle(_memory_mode) -> None:
    user_id = api_state.store.get_or_create_dev_user().id
    conversation = memory_conversation(
        user_id=user_id,
        title="Run lane",
        title_source="system_default",
        language="en",
    )
    from argus.api.message_store import create_message

    create_message(
        user_id=user_id,
        conversation_id=conversation.id,
        role="user",
        content="Run backtest",
        metadata={
            "agent_runtime_turn": {
                "status": "started",
                "conversation_id": conversation.id,
                "request_id": "req-run",
            },
            "chat_action": {"type": "run_backtest"},
        },
    )

    assert api_state.store.chat_turn_lifecycles == {}


def test_terminal_assistant_message_completes_the_turn(_memory_mode) -> None:
    user_id = api_state.store.get_or_create_dev_user().id
    conversation = memory_conversation(
        user_id=user_id,
        title="Turn lane",
        title_source="system_default",
        language="en",
    )
    from argus.api.message_store import create_message

    user_message = create_message(
        user_id=user_id,
        conversation_id=conversation.id,
        role="user",
        content="test AAPL",
        metadata={
            "agent_runtime_turn": {
                "status": "started",
                "conversation_id": conversation.id,
                "request_id": "req-complete",
            }
        },
    )
    assistant = create_message(
        user_id=user_id,
        conversation_id=conversation.id,
        role="assistant",
        content="Done.",
        metadata={
            "agent_runtime_turn": {
                "status": "succeeded",
                "terminal": True,
                "conversation_id": conversation.id,
                "request_id": "req-complete",
            }
        },
    )

    row = api_state.store.chat_turn_lifecycles[user_message.id]
    assert row["status"] == "completed"
    assert row["assistant_message_id"] == assistant.id
    turn_metadata = assistant.metadata["agent_runtime_turn"]
    assert turn_metadata["turn_id"] == user_message.id


def test_get_messages_reconciles_stale_turns(_memory_mode) -> None:
    user_id = api_state.store.get_or_create_dev_user().id
    conversation = memory_conversation(
        user_id=user_id,
        title="Turn lane",
        title_source="system_default",
        language="en",
    )
    lifecycle.create_accepted_memory(
        api_state.store,
        turn_id="stale-turn",
        user_id=user_id,
        conversation_id=conversation.id,
        request_id="req-stale",
        now=datetime.now(timezone.utc) - timedelta(minutes=30),
    )
    memory_message(
        conversation_id=conversation.id,
        role="assistant",
        content="Recovered earlier.",
        metadata={
            "agent_runtime_turn": {
                "turn_id": "stale-turn",
                "request_id": "req-stale",
                "terminal": True,
                "status": "failed",
            }
        },
    )

    response = TestClient(app).get(f"/api/v1/conversations/{conversation.id}/messages")
    assert response.status_code == 200

    row = api_state.store.chat_turn_lifecycles["stale-turn"]
    assert row["status"] == "reconciled"
    assert row["reconciled_outcome"] == "recoverable_failed"
