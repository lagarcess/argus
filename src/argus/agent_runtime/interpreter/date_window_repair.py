"""Temporal/date-window repair and focused-date-window extraction helpers.

Behavior-preserving relocation from llm_interpreter.py (issue #131)."""

from __future__ import annotations

from argus.agent_runtime.interpreter.draft_shape import (
    _request_has_active_strategy_context,
)
from argus.agent_runtime.interpreter.run_field_audits import (
    _response_has_pending_base_field,
)
from argus.agent_runtime.interpreter.shared import (
    _date_range_from_intent_or_bounded_evidence,
    _draft_has_semantic_date_window_evidence,
    _draft_semantic_evidence_spans,
    _field_path_base,
    _has_complete_date_range_payload,
    _llm_strategy_draft_has_concrete_execution_target,
    _llm_strategy_draft_has_rule_or_indicator_fields,
    _llm_value_is_empty,
    _natural_time_language_candidates_from_hints,
    _normalized_stated_field,
)
from argus.agent_runtime.llm_interpreter_types import (
    FocusedDateWindowExtraction,
    LLMInterpretationResponse,
    LLMStrategyDraft,
)
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.strategy_contract import (
    SUPPORTED_STRATEGY_TYPES,
    canonical_strategy_type,
    executable_strategy_type,
    has_partial_explicit_date_range,
    normalize_date_range_candidate,
    resolve_date_range,
)
from argus.nlp.natural_time import (
    resolve_date_range_intent,
    resolve_date_range_text,
    resolve_rolling_window_intent_text,
)


def _response_needs_temporal_runtime_repair(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    if _request_has_pending_date_answer_context(request):
        return True
    if _response_has_repairable_current_turn_date_gap(
        response=response,
        request=request,
    ):
        return True
    draft = response.candidate_strategy_draft
    if has_partial_explicit_date_range(draft.date_range):
        return True
    resolved_from_draft = _date_range_from_intent_or_bounded_evidence(
        draft,
        language=request.user.language_preference,
    )
    if _llm_value_is_empty(draft.date_range):
        return resolved_from_draft is not None
    current_message_range = _date_range_from_current_turn_message(request)
    if (
        current_message_range is not None
        and isinstance(draft.date_range, dict)
        and not has_partial_explicit_date_range(draft.date_range)
        and _normalized_stated_field(draft.date_range)
        != _normalized_stated_field(current_message_range)
        and (
            "runtime_date_range_normalization" not in response.reason_codes
            or _current_turn_has_relative_window_evidence(request)
        )
    ):
        return True
    if _current_turn_has_relative_window_evidence(request):
        return (
            resolved_from_draft is None
            or not isinstance(draft.date_range, dict)
            or has_partial_explicit_date_range(draft.date_range)
            or _normalized_stated_field(draft.date_range)
            != _normalized_stated_field(resolved_from_draft)
        )
    if (
        resolved_from_draft is not None
        and isinstance(draft.date_range, dict)
        and not has_partial_explicit_date_range(draft.date_range)
        and _normalized_stated_field(draft.date_range)
        != _normalized_stated_field(resolved_from_draft)
    ):
        return True
    return False


def _date_range_from_current_turn_message(
    request: InterpretationRequest,
) -> dict[str, str] | None:
    current_message = request.current_user_message.strip()
    if not current_message:
        return None
    for languages in _natural_time_language_candidates_from_hints(
        request.user.language_preference
    ):
        resolved = resolve_date_range_text(current_message, languages=languages)
        if resolved is not None:
            return resolved.payload
    return None


def _current_turn_has_relative_window_evidence(
    request: InterpretationRequest,
) -> bool:
    current_message = request.current_user_message.strip()
    if not current_message:
        return False
    for languages in _natural_time_language_candidates_from_hints(
        request.user.language_preference
    ):
        if (
            resolve_rolling_window_intent_text(current_message, languages=languages)
            is not None
        ):
            return True
    return False


def _clear_auto_simplified_strategy_when_rule_is_ambiguous(
    response: LLMInterpretationResponse,
) -> LLMInterpretationResponse:
    if not _response_has_ambiguous_rule_fields(response):
        return response
    draft = response.candidate_strategy_draft
    if canonical_strategy_type(draft.strategy_type) not in {
        "buy_and_hold",
        "dca_accumulation",
    }:
        return response
    repaired = response.model_copy(deep=True)
    repaired.requires_clarification = True
    repaired.assistant_response = None
    repaired.reason_codes = list(
        dict.fromkeys(
            [
                *response.reason_codes,
                "blocked_auto_simplification_for_ambiguous_rule",
            ]
        )
    )
    repaired.candidate_strategy_draft.strategy_type = None
    return repaired


def _response_has_ambiguous_rule_fields(response: LLMInterpretationResponse) -> bool:
    return any(
        field.field_name in {"entry_logic", "exit_logic"}
        for field in response.ambiguous_fields
    )


def _request_has_pending_date_answer_context(
    request: InterpretationRequest,
) -> bool:
    if request.selected_thread_metadata.get("last_stage_outcome") != (
        "await_user_reply"
    ):
        return False
    requested_field = _field_path_base(
        str(request.selected_thread_metadata.get("requested_field") or "")
    )
    if requested_field != "date_range":
        return False
    if not request.current_user_message.strip():
        return False
    return _request_has_active_strategy_context(request)


def _draft_complete_date_range_matches_current_turn_date_evidence(
    draft: LLMStrategyDraft,
    *,
    request: InterpretationRequest,
) -> bool:
    expected = _date_range_from_intent_or_bounded_evidence(
        draft,
        language=request.user.language_preference,
    )
    if expected is None:
        return False
    normalized = normalize_date_range_candidate(draft.date_range)
    if not isinstance(normalized, dict):
        return False
    if not _has_complete_date_range_payload(normalized):
        return False
    try:
        resolved = resolve_date_range(normalized)
    except Exception:
        resolved = None
    current = (
        resolved.payload
        if resolved is not None and not resolved.used_default
        else normalized
    )
    current_message_range = _date_range_from_current_turn_message(request)
    if current_message_range is not None:
        return _normalized_stated_field(current) == _normalized_stated_field(
            current_message_range
        )
    if not _date_range_intent_can_safely_suppress_focused_repair(draft):
        return False
    return _normalized_stated_field(current) == _normalized_stated_field(expected)


def _date_range_intent_can_safely_suppress_focused_repair(
    draft: LLMStrategyDraft,
) -> bool:
    intent = draft.date_range_intent
    if intent is None:
        return False
    if intent.kind != "calendar_year":
        return _draft_has_semantic_date_window_evidence(draft)
    if intent.year is None:
        return False
    evidence = str(intent.evidence or "").strip()
    return evidence == str(intent.year)


def _response_has_repairable_current_turn_date_gap(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    if not response.requires_clarification:
        return False
    draft = response.candidate_strategy_draft
    if not _llm_value_is_empty(draft.date_range):
        return False
    if canonical_strategy_type(draft.strategy_type) not in SUPPORTED_STRATEGY_TYPES:
        return False
    if not _llm_strategy_draft_has_concrete_execution_target(draft):
        return False
    return bool(
        request.current_user_message.strip()
        or draft.raw_user_phrasing
        or draft.strategy_thesis
    )


def _pending_supported_execution_date_answer_can_use_focused_audit(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    if response.semantic_turn_act != "answer_pending_need":
        return False
    if not _response_has_pending_base_field(response, "date_range"):
        return False
    if response.unsupported_constraints or response.ambiguous_fields:
        return False
    draft = response.candidate_strategy_draft
    if canonical_strategy_type(draft.strategy_type) not in SUPPORTED_STRATEGY_TYPES:
        return False
    if not _llm_strategy_draft_has_concrete_execution_target(draft):
        return False
    return bool(
        request.current_user_message.strip()
        or draft.raw_user_phrasing
        or draft.strategy_thesis
    )


def _draft_has_supported_capability_shape_for_date_repair(
    draft: LLMStrategyDraft,
) -> bool:
    strategy_type = executable_strategy_type(draft.model_dump(mode="python"))
    if strategy_type not in SUPPORTED_STRATEGY_TYPES:
        return False
    if not (draft.asset_universe or draft.asset_class):
        return False
    return any(
        [
            draft.capital_amount is not None,
            draft.total_capital is not None,
            draft.initial_capital is not None,
            draft.recurring_contribution is not None,
            bool(draft.timeframe),
            bool(draft.cadence),
            bool(draft.comparison_baseline),
            _llm_strategy_draft_has_rule_or_indicator_fields(draft),
            bool(draft.field_provenance),
            bool(_draft_semantic_evidence_spans(draft)),
        ]
    )


def _focused_date_window_extraction_messages(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You extract only the temporal constraint for an Argus backtest. "
                "The current user message may be in any language, shorthand, or "
                "messy prose. Return canonical machine fields, not user-facing "
                "copy. Do not decide strategy, asset, capital, support status, or "
                "whether to run. Do not infer a default window when the current "
                "message does not state one. Do not copy endpoint dates from the "
                "structured draft unless they are directly supported by the current "
                "user message. If the structured draft has a partial date_range "
                "whose start or end contains natural-language prose instead of an "
                "ISO date or today/current_date sentinel, treat that value only as "
                "non-executable evidence and re-extract the temporal intent from "
                "the current user message.\n\n"
                "For relative or semantic windows, do not calculate endpoint dates. "
                "A relative lookback anchored to the present is already a complete "
                "temporal constraint, even when the user does not provide calendar "
                "endpoint dates. If the current message states a lookback duration "
                "with a count and time unit in any language, set has_date_window=true "
                "and return date_range_intent kind=rolling_window with anchor=today. "
                "Do not ask for start/end dates just because the current message uses "
                "natural language. "
                "Return date_range_intent with kind=rolling_window, count, unit, "
                "anchor=today, confidence, and evidence. For year-to-date, return "
                "kind=year_to_date. For a calendar year, return kind=calendar_year "
                "and year. For since-style windows, return kind=since and start. "
                "For explicit calendar start/end endpoints, return date_range with "
                "ISO dates or the canonical sentinel today/current_date. Never put "
                "prose or shorthand relative windows inside date_range start/end. "
                "If no temporal window is present, has_date_window=false."
            ),
        },
        {
            "role": "system",
            "content": (
                "Structured draft JSON that may contain drifted dates: "
                f"{response.candidate_strategy_draft.model_dump(mode='json')}"
            ),
        },
        {"role": "user", "content": request.current_user_message},
    ]


def _response_from_focused_date_window_extraction(
    *,
    response: LLMInterpretationResponse,
    extraction: FocusedDateWindowExtraction,
    request: InterpretationRequest,
) -> LLMInterpretationResponse | None:
    if not extraction.has_date_window or extraction.confidence < 0.65:
        return None
    repaired = response.model_copy(deep=True)
    draft = repaired.candidate_strategy_draft
    raw_text = (
        str(extraction.date_range_raw_text or "").strip()
        or str(extraction.evidence or "").strip()
    )
    changed = False
    if extraction.date_range_intent is not None:
        intent_resolution = resolve_date_range_intent(extraction.date_range_intent)
        if intent_resolution is None:
            return None
        draft.date_range_intent = extraction.date_range_intent
        draft.date_range = intent_resolution.payload
        changed = True
    elif extraction.date_range is not None:
        normalized_date_range = normalize_date_range_candidate(extraction.date_range)
        if not _has_complete_date_range_payload(normalized_date_range):
            return None
        try:
            explicit_resolution = resolve_date_range(normalized_date_range)
        except Exception:
            return None
        if explicit_resolution.used_default:
            return None
        draft.date_range = explicit_resolution.payload
        changed = True
    if not changed:
        return None
    pending_date_answer = _request_has_pending_date_answer_context(request)
    if raw_text:
        draft.date_range_raw_text = raw_text
        draft.evidence_spans = {
            **dict(draft.evidence_spans or {}),
            "date_range": raw_text,
        }
    if not has_partial_explicit_date_range(draft.date_range):
        repaired.missing_required_fields = [
            field
            for field in repaired.missing_required_fields
            if _field_path_base(field) != "date_range"
        ]
        repaired.ambiguous_fields = [
            field
            for field in repaired.ambiguous_fields
            if _field_path_base(field.field_name) != "date_range"
        ]
    if (
        pending_date_answer
        and not repaired.missing_required_fields
        and not repaired.ambiguous_fields
        and not repaired.unsupported_constraints
    ):
        repaired.requires_clarification = False
        repaired.assistant_response = None
        repaired.intent = "backtest_execution"
        repaired.task_relation = "continue"
        repaired.semantic_turn_act = "answer_pending_need"
        repaired.result_followup_focus = None
        repaired.capability_question_focus = None
        repaired.context_question_focus = None
        repaired.artifact_target = "active_confirmation"
    elif (
        repaired.requires_clarification
        and not repaired.missing_required_fields
        and not repaired.ambiguous_fields
        and not repaired.unsupported_constraints
        and _llm_strategy_draft_has_concrete_execution_target(draft)
    ):
        repaired.requires_clarification = False
        repaired.assistant_response = None
        repaired.intent = "backtest_execution"
    repaired.reason_codes = list(
        dict.fromkeys(
            [
                *repaired.reason_codes,
                "focused_date_window_intent_repair",
                *(
                    ["pending_date_answer_focused_window_repair"]
                    if pending_date_answer
                    else []
                ),
            ]
        )
    )
    return repaired
