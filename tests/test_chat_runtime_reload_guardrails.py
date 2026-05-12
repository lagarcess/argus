from __future__ import annotations

import json
from typing import Any

from argus.api.main import app
from argus.api.message_store import create_message
from argus.api.schemas import BacktestRun
from argus.domain.store import utcnow
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
    response = client.post("/api/v1/conversations", json={"language": "en"})
    assert response.status_code == 200
    return response.json()["conversation"]


def _user_id(client: TestClient) -> str:
    response = client.get("/api/v1/me")
    assert response.status_code == 200
    return str(response.json()["user"]["id"])


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


def _confirmation_metadata() -> dict[str, Any]:
    return {
        "conversation_mode": "confirm",
        "agent_runtime_stage_outcome": "await_approval",
        "confirmation_payload": {
            "strategy": {
                "strategy_type": "buy_and_hold",
                "strategy_thesis": "Buy and hold Apple.",
                "asset_universe": ["AAPL"],
                "asset_class": "equity",
                "date_range": "past year",
            },
            "optional_parameters": {},
        },
        "confirmation_card": {
            "title": "AAPL buy and hold",
            "statusLabel": "Ready to run",
            "summary": "I read this as AAPL using a buy and hold approach.",
            "rows": [
                {"label": "Strategy", "value": "Buy and hold"},
                {"label": "Assets", "value": "AAPL"},
                {"label": "Period", "value": "past year"},
            ],
            "assumptions": ["Benchmark: SPY"],
            "actions": [
                {
                    "id": "run-backtest",
                    "type": "run_backtest",
                    "label": "Run backtest",
                    "presentation": "confirmation",
                    "payload": {},
                }
            ],
        },
    }


def _pending_strategy_metadata() -> dict[str, Any]:
    return {
        "conversation_mode": "setup",
        "agent_runtime_stage_outcome": "await_user_reply",
        "pending_strategy": {
            "strategy": {
                "strategy_type": "buy_and_hold",
                "strategy_thesis": "Buy and hold Apple.",
                "asset_universe": ["AAPL"],
                "asset_class": "equity",
                "date_range": "past year",
            },
            "requested_field": "initial_capital",
            "missing_required_fields": ["initial_capital"],
        },
    }


def test_confirmation_action_uses_structured_metadata_only_when_checkpoint_missing(
    monkeypatch,
) -> None:
    from argus.api.routers import agent as agent_router

    captured: dict[str, Any] = {}

    async def _runtime(**kwargs: Any):
        captured.update(kwargs)
        snapshot = kwargs["fallback_latest_task_snapshot"]
        assert snapshot.pending_strategy_summary is not None
        assert snapshot.pending_strategy_summary.asset_universe == ["AAPL"]
        yield {"type": "stage_start", "stage": "interpret"}
        yield {
            "type": "final",
            "payload": {
                "stage_outcome": "ready_to_respond",
                "assistant_response": "I tested Apple from the recovered confirmation.",
                "final_response_payload": {
                    "result": {
                        "execution_status": "succeeded",
                        "resolved_strategy": {
                            "strategy_type": "buy_and_hold",
                            "asset_universe": ["AAPL"],
                        },
                        "resolved_parameters": {"timeframe": "1D"},
                        "metrics": {
                            "aggregate": {
                                "performance": {"total_return_pct": 11.5}
                            },
                            "by_symbol": {},
                        },
                        "benchmark_metrics": {"benchmark_symbol": "SPY"},
                    },
                    "result_card": {
                        "title": "AAPL buy and hold",
                        "date_range": {
                            "start": "2025-05-07",
                            "end": "2026-05-07",
                            "display": "May 7, 2025 to May 7, 2026",
                        },
                        "status_label": "Simulation Complete",
                        "rows": [
                            {
                                "key": "total_return_pct",
                                "label": "Total Return (%)",
                                "value": "+11.5%",
                            }
                        ],
                        "assumptions": ["Benchmark: SPY"],
                        "actions": [
                            {"type": "save_strategy", "label": "Save strategy"}
                        ],
                    },
                },
            },
        }

    monkeypatch.setattr(agent_router, "stream_agent_turn_events", _runtime)
    client = _client()
    conversation = _conversation(client)
    user_id = _user_id(client)
    create_message(
        user_id=user_id,
        conversation_id=conversation["id"],
        role="assistant",
        content="I read this as AAPL using a buy and hold approach.",
        metadata=_confirmation_metadata(),
    )

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "action": {
                "type": "run_backtest",
                "label": "Run backtest",
                "presentation": "confirmation",
                "payload": {},
            },
            "language": "en",
        },
    )

    assert response.status_code == 200
    assert captured["thread_id"] == conversation["id"]
    run = _stream_payloads(response.text, "final")[0]["run"]
    assert run["symbols"] == ["AAPL"]


def test_pending_strategy_metadata_fallback_carries_text_turn_context(
    monkeypatch,
) -> None:
    from argus.api.routers import agent as agent_router

    captured: dict[str, Any] = {}

    async def _runtime(**kwargs: Any):
        captured.update(kwargs)
        snapshot = kwargs["fallback_latest_task_snapshot"]
        assert snapshot.pending_strategy_summary is not None
        assert snapshot.pending_strategy_summary.asset_universe == ["AAPL"]
        assert kwargs["fallback_selected_thread_metadata"]["requested_field"] == (
            "initial_capital"
        )
        yield {"type": "stage_start", "stage": "interpret"}
        yield {
            "type": "final",
            "payload": {
                "stage_outcome": "await_approval",
                "assistant_response": "I read this as AAPL buy and hold.",
                "confirmation_payload": {
                    "strategy": {
                        "strategy_type": "buy_and_hold",
                        "asset_universe": ["AAPL"],
                        "date_range": "past year",
                    },
                    "optional_parameters": {
                        "initial_capital": {
                            "value": 10000,
                            "source": "user",
                            "label": "Initial capital",
                        }
                    },
                },
            },
        }

    monkeypatch.setattr(agent_router, "stream_agent_turn_events", _runtime)
    client = _client()
    conversation = _conversation(client)
    user_id = _user_id(client)
    create_message(
        user_id=user_id,
        conversation_id=conversation["id"],
        role="assistant",
        content="How much capital would you like to allocate?",
        metadata=_pending_strategy_metadata(),
    )

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "10k",
            "language": "en",
        },
    )

    assert response.status_code == 200
    final = _stream_payloads(response.text, "final")[0]
    assert final["confirmation"]["summary"]
    assert captured["thread_id"] == conversation["id"]


def test_newer_unrelated_assistant_message_blocks_pending_strategy_fallback(
    monkeypatch,
) -> None:
    from argus.api.routers import agent as agent_router

    captured: dict[str, Any] = {}

    async def _runtime(**kwargs: Any):
        captured.update(kwargs)
        yield {
            "type": "final",
            "payload": {
                "stage_outcome": "ready_to_respond",
                "assistant_response": "I need the strategy again.",
            },
        }

    monkeypatch.setattr(agent_router, "stream_agent_turn_events", _runtime)
    client = _client()
    conversation = _conversation(client)
    user_id = _user_id(client)
    create_message(
        user_id=user_id,
        conversation_id=conversation["id"],
        role="assistant",
        content="How much capital would you like to allocate?",
        metadata=_pending_strategy_metadata(),
    )
    create_message(
        user_id=user_id,
        conversation_id=conversation["id"],
        role="assistant",
        content="Let's start fresh. What would you like to test?",
        metadata={"agent_runtime_stage_outcome": "ready_to_respond"},
    )

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "10k",
            "language": "en",
        },
    )

    assert response.status_code == 200
    assert captured["fallback_latest_task_snapshot"] is None
    assert captured["fallback_selected_thread_metadata"] is None


def test_stale_confirmation_card_without_structured_payload_returns_recovery(
    monkeypatch,
) -> None:
    from argus.api.routers import agent as agent_router

    runtime_calls = 0

    async def _runtime(**_: Any):
        nonlocal runtime_calls
        runtime_calls += 1
        yield {"type": "final", "payload": {"stage_outcome": "ready_to_respond"}}

    monkeypatch.setattr(agent_router, "stream_agent_turn_events", _runtime)
    client = _client()
    conversation = _conversation(client)
    user_id = _user_id(client)
    metadata = _confirmation_metadata()
    metadata.pop("confirmation_payload")
    create_message(
        user_id=user_id,
        conversation_id=conversation["id"],
        role="assistant",
        content="I read this as AAPL using a buy and hold approach.",
        metadata=metadata,
    )

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "action": {
                "type": "run_backtest",
                "label": "Run backtest",
                "presentation": "confirmation",
                "payload": {},
            },
            "language": "en",
        },
    )

    assert response.status_code == 200
    assert runtime_calls == 0
    text = _stream_payloads(response.text, "token")[0]["content"]
    assert "lost the active confirmation state" in text
    assert "confirm it again" in text


def test_canceled_confirmation_does_not_recover_older_card(monkeypatch) -> None:
    from argus.api.routers import agent as agent_router

    runtime_calls = 0

    async def _runtime(**_: Any):
        nonlocal runtime_calls
        runtime_calls += 1
        yield {"type": "final", "payload": {"stage_outcome": "ready_to_respond"}}

    monkeypatch.setattr(agent_router, "stream_agent_turn_events", _runtime)
    client = _client()
    conversation = _conversation(client)
    user_id = _user_id(client)
    create_message(
        user_id=user_id,
        conversation_id=conversation["id"],
        role="assistant",
        content="I read this as AAPL using a buy and hold approach.",
        metadata=_confirmation_metadata(),
    )
    create_message(
        user_id=user_id,
        conversation_id=conversation["id"],
        role="assistant",
        content="No problem. I will leave that draft unrun.",
        metadata={
            "conversation_mode": "guide",
            "agent_runtime_stage_outcome": "ready_to_respond",
            "chat_action": {
                "type": "cancel_confirmation",
                "label": "Cancel",
                "presentation": "confirmation",
                "payload": {},
            },
        },
    )

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "action": {
                "type": "run_backtest",
                "label": "Run backtest",
                "presentation": "confirmation",
                "payload": {},
            },
            "language": "en",
        },
    )

    assert response.status_code == 409
    assert runtime_calls == 0


def test_result_followup_after_reload_carries_latest_run_reference(
    monkeypatch,
) -> None:
    from argus.api import state as api_state
    from argus.api.routers import agent as agent_router

    captured: dict[str, Any] = {}

    async def _runtime(**kwargs: Any):
        captured.update(kwargs)
        yield {"type": "stage_start", "stage": "interpret"}
        yield {
            "type": "final",
            "payload": {
                "stage_outcome": "ready_to_respond",
                "assistant_response": "It underperformed SPY by 4.2 percentage points.",
            },
        }

    monkeypatch.setattr(agent_router, "stream_agent_turn_events", _runtime)
    client = _client()
    conversation = _conversation(client)
    user_id = _user_id(client)
    run_id = api_state.store.new_id()
    run = BacktestRun(
        id=run_id,
        conversation_id=conversation["id"],
        strategy_id=None,
        status="completed",
        asset_class="equity",
        symbols=["AAPL"],
        allocation_method="equal_weight",
        benchmark_symbol="SPY",
        metrics={
            "aggregate": {
                "performance": {
                    "total_return_pct": 8.1,
                    "benchmark_return_pct": 12.3,
                    "delta_vs_benchmark_pct": -4.2,
                }
            },
            "by_symbol": {},
        },
        config_snapshot={"template": "buy_and_hold", "symbols": ["AAPL"]},
        conversation_result_card={
            "title": "AAPL buy and hold",
            "date_range": {
                "start": "2025-05-07",
                "end": "2026-05-07",
                "display": "May 7, 2025 to May 7, 2026",
            },
            "status_label": "Simulation Complete",
            "rows": [
                {
                    "key": "benchmark_delta",
                    "label": "Benchmark",
                    "value": "-4.2% vs SPY",
                }
            ],
            "assumptions": ["Benchmark: SPY"],
            "actions": [{"type": "show_breakdown", "label": "Show a breakdown"}],
        },
        created_at=utcnow(),
        chart=None,
        trades=[],
    )
    api_state.store.backtest_runs[run_id] = run
    api_state.store.backtest_run_owners[run_id] = user_id
    create_message(
        user_id=user_id,
        conversation_id=conversation["id"],
        role="assistant",
        content="I tested that idea.",
        metadata={
            "conversation_mode": "result_review",
            "result_card": run.conversation_result_card,
            "result_run_id": run.id,
            "latest_run_id": run.id,
            "result_conversation_id": conversation["id"],
        },
    )

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "Why did it underperform?",
            "language": "en",
        },
    )

    assert response.status_code == 200
    snapshot = captured["fallback_latest_task_snapshot"]
    reference = snapshot.latest_backtest_result_reference
    assert reference is not None
    assert reference.artifact_id == run_id
    assert reference.metadata["metrics"]["aggregate"]["performance"][
        "delta_vs_benchmark_pct"
    ] == -4.2
    assert reference.metadata["conversation_id"] == conversation["id"]


def test_save_strategy_action_without_canonical_run_id_does_not_save_latest() -> None:
    from argus.api import state as api_state

    client = _client()
    conversation = _conversation(client)
    user_id = _user_id(client)
    run_id = api_state.store.new_id()
    api_state.store.backtest_runs[run_id] = BacktestRun(
        id=run_id,
        conversation_id=conversation["id"],
        strategy_id=None,
        status="completed",
        asset_class="equity",
        symbols=["MSFT"],
        allocation_method="equal_weight",
        benchmark_symbol="SPY",
        metrics={"aggregate": {"performance": {"total_return_pct": 6.2}}},
        config_snapshot={"template": "buy_and_hold", "symbols": ["MSFT"]},
        conversation_result_card={
            "title": "MSFT buy and hold",
            "rows": [
                {"key": "total_return_pct", "label": "Total Return", "value": "+6.2%"}
            ],
            "assumptions": ["Benchmark: SPY"],
        },
        created_at=utcnow(),
        chart=None,
        trades=[],
    )
    api_state.store.backtest_run_owners[run_id] = user_id

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "action": {
                "type": "save_strategy",
                "label": "Save strategy",
                "presentation": "result",
                "payload": {},
            },
            "language": "en",
        },
    )

    assert response.status_code == 200
    text = _stream_payloads(response.text, "token")[0]["content"]
    assert "could not find" in text
    assert client.get("/api/v1/strategies").json()["items"] == []
