from __future__ import annotations

import json
from typing import Any

import pytest
from argus.api.main import app
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


def _conversation(client: TestClient) -> dict[str, Any]:
    return client.post("/api/v1/conversations", json={}).json()["conversation"]


def _data_events(stream: str) -> list[dict[str, Any]]:
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
            continue
        events.append(json.loads(raw))
    return events


def _final_payload(stream: str) -> dict[str, Any]:
    final_events = [
        event for event in _data_events(stream) if event.get("type") == "final"
    ]
    assert len(final_events) == 1
    payload = final_events[0]["payload"]
    assert isinstance(payload, dict)
    return payload


@pytest.fixture(autouse=True)
def _patch_runtime_io(monkeypatch: pytest.MonkeyPatch) -> None:
    from argus.api import state as api_state

    monkeypatch.setattr(api_state, "supabase_gateway", None)


def test_internal_agent_runtime_turn_is_not_exposed_by_launch_api() -> None:
    paths = {
        getattr(route, "path", "")
        for route in app.routes
        if getattr(route, "path", "")
    }

    assert "/api/v1/chat/stream" in paths
    assert "/internal/agent-runtime/turn" not in paths


def test_chat_stream_confirmation_uses_final_payload_without_named_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api.routers import agent as agent_router

    async def _fake_stream_agent_turn_events(**_: Any):
        yield {"type": "stage_start", "stage": "interpret"}
        yield {"type": "stage_outcome", "outcome": "ready_for_confirmation"}
        yield {
            "type": "final",
            "payload": {
                "stage_outcome": "await_approval",
                "assistant_response": "Ready to test AAPL with buy and hold.",
                "confirmation_payload": {
                        "strategy": {
                            "strategy_type": "buy_and_hold",
                            "asset_universe": ["AAPL"],
                            "date_range": {"start": "2025-05-03", "end": "2026-05-03"},
                            "capital_amount": 10000,
                        },
                        "optional_parameters": {},
                        "launch_payload": {
                            "strategy_type": "buy_and_hold",
                            "symbol": "AAPL",
                            "symbols": ["AAPL"],
                            "timeframe": "1D",
                            "date_range": {
                                "start": "2025-05-03",
                                "end": "2026-05-03",
                            },
                            "sizing_mode": "capital_amount",
                            "capital_amount": 10000,
                            "benchmark_symbol": "SPY",
                        },
                        "validation": {
                            "status": "ready_to_run",
                            "executable": True,
                        },
                    },
                },
            }

    monkeypatch.setattr(
        agent_router,
        "stream_agent_turn_events",
        _fake_stream_agent_turn_events,
    )
    client = _client()
    conversation = _conversation(client)

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "Buy and hold Apple over the past year",
            "language": "en",
        },
    )

    assert response.status_code == 200
    assert "event:" not in response.text
    assert response.text.count("data: [DONE]") == 1
    payload = _final_payload(response.text)
    assert payload["confirmation"]["actions"][0]["type"] == "run_backtest"
    assert payload.get("assistant_response") is None
    assert payload["message_id"]
    assert "run" not in payload


def test_chat_stream_result_uses_final_payload_run_without_named_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api.routers import agent as agent_router

    result_card = {
        "title": "AAPL buy and hold",
        "date_range": {
            "start": "2025-05-03",
            "end": "2026-05-03",
            "display": "May 3, 2025 to May 3, 2026",
        },
        "status_label": "Completed",
        "rows": [{"key": "total_return_pct", "label": "Total Return", "value": "+12.4%"}],
        "assumptions": ["$10,000 starting capital", "Benchmark: SPY"],
        "actions": [
            {
                "id": "show-breakdown",
                "type": "show_breakdown",
                "label": "Show a breakdown",
                "presentation": "result",
                "payload": {},
            }
        ],
    }

    async def _fake_stream_agent_turn_events(**_: Any):
        yield {"type": "stage_start", "stage": "interpret"}
        yield {"type": "stage_start", "stage": "execute"}
        yield {"type": "token", "content": "Short grounded summary."}
        yield {
            "type": "final",
            "payload": {
                "stage_outcome": "end_run",
                "assistant_response": "Short grounded summary.",
                "final_response_payload": {
                    "result_card": result_card,
                    "result": {
                        "resolved_strategy": {
                            "strategy_type": "buy_and_hold",
                            "asset_universe": ["AAPL"],
                        },
                        "resolved_parameters": {"timeframe": "1D"},
                        "metrics": {
                            "aggregate": {"performance": {"total_return_pct": 12.4}}
                        },
                        "benchmark_metrics": {"benchmark_symbol": "SPY"},
                    },
                },
            },
        }

    monkeypatch.setattr(
        agent_router,
        "stream_agent_turn_events",
        _fake_stream_agent_turn_events,
    )
    client = _client()
    conversation = _conversation(client)

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "Run it",
            "language": "en",
        },
    )

    assert response.status_code == 200
    assert "event:" not in response.text
    assert response.text.count("data: [DONE]") == 1
    payload = _final_payload(response.text)
    assert payload["run"]["conversation_result_card"]["title"] == "AAPL buy and hold"
    assert payload["message_id"]

    messages = client.get(f"/api/v1/conversations/{conversation['id']}/messages").json()[
        "items"
    ]
    assert messages[-1]["id"] == payload["message_id"]
    assert messages[-1]["content"] == "Short grounded summary."


def test_chat_stream_artifact_naming_scheduler_failure_does_not_block_done(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api.routers import agent as agent_router

    scheduled: list[dict[str, Any]] = []

    async def _fake_stream_agent_turn_events(**_: Any):
        yield {"type": "stage_start", "stage": "interpret"}
        yield {
            "type": "final",
            "payload": {
                "stage_outcome": "ready_to_respond",
                "assistant_response": "Short grounded summary.",
            },
        }

    def _failing_scheduler(**kwargs: Any) -> None:
        scheduled.append(kwargs)
        raise RuntimeError("title service unavailable")

    monkeypatch.setattr(
        agent_router,
        "stream_agent_turn_events",
        _fake_stream_agent_turn_events,
    )
    monkeypatch.setattr(
        agent_router,
        "schedule_artifact_naming_after_stream",
        _failing_scheduler,
        raising=False,
    )
    client = _client()
    conversation = _conversation(client)

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "Explain dollar cost averaging.",
            "language": "en",
        },
    )

    assert response.status_code == 200
    assert response.text.count("data: [DONE]") == 1
    assert _final_payload(response.text)["assistant_response"] == (
        "Short grounded summary."
    )
    assert len(scheduled) == 1


def test_chat_stream_finalizes_ai_title_after_meaningful_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api import state as api_state
    from argus.api.routers import agent as agent_router

    async def _fake_stream_agent_turn_events(**_: Any):
        yield {"type": "stage_start", "stage": "interpret"}
        yield {
            "type": "final",
            "payload": {
                "stage_outcome": "ready_to_respond",
                "assistant_response": (
                    "Dollar cost averaging means investing a fixed amount "
                    "on a schedule."
                ),
            },
        }

    def _suggest_entity_name(**kwargs: Any) -> str:
        assert kwargs["entity_type"] == "conversation"
        assert "dollar cost averaging" in kwargs["context"].lower()
        return "DCA Basics"

    monkeypatch.setenv("ARGUS_ENABLE_ARTIFACT_NAMING_IN_TESTS", "1")
    monkeypatch.setattr(
        agent_router,
        "stream_agent_turn_events",
        _fake_stream_agent_turn_events,
    )
    monkeypatch.setattr(
        "argus.api.artifact_naming.suggest_entity_name",
        _suggest_entity_name,
    )
    client = _client()
    conversation = _conversation(client)

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "Can you explain dollar cost averaging?",
            "language": "en",
        },
    )

    assert response.status_code == 200
    assert response.text.count("data: [DONE]") == 1
    updated = api_state.store.conversations[conversation["id"]]
    assert updated.title == "DCA Basics"
    assert updated.title_source == "ai_generated"


def test_chat_stream_persists_visible_streamed_text_for_non_card_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api.routers import agent as agent_router

    async def _fake_stream_agent_turn_events(**_: Any):
        yield {"type": "stage_start", "stage": "interpret"}
        yield {"type": "stage_outcome", "outcome": "needs_clarification"}
        yield {"type": "token", "content": "Visible clarification."}
        yield {
            "type": "final",
            "payload": {
                "stage_outcome": "await_user_reply",
                "assistant_response": "Different final clarification.",
                "pending_strategy": {
                    "strategy": {
                        "strategy_type": None,
                        "asset_universe": [],
                        "date_range": None,
                    },
                    "missing_required_fields": ["asset_universe"],
                },
            },
        }

    monkeypatch.setattr(
        agent_router,
        "stream_agent_turn_events",
        _fake_stream_agent_turn_events,
    )
    client = _client()
    conversation = _conversation(client)

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "hello from browser smoke",
            "language": "en",
        },
    )

    assert response.status_code == 200
    payload = _final_payload(response.text)
    assert payload["assistant_response"] == "Visible clarification."

    messages = client.get(f"/api/v1/conversations/{conversation['id']}/messages").json()[
        "items"
    ]
    assert messages[-1]["id"] == payload["message_id"]
    assert messages[-1]["content"] == "Visible clarification."
