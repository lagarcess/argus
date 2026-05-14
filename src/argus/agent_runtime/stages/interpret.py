from __future__ import annotations

import asyncio
import inspect
from typing import Any

from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.confirmation_artifacts import (
    validate_confirmation_execution_payload,
)
from argus.agent_runtime.extraction import detect_unsupported_constraints
from argus.agent_runtime.profile.response_profile import (
    resolve_effective_response_profile,
)
from argus.agent_runtime.resolution import AssetResolution
from argus.agent_runtime.resolution import (
    resolve_asset_candidate as runtime_resolve_asset_candidate,
)
from argus.agent_runtime.result_followups import (
    compose_result_followup_response,
    fallback_result_followup_response,
)
from argus.agent_runtime.rule_specs import (
    indicator_parameters_from_strategy as canonical_indicator_parameters_from_strategy,
)
from argus.agent_runtime.rule_specs import (
    moving_average_crossover_rules_from_text,
    moving_average_crossover_text,
    opposite_moving_average_crossover_rule,
    rule_spec_from_strategy,
    strategy_rule,
)
from argus.agent_runtime.semantic_integrity import (
    SemanticIntegrityReport,
    conserve_semantic_constraints,
)
from argus.agent_runtime.stages.interpret_types import (
    InterpretationRequest,
    InterpretDecision,
    SemanticTurnAct,
    StageResult,
    StructuredInterpretation,
    StructuredInterpreter,
)
from argus.agent_runtime.state.models import (
    AmbiguousField,
    ArtifactReference,
    ConfirmationPayload,
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
    executable_strategy_type,
    resolve_date_range,
    strategy_can_be_approved,
)
from argus.domain.backtesting.rules import validate_rule_spec
from argus.domain.indicators import (
    IndicatorExecutionSpec,
    executable_indicator_spec,
    normalize_indicator_parameters,
)
from argus.domain.market_data import resolve_asset

_DEFAULT_RESOLVE_ASSET = resolve_asset

STRATEGY_TURN_ACTS: set[SemanticTurnAct] = {
    "new_idea",
    "answer_pending_need",
    "refine_current_idea",
    "approval",
    "unsupported_request",
}

CONTEXTUAL_PATCH_TURN_ACTS = {
    "answer_pending_need",
    "approval",
    "refine_current_idea",
}

CONFIRMATION_EDIT_ACTION_FIELDS = {
    "change_asset": ("asset_universe", "What asset should I use instead?"),
    "change_dates": ("date_range", "What date range should I use instead?"),
    "adjust_assumptions": (
        "assumption",
        "Which assumption do you want to adjust: starting capital, timeframe, fees, or slippage?",
    ),
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
        user=user,
    )
    if structured_action_result is not None:
        return structured_action_result
    selected_metadata = dict(selected_thread_metadata or {})
    typed_pending_result = _typed_pending_need_fallback_stage_result_if_applicable(
        user=user,
        snapshot=snapshot,
        selected_thread_metadata=selected_metadata,
        current_user_message=state.current_user_message,
        capability_contract=capability_contract,
    )
    if typed_pending_result is not None:
        return typed_pending_result
    if structured_interpreter is None:
        return _offline_interpreter_unavailable_result(
            user=user,
            snapshot=snapshot,
            current_user_message=state.current_user_message,
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
        return _offline_interpreter_unavailable_result(
            user=user,
            snapshot=snapshot,
            current_user_message=state.current_user_message,
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
            current_user_message=state.current_user_message,
            selected_thread_metadata=selected_thread_metadata,
            prior_strategy=_active_strategy_from_snapshot(snapshot),
            optional_parameter_values=optional_parameter_values,
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
        return StageResult(
            outcome="needs_clarification",
            decision=decision,
            stage_patch=optional_parameter_stage_patch,
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


def _route_contextual_money_answer(
    *,
    strategy: StrategySummary,
    selected_thread_metadata: dict[str, Any],
) -> tuple[StrategySummary, dict[str, Any]]:
    requested_field = str(selected_thread_metadata.get("requested_field") or "")
    if requested_field not in {"initial_capital", "capital_amount"}:
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
            "assistant_response": _offline_recovery_message(snapshot),
        },
    )


def _offline_recovery_message(snapshot: TaskSnapshot | None) -> str:
    if snapshot is not None and snapshot.pending_strategy_summary is not None:
        strategy = snapshot.pending_strategy_summary
        assets = ", ".join(strategy.asset_universe) or "the current asset"
        strategy_label = (strategy.strategy_type or "strategy").replace("_", " ")
        if snapshot.active_confirmation_reference is None:
            return (
                f"I still have the {assets} {strategy_label} draft in this chat, "
                "but the interpreter was unavailable before I could safely apply that "
                "change. Please retry in a moment."
            )
        assumptions_response = _draft_assumptions_response(snapshot)
        if assumptions_response is not None:
            return (
                assumptions_response
                + " I could not reliably interpret your latest message, so I left the "
                "visible draft unchanged."
            )
        return (
            f"I still have the {assets} {strategy_label} draft in this chat, "
            "but the interpreter was unavailable before I could safely apply that "
            "change. Please try again in a moment or use the visible card action to "
            "adjust the draft."
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


def _structured_action_stage_result_if_applicable(
    *,
    state: RunState,
    snapshot: TaskSnapshot | None,
    selected_thread_metadata: dict[str, Any],
    user: UserState,
) -> StageResult | None:
    del user
    action = state.structured_action
    if action is None:
        return None
    if action.presentation == "result":
        return _result_action_stage_result_if_applicable(
            state=state,
            snapshot=snapshot,
        )
    if action.presentation != "confirmation":
        return None
    stale_action_response = _stale_confirmation_action_response(
        action=action,
        snapshot=snapshot,
    )
    if stale_action_response is not None:
        return StageResult(
            outcome="await_user_reply",
            stage_patch={
                "assistant_prompt": stale_action_response,
                "requested_field": None,
                "missing_required_fields": [],
            },
        )
    if snapshot is None or snapshot.pending_strategy_summary is None:
        return StageResult(
            outcome="await_user_reply",
            stage_patch={
                "assistant_prompt": (
                    "I do not have an active confirmation to change. "
                    "Describe the investing idea again and I will prepare a fresh draft."
                ),
                "requested_field": None,
                "missing_required_fields": [],
            },
        )

    pending = snapshot.pending_strategy_summary.model_copy(deep=True)
    action_type = action.type
    if action_type == "run_backtest":
        if not _prior_stage_was_await_approval(selected_thread_metadata):
            return StageResult(
                outcome="ready_for_confirmation",
                stage_patch={
                    "candidate_strategy_draft": pending.model_dump(mode="python"),
                    "assistant_prompt": None,
                },
            )
        approved = pending
        confirmation_payload = _validated_approval_confirmation_payload_from_state(
            state=state,
            approved_strategy=approved,
        )
        if confirmation_payload is None:
            return StageResult(
                outcome="ready_for_confirmation",
                stage_patch={
                    "candidate_strategy_draft": approved.model_dump(mode="python"),
                    "assistant_prompt": None,
                },
            )
        if not strategy_can_be_approved(approved):
            return StageResult(
                outcome="needs_clarification",
                stage_patch={
                    "candidate_strategy_draft": approved.model_dump(mode="python"),
                    "missing_required_fields": missing_required_fields_for_strategy(
                        approved,
                        contract=build_default_capability_contract(),
                    ),
                },
            )
        return StageResult(
            outcome="approved_for_execution",
            stage_patch={
                "candidate_strategy_draft": approved.model_dump(mode="python"),
                "confirmation_payload": confirmation_payload,
            },
        )

    if action_type in CONFIRMATION_EDIT_ACTION_FIELDS:
        requested_field, prompt = CONFIRMATION_EDIT_ACTION_FIELDS[action_type]
        return StageResult(
            outcome="await_user_reply",
            stage_patch={
                "candidate_strategy_draft": pending.model_dump(mode="python"),
                "assistant_prompt": prompt,
                "requested_field": requested_field,
                "missing_required_fields": [requested_field],
                "response_intent": {
                    "kind": "clarification",
                    "semantic_needs": [_semantic_need_for_action(action_type)],
                    "requested_fields": [requested_field],
                    "facts": {
                        "strategy": pending.model_dump(mode="python"),
                        "current_user_message": state.current_user_message,
                        "structured_action": action.model_dump(mode="python"),
                    },
                    "options": [],
                },
            },
        )

    if action_type == "cancel_confirmation":
        return StageResult(
            outcome="ready_to_respond",
            stage_patch={
                "candidate_strategy_draft": StrategySummary().model_dump(mode="python"),
                "assistant_response": "No problem. I will leave that draft unrun.",
            },
        )
    return None


def _typed_pending_need_fallback_stage_result_if_applicable(
    *,
    user: UserState,
    snapshot: TaskSnapshot | None,
    selected_thread_metadata: dict[str, Any],
    current_user_message: str,
    capability_contract: Any,
) -> StageResult | None:
    if snapshot is None or snapshot.pending_strategy_summary is None:
        return None
    requested_field = _requested_pending_field(
        snapshot=snapshot,
        selected_thread_metadata=selected_thread_metadata,
    )
    if requested_field not in {"date_range", "asset_universe", "entry_logic"}:
        return None

    pending = snapshot.pending_strategy_summary.model_copy(deep=True)
    reason_code = ""
    resolution_provenance: list[ResolutionProvenance] = list(
        pending.resolution_provenance
    )
    if requested_field == "date_range":
        resolved = resolve_date_range(current_user_message)
        if resolved.used_default:
            return None
        pending.date_range = resolved.label
        reason_code = "typed_pending_date_answer_applied"
    elif requested_field == "asset_universe":
        resolution = _resolve_asset_candidate(
            current_user_message,
            field="asset_universe[0]",
            source="llm_extraction",
        )
        resolution_provenance.append(resolution.provenance)
        if resolution.status != "resolved" or resolution.asset is None:
            return None
        pending.asset_universe = [resolution.asset.canonical_symbol]
        pending.asset_class = resolution.asset.asset_class
        pending.resolution_provenance = _dedupe_resolution_provenance(
            resolution_provenance
        )
        reason_code = "typed_pending_asset_answer_applied"
    elif requested_field == "entry_logic":
        rules = moving_average_crossover_rules_from_text(current_user_message)
        if rules is None:
            return None
        entry_rule, exit_rule = rules
        pending.entry_rule = entry_rule
        pending.exit_rule = exit_rule
        pending.rule_spec = None
        pending.entry_logic = moving_average_crossover_text(entry_rule)
        pending.exit_logic = moving_average_crossover_text(exit_rule)
        pending.extra_parameters = {
            **pending.extra_parameters,
            "entry_rule": entry_rule,
            "exit_rule": exit_rule,
        }
        resolved = resolve_date_range(current_user_message)
        if not resolved.used_default:
            pending.date_range = resolved.label
        reason_code = "typed_pending_signal_rule_answer_applied"

    pending = _strategy_with_execution_defaults(_canonicalized_strategy(pending))
    missing_required_fields = missing_required_fields_for_strategy(
        pending,
        contract=capability_contract,
    )
    effective_profile = resolve_effective_response_profile(
        user=user,
        explicit_overrides=None,
    )
    decision = InterpretDecision(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=bool(missing_required_fields),
        user_goal_summary=(
            f"User answered the pending {requested_field.replace('_', ' ')} question."
        ),
        candidate_strategy_draft=pending,
        missing_required_fields=missing_required_fields,
        optional_parameter_opportunity=list(capability_contract.optional_defaults),
        confidence=0.72,
        arbitration_mode="deterministic",
        reason_codes=[
            "llm_interpreter_unavailable",
            reason_code,
            "typed_pending_need_validator_used",
        ],
        effective_response_profile=effective_profile,
        resolution_provenance=list(pending.resolution_provenance),
        semantic_turn_act="answer_pending_need",
    )
    return StageResult(
        outcome="needs_clarification"
        if missing_required_fields
        else "ready_for_confirmation",
        decision=decision,
        stage_patch={"requested_field": None},
    )


def _requested_pending_field(
    *,
    snapshot: TaskSnapshot,
    selected_thread_metadata: dict[str, Any],
) -> str | None:
    requested = selected_thread_metadata.get("requested_field")
    if isinstance(requested, str) and requested.strip():
        return _field_base(requested)
    pending = snapshot.pending_strategy_summary
    if pending is None:
        return None
    if not pending.date_range:
        return "date_range"
    if not pending.asset_universe:
        return "asset_universe"
    if (
        executable_strategy_type(pending) == "signal_strategy"
        and not _has_executable_signal_rule(pending)
    ):
        return "entry_logic"
    return None


def _result_action_stage_result_if_applicable(
    *,
    state: RunState,
    snapshot: TaskSnapshot | None,
) -> StageResult | None:
    action = state.structured_action
    if action is None or action.type != "refine_strategy":
        return None
    reference = (
        snapshot.latest_backtest_result_reference if snapshot is not None else None
    )
    if reference is None:
        return StageResult(
            outcome="ready_to_respond",
            stage_patch={
                "assistant_response": (
                    "I do not have a completed result to refine. Run a strategy "
                    "first, then use Refine strategy from the result card."
                ),
            },
        )
    strategy = _strategy_from_result_action_snapshot(snapshot=snapshot)
    latest_run_id = _latest_run_id_for_action(
        action_payload=action.payload,
        reference=reference,
    )
    return StageResult(
        outcome="await_user_reply",
        stage_patch={
            "candidate_strategy_draft": strategy.model_dump(mode="python"),
            "assistant_prompt": "What would you like to change about this strategy?",
            "requested_field": "refinement",
            "missing_required_fields": ["refinement"],
            "response_intent": {
                "kind": "clarification",
                "semantic_needs": [],
                "requested_fields": ["refinement"],
                "facts": {
                    "strategy": strategy.model_dump(mode="python"),
                    "current_user_message": state.current_user_message,
                    "structured_action": action.model_dump(mode="python"),
                    "latest_run_id": latest_run_id,
                    "latest_result_reference": reference.model_dump(mode="python"),
                },
                "options": [],
            },
        },
    )


def _strategy_from_result_action_snapshot(
    *,
    snapshot: TaskSnapshot | None,
) -> StrategySummary:
    if snapshot is not None and snapshot.confirmed_strategy_summary is not None:
        return snapshot.confirmed_strategy_summary.model_copy(deep=True)
    if snapshot is not None and snapshot.latest_backtest_result_reference is not None:
        return _strategy_from_result_reference(snapshot.latest_backtest_result_reference)
    return StrategySummary()


def _latest_run_id_for_action(
    *,
    action_payload: dict[str, Any],
    reference: ArtifactReference,
) -> str:
    raw_run_id = action_payload.get("run_id") or action_payload.get("runId")
    if raw_run_id is not None:
        run_id = str(raw_run_id).strip()
        if run_id:
            return run_id
    return reference.artifact_id


def _strategy_from_result_reference(reference: ArtifactReference) -> StrategySummary:
    metadata = dict(reference.metadata)
    config = metadata.get("config_snapshot")
    config_snapshot = dict(config) if isinstance(config, dict) else {}
    resolved_strategy = config_snapshot.get("resolved_strategy")
    payload = dict(resolved_strategy) if isinstance(resolved_strategy, dict) else {}
    resolved_parameters = config_snapshot.get("resolved_parameters")
    parameters = (
        dict(resolved_parameters) if isinstance(resolved_parameters, dict) else {}
    )

    if not payload.get("strategy_type") and config_snapshot.get("template"):
        payload["strategy_type"] = config_snapshot["template"]
    if not payload.get("asset_class") and metadata.get("asset_class"):
        payload["asset_class"] = metadata["asset_class"]
    if not payload.get("asset_universe"):
        symbols = payload.get("symbols") or config_snapshot.get("symbols")
        if isinstance(symbols, list):
            payload["asset_universe"] = [str(symbol) for symbol in symbols if symbol]
    if not payload.get("date_range"):
        payload["date_range"] = parameters.get("date_range") or config_snapshot.get(
            "date_range"
        )

    allowed_fields = set(StrategySummary.model_fields)
    strategy_payload = {
        key: value
        for key, value in payload.items()
        if key in allowed_fields and value not in (None, "", [], {})
    }
    try:
        return StrategySummary.model_validate(strategy_payload)
    except Exception:
        return StrategySummary()


def _prior_stage_was_await_approval(metadata: dict[str, Any]) -> bool:
    return str(metadata.get("last_stage_outcome") or "") == "await_approval"


def _semantic_need_for_action(action_type: str) -> str:
    mapping = {
        "change_asset": "asset_target",
        "change_dates": "period",
        "adjust_assumptions": "assumption",
    }
    return mapping[action_type]


def _approval_stage_result_if_applicable(
    *,
    decision: InterpretDecision,
    snapshot: TaskSnapshot | None,
    state: RunState,
    selected_thread_metadata: dict[str, Any],
) -> StageResult | None:
    if decision.semantic_turn_act != "approval":
        return None
    if not _prior_stage_was_await_approval(selected_thread_metadata):
        return None
    if snapshot is None or snapshot.pending_strategy_summary is None:
        return None
    approved_strategy = snapshot.pending_strategy_summary.model_copy(deep=True)
    confirmation_payload = _validated_approval_confirmation_payload_from_state(
        state=state,
        approved_strategy=approved_strategy,
    )
    if confirmation_payload is None:
        return StageResult(
            outcome="ready_for_confirmation",
            decision=decision.model_copy(
                update={
                    "intent": "backtest_execution",
                    "task_relation": "continue",
                    "requires_clarification": False,
                    "candidate_strategy_draft": approved_strategy,
                    "missing_required_fields": [],
                    "semantic_turn_act": "approval",
                }
            ),
            stage_patch={
                "assistant_prompt": None,
            },
        )
    if not strategy_can_be_approved(approved_strategy):
        return None
    return StageResult(
        outcome="approved_for_execution",
        decision=decision.model_copy(
            update={
                "intent": "backtest_execution",
                "task_relation": "continue",
                "requires_clarification": False,
                "candidate_strategy_draft": approved_strategy,
                "missing_required_fields": [],
                "semantic_turn_act": "approval",
            }
        ),
        stage_patch={
            "confirmation_payload": confirmation_payload,
        },
    )


def _retry_failed_action_stage_result_if_applicable(
    *,
    decision: InterpretDecision,
    snapshot: TaskSnapshot | None,
) -> StageResult | None:
    if decision.semantic_turn_act != "retry_failed_action":
        return None
    reference = (
        snapshot.latest_failed_action_reference if snapshot is not None else None
    )
    launch_payload = _launch_payload_from_failed_action(reference)
    if launch_payload is None:
        return StageResult(
            outcome="ready_to_respond",
            decision=decision.model_copy(
                update={
                    "intent": "conversation_followup",
                    "task_relation": "continue",
                    "requires_clarification": False,
                    "missing_required_fields": [],
                }
            ),
            stage_patch={
                "assistant_response": (
                    "I do not have a failed run payload to retry. Use the visible "
                    "Run backtest action again, or confirm the strategy you want me "
                    "to run."
                )
            },
        )
    if not _failed_action_is_retryable(reference):
        return StageResult(
            outcome="ready_to_respond",
            decision=decision.model_copy(
                update={
                    "intent": "conversation_followup",
                    "task_relation": "continue",
                    "requires_clarification": False,
                    "missing_required_fields": [],
                }
            ),
            stage_patch={
                "assistant_response": _non_retryable_failed_action_response(reference)
            },
        )
    return StageResult(
        outcome="approved_for_execution",
        decision=decision.model_copy(
            update={
                "intent": "backtest_execution",
                "task_relation": "continue",
                "requires_clarification": False,
                "candidate_strategy_draft": StrategySummary(),
                "missing_required_fields": [],
            }
        ),
        stage_patch={"confirmation_payload": launch_payload},
    )


def _launch_payload_from_failed_action(
    reference: ArtifactReference | None,
) -> dict[str, Any] | None:
    if reference is None or reference.artifact_kind != "failed_action":
        return None
    metadata = dict(reference.metadata)
    if metadata.get("action_type") != "run_backtest":
        return None
    launch_payload = metadata.get("launch_payload")
    if not isinstance(launch_payload, dict) or not launch_payload:
        return None
    return dict(launch_payload)


def _failed_action_is_retryable(reference: ArtifactReference | None) -> bool:
    if reference is None or reference.artifact_kind != "failed_action":
        return False
    retryable = dict(reference.metadata).get("retryable")
    return retryable is not False


def _non_retryable_failed_action_response(reference: ArtifactReference | None) -> str:
    metadata = dict(reference.metadata) if reference is not None else {}
    message = metadata.get("user_safe_message") or metadata.get("error")
    if isinstance(message, str) and message.strip():
        return (
            f"I still have the failed setup, but rerunning the same payload will "
            f"hit the same blocker: {message.strip()} Adjust the rule, asset, or "
            "date range and I will keep the idea intact."
        )
    return (
        "I still have the failed setup, but rerunning the same payload will hit "
        "the same blocker. Adjust the rule, asset, or date range and I will keep "
        "the idea intact."
    )


def _pending_artifact_followup_stage_result_if_applicable(
    *,
    decision: InterpretDecision,
    snapshot: TaskSnapshot | None,
) -> StageResult | None:
    if not _has_pending_confirmation_context(snapshot):
        return None
    requested_assumptions = decision.result_followup_focus == "assumptions"
    pending_without_result = (
        decision.semantic_turn_act == "result_followup"
        and snapshot is not None
        and snapshot.latest_backtest_result_reference is None
    )
    if not requested_assumptions and not pending_without_result:
        return None
    draft_response = _draft_assumptions_response(snapshot)
    if draft_response is None:
        return None
    return StageResult(
        outcome="ready_to_respond",
        decision=decision.model_copy(
            update={
                "intent": "conversation_followup",
                "requires_clarification": False,
                "missing_required_fields": [],
            }
        ),
        stage_patch={"assistant_response": draft_response},
    )


async def _artifact_followup_stage_result_if_applicable(
    *,
    decision: InterpretDecision,
    snapshot: TaskSnapshot | None,
    current_user_message: str,
) -> StageResult | None:
    if not _decision_targets_result_artifact(decision=decision, snapshot=snapshot):
        return None
    focus = decision.result_followup_focus or "general"
    if focus == "assumptions":
        draft_response = _draft_assumptions_response(snapshot)
        if draft_response is not None:
            return StageResult(
                outcome="ready_to_respond",
                decision=decision.model_copy(
                    update={
                        "intent": "conversation_followup",
                        "requires_clarification": False,
                        "missing_required_fields": [],
                    }
                ),
                stage_patch={"assistant_response": draft_response},
            )
    reference = (
        snapshot.latest_backtest_result_reference if snapshot is not None else None
    )
    if reference is None:
        return None
    metadata = dict(reference.metadata)
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
    return StageResult(
        outcome="ready_to_respond",
        decision=decision.model_copy(
            update={
                "requires_clarification": False,
                "missing_required_fields": [],
                "semantic_turn_act": "result_followup",
                "result_followup_focus": focus,
            }
        ),
        stage_patch={"assistant_response": response},
    )


def _decision_targets_result_artifact(
    *,
    decision: InterpretDecision,
    snapshot: TaskSnapshot | None,
) -> bool:
    if snapshot is None or snapshot.latest_backtest_result_reference is None:
        return False
    if decision.semantic_turn_act == "result_followup":
        return True
    return decision.intent == "results_explanation"


def _stale_confirmation_action_response(
    *,
    action: StructuredActionContext,
    snapshot: TaskSnapshot | None,
) -> str | None:
    reference = (
        snapshot.active_confirmation_reference if snapshot is not None else None
    )
    if reference is None:
        return None
    payload = dict(action.payload or {})
    clicked_id = str(
        payload.get("artifact_id") or payload.get("confirmation_id") or ""
    ).strip()
    active_id = str(
        reference.metadata.get("confirmation_id") or reference.artifact_id
    ).strip()
    if clicked_id and active_id and clicked_id != active_id:
        return (
            "That confirmation was updated. Use the latest visible card and I will "
            "keep the current draft intact."
        )
    clicked_hash = str(payload.get("launch_payload_hash") or "").strip()
    active_hash = str(reference.metadata.get("launch_payload_hash") or "").strip()
    if clicked_hash and active_hash and clicked_hash != active_hash:
        return (
            "That confirmation payload is stale. Use the latest visible card and I "
            "will keep the current draft intact."
        )
    return None


def _has_pending_confirmation_context(snapshot: TaskSnapshot | None) -> bool:
    return bool(
        snapshot is not None
        and (
            snapshot.active_confirmation_reference is not None
            or snapshot.pending_strategy_summary is not None
        )
    )


def _draft_assumptions_response(snapshot: TaskSnapshot | None) -> str | None:
    if snapshot is None:
        return None
    assumptions = _active_confirmation_assumptions(snapshot)
    if not assumptions and snapshot.pending_strategy_summary is not None:
        assumptions = list(snapshot.pending_strategy_summary.assumptions)
    if not assumptions and snapshot.pending_strategy_summary is not None:
        assumptions = _inferred_strategy_assumptions(snapshot.pending_strategy_summary)
    if not assumptions:
        return None
    return "For the visible draft, I am using: " + "; ".join(assumptions) + "."


def _active_confirmation_assumptions(snapshot: TaskSnapshot) -> list[str]:
    reference = snapshot.active_confirmation_reference
    if reference is None:
        return []
    metadata = dict(reference.metadata)
    for key in ("confirmation_card", "card", "presentation"):
        card = metadata.get(key)
        if isinstance(card, dict):
            assumptions = card.get("assumptions")
            if isinstance(assumptions, list):
                return [str(item) for item in assumptions if str(item).strip()]
    assumptions = metadata.get("assumptions")
    if isinstance(assumptions, list):
        return [str(item) for item in assumptions if str(item).strip()]
    return []


def _inferred_strategy_assumptions(strategy: StrategySummary) -> list[str]:
    assumptions = ["Long-only", "Equal weight"]
    if strategy.comparison_baseline:
        assumptions.append(f"Benchmark: {strategy.comparison_baseline}")
    elif strategy.asset_class == "crypto":
        assumptions.append("Benchmark: BTC")
    elif strategy.asset_class == "equity":
        assumptions.append("Benchmark: SPY")
    if strategy.timeframe:
        assumptions.append(f"Timeframe: {strategy.timeframe}")
    return assumptions


def _approval_optional_parameters_from_state(state: RunState) -> dict[str, Any]:
    payload = state.confirmation_payload
    if payload is None:
        return {}
    if isinstance(payload, ConfirmationPayload):
        return dict(payload.optional_parameters)
    if isinstance(payload, dict):
        optional_parameters = payload.get("optional_parameters")
        if isinstance(optional_parameters, dict):
            return dict(optional_parameters)
    return {}


def _validated_approval_confirmation_payload_from_state(
    *,
    state: RunState,
    approved_strategy: StrategySummary,
) -> dict[str, Any] | None:
    payload = _confirmation_payload_dict(state.confirmation_payload)
    if not _confirmation_payload_matches_visible_strategy(payload, approved_strategy):
        return None
    if not _confirmation_payload_is_validated_executable(payload):
        return None
    return payload


def _confirmation_payload_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, ConfirmationPayload):
        return value.model_dump(mode="python")
    if isinstance(value, dict):
        return dict(value)
    return {}


def _confirmation_payload_matches_visible_strategy(
    payload: dict[str, Any],
    strategy: StrategySummary,
) -> bool:
    payload_strategy = payload.get("strategy")
    if not isinstance(payload_strategy, dict):
        return False
    visible_strategy = strategy.model_dump(mode="python")
    fields_that_bind_launch_truth = {
        "strategy_type",
        "asset_universe",
        "asset_class",
        "date_range",
        "entry_logic",
        "exit_logic",
        "entry_rule",
        "exit_rule",
        "rule_spec",
        "cadence",
        "capital_amount",
    }
    for field in fields_that_bind_launch_truth:
        if _normalized_launch_binding_value(payload_strategy.get(field)) != (
            _normalized_launch_binding_value(visible_strategy.get(field))
        ):
            return False
    return True


def _confirmation_payload_is_validated_executable(payload: dict[str, Any]) -> bool:
    validation = payload.get("validation")
    return (
        isinstance(validation, dict)
        and validation.get("executable") is True
        and validate_confirmation_execution_payload(payload).executable
    )


def _normalized_launch_binding_value(value: Any) -> Any:
    if isinstance(value, list):
        return [str(item).strip().upper() for item in value if str(item).strip()]
    if isinstance(value, str):
        return value.strip()
    if value in (None, "", [], {}):
        return None
    return value


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
        semantic_turn_act in CONTEXTUAL_PATCH_TURN_ACTS
        or task_relation == "refine"
        or _strategy_looks_like_pending_artifact_patch(
            prior=prior,
            strategy=strategy,
            selected_thread_metadata=selected_thread_metadata,
        )
    )
    if not should_merge:
        return strategy
    merged = prior.model_copy(deep=True)
    incoming = strategy.model_dump(mode="python")
    for key, value in incoming.items():
        if key in {"raw_user_phrasing", "strategy_thesis"}:
            continue
        if value in (None, "", [], {}):
            continue
        setattr(merged, key, value)
    if strategy.raw_user_phrasing:
        merged.raw_user_phrasing = strategy.raw_user_phrasing
    return merged


def _strategy_looks_like_pending_artifact_patch(
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
        return _strategy_supplies_executable_rule_patch(strategy)
    if requested_field == "refinement":
        return _strategy_has_execution_anchor(strategy) and bool(
            prior.asset_universe or prior.date_range
        )
    return False


def _strategy_supplies_executable_rule_patch(strategy: StrategySummary) -> bool:
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
    allowed_missing_fields = set(
        missing_required_fields_for_strategy(strategy, contract=contract)
    )
    missing = [
        field
        for field in interpretation.missing_required_fields
        if isinstance(field, str) and field and field in allowed_missing_fields
    ]
    missing.extend(missing_required_fields_for_strategy(strategy, contract=contract))
    return list(dict.fromkeys(missing))


def missing_required_fields_for_strategy(
    strategy: StrategySummary,
    *,
    contract: Any,
) -> list[str]:
    strategy_type = executable_strategy_type(strategy)
    required = list(contract.required_fields)
    if strategy_type == "dca_accumulation":
        required = [
            field_name
            for field_name in required
            if field_name not in {"entry_logic", "exit_logic"}
        ]
        if strategy.capital_amount is None:
            required.append("capital_amount")
    if strategy_type == "buy_and_hold":
        required = ["asset_universe", "date_range"]
    if strategy_type == "signal_strategy":
        required = [
            field_name
            for field_name in required
            if field_name != "exit_logic"
        ]
    missing: list[str] = []
    payload = strategy.model_dump(mode="python")
    for field_name in required:
        value = payload.get(field_name)
        if isinstance(value, list):
            if not value:
                missing.append(field_name)
        elif value is None or value == "":
            missing.append(field_name)
    if strategy_type == "signal_strategy" and not _has_executable_signal_rule(strategy):
        missing.append("entry_logic")
    return list(dict.fromkeys(missing))


def _has_executable_signal_rule(strategy: StrategySummary) -> bool:
    return bool(strategy_rule(strategy, "entry") or _valid_rule_spec_from_strategy(strategy))


def _valid_rule_spec_from_strategy(strategy: StrategySummary) -> dict[str, Any] | None:
    rule_spec = rule_spec_from_strategy(strategy)
    if rule_spec is None:
        return None
    try:
        validate_rule_spec(rule_spec)
    except ValueError:
        return None
    return rule_spec


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
