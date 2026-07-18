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
        user_id: str | None = None,
    ) -> None:
        self.id = message_id
        self.conversation_id = conversation_id
        self.role = "assistant"
        self.created_at = created_at
        if user_id is not None:
            self.user_id = user_id
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


def test_lifecycle_creation_failure_cannot_orphan_the_accepted_message(
    _memory_mode, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acceptance is one boundary: if the lifecycle row cannot be created,
    the user message must not remain durably accepted without it."""

    user_id = api_state.store.get_or_create_dev_user().id
    conversation = memory_conversation(
        user_id=user_id,
        title="Atomic accept",
        title_source="system_default",
        language="en",
    )
    from argus.api.message_store import create_message

    def _boom(*args: object, **kwargs: object) -> object:
        raise RuntimeError("lifecycle write failed")

    monkeypatch.setattr(lifecycle, "create_accepted_memory", _boom)

    with pytest.raises(RuntimeError):
        create_message(
            user_id=user_id,
            conversation_id=conversation.id,
            role="user",
            content="test AAPL",
            metadata={
                "agent_runtime_turn": {
                    "status": "started",
                    "conversation_id": conversation.id,
                    "request_id": "req-atomic",
                }
            },
        )

    assert api_state.store.messages.get(conversation.id, []) == []
    assert api_state.store.chat_turn_lifecycles == {}


def test_cross_owner_terminal_evidence_is_rejected() -> None:
    """Evidence in a conversation the lifecycle owner does not own must never
    reconcile the row; with no owned evidence the turn abandons."""

    store = AlphaStore()
    _seed_conversation(store)
    store.conversation_owners["conv-1"] = "someone-else"
    _accept(store, accepted_ago_minutes=20)
    store.messages["conv-1"] = [
        _Msg(
            message_id="assistant-foreign",
            conversation_id="conv-1",
            turn_id="turn-1",
            request_id="req-1",
            status="succeeded",
            created_at=datetime.now(timezone.utc),
        )
    ]

    reconciled = lifecycle.reconcile_stale_turns_memory(store, conversation_id="conv-1")

    assert len(reconciled) == 1
    assert reconciled[0]["status"] == "abandoned"
    assert reconciled[0]["failure_code"] == "turn_abandoned"


def test_foreign_message_user_cannot_qualify_as_evidence() -> None:
    """A message whose user_id differs from the lifecycle owner is never
    terminal evidence, even inside the owner's conversation."""

    store = AlphaStore()
    _seed_conversation(store)
    store.conversation_owners["conv-1"] = "user-1"
    _accept(store, accepted_ago_minutes=20)
    store.messages["conv-1"] = [
        _Msg(
            message_id="assistant-intruder",
            conversation_id="conv-1",
            turn_id="turn-1",
            request_id="req-1",
            status="succeeded",
            created_at=datetime.now(timezone.utc),
            user_id="intruder-9",
        )
    ]

    reconciled = lifecycle.reconcile_stale_turns_memory(store, conversation_id="conv-1")

    assert len(reconciled) == 1
    assert reconciled[0]["status"] == "abandoned"
    assert reconciled[0]["failure_code"] == "turn_abandoned"


def test_unauthorized_get_cannot_trigger_reconciliation(_memory_mode) -> None:
    """#240: reconciliation never runs before route ownership succeeds — an
    unauthorized reader's GET must not mutate the owner's lifecycle rows."""

    api_state.store.get_or_create_dev_user()
    foreign_owner = "11111111-1111-1111-1111-111111111111"
    conversation = memory_conversation(
        user_id=foreign_owner,
        title="Not yours",
        title_source="system_default",
        language="en",
    )
    lifecycle.create_accepted_memory(
        api_state.store,
        turn_id="foreign-stale-turn",
        user_id=foreign_owner,
        conversation_id=conversation.id,
        request_id="req-foreign",
        now=datetime.now(timezone.utc) - timedelta(minutes=30),
    )

    response = TestClient(app).get(f"/api/v1/conversations/{conversation.id}/messages")

    assert response.status_code == 404
    row = api_state.store.chat_turn_lifecycles["foreign-stale-turn"]
    assert row["status"] == "accepted"


def test_gateway_reconcile_recheck_spares_a_freshly_running_turn() -> None:
    """A row that went running with a fresh clock after the stale read must
    not be abandoned from that stale earlier read."""

    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from argus.domain.supabase_gateway import SupabaseGateway

    client = MagicMock()
    client.rpc.return_value.execute.return_value = SimpleNamespace(
        data={"reconciled": []}
    )
    gateway = SupabaseGateway(client=client)

    gateway.reconcile_stale_chat_turns(conversation_id="conv-1", user_id="user-1")

    # The reconciliation boundary is database-owned: one RPC, where the
    # database clock, row locks, and the post-lock stale recheck live, and it
    # is owner-scoped by the requesting user.
    client.rpc.assert_called_once()
    name, params = client.rpc.call_args.args
    assert name == "reconcile_stale_chat_turns"
    assert params == {"p_conversation_id": "conv-1", "p_user_id": "user-1"}
    client.table.assert_not_called()


def test_abandoned_lifecycle_projects_typed_recovery_on_get(_memory_mode) -> None:
    user_id = api_state.store.get_or_create_dev_user().id
    conversation = memory_conversation(
        user_id=user_id,
        title="Projection",
        title_source="system_default",
        language="en",
    )
    from argus.api.message_store import create_message

    user_message = create_message(
        user_id=user_id,
        conversation_id=conversation.id,
        role="user",
        content="test AAPL momentum",
        metadata={
            "agent_runtime_turn": {
                "status": "started",
                "conversation_id": conversation.id,
                "request_id": "req-project",
            }
        },
    )
    row = api_state.store.chat_turn_lifecycles[user_message.id]
    row["accepted_at"] = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()

    response = TestClient(app).get(f"/api/v1/conversations/{conversation.id}/messages")
    assert response.status_code == 200
    items = response.json()["items"]

    user_index = next(
        index for index, item in enumerate(items) if item["id"] == user_message.id
    )
    projection = items[user_index + 1]
    assert projection["role"] == "assistant"
    turn = projection["metadata"]["agent_runtime_turn"]
    assert turn["status"] == "abandoned"
    assert turn["terminal"] is True
    assert turn["turn_id"] == user_message.id
    assert projection["metadata"]["failure_code"] == "turn_abandoned"
    assert projection["metadata"]["retryable"] is True
    assert projection["metadata"]["retry_last_turn"] == {"message": "test AAPL momentum"}
    # Immutable messages were not mutated: the projection is ephemeral.
    persisted_ids = {message.id for message in api_state.store.messages[conversation.id]}
    assert projection["id"] not in persisted_ids


def test_multi_turn_abandoned_recovery_stays_adjacent(_memory_mode) -> None:
    """#240: the typed recovery item sits directly after its owning user
    message even when later turns exist — never re-sorted to the end by its
    reconciliation timestamp."""

    user_id = api_state.store.get_or_create_dev_user().id
    conversation = memory_conversation(
        user_id=user_id,
        title="Adjacency",
        title_source="system_default",
        language="en",
    )
    from argus.api.message_store import create_message

    abandoned_user_message = create_message(
        user_id=user_id,
        conversation_id=conversation.id,
        role="user",
        content="first idea that stalled",
        metadata={
            "agent_runtime_turn": {
                "status": "started",
                "conversation_id": conversation.id,
                "request_id": "req-stalled",
            }
        },
    )
    row = api_state.store.chat_turn_lifecycles[abandoned_user_message.id]
    row["accepted_at"] = (
        datetime.now(timezone.utc) - timedelta(minutes=30)
    ).isoformat()
    # A later, healthy turn follows before anyone reloads.
    later_user = memory_message(
        conversation_id=conversation.id,
        role="user",
        content="second idea",
    )
    later_assistant = memory_message(
        conversation_id=conversation.id,
        role="assistant",
        content="Answer to the second idea.",
    )

    response = TestClient(app).get(f"/api/v1/conversations/{conversation.id}/messages")
    assert response.status_code == 200
    items = response.json()["items"]

    ids = [item["id"] for item in items]
    owner_index = ids.index(abandoned_user_message.id)
    projection = items[owner_index + 1]
    assert projection["metadata"].get("turn_lifecycle_projection") is True
    assert projection["metadata"]["agent_runtime_turn"]["turn_id"] == (
        abandoned_user_message.id
    )
    # The later turn stays after the recovery item.
    assert ids.index(later_user.id) > owner_index + 1
    assert ids.index(later_assistant.id) > owner_index + 1


def test_reconciled_outcome_appears_on_reload(_memory_mode) -> None:
    """#240: a reconciled lifecycle projects its status and outcome onto the
    linked assistant message on reload, without mutating persistence."""

    user_id = api_state.store.get_or_create_dev_user().id
    conversation = memory_conversation(
        user_id=user_id,
        title="Reconciled",
        title_source="system_default",
        language="en",
    )
    from argus.api.message_store import create_message

    user_message = create_message(
        user_id=user_id,
        conversation_id=conversation.id,
        role="user",
        content="test SPY drift",
        metadata={
            "agent_runtime_turn": {
                "status": "started",
                "conversation_id": conversation.id,
                "request_id": "req-reconciled",
            }
        },
    )
    row = api_state.store.chat_turn_lifecycles[user_message.id]
    row["accepted_at"] = (
        datetime.now(timezone.utc) - timedelta(minutes=30)
    ).isoformat()
    assistant = memory_message(
        conversation_id=conversation.id,
        role="assistant",
        content="Recovered terminal answer.",
        metadata={
            "agent_runtime_turn": {
                "turn_id": user_message.id,
                "request_id": "req-reconciled",
                "terminal": True,
                "status": "failed",
            }
        },
    )

    response = TestClient(app).get(f"/api/v1/conversations/{conversation.id}/messages")
    assert response.status_code == 200
    items = response.json()["items"]

    reloaded = next(item for item in items if item["id"] == assistant.id)
    reconciled = reloaded["metadata"]["turn_lifecycle_reconciled"]
    assert reconciled["status"] == "reconciled"
    assert reconciled["outcome"] == "recoverable_failed"
    assert reconciled["turn_id"] == user_message.id
    # Persistence was not mutated: the stored message has no projection key.
    stored = next(
        message
        for message in api_state.store.messages[conversation.id]
        if message.id == assistant.id
    )
    assert "turn_lifecycle_reconciled" not in (stored.metadata or {})


def test_projection_has_no_first_twenty_historical_ceiling(_memory_mode) -> None:
    """#240: a conversation with more than 20 historical abandoned turns
    still projects recovery for the newest one."""

    user_id = api_state.store.get_or_create_dev_user().id
    conversation = memory_conversation(
        user_id=user_id,
        title="Deep history",
        title_source="system_default",
        language="en",
    )
    base = datetime.now(timezone.utc) - timedelta(hours=2)
    newest_turn_id = None
    for index in range(21):
        message = memory_message(
            conversation_id=conversation.id,
            role="user",
            content=f"idea {index}",
        )
        api_state.store.chat_turn_lifecycles[message.id] = {
            "turn_id": message.id,
            "user_id": user_id,
            "conversation_id": conversation.id,
            "request_id": f"req-{index}",
            "status": "abandoned",
            "failure_code": "turn_abandoned",
            "retryable": True,
            "accepted_at": (base + timedelta(minutes=index)).isoformat(),
            "finished_at": (base + timedelta(minutes=index, seconds=30)).isoformat(),
        }
        newest_turn_id = message.id

    response = TestClient(app).get(
        f"/api/v1/conversations/{conversation.id}/messages",
        params={"limit": 100},
    )
    assert response.status_code == 200
    items = response.json()["items"]

    projected_turns = {
        item["metadata"]["agent_runtime_turn"]["turn_id"]
        for item in items
        if item["metadata"].get("turn_lifecycle_projection")
    }
    assert len(projected_turns) == 21
    assert newest_turn_id in projected_turns


def test_lifecycle_hooks_log_safe_fields_only(
    _memory_mode, monkeypatch: pytest.MonkeyPatch
) -> None:
    from argus.api.chat import turn_lifecycle_hooks
    from loguru import logger as loguru_logger

    class _ExplodingGateway:
        def transition_chat_turn_lifecycle(self, **kwargs: object) -> object:
            raise RuntimeError("secret dsn postgres://user:pass@host/db")

    monkeypatch.setattr(api_state, "supabase_gateway", _ExplodingGateway())

    records: list[str] = []
    sink_id = loguru_logger.add(
        lambda message: records.append(
            message.record["message"] + " " + str(message.record["extra"])
        ),
        level="WARNING",
    )
    try:
        turn_lifecycle_hooks.transition_turn(turn_id="turn-log", to_status="completed")
    finally:
        loguru_logger.remove(sink_id)

    blob = " ".join(records)
    assert "error_type" in blob and "RuntimeError" in blob
    assert "secret dsn" not in blob
    assert "postgres://" not in blob


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
