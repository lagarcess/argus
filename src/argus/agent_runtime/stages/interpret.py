from __future__ import annotations

import asyncio
import inspect
import os
from dataclasses import dataclass
from typing import Any

from argus.agent_runtime.capabilities.answers import (
    EXECUTABLE_STRATEGY_FAMILIES,
    compose_capability_answer,
    compose_capability_recovery_answer,
)
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
    compose_private_alpha_save_response,
    compose_result_followup_response,
    fallback_private_alpha_save_response,
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
    ArtifactTarget,
    CapabilityQuestionFocus,
    ContextQuestionFocus,
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
from argus.context import (
    ContextPacket,
    context_packet_freshness,
    fetch_alpaca_market_movers_packet,
)
from argus.domain.indicators import (
    EXECUTABLE_INDICATORS,
    IndicatorExecutionSpec,
    executable_indicator_spec,
    normalize_indicator_parameters,
)
from argus.domain.market_data import resolve_asset
from argus.llm.openrouter import invoke_openrouter_chat_completion

_DEFAULT_RESOLVE_ASSET = resolve_asset
_STANDALONE_CONTEXT_PACKET_TIMEOUT_SECONDS = 2.5
_LATEST_RESULT_SAVE_REQUESTED_REASON = "latest_result_save_requested"


@dataclass(frozen=True)
class _LiveContextCuriosityFacts:
    content: str
    packet_symbols: tuple[str, ...] = ()

STRATEGY_TURN_ACTS: set[SemanticTurnAct] = {
    "new_idea",
    "answer_pending_need",
    "refine_current_idea",
    "approval",
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
    artifact_target, artifact_target_reason_codes = _validated_artifact_target(
        interpretation=interpretation,
        snapshot=snapshot,
        selected_thread_metadata=selected_thread_metadata,
    )
    (
        incoming_strategy,
        hidden_context_guard_reason_codes,
        clear_assistant_response_for_hidden_context,
    ) = _strategy_with_hidden_context_guard(
        strategy=incoming_strategy,
        interpretation=interpretation,
        snapshot=snapshot,
        artifact_target=artifact_target,
        current_user_message=state.current_user_message,
    )
    if clear_assistant_response_for_hidden_context:
        interpretation = interpretation.model_copy(
            update={
                "assistant_response": None,
                "requires_clarification": True,
            }
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
                "assistant_response": interpretation.assistant_response,
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
            *artifact_target_reason_codes,
            *hidden_context_guard_reason_codes,
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
        context_question_focus=interpretation.context_question_focus,
        artifact_target=artifact_target,
    )
    if interpretation.capability_question_focus is not None:
        decision.normalized_signals["capability_question_focus"] = (
            interpretation.capability_question_focus
        )
    if interpretation.context_question_focus is not None:
        decision.normalized_signals["context_question_focus"] = (
            interpretation.context_question_focus
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
    pending_refinement_result = _pending_refinement_misroute_result_if_applicable(
        decision=decision,
        snapshot=snapshot,
    )
    if pending_refinement_result is not None:
        return pending_refinement_result
    private_alpha_save_result = await _private_alpha_save_request_result_if_applicable(
        decision=decision,
        snapshot=snapshot,
        current_user_message=state.current_user_message,
    )
    if private_alpha_save_result is not None:
        return private_alpha_save_result
    followup_result = await _artifact_followup_stage_result_if_applicable(
        decision=decision,
        snapshot=snapshot,
        current_user_message=state.current_user_message,
    )
    if followup_result is not None:
        return followup_result
    context_answer = await _context_curiosity_answer_if_applicable(
        focus=interpretation.context_question_focus,
        semantic_turn_act=interpretation.semantic_turn_act,
        expects_strategy_route=expects_strategy_route,
        requires_clarification=requires_clarification,
        assistant_response=interpretation.assistant_response,
        current_user_message=state.current_user_message,
        artifact_target=artifact_target,
    )
    if context_answer is not None:
        return StageResult(
            outcome="ready_to_respond",
            decision=decision,
            stage_patch={"assistant_response": context_answer},
        )
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
    unanchored_strategy_recovery = await _unanchored_strategy_route_answer_if_needed(
        reason_codes=decision.reason_codes,
        expects_strategy_route=expects_strategy_route,
        requires_clarification=requires_clarification,
        current_user_message=state.current_user_message,
        capability_contract=capability_contract,
    )
    if unanchored_strategy_recovery is not None:
        return StageResult(
            outcome="ready_to_respond",
            decision=decision,
            stage_patch={"assistant_response": unanchored_strategy_recovery},
        )
    educational_recovery = await _educational_answer_recovery_if_needed(
        semantic_turn_act=interpretation.semantic_turn_act,
        expects_strategy_route=expects_strategy_route,
        requires_clarification=requires_clarification,
        assistant_response=interpretation.assistant_response,
        current_user_message=state.current_user_message,
    )
    if educational_recovery is not None:
        return StageResult(
            outcome="ready_to_respond",
            decision=decision,
            stage_patch={"assistant_response": educational_recovery},
        )
    unhandled_recovery = await _unhandled_response_recovery_if_needed(
        semantic_turn_act=interpretation.semantic_turn_act,
        expects_strategy_route=expects_strategy_route,
        requires_clarification=requires_clarification,
        assistant_response=interpretation.assistant_response,
        current_user_message=state.current_user_message,
    )
    if unhandled_recovery is not None:
        return StageResult(
            outcome="ready_to_respond",
            decision=decision,
            stage_patch={"assistant_response": unhandled_recovery},
        )
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


def _validated_artifact_target(
    *,
    interpretation: StructuredInterpretation,
    snapshot: TaskSnapshot | None,
    selected_thread_metadata: dict[str, Any],
) -> tuple[ArtifactTarget | None, list[str]]:
    proposed = interpretation.artifact_target
    reason_codes: list[str] = []
    requested_field = _field_base(
        str(selected_thread_metadata.get("requested_field") or "")
    )
    if requested_field == "refinement" and snapshot is not None:
        if snapshot.pending_strategy_summary is not None:
            if proposed != "pending_refinement":
                reason_codes.append("pending_refinement_overrode_latest_result")
            return "pending_refinement", reason_codes
    if proposed == "latest_result":
        if snapshot is not None and snapshot.latest_backtest_result_reference is not None:
            return "latest_result", reason_codes
        reason_codes.append("invalid_latest_result_target_cleared")
        return "none", reason_codes
    if proposed == "active_confirmation":
        if snapshot is not None and snapshot.active_confirmation_reference is not None:
            return "active_confirmation", reason_codes
        reason_codes.append("invalid_active_confirmation_target_cleared")
        return "none", reason_codes
    if proposed in {"none", "pending_refinement"}:
        return proposed, reason_codes
    if (
        interpretation.semantic_turn_act == "result_followup"
        and snapshot is not None
        and snapshot.latest_backtest_result_reference is not None
    ):
        reason_codes.append("legacy_result_followup_target_inferred")
        return "latest_result", reason_codes
    if (
        interpretation.intent == "results_explanation"
        and snapshot is not None
        and snapshot.latest_backtest_result_reference is not None
    ):
        reason_codes.append("legacy_result_explanation_target_inferred")
        return "latest_result", reason_codes
    return proposed, reason_codes


def _pending_refinement_misroute_result_if_applicable(
    *,
    decision: InterpretDecision,
    snapshot: TaskSnapshot | None,
) -> StageResult | None:
    if decision.artifact_target != "pending_refinement":
        return None
    if decision.semantic_turn_act != "result_followup":
        return None
    if _candidate_strategy_has_backtest_shape(decision.candidate_strategy_draft):
        return None
    strategy = (
        snapshot.pending_strategy_summary.model_copy(deep=True)
        if snapshot is not None and snapshot.pending_strategy_summary is not None
        else decision.candidate_strategy_draft
    )
    refined = decision.model_copy(
        update={
            "intent": "strategy_drafting",
            "task_relation": "refine",
            "requires_clarification": True,
            "candidate_strategy_draft": strategy,
            "missing_required_fields": ["refinement"],
            "semantic_turn_act": "answer_pending_need",
            "artifact_target": "pending_refinement",
            "reason_codes": [
                *decision.reason_codes,
                "pending_refinement_result_followup_suppressed",
            ],
        }
    )
    return StageResult(
        outcome="needs_clarification",
        decision=refined,
        stage_patch={
            "requested_field": "refinement",
            "missing_required_fields": ["refinement"],
            "response_intent": {
                "kind": "clarification",
                "semantic_needs": ["rule_definition"],
                "requested_fields": ["refinement"],
                "facts": {"strategy": strategy.model_dump(mode="python")},
                "options": [],
            },
        },
    )


def _strategy_with_hidden_context_guard(
    *,
    strategy: StrategySummary,
    interpretation: StructuredInterpretation,
    snapshot: TaskSnapshot | None,
    artifact_target: ArtifactTarget | None,
    current_user_message: str,
) -> tuple[StrategySummary, list[str], bool]:
    if artifact_target != "none":
        return strategy, [], False
    if interpretation.semantic_turn_act != "new_idea":
        return strategy, [], False
    if interpretation.task_relation != "new_task":
        return strategy, [], False
    if snapshot is None or snapshot.pending_strategy_summary is None:
        return strategy, [], False
    prior = snapshot.pending_strategy_summary
    if not prior.asset_universe or strategy.asset_universe != prior.asset_universe:
        return strategy, [], False
    if _strategy_has_fresh_execution_detail(strategy=strategy, prior=prior):
        return strategy, [], False
    if _message_explicitly_mentions_symbol(
        current_user_message,
        symbols=strategy.asset_universe,
    ):
        return strategy, [], False
    updated = strategy.model_copy(deep=True)
    updated.asset_universe = []
    updated.asset_class = None
    updated.resolution_provenance = []
    return updated, ["hidden_artifact_asset_context_cleared"], True


def _strategy_has_fresh_execution_detail(
    *,
    strategy: StrategySummary,
    prior: StrategySummary,
) -> bool:
    for field_name in (
        "date_range",
        "timeframe",
        "cadence",
        "entry_logic",
        "exit_logic",
        "entry_rule",
        "exit_rule",
        "rule_spec",
        "capital_amount",
        "position_size",
        "comparison_baseline",
    ):
        value = getattr(strategy, field_name)
        if value in (None, "", [], {}):
            continue
        if value != getattr(prior, field_name):
            return True
    return False


def _message_explicitly_mentions_symbol(
    message: str,
    *,
    symbols: list[str],
) -> bool:
    punctuation = ".,;:!?()[]{}<>\"'`"
    token_map = str.maketrans({char: " " for char in punctuation})
    tokens = set(message.translate(token_map).split())
    cashtag_tokens = {
        token.lstrip("$").casefold()
        for token in tokens
        if token.startswith("$")
    }
    return any(
        symbol in tokens
        or f"${symbol}" in tokens
        or symbol.casefold() in cashtag_tokens
        for symbol in symbols
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
    if focus in {"supported_strategies", "general"} and assistant_response:
        return None
    composed = await _compose_natural_capability_answer(
        focus=focus,
        current_user_message=current_user_message,
        capability_contract=capability_contract,
    )
    if composed:
        return composed
    return compose_capability_answer(focus=focus, contract=capability_contract)


async def _context_curiosity_answer_if_applicable(
    *,
    focus: ContextQuestionFocus | None,
    semantic_turn_act: SemanticTurnAct | None,
    expects_strategy_route: bool,
    requires_clarification: bool,
    assistant_response: str | None,
    current_user_message: str,
    artifact_target: ArtifactTarget | None,
) -> str | None:
    if (
        focus is None
        or semantic_turn_act != "educational_question"
        or expects_strategy_route
        or requires_clarification
    ):
        return None
    composed = await _compose_natural_context_curiosity_answer(
        focus=focus,
        current_user_message=current_user_message,
        artifact_target=artifact_target,
    )
    if composed:
        return composed
    return assistant_response or _context_curiosity_recovery_answer(focus)


async def _compose_natural_capability_answer(
    *,
    focus: CapabilityQuestionFocus,
    current_user_message: str,
    capability_contract: Any,
) -> str | None:
    fact_packet = compose_capability_answer(
        focus=focus,
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
        answer = await invoke_openrouter_chat_completion(
            task="chat_composer",
            messages=messages,
        )
        if _capability_answer_respects_contract(
            answer=answer,
            focus=focus,
        ):
            return answer
        return compose_capability_answer(
            focus=focus,
            contract=capability_contract,
        )
    except Exception:
        if focus == "supported_indicators":
            return compose_capability_answer(
                focus=focus,
                contract=capability_contract,
            )
        return compose_capability_recovery_answer(
            focus=focus,
            contract=capability_contract,
        )


def _capability_answer_respects_contract(
    *,
    answer: str | None,
    focus: CapabilityQuestionFocus,
) -> bool:
    if not answer:
        return False
    if focus != "supported_indicators":
        return True
    return not _answer_contradicts_supported_indicators(answer)


def _answer_contradicts_supported_indicators(answer: str) -> bool:
    for sentence in _plain_sentences(answer):
        tokens = _plain_word_tokens(sentence)
        if not tokens:
            continue
        indicator_spans = _supported_indicator_token_spans(tokens)
        if not indicator_spans:
            continue
        negative_positions = _negative_support_claim_positions(tokens)
        for start, end in indicator_spans:
            if any(start - 3 <= position <= end + 6 for position in negative_positions):
                return True
    return False


def _plain_sentences(text: str) -> list[str]:
    sentences: list[str] = []
    start = 0
    for index, char in enumerate(str(text or "")):
        if char not in ".?!":
            continue
        sentence = text[start : index + 1].strip()
        if sentence:
            sentences.append(sentence)
        start = index + 1
    trailing = text[start:].strip()
    if trailing:
        sentences.append(trailing)
    return sentences


def _plain_word_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    current: list[str] = []
    for char in str(text or "").casefold():
        if char.isalnum():
            current.append(char)
            continue
        if char == "'":
            continue
        if current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))
    return tokens


def _supported_indicator_token_spans(tokens: list[str]) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for spec in EXECUTABLE_INDICATORS.values():
        terms = (spec.key, spec.label, *spec.aliases)
        for term in terms:
            term_tokens = _plain_word_tokens(term)
            if not term_tokens:
                continue
            spans.extend(_token_sequence_spans(tokens, term_tokens))
    return spans


def _token_sequence_spans(
    tokens: list[str],
    sequence: list[str],
) -> list[tuple[int, int]]:
    if not sequence or len(sequence) > len(tokens):
        return []
    spans: list[tuple[int, int]] = []
    last_start = len(tokens) - len(sequence)
    for start in range(last_start + 1):
        end = start + len(sequence)
        if tokens[start:end] == sequence:
            spans.append((start, end - 1))
    return spans


def _negative_support_claim_positions(tokens: list[str]) -> set[int]:
    positions: set[int] = set()
    negative_words = {"not", "never", "unsupported", "unavailable"}
    support_words = {"allowed", "available", "executable", "runnable", "supported"}
    action_words = {"execute", "run", "use"}
    blocking_words = {"cannot", "cant"}
    for index, token in enumerate(tokens):
        if token in {"unsupported", "unavailable"}:
            positions.add(index)
            continue
        previous = set(tokens[max(0, index - 3) : index])
        if token in support_words and previous.intersection(negative_words):
            positions.add(index)
            continue
        if token in action_words and previous.intersection(blocking_words):
            positions.add(index)
    return positions


async def _compose_natural_context_curiosity_answer(
    *,
    focus: ContextQuestionFocus,
    current_user_message: str,
    artifact_target: ArtifactTarget | None,
) -> str | None:
    fact_packet = _context_curiosity_fact_packet(focus)
    live_facts = await _live_context_curiosity_facts(focus)
    if focus == "market_movers" and not live_facts.packet_symbols:
        return _packet_grounded_context_recovery_answer(
            focus=focus,
            live_facts=live_facts,
        )
    provenance_rule = (
        "If you use visible artifact context, say so naturally with phrases like "
        "'from this result' or 'from the current draft'."
        if artifact_target in {"latest_result", "active_confirmation", "pending_refinement"}
        else "Do not imply you used a prior result or hidden memory."
    )
    messages = [
        {
            "role": "system",
            "content": (
                "You are Argus, a chat-first investing experimentation assistant. "
                "Answer broad market or macro curiosity in warm, plain English. "
                "Keep it concise. The opening sentence must give useful investing "
                "context, not an apology, greeting, or capability rejection. Explain "
                "any product boundary after the context and only if needed. Offer a "
                "nearby historical testable path using only supported experiment "
                "paths. Do not open with what Argus cannot do. Do not reject "
                "standalone context questions; answer briefly, then connect them to "
                "an experiment. Do not imply Argus is a live market-news product. "
                "Do not invent current facts, prices, headlines, macro readings, "
                "causality, or investment advice. Do not name data vendors in the "
                "user-facing answer. Do not suggest live screens, feeds, event-driven "
                "execution, unusual-volume scans, sector screens, filter pipelines, "
                "or macro data as direct trading signals. Do not propose a concrete "
                "executable rule unless it is named in the supported experiment "
                "paths; for example, do not invent price-jump, fixed-hold-period, "
                "or custom ranking rules. "
                f"{provenance_rule}"
            ),
        },
        {
            "role": "system",
            "content": f"Context-curiosity facts: {fact_packet}",
        },
        {
            "role": "system",
            "content": f"Available short-lived context packet: {live_facts.content}",
        },
        {
            "role": "system",
            "content": (
                "Supported experiment paths: "
                f"{_supported_experiment_fact_packet()}"
            ),
        },
        {"role": "user", "content": current_user_message},
    ]
    try:
        answer = await invoke_openrouter_chat_completion(
            task="chat_composer",
            messages=messages,
        )
        if _context_answer_respects_live_packet(
            answer=answer,
            live_facts=live_facts,
        ):
            return answer
        retry_messages = _context_packet_grounding_retry_messages(
            messages=messages,
            live_facts=live_facts,
        )
        retry_answer = await invoke_openrouter_chat_completion(
            task="chat_composer",
            messages=retry_messages,
        )
        if _context_answer_respects_live_packet(
            answer=retry_answer,
            live_facts=live_facts,
        ):
            return retry_answer
        return _packet_grounded_context_recovery_answer(
            focus=focus,
            live_facts=live_facts,
        )
    except Exception:
        return None


def _context_curiosity_fact_packet(focus: ContextQuestionFocus) -> str:
    facts = {
        "macro_context": (
            "Macro context can frame historical explanations and regime questions "
            "such as inflation, rates, employment, recession indicators, and risk "
            "backdrop. It is contextual only and cannot alter simulation truth or "
            "become a trade signal. Good next steps are choosing a symbol/strategy "
            "and comparing historical periods the user names. Allowed next steps: "
            "ask the user to choose a symbol, strategy, and date windows; compare "
            "buy-and-hold, recurring buys, or supported indicator rules across "
            "those user-chosen windows."
        ),
        "corporate_events": (
            "Corporate actions can provide symbol/date-scoped event context such "
            "as splits and dividends around an equity run. They are valid context "
            "for understanding what was happening around a historical period. They "
            "are not direct event-trading rules, and they cannot rewrite completed "
            "explanations or alter simulation truth. Good next steps are choosing "
            "an equity symbol and date range, then testing a supported strategy "
            "through that period. Allowed next steps: ask for an equity symbol and "
            "date range around an event; test buy-and-hold, recurring buys, or a "
            "supported indicator rule through the period. Do not propose earnings "
            "plays, merger trades, event prediction, volume-impact models, or direct "
            "event-driven rules."
        ),
        "market_movers": (
            "Movers and most-actives context is very short-lived and narrow. It is "
            "not a generic product feed, but it can help the user pick a current "
            "symbol seed for a historical experiment. If a current movers packet is "
            "available, you may mention up to five provided symbols as possible test "
            "seeds, never as recommendations, and make clear that Argus will validate "
            "the selected symbol before any run. Good next steps are choosing one "
            "symbol or date window the user is curious about, then testing buy and "
            "hold, recurring buys, or a supported indicator rule. Do not turn this "
            "into a dashboard, ranking feed, sector-rotation screen, filter pipeline, "
            "volume-surge test, or volume-spike strategy."
        ),
    }
    return facts[focus]


async def _live_context_curiosity_facts(
    focus: ContextQuestionFocus,
) -> _LiveContextCuriosityFacts:
    if focus != "market_movers":
        return _LiveContextCuriosityFacts(
            content=(
                "No live context packet is collected for this standalone turn. Use "
                "the static context-curiosity facts only."
            )
        )
    packet = await _fetch_standalone_market_movers_packet()
    if packet is None:
        return _LiveContextCuriosityFacts(
            content=(
                "No current movers packet is available inside this turn. Do not "
                "claim to have checked current movers; explain the concept and ask "
                "the user to pick a symbol, theme, or date window for a historical "
                "test."
            )
        )
    return _LiveContextCuriosityFacts(
        content=_market_movers_packet_fact_text(packet),
        packet_symbols=tuple(_market_movers_packet_symbols(packet)),
    )


async def _fetch_standalone_market_movers_packet() -> ContextPacket | None:
    try:
        packet = await asyncio.wait_for(
            asyncio.to_thread(
                fetch_alpaca_market_movers_packet,
                market_type="stocks",
                top=5,
            ),
            timeout=_STANDALONE_CONTEXT_PACKET_TIMEOUT_SECONDS,
        )
    except Exception:
        return None
    if packet is None:
        return None
    freshness = context_packet_freshness(packet)
    if freshness == "stale":
        return None
    if freshness != packet.freshness:
        packet = packet.model_copy(update={"freshness": freshness})
    return packet


def _market_movers_packet_fact_text(packet: ContextPacket) -> str:
    gainers: list[str] = []
    losers: list[str] = []
    for fact in packet.facts:
        if fact.kind not in {"market_mover_gainer", "market_mover_loser"}:
            continue
        if not isinstance(fact.value, dict):
            continue
        symbol = str(fact.value.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        formatted = _format_market_mover_symbol(
            symbol=symbol,
            percent_change=fact.value.get("percent_change"),
        )
        if fact.kind == "market_mover_gainer":
            gainers.append(formatted)
        else:
            losers.append(formatted)
    sections = []
    if gainers:
        sections.append(f"current gainers: {', '.join(gainers[:5])}")
    if losers:
        sections.append(f"current losers: {', '.join(losers[:5])}")
    if not sections:
        return (
            "A current movers packet was retrieved, but it contained no usable "
            "symbol facts. Do not fabricate mover symbols."
        )
    retrieved_at = packet.retrieved_at.isoformat()
    return (
        "Short-lived movers packet retrieved at "
        f"{retrieved_at}; { '; '.join(sections) }. Use these only as possible "
        "historical-test seeds, not recommendations, predictions, causal evidence, "
        "or simulation truth. Treat symbols as unvalidated until the user chooses "
        "one and deterministic asset validation confirms it can run."
    )


def _market_movers_packet_symbols(packet: ContextPacket) -> list[str]:
    symbols: list[str] = []
    for fact in packet.facts:
        if fact.kind not in {"market_mover_gainer", "market_mover_loser"}:
            continue
        if not isinstance(fact.value, dict):
            continue
        symbol = str(fact.value.get("symbol") or "").strip().upper()
        if symbol:
            symbols.append(symbol)
    return list(dict.fromkeys(symbols))


def _context_answer_respects_live_packet(
    *,
    answer: str | None,
    live_facts: _LiveContextCuriosityFacts,
) -> bool:
    if not live_facts.packet_symbols:
        return True
    return bool(
        answer
        and _mentioned_packet_symbols(
            text=answer,
            symbols=live_facts.packet_symbols,
        )
    )


def _mentioned_packet_symbols(
    *,
    text: str,
    symbols: tuple[str, ...],
) -> list[str]:
    token_map = str.maketrans({char: " " for char in ".,;:!?()[]{}<>\"'`"})
    tokens = {
        token.strip("$").upper()
        for token in text.translate(token_map).split()
        if token.strip("$")
    }
    return [symbol for symbol in symbols if symbol.upper() in tokens]


def _context_packet_grounding_retry_messages(
    *,
    messages: list[dict[str, str]],
    live_facts: _LiveContextCuriosityFacts,
) -> list[dict[str, str]]:
    user_message = messages[-1]
    grounding_message = {
        "role": "system",
        "content": (
            "The previous draft did not use the available short-lived context "
            "packet. Rewrite the answer using at least one provided packet symbol "
            "as an unvalidated historical-test seed. Do not present the packet as "
            "a live dashboard, recommendation, ranking feed, causal proof, or "
            "simulation truth. Keep the user moving toward choosing a symbol and "
            "a supported historical experiment."
        ),
    }
    return [
        *messages[:-1],
        {
            "role": "system",
            "content": (
                "Packet symbols that must ground this answer: "
                f"{', '.join(live_facts.packet_symbols)}"
            ),
        },
        grounding_message,
        user_message,
    ]


def _packet_grounded_context_recovery_answer(
    *,
    focus: ContextQuestionFocus,
    live_facts: _LiveContextCuriosityFacts,
) -> str:
    if focus == "market_movers" and live_facts.packet_symbols:
        seeds = _join_context_symbols(live_facts.packet_symbols[:5])
        return (
            f"A short-lived movers snapshot can help pick experiment seeds: {seeds}. "
            "Treat those as symbols to validate, not recommendations or a live "
            "ranking. Pick one, and I can test buy-and-hold, recurring buys, or a "
            "supported indicator rule over a historical window."
        )
    return _context_curiosity_recovery_answer(focus)


def _join_context_symbols(symbols: tuple[str, ...]) -> str:
    if not symbols:
        return "a symbol you choose"
    if len(symbols) == 1:
        return symbols[0]
    return f"{', '.join(symbols[:-1])}, or {symbols[-1]}"


def _format_market_mover_symbol(*, symbol: str, percent_change: Any) -> str:
    if percent_change in (None, ""):
        return symbol
    if isinstance(percent_change, int | float):
        return f"{symbol} ({percent_change:+g}%)"
    text = str(percent_change).strip()
    if not text:
        return symbol
    if text.endswith("%"):
        return f"{symbol} ({text})"
    return f"{symbol} ({text}%)"


def _supported_experiment_fact_packet() -> str:
    families = "; ".join(EXECUTABLE_STRATEGY_FAMILIES)
    return (
        f"{families}. Macro, news, corporate-action, and movers context may frame "
        "a question or explain backdrop, but cannot alter simulation truth or become "
        "the executable rule. Suggested next experiments must stay inside these "
        "families instead of inventing unregistered triggers or holding-period rules."
    )


def _context_curiosity_recovery_answer(focus: ContextQuestionFocus) -> str:
    if focus == "macro_context":
        return (
            "Macro conditions can be useful context for a historical test. Give me "
            "a strategy or symbol and I can help compare how it behaved across "
            "different rate or inflation backdrops."
        )
    if focus == "corporate_events":
        return (
            "Corporate events are most useful when tied to a symbol and period. "
            "Give me an equity ticker and I can use events like splits or dividends "
            "as context around a historical test."
        )
    return (
        "A market move can be a useful starting point for an experiment. Give me "
        "a symbol or idea and I can turn it into a historical test instead of a feed."
    )


async def _unanchored_strategy_route_answer_if_needed(
    *,
    reason_codes: list[str],
    expects_strategy_route: bool,
    requires_clarification: bool,
    current_user_message: str,
    capability_contract: Any,
) -> str | None:
    if (
        "unanchored_strategy_route_suppressed" not in reason_codes
        or expects_strategy_route
        or requires_clarification
    ):
        return None
    composed = await _compose_unanchored_strategy_recovery_answer(
        current_user_message=current_user_message,
        capability_contract=capability_contract,
    )
    if composed:
        return composed
    return _llm_composition_unavailable_recovery_answer()


async def _compose_unanchored_strategy_recovery_answer(
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
                "The user expressed a broad or vague investing strategy intention, "
                "but deterministic validation found no executable strategy anchor "
                "yet. Do not create a draft. Answer in warm, plain English. Give "
                "useful beginner-friendly context, name only supported experiment "
                "families from the facts, and offer one clear next step. Do not use "
                "report tone, do not say generic filler like 'I'm here', and do not "
                "give investment advice."
            ),
        },
        {"role": "system", "content": f"Supported-strategy facts: {fact_packet}"},
        {"role": "user", "content": current_user_message},
    ]
    try:
        response = await invoke_openrouter_chat_completion(
            task="chat_composer",
            messages=messages,
        )
    except Exception:
        return None
    cleaned = str(response or "").strip()
    return cleaned or None


async def _educational_answer_recovery_if_needed(
    *,
    semantic_turn_act: SemanticTurnAct | None,
    expects_strategy_route: bool,
    requires_clarification: bool,
    assistant_response: str | None,
    current_user_message: str,
) -> str | None:
    if (
        semantic_turn_act != "educational_question"
        or expects_strategy_route
        or requires_clarification
        or assistant_response
    ):
        return None
    composed = await _compose_general_educational_answer(
        current_user_message=current_user_message
    )
    if composed:
        return composed
    return _llm_composition_unavailable_recovery_answer()


async def _unhandled_response_recovery_if_needed(
    *,
    semantic_turn_act: SemanticTurnAct | None,
    expects_strategy_route: bool,
    requires_clarification: bool,
    assistant_response: str | None,
    current_user_message: str,
) -> str | None:
    if expects_strategy_route or requires_clarification or assistant_response:
        return None
    composed = await _compose_unhandled_conversation_answer(
        semantic_turn_act=semantic_turn_act,
        current_user_message=current_user_message,
    )
    if composed:
        return composed
    return _llm_composition_unavailable_recovery_answer()


def _llm_composition_unavailable_recovery_answer() -> str:
    return (
        "I couldn't shape that cleanly just now. Try giving me an asset and rough "
        "time window, and I'll turn it into the closest runnable historical test."
    )


async def _compose_general_educational_answer(*, current_user_message: str) -> str | None:
    messages = [
        {
            "role": "system",
            "content": (
                "You are Argus, a chat-first investing experimentation assistant. "
                "The structured interpreter identified this as an educational or "
                "broad investing-curiosity turn but did not produce user-facing prose. "
                "Answer in warm, plain English. Start with useful context, keep it "
                "concise, avoid report tone, do not name data vendors, do not imply "
                "live news coverage, and do not give investment advice. End with one "
                "nearby historical experiment or recoverable next step when useful."
            ),
        },
        {"role": "user", "content": current_user_message},
    ]
    try:
        response = await invoke_openrouter_chat_completion(
            task="chat_composer",
            messages=messages,
        )
    except Exception:
        return None
    cleaned = str(response or "").strip()
    return cleaned or None


async def _compose_unhandled_conversation_answer(
    *,
    semantic_turn_act: SemanticTurnAct | None,
    current_user_message: str,
) -> str | None:
    messages = [
        {
            "role": "system",
            "content": (
                "You are Argus, a chat-first investing experimentation assistant. "
                "The runtime has no executable strategy, no clarification contract, "
                "and no user-facing answer for this turn. Recover by answering in "
                "warm, plain English. Do not use report tone. Do not name data "
                "vendors, imply live market-news coverage, invent current facts, "
                "or give investment advice. Preserve continuity of exploration by "
                "offering one nearby historical experiment or recoverable next step "
                "from the supported experiment paths. Do not suggest live screens, "
                "feeds, rankings, sector screens, filter pipelines, volume-surge "
                "tests, event-driven execution, or macro data as direct trading "
                "signals."
            ),
        },
        {
            "role": "system",
            "content": f"Semantic turn act: {semantic_turn_act or 'unspecified'}",
        },
        {
            "role": "system",
            "content": (
                "Supported experiment paths: "
                f"{_supported_experiment_fact_packet()}"
            ),
        },
        {"role": "user", "content": current_user_message},
    ]
    try:
        response = await invoke_openrouter_chat_completion(
            task="chat_composer",
            messages=messages,
        )
    except Exception:
        return None
    cleaned = str(response or "").strip()
    return cleaned or None


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
    save_requested = _latest_result_save_requested(decision)
    if decision.artifact_target != "latest_result":
        return None
    if assistant_response and not unanchored_strategy_route and not save_requested:
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
    if save_requested and not _strategies_enabled():
        response = await compose_private_alpha_save_response(
            metadata=metadata,
            user_message=current_user_message,
        )
        if response is None:
            response = fallback_private_alpha_save_response()
    else:
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
            "assistant_response": (
                response
                if save_requested and not _strategies_enabled()
                else with_response_heading(
                    heading=result_followup_heading(focus),
                    body=response,
                )
            )
        },
    )


async def _private_alpha_save_request_result_if_applicable(
    *,
    decision: InterpretDecision,
    snapshot: TaskSnapshot | None,
    current_user_message: str,
) -> StageResult | None:
    if not _latest_result_save_requested(decision):
        return None
    if _strategies_enabled():
        return None
    if decision.artifact_target != "latest_result":
        return None
    if snapshot is None or snapshot.latest_backtest_result_reference is None:
        return None
    response = await compose_private_alpha_save_response(
        metadata=dict(snapshot.latest_backtest_result_reference.metadata),
        user_message=current_user_message,
    )
    if response is None:
        response = fallback_private_alpha_save_response()
    return StageResult(
        outcome="ready_to_respond",
        decision=decision.model_copy(
            update={
                "intent": "conversation_followup",
                "requires_clarification": False,
                "missing_required_fields": [],
                "semantic_turn_act": "result_followup",
                "result_followup_focus": decision.result_followup_focus or "general",
            }
        ),
        stage_patch={"assistant_response": response},
    )


def _strategies_enabled() -> bool:
    raw = os.getenv("ARGUS_STRATEGIES_ENABLED", "false").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _latest_result_save_requested(decision: InterpretDecision) -> bool:
    return _LATEST_RESULT_SAVE_REQUESTED_REASON in decision.reason_codes


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
