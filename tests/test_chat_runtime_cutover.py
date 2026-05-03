from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient

from argus.api.main import app


def _client() -> TestClient:
    client = TestClient(app)
    client.post("/api/v1/dev/reset")
    return client


def _set_onboarding_ready(client: TestClient, primary_goal: str = "surprise_me") -> None:
    response = client.patch(
        "/api/v1/me",
        json={
            "onboarding": {
                "stage": "ready",
                "language_confirmed": True,
                "primary_goal": primary_goal,
                "completed": False,
            }
        },
    )
    assert response.status_code == 200


def test_chat_stream_routes_through_agent_runtime_and_emits_result_card(
    monkeypatch,
) -> None:
    from argus.api import main as api_main

    captured: dict[str, Any] = {}

    def _fake_run_agent_turn(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {
            "stage_outcome": "ready_to_respond",
            "assistant_response": "Here is your buy-and-hold result.",
            "final_response_payload": {
                "result": {
                    "execution_status": "succeeded",
                    "resolved_strategy": {
                        "strategy_type": "buy_and_hold",
                        "symbol": "TSLA",
                    },
                    "resolved_parameters": {
                        "timeframe": "1D",
                        "date_range": {
                            "start": "2025-01-01",
                            "end": "2025-12-31",
                        },
                    },
                    "metrics": {
                        "aggregate": {"performance": {"total_return_pct": 12.5}}
                    },
                    "benchmark_metrics": {
                        "benchmark_symbol": "SPY",
                        "benchmark_return_pct": 9.2,
                    },
                    "assumptions": ["Starting capital: $10,000."],
                    "caveats": [],
                },
                "result_card": {
                    "title": "TSLA Buy and Hold",
                    "status_label": "Completed",
                    "rows": [
                        {"label": "Total Return", "value": "+12.5%"},
                    ],
                },
                "explanation_context": {
                    "strategy_type": "buy_and_hold",
                    "assumptions": ["Starting capital: $10,000."],
                    "caveats": [],
                },
            },
        }

    monkeypatch.setattr(api_main, "run_agent_turn", _fake_run_agent_turn)

    client = _client()
    _set_onboarding_ready(client, primary_goal="test_stock_idea")
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "Buy and hold Tesla over the last year.",
            "language": "en",
        },
    )

    assert response.status_code == 200
    assert captured["thread_id"] == conversation["id"]
    assert captured["message"] == "Buy and hold Tesla over the last year."
    assert captured["user"].user_id
    assert "event: status" in response.text
    assert '"status":"ready_to_respond"' in response.text
    assert "event: token" in response.text
    assert "Here is your buy-and-hold result." in response.text
    assert "event: result" in response.text

    result_line = next(
        line.removeprefix("data: ")
        for line in response.text.splitlines()
        if line.startswith("data: {") and '"run"' in line
    )
    run_payload = json.loads(result_line)["run"]
    assert run_payload["conversation_result_card"]["title"] == "TSLA Buy and Hold"

    messages = client.get(f"/api/v1/conversations/{conversation['id']}/messages")
    assert messages.status_code == 200
    assert [message["role"] for message in messages.json()["items"]] == [
        "user",
        "assistant",
    ]


def test_chat_stream_falls_back_conversationally_for_unsupported_runtime_result(
    monkeypatch,
) -> None:
    from argus.api import main as api_main

    def _fake_run_agent_turn(**_: Any) -> dict[str, Any]:
        return {
            "stage_outcome": "await_user_reply",
            "assistant_prompt": (
                "Trailing stops are not supported yet. "
                "I can help reframe this into a supported backtest."
            ),
            "final_response_payload": {
                "error": "unsupported_capability",
            },
        }

    monkeypatch.setattr(api_main, "run_agent_turn", _fake_run_agent_turn)

    client = _client()
    _set_onboarding_ready(client, primary_goal="test_stock_idea")
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "Backtest Tesla with a 5% trailing stop.",
            "language": "en",
        },
    )

    assert response.status_code == 200
    assert "event: token" in response.text
    assert "supported backtest" in response.text.lower()
    assert "event: result" not in response.text
