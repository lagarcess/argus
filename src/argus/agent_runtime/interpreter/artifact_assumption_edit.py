"""Artifact assumption-edit application: apply resolved/legacy edits to a draft and route pending artifact-assumption edits.

Behavior-preserving relocation from llm_interpreter.py (issue #131)."""

from __future__ import annotations

from typing import Any

from argus.agent_runtime.artifact_edit_planner import (
    ArtifactAssumptionEditPlan,
    ResolvedArtifactEdit,
    apply_edit_operations,
)
from argus.agent_runtime.artifacts.asset_edits import normalized_asset_universe_operation
from argus.agent_runtime.interpreter.shared import (
    _field_path_base,
    _supported_dca_cadence_value,
)
from argus.agent_runtime.llm_interpreter_types import (
    LLMInterpretationResponse,
    LLMStrategyDraft,
)
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.nlp.natural_time import resolve_date_range_intent


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
    if requested_field in {"assumption", "asset_universe", "comparison_baseline"}:
        return True
    return bool(
        not requested_field
        and snapshot is not None
        and snapshot.active_confirmation_reference is not None
        and request.current_user_message.strip()
    )


def _current_artifact_asset_universe(request: InterpretationRequest) -> list[str]:
    snapshot = request.latest_task_snapshot
    if snapshot is None:
        return []
    prior = snapshot.pending_strategy_summary or snapshot.confirmed_strategy_summary
    if prior is not None and prior.asset_universe:
        return list(prior.asset_universe)
    reference = snapshot.active_confirmation_reference
    reference_assets = getattr(reference, "asset_universe", None)
    if reference_assets:
        return list(reference_assets)
    return []


def _apply_resolved_edit_to_draft(
    resolved: ResolvedArtifactEdit,
    *,
    draft: LLMStrategyDraft,
    field_provenance: dict[str, str],
    extra_parameters: dict[str, Any],
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
        intent_resolution = resolve_date_range_intent(resolved.date_window)
        if intent_resolution is not None:
            draft.date_range_intent = resolved.date_window
            draft.date_range = intent_resolution.payload
            field_provenance["date_range"] = "explicit_user"
    if resolved.initial_capital is not None:
        draft.capital_amount = resolved.initial_capital
        field_provenance["capital_amount"] = "starting_capital"
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
        draft.capital_amount = plan.initial_capital
        field_provenance["capital_amount"] = "starting_capital"
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


def _response_from_artifact_assumption_edit_plan(
    *,
    plan: ArtifactAssumptionEditPlan,
    request: InterpretationRequest,
) -> LLMInterpretationResponse:
    draft = LLMStrategyDraft(raw_user_phrasing=request.current_user_message)
    field_provenance: dict[str, str] = {}
    extra_parameters: dict[str, Any] = {}
    if plan.operations:
        _apply_resolved_edit_to_draft(
            apply_edit_operations(
                plan.operations,
                current_asset_universe=_current_artifact_asset_universe(request),
            ),
            draft=draft,
            field_provenance=field_provenance,
            extra_parameters=extra_parameters,
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
    )
