"""Temporal/date-window repair and focused-date-window extraction helpers.

Behavior-preserving relocation from llm_interpreter.py (issue #131)."""

from __future__ import annotations

from typing import Any

from loguru import logger

from argus.agent_runtime.interpreter.artifact_assumption_edit import (
    _request_targets_post_result_artifact_edit,
)
from argus.agent_runtime.interpreter.draft_shape import (
    _request_has_active_strategy_context,
)
from argus.agent_runtime.interpreter.run_field_audits import (
    _response_has_pending_base_field,
)
from argus.agent_runtime.interpreter.shared import (
    _date_range_from_intent_or_bounded_evidence,
    _date_window_intent_bound_to_latest_result,
    _draft_has_semantic_date_window_evidence,
    _draft_semantic_evidence_spans,
    _field_path_base,
    _has_complete_date_range_payload,
    _latest_result_date_window,
    _llm_strategy_draft_has_concrete_execution_target,
    _llm_strategy_draft_has_rule_or_indicator_fields,
    _llm_value_is_empty,
    _natural_time_language_candidates_from_hints,
    _normalized_stated_field,
)
from argus.agent_runtime.llm_interpreter_types import (
    FocusedDateWindowExtraction,
    LLMDateRangeIntent,
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
    has_relative_window = _current_turn_has_relative_window_evidence(request)
    current_message_range = _date_range_from_current_turn_message(request)
    if (
        current_message_range is not None
        and isinstance(draft.date_range, dict)
        and not has_partial_explicit_date_range(draft.date_range)
        and _normalized_stated_field(draft.date_range)
        != _normalized_stated_field(current_message_range)
        and (
            "runtime_date_range_normalization" not in response.reason_codes
            or has_relative_window
        )
    ):
        return True
    if has_relative_window:
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
    # A calendar-year intent is only trustworthy when its evidence is the bare
    # year the user actually stated; anything else (or no evidence) means the
    # window needs the focused re-extraction.
    if (
        isinstance(draft.date_range, dict)
        and not has_partial_explicit_date_range(draft.date_range)
        and draft.date_range_intent is not None
        and draft.date_range_intent.kind == "calendar_year"
        and not _date_range_intent_can_safely_suppress_focused_repair(draft)
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


def _post_result_dateless_execution_draft(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    """Post-result draft complete except the window.

    The focused extraction must get a chance to name the latest-result
    reference ("same time period") before the runtime asks the user for
    dates — binding silently is the approved behavior and the primary model
    under-reports the typed reference.
    """

    if not _request_targets_post_result_artifact_edit(request):
        return False
    draft = response.candidate_strategy_draft
    if not _llm_value_is_empty(draft.date_range):
        return False
    if draft.date_range_intent is not None:
        return False
    if str(draft.date_range_raw_text or "").strip():
        return False
    return _llm_strategy_draft_has_concrete_execution_target(draft)


def _response_with_post_result_window_inherited(
    response: LLMInterpretationResponse,
    *,
    request: InterpretationRequest,
) -> LLMInterpretationResponse:
    """Inherit the completed run's window for a dateless post-result variant.

    Founder-approved continuity: a new idea or refinement right after a
    result that names no window borrows the run's window silently — the card
    shows it and stays editable. Binding by state (completed run + dateless
    executable draft) needs no model cooperation and no text matching, so
    prose proposals and bare "yes" turns can never loop.
    """

    if response.semantic_turn_act not in {"new_idea", "refine_current_idea"}:
        return response
    if not _post_result_dateless_execution_draft(
        response=response,
        request=request,
    ):
        return response
    window = _latest_result_date_window(request)
    if window is None:
        return response
    logger.debug(
        "Post-result window inherited start={} end={}",
        window["start"],
        window["end"],
    )
    draft = response.candidate_strategy_draft.model_copy(
        update={
            "date_range": dict(window),
            "date_range_intent": LLMDateRangeIntent(
                kind="explicit_range",
                start=window["start"],
                end=window["end"],
                confidence=0.8,
                evidence="latest completed result window",
            ),
        }
    )
    missing_required_fields = [
        field
        for field in response.missing_required_fields
        if _field_path_base(field) != "date_range"
    ]
    return response.model_copy(
        update={
            "candidate_strategy_draft": draft,
            "missing_required_fields": missing_required_fields,
            "reason_codes": list(
                dict.fromkeys(
                    [*response.reason_codes, "latest_result_window_bound"]
                )
            ),
        }
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


def _draft_with_pending_strategy_gaps_filled(
    draft: LLMStrategyDraft,
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> LLMStrategyDraft:
    """Fill a pending-answer patch draft from the pending strategy.

    A date answer only names the window; the assets, cadence, and sizing
    already live on the pending strategy. Without them the draft cannot pass
    required-shape checks and the runtime would re-ask, which is the repeated
    confirmation loop from issue #141.
    """

    if response.semantic_turn_act != "answer_pending_need":
        return draft
    snapshot = request.latest_task_snapshot
    pending = snapshot.pending_strategy_summary if snapshot is not None else None
    if pending is None:
        return draft
    updates: dict[str, Any] = {}
    provenance = dict(draft.field_provenance or {})
    if not draft.asset_universe and pending.asset_universe:
        updates["asset_universe"] = list(pending.asset_universe)
        provenance.setdefault("asset_universe", "prior_strategy_state")
    if not draft.asset_class and pending.asset_class:
        updates["asset_class"] = pending.asset_class
    if not draft.strategy_type and pending.strategy_type:
        updates["strategy_type"] = pending.strategy_type
    if not draft.strategy_thesis and pending.strategy_thesis:
        updates["strategy_thesis"] = pending.strategy_thesis
    if not draft.cadence and pending.cadence:
        updates["cadence"] = pending.cadence
    if draft.capital_amount is None and pending.capital_amount is not None:
        updates["capital_amount"] = pending.capital_amount
        provenance.setdefault("capital_amount", "prior_strategy_state")
    pending_contribution = pending.extra_parameters.get("recurring_contribution")
    if (
        draft.recurring_contribution is None
        and isinstance(pending_contribution, (int, float))
        and not isinstance(pending_contribution, bool)
    ):
        updates["recurring_contribution"] = float(pending_contribution)
        provenance.setdefault("recurring_contribution", "prior_strategy_state")
    if not updates:
        return draft
    if provenance != (draft.field_provenance or {}):
        updates["field_provenance"] = provenance
    return draft.model_copy(update=updates)


def _response_with_latest_result_window_bound(
    response: LLMInterpretationResponse,
    *,
    request: InterpretationRequest,
) -> LLMInterpretationResponse:
    """Bind a same_as_latest_result date intent to the canonical run window.

    The interpreter names the reference ("same time period"); only the
    canonical latest completed result owns the dates. Without a completed
    result the intent stays unresolved and the normal date clarification
    applies.
    """

    draft = response.candidate_strategy_draft
    intent = draft.date_range_intent
    if intent is None or intent.kind != "same_as_latest_result":
        return response
    window = _latest_result_date_window(request)
    if window is None:
        logger.debug(
            "Latest result window binding skipped: reference named but no "
            "canonical window available has_snapshot={} has_reference={}",
            request.latest_task_snapshot is not None,
            request.latest_task_snapshot is not None
            and request.latest_task_snapshot.latest_backtest_result_reference
            is not None,
        )
        return response
    logger.debug(
        "Latest result window bound start={} end={}",
        window["start"],
        window["end"],
    )
    bound_draft = draft.model_copy(
        update={
            "date_range": dict(window),
            "date_range_intent": _date_window_intent_bound_to_latest_result(
                intent,
                latest_result_window=window,
            ),
        }
    )
    bound_draft = _draft_with_pending_strategy_gaps_filled(
        bound_draft,
        response=response,
        request=request,
    )
    missing_required_fields = [
        field
        for field in response.missing_required_fields
        if _field_path_base(field) != "date_range"
    ]
    return response.model_copy(
        update={
            "candidate_strategy_draft": bound_draft,
            "missing_required_fields": missing_required_fields,
            "reason_codes": list(
                dict.fromkeys(
                    [*response.reason_codes, "latest_result_window_bound"]
                )
            ),
        }
    )


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


def _response_has_repairable_recovery_date_gap(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    """A recovery/unsupported draft dropped the user's stated date window.

    The model refused the idea but omitted the date the user gave; the focused
    re-extraction recovers it so the recovery clarification keeps the window
    instead of nulling it (never null, never a silent trailing-year default).
    """

    if response.intent != "unsupported_or_out_of_scope":
        return False
    if response.semantic_turn_act != "unsupported_request":
        return False
    # A strategy-shape gap belongs to the strategy repair, which runs earlier in
    # the readiness pipeline; only a date-only gap is recoverable here.
    if any(
        _field_path_base(field) != "date_range"
        for field in response.missing_required_fields
    ):
        return False
    draft = response.candidate_strategy_draft
    if not _llm_value_is_empty(draft.date_range):
        return False
    if draft.date_range_intent is not None:
        return False
    if not (draft.asset_universe or draft.asset_class):
        return False
    return bool(request.current_user_message.strip())


def _complete_date_range_matches_resolved_intent(draft: LLMStrategyDraft) -> bool:
    normalized = normalize_date_range_candidate(draft.date_range)
    if not (
        isinstance(normalized, dict)
        and _has_complete_date_range_payload(normalized)
    ):
        return False
    resolved = resolve_date_range_intent(draft.date_range_intent)
    if resolved is None:
        return False
    return _normalized_stated_field(normalized) == _normalized_stated_field(
        resolved.payload
    )


def _complete_date_range_needs_current_turn_date_audit(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
    has_complete_date_range: bool,
    has_material_execution_evidence: bool,
) -> bool:
    if not has_complete_date_range:
        return False
    if not has_material_execution_evidence:
        return False
    draft = response.candidate_strategy_draft
    if canonical_strategy_type(draft.strategy_type) not in SUPPORTED_STRATEGY_TYPES:
        return False
    if not _llm_strategy_draft_has_concrete_execution_target(draft):
        return False
    has_semantic_date_evidence = _draft_has_semantic_date_window_evidence(draft)
    if has_semantic_date_evidence:
        return False
    if _draft_complete_date_range_matches_current_turn_date_evidence(
        draft,
        request=request,
    ):
        return False
    if _complete_date_range_matches_resolved_intent(draft):
        return False
    if resolve_date_range_intent(draft.date_range_intent) is not None:
        return True
    return True


def response_with_recovery_intent_window_materialized(
    response: LLMInterpretationResponse,
) -> LLMInterpretationResponse:
    """Materialize a refusal draft's typed date_range_intent into date_range.

    The refusal keeps the user's stated window from the typed intent alone (no
    text re-scan); an unresolvable intent stays empty for clarification, never a
    trailing default.
    """

    if response.intent != "unsupported_or_out_of_scope":
        return response
    draft = response.candidate_strategy_draft
    if not _llm_value_is_empty(draft.date_range):
        return response
    intent = draft.date_range_intent
    if intent is None or str(intent.kind or "") == "same_as_latest_result":
        return response
    intent_resolution = resolve_date_range_intent(intent)
    if intent_resolution is None:
        return response
    repaired = response.model_copy(deep=True)
    repaired.candidate_strategy_draft.date_range = intent_resolution.payload
    repaired.reason_codes = list(
        dict.fromkeys(
            [*repaired.reason_codes, "recovery_intent_window_materialized"]
        )
    )
    return repaired


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
                "When the current message reuses the previous or latest test's "
                "window ('same time period', 'mismo periodo', 'the same period as "
                "the test we just ran', any language), set has_date_window=true "
                "and return kind=same_as_latest_result with the reference phrase "
                "as evidence and no start/end; the runtime binds the dates from "
                "the canonical result. "
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
        if str(extraction.date_range_intent.kind or "") == "same_as_latest_result":
            window = _latest_result_date_window(request)
            if window is None:
                return None
            draft.date_range_intent = _date_window_intent_bound_to_latest_result(
                extraction.date_range_intent,
                latest_result_window=window,
            )
            draft.date_range = dict(window)
            changed = True
        else:
            intent_resolution = resolve_date_range_intent(
                extraction.date_range_intent
            )
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
    # A constraint-less refusal only recovers its dropped window — never the pending
    # draft, never a promotion; a constraint-carrying refusal mid date-answer is
    # stale context the pending answer may override.
    refused_turn = (
        response.intent == "unsupported_or_out_of_scope"
        and not response.unsupported_constraints
    )
    if raw_text:
        draft.date_range_raw_text = raw_text
        draft.evidence_spans = {
            **dict(draft.evidence_spans or {}),
            "date_range": raw_text,
        }
    if pending_date_answer and not refused_turn:
        supported_pending_draft = _supported_pending_strategy_draft_for_date_answer(
            request
        )
        if supported_pending_draft is not None:
            supported_pending_draft.date_range = draft.date_range
            supported_pending_draft.date_range_intent = draft.date_range_intent
            supported_pending_draft.date_range_raw_text = draft.date_range_raw_text
            supported_pending_draft.evidence_spans = {
                **dict(supported_pending_draft.evidence_spans or {}),
                **dict(draft.evidence_spans or {}),
            }
            repaired.candidate_strategy_draft = supported_pending_draft
            repaired.unsupported_constraints = []
            repaired.ambiguous_fields = []
            draft = repaired.candidate_strategy_draft
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
        and not refused_turn
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
        and not refused_turn
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


def _supported_pending_strategy_draft_for_date_answer(
    request: InterpretationRequest,
) -> LLMStrategyDraft | None:
    snapshot = request.latest_task_snapshot
    if snapshot is None:
        return None
    pending_strategy = (
        snapshot.pending_strategy_summary or snapshot.confirmed_strategy_summary
    )
    if pending_strategy is None:
        return None
    strategy_type = canonical_strategy_type(pending_strategy.strategy_type)
    if strategy_type not in SUPPORTED_STRATEGY_TYPES:
        return None
    payload = pending_strategy.model_dump(mode="python")
    draft_fields = set(LLMStrategyDraft.model_fields)
    draft_payload = {
        key: value
        for key, value in payload.items()
        if key in draft_fields and value not in (None, "", [], {})
    }
    draft_payload["strategy_type"] = strategy_type
    return LLMStrategyDraft.model_validate(draft_payload)
