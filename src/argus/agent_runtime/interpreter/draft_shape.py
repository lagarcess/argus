"""LLM strategy-draft shape predicates and underfill checks.

Behavior-preserving relocation from llm_interpreter.py (issue #131)."""

from __future__ import annotations

import time
from typing import Any

from argus.agent_runtime.artifacts.asset_edits import normalized_asset_universe_operation
from argus.agent_runtime.interpreter.artifact_assumption_edit import (
    _current_artifact_strategy,
    _request_targets_pending_artifact_assumption_edit,
)
from argus.agent_runtime.interpreter.dca_audits import _dca_draft_has_recurring_amount
from argus.agent_runtime.interpreter.readiness_helpers import (
    _active_artifact_asset_universe_operation_needs_planner,
)
from argus.agent_runtime.interpreter.shared import (
    _TOTAL_CAPITAL_SOURCES,
    _field_path_base,
    _llm_strategy_draft_has_extractable_fields,
    _llm_strategy_draft_has_rule_or_indicator_fields,
    _selected_requested_field_base,
    _supported_dca_cadence_value,
)
from argus.agent_runtime.llm_interpreter_types import (
    LLMInterpretationResponse,
    LLMStrategyDraft,
)
from argus.agent_runtime.stages.artifact_context import launch_payload_from_failed_action
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.strategy_contract import (
    SUPPORTED_STRATEGY_TYPES,
    canonical_strategy_type,
    executable_strategy_type,
    normalize_date_range_candidate,
    resolve_date_range,
)
from argus.nlp.natural_time import (
    resolve_date_range_intent,
    resolve_date_range_text,
)


def _elapsed_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)


def _structured_strategy_missing_fields_can_clarify(
    *,
    response: LLMInterpretationResponse,
    draft: LLMStrategyDraft,
    missing: list[str],
) -> bool:
    if not missing:
        return False
    if not response.requires_clarification:
        return False
    if not response.missing_required_fields:
        return False
    if response.semantic_turn_act in {
        "approval",
        "result_followup",
        "retry_failed_action",
        "unsupported_request",
    }:
        return False
    if response.unsupported_constraints:
        return False
    if "supported_strategy_capability_conflict_audit" in response.reason_codes:
        return False
    strategy_type = executable_strategy_type(draft.model_dump(mode="python"))
    if strategy_type not in SUPPORTED_STRATEGY_TYPES:
        return False
    declared_missing = {
        _field_path_base(field) for field in response.missing_required_fields
    }
    return set(missing).issubset(
        declared_missing
    ) and _llm_strategy_draft_has_extractable_fields(draft)


def _request_has_failed_action_launch_payload(request: InterpretationRequest) -> bool:
    snapshot = request.latest_task_snapshot
    if snapshot is None:
        return False
    return (
        launch_payload_from_failed_action(snapshot.latest_failed_action_reference)
        is not None
    )


def _response_underfills_pending_result_refinement(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    requested_field = _field_path_base(
        request.selected_thread_metadata.get("requested_field")
    )
    if requested_field != "refinement":
        return False
    snapshot = request.latest_task_snapshot
    if snapshot is None or snapshot.pending_strategy_summary is None:
        return False
    if (
        _request_has_latest_result(request)
        and response.semantic_turn_act == "result_followup"
    ):
        return False
    if response.intent not in {"strategy_drafting", "backtest_execution"}:
        return True
    return not _llm_strategy_draft_has_extractable_fields(
        response.candidate_strategy_draft
    )


def _response_underfills_active_artifact_rule_edit(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    if not _request_has_active_strategy_context(request):
        return False
    if not response.requires_clarification or not response.assistant_response:
        return False
    if response.semantic_turn_act in {
        "approval",
        "educational_question",
        "result_followup",
        "retry_failed_action",
    }:
        return False
    draft = response.candidate_strategy_draft
    if _llm_strategy_draft_has_rule_or_indicator_fields(draft):
        return False
    return bool(draft.raw_user_phrasing or draft.strategy_thesis)


def _response_underfills_active_artifact_assumption_edit(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    if not _request_targets_pending_artifact_assumption_edit(request):
        return False
    if response.semantic_turn_act in {
        "approval",
        "educational_question",
        "result_followup",
        "retry_failed_action",
    }:
        return False
    if _refinement_reply_needs_full_interpretation(
        response=response,
        request=request,
    ):
        # Reshapes and rule tweaks are full-interpretation refine replies,
        # not assumption edits; treating them as underfilled would reject
        # the very response the planner path steps aside for.
        return False
    draft = response.candidate_strategy_draft
    if _llm_strategy_draft_has_supported_artifact_assumption_edit(draft):
        return False
    if response.requires_clarification and response.assistant_response:
        return False
    return bool(response.intent in {"strategy_drafting", "backtest_execution"})


def _refinement_reply_needs_full_interpretation(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    """A refine reply is only a planner edit when the response says so.

    The "Refine idea" prompt invites any change, including strategy reshapes
    ("make it recurring buys instead") that the edit-operation set cannot
    express. Those must keep flowing through full interpretation so the
    refine fork can produce a new draft; routing them into the planner would
    shoehorn the reshape into cadence/contribution sets and silently keep the
    old strategy type.
    """

    if _selected_requested_field_base(request) != "refinement":
        return False
    draft = response.candidate_strategy_draft
    pending = _current_artifact_strategy(request)
    draft_type = canonical_strategy_type(draft.strategy_type)
    pending_type = canonical_strategy_type(pending.strategy_type) if pending else None
    if draft_type and pending_type and draft_type != pending_type:
        return True
    if _active_artifact_asset_universe_operation_needs_planner(
        response=response,
        request=request,
    ):
        return False
    return not _refinement_reply_evidences_planner_edit(draft)


def _refinement_reply_evidences_planner_edit(draft: LLMStrategyDraft) -> bool:
    """Planner-expressible evidence in a refine reply.

    EditOperation also covers date_window and cadence, so date-only or
    cadence-only refine replies ("change the date range to 2021", "make it
    weekly") belong on the planner path even though they are not
    assumption-field edits.
    """

    if _llm_strategy_draft_has_supported_artifact_assumption_edit(draft):
        return True
    if str(draft.cadence or "").strip():
        return True
    return bool(
        draft.date_range
        or draft.date_range_intent is not None
        or str(draft.date_range_raw_text or "").strip()
    )


def _llm_strategy_draft_has_supported_artifact_assumption_edit(
    draft: LLMStrategyDraft,
) -> bool:
    field_provenance = draft.field_provenance or {}
    extra_parameters = draft.extra_parameters or {}
    return any(
        [
            draft.capital_amount is not None
            and field_provenance.get("capital_amount") in _TOTAL_CAPITAL_SOURCES,
            draft.initial_capital is not None
            and field_provenance.get("initial_capital") in _TOTAL_CAPITAL_SOURCES,
            draft.capital_amount is not None
            and field_provenance.get("capital_amount") == "recurring_contribution",
            draft.recurring_contribution is not None
            and field_provenance.get("recurring_contribution")
            == "recurring_contribution",
            bool(draft.asset_universe)
            and normalized_asset_universe_operation(draft.asset_universe_operation)
            is not None,
            bool(draft.comparison_baseline)
            and field_provenance.get("comparison_baseline") == "explicit_user",
            bool(draft.timeframe)
            and field_provenance.get("timeframe") == "explicit_user",
            "fee_rate" in extra_parameters
            and field_provenance.get("fee_rate") == "explicit_user",
            "slippage" in extra_parameters
            and field_provenance.get("slippage") == "explicit_user",
        ]
    )


def _llm_strategy_draft_has_structured_rule_or_indicator_fields(
    draft: LLMStrategyDraft,
) -> bool:
    return any(
        [
            bool(draft.entry_rule),
            bool(draft.exit_rule),
            bool(draft.rule_spec),
            bool(draft.indicator),
            draft.indicator_period is not None,
            draft.entry_threshold is not None,
            draft.exit_threshold is not None,
        ]
    )


def _llm_strategy_draft_has_executable_shape(draft: LLMStrategyDraft) -> bool:
    strategy_type = canonical_strategy_type(draft.strategy_type)
    if strategy_type == "buy_and_hold":
        return bool(draft.asset_universe or draft.date_range)
    if strategy_type == "dca_accumulation":
        return bool(_supported_dca_cadence_value(draft.cadence)) and (
            _dca_draft_has_recurring_amount(draft)
        )
    if strategy_type == "signal_strategy":
        return _llm_strategy_draft_has_structured_rule_or_indicator_fields(draft)
    return bool(
        draft.cadence or _llm_strategy_draft_has_structured_rule_or_indicator_fields(draft)
    )


def _llm_signal_strategy_is_underfilled(draft: LLMStrategyDraft) -> bool:
    if canonical_strategy_type(draft.strategy_type) != "signal_strategy":
        return False
    return not any([draft.entry_rule, draft.rule_spec])


def _llm_strategy_draft_has_structural_execution_fields(
    draft: LLMStrategyDraft,
) -> bool:
    return bool(_material_strategy_updates_from_draft(draft))


def _llm_strategy_draft_has_unstructured_strategy_text(
    draft: LLMStrategyDraft,
) -> bool:
    if _llm_strategy_draft_has_structural_execution_fields(draft):
        return False
    return bool(draft.raw_user_phrasing or draft.strategy_thesis)


def _response_replays_prior_strategy_without_current_turn_update(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    if "pending_response_option_selected" in response.reason_codes:
        return False
    if response.semantic_turn_act in {
        "approval",
        "educational_question",
        "result_followup",
        "retry_failed_action",
        "unsupported_request",
    }:
        return False
    if response.requires_clarification and response.assistant_response:
        return False
    snapshot = request.latest_task_snapshot
    if snapshot is None:
        return False
    prior = snapshot.pending_strategy_summary or snapshot.confirmed_strategy_summary
    if prior is None:
        return False
    draft = response.candidate_strategy_draft
    material_updates = _material_strategy_updates_from_draft(draft)
    if not material_updates:
        return True
    prior_payload = prior.model_dump(mode="python")
    for key, value in material_updates.items():
        if _normalized_material_strategy_value(key, prior_payload.get(key)) != value:
            return False
    return (
        response.task_relation == "refine"
        or request.current_user_message.strip()
        not in {
            str(prior.raw_user_phrasing or "").strip(),
            str(prior.strategy_thesis or "").strip(),
        }
    )


def _material_strategy_updates_from_draft(
    draft: LLMStrategyDraft,
) -> dict[str, Any]:
    payload = draft.model_dump(mode="python")
    material_fields = {
        "strategy_type",
        "asset_universe",
        "asset_class",
        "timeframe",
        "cadence",
        "entry_logic",
        "exit_logic",
        "date_range",
        "sizing_mode",
        "capital_amount",
        "position_size",
        "risk_rules",
        "comparison_baseline",
        "entry_rule",
        "exit_rule",
        "rule_spec",
    }
    updates = {
        key: _normalized_material_strategy_value(key, value)
        for key, value in payload.items()
        if key in material_fields and value not in (None, "", [], {})
    }
    if "date_range" not in updates and draft.date_range_intent is not None:
        intent_resolution = resolve_date_range_intent(draft.date_range_intent)
        if intent_resolution is not None:
            updates["date_range"] = _normalized_material_date_range_payload(
                intent_resolution.payload
            )
    indicator_updates = {
        key: payload.get(key)
        for key in {
            "indicator",
            "indicator_period",
            "entry_threshold",
            "exit_threshold",
        }
        if payload.get(key) is not None
    }
    if indicator_updates:
        updates["indicator_parameters"] = indicator_updates
    return updates


def _normalized_material_strategy_value(key: str, value: Any) -> Any:
    if key == "date_range":
        return _normalized_material_date_range_payload(value)
    if key == "asset_universe" and isinstance(value, list):
        return [str(symbol).strip().upper() for symbol in value if str(symbol).strip()]
    return value


def _normalized_material_date_range_payload(value: Any) -> Any:
    normalized = normalize_date_range_candidate(value)
    if isinstance(normalized, str):
        natural = resolve_date_range_text(normalized)
        if natural is not None:
            return ("resolved", natural.start.isoformat(), natural.end.isoformat())
    try:
        resolved = resolve_date_range(normalized)
    except Exception:
        return normalized
    if resolved.used_default and isinstance(normalized, str) and normalized.strip():
        return (
            "unresolved_default",
            resolved.start.isoformat(),
            resolved.end.isoformat(),
        )
    return ("resolved", resolved.start.isoformat(), resolved.end.isoformat())


def _request_has_latest_result(request: InterpretationRequest) -> bool:
    snapshot = request.latest_task_snapshot
    return bool(snapshot and snapshot.latest_backtest_result_reference is not None)


def _request_has_active_strategy_context(request: InterpretationRequest) -> bool:
    snapshot = request.latest_task_snapshot
    if snapshot is None:
        return False
    return bool(
        snapshot.pending_strategy_summary
        or snapshot.confirmed_strategy_summary
        or snapshot.active_confirmation_reference
    )
