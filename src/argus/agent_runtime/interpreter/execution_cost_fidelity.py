from __future__ import annotations

import math

from argus.agent_runtime.interpreter.audits import (
    StatedExecutionCost,
    StatedRunFieldFidelityAudit,
)
from argus.agent_runtime.interpreter.execution_cost_capability import (
    execution_costs_enabled,
)
from argus.agent_runtime.llm_interpreter_types import (
    LLMInterpretationResponse,
    LLMStrategyDraft,
)
from argus.agent_runtime.state.models import StrategySummary

EXECUTION_COST_FIDELITY_INSTRUCTIONS = (
    "For a fee or slippage stated in the current message, return the matching "
    "typed fee or slippage object with its canonical decimal rate and an exact "
    "bounded evidence_span copied from that message. One basis point is 0.0001, so "
    "10 bps is 0.001 and 5 bps is 0.0005. Preserve 0.0 for an explicit clear. "
    "Leave the object null when that cost is absent, and never copy a draft-only "
    "default or cost. "
)


def apply_cost_fidelity(
    response: LLMInterpretationResponse,
    audit: StatedRunFieldFidelityAudit,
    current_message: str,
    prior_strategy: StrategySummary | None,
) -> bool:
    if not execution_costs_enabled():
        return False
    draft = response.candidate_strategy_draft
    changed = False
    validated_fields: set[str] = set()
    grounded_conflicts: set[str] = set()
    for audit_field, draft_field in (
        ("fee", "fee_rate"),
        ("slippage", "slippage"),
    ):
        cost = getattr(audit, audit_field)
        evidence_span = _bounded_cost_evidence(cost, current_message=current_message)
        if evidence_span is None:
            continue
        rate = _supported_cost_rate(cost, field_name=draft_field)
        if rate is None or not _candidate_agrees_with_cost(
            draft.extra_parameters.get(draft_field),
            rate,
        ):
            grounded_conflicts.add(draft_field)
            continue
        validated_fields.add(draft_field)
        if draft.extra_parameters.get(draft_field) != rate:
            draft.extra_parameters[draft_field] = rate
            changed = True
        if draft.evidence_spans.get(draft_field) != evidence_span:
            draft.evidence_spans[draft_field] = evidence_span
            changed = True
        if draft.field_provenance.get(draft_field) != "explicit_user":
            draft.field_provenance[draft_field] = "explicit_user"
            changed = True
        validated_marker = (rate, evidence_span)
        if draft._validated_execution_cost_evidence.get(
            draft_field
        ) != validated_marker:
            draft._validated_execution_cost_evidence[draft_field] = validated_marker
            changed = True

    unresolved_fields: list[str] = []
    for field_name in ("fee_rate", "slippage"):
        if field_name in validated_fields:
            continue
        if field_name in grounded_conflicts or _introduces_unowned_cost(
            draft, field_name=field_name, prior_strategy=prior_strategy
        ):
            unresolved_fields.append(field_name)
        if field_name in draft.extra_parameters:
            draft.extra_parameters.pop(field_name, None)
            changed = True
        if field_name in draft.evidence_spans:
            draft.evidence_spans.pop(field_name, None)
            changed = True
        if field_name in draft.field_provenance:
            draft.field_provenance.pop(field_name, None)
            changed = True
        draft._validated_execution_cost_evidence.pop(field_name, None)

    if not unresolved_fields:
        return changed
    response.requires_clarification = True
    response.assistant_response = None
    response.missing_required_fields = list(
        dict.fromkeys([*response.missing_required_fields, "assumption"])
    )
    response.reason_codes = list(
        dict.fromkeys(
            [
                *response.reason_codes,
                "stated_run_field_fidelity_audit",
                "execution_cost_evidence_unresolved",
            ]
        )
    )
    return True


def _bounded_cost_evidence(
    cost: StatedExecutionCost | None,
    *,
    current_message: str,
) -> str | None:
    if cost is None:
        return None
    evidence_span = cost.evidence_span.strip()
    if not evidence_span or evidence_span not in current_message:
        return None
    return evidence_span


def _supported_cost_rate(
    cost: StatedExecutionCost,
    *,
    field_name: str,
) -> float | None:
    return supported_cost_rate_value(float(cost.rate), field_name=field_name)


def supported_cost_rate_value(rate: float, *, field_name: str) -> float | None:
    """One rate-sanity rule for every channel that can own a modeled cost."""

    if not math.isfinite(rate) or rate < 0.0:
        return None
    if field_name == "slippage" and rate > 0.05:
        return None
    return rate


def record_typed_plan_cost_evidence(
    draft: LLMStrategyDraft,
    *,
    field_name: str,
    rate: float,
) -> None:
    """Typed edit-plan resolution is validated cost evidence with no quote span."""

    draft._validated_execution_cost_evidence[field_name] = (rate, None)


def _candidate_agrees_with_cost(candidate: object, rate: float) -> bool:
    if candidate is None:
        return True
    if isinstance(candidate, bool) or not isinstance(candidate, (int, float)):
        return False
    candidate_rate = float(candidate)
    return math.isfinite(candidate_rate) and candidate_rate == rate


def _introduces_unowned_cost(
    draft: LLMStrategyDraft,
    *,
    field_name: str,
    prior_strategy: StrategySummary | None,
) -> bool:
    if field_name not in draft.extra_parameters:
        return False
    try:
        candidate_rate = float(draft.extra_parameters[field_name])
    except (TypeError, ValueError):
        return True
    if not math.isfinite(candidate_rate) or candidate_rate < 0.0:
        return True
    prior_rate = _owned_prior_cost(prior_strategy, field_name=field_name)
    return prior_rate is None or candidate_rate != prior_rate


def _owned_prior_cost(
    strategy: StrategySummary | None,
    *,
    field_name: str,
) -> float | None:
    if strategy is None:
        return None
    provenance = strategy.extra_parameters.get("field_provenance")
    if not isinstance(provenance, dict):
        return None
    if provenance.get(field_name) != "explicit_user":
        return None
    if field_name not in strategy.extra_parameters:
        return None
    try:
        rate = float(strategy.extra_parameters[field_name])
    except (TypeError, ValueError):
        return None
    if not math.isfinite(rate) or rate < 0.0:
        return None
    return rate
