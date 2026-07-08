# ruff: noqa: F401, I001
# This stage is being modularized into argus.agent_runtime.stages.interpret_internal.*;
# it re-exports relocated symbols and preserves its full original import surface so
# external callers/tests that access ``interpret.<name>`` keep working.
from __future__ import annotations

import asyncio
import inspect
import os
from dataclasses import dataclass
from datetime import date
from typing import Any, cast, get_args

from argus.agent_runtime.artifact_edit_planner import plan_artifact_assumption_edit
from argus.agent_runtime.artifacts.patch_policy import (
    executable_artifact_patch_missing_fields,
    relevant_unsupported_constraints_for_artifact_patch,
)
from argus.agent_runtime.artifacts.strategy_edits import (
    ArtifactPatch,
    apply_artifact_patch,
)
from argus.agent_runtime.capabilities.answers import (
    EXECUTABLE_STRATEGY_FAMILIES,
    capability_fact_packet,
)
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.extraction import detect_unsupported_constraints
from argus.agent_runtime.interpreter import provider_context_assets
from argus.agent_runtime.profile.response_profile import (
    resolve_effective_response_profile,
)
from argus.agent_runtime.recovery_messages import (
    recovery_message,
    recovery_state_stage_patch,
    retry_last_turn_stage_patch,
)
from argus.agent_runtime.resolution import AssetResolution, callable_accepts_keyword
from argus.agent_runtime.resolution import (
    resolve_asset_candidate as runtime_resolve_asset_candidate,
)
from argus.agent_runtime.response_language import response_language_instruction
from argus.agent_runtime.response_style import result_followup_response_intent
from argus.agent_runtime.result_followups import (
    compose_private_alpha_save_response,
    compose_result_followup_response,
    fallback_private_alpha_save_response,
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
    RESULT_EXPLANATION_TARGET_INFERRED,
    RESULT_FOLLOWUP_TARGET_INFERRED,
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
from argus.agent_runtime.stages.interpret_internal.answer_composition import (  # noqa: F401
    _STANDALONE_CONTEXT_PACKET_TIMEOUT_SECONDS,
    _SUPPORTED_STRATEGY_FAMILY_TERMS,
    _answer_contradicts_supported_indicators,
    _answer_contradicts_supported_strategy_families,
    _capability_answer_respects_contract,
    _context_answer_respects_live_packet,
    _context_curiosity_fact_packet,
    _context_curiosity_recovery_answer,
    _context_packet_grounding_retry_messages,
    _format_market_mover_symbol,
    _join_context_symbols,
    _LiveContextCuriosityFacts,
    _llm_composition_unavailable_recovery_answer,
    _market_movers_packet_fact_text,
    _market_movers_packet_symbols,
    _mentioned_packet_symbols,
    _negative_support_claim_positions,
    _packet_grounded_context_recovery_answer,
    _plain_sentences,
    _plain_word_tokens,
    _route_contextual_money_answer,
    _supported_indicator_token_spans,
    _supported_strategy_family_token_spans,
    _token_sequence_spans,
)
from argus.agent_runtime.stages.interpret_internal.asset_resolution import (  # noqa: F401
    _USER_GROUNDED_CADENCE_SOURCES,
    _USER_GROUNDED_CAPITAL_SOURCES,
    STRATEGY_TURN_ACTS,
    _active_strategy_from_snapshot,
    _ambiguous_fields_from_resolution,
    _asset_resolution_source_for_canonicalization,
    _candidate_strategy_has_backtest_shape,
    _clear_incompatible_strategy_rule_state,
    _dedupe_ambiguous_fields,
    _dedupe_resolution_provenance,
    _dedupe_unsupported_constraints,
    _educational_turn_has_strategy_baggage,
    _extra_parameters_for_strategy_family,
    _filter_resolved_strategy_ambiguities,
    _fresh_complete_restatement_started_new_confirmation,
    _indicator_key_from_strategy,
    _indicator_parameters_from_strategy,
    _indicator_simplification_thesis,
    _indicator_supports_default_threshold_rule,
    _is_ambiguous_asset_resolution,
    _merge_non_empty_strategy_fields,
    _missing_fields_for_interpretation,
    _normalized_symbol,
    _optional_parameter_stage_patch,
    _pending_refinement_misroute_result_if_applicable,
    _provenance_field,
    _requested_asset_answer_candidates,
    _RequestedAssetCandidate,
    _strategy_canonical_asset_symbols,
    _strategy_field_is_executable,
    _strategy_field_provenance,
    _strategy_has_complete_no_rule_execution_shape,
    _strategy_has_content,
    _strategy_has_execution_anchor,
    _strategy_has_fresh_execution_detail,
    _strategy_has_unstructured_strategy_thesis,
    _strategy_has_user_grounded_cadence,
    _strategy_has_user_grounded_capital_amount,
    _strategy_is_semantically_confirmable,
    _strategy_looks_like_pending_artifact_edit,
    _strategy_route_expected,
    _strategy_supplies_contextual_rule_edit,
    _strategy_with_default_template_for_complete_no_rule_shape,
    _strategy_with_current_message_draft_only_indicator_text,
    _strategy_with_execution_defaults,
    _strategy_with_hidden_context_guard,
    _strategy_with_pending_resolution_affirmation,
    _strategy_with_separate_benchmark_symbol,
    _strategy_with_supported_indicator_simplification,
    _supported_timeframes,
    _unresolved_requested_asset_resolution,
    _unstructured_strategy_raw_value,
    _unsupported_constraints_from_resolution,
    _unsupported_strategy_logic_constraint,
    _unsupported_symbol_constraints,
    _validated_artifact_target,
    _without_invalid_symbols,
    _without_stale_requested_asset_rejection_constraints,
)
from argus.agent_runtime.stages.interpret_internal.confirmation_artifact_edits import (
    asset_edit_symbol_resolver as _asset_edit_symbol_resolver,
)
from argus.agent_runtime.stages.interpret_internal.contextual_merge import (  # noqa: F401
    CONTEXTUAL_EDIT_TURN_ACTS,
    _compact_asset_evidence_token,
    _contextual_date_range_value,
    _declared_strategy_family,
    _extra_parameters_without_unrequested_money_context,
    _has_complete_date_range,
    _is_cadence_word_asset_candidate,
    _is_field_owned_indicator_asset_candidate,
    _merge_contextual_extra_parameters,
    _merged_contextual_date_range,
    _message_has_cashtag_for_asset,
    _reset_contextual_strategy_definition,
    _should_preserve_pending_strategy_family,
    _should_preserve_prior_money_context,
    _strategy_asset_universe_is_field_owned_indicator_context,
    _strategy_fills_pending_execution_context,
    _strategy_supplies_execution_context,
    _strategy_uses_rule_or_indicator_context,
    _strategy_with_contextual_merge,
)
from argus.agent_runtime.stages.interpret_internal.interpreter_unavailable_continuity import (
    draft_only_indicator_interpretation_when_interpreter_unavailable as _draft_only_indicator_interpretation_when_interpreter_unavailable,
    pending_response_option_interpretation_from_typed_selection as _pending_response_option_interpretation_from_typed_selection,
    pending_response_option_when_interpreter_unavailable as _pending_response_option_when_interpreter_unavailable,
    planned_active_confirmation_edit_interpretation as _planned_active_confirmation_edit_interpretation,
    planned_pending_refinement_edit_interpretation as _planned_pending_refinement_edit_interpretation,
    structured_interpretation_has_complete_typed_asset_patch as _structured_interpretation_has_complete_typed_asset_patch,
    structured_interpretation_has_supported_artifact_assumption_edit as _structured_interpretation_has_supported_artifact_assumption_edit,
)
from argus.agent_runtime.stages.interpret_internal.latest_result_answer import (
    latest_result_answer_stage_result_if_applicable as _latest_result_answer_stage_result_if_applicable,
)
from argus.agent_runtime.stages.interpret_internal.pending_date_answer import (
    pending_date_answer_interpretation as _pending_date_answer_interpretation,
)
from argus.agent_runtime.stages.interpret_internal.date_contract import (  # noqa: F401
    _DATE_RANGE_EVIDENCE_KEYS,
    _changed_date_endpoint,
    _date_range_endpoints,
    _pending_date_edit_reuses_prior_date_range,
    _strategy_date_evidence_candidates,
    _strategy_date_range_needs_current_message_repair,
    _strategy_has_non_executable_timeframe_label,
)
from argus.agent_runtime.stages.interpret_internal.offline_recovery import (  # noqa: F401
    _LATEST_RESULT_SAVE_REQUESTED_REASON,
    _current_setup_phrase,
    _latest_result_save_requested,
    _offline_interpreter_unavailable_result,
    _offline_recovery_message,
    _pending_assumption_edit_was_not_applied,
    _strategies_enabled,
)
from argus.agent_runtime.stages.interpret_internal.route_repair import (  # noqa: F401
    _repair_fresh_restatement_route_when_pending_need_is_active,
    _repair_retry_route_when_pending_need_is_active,
)
from argus.agent_runtime.stages.interpret_internal.shared import (  # noqa: F401
    _field_base,
    _should_preserve_prior_asset_context,
    _strategy_supplies_executable_rule_edit,
    _supported_experiment_fact_packet,
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
from argus.agent_runtime.stages.recovery_composer import (
    compose_active_confirmation_interpreter_recovery,
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
    dedupe_resolution_provenance_items,
)
from argus.agent_runtime.strategy_contract import (
    SUPPORTED_STRATEGY_TYPES,
    canonical_strategy_type,
    display_strategy_type,
    executable_strategy_type,
    has_partial_explicit_date_range,
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
from argus.domain.backtesting.config import (
    AssetClass as BacktestAssetClass,
)
from argus.domain.backtesting.config import (
    default_benchmark as default_backtest_benchmark,
)
from argus.domain.indicators import (
    EXECUTABLE_INDICATORS,
    IndicatorExecutionSpec,
    executable_indicator_spec,
    normalize_indicator_parameters,
)
from argus.domain.market_data import resolve_asset
from argus.llm.openrouter import invoke_openrouter_chat_completion
from argus.nlp.natural_time import (
    date_range_evidence_has_explicit_endpoints,
    dateparser_languages_for_user_language,
    parse_date_text,
    resolve_date_range_endpoint_patch,
    resolve_date_range_intent,
    resolve_date_range_text,
)
from loguru import logger

_DEFAULT_RESOLVE_ASSET = resolve_asset
_BACKTEST_ASSET_CLASSES = frozenset(get_args(BacktestAssetClass))


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
    logger.debug(
        "Interpret stage started",
        language=user.language_preference,
        selected_thread_metadata_keys=sorted((selected_thread_metadata or {}).keys()),
    )
    capability_contract = build_default_capability_contract()
    snapshot = normalize_task_snapshot(latest_task_snapshot)
    structured_action_result = _structured_action_stage_result_if_applicable(
        state=state,
        snapshot=snapshot,
        selected_thread_metadata=selected_thread_metadata or {},
        language=user.language_preference,
    )
    if structured_action_result is not None:
        return structured_action_result
    selected_metadata = dict(selected_thread_metadata or {})
    if structured_interpreter is None:
        return await _interpreter_unavailable_result(
            state=state,
            user=user,
            snapshot=snapshot,
            current_user_message=state.current_user_message,
            capability_contract=capability_contract,
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
        logger.debug("Interpret stage structured interpreter returned no result")
        return await _interpreter_unavailable_result(
            state=state,
            user=user,
            snapshot=snapshot,
            current_user_message=state.current_user_message,
            capability_contract=capability_contract,
            selected_thread_metadata=selected_metadata,
        )
    pending_response_option_interpretation = (
        _pending_response_option_interpretation_from_typed_selection(
            state=state,
            user=user,
            snapshot=snapshot,
            current_user_message=state.current_user_message,
            selected_thread_metadata=selected_metadata,
        )
    )
    if pending_response_option_interpretation is not None:
        interpretation = pending_response_option_interpretation
    logger.debug(
        "Interpret stage structured interpreter completed",
        intent=interpretation.intent,
        semantic_turn_act=interpretation.semantic_turn_act,
        requires_clarification=interpretation.requires_clarification,
        missing_required_fields=interpretation.missing_required_fields,
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
    logger.debug(
        "Interpret stage post-LLM repair started",
        intent=interpretation.intent,
        semantic_turn_act=interpretation.semantic_turn_act,
    )
    interpretation = _repair_retry_route_when_pending_need_is_active(
        interpretation=interpretation,
        snapshot=snapshot,
        selected_thread_metadata=selected_thread_metadata,
    )
    interpretation = _repair_fresh_restatement_route_when_pending_need_is_active(
        interpretation=interpretation,
        snapshot=snapshot,
        selected_thread_metadata=selected_thread_metadata,
    )
    interpretation = _repair_pending_date_answer_route_when_pending_need_is_active(
        interpretation=interpretation,
        current_user_message=state.current_user_message,
        language=user.language_preference,
        snapshot=snapshot,
        selected_thread_metadata=selected_thread_metadata,
    )
    interpretation = _repair_pending_date_answer_noop_from_current_message(
        interpretation=interpretation,
        current_user_message=state.current_user_message,
        language=user.language_preference,
        snapshot=snapshot,
        selected_thread_metadata=selected_thread_metadata,
    )
    route_suppression_reason_codes: list[str] = []
    expects_strategy_route = _strategy_route_expected(
        intent=interpretation.intent,
        semantic_turn_act=interpretation.semantic_turn_act,
    ) or (
        interpretation.semantic_turn_act != "result_followup"
        and _candidate_strategy_has_backtest_shape(
            interpretation.candidate_strategy_draft
        )
    )
    educational_turn_has_strategy_baggage = _educational_turn_has_strategy_baggage(
        interpretation=interpretation,
        expects_strategy_route=expects_strategy_route,
    )
    if educational_turn_has_strategy_baggage:
        expects_strategy_route = False
        route_suppression_reason_codes.append("educational_strategy_route_suppressed")
        interpretation = interpretation.model_copy(
            update={
                "intent": "conversation_followup",
                "task_relation": "continue",
                "requires_clarification": False,
                "candidate_strategy_draft": StrategySummary(),
                "missing_required_fields": [],
                "ambiguous_fields": [],
                "unsupported_constraints": [],
                "semantic_turn_act": "educational_question",
            },
        )
    planned_active_confirmation_edit = (
        await _planned_active_confirmation_edit_for_typed_llm_assumption_edit(
            state=state,
            user=user,
            snapshot=snapshot,
            selected_thread_metadata=selected_thread_metadata,
            interpretation=interpretation,
            capability_contract=capability_contract,
        )
    )
    if planned_active_confirmation_edit is not None:
        return planned_active_confirmation_edit
    incoming_strategy = _strategy_with_contextual_merge(
        strategy=interpretation.candidate_strategy_draft,
        snapshot=snapshot,
        selected_thread_metadata=selected_thread_metadata,
        semantic_turn_act=interpretation.semantic_turn_act,
        task_relation=interpretation.task_relation,
        current_user_message=state.current_user_message,
        reason_codes=interpretation.reason_codes,
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
    typed_pending_option_applied = (
        "pending_response_option_selected" in interpretation.reason_codes
    )
    supported_indicator_simplification_applied = False
    if not typed_pending_option_applied:
        incoming_strategy, supported_indicator_simplification_applied = (
            _strategy_with_supported_indicator_simplification(
                strategy=incoming_strategy,
                snapshot=snapshot,
                selected_thread_metadata=selected_thread_metadata,
                semantic_turn_act=interpretation.semantic_turn_act,
                task_relation=interpretation.task_relation,
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
    incoming_strategy, requested_asset_answer_applied = (
        _strategy_with_requested_asset_answer_resolution(
            strategy=incoming_strategy,
            explicit_strategy=interpretation.candidate_strategy_draft,
            prior_strategy=_active_strategy_from_snapshot(snapshot),
            selected_thread_metadata=selected_thread_metadata,
            current_user_message=state.current_user_message,
            semantic_turn_act=interpretation.semantic_turn_act,
            pending_resolution_applied=pending_resolution_applied,
        )
    )
    if requested_asset_answer_applied:
        unsupported_constraints = _without_stale_requested_asset_rejection_constraints(
            interpretation.unsupported_constraints,
            strategy=incoming_strategy,
        )
        expects_strategy_route = True
        interpretation = interpretation.model_copy(
            update={
                "intent": "backtest_execution",
                "task_relation": "continue",
                "requires_clarification": False,
                "assistant_response": None,
                "semantic_turn_act": "answer_pending_need",
                "missing_required_fields": [],
                "unsupported_constraints": unsupported_constraints,
                "reason_codes": [
                    *interpretation.reason_codes,
                    "requested_asset_answer_route_repaired",
                    *(
                        ["stale_requested_asset_rejection_removed"]
                        if len(unsupported_constraints)
                        < len(interpretation.unsupported_constraints)
                        else []
                    ),
                ],
            }
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
    if expects_strategy_route and state.context_hints:
        incoming_strategy.resolution_provenance = _dedupe_resolution_provenance(
            [*incoming_strategy.resolution_provenance, *state.context_hints]
        )
    strategy = (
        _strategy_with_execution_defaults(
            _canonicalized_strategy(
                incoming_strategy,
                current_user_message=state.current_user_message,
                selected_thread_metadata=selected_thread_metadata,
            )
        )
        if expects_strategy_route
        else incoming_strategy
    )
    benchmark_reason_codes: list[str] = []
    asset_repair_reason_codes: list[str] = []
    if expects_strategy_route:
        prior_strategy = _active_strategy_from_snapshot(snapshot)
        strategy, unstated_benchmark_reason_codes = (
            _strategy_with_unstated_benchmark_guard(
                strategy=strategy,
                prior_strategy=prior_strategy,
            )
        )
        benchmark_reason_codes.extend(unstated_benchmark_reason_codes)
        strategy, asset_repair_reason_codes = (
            _strategy_with_benchmark_owner_asset_repair(strategy)
        )
    if expects_strategy_route:
        prior_strategy = _active_strategy_from_snapshot(snapshot)
        strategy, interpretation = _strategy_with_current_message_run_field_contract(
            strategy=strategy,
            interpretation=interpretation,
            prior_strategy=prior_strategy,
            current_user_message=state.current_user_message,
            supported_timeframes=_supported_timeframes(capability_contract),
            language=user.language_preference,
        )
    shape_default_reason_codes: list[str] = []
    if expects_strategy_route:
        strategy, shape_default_reason_codes = (
            _strategy_with_default_template_for_complete_no_rule_shape(strategy)
        )
    if expects_strategy_route:
        strategy, separate_benchmark_reason_codes = _strategy_with_separate_benchmark_symbol(
            strategy
        )
        strategy, validated_benchmark_reason_codes = (
            _strategy_with_validated_benchmark_symbol(strategy)
        )
        strategy, default_benchmark_reason_codes = _strategy_with_default_benchmark(
            strategy
        )
        benchmark_reason_codes = [
            *benchmark_reason_codes,
            *separate_benchmark_reason_codes,
            *validated_benchmark_reason_codes,
            *default_benchmark_reason_codes,
        ]
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
    if expects_strategy_route:
        strategy, draft_only_indicator_reason_codes = (
            _strategy_with_current_message_draft_only_indicator_text(
                strategy=strategy,
                interpretation=interpretation,
                current_user_message=state.current_user_message,
            )
        )
        if draft_only_indicator_reason_codes:
            interpretation = interpretation.model_copy(
                update={
                    "requires_clarification": True,
                    "assistant_response": None,
                    "reason_codes": list(
                        dict.fromkeys(
                            [
                                *interpretation.reason_codes,
                                *draft_only_indicator_reason_codes,
                            ]
                        )
                    ),
                }
            )
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
    if requested_asset_answer_applied:
        ambiguous_fields = []
    elif pending_resolution_applied:
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
    missing_required_fields = executable_artifact_patch_missing_fields(
        strategy=strategy,
        missing_fields=missing_required_fields,
    )
    unsupported_constraints = relevant_unsupported_constraints_for_artifact_patch(
        strategy=strategy,
        constraints=unsupported_constraints,
    )
    unsupported_strategy_logic_owns_pending_need = any(
        constraint.category == "unsupported_strategy_logic"
        for constraint in unsupported_constraints
    )
    if (
        unsupported_strategy_logic_owns_pending_need
        and "draft_only_indicator_text_preserved" in interpretation.reason_codes
    ):
        missing_required_fields = []
    pending_date_edit_reason_codes: list[str] = []
    if _pending_date_edit_reuses_prior_date_range(
        strategy=strategy,
        snapshot=snapshot,
        selected_thread_metadata=selected_thread_metadata,
        semantic_turn_act=interpretation.semantic_turn_act,
    ):
        missing_required_fields = list(
            dict.fromkeys([*missing_required_fields, "date_range"])
        )
        pending_date_edit_reason_codes.append("pending_date_edit_noop_rejected")
        interpretation = interpretation.model_copy(
            update={
                "requires_clarification": True,
                "assistant_response": None,
            }
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
    post_validation_reason_codes = [
        *benchmark_reason_codes,
        *(
            ["fresh_complete_restatement_started_new_confirmation"]
            if _fresh_complete_restatement_started_new_confirmation(
                interpretation=interpretation,
                selected_thread_metadata=selected_thread_metadata,
                expects_strategy_route=expects_strategy_route,
                requires_clarification=requires_clarification,
                ambiguous_fields=ambiguous_fields,
                unsupported_constraints=unsupported_constraints,
                missing_required_fields=missing_required_fields,
            )
            else []
        ),
    ]
    decision = InterpretDecision(
        intent=interpretation.intent,
        task_relation=interpretation.task_relation,
        requires_clarification=requires_clarification,
        user_goal_summary=interpretation.user_goal_summary,
        detected_user_language=interpretation.detected_user_language,
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
            *(
                ["requested_asset_answer_checked_provider"]
                if requested_asset_answer_applied
                else []
            ),
            *shape_default_reason_codes,
            *asset_repair_reason_codes,
            *integrity_report.reason_codes,
            *constraint_filter_reason_codes,
            *ambiguity_filter_reason_codes,
            *artifact_target_reason_codes,
            *hidden_context_guard_reason_codes,
            *pending_date_edit_reason_codes,
            *post_validation_reason_codes,
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
        result_followup_fact_key=interpretation.result_followup_fact_key,
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
        language=user.language_preference,
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
    latest_result_fact_answer = await _latest_result_answer_stage_result_if_applicable(
        decision=decision,
        snapshot=snapshot,
        current_user_message=state.current_user_message,
        language=user.language_preference,
    )
    if latest_result_fact_answer is not None:
        return latest_result_fact_answer
    pending_refinement_result = _pending_refinement_misroute_result_if_applicable(
        decision=decision,
        snapshot=snapshot,
    )
    if pending_refinement_result is not None:
        return pending_refinement_result
    private_alpha_save_result = await _private_alpha_save_request_result_if_applicable(
        user=user,
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
        language=user.language_preference,
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
        language=user.language_preference,
    )
    if context_answer is not None:
        return StageResult(
            outcome="ready_to_respond",
            decision=decision,
            stage_patch={"assistant_response": context_answer},
        )
    supported_strategy_answer = await _supported_strategy_education_repair_if_needed(
        semantic_turn_act=interpretation.semantic_turn_act,
        assistant_response=interpretation.assistant_response,
        current_user_message=state.current_user_message,
        capability_contract=capability_contract,
        language=user.language_preference,
    )
    if supported_strategy_answer is not None:
        return StageResult(
            outcome="ready_to_respond",
            decision=decision,
            stage_patch={"assistant_response": supported_strategy_answer},
        )
    capability_answer = await _capability_answer_if_applicable(
        focus=interpretation.capability_question_focus,
        semantic_turn_act=interpretation.semantic_turn_act,
        expects_strategy_route=expects_strategy_route,
        requires_clarification=requires_clarification,
        assistant_response=interpretation.assistant_response,
        current_user_message=state.current_user_message,
        capability_contract=capability_contract,
        language=user.language_preference,
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
        language=user.language_preference,
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
        language=user.language_preference,
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
        language=user.language_preference,
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
        stage_patch = dict(optional_parameter_stage_patch)
        # Preserve the artifact-edit planner's honesty note (a mixed
        # supported/unsupported edit) alongside the confirmation card, so it is
        # not silently dropped. Scoped to the edit-planner reason code so spurious
        # clarifications overridden to a confirmation on other routes stay
        # suppressed; clean edits leave assistant_response None -> no message.
        if (
            interpretation.assistant_response
            and "artifact_assumption_edit_planned"
            in (interpretation.reason_codes or [])
        ):
            stage_patch["assistant_response"] = interpretation.assistant_response
        return StageResult(
            outcome="ready_for_confirmation",
            decision=decision,
            stage_patch=stage_patch,
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


def _strategy_with_current_message_run_field_contract(
    *,
    strategy: StrategySummary,
    interpretation: StructuredInterpretation,
    prior_strategy: StrategySummary | None,
    current_user_message: str,
    supported_timeframes: tuple[str, ...],
    language: str,
) -> tuple[StrategySummary, StructuredInterpretation]:
    del current_user_message
    raw_date_range = _explicit_date_range_from_strategy_for_repair(
        strategy,
        language=language,
    )
    date_range, date_endpoint_patch_applied = (
        _complete_current_message_date_endpoint_patch(
            strategy=strategy,
            date_range=raw_date_range,
            prior_date_range=(
                prior_strategy.date_range if prior_strategy is not None else None
            ),
            language=language,
        )
    )
    updated = strategy.model_copy(deep=True)
    changed = False
    repaired_field_bases: set[str] = set()
    repair_reason_codes = ["current_message_run_field_contract_repair"]
    if date_endpoint_patch_applied:
        repair_reason_codes.append("structured_date_endpoint_patch_applied")
        logger.debug(
            "Interpret stage date endpoint patch applied",
            strategy_type=strategy.strategy_type,
        )
    if (
        date_range is not None
        and not has_partial_explicit_date_range(date_range)
        and _strategy_date_range_needs_current_message_repair(
            strategy=updated,
            interpretation=interpretation,
            current_date_range=date_range,
        )
    ):
        updated.date_range = date_range
        changed = True
        repaired_field_bases.add("date_range")
        logger.debug(
            "Interpret stage date range repaired from temporal contract",
            strategy_type=strategy.strategy_type,
        )
    if (
        _strategy_has_non_executable_timeframe_label(
            updated,
            supported_timeframes=supported_timeframes,
        )
    ):
        updated.timeframe = None
        changed = True
    if not changed:
        return strategy, interpretation

    missing_required_fields = [
        field
        for field in interpretation.missing_required_fields
        if str(field).split("[", 1)[0] not in repaired_field_bases
    ]
    ambiguous_fields = [
        field
        for field in interpretation.ambiguous_fields
        if field.field_name.split("[", 1)[0] not in repaired_field_bases
    ]
    unsupported_constraints = list(interpretation.unsupported_constraints)
    requires_clarification = interpretation.requires_clarification
    assistant_response = interpretation.assistant_response
    if (
        not missing_required_fields
        and not ambiguous_fields
        and not unsupported_constraints
    ):
        requires_clarification = False
        assistant_response = None
    repaired = interpretation.model_copy(
        update={
            "requires_clarification": requires_clarification,
            "assistant_response": assistant_response,
            "missing_required_fields": missing_required_fields,
            "ambiguous_fields": ambiguous_fields,
            "unsupported_constraints": unsupported_constraints,
            "reason_codes": list(
                dict.fromkeys(
                    [
                        *interpretation.reason_codes,
                        *repair_reason_codes,
                    ]
                )
            ),
        }
    )
    return updated, repaired


def _complete_current_message_date_endpoint_patch(
    *,
    strategy: StrategySummary,
    date_range: dict[str, str] | None,
    prior_date_range: Any = None,
    language: str | None = None,
) -> tuple[dict[str, str] | None, bool]:
    if date_range is None:
        return date_range, False
    current_date = date.today()
    rolling_patch = _rolling_window_range_from_endpoint_patch(
        strategy.extra_parameters.get("date_range_intent"),
        date_range=date_range,
        prior_date_range=prior_date_range,
        date_range_raw_text=strategy.extra_parameters.get("date_range_raw_text"),
        language=language,
        today=current_date,
    )
    if rolling_patch is not None:
        return rolling_patch, True
    if not has_partial_explicit_date_range(date_range):
        return date_range, False
    prior = strategy.date_range
    if not isinstance(prior, dict):
        return date_range, False
    start = date_range.get("start") or prior.get("start") or prior.get("from")
    end = date_range.get("end") or prior.get("end") or prior.get("to")
    if not start or not end:
        return date_range, False
    return {"start": str(start), "end": str(end)}, True


def _iso_date_value(value: Any) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def _rolling_window_range_from_endpoint_patch(
    date_range_intent: Any,
    *,
    date_range: dict[str, str] | None = None,
    prior_date_range: Any = None,
    date_range_raw_text: Any = None,
    language: str | None = None,
    today: date | None = None,
) -> dict[str, str] | None:
    if not isinstance(date_range_intent, dict):
        return None
    base_intent = date_range_intent.get("base_intent")
    if not isinstance(base_intent, dict):
        return None
    endpoint_patch = _endpoint_patch_with_inferred_endpoint(
        date_range_intent,
        date_range=date_range,
        prior_date_range=prior_date_range,
        date_range_raw_text=date_range_raw_text,
        language=language,
        today=today,
    )
    resolved = resolve_date_range_endpoint_patch(
        base_intent,
        endpoint_patch,
        today=today,
    )
    return resolved.payload if resolved is not None else None


def _endpoint_patch_with_inferred_endpoint(
    date_range_intent: dict[str, Any],
    *,
    date_range: dict[str, str] | None,
    prior_date_range: Any,
    date_range_raw_text: Any,
    language: str | None,
    today: date | None,
) -> dict[str, Any]:
    endpoint = str(date_range_intent.get("endpoint") or "").strip()
    if endpoint in {"start", "end"}:
        if date_range_intent.get(endpoint) not in (None, "", [], {}):
            return date_range_intent
        endpoint_value = _endpoint_date_from_bounded_text(
            date_range_raw_text,
            language=language,
            today=today,
        )
        if endpoint_value is None:
            return date_range_intent
        patch = dict(date_range_intent)
        patch[endpoint] = endpoint_value
        return patch
    inferred = _changed_date_endpoint(
        date_range=date_range,
        prior_date_range=prior_date_range,
    )
    if inferred is None:
        return date_range_intent
    endpoint, value = inferred
    patch = dict(date_range_intent)
    patch["endpoint"] = endpoint
    patch[endpoint] = value
    return patch


def _endpoint_date_from_bounded_text(
    value: Any,
    *,
    language: str | None,
    today: date | None,
) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    parsed = parse_date_text(
        text,
        today=today,
        languages=dateparser_languages_for_user_language(language),
        prefer_dates_from="past",
    )
    return parsed.isoformat() if parsed is not None else None


def _explicit_date_range_from_strategy_for_repair(
    strategy: StrategySummary,
    *,
    language: str | None,
) -> dict[str, str] | None:
    current_date = date.today()
    intent = strategy.extra_parameters.get("date_range_intent")
    intent_kind = (
        str(intent.get("kind") or "").strip() if isinstance(intent, dict) else ""
    )
    bounded_evidence_range = (
        None
        if intent_kind == "endpoint_patch"
        else _date_range_from_strategy_bounded_evidence(
            strategy,
            language=language,
            today=current_date,
        )
    )
    intent_range: dict[str, str] | None = None
    if isinstance(intent, dict):
        resolved = resolve_date_range_intent(intent, today=current_date)
        if resolved is not None:
            intent_range = resolved.payload
    if intent_range is not None and _date_range_intent_is_explicit_user_range(
        strategy,
        intent,
    ):
        return intent_range
    if bounded_evidence_range is not None:
        if intent_range is None:
            return bounded_evidence_range
        if _date_range_endpoints(bounded_evidence_range) != _date_range_endpoints(
            intent_range
        ):
            return bounded_evidence_range
    if intent_range is not None:
        return intent_range
    if isinstance(strategy.date_range, dict):
        payload = {
            key: str(value)
            for key in ("start", "end")
            if (value := strategy.date_range.get(key)) not in (None, "")
        }
        return payload or None
    return None


def _date_range_intent_is_explicit_user_range(
    strategy: StrategySummary,
    intent: Any,
) -> bool:
    if not isinstance(intent, dict):
        return False
    if str(intent.get("kind") or "").strip() != "explicit_range":
        return False
    if intent.get("start") in (None, "", [], {}) or intent.get("end") in (
        None,
        "",
        [],
        {},
    ):
        return False
    field_provenance = strategy.extra_parameters.get("field_provenance")
    if not isinstance(field_provenance, dict):
        return False
    return field_provenance.get("date_range") == "explicit_user"


def _date_range_from_strategy_bounded_evidence(
    strategy: StrategySummary,
    *,
    language: str | None,
    today: date,
) -> dict[str, str] | None:
    candidates = _strategy_date_evidence_candidates(strategy)
    if not candidates:
        return None
    languages = dateparser_languages_for_user_language(language)
    for candidate in candidates:
        resolved = resolve_date_range_text(candidate, today=today, languages=languages)
        if resolved is None:
            continue
        if not date_range_evidence_has_explicit_endpoints(resolved.evidence_spans):
            continue
        return resolved.payload
    return None


def _repair_pending_date_answer_route_when_pending_need_is_active(
    *,
    interpretation: StructuredInterpretation,
    current_user_message: str,
    language: str | None,
    snapshot: TaskSnapshot | None,
    selected_thread_metadata: dict[str, Any],
) -> StructuredInterpretation:
    requested_field = _field_base(
        str(selected_thread_metadata.get("requested_field") or "")
    )
    if requested_field != "date_range":
        return interpretation
    last_stage_outcome = str(selected_thread_metadata.get("last_stage_outcome") or "")
    if last_stage_outcome and last_stage_outcome != "await_user_reply":
        return interpretation
    candidate_endpoints = _date_range_endpoints(
        interpretation.candidate_strategy_draft.date_range
    )
    if interpretation.candidate_strategy_draft.date_range not in (None, "", [], {}):
        return interpretation
    if candidate_endpoints is not None and any(candidate_endpoints):
        return interpretation
    if (
        interpretation.semantic_turn_act != "answer_pending_need"
        and not interpretation.requires_clarification
        and _candidate_strategy_has_backtest_shape(interpretation.candidate_strategy_draft)
    ):
        return interpretation
    repaired = _pending_date_answer_interpretation(
        current_user_message=current_user_message,
        language=language,
        snapshot=snapshot,
        selected_thread_metadata=selected_thread_metadata,
        today=date.today(),
        reason_code=(
            "pending_date_answer_current_message_repaired"
            if interpretation.semantic_turn_act == "answer_pending_need"
            else "pending_date_answer_route_repaired"
        ),
    )
    if repaired is None:
        return interpretation
    return repaired


def _repair_pending_date_answer_noop_from_current_message(
    *,
    interpretation: StructuredInterpretation,
    current_user_message: str,
    language: str | None,
    snapshot: TaskSnapshot | None,
    selected_thread_metadata: dict[str, Any],
) -> StructuredInterpretation:
    if interpretation.semantic_turn_act != "answer_pending_need":
        return interpretation
    if interpretation.requires_clarification:
        return interpretation
    requested_field = _field_base(
        str(selected_thread_metadata.get("requested_field") or "")
    )
    if requested_field != "date_range":
        return interpretation
    last_stage_outcome = str(selected_thread_metadata.get("last_stage_outcome") or "")
    if last_stage_outcome and last_stage_outcome != "await_user_reply":
        return interpretation
    prior = _active_strategy_from_snapshot(snapshot)
    if prior is None:
        return interpretation
    prior_endpoints = _date_range_endpoints(prior.date_range)
    if prior_endpoints is None or not all(prior_endpoints):
        return interpretation
    candidate = interpretation.candidate_strategy_draft
    candidate_endpoints = _date_range_endpoints(candidate.date_range)
    if candidate_endpoints is not None and candidate_endpoints != prior_endpoints:
        return interpretation
    text = current_user_message.strip()
    if not text:
        return interpretation
    resolved_range = resolve_date_range_text(
        text,
        today=date.today(),
        languages=dateparser_languages_for_user_language(language),
    )
    if resolved_range is None:
        return interpretation
    repaired_date_range = resolved_range.payload
    if _date_range_endpoints(repaired_date_range) == prior_endpoints:
        return interpretation
    extra_parameters = dict(candidate.extra_parameters)
    evidence_spans = extra_parameters.get("evidence_spans")
    if not isinstance(evidence_spans, dict):
        evidence_spans = {}
    extra_parameters.update(
        {
            "date_range_raw_text": text,
            "date_range_intent": {
                "kind": "explicit_range",
                "start": repaired_date_range["start"],
                "end": repaired_date_range["end"],
                "confidence": 0.9,
                "evidence": text,
            },
            "evidence_spans": {
                **evidence_spans,
                "date_range": text,
            },
        }
    )
    return interpretation.model_copy(
        update={
            "candidate_strategy_draft": candidate.model_copy(
                update={
                    "date_range": repaired_date_range,
                    "extra_parameters": extra_parameters,
                }
            ),
            "reason_codes": [
                *interpretation.reason_codes,
                "pending_date_answer_current_message_repaired",
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
    language: str,
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
        language=language,
    )
    if composed:
        return composed
    return recovery_message("capability_answer_unavailable", language=language)


async def _context_curiosity_answer_if_applicable(
    *,
    focus: ContextQuestionFocus | None,
    semantic_turn_act: SemanticTurnAct | None,
    expects_strategy_route: bool,
    requires_clarification: bool,
    assistant_response: str | None,
    current_user_message: str,
    artifact_target: ArtifactTarget | None,
    language: str,
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
        language=language,
    )
    if composed:
        return composed
    return assistant_response or _context_curiosity_recovery_answer(
        focus,
        language=language,
    )


async def _compose_natural_capability_answer(
    *,
    focus: CapabilityQuestionFocus,
    current_user_message: str,
    capability_contract: Any,
    language: str = "en",
) -> str | None:
    fact_packet = capability_fact_packet(
        focus=focus,
        contract=capability_contract,
    )
    messages = [
        {
            "role": "system",
            "content": (
                "You are Argus, a chat-first investing experimentation assistant. "
                f"{response_language_instruction(language)} "
                "Answer in warm, plain language. Keep it concise and useful for a "
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
        return None
    except Exception:
        return None


async def _supported_strategy_education_repair_if_needed(
    *,
    semantic_turn_act: SemanticTurnAct | None,
    assistant_response: str | None,
    current_user_message: str,
    capability_contract: Any,
    language: str,
) -> str | None:
    if (
        semantic_turn_act != "educational_question"
        or not assistant_response
        or not _answer_contradicts_supported_strategy_families(assistant_response)
    ):
        return None
    composed = await _compose_natural_capability_answer(
        focus="supported_strategies",
        current_user_message=current_user_message,
        capability_contract=capability_contract,
        language=language,
    )
    return composed or recovery_message("capability_answer_unavailable", language=language)


async def _compose_natural_context_curiosity_answer(
    *,
    focus: ContextQuestionFocus,
    current_user_message: str,
    artifact_target: ArtifactTarget | None,
    language: str = "en",
) -> str | None:
    fact_packet = _context_curiosity_fact_packet(focus)
    live_facts = await _live_context_curiosity_facts(focus)
    if focus == "market_movers" and not live_facts.packet_symbols:
        return _packet_grounded_context_recovery_answer(
            focus=focus,
            live_facts=live_facts,
            language=language,
        )
    provenance_rule = (
        "If you use visible artifact context, say so naturally with phrases like "
        "'from this result' or 'from this confirmation'."
        if artifact_target in {"latest_result", "active_confirmation", "pending_refinement"}
        else "Do not imply you used a prior result or hidden memory."
    )
    messages = [
        {
            "role": "system",
            "content": (
                "You are Argus, a chat-first investing experimentation assistant. "
                f"{response_language_instruction(language)} "
                "Answer broad market or macro curiosity in warm, plain language. "
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
            language=language,
        )
    except Exception:
        return None


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


async def _unanchored_strategy_route_answer_if_needed(
    *,
    reason_codes: list[str],
    expects_strategy_route: bool,
    requires_clarification: bool,
    current_user_message: str,
    capability_contract: Any,
    language: str,
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
        language=language,
    )
    if composed:
        return composed
    return _llm_composition_unavailable_recovery_answer(language=language)


async def _compose_unanchored_strategy_recovery_answer(
    *,
    current_user_message: str,
    capability_contract: Any,
    language: str = "en",
) -> str | None:
    fact_packet = capability_fact_packet(
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
                f"yet. Do not create a draft. {response_language_instruction(language)} "
                "Answer in warm, plain language. Give "
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
    language: str,
) -> str | None:
    if (
        semantic_turn_act != "educational_question"
        or expects_strategy_route
        or requires_clarification
        or assistant_response
    ):
        return None
    composed = await _compose_general_educational_answer(
        current_user_message=current_user_message,
        language=language,
    )
    if composed:
        return composed
    return _llm_composition_unavailable_recovery_answer(language=language)


async def _unhandled_response_recovery_if_needed(
    *,
    semantic_turn_act: SemanticTurnAct | None,
    expects_strategy_route: bool,
    requires_clarification: bool,
    assistant_response: str | None,
    current_user_message: str,
    language: str,
) -> str | None:
    if expects_strategy_route or requires_clarification or assistant_response:
        return None
    composed = await _compose_unhandled_conversation_answer(
        semantic_turn_act=semantic_turn_act,
        current_user_message=current_user_message,
        language=language,
    )
    if composed:
        return composed
    return _llm_composition_unavailable_recovery_answer(language=language)


async def _compose_general_educational_answer(
    *,
    current_user_message: str,
    language: str = "en",
) -> str | None:
    messages = [
        {
            "role": "system",
            "content": (
                "You are Argus, a chat-first investing experimentation assistant. "
                "The structured interpreter identified this as an educational or "
                "broad investing-curiosity turn but did not produce user-facing prose. "
                f"{response_language_instruction(language)} "
                "Answer in warm, plain language. Start with useful context, keep it "
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
    language: str = "en",
) -> str | None:
    messages = [
        {
            "role": "system",
            "content": (
                "You are Argus, a chat-first investing experimentation assistant. "
                "The runtime has no executable strategy, no clarification contract, "
                "and no user-facing answer for this turn. "
                f"{response_language_instruction(language)} "
                "Recover by answering in warm, plain language. Do not use report tone. "
                "Do not name data "
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


def _strategy_with_requested_asset_answer_resolution(
    *,
    strategy: StrategySummary,
    explicit_strategy: StrategySummary,
    prior_strategy: StrategySummary | None,
    selected_thread_metadata: dict[str, Any],
    current_user_message: str,
    semantic_turn_act: str | None,
    pending_resolution_applied: bool,
) -> tuple[StrategySummary, bool]:
    if pending_resolution_applied:
        return strategy, False
    requested_field = _field_base(
        str(selected_thread_metadata.get("requested_field") or "")
    )
    if requested_field != "asset_universe":
        return strategy, False
    del semantic_turn_act
    asset_candidates = _requested_asset_answer_candidates(
        explicit_strategy=explicit_strategy,
        current_user_message=current_user_message,
    )
    if not asset_candidates:
        return strategy, False
    prior_symbols = _strategy_canonical_asset_symbols(prior_strategy)
    fallback_resolution: AssetResolution | None = None
    resolution: AssetResolution | None = None
    for asset_candidate in asset_candidates:
        if (
            not asset_candidate.from_user_answer
            and _normalized_symbol(asset_candidate.text) in prior_symbols
        ):
            continue
        candidate_resolution = _resolve_asset_candidate_safely(
            asset_candidate.text,
            field="asset_universe[0]",
            source=asset_candidate.source,
        )
        if candidate_resolution is None:
            if fallback_resolution is None and asset_candidate.from_user_answer:
                fallback_resolution = _unresolved_requested_asset_resolution(
                    asset_candidate.text,
                    field="asset_universe[0]",
                    source=asset_candidate.source,
                )
            continue
        if (
            not asset_candidate.from_user_answer
            and candidate_resolution.asset is not None
            and candidate_resolution.asset.canonical_symbol in prior_symbols
        ):
            continue
        if candidate_resolution.status == "resolved" and candidate_resolution.asset is not None:
            resolution = candidate_resolution
            break
        if fallback_resolution is None:
            fallback_resolution = candidate_resolution
    if resolution is None:
        resolution = fallback_resolution
    if resolution is None:
        return strategy, False
    updated = (prior_strategy or strategy).model_copy(deep=True)
    existing_provenance: list[ResolutionProvenance | dict[str, Any]] = []
    for item in updated.resolution_provenance:
        if _field_base(_provenance_field(item)) != "asset_universe":
            existing_provenance.append(item)
    updated.resolution_provenance = _dedupe_resolution_provenance(
        [*existing_provenance, resolution.provenance]
    )
    if resolution.status == "resolved" and resolution.asset is not None:
        updated.asset_universe = [resolution.asset.canonical_symbol]
        updated.asset_class = resolution.asset.asset_class
    else:
        updated.asset_universe = []
        updated.asset_class = None
    return updated, True


def _resolve_asset_candidate_safely(
    query: str,
    *,
    field: str,
    source: ResolutionSource,
    asset_class_hint: str | None = None,
) -> AssetResolution | None:
    try:
        return _resolve_asset_candidate(
            query,
            field=field,
            source=source,
            asset_class_hint=asset_class_hint,
        )
    except ValueError:
        return None


async def _interpreter_unavailable_result(
    *,
    state: RunState,
    user: UserState,
    snapshot: TaskSnapshot | None = None,
    current_user_message: str = "",
    capability_contract: Any,
    selected_thread_metadata: dict[str, Any] | None = None,
) -> StageResult:
    selected_metadata = selected_thread_metadata or {}
    planned_refinement_edit = await _planned_pending_refinement_edit_interpretation(
        snapshot=snapshot,
        current_user_message=current_user_message,
        selected_thread_metadata=selected_metadata,
        resolve_asset_candidate=_resolve_asset_candidate_safely,
        plan_artifact_assumption_edit_fn=plan_artifact_assumption_edit,
    )
    if planned_refinement_edit is not None:
        return await _stage_result_from_interpretation(
            state=state,
            user=user,
            snapshot=snapshot,
            interpretation=planned_refinement_edit,
            capability_contract=capability_contract,
            selected_thread_metadata=selected_metadata,
        )
    result_followup = await _latest_result_followup_when_interpreter_unavailable(
        user=user,
        snapshot=snapshot,
        current_user_message=current_user_message,
    )
    if result_followup is not None:
        return result_followup
    pending_option = _pending_response_option_when_interpreter_unavailable(
        state=state,
        user=user,
        snapshot=snapshot,
        current_user_message=current_user_message,
        selected_thread_metadata=selected_metadata,
    )
    if pending_option is not None:
        return await _stage_result_from_interpretation(
            state=state,
            user=user,
            snapshot=snapshot,
            interpretation=pending_option,
            capability_contract=capability_contract,
            selected_thread_metadata=selected_metadata,
        )
    if snapshot is None or snapshot.active_confirmation_reference is None:
        pending_date_answer = _pending_date_answer_interpretation(
            current_user_message=current_user_message,
            language=user.language_preference,
            snapshot=snapshot,
            selected_thread_metadata=selected_metadata,
            today=date.today(),
            reason_code="pending_date_answer_interpreter_unavailable_repaired",
            user_goal_summary=(
                "User supplied the requested date range while structured "
                "interpretation was unavailable."
            ),
        )
        if pending_date_answer is not None:
            return await _stage_result_from_interpretation(
                state=state,
                user=user,
                snapshot=snapshot,
                interpretation=pending_date_answer,
                capability_contract=capability_contract,
                selected_thread_metadata=selected_metadata,
            )
    active_confirmation_followup = (
        await _active_confirmation_followup_when_interpreter_unavailable(
            state=state,
            user=user,
            snapshot=snapshot,
            current_user_message=current_user_message,
            capability_contract=capability_contract,
            selected_thread_metadata=selected_metadata,
        )
    )
    if active_confirmation_followup is not None:
        return active_confirmation_followup
    draft_only_indicator_interpretation = (
        _draft_only_indicator_interpretation_when_interpreter_unavailable(
            snapshot=snapshot,
            current_user_message=current_user_message,
            resolve_asset_candidate=_resolve_asset_candidate_safely,
            default_benchmark_for_asset_class=_default_benchmark_for_asset_class,
        )
    )
    if draft_only_indicator_interpretation is not None:
        return await _stage_result_from_interpretation(
            state=RunState.new(
                current_user_message=current_user_message,
                recent_thread_history=[],
            ),
            user=user,
            snapshot=None,
            interpretation=draft_only_indicator_interpretation,
            capability_contract=capability_contract,
            selected_thread_metadata=selected_metadata,
        )
    return _offline_interpreter_unavailable_result(
        user=user,
        snapshot=snapshot,
        current_user_message=current_user_message,
        selected_thread_metadata=selected_metadata,
    )


async def _planned_active_confirmation_edit_when_interpreter_unavailable(
    *,
    state: RunState,
    user: UserState,
    snapshot: TaskSnapshot,
    current_user_message: str,
    capability_contract: Any,
    selected_thread_metadata: dict[str, Any],
) -> StageResult | None:
    interpretation = await _planned_active_confirmation_edit_interpretation(
        snapshot=snapshot,
        current_user_message=current_user_message,
        resolve_asset_candidate=_resolve_asset_candidate_safely,
        plan_artifact_assumption_edit_fn=plan_artifact_assumption_edit,
    )
    if interpretation is None:
        return None
    return await _stage_result_from_interpretation(
        state=state,
        user=user,
        snapshot=snapshot,
        interpretation=interpretation,
        capability_contract=capability_contract,
        selected_thread_metadata=selected_thread_metadata,
    )


async def _planned_active_confirmation_edit_for_typed_llm_assumption_edit(
    *,
    state: RunState,
    user: UserState,
    snapshot: TaskSnapshot | None,
    selected_thread_metadata: dict[str, Any],
    interpretation: StructuredInterpretation,
    capability_contract: Any,
) -> StageResult | None:
    if snapshot is None or snapshot.active_confirmation_reference is None:
        return None
    if "artifact_assumption_edit_planned" in interpretation.reason_codes:
        return None
    if _structured_interpretation_has_complete_typed_asset_patch(interpretation):
        return None
    if not _structured_interpretation_has_supported_artifact_assumption_edit(
        interpretation
    ):
        return None
    return await _planned_active_confirmation_edit_when_interpreter_unavailable(
        state=state,
        user=user,
        snapshot=snapshot,
        current_user_message=state.current_user_message,
        capability_contract=capability_contract,
        selected_thread_metadata=selected_thread_metadata,
    )


async def _active_confirmation_followup_when_interpreter_unavailable(
    *,
    state: RunState,
    user: UserState,
    snapshot: TaskSnapshot | None,
    current_user_message: str,
    capability_contract: Any,
    selected_thread_metadata: dict[str, Any],
) -> StageResult | None:
    if (
        snapshot is None
        or snapshot.pending_strategy_summary is None
        or snapshot.active_confirmation_reference is None
        or not current_user_message.strip()
    ):
        return None
    if _pending_assumption_edit_was_not_applied(
        current_user_message=current_user_message,
        selected_thread_metadata=selected_thread_metadata,
    ):
        return None
    planned_edit = await _planned_active_confirmation_edit_when_interpreter_unavailable(
        state=state,
        user=user,
        snapshot=snapshot,
        current_user_message=current_user_message,
        capability_contract=capability_contract,
        selected_thread_metadata=selected_thread_metadata,
    )
    if planned_edit is not None:
        return planned_edit
    strategy = snapshot.pending_strategy_summary
    setup_phrase = _current_setup_phrase(strategy)
    assumptions_response = _draft_assumptions_response(snapshot)
    action_guidance = recovery_message(
        "confirmation_action_guidance",
        language=user.language_preference,
    )
    response = await compose_active_confirmation_interpreter_recovery(
        current_user_message=current_user_message,
        setup_phrase=setup_phrase,
        assumptions_response=assumptions_response,
        action_guidance=action_guidance,
        language=user.language_preference,
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
            "Structured interpretation was unavailable; answered while preserving "
            "the active confirmation artifact."
        ),
        candidate_strategy_draft=StrategySummary(),
        missing_required_fields=[],
        optional_parameter_opportunity=[],
        confidence=0.0,
        arbitration_mode="deterministic",
        reason_codes=[
            "llm_interpreter_unavailable",
            "active_confirmation_composed_recovery",
        ],
        effective_response_profile=effective_profile,
        semantic_turn_act="educational_question",
    )
    return StageResult(
        outcome="ready_to_respond",
        decision=decision,
        stage_patch={"assistant_response": response},
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
        language=user.language_preference,
    )
    used_recovery = response is None
    if response is None:
        response = recovery_message(
            "latest_result_followup_unavailable",
            language=user.language_preference,
        )
    effective_profile = resolve_effective_response_profile(
        user=user,
        explicit_overrides=None,
    )
    decision = InterpretDecision(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary=(
            "Structured interpretation was unavailable; answered from the "
            "latest result artifact facts."
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
            "assistant_response": response,
            "response_intent": result_followup_response_intent("general"),
            **(
                recovery_state_stage_patch(
                    "latest_result_followup_unavailable",
                    language=user.language_preference,
                    retryable=True,
                )
                if used_recovery
                else {}
            ),
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
            language=user.language_preference,
        )
        if response is None:
            response = fallback_private_alpha_save_response(
                language=user.language_preference
            )
    else:
        response = await compose_result_followup_response(
            metadata=metadata,
            focus=focus,
            user_message=current_user_message,
            language=user.language_preference,
        )
        used_recovery = response is None
        if response is None:
            response = recovery_message(
                "latest_result_followup_unavailable",
                language=user.language_preference,
            )
    if save_requested and not _strategies_enabled():
        used_recovery = False
    stage_patch: dict[str, Any] = {
        "assistant_response": response,
    }
    if not (save_requested and not _strategies_enabled()):
        stage_patch["response_intent"] = result_followup_response_intent(focus)
    if used_recovery:
        stage_patch.update(
            recovery_state_stage_patch(
                "latest_result_followup_unavailable",
                language=user.language_preference,
                retryable=True,
            )
        )
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
        stage_patch=stage_patch,
    )


async def _private_alpha_save_request_result_if_applicable(
    *,
    user: UserState,
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
        language=user.language_preference,
    )
    if response is None:
        response = fallback_private_alpha_save_response(
            language=user.language_preference
        )
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


def _canonicalized_strategy(
    strategy: StrategySummary,
    *,
    current_user_message: str | None,
    selected_thread_metadata: dict[str, Any],
) -> StrategySummary:
    updated = strategy.model_copy(deep=True)
    canonical_symbols: list[str] = []
    asset_classes: set[str] = set()
    invalid_symbols: list[str] = []
    field_owned_indicator_symbols: list[str] = []
    cadence_word_symbols: list[str] = []
    provenance: list[ResolutionProvenance] = []
    asset_field_requested = (
        _field_base(str(selected_thread_metadata.get("requested_field") or ""))
        == "asset_universe"
    )

    for index, symbol in enumerate(updated.asset_universe):
        if _is_field_owned_indicator_asset_candidate(
            symbol,
            strategy=updated,
            current_user_message=current_user_message,
            asset_field_requested=asset_field_requested,
        ):
            field_owned_indicator_symbols.append(symbol)
            continue
        if _is_cadence_word_asset_candidate(
            symbol,
            strategy=updated,
            current_user_message=current_user_message,
            asset_field_requested=asset_field_requested,
        ):
            cadence_word_symbols.append(symbol)
            continue
        field = f"asset_universe[{index}]"
        resolution = (
            provider_context_assets.resolution_from_strategy_context(
                updated,
                symbol,
                field=field,
            )
            or _resolve_asset_candidate(
                symbol,
                field=field,
                source=_asset_resolution_source_for_canonicalization(
                    updated,
                    index=index,
                    symbol=symbol,
                ),
                asset_class_hint=updated.asset_class,
            )
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
    elif field_owned_indicator_symbols or cadence_word_symbols:
        updated.asset_universe = []
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


def _strategy_with_benchmark_owner_asset_repair(
    strategy: StrategySummary,
) -> tuple[StrategySummary, list[str]]:
    """Ground the single missing traded asset when the benchmark owner is stated.

    Consumes only the interpreter's provider-grounded current-turn asset records
    (never a raw-text re-scan): a user-stated benchmark disambiguates which
    grounded mention is the comparison, so exactly one remaining record is the
    traded asset. Never guesses when the benchmark is unstated or when more than
    one candidate remains.
    """

    if strategy.asset_universe:
        return strategy, []
    benchmark = _normalized_symbol(strategy.comparison_baseline)
    if benchmark is None:
        return strategy, []
    provenance = strategy.extra_parameters.get("field_provenance")
    if not (
        isinstance(provenance, dict)
        and provenance.get("comparison_baseline") == "explicit_user"
    ):
        return strategy, []
    resolutions: list[AssetResolution] = []
    for symbol in provider_context_assets.resolved_asset_symbols_from_strategy_context(
        strategy
    ):
        if symbol == benchmark:
            continue
        resolution = provider_context_assets.resolution_from_strategy_context(
            strategy,
            symbol,
            field="asset_universe[0]",
        )
        if resolution is None or resolution.asset is None:
            continue
        resolutions.append(resolution)
    if len(resolutions) != 1:
        return strategy, []
    resolved_asset = resolutions[0].asset
    updated = strategy.model_copy(deep=True)
    updated.asset_universe = [resolved_asset.canonical_symbol]
    updated.asset_class = resolved_asset.asset_class
    return updated, ["current_message_asset_grounding_repaired"]


def _default_benchmark_for_asset_class(
    asset_class: str,
    *,
    symbols: list[str],
) -> str | None:
    if asset_class not in _BACKTEST_ASSET_CLASSES:
        return None
    return default_backtest_benchmark(
        cast(BacktestAssetClass, asset_class),
        symbols,
    )


def _strategy_with_default_benchmark(
    strategy: StrategySummary,
) -> tuple[StrategySummary, list[str]]:
    if _normalized_symbol(strategy.comparison_baseline):
        return strategy, []
    if not strategy.asset_class:
        return strategy, []
    benchmark = _default_benchmark_for_asset_class(
        strategy.asset_class,
        symbols=strategy.asset_universe,
    )
    if benchmark is None:
        return strategy, []
    updated = strategy.model_copy(deep=True)
    updated.comparison_baseline = benchmark
    return updated, ["default_benchmark_applied"]


def _strategy_with_unstated_benchmark_guard(
    *,
    strategy: StrategySummary,
    prior_strategy: StrategySummary | None,
) -> tuple[StrategySummary, list[str]]:
    benchmark = _normalized_symbol(strategy.comparison_baseline)
    if benchmark is None:
        return strategy, []
    provenance = strategy.extra_parameters.get("field_provenance")
    if isinstance(provenance, dict) and provenance.get("comparison_baseline") in {
        "explicit_user",
        "stated_run_field_fidelity_audit",
    }:
        return strategy, []
    prior_benchmark = (
        _normalized_symbol(prior_strategy.comparison_baseline)
        if prior_strategy is not None
        else None
    )
    if prior_benchmark == benchmark:
        return strategy, []
    if _strategy_uses_safe_default_benchmark(strategy, benchmark):
        return strategy, []
    updated = strategy.model_copy(deep=True)
    if prior_benchmark is not None:
        updated.comparison_baseline = prior_benchmark
        return updated, ["unstated_benchmark_symbol_reverted"]
    updated.comparison_baseline = None
    return updated, ["unstated_benchmark_symbol_cleared"]


def _strategy_uses_safe_default_benchmark(
    strategy: StrategySummary,
    benchmark: str,
) -> bool:
    if not strategy.asset_class or not strategy.asset_universe:
        return False
    default_benchmark = _default_benchmark_for_asset_class(
        strategy.asset_class,
        symbols=strategy.asset_universe,
    )
    return default_benchmark == benchmark


def _strategy_with_validated_benchmark_symbol(
    strategy: StrategySummary,
) -> tuple[StrategySummary, list[str]]:
    benchmark = _normalized_symbol(strategy.comparison_baseline)
    if benchmark is None:
        return strategy, []
    try:
        resolution = (
            provider_context_assets.resolution_from_strategy_context(
                strategy,
                benchmark,
                field="comparison_baseline",
            )
            or _resolve_asset_candidate(
                benchmark,
                field="comparison_baseline",
                source="llm_extraction",
                asset_class_hint=strategy.asset_class,
            )
        )
    except ValueError:
        resolution = None
    if resolution is not None and resolution.status == "resolved" and resolution.asset is not None:
        benchmark_asset_class = resolution.asset.asset_class
        if strategy.asset_class and benchmark_asset_class != strategy.asset_class:
            updated = strategy.model_copy(deep=True)
            updated.comparison_baseline = None
            return updated, ["invalid_benchmark_symbol_cleared"]
        canonical = resolution.asset.canonical_symbol.strip().upper()
        if canonical == benchmark:
            return strategy, []
        updated = strategy.model_copy(deep=True)
        updated.comparison_baseline = canonical
        return updated, ["benchmark_symbol_provider_validated"]
    updated = strategy.model_copy(deep=True)
    updated.comparison_baseline = None
    return updated, ["invalid_benchmark_symbol_cleared"]


def _resolve_asset_candidate(
    query: str,
    *,
    field: str,
    source: ResolutionSource,
    asset_class_hint: str | None = None,
) -> AssetResolution:
    if resolve_asset is _DEFAULT_RESOLVE_ASSET:
        kwargs: dict[str, Any] = {"field": field, "source": source}
        if asset_class_hint is not None and callable_accepts_keyword(
            runtime_resolve_asset_candidate,
            "asset_class_hint",
        ):
            kwargs["asset_class_hint"] = asset_class_hint
        return runtime_resolve_asset_candidate(query, **kwargs)
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
