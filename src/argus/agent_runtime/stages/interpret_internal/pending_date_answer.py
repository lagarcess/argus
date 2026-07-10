"""Pending date-answer interpretation helpers for interpret stage."""

from __future__ import annotations

from datetime import date
from typing import Any

from argus.agent_runtime.stages.interpret_internal.asset_resolution import (
    _active_strategy_from_snapshot,
)
from argus.agent_runtime.stages.interpret_internal.date_contract import (
    _date_range_endpoints,
)
from argus.agent_runtime.stages.interpret_internal.shared import _field_base
from argus.agent_runtime.stages.interpret_types import StructuredInterpretation
from argus.agent_runtime.state.models import StrategySummary, TaskSnapshot
from argus.agent_runtime.strategy_contract import (
    executable_strategy_type,
    strategy_can_be_approved,
)
from argus.nlp.natural_time import (
    dateparser_languages_for_user_language,
    parse_date_text,
    resolve_calendar_year_intent_text,
    resolve_date_range_endpoint_patch,
    resolve_date_range_intent,
    resolve_date_range_text,
)


def pending_date_answer_interpretation(
    *,
    current_user_message: str,
    language: str | None,
    snapshot: TaskSnapshot | None,
    selected_thread_metadata: dict[str, Any],
    today: date | None = None,
    reason_code: str = "pending_date_answer_route_repaired",
    user_goal_summary: str = (
        "User supplied the requested date range after structured interpretation "
        "misrouted the pending-field answer."
    ),
) -> StructuredInterpretation | None:
    requested_field = _field_base(
        str(selected_thread_metadata.get("requested_field") or "")
    )
    if requested_field != "date_range":
        return None
    if snapshot is None or snapshot.pending_strategy_summary is None:
        return None
    if snapshot.latest_backtest_result_reference is not None:
        return None
    last_stage_outcome = str(selected_thread_metadata.get("last_stage_outcome") or "")
    if last_stage_outcome and last_stage_outcome != "await_user_reply":
        return None
    prior = _active_strategy_from_snapshot(snapshot)
    if prior is None:
        return None
    if not _prior_strategy_allows_pending_date_answer_fallback(prior):
        return None
    current_date = today or date.today()
    text = current_user_message.strip()
    if not text:
        return None
    prior_endpoints = _date_range_endpoints(prior.date_range)
    prior_has_complete_date_range = prior_endpoints is not None and all(
        prior_endpoints
    )
    languages = dateparser_languages_for_user_language(language)
    resolved_range = resolve_date_range_text(
        text,
        today=current_date,
        languages=languages,
    )
    date_range: dict[str, str] | None = None
    date_range_intent: dict[str, Any] | None = None
    if resolved_range is not None:
        date_range = resolved_range.payload
    else:
        year_intent = resolve_calendar_year_intent_text(
            text,
            today=current_date,
            languages=languages,
        )
        if year_intent is not None:
            intent_resolution = resolve_date_range_intent(
                year_intent,
                today=current_date,
            )
            if intent_resolution is None:
                return None
            date_range = intent_resolution.payload
            date_range_intent = year_intent
        else:
            start_endpoint = parse_date_text(
                text,
                today=current_date,
                endpoint="start",
                languages=languages,
                prefer_dates_from="past",
            )
            endpoint = parse_date_text(
                text,
                today=current_date,
                endpoint="end",
                languages=languages,
                prefer_dates_from="past",
            )
            if endpoint is None:
                return None
            if (
                not prior_has_complete_date_range
                and start_endpoint is not None
                and start_endpoint <= endpoint
            ):
                date_range = {
                    "start": start_endpoint.isoformat(),
                    "end": endpoint.isoformat(),
                }
                date_range_intent = _date_range_intent_from_endpoints(
                    start=start_endpoint,
                    end=endpoint,
                    evidence=text,
                )
            endpoint_patch = {
                "kind": "endpoint_patch",
                "endpoint": "end",
                "end": endpoint.isoformat(),
                "confidence": 0.8,
                "evidence": text,
            }
            if date_range is None:
                prior_intent = prior.extra_parameters.get("date_range_intent")
                resolved_patch = resolve_date_range_endpoint_patch(
                    prior_intent,
                    endpoint_patch,
                    today=current_date,
                )
                if resolved_patch is not None:
                    date_range = resolved_patch.payload
                    date_range_intent = {
                        **endpoint_patch,
                        "base_intent": prior_intent,
                    }
                else:
                    date_range = {"end": endpoint.isoformat()}
                    date_range_intent = endpoint_patch
        if date_range is None:
            return None
    extra_parameters: dict[str, Any] = {
        "date_range_raw_text": text,
        "evidence_spans": {"date_range": text},
    }
    if date_range_intent is not None:
        extra_parameters["date_range_intent"] = date_range_intent
    return StructuredInterpretation(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary=user_goal_summary,
        candidate_strategy_draft=StrategySummary(
            date_range=date_range,
            extra_parameters=extra_parameters,
        ),
        missing_required_fields=[],
        semantic_turn_act="answer_pending_need",
        reason_codes=[reason_code],
    )


def _date_range_intent_from_endpoints(
    *,
    start: date,
    end: date,
    evidence: str,
) -> dict[str, Any]:
    if (
        start.month == 1
        and start.day == 1
        and end.month == 12
        and end.day == 31
        and start.year == end.year
    ):
        return {
            "kind": "calendar_year",
            "year": start.year,
            "confidence": 0.8,
            "evidence": evidence,
        }
    return {
        "kind": "explicit_range",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "confidence": 0.8,
        "evidence": evidence,
    }


def _prior_strategy_allows_pending_date_answer_fallback(
    prior: StrategySummary,
) -> bool:
    endpoints = _date_range_endpoints(prior.date_range)
    if strategy_can_be_approved(prior):
        return endpoints is not None and all(endpoints)
    if endpoints is not None and any(endpoints):
        return False
    if executable_strategy_type(prior) not in {"buy_and_hold", "dca_accumulation"}:
        return False
    candidate = prior.model_copy(deep=True)
    candidate.date_range = {"start": "2000-01-01", "end": "2000-12-31"}
    return strategy_can_be_approved(candidate)
