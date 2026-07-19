"""#240 — route matrix for every accepted POST /api/v1/chat/stream path.

Each non-backtest path must atomically accept (user message + lifecycle row
sharing the preallocated turn_id), transition running only before real
runtime work, and end with durable completed/recoverable_failed evidence —
or remain genuinely incomplete for stale reconciliation. chat.run_backtest
stays excluded because backtest_jobs owns that action's durable state.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from argus.api import state as api_state
from argus.api.main import app
from argus.api.message_store import memory_conversation, memory_message
from fastapi.testclient import TestClient


def _stream_events(stream: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for part in stream.split("\n\n"):
        data_line = next(
            (line for line in part.splitlines() if line.startswith("data: ")),
            None,
        )
        if data_line is None:
            continue
        raw = data_line.removeprefix("data: ").strip()
        if raw == "[DONE]":
            events.append({"type": "done"})
            continue
        events.append(json.loads(raw))
    return events


async def _runtime_success_events(**kwargs: Any):
    yield {"type": "stage_start", "stage": "interpret"}
    yield {"type": "token", "content": "Here is my answer."}
    yield {
        "type": "final",
        "payload": {
            "stage_outcome": "ready_to_respond",
            "assistant_response": "Here is my answer.",
        },
    }


@pytest.fixture(autouse=True)
def _memory_mode(monkeypatch: pytest.MonkeyPatch):
    from argus.api.routers import agent as agent_router

    monkeypatch.setattr(api_state, "supabase_gateway", None)
    monkeypatch.setattr(
        agent_router, "stream_agent_turn_events", _runtime_success_events
    )
    api_state.store.reset()
    yield


def _client() -> TestClient:
    client = TestClient(app)
    client.post("/api/v1/dev/reset")
    return client


def _ready_user(client: TestClient) -> str:
    client.patch(
        "/api/v1/me",
        json={
            "onboarding": {
                "stage": "ready",
                "completed": True,
                "language_confirmed": True,
                "primary_goal": "surprise_me",
            }
        },
    )
    return api_state.store.get_or_create_dev_user().id


def _conversation(user_id: str) -> str:
    conversation = memory_conversation(
        user_id=user_id,
        title="Route matrix",
        title_source="system_default",
        language="en",
    )
    return conversation.id


def _user_turns(conversation_id: str) -> list[Any]:
    return [
        message
        for message in api_state.store.messages.get(conversation_id, [])
        if message.role == "user"
    ]


# ── Path 1: normal message reaching LangGraph ────────────────────────────────


def test_normal_message_runs_before_graph_work_and_completes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Path 1: the accepted turn transitions to running immediately before
    the first actual runtime operation, and the terminal assistant message
    carries canonical completed metadata that finishes the lifecycle."""

    from argus.api.routers import agent as agent_router

    statuses_at_graph_start: list[dict[str, str]] = []

    async def _probing_runtime_events(**kwargs: Any):
        statuses_at_graph_start.append(
            {
                turn_id: str(row.get("status"))
                for turn_id, row in api_state.store.chat_turn_lifecycles.items()
            }
        )
        yield {"type": "token", "content": "Answer."}
        yield {
            "type": "final",
            "payload": {
                "stage_outcome": "ready_to_respond",
                "assistant_response": "Answer.",
            },
        }

    monkeypatch.setattr(
        agent_router, "stream_agent_turn_events", _probing_runtime_events
    )

    client = _client()
    user_id = _ready_user(client)
    conversation_id = _conversation(user_id)

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation_id,
            "message": "test AAPL momentum",
            "language": "en",
        },
    )
    assert response.status_code == 200

    turns = _user_turns(conversation_id)
    assert len(turns) == 1
    turn_id = turns[0].id
    assert statuses_at_graph_start == [{turn_id: "running"}]

    row = api_state.store.chat_turn_lifecycles[turn_id]
    assert row["status"] == "completed"
    assistant = api_state.store.messages[conversation_id][-1]
    turn = (assistant.metadata or {})["agent_runtime_turn"]
    assert turn["status"] == "completed"
    assert turn["terminal"] is True
    assert turn["turn_id"] == turn_id
    assert turn["request_id"] == row["request_id"]


# ── Path 2: onboarding-required early assistant response ─────────────────────


def test_onboarding_prompt_completes_the_accepted_turn() -> None:
    """Path 2 (the accepted-forever reproduction): the onboarding prompt is a
    deterministic early responder — HTTP 200 must leave the accepted turn
    completed, never accepted forever."""

    client = _client()
    # Fresh dev user keeps the default onboarding stage (language_selection),
    # so the route answers with the onboarding prompt before any graph work.
    user_id = api_state.store.get_or_create_dev_user().id
    conversation_id = _conversation(user_id)

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation_id,
            "message": "test AAPL momentum",
            "language": "en",
        },
    )
    assert response.status_code == 200
    events = _stream_events(response.text)
    assert any(event.get("type") == "final" for event in events)

    turns = _user_turns(conversation_id)
    assert len(turns) == 1
    row = api_state.store.chat_turn_lifecycles[turns[0].id]
    assert row["status"] == "completed"
    assistant = api_state.store.messages[conversation_id][-1]
    turn = (assistant.metadata or {})["agent_runtime_turn"]
    assert turn["status"] == "completed"
    assert turn["terminal"] is True
    assert turn["turn_id"] == turns[0].id


# ── Path 2b: onboarding control messages (goal selection and skip) ───────────


@pytest.mark.parametrize(
    "control_message",
    ["__ONBOARDING_GOAL__:learn_basics", "__ONBOARDING_SKIP__"],
    ids=["goal_selection", "skip"],
)
def test_onboarding_controls_are_durable_accepted_turns(
    control_message: str,
) -> None:
    """Path 2b: goal selection and skip are supported message-only requests —
    they accept atomically (user message + lifecycle) and complete through
    the durable assistant response, with no raw control token leaking into
    the conversation preview."""

    client = _client()
    user_id = api_state.store.get_or_create_dev_user().id
    conversation_id = _conversation(user_id)

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation_id,
            "message": control_message,
            "language": "en",
        },
    )
    assert response.status_code == 200
    events = _stream_events(response.text)
    assert any(event.get("type") == "final" for event in events)

    turns = _user_turns(conversation_id)
    assert len(turns) == 1
    control_turn = turns[0]
    assert control_turn.content == control_message
    row = api_state.store.chat_turn_lifecycles.get(control_turn.id)
    assert row is not None
    assert row["status"] == "completed"

    assistant = api_state.store.messages[conversation_id][-1]
    assert assistant.role == "assistant"
    turn = (assistant.metadata or {})["agent_runtime_turn"]
    assert turn["status"] == "completed"
    assert turn["terminal"] is True
    assert turn["turn_id"] == control_turn.id

    conversation = api_state.store.conversations[conversation_id]
    assert "__ONBOARDING" not in str(conversation.last_message_preview or "")


def test_onboarding_goal_interruption_leaves_reconcilable_acceptance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Path 2b interruption: if the assistant response never persists, the
    accepted lifecycle remains — reconcilable, never an untracked response."""

    from argus.api.routers import agent as agent_router

    def _boom(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("onboarding persistence interrupted")

    monkeypatch.setattr(agent_router, "persist_onboarding_update", _boom)

    _client()
    user_id = api_state.store.get_or_create_dev_user().id
    conversation_id = _conversation(user_id)

    failure_client = TestClient(app, raise_server_exceptions=False)
    try:
        failure_client.post(
            "/api/v1/chat/stream",
            json={
                "conversation_id": conversation_id,
                "message": "__ONBOARDING_GOAL__:learn_basics",
                "language": "en",
            },
        )
    except RuntimeError:
        pass

    turns = _user_turns(conversation_id)
    assert len(turns) == 1
    row = api_state.store.chat_turn_lifecycles.get(turns[0].id)
    assert row is not None
    assert row["status"] == "accepted"

    # The stale reconciler can settle the orphan.
    from argus.domain.chat_turn_lifecycle import reconcile_stale_turns_memory

    row["accepted_at"] = (
        datetime.now(timezone.utc) - timedelta(minutes=30)
    ).isoformat()
    reconciled = reconcile_stale_turns_memory(
        api_state.store, conversation_id=conversation_id, user_id=user_id
    )
    assert len(reconciled) == 1
    assert reconciled[0]["status"] == "abandoned"


# ── Path 3: runtime-fallback early response ──────────────────────────────────


def test_runtime_fallback_early_response_completes_the_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Path 3: a deterministic fallback responder performs no graph work and
    completes the accepted turn directly with its durable recovery answer."""

    from argus.api.routers import agent as agent_router

    async def _must_not_run(**kwargs: Any):
        raise AssertionError("fallback turns must not reach the runtime")
        yield  # pragma: no cover

    monkeypatch.setattr(agent_router, "stream_agent_turn_events", _must_not_run)
    monkeypatch.setattr(
        agent_router,
        "stale_confirmation_action_message",
        lambda **kwargs: "That confirmation is no longer active.",
    )

    client = _client()
    user_id = _ready_user(client)
    conversation_id = _conversation(user_id)

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation_id,
            "message": "Change dates",
            "language": "en",
            "action": {
                "type": "change_dates",
                "label": "Change dates",
                "payload": {"confirmation_id": "confirmation-stale"},
            },
        },
    )
    assert response.status_code == 200

    turns = _user_turns(conversation_id)
    assert len(turns) == 1
    row = api_state.store.chat_turn_lifecycles[turns[0].id]
    assert row["status"] == "completed"
    assistant = api_state.store.messages[conversation_id][-1]
    turn = (assistant.metadata or {})["agent_runtime_turn"]
    assert turn["status"] == "completed"
    assert turn["terminal"] is True
    assert turn["turn_id"] == turns[0].id


# ── Path 7: recoverable terminal failure ─────────────────────────────────────


def test_runtime_failure_writes_canonical_recoverable_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Path 7: a runtime failure persists canonical recoverable_failed turn
    metadata (never the legacy 'failed' status) with failure_code and
    retryable, and the lifecycle row carries the same evidence."""

    from argus.api.routers import agent as agent_router

    async def _exploding_runtime_events(**kwargs: Any):
        yield {"type": "token", "content": "partial"}
        raise RuntimeError("runtime exploded")

    monkeypatch.setattr(
        agent_router, "stream_agent_turn_events", _exploding_runtime_events
    )

    client = _client()
    user_id = _ready_user(client)
    conversation_id = _conversation(user_id)

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation_id,
            "message": "test AAPL momentum",
            "language": "en",
        },
    )
    assert response.status_code == 200
    events = _stream_events(response.text)
    assert any(event.get("type") == "error" for event in events)

    turns = _user_turns(conversation_id)
    assert len(turns) == 1
    assistant = api_state.store.messages[conversation_id][-1]
    turn = (assistant.metadata or {})["agent_runtime_turn"]
    assert turn["status"] == "recoverable_failed"
    assert turn["terminal"] is True
    assert turn["turn_id"] == turns[0].id
    assert turn["failure_code"] == "agent_runtime_failure"
    assert turn["retryable"] is True

    row = api_state.store.chat_turn_lifecycles[turns[0].id]
    assert row["status"] == "recoverable_failed"
    assert row["failure_code"] == "agent_runtime_failure"
    assert row["retryable"] is True


# ── Path 8: initialization / pre-graph failure ───────────────────────────────


def test_initialization_failure_completes_recoverable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Path 8: a pre-graph initialization failure still accepts the turn and
    ends it recoverable_failed with canonical metadata."""

    def _broken_workflow(request: Any) -> Any:
        raise RuntimeError("workflow init failed")

    monkeypatch.setattr(api_state, "get_agent_runtime_workflow", _broken_workflow)

    client = _client()
    user_id = _ready_user(client)
    conversation_id = _conversation(user_id)

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation_id,
            "message": "test AAPL momentum",
            "language": "en",
        },
    )
    assert response.status_code == 200
    events = _stream_events(response.text)
    assert any(event.get("type") == "error" for event in events)

    turns = _user_turns(conversation_id)
    assert len(turns) == 1
    assistant = api_state.store.messages[conversation_id][-1]
    turn = (assistant.metadata or {})["agent_runtime_turn"]
    assert turn["status"] == "recoverable_failed"
    assert turn["terminal"] is True
    assert turn["turn_id"] == turns[0].id
    assert turn["failure_code"] == "agent_runtime_failure"
    assert turn["retryable"] is True

    row = api_state.store.chat_turn_lifecycles[turns[0].id]
    assert row["status"] == "recoverable_failed"
    assert row["failure_code"] == "agent_runtime_failure"


# ── Path 4: select_response_option ───────────────────────────────────────────


def _seed_clarification(conversation_id: str) -> str:
    assistant = memory_message(
        conversation_id=conversation_id,
        role="assistant",
        content="Which timeframe should we use?",
        metadata={
            "conversation_mode": "setup",
            "agent_runtime_stage_outcome": "await_user_reply",
            "clarification": {
                "options": [
                    {
                        "id": "option_0",
                        "replacement_values": {"timeframe": "1D"},
                    }
                ]
            },
            "pending_strategy": {
                "strategy": {
                    "strategy_type": "buy_and_hold",
                    "strategy_thesis": "Buy and hold Apple.",
                    "asset_universe": ["AAPL"],
                    "asset_class": "equity",
                    "timeframe": "5m",
                    "date_range": {"start": "2024-01-01", "end": "2024-01-05"},
                },
                "requested_field": "timeframe",
                "missing_required_fields": ["timeframe"],
            },
        },
    )
    return assistant.id


def _response_option_payload(conversation_id: str, assistant_id: str) -> dict:
    return {
        "conversation_id": conversation_id,
        "message": "Retry with daily bars",
        "language": "en",
        "action": {
            "type": "select_response_option",
            "label": "Retry with daily bars",
            "payload": {
                "source_assistant_id": assistant_id,
                "option_id": "option_0",
                "replacement_values": {"timeframe": "1D"},
            },
        },
    }


def test_select_response_option_accepts_atomically() -> None:
    """Path 4: the option claim persists the request message and its
    lifecycle row in the same admission, sharing the preallocated turn_id,
    and the turn ends completed."""

    client = _client()
    user_id = _ready_user(client)
    conversation_id = _conversation(user_id)
    assistant_id = _seed_clarification(conversation_id)

    response = client.post(
        "/api/v1/chat/stream",
        json=_response_option_payload(conversation_id, assistant_id),
    )
    assert response.status_code == 200

    turns = _user_turns(conversation_id)
    assert len(turns) == 1
    request_message = turns[0]
    row = api_state.store.chat_turn_lifecycles.get(request_message.id)
    assert row is not None
    assert row["user_id"] == user_id
    assert row["conversation_id"] == conversation_id
    assert row["status"] == "completed"


def test_select_response_option_acceptance_is_atomic_on_lifecycle_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Path 4 rollback: if the lifecycle write fails inside the claim, the
    appended request message rolls back — acceptance is all-or-nothing."""

    from argus.domain import chat_turn_lifecycle as lifecycle_module

    client = _client()
    user_id = _ready_user(client)
    conversation_id = _conversation(user_id)
    assistant_id = _seed_clarification(conversation_id)

    def _boom(*args: object, **kwargs: object) -> object:
        raise RuntimeError("lifecycle write failed")

    monkeypatch.setattr(lifecycle_module, "create_accepted_memory", _boom)
    monkeypatch.setattr(
        "argus.api.message_store.create_accepted_memory", _boom, raising=False
    )

    failure_client = TestClient(app, raise_server_exceptions=False)
    response = failure_client.post(
        "/api/v1/chat/stream",
        json=_response_option_payload(conversation_id, assistant_id),
    )

    assert response.status_code >= 500
    assert _user_turns(conversation_id) == []
    assert api_state.store.chat_turn_lifecycles == {}


# ── Path 5: cancel_confirmation ──────────────────────────────────────────────


def test_cancel_confirmation_participates_in_the_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Path 5: cancellation is an ordinary accepted turn — durable user
    message plus lifecycle row — and completes after its durable (empty)
    assistant cancellation artifact."""

    from argus.api.routers import agent as agent_router

    monkeypatch.setattr(
        agent_router, "checkpoint_has_pending_confirmation", lambda values: True
    )
    monkeypatch.setattr(
        agent_router,
        "stale_confirmation_action_message",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        agent_router,
        "confirmation_metadata_fallback_context",
        lambda **kwargs: None,
    )

    client = _client()
    user_id = _ready_user(client)
    conversation_id = _conversation(user_id)

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation_id,
            "message": "Cancel",
            "language": "en",
            "action": {
                "type": "cancel_confirmation",
                "label": "Cancel",
                "payload": {"confirmation_id": "confirmation-9"},
            },
        },
    )
    assert response.status_code == 200
    events = _stream_events(response.text)
    assert any(event.get("type") == "final" for event in events)

    turns = _user_turns(conversation_id)
    assert len(turns) == 1
    cancel_turn = turns[0]
    assert (cancel_turn.metadata or {})["chat_action"]["type"] == (
        "cancel_confirmation"
    )
    row = api_state.store.chat_turn_lifecycles.get(cancel_turn.id)
    assert row is not None
    assert row["status"] == "completed"
    assistant = api_state.store.messages[conversation_id][-1]
    assert assistant.role == "assistant"
    turn = (assistant.metadata or {})["agent_runtime_turn"]
    assert turn["status"] == "completed"
    assert turn["terminal"] is True
    assert turn["turn_id"] == cancel_turn.id


# ── Path 9: chat.run_backtest exclusion ──────────────────────────────────────


def test_run_backtest_action_route_stays_excluded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Path 9: a run action's user message persists, but backtest_jobs owns
    its durable state — no chat lifecycle row exists for that turn."""

    from argus.api.routers import agent as agent_router

    monkeypatch.setattr(
        agent_router, "checkpoint_has_pending_confirmation", lambda values: True
    )
    monkeypatch.setattr(
        agent_router,
        "stale_confirmation_action_message",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        agent_router,
        "confirmation_metadata_fallback_context",
        lambda **kwargs: None,
    )

    client = _client()
    user_id = _ready_user(client)
    conversation_id = _conversation(user_id)

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation_id,
            "message": "Run backtest",
            "language": "en",
            "action": {
                "type": "run_backtest",
                "label": "Run backtest",
                "payload": {"confirmation_id": "confirmation-run-1"},
            },
        },
    )
    assert response.status_code == 200

    turns = _user_turns(conversation_id)
    assert len(turns) == 1
    assert (turns[0].metadata or {})["chat_action"]["type"] == "run_backtest"
    assert api_state.store.chat_turn_lifecycles == {}
