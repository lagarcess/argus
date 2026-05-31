from __future__ import annotations

import json
from typing import Any

import pytest
from argus.api.main import app
from argus.api.schemas import BacktestRun
from argus.domain.engine import SymbolAsset
from argus.domain.indicators import IndicatorInfo
from argus.domain.market_data.assets import ResolvedAsset
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


def _stream_payloads(stream: str, event_name: str) -> list[dict[str, Any]]:
    payloads = []
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
        payload = json.loads(raw)
        event_line = next(
            (line for line in part.splitlines() if line.startswith("event: ")),
            None,
        )
        if event_line == f"event: {event_name}":
            payloads.append(payload)
            continue
        if payload.get("type") == event_name:
            if event_name == "token":
                payloads.append(
                    {"text": payload.get("content") or payload.get("text") or ""}
                )
            else:
                payloads.append(payload)
            continue
        if payload.get("type") != "final":
            continue
        final_payload = payload.get("payload")
        if not isinstance(final_payload, dict):
            continue
        if event_name == "confirmation" and isinstance(
            final_payload.get("confirmation"), dict
        ):
            payloads.append({"confirmation": final_payload["confirmation"]})
        if event_name == "result" and isinstance(final_payload.get("run"), dict):
            run = final_payload["run"]
            payloads.append({"run": run, "payload": {"run": run}})
        if event_name == "final":
            payloads.append(final_payload)
    return payloads


def _conversation(client: TestClient) -> dict[str, Any]:
    return client.post("/api/v1/conversations", json={}).json()["conversation"]


def _confirmation_runtime_result() -> dict[str, Any]:
    return {
        "stage_outcome": "await_approval",
        "assistant_response": "Ready to test AAPL with buy and hold.",
        "confirmation_payload": {
            "strategy": {
                "strategy_type": "buy_and_hold",
                "asset_universe": ["AAPL"],
                "date_range": {"start": "2025-05-03", "end": "2026-05-03"},
                "capital_amount": 10000,
            },
            "optional_parameters": {
                "initial_capital": {
                    "value": 1000.0,
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
            "launch_payload": {
                "strategy_type": "buy_and_hold",
                "symbol": "AAPL",
                "symbols": ["AAPL"],
                "timeframe": "1D",
                "date_range": {"start": "2025-05-03", "end": "2026-05-03"},
                "sizing_mode": "capital_amount",
                "capital_amount": 1000.0,
                "benchmark_symbol": "SPY",
            },
            "validation": {"executable": True},
        },
    }


def _pending_runtime_result() -> dict[str, Any]:
    return {
        "stage_outcome": "await_user_reply",
        "assistant_prompt": "What asset should I use instead?",
        "requested_field": "asset_universe",
        "pending_strategy": {
            "strategy": {
                "strategy_type": "buy_and_hold",
                "strategy_thesis": "Buy and hold Apple.",
                "asset_universe": ["AAPL"],
                "asset_class": "equity",
                "date_range": "past year",
            },
            "requested_field": "asset_universe",
            "missing_required_fields": ["asset_universe"],
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
                "id": "save-strategy",
                "type": "save_strategy",
                "label": "Save strategy",
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


def _stream_events_from_runtime(runtime):
    async def _events(**kwargs: Any):
        yield {"type": "final", "payload": runtime(**kwargs)}

    return _events


@pytest.fixture(autouse=True)
def _patch_runtime_io(monkeypatch: pytest.MonkeyPatch) -> None:
    from argus.api import backtest_service
    from argus.api import state as api_state
    from argus.api.chat import persistence as chat_persistence

    monkeypatch.setattr(api_state, "supabase_gateway", None)
    monkeypatch.setattr(
        backtest_service,
        "classify_symbol",
        lambda symbol: SymbolAsset(symbol=symbol.strip().upper(), asset_class="equity"),
    )
    monkeypatch.setattr(
        chat_persistence,
        "classify_symbol",
        lambda symbol: SymbolAsset(symbol=symbol.strip().upper(), asset_class="equity"),
    )


def test_chat_stream_emits_structured_confirmation_actions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api.routers import agent as agent_router

    seen: dict[str, Any] = {}

    def _runtime(**kwargs: Any) -> dict[str, Any]:
        seen.update(kwargs)
        return _confirmation_runtime_result()

    monkeypatch.setattr(
        agent_router,
        "stream_agent_turn_events",
        _stream_events_from_runtime(_runtime),
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
    assert seen["thread_id"] == conversation["id"]
    assert seen["message"] == "Buy and hold Apple over the past year"
    confirmation = _stream_payloads(response.text, "confirmation")[0]["confirmation"]
    confirmation_id = confirmation["confirmation_id"]
    assert confirmation["confirmation_state"] == "active"
    assert [action["type"] for action in confirmation["actions"]] == [
        "run_backtest",
        "change_dates",
        "change_asset",
        "adjust_assumptions",
        "cancel_confirmation",
    ]
    for action in confirmation["actions"]:
        assert action["presentation"] == "confirmation"
        assert action["payload"]["confirmation_id"] == confirmation_id
        assert action["payload"]["artifact_id"] == confirmation_id
        assert action["payload"]["launch_payload_hash"]


def test_chat_stream_persists_confirmation_metadata_and_preview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api.routers import agent as agent_router

    monkeypatch.setattr(
        agent_router,
        "stream_agent_turn_events",
        _stream_events_from_runtime(lambda **_: _confirmation_runtime_result()),
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
    messages = client.get(f"/api/v1/conversations/{conversation['id']}/messages").json()[
        "items"
    ]
    assistant = messages[-1]
    assert assistant["role"] == "assistant"
    assert assistant["metadata"]["confirmation_card"]["title"] == "AAPL buy and hold"
    conversations = client.get("/api/v1/conversations").json()["items"]
    assert conversations[0]["id"] == conversation["id"]
    assert conversations[0]["last_message_preview"] == assistant["content"]
    assert "AAPL" in conversations[0]["last_message_preview"]


def test_chat_stream_persists_pending_strategy_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api.routers import agent as agent_router

    monkeypatch.setattr(
        agent_router,
        "stream_agent_turn_events",
        _stream_events_from_runtime(lambda **_: _pending_runtime_result()),
    )
    client = _client()
    conversation = _conversation(client)

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "change asset",
            "language": "en",
        },
    )

    assert response.status_code == 200
    final = _stream_payloads(response.text, "final")[0]["payload"]
    assert final["pending_strategy"]["requested_field"] == "asset_universe"
    messages = client.get(f"/api/v1/conversations/{conversation['id']}/messages").json()[
        "items"
    ]
    assistant = messages[-1]
    assert assistant["role"] == "assistant"
    assert assistant["metadata"]["pending_strategy"]["strategy"]["asset_universe"] == [
        "AAPL"
    ]
    assert assistant["metadata"]["pending_strategy"]["requested_field"] == (
        "asset_universe"
    )


def test_confirmation_action_requires_pending_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api.routers import agent as agent_router

    runtime_calls = 0

    def _runtime(**kwargs: Any) -> dict[str, Any]:
        nonlocal runtime_calls
        if kwargs["message"] != "run backtest":
            return _confirmation_runtime_result()
        runtime_calls += 1
        return _result_runtime_result()

    monkeypatch.setattr(
        agent_router,
        "stream_agent_turn_events",
        _stream_events_from_runtime(_runtime),
    )
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

    assert response.status_code == 409
    assert response.json()["code"] == "confirmation_required"
    assert runtime_calls == 0


def test_confirmation_action_routes_without_fake_yes_and_orders_result_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api.routers import agent as agent_router

    seen_messages: list[str] = []

    def _runtime(**kwargs: Any) -> dict[str, Any]:
        seen_messages.append(kwargs["message"])
        if kwargs["message"] != "run backtest":
            return _confirmation_runtime_result()
        return _result_runtime_result()

    monkeypatch.setattr(
        agent_router,
        "stream_agent_turn_events",
        _stream_events_from_runtime(_runtime),
    )
    client = _client()
    conversation = _conversation(client)
    create_confirmation = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "Buy and hold Apple over the past year",
            "language": "en",
        },
    )
    assert create_confirmation.status_code == 200

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
    assert seen_messages == [
        "Buy and hold Apple over the past year",
        "run backtest",
    ]
    assert (
        "Run backtest"
        in client.get(f"/api/v1/conversations/{conversation['id']}/messages").text
    )
    assert "event:" not in response.text
    assert response.text.count("data: [DONE]") == 1
    run = _stream_payloads(response.text, "result")[0]["run"]
    assert [action["type"] for action in run["conversation_result_card"]["actions"]] == [
        "show_breakdown",
        "save_strategy",
        "refine_strategy",
    ]
    for action in run["conversation_result_card"]["actions"]:
        assert action["presentation"] == "result"
        assert action["payload"]["run_id"] == run["id"]
        assert action["payload"]["strategy_id"] is None
        assert action["payload"]["conversation_id"] == conversation["id"]


def test_chat_stream_passes_and_persists_composer_mention_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api.routers import agent as agent_router

    seen: dict[str, Any] = {}

    def _runtime(**kwargs: Any) -> dict[str, Any]:
        seen.update(kwargs)
        return _confirmation_runtime_result()

    monkeypatch.setattr(
        agent_router,
        "stream_agent_turn_events",
        _stream_events_from_runtime(_runtime),
    )
    client = _client()
    conversation = _conversation(client)

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "Buy and hold BTC over the past year",
            "mentions": [
                {
                    "id": "asset:BTC",
                    "type": "asset",
                    "label": "Bitcoin",
                    "symbol": "BTC",
                    "description": "Crypto",
                    "insert_text": "BTC",
                    "support_status": "supported",
                }
            ],
            "language": "en",
        },
    )

    assert response.status_code == 200
    assert seen["message"] == "Buy and hold BTC over the past year"
    assert seen["context_hints"][0]["source"] == "user_mention"
    assert seen["context_hints"][0]["canonical_symbol"] == "BTC"
    assert seen["context_hints"][0]["asset_class"] == "crypto"

    user_message = client.get(
        f"/api/v1/conversations/{conversation['id']}/messages"
    ).json()["items"][0]
    assert user_message["content"] == "Buy and hold BTC over the past year"
    assert user_message["metadata"]["mentions"][0]["symbol"] == "BTC"
    assert user_message["metadata"]["resolution_provenance"][0]["source"] == (
        "user_mention"
    )
    assert user_message["metadata"]["resolution_provenance"][0]["raw_text"] == "BTC"


def test_result_breakdown_action_uses_stored_result_without_rerun(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api.chat.breakdown import (
        fallback_result_breakdown_message,
        result_breakdown_context,
    )
    from argus.api.routers import agent as agent_router

    runtime_calls = 0

    def _runtime(**kwargs: Any) -> dict[str, Any]:
        nonlocal runtime_calls
        if kwargs["message"] != "run backtest":
            return _confirmation_runtime_result()
        runtime_calls += 1
        return _result_runtime_result()

    monkeypatch.setattr(
        agent_router,
        "stream_agent_turn_events",
        _stream_events_from_runtime(_runtime),
    )
    monkeypatch.setattr(
        agent_router,
        "result_breakdown_message",
        lambda run: fallback_result_breakdown_message(result_breakdown_context(run)),
    )
    client = _client()
    conversation = _conversation(client)
    confirmation = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "Buy and hold Apple over the past year",
            "language": "en",
        },
    )
    assert confirmation.status_code == 200

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
    assert "event: result" not in second.text
    breakdown = _stream_payloads(second.text, "token")[0]["text"]
    assert "### Quick Breakdown" not in breakdown
    assert "- Result:" in breakdown
    assert "- Next step:" in breakdown
    messages = client.get(f"/api/v1/conversations/{conversation['id']}/messages")
    assert run_id in messages.text
    assistant = messages.json()["items"][-1]
    assert assistant["metadata"]["chat_action"]["type"] == "show_breakdown"
    assert assistant["metadata"]["result_run_id"] == run_id
    assert assistant["metadata"]["result_fact_bank"]["run_id"] == run_id
    assert assistant["metadata"]["result_fact_bank"]["symbols"] == ["AAPL"]
    assert "result_card" not in assistant["metadata"]


def test_breakdown_action_emits_working_stage_before_generating_text() -> None:
    from pathlib import Path

    source = Path("src/argus/api/routers/agent.py").read_text()
    action_block = source.split('payload.action.type == "show_breakdown"', 1)[1].split(
        "runtime_user = UserState", 1
    )[0]

    assert action_block.index(
        'yield sse_data({"type": "stage_start", "stage": "explain"})'
    ) < action_block.index("assistant_text = result_breakdown_message(run)")


def test_result_action_with_run_from_another_conversation_does_not_fallback() -> None:
    from argus.api import state as api_state

    client = _client()
    active_conversation = _conversation(client)
    other_conversation = _conversation(client)
    user_id = client.get("/api/v1/me").json()["user"]["id"]

    other_run_id = api_state.store.new_id()
    api_state.store.backtest_runs[other_run_id] = BacktestRun(
        id=other_run_id,
        conversation_id=other_conversation["id"],
        strategy_id=None,
        status="completed",
        asset_class="equity",
        symbols=["MSFT"],
        allocation_method="equal_weight",
        benchmark_symbol="SPY",
        metrics={"aggregate": {"performance": {"total_return_pct": 8.2}}},
        config_snapshot={"template": "buy_and_hold", "symbols": ["MSFT"]},
        conversation_result_card={
            "title": "MSFT buy and hold",
            "rows": [
                {"key": "total_return_pct", "label": "Total Return", "value": "+8.2%"}
            ],
            "assumptions": ["Benchmark: SPY"],
        },
        created_at=utcnow(),
        chart=None,
        trades=[],
    )
    api_state.store.backtest_run_owners[other_run_id] = user_id

    active_run_id = api_state.store.new_id()
    api_state.store.backtest_runs[active_run_id] = BacktestRun(
        id=active_run_id,
        conversation_id=active_conversation["id"],
        strategy_id=None,
        status="completed",
        asset_class="equity",
        symbols=["AAPL"],
        allocation_method="equal_weight",
        benchmark_symbol="SPY",
        metrics={"aggregate": {"performance": {"total_return_pct": 12.4}}},
        config_snapshot={"template": "buy_and_hold", "symbols": ["AAPL"]},
        conversation_result_card={
            "title": "AAPL buy and hold",
            "rows": [
                {"key": "total_return_pct", "label": "Total Return", "value": "+12.4%"}
            ],
            "assumptions": ["Benchmark: SPY"],
        },
        created_at=utcnow(),
        chart=None,
        trades=[],
    )
    api_state.store.backtest_run_owners[active_run_id] = user_id

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": active_conversation["id"],
            "action": {
                "type": "save_strategy",
                "label": "Save strategy",
                "presentation": "result",
                "payload": {
                    "run_id": other_run_id,
                    "conversation_id": active_conversation["id"],
                },
            },
            "language": "en",
        },
    )

    assert response.status_code == 200
    text = _stream_payloads(response.text, "token")[0]["text"]
    assert "could not find" in text
    assert client.get("/api/v1/strategies").json()["items"] == []


def test_show_breakdown_action_rejects_mismatched_conversation_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api import state as api_state

    client = _client()
    active_conversation = _conversation(client)
    other_conversation = _conversation(client)
    user_id = client.get("/api/v1/me").json()["user"]["id"]
    run_id = api_state.store.new_id()
    api_state.store.backtest_runs[run_id] = BacktestRun(
        id=run_id,
        conversation_id=active_conversation["id"],
        strategy_id=None,
        status="completed",
        asset_class="equity",
        symbols=["AAPL"],
        allocation_method="equal_weight",
        benchmark_symbol="SPY",
        metrics={"aggregate": {"performance": {"total_return_pct": 12.4}}},
        config_snapshot={"template": "buy_and_hold", "symbols": ["AAPL"]},
        conversation_result_card={
            "title": "AAPL buy and hold",
            "rows": [
                {"key": "total_return_pct", "label": "Total Return", "value": "+12.4%"}
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
            "conversation_id": active_conversation["id"],
            "action": {
                "type": "show_breakdown",
                "label": "Show a breakdown",
                "presentation": "result",
                "payload": {
                    "run_id": run_id,
                    "conversation_id": other_conversation["id"],
                },
            },
            "language": "en",
        },
    )

    assert response.status_code == 200
    text = _stream_payloads(response.text, "token")[0]["text"]
    assert "could not find" in text
    assistant = client.get(
        f"/api/v1/conversations/{active_conversation['id']}/messages"
    ).json()["items"][-1]
    assert "result_run_id" not in assistant["metadata"]


def test_save_strategy_action_creates_strategy_from_latest_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api import state as api_state

    monkeypatch.setenv("ARGUS_STRATEGIES_ENABLED", "true")
    client = _client()
    conversation = _conversation(client)
    user_id = client.get("/api/v1/me").json()["user"]["id"]
    run_id = api_state.store.new_id()
    api_state.store.backtest_runs[run_id] = BacktestRun(
        id=run_id,
        conversation_id=conversation["id"],
        strategy_id=None,
        status="completed",
        asset_class="equity",
        symbols=["AAPL"],
        allocation_method="equal_weight",
        benchmark_symbol="SPY",
        metrics={"aggregate": {"performance": {"total_return_pct": 12.4}}},
        config_snapshot={
            "template": "buy_and_hold",
            "asset_class": "equity",
            "symbols": ["AAPL"],
            "start_date": "2025-05-03",
            "end_date": "2026-05-03",
            "starting_capital": 10000,
            "benchmark_symbol": "SPY",
        },
        conversation_result_card={
            "title": "AAPL buy and hold",
            "date_range": {
                "start": "2025-05-03",
                "end": "2026-05-03",
                "display": "May 3, 2025 to May 3, 2026",
            },
            "rows": [
                {
                    "key": "total_return_pct",
                    "label": "Total Return (%)",
                    "value": "+12.4%",
                }
            ],
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
                "payload": {
                    "run_id": run_id,
                    "conversation_id": conversation["id"],
                },
            },
            "language": "en",
        },
    )

    assert response.status_code == 200
    text = _stream_payloads(response.text, "token")[0]["text"]
    assert "Saved" in text
    strategies = client.get("/api/v1/strategies").json()["items"]
    assert [strategy["symbols"] for strategy in strategies] == [["AAPL"]]
    saved_strategy_id = strategies[0]["id"]
    final = _stream_payloads(response.text, "final")[0]["payload"]
    assert final["saved_strategy_id"] == saved_strategy_id
    assert final["result_strategy_id"] == saved_strategy_id
    assert final["result_run_id"] == run_id
    stored_run = api_state.store.backtest_runs[run_id]
    assert stored_run.strategy_id == saved_strategy_id
    assert stored_run.conversation_result_card["saved_strategy_id"] == saved_strategy_id
    assert stored_run.conversation_result_card["saved_state"] == {
        "status": "saved",
        "strategy_id": saved_strategy_id,
    }
    assert all(
        action["type"] != "save_strategy"
        for action in stored_run.conversation_result_card.get("actions", [])
    )
    assistant = client.get(f"/api/v1/conversations/{conversation['id']}/messages").json()[
        "items"
    ][-1]
    assert assistant["metadata"]["saved_strategy_id"] == saved_strategy_id
    assert assistant["metadata"]["result_strategy_id"] == saved_strategy_id
    assert assistant["metadata"]["result_fact_bank"]["run_id"] == run_id

    duplicate = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "action": {
                "type": "save_strategy",
                "label": "Save strategy",
                "presentation": "result",
                "payload": {
                    "run_id": run_id,
                    "conversation_id": conversation["id"],
                },
            },
            "language": "en",
        },
    )

    assert duplicate.status_code == 200
    strategies_after_duplicate = client.get("/api/v1/strategies").json()["items"]
    assert [strategy["id"] for strategy in strategies_after_duplicate] == [
        saved_strategy_id
    ]


def test_save_strategy_action_is_history_preserved_when_strategies_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api import state as api_state

    composed_save_response: dict[str, Any] = {}

    async def compose_private_alpha_save_response(**kwargs: Any) -> str:
        composed_save_response.update(kwargs)
        return "I cannot move this into Strategies here, but the run stays reachable from this chat and Recents."

    monkeypatch.setenv("ARGUS_STRATEGIES_ENABLED", "false")
    monkeypatch.setattr(
        "argus.api.routers.agent.compose_private_alpha_save_response",
        compose_private_alpha_save_response,
    )
    client = _client()
    conversation = _conversation(client)
    user_id = client.get("/api/v1/me").json()["user"]["id"]
    run_id = api_state.store.new_id()
    api_state.store.backtest_runs[run_id] = BacktestRun(
        id=run_id,
        conversation_id=conversation["id"],
        strategy_id=None,
        status="completed",
        asset_class="equity",
        symbols=["AAPL"],
        allocation_method="equal_weight",
        benchmark_symbol="SPY",
        metrics={"aggregate": {"performance": {"total_return_pct": 12.4}}},
        config_snapshot={
            "template": "buy_and_hold",
            "asset_class": "equity",
            "symbols": ["AAPL"],
            "start_date": "2025-05-03",
            "end_date": "2026-05-03",
            "starting_capital": 10000,
            "benchmark_symbol": "SPY",
        },
        conversation_result_card={
            "title": "AAPL buy and hold",
            "date_range": {
                "start": "2025-05-03",
                "end": "2026-05-03",
                "display": "May 3, 2025 to May 3, 2026",
            },
            "rows": [
                {
                    "key": "total_return_pct",
                    "label": "Total Return (%)",
                    "value": "+12.4%",
                }
            ],
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
                "payload": {
                    "run_id": run_id,
                    "conversation_id": conversation["id"],
                },
            },
            "language": "en",
        },
    )

    assert response.status_code == 200
    text = _stream_payloads(response.text, "token")[0]["text"]
    assert "Saved" not in text
    assert "Strategy was saved" not in text
    assert composed_save_response["user_message"] == "save this strategy"
    assert composed_save_response["metadata"]["run_id"] == run_id
    assert composed_save_response["metadata"]["symbols"] == ["AAPL"]
    assert composed_save_response["metadata"]["benchmark_symbol"] == "SPY"
    assert composed_save_response["metadata"]["metrics"] == {
        "aggregate": {"performance": {"total_return_pct": 12.4}}
    }
    assert composed_save_response["metadata"]["config_snapshot"] == {
        "template": "buy_and_hold",
        "asset_class": "equity",
        "symbols": ["AAPL"],
        "start_date": "2025-05-03",
        "end_date": "2026-05-03",
        "starting_capital": 10000,
        "benchmark_symbol": "SPY",
    }
    assert composed_save_response["metadata"]["result_card"]["title"] == (
        "AAPL buy and hold"
    )
    assert client.get("/api/v1/strategies").json()["items"] == []


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
    assert "reliable draft" in second_text
    assert "interpreter" not in second_text.lower()


def test_discovery_endpoints_return_assets_and_indicators(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api.routers import discovery as discovery_router

    monkeypatch.setattr(
        discovery_router,
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
        discovery_router,
        "search_indicators",
        lambda q, limit=12: [
            IndicatorInfo("rsi", "RSI", "Relative Strength Index", "executable")
        ],
    )
    client = _client()

    assets = client.get("/api/v1/discovery/assets?q=apple&limit=5")
    indicators = client.get("/api/v1/discovery/indicators?q=rsi&limit=5")

    assert assets.status_code == 200
    assert assets.json()["items"][0]["insert_text"] == "AAPL"
    assert indicators.status_code == 200
    assert indicators.json()["items"][0]["provider"] == "pandas-ta-classic"
    assert indicators.json()["items"][0]["support_status"] == "supported"


def test_discovery_assets_display_currency_pair_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api.routers import discovery as discovery_router

    monkeypatch.setattr(
        discovery_router,
        "search_assets",
        lambda q, limit=12: [
            ResolvedAsset(
                canonical_symbol="EURUSD",
                asset_class="currency_pair",
                name="EUR/USD",
                raw_symbol=q,
            )
        ],
    )
    client = _client()

    response = client.get("/api/v1/discovery/assets?q=eur/usd&limit=5")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["description"] == "Currency Pair"
    assert "currency_pair" not in item["description"]
