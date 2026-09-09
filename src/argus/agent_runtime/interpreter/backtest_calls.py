"""Prepare a declared backtest through the existing strategy contract owners."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, cast

from argus.agent_runtime.backtest_input import BacktestStrategyInput
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.interpreter import provider_context_assets
from argus.agent_runtime.interpreter.audits import (
    StatedExecutionCost,
    StatedRunFieldFidelityAudit,
)
from argus.agent_runtime.interpreter.execution_cost_fidelity import (
    apply_cost_fidelity,
    numeric_cost_anchor_in_message,
)
from argus.agent_runtime.interpreter.focused_extraction import (
    _merge_focused_repair_with_base,
)
from argus.agent_runtime.interpreter.repair_observability import repair_effect_metadata
from argus.agent_runtime.llm_interpreter_types import (
    InterpretationContractError,
    LLMAmbiguousField,
    LLMInterpretationResponse,
    LLMStrategyDraft,
)
from argus.agent_runtime.stages.interpret_types import (
    InterpretationRequest,
    SemanticTurnAct,
    StageResult,
)
from argus.agent_runtime.state.models import RunState, TaskSnapshot, UserState
from argus.agent_runtime.strategy_contract import canonical_strategy_type
from argus.domain.tool_contracts import ToolCall
from argus.llm.openrouter import tool_call_receipt_scope


async def prepare_backtest_tool_input(
    input: BacktestStrategyInput,
    *,
    state: RunState,
    user: UserState | None,
    latest_task_snapshot: TaskSnapshot | None = None,
    selected_thread_metadata: dict[str, Any] | None = None,
    call: ToolCall | None = None,
) -> StageResult:
    from argus.agent_runtime import llm_interpreter

    user = user if user is not None else UserState(user_id="tool-execution")
    single_call = len(state.tool_calls) <= 1
    message = _call_source(
        input, state=state, call=call, latest_task_snapshot=latest_task_snapshot
    )
    request = InterpretationRequest(
        current_user_message=message or "",
        recent_thread_history=state.recent_thread_history if single_call else [],
        user=user,
        latest_task_snapshot=latest_task_snapshot if single_call else None,
        selected_thread_metadata=(selected_thread_metadata or {}) if single_call else {},
    )
    draft = LLMStrategyDraft.model_validate(input.model_dump(mode="python"))
    _declare_money_roles(draft)
    response = LLMInterpretationResponse(
        intent="calculate",
        task_relation=(state.task_relation or "new_task") if single_call else "new_task",
        semantic_turn_act=(
            cast(SemanticTurnAct, state.semantic_turn_act)
            if single_call
            and state.semantic_turn_act in {"answer_pending_need", "refine_current_idea"}
            else "new_idea"
        ),
        user_goal_summary=input.strategy_thesis or state.user_goal_summary or "",
        candidate_strategy_draft=draft,
    )
    context = provider_context_assets.context_for_declared_assets(
        state.normalized_signals.get(provider_context_assets.TOOL_ASSET_CONTEXT_SIGNAL),
        draft.asset_universe,
    )
    response = llm_interpreter._normalize_response_for_runtime_context(
        response, request=request, asset_resolution_context=context
    )
    before = response.model_copy(deep=True)
    # A complete batch is already scoped by typed arguments. Never reread its
    # whole question once per call to manufacture another call's missing facts.
    result = None
    repair_attempted = False
    repair_failed = False
    if not single_call:
        result = await _prepared_stage(
            response.model_copy(deep=True), request=request, state=state
        )
    if message is not None and (
        result is None or result.outcome != "ready_for_confirmation"
    ):
        repair_attempted = True
        with tool_call_receipt_scope(
            call_id=call.call_id if call is not None else "legacy-backtest-preparation",
            tool_name="backtest",
        ):
            try:
                response = await llm_interpreter._audited_response_ready_for_runtime(
                    response=response,
                    preferred_model="",
                    request=request,
                    asset_resolution_context=context,
                )
            except InterpretationContractError:
                repair_failed = True
                response = before.model_copy(deep=True)
                response.requires_clarification = True
        response = _merge_focused_repair_with_base(
            response=response, base_response=before
        )
        conflicts = _preserve_known_input(
            before, response, message=request.current_user_message
        )
        # Readiness owns input facts and blockers. It cannot reselect a tool,
        # change this call's context relation, or turn preparation into approval.
        response.intent = before.intent
        response.task_relation = before.task_relation
        response.semantic_turn_act = before.semantic_turn_act
        response.tool_calls = []
        _declare_money_roles(response.candidate_strategy_draft)
        result = await _prepared_stage(response, request=request, state=state)
        if conflicts:
            result.outcome = "needs_clarification"
            result.stage_patch.update(
                requires_clarification=True,
                assistant_response=None,
                ambiguous_fields=[
                    *result.patch.get("ambiguous_fields", []),
                    *[item.model_dump(mode="python") for item in conflicts],
                ],
            )
    if result is None:
        result = await _prepared_stage(response, request=request, state=state)
    result.stage_patch["normalized_signals"] = {
        **state.normalized_signals,
        **result.patch.get("normalized_signals", {}),
        "tool_input_repair": {
            "call_id": call.call_id if call is not None else None,
            "repair_attempted": repair_attempted,
            **repair_effect_metadata(
                before=before,
                after=response,
                trigger_reason="declared_backtest_input",
                repair_applied=repair_attempted and not repair_failed,
                no_op_reason=(
                    "readiness_contract_unresolved"
                    if repair_failed
                    else "unscoped_batch"
                    if message is None
                    else None
                ),
            ),
        },
    }
    return result


async def _prepared_stage(
    response: LLMInterpretationResponse,
    *,
    request: InterpretationRequest,
    state: RunState,
) -> StageResult:
    from argus.agent_runtime.llm_interpreter import canonical_strategy_interpretation
    from argus.agent_runtime.stages.interpret import _stage_result_from_interpretation

    _ground_declared_costs(response, current_message=request.current_user_message)
    interpretation = canonical_strategy_interpretation(response, request=request)
    preparation_state = state.model_copy(
        update={
            "current_user_message": request.current_user_message,
            "tool_calls": [],
            "structured_action": None,
            "confirmation_payload": None,
            "candidate_strategy_draft": interpretation.candidate_strategy_draft,
        }
    )
    result = await _stage_result_from_interpretation(
        state=preparation_state,
        user=request.user,
        snapshot=request.latest_task_snapshot,
        interpretation=interpretation,
        capability_contract=build_default_capability_contract(),
        selected_thread_metadata=request.selected_thread_metadata,
    )
    if result.outcome not in {"ready_for_confirmation", "needs_clarification"}:
        raise ValueError("Backtest input preparation cannot authorize execution")
    return result


def _call_source(
    input: BacktestStrategyInput,
    *,
    state: RunState,
    call: ToolCall | None,
    latest_task_snapshot: TaskSnapshot | None = None,
) -> str | None:
    if len(state.tool_calls) <= 1:
        return state.current_user_message
    source = (input.raw_user_phrasing or "").strip()
    messages = [state.current_user_message]
    if (
        latest_task_snapshot is not None
        and call is not None
        and call in latest_task_snapshot.pending_tool_calls
        and state.tool_calls
    ):
        from argus.agent_runtime.tools.registered_backtest import (
            backtest_call_is_approved,
        )

        if backtest_call_is_approved(call=state.tool_calls[0], state=state):
            messages.extend(
                item.content
                for item in state.recent_thread_history
                if item.role == "user"
            )
    matches = [message.strip() for message in messages if source and source in message]
    if len(matches) != 1:
        return None
    message = matches[0]
    if source == message:
        return None
    start = message.find(source)
    if start != message.rfind(source):
        return None
    end = start + len(source)
    for other in state.tool_calls:
        if call is not None and other.call_id == call.call_id:
            continue
        strategy = other.arguments.get("strategy")
        other_source = (
            strategy.get("raw_user_phrasing") if isinstance(strategy, dict) else None
        )
        if isinstance(other_source, str) and other_source.strip():
            other_source = other_source.strip()
            other_start = message.find(other_source)
            if other_start >= 0 and (
                other_start != message.rfind(other_source)
                or max(start, other_start) < min(end, other_start + len(other_source))
            ):
                return None
    return source


def _preserve_known_input(
    before: LLMInterpretationResponse, after: LLMInterpretationResponse, *, message: str
) -> list[LLMAmbiguousField]:
    from argus.agent_runtime.llm_interpreter import _strategy_from_llm

    base = before.candidate_strategy_draft
    repaired = after.candidate_strategy_draft
    canonical = [
        _strategy_from_llm(draft.model_copy(deep=True), message).model_dump(mode="python")
        for draft in (base, repaired)
    ]
    descriptive = {
        "raw_user_phrasing",
        "language",
        "strategy_thesis",
        "entry_logic",
        "exit_logic",
        "date_range_raw_text",
        "assumptions",
        "field_provenance",
        "evidence_spans",
        "extra_parameters",
        "resolution_provenance",
    }
    conflicts = []
    for name in type(base).model_fields:
        value = getattr(base, name)
        if name in descriptive or value is None or value in ("", [], {}):
            continue
        replacement = getattr(repaired, name)
        if replacement == value:
            continue
        facts = [item.get(name, item["extra_parameters"].get(name)) for item in canonical]
        if facts[0] is not None and facts[0] == facts[1]:
            continue
        setattr(repaired, name, deepcopy(value))
        if name in repaired.extra_parameters:
            if name in base.extra_parameters:
                repaired.extra_parameters[name] = deepcopy(base.extra_parameters[name])
            else:
                repaired.extra_parameters.pop(name)
        if replacement is not None and replacement not in ("", [], {}):
            conflicts.append(
                LLMAmbiguousField(
                    field_name=name,
                    raw_value=str(value),
                    reason_code="declared_tool_input_conflict",
                )
            )
    return conflicts


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
