"""Trusted provider context follows the pending queue across Run approvals."""

from __future__ import annotations

import json

import pytest
from argus.agent_runtime.backtest_input import BacktestStrategyInput
from argus.agent_runtime.graph import workflow
from argus.agent_runtime.interpreter.provider_context_assets import (
    TOOL_ASSET_CONTEXT_SIGNAL,
    context_for_declared_assets,
)
from argus.agent_runtime.runtime import _public_result
from argus.agent_runtime.stages.interpret_types import StageResult
from argus.agent_runtime.state.models import (
    RunState,
    TaskSnapshot,
    ToolCallRecord,
    UserState,
)
from argus.domain.tool_contracts import ToolCall
from faker import Faker

from tests.agent_runtime.test_provider_asset_ownership import BTC_CONTEXT_ROW
from tests.agent_runtime.test_registered_tool_execution import _dca_state

fake = Faker()


@pytest.fixture
def pending_queue():
    state = _dca_state(approved=False)
    strategies = [
        state.candidate_strategy_draft.model_copy(update={"asset_universe": [symbol]})
        for symbol in ("AAPL", "MSFT")
    ]
    state.tool_calls = [
        ToolCall(
            tool_name="backtest",
            call_id=fake.uuid4(),
            arguments={
                "strategy": BacktestStrategyInput.from_runtime_strategy(
                    strategy
                ).model_dump(mode="json")
            },
        )
        for strategy in strategies
    ]
    rows = [
        {
            **BTC_CONTEXT_ROW,
            "symbol": strategy.asset_universe[0],
            "raw_text": strategy.asset_universe[0],
            "raw_symbol": strategy.asset_universe[0],
            "asset_class": strategy.asset_class,
            "name": fake.company(),
            "exchange": "NASDAQ",
        }
        for strategy in strategies
    ]
    packet = json.dumps({"asset_resolution_candidates": rows})
    state.normalized_signals = {
        TOOL_ASSET_CONTEXT_SIGNAL: packet,
        "unrelated_turn_signal": fake.uuid4(),
    }
    return state, strategies, packet


def _snapshot(state, *, prior=None, outcome="await_approval"):
    return workflow._build_task_snapshot(
        run_state=state,
        stage_outcome=outcome,
        prior_task_snapshot=prior,
        artifact_references=[],
    )


@pytest.mark.asyncio
async def test_two_pending_calls_keep_trusted_context_across_snapshot_and_run(
    monkeypatch, pending_queue
):
    initial, strategies, packet = pending_queue
    snapshot = _snapshot(initial)
    assert snapshot.pending_tool_context == {TOOL_ASSET_CONTEXT_SIGNAL: packet}

    for index, strategy in enumerate(strategies):
        # Checkpoint deserialization and a new RunState are the real turn boundary.
        snapshot = TaskSnapshot.model_validate_json(snapshot.model_dump_json())
        current = RunState.new(
            current_user_message=fake.sentence(),
            recent_thread_history=[],
            action_context={"type": "run_backtest"},
        )
        assert current.normalized_signals == {}

        async def approve(strategy=strategy, **kwargs):
            return StageResult(
                outcome="approved_for_execution",
                stage_patch={"candidate_strategy_draft": strategy},
            )

        monkeypatch.setattr(workflow, "interpret_stage_async", approve)
        resumed = await workflow._interpret_node_async(
            {
                "run_state": current,
                "user": UserState(user_id=fake.uuid4()),
                "latest_task_snapshot": snapshot,
            },
            structured_interpreter=None,
        )
        state = resumed["run_state"]
        assert state.normalized_signals[TOOL_ASSET_CONTEXT_SIGNAL] == packet
        assert [call.call_id for call in state.tool_calls] == [
            call.call_id for call in initial.tool_calls[index:]
        ]
        filtered = context_for_declared_assets(
            state.normalized_signals[TOOL_ASSET_CONTEXT_SIGNAL],
            strategy.asset_universe,
        )
        assert [
            row["symbol"] for row in json.loads(filtered)["asset_resolution_candidates"]
        ] == strategy.asset_universe

        state.tool_call_records = [
            ToolCallRecord(
                call_id=state.tool_calls[0].call_id,
                tool_name=state.tool_calls[0].tool_name,
                outcome="succeeded",
            )
        ]
        state.tool_calls = state.tool_calls[1:]
        snapshot = _snapshot(
            state,
            prior=resumed["latest_task_snapshot"],
            outcome="await_approval" if state.tool_calls else "execution_succeeded",
        )

    assert snapshot.pending_tool_calls == []
    assert snapshot.pending_tool_context == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("current_packet", [None, "fresh-provider-context"])
async def test_approval_preserves_current_signals_and_prefers_current_trusted_context(
    monkeypatch, pending_queue, current_packet
):
    initial, _, packet = pending_queue
    current = RunState.new(
        current_user_message=fake.sentence(),
        recent_thread_history=[],
        action_context={"type": "run_backtest"},
    )
    current.normalized_signals = {"current_turn_signal": fake.uuid4()}
    stage_signals = {"approval_signal": fake.uuid4()}
    if current_packet is not None:
        stage_signals[TOOL_ASSET_CONTEXT_SIGNAL] = current_packet

    async def approve(**kwargs):
        return StageResult(
            outcome="approved_for_execution",
            stage_patch={"normalized_signals": stage_signals},
        )

    monkeypatch.setattr(workflow, "interpret_stage_async", approve)
    resumed = await workflow._interpret_node_async(
        {
            "run_state": current,
            "user": UserState(user_id=fake.uuid4()),
            "latest_task_snapshot": _snapshot(initial),
        },
        structured_interpreter=None,
    )
    assert resumed["run_state"].normalized_signals == {
        TOOL_ASSET_CONTEXT_SIGNAL: packet,
        **current.normalized_signals,
        **stage_signals,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_unrelated_turn_does_not_restore_pending_context(
    monkeypatch, pending_queue, cancel
):
    initial, _, packet = pending_queue
    current = RunState.new(
        current_user_message=fake.sentence(),
        recent_thread_history=[],
        action_context={"type": "cancel_confirmation"} if cancel else None,
    )

    async def answer(**kwargs):
        return StageResult(outcome="ready_to_respond")

    monkeypatch.setattr(workflow, "interpret_stage_async", answer)
    result = await workflow._interpret_node_async(
        {
            "run_state": current,
            "user": UserState(user_id=fake.uuid4()),
            "latest_task_snapshot": _snapshot(initial),
        },
        structured_interpreter=None,
    )

    assert result["run_state"].normalized_signals == {}
    snapshot = result["latest_task_snapshot"]
    assert snapshot.pending_tool_calls == ([] if cancel else initial.tool_calls)
    assert snapshot.pending_tool_context == (
        {} if cancel else {TOOL_ASSET_CONTEXT_SIGNAL: packet}
    )


@pytest.mark.parametrize("new_packet", [None, "new-queue-provider-context"])
def test_replaced_queue_does_not_inherit_previous_context(pending_queue, new_packet):
    initial, _, _ = pending_queue
    current = RunState(
        current_user_message=fake.sentence(),
        tool_calls=[initial.tool_calls[0].model_copy(update={"call_id": fake.uuid4()})],
        normalized_signals={TOOL_ASSET_CONTEXT_SIGNAL: new_packet},
    )
    snapshot = _snapshot(current, prior=_snapshot(initial))

    assert snapshot.pending_tool_calls == current.tool_calls
    assert snapshot.pending_tool_context == (
        {} if new_packet is None else {TOOL_ASSET_CONTEXT_SIGNAL: new_packet}
    )


def test_completed_queue_cannot_be_preserved_as_a_side_question(pending_queue):
    initial, _, _ = pending_queue
    current = initial.model_copy(deep=True)
    current.tool_calls = []
    current.tool_call_records = [
        ToolCallRecord(
            call_id=call.call_id, tool_name=call.tool_name, outcome="succeeded"
        )
        for call in initial.tool_calls
    ]
    snapshot = _snapshot(current, prior=_snapshot(initial), outcome="ready_to_respond")

    assert snapshot.pending_tool_calls == []
    assert snapshot.pending_tool_context == {}


def test_legacy_snapshot_has_no_pending_context():
    snapshot = TaskSnapshot.model_validate({"pending_tool_calls": []})

    assert snapshot.pending_tool_context == {}


def test_pending_context_is_persisted_but_omitted_from_model_and_public_projections(
    pending_queue,
):
    from argus.agent_runtime.capabilities.contract import (
        build_default_capability_contract,
    )
    from argus.agent_runtime.llm_interpreter import OpenRouterStructuredInterpreter
    from argus.agent_runtime.stages.interpret_types import InterpretationRequest
    from argus.domain.tool_declaration import ToolCatalog

    state, _, packet = pending_queue
    snapshot = _snapshot(state)
    assert snapshot.model_dump()["pending_tool_context"] == {
        TOOL_ASSET_CONTEXT_SIGNAL: packet
    }
    public = _public_result({"run_state": state, "latest_task_snapshot": snapshot})
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract(), tool_catalog=ToolCatalog(())
    )
    messages = interpreter._messages(
        InterpretationRequest(
            current_user_message=fake.sentence(),
            user=UserState(user_id=fake.uuid4()),
            latest_task_snapshot=snapshot,
        )
    )
    projections = [
        json.dumps(public),
        str([message.content for message in messages]),
        json.dumps(interpreter.response_model.model_json_schema()),
    ]
    for projection in projections:
        assert "pending_tool_context" not in projection
        assert TOOL_ASSET_CONTEXT_SIGNAL not in projection
        assert packet not in projection
