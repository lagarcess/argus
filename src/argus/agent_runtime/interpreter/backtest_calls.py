"""Prepare a declared backtest through the existing strategy contract owners."""

from __future__ import annotations

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
from argus.agent_runtime.semantic_integrity import (
    DECLARED_TOOL_INPUT_CONFLICT,
    canonical_capital_role,
    strategy_semantic_facts,
)
from argus.agent_runtime.stages.interpret_types import (
    InterpretationRequest,
    SemanticTurnAct,
    StageResult,
)
from argus.agent_runtime.state.models import (
    RunState,
    StrategySummary,
    TaskSnapshot,
    UserState,
)
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
        _declare_money_roles(response.candidate_strategy_draft)
        conflicts = _known_input_conflicts(before, response, request=request)
        if conflicts:
            # A repair is one proposed replacement. Reject it atomically:
            # restoring one carrier can leave another overriding the same fact.
            response = before.model_copy(deep=True)
            response.ambiguous_fields.extend(conflicts)
            response.requires_clarification = True
            response.assistant_response = None
        # Readiness owns input facts and blockers. It cannot reselect a tool,
        # change this call's context relation, or turn preparation into approval.
        response.intent = before.intent
        response.task_relation = before.task_relation
        response.semantic_turn_act = before.semantic_turn_act
        response.tool_calls = []
        result = await _prepared_stage(response, request=request, state=state)
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
    from argus.agent_runtime.interpreter.artifact_assumption_edit import (
        _current_artifact_strategy,
    )
    from argus.agent_runtime.llm_interpreter import canonical_strategy_interpretation
    from argus.agent_runtime.stages.interpret import _stage_result_from_interpretation

    _ground_declared_costs(
        response,
        current_message=request.current_user_message,
        prior_strategy=_current_artifact_strategy(request),
    )
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


def _known_input_conflicts(
    before: LLMInterpretationResponse,
    after: LLMInterpretationResponse,
    *,
    request: InterpretationRequest,
) -> list[LLMAmbiguousField]:
    facts = [
        _draft_semantic_facts(response, request=request) for response in (before, after)
    ]
    return [
        LLMAmbiguousField(
            field_name=name,
            raw_value=str(value),
            candidate_normalized_value=facts[1].get(name),
            reason_code=DECLARED_TOOL_INPUT_CONFLICT,
        )
        for name, value in facts[0].items()
        if not _preserves_supplied_fact(value, facts[1].get(name))
    ]


def _draft_semantic_facts(
    response: LLMInterpretationResponse, *, request: InterpretationRequest
) -> dict[str, Any]:
    from argus.agent_runtime.interpreter.artifact_assumption_edit import (
        _canonical_draft_date_request,
    )
    from argus.agent_runtime.interpreter.strategy_builder import (
        _merge_prior_strategy,
        _strategy_from_llm,
    )
    from argus.agent_runtime.stages.interpret import _supported_timeframes

    response = response.model_copy(deep=True)
    draft = response.candidate_strategy_draft
    strategy = _strategy_from_llm(draft, request.current_user_message)
    _merge_prior_strategy(strategy=strategy, request=request, response=response)
    facts = strategy_semantic_facts(
        strategy,
        selected_thread_metadata=request.selected_thread_metadata,
        supported_timeframes=_supported_timeframes(build_default_capability_contract()),
    )
    date_request = _canonical_draft_date_request(draft, request=request)
    facts["date_range"] = (
        {"kind": date_request[0], "value": date_request[1]}
        if date_request is not None
        else None
    )
    # Declared runtime extensions still carry supplied facts before evidence
    # validation. Their declaration owns membership; this guard adds no slot map.
    for name, field in type(draft).model_fields.items():
        metadata = field.json_schema_extra
        if isinstance(metadata, dict) and metadata.get("x-argus-runtime-extension"):
            facts[name] = getattr(draft, name)
    return facts


def _preserves_supplied_fact(before: Any, after: Any) -> bool:
    if before is None or before in ("", [], {}):
        return True
    if isinstance(before, dict):
        return isinstance(after, dict) and all(
            _preserves_supplied_fact(value, after.get(name))
            for name, value in before.items()
        )
    return bool(before == after)


def _declare_money_roles(draft: LLMStrategyDraft) -> None:
    """Typed argument identity owns the role; zero remains a supplied fact."""
    draft.field_provenance.update(draft.declared_capital_roles())
    if draft.capital_amount is not None:
        role = canonical_capital_role(
            draft.field_provenance.get("capital_amount"),
            strategy_type=draft.strategy_type,
        )
        if role is not None:
            draft.field_provenance.setdefault("capital_amount", role)
    if canonical_strategy_type(draft.strategy_type) == "dca_accumulation":
        if draft.cadence is not None:
            draft.field_provenance.setdefault("cadence", "explicit_user")


def _ground_declared_costs(
    response: LLMInterpretationResponse,
    *,
    current_message: str,
    prior_strategy: StrategySummary | None = None,
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
        prior_strategy=prior_strategy,
    )
