from __future__ import annotations

import asyncio
import inspect
from typing import Any

from argus.agent_runtime.capabilities.answers import compose_capability_answer
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.extraction import detect_unsupported_constraints
from argus.agent_runtime.profile.response_profile import (
    resolve_effective_response_profile,
)
from argus.agent_runtime.resolution import AssetResolution
from argus.agent_runtime.resolution import (
    resolve_asset_candidate as runtime_resolve_asset_candidate,
)
from argus.agent_runtime.response_style import (
    result_followup_heading,
    with_response_heading,
)
from argus.agent_runtime.result_followups import (
    compose_result_followup_response,
    fallback_result_followup_response,
)
from argus.agent_runtime.rule_specs import (
    indicator_parameters_from_strategy as canonical_indicator_parameters_from_strategy,
)
from argus.agent_runtime.rule_specs import (
    moving_average_crossover_text,
    opposite_moving_average_crossover_rule,
    strategy_rule,
)
from argus.agent_runtime.semantic_integrity import (
    SemanticIntegrityReport,
    conserve_semantic_constraints,
    filter_unsubstantiated_timeframe_constraints,
)
from argus.agent_runtime.stages.artifact_context import (
    draft_assumptions_response as _draft_assumptions_response,
)
from argus.agent_runtime.stages.interpret_actions import (
    approval_stage_result_if_applicable as _approval_stage_result_if_applicable,
)
from argus.agent_runtime.stages.interpret_actions import (
    artifact_followup_stage_result_if_applicable as _artifact_followup_stage_result_if_applicable,
)
from argus.agent_runtime.stages.interpret_actions import (
    pending_artifact_followup_stage_result_if_applicable as _pending_artifact_followup_stage_result_if_applicable,
)
from argus.agent_runtime.stages.interpret_actions import (
    retry_failed_action_stage_result_if_applicable as _retry_failed_action_stage_result_if_applicable,
)
from argus.agent_runtime.stages.interpret_actions import (
    structured_action_stage_result_if_applicable as _structured_action_stage_result_if_applicable,
)
from argus.agent_runtime.stages.interpret_types import (
    CapabilityQuestionFocus,
    InterpretationRequest,
    InterpretDecision,
    SemanticTurnAct,
    StageResult,
    StructuredInterpretation,
    StructuredInterpreter,
)
from argus.agent_runtime.state.models import (
    AmbiguousField,
    IntentName,
    ResolutionProvenance,
    ResolutionSource,
    ResponseProfileOverrides,
    RunState,
    StrategySummary,
    TaskSnapshot,
    UnsupportedConstraint,
    UserState,
)
from argus.agent_runtime.strategy_contract import (
    SUPPORTED_STRATEGY_TYPES,
    canonical_strategy_type,
    executable_strategy_type,
)
from argus.agent_runtime.strategy_requirements import (
    missing_required_fields_for_strategy,
)
from argus.agent_runtime.strategy_requirements import (
    valid_rule_spec_from_strategy as _valid_rule_spec_from_strategy,
)
from argus.domain.indicators import (
    IndicatorExecutionSpec,
    executable_indicator_spec,
    normalize_indicator_parameters,
)
from argus.domain.market_data import resolve_asset
from argus.llm.openrouter import invoke_openrouter_chat_completion

_DEFAULT_RESOLVE_ASSET = resolve_asset

STRATEGY_TURN_ACTS: set[SemanticTurnAct] = {
    "new_idea",
    "answer_pending_need",
    "refine_current_idea",
    "approval",
    "unsupported_request",
}

CONTEXTUAL_EDIT_TURN_ACTS = {
    "answer_pending_need",
    "approval",
    "refine_current_idea",
}


def interpret_stage(
    *,
    state: RunState,
    user: UserState,
    latest_task_snapshot: TaskSnapshot | dict[str, Any] | None,
    selected_thread_metadata: dict[str, Any] | None = None,
    structured_interpreter: StructuredInterpreter | None = None,
) -> StageResult:
    return asyncio.run(
        interpret_stage_async(
            state=state,
            user=user,
            latest_task_snapshot=latest_task_snapshot,
            selected_thread_metadata=selected_thread_metadata,
            structured_interpreter=structured_interpreter,
        )
    )


async def interpret_stage_async(
    *,
    state: RunState,
    user: UserState,
    latest_task_snapshot: TaskSnapshot | dict[str, Any] | None,
    selected_thread_metadata: dict[str, Any] | None = None,
    structured_interpreter: StructuredInterpreter | None = None,
) -> StageResult:
    capability_contract = build_default_capability_contract()
    snapshot = normalize_task_snapshot(latest_task_snapshot)
    structured_action_result = _structured_action_stage_result_if_applicable(
        state=state,
        snapshot=snapshot,
        selected_thread_metadata=selected_thread_metadata or {},
    )
    if structured_action_result is not None:
        return structured_action_result
    selected_metadata = dict(selected_thread_metadata or {})
    if structured_interpreter is None:
        return await _interpreter_unavailable_result(
            user=user,
            snapshot=snapshot,
            current_user_message=state.current_user_message,
            selected_thread_metadata=selected_metadata,
        )

    interpretation = await _call_structured_interpreter(
        structured_interpreter,
        InterpretationRequest(
            current_user_message=state.current_user_message,
            recent_thread_history=list(state.recent_thread_history),
            latest_task_snapshot=snapshot,
            selected_thread_metadata=selected_metadata,
            user=user,
        ),
    )
    if interpretation is None:
        return await _interpreter_unavailable_result(
            user=user,
            snapshot=snapshot,
            current_user_message=state.current_user_message,
            selected_thread_metadata=selected_metadata,
        )

    return await _stage_result_from_interpretation(
        state=state,
        user=user,
        snapshot=snapshot,
        interpretation=interpretation,
        capability_contract=capability_contract,
        selected_thread_metadata=selected_metadata,
    )


async def _call_structured_interpreter(
    structured_interpreter: StructuredInterpreter,
    request: InterpretationRequest,
) -> StructuredInterpretation | None:
    async_invoke = getattr(structured_interpreter, "ainvoke", None)
    if async_invoke is not None:
        result = async_invoke(request)
        if inspect.isawaitable(result):
            return await result
        return result
    result = structured_interpreter(request)
    if inspect.isawaitable(result):
        return await result
    return result


async def _stage_result_from_interpretation(
    *,
    state: RunState,
    user: UserState,
    snapshot: TaskSnapshot | None,
    interpretation: StructuredInterpretation,
    capability_contract: Any,
    selected_thread_metadata: dict[str, Any],
) -> StageResult:
    interpretation = _repair_retry_route_when_pending_need_is_active(
        interpretation=interpretation,
        snapshot=snapshot,
        selected_thread_metadata=selected_thread_metadata,
    )
    route_suppression_reason_codes: list[str] = []
    expects_strategy_route = _strategy_route_expected(
        intent=interpretation.intent,
        semantic_turn_act=interpretation.semantic_turn_act,
    ) or _candidate_strategy_has_backtest_shape(
        interpretation.candidate_strategy_draft
    )
    incoming_strategy = _strategy_with_contextual_merge(
        strategy=interpretation.candidate_strategy_draft,
        snapshot=snapshot,
        selected_thread_metadata=selected_thread_metadata,
        semantic_turn_act=interpretation.semantic_turn_act,
        task_relation=interpretation.task_relation,
    )
    incoming_strategy, supported_indicator_simplification_applied = (
        _strategy_with_supported_indicator_simplification(
            strategy=incoming_strategy,
            snapshot=snapshot,
        )
    )
    if supported_indicator_simplification_applied:
        interpretation = interpretation.model_copy(
            update={
                "intent": "strategy_drafting",
                "task_relation": "refine",
                "requires_clarification": False,
                "assistant_response": None,
                "semantic_turn_act": "refine_current_idea",
                "missing_required_fields": [],
                "reason_codes": [
                    *interpretation.reason_codes,
                    "supported_indicator_simplification_applied",
                ],
            }
        )
        expects_strategy_route = True
    incoming_strategy, pending_resolution_applied = (
        _strategy_with_pending_resolution_affirmation(
            strategy=incoming_strategy,
            explicit_strategy=interpretation.candidate_strategy_draft,
            selected_thread_metadata=selected_thread_metadata,
            current_user_message=state.current_user_message,
            semantic_turn_act=interpretation.semantic_turn_act,
        )
    )
    if (
        expects_strategy_route
        and interpretation.semantic_turn_act != "retry_failed_action"
        and not _strategy_has_execution_anchor(incoming_strategy)
        and (
            bool(interpretation.assistant_response)
            or (
                not interpretation.requires_clarification
                and not interpretation.missing_required_fields
            )
        )
    ):
        expects_strategy_route = False
        route_suppression_reason_codes.append("unanchored_strategy_route_suppressed")
        interpretation = interpretation.model_copy(
            update={
                "intent": "conversation_followup",
                "task_relation": "continue",
                "requires_clarification": False,
                "assistant_response": (
                    interpretation.assistant_response
                    or _unanchored_strategy_route_response()
                ),
                "semantic_turn_act": "educational_question",
                "missing_required_fields": [],
            }
        )
    strategy = (
        _strategy_with_execution_defaults(_canonicalized_strategy(incoming_strategy))
        if expects_strategy_route
        else incoming_strategy
    )
    strategy, optional_parameter_values = _route_contextual_money_answer(
        strategy=strategy,
        selected_thread_metadata=selected_thread_metadata,
    )
    integrity_report = (
        conserve_semantic_constraints(
            strategy=strategy,
            selected_thread_metadata=selected_thread_metadata,
            prior_strategy=_active_strategy_from_snapshot(snapshot),
            optional_parameter_values=optional_parameter_values,
            supported_timeframes=_supported_timeframes(capability_contract),
        )
        if expects_strategy_route
        else SemanticIntegrityReport(
            strategy=strategy,
            optional_parameter_values=optional_parameter_values,
        )
    )
    strategy = integrity_report.strategy
    optional_parameter_values = integrity_report.optional_parameter_values
    unsupported_constraints = [
        *interpretation.unsupported_constraints,
        *integrity_report.unsupported_constraints,
    ]
    constraint_filter_reason_codes: list[str] = []
    ambiguity_filter_reason_codes: list[str] = []
    if expects_strategy_route:
        unsupported_constraints, constraint_filter_reason_codes = (
            filter_unsubstantiated_timeframe_constraints(
                constraints=unsupported_constraints,
                strategy=strategy,
                selected_thread_metadata=selected_thread_metadata,
                supported_timeframes=_supported_timeframes(capability_contract),
            )
        )
    ambiguous_fields = list(interpretation.ambiguous_fields)
    if pending_resolution_applied:
        ambiguous_fields = [
            field
            for field in ambiguous_fields
            if _field_base(field.field_name) != "asset_universe"
        ]
    if integrity_report.evidence.normalized_date_range is not None:
        ambiguous_fields = [
            field
            for field in ambiguous_fields
            if _field_base(field.field_name) != "date_range"
        ]
    if expects_strategy_route:
        strategy.resolution_provenance = _dedupe_resolution_provenance(
            [*strategy.resolution_provenance, *state.context_hints]
        )
        ambiguous_fields = _dedupe_ambiguous_fields(
            [
                *ambiguous_fields,
                *_ambiguous_fields_from_resolution(strategy.resolution_provenance),
            ]
        )
        ambiguous_fields, ambiguity_filter_reason_codes = (
            _filter_resolved_strategy_ambiguities(
                strategy=strategy,
                fields=ambiguous_fields,
            )
        )
        unsupported_constraints = _dedupe_unsupported_constraints(
            [
                *unsupported_constraints,
                *detect_unsupported_constraints(
                    strategy=strategy,
                    contract=capability_contract,
                ),
                *_unsupported_symbol_constraints(
                    strategy=strategy,
                    contract=capability_contract,
                ),
                *_unsupported_constraints_from_resolution(
                    strategy.resolution_provenance,
                    contract=capability_contract,
                ),
            ]
        )
        strategy_logic_constraint = _unsupported_strategy_logic_constraint(
            strategy=strategy,
            existing_constraints=unsupported_constraints,
            contract=capability_contract,
        )
        if strategy_logic_constraint is not None:
            unsupported_constraints = _dedupe_unsupported_constraints(
                [*unsupported_constraints, strategy_logic_constraint]
            )
    missing_required_fields = _missing_fields_for_interpretation(
        interpretation=interpretation,
        strategy=strategy,
        contract=capability_contract,
        expects_strategy_route=expects_strategy_route,
    )
    missing_required_fields = list(
        dict.fromkeys(
            [*missing_required_fields, *integrity_report.blocking_missing_fields]
        )
    )
    response_overrides = interpretation.response_profile_overrides
    effective_profile = resolve_effective_response_profile(
        user=user,
        explicit_overrides=response_overrides,
    )
    llm_clarification_blocks = (
        interpretation.requires_clarification
        and not pending_resolution_applied
        and not interpretation.assistant_response
        and not _strategy_is_semantically_confirmable(
            expects_strategy_route=expects_strategy_route,
            ambiguous_fields=ambiguous_fields,
            unsupported_constraints=unsupported_constraints,
            missing_required_fields=missing_required_fields,
        )
    )
    requires_clarification = bool(
        llm_clarification_blocks
        or ambiguous_fields
        or unsupported_constraints
        or missing_required_fields
    )
    decision = InterpretDecision(
        intent=interpretation.intent,
        task_relation=interpretation.task_relation,
        requires_clarification=requires_clarification,
        user_goal_summary=interpretation.user_goal_summary,
        candidate_strategy_draft=strategy,
        missing_required_fields=missing_required_fields,
        optional_parameter_opportunity=list(capability_contract.optional_defaults),
        confidence=interpretation.confidence,
        arbitration_mode="structured_arbitration",
        reason_codes=[
            "llm_interpreter_used",
            *route_suppression_reason_codes,
            *(
                ["pending_resolution_candidate_affirmed"]
                if pending_resolution_applied
                else []
            ),
            *integrity_report.reason_codes,
            *constraint_filter_reason_codes,
            *ambiguity_filter_reason_codes,
            *interpretation.reason_codes,
        ],
        effective_response_profile=effective_profile,
        user_preference_overridden_for_turn=has_response_profile_overrides(
            response_overrides
        ),
        normalized_signals={},
        ambiguous_fields=ambiguous_fields,
        unsupported_constraints=unsupported_constraints,
        resolution_provenance=list(strategy.resolution_provenance),
        semantic_turn_act=interpretation.semantic_turn_act,
        result_followup_focus=interpretation.result_followup_focus,
        capability_question_focus=interpretation.capability_question_focus,
    )
    if interpretation.capability_question_focus is not None:
        decision.normalized_signals["capability_question_focus"] = (
            interpretation.capability_question_focus
        )
    optional_parameter_stage_patch = _optional_parameter_stage_patch(
        decision=decision,
        values=optional_parameter_values,
    )
    approval_result = _approval_stage_result_if_applicable(
        decision=decision,
        snapshot=snapshot,
        state=state,
        selected_thread_metadata=selected_thread_metadata,
        interpretation=interpretation,
    )
    if approval_result is not None:
        return approval_result
    retry_result = _retry_failed_action_stage_result_if_applicable(
        decision=decision,
        snapshot=snapshot,
    )
    if retry_result is not None:
        return retry_result
    pending_artifact_followup_result = (
        _pending_artifact_followup_stage_result_if_applicable(
            decision=decision,
            snapshot=snapshot,
        )
    )
    if pending_artifact_followup_result is not None:
        return pending_artifact_followup_result
    followup_result = await _artifact_followup_stage_result_if_applicable(
        decision=decision,
        snapshot=snapshot,
        current_user_message=state.current_user_message,
    )
    if followup_result is not None:
        return followup_result
    capability_answer = await _capability_answer_if_applicable(
        focus=interpretation.capability_question_focus,
        semantic_turn_act=interpretation.semantic_turn_act,
        expects_strategy_route=expects_strategy_route,
        requires_clarification=requires_clarification,
        assistant_response=interpretation.assistant_response,
        current_user_message=state.current_user_message,
        capability_contract=capability_contract,
    )
    if capability_answer is not None:
        return StageResult(
            outcome="ready_to_respond",
            decision=decision,
            stage_patch={"assistant_response": capability_answer},
        )
    latest_result_recovery = await _latest_result_followup_recovery_if_applicable(
        user=user,
        snapshot=snapshot,
        current_user_message=state.current_user_message,
        decision=decision,
        assistant_response=interpretation.assistant_response,
    )
    if latest_result_recovery is not None:
        return latest_result_recovery
    if (
        interpretation.assistant_response
        and not expects_strategy_route
        and not requires_clarification
    ):
        return StageResult(
            outcome="ready_to_respond",
            decision=decision,
            stage_patch={"assistant_response": interpretation.assistant_response},
        )
    if requires_clarification:
        stage_patch = dict(optional_parameter_stage_patch)
        if interpretation.assistant_response:
            stage_patch["assistant_response"] = interpretation.assistant_response
        return StageResult(
            outcome="needs_clarification",
            decision=decision,
            stage_patch=stage_patch,
        )
    if expects_strategy_route:
        return StageResult(
            outcome="ready_for_confirmation",
            decision=decision,
            stage_patch=optional_parameter_stage_patch,
        )
    return StageResult(
        outcome="ready_to_respond",
        decision=decision,
        stage_patch=(
            {
                **optional_parameter_stage_patch,
                "assistant_response": interpretation.assistant_response,
            }
            if interpretation.assistant_response
            else optional_parameter_stage_patch
        ),
    )


def _repair_retry_route_when_pending_need_is_active(
    *,
    interpretation: StructuredInterpretation,
    snapshot: TaskSnapshot | None,
    selected_thread_metadata: dict[str, Any],
) -> StructuredInterpretation:
    if interpretation.semantic_turn_act != "retry_failed_action":
        return interpretation
    if snapshot is None or snapshot.pending_strategy_summary is None:
        return interpretation
    if snapshot.latest_failed_action_reference is not None:
        return interpretation
    requested_field = _field_base(str(selected_thread_metadata.get("requested_field") or ""))
    prior_outcome = str(selected_thread_metadata.get("last_stage_outcome") or "")
    if not requested_field and prior_outcome != "await_user_reply":
        return interpretation
    return interpretation.model_copy(
        update={
            "intent": "backtest_execution",
            "task_relation": "continue",
            "requires_clarification": False,
            "assistant_response": None,
            "semantic_turn_act": "answer_pending_need",
            "reason_codes": [
                *interpretation.reason_codes,
                "retry_route_repaired_to_pending_need",
            ],
        }
    )


async def _capability_answer_if_applicable(
    *,
    focus: CapabilityQuestionFocus | None,
    semantic_turn_act: SemanticTurnAct | None,
    expects_strategy_route: bool,
    requires_clarification: bool,
    assistant_response: str | None,
    current_user_message: str,
    capability_contract: Any,
) -> str | None:
    if (
        focus is None
        or semantic_turn_act != "educational_question"
        or expects_strategy_route
        or requires_clarification
    ):
        return None
    if focus == "supported_strategies" and assistant_response:
        return None
    if focus == "supported_strategies":
        composed = await _compose_supported_strategy_capability_answer(
            current_user_message=current_user_message,
            capability_contract=capability_contract,
        )
        if composed:
            return composed
    return compose_capability_answer(focus=focus, contract=capability_contract)


async def _compose_supported_strategy_capability_answer(
    *,
    current_user_message: str,
    capability_contract: Any,
) -> str | None:
    fact_packet = compose_capability_answer(
        focus="supported_strategies",
        contract=capability_contract,
    )
    messages = [
        {
            "role": "system",
            "content": (
                "You are Argus, a chat-first investing experimentation assistant. "
                "Answer in warm, plain English. Keep it concise and useful for a "
                "normal person. Use the supported-strategy facts as hard bounds. "
                "Do not invent unsupported strategy families, predictions, or "
                "investment advice. If the user asks about a concept such as dollar "
                "cost averaging, explain it simply and connect it to the closest "
                "runnable Argus experiment."
            ),
        },
        {
            "role": "system",
            "content": f"Supported-strategy facts: {fact_packet}",
        },
        {"role": "user", "content": current_user_message},
    ]
    try:
        return await invoke_openrouter_chat_completion(
            task="chat_composer",
            messages=messages,
        )
    except Exception:
        return None


def _route_contextual_money_answer(
    *,
    strategy: StrategySummary,
    selected_thread_metadata: dict[str, Any],
) -> tuple[StrategySummary, dict[str, Any]]:
    requested_field = str(selected_thread_metadata.get("requested_field") or "")
    if requested_field not in {"initial_capital", "capital_amount", "assumption"}:
        return strategy, {}
    if strategy.capital_amount is None:
        return strategy, {}
    if executable_strategy_type(strategy) == "dca_accumulation":
        return strategy, {}
    updated = strategy.model_copy(deep=True)
    initial_capital = updated.capital_amount
    updated.capital_amount = None
    return updated, {"initial_capital": initial_capital}


def _strategy_with_pending_resolution_affirmation(
    *,
    strategy: StrategySummary,
    explicit_strategy: StrategySummary,
    selected_thread_metadata: dict[str, Any],
    current_user_message: str,
    semantic_turn_act: str | None,
) -> tuple[StrategySummary, bool]:
    if semantic_turn_act != "answer_pending_need":
        return strategy, False
    pending_resolution = selected_thread_metadata.get("pending_resolution")
    if not isinstance(pending_resolution, dict):
        return strategy, False
    field = _field_base(str(pending_resolution.get("field") or ""))
    if field != "asset_universe":
        return strategy, False
    if explicit_strategy.asset_universe:
        return strategy, False
    del current_user_message
    candidate = pending_resolution.get(
        "candidate_normalized_value"
    ) or pending_resolution.get("canonical_symbol")
    if not isinstance(candidate, str) or not candidate.strip():
        return strategy, False
    updated = strategy.model_copy(deep=True)
    updated.asset_universe = [candidate.strip().upper()]
    asset_class = pending_resolution.get("asset_class")
    if isinstance(asset_class, str) and asset_class.strip():
        updated.asset_class = asset_class.strip()
    updated.resolution_provenance = [
        item
        for item in updated.resolution_provenance
        if not _is_ambiguous_asset_resolution(item)
    ]
    return updated, True


def _strategy_with_supported_indicator_simplification(
    *,
    strategy: StrategySummary,
    snapshot: TaskSnapshot | None,
) -> tuple[StrategySummary, bool]:
    indicator_key = _indicator_key_from_strategy(strategy)
    if indicator_key is None:
        return strategy, False

    prior = _active_strategy_from_snapshot(snapshot)
    if prior is None and not _strategy_has_content(strategy):
        return strategy, False
    base = (
        prior.model_copy(deep=True)
        if prior is not None
        else strategy.model_copy(deep=True)
    )
    spec = executable_indicator_spec(indicator_key)
    if spec is None or not _indicator_supports_default_threshold_rule(spec):
        return strategy, False

    updated = _merge_non_empty_strategy_fields(
        base=base,
        incoming=strategy,
        field_names=(
            "asset_universe",
            "asset_class",
            "date_range",
            "timeframe",
            "capital_amount",
            "position_size",
            "comparison_baseline",
            "entry_logic",
            "exit_logic",
            "extra_parameters",
        ),
    )
    prior_strategy_type = executable_strategy_type(base)
    incoming_indicator_parameters = _indicator_parameters_from_strategy(strategy)
    parameters = normalize_indicator_parameters(
        spec.key,
        {
            **_indicator_parameters_from_strategy(updated),
            **incoming_indicator_parameters,
            "indicator": spec.key,
        },
    )
    updated.raw_user_phrasing = strategy.raw_user_phrasing or updated.raw_user_phrasing
    updated.strategy_type = "indicator_threshold"
    updated.entry_rule = None
    updated.exit_rule = None
    updated.strategy_thesis = _indicator_simplification_thesis(
        strategy=updated,
        spec=spec,
    )
    rewrite_threshold_logic = (
        prior_strategy_type != "indicator_threshold" or bool(incoming_indicator_parameters)
    )
    if rewrite_threshold_logic or not updated.entry_logic:
        updated.entry_logic = spec.format_threshold_rule(
            "entry",
            threshold=float(parameters["entry_threshold"]),
            period=int(parameters["indicator_period"]),
        )
    if rewrite_threshold_logic or not updated.exit_logic:
        updated.exit_logic = spec.format_threshold_rule(
            "exit",
            threshold=float(parameters["exit_threshold"]),
            period=int(parameters["indicator_period"]),
        )
    updated.extra_parameters = {
        **{
            key: value
            for key, value in updated.extra_parameters.items()
            if key not in {"entry_rule", "exit_rule"}
        },
        "indicator": spec.key,
        "indicator_parameters": parameters,
        "simplified_from_strategy_type": (
            prior.strategy_type if prior is not None else strategy.strategy_type
        ),
    }
    return updated, True


def _indicator_key_from_strategy(strategy: StrategySummary) -> str | None:
    indicator_parameters = canonical_indicator_parameters_from_strategy(strategy)
    parameter_indicator = indicator_parameters.get("indicator")
    if isinstance(parameter_indicator, str) and parameter_indicator.strip():
        return parameter_indicator.strip()
    raw_indicator = strategy.extra_parameters.get("indicator")
    if isinstance(raw_indicator, str) and raw_indicator.strip():
        return raw_indicator.strip()
    raw_parameters = strategy.extra_parameters.get("indicator_parameters")
    if isinstance(raw_parameters, dict):
        parameter_indicator = raw_parameters.get("indicator")
        if isinstance(parameter_indicator, str) and parameter_indicator.strip():
            return parameter_indicator.strip()
    return None


def _active_strategy_from_snapshot(snapshot: TaskSnapshot | None) -> StrategySummary | None:
    if snapshot is None:
        return None
    return snapshot.pending_strategy_summary or snapshot.confirmed_strategy_summary


def _strategy_has_content(strategy: StrategySummary) -> bool:
    return any(
        value not in (None, "", [], {})
        for value in strategy.model_dump(mode="python").values()
    )


def _indicator_supports_default_threshold_rule(
    spec: IndicatorExecutionSpec,
) -> bool:
    return spec.default_entry_threshold != spec.default_exit_threshold and any(
        parameter.key == "entry_threshold" for parameter in spec.parameter_schema
    )


def _indicator_parameters_from_strategy(strategy: StrategySummary) -> dict[str, Any]:
    return canonical_indicator_parameters_from_strategy(strategy)


def _merge_non_empty_strategy_fields(
    *,
    base: StrategySummary,
    incoming: StrategySummary,
    field_names: tuple[str, ...],
) -> StrategySummary:
    updated = base.model_copy(deep=True)
    incoming_payload = incoming.model_dump(mode="python")
    for field_name in field_names:
        value = incoming_payload.get(field_name)
        if value in (None, "", [], {}):
            continue
        setattr(updated, field_name, value)
    return updated


def _indicator_simplification_thesis(
    *,
    strategy: StrategySummary,
    spec: IndicatorExecutionSpec,
) -> str:
    assets = ", ".join(strategy.asset_universe)
    if assets:
        return f"Test {assets} with a supported {spec.label} threshold rule."
    return f"Test the current draft with a supported {spec.label} threshold rule."


def _is_ambiguous_asset_resolution(item: ResolutionProvenance | dict[str, Any]) -> bool:
    if not isinstance(item, ResolutionProvenance):
        try:
            item = ResolutionProvenance.model_validate(item)
        except (TypeError, ValueError):
            return False
    return (
        item.source == "llm_extraction"
        and item.resolution_status == "ambiguous"
        and _field_base(item.field) == "asset_universe"
    )


def _field_base(field_name: str) -> str:
    return field_name.split("[", 1)[0]


def _supported_timeframes(contract: Any) -> tuple[str, ...]:
    parameter = contract.get_optional_parameter("timeframe")
    if parameter is None or parameter.allowed_range is None:
        return ()
    return tuple(str(value) for value in parameter.allowed_range.allowed_values)


def _optional_parameter_stage_patch(
    *,
    decision: InterpretDecision,
    values: dict[str, Any],
) -> dict[str, Any]:
    if not values:
        return {}
    optional_parameter_status = dict(decision.to_patch()["optional_parameter_status"])
    optional_parameter_status.update(values)
    return {"optional_parameter_status": optional_parameter_status}


def _offline_interpreter_unavailable_result(
    *,
    user: UserState,
    snapshot: TaskSnapshot | None = None,
    current_user_message: str = "",
    selected_thread_metadata: dict[str, Any] | None = None,
) -> StageResult:
    effective_profile = resolve_effective_response_profile(
        user=user,
        explicit_overrides=None,
    )
    decision = InterpretDecision(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="The LLM interpreter was unavailable for this turn.",
        candidate_strategy_draft=StrategySummary(),
        missing_required_fields=[],
        optional_parameter_opportunity=[],
        confidence=0.0,
        arbitration_mode="deterministic",
        reason_codes=["llm_interpreter_unavailable"],
        effective_response_profile=effective_profile,
        semantic_turn_act=None,
    )
    return StageResult(
        outcome="ready_to_respond",
        decision=decision,
        stage_patch={
            "assistant_response": _offline_recovery_message(
                snapshot,
                current_user_message=current_user_message,
                selected_thread_metadata=selected_thread_metadata or {},
            ),
        },
    )


async def _interpreter_unavailable_result(
    *,
    user: UserState,
    snapshot: TaskSnapshot | None = None,
    current_user_message: str = "",
    selected_thread_metadata: dict[str, Any] | None = None,
) -> StageResult:
    result_followup = await _latest_result_followup_when_interpreter_unavailable(
        user=user,
        snapshot=snapshot,
        current_user_message=current_user_message,
    )
    if result_followup is not None:
        return result_followup
    return _offline_interpreter_unavailable_result(
        user=user,
        snapshot=snapshot,
        current_user_message=current_user_message,
        selected_thread_metadata=selected_thread_metadata or {},
    )


async def _latest_result_followup_when_interpreter_unavailable(
    *,
    user: UserState,
    snapshot: TaskSnapshot | None,
    current_user_message: str,
) -> StageResult | None:
    if snapshot is None or snapshot.latest_backtest_result_reference is None:
        return None
    if not current_user_message.strip():
        return None
    reference = snapshot.latest_backtest_result_reference
    metadata = dict(reference.metadata)
    response = await compose_result_followup_response(
        metadata=metadata,
        focus="general",
        user_message=current_user_message,
    )
    if response is None:
        response = fallback_result_followup_response(
            metadata=metadata,
            focus="general",
        )
    if response is None:
        return None
    effective_profile = resolve_effective_response_profile(
        user=user,
        explicit_overrides=None,
    )
    decision = InterpretDecision(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary=(
            "The LLM interpreter was unavailable; answered from the latest "
            "result artifact facts."
        ),
        candidate_strategy_draft=StrategySummary(),
        missing_required_fields=[],
        optional_parameter_opportunity=[],
        confidence=0.0,
        arbitration_mode="deterministic",
        reason_codes=[
            "llm_interpreter_unavailable",
            "latest_result_fact_bank_recovery",
        ],
        effective_response_profile=effective_profile,
        semantic_turn_act="result_followup",
        result_followup_focus="general",
    )
    return StageResult(
        outcome="ready_to_respond",
        decision=decision,
        stage_patch={
            "assistant_response": with_response_heading(
                heading=result_followup_heading("general"),
                body=response,
            )
        },
    )


async def _latest_result_followup_recovery_if_applicable(
    *,
    user: UserState,
    snapshot: TaskSnapshot | None,
    current_user_message: str,
    decision: InterpretDecision,
    assistant_response: str | None,
) -> StageResult | None:
    unanchored_strategy_route = (
        "unanchored_strategy_route_suppressed" in decision.reason_codes
    )
    if assistant_response and not unanchored_strategy_route:
        return None
    if _candidate_strategy_has_backtest_shape(decision.candidate_strategy_draft):
        return None
    if snapshot is None or snapshot.latest_backtest_result_reference is None:
        return None
    if not current_user_message.strip():
        return None
    reference = snapshot.latest_backtest_result_reference
    metadata = dict(reference.metadata)
    focus = decision.result_followup_focus or "general"
    response = await compose_result_followup_response(
        metadata=metadata,
        focus=focus,
        user_message=current_user_message,
    )
    if response is None:
        response = fallback_result_followup_response(
            metadata=metadata,
            focus=focus,
        )
    if response is None:
        return None
    effective_profile = resolve_effective_response_profile(
        user=user,
        explicit_overrides=None,
    )
    return StageResult(
        outcome="ready_to_respond",
        decision=decision.model_copy(
            update={
                "intent": "conversation_followup",
                "requires_clarification": False,
                "missing_required_fields": [],
                "effective_response_profile": effective_profile,
                "semantic_turn_act": "result_followup",
                "result_followup_focus": focus,
                "reason_codes": [
                    *decision.reason_codes,
                    (
                        "latest_result_unanchored_turn_recovery"
                        if unanchored_strategy_route
                        else "latest_result_empty_turn_recovery"
                    ),
                ],
            }
        ),
        stage_patch={
            "assistant_response": with_response_heading(
                heading=result_followup_heading(focus),
                body=response,
            )
        },
    )


def _offline_recovery_message(
    snapshot: TaskSnapshot | None,
    *,
    current_user_message: str = "",
    selected_thread_metadata: dict[str, Any] | None = None,
) -> str:
    if snapshot is not None and snapshot.pending_strategy_summary is not None:
        strategy = snapshot.pending_strategy_summary
        assets = ", ".join(strategy.asset_universe) or "the current asset"
        strategy_label = (strategy.strategy_type or "strategy").replace("_", " ")
        if _pending_assumption_edit_was_not_applied(
            current_user_message=current_user_message,
            selected_thread_metadata=selected_thread_metadata or {},
        ):
            return (
                f"I still have the {assets} {strategy_label} draft in this chat, "
                "but I could not safely apply that assumption change, so I left "
                "the visible draft unchanged. Please retry the change in a moment."
            )
        if snapshot.active_confirmation_reference is None:
            return (
                f"I still have the {assets} {strategy_label} draft in this chat, "
                "but the interpreter was unavailable before I could safely apply that "
                "change. Please retry in a moment."
            )
        assumptions_response = _draft_assumptions_response(snapshot)
        action_guidance = (
            "The visible confirmation is still ready. Use the card to start the "
            "simulation, or use the card controls to change it."
        )
        if assumptions_response is not None:
            return f"{assumptions_response} {action_guidance}"
        return (
            f"I still have the {assets} {strategy_label} draft in this chat, "
            "but the interpreter was unavailable before I could safely apply that "
            f"change. {action_guidance}"
        )
    if snapshot is not None and snapshot.latest_backtest_result_reference is not None:
        return (
            "I still have the latest result in this chat, but the interpreter was "
            "unavailable before I could safely answer that follow-up. Please retry in "
            "a moment."
        )
    return (
        "I saved your message, but the interpreter was unavailable before I could "
        "turn it into a reliable draft. Please retry in a moment."
    )


def _pending_assumption_edit_was_not_applied(
    *,
    current_user_message: str,
    selected_thread_metadata: dict[str, Any],
) -> bool:
    requested_field = _field_base(str(selected_thread_metadata.get("requested_field") or ""))
    return requested_field == "assumption" and bool(current_user_message.strip())


def _strategy_with_contextual_merge(
    *,
    strategy: StrategySummary,
    snapshot: TaskSnapshot | None,
    selected_thread_metadata: dict[str, Any],
    semantic_turn_act: str | None,
    task_relation: str,
) -> StrategySummary:
    if snapshot is None:
        return strategy
    prior = snapshot.pending_strategy_summary or snapshot.confirmed_strategy_summary
    if prior is None:
        return strategy
    should_merge = (
        semantic_turn_act in CONTEXTUAL_EDIT_TURN_ACTS
        or task_relation == "refine"
        or _strategy_supplies_contextual_rule_edit(prior=prior, strategy=strategy)
        or _strategy_fills_pending_execution_context(
            prior=prior,
            strategy=strategy,
            selected_thread_metadata=selected_thread_metadata,
        )
        or _strategy_looks_like_pending_artifact_edit(
            prior=prior,
            strategy=strategy,
            selected_thread_metadata=selected_thread_metadata,
        )
    )
    if not should_merge:
        return strategy
    incoming_strategy_family = _declared_strategy_family(strategy)
    prior_strategy_family = executable_strategy_type(prior)
    strategy_family_changed = (
        incoming_strategy_family in SUPPORTED_STRATEGY_TYPES
        and prior_strategy_family in SUPPORTED_STRATEGY_TYPES
        and incoming_strategy_family != prior_strategy_family
    )
    preserve_prior_family = _should_preserve_pending_strategy_family(
        prior=prior,
        strategy=strategy,
        incoming_strategy_family=incoming_strategy_family,
        prior_strategy_family=prior_strategy_family,
        selected_thread_metadata=selected_thread_metadata,
        semantic_turn_act=semantic_turn_act,
        task_relation=task_relation,
    )
    if preserve_prior_family:
        strategy_family_changed = False
        incoming_strategy_family = prior_strategy_family
    merged = (
        _reset_contextual_strategy_definition(
            prior,
            incoming_strategy_family,
        )
        if strategy_family_changed and incoming_strategy_family is not None
        else prior.model_copy(deep=True)
    )
    incoming = strategy.model_dump(mode="python")
    for key, value in incoming.items():
        if key == "raw_user_phrasing":
            continue
        if key == "strategy_thesis" and not strategy_family_changed:
            continue
        if key == "strategy_type" and preserve_prior_family:
            continue
        if value in (None, "", [], {}):
            continue
        if key == "extra_parameters":
            if preserve_prior_family and isinstance(value, dict):
                value = {
                    nested_key: nested_value
                    for nested_key, nested_value in value.items()
                    if nested_key not in {"raw_strategy_type", "template"}
                }
            merged.extra_parameters = _merge_contextual_extra_parameters(
                base=merged.extra_parameters,
                incoming=value if isinstance(value, dict) else {},
            )
            continue
        setattr(merged, key, value)
    if strategy_family_changed and incoming_strategy_family is not None:
        merged.strategy_type = incoming_strategy_family
    if strategy.raw_user_phrasing:
        merged.raw_user_phrasing = strategy.raw_user_phrasing
    declared_family = _declared_strategy_family(merged)
    if declared_family in SUPPORTED_STRATEGY_TYPES:
        _clear_incompatible_strategy_rule_state(merged, declared_family)
    return merged


def _should_preserve_pending_strategy_family(
    *,
    prior: StrategySummary,
    strategy: StrategySummary,
    incoming_strategy_family: str | None,
    prior_strategy_family: str,
    selected_thread_metadata: dict[str, Any],
    semantic_turn_act: str | None,
    task_relation: str,
) -> bool:
    # The LLM may label a pending-field answer as "refine"; the narrower
    # semantic turn act and selected artifact context decide whether family
    # changes are allowed.
    del task_relation
    if semantic_turn_act not in {"answer_pending_need", "new_idea"}:
        return False
    requested_field = _field_base(
        str(selected_thread_metadata.get("requested_field") or "")
    )
    if requested_field in {"refinement", "entry_logic", "exit_logic"}:
        return False
    if not _strategy_fills_pending_execution_context(
        prior=prior,
        strategy=strategy,
        selected_thread_metadata=selected_thread_metadata,
    ):
        return False
    if (
        incoming_strategy_family not in SUPPORTED_STRATEGY_TYPES
        or prior_strategy_family not in SUPPORTED_STRATEGY_TYPES
        or incoming_strategy_family == prior_strategy_family
    ):
        return False
    if incoming_strategy_family not in {"buy_and_hold", "dca_accumulation"}:
        return False
    if not _strategy_supplies_executable_rule_edit(prior):
        return False
    if _strategy_supplies_executable_rule_edit(strategy):
        return False
    return True


def _strategy_fills_pending_execution_context(
    *,
    prior: StrategySummary,
    strategy: StrategySummary,
    selected_thread_metadata: dict[str, Any],
) -> bool:
    requested_field = _field_base(
        str(selected_thread_metadata.get("requested_field") or "")
    )
    context_fields = {
        "asset_universe",
        "date_range",
        "timeframe",
        "capital_amount",
        "initial_capital",
        "position_size",
        "assumption",
    }
    if requested_field in context_fields:
        return _strategy_supplies_execution_context(strategy)
    return (
        selected_thread_metadata.get("last_stage_outcome") == "await_user_reply"
        and (
            (not prior.asset_universe and bool(strategy.asset_universe))
            or (prior.date_range in (None, "") and bool(strategy.date_range))
            or (prior.timeframe in (None, "") and bool(strategy.timeframe))
            or (prior.capital_amount is None and strategy.capital_amount is not None)
            or (prior.position_size is None and strategy.position_size is not None)
        )
    )


def _strategy_supplies_execution_context(strategy: StrategySummary) -> bool:
    return bool(
        strategy.asset_universe
        or strategy.date_range
        or strategy.timeframe
        or strategy.capital_amount is not None
        or strategy.position_size is not None
    )


def _merge_contextual_extra_parameters(
    *,
    base: dict[str, Any],
    incoming: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(base or {})
    for key, value in incoming.items():
        if value in (None, "", [], {}):
            continue
        if (
            key == "indicator_parameters"
            and isinstance(value, dict)
            and isinstance(merged.get(key), dict)
        ):
            nested = dict(merged[key])
            for nested_key, nested_value in value.items():
                if nested_value in (None, "", [], {}):
                    continue
                nested[nested_key] = nested_value
            merged[key] = nested
            continue
        merged[key] = value
    return merged


def _declared_strategy_family(strategy: StrategySummary) -> str | None:
    """Return the family the LLM explicitly declared, ignoring derived rule state."""

    raw_candidates: list[Any] = [strategy.strategy_type]
    extra_parameters = dict(strategy.extra_parameters or {})
    raw_candidates.extend(
        [
            extra_parameters.get("raw_strategy_type"),
            extra_parameters.get("template"),
        ]
    )
    for raw_candidate in raw_candidates:
        candidate = canonical_strategy_type(raw_candidate)
        if candidate in SUPPORTED_STRATEGY_TYPES:
            return candidate
    if _indicator_key_from_strategy(strategy) is not None:
        return "indicator_threshold"
    return None


def _reset_contextual_strategy_definition(
    prior: StrategySummary,
    incoming_strategy_family: str,
) -> StrategySummary:
    """Preserve context fields while clearing incompatible strategy-rule state."""

    updated = prior.model_copy(deep=True)
    updated.strategy_type = incoming_strategy_family
    updated.strategy_thesis = None
    _clear_incompatible_strategy_rule_state(updated, incoming_strategy_family)
    return updated


def _clear_incompatible_strategy_rule_state(
    strategy: StrategySummary,
    strategy_family: str,
) -> None:
    """Keep one declared strategy family from carrying another family's rules."""

    if strategy_family in {"buy_and_hold", "dca_accumulation"}:
        strategy.entry_logic = None
        strategy.exit_logic = None
    if strategy_family != "signal_strategy":
        strategy.entry_rule = None
        strategy.exit_rule = None
        strategy.rule_spec = None
    if strategy_family != "dca_accumulation":
        strategy.cadence = None
    strategy.extra_parameters = _extra_parameters_for_strategy_family(
        strategy.extra_parameters,
        strategy_family,
    )


def _extra_parameters_for_strategy_family(
    extra_parameters: dict[str, Any],
    strategy_family: str,
) -> dict[str, Any]:
    incompatible_keys = {"entry_rule", "exit_rule", "rule_spec"}
    if strategy_family != "indicator_threshold":
        incompatible_keys.update({"indicator", "indicator_parameters"})
    if strategy_family != "dca_accumulation":
        incompatible_keys.update(
            {
                "cadence",
                "recurring_contribution",
                "contribution_amount",
                "periodic_contribution",
                "dca_contribution",
            }
        )
    return {
        key: value
        for key, value in extra_parameters.items()
        if key not in incompatible_keys
    }


def _strategy_looks_like_pending_artifact_edit(
    *,
    prior: StrategySummary,
    strategy: StrategySummary,
    selected_thread_metadata: dict[str, Any],
) -> bool:
    requested_field = _field_base(
        str(selected_thread_metadata.get("requested_field") or "")
    )
    if not requested_field:
        return False
    if requested_field == "date_range":
        return bool(strategy.date_range)
    if requested_field == "asset_universe":
        return bool(strategy.asset_universe)
    if requested_field in {"entry_logic", "exit_logic"}:
        return _strategy_supplies_executable_rule_edit(strategy)
    if requested_field == "refinement":
        return _strategy_has_execution_anchor(strategy) and bool(
            prior.asset_universe or prior.date_range
        )
    return False


def _strategy_supplies_contextual_rule_edit(
    *,
    prior: StrategySummary,
    strategy: StrategySummary,
) -> bool:
    if not _strategy_supplies_executable_rule_edit(strategy):
        return False
    return bool(
        prior.asset_universe
        or prior.date_range
        or prior.asset_class
        or prior.capital_amount is not None
        or prior.position_size is not None
    )


def _strategy_supplies_executable_rule_edit(strategy: StrategySummary) -> bool:
    return bool(
        strategy_rule(strategy, "entry")
        or strategy_rule(strategy, "exit")
        or _valid_rule_spec_from_strategy(strategy)
        or canonical_indicator_parameters_from_strategy(strategy)
    )


def _canonicalized_strategy(strategy: StrategySummary) -> StrategySummary:
    updated = strategy.model_copy(deep=True)
    canonical_symbols: list[str] = []
    asset_classes: set[str] = set()
    invalid_symbols: list[str] = []
    provenance: list[ResolutionProvenance] = []

    for index, symbol in enumerate(updated.asset_universe):
        resolution = _resolve_asset_candidate(
            symbol,
            field=f"asset_universe[{index}]",
            source="llm_extraction",
        )
        provenance.append(resolution.provenance)
        if resolution.status != "resolved" or resolution.asset is None:
            if resolution.status in {"unsupported", "unavailable_for_requested_run"}:
                invalid_symbols.append(symbol)
            continue
        canonical_symbols.append(resolution.asset.canonical_symbol)
        asset_classes.add(resolution.asset.asset_class)

    if canonical_symbols:
        updated.asset_universe = list(dict.fromkeys(canonical_symbols))
    if len(asset_classes) == 1:
        updated.asset_class = next(iter(asset_classes))
    elif len(asset_classes) > 1:
        updated.asset_class = "mixed"
    if invalid_symbols:
        updated.extra_parameters = {
            **updated.extra_parameters,
            "invalid_symbols": invalid_symbols,
        }
    updated.resolution_provenance = _dedupe_resolution_provenance(
        [*updated.resolution_provenance, *provenance]
    )
    return updated


def _strategy_with_execution_defaults(strategy: StrategySummary) -> StrategySummary:
    strategy_type = executable_strategy_type(strategy)
    updated = strategy.model_copy(deep=True)
    if strategy_type == "signal_strategy":
        updated.strategy_type = "signal_strategy"
        entry_rule = strategy_rule(updated, "entry")
        if entry_rule is not None:
            updated.entry_rule = entry_rule
            updated.exit_rule = strategy_rule(
                updated, "exit"
            ) or opposite_moving_average_crossover_rule(entry_rule)
            updated.extra_parameters = {
                **updated.extra_parameters,
                "entry_rule": updated.entry_rule,
                "exit_rule": updated.exit_rule,
            }
            if not updated.entry_logic:
                updated.entry_logic = moving_average_crossover_text(updated.entry_rule)
            if not updated.exit_logic:
                updated.exit_logic = moving_average_crossover_text(updated.exit_rule)
    return updated


def _resolve_asset_candidate(
    query: str,
    *,
    field: str,
    source: ResolutionSource,
) -> AssetResolution:
    if resolve_asset is _DEFAULT_RESOLVE_ASSET:
        return runtime_resolve_asset_candidate(query, field=field, source=source)
    resolved = resolve_asset(query)
    provenance = ResolutionProvenance(
        field=field,
        raw_text=query,
        source=source,
        candidate_kind="asset",
        resolution_status="resolved",
        canonical_symbol=resolved.canonical_symbol,
        asset_class=resolved.asset_class,
        validated_by="provider_catalog",
        confidence="high",
    )
    return AssetResolution(
        status="resolved",
        raw_text=query,
        asset=resolved,
        candidates=(resolved,),
        provenance=provenance,
    )


def _unsupported_symbol_constraints(
    *,
    strategy: StrategySummary,
    contract: Any,
) -> list[UnsupportedConstraint]:
    invalid_symbols = strategy.extra_parameters.get("invalid_symbols", [])
    if not invalid_symbols:
        return []
    return [
        UnsupportedConstraint(
            category="unsupported_symbol",
            raw_value=", ".join(str(symbol) for symbol in invalid_symbols),
            explanation=(
                "I understood the asset reference, but I could not verify it in "
                "the supported market data universe for this run."
            ),
            simplification_options=contract.get_simplification_options(
                "unsupported_symbol"
            ),
        )
    ]


def _unsupported_strategy_logic_constraint(
    *,
    strategy: StrategySummary,
    existing_constraints: list[UnsupportedConstraint],
    contract: Any,
) -> UnsupportedConstraint | None:
    if existing_constraints:
        return None
    if executable_strategy_type(strategy) in SUPPORTED_STRATEGY_TYPES:
        return None
    if _strategy_supplies_executable_rule_edit(strategy):
        return None
    if not _strategy_has_unstructured_strategy_thesis(strategy):
        return None
    raw_value = _unstructured_strategy_raw_value(strategy)
    return UnsupportedConstraint(
        category="unsupported_strategy_logic",
        raw_value=raw_value,
        explanation=(
            "That idea needs a rule or data source the current backtest engine "
            "cannot execute directly yet."
        ),
        simplification_options=contract.get_simplification_options(
            "unsupported_strategy_logic"
        ),
    )


def _strategy_has_unstructured_strategy_thesis(strategy: StrategySummary) -> bool:
    return bool(
        str(strategy.strategy_thesis or "").strip()
        or str(strategy.raw_user_phrasing or "").strip()
    )


def _unstructured_strategy_raw_value(strategy: StrategySummary) -> str:
    for value in (
        strategy.entry_logic,
        strategy.strategy_thesis,
        strategy.raw_user_phrasing,
        strategy.strategy_type,
    ):
        text = str(value or "").strip()
        if text:
            return text
    return "unsupported strategy logic"


def _ambiguous_fields_from_resolution(
    provenance: list[ResolutionProvenance],
) -> list[AmbiguousField]:
    return [
        AmbiguousField(
            field_name=item.field,
            raw_value=item.raw_text,
            candidate_normalized_value=item.canonical_symbol,
            reason_code=f"{item.candidate_kind}_resolution_ambiguous",
        )
        for item in provenance
        if item.source == "llm_extraction" and item.resolution_status == "ambiguous"
    ]


def _filter_resolved_strategy_ambiguities(
    *,
    strategy: StrategySummary,
    fields: list[AmbiguousField],
) -> tuple[list[AmbiguousField], list[str]]:
    filtered: list[AmbiguousField] = []
    suppressed = False
    for field in fields:
        field_name = _field_base(field.field_name)
        if _strategy_field_is_executable(strategy=strategy, field_name=field_name):
            suppressed = True
            continue
        filtered.append(field)
    reason_codes = ["resolved_strategy_ambiguity_suppressed"] if suppressed else []
    return filtered, reason_codes


def _strategy_field_is_executable(
    *,
    strategy: StrategySummary,
    field_name: str,
) -> bool:
    if field_name == "entry_logic":
        return bool(
            strategy_rule(strategy, "entry")
            or _valid_rule_spec_from_strategy(strategy)
            or canonical_indicator_parameters_from_strategy(strategy)
        )
    if field_name == "exit_logic":
        return bool(
            strategy_rule(strategy, "exit")
            or _valid_rule_spec_from_strategy(strategy)
            or canonical_indicator_parameters_from_strategy(strategy)
        )
    if field_name in {"entry_rule", "exit_rule", "rule_spec"}:
        return bool(
            strategy_rule(strategy, "entry")
            or strategy_rule(strategy, "exit")
            or _valid_rule_spec_from_strategy(strategy)
        )
    return False


def _unsupported_constraints_from_resolution(
    provenance: list[ResolutionProvenance],
    *,
    contract: Any,
) -> list[UnsupportedConstraint]:
    constraints: list[UnsupportedConstraint] = []
    for item in provenance:
        if (
            item.resolution_status
            not in {
                "unsupported",
                "unavailable_for_requested_run",
            }
            or item.source != "llm_extraction"
        ):
            continue
        category = (
            "unavailable_for_requested_run"
            if item.resolution_status == "unavailable_for_requested_run"
            else f"unsupported_{item.candidate_kind}"
        )
        if item.resolution_status == "unavailable_for_requested_run":
            explanation = (
                "I found the instrument, but the requested date range or timeframe "
                "is not available for a supported run."
            )
        else:
            explanation = (
                "I understood the asset reference, but Argus Alpha cannot execute it "
                "as requested yet."
                if item.candidate_kind == "asset"
                else "I understand that indicator, but Argus Alpha cannot execute it yet."
            )
        constraints.append(
            UnsupportedConstraint(
                category=category,
                raw_value=item.raw_text,
                explanation=explanation,
                simplification_options=contract.get_simplification_options(category),
            )
        )
    return constraints


def _missing_fields_for_interpretation(
    *,
    interpretation: StructuredInterpretation,
    strategy: StrategySummary,
    contract: Any,
    expects_strategy_route: bool | None = None,
) -> list[str]:
    route_expected = (
        expects_strategy_route
        if expects_strategy_route is not None
        else _strategy_route_expected(
            intent=interpretation.intent,
            semantic_turn_act=interpretation.semantic_turn_act,
        )
    )
    if not route_expected:
        return []
    required_missing_fields = missing_required_fields_for_strategy(
        strategy,
        contract=contract,
    )
    if executable_strategy_type(strategy) not in SUPPORTED_STRATEGY_TYPES:
        required_missing_fields = list(
            dict.fromkeys(["entry_logic", *required_missing_fields])
        )
    allowed_missing_fields = set(required_missing_fields)
    missing = [
        field
        for field in interpretation.missing_required_fields
        if isinstance(field, str) and field and field in allowed_missing_fields
    ]
    if "entry_logic" in required_missing_fields and "entry_logic" not in missing:
        missing.insert(0, "entry_logic")
    missing.extend(required_missing_fields)
    return list(dict.fromkeys(missing))


def _strategy_is_semantically_confirmable(
    *,
    expects_strategy_route: bool,
    ambiguous_fields: list[AmbiguousField],
    unsupported_constraints: list[UnsupportedConstraint],
    missing_required_fields: list[str],
) -> bool:
    return (
        expects_strategy_route
        and not ambiguous_fields
        and not unsupported_constraints
        and not missing_required_fields
    )


def _strategy_route_expected(
    *,
    intent: IntentName,
    semantic_turn_act: SemanticTurnAct | None,
) -> bool:
    return intent in {"strategy_drafting", "backtest_execution"} or (
        semantic_turn_act in STRATEGY_TURN_ACTS
    )


def _candidate_strategy_has_backtest_shape(strategy: StrategySummary) -> bool:
    return _strategy_has_execution_anchor(strategy)


def _strategy_has_execution_anchor(strategy: StrategySummary) -> bool:
    return any(
        value not in (None, "", [], {})
        for value in (
            strategy.strategy_type,
            strategy.asset_universe,
            strategy.asset_class,
            strategy.date_range,
            strategy.timeframe,
            strategy.entry_logic,
            strategy.exit_logic,
            strategy.rule_spec,
            strategy.cadence,
            strategy.capital_amount,
            strategy.position_size,
            strategy.risk_rules,
            strategy.comparison_baseline,
            strategy.extra_parameters,
        )
    )


def _unanchored_strategy_route_response() -> str:
    return "I'm here. Tell me the investing idea you want to test."


def _dedupe_unsupported_constraints(
    constraints: list[UnsupportedConstraint],
) -> list[UnsupportedConstraint]:
    seen: set[tuple[str, str]] = set()
    deduped: list[UnsupportedConstraint] = []
    for constraint in constraints:
        key = (constraint.category, constraint.raw_value)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(constraint)
    return deduped


def _dedupe_ambiguous_fields(fields: list[AmbiguousField]) -> list[AmbiguousField]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[AmbiguousField] = []
    for field in fields:
        key = (field.field_name, field.raw_value, field.reason_code)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(field)
    return deduped


def _dedupe_resolution_provenance(
    provenance: list[ResolutionProvenance | dict[str, Any]],
) -> list[ResolutionProvenance]:
    seen: set[tuple[str, str, str, str]] = set()
    deduped: list[ResolutionProvenance] = []
    for raw_item in provenance:
        if isinstance(raw_item, ResolutionProvenance):
            item = raw_item
        else:
            try:
                item = ResolutionProvenance.model_validate(raw_item)
            except (TypeError, ValueError):
                continue
        key = (
            item.field,
            item.raw_text,
            item.source,
            item.candidate_kind,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def normalize_task_snapshot(
    latest_task_snapshot: TaskSnapshot | dict[str, Any] | None,
) -> TaskSnapshot | None:
    if latest_task_snapshot is None:
        return None
    if isinstance(latest_task_snapshot, TaskSnapshot):
        return latest_task_snapshot
    return TaskSnapshot.model_validate(latest_task_snapshot)


def has_response_profile_overrides(overrides: ResponseProfileOverrides) -> bool:
    return any(
        value is not None
        for value in (
            overrides.tone,
            overrides.verbosity,
            overrides.expertise_mode,
        )
    )
