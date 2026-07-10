"""Evidence helpers for preserving unsupported indicator mentions."""

from __future__ import annotations

from typing import Any

from argus.agent_runtime.state.models import StrategySummary
from argus.domain.indicators import (
    draft_only_indicator_from_text,
    executable_indicator_spec,
)


def explicit_draft_only_indicator_evidence(
    *,
    strategy: StrategySummary,
    current_user_message: str,
) -> tuple[Any, str] | None:
    extra_parameters = dict(strategy.extra_parameters or {})
    field_provenance = extra_parameters.get("field_provenance")
    if not isinstance(field_provenance, dict):
        field_provenance = {}
    evidence_spans = extra_parameters.get("evidence_spans")
    if not isinstance(evidence_spans, dict):
        evidence_spans = {}
    indicator_is_user_explicit = field_provenance.get("indicator") == "explicit_user"
    period_is_user_explicit = (
        field_provenance.get("indicator_period") == "explicit_user"
    )
    candidates: list[Any] = []
    if isinstance(evidence_spans.get("indicator"), str):
        candidates.append(evidence_spans.get("indicator"))
    if indicator_is_user_explicit or period_is_user_explicit:
        candidates.append(extra_parameters.get("indicator"))
        indicator_parameters = extra_parameters.get("indicator_parameters")
        if isinstance(indicator_parameters, dict):
            candidates.append(indicator_parameters.get("indicator"))
        candidates.append(current_user_message)
    if not candidates:
        return None
    for candidate in candidates:
        if not isinstance(candidate, str) or not candidate.strip():
            continue
        if executable_indicator_spec(candidate) is not None:
            continue
        draft_only_indicator = draft_only_indicator_from_text(candidate)
        if draft_only_indicator is not None:
            return draft_only_indicator, candidate.strip()
    return None


def strategy_type_is_user_selected(strategy: StrategySummary) -> bool:
    extra_parameters = dict(strategy.extra_parameters or {})
    field_provenance = extra_parameters.get("field_provenance")
    if not isinstance(field_provenance, dict):
        return False
    return field_provenance.get("strategy_type") in {
        "explicit_user",
        "pending_response_option",
    }
