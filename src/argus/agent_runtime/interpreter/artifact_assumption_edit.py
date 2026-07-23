"""Artifact assumption-edit application: apply resolved/legacy edits to a draft and route pending artifact-assumption edits.

Behavior-preserving relocation from llm_interpreter.py (issue #131)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from argus.agent_runtime.artifact_edit_planner import (
    ArtifactAssumptionEditPlan,
    ResolvedArtifactEdit,
    apply_edit_operations,
)
from argus.agent_runtime.artifacts.asset_edits import normalized_asset_universe_operation
from argus.agent_runtime.interpreter.shared import (
    _date_window_intent_bound_to_latest_result,
    _field_path_base,
    _latest_result_date_window,
    _supported_dca_cadence_value,
)
from argus.agent_runtime.llm_interpreter_types import (
    LLMInterpretationResponse,
    LLMStrategyDraft,
)
from argus.agent_runtime.resolution import AssetResolution
from argus.agent_runtime.rule_specs import indicator_parameters_from_strategy
from argus.agent_runtime.stages.artifact_context import (
    active_confirmation_effective_strategy,
    strategy_from_result_reference,
)
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.state.models import StrategySummary
from argus.agent_runtime.strategy_contract import canonical_strategy_type
from argus.nlp.natural_time import resolve_date_range_intent

ResolveAssetCandidate = Callable[..., AssetResolution | None]

# Pending requested_field values whose next user reply edits the pending
# artifact. The result-card "Refine idea" action ("refinement",
# api/chat/result_actions.py) and the confirmation-card assumption prompts are
# two entry points into the same typed edit contract.
ARTIFACT_EDIT_PENDING_FIELDS = frozenset(
    {
        "assumption",
        "asset_universe",
        "comparison_baseline",
        "refinement",
    }
)


def _normalized_ticker_symbol(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    symbol = value.strip().upper()
    return symbol or None


def _request_targets_pending_artifact_assumption_edit(
    request: InterpretationRequest,
) -> bool:
    requested_field = _field_path_base(
        request.selected_thread_metadata.get("requested_field")
    )
    snapshot = request.latest_task_snapshot
    has_artifact_context = bool(
        snapshot
        and (
            snapshot.pending_strategy_summary
            or snapshot.confirmed_strategy_summary
            or snapshot.active_confirmation_reference
        )
    )
    if not has_artifact_context:
        return False
    if requested_field in ARTIFACT_EDIT_PENDING_FIELDS:
        return True
    return bool(
        not requested_field
        and snapshot is not None
        and snapshot.active_confirmation_reference is not None
        and request.current_user_message.strip()
    )


def _request_targets_post_result_artifact_edit(
    request: InterpretationRequest,
) -> bool:
    """Free-form post-result surface: a completed result and nothing pending.

    A reply here can still be an edit of the completed strategy ("could we
    try NVDA over the same period") — the no-chip twin of the Refine idea
    action. Chips and natural language are two entry points to one contract,
    so this surface may reach the same planner; response-conditioned guards
    decide whether a specific turn actually is an edit.
    """

    requested_field = _field_path_base(
        request.selected_thread_metadata.get("requested_field")
    )
    if requested_field and requested_field != "refinement":
        return False
    snapshot = request.latest_task_snapshot
    if snapshot is None or snapshot.latest_backtest_result_reference is None:
        return False
    if (
        snapshot.pending_strategy_summary is not None
        or snapshot.active_confirmation_reference is not None
    ):
        return False
    return bool(request.current_user_message.strip())


def _current_artifact_asset_universe(request: InterpretationRequest) -> list[str]:
    strategy = _current_artifact_strategy(request)
    if strategy is not None and strategy.asset_universe:
        return list(strategy.asset_universe)
    reference = (
        request.latest_task_snapshot.active_confirmation_reference
        if request.latest_task_snapshot is not None
        else None
    )
    reference_assets = getattr(reference, "asset_universe", None)
    if reference_assets:
        return list(reference_assets)
    return []


def _current_artifact_strategy(request: InterpretationRequest) -> StrategySummary | None:
    snapshot = request.latest_task_snapshot
    if snapshot is None:
        return None
    prior = snapshot.pending_strategy_summary or snapshot.confirmed_strategy_summary
    if snapshot.active_confirmation_reference is not None:
        effective = active_confirmation_effective_strategy(
            snapshot=snapshot,
            fallback=prior or StrategySummary(),
        )
        if effective != StrategySummary():
            return effective
    if prior is None and snapshot.latest_backtest_result_reference is not None:
        # Post-result surface: the canonical strategy is the one that ran.
        reconstructed = strategy_from_result_reference(
            snapshot.latest_backtest_result_reference
        )
        if reconstructed.asset_universe:
            return reconstructed
    return prior


def asset_edit_symbol_resolver(
    resolve_asset_candidate: ResolveAssetCandidate,
) -> Callable[[str], str | None]:
    def _resolve(raw_symbol: str) -> str | None:
        resolution = resolve_asset_candidate(
            raw_symbol,
            field="asset_edit",
            source="user_mention",
        )
        if (
            resolution is not None
            and resolution.status == "resolved"
            and resolution.asset
        ):
            return resolution.asset.canonical_symbol
        return None

    return _resolve


def _apply_resolved_edit_to_draft(
    resolved: ResolvedArtifactEdit,
    *,
    draft: LLMStrategyDraft,
    field_provenance: dict[str, str],
    extra_parameters: dict[str, Any],
    allow_indicator_parameters: bool = False,
    latest_result_window: dict[str, str] | None = None,
) -> None:
    if resolved.asset_universe is not None:
        draft.asset_universe = list(resolved.asset_universe)
        draft.asset_universe_operation = "replace"
        extra_parameters["asset_universe_operation"] = "replace"
        field_provenance["asset_universe"] = "explicit_user"
    if resolved.comparison_baseline:
        draft.comparison_baseline = resolved.comparison_baseline
        field_provenance["comparison_baseline"] = "explicit_user"
    if resolved.date_window is not None:
        date_window_intent = _date_window_intent_bound_to_latest_result(
            resolved.date_window,
            latest_result_window=latest_result_window,
        )
        if (
            date_window_intent is not None
            and str(date_window_intent.kind or "").strip() == "future_window"
        ):
            # A forward-looking edit is original intent for the future
            # admission boundary; it is never resolved, dropped, or partially
            # applied alongside the other edits.
            draft.date_range_intent = date_window_intent
        else:
            intent_resolution = (
                resolve_date_range_intent(date_window_intent)
                if date_window_intent is not None
                else None
            )
            if intent_resolution is not None:
                draft.date_range_intent = date_window_intent
                draft.date_range = intent_resolution.payload
                field_provenance["date_range"] = "explicit_user"
    if resolved.initial_capital is not None:
        draft.initial_capital = resolved.initial_capital
        field_provenance["initial_capital"] = "starting_capital"
    if resolved.recurring_contribution_amount is not None:
        recurring_amount = float(resolved.recurring_contribution_amount)
        draft.capital_amount = recurring_amount
        draft.recurring_contribution = recurring_amount
        field_provenance["capital_amount"] = "recurring_contribution"
        field_provenance["recurring_contribution"] = "recurring_contribution"
        extra_parameters["recurring_contribution"] = recurring_amount
    if resolved.cadence is not None:
        cadence = _supported_dca_cadence_value(resolved.cadence)
        if cadence is not None:
            draft.cadence = cadence
            field_provenance["cadence"] = "explicit_user"
            extra_parameters["recurring_cadence"] = cadence
    if resolved.timeframe is not None:
        draft.timeframe = resolved.timeframe
        field_provenance["timeframe"] = "explicit_user"
    if resolved.fee_rate is not None:
        extra_parameters["fee_rate"] = resolved.fee_rate
        field_provenance["fee_rate"] = "explicit_user"
    if resolved.slippage is not None:
        extra_parameters["slippage"] = resolved.slippage
        field_provenance["slippage"] = "explicit_user"
    if resolved.indicator_parameters and allow_indicator_parameters:
        draft.strategy_type = "indicator_threshold"
        draft.indicator = "rsi"
        indicator_parameters = {
            "indicator": "rsi",
            **resolved.indicator_parameters,
        }
        if "indicator_period" in resolved.indicator_parameters:
            draft.indicator_period = int(resolved.indicator_parameters["indicator_period"])
            field_provenance["indicator_period"] = "explicit_user"
        if "entry_threshold" in resolved.indicator_parameters:
            draft.entry_threshold = float(resolved.indicator_parameters["entry_threshold"])
            field_provenance["entry_threshold"] = "explicit_user"
        if "exit_threshold" in resolved.indicator_parameters:
            draft.exit_threshold = float(resolved.indicator_parameters["exit_threshold"])
            field_provenance["exit_threshold"] = "explicit_user"
        extra_parameters["indicator"] = "rsi"
        extra_parameters["indicator_parameters"] = indicator_parameters
        field_provenance["indicator_parameters"] = "explicit_user"


def _apply_legacy_flat_edit_fields(
    plan: ArtifactAssumptionEditPlan,
    *,
    draft: LLMStrategyDraft,
    field_provenance: dict[str, str],
    extra_parameters: dict[str, Any],
) -> None:
    if plan.asset_universe:
        operation = normalized_asset_universe_operation(
            plan.asset_universe_operation
        )
        draft.asset_universe = list(plan.asset_universe)
        if operation is not None:
            draft.asset_universe_operation = operation
            extra_parameters["asset_universe_operation"] = operation
        field_provenance["asset_universe"] = "explicit_user"
    if plan.comparison_baseline is not None:
        benchmark = str(plan.comparison_baseline or "").strip().upper()
        if benchmark:
            draft.comparison_baseline = benchmark
            field_provenance["comparison_baseline"] = "explicit_user"
    if plan.initial_capital is not None:
        draft.initial_capital = plan.initial_capital
        field_provenance["initial_capital"] = "starting_capital"
    if plan.recurring_contribution_amount is not None:
        recurring_amount = float(plan.recurring_contribution_amount)
        draft.capital_amount = recurring_amount
        draft.recurring_contribution = recurring_amount
        field_provenance["capital_amount"] = "recurring_contribution"
        field_provenance["recurring_contribution"] = "recurring_contribution"
        extra_parameters["recurring_contribution"] = recurring_amount
    if plan.cadence is not None:
        cadence = _supported_dca_cadence_value(plan.cadence)
        if cadence is not None:
            draft.cadence = cadence
            field_provenance["cadence"] = "explicit_user"
            extra_parameters["recurring_cadence"] = cadence
    if plan.timeframe is not None:
        draft.timeframe = plan.timeframe
        field_provenance["timeframe"] = "explicit_user"
    if plan.fee_rate is not None:
        extra_parameters["fee_rate"] = plan.fee_rate
        field_provenance["fee_rate"] = "explicit_user"
    if plan.slippage is not None:
        extra_parameters["slippage"] = plan.slippage
        field_provenance["slippage"] = "explicit_user"


def _edit_plan_reshapes_non_recurring_strategy(
    plan: ArtifactAssumptionEditPlan,
    *,
    prior_strategy_type: Any,
) -> bool:
    """Recurring-buy plan fields aimed at a non-recurring strategy are a
    reshape ("make it recurring buys instead"), not an assumption edit.

    The edit-operation set cannot change strategy_type, so applying such a
    plan would silently keep the old strategy; callers must step aside and
    let a reshape-capable interpretation path handle the turn.
    """

    proposes_recurring_fields = (
        plan.cadence is not None
        or plan.recurring_contribution_amount is not None
        or any(
            operation.target in {"cadence", "recurring_contribution"}
            for operation in plan.operations
        )
    )
    if not proposes_recurring_fields:
        return False
    return canonical_strategy_type(prior_strategy_type) != "dca_accumulation"


def _current_artifact_uses_rsi(request: InterpretationRequest) -> bool:
    strategy = _current_artifact_strategy(request)
    if strategy is None:
        return False
    parameters = indicator_parameters_from_strategy(strategy)
    indicator = str(
        parameters.get("indicator")
        or strategy.extra_parameters.get("indicator")
        or ""
    ).strip().casefold()
    return indicator == "rsi"


def _response_from_artifact_assumption_edit_plan(
    *,
    plan: ArtifactAssumptionEditPlan,
    request: InterpretationRequest,
    asset_symbol_resolver: Callable[[str], str | None] | None = None,
) -> LLMInterpretationResponse:
    draft = LLMStrategyDraft(raw_user_phrasing=request.current_user_message)
    artifact_target = (
        "latest_result" if _request_targets_post_result_artifact_edit(request) else None
    )
    current_strategy = _current_artifact_strategy(request)
    if current_strategy is not None and current_strategy.strategy_type:
        draft.strategy_type = current_strategy.strategy_type
    field_provenance: dict[str, str] = {}
    extra_parameters: dict[str, Any] = {}
    if plan.operations:
        allow_indicator_parameters = _current_artifact_uses_rsi(request)
        resolved = apply_edit_operations(
            plan.operations,
            current_asset_universe=_current_artifact_asset_universe(request),
            asset_symbol_resolver=asset_symbol_resolver,
        )
        _apply_resolved_edit_to_draft(
            resolved,
            draft=draft,
            field_provenance=field_provenance,
            extra_parameters=extra_parameters,
            allow_indicator_parameters=allow_indicator_parameters,
            latest_result_window=_latest_result_date_window(request),
        )
    else:
        _apply_legacy_flat_edit_fields(
            plan,
            draft=draft,
            field_provenance=field_provenance,
            extra_parameters=extra_parameters,
        )
    if extra_parameters:
        draft.extra_parameters.update(extra_parameters)
    if field_provenance:
        draft.field_provenance = field_provenance

    if plan.outcome == "ready_to_confirm":
        if plan.operations and not field_provenance and not extra_parameters:
            return LLMInterpretationResponse(
                intent="conversation_followup",
                task_relation="continue",
                requires_clarification=True,
                user_goal_summary=(
                    plan.user_goal_summary
                    or "The requested assumption change cannot be applied here."
                ),
                candidate_strategy_draft=draft,
                assistant_response=(
                    plan.assistant_response
                    or "I can change RSI thresholds only on an active RSI confirmation card."
                ),
                confidence=plan.confidence,
                reason_codes=["artifact_assumption_edit_planned"],
                semantic_turn_act="unsupported_request",
                artifact_target=artifact_target,
            )
        return LLMInterpretationResponse(
            intent="backtest_execution",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary=(
                plan.user_goal_summary or "User changed a visible confirmation assumption."
            ),
            candidate_strategy_draft=draft,
            # Surface the model's note when an applied edit also had a part it could
            # not change (mixed supported/unsupported), so the reply never silently
            # drops the unsupported part. None for a clean edit.
            assistant_response=plan.assistant_response,
            confidence=plan.confidence,
            reason_codes=["artifact_assumption_edit_planned"],
            semantic_turn_act="answer_pending_need",
            artifact_target=artifact_target,
        )

    return LLMInterpretationResponse(
        intent=(
            "unsupported_or_out_of_scope"
            if plan.outcome == "unsupported"
            else "conversation_followup"
        ),
        task_relation="continue",
        requires_clarification=True,
        user_goal_summary=(
            plan.user_goal_summary
            or "The requested assumption change needs clarification."
        ),
        candidate_strategy_draft=draft,
        missing_required_fields=list(plan.missing_required_fields),
        assistant_response=plan.assistant_response,
        confidence=plan.confidence,
        reason_codes=["artifact_assumption_edit_planned"],
        semantic_turn_act=(
            "unsupported_request"
            if plan.outcome == "unsupported"
            else "answer_pending_need"
        ),
        artifact_target=artifact_target,
    )
