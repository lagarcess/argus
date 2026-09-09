"""The existing backtest execution owner exposed as a typed catalog tool."""

from __future__ import annotations

import asyncio
from typing import get_args

from argus.agent_runtime.confirmation_artifacts import confirmation_id_from_payload
from argus.agent_runtime.stages.interpret_types import StageResult
from argus.agent_runtime.stages.tool_execution import ToolExecutionContext
from argus.agent_runtime.state.models import RunState
from argus.agent_runtime.tools.backtest_presentation import (
    BacktestArguments,
    BacktestExecutionResult,
    backtest_execution_result,
    backtest_presentation,
)
from argus.domain.tool_contracts import (
    ToolCall,
)
from argus.domain.tool_declaration import (
    ToolCardBinding,
    ToolDeclaration,
    ToolInvocationError,
    ToolPolicy,
    ToolProgressTemplate,
)


async def run_registered_backtest(
    arguments: BacktestArguments, *, context: ToolExecutionContext
) -> BacktestExecutionResult:
    from argus.agent_runtime.stages.execute import execute_stage

    if (
        context is None
        or not context.approval_available
        or context.call is None
        or not backtest_call_is_approved(call=context.call, state=context.state)
    ):
        raise ToolInvocationError("invalid", code="confirmation_required")
    context.stage_result = await asyncio.to_thread(
        execute_stage,
        state=context.state,
        tool=context.backtest_tool,
        max_retries=context.max_retries,
        language=context.language,
    )
    patch = context.stage_result.patch
    job = patch.get("backtest_job")
    if isinstance(job, dict):
        return BacktestExecutionResult(execution_status="pending", job_id=str(job["id"]))
    if context.stage_result.outcome != "execution_succeeded":
        raise ToolInvocationError("unavailable", code="backtest_execution_failed")
    return backtest_execution_result(patch.get("final_response_payload", {}))


def get_backtest_declaration() -> ToolDeclaration:
    from argus.domain.backtesting.config import AssetClass, default_benchmark

    return ToolDeclaration(
        name="backtest",
        description=(
            "Simulate a supported long-only strategy against historical market data. "
            "Each call presents its exact inputs for confirmation before execution."
        ),
        handler=run_registered_backtest,
        confirmation_handler=prepare_backtest_confirmation,
        policy=ToolPolicy(
            execution="workflow", external_calls=1, confirmation="required"
        ),
        progress=ToolProgressTemplate(
            locale_key="chat.tools.progress.backtest",
            argument_fields=("strategy.asset_universe",),
        ),
        card=ToolCardBinding(
            card_type="backtest", version=1, presenter=backtest_presentation
        ),
        domain=(
            "Historical simulations only; no forecasts or real-money orders.",
            "Approved launch validation owns strategy, asset, date and capital semantics.",
            "Unavailable data or invalid execution never yields a numerical answer.",
            *(
                f"Default benchmark for {asset_class}: "
                f"{default_benchmark(asset_class, ['first_tested_symbol'])}."
                for asset_class in get_args(AssetClass)
            ),
        ),
    )


def approved_backtest_call(state: RunState) -> ToolCall | None:
    """Compatibility for an existing validated Run button, never model inference."""
    if (
        state.confirmation_payload is None
        or state.structured_action is None
        or state.structured_action.type != "run_backtest"
    ):
        return None
    return ToolCall(
        tool_name="backtest",
        call_id=confirmation_id_from_payload(state.structured_action.payload),
        arguments={"strategy": state.candidate_strategy_draft.model_dump(mode="json")},
    )


def backtest_call_is_approved(*, call: ToolCall, state: RunState) -> bool:
    from argus.agent_runtime.stages.artifact_context import (
        validated_approval_confirmation_payload_from_state,
    )

    if call.tool_name != "backtest":
        return False
    action = state.structured_action
    if action is None or action.type != "run_backtest":
        return False
    arguments = BacktestArguments.model_validate(call.arguments)
    if arguments.strategy != state.candidate_strategy_draft:
        return False
    return (
        validated_approval_confirmation_payload_from_state(
            state=state, approved_strategy=arguments.strategy
        )
        is not None
    )


def prepare_backtest_confirmation(
    arguments: BacktestArguments, *, context: ToolExecutionContext
) -> StageResult:
    if (
        context.approval_available
        and context.call is not None
        and backtest_call_is_approved(call=context.call, state=context.state)
    ):
        return StageResult(outcome="approved_for_execution")
    return StageResult(
        outcome="ready_for_confirmation",
        stage_patch={
            "candidate_strategy_draft": arguments.strategy.model_dump(mode="python"),
            "confirmation_payload": None,
            "assistant_prompt": None,
        },
    )
