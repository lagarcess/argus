from __future__ import annotations

import math
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation

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

# A user states costs as a decimal rate, a percentage, or basis points; the
# same three readings ground both corroboration and numeric anchoring.
_COST_UNIT_DIVISORS = (Decimal(1), Decimal(100), Decimal(10000))

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
    refused_fields: set[str] = set()
    for audit_field, draft_field in (
        ("fee", "fee_rate"),
        ("slippage", "slippage"),
    ):
        cost = getattr(audit, audit_field)
        evidence_span = _bounded_cost_evidence(cost, current_message=current_message)
        if evidence_span is None:
            continue
        rate = _supported_cost_rate(cost, field_name=draft_field)
        if rate is None:
            # The user stated the value and it anchors in the message; the
            # value itself cannot be modeled. That is a refusal, not an
            # ambiguity.
            refused_fields.add(draft_field)
            grounded_conflicts.add(draft_field)
            continue
        if not _candidate_agrees_with_cost(
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
        if draft._validated_execution_cost_evidence.get(draft_field) != validated_marker:
            draft._validated_execution_cost_evidence[draft_field] = validated_marker
            changed = True

    unresolved_fields: list[str] = []
    for field_name in ("fee_rate", "slippage"):
        if field_name in validated_fields:
            continue
        if field_name not in grounded_conflicts and _cost_retains_validated_evidence(
            draft,
            field_name=field_name,
            current_message=current_message,
        ):
            # Deterministic validation already earned this turn survives an
            # absent or empty audit; re-litigating it is how a repair pass
            # silently drops a stated cost (#367). A conflicting audit above
            # still wins, because it read the same message and disagreed.
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
    for field_name in unresolved_fields:
        if field_name in refused_fields:
            _record_cost_refusal_disclosure(draft, field_name=field_name)
            changed = True
    if all(field_name in refused_fields for field_name in unresolved_fields):
        # Every unresolved cost is a disclosed refusal: the card names it with
        # a reason, exactly as the planner route would, so the turn proceeds
        # instead of stalling the rest of the user's edit (§3.2).
        response.reason_codes = list(
            dict.fromkeys(
                [
                    *response.reason_codes,
                    "stated_run_field_fidelity_audit",
                    "execution_cost_refusal_disclosed",
                ]
            )
        )
        return True
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


_COST_FIELD_DISCLOSURE_TARGETS = {"fee_rate": "fees", "slippage": "slippage"}


def _record_cost_refusal_disclosure(draft: LLMStrategyDraft, *, field_name: str) -> None:
    """Card turns drop assistant prose, so a refused stated cost rides the
    draft as a typed disclosure record instead of vanishing (§3.2)."""

    target = _COST_FIELD_DISCLOSURE_TARGETS.get(field_name, field_name)
    disclosure = draft.extra_parameters.get("edit_disclosure")
    if not isinstance(disclosure, dict):
        disclosure = {}
    unapplied = [
        entry for entry in (disclosure.get("unapplied") or []) if isinstance(entry, dict)
    ]
    if any(entry.get("target") == target for entry in unapplied):
        return
    unapplied.append({"op": "set", "target": target, "reason": "unsupported_value"})
    disclosure["unapplied"] = unapplied
    draft.extra_parameters["edit_disclosure"] = disclosure


def _cost_retains_validated_evidence(
    draft: LLMStrategyDraft,
    *,
    field_name: str,
    current_message: str,
) -> bool:
    """A cost the deterministic channel already validated for this value.

    A str span must still anchor in the current message; a None span is typed
    edit-plan provenance and needs no quote. A value that no longer matches
    the validated marker is a new claim and gets no pass.
    """
    marker = draft._validated_execution_cost_evidence.get(field_name)
    if marker is None:
        return False
    rate, span = marker
    candidate = draft.extra_parameters.get(field_name)
    if isinstance(candidate, bool) or not isinstance(candidate, (int, float)):
        return False
    if float(candidate) != float(rate):
        return False
    if span is None:
        return True
    return bool(span) and span in str(current_message or "")


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
    """One rate-sanity rule for every channel that can own a modeled cost.

    The caps are the engine envelope's, imported rather than restated, so the
    resolver can never admit a rate the run-time validator refuses.
    """
    from argus.domain.backtesting.config import MAX_FEE_RATE, MAX_SLIPPAGE_RATE

    if not math.isfinite(rate) or rate < 0.0:
        return None
    if field_name == "slippage" and rate > MAX_SLIPPAGE_RATE:
        return None
    if field_name == "fee_rate" and rate > MAX_FEE_RATE:
        return None
    return rate


def ground_planned_execution_costs(
    draft: LLMStrategyDraft,
    *,
    current_message: str,
    primary_draft: LLMStrategyDraft | None,
    extra_parameters: dict[str, object],
    field_provenance: dict[str, str],
) -> list[str]:
    """A planned cost may become owned only when the same turn's primary
    interpretation corroborates the value and the current message anchors it
    (verbatim primary span, or a message number under a supported cost unit).
    Ungrounded planned costs are removed instead of gaining provenance."""

    dropped: list[str] = []
    for field_name in ("fee_rate", "slippage"):
        if field_name not in extra_parameters:
            continue
        rate = extra_parameters[field_name]
        grounded, span = planned_cost_change_is_grounded(
            rate,
            field_name=field_name,
            current_message=current_message,
            corroborating_values=(
                primary_draft.extra_parameters if primary_draft is not None else None
            ),
            corroborating_spans=(
                primary_draft.evidence_spans if primary_draft is not None else None
            ),
        )
        if grounded:
            if span is not None:
                draft.evidence_spans[field_name] = span
            draft._validated_execution_cost_evidence[field_name] = (
                float(rate),  # type: ignore[arg-type]
                span,
            )
            continue
        dropped.append(field_name)
        extra_parameters.pop(field_name, None)
        field_provenance.pop(field_name, None)
        draft.extra_parameters.pop(field_name, None)
        draft.field_provenance.pop(field_name, None)
        draft.evidence_spans.pop(field_name, None)
        draft._validated_execution_cost_evidence.pop(field_name, None)
    return dropped


def planned_cost_change_is_grounded(
    rate: object,
    *,
    field_name: str,
    current_message: str,
    corroborating_values: Mapping[str, object] | None,
    corroborating_spans: Mapping[str, object] | None,
) -> tuple[bool, str | None]:
    """Grounding rule for a planned cost value. When the turn has an
    independent interpretation, it must corroborate the value (any supported
    cost unit) and the current message must anchor it — a verbatim
    corroborating span, or a message number that reads as the value under a
    supported unit. When no interpretation exists (interpreter-unavailable
    continuity), the message number is the only available evidence and is
    required on its own."""

    if corroborating_values is None:
        return numeric_cost_anchor_in_message(rate, current_message), None
    if not _unit_equivalent_cost(corroborating_values.get(field_name), rate):
        return False, None
    span = str((corroborating_spans or {}).get(field_name) or "").strip()
    if span and span in str(current_message):
        return True, span
    if numeric_cost_anchor_in_message(rate, current_message):
        return True, None
    return False, None


def numeric_cost_anchor_in_message(rate: object, message: str) -> bool:
    target = _decimal_or_none(rate)
    if target is None:
        return False
    for number in _numeric_message_tokens(str(message or "")):
        if any(number / divisor == target for divisor in _COST_UNIT_DIVISORS):
            return True
    return False


def _numeric_message_tokens(message: str) -> list[Decimal]:
    numbers: list[Decimal] = []
    for raw_token in message.split():
        token = raw_token.strip("%$€£:;,!?()[]{}\"'").replace(",", "")
        while token.endswith("."):
            token = token[:-1]
        number = _decimal_or_none(token)
        if number is not None:
            numbers.append(number)
    return numbers


def _unit_equivalent_cost(candidate: object, rate: object) -> bool:
    stated = _decimal_or_none(candidate)
    target = _decimal_or_none(rate)
    if stated is None or target is None:
        return False
    return any(stated / divisor == target for divisor in _COST_UNIT_DIVISORS)


def _decimal_or_none(value: object) -> Decimal | None:
    if isinstance(value, bool):
        return None
    if not isinstance(value, (int, float, str)):
        return None
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None
    if not parsed.is_finite():
        return None
    return parsed


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
