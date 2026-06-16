from __future__ import annotations

import json
from types import SimpleNamespace
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
            "launch_payload": {
                "strategy_type": "buy_and_hold",
                "symbol": "AAPL",
                "symbols": ["AAPL"],
                "timeframe": "1D",
                "date_range": {"start": "2025-05-14", "end": "2026-05-14"},
                "entry_rule": None,
                "exit_rule": None,
                "sizing_mode": "capital_amount",
                "capital_amount": 1000,
                "position_size": None,
                "cadence": None,
                "parameters": {},
                "risk_rules": [],
                "benchmark_symbol": "SPY",
                "language": "en",
            },
            "validation": {"status": "ready_to_run", "executable": True},
        },
        "confirmation_card": {
            "confirmation_id": "confirm-aapl",
            "confirmation_state": "active",
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
                    "payload": {"confirmation_id": "confirm-aapl"},
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
                            "aggregate": {"performance": {"total_return_pct": 11.5}},
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
                        "actions": [{"type": "save_strategy", "label": "Save strategy"}],
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
                "payload": {"confirmation_id": "confirm-aapl"},
            },
            "language": "en",
        },
    )

    assert response.status_code == 200
    assert captured["thread_id"] == conversation["id"]
    run = _stream_payloads(response.text, "final")[0]["run"]
    assert run["symbols"] == ["AAPL"]


def test_confirmation_action_prefers_visible_card_metadata_over_checkpoint(
    monkeypatch,
) -> None:
    from argus.agent_runtime.state.models import StrategySummary, TaskSnapshot
    from argus.api.routers import agent as agent_router

    captured: dict[str, Any] = {}

    async def _checkpoint(**_: Any):
        return {
            "stage_outcome": "await_approval",
            "latest_task_snapshot": TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    strategy_thesis="Stale checkpoint draft.",
                    asset_universe=["MSFT"],
                    asset_class="equity",
                    date_range="past year",
                )
            ),
        }

    async def _runtime(**kwargs: Any):
        captured.update(kwargs)
        yield {"type": "stage_start", "stage": "interpret"}
        yield {
            "type": "final",
            "payload": {
                "stage_outcome": "ready_to_respond",
                "assistant_response": "Used visible card context.",
            },
        }

    monkeypatch.setattr(agent_router, "runtime_checkpoint_values", _checkpoint)
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
                "payload": {"confirmation_id": "confirm-aapl"},
            },
            "language": "en",
        },
    )

    assert response.status_code == 200
    fallback_payload = captured["fallback_confirmation_payload"]
    assert fallback_payload["launch_payload"]["symbol"] == "AAPL"
    snapshot = captured["fallback_latest_task_snapshot"]
    assert snapshot.pending_strategy_summary.asset_universe == ["AAPL"]


def test_valid_confirmation_action_reuses_recent_messages_for_metadata_fallback(
    monkeypatch,
) -> None:
    from argus.agent_runtime.state.models import StrategySummary, TaskSnapshot
    from argus.api import state as api_state
    from argus.api.chat import actions as chat_actions
    from argus.api.chat import recovery as chat_recovery
    from argus.api.routers import agent as agent_router

    captured: dict[str, Any] = {}
    recent_message_reads = 0

    async def _checkpoint(**_: Any):
        return {
            "stage_outcome": "await_approval",
            "latest_task_snapshot": TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    strategy_thesis="Stale checkpoint draft.",
                    asset_universe=["MSFT"],
                    asset_class="equity",
                    date_range="past year",
                )
            ),
        }

    async def _runtime(**kwargs: Any):
        captured.update(kwargs)
        yield {"type": "stage_start", "stage": "interpret"}
        yield {
            "type": "final",
            "payload": {
                "stage_outcome": "ready_to_respond",
                "assistant_response": "Used visible card context.",
            },
        }

    def _recent_messages_for_conversation(
        *,
        user_id: str,
        conversation_id: str,
        limit: int,
    ):
        nonlocal recent_message_reads
        recent_message_reads += 1
        return list(api_state.store.messages.get(conversation_id, []))[-limit:]

    monkeypatch.setattr(agent_router, "runtime_checkpoint_values", _checkpoint)
    monkeypatch.setattr(agent_router, "stream_agent_turn_events", _runtime)
    monkeypatch.setattr(
        agent_router,
        "_recent_messages_for_conversation",
        _recent_messages_for_conversation,
        raising=False,
    )
    monkeypatch.setattr(
        chat_actions,
        "_recent_messages_for_conversation",
        _recent_messages_for_conversation,
    )
    monkeypatch.setattr(
        chat_recovery,
        "_recent_messages_for_conversation",
        _recent_messages_for_conversation,
    )
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
                "payload": {"confirmation_id": "confirm-aapl"},
            },
            "language": "en",
        },
    )

    assert response.status_code == 200
    assert recent_message_reads == 1
    fallback_payload = captured["fallback_confirmation_payload"]
    assert fallback_payload["launch_payload"]["symbol"] == "AAPL"
    snapshot = captured["fallback_latest_task_snapshot"]
    assert snapshot.pending_strategy_summary.asset_universe == ["AAPL"]


def test_confirmation_final_payload_keeps_artifact_identity_consistent(
    monkeypatch,
) -> None:
    from argus.api.routers import agent as agent_router

    confirmation_payload = _confirmation_metadata()["confirmation_payload"]

    async def _runtime(**_: Any):
        yield {"type": "stage_start", "stage": "interpret"}
        yield {
            "type": "final",
            "payload": {
                "stage_outcome": "await_approval",
                "assistant_response": "Ready to confirm.",
                "confirmation_payload": confirmation_payload,
                "artifact_references": [
                    {
                        "artifact_kind": "confirmation",
                        "artifact_id": "confirm-from-stage",
                        "artifact_status": "active",
                        "metadata": {
                            "confirmation_id": "confirm-from-stage",
                            "confirmation_payload": confirmation_payload,
                        },
                    }
                ],
            },
        }

    monkeypatch.setattr(agent_router, "stream_agent_turn_events", _runtime)
    client = _client()
    conversation = _conversation(client)

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "Backtest buy and hold Apple over the past year.",
            "language": "en",
        },
    )

    assert response.status_code == 200
    final = _stream_payloads(response.text, "final")[0]
    confirmation_id = final["confirmation"]["confirmation_id"]
    assert confirmation_id == "confirm-from-stage"
    assert final["artifact_references"][0]["artifact_id"] == confirmation_id
    assert (
        final["active_confirmation_reference"]["artifact_id"]
        == final["artifact_references"][0]["artifact_id"]
    )


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


def test_adjust_assumptions_action_round_trips_pending_edit_after_reload(
    monkeypatch,
) -> None:
    from argus.api.routers import agent as agent_router

    captured_calls: list[dict[str, Any]] = []

    async def _runtime(**kwargs: Any):
        captured_calls.append(kwargs)
        if kwargs["action_context"] is not None:
            assert kwargs["action_context"]["type"] == "adjust_assumptions"
            assert kwargs["fallback_confirmation_payload"]["strategy"][
                "asset_universe"
            ] == ["AAPL"]
            snapshot = kwargs["fallback_latest_task_snapshot"]
            assert snapshot.pending_strategy_summary.asset_universe == ["AAPL"]
            yield {"type": "stage_start", "stage": "interpret"}
            yield {
                "type": "final",
                "payload": {
                    "stage_outcome": "await_user_reply",
                    "assistant_response": "What assumption should I adjust for AAPL?",
                    "pending_strategy": {
                        "strategy": snapshot.pending_strategy_summary.model_dump(
                            mode="python"
                        ),
                        "requested_field": "assumption",
                        "missing_required_fields": ["assumption"],
                        "response_intent": {
                            "kind": "clarification",
                            "requested_fields": ["assumption"],
                            "facts": {
                                "structured_action": kwargs["action_context"],
                            },
                        },
                    },
                },
            }
            return

        fallback_metadata = kwargs["fallback_selected_thread_metadata"]
        assert fallback_metadata["fallback_source"] == "pending_strategy_metadata"
        assert fallback_metadata["requested_field"] == "assumption"
        snapshot = kwargs["fallback_latest_task_snapshot"]
        assert snapshot.pending_strategy_summary.asset_universe == ["AAPL"]
        yield {"type": "stage_start", "stage": "interpret"}
        yield {
            "type": "final",
            "payload": {
                "stage_outcome": "ready_to_respond",
                "assistant_response": "Got it. I will use that assumption.",
            },
        }

    monkeypatch.setattr(agent_router, "stream_agent_turn_events", _runtime)
    client = _client()
    conversation = _conversation(client)
    user_id = _user_id(client)
    metadata = _confirmation_metadata()
    metadata["confirmation_card"]["actions"].append(
        {
            "id": "adjust-assumptions",
            "type": "adjust_assumptions",
            "label": "Adjust assumptions",
            "presentation": "confirmation",
            "payload": {"confirmation_id": "confirm-aapl"},
        }
    )
    create_message(
        user_id=user_id,
        conversation_id=conversation["id"],
        role="assistant",
        content="I read this as AAPL using a buy and hold approach.",
        metadata=metadata,
    )

    action_response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "action": {
                "type": "adjust_assumptions",
                "label": "Adjust assumptions",
                "presentation": "confirmation",
                "payload": {"confirmation_id": "confirm-aapl"},
            },
            "language": "en",
        },
    )

    assert action_response.status_code == 200
    final = _stream_payloads(action_response.text, "final")[0]
    assert final["stage_outcome"] == "await_user_reply"
    messages = client.get(
        f"/api/v1/conversations/{conversation['id']}/messages"
    ).json()["items"]
    latest_assistant = messages[-1]
    assert latest_assistant["role"] == "assistant"
    assert latest_assistant["metadata"]["chat_action"]["type"] == "adjust_assumptions"
    assert latest_assistant["metadata"]["pending_strategy"]["requested_field"] == (
        "assumption"
    )

    reply_response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "Use a 5000 dollar starting amount.",
            "language": "en",
        },
    )

    assert reply_response.status_code == 200
    assert len(captured_calls) == 2


def test_pending_strategy_metadata_fallback_is_used_even_when_checkpoint_has_pending(
    monkeypatch,
) -> None:
    from argus.agent_runtime.state.models import StrategySummary, TaskSnapshot
    from argus.api.routers import agent as agent_router

    captured: dict[str, Any] = {}

    async def _checkpoint(**_: Any) -> dict[str, Any]:
        return {
            "stage_outcome": "await_user_reply",
            "latest_task_snapshot": TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="signal_strategy",
                    strategy_thesis="Checkpoint has a pending draft.",
                )
            ),
        }

    async def _runtime(**kwargs: Any):
        captured.update(kwargs)
        yield {"type": "stage_start", "stage": "interpret"}
        yield {
            "type": "final",
            "payload": {
                "stage_outcome": "ready_for_confirmation",
                "assistant_response": None,
            },
        }

    monkeypatch.setattr(agent_router, "runtime_checkpoint_values", _checkpoint)
    monkeypatch.setattr(agent_router, "stream_agent_turn_events", _runtime)
    client = _client()
    conversation = _conversation(client)
    user_id = _user_id(client)
    create_message(
        user_id=user_id,
        conversation_id=conversation["id"],
        role="assistant",
        content="Which asset and period should I use?",
        metadata={
            "conversation_mode": "setup",
            "agent_runtime_stage_outcome": "await_user_reply",
            "pending_strategy": {
                "strategy": {
                    "strategy_type": "signal_strategy",
                    "strategy_thesis": "Buy on a 50/200 crossover.",
                    "entry_logic": "50-day SMA crosses above 200-day SMA",
                    "exit_logic": "50-day SMA crosses below 200-day SMA",
                    "entry_rule": {
                        "type": "moving_average_crossover",
                        "fast_indicator": "sma",
                        "fast_period": 50,
                        "slow_indicator": "sma",
                        "slow_period": 200,
                        "direction": "bullish",
                    },
                    "exit_rule": {
                        "type": "moving_average_crossover",
                        "fast_indicator": "sma",
                        "fast_period": 50,
                        "slow_indicator": "sma",
                        "slow_period": 200,
                        "direction": "bearish",
                    },
                },
                "requested_field": None,
                "missing_required_fields": ["asset_universe", "date_range"],
            },
        },
    )

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "TSLA over the last year",
            "language": "en",
        },
    )

    assert response.status_code == 200
    snapshot = captured["fallback_latest_task_snapshot"]
    assert snapshot is not None
    assert snapshot.pending_strategy_summary is not None
    assert snapshot.pending_strategy_summary.strategy_type == "signal_strategy"
    assert captured["fallback_selected_thread_metadata"]["fallback_source"] == (
        "pending_strategy_metadata"
    )


def test_visible_confirmation_metadata_fallback_carries_text_turn_context(
    monkeypatch,
) -> None:
    from argus.api.routers import agent as agent_router

    captured: dict[str, Any] = {}

    async def _runtime(**kwargs: Any):
        captured.update(kwargs)
        snapshot = kwargs["fallback_latest_task_snapshot"]
        assert snapshot.pending_strategy_summary is not None
        assert snapshot.pending_strategy_summary.asset_universe == ["AAPL"]
        assert snapshot.active_confirmation_reference is not None
        yield {"type": "stage_start", "stage": "interpret"}
        yield {
            "type": "final",
            "payload": {
                "stage_outcome": "ready_to_respond",
                "assistant_response": "For the visible confirmation, I am using Benchmark: SPY.",
            },
        }

    async def _checkpoint(**_: Any):
        return {}

    monkeypatch.setattr(agent_router, "runtime_checkpoint_values", _checkpoint)
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
            "message": "What assumptions are you using?",
            "language": "en",
        },
    )

    assert response.status_code == 200
    assert captured["fallback_confirmation_payload"]["strategy"]["asset_universe"] == [
        "AAPL"
    ]
    assert captured["fallback_artifact_references"][0].artifact_kind == "confirmation"


def test_newer_confirmation_metadata_overrides_stale_result_checkpoint_for_text_turn(
    monkeypatch,
) -> None:
    from argus.agent_runtime.state.models import (
        ArtifactReference,
        StrategySummary,
        TaskSnapshot,
    )
    from argus.api.routers import agent as agent_router

    captured: dict[str, Any] = {}

    async def _checkpoint(**_: Any):
        return {
            "stage_outcome": "ready_to_respond",
            "latest_task_snapshot": TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    strategy_thesis="Stale checkpoint draft.",
                    asset_universe=["MSFT"],
                    asset_class="equity",
                    date_range="past year",
                ),
                latest_backtest_result_reference=ArtifactReference(
                    artifact_kind="backtest_result",
                    artifact_id="run-old",
                    artifact_status="completed",
                    metadata={"symbols": ["MSFT"]},
                ),
            ),
        }

    async def _runtime(**kwargs: Any):
        captured.update(kwargs)
        snapshot = kwargs["fallback_latest_task_snapshot"]
        assert snapshot.pending_strategy_summary is not None
        assert snapshot.pending_strategy_summary.asset_universe == ["AAPL"]
        assert snapshot.active_confirmation_reference is not None
        yield {"type": "stage_start", "stage": "interpret"}
        yield {
            "type": "final",
            "payload": {
                "stage_outcome": "ready_to_respond",
                "assistant_response": (
                    "That strategy is ready on the visible card. Use the card "
                    "action when you want to start the simulation."
                ),
            },
        }

    monkeypatch.setattr(agent_router, "runtime_checkpoint_values", _checkpoint)
    monkeypatch.setattr(agent_router, "stream_agent_turn_events", _runtime)
    client = _client()
    conversation = _conversation(client)
    user_id = _user_id(client)
    create_message(
        user_id=user_id,
        conversation_id=conversation["id"],
        role="assistant",
        content="Here is the old result.",
        metadata={
            "result_run_id": "run-old",
            "result_card": {
                "title": "MSFT buy and hold",
                "rows": [{"label": "Total Return (%)", "value": "+1.0%"}],
            },
        },
    )
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
            "message": "yes run it",
            "language": "en",
        },
    )

    assert response.status_code == 200
    assert captured["fallback_confirmation_payload"]["strategy"]["asset_universe"] == [
        "AAPL"
    ]
    assert captured["fallback_selected_thread_metadata"]["last_stage_outcome"] == (
        "await_approval"
    )


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


def test_stale_confirmation_card_without_structured_payload_returns_spanish_recovery(
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
        content="Entendí esto como AAPL con comprar y mantener.",
        metadata=metadata,
    )

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "action": {
                "type": "run_backtest",
                "label": "Ejecutar backtest",
                "presentation": "confirmation",
                "payload": {},
            },
            "language": "es-419",
        },
    )

    assert response.status_code == 200
    assert runtime_calls == 0
    text = _stream_payloads(response.text, "token")[0]["content"]
    lowered = text.lower()
    assert "confirmación" in lowered
    assert "guardada" in lowered
    assert "lost the active confirmation state" not in lowered


def test_stale_confirmation_action_id_does_not_execute(monkeypatch) -> None:
    from argus.api.routers import agent as agent_router

    runtime_calls = 0

    async def _runtime(**_: Any):
        nonlocal runtime_calls
        runtime_calls += 1
        yield {"type": "final", "payload": {"stage_outcome": "approved_for_execution"}}

    monkeypatch.setattr(agent_router, "stream_agent_turn_events", _runtime)
    client = _client()
    conversation = _conversation(client)
    user_id = _user_id(client)
    old_metadata = _confirmation_metadata()
    old_metadata["confirmation_card"]["confirmation_id"] = "confirm-old"
    old_metadata["confirmation_card"]["confirmation_state"] = "active"
    old_metadata["confirmation_card"]["actions"][0]["payload"] = {
        "confirmation_id": "confirm-old"
    }
    new_metadata = _confirmation_metadata()
    new_metadata["confirmation_card"]["confirmation_id"] = "confirm-new"
    new_metadata["confirmation_card"]["confirmation_state"] = "active"
    new_metadata["confirmation_card"]["title"] = "NVDA buy and hold"
    new_metadata["confirmation_card"]["actions"][0]["payload"] = {
        "confirmation_id": "confirm-new"
    }
    new_metadata["confirmation_payload"]["strategy"]["asset_universe"] = ["NVDA"]
    create_message(
        user_id=user_id,
        conversation_id=conversation["id"],
        role="assistant",
        content="I read this as AAPL using a buy and hold approach.",
        metadata=old_metadata,
    )
    create_message(
        user_id=user_id,
        conversation_id=conversation["id"],
        role="assistant",
        content="I read this as NVDA using a buy and hold approach.",
        metadata=new_metadata,
    )

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "action": {
                "type": "run_backtest",
                "label": "Run backtest",
                "presentation": "confirmation",
                "payload": {"confirmation_id": "confirm-old"},
            },
            "language": "en",
        },
    )

    assert response.status_code == 200
    assert runtime_calls == 0
    text = _stream_payloads(response.text, "token")[0]["content"]
    assert "confirmation was updated" in text.lower()
    assert "latest" in text.lower()


def test_stale_confirmation_action_id_returns_spanish_recovery(monkeypatch) -> None:
    from argus.api.routers import agent as agent_router

    runtime_calls = 0

    async def _runtime(**_: Any):
        nonlocal runtime_calls
        runtime_calls += 1
        yield {"type": "final", "payload": {"stage_outcome": "approved_for_execution"}}

    monkeypatch.setattr(agent_router, "stream_agent_turn_events", _runtime)
    client = _client()
    conversation = _conversation(client)
    user_id = _user_id(client)
    old_metadata = _confirmation_metadata()
    old_metadata["confirmation_card"]["confirmation_id"] = "confirm-old"
    old_metadata["confirmation_card"]["confirmation_state"] = "active"
    old_metadata["confirmation_card"]["actions"][0]["payload"] = {
        "confirmation_id": "confirm-old"
    }
    new_metadata = _confirmation_metadata()
    new_metadata["confirmation_card"]["confirmation_id"] = "confirm-new"
    new_metadata["confirmation_card"]["confirmation_state"] = "active"
    new_metadata["confirmation_card"]["title"] = "NVDA comprar y mantener"
    new_metadata["confirmation_card"]["actions"][0]["payload"] = {
        "confirmation_id": "confirm-new"
    }
    new_metadata["confirmation_payload"]["strategy"]["asset_universe"] = ["NVDA"]
    create_message(
        user_id=user_id,
        conversation_id=conversation["id"],
        role="assistant",
        content="Entendí esto como AAPL con comprar y mantener.",
        metadata=old_metadata,
    )
    create_message(
        user_id=user_id,
        conversation_id=conversation["id"],
        role="assistant",
        content="Entendí esto como NVDA con comprar y mantener.",
        metadata=new_metadata,
    )

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "action": {
                "type": "run_backtest",
                "label": "Ejecutar backtest",
                "presentation": "confirmation",
                "payload": {"confirmation_id": "confirm-old"},
            },
            "language": "es-419",
        },
    )

    assert response.status_code == 200
    assert runtime_calls == 0
    text = _stream_payloads(response.text, "token")[0]["content"]
    lowered = text.lower()
    assert "confirmación" in lowered
    assert "tarjeta" in lowered
    assert "confirmation was updated" not in lowered


def test_run_confirmation_action_without_confirmation_id_does_not_execute(
    monkeypatch,
) -> None:
    from argus.api.routers import agent as agent_router

    runtime_calls = 0

    async def _runtime(**_: Any):
        nonlocal runtime_calls
        runtime_calls += 1
        yield {"type": "final", "payload": {"stage_outcome": "approved_for_execution"}}

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
    assert runtime_calls == 0
    text = _stream_payloads(response.text, "token")[0]["content"]
    lowered = text.lower()
    assert "confirmation action" in lowered
    assert "latest card action" in lowered


def test_run_confirmation_action_without_confirmation_id_returns_spanish_recovery(
    monkeypatch,
) -> None:
    from argus.api.routers import agent as agent_router

    runtime_calls = 0

    async def _runtime(**_: Any):
        nonlocal runtime_calls
        runtime_calls += 1
        yield {"type": "final", "payload": {"stage_outcome": "approved_for_execution"}}

    monkeypatch.setattr(agent_router, "stream_agent_turn_events", _runtime)
    client = _client()
    conversation = _conversation(client)
    user_id = _user_id(client)
    create_message(
        user_id=user_id,
        conversation_id=conversation["id"],
        role="assistant",
        content="Entendí esto como AAPL con comprar y mantener.",
        metadata=_confirmation_metadata(),
    )

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "action": {
                "type": "run_backtest",
                "label": "Ejecutar backtest",
                "presentation": "confirmation",
                "payload": {},
            },
            "language": "es-419",
        },
    )

    assert response.status_code == 200
    assert runtime_calls == 0
    text = _stream_payloads(response.text, "token")[0]["content"]
    lowered = text.lower()
    assert "identidad" in lowered
    assert "tarjeta" in lowered
    assert "confirmation action" not in lowered


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


def test_cancel_confirmation_action_persists_invisible_artifact_tombstone() -> None:
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
                "type": "cancel_confirmation",
                "label": "Cancel",
                "presentation": "confirmation",
                "payload": {"confirmation_id": "confirm-aapl"},
            },
            "language": "en",
        },
    )

    assert response.status_code == 200
    final = _stream_payloads(response.text, "final")[0]
    assert final["stage_outcome"] == "ready_to_respond"
    assert final["assistant_response"] == ""
    assert final["confirmation_cancelled"] == {"confirmation_id": "confirm-aapl"}
    messages = client.get(f"/api/v1/conversations/{conversation['id']}/messages").json()[
        "items"
    ]
    assert all(
        not (
            message["role"] == "user"
            and message["metadata"]
            and message["metadata"].get("chat_action", {}).get("type")
            == "cancel_confirmation"
        )
        for message in messages
    )
    assert messages[-1]["role"] == "assistant"
    assert messages[-1]["content"] == ""
    assert messages[-1]["metadata"]["chat_action"]["type"] == "cancel_confirmation"
    assert messages[-1]["metadata"]["artifact_event"] == {
        "type": "confirmation_cancelled",
        "confirmation_id": "confirm-aapl",
    }


def test_canceled_confirmation_blocks_stale_checkpoint_run_action(monkeypatch) -> None:
    from argus.api.routers import agent as agent_router

    runtime_calls = 0

    async def _checkpoint_still_pending(**_: Any) -> dict[str, Any]:
        return {
            "stage_outcome": "await_approval",
            "run_state": SimpleNamespace(
                confirmation_payload=_confirmation_metadata()["confirmation_payload"]
            ),
        }

    async def _runtime(**_: Any):
        nonlocal runtime_calls
        runtime_calls += 1
        yield {"type": "stage_start", "stage": "execute"}
        yield {
            "type": "final",
            "payload": {
                "stage_outcome": "approved_for_execution",
                "assistant_response": "Running the stale draft.",
            },
        }

    monkeypatch.setattr(agent_router, "runtime_checkpoint_values", _checkpoint_still_pending)
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

    cancel_response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "action": {
                "type": "cancel_confirmation",
                "label": "Cancel",
                "presentation": "confirmation",
                "payload": {"confirmation_id": "confirm-aapl"},
            },
            "language": "en",
        },
    )
    assert cancel_response.status_code == 200

    stale_run_response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "action": {
                "type": "run_backtest",
                "label": "Run backtest",
                "presentation": "confirmation",
                "payload": {"confirmation_id": "confirm-aapl"},
            },
            "language": "en",
        },
    )

    assert stale_run_response.status_code == 409
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
    assert (
        reference.metadata["metrics"]["aggregate"]["performance"][
            "delta_vs_benchmark_pct"
        ]
        == -4.2
    )
    assert reference.metadata["conversation_id"] == conversation["id"]


def test_result_followup_prefers_visible_result_over_stale_checkpoint(
    monkeypatch,
) -> None:
    from argus.agent_runtime.state.models import StrategySummary, TaskSnapshot
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
                "assistant_response": "I can use the latest visible result.",
            },
        }

    async def _stale_checkpoint_values(**kwargs: Any) -> dict[str, Any]:
        del kwargs
        return {
            "latest_task_snapshot": TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    strategy_thesis="Older confirmation state.",
                    asset_universe=["TSLA"],
                    asset_class="equity",
                    date_range="past year",
                )
            )
        }

    monkeypatch.setattr(agent_router, "stream_agent_turn_events", _runtime)
    monkeypatch.setattr(
        agent_router,
        "runtime_checkpoint_values",
        _stale_checkpoint_values,
    )
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
        symbols=["AAPL", "GOOG"],
        allocation_method="equal_weight",
        benchmark_symbol="SPY",
        metrics={
            "aggregate": {
                "performance": {
                    "total_return_pct": 20.6,
                    "benchmark_return_pct": 15.2,
                    "delta_vs_benchmark_pct": 5.4,
                }
            },
            "by_symbol": {},
        },
        config_snapshot={
            "template": "dca_accumulation",
            "symbols": ["AAPL", "GOOG"],
            "resolved_strategy": {
                "strategy_type": "dca_accumulation",
                "strategy_thesis": "Buy AAPL and GOOG every month.",
                "asset_universe": ["AAPL", "GOOG"],
                "asset_class": "equity",
                "date_range": {"start": "2021-01-01", "end": "2024-01-31"},
                "capital_amount": 200,
                "cadence": "monthly",
                "comparison_baseline": "SPY",
            },
            "resolved_parameters": {
                "timeframe": "1D",
                "capital_amount": 200,
                "recurring_contribution": 200,
                "cadence": "monthly",
                "benchmark_symbol": "SPY",
            },
        },
        conversation_result_card={
            "title": "AAPL, GOOG DCA Accumulation",
            "status_label": "Simulation Complete",
            "rows": [
                {"key": "total_return_pct", "label": "Total return", "value": "+20.6%"}
            ],
            "assumptions": [
                "$200 recurring contribution",
                "Monthly cadence",
                "Daily data",
                "Benchmark: SPY",
            ],
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
            "message": "do the date range October 2019 to October 2025",
            "language": "en",
        },
    )

    assert response.status_code == 200
    snapshot = captured["fallback_latest_task_snapshot"]
    assert snapshot.pending_strategy_summary is None
    reference = snapshot.latest_backtest_result_reference
    assert reference is not None
    assert reference.artifact_id == run_id
    assert reference.metadata["symbols"] == ["AAPL", "GOOG"]


def test_refine_strategy_action_uses_latest_result_context_after_reload() -> None:
    from argus.api import state as api_state

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
        config_snapshot={
            "template": "buy_and_hold",
            "symbols": ["AAPL"],
            "resolved_strategy": {
                "strategy_type": "buy_and_hold",
                "strategy_thesis": "Buy and hold Apple.",
                "asset_universe": ["AAPL"],
                "asset_class": "equity",
                "date_range": "past year",
            },
        },
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
                    "key": "total_return_pct",
                    "label": "Total Return",
                    "value": "+8.1%",
                }
            ],
            "assumptions": ["Benchmark: SPY"],
            "actions": [{"type": "refine_strategy", "label": "Refine strategy"}],
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

    followup_response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "Why did this result happen?",
            "language": "en",
        },
    )
    assert followup_response.status_code == 200
    api_state.reset_agent_runtime_workflow(app)

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "action": {
                "type": "refine_strategy",
                "label": "Refine strategy",
                "presentation": "result",
                "payload": {
                    "run_id": run.id,
                    "conversation_id": conversation["id"],
                },
            },
            "language": "en",
        },
    )

    assert response.status_code == 200
    final = _stream_payloads(response.text, "final")[0]
    assert final["stage_outcome"] == "await_user_reply"
    assert "change" in final["assistant_response"].lower()
    assert final["pending_strategy"]["requested_field"] == "refinement"
    assert final["pending_strategy"]["strategy"]["asset_universe"] == ["AAPL"]


def test_refine_strategy_action_preserves_completed_dca_fields_after_reload() -> None:
    from argus.api import state as api_state

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
        symbols=["AAPL", "GOOG"],
        allocation_method="equal_weight",
        benchmark_symbol="SPY",
        metrics={"aggregate": {"performance": {"total_return_pct": 20.6}}},
        config_snapshot={
            "template": "dca_accumulation",
            "symbols": ["AAPL", "GOOG"],
            "date_range": {"start": "2021-01-01", "end": "2024-01-31"},
            "resolved_strategy": {
                "strategy_type": "dca_accumulation",
                "strategy_thesis": "Buy AAPL and GOOG every month.",
                "asset_universe": ["AAPL", "GOOG"],
                "asset_class": "equity",
                "date_range": {"start": "2021-01-01", "end": "2024-01-31"},
                "capital_amount": 200,
                "cadence": "monthly",
                "comparison_baseline": "SPY",
            },
            "resolved_parameters": {
                "timeframe": "1D",
                "capital_amount": 200,
                "recurring_contribution": 200,
                "cadence": "monthly",
                "benchmark_symbol": "SPY",
            },
        },
        conversation_result_card={
            "title": "AAPL, GOOG DCA Accumulation",
            "status_label": "Simulation Complete",
            "rows": [],
            "assumptions": [
                "$200 recurring contribution",
                "Monthly cadence",
                "Daily data",
                "Benchmark: SPY",
            ],
            "actions": [{"type": "refine_strategy", "label": "Refine strategy"}],
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
    api_state.reset_agent_runtime_workflow(app)

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "action": {
                "type": "refine_strategy",
                "label": "Refine strategy",
                "presentation": "result",
                "payload": {
                    "run_id": run.id,
                    "conversation_id": conversation["id"],
                },
            },
            "language": "en",
        },
    )

    assert response.status_code == 200
    final = _stream_payloads(response.text, "final")[0]
    strategy = final["pending_strategy"]["strategy"]
    assert strategy["strategy_type"] == "dca_accumulation"
    assert strategy["asset_universe"] == ["AAPL", "GOOG"]
    assert strategy["asset_class"] == "equity"
    assert strategy["date_range"] == {"start": "2021-01-01", "end": "2024-01-31"}
    assert strategy["capital_amount"] == 200
    assert strategy["cadence"] == "monthly"
    assert strategy["timeframe"] == "1D"
    assert strategy["comparison_baseline"] == "SPY"


def test_review_one_replay_preserves_result_artifact_through_date_patch(
    monkeypatch,
) -> None:
    from argus.agent_runtime import resolution as resolution_module
    from argus.agent_runtime.graph.workflow import build_workflow
    from argus.agent_runtime.stages.interpret_types import (
        InterpretationRequest,
        StructuredInterpretation,
    )
    from argus.agent_runtime.state.models import StrategySummary
    from argus.api import state as api_state
    from argus.api.chat.recovery import failed_action_metadata_fallback_context
    from langgraph.checkpoint.memory import MemorySaver

    class _ResolvedAssetStub:
        def __init__(self, canonical_symbol: str, asset_class: str) -> None:
            self.canonical_symbol = canonical_symbol
            self.asset_class = asset_class

    class _DatePatchInterpreter:
        async def ainvoke(
            self,
            request: InterpretationRequest,
        ) -> StructuredInterpretation:
            snapshot = request.latest_task_snapshot
            assert snapshot is not None
            assert snapshot.latest_failed_action_reference is None
            reference = snapshot.latest_backtest_result_reference
            assert reference is not None
            assert reference.metadata["symbols"] == ["AAPL", "GOOG"]
            return StructuredInterpretation(
                intent="results_explanation",
                task_relation="continue",
                requires_clarification=False,
                user_goal_summary="User changed the completed result date range.",
                candidate_strategy_draft=StrategySummary(
                    date_range={"start": "2019-10-01", "end": "2025-10-31"},
                ),
                confidence=0.9,
                semantic_turn_act="result_followup",
                result_followup_focus="next_experiment",
                artifact_target="latest_result",
            )

    def _resolve_asset(query: str) -> _ResolvedAssetStub:
        return _ResolvedAssetStub(query.strip().upper(), "equity")

    monkeypatch.setattr(resolution_module, "resolve_market_asset", _resolve_asset)
    client = _client()
    app.state.agent_runtime_workflow = build_workflow(
        structured_interpreter=_DatePatchInterpreter(),
        checkpointer=MemorySaver(),
    )
    conversation = _conversation(client)
    user_id = _user_id(client)
    failed_launch_payload = {
        "strategy_type": "dca_accumulation",
        "symbol": "AAPL",
        "symbols": ["AAPL", "GOOG"],
        "timeframe": "1D",
        "date_range": {"start": "2021-01-01", "end": "2024-01-31"},
        "sizing_mode": "capital_amount",
        "capital_amount": 200,
        "cadence": "monthly",
        "benchmark_symbol": "SPY",
    }
    create_message(
        user_id=user_id,
        conversation_id=conversation["id"],
        role="assistant",
        content="The previous run failed but can be retried.",
        metadata={
            "conversation_mode": "setup",
            "agent_runtime_stage_outcome": "execution_failed_recoverably",
            "failed_action": {
                "artifact_id": "failed-review-one",
                "action_type": "run_backtest",
                "launch_payload": failed_launch_payload,
                "failure_classification": "upstream_dependency_error",
                "error": "market_data_unavailable",
                "retryable": True,
            },
        },
    )
    assert (
        failed_action_metadata_fallback_context(
            user_id=user_id,
            conversation_id=conversation["id"],
        )
        is not None
    )
    run_id = api_state.store.new_id()
    run = BacktestRun(
        id=run_id,
        conversation_id=conversation["id"],
        strategy_id=None,
        status="completed",
        asset_class="equity",
        symbols=["AAPL", "GOOG"],
        allocation_method="equal_weight",
        benchmark_symbol="SPY",
        metrics={"aggregate": {"performance": {"total_return_pct": 20.6}}},
        config_snapshot={
            "template": "dca_accumulation",
            "symbols": ["AAPL", "GOOG"],
            "date_range": {"start": "2021-01-01", "end": "2024-01-31"},
            "resolved_strategy": {
                "strategy_type": "dca_accumulation",
                "strategy_thesis": "Buy AAPL and GOOG every month.",
                "asset_universe": ["AAPL", "GOOG"],
                "asset_class": "equity",
                "date_range": {"start": "2021-01-01", "end": "2024-01-31"},
                "capital_amount": 200,
                "cadence": "monthly",
                "comparison_baseline": "SPY",
            },
            "resolved_parameters": {
                "timeframe": "1D",
                "capital_amount": 200,
                "recurring_contribution": 200,
                "cadence": "monthly",
                "benchmark_symbol": "SPY",
            },
        },
        conversation_result_card={
            "title": "AAPL, GOOG DCA Accumulation",
            "status_label": "Simulation Complete",
            "rows": [],
            "assumptions": [
                "$200 recurring contribution",
                "Monthly cadence",
                "Daily data",
                "Benchmark: SPY",
            ],
            "actions": [{"type": "refine_strategy", "label": "Refine strategy"}],
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
    assert (
        failed_action_metadata_fallback_context(
            user_id=user_id,
            conversation_id=conversation["id"],
        )
        is None
    )

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "do the date range October 2019 to October 2025",
            "language": "en",
        },
    )

    assert response.status_code == 200
    final = _stream_payloads(response.text, "final")[0]
    assert final["stage_outcome"] == "await_approval"
    strategy = final["confirmation_payload"]["strategy"]
    assert strategy["strategy_type"] == "dca_accumulation"
    assert strategy["asset_universe"] == ["AAPL", "GOOG"]
    assert strategy["asset_class"] == "equity"
    assert strategy["date_range"] == {"start": "2019-10-01", "end": "2025-10-31"}
    assert strategy["capital_amount"] == 200
    assert strategy["cadence"] == "monthly"
    assert strategy["timeframe"] == "1D"
    assert strategy["comparison_baseline"] == "SPY"
    assert "assistant_response" not in final
    assert "latest_failed_action_reference" not in final
    messages = client.get(f"/api/v1/conversations/{conversation['id']}/messages").json()[
        "items"
    ]
    latest_assistant = messages[-1]
    assert latest_assistant["metadata"]["conversation_mode"] == "confirm"
    assert "latest_failed_action_reference" not in latest_assistant["metadata"]
    assert (
        failed_action_metadata_fallback_context(
            user_id=user_id,
            conversation_id=conversation["id"],
        )
        is None
    )


def test_refine_strategy_text_reply_uses_persisted_refinement_context_after_reload(
    monkeypatch,
) -> None:
    from argus.api import state as api_state
    from argus.api.routers import agent as agent_router

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
        metrics={"aggregate": {"performance": {"total_return_pct": 8.1}}},
        config_snapshot={
            "template": "buy_and_hold",
            "symbols": ["AAPL"],
            "resolved_strategy": {
                "strategy_type": "buy_and_hold",
                "strategy_thesis": "Buy and hold Apple.",
                "asset_universe": ["AAPL"],
                "asset_class": "equity",
                "date_range": "past year",
            },
        },
        conversation_result_card={
            "title": "AAPL buy and hold",
            "status_label": "Simulation Complete",
            "rows": [],
            "assumptions": ["Benchmark: SPY"],
            "actions": [{"type": "refine_strategy", "label": "Refine strategy"}],
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

    refine_response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "action": {
                "type": "refine_strategy",
                "label": "Refine strategy",
                "presentation": "result",
                "payload": {
                    "run_id": run.id,
                    "conversation_id": conversation["id"],
                },
            },
            "language": "en",
        },
    )
    assert refine_response.status_code == 200
    api_state.reset_agent_runtime_workflow(app)

    captured: dict[str, Any] = {}

    async def _runtime(**kwargs: Any):
        captured.update(kwargs)
        snapshot = kwargs["fallback_latest_task_snapshot"]
        assert snapshot.pending_strategy_summary is not None
        assert snapshot.pending_strategy_summary.asset_universe == ["AAPL"]
        assert snapshot.latest_backtest_result_reference is not None
        assert snapshot.latest_backtest_result_reference.artifact_id == run.id
        assert kwargs["fallback_selected_thread_metadata"]["requested_field"] == (
            "refinement"
        )
        assert (
            kwargs["fallback_selected_thread_metadata"]["source_result_run_id"]
            == run.id
        )
        yield {"type": "stage_start", "stage": "interpret"}
        yield {
            "type": "final",
            "payload": {
                "stage_outcome": "ready_for_confirmation",
                "assistant_response": "I read this as AAPL recurring buys.",
                "confirmation_payload": {
                    "strategy": {
                        "strategy_type": "dca_accumulation",
                        "asset_universe": ["AAPL"],
                        "asset_class": "equity",
                        "date_range": "past year",
                        "cadence": "biweekly",
                        "capital_amount": 500,
                    },
                    "optional_parameters": {},
                    "validation": {"status": "ready_to_run", "executable": True},
                },
            },
        }

    monkeypatch.setattr(agent_router, "stream_agent_turn_events", _runtime)

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "i want to do recurrent biweekly buys of 500 bucks instead",
            "language": "en",
        },
    )

    assert response.status_code == 200
    assert captured["message"].startswith("i want to do recurrent biweekly")


def test_refine_strategy_action_uses_card_run_before_runtime_memory(
    monkeypatch,
) -> None:
    from argus.api import state as api_state
    from argus.api.routers import agent as agent_router

    runtime_invoked = False
    captured: dict[str, Any] = {}

    async def _runtime(**kwargs: Any):
        nonlocal runtime_invoked
        runtime_invoked = True
        captured.update(kwargs)
        yield {"type": "stage_start", "stage": "interpret"}
        yield {
            "type": "final",
            "payload": {
                "stage_outcome": "await_user_reply",
                "assistant_response": "What would you like to change?",
                "pending_strategy": {
                    "requested_field": "refinement",
                    "strategy": {
                        "strategy_type": "buy_and_hold",
                        "asset_universe": ["DOGE"],
                        "asset_class": "crypto",
                    },
                },
                "latest_run_id": kwargs[
                    "fallback_latest_task_snapshot"
                ].latest_backtest_result_reference.artifact_id,
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
        asset_class="crypto",
        symbols=["DOGE"],
        allocation_method="equal_weight",
        benchmark_symbol="BTC",
        metrics={
            "aggregate": {
                "performance": {
                    "total_return_pct": 1.4,
                    "benchmark_return_pct": 13.5,
                    "delta_vs_benchmark_pct": -12.1,
                }
            },
            "by_symbol": {},
        },
        config_snapshot={
            "template": "buy_and_hold",
            "symbols": ["DOGE"],
            "resolved_strategy": {
                "strategy_type": "buy_and_hold",
                "strategy_thesis": "Buy and hold Dogecoin.",
                "asset_universe": ["DOGE"],
                "asset_class": "crypto",
                "date_range": "last 90 days",
            },
        },
        conversation_result_card={
            "title": "DOGE buy and hold",
            "status_label": "Simulation Complete",
            "rows": [
                {
                    "key": "total_return_pct",
                    "label": "Total Return",
                    "value": "+1.4%",
                }
            ],
            "assumptions": ["Benchmark: BTC"],
            "actions": [{"type": "refine_strategy", "label": "Refine strategy"}],
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
        content="DOGE result ready.",
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
            "action": {
                "type": "refine_strategy",
                "label": "Refine strategy",
                "presentation": "result",
                "payload": {
                    "run_id": run.id,
                    "conversation_id": conversation["id"],
                },
            },
            "language": "en",
        },
    )

    assert response.status_code == 200
    final = _stream_payloads(response.text, "final")[0]
    assert runtime_invoked is True
    snapshot = captured["fallback_latest_task_snapshot"]
    assert snapshot.latest_backtest_result_reference is not None
    assert snapshot.latest_backtest_result_reference.artifact_id == run.id
    assert final["stage_outcome"] == "await_user_reply"
    assert final["latest_run_id"] == run.id
    assert final["pending_strategy"]["requested_field"] == "refinement"
    assert final["pending_strategy"]["strategy"]["asset_universe"] == ["DOGE"]


def test_result_followup_after_reload_preserves_saved_strategy_id() -> None:
    from argus.api import state as api_state
    from argus.api.chat.recovery import latest_result_fallback_context

    client = _client()
    conversation = _conversation(client)
    user_id = _user_id(client)
    run_id = api_state.store.new_id()
    strategy_id = api_state.store.new_id()
    run = BacktestRun(
        id=run_id,
        conversation_id=conversation["id"],
        strategy_id=strategy_id,
        status="completed",
        asset_class="equity",
        symbols=["AAPL"],
        allocation_method="equal_weight",
        benchmark_symbol="SPY",
        metrics={"aggregate": {"performance": {"total_return_pct": 8.1}}},
        config_snapshot={"template": "buy_and_hold", "symbols": ["AAPL"]},
        conversation_result_card={
            "title": "AAPL buy and hold",
            "rows": [
                {"key": "total_return_pct", "label": "Total Return", "value": "+8.1%"}
            ],
            "assumptions": ["Benchmark: SPY"],
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
        content="Saved AAPL buy and hold to Strategies.",
        metadata={
            "conversation_mode": "result_review",
            "result_run_id": run.id,
            "latest_run_id": run.id,
            "result_strategy_id": strategy_id,
            "saved_strategy_id": strategy_id,
        },
    )

    fallback = latest_result_fallback_context(
        user_id=user_id,
        conversation_id=conversation["id"],
    )

    assert fallback is not None
    snapshot = fallback.latest_task_snapshot
    assert snapshot is not None
    reference = snapshot.latest_backtest_result_reference
    assert reference is not None
    assert reference.metadata["saved_strategy_id"] == strategy_id
    assert reference.metadata["result_strategy_id"] == strategy_id
    assert reference.metadata["latest_run_id"] == run_id


def test_pending_refinement_fallback_carries_source_result_reference() -> None:
    from argus.api import state as api_state
    from argus.api.chat.recovery import pending_strategy_metadata_fallback_context

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
        symbols=["MSFT"],
        allocation_method="equal_weight",
        benchmark_symbol="SPY",
        metrics={
            "aggregate": {
                "performance": {
                    "total_return_pct": 15.6,
                    "benchmark_return_pct": 16.6,
                    "delta_vs_benchmark_pct": -1.1,
                }
            }
        },
        config_snapshot={
            "template": "buy_and_hold",
            "symbols": ["MSFT"],
            "resolved_strategy": {
                "strategy_type": "buy_and_hold",
                "strategy_thesis": "Buy and hold Microsoft.",
                "asset_universe": ["MSFT"],
                "asset_class": "equity",
                "date_range": {"start": "2025-01-01", "end": "2025-12-31"},
            },
        },
        conversation_result_card={
            "title": "MSFT buy and hold",
            "status_label": "Simulation Complete",
            "rows": [],
            "assumptions": ["Benchmark: SPY"],
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
        content="What would you like to change about this strategy?",
        metadata={
            "conversation_mode": "setup",
            "agent_runtime_stage_outcome": "await_user_reply",
            "pending_strategy": {
                "strategy": {
                    "strategy_type": "buy_and_hold",
                    "strategy_thesis": "Buy and hold Microsoft.",
                    "asset_universe": ["MSFT"],
                    "asset_class": "equity",
                    "date_range": {"start": "2025-01-01", "end": "2025-12-31"},
                },
                "requested_field": "refinement",
                "missing_required_fields": ["refinement"],
                "source_result": {
                    "run_id": run.id,
                    "strategy_id": run.strategy_id,
                    "conversation_id": conversation["id"],
                },
            },
            "source_result_run_id": run.id,
            "source_result_conversation_id": conversation["id"],
        },
    )

    fallback = pending_strategy_metadata_fallback_context(
        user_id=user_id,
        conversation_id=conversation["id"],
    )

    assert fallback is not None
    snapshot = fallback.latest_task_snapshot
    assert snapshot is not None
    assert snapshot.pending_strategy_summary is not None
    reference = snapshot.latest_backtest_result_reference
    assert reference is not None
    assert reference.artifact_id == run.id
    assert reference.metadata["symbols"] == ["MSFT"]
    assert fallback.selected_thread_metadata is not None
    assert fallback.selected_thread_metadata["requested_field"] == "refinement"
    assert fallback.selected_thread_metadata["source_result_run_id"] == run.id


def test_pending_edit_prompt_takes_precedence_over_older_confirmation_fallback() -> None:
    from argus.api.chat.recovery import (
        confirmation_metadata_fallback_context,
        pending_strategy_metadata_fallback_context,
    )

    client = _client()
    conversation = _conversation(client)
    user_id = _user_id(client)
    create_message(
        user_id=user_id,
        conversation_id=conversation["id"],
        role="assistant",
        content="Ready to test buy-and-hold for AAPL.",
        metadata=_confirmation_metadata(),
    )
    pending_metadata = _pending_strategy_metadata()
    pending_metadata["pending_strategy"]["requested_field"] = "asset_universe"
    pending_metadata["pending_strategy"]["missing_required_fields"] = [
        "asset_universe"
    ]
    create_message(
        user_id=user_id,
        conversation_id=conversation["id"],
        role="assistant",
        content="What asset should I use instead?",
        metadata=pending_metadata,
    )

    confirmation_fallback = confirmation_metadata_fallback_context(
        user_id=user_id,
        conversation_id=conversation["id"],
    )
    pending_fallback = pending_strategy_metadata_fallback_context(
        user_id=user_id,
        conversation_id=conversation["id"],
    )

    assert confirmation_fallback is None
    assert pending_fallback is not None
    assert pending_fallback.selected_thread_metadata is not None
    assert pending_fallback.selected_thread_metadata["requested_field"] == (
        "asset_universe"
    )


def test_plain_text_after_pending_edit_prompt_passes_requested_field_to_runtime(
    monkeypatch,
) -> None:
    from argus.api.routers import agent as agent_router

    captured: dict[str, Any] = {}

    async def _checkpoint(**_: Any) -> dict[str, Any]:
        return {}

    async def _runtime(**kwargs: Any):
        captured.update(kwargs)
        yield {"type": "stage_start", "stage": "interpret"}
        yield {
            "type": "final",
            "payload": {
                "stage_outcome": "ready_to_respond",
                "assistant_response": "Captured fallback context.",
            },
        }

    monkeypatch.setattr(agent_router, "runtime_checkpoint_values", _checkpoint)
    monkeypatch.setattr(agent_router, "stream_agent_turn_events", _runtime)

    client = _client()
    conversation = _conversation(client)
    user_id = _user_id(client)
    create_message(
        user_id=user_id,
        conversation_id=conversation["id"],
        role="assistant",
        content="Ready to test buy-and-hold for AAPL.",
        metadata=_confirmation_metadata(),
    )
    pending_metadata = _pending_strategy_metadata()
    pending_metadata["pending_strategy"]["requested_field"] = "asset_universe"
    pending_metadata["pending_strategy"]["missing_required_fields"] = [
        "asset_universe"
    ]
    create_message(
        user_id=user_id,
        conversation_id=conversation["id"],
        role="assistant",
        content="What asset should I use instead?",
        metadata=pending_metadata,
    )

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "microsoft",
            "language": "en",
        },
    )

    assert response.status_code == 200
    assert captured["message"] == "microsoft"
    assert captured["fallback_selected_thread_metadata"]["requested_field"] == (
        "asset_universe"
    )
    snapshot = captured["fallback_latest_task_snapshot"]
    assert snapshot.pending_strategy_summary is not None
    assert snapshot.pending_strategy_summary.asset_universe == ["AAPL"]


def test_confirmation_action_asset_edit_round_trips_through_api_metadata(
    monkeypatch,
) -> None:
    from argus.agent_runtime import resolution as resolution_module
    from argus.agent_runtime.graph.workflow import build_workflow
    from argus.agent_runtime.stages.interpret_types import (
        InterpretationRequest,
        StructuredInterpretation,
    )
    from argus.agent_runtime.state.models import StrategySummary
    from langgraph.checkpoint.memory import MemorySaver

    class _ResolvedAssetStub:
        def __init__(self, canonical_symbol: str, asset_class: str) -> None:
            self.canonical_symbol = canonical_symbol
            self.asset_class = asset_class

    class _ProviderBackedAssetAnswerInterpreter:
        async def ainvoke(
            self, request: InterpretationRequest
        ) -> StructuredInterpretation:
            return StructuredInterpretation(
                intent="backtest_execution",
                task_relation="continue",
                requires_clarification=False,
                user_goal_summary="User supplied the replacement asset.",
                candidate_strategy_draft=StrategySummary(asset_universe=["GOOGL"]),
                confidence=0.9,
                semantic_turn_act="answer_pending_need",
            )

    def _resolve_asset(query: str) -> _ResolvedAssetStub:
        normalized = query.strip().casefold()
        if normalized in {"google", "googl"}:
            return _ResolvedAssetStub("GOOGL", "equity")
        return _ResolvedAssetStub(query.strip().upper(), "equity")

    monkeypatch.setattr(resolution_module, "resolve_market_asset", _resolve_asset)
    app.state.agent_runtime_workflow = build_workflow(
        structured_interpreter=_ProviderBackedAssetAnswerInterpreter(),
        checkpointer=MemorySaver(),
    )

    client = _client()
    app.state.agent_runtime_workflow = build_workflow(
        structured_interpreter=_ProviderBackedAssetAnswerInterpreter(),
        checkpointer=MemorySaver(),
    )
    conversation = _conversation(client)
    user_id = _user_id(client)
    create_message(
        user_id=user_id,
        conversation_id=conversation["id"],
        role="assistant",
        content="Ready to test TSLA with an RSI threshold.",
        metadata={
            "conversation_mode": "confirm",
            "agent_runtime_stage_outcome": "await_approval",
            "confirmation_payload": {
                "strategy": {
                    "strategy_type": "rsi_threshold",
                    "strategy_thesis": "Test TSLA with an RSI threshold rule.",
                    "asset_universe": ["TSLA"],
                    "asset_class": "equity",
                    "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
                    "entry_logic": "Buy when RSI(14) drops to 30 or below",
                    "exit_logic": "Sell when RSI(14) rises to 55 or above",
                    "extra_parameters": {
                        "indicator": "rsi",
                        "indicator_parameters": {
                            "indicator": "rsi",
                            "indicator_period": 14,
                            "entry_threshold": 30,
                            "exit_threshold": 55,
                        },
                    },
                },
                "optional_parameters": {},
                "launch_payload": {
                    "strategy_type": "rsi_threshold",
                    "symbol": "TSLA",
                    "symbols": ["TSLA"],
                    "timeframe": "1D",
                    "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
                    "entry_rule": "rsi_below",
                    "exit_rule": "rsi_above",
                    "sizing_mode": "capital_amount",
                    "capital_amount": 1000,
                    "parameters": {
                        "indicator": "rsi",
                        "indicator_period": 14,
                        "entry_threshold": 30,
                        "exit_threshold": 55,
                    },
                    "risk_rules": [],
                    "benchmark_symbol": "SPY",
                    "language": "en",
                },
                "validation": {"status": "ready_to_run", "executable": True},
            },
            "confirmation_card": {
                "confirmation_id": "confirm-tsla-rsi",
                "confirmation_state": "active",
                "title": "TSLA rsi threshold",
                "statusLabel": "Ready to run",
                "summary": "Ready to test TSLA with an RSI threshold.",
                "rows": [
                    {"label": "Strategy", "value": "RSI Threshold"},
                    {"label": "Assets", "value": "TSLA"},
                    {"label": "Period", "value": "January 1, 2024 - December 31, 2024"},
                ],
                "assumptions": ["Benchmark: SPY"],
                "actions": [
                    {
                        "id": "change-asset",
                        "type": "change_asset",
                        "label": "Change asset",
                        "presentation": "confirmation",
                        "payload": {"confirmation_id": "confirm-tsla-rsi"},
                    }
                ],
            },
        },
    )

    change_response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "action": {
                "type": "change_asset",
                "label": "Change asset",
                "presentation": "confirmation",
                "payload": {"confirmation_id": "confirm-tsla-rsi"},
            },
            "language": "en",
        },
    )

    assert change_response.status_code == 200
    change_final = _stream_payloads(change_response.text, "final")[0]
    assert change_final["pending_strategy"]["requested_field"] == "asset_universe"

    answer_response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "google",
            "language": "en",
        },
    )

    assert answer_response.status_code == 200
    answer_final = _stream_payloads(answer_response.text, "final")[0]
    assert answer_final["confirmation_payload"]["strategy"]["asset_universe"] == [
        "GOOGL"
    ]
    assert answer_final["confirmation_payload"]["strategy"]["entry_logic"] == (
        "Buy when RSI(14) drops to 30 or below"
    )
    assert answer_final["confirmation_payload"]["strategy"]["exit_logic"] == (
        "Sell when RSI(14) rises to 55 or above"
    )


def test_retry_after_reload_carries_latest_failed_action_reference(monkeypatch) -> None:
    from argus.api.routers import agent as agent_router

    captured: dict[str, Any] = {}

    async def _runtime(**kwargs: Any):
        captured.update(kwargs)
        yield {"type": "stage_start", "stage": "interpret"}
        yield {
            "type": "final",
            "payload": {
                "stage_outcome": "approved_for_execution",
                "assistant_response": "Retrying the same backtest.",
            },
        }

    monkeypatch.setattr(agent_router, "stream_agent_turn_events", _runtime)
    client = _client()
    conversation = _conversation(client)
    user_id = _user_id(client)
    launch_payload = {
        "strategy_type": "buy_and_hold",
        "symbol": "MSFT",
        "symbols": ["MSFT"],
        "timeframe": "1D",
        "date_range": {"start": "2025-05-13", "end": "2026-05-13"},
        "sizing_mode": "capital_amount",
        "capital_amount": 1000,
        "benchmark_symbol": "SPY",
    }
    create_message(
        user_id=user_id,
        conversation_id=conversation["id"],
        role="assistant",
        content="I still have the MSFT buy-and-hold draft, but market data failed.",
        metadata={
            "conversation_mode": "setup",
            "agent_runtime_stage_outcome": "execution_failed_recoverably",
            "failed_action": {
                "action_type": "run_backtest",
                "launch_payload": launch_payload,
                "failure_classification": "upstream_dependency_error",
                "error": "market_data_unavailable",
            },
        },
    )

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "Can you try again?",
            "language": "en",
        },
    )

    assert response.status_code == 200
    snapshot = captured["fallback_latest_task_snapshot"]
    reference = snapshot.latest_failed_action_reference
    assert reference is not None
    assert reference.artifact_kind == "failed_action"
    assert reference.metadata["launch_payload"] == launch_payload


def test_structured_retry_action_after_reload_carries_failed_action_reference(
    monkeypatch,
) -> None:
    from argus.api.routers import agent as agent_router

    captured: dict[str, Any] = {}

    async def _runtime(**kwargs: Any):
        captured.update(kwargs)
        yield {"type": "stage_start", "stage": "interpret"}
        yield {
            "type": "final",
            "payload": {
                "stage_outcome": "ready_for_confirmation",
                "assistant_response": "I rebuilt the failed run for review.",
            },
        }

    monkeypatch.setattr(agent_router, "stream_agent_turn_events", _runtime)
    client = _client()
    conversation = _conversation(client)
    user_id = _user_id(client)
    launch_payload = {
        "strategy_type": "buy_and_hold",
        "symbol": "MSFT",
        "symbols": ["MSFT"],
        "timeframe": "1D",
        "date_range": {"start": "2025-05-13", "end": "2026-05-13"},
        "sizing_mode": "capital_amount",
        "capital_amount": 1000,
        "benchmark_symbol": "SPY",
    }
    create_message(
        user_id=user_id,
        conversation_id=conversation["id"],
        role="assistant",
        content="I still have the MSFT buy-and-hold draft, but market data failed.",
        metadata={
            "conversation_mode": "setup",
            "agent_runtime_stage_outcome": "execution_failed_recoverably",
            "failed_action": {
                "artifact_id": "failed-msft-run",
                "action_type": "run_backtest",
                "launch_payload": launch_payload,
                "failure_classification": "upstream_dependency_error",
                "error": "market_data_unavailable",
                "retryable": True,
            },
        },
    )

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "action": {
                "type": "retry_failed_action",
                "label": "Retry",
                "payload": {"failed_action_id": "failed-msft-run"},
            },
            "language": "en",
        },
    )

    assert response.status_code == 200
    snapshot = captured["fallback_latest_task_snapshot"]
    reference = snapshot.latest_failed_action_reference
    assert reference is not None
    assert reference.artifact_id == "failed-msft-run"
    assert reference.metadata["launch_payload"] == launch_payload


def test_spanish_structured_retry_prefers_failed_action_over_stale_confirmation(
    monkeypatch,
) -> None:
    from argus.api.routers import agent as agent_router

    captured: dict[str, Any] = {}

    async def _runtime(**kwargs: Any):
        captured.update(kwargs)
        yield {"type": "stage_start", "stage": "interpret"}
        yield {
            "type": "final",
            "payload": {
                "stage_outcome": "ready_to_respond",
                "assistant_response": "Recupere la prueba fallida.",
            },
        }

    monkeypatch.setattr(agent_router, "stream_agent_turn_events", _runtime)
    client = _client()
    conversation = _conversation(client)
    user_id = _user_id(client)
    launch_payload = {
        "strategy_type": "buy_and_hold",
        "symbol": "AAPL",
        "symbols": ["AAPL"],
        "timeframe": "1D",
        "date_range": {"start": "2025-01-01", "end": "2025-04-01"},
        "sizing_mode": "capital_amount",
        "capital_amount": 10000,
        "benchmark_symbol": "SPY",
    }
    create_message(
        user_id=user_id,
        conversation_id=conversation["id"],
        role="assistant",
        content="Tengo una confirmacion anterior para AAPL.",
        metadata=_confirmation_metadata(),
    )
    create_message(
        user_id=user_id,
        conversation_id=conversation["id"],
        role="assistant",
        content="La ejecucion fallo, pero puedes reintentarla.",
        metadata={
            "conversation_mode": "setup",
            "agent_runtime_stage_outcome": "execution_failed_recoverably",
            "failed_action": {
                "artifact_id": "failed-aapl-es",
                "action_type": "run_backtest",
                "launch_payload": launch_payload,
                "failure_classification": "upstream_dependency_error",
                "error": "market_data_unavailable",
                "retryable": True,
            },
        },
    )

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "action": {
                "type": "retry_failed_action",
                "label": "Reintentar",
                "labelKey": "common.retry",
                "payload": {"failed_action_id": "failed-aapl-es"},
            },
            "language": "es-419",
        },
    )

    assert response.status_code == 200
    assert captured["user"].language_preference == "es-419"
    assert captured["action_context"]["type"] == "retry_failed_action"
    assert captured["action_context"]["payload"] == {
        "failed_action_id": "failed-aapl-es"
    }
    assert captured["fallback_selected_thread_metadata"] == {
        "latest_task_type": "backtest_execution",
        "last_stage_outcome": "execution_failed_recoverably",
        "fallback_source": "failed_action_metadata",
    }
    snapshot = captured["fallback_latest_task_snapshot"]
    assert snapshot.pending_strategy_summary is None
    assert snapshot.active_confirmation_reference is None
    reference = snapshot.latest_failed_action_reference
    assert reference is not None
    assert reference.artifact_id == "failed-aapl-es"
    assert reference.metadata["launch_payload"] == launch_payload


def test_failed_action_fallback_is_superseded_by_newer_completed_result() -> None:
    from argus.api import state as api_state
    from argus.api.chat.recovery import failed_action_metadata_fallback_context

    client = _client()
    conversation = _conversation(client)
    user_id = _user_id(client)
    launch_payload = {
        "strategy_type": "buy_and_hold",
        "symbol": "NVDA",
        "symbols": ["NVDA"],
        "timeframe": "1D",
        "date_range": {"start": "2026-01-01", "end": "2026-05-13"},
        "sizing_mode": "capital_amount",
        "capital_amount": 1000,
        "benchmark_symbol": "SPY",
    }
    create_message(
        user_id=user_id,
        conversation_id=conversation["id"],
        role="assistant",
        content="The run failed.",
        metadata={
            "latest_failed_action_reference": {
                "artifact_kind": "failed_action",
                "artifact_id": "failed-action-1",
                "artifact_status": "failed",
                "metadata": {
                    "action_type": "run_backtest",
                    "launch_payload": launch_payload,
                },
            }
        },
    )
    run_id = api_state.store.new_id()
    api_state.store.backtest_runs[run_id] = BacktestRun(
        id=run_id,
        conversation_id=conversation["id"],
        strategy_id=None,
        status="completed",
        asset_class="equity",
        symbols=["NVDA"],
        allocation_method="equal_weight",
        benchmark_symbol="SPY",
        metrics={"aggregate": {"performance": {"total_return_pct": 12.0}}},
        config_snapshot={"template": "buy_and_hold", "symbols": ["NVDA"]},
        conversation_result_card={
            "title": "NVDA buy and hold",
            "rows": [
                {"key": "total_return_pct", "label": "Total Return", "value": "+12.0%"}
            ],
            "assumptions": ["Benchmark: SPY"],
        },
        created_at=utcnow(),
        chart=None,
        trades=[],
    )
    api_state.store.backtest_run_owners[run_id] = user_id
    create_message(
        user_id=user_id,
        conversation_id=conversation["id"],
        role="assistant",
        content="Here is the completed result.",
        metadata={"result_run_id": run_id, "latest_run_id": run_id},
    )

    fallback = failed_action_metadata_fallback_context(
        user_id=user_id,
        conversation_id=conversation["id"],
    )

    assert fallback is None


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


def test_show_breakdown_action_without_canonical_run_id_does_not_use_latest(
    monkeypatch,
) -> None:
    from argus.api import state as api_state
    from argus.api.routers import agent as agent_router

    captured: dict[str, Any] = {}

    def _breakdown(run: BacktestRun | None, *, language: str) -> SimpleNamespace:
        captured["run"] = run
        return SimpleNamespace(
            text=(
                "I could not find the completed backtest to explain."
                if run is None
                else "Unexpected latest-run breakdown."
            ),
            source="missing_result" if run is None else "latest_result",
            fallback_used=True,
            failure_mode="missing_result" if run is None else None,
        )

    monkeypatch.setattr(
        agent_router,
        "result_breakdown_message_with_metadata",
        _breakdown,
    )
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
    create_message(
        user_id=user_id,
        conversation_id=conversation["id"],
        role="assistant",
        content="Here is the completed result.",
        metadata={"result_run_id": run_id, "latest_run_id": run_id},
    )

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "action": {
                "type": "show_breakdown",
                "label": "Explain result",
                "presentation": "result",
                "payload": {},
            },
            "language": "en",
        },
    )

    assert response.status_code == 200
    assert captured["run"] is None
    text = _stream_payloads(response.text, "token")[0]["content"]
    assert "could not find" in text
