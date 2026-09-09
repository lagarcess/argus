"""Prepare a declared backtest through the existing strategy contract owners."""

from __future__ import annotations

from typing import Any

from argus.agent_runtime.backtest_input import BacktestStrategyInput
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.interpreter.audits import (
    StatedExecutionCost,
    StatedRunFieldFidelityAudit,
)
from argus.agent_runtime.interpreter.date_window_repair import (
    _response_with_latest_result_window_bound,
)
from argus.agent_runtime.interpreter.execution_cost_fidelity import (
    apply_cost_fidelity,
    numeric_cost_anchor_in_message,
)
from argus.agent_runtime.llm_interpreter_types import (
    LLMInterpretationResponse,
    LLMStrategyDraft,
)
from argus.agent_runtime.stages.interpret_types import InterpretationRequest, StageResult
from argus.agent_runtime.state.models import RunState, TaskSnapshot, UserState
from argus.agent_runtime.strategy_contract import canonical_strategy_type


async def prepare_backtest_tool_input(
    input: BacktestStrategyInput,
    *,
    state: RunState,
    user: UserState | None,
    latest_task_snapshot: TaskSnapshot | None = None,
    selected_thread_metadata: dict[str, Any] | None = None,
) -> StageResult:
    from argus.agent_runtime.llm_interpreter import canonical_strategy_interpretation
    from argus.agent_runtime.stages.interpret import _stage_result_from_interpretation

    user = user if user is not None else UserState(user_id="tool-execution")
    draft = LLMStrategyDraft.model_validate(input.model_dump(mode="python"))
    _declare_money_roles(draft)
    response = LLMInterpretationResponse(
        intent="calculate",
        task_relation="new_task",
        semantic_turn_act="new_idea",
        user_goal_summary=input.strategy_thesis or state.user_goal_summary or "",
        candidate_strategy_draft=draft,
    )
    _ground_declared_costs(response, current_message=state.current_user_message)
    request = InterpretationRequest(
        current_user_message=state.current_user_message,
        user=user,
        latest_task_snapshot=latest_task_snapshot,
        selected_thread_metadata=selected_thread_metadata or {},
    )
    response = _response_with_latest_result_window_bound(response, request=request)
    interpretation = canonical_strategy_interpretation(response, request=request)
    # Each declared call owns its complete input. A previous artifact or a Run
    # action cannot overwrite a different call or authorize it during preparation.
    preparation_state = state.model_copy(
        update={
            "tool_calls": [],
            "structured_action": None,
            "confirmation_payload": None,
            "candidate_strategy_draft": interpretation.candidate_strategy_draft,
        }
    )
    result = await _stage_result_from_interpretation(
        state=preparation_state,
        user=user,
        snapshot=None,
        interpretation=interpretation,
        capability_contract=build_default_capability_contract(),
        selected_thread_metadata={},
    )
    if result.outcome not in {"ready_for_confirmation", "needs_clarification"}:
        raise ValueError("Backtest input preparation cannot authorize execution")
    return result


def _declare_money_roles(draft: LLMStrategyDraft) -> None:
    """Typed argument identity owns the role; zero remains a supplied fact."""
    draft.field_provenance.update(draft.declared_capital_roles())
    if canonical_strategy_type(draft.strategy_type) == "dca_accumulation":
        if draft.capital_amount is not None:
            draft.field_provenance.setdefault("capital_amount", "recurring_contribution")
        if draft.cadence is not None:
            draft.field_provenance.setdefault("cadence", "explicit_user")


def _ground_declared_costs(
    response: LLMInterpretationResponse, *, current_message: str
) -> None:
    draft = response.candidate_strategy_draft
    costs: dict[str, StatedExecutionCost] = {}
    for name, audit_field in (("fee_rate", "fee"), ("slippage", "slippage")):
        value = getattr(draft, name)
        if value is None:
            continue
        draft.extra_parameters[name] = value
        span = draft.evidence_spans.get(name)
        if (
            span
            and span in current_message
            and numeric_cost_anchor_in_message(value, span)
        ):
            costs[audit_field] = StatedExecutionCost(
                rate=float(value), evidence_span=span
            )
    apply_cost_fidelity(
        response,
        StatedRunFieldFidelityAudit.model_validate(costs),
        current_message,
        prior_strategy=None,
    )
