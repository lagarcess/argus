from __future__ import annotations

import json
from typing import Any

from argus.agent_runtime.confirmation_facts import confirmation_display_facts
from argus.api import state as api_state
from argus.api.main import app
from argus.api.message_store import create_message
from argus.api.routers import agent as agent_router
from fastapi.testclient import TestClient


def test_empty_prose_assumptions_answer_completes_and_reloads_after_language_change(
    monkeypatch,
) -> None:
    strategy = {
        "strategy_type": "dca_accumulation",
        "asset_universe": ["AAPL"],
        "asset_class": "equity",
        "capital_amount": 500,
        "cadence": "monthly",
        "date_range": {"start": "2025-01-02", "end": "2025-12-31"},
    }
    launch_payload = {
        "strategy_type": strategy["strategy_type"],
        "symbol": strategy["asset_universe"][0],
        "symbols": strategy["asset_universe"],
        "date_range": strategy["date_range"],
        "timeframe": "1D",
        "sizing_mode": "capital_amount",
        "capital_amount": strategy["capital_amount"],
        "cadence": strategy["cadence"],
        "benchmark_symbol": "SPY",
    }
    optional_parameters = {
        "initial_capital": {"source": "user", "value": 0},
        "timeframe": {"source": "default", "value": "1D"},
        "fees": {"source": "default", "value": 0},
        "slippage": {"source": "default", "value": 0},
    }
    display_facts = confirmation_display_facts(
        strategy=strategy,
        optional_parameters=optional_parameters,
        launch_payload=launch_payload,
    )
    response_intent = {
        "kind": "artifact_assumptions",
        "facts": {
            "artifact_kind": "confirmation",
            "asset_class": strategy["asset_class"],
            "display_facts": display_facts,
        },
    }
    runtime_calls = []

    async def runtime(**kwargs: Any):
        runtime_calls.append(kwargs)
        yield {"type": "stage_start", "stage": "interpret"}
        yield {
            "type": "final",
            "payload": {
                "stage_outcome": "ready_to_respond",
                "assistant_response": "",
                "response_intent": response_intent,
            },
        }

    monkeypatch.setattr(agent_router, "stream_agent_turn_events", runtime)
    client = TestClient(app)
    assert client.post("/api/v1/dev/reset").status_code == 200
    conversation = client.post("/api/v1/conversations", json={"language": "en"}).json()[
        "conversation"
    ]
    user_id = client.get("/api/v1/me").json()["user"]["id"]
    private_source = "Private English confirmation assumptions are retained for audit."
    source = create_message(
        user_id=user_id,
        conversation_id=conversation["id"],
        role="assistant",
        content=private_source,
        metadata={
            "agent_runtime_stage_outcome": "await_approval",
            "confirmation_card": {
                "confirmation_id": api_state.store.new_id(),
                "confirmation_state": "active",
                "display_facts": display_facts,
                "assumptions": [private_source],
            },
            "confirmation_payload": {
                "strategy": strategy,
                "optional_parameters": optional_parameters,
                "launch_payload": launch_payload,
            },
        },
    )

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "What assumptions are you using?",
            "language": "en",
        },
    )

    assert response.status_code == 200
    assert response.text.endswith("data: [DONE]\n\n")
    events = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ") and line != "data: [DONE]"
    ]
    assert not [event for event in events if event["type"] in {"error", "token"}]
    finals = [event["payload"] for event in events if event["type"] == "final"]
    assert len(finals) == 1
    final = finals[0]
    assert final["stage_outcome"] == "ready_to_respond"
    assert final["assistant_response"] == ""
    assert final["response_intent"] == response_intent
    assert not final.get("recovery")
    assert not final.get("retry_last_turn")
    assert len(runtime_calls) == 1

    message_url = f"/api/v1/conversations/{conversation['id']}/messages"
    before = client.get(message_url)
    assert before.status_code == 200
    changed_language = client.patch(
        "/api/v1/me", json={"language": "es-419", "locale": "es-419"}
    )
    assert changed_language.status_code == 200
    after = client.get(message_url)
    assert after.status_code == 200
    for messages in (before.json()["items"], after.json()["items"]):
        answer = next(
            message for message in messages if message["id"] == final["message_id"]
        )
        assert answer["content"] == ""
        assert private_source not in json.dumps(answer)
        assert answer["metadata"]["response_intent"] == response_intent
        terminal = answer["metadata"]["agent_runtime_turn"]
        assert terminal["terminal"] is True
        assert terminal["status"] == "completed"
        assert not terminal.get("failure_code")
        assert not answer["metadata"].get("retry_last_turn")
    assert source.content == private_source
    assert source.metadata["confirmation_card"]["confirmation_state"] == "active"
    assert len(runtime_calls) == 1  # Reload and language changes never invoke a model.
