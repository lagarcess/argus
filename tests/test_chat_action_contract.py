from __future__ import annotations

import json
from typing import Any

from argus.api.main import app
from argus.api.message_store import create_message
from fastapi.testclient import TestClient


def _client() -> TestClient:
    client = TestClient(app)
    client.post("/api/v1/dev/reset")
    client.patch(
        "/api/v1/me",
        json={
            "onboarding": {
                "stage": "ready",
                "language_confirmed": True,
                "primary_goal": "test_stock_idea",
                "completed": False,
            }
        },
    )
    return client


def _stream_payloads(stream: str, event_type: str) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for part in stream.split("\n\n"):
        data_line = next(
            (line for line in part.splitlines() if line.startswith("data: ")),
            None,
        )
        if data_line is None:
            continue
        raw = data_line.removeprefix("data: ").strip()
        if raw == "[DONE]":
            continue
        event = json.loads(raw)
        if event.get("type") == event_type:
            payloads.append(event.get("payload", event))
    return payloads


def _conversation(client: TestClient) -> dict[str, Any]:
    response = client.post("/api/v1/conversations", json={"language": "en"})
    assert response.status_code == 200
    return response.json()["conversation"]


def _user_id(client: TestClient) -> str:
    response = client.get("/api/v1/me")
    assert response.status_code == 200
    return str(response.json()["user"]["id"])


def test_change_asset_action_uses_structured_runtime_context() -> None:
    client = _client()
    conversation = _conversation(client)
    user_id = _user_id(client)
    create_message(
        user_id=user_id,
        conversation_id=conversation["id"],
        role="assistant",
        content="I read this as AAPL using a buy and hold approach.",
        metadata={
            "conversation_mode": "confirm",
            "agent_runtime_stage_outcome": "await_approval",
            "confirmation_payload": {
                "strategy": {
                    "strategy_type": "buy_and_hold",
                    "strategy_thesis": "Buy and hold Apple.",
                    "asset_universe": ["AAPL"],
                    "asset_class": "equity",
                    "date_range": "past year",
                    "capital_amount": 10000,
                },
                "optional_parameters": {},
            },
            "confirmation_card": {
                "title": "AAPL buy and hold",
                "statusLabel": "Ready to run",
                "summary": "I read this as AAPL using a buy and hold approach.",
                "rows": [],
                "assumptions": ["Benchmark: SPY"],
                "actions": [
                    {
                        "id": "change-asset",
                        "type": "change_asset",
                        "label": "Change asset",
                        "presentation": "confirmation",
                        "payload": {},
                    }
                ],
            },
        },
    )

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "action": {
                "type": "change_asset",
                "label": "Change asset",
                "presentation": "confirmation",
                "payload": {},
            },
            "language": "en",
        },
    )

    assert response.status_code == 200
    final = _stream_payloads(response.text, "final")[0]
    text = final["assistant_response"] or final.get("assistant_prompt") or ""
    assert "asset" in text.lower()
    assert final["stage_outcome"] == "await_user_reply"
    assert final["pending_strategy"]["requested_field"] == "asset_universe"
    messages = client.get(f"/api/v1/conversations/{conversation['id']}/messages").json()[
        "items"
    ]
    user_message = messages[-2]
    assistant_message = messages[-1]
    assert user_message["metadata"]["chat_action"]["type"] == "change_asset"
    assert assistant_message["metadata"]["pending_strategy"]["requested_field"] == (
        "asset_universe"
    )
