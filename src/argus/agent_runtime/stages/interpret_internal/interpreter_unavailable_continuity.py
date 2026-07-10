"""Interpreter-unavailable continuity helpers for interpret stage."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from argus.agent_runtime.artifact_edit_planner import (
    ArtifactAssumptionEditPlan,
    apply_edit_operations,
)
from argus.agent_runtime.artifact_edit_planner import (
    plan_artifact_assumption_edit as _plan_artifact_assumption_edit,
)
from argus.agent_runtime.artifacts.asset_edits import (
    normalized_asset_universe_operation,
    same_asset_universe,
)
from argus.agent_runtime.asset_text_grounding import provider_ticker_mentions_from_text
from argus.agent_runtime.interpreter.artifact_assumption_edit import (
    _edit_plan_reshapes_non_recurring_strategy,
)
from argus.agent_runtime.interpreter.pending_option import (
    _apply_pending_response_option_replacement,
    _llm_draft_from_strategy_summary,
    _pending_response_intent_options,
)
from argus.agent_runtime.interpreter.shared import (
    _latest_result_date_window_from_snapshot,
    _supported_dca_cadence_value,
)
from argus.agent_runtime.interpreter.strategy_builder import _strategy_from_llm
from argus.agent_runtime.resolution import AssetResolution
from argus.agent_runtime.simplification_option_contract import (
    simplification_option_matches_selection,
)
from argus.agent_runtime.stages.artifact_context import (
    active_confirmation_effective_strategy,
    strategy_from_result_reference,
)
from argus.agent_runtime.stages.interpret_actions import (
    CONFIRMATION_EDIT_ACTION_FIELDS,
)
from argus.agent_runtime.stages.interpret_internal.asset_resolution import (
    _dedupe_resolution_provenance,
)
from argus.agent_runtime.stages.interpret_internal.confirmation_artifact_edits import (
    apply_resolved_artifact_edit_to_strategy_summary,
    asset_edit_symbol_resolver,
    strategy_summary_uses_rsi,
)
from argus.agent_runtime.stages.interpret_internal.shared import _field_base
from argus.agent_runtime.stages.interpret_types import (
    InterpretationRequest,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import RunState, StrategySummary, TaskSnapshot
from argus.agent_runtime.strategy_contract import canonical_strategy_type
from argus.domain.indicators import draft_only_indicator_from_text

ResolveAssetCandidate = Callable[..., AssetResolution | None]
DefaultBenchmarkForAssetClass = Callable[..., str | None]
PlanArtifactAssumptionEdit = Callable[..., Any]


def pending_response_option_when_interpreter_unavailable(
    *,
    state: RunState,
    user: Any,
    snapshot: TaskSnapshot | None,
    current_user_message: str,
    selected_thread_metadata: dict[str, Any],
) -> StructuredInterpretation | None:
    interpretation = pending_response_option_interpretation_from_typed_selection(
        state=state,
        user=user,
        snapshot=snapshot,
        current_user_message=current_user_message,
        selected_thread_metadata=selected_thread_metadata,
    )
    if interpretation is None:
        return None
    return interpretation.model_copy(
        update={
            "user_goal_summary": (
                "User selected a pending simplification option while structured "
                "interpretation was unavailable."
            ),
            "reason_codes": list(
                dict.fromkeys(
                    [
                        *interpretation.reason_codes,
                        "pending_response_option_interpreter_unavailable_repaired",
                    ]
                )
            ),
        }
    )


def pending_response_option_interpretation_from_typed_selection(
    *,
    state: RunState,
    user: Any,
    snapshot: TaskSnapshot | None,
    current_user_message: str,
    selected_thread_metadata: dict[str, Any],
) -> StructuredInterpretation | None:
    if snapshot is None or snapshot.pending_strategy_summary is None:
        return None
    if not current_user_message.strip():
        return None
    request = InterpretationRequest(
        current_user_message=current_user_message,
        recent_thread_history=list(state.recent_thread_history),
        latest_task_snapshot=snapshot,
        selected_thread_metadata=_selected_thread_metadata_with_nested_response_intent(
            selected_thread_metadata
        ),
        user=user,
    )
    options = _pending_response_intent_options(request)
    option_index = _pending_response_option_index_from_typed_selection(
        state=state,
        selected_thread_metadata=selected_thread_metadata,
        options=options,
    )
    if option_index is None:
        return None
    replacement_values = options[option_index].get("replacement_values")
    if not isinstance(replacement_values, dict):
        return None
    draft = _llm_draft_from_strategy_summary(snapshot.pending_strategy_summary)
    replacement_result = _apply_pending_response_option_replacement(
        draft=draft,
        replacement_values=replacement_values,
        current_missing=[],
    )
    strategy = _strategy_from_llm(replacement_result["draft"])
    missing_fields = list(replacement_result["missing_fields"])
    return StructuredInterpretation(
        intent="strategy_drafting" if missing_fields else "backtest_execution",
        task_relation="continue",
        requires_clarification=bool(missing_fields),
        user_goal_summary=(
            "User selected a pending simplification option from the previous "
            "assistant turn."
        ),
        candidate_strategy_draft=strategy,
        missing_required_fields=missing_fields,
        semantic_turn_act="answer_pending_need",
        reason_codes=[
            "pending_response_option_selected",
            "pending_response_option_typed_selection_applied",
        ],
    )


def draft_only_indicator_interpretation_when_interpreter_unavailable(
    *,
    snapshot: TaskSnapshot | None,
    current_user_message: str,
    resolve_asset_candidate: ResolveAssetCandidate,
    default_benchmark_for_asset_class: DefaultBenchmarkForAssetClass,
) -> StructuredInterpretation | None:
    if snapshot is not None:
        return None
    text = current_user_message.strip()
    if not text:
        return None
    indicator = draft_only_indicator_from_text(text)
    if indicator is None:
        return None

    def _resolve_candidate(query: str) -> AssetResolution | None:
        return resolve_asset_candidate(
            query,
            field="asset_universe",
            source="user_mention",
        )

    mentions = provider_ticker_mentions_from_text(
        text,
        resolve_candidate=_resolve_candidate,
        limit=5,
    )
    if not mentions:
        return None
    symbols: list[str] = []
    asset_classes: set[str] = set()
    provenance = []
    for mention in mentions:
        asset = mention.asset
        symbol = str(getattr(asset, "canonical_symbol", "") or "").strip().upper()
        asset_class = str(getattr(asset, "asset_class", "") or "").strip()
        if not symbol or not asset_class:
            continue
        if symbol not in symbols:
            symbols.append(symbol)
        asset_classes.add(asset_class)
        provenance.append(mention.resolution.provenance)
    if not symbols or len(asset_classes) != 1:
        return None
    asset_class = next(iter(asset_classes))
    strategy = StrategySummary(
        raw_user_phrasing=text,
        strategy_thesis=text,
        asset_universe=symbols[:5],
        asset_class=asset_class,
        comparison_baseline=default_benchmark_for_asset_class(
            asset_class,
            symbols=symbols[:5],
        ),
        resolution_provenance=_dedupe_resolution_provenance(provenance),
        extra_parameters={
            "unsupported_indicator": indicator.key,
            "unsupported_indicator_label": indicator.label,
        },
    )
    return StructuredInterpretation(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary=(
            "Structured interpretation was unavailable, but the user supplied "
            "a provider-backed asset and a draft-only indicator."
        ),
        candidate_strategy_draft=strategy,
        missing_required_fields=[],
        assistant_response=None,
        semantic_turn_act="new_idea",
        reason_codes=[
            "llm_interpreter_unavailable_draft_only_indicator_recovered",
            "draft_only_indicator_text_preserved",
        ],
    )


async def planned_active_confirmation_edit_interpretation(
    *,
    snapshot: TaskSnapshot,
    current_user_message: str,
    resolve_asset_candidate: ResolveAssetCandidate,
    plan_artifact_assumption_edit_fn: PlanArtifactAssumptionEdit | None = None,
) -> StructuredInterpretation | None:
    active_confirmation = snapshot.active_confirmation_reference
    if active_confirmation is None:
        return None
    prior_strategy = active_confirmation_effective_strategy(
        snapshot=snapshot,
        fallback=(
            snapshot.pending_strategy_summary
            or snapshot.confirmed_strategy_summary
            or StrategySummary()
        ),
    )
    return await _planned_artifact_edit_interpretation(
        prior_strategy=prior_strategy,
        active_confirmation_payload=active_confirmation.model_dump(mode="json"),
        current_user_message=current_user_message,
        resolve_asset_candidate=resolve_asset_candidate,
        plan_artifact_assumption_edit_fn=plan_artifact_assumption_edit_fn,
        artifact_target="active_confirmation",
        default_goal_summary="User changed a visible confirmation assumption.",
        latest_result_window=_latest_result_date_window_from_snapshot(snapshot),
    )


async def planned_pending_confirmation_edit_interpretation(
    *,
    snapshot: TaskSnapshot | None,
    current_user_message: str,
    requested_field: str,
    resolve_asset_candidate: ResolveAssetCandidate,
    plan_artifact_assumption_edit_fn: PlanArtifactAssumptionEdit | None = None,
) -> StructuredInterpretation | None:
    """Plan a chip-clarify answer against the pending confirmation draft.

    Some live chip-answer turns carry the previous requested field but not the
    active confirmation reference. In that state the chip is still just the
    display doorway; the typed edit planner must decide the actual operation.
    """

    # The caller owns requested-field validation so its admit/drop behavior
    # cannot diverge from this planner's preconditions.
    del requested_field
    if (
        snapshot is None
        or snapshot.pending_strategy_summary is None
        or snapshot.active_confirmation_reference is not None
    ):
        return None
    return await _planned_artifact_edit_interpretation(
        prior_strategy=snapshot.pending_strategy_summary,
        active_confirmation_payload=None,
        current_user_message=current_user_message,
        resolve_asset_candidate=resolve_asset_candidate,
        plan_artifact_assumption_edit_fn=plan_artifact_assumption_edit_fn,
        artifact_target="active_confirmation",
        default_goal_summary="User changed a visible confirmation assumption.",
        latest_result_window=_latest_result_date_window_from_snapshot(snapshot),
    )


async def planned_pending_refinement_edit_interpretation(
    *,
    snapshot: TaskSnapshot | None,
    current_user_message: str,
    selected_thread_metadata: dict[str, Any],
    resolve_asset_candidate: ResolveAssetCandidate,
    plan_artifact_assumption_edit_fn: PlanArtifactAssumptionEdit | None = None,
) -> StructuredInterpretation | None:
    """Offline edit planning for the result-card refine pending state.

    A refine draft has a pending strategy and a source result but no active
    confirmation card, so the confirmation-scoped offline planner never
    engages; without this path a refine reply during model outages dies in
    generic recovery copy.
    """

    requested_field = str(
        selected_thread_metadata.get("requested_field") or ""
    ).partition(".")[0]
    if requested_field != "refinement":
        return None
    if snapshot is None or snapshot.pending_strategy_summary is None:
        return None
    return await _planned_artifact_edit_interpretation(
        prior_strategy=snapshot.pending_strategy_summary,
        active_confirmation_payload=None,
        current_user_message=current_user_message,
        resolve_asset_candidate=resolve_asset_candidate,
        plan_artifact_assumption_edit_fn=plan_artifact_assumption_edit_fn,
        artifact_target="pending_refinement",
        default_goal_summary="User changed the refine draft.",
        latest_result_window=_latest_result_date_window_from_snapshot(snapshot),
    )


async def planned_latest_result_edit_interpretation(
    *,
    snapshot: TaskSnapshot | None,
    current_user_message: str,
    resolve_asset_candidate: ResolveAssetCandidate,
    plan_artifact_assumption_edit_fn: PlanArtifactAssumptionEdit | None = None,
) -> StructuredInterpretation | None:
    """Planned edit against the completed run when nothing is pending.

    The post-result surface has no pending draft or confirmation card, so an
    edit-shaped turn must plan against the strategy that actually ran."""

    if snapshot is None or snapshot.latest_backtest_result_reference is None:
        return None
    if (
        snapshot.pending_strategy_summary is not None
        or snapshot.active_confirmation_reference is not None
    ):
        return None
    prior_strategy = strategy_from_result_reference(
        snapshot.latest_backtest_result_reference
    )
    return await _planned_artifact_edit_interpretation(
        prior_strategy=prior_strategy,
        active_confirmation_payload=None,
        current_user_message=current_user_message,
        resolve_asset_candidate=resolve_asset_candidate,
        plan_artifact_assumption_edit_fn=plan_artifact_assumption_edit_fn,
        artifact_target="latest_result",
        default_goal_summary="User changed an assumption of the completed run.",
        latest_result_window=_latest_result_date_window_from_snapshot(snapshot),
    )


async def _planned_artifact_edit_interpretation(
    *,
    prior_strategy: StrategySummary,
    active_confirmation_payload: dict[str, Any] | None,
    current_user_message: str,
    resolve_asset_candidate: ResolveAssetCandidate,
    plan_artifact_assumption_edit_fn: PlanArtifactAssumptionEdit | None,
    artifact_target: str,
    default_goal_summary: str,
    latest_result_window: dict[str, str] | None = None,
) -> StructuredInterpretation | None:
    if not prior_strategy.asset_universe:
        return None
    planner = plan_artifact_assumption_edit_fn or _plan_artifact_assumption_edit
    plan: ArtifactAssumptionEditPlan | None = await planner(
        current_user_message=current_user_message,
        prior_strategy=prior_strategy.model_dump(mode="json"),
        active_confirmation=active_confirmation_payload,
        preferred_model="",
    )
    if plan is None or plan.outcome != "ready_to_confirm":
        return None
    if artifact_target in {"pending_refinement", "latest_result"} and (
        _edit_plan_reshapes_non_recurring_strategy(
            plan,
            prior_strategy_type=prior_strategy.strategy_type,
        )
    ):
        return None
    candidate = StrategySummary(raw_user_phrasing=current_user_message)
    if prior_strategy.strategy_type:
        # Money-role and cadence integrity read the strategy family from the
        # draft itself; an edit never changes the anchor's family.
        candidate.strategy_type = prior_strategy.strategy_type
    field_provenance: dict[str, str] = {}
    if plan.operations:
        apply_resolved_artifact_edit_to_strategy_summary(
            apply_edit_operations(
                plan.operations,
                current_asset_universe=prior_strategy.asset_universe,
                asset_symbol_resolver=asset_edit_symbol_resolver(resolve_asset_candidate),
            ),
            candidate=candidate,
            field_provenance=field_provenance,
            allow_indicator_parameters=strategy_summary_uses_rsi(prior_strategy),
            latest_result_window=latest_result_window,
        )
    elif plan.asset_universe:
        operation = normalized_asset_universe_operation(plan.asset_universe_operation)
        if operation is None:
            if not same_asset_universe(
                plan.asset_universe,
                prior_strategy.asset_universe,
            ):
                return None
        else:
            candidate.asset_universe = list(plan.asset_universe)
            candidate.extra_parameters["asset_universe_operation"] = operation
            field_provenance["asset_universe"] = "explicit_user"
    if plan.comparison_baseline is not None:
        baseline = str(plan.comparison_baseline or "").strip().upper()
        if baseline:
            candidate.comparison_baseline = baseline
            field_provenance["comparison_baseline"] = "explicit_user"
    if plan.initial_capital is not None:
        candidate.capital_amount = float(plan.initial_capital)
        field_provenance["capital_amount"] = "starting_capital"
    if plan.cadence is not None and not plan.operations:
        cadence = _supported_dca_cadence_value(plan.cadence)
        if cadence is not None:
            candidate.cadence = cadence
            candidate.extra_parameters["recurring_cadence"] = cadence
            field_provenance["cadence"] = "explicit_user"
    if plan.timeframe is not None:
        candidate.timeframe = str(plan.timeframe)
        field_provenance["timeframe"] = "explicit_user"
    if (
        field_provenance.get("capital_amount") == "starting_capital"
        and canonical_strategy_type(prior_strategy.strategy_type) == "dca_accumulation"
    ):
        # A starting principal is not the recurring contribution; keep it
        # typed so the DCA money-role guard decides instead of overwriting
        # the anchor's contribution.
        if candidate.capital_amount is not None:
            candidate.extra_parameters["initial_capital"] = float(
                candidate.capital_amount
            )
        candidate.capital_amount = None
        del field_provenance["capital_amount"]
        field_provenance["initial_capital"] = "starting_capital"
    if not field_provenance:
        return None
    candidate.extra_parameters["field_provenance"] = field_provenance
    return StructuredInterpretation(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary=plan.user_goal_summary or default_goal_summary,
        candidate_strategy_draft=candidate,
        confidence=plan.confidence,
        reason_codes=["artifact_assumption_edit_planned"],
        semantic_turn_act="answer_pending_need",
        artifact_target=artifact_target,
    )


# The chip-opened clarify scopes. The chip's field is display scope only; the
# answer turn is planned like any natural-language edit.
CONFIRMATION_EDIT_CLARIFY_FIELDS = frozenset(CONFIRMATION_EDIT_ACTION_FIELDS.values())


def _chip_clarify_requested_field(
    selected_thread_metadata: dict[str, Any],
) -> str | None:
    requested_field = _field_base(
        str(selected_thread_metadata.get("requested_field") or "")
    )
    if requested_field not in CONFIRMATION_EDIT_CLARIFY_FIELDS:
        return None
    return requested_field


def pending_confirmation_chip_clarify_edit_requested_field(
    *,
    interpretation: StructuredInterpretation,
    selected_thread_metadata: dict[str, Any],
) -> str | None:
    requested_field = _chip_clarify_requested_field(selected_thread_metadata)
    if requested_field is None:
        return None
    last_stage_outcome = selected_thread_metadata.get("last_stage_outcome")
    if last_stage_outcome not in (None, "await_user_reply"):
        return None
    if interpretation.semantic_turn_act != "answer_pending_need":
        return None
    if not _interpretation_supplies_chip_artifact_edit(interpretation):
        return None
    return requested_field


def chip_clarify_answer_supplies_artifact_edit(
    *,
    interpretation: StructuredInterpretation,
    selected_thread_metadata: dict[str, Any],
) -> bool:
    if _chip_clarify_requested_field(selected_thread_metadata) is None:
        return False
    return _interpretation_supplies_chip_artifact_edit(interpretation)


def _interpretation_supplies_chip_artifact_edit(
    interpretation: StructuredInterpretation,
) -> bool:
    if interpretation.semantic_turn_act in {
        "approval",
        "educational_question",
        "result_followup",
        "retry_failed_action",
        "unsupported_request",
    }:
        return False
    if interpretation.intent not in {"strategy_drafting", "backtest_execution"}:
        return False
    strategy = interpretation.candidate_strategy_draft
    extra_parameters = strategy.extra_parameters or {}
    return bool(
        strategy.asset_universe
        or strategy.date_range not in (None, "", {})
        or strategy.capital_amount is not None
        or strategy.timeframe not in (None, "")
        or strategy.cadence not in (None, "")
        or strategy.comparison_baseline not in (None, "")
        or any(
            extra_parameters.get(key) is not None
            for key in (
                "initial_capital",
                "recurring_contribution",
                "fee_rate",
                "slippage",
                "date_range_intent",
            )
        )
    )


def structured_interpretation_has_supported_artifact_assumption_edit(
    interpretation: StructuredInterpretation,
) -> bool:
    if interpretation.semantic_turn_act in {
        "approval",
        "educational_question",
        "result_followup",
        "retry_failed_action",
    }:
        return False
    if interpretation.intent not in {"strategy_drafting", "backtest_execution"}:
        return False
    strategy = interpretation.candidate_strategy_draft
    extra_parameters = strategy.extra_parameters or {}
    field_provenance = extra_parameters.get("field_provenance")
    if not isinstance(field_provenance, dict):
        field_provenance = {}
    if any(
        key in extra_parameters and field_provenance.get(key) == "explicit_user"
        for key in ("fee_rate", "slippage")
    ):
        return True
    return bool(strategy.asset_universe) and (
        normalized_asset_universe_operation(
            extra_parameters.get("asset_universe_operation")
        )
        is not None
    )


def structured_interpretation_has_complete_typed_asset_patch(
    interpretation: StructuredInterpretation,
) -> bool:
    strategy = interpretation.candidate_strategy_draft
    if not strategy.asset_universe:
        return False
    extra_parameters = strategy.extra_parameters or {}
    if (
        normalized_asset_universe_operation(
            extra_parameters.get("asset_universe_operation")
        )
        is None
    ):
        return False
    return bool(
        strategy.date_range in (None, {}, "")
        and strategy.capital_amount is None
        and strategy.position_size is None
        and strategy.timeframe in (None, "")
    )


def _pending_response_option_index_from_typed_selection(
    *,
    state: RunState,
    selected_thread_metadata: dict[str, Any],
    options: list[dict[str, Any]],
) -> int | None:
    if not options:
        return None
    for index in _typed_selected_option_indices(
        state=state,
        selected_thread_metadata=selected_thread_metadata,
    ):
        if 0 <= index < len(options):
            return index
    for selected_values in _typed_selected_replacement_values(
        state=state,
        selected_thread_metadata=selected_thread_metadata,
    ):
        matches = [
            index
            for index, option in enumerate(options)
            if simplification_option_matches_selection(
                option_replacement_values=option.get("replacement_values"),
                selected_replacement_values=selected_values,
            )
        ]
        if len(matches) == 1:
            return matches[0]
    return None


def _typed_selected_option_indices(
    *,
    state: RunState,
    selected_thread_metadata: dict[str, Any],
) -> list[int]:
    indices: list[int] = []
    for payload in _typed_selection_payloads(
        state=state,
        selected_thread_metadata=selected_thread_metadata,
    ):
        for key in (
            "option_index",
            "selected_option_index",
            "response_option_index",
        ):
            index = payload.get(key)
            if isinstance(index, int) and not isinstance(index, bool):
                indices.append(index)
    return indices


def _typed_selected_replacement_values(
    *,
    state: RunState,
    selected_thread_metadata: dict[str, Any],
) -> list[dict[str, Any]]:
    selections: list[dict[str, Any]] = []
    for payload in _typed_selection_payloads(
        state=state,
        selected_thread_metadata=selected_thread_metadata,
    ):
        for key in (
            "replacement_values",
            "selected_replacement_values",
            "response_option_replacement_values",
        ):
            value = payload.get(key)
            if isinstance(value, dict):
                selections.append(dict(value))
        option = payload.get("response_option")
        if isinstance(option, dict) and isinstance(
            option.get("replacement_values"), dict
        ):
            selections.append(dict(option["replacement_values"]))
    return selections


def _typed_selection_payloads(
    *,
    state: RunState,
    selected_thread_metadata: dict[str, Any],
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    if state.structured_action is not None:
        payloads.append(dict(state.structured_action.payload))
    for key in (
        "response_option_selection",
        "selected_response_option",
        "chat_action",
        "structured_action",
    ):
        value = selected_thread_metadata.get(key)
        if isinstance(value, dict):
            payloads.append(value)
            nested_payload = value.get("payload")
            if isinstance(nested_payload, dict):
                payloads.append(nested_payload)
    return payloads


def _selected_thread_metadata_with_nested_response_intent(
    selected_thread_metadata: dict[str, Any],
) -> dict[str, Any]:
    if isinstance(selected_thread_metadata.get("response_intent"), dict):
        return selected_thread_metadata
    pending_strategy = selected_thread_metadata.get("pending_strategy")
    if not isinstance(pending_strategy, dict):
        return selected_thread_metadata
    response_intent = pending_strategy.get("response_intent")
    if not isinstance(response_intent, dict):
        return selected_thread_metadata
    return {**selected_thread_metadata, "response_intent": dict(response_intent)}
