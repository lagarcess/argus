from __future__ import annotations

import asyncio
import inspect
from typing import Any

from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.extraction import detect_unsupported_constraints
from argus.agent_runtime.profile.response_profile import (
    resolve_effective_response_profile,
)
from argus.agent_runtime.resolution import AssetResolution
from argus.agent_runtime.resolution import (
    resolve_asset_candidate as runtime_resolve_asset_candidate,
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
    strategy_can_be_approved,
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
    if structured_interpreter is None:
        return _offline_interpreter_unavailable_result(user=user, snapshot=snapshot)

    interpretation = await _call_structured_interpreter(
        structured_interpreter,
        InterpretationRequest(
            current_user_message=state.current_user_message,
            recent_thread_history=list(state.recent_thread_history),
            latest_task_snapshot=snapshot,
            selected_thread_metadata=dict(selected_thread_metadata or {}),
            user=user,
        ),
    )
    if interpretation is None:
        return _offline_interpreter_unavailable_result(user=user, snapshot=snapshot)

    return _stage_result_from_interpretation(
        state=state,
        user=user,
        snapshot=snapshot,
        interpretation=interpretation,
        capability_contract=capability_contract,
        selected_thread_metadata=dict(selected_thread_metadata or {}),
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


def _stage_result_from_interpretation(
    *,
    state: RunState,
    user: UserState,
    snapshot: TaskSnapshot | None,
    interpretation: StructuredInterpretation,
    capability_contract: Any,
    selected_thread_metadata: dict[str, Any],
) -> StageResult:
    expects_strategy_route = _strategy_route_expected(
        intent=interpretation.intent,
        semantic_turn_act=interpretation.semantic_turn_act,
    )
    incoming_strategy = _strategy_with_contextual_merge(
        strategy=interpretation.candidate_strategy_draft,
        snapshot=snapshot,
        semantic_turn_act=interpretation.semantic_turn_act,
        task_relation=interpretation.task_relation,
    )
    strategy = (
        _canonicalized_strategy(incoming_strategy)
        if expects_strategy_route
        else incoming_strategy
    )
    unsupported_constraints = list(interpretation.unsupported_constraints)
    ambiguous_fields = list(interpretation.ambiguous_fields)
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
    )
    response_overrides = interpretation.response_profile_overrides
    effective_profile = resolve_effective_response_profile(
        user=user,
        explicit_overrides=response_overrides,
    )
    requires_clarification = bool(
        interpretation.requires_clarification
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
        reason_codes=["llm_interpreter_used", *interpretation.reason_codes],
        effective_response_profile=effective_profile,
        user_preference_overridden_for_turn=has_response_profile_overrides(
            response_overrides
        ),
        normalized_signals={},
        ambiguous_fields=ambiguous_fields,
        unsupported_constraints=unsupported_constraints,
        resolution_provenance=list(strategy.resolution_provenance),
        semantic_turn_act=interpretation.semantic_turn_act,
    )
    approval_result = _approval_stage_result_if_applicable(
        decision=decision,
        snapshot=snapshot,
        state=state,
        selected_thread_metadata=selected_thread_metadata,
    )
    if approval_result is not None:
        return approval_result
    if (
        interpretation.assistant_response
        and not _strategy_route_expected(
            intent=decision.intent,
            semantic_turn_act=decision.semantic_turn_act,
        )
        and not requires_clarification
    ):
        return StageResult(
            outcome="ready_to_respond",
            decision=decision,
            stage_patch={"assistant_response": interpretation.assistant_response},
        )
    if requires_clarification:
        return StageResult(outcome="needs_clarification", decision=decision)
    if expects_strategy_route:
        return StageResult(outcome="ready_for_confirmation", decision=decision)
    return StageResult(
        outcome="ready_to_respond",
        decision=decision,
        stage_patch=(
            {"assistant_response": interpretation.assistant_response}
            if interpretation.assistant_response
            else {}
        ),
    )


def _offline_interpreter_unavailable_result(
    *,
    user: UserState,
    snapshot: TaskSnapshot | None = None,
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
        return (
            f"I still have the {assets} {strategy_label} draft in this chat, "
            "but I could not process that last change. Try again with the change "
            "in one sentence, "
            "or use the visible action chip to adjust the draft."
        )
    if snapshot is not None and snapshot.latest_backtest_result_reference is not None:
        return (
            "I still have the latest result in this chat, but I could not process that "
            "follow-up. Try the question again in one sentence."
        )
    return (
        "I could not process that turn. Your message is saved; please try again "
        "in one sentence."
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
        approved = _canonicalized_strategy(pending)
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
                "confirmation_payload": {
                    "strategy": approved.model_dump(mode="python"),
                    "optional_parameters": {},
                },
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


def _result_action_stage_result_if_applicable(
    *,
    state: RunState,
    snapshot: TaskSnapshot | None,
) -> StageResult | None:
    action = state.structured_action
    if action is None or action.type != "refine_strategy":
        return None
    reference = (
        snapshot.latest_backtest_result_reference
        if snapshot is not None
        else None
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
    parameters = dict(resolved_parameters) if isinstance(resolved_parameters, dict) else {}

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
    approved_strategy = _canonicalized_strategy(snapshot.pending_strategy_summary)
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
            "confirmation_payload": {
                "strategy": approved_strategy.model_dump(mode="python"),
                "optional_parameters": _approval_optional_parameters_from_state(state),
            },
        },
    )


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


def _strategy_with_contextual_merge(
    *,
    strategy: StrategySummary,
    snapshot: TaskSnapshot | None,
    semantic_turn_act: str | None,
    task_relation: str,
) -> StrategySummary:
    if snapshot is None:
        return strategy
    if (
        semantic_turn_act not in CONTEXTUAL_PATCH_TURN_ACTS
        and task_relation != "refine"
    ):
        return strategy
    prior = snapshot.pending_strategy_summary or snapshot.confirmed_strategy_summary
    if prior is None:
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
        if item.resolution_status not in {
            "unsupported",
            "unavailable_for_requested_run",
        } or item.source != "llm_extraction":
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
) -> list[str]:
    if not _strategy_route_expected(
        intent=interpretation.intent,
        semantic_turn_act=interpretation.semantic_turn_act,
    ):
        return []
    missing = [
        field
        for field in interpretation.missing_required_fields
        if isinstance(field, str) and field
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
    if strategy_type == "dca_accumulation" and strategy.capital_amount is None:
        required.append("capital_amount")
    if strategy_type == "buy_and_hold":
        required = ["asset_universe", "date_range"]
    missing: list[str] = []
    payload = strategy.model_dump(mode="python")
    for field_name in required:
        value = payload.get(field_name)
        if isinstance(value, list):
            if not value:
                missing.append(field_name)
        elif value is None or value == "":
            missing.append(field_name)
    return list(dict.fromkeys(missing))


def _strategy_route_expected(
    *,
    intent: IntentName,
    semantic_turn_act: SemanticTurnAct | None,
) -> bool:
    return intent in {"strategy_drafting", "backtest_execution"} or (
        semantic_turn_act in STRATEGY_TURN_ACTS
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
    provenance: list[ResolutionProvenance],
) -> list[ResolutionProvenance]:
    seen: set[tuple[str, str, str, str]] = set()
    deduped: list[ResolutionProvenance] = []
    for item in provenance:
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
