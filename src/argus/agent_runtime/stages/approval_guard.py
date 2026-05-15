from __future__ import annotations

from typing import Any

from argus.agent_runtime.stages.interpret_types import (
    InterpretDecision,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import StrategySummary

_MATERIAL_STRATEGY_FIELDS = (
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
    "assumptions",
    "comparison_baseline",
    "entry_rule",
    "exit_rule",
    "rule_spec",
    "extra_parameters",
)
_CARD_ACTION_REQUEST_FIELDS = tuple(
    field for field in _MATERIAL_STRATEGY_FIELDS if field != "extra_parameters"
)


def decision_is_pure_approval(
    *,
    decision: InterpretDecision,
    visible_strategy: StrategySummary,
    interpretation: StructuredInterpretation | None = None,
    interpreted_candidate_strategy: StrategySummary | None = None,
) -> bool:
    """Return whether free text can safely approve the visible confirmation."""
    semantic_turn_act = (
        interpretation.semantic_turn_act
        if interpretation is not None
        else decision.semantic_turn_act
    )
    task_relation = (
        interpretation.task_relation if interpretation is not None else decision.task_relation
    )
    requires_clarification = (
        interpretation.requires_clarification
        if interpretation is not None
        else decision.requires_clarification
    )
    missing_required_fields = (
        interpretation.missing_required_fields
        if interpretation is not None
        else decision.missing_required_fields
    )
    ambiguous_fields = (
        interpretation.ambiguous_fields
        if interpretation is not None
        else decision.ambiguous_fields
    )
    unsupported_constraints = (
        interpretation.unsupported_constraints
        if interpretation is not None
        else decision.unsupported_constraints
    )
    if semantic_turn_act != "approval":
        return False
    if task_relation != "continue":
        return False
    if (
        requires_clarification
        or missing_required_fields
        or ambiguous_fields
        or unsupported_constraints
    ):
        return False
    return not _candidate_contains_material_strategy_patch(
        candidate=interpreted_candidate_strategy or decision.candidate_strategy_draft,
        visible=visible_strategy,
    )


def decision_requests_confirmation_card_action(
    *,
    decision: InterpretDecision,
    visible_strategy: StrategySummary,
    interpretation: StructuredInterpretation | None = None,
    interpreted_candidate_strategy: StrategySummary | None = None,
) -> bool:
    """Return whether text should defer to the visible card action controls."""
    semantic_turn_act = (
        interpretation.semantic_turn_act
        if interpretation is not None
        else decision.semantic_turn_act
    )
    task_relation = (
        interpretation.task_relation if interpretation is not None else decision.task_relation
    )
    requires_clarification = (
        interpretation.requires_clarification
        if interpretation is not None
        else decision.requires_clarification
    )
    missing_required_fields = (
        interpretation.missing_required_fields
        if interpretation is not None
        else decision.missing_required_fields
    )
    ambiguous_fields = (
        interpretation.ambiguous_fields
        if interpretation is not None
        else decision.ambiguous_fields
    )
    if semantic_turn_act != "approval":
        return False
    if task_relation != "continue":
        return False
    if requires_clarification or missing_required_fields or ambiguous_fields:
        return False
    candidate = interpreted_candidate_strategy or decision.candidate_strategy_draft
    return not _candidate_contains_material_strategy_patch(
        candidate=candidate,
        visible=visible_strategy,
        material_fields=_CARD_ACTION_REQUEST_FIELDS,
    )


def _candidate_contains_material_strategy_patch(
    *,
    candidate: StrategySummary,
    visible: StrategySummary,
    material_fields: tuple[str, ...] = _MATERIAL_STRATEGY_FIELDS,
) -> bool:
    candidate_payload = candidate.model_dump(mode="python")
    visible_payload = visible.model_dump(mode="python")
    for field_name in material_fields:
        candidate_value = candidate_payload.get(field_name)
        if candidate_value in (None, "", [], {}):
            continue
        if _normalize_strategy_value(
            field_name,
            candidate_value,
        ) != _normalize_strategy_value(field_name, visible_payload.get(field_name)):
            return True
    return False


def _normalize_strategy_value(field_name: str, value: Any) -> Any:
    if value in (None, "", [], {}):
        return None
    if field_name == "asset_universe" and isinstance(value, list):
        return tuple(str(item).strip().upper() for item in value if str(item).strip())
    if isinstance(value, list):
        return tuple(_normalize_strategy_value(field_name, item) for item in value)
    if isinstance(value, dict):
        normalized_items = {
            str(key): _normalize_strategy_value(str(key), nested)
            for key, nested in value.items()
            if nested not in (None, "", [], {})
        }
        return tuple(sorted(normalized_items.items()))
    if isinstance(value, str):
        return value.strip().lower()
    return value
