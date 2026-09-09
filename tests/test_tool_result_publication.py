"""A tool answer survives delivery and reload without minting a backtest."""

from __future__ import annotations

import json
from typing import Any

import pytest
from argus.api import state as api_state
from argus.api.main import app
from argus.domain.tool_contracts import ToolResultCard
from faker import Faker
from fastapi.testclient import TestClient

fake = Faker()


def card_document(*, call_id: str | None = None) -> dict[str, Any]:
    """Test-only identity output; deliberately no financial computation."""
    return ToolResultCard.model_validate(
        {
            "kind": "tool_result",
            "schema_version": 1,
            "tool_name": "identity_value",
            "call_id": call_id or fake.uuid4(),
            "artifact_id": fake.uuid4(),
            "input_revision": 0,
            "card_type": "identity_value",
            "card_version": 1,
            "arguments": {"known": 0, "unknown": None},
            "outcome": {"status": "succeeded", "result": {"value": 0}, "failure": None},
            "presentation": {
                "title": {
                    "locale_key": "chat.tools.identity.title",
                    "interpolation_args": {},
                },
                "answer": {
                    "name": "value",
                    "label": {
                        "locale_key": "chat.tools.identity.value",
                        "interpolation_args": {},
                    },
                    "value": 0,
                    "unit": None,
                },
                "rows": [],
                "inputs": [],
                "notes": [],
            },
            "artifact_state": "active",
        }
    ).model_dump(mode="json")


def test_plural_results_persist_and_reload_without_backtest(monkeypatch) -> None:
    from argus.api.routers import agent as agent_router

    cards = [card_document(), card_document()]

    async def stream(**_: Any):
        yield {
            "type": "final",
            "payload": {
                "stage_outcome": "ready_to_respond",
                "assistant_response": "",
                "final_response_payload": {"tool_result_cards": cards},
            },
        }

    monkeypatch.setattr(agent_router, "stream_agent_turn_events", stream)
    client = TestClient(app)
    client.post("/api/v1/dev/reset")
    conversation_id = client.post("/api/v1/conversations", json={}).json()[
        "conversation"
    ]["id"]
    response = client.post(
        "/api/v1/chat/stream",
        json={"conversation_id": conversation_id, "message": fake.sentence()},
    )
    assert response.status_code == 200, response.text
    finals = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: {")
    ]
    final = next(frame["payload"] for frame in finals if frame.get("type") == "final")
    assert final["tool_result_cards"] == cards
    messages = client.get(f"/api/v1/conversations/{conversation_id}/messages").json()[
        "items"
    ]
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[-1]["metadata"]["tool_result_cards"] == cards
    assert "result_card" not in messages[-1]["metadata"]
    assert not api_state.store.backtest_runs


def test_publication_refuses_ambiguous_duplicate_card_identity() -> None:
    from argus.api.chat.tool_results import runtime_tool_result_cards

    card = card_document()
    with pytest.raises(ValueError):
        runtime_tool_result_cards(
            {"final_response_payload": {"tool_result_cards": [card, card]}}
        )


def test_each_tool_effect_settles_with_its_original_call_identity(monkeypatch) -> None:
    from argus.api.chat import turn_metering
    from argus.api.chat.tool_results import ToolExecutionEffect

    effects = [
        ToolExecutionEffect(
            call_id=fake.uuid4(),
            tool_name="identity_value",
            artifact_id=fake.uuid4(),
            stage_patch={"research": {"query": fake.sentence()}},
        )
        for _ in range(2)
    ]
    settled = []
    monkeypatch.setattr(turn_metering, "settle_discovery_turn", lambda **_: None)
    monkeypatch.setattr(
        turn_metering,
        "settle_research_turn",
        lambda result, **identity: settled.append((result, identity)),
    )
    request_id = fake.uuid4()
    turn_metering.settle_metered_turn(
        effects[-1].stage_patch,
        discovery_usage=None,
        user_id=fake.uuid4(),
        is_guest=False,
        client_identity=None,
        conversation_id=fake.uuid4(),
        message_id=fake.uuid4(),
        request_id=request_id,
        tool_effects=effects,
    )
    assert [result for result, _ in settled] == [effect.stage_patch for effect in effects]
    assert [identity["tool_call_id"] for _, identity in settled] == [
        effect.call_id for effect in effects
    ]
    assert all(identity["request_id"] == request_id for _, identity in settled)


@pytest.mark.parametrize("mismatch", ["duplicate_call", "wrong_artifact"])
def test_invalid_private_effect_batch_dispatches_nothing(monkeypatch, mismatch) -> None:
    from argus.api.chat import research_jobs
    from argus.api.chat.tool_results import apply_runtime_tool_effects

    card = card_document()
    effects = [
        {
            "call_id": card["call_id"],
            "tool_name": card["tool_name"],
            "artifact_id": card["artifact_id"],
            "stage_patch": {"research_job_request": {}},
        }
    ]
    if mismatch == "duplicate_call":
        effects.append(effects[0])
    else:
        effects[0]["artifact_id"] = fake.uuid4()
    calls = []
    monkeypatch.setattr(
        research_jobs,
        "apply_research_job_request",
        lambda *args, **kwargs: calls.append(kwargs),
    )
    with pytest.raises(ValueError):
        apply_runtime_tool_effects(
            {"tool_result_cards": [card]},
            effects,
            user_id=fake.uuid4(),
            conversation_id=fake.uuid4(),
            request_message_id=fake.uuid4(),
            request_id=fake.uuid4(),
        )
    assert calls == []


def test_repeated_research_effects_publish_each_job_without_private_patch(
    monkeypatch,
) -> None:
    from argus.api.chat import research_jobs
    from argus.api.routers import agent as agent_router

    cards = [card_document(), card_document()]
    jobs = [fake.uuid4(), fake.uuid4()]
    submitted = []
    effects = [
        {
            "call_id": card["call_id"],
            "tool_name": card["tool_name"],
            "artifact_id": card["artifact_id"],
            "stage_patch": {"research_job_request": {"private_query": fake.sentence()}},
        }
        for card in cards
    ]

    def submit(patch, *, tool_call_id, tool_name, tool_artifact_id, tool_arguments, **_):
        submitted.append(tool_call_id)
        index = next(
            index for index, card in enumerate(cards) if card["call_id"] == tool_call_id
        )
        assert tool_arguments == cards[index]["arguments"]
        assert tool_artifact_id == cards[index]["artifact_id"]
        patch.pop("research_job_request")
        return {"id": jobs[index], "status": "queued", "operation_scope": "chat.research"}

    async def stream(**_: Any):
        yield {
            "type": "final",
            "_tool_effects": effects,
            "payload": {
                "stage_outcome": "ready_to_respond",
                "assistant_response": "",
                "research_job_request": effects[-1]["stage_patch"][
                    "research_job_request"
                ],
                "final_response_payload": {"tool_result_cards": cards},
            },
        }

    monkeypatch.setattr(research_jobs, "apply_research_job_request", submit)
    monkeypatch.setattr(agent_router, "stream_agent_turn_events", stream)
    client = TestClient(app)
    client.post("/api/v1/dev/reset")
    conversation_id = client.post("/api/v1/conversations", json={}).json()[
        "conversation"
    ]["id"]
    response = client.post(
        "/api/v1/chat/stream",
        json={"conversation_id": conversation_id, "message": fake.sentence()},
    )
    frames = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: {")
    ]
    payload = next(frame["payload"] for frame in frames if frame.get("type") == "final")
    assert [item["job"]["id"] for item in payload["tool_jobs"]] == jobs
    assert [item["call_id"] for item in payload["tool_jobs"]] == [
        card["call_id"] for card in cards
    ]
    assert "backtest_job" not in payload
    assert submitted == [card["call_id"] for card in cards]
    assert "private_query" not in response.text and "stage_patch" not in response.text
    message = client.get(f"/api/v1/conversations/{conversation_id}/messages").json()[
        "items"
    ][-1]
    assert message["metadata"]["tool_jobs"] == payload["tool_jobs"]
