"""Refusals reach private evidence without changing the chat contract."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from argus.api import state as api_state
from argus.api.chat import refusal_evidence
from argus.api.main import app
from argus.api.routers import agent as agent_router
from faker import Faker
from fastapi.testclient import TestClient

fake = Faker()


@pytest.fixture
def captured(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    rows: list[Any] = []
    monkeypatch.setattr(
        refusal_evidence,
        "persist_refusal_observation",
        lambda *, gateway, observation: rows.append(observation) is None,
    )
    return rows


@pytest.fixture
def chat() -> tuple[TestClient, str]:
    client = TestClient(app)
    assert client.post("/api/v1/dev/reset").status_code == 200
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]
    return client, conversation["id"]


@pytest.mark.parametrize(
    "site,action_type,code",
    [
        ("response_option", "select_response_option", "artifact_action_invalid_state"),
        ("confirmation_edit", "adjust_assumptions", "confirmation_required"),
        ("retest", "retest_run", "artifact_action_invalid_state"),
        ("cancellation", "cancel_confirmation", "confirmation_required"),
        ("no_checkpoint", "run_backtest", "confirmation_required"),
        ("invalidated_checkpoint", "run_backtest", "confirmation_required"),
        ("run_identity", "run_backtest", "idempotency_conflict"),
    ],
)
def test_each_artifact_rejection_is_recorded_once_without_contract_changes(
    chat: tuple[TestClient, str],
    captured: list[Any],
    monkeypatch: pytest.MonkeyPatch,
    site: str,
    action_type: str,
    code: str,
) -> None:
    client, conversation_id = chat
    confirmation_id = fake.uuid4()
    action_payload: dict[str, Any] = {"confirmation_id": confirmation_id}
    if site == "response_option":
        action_payload = {
            "source_assistant_id": fake.uuid4(),
            "option_id": "option_0",
            "replacement_values": {"timeframe": "1D"},
        }
    if site == "retest":
        action_payload = {
            "source_run_id": fake.uuid4(),
            "window_policy": "preserve_start_ending_latest_available",
            "contract_version": "argus_retest_run/v2",
        }
    if site in {"no_checkpoint", "invalidated_checkpoint"}:
        monkeypatch.setattr(
            agent_router, "stale_confirmation_action_message", lambda **_: None
        )
        monkeypatch.setattr(
            agent_router, "confirmation_metadata_fallback_context", lambda **_: None
        )
        monkeypatch.setattr(
            agent_router,
            "checkpoint_has_pending_confirmation",
            lambda _: site == "invalidated_checkpoint",
        )
        monkeypatch.setattr(
            agent_router, "recent_metadata_invalidates_confirmation", lambda _: True
        )
    body = {
        "conversation_id": conversation_id,
        "action": {"type": action_type, "payload": action_payload},
    }
    request_id = fake.uuid4()
    headers = {
        "X-Request-ID": request_id,
        "Idempotency-Key": fake.uuid4() if site == "run_identity" else confirmation_id,
    }
    messages_before = deepcopy(api_state.store.messages)
    turns_before = deepcopy(api_state.store.chat_turn_lifecycles)
    usage_before = deepcopy(api_state.store.usage_counters)
    visitor_usage_before = deepcopy(api_state.store.visitor_usage_counters)
    response = client.post("/api/v1/chat/stream", json=body, headers=headers)
    assert response.status_code == 409, response.text
    assert response.json()["code"] == code
    assert len(captured) == 1
    row = captured[0]
    assert row.request_id == request_id
    assert row.conversation_id == conversation_id
    assert row.action["type"] == action_type
    assert row.action["payload"] == action_payload
    assert row.outcome == response.json()
    assert row.status_code == response.status_code
    assert row.request_message_id is None
    assert row.response_message_id is None
    assert api_state.store.messages == messages_before
    assert api_state.store.chat_turn_lifecycles == turns_before
    assert api_state.store.usage_counters == usage_before
    assert api_state.store.visitor_usage_counters == visitor_usage_before
    assert not api_state.store.backtest_jobs
    # The observer is independent of the error's rendering and settlement.
    monkeypatch.setattr(
        refusal_evidence, "persist_refusal_observation", lambda **_: False
    )
    control = client.post("/api/v1/chat/stream", json=body, headers=headers)
    assert control.content == response.content


@pytest.mark.parametrize(
    "response_intent",
    [
        {"kind": "unsupported_recovery", "facts": {"requested_metric": "sortino_ratio"}},
        {"kind": "coverage_recovery", "facts": {"requested_date_range": "past year"}},
        None,
    ],
)
def test_terminal_refusal_retains_its_question_and_shape_without_classifying(
    chat: tuple[TestClient, str],
    captured: list[Any],
    monkeypatch: pytest.MonkeyPatch,
    response_intent: dict[str, Any] | None,
) -> None:
    asked, answer = fake.sentence(), fake.sentence()

    async def runtime(**_: Any):
        yield {
            "type": "final",
            "payload": {
                "stage_outcome": "ready_to_respond",
                "assistant_response": answer,
                **({"response_intent": response_intent} if response_intent else {}),
            },
        }

    monkeypatch.setattr(agent_router, "stream_agent_turn_events", runtime)
    client, conversation_id = chat
    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation_id,
            "message": asked,
        },
    )
    assert response.status_code == 200
    assert len(captured) == 1
    row = captured[0]
    messages = {m.id: m for m in api_state.store.messages[conversation_id]}
    assert messages[row.request_message_id].content == asked
    reply = messages[row.response_message_id]
    assert reply.content == answer
    assert reply.metadata.get("response_intent") == response_intent
    assert row.asked is None and row.outcome is None  # canonical messages own these
    assert "refusal" not in response.text


def test_observer_outage_does_not_replace_the_original_rejection(
    chat: tuple[TestClient, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(**_: Any) -> bool:
        raise RuntimeError("simulated storage failure")

    monkeypatch.setattr(refusal_evidence, "persist_refusal_observation", fail)
    client, conversation_id = chat
    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation_id,
            "action": {
                "type": "run_backtest",
                "payload": {"confirmation_id": fake.uuid4()},
            },
        },
    )
    assert response.status_code == 400
    assert response.json()["code"] == "idempotency_key_required"


def test_runtime_failure_has_an_exact_recorded_pair(
    chat: tuple[TestClient, str],
    captured: list[Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def failing_runtime(**_: Any):
        yield {"type": "stage_start", "stage": "interpret"}
        raise RuntimeError("synthetic runtime failure")

    monkeypatch.setattr(agent_router, "stream_agent_turn_events", failing_runtime)
    client, conversation_id = chat
    asked = fake.sentence()
    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation_id,
            "message": asked,
        },
    )
    assert response.status_code == 200
    assert len(captured) == 1
    row = captured[0]
    messages = {m.id: m for m in api_state.store.messages[conversation_id]}
    assert messages[row.request_message_id].content == asked
    assert (
        messages[row.response_message_id].metadata["recovery"]["code"]
        == "runtime_failure"
    )


def test_storage_outage_keeps_a_successful_terminal_successful(
    chat: tuple[TestClient, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(**_: Any) -> bool:
        raise RuntimeError("simulated storage failure")

    answer = fake.sentence()

    async def runtime(**_: Any):
        yield {
            "type": "final",
            "payload": {
                "stage_outcome": "ready_to_respond",
                "assistant_response": answer,
            },
        }

    monkeypatch.setattr(refusal_evidence, "persist_refusal_observation", fail)
    monkeypatch.setattr(agent_router, "stream_agent_turn_events", runtime)
    client, conversation_id = chat
    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation_id,
            "message": fake.sentence(),
        },
    )
    assert response.status_code == 200
    assert '"type": "error"' not in response.text
    assert api_state.store.messages[conversation_id][-1].content == answer
