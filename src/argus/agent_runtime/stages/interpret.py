from __future__ import annotations

import asyncio
import inspect
import os
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, cast, get_args

from argus.agent_runtime.artifacts.patch_policy import (
    executable_artifact_patch_missing_fields,
    relevant_unsupported_constraints_for_artifact_patch,
)
from argus.agent_runtime.asset_text_grounding import (
    grounded_asset_mention_has_name_support,
    grounded_asset_mentions_from_text,
    provider_ticker_mentions_from_text,
)
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
from argus.agent_runtime.recovery_messages import (
    recovery_message,
    recovery_state_stage_patch,
    retry_last_turn_stage_patch,
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
from argus.agent_runtime.run_field_contract import (
    current_message_execution_context_tokens,
)
from argus.agent_runtime.semantic_integrity import (
    SemanticIntegrityReport,
    conserve_semantic_constraints,
    filter_unsubstantiated_timeframe_constraints,
)
from argus.agent_runtime.stages.artifact_context import (
    LEGACY_RESULT_EXPLANATION_TARGET_INFERRED,
    LEGACY_RESULT_FOLLOWUP_TARGET_INFERRED,
    launch_payload_from_failed_action,
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
    resolve_date_range,
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
from argus.nlp.natural_time import (
    dateparser_languages_for_user_language,
    parse_explicit_date_text,
    resolve_date_range_intent,
)
from argus.llm.openrouter import invoke_openrouter_chat_completion

_DEFAULT_RESOLVE_ASSET = resolve_asset
_STANDALONE_CONTEXT_PACKET_TIMEOUT_SECONDS = 2.5
_LATEST_RESULT_SAVE_REQUESTED_REASON = "latest_result_save_requested"
_BACKTEST_ASSET_CLASSES = frozenset(get_args(BacktestAssetClass))
_USER_GROUNDED_CAPITAL_SOURCES = frozenset(
    {
        "explicit_user",
        "prior",
        "recurring_contribution",
        "contribution_amount",
        "periodic_contribution",
        "dca_contribution",
    }
)
_USER_GROUNDED_CADENCE_SOURCES = frozenset(
    {
        "explicit_user",
        "prior",
        "visible_draft",
    }
)


@dataclass(frozen=True)
class _LiveContextCuriosityFacts:
    content: str
    packet_symbols: tuple[str, ...] = ()


@dataclass(frozen=True)
class _ProvenanceAsset:
    canonical_symbol: str
    asset_class: str
    raw_symbol: str = ""
    name: str = ""


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
        pending_date_result = await _pending_date_answer_result_when_interpreter_unavailable(
            state=state,
            user=user,
            snapshot=snapshot,
            capability_contract=capability_contract,
            selected_thread_metadata=selected_metadata,
        )
        if pending_date_result is not None:
            return pending_date_result
        pending_asset_result = await _pending_asset_answer_result_when_interpreter_unavailable(
            state=state,
            user=user,
            snapshot=snapshot,
            capability_contract=capability_contract,
            selected_thread_metadata=selected_metadata,
        )
        if pending_asset_result is not None:
            return pending_asset_result
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
        pending_date_result = await _pending_date_answer_result_when_interpreter_unavailable(
            state=state,
            user=user,
            snapshot=snapshot,
            capability_contract=capability_contract,
            selected_thread_metadata=selected_metadata,
        )
        if pending_date_result is not None:
            return pending_date_result
        pending_asset_result = await _pending_asset_answer_result_when_interpreter_unavailable(
            state=state,
            user=user,
            snapshot=snapshot,
            capability_contract=capability_contract,
            selected_thread_metadata=selected_metadata,
        )
        if pending_asset_result is not None:
            return pending_asset_result
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


async def _pending_date_answer_result_when_interpreter_unavailable(
    *,
    state: RunState,
    user: UserState,
    snapshot: TaskSnapshot | None,
    capability_contract: Any,
    selected_thread_metadata: dict[str, Any],
) -> StageResult | None:
    interpretation = _pending_date_answer_interpretation_when_unavailable(
        current_user_message=state.current_user_message,
        language=user.language_preference,
        snapshot=snapshot,
        selected_thread_metadata=selected_thread_metadata,
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


async def _pending_asset_answer_result_when_interpreter_unavailable(
    *,
    state: RunState,
    user: UserState,
    snapshot: TaskSnapshot | None,
    capability_contract: Any,
    selected_thread_metadata: dict[str, Any],
) -> StageResult | None:
    interpretation = _pending_asset_answer_interpretation_when_unavailable(
        current_user_message=state.current_user_message,
        snapshot=snapshot,
        selected_thread_metadata=selected_thread_metadata,
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


def _pending_asset_answer_interpretation_when_unavailable(
    *,
    current_user_message: str,
    snapshot: TaskSnapshot | None,
    selected_thread_metadata: dict[str, Any],
) -> StructuredInterpretation | None:
    requested_field = _field_base(
        str(selected_thread_metadata.get("requested_field") or "")
    )
    if requested_field != "asset_universe":
        return None
    if snapshot is None or snapshot.pending_strategy_summary is None:
        return None
    asset_answer = current_user_message.strip()
    if not asset_answer:
        return None
    return StructuredInterpretation(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User supplied the requested replacement asset.",
        candidate_strategy_draft=StrategySummary(asset_universe=[asset_answer]),
        missing_required_fields=[],
        semantic_turn_act="answer_pending_need",
        reason_codes=["deterministic_pending_asset_answer_fallback"],
    )


def _pending_date_answer_interpretation_when_unavailable(
    *,
    current_user_message: str,
    language: str | None,
    snapshot: TaskSnapshot | None,
    selected_thread_metadata: dict[str, Any],
) -> StructuredInterpretation | None:
    requested_field = _field_base(
        str(selected_thread_metadata.get("requested_field") or "")
    )
    if requested_field != "date_range":
        return None
    if snapshot is None or snapshot.pending_strategy_summary is None:
        return None
    endpoint_role = _pending_date_endpoint_role(snapshot.pending_strategy_summary)
    endpoint = _parse_pending_date_endpoint_answer(
        current_user_message,
        endpoint_role=endpoint_role,
        language=language,
    )
    if endpoint is None:
        return None
    return StructuredInterpretation(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User supplied the requested date range detail.",
        candidate_strategy_draft=StrategySummary(
            date_range={endpoint_role: endpoint.isoformat()},
        ),
        missing_required_fields=[],
        semantic_turn_act="answer_pending_need",
        reason_codes=["deterministic_pending_date_answer_fallback"],
    )


def _pending_date_endpoint_role(strategy: StrategySummary) -> str:
    date_range = strategy.date_range
    if isinstance(date_range, dict):
        has_start = bool(date_range.get("start") or date_range.get("from"))
        has_end = bool(date_range.get("end") or date_range.get("to"))
        if has_start and not has_end:
            return "end"
        if has_end and not has_start:
            return "start"
    return "end"


def _parse_pending_date_endpoint_answer(
    message: str,
    *,
    endpoint_role: str,
    language: str | None,
) -> date | None:
    endpoint = "end" if endpoint_role == "end" else "start"
    return parse_explicit_date_text(
        message,
        endpoint=endpoint,
        languages=dateparser_languages_for_user_language(language),
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
    original_semantic_turn_act = interpretation.semantic_turn_act
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
    route_suppression_reason_codes: list[str] = []
    expects_strategy_route = _strategy_route_expected(
        intent=interpretation.intent,
        semantic_turn_act=interpretation.semantic_turn_act,
    ) or _candidate_strategy_has_backtest_shape(
        interpretation.candidate_strategy_draft
    )
    dca_education_answer = _dca_education_answer_for_message(
        state.current_user_message
    )
    educational_turn_has_strategy_baggage = _educational_turn_has_strategy_baggage(
        interpretation=interpretation,
        expects_strategy_route=expects_strategy_route,
    )
    misclassified_dca_education_has_strategy_baggage = (
        _misclassified_dca_education_has_strategy_baggage(
            interpretation=interpretation,
            expects_strategy_route=expects_strategy_route,
            dca_education_answer=dca_education_answer,
        )
    )
    if (
        educational_turn_has_strategy_baggage
        or misclassified_dca_education_has_strategy_baggage
    ):
        expects_strategy_route = False
        route_suppression_reason_codes.append("educational_strategy_route_suppressed")
        update: dict[str, Any] = {
            "intent": "conversation_followup",
            "task_relation": "continue",
            "requires_clarification": False,
            "candidate_strategy_draft": StrategySummary(),
            "missing_required_fields": [],
            "ambiguous_fields": [],
            "unsupported_constraints": [],
            "semantic_turn_act": "educational_question",
        }
        if (
            misclassified_dca_education_has_strategy_baggage
            and dca_education_answer is not None
        ):
            update["assistant_response"] = dca_education_answer
        interpretation = interpretation.model_copy(
            update=update,
        )
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
        _strategy_with_execution_defaults(_canonicalized_strategy(incoming_strategy))
        if expects_strategy_route
        else incoming_strategy
    )
    benchmark_reason_codes: list[str] = []
    if expects_strategy_route:
        prior_strategy = _active_strategy_from_snapshot(snapshot)
        strategy, unstated_benchmark_reason_codes = (
            _strategy_with_unstated_benchmark_guard(
                strategy=strategy,
                prior_strategy=prior_strategy,
            )
        )
        benchmark_reason_codes.extend(unstated_benchmark_reason_codes)
    current_message_asset_grounding_reason_codes: list[str] = []
    if expects_strategy_route and _should_apply_current_message_asset_grounding(
        semantic_turn_act=original_semantic_turn_act,
        selected_thread_metadata=selected_thread_metadata,
        snapshot=snapshot,
    ):
        strategy, current_message_asset_grounding_reason_codes = (
            _strategy_with_current_message_asset_grounding(
                strategy=strategy,
                current_user_message=state.current_user_message,
            )
        )
    if expects_strategy_route:
        strategy, interpretation = _strategy_with_current_message_run_field_contract(
            strategy=strategy,
            interpretation=interpretation,
            current_user_message=state.current_user_message,
            supported_timeframes=_supported_timeframes(capability_contract),
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
        benchmark_reason_codes = [
            *benchmark_reason_codes,
            *current_message_asset_grounding_reason_codes,
            *separate_benchmark_reason_codes,
            *validated_benchmark_reason_codes,
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
            *integrity_report.reason_codes,
            *constraint_filter_reason_codes,
            *ambiguity_filter_reason_codes,
            *artifact_target_reason_codes,
            *hidden_context_guard_reason_codes,
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
    runnable_prompt_result = _runnable_prompt_example_result_if_applicable(
        decision=decision,
        snapshot=snapshot,
        current_user_message=state.current_user_message,
    )
    if runnable_prompt_result is not None:
        return runnable_prompt_result
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
    supported_strategy_answer = await _supported_strategy_education_repair_if_needed(
        semantic_turn_act=interpretation.semantic_turn_act,
        assistant_response=interpretation.assistant_response,
        current_user_message=state.current_user_message,
        capability_contract=capability_contract,
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


def _strategy_with_current_message_run_field_contract(
    *,
    strategy: StrategySummary,
    interpretation: StructuredInterpretation,
    current_user_message: str,
    supported_timeframes: tuple[str, ...],
) -> tuple[StrategySummary, StructuredInterpretation]:
    raw_date_range = _explicit_date_range_from_strategy_for_repair(strategy)
    date_range, date_endpoint_patch_applied = (
        _complete_current_message_date_endpoint_patch(
            strategy=strategy,
            date_range=raw_date_range,
        )
    )
    updated = strategy.model_copy(deep=True)
    changed = False
    repaired_field_bases: set[str] = set()
    repair_reason_codes = ["current_message_run_field_contract_repair"]
    if date_endpoint_patch_applied:
        repair_reason_codes.append("structured_date_endpoint_patch_applied")
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
) -> tuple[dict[str, str] | None, bool]:
    if date_range is None or not has_partial_explicit_date_range(date_range):
        return date_range, False
    prior = strategy.date_range
    if not isinstance(prior, dict):
        return date_range, False
    start = date_range.get("start") or prior.get("start") or prior.get("from")
    end = date_range.get("end") or prior.get("end") or prior.get("to")
    if not start or not end:
        return date_range, False
    return {"start": str(start), "end": str(end)}, True


def _explicit_date_range_from_strategy_for_repair(
    strategy: StrategySummary,
) -> dict[str, str] | None:
    intent = strategy.extra_parameters.get("date_range_intent")
    if isinstance(intent, dict):
        resolved = resolve_date_range_intent(intent)
        if resolved is not None:
            return resolved.payload
    if isinstance(strategy.date_range, dict):
        payload = {
            key: str(value)
            for key in ("start", "end")
            if (value := strategy.date_range.get(key)) not in (None, "")
        }
        return payload or None
    return None


def _strategy_date_range_needs_current_message_repair(
    *,
    strategy: StrategySummary,
    interpretation: StructuredInterpretation,
    current_date_range: dict[str, str],
) -> bool:
    if interpretation.semantic_turn_act == "answer_pending_need":
        return (
            strategy.date_range in (None, "", [], {})
            or has_partial_explicit_date_range(strategy.date_range)
            or not isinstance(strategy.date_range, dict)
            or _date_range_endpoints(strategy.date_range)
            != _date_range_endpoints(current_date_range)
        )
    if strategy.date_range in (None, "", [], {}):
        return True
    if has_partial_explicit_date_range(strategy.date_range):
        return True
    if isinstance(strategy.date_range, str):
        return False
    if _date_range_endpoints(strategy.date_range) != _date_range_endpoints(
        current_date_range
    ):
        return True
    return any(
        str(field).split("[", 1)[0] == "date_range"
        for field in interpretation.missing_required_fields
    ) or any(
        field.field_name.split("[", 1)[0] == "date_range"
        for field in interpretation.ambiguous_fields
    )


def _date_range_endpoints(value: Any) -> tuple[str | None, str | None] | None:
    if not isinstance(value, dict):
        return None
    start = value.get("start") or value.get("from")
    end = value.get("end") or value.get("to")
    return (
        str(start).strip() if start not in (None, "", [], {}) else None,
        str(end).strip() if end not in (None, "", [], {}) else None,
    )


def _strategy_has_non_executable_timeframe_label(
    strategy: StrategySummary,
    *,
    supported_timeframes: tuple[str, ...],
) -> bool:
    if strategy.timeframe in (None, "", [], {}):
        return False
    normalized = str(strategy.timeframe).strip().casefold().replace(" ", "")
    supported = {
        str(value).strip().casefold().replace(" ", "")
        for value in supported_timeframes
    }
    return bool(normalized and normalized not in supported)


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


def _repair_fresh_restatement_route_when_pending_need_is_active(
    *,
    interpretation: StructuredInterpretation,
    snapshot: TaskSnapshot | None,
    selected_thread_metadata: dict[str, Any],
) -> StructuredInterpretation:
    if snapshot is None or snapshot.pending_strategy_summary is None:
        return interpretation
    if snapshot.latest_backtest_result_reference is not None:
        return interpretation
    if interpretation.semantic_turn_act in {
        "approval",
        "new_idea",
        "retry_failed_action",
        "unsupported_request",
    }:
        return interpretation
    if interpretation.intent not in {"conversation_followup", "strategy_drafting"}:
        return interpretation
    prior_outcome = str(selected_thread_metadata.get("last_stage_outcome") or "")
    requested_field = _field_base(
        str(selected_thread_metadata.get("requested_field") or "")
    )
    if (
        prior_outcome not in {"await_user_reply", "needs_clarification"}
        and not requested_field
        and selected_thread_metadata.get("fallback_source")
        != "pending_strategy_metadata"
    ):
        return interpretation
    prior = snapshot.pending_strategy_summary
    candidate = _strategy_with_contextual_merge(
        strategy=interpretation.candidate_strategy_draft,
        snapshot=snapshot,
        selected_thread_metadata=selected_thread_metadata,
        semantic_turn_act="new_idea",
        task_relation="new_task",
        reason_codes=interpretation.reason_codes,
    )
    if not _strategy_has_execution_anchor(candidate):
        return interpretation
    if not candidate.strategy_type or not candidate.asset_universe or not candidate.date_range:
        return interpretation
    if not _strategy_has_fresh_execution_detail(strategy=candidate, prior=prior):
        return interpretation
    return interpretation.model_copy(
        update={
            "intent": "backtest_execution",
            "task_relation": "new_task",
            "requires_clarification": False,
            "assistant_response": None,
            "candidate_strategy_draft": candidate,
            "missing_required_fields": [],
            "semantic_turn_act": "new_idea",
            "result_followup_focus": None,
            "artifact_target": "none",
            "reason_codes": list(
                dict.fromkeys(
                    [
                        *interpretation.reason_codes,
                        "fresh_restatement_followup_route_repaired",
                    ]
                )
            ),
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
        reason_codes.append(LEGACY_RESULT_FOLLOWUP_TARGET_INFERRED)
        return "latest_result", reason_codes
    if (
        interpretation.intent == "results_explanation"
        and snapshot is not None
        and snapshot.latest_backtest_result_reference is not None
    ):
        reason_codes.append(LEGACY_RESULT_EXPLANATION_TARGET_INFERRED)
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
    if focus in {"supported_strategies", "general"} and (
        _answer_contradicts_supported_strategy_families(answer)
    ):
        return False
    if focus != "supported_indicators":
        return True
    return not _answer_contradicts_supported_indicators(answer)


async def _supported_strategy_education_repair_if_needed(
    *,
    semantic_turn_act: SemanticTurnAct | None,
    assistant_response: str | None,
    current_user_message: str,
    capability_contract: Any,
) -> str | None:
    if (
        semantic_turn_act != "educational_question"
        or not assistant_response
        or not _answer_contradicts_supported_strategy_families(assistant_response)
    ):
        return None
    return await _compose_natural_capability_answer(
        focus="supported_strategies",
        current_user_message=current_user_message,
        capability_contract=capability_contract,
    )


def _runnable_prompt_example_result_if_applicable(
    *,
    decision: InterpretDecision,
    snapshot: TaskSnapshot | None,
    current_user_message: str,
) -> StageResult | None:
    if not _message_asks_for_runnable_prompt_example(current_user_message):
        return None
    prompt = _runnable_prompt_example_from_failed_action(snapshot)
    reason_code = (
        "retry_failed_action_prompt_example_suppressed"
        if decision.semantic_turn_act == "retry_failed_action"
        else "runnable_prompt_example_route_suppressed"
    )
    return StageResult(
        outcome="ready_to_respond",
        decision=decision.model_copy(
            update={
                "intent": "conversation_followup",
                "task_relation": "continue",
                "requires_clarification": False,
                "candidate_strategy_draft": StrategySummary(),
                "missing_required_fields": [],
                "reason_codes": [
                    *decision.reason_codes,
                    reason_code,
                ],
                "semantic_turn_act": "educational_question",
                "capability_question_focus": "general",
                "artifact_target": "none",
            }
        ),
        stage_patch={"assistant_response": prompt},
    )


def _message_asks_for_runnable_prompt_example(message: str) -> bool:
    tokens = set(_plain_word_tokens(message))
    if "prompt" not in tokens and "example" not in tokens:
        return False
    if not tokens & {"run", "runnable", "errors", "error"}:
        return False
    return bool(
        tokens
        & {
            "example",
            "give",
            "provide",
            "show",
            "suggest",
            "try",
            "what",
            "which",
            "write",
        }
    )


def _runnable_prompt_example_from_failed_action(snapshot: TaskSnapshot | None) -> str:
    payload = (
        launch_payload_from_failed_action(snapshot.latest_failed_action_reference)
        if snapshot is not None and snapshot.latest_failed_action_reference is not None
        else None
    )
    symbol = "Amazon stock"
    start = "January 1, 2026"
    end = (date.today() - timedelta(days=1)).isoformat()
    if isinstance(payload, dict):
        raw_symbol = str(
            (payload.get("symbols") or [payload.get("symbol") or ""])[0]
            if isinstance(payload.get("symbols"), list)
            else payload.get("symbol") or ""
        ).strip()
        if raw_symbol:
            symbol = f"{raw_symbol.upper()} stock"
        date_range = payload.get("date_range")
        if isinstance(date_range, dict):
            start = str(date_range.get("start") or start)
            end = str(date_range.get("end") or end)
    return f'Try: "Buy and hold {symbol} from {start} through {end}."'


def _answer_contradicts_supported_strategy_families(answer: str) -> bool:
    for sentence in _plain_sentences(answer):
        tokens = _plain_word_tokens(sentence)
        if not tokens:
            continue
        strategy_spans = _supported_strategy_family_token_spans(tokens)
        if not strategy_spans:
            continue
        negative_positions = _negative_support_claim_positions(tokens)
        for start, end in strategy_spans:
            if any(start - 3 <= position <= end + 6 for position in negative_positions):
                return True
    return False


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


_SUPPORTED_STRATEGY_FAMILY_TERMS: tuple[str, ...] = (
    "buy and hold",
    "buy-and-hold",
    "hold",
    "recurring buys",
    "recurring buy",
    "dca",
    "dollar cost averaging",
    "indicator threshold",
    "indicator rules",
    "signal rules",
    "moving average",
    "macd",
    "bollinger band",
)


def _supported_strategy_family_token_spans(tokens: list[str]) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for term in _SUPPORTED_STRATEGY_FAMILY_TERMS:
        term_tokens = _plain_word_tokens(term)
        if not term_tokens:
            continue
        spans.extend(_token_sequence_spans(tokens, term_tokens))
    return spans


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
        "'from this result' or 'from this confirmation'."
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


def _without_stale_requested_asset_rejection_constraints(
    constraints: list[UnsupportedConstraint],
    *,
    strategy: StrategySummary,
) -> list[UnsupportedConstraint]:
    if not strategy.asset_universe:
        return list(constraints)
    stale_rejection_categories = {"action", "navigation_or_tool"}
    return [
        constraint
        for constraint in constraints
        if constraint.category not in stale_rejection_categories
    ]


def _resolve_asset_candidate_safely(
    query: str,
    *,
    field: str,
    source: ResolutionSource,
) -> AssetResolution | None:
    try:
        return _resolve_asset_candidate(query, field=field, source=source)
    except ValueError:
        return None


def _unresolved_requested_asset_resolution(
    query: str,
    *,
    field: str,
    source: ResolutionSource,
) -> AssetResolution:
    return AssetResolution(
        status="unsupported",
        raw_text=query,
        asset=None,
        candidates=(),
        provenance=ResolutionProvenance(
            field=field,
            raw_text=query,
            source=source,
            candidate_kind="asset",
            resolution_status="unsupported",
            validated_by="provider_catalog",
            confidence="low",
        ),
    )


def _strategy_canonical_asset_symbols(strategy: StrategySummary | None) -> set[str]:
    if strategy is None:
        return set()
    return {
        symbol.strip().upper()
        for symbol in strategy.asset_universe
        if isinstance(symbol, str) and symbol.strip()
    }


def _provenance_field(item: ResolutionProvenance | dict[str, Any]) -> str:
    if isinstance(item, ResolutionProvenance):
        return item.field
    field = item.get("field")
    return field if isinstance(field, str) else ""


@dataclass(frozen=True)
class _RequestedAssetCandidate:
    text: str
    source: ResolutionSource
    from_user_answer: bool = False


def _requested_asset_answer_candidates(
    *,
    explicit_strategy: StrategySummary,
    current_user_message: str,
) -> list[_RequestedAssetCandidate]:
    candidates: list[_RequestedAssetCandidate] = []
    answer = current_user_message.strip()
    if answer:
        candidates.append(
            _RequestedAssetCandidate(
                text=answer,
                source="user_mention",
                from_user_answer=True,
            )
        )
    for symbol in explicit_strategy.asset_universe:
        candidate = str(symbol or "").strip()
        if candidate:
            candidates.append(
                _RequestedAssetCandidate(text=candidate, source="llm_extraction")
            )
    deduped: list[_RequestedAssetCandidate] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = candidate.text.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def _strategy_with_supported_indicator_simplification(
    *,
    strategy: StrategySummary,
    snapshot: TaskSnapshot | None,
    selected_thread_metadata: dict[str, Any],
    semantic_turn_act: str | None,
    task_relation: str,
) -> tuple[StrategySummary, bool]:
    if semantic_turn_act == "approval":
        return strategy, False
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

    preserve_prior_asset_context = (
        prior is not None
        and _should_preserve_prior_asset_context(
            prior=prior,
            selected_thread_metadata=selected_thread_metadata,
            semantic_turn_act=semantic_turn_act,
            task_relation=task_relation,
        )
    )
    merge_fields = [
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
    ]
    if preserve_prior_asset_context:
        merge_fields = [
            field
            for field in merge_fields
            if field not in {"asset_universe", "asset_class"}
        ]
    updated = _merge_non_empty_strategy_fields(
        base=base,
        incoming=strategy,
        field_names=tuple(merge_fields),
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
    return f"Test the current idea with a supported {spec.label} threshold rule."


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
        user_goal_summary="Structured interpretation was unavailable for this turn.",
        candidate_strategy_draft=StrategySummary(),
        missing_required_fields=[],
        optional_parameter_opportunity=[],
        confidence=0.0,
        arbitration_mode="deterministic",
        reason_codes=["llm_interpreter_unavailable"],
        effective_response_profile=effective_profile,
        semantic_turn_act=None,
    )
    stage_patch: dict[str, Any] = {
        "assistant_response": _offline_recovery_message(
            snapshot,
            current_user_message=current_user_message,
            selected_thread_metadata=selected_thread_metadata or {},
            language=user.language_preference,
        ),
    }
    stage_patch.update(
        recovery_state_stage_patch(
            "interpreter_unavailable",
            language=user.language_preference,
            retryable=True,
        )
    )
    retry_last_turn = retry_last_turn_stage_patch(current_user_message)
    if retry_last_turn is not None:
        stage_patch.update(retry_last_turn)
    return StageResult(
        outcome="ready_to_respond",
        decision=decision,
        stage_patch=stage_patch,
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
    active_confirmation_followup = (
        await _active_confirmation_followup_when_interpreter_unavailable(
            user=user,
            snapshot=snapshot,
            current_user_message=current_user_message,
            selected_thread_metadata=selected_thread_metadata or {},
        )
    )
    if active_confirmation_followup is not None:
        return active_confirmation_followup
    return _offline_interpreter_unavailable_result(
        user=user,
        snapshot=snapshot,
        current_user_message=current_user_message,
        selected_thread_metadata=selected_thread_metadata or {},
    )


async def _active_confirmation_followup_when_interpreter_unavailable(
    *,
    user: UserState,
    snapshot: TaskSnapshot | None,
    current_user_message: str,
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
    strategy = snapshot.pending_strategy_summary
    setup_phrase = _current_setup_phrase(strategy)
    assumptions_response = _draft_assumptions_response(snapshot)
    action_guidance = (
        "The visible confirmation is still ready. Use the card to start the "
        "simulation, or use the card controls to change it."
    )
    response = await compose_active_confirmation_interpreter_recovery(
        current_user_message=current_user_message,
        setup_phrase=setup_phrase,
        assumptions_response=assumptions_response,
        action_guidance=action_guidance,
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
    language: str = "en",
) -> str:
    if snapshot is not None and snapshot.pending_strategy_summary is not None:
        strategy = snapshot.pending_strategy_summary
        setup_phrase = _current_setup_phrase(strategy)
        if _pending_assumption_edit_was_not_applied(
            current_user_message=current_user_message,
            selected_thread_metadata=selected_thread_metadata or {},
        ):
            return recovery_message("assumption_edit_unapplied", language=language)
        if snapshot.active_confirmation_reference is None:
            return recovery_message(
                "setup_change_unapplied",
                language=language,
                setup_phrase=setup_phrase,
            )
        assumptions_response = _draft_assumptions_response(snapshot)
        action_guidance = recovery_message(
            "confirmation_action_guidance",
            language=language,
        )
        if assumptions_response is not None:
            return f"{assumptions_response} {action_guidance}"
        return recovery_message(
            "confirmation_change_unapplied",
            language=language,
            setup_phrase=setup_phrase,
            action_guidance=action_guidance,
        )
    if snapshot is not None and snapshot.latest_backtest_result_reference is not None:
        return recovery_message(
            "latest_result_followup_unavailable",
            language=language,
        )
    return recovery_message("interpreter_unavailable", language=language)


def _current_setup_phrase(strategy: StrategySummary) -> str:
    assets = [symbol for symbol in strategy.asset_universe if symbol]
    asset_label = ", ".join(assets)
    strategy_label = display_strategy_type(strategy).strip().lower()
    if asset_label and strategy_label:
        return f"{asset_label} {strategy_label} setup"
    if asset_label:
        return f"{asset_label} setup"
    if strategy_label:
        return f"current {strategy_label} setup"
    return "current setup"


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
    current_user_message: str | None = None,
    reason_codes: list[str] | None = None,
) -> StrategySummary:
    if snapshot is None:
        return strategy
    prior = snapshot.pending_strategy_summary or snapshot.confirmed_strategy_summary
    if prior is None:
        return strategy
    if "pending_response_option_selected" in set(reason_codes or []):
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
    preserve_prior_asset_context = _should_preserve_prior_asset_context(
        prior=prior,
        selected_thread_metadata=selected_thread_metadata,
        semantic_turn_act=semantic_turn_act,
        task_relation=task_relation,
    )
    preserve_prior_money_context = _should_preserve_prior_money_context(
        selected_thread_metadata=selected_thread_metadata,
        semantic_turn_act=semantic_turn_act,
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
        if preserve_prior_asset_context and key in {
            "asset_universe",
            "asset_class",
            "resolution_provenance",
        }:
            continue
        if preserve_prior_money_context and key in {
            "capital_amount",
            "initial_capital",
            "total_capital",
            "position_size",
        }:
            continue
        if value in (None, "", [], {}):
            continue
        if key == "date_range" and isinstance(value, dict):
            value = _contextual_date_range_value(
                base=merged.date_range,
                incoming=value,
                current_user_message=current_user_message,
                selected_thread_metadata=selected_thread_metadata,
            )
        if key == "extra_parameters":
            if preserve_prior_family and isinstance(value, dict):
                value = {
                    nested_key: nested_value
                    for nested_key, nested_value in value.items()
                    if nested_key not in {"raw_strategy_type", "template"}
                }
            if preserve_prior_money_context and isinstance(value, dict):
                value = _extra_parameters_without_unrequested_money_context(value)
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


def _should_preserve_prior_money_context(
    *,
    selected_thread_metadata: dict[str, Any],
    semantic_turn_act: str | None,
) -> bool:
    if semantic_turn_act != "answer_pending_need":
        return False
    if selected_thread_metadata.get("last_stage_outcome") != "await_user_reply":
        return False
    requested_field = _field_base(
        str(selected_thread_metadata.get("requested_field") or "")
    )
    return requested_field in {"asset_universe", "date_range", "timeframe"}


def _extra_parameters_without_unrequested_money_context(
    extra_parameters: dict[str, Any],
) -> dict[str, Any]:
    money_context_keys = {
        "initial_capital",
        "starting_capital",
        "starting_principal",
        "initial_lump_sum",
        "initial_lump",
        "lump_sum",
        "total_capital",
        "total_budget",
        "max_budget",
        "investment_budget",
        "cap",
        "contribution_cap",
        "capital_cap",
        "investment_cap",
        "recurring_contribution",
        "contribution_amount",
        "periodic_contribution",
        "dca_contribution",
    }
    money_provenance_keys = {
        "capital_amount",
        "initial_capital",
        "total_capital",
        "position_size",
        "recurring_contribution",
    }
    cleaned: dict[str, Any] = {}
    for key, value in extra_parameters.items():
        if key in money_context_keys:
            continue
        if key == "field_provenance" and isinstance(value, dict):
            provenance = {
                provenance_key: provenance_value
                for provenance_key, provenance_value in value.items()
                if provenance_key not in money_provenance_keys
            }
            if provenance:
                cleaned[key] = provenance
            continue
        cleaned[key] = value
    return cleaned


def _should_apply_current_message_asset_grounding(
    *,
    semantic_turn_act: str | None,
    selected_thread_metadata: dict[str, Any],
    snapshot: TaskSnapshot | None,
) -> bool:
    requested_field = _field_base(
        str(selected_thread_metadata.get("requested_field") or "")
    )
    if requested_field == "asset_universe":
        return True
    if semantic_turn_act != "answer_pending_need":
        return True
    if selected_thread_metadata.get("last_stage_outcome") != "await_user_reply":
        return True
    prior = _active_strategy_from_snapshot(snapshot)
    return not bool(prior and prior.asset_universe)


def _contextual_date_range_value(
    *,
    base: Any,
    incoming: dict[str, Any],
    current_user_message: str | None,
    selected_thread_metadata: dict[str, Any],
) -> dict[str, Any]:
    if _has_complete_date_range(incoming):
        return incoming
    del current_user_message, selected_thread_metadata
    return _merged_contextual_date_range(
        base=base,
        incoming=incoming,
    )


def _has_complete_date_range(value: Any) -> bool:
    endpoints = _date_range_endpoints(value)
    return endpoints is not None and all(endpoints)


def _merged_contextual_date_range(
    *,
    base: Any,
    incoming: dict[str, Any],
) -> dict[str, Any]:
    incoming_endpoints = {
        "start": incoming.get("start") or incoming.get("from"),
        "end": incoming.get("end") or incoming.get("to"),
    }
    incoming_endpoints = {
        key: value
        for key, value in incoming_endpoints.items()
        if value not in (None, "", [], {})
    }
    if set(incoming_endpoints) == {"start", "end"}:
        return incoming
    if not isinstance(base, dict):
        return incoming
    merged = {
        "start": base.get("start") or base.get("from"),
        "end": base.get("end") or base.get("to"),
    }
    merged.update(incoming_endpoints)
    return {key: value for key, value in merged.items() if value not in (None, "")}


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


def _should_preserve_prior_asset_context(
    *,
    prior: StrategySummary,
    selected_thread_metadata: dict[str, Any],
    semantic_turn_act: str | None,
    task_relation: str,
) -> bool:
    if not prior.asset_universe:
        return False
    if semantic_turn_act != "answer_pending_need":
        return False
    if task_relation not in {"continue", "refine"}:
        return False
    requested_field = _field_base(
        str(selected_thread_metadata.get("requested_field") or "")
    )
    if requested_field == "asset_universe":
        return False
    return selected_thread_metadata.get("last_stage_outcome") == "await_user_reply"


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
        if (
            key == "field_provenance"
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
        resolution = _trusted_user_mention_resolution(
            updated,
            index=index,
            symbol=symbol,
        ) or _resolve_asset_candidate(
            symbol,
            field=f"asset_universe[{index}]",
            source=_asset_resolution_source_for_canonicalization(
                updated,
                index=index,
                symbol=symbol,
            ),
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


def _trusted_user_mention_resolution(
    strategy: StrategySummary,
    *,
    index: int,
    symbol: str,
) -> AssetResolution | None:
    field = f"asset_universe[{index}]"
    normalized_symbol = str(symbol or "").strip().upper()
    for raw_item in strategy.resolution_provenance:
        if isinstance(raw_item, ResolutionProvenance):
            item = raw_item
        else:
            try:
                item = ResolutionProvenance.model_validate(raw_item)
            except (TypeError, ValueError):
                continue
        if item.source != "user_mention":
            continue
        if item.candidate_kind != "asset" or item.resolution_status != "resolved":
            continue
        if item.validated_by != "provider_catalog":
            continue
        if _field_base(item.field) != "asset_universe":
            continue
        if item.field != field and len(strategy.asset_universe) > 1:
            continue
        canonical = str(item.canonical_symbol or "").strip().upper()
        raw_text = str(item.raw_text or "").strip().upper()
        asset_class = str(item.asset_class or "").strip()
        if asset_class not in _BACKTEST_ASSET_CLASSES:
            continue
        if normalized_symbol not in {canonical, raw_text}:
            continue
        asset = _ProvenanceAsset(
            canonical_symbol=canonical or normalized_symbol,
            asset_class=asset_class,
            raw_symbol=canonical or normalized_symbol,
        )
        return AssetResolution(
            status="resolved",
            raw_text=item.raw_text,
            asset=asset,
            candidates=(asset,),
            provenance=item,
        )
    return None


def _strategy_with_current_message_asset_grounding(
    *,
    strategy: StrategySummary,
    current_user_message: str,
) -> tuple[StrategySummary, list[str]]:
    if not current_user_message.strip():
        return strategy, []
    if not strategy.asset_universe:
        return _strategy_with_missing_asset_grounded_from_current_message(
            strategy=strategy,
            current_user_message=current_user_message,
        )
    if _message_explicitly_mentions_symbol(
        current_user_message,
        symbols=strategy.asset_universe,
    ):
        return strategy, []

    def _resolve_candidate(query: str) -> AssetResolution | None:
        return _resolve_asset_candidate_safely(
            query,
            field="asset_universe[0]",
            source="user_mention",
        )

    current_symbols = [
        symbol
        for symbol in (_normalized_symbol(value) for value in strategy.asset_universe)
        if symbol is not None
    ]
    current_symbol_set = set(current_symbols)
    benchmark_symbol = _normalized_symbol(strategy.comparison_baseline)
    mentions = grounded_asset_mentions_from_text(
        current_user_message,
        resolve_candidate=_resolve_candidate,
        excluded_tokens=current_message_execution_context_tokens(
            current_user_message,
            strategy_type=strategy.strategy_type,
        ),
        limit=5,
    )
    if not mentions:
        repaired_symbols = _without_weak_implicit_current_symbols(
            current_symbols=current_symbols,
            benchmark_symbol=benchmark_symbol,
            current_user_message=current_user_message,
        )
        if repaired_symbols != current_symbols:
            updated = strategy.model_copy(deep=True)
            updated.asset_universe = repaired_symbols
            return updated, ["current_message_asset_grounding_repaired"]
        return strategy, []

    grounded_assets = [
        mention.asset
        for mention in mentions
        if _normalized_symbol(getattr(mention.asset, "canonical_symbol", None))
        != benchmark_symbol
    ]
    grounded_symbols = [
        str(getattr(asset, "canonical_symbol", "") or "").strip().upper()
        for asset in grounded_assets
        if str(getattr(asset, "canonical_symbol", "") or "").strip()
    ]
    grounded_symbols = list(dict.fromkeys(grounded_symbols))
    if not grounded_symbols:
        repaired_symbols = _without_weak_implicit_current_symbols(
            current_symbols=current_symbols,
            benchmark_symbol=benchmark_symbol,
            current_user_message=current_user_message,
        )
        if repaired_symbols != current_symbols:
            updated = strategy.model_copy(deep=True)
            updated.asset_universe = repaired_symbols
            return updated, ["current_message_asset_grounding_repaired"]
        return strategy, []

    grounded_symbols = _without_weak_implicit_short_symbol_mentions(
        grounded_symbols=grounded_symbols,
        grounded_mentions=mentions,
        current_symbols=current_symbols,
        benchmark_symbol=benchmark_symbol,
        current_user_message=current_user_message,
    )
    grounded_symbols = _symbols_corroborated_by_strategy_text(
        symbols=grounded_symbols,
        strategy=strategy,
        benchmark_symbol=benchmark_symbol,
    )
    grounded_symbol_set = set(grounded_symbols)
    if not grounded_symbol_set:
        return strategy, []
    retained_symbols = [
        symbol for symbol in current_symbols if symbol in grounded_symbol_set
    ]
    weak_current_symbols = _weak_implicit_current_symbol_set(
        current_symbols=current_symbols,
        benchmark_symbol=benchmark_symbol,
        current_user_message=current_user_message,
    )
    if retained_symbols:
        repaired_symbols = retained_symbols
    elif current_symbol_set and current_symbol_set.issubset(grounded_symbol_set):
        return strategy, []
    else:
        alternate_grounded_symbols = [
            symbol for symbol in grounded_symbols if symbol not in current_symbol_set
        ]
        if current_symbol_set and not current_symbol_set.issubset(weak_current_symbols):
            if not _grounded_symbols_have_name_support(
                symbols=alternate_grounded_symbols,
                mentions=mentions,
            ):
                return strategy, []
        if current_symbol_set and len(alternate_grounded_symbols) != 1:
            return strategy, []
        repaired_symbols = alternate_grounded_symbols or grounded_symbols
    if repaired_symbols == current_symbols:
        return strategy, []

    asset_class_by_symbol = {
        str(getattr(asset, "canonical_symbol", "") or "").strip().upper(): getattr(
            asset,
            "asset_class",
            None,
        )
        for asset in grounded_assets
    }
    asset_classes = {
        str(asset_class)
        for symbol in repaired_symbols
        if (asset_class := asset_class_by_symbol.get(symbol))
    }
    updated = strategy.model_copy(deep=True)
    updated.asset_universe = repaired_symbols
    if len(asset_classes) == 1:
        updated.asset_class = next(iter(asset_classes))
    elif len(asset_classes) > 1:
        updated.asset_class = "mixed"
    updated.resolution_provenance = _dedupe_resolution_provenance(
        [
            item
            for item in updated.resolution_provenance
            if _field_base(_provenance_field(item)) != "asset_universe"
        ]
        + [
            mention.resolution.provenance
            for mention in mentions
            if str(
                getattr(mention.resolution.asset, "canonical_symbol", "") or ""
            ).strip().upper()
            in repaired_symbols
        ]
    )
    return updated, ["current_message_asset_grounding_repaired"]


def _grounded_symbols_have_name_support(
    *,
    symbols: list[str],
    mentions: list[Any],
) -> bool:
    symbol_set = set(symbols)
    if not symbol_set:
        return False
    return any(
        symbol in symbol_set and grounded_asset_mention_has_name_support(mention)
        for mention in mentions
        if (
            symbol := _normalized_symbol(
                getattr(mention.asset, "canonical_symbol", None)
            )
        )
    )


def _symbols_corroborated_by_strategy_text(
    *,
    symbols: list[str],
    strategy: StrategySummary,
    benchmark_symbol: str | None,
) -> list[str]:
    if len(symbols) <= 1:
        return symbols
    strategy_text = str(strategy.strategy_thesis or "").strip()
    if not strategy_text:
        return symbols

    def _resolve_candidate(query: str) -> AssetResolution | None:
        return _resolve_asset_candidate_safely(
            query,
            field="asset_universe[0]",
            source="user_mention",
        )

    semantic_mentions = grounded_asset_mentions_from_text(
        strategy_text,
        resolve_candidate=_resolve_candidate,
        excluded_tokens=current_message_execution_context_tokens(
            strategy_text,
            strategy_type=strategy.strategy_type,
        ),
        limit=5,
    )
    if not semantic_mentions:
        return symbols

    semantic_symbols = {
        symbol
        for mention in semantic_mentions
        if (
            symbol := _normalized_symbol(
                getattr(mention.asset, "canonical_symbol", None)
            )
        )
        and symbol != benchmark_symbol
    }
    if not semantic_symbols:
        return symbols
    filtered = [symbol for symbol in symbols if symbol in semantic_symbols]
    return filtered or symbols


def _strategy_with_missing_asset_grounded_from_current_message(
    *,
    strategy: StrategySummary,
    current_user_message: str,
) -> tuple[StrategySummary, list[str]]:
    def _resolve_candidate(query: str) -> AssetResolution | None:
        return _resolve_asset_candidate_safely(
            query,
            field="asset_universe[0]",
            source="user_mention",
        )

    benchmark_symbol = _normalized_symbol(strategy.comparison_baseline)
    mentions = grounded_asset_mentions_from_text(
        current_user_message,
        resolve_candidate=_resolve_candidate,
        excluded_tokens=current_message_execution_context_tokens(
            current_user_message,
            strategy_type=strategy.strategy_type,
        ),
        limit=5,
    )
    if not mentions:
        return _strategy_with_missing_asset_from_misplaced_benchmark(
            strategy=strategy,
            current_user_message=current_user_message,
            semantic_mentions=[],
            benchmark_symbol=benchmark_symbol,
            resolve_candidate=_resolve_candidate,
        )
    grounded_assets = [
        mention.asset
        for mention in mentions
        if _normalized_symbol(getattr(mention.asset, "canonical_symbol", None))
        != benchmark_symbol
    ]
    grounded_symbols = [
        str(getattr(asset, "canonical_symbol", "") or "").strip().upper()
        for asset in grounded_assets
        if str(getattr(asset, "canonical_symbol", "") or "").strip()
    ]
    grounded_symbols = list(dict.fromkeys(grounded_symbols))
    if len(grounded_symbols) != 1:
        if not grounded_symbols:
            return _strategy_with_missing_asset_from_misplaced_benchmark(
                strategy=strategy,
                current_user_message=current_user_message,
                semantic_mentions=mentions,
                benchmark_symbol=benchmark_symbol,
                resolve_candidate=_resolve_candidate,
            )
        return strategy, []

    asset_class = str(getattr(grounded_assets[0], "asset_class", "") or "").strip()
    updated = strategy.model_copy(deep=True)
    updated.asset_universe = grounded_symbols
    if asset_class:
        updated.asset_class = asset_class
    updated.resolution_provenance = _dedupe_resolution_provenance(
        [
            item
            for item in updated.resolution_provenance
            if _field_base(_provenance_field(item)) != "asset_universe"
        ]
        + [
            mention.resolution.provenance
            for mention in mentions
            if str(
                getattr(mention.resolution.asset, "canonical_symbol", "") or ""
            ).strip().upper()
            in grounded_symbols
        ]
    )
    return updated, ["current_message_asset_grounding_repaired"]


def _strategy_with_missing_asset_from_misplaced_benchmark(
    *,
    strategy: StrategySummary,
    current_user_message: str,
    semantic_mentions: list[Any],
    benchmark_symbol: str | None,
    resolve_candidate: Any,
) -> tuple[StrategySummary, list[str]]:
    if not benchmark_symbol:
        return strategy, []
    if any(
        _normalized_symbol(getattr(mention.asset, "canonical_symbol", None))
        != benchmark_symbol
        and grounded_asset_mention_has_name_support(mention)
        for mention in semantic_mentions
    ):
        return strategy, []

    ticker_mentions = provider_ticker_mentions_from_text(
        current_user_message,
        resolve_candidate=resolve_candidate,
        excluded_tokens=current_message_execution_context_tokens(
            current_user_message,
            strategy_type=strategy.strategy_type,
        ),
        limit=10,
    )
    matching_mentions = [
        mention
        for mention in ticker_mentions
        if _normalized_symbol(getattr(mention.asset, "canonical_symbol", None))
        == benchmark_symbol
    ]
    if len(matching_mentions) != 1:
        return strategy, []

    mention = matching_mentions[0]
    asset = mention.asset
    asset_class = str(getattr(asset, "asset_class", "") or "").strip()
    updated = strategy.model_copy(deep=True)
    updated.asset_universe = [benchmark_symbol]
    if asset_class:
        updated.asset_class = asset_class
        updated.comparison_baseline = _default_benchmark_for_asset_class(
            asset_class,
            symbols=[benchmark_symbol],
        )
    else:
        updated.comparison_baseline = None
    updated.strategy_thesis = None
    updated.extra_parameters = _without_field_provenance_keys(
        updated.extra_parameters,
        {"comparison_baseline"},
    )
    updated.resolution_provenance = _dedupe_resolution_provenance(
        [
            item
            for item in updated.resolution_provenance
            if _field_base(_provenance_field(item)) != "asset_universe"
        ]
        + [mention.resolution.provenance]
    )
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


def _without_field_provenance_keys(
    extra_parameters: dict[str, Any],
    field_names: set[str],
) -> dict[str, Any]:
    if not extra_parameters:
        return {}
    updated = dict(extra_parameters)
    field_provenance = updated.get("field_provenance")
    if isinstance(field_provenance, dict):
        remaining = {
            key: value
            for key, value in field_provenance.items()
            if key not in field_names
        }
        if remaining:
            updated["field_provenance"] = remaining
        else:
            updated.pop("field_provenance", None)
    return updated


def _without_weak_implicit_current_symbols(
    *,
    current_symbols: list[str],
    benchmark_symbol: str | None,
    current_user_message: str,
) -> list[str]:
    if benchmark_symbol is None or not current_symbols:
        return current_symbols
    weak_symbols = _weak_implicit_current_symbol_set(
        current_symbols=current_symbols,
        benchmark_symbol=benchmark_symbol,
        current_user_message=current_user_message,
    )
    if not weak_symbols:
        return current_symbols
    stronger_symbols = [symbol for symbol in current_symbols if symbol not in weak_symbols]
    return stronger_symbols or current_symbols


def _weak_implicit_current_symbol_set(
    *,
    current_symbols: list[str],
    benchmark_symbol: str | None,
    current_user_message: str,
) -> set[str]:
    if benchmark_symbol is None:
        return set()
    return {
        symbol
        for symbol in current_symbols
        if len(symbol) <= 2
        and not _message_explicitly_mentions_symbol(
            current_user_message,
            symbols=[symbol],
        )
    }


def _without_weak_implicit_short_symbol_mentions(
    *,
    grounded_symbols: list[str],
    grounded_mentions: list[Any],
    current_symbols: list[str],
    benchmark_symbol: str | None,
    current_user_message: str,
) -> list[str]:
    if benchmark_symbol is None or not current_symbols:
        return grounded_symbols

    current_symbol_set = set(current_symbols)
    weak_symbols: set[str] = set()
    for mention in grounded_mentions:
        symbol = _normalized_symbol(getattr(mention.asset, "canonical_symbol", None))
        if symbol is None or symbol not in current_symbol_set:
            continue
        if _message_explicitly_mentions_symbol(current_user_message, symbols=[symbol]):
            continue
        if len(symbol) > 2:
            continue
        raw_text = str(getattr(mention, "raw_text", "") or "").strip()
        if not raw_text or raw_text != raw_text.lower() or len(raw_text.split()) != 1:
            continue
        weak_symbols.add(symbol)

    if not weak_symbols:
        pruned_current_symbols = _without_weak_implicit_current_symbols(
            current_symbols=current_symbols,
            benchmark_symbol=benchmark_symbol,
            current_user_message=current_user_message,
        )
        weak_symbols = set(current_symbols) - set(pruned_current_symbols)
        if not weak_symbols:
            return grounded_symbols

    filtered = [symbol for symbol in grounded_symbols if symbol not in weak_symbols]
    if not filtered:
        filtered = [symbol for symbol in current_symbols if symbol not in weak_symbols]
    if not filtered:
        return grounded_symbols
    return filtered


def _asset_resolution_source_for_canonicalization(
    strategy: StrategySummary,
    *,
    index: int,
    symbol: str,
) -> ResolutionSource:
    field = f"asset_universe[{index}]"
    normalized_symbol = str(symbol or "").strip().upper()
    for item in strategy.resolution_provenance:
        if _field_base(_provenance_field(item)) != "asset_universe":
            continue
        if _provenance_field(item) != field and len(strategy.asset_universe) > 1:
            continue
        raw_text = (
            item.raw_text
            if isinstance(item, ResolutionProvenance)
            else item.get("raw_text")
        )
        canonical = (
            item.canonical_symbol
            if isinstance(item, ResolutionProvenance)
            else item.get("canonical_symbol")
        )
        if str(canonical or "").strip().upper() == normalized_symbol or (
            str(raw_text or "").strip().upper() == normalized_symbol
        ):
            source = (
                item.source
                if isinstance(item, ResolutionProvenance)
                else item.get("source")
            )
            if source in {"llm_extraction", "user_mention"}:
                return source
    return "llm_extraction"


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


def _strategy_with_default_template_for_complete_no_rule_shape(
    strategy: StrategySummary,
) -> tuple[StrategySummary, list[str]]:
    if executable_strategy_type(strategy) in SUPPORTED_STRATEGY_TYPES:
        return strategy, []
    if strategy.strategy_type not in (None, ""):
        return strategy, []
    if not _strategy_has_complete_no_rule_execution_shape(strategy):
        return strategy, []
    if _strategy_supplies_executable_rule_edit(strategy):
        return strategy, []
    updated = strategy.model_copy(deep=True)
    updated.strategy_type = "buy_and_hold"
    _clear_incompatible_strategy_rule_state(updated, "buy_and_hold")
    return updated, ["complete_no_rule_shape_defaulted_to_buy_and_hold"]


def _strategy_has_complete_no_rule_execution_shape(strategy: StrategySummary) -> bool:
    return bool(
        strategy.asset_universe
        and strategy.date_range
        and not strategy.cadence
        and not strategy.entry_logic
        and not strategy.exit_logic
        and not strategy.entry_rule
        and not strategy.exit_rule
        and not strategy.rule_spec
    )


def _strategy_with_separate_benchmark_symbol(
    strategy: StrategySummary,
) -> tuple[StrategySummary, list[str]]:
    benchmark = _normalized_symbol(strategy.comparison_baseline)
    if benchmark is None:
        return strategy, []
    updated = strategy.model_copy(deep=True)
    updated.comparison_baseline = benchmark
    assets = [_normalized_symbol(symbol) for symbol in updated.asset_universe]
    normalized_assets = [symbol for symbol in assets if symbol is not None]
    filtered_assets = [
        symbol
        for symbol in normalized_assets
        if symbol != benchmark
    ]
    if len(filtered_assets) == len(normalized_assets):
        return updated, []
    updated.asset_universe = list(dict.fromkeys(filtered_assets))
    return updated, ["benchmark_symbol_removed_from_asset_universe"]


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
    updated = strategy.model_copy(deep=True)
    if prior_benchmark is not None:
        updated.comparison_baseline = prior_benchmark
        return updated, ["unstated_benchmark_symbol_reverted"]
    updated.comparison_baseline = None
    return updated, ["unstated_benchmark_symbol_cleared"]


def _strategy_with_validated_benchmark_symbol(
    strategy: StrategySummary,
) -> tuple[StrategySummary, list[str]]:
    benchmark = _normalized_symbol(strategy.comparison_baseline)
    if benchmark is None:
        return strategy, []
    try:
        resolution = _resolve_asset_candidate(
            benchmark,
            field="comparison_baseline",
            source="llm_extraction",
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


def _normalized_symbol(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().upper()
    return normalized or None


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
    if field_name == "capital_amount":
        return _strategy_has_user_grounded_capital_amount(strategy)
    if field_name == "cadence":
        return _strategy_has_user_grounded_cadence(strategy)
    return False


def _strategy_has_user_grounded_capital_amount(strategy: StrategySummary) -> bool:
    if strategy.capital_amount is None:
        return False
    return _strategy_field_provenance(strategy, "capital_amount") in (
        _USER_GROUNDED_CAPITAL_SOURCES
    )


def _strategy_has_user_grounded_cadence(strategy: StrategySummary) -> bool:
    if strategy.cadence in (None, "", [], {}):
        return False
    return _strategy_field_provenance(strategy, "cadence") in (
        _USER_GROUNDED_CADENCE_SOURCES
    )


def _strategy_field_provenance(strategy: StrategySummary, field_name: str) -> str:
    field_provenance = dict(strategy.extra_parameters or {}).get("field_provenance")
    if not isinstance(field_provenance, dict):
        return ""
    return str(field_provenance.get(field_name) or "").strip()


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


def _fresh_complete_restatement_started_new_confirmation(
    *,
    interpretation: StructuredInterpretation,
    selected_thread_metadata: dict[str, Any],
    expects_strategy_route: bool,
    requires_clarification: bool,
    ambiguous_fields: list[AmbiguousField],
    unsupported_constraints: list[UnsupportedConstraint],
    missing_required_fields: list[str],
) -> bool:
    if selected_thread_metadata.get("last_stage_outcome") != "await_user_reply":
        return False
    requested_field = _field_base(
        str(selected_thread_metadata.get("requested_field") or "")
    )
    if not requested_field:
        return False
    if interpretation.semantic_turn_act != "new_idea":
        return False
    if interpretation.task_relation != "new_task":
        return False
    return _strategy_is_semantically_confirmable(
        expects_strategy_route=expects_strategy_route,
        ambiguous_fields=ambiguous_fields,
        unsupported_constraints=unsupported_constraints,
        missing_required_fields=missing_required_fields,
    ) and not requires_clarification


def _strategy_route_expected(
    *,
    intent: IntentName,
    semantic_turn_act: SemanticTurnAct | None,
) -> bool:
    return intent in {"strategy_drafting", "backtest_execution"} or (
        semantic_turn_act in STRATEGY_TURN_ACTS
    )


def _educational_turn_has_strategy_baggage(
    *,
    interpretation: StructuredInterpretation,
    expects_strategy_route: bool,
) -> bool:
    if interpretation.semantic_turn_act != "educational_question":
        return False
    return bool(
        expects_strategy_route
        or _strategy_has_content(interpretation.candidate_strategy_draft)
        or interpretation.requires_clarification
        or interpretation.missing_required_fields
        or interpretation.ambiguous_fields
        or interpretation.unsupported_constraints
    )


def _misclassified_dca_education_has_strategy_baggage(
    *,
    interpretation: StructuredInterpretation,
    expects_strategy_route: bool,
    dca_education_answer: str | None,
) -> bool:
    if (
        interpretation.semantic_turn_act == "educational_question"
        or dca_education_answer is None
    ):
        return False
    return bool(
        expects_strategy_route
        or _strategy_has_content(interpretation.candidate_strategy_draft)
        or interpretation.requires_clarification
        or interpretation.missing_required_fields
        or interpretation.ambiguous_fields
        or interpretation.unsupported_constraints
    )


def _dca_education_answer_for_message(message: str) -> str | None:
    tokens = _plain_word_tokens(message)
    if not tokens:
        return None
    if not _message_asks_for_strategy_explanation(tokens):
        return None
    if not _message_mentions_dca_concept(tokens):
        return None
    return (
        "Dollar cost averaging means investing a set amount on a recurring "
        "schedule instead of all at once. In Argus, the closest runnable version "
        "is recurring buys/DCA: choose one asset, a date range, a cadence, and a "
        "contribution amount, and I can simulate the historical result."
    )


def _message_asks_for_strategy_explanation(tokens: list[str]) -> bool:
    if any(token in {"explain", "define", "meaning"} for token in tokens):
        return True
    if any(token in {"mean", "means"} for token in tokens) and "what" in tokens:
        return True
    explanation_starts = (
        ("what", "is"),
        ("what", "are"),
        ("what", "does"),
        ("tell", "me", "about"),
    )
    if any(
        _token_sequence_spans(tokens, list(sequence))
        for sequence in explanation_starts
    ):
        return True
    return "how" in tokens and any(token in {"work", "works"} for token in tokens)


def _message_mentions_dca_concept(tokens: list[str]) -> bool:
    dca_terms = (
        ("dca",),
        ("dollar", "cost", "averaging"),
        ("recurring", "buy"),
        ("recurring", "buys"),
    )
    return any(_token_sequence_spans(tokens, list(term)) for term in dca_terms)


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
    return dedupe_resolution_provenance_items(provenance)


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
