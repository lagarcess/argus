"""Current-message date/run-field contract helpers.

Behavior-preserving relocation from stages/interpret.py (issue #131)."""

from __future__ import annotations

from typing import Any

from argus.agent_runtime.stages.interpret_internal.asset_resolution import (
    _active_strategy_from_snapshot,
)
from argus.agent_runtime.stages.interpret_internal.shared import _field_base
from argus.agent_runtime.stages.interpret_types import (
    SemanticTurnAct,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import (
    StrategySummary,
    TaskSnapshot,
)
from argus.agent_runtime.strategy_contract import has_partial_explicit_date_range

_DATE_RANGE_EVIDENCE_KEYS = (
    "date_range",
    "date_range_raw_text",
    "date_range_intent",
)


def _changed_date_endpoint(
    *,
    date_range: dict[str, str] | None,
    prior_date_range: Any,
) -> tuple[str, str] | None:
    if not isinstance(date_range, dict):
        return None
    start = date_range.get("start") or date_range.get("from")
    end = date_range.get("end") or date_range.get("to")
    start_value = str(start).strip() if start not in (None, "", [], {}) else None
    end_value = str(end).strip() if end not in (None, "", [], {}) else None
    if bool(start_value) != bool(end_value):
        endpoint = "start" if start_value else "end"
        value = start_value or end_value
        return (endpoint, value) if value else None

    prior_endpoints = _date_range_endpoints(prior_date_range)
    if prior_endpoints is None or start_value is None or end_value is None:
        return None
    prior_start, prior_end = prior_endpoints
    start_changed = prior_start is not None and start_value != prior_start
    end_changed = prior_end is not None and end_value != prior_end
    if start_changed == end_changed:
        return None
    return ("start", start_value) if start_changed else ("end", end_value)


def _strategy_date_evidence_candidates(strategy: StrategySummary) -> list[str]:
    candidates: list[str] = []
    extra_parameters = dict(strategy.extra_parameters or {})
    raw_text = extra_parameters.get("date_range_raw_text")
    if raw_text not in (None, "", [], {}):
        candidates.append(str(raw_text))
    intent = extra_parameters.get("date_range_intent")
    if isinstance(intent, dict):
        evidence = intent.get("evidence")
        if evidence not in (None, "", [], {}):
            candidates.append(str(evidence))
    evidence_spans = extra_parameters.get("evidence_spans")
    if isinstance(evidence_spans, dict):
        for key in _DATE_RANGE_EVIDENCE_KEYS:
            value = evidence_spans.get(key)
            if value not in (None, "", [], {}):
                candidates.append(str(value))
    return list(dict.fromkeys(candidate.strip() for candidate in candidates if candidate.strip()))


def _strategy_date_range_needs_current_message_repair(
    *,
    strategy: StrategySummary,
    interpretation: StructuredInterpretation,
    current_date_range: dict[str, str],
) -> bool:
    if interpretation.semantic_turn_act == "answer_pending_need":
        return (
            strategy.date_range in (None, "", [], {})
            or has_partial_explicit_date_range(strategy.date_range)
            or not isinstance(strategy.date_range, dict)
            or _date_range_endpoints(strategy.date_range)
            != _date_range_endpoints(current_date_range)
        )
    if strategy.date_range in (None, "", [], {}):
        return True
    if has_partial_explicit_date_range(strategy.date_range):
        return True
    if isinstance(strategy.date_range, str):
        return False
    if _date_range_endpoints(strategy.date_range) != _date_range_endpoints(
        current_date_range
    ):
        return True
    return any(
        str(field).split("[", 1)[0] == "date_range"
        for field in interpretation.missing_required_fields
    ) or any(
        field.field_name.split("[", 1)[0] == "date_range"
        for field in interpretation.ambiguous_fields
    )


def _pending_date_edit_reuses_prior_date_range(
    *,
    strategy: StrategySummary,
    snapshot: TaskSnapshot | None,
    selected_thread_metadata: dict[str, Any],
    semantic_turn_act: SemanticTurnAct | None,
) -> bool:
    if semantic_turn_act != "answer_pending_need":
        return False
    if selected_thread_metadata.get("last_stage_outcome") != "await_user_reply":
        return False
    requested_field = _field_base(
        str(selected_thread_metadata.get("requested_field") or "")
    )
    if requested_field != "date_range":
        return False
    prior = _active_strategy_from_snapshot(snapshot)
    if prior is None:
        return False
    prior_endpoints = _date_range_endpoints(prior.date_range)
    if prior_endpoints is None or not all(prior_endpoints):
        return False
    return _date_range_endpoints(strategy.date_range) == prior_endpoints


def _date_range_endpoints(value: Any) -> tuple[str | None, str | None] | None:
    if not isinstance(value, dict):
        return None
    start = value.get("start") or value.get("from")
    end = value.get("end") or value.get("to")
    return (
        str(start).strip() if start not in (None, "", [], {}) else None,
        str(end).strip() if end not in (None, "", [], {}) else None,
    )


def _strategy_has_non_executable_timeframe_label(
    strategy: StrategySummary,
    *,
    supported_timeframes: tuple[str, ...],
) -> bool:
    if strategy.timeframe in (None, "", [], {}):
        return False
    normalized = str(strategy.timeframe).strip().casefold().replace(" ", "")
    supported = {
        str(value).strip().casefold().replace(" ", "")
        for value in supported_timeframes
    }
    return bool(normalized and normalized not in supported)
