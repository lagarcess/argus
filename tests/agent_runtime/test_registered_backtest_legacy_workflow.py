"""The existing seven-intent confirmation flow admits a registered backtest."""

from __future__ import annotations

import socket
from types import SimpleNamespace

import pytest
from argus.agent_runtime.graph.workflow import build_workflow
from argus.agent_runtime.runtime import run_agent_turn
from argus.agent_runtime.stages.interpret_types import StructuredInterpretation
from argus.agent_runtime.state.models import StrategySummary, UserState
from argus.domain.backtesting.config import MIN_STARTING_CAPITAL
from faker import Faker
from langgraph.checkpoint.memory import MemorySaver

fake = Faker()


def test_registry_artifacts_do_not_change_existing_interpreter_messages():
    from argus.agent_runtime.capabilities.contract import (
        build_default_capability_contract,
    )
    from argus.agent_runtime.llm_interpreter import OpenRouterStructuredInterpreter
    from argus.agent_runtime.stages.interpret_types import InterpretationRequest
    from argus.agent_runtime.state.models import ArtifactReference, TaskSnapshot

    request = InterpretationRequest(
        current_user_message=fake.sentence(),
        user=UserState(user_id=fake.uuid4()),
        latest_task_snapshot=TaskSnapshot(),
    )
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    expected = interpreter._messages(request)
    artifact = ArtifactReference(
        artifact_kind="tool_result",
        artifact_id=fake.uuid4(),
        metadata={"call_id": fake.uuid4(), "arguments": {"value": 0}},
    )
    request.latest_task_snapshot.artifact_references.append(artifact)
    request.selected_thread_metadata["tool_result_cards"] = [artifact.metadata]

    assert interpreter._messages(request) == expected


def _strategy(kind: str) -> StrategySummary:
    contribution = fake.random_int(min=25, max=500)
    strategy = StrategySummary(
        strategy_type=kind,
        strategy_thesis="Test Apple with no fees and 5 basis points of slippage.",
        asset_universe=["AAPL"],
        asset_class="equity",
        timeframe="1D",
        capital_amount=contribution,
        date_range={"start": "2023-01-03", "end": "2024-12-31"},
        extra_parameters={
            "fee_rate": 0,
            "slippage": 0.0005,
            "field_provenance": {
                "fee_rate": "explicit_user",
                "slippage": "explicit_user",
            },
        },
    )
    if kind == "dca_accumulation":
        strategy.cadence = "monthly"
        strategy.extra_parameters.update(
            starting_capital=0, recurring_contribution=contribution
        )
    else:
        strategy.capital_amount += MIN_STARTING_CAPITAL
        rule = {
            "type": "moving_average_crossover",
            "fast_indicator": "sma",
            "fast_period": 20,
            "slow_indicator": "sma",
            "slow_period": 50,
        }
        strategy.entry_rule = {**rule, "direction": "bullish"}
        strategy.exit_rule = {**rule, "direction": "bearish"}
        strategy.entry_logic = "20-day SMA crosses above 50-day SMA"
        strategy.exit_logic = "20-day SMA crosses below 50-day SMA"
    return strategy


@pytest.mark.asyncio()
@pytest.mark.parametrize("kind", ["dca_accumulation", "signal_strategy"])
async def test_existing_confirmation_run_preserves_declared_facts(monkeypatch, kind):
    from argus.agent_runtime import resolution

    def network_forbidden(*args, **kwargs):
        raise AssertionError("This workflow proof must not contact a provider")

    monkeypatch.setattr(socket.socket, "connect", network_forbidden)
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "true")
    monkeypatch.setattr(
        resolution,
        "resolve_market_asset",
        lambda symbol: SimpleNamespace(canonical_symbol=symbol, asset_class="equity"),
    )
    strategy = _strategy(kind)
    interpreted = []
    received = []
    job_id = fake.uuid4()
    thread_id = fake.uuid4()

    class ExistingInterpreter:
        async def ainvoke(self, request):
            interpreted.append(request)
            return StructuredInterpretation(
                intent="backtest_execution",
                task_relation="new_task",
                user_goal_summary=strategy.strategy_thesis,
                candidate_strategy_draft=strategy,
                semantic_turn_act="new_idea",
            )

    class QueuedBacktest:
        def run(self, payload):
            received.append(payload)
            return {
                "success": True,
                "payload": {
                    "backtest_job": {
                        "id": job_id,
                        "conversation_id": thread_id,
                        "status": "queued",
                    }
                },
            }

    workflow = build_workflow(
        structured_interpreter=ExistingInterpreter(),
        tool=QueuedBacktest(),
        checkpointer=MemorySaver(),
    )
    user = UserState(user_id=fake.uuid4(), expertise_level="advanced")
    confirmation = await run_agent_turn(
        workflow=workflow,
        user=user,
        thread_id=thread_id,
        message=strategy.strategy_thesis,
    )
    assert confirmation["stage_outcome"] == "await_approval", confirmation.get(
        "pending_strategy"
    )
    assert received == []
    reference = next(
        ref
        for ref in confirmation["artifact_references"]
        if ref["artifact_kind"] == "confirmation"
    )
    action = {
        "type": "run_backtest",
        "presentation": "confirmation",
        "payload": {
            "artifact_id": reference["artifact_id"],
            "confirmation_id": reference["artifact_id"],
            "conversation_id": thread_id,
            "launch_payload_hash": reference["metadata"]["launch_payload_hash"],
        },
    }
    result = await run_agent_turn(
        workflow=workflow,
        user=user,
        thread_id=thread_id,
        message="Run backtest",
        action_context=action,
    )

    assert len(interpreted) == 1
    assert len(received) == 1
    launch = received[0]
    assert launch["_execution_realism"] == {
        "enabled": True,
        "fee_bps": 0,
        "slippage_bps": 5,
    }
    assert launch["date_range"] == strategy.date_range
    assert launch["benchmark_symbol"] == "SPY"
    if kind == "dca_accumulation":
        assert launch["starting_capital"] == 0
        assert launch["recurring_contribution"] == strategy.capital_amount
        assert launch["cadence"] == strategy.cadence
    else:
        assert launch["entry_rule"] == strategy.entry_rule
        assert launch["exit_rule"] == strategy.exit_rule
    cards = result["final_response_payload"]["tool_result_cards"]
    assert len(cards) == 1
    assert cards[0]["call_id"] == reference["artifact_id"]
    checkpoint = await workflow.aget_state({"configurable": {"thread_id": thread_id}})
    approved = checkpoint.values["run_state"].candidate_strategy_draft
    assert cards[0]["arguments"]["strategy"] == approved.model_dump(mode="json")
    assert cards[0]["outcome"]["result"]["job_id"] == job_id
    assert cards[0]["presentation"]["answer"] is None
