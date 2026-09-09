"""Rich declared input reaches preparation and exact confirmation approval."""

from __future__ import annotations

import pytest
from argus.agent_runtime.stages import execute
from argus.agent_runtime.stages.interpret_types import StageResult
from argus.agent_runtime.state.models import TaskSnapshot, UserState
from argus.agent_runtime.tools.backtest_presentation import BacktestArguments
from argus.agent_runtime.tools.registered_backtest import (
    backtest_call_is_approved,
    get_backtest_declaration,
)
from argus.domain.tool_contracts import ToolCall
from argus.domain.tool_declaration import ToolCatalog
from faker import Faker

from tests.agent_runtime.test_registered_tool_execution import _dca_state, _forbid_launch

fake = Faker()


def test_declared_strategy_input_preserves_rich_capital_and_temporal_facts():
    arguments = BacktestArguments.model_validate(
        {
            "strategy": {
                "strategy_type": "dca_accumulation",
                "asset_universe": ["SPY"],
                "date_range_intent": {
                    "kind": "explicit_range",
                    "start": "2024-01-01",
                    "end": "2024-12-31",
                },
                "initial_capital": 0,
                "recurring_contribution": 200,
                "total_capital": 5000,
                "field_provenance": {
                    "initial_capital": "explicit_user",
                    "recurring_contribution": "explicit_user",
                },
            }
        }
    )
    payload = arguments.strategy.model_dump(mode="json")

    assert payload["initial_capital"] == 0
    assert payload["recurring_contribution"] == 200
    assert payload["total_capital"] == 5000
    assert payload["date_range_intent"]["start"] == "2024-01-01"
    assert payload["field_provenance"]["initial_capital"] == "explicit_user"


@pytest.mark.asyncio()
@pytest.mark.parametrize(
    "prepared_outcome", ["ready_for_confirmation", "needs_clarification"]
)
async def test_unapproved_call_prepares_once_with_trusted_context(
    monkeypatch, prepared_outcome
):
    from argus.agent_runtime.interpreter import backtest_calls

    state = _dca_state(approved=False)
    state.tool_calls = [
        ToolCall(
            tool_name="backtest",
            call_id=fake.uuid4(),
            arguments={
                "strategy": {
                    "asset_universe": state.candidate_strategy_draft.asset_universe,
                    "initial_capital": 0,
                    "recurring_contribution": 200,
                }
            },
        )
    ]
    user = UserState(user_id=fake.uuid4())
    snapshot = TaskSnapshot()
    metadata = {"requested_field": "date_range"}
    received = []

    async def prepare(input, **context):
        received.append((input, context))
        return StageResult(
            outcome=prepared_outcome,
            stage_patch={
                "candidate_strategy_draft": state.candidate_strategy_draft,
                "missing_required_fields": ["date_range"]
                if prepared_outcome == "needs_clarification"
                else [],
            },
        )

    monkeypatch.setattr(backtest_calls, "prepare_backtest_tool_input", prepare)
    monkeypatch.setattr(execute, "_launch_payload", _forbid_launch)
    result = await execute.execute_stage_async(
        state=state,
        tool=object(),
        catalog=ToolCatalog((get_backtest_declaration(),)),
        user=user,
        latest_task_snapshot=snapshot,
        selected_thread_metadata=metadata,
    )

    assert result.outcome == prepared_outcome
    assert len(received) == 1
    input, trusted = received[0]
    assert input.initial_capital == 0
    assert trusted["state"] is state
    assert trusted["user"] is user
    assert trusted["latest_task_snapshot"] is snapshot
    assert trusted["selected_thread_metadata"] is metadata
    assert result.patch["tool_calls"] == state.tool_calls
    assert result.patch["tool_call_records"] == []


def test_canonical_approval_projection_preserves_exact_confirmation_and_zero():
    from argus.agent_runtime.backtest_input import BacktestStrategyInput

    state = _dca_state(approved=True)
    canonical = state.candidate_strategy_draft
    input = BacktestStrategyInput.from_runtime_strategy(canonical)
    call = ToolCall(
        tool_name="backtest",
        call_id=fake.uuid4(),
        arguments={
            "strategy": input.model_dump(mode="json"),
        },
    )

    assert input.to_runtime_strategy() == canonical
    assert backtest_call_is_approved(call=call, state=state)
    changed = input.model_copy(update={"capital_amount": canonical.capital_amount + 1})
    assert not backtest_call_is_approved(
        call=call.model_copy(
            update={"arguments": {"strategy": changed.model_dump(mode="json")}}
        ),
        state=state,
    )


@pytest.mark.asyncio()
async def test_preparation_cannot_approve_a_different_call(monkeypatch):
    from argus.agent_runtime.backtest_input import BacktestStrategyInput
    from argus.agent_runtime.interpreter import backtest_calls

    state = _dca_state(approved=True)
    changed = BacktestStrategyInput.from_runtime_strategy(
        state.candidate_strategy_draft
    ).model_copy(
        update={"capital_amount": state.candidate_strategy_draft.capital_amount + 1}
    )
    state.tool_calls = [
        ToolCall(
            tool_name="backtest",
            call_id=fake.uuid4(),
            arguments={"strategy": changed.model_dump(mode="json")},
        )
    ]

    async def invalid_preparation(input, **context):
        return StageResult(outcome="approved_for_execution")

    monkeypatch.setattr(
        backtest_calls, "prepare_backtest_tool_input", invalid_preparation
    )
    monkeypatch.setattr(execute, "_launch_payload", _forbid_launch)
    with pytest.raises(ValueError, match="cannot authorize execution"):
        await execute.execute_stage_async(
            state=state,
            tool=object(),
            catalog=ToolCatalog((get_backtest_declaration(),)),
        )


@pytest.mark.asyncio()
async def test_execution_preparation_blockers_use_the_existing_clarify_node(monkeypatch):
    from argus.agent_runtime.graph import workflow
    from argus.agent_runtime.runtime import build_workflow_input
    from langgraph.checkpoint.memory import MemorySaver

    call = ToolCall(
        tool_name="backtest", call_id=fake.uuid4(), arguments={"strategy": {}}
    )

    async def interpret(**context):
        return StageResult(
            outcome="approved_for_execution", stage_patch={"tool_calls": [call]}
        )

    async def blocked_execution(**context):
        return StageResult(
            outcome="needs_clarification",
            stage_patch={
                "tool_calls": [call],
                "missing_required_fields": ["date_range"],
            },
        )

    seen = []

    async def clarify(**context):
        seen.append(context["state"].missing_required_fields)
        return StageResult(outcome="await_user_reply")

    monkeypatch.setattr(workflow, "interpret_stage_async", interpret)
    monkeypatch.setattr(workflow, "execute_stage_async", blocked_execution)
    monkeypatch.setattr(workflow, "clarify_stage_async", clarify)
    graph = workflow.build_workflow(
        checkpointer=MemorySaver(),
        tool=object(),
    )
    result = await graph.ainvoke(
        build_workflow_input(
            user=UserState(user_id=fake.uuid4()), message=fake.sentence()
        ),
        config={"configurable": {"thread_id": fake.uuid4()}},
    )

    assert result["stage_outcome"] == workflow.WorkflowStageOutcome.AWAIT_USER_REPLY
    assert seen == [["date_range"]]
    assert result["latest_task_snapshot"].pending_tool_calls == [call]
