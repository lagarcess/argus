from __future__ import annotations

import json
from typing import Any

import pytest
from argus.api.main import app
from argus.domain.engine import SymbolAsset
from argus.domain.indicators import IndicatorInfo
from argus.domain.market_data.assets import ResolvedAsset
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


def _stream_payloads(stream: str, event_name: str) -> list[dict[str, Any]]:
    payloads = []
    for part in stream.split("\n\n"):
        if f"event: {event_name}" not in part:
            continue
        data_line = next(line for line in part.splitlines() if line.startswith("data: "))
        payloads.append(json.loads(data_line.removeprefix("data: ")))
    return payloads


def _conversation(client: TestClient) -> dict[str, Any]:
    return client.post("/api/v1/conversations", json={}).json()["conversation"]


def _confirmation_runtime_result() -> dict[str, Any]:
    return {
        "stage_outcome": "await_approval",
        "assistant_response": "I read this as AAPL buy and hold.",
        "confirmation_payload": {
            "strategy": {
                "strategy_type": "buy_and_hold",
                "asset_universe": ["AAPL"],
                "date_range": {"start": "2025-05-03", "end": "2026-05-03"},
                "capital_amount": 10000,
            },
            "optional_parameters": {
                "initial_capital": {
                    "value": 10000.0,
                    "source": "default",
                    "label": "Initial capital",
                    "description": "Starting cash",
                },
                "timeframe": {
                    "value": "1D",
                    "source": "default",
                    "label": "Timeframe",
                    "description": "Bar interval",
                },
                "fees": {"value": 0.0, "source": "default", "label": "Fees"},
                "slippage": {"value": 0.0, "source": "default", "label": "Slippage"},
            },
        },
    }


def _result_runtime_result() -> dict[str, Any]:
    result_card = {
        "title": "AAPL buy and hold",
        "date_range": {
            "start": "2025-05-03",
            "end": "2026-05-03",
            "display": "May 3, 2025 to May 3, 2026",
        },
        "status_label": "Completed",
        "rows": [
            {"key": "total_return_pct", "label": "Total Return (%)", "value": "+12.4%"},
            {"key": "benchmark_delta", "label": "Benchmark", "value": "+2.1% vs SPY"},
        ],
        "assumptions": ["$10,000 starting capital", "1D bars", "Benchmark: SPY"],
        "benchmark_note": "Compared with SPY.",
        "actions": [
            {
                "id": "show-breakdown",
                "type": "show_breakdown",
                "label": "Show a breakdown",
                "presentation": "result",
                "payload": {},
            },
            {
                "id": "add-to-collection",
                "type": "add_to_collection",
                "label": "Add to collection",
                "presentation": "result",
                "payload": {},
            },
            {
                "id": "refine-strategy",
                "type": "refine_strategy",
                "label": "Refine strategy",
                "presentation": "result",
                "payload": {},
            },
        ],
    }
    return {
        "stage_outcome": "end_run",
        "assistant_response": "Short grounded summary from the runtime.",
        "final_response_payload": {
            "result_card": result_card,
            "result": {
                "resolved_strategy": {
                    "strategy_type": "buy_and_hold",
                    "symbol": "AAPL",
                    "asset_universe": ["AAPL"],
                },
                "resolved_parameters": {
                    "timeframe": "1D",
                    "date_range": "May 3, 2025 to May 3, 2026",
                },
                "metrics": {
                    "aggregate": {
                        "performance": {
                            "total_return_pct": 12.4,
                            "delta_vs_benchmark_pct": 2.1,
                        }
                    }
                },
                "benchmark_metrics": {"benchmark_symbol": "SPY"},
            },
        },
    }


@pytest.fixture(autouse=True)
def _patch_runtime_io(monkeypatch: pytest.MonkeyPatch) -> None:
    from argus.api import main as api_main

    monkeypatch.setattr(api_main, "supabase_gateway", None)
    monkeypatch.setattr(
        api_main,
        "classify_symbol",
        lambda symbol: SymbolAsset(symbol=symbol.strip().upper(), asset_class="equity"),
    )


def test_chat_stream_emits_structured_confirmation_actions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api import main as api_main

    seen: dict[str, Any] = {}

    def _runtime(**kwargs: Any) -> dict[str, Any]:
        seen.update(kwargs)
        return _confirmation_runtime_result()

    monkeypatch.setattr(api_main, "run_agent_turn", _runtime)
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
    assert seen["thread_id"] == conversation["id"]
    assert seen["message"] == "Buy and hold Apple over the past year"
    confirmation = _stream_payloads(response.text, "confirmation")[0]["confirmation"]
    assert confirmation["actions"] == [
        {
            "id": "run-backtest",
            "type": "run_backtest",
            "label": "Run backtest",
            "presentation": "confirmation",
            "payload": {},
        },
        {
            "id": "change-dates",
            "type": "change_dates",
            "label": "Change dates",
            "presentation": "confirmation",
            "payload": {},
        },
        {
            "id": "change-asset",
            "type": "change_asset",
            "label": "Change asset",
            "presentation": "confirmation",
            "payload": {},
        },
        {
            "id": "adjust-assumptions",
            "type": "adjust_assumptions",
            "label": "Adjust assumptions",
            "presentation": "confirmation",
            "payload": {},
        },
    ]


def test_confirmation_action_routes_without_fake_yes_and_orders_result_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api import main as api_main

    seen_messages: list[str] = []

    def _runtime(**kwargs: Any) -> dict[str, Any]:
        seen_messages.append(kwargs["message"])
        return _result_runtime_result()

    monkeypatch.setattr(api_main, "run_agent_turn", _runtime)
    client = _client()
    conversation = _conversation(client)

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
    assert seen_messages == ["run backtest"]
    assert "Run backtest" in client.get(
        f"/api/v1/conversations/{conversation['id']}/messages"
    ).text
    assert response.text.index("event: result") < response.text.index("event: token")
    run = _stream_payloads(response.text, "result")[0]["run"]
    assert [action["type"] for action in run["conversation_result_card"]["actions"]] == [
        "show_breakdown",
        "add_to_collection",
        "refine_strategy",
    ]


def test_result_breakdown_action_uses_stored_result_without_rerun(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api import main as api_main

    runtime_calls = 0

    def _runtime(**_: Any) -> dict[str, Any]:
        nonlocal runtime_calls
        runtime_calls += 1
        return _result_runtime_result()

    monkeypatch.setattr(api_main, "run_agent_turn", _runtime)
    monkeypatch.setattr(api_main, "build_openrouter_model", lambda _task: None)
    client = _client()
    conversation = _conversation(client)

    first = client.post(
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
    run_id = _stream_payloads(first.text, "result")[0]["run"]["id"]

    second = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "action": {
                "type": "show_breakdown",
                "label": "Show a breakdown",
                "presentation": "result",
                "payload": {"run_id": run_id},
            },
            "language": "en",
        },
    )

    assert second.status_code == 200
    assert runtime_calls == 1
    breakdown = _stream_payloads(second.text, "token")[0]["text"]
    assert "Total Return (%)" in breakdown
    assert "Benchmark" in breakdown
    assert run_id in client.get(f"/api/v1/conversations/{conversation['id']}/messages").text


def test_chat_stream_requires_message_or_action() -> None:
    client = _client()
    conversation = _conversation(client)

    response = client.post(
        "/api/v1/chat/stream",
        json={"conversation_id": conversation["id"], "language": "en"},
    )

    assert response.status_code == 422


def test_learn_basics_symbol_followup_does_not_leak_entry_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    client = TestClient(app)
    client.post("/api/v1/dev/reset")
    client.patch(
        "/api/v1/me",
        json={
            "onboarding": {
                "stage": "primary_goal_selection",
                "language_confirmed": True,
                "primary_goal": None,
                "completed": False,
            }
        },
    )
    conversation = _conversation(client)

    first = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "__ONBOARDING_GOAL__:learn_basics",
            "language": "en",
        },
    )
    second = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "apple",
            "language": "en",
        },
    )

    first_text = _stream_payloads(first.text, "token")[0]["text"]
    second_text = _stream_payloads(second.text, "token")[0]["text"]
    assert "help you choose a sensible next step" in first_text
    assert "What should trigger the buy?" not in second_text
    assert "I can work with AAPL" in second_text
    assert "simple test" in second_text


def test_discovery_endpoints_return_assets_and_indicators(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api import main as api_main

    monkeypatch.setattr(
        api_main,
        "search_assets",
        lambda q, limit=12: [
            ResolvedAsset(
                canonical_symbol="AAPL",
                asset_class="equity",
                name="Apple Inc.",
                raw_symbol=q,
            )
        ],
    )
    monkeypatch.setattr(
        api_main,
        "search_indicators",
        lambda q, limit=12: [IndicatorInfo("rsi", "RSI", "Relative Strength Index", "supported")],
    )
    client = _client()

    assets = client.get("/api/v1/discovery/assets?q=apple&limit=5")
    indicators = client.get("/api/v1/discovery/indicators?q=rsi&limit=5")

    assert assets.status_code == 200
    assert assets.json()["items"][0]["insert_text"] == "AAPL"
    assert indicators.status_code == 200
    assert indicators.json()["items"][0]["provider"] == "pandas-ta-classic"
