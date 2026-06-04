from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from argus.api.main import app
from fastapi.testclient import TestClient


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
    from argus.api.routers import agent as agent_router

    captured: dict[str, Any] = {}

    async def _fake_stream_agent_turn_events(**kwargs: Any):
        captured.update(kwargs)
        yield {"type": "stage_start", "stage": "interpret"}
        yield {"type": "token", "content": "Here is your buy-and-hold result."}
        yield {
            "type": "final",
            "payload": {
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
            },
        }

    monkeypatch.setattr(
        agent_router,
        "stream_agent_turn_events",
        _fake_stream_agent_turn_events,
    )

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
    assert '"type":"stage_start","stage":"interpret"' in response.text
    assert '"type":"final"' in response.text
    assert '"type":"token"' in response.text
    assert "Here is your buy-and-hold result." in response.text
    assert '"run"' in response.text

    result_line = next(
        line.removeprefix("data: ")
        for line in response.text.splitlines()
        if line.startswith("data: {") and '"run"' in line
    )
    run_payload = json.loads(result_line)["payload"]["run"]
    assert run_payload["conversation_result_card"]["title"] == "TSLA Buy and Hold"

    messages = client.get(f"/api/v1/conversations/{conversation['id']}/messages")
    assert messages.status_code == 200
    assert [message["role"] for message in messages.json()["items"]] == [
        "user",
        "assistant",
    ]


def test_chat_stream_production_path_uses_astream_events_not_invoke() -> None:
    api_source = Path("src/argus/api/main.py").read_text(encoding="utf-8")
    runtime_source = Path("src/argus/agent_runtime/runtime.py").read_text(
        encoding="utf-8"
    )

    assert ".astream_events(" in runtime_source
    assert "workflow.invoke(" not in api_source
    assert "workflow.invoke(" not in runtime_source
    assert "InMemorySessionManager" not in api_source
    assert "InMemorySessionManager" not in runtime_source


def test_chat_stream_falls_back_conversationally_for_unsupported_runtime_result(
    monkeypatch,
) -> None:
    from argus.api.routers import agent as agent_router

    async def _fake_stream_agent_turn_events(**_: Any):
        yield {"type": "stage_start", "stage": "interpret"}
        yield {
            "type": "final",
            "payload": {
                "stage_outcome": "await_user_reply",
                "assistant_prompt": (
                    "Trailing stops are not supported yet. "
                    "I can help reframe this into a supported backtest."
                ),
                "final_response_payload": {
                    "error": "unsupported_capability",
                },
            },
        }

    monkeypatch.setattr(
        agent_router,
        "stream_agent_turn_events",
        _fake_stream_agent_turn_events,
    )

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
    assert '"type":"token"' in response.text
    assert "supported backtest" in response.text.lower()
    assert '"run"' not in response.text


def test_runtime_confirmation_card_resolves_relative_period_and_natural_actions(
    monkeypatch,
) -> None:
    from argus.api.chat import confirmation as chat_service

    monkeypatch.setattr(
        chat_service,
        "_confirmation_today",
        lambda: date(2026, 5, 3),
    )

    card = chat_service.runtime_confirmation_card(
        {
            "stage_outcome": "await_approval",
            "confirmation_payload": {
                "strategy": {
                    "strategy_type": "rsi_threshold",
                    "strategy_thesis": "Run the supported RSI preset on Google.",
                    "asset_universe": ["GOOGL"],
                    "asset_class": "equity",
                    "date_range": "past year",
                    "entry_logic": "Buy when RSI(14) drops to 30 or below",
                    "exit_logic": "Sell when RSI(14) rises to 55 or above",
                    "capital_amount": 10000,
                },
                "optional_parameters": {
                    "timeframe": {"value": "1D", "source": "default"},
                    "initial_capital": {"value": 1000.0, "source": "default"},
                },
                "launch_payload": {
                    "strategy_type": "indicator_threshold",
                    "symbol": "GOOGL",
                    "symbols": ["GOOGL"],
                    "timeframe": "1D",
                    "date_range": {"start": "2025-05-03", "end": "2026-05-03"},
                    "entry_rule": {
                        "indicator": "rsi",
                        "operator": "below",
                        "period": 14,
                        "threshold": 30,
                    },
                    "exit_rule": {
                        "indicator": "rsi",
                        "operator": "above",
                        "period": 14,
                        "threshold": 55,
                    },
                    "sizing_mode": "capital_amount",
                    "capital_amount": 10000,
                    "benchmark_symbol": "SPY",
                },
                "validation": {"executable": True},
            },
        }
    )

    assert card is not None
    period = next(row["value"] for row in card["rows"] if row["label"] == "Period")
    assert period == "past year (May 3, 2025 - May 3, 2026)"
    assert card["summary"] == (
        "Ready to test GOOGL with an RSI threshold over past year, "
        "May 3, 2025 - May 3, 2026."
    )
    run_action = next(
        action for action in card["actions"] if action["type"] == "run_backtest"
    )
    assert run_action["id"] == "run-backtest"
    assert run_action["presentation"] == "confirmation"
    assert run_action["payload"]["confirmation_id"] == card["confirmation_id"]
    assert run_action["payload"]["launch_payload_hash"]


def test_runtime_confirmation_card_expands_compact_period_and_hides_indicator_cadence(
    monkeypatch,
) -> None:
    from argus.api.chat import confirmation as chat_service

    monkeypatch.setattr(
        chat_service,
        "_confirmation_today",
        lambda: date(2026, 5, 3),
    )

    card = chat_service.runtime_confirmation_card(
        {
            "stage_outcome": "await_approval",
            "confirmation_payload": {
                "strategy": {
                    "strategy_type": "rsi_threshold",
                    "strategy_thesis": "Run the supported RSI preset on Google.",
                    "asset_universe": ["GOOGL"],
                    "asset_class": "equity",
                    "date_range": "1y",
                    "cadence": "daily",
                    "entry_logic": "RSI drops below 30",
                    "exit_logic": "RSI rises above 55",
                    "capital_amount": 10000,
                },
                "optional_parameters": {},
            },
        }
    )

    assert card is not None
    rows_by_label = {row["label"]: row["value"] for row in card["rows"]}
    assert rows_by_label["Period"] == "past year (May 3, 2025 - May 3, 2026)"
    assert "Cadence" not in rows_by_label


def test_runtime_confirmation_card_simplifies_counted_one_year_period(
    monkeypatch,
) -> None:
    from argus.api.chat import confirmation as chat_service

    monkeypatch.setattr(
        chat_service,
        "_confirmation_today",
        lambda: date(2026, 5, 3),
    )

    card = chat_service.runtime_confirmation_card(
        {
            "stage_outcome": "await_approval",
            "confirmation_payload": {
                "strategy": {
                    "strategy_type": "rsi_threshold",
                    "strategy_thesis": "Run the supported RSI preset on Google.",
                    "asset_universe": ["GOOGL"],
                    "asset_class": "equity",
                    "date_range": "past 1 year",
                    "entry_logic": "RSI drops below 30",
                    "exit_logic": "RSI rises above 55",
                },
                "optional_parameters": {},
            },
        }
    )

    assert card is not None
    rows_by_label = {row["label"]: row["value"] for row in card["rows"]}
    assert rows_by_label["Period"] == "past year (May 3, 2025 - May 3, 2026)"


def test_runtime_confirmation_card_formats_machine_date_tokens(
    monkeypatch,
) -> None:
    from argus.api.chat import confirmation as chat_service

    monkeypatch.setattr(
        chat_service,
        "_confirmation_today",
        lambda: date(2026, 5, 3),
    )

    def card_for(date_range: str) -> dict[str, Any]:
        card = chat_service.runtime_confirmation_card(
            {
                "stage_outcome": "await_approval",
                "confirmation_payload": {
                    "strategy": {
                        "strategy_type": "indicator_threshold",
                        "strategy_thesis": "Run a dip-buying strategy on Apple.",
                        "asset_universe": ["AAPL"],
                        "asset_class": "equity",
                        "date_range": date_range,
                        "entry_logic": "Buy when RSI <= 30",
                        "exit_logic": "Sell when RSI >= 55",
                    },
                    "optional_parameters": {},
                },
            }
        )
        assert card is not None
        return card

    last_three_months = card_for("last_3_months")
    ytd = card_for("year_to_date")

    last_rows = {row["label"]: row["value"] for row in last_three_months["rows"]}
    ytd_rows = {row["label"]: row["value"] for row in ytd["rows"]}
    assert last_rows["Strategy"] == "Dip Buying"
    assert last_rows["Period"] == "past 3 months (February 3, 2026 - May 3, 2026)"
    assert ytd_rows["Period"] == "year to date (January 1, 2026 - May 3, 2026)"


def test_runtime_confirmation_card_formats_structured_date_range(
    monkeypatch,
) -> None:
    from argus.api.chat import confirmation as chat_service

    monkeypatch.setattr(
        chat_service,
        "_confirmation_today",
        lambda: date(2026, 5, 3),
    )

    card = chat_service.runtime_confirmation_card(
        {
            "stage_outcome": "await_approval",
            "confirmation_payload": {
                "strategy": {
                    "strategy_type": "buy_and_hold",
                    "strategy_thesis": "Buy and hold Bitcoin from January 1 last year.",
                    "asset_universe": ["BTC"],
                    "asset_class": "crypto",
                    "date_range": {"start": "2025-01-01", "end": "today"},
                },
                "optional_parameters": {},
            },
        }
    )

    assert card is not None
    rows_by_label = {row["label"]: row["value"] for row in card["rows"]}
    assert rows_by_label["Period"] == "January 1, 2025 - May 3, 2026"
