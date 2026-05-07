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


def interpret_stage(
    *,
    state: RunState,
    user: UserState,
    latest_task_snapshot: TaskSnapshot | dict[str, Any] | None,
    structured_interpreter: StructuredInterpreter | None = None,
) -> StageResult:
    return asyncio.run(
        interpret_stage_async(
            state=state,
            user=user,
            latest_task_snapshot=latest_task_snapshot,
            structured_interpreter=structured_interpreter,
        )
    )


async def interpret_stage_async(
    *,
    state: RunState,
    user: UserState,
    latest_task_snapshot: TaskSnapshot | dict[str, Any] | None,
    structured_interpreter: StructuredInterpreter | None = None,
) -> StageResult:
    capability_contract = build_default_capability_contract()
    snapshot = normalize_task_snapshot(latest_task_snapshot)
    if structured_interpreter is None:
        return _offline_interpreter_unavailable_result(user=user)

    interpretation = await _call_structured_interpreter(
        structured_interpreter,
        InterpretationRequest(
            current_user_message=state.current_user_message,
            recent_thread_history=list(state.recent_thread_history),
            latest_task_snapshot=snapshot,
            user=user,
        ),
    )
    if interpretation is None:
        return _offline_interpreter_unavailable_result(user=user)

    return _stage_result_from_interpretation(
        state=state,
        user=user,
        snapshot=snapshot,
        interpretation=interpretation,
        capability_contract=capability_contract,
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
) -> StageResult:
    expects_strategy_route = _strategy_route_expected(
        intent=interpretation.intent,
        semantic_turn_act=interpretation.semantic_turn_act,
    )
    strategy = (
        _canonicalized_strategy(interpretation.candidate_strategy_draft)
        if expects_strategy_route
        else interpretation.candidate_strategy_draft
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


def _offline_interpreter_unavailable_result(*, user: UserState) -> StageResult:
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
            "assistant_response": (
                "I could not reach the interpretation model for this turn. "
                "Your message is saved; please try again."
            )
        },
    )


def _approval_stage_result_if_applicable(
    *,
    decision: InterpretDecision,
    snapshot: TaskSnapshot | None,
    state: RunState,
) -> StageResult | None:
    if decision.semantic_turn_act != "approval":
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
