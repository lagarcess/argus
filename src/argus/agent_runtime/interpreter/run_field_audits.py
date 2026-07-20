"""Stated-run-field fidelity, capability-conflict, and latest-result-routing audit helpers.

Behavior-preserving relocation from llm_interpreter.py (issue #131)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date
from typing import Any

from argus.agent_runtime.interpreter.audits import StatedRunFieldFidelityAudit
from argus.agent_runtime.interpreter.dca_audits import (
    _capability_required_missing_fields_for_canonical_strategy,
)
from argus.agent_runtime.interpreter.draft_shape import (
    _llm_strategy_draft_has_executable_shape,
    _request_has_latest_result,
)
from argus.agent_runtime.interpreter.executable_grounding import (
    _draft_has_non_executable_timeframe_label,
)
from argus.agent_runtime.interpreter.shared import (
    _bounded_date_evidence_candidates,
    _date_range_from_bounded_evidence,
    _date_range_from_intent_or_bounded_evidence,
    _date_range_with_fidelity_audit,
    _draft_has_comparison_baseline_evidence,
    _draft_has_semantic_date_window_evidence,
    _draft_semantic_evidence_spans,
    _field_path_base,
    _has_complete_date_range_payload,
    _llm_strategy_draft_has_concrete_execution_target,
    _llm_strategy_draft_has_extractable_fields,
    _llm_strategy_draft_has_rule_or_indicator_fields,
    _llm_value_is_empty,
    _normalized_stated_field,
    _supported_dca_cadence_value,
)
from argus.agent_runtime.interpreter.signal_rule import (
    _asset_recovery_query_is_explicit_ticker,
)
from argus.agent_runtime.interpreter.unsupported_admission import (
    CAPABILITY_CONFLICT_KEEP_DIRECTION_PROMPT,
    inverse_capability_conflict_messages,
    inverse_promotion_reason_codes,
    response_has_only_unsupported_strategy_logic_constraints,
    response_needs_inverse_capability_conflict_audit,
)
from argus.agent_runtime.llm_interpreter_types import (
    LLMInterpretationResponse,
    LLMStrategyDraft,
)
from argus.agent_runtime.result_followups import result_followup_fact_bank
from argus.agent_runtime.run_field_contract import (
    field_fidelity_tokens as _field_fidelity_tokens,
)
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.strategy_contract import (
    SUPPORTED_STRATEGY_TYPES,
    canonical_strategy_type,
    has_partial_explicit_date_range,
    normalize_date_range_candidate,
    resolve_date_range,
)
from argus.nlp.natural_time import resolve_date_range_intent


def _structured_supported_strategy_capability_conflict_fallback(
    response: LLMInterpretationResponse,
) -> LLMInterpretationResponse | None:
    if not _response_needs_supported_strategy_capability_conflict_audit(response):
        return None
    if not response_has_only_unsupported_strategy_logic_constraints(response):
        return None
    draft = response.candidate_strategy_draft
    strategy_type = canonical_strategy_type(draft.strategy_type)
    if strategy_type not in {"buy_and_hold", "dca_accumulation"}:
        return None
    if _llm_strategy_draft_has_rule_or_indicator_fields(draft):
        return None
    if not (draft.asset_universe or draft.asset_class):
        return None
    if strategy_type == "buy_and_hold" and not (
        draft.date_range
        or _draft_has_semantic_date_window_evidence(draft)
        or resolve_date_range_intent(draft.date_range_intent) is not None
    ):
        return None
    if strategy_type == "dca_accumulation" and not (
        draft.recurring_contribution is not None
        or draft.capital_amount is not None
        or draft.total_capital is not None
        or draft.initial_capital is not None
    ):
        return None
    repaired = _response_with_supported_strategy_capability_conflict_removed(
        response=response,
        strategy_type=strategy_type,
    )
    repaired.reason_codes = list(
        dict.fromkeys(
            [
                code
                for code in repaired.reason_codes
                if code != "supported_strategy_capability_conflict_audit"
            ]
            + ["supported_strategy_capability_structured_fallback"]
        )
    )
    return repaired


def _response_needs_supported_strategy_capability_conflict_audit(
    response: LLMInterpretationResponse,
) -> bool:
    if response.intent not in {
        "strategy_drafting",
        "backtest_execution",
        "unsupported_or_out_of_scope",
    }:
        return False
    has_unsupported_strategy_logic = any(
        item.category == "unsupported_strategy_logic"
        for item in response.unsupported_constraints
    )
    if response.capability_question_focus is not None and (
        not has_unsupported_strategy_logic
    ):
        return False
    if not has_unsupported_strategy_logic:
        return response_needs_inverse_capability_conflict_audit(response)
    draft = response.candidate_strategy_draft
    if canonical_strategy_type(draft.strategy_type) in {
        "buy_and_hold",
        "dca_accumulation",
    }:
        return True
    if response.semantic_turn_act != "unsupported_request":
        return False
    if _llm_value_is_empty(draft.strategy_type) and _llm_value_is_empty(
        draft.strategy_thesis
    ):
        return False
    if _llm_strategy_draft_has_rule_or_indicator_fields(draft):
        return _llm_strategy_draft_has_concrete_execution_target(draft)
    return _llm_strategy_draft_has_concrete_execution_target(draft)


def _supported_strategy_capability_conflict_messages(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> list[dict[str, str]]:
    if response_needs_inverse_capability_conflict_audit(response):
        return inverse_capability_conflict_messages(response=response, request=request)
    constraints = [
        item.model_dump(mode="json")
        for item in response.unsupported_constraints
        if item.category == "unsupported_strategy_logic"
    ]
    return [
        {
            "role": "system",
            "content": CAPABILITY_CONFLICT_KEEP_DIRECTION_PROMPT,
        },
        {
            "role": "system",
            "content": (
                "Structured draft JSON: "
                f"{response.candidate_strategy_draft.model_dump(mode='json')}"
            ),
        },
        {
            "role": "system",
            "content": (
                "Unsupported strategy constraints JSON: "
                f"{json.dumps(constraints, ensure_ascii=False)}"
            ),
        },
        {"role": "user", "content": request.current_user_message},
    ]


def _response_with_supported_strategy_capability_conflict_removed(
    *,
    response: LLMInterpretationResponse,
    strategy_type: str,
) -> LLMInterpretationResponse:
    repaired = response.model_copy(deep=True)
    repaired.candidate_strategy_draft.strategy_type = strategy_type
    if strategy_type in {"buy_and_hold", "dca_accumulation"}:
        _clear_rule_or_indicator_fields(repaired.candidate_strategy_draft)
    repaired.unsupported_constraints = [
        item
        for item in repaired.unsupported_constraints
        if item.category != "unsupported_strategy_logic"
    ]
    repaired.missing_required_fields = (
        _capability_required_missing_fields_for_canonical_strategy(
            repaired.missing_required_fields,
            draft=repaired.candidate_strategy_draft,
        )
    )
    repaired.intent = "strategy_drafting"
    repaired.semantic_turn_act = "new_idea"
    repaired.requires_clarification = bool(
        repaired.missing_required_fields
        or repaired.ambiguous_fields
        or repaired.unsupported_constraints
    )
    repaired.assistant_response = None
    repaired.reason_codes = list(
        dict.fromkeys(
            [
                *repaired.reason_codes,
                "supported_strategy_capability_conflict_audit",
                *inverse_promotion_reason_codes(response),
            ]
        )
    )
    repaired.capability_question_focus = None
    if (
        not repaired.unsupported_constraints
        and not repaired.ambiguous_fields
        and not repaired.missing_required_fields
        and _llm_strategy_draft_has_concrete_execution_target(
            repaired.candidate_strategy_draft
        )
    ):
        repaired.intent = "backtest_execution"
        repaired.requires_clarification = False
        repaired.assistant_response = None
        repaired.semantic_turn_act = "new_idea"
    return repaired


def _clear_rule_or_indicator_fields(draft: LLMStrategyDraft) -> None:
    draft.entry_logic = None
    draft.exit_logic = None
    draft.entry_rule = None
    draft.exit_rule = None
    draft.rule_spec = None
    draft.indicator = None
    draft.indicator_period = None
    draft.entry_threshold = None
    draft.exit_threshold = None


def _response_with_executable_fields_preferred_over_clarification_prose(
    response: LLMInterpretationResponse,
) -> LLMInterpretationResponse:
    # An unsupported verdict on either typed field is not clarification noise;
    # only the inverse capability audit may normalize it into a supported run.
    draft = response.candidate_strategy_draft
    if not (
        response.requires_clarification
        and response.assistant_response
        and response.intent
        in {
            "strategy_drafting",
            "backtest_execution",
        }
        and response.semantic_turn_act
        not in {
            "answer_pending_need",
            "approval",
            "educational_question",
            "refine_current_idea",
            "result_followup",
            "retry_failed_action",
            "unsupported_request",
        }
        and response.capability_question_focus is None
        and response.context_question_focus is None
        and not response.unsupported_constraints
        and not response.ambiguous_fields
        and not response.missing_required_fields
        and canonical_strategy_type(draft.strategy_type)
        in {"buy_and_hold", "dca_accumulation"}
        and not _llm_strategy_draft_has_rule_or_indicator_fields(draft)
        and _llm_strategy_draft_has_executable_shape(draft)
        and not has_partial_explicit_date_range(draft.date_range)
    ):
        return response
    return response.model_copy(
        update={
            "intent": "backtest_execution",
            "requires_clarification": False,
            "assistant_response": None,
            "semantic_turn_act": "new_idea",
            "reason_codes": list(
                dict.fromkeys(
                    [
                        *response.reason_codes,
                        "executable_fields_overrode_clarification_prose",
                    ]
                )
            ),
        }
    )


def _response_from_current_message_run_field_contract(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> LLMInterpretationResponse | None:
    """Preserve obvious run facts from the current turn when audit models omit them."""

    repaired = response.model_copy(deep=True)
    draft = repaired.candidate_strategy_draft
    current_message = request.current_user_message
    changed = False

    date_range = _date_range_from_intent_or_bounded_evidence(
        draft,
        language=request.user.language_preference,
    )
    if date_range is None:
        return None
    if (
        date_range is not None
        and (
            _draft_date_range_needs_stated_run_field_audit(
                draft,
                current_message=current_message,
            )
            or _response_needs_current_message_date_repair(
                response=repaired,
                current_message=current_message,
                language=request.user.language_preference,
            )
        )
    ):
        draft.date_range = date_range
        if _draft_has_non_executable_timeframe_label(draft):
            draft.timeframe = None
        if has_partial_explicit_date_range(date_range):
            repaired.requires_clarification = True
            repaired.assistant_response = None
            repaired.missing_required_fields = list(
                dict.fromkeys([*repaired.missing_required_fields, "date_range"])
            )
        else:
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
        changed = True

    if (
        changed
        and repaired.requires_clarification
        and not has_partial_explicit_date_range(draft.date_range)
        and not repaired.missing_required_fields
        and not repaired.ambiguous_fields
        and not repaired.unsupported_constraints
        and _llm_strategy_draft_has_concrete_execution_target(draft)
    ):
        repaired.requires_clarification = False
        repaired.assistant_response = None
    if (
        changed
        and not repaired.requires_clarification
        and not repaired.missing_required_fields
        and not repaired.ambiguous_fields
        and not repaired.unsupported_constraints
        and _llm_strategy_draft_has_concrete_execution_target(draft)
    ):
        repaired.intent = "backtest_execution"
        repaired.semantic_turn_act = "new_idea"

    if not changed:
        return None
    repaired.reason_codes = list(
        dict.fromkeys(
            [
                *repaired.reason_codes,
                "current_message_run_field_contract_repair",
            ]
        )
    )
    return repaired


def _response_with_resolved_runtime_date_range(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> LLMInterpretationResponse:
    date_range = _resolved_runtime_date_range_from_draft(
        response.candidate_strategy_draft,
        request=request,
    )
    if date_range is None:
        return response
    draft = response.candidate_strategy_draft
    if _normalized_stated_field(draft.date_range) == _normalized_stated_field(
        date_range
    ):
        return response
    repaired = response.model_copy(deep=True)
    repaired.candidate_strategy_draft.date_range = date_range
    if not has_partial_explicit_date_range(date_range):
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
        repaired.requires_clarification
        and not has_partial_explicit_date_range(date_range)
        and not repaired.missing_required_fields
        and not repaired.ambiguous_fields
        and not repaired.unsupported_constraints
        and _llm_strategy_draft_has_concrete_execution_target(
            repaired.candidate_strategy_draft
        )
    ):
        repaired.requires_clarification = False
        repaired.assistant_response = None
    repaired.reason_codes = list(
        dict.fromkeys(
            [
                *repaired.reason_codes,
                "runtime_date_range_normalization",
            ]
        )
    )
    return repaired


def _resolved_runtime_date_range_from_draft(
    draft: LLMStrategyDraft,
    *,
    request: InterpretationRequest,
) -> dict[str, str] | None:
    normalized = normalize_date_range_candidate(draft.date_range)
    if isinstance(normalized, dict) and _has_complete_date_range_payload(normalized):
        try:
            resolved = resolve_date_range(normalized)
        except Exception:
            resolved = None
        if resolved is not None and not resolved.used_default:
            current_message_range = (
                _runtime_date_range_from_current_message_or_draft_evidence(
                    draft,
                    request=request,
                )
            )
            if (
                current_message_range is not None
                and _normalized_stated_field(resolved.payload)
                != _normalized_stated_field(current_message_range)
            ):
                return current_message_range
            return resolved.payload
    return _date_range_from_intent_or_bounded_evidence(
        draft,
        language=request.user.language_preference,
    )


def _runtime_date_range_from_current_message_or_draft_evidence(
    draft: LLMStrategyDraft,
    *,
    request: InterpretationRequest,
) -> dict[str, str] | None:
    bounded = _date_range_from_bounded_evidence(
        draft,
        language=request.user.language_preference,
    )
    if bounded is not None:
        return bounded
    if not _date_range_intent_evidence_matches_current_message(draft, request=request):
        return None
    resolved = resolve_date_range_intent(draft.date_range_intent)
    if resolved is None:
        return None
    return resolved.payload


def _date_range_intent_evidence_matches_current_message(
    draft: LLMStrategyDraft,
    *,
    request: InterpretationRequest,
) -> bool:
    evidence = str(getattr(draft.date_range_intent, "evidence", "") or "").strip()
    if not evidence:
        return False
    evidence_text = evidence.casefold()
    current_message = request.current_user_message.casefold()
    if evidence_text in current_message:
        return True
    for candidate in _bounded_date_evidence_candidates(draft):
        candidate_text = str(candidate or "").strip().casefold()
        if candidate_text and (
            evidence_text in candidate_text or candidate_text in evidence_text
        ):
            return True
    return False


def _pending_dca_assumption_reply_needs_stated_run_field_audit(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest | None,
) -> bool:
    if request is None or response.semantic_turn_act != "answer_pending_need":
        return False
    requested_field = _field_path_base(
        request.selected_thread_metadata.get("requested_field")
    )
    if requested_field != "assumption":
        return False
    return canonical_strategy_type(
        response.candidate_strategy_draft.strategy_type
    ) == "dca_accumulation"


def _focused_repair_capital_needs_stated_run_field_audit(
    draft: LLMStrategyDraft,
    *,
    current_message: str,
) -> bool:
    if draft.capital_amount is not None:
        return False
    return _draft_capital_needs_stated_run_field_audit(
        draft,
        current_message=current_message,
    )


def _draft_capital_needs_stated_run_field_audit(
    draft: LLMStrategyDraft,
    *,
    current_message: str,
) -> bool:
    if canonical_strategy_type(draft.strategy_type) == "dca_accumulation":
        return False
    if not _draft_has_non_money_execution_anchor(draft):
        return False
    if _text_contains_capital_audit_signal(current_message, draft=draft):
        return True
    return draft.capital_amount is None and _draft_contains_structured_capital_context(draft)


def _explicit_benchmark_ticker_queries(message: str) -> list[str]:
    tokens = _field_fidelity_tokens(str(message or ""))
    queries: list[str] = []
    seen: set[str] = set()
    benchmark_cues = {"against", "vs", "versus", "contra"}
    for index, token in enumerate(tokens):
        candidate = token.strip().lstrip("$")
        if not candidate:
            continue
        compact = "".join(
            character
            for character in candidate
            if character.isalnum()
        )
        if len(compact) < 2 or not any(character.isalpha() for character in compact):
            continue
        previous = tokens[index - 1].strip().casefold() if index > 0 else ""
        is_cued_lowercase_ticker = (
            previous in benchmark_cues
            and candidate == candidate.lower()
            and len(compact) <= 5
        )
        if not (
            _asset_recovery_query_is_explicit_ticker(token)
            or is_cued_lowercase_ticker
        ):
            continue
        normalized = candidate.upper()
        if normalized in seen:
            continue
        seen.add(normalized)
        queries.append(candidate)
    return queries


def _response_needs_current_message_date_repair(
    *,
    response: LLMInterpretationResponse,
    current_message: str,
    language: str | None = None,
) -> bool:
    draft = response.candidate_strategy_draft
    if not _llm_value_is_empty(draft.date_range):
        return False
    del current_message
    if _date_range_from_intent_or_bounded_evidence(draft, language=language) is None:
        return False
    if _llm_strategy_draft_has_concrete_execution_target(draft):
        return True
    if _response_has_pending_base_field(response, "date_range"):
        return True
    return response.requires_clarification and _llm_strategy_draft_has_concrete_execution_target(
        draft
    )


def _response_needs_missing_benchmark_fidelity_audit(
    response: LLMInterpretationResponse,
) -> bool:
    draft = response.candidate_strategy_draft
    return (
        response.requires_clarification
        and not response.missing_required_fields
        and not response.ambiguous_fields
        and _llm_value_is_empty(draft.comparison_baseline)
        and _llm_strategy_draft_has_concrete_execution_target(draft)
    )


def _dca_response_needs_semantic_field_audit(
    response: LLMInterpretationResponse,
) -> bool:
    draft = response.candidate_strategy_draft
    if canonical_strategy_type(draft.strategy_type) != "dca_accumulation":
        return False
    field_provenance = dict(draft.field_provenance or {})
    amount_source = str(field_provenance.get("capital_amount") or "").strip()
    cadence_source = str(field_provenance.get("cadence") or "").strip()
    if draft.capital_amount is None or amount_source not in {
        "explicit_user",
        "prior",
        "recurring_contribution",
        "contribution_amount",
        "periodic_contribution",
        "dca_contribution",
    }:
        return True
    if draft.cadence in (None, "", [], {}) or cadence_source not in {
        "explicit_user",
        "prior",
        "visible_draft",
    }:
        return True
    return False


def _response_has_pending_base_field(
    response: LLMInterpretationResponse,
    field_name: str,
) -> bool:
    return any(
        _field_path_base(field) == field_name
        for field in response.missing_required_fields
    ) or any(
        _field_path_base(field.field_name) == field_name
        for field in response.ambiguous_fields
    )


def _draft_has_unprovenanced_benchmark(draft: LLMStrategyDraft) -> bool:
    if _llm_value_is_empty(draft.comparison_baseline):
        return False
    provenance = draft.field_provenance or {}
    return provenance.get("comparison_baseline") not in {
        "explicit_user",
        "stated_run_field_fidelity_audit",
    }


def _draft_date_range_needs_stated_run_field_audit(
    draft: LLMStrategyDraft,
    *,
    current_message: str = "",
) -> bool:
    if _llm_value_is_empty(draft.date_range):
        return False
    current_message_range = _date_range_from_intent_or_bounded_evidence(draft)
    if (
        current_message_range is not None
        and not has_partial_explicit_date_range(current_message_range)
        and isinstance(draft.date_range, dict)
        and not has_partial_explicit_date_range(draft.date_range)
        and _normalized_stated_field(draft.date_range)
        != _normalized_stated_field(current_message_range)
    ):
        return True
    if (
        current_message_range is None
        and _draft_date_range_has_unstated_current_endpoint(draft.date_range)
    ):
        return True
    if has_partial_explicit_date_range(draft.date_range):
        return current_message_range is not None and not has_partial_explicit_date_range(
            current_message_range
        )
    if isinstance(draft.date_range, str) and current_message_range is not None:
        normalized_range = draft.date_range.strip().casefold()
        return bool(normalized_range and normalized_range not in current_message.casefold())
    return False


def _draft_date_range_has_unstated_current_endpoint(
    date_range_value: Any,
) -> bool:
    if not isinstance(date_range_value, dict):
        return False
    for key in ("end", "to"):
        endpoint = date_range_value.get(key)
        if _date_endpoint_is_runtime_current(endpoint):
            return True
    return False


def _date_endpoint_is_runtime_current(value: Any) -> bool:
    if value in (None, "", [], {}):
        return False
    normalized = str(value).strip().casefold()
    return normalized in {
        "today",
        "now",
        "present",
        "current",
        "current_date",
        date.today().isoformat(),
    }


def _draft_contains_structured_capital_context(draft: LLMStrategyDraft) -> bool:
    text = _structured_draft_context_text(draft)
    if "$" in str(text or ""):
        return True
    non_capital_tokens = _draft_non_capital_numeric_evidence_tokens(draft)
    for token in _field_fidelity_tokens(str(text or "")):
        normalized = token.strip().casefold()
        if normalized in non_capital_tokens:
            continue
        if any(character.isdigit() for character in normalized) and any(
            character.isalpha() for character in normalized
        ):
            return True
    return False


def _draft_has_non_money_execution_anchor(draft: LLMStrategyDraft) -> bool:
    return any(
        [
            canonical_strategy_type(draft.strategy_type) in SUPPORTED_STRATEGY_TYPES,
            bool(draft.asset_universe),
            bool(draft.asset_class),
            bool(draft.date_range),
            draft.date_range_intent is not None,
            bool(draft.timeframe),
            bool(draft.cadence),
            bool(draft.comparison_baseline),
            _llm_strategy_draft_has_rule_or_indicator_fields(draft),
            _draft_has_semantic_date_window_evidence(draft),
            _draft_has_comparison_baseline_evidence(draft),
        ]
    )


def _text_contains_capital_audit_signal(
    text: str,
    *,
    draft: LLMStrategyDraft,
) -> bool:
    if "$" in str(text or ""):
        return True
    tokens = _field_fidelity_tokens(str(text or "").casefold())
    if not tokens:
        return False
    non_capital_tokens = _draft_non_capital_numeric_evidence_tokens(draft)
    return any(
        token not in non_capital_tokens
        and any(character.isdigit() for character in token)
        for token in tokens
    )


def _draft_non_capital_numeric_evidence_tokens(draft: LLMStrategyDraft) -> set[str]:
    tokens = set(_draft_date_evidence_tokens(draft))
    if not _llm_value_is_empty(draft.timeframe):
        tokens.update(_field_fidelity_tokens(str(draft.timeframe).casefold()))
    return tokens


def _draft_date_evidence_tokens(draft: LLMStrategyDraft) -> set[str]:
    candidates = list(_bounded_date_evidence_candidates(draft))
    date_range = normalize_date_range_candidate(draft.date_range)
    if isinstance(date_range, Mapping):
        candidates.extend(str(value) for value in date_range.values() if value)
    date_range_intent = draft.date_range_intent
    intent_evidence = getattr(date_range_intent, "evidence", None)
    if intent_evidence:
        candidates.append(str(intent_evidence))
    return {
        token
        for candidate in candidates
        for token in _date_evidence_tokens_from_text(candidate)
    }


def _date_evidence_tokens_from_text(value: Any) -> set[str]:
    text = str(value or "").casefold()
    tokens = set(_field_fidelity_tokens(text))
    for separator in ("-", "/"):
        if separator in text:
            tokens.update(_field_fidelity_tokens(text.replace(separator, " ")))
    return tokens


def _draft_has_timeframe_evidence_for_audit(draft: LLMStrategyDraft) -> bool:
    if not _llm_value_is_empty(draft.timeframe):
        return True
    evidence_spans = _draft_semantic_evidence_spans(draft)
    return not _llm_value_is_empty(evidence_spans.get("timeframe"))


def _structured_draft_context_text(
    draft: LLMStrategyDraft,
    *,
    extra_text: str = "",
) -> str:
    values = (
        extra_text,
        draft.raw_user_phrasing,
        draft.date_range_raw_text,
        draft.strategy_thesis,
        draft.entry_logic,
        draft.exit_logic,
        " ".join((draft.evidence_spans or {}).values()),
    )
    return " ".join(str(value) for value in values if value)


def _response_needs_latest_result_routing_audit(
    response: LLMInterpretationResponse,
    *,
    request: InterpretationRequest,
) -> bool:
    if not _request_has_latest_result(request):
        return False
    if response.semantic_turn_act == "result_followup":
        return True
    if response.intent == "results_explanation":
        return True
    if _llm_strategy_draft_has_executable_shape(response.candidate_strategy_draft):
        return True
    if _llm_strategy_draft_has_extractable_fields(response.candidate_strategy_draft):
        return True
    return bool(
        response.capability_question_focus is not None
        or (
            response.task_relation == "continue"
            and response.assistant_response is None
        )
    )


def _response_targets_latest_result_followup(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    return (
        _request_has_latest_result(request)
        and response.semantic_turn_act == "result_followup"
    )


def _latest_result_routing_audit_messages(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are Argus's post-result routing audit. Decide whether the "
                "current user message should be answered from the latest completed "
                "result artifact or as a general product/capability question. "
                "Choose targets_latest_result=true for questions about what "
                "happened, what was tested, assumptions in the run, drawdown, "
                "benchmark comparison, or what experiment to try next from the "
                "latest result. Choose false for new investing ideas, beginner "
                "education, and direct questions about Argus capabilities that do "
                "not depend on the latest result. If the primary interpreter copied "
                "symbols, dates, timeframe, or strategy labels out of the latest "
                "result but did not produce a new executable rule, treat that as "
                "latest-result context rather than a new strategy. Short anaphoric "
                "questions such as 'what date did this peak?', 'when did this peak?', "
                "'what was the peak value?', 'when was the worst drawdown?', "
                "'cuándo alcanzó el máximo?', or 'cuál fue la caída máxima?' target "
                "the latest result when a latest result exists, even if the primary "
                "interpreter filled strategy fields from prior context. Set "
                "save_requested=true when the user is asking to save, keep, "
                "bookmark, or promote the latest completed result artifact. "
                "Examples that must set save_requested=true when a latest result "
                "exists: 'save this', 'save this result', 'keep this', "
                "'bookmark this run', 'save that strategy from the result'. Use "
                "focus=peak_date and fact_key=peak_date for questions asking when "
                "the portfolio value peaked. Use focus=peak_value and "
                "fact_key=peak_value for questions asking what the highest portfolio "
                "value was. Use focus=drawdown_date and fact_key=drawdown_date for "
                "questions asking when the largest drawdown bottomed. Use "
                "focus=max_drawdown and fact_key=max_drawdown for questions asking "
                "how large the drawdown was. Use focus=result_card_fact and set "
                "fact_key to the canonical metric name for other factual values, "
                "including execution-cost facts such as fee_bps, slippage_bps, "
                "gross_total_return, net_total_return, return_drag, and "
                "benchmark_cost_treatment. Keep unsupported metrics like "
                "sortino_ratio unsupported. Use why_underperformed for questions that ask why a result matched, "
                "beat, lagged, or compared with its benchmark; use what_tested only "
                "when the user is asking for the run setup itself."
            ),
        },
        {
            "role": "system",
            "content": (
                "Latest result fact bank JSON: "
                + json.dumps(_latest_result_fact_bank_for_routing(request))
            ),
        },
        {
            "role": "system",
            "content": (
                "Primary interpreter decision JSON: " + response.model_dump_json()
            ),
        },
        {"role": "user", "content": request.current_user_message},
    ]


def _latest_result_fact_bank_for_routing(
    request: InterpretationRequest,
) -> dict[str, str]:
    snapshot = request.latest_task_snapshot
    if snapshot is None or snapshot.latest_backtest_result_reference is None:
        return {}
    metadata = dict(snapshot.latest_backtest_result_reference.metadata)
    fact_bank = result_followup_fact_bank(metadata)
    return {
        key: fact_bank[key]
        for key in (
            "symbols",
            "strategy",
            "date_range",
            "total_return",
            "benchmark_symbol",
            "benchmark_return",
            "benchmark_delta",
            "max_drawdown",
            "fee_bps",
            "slippage_bps",
            "gross_total_return",
            "net_total_return",
            "return_drag",
            "benchmark_cost_treatment",
            "runnable_next_tests",
        )
        if key in fact_bank
    }


def _stated_run_field_fidelity_messages(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are Argus's run-field fidelity audit. Compare the current "
                "user message with the structured draft and return only run fields "
                "the user explicitly stated but the draft may have dropped or "
                "reshaped. Do not infer defaults, fees, slippage, symbols, or rules. "
                "If a field is absent from the current user message, return null "
                "for that field. Normalize starting capital exactly from the "
                "current message: 10k -> 10000, 100K -> 100000, $10,000 "
                "-> 10000, 100k -> 100000, and a plain number such as "
                "100000 -> 100000 when the message uses it as the amount to "
                "test, invest, allocate, put on, or use as capital. This is "
                "language-agnostic: preserve bare numeric amounts and numeric "
                "magnitude shorthand that appear in the user's investing idea. "
                "A standalone numeric magnitude at the end of an otherwise "
                "complete strategy, asset, and date-window request is a "
                "starting-capital candidate when it is not serving as a date, "
                "lookback window, percentage, indicator parameter, share count, "
                "or asset identifier. Do not require currency symbols. Do not "
                "treat dates, calendar years, "
                "indicator windows, lookback windows, percentages, share counts, "
                "or asset names as capital. For DCA or recurring buys, return the per-purchase "
                "recurring contribution as recurring_contribution_amount, not "
                "capital_amount; return cadence only when the current message states "
                "one. If a money amount is total budget, starting principal, or cap, "
                "leave recurring_contribution_amount null. Normalize one-hour/hourly "
                "bars to 1h, four-hour bars to "
                "4h, and daily bars to 1D. Preserve today/current as today or the "
                f"runtime date {date.today().isoformat()} only when the user stated "
                "today/current. If the user stated only a start or only an end date, "
                "return only that endpoint; do not infer the missing endpoint or "
                "rewrite the unstated endpoint. For pending date answers such as "
                "'end of 2023' or 'through December 2024', return only the end "
                "endpoint. Date phrases such as 'at the start of 2024', 'from "
                "the beginning of 2024', or 'since 2024' state only a start "
                "endpoint unless the message also states an end. Return explicit "
                "comparison assets as comparison_baseline, "
                "not asset_universe. Treat benchmark/reference/baseline/comparison "
                "relationships semantically in any language; if a user names an "
                "asset as a reference, benchmark, against/versus target, or "
                "comparison target, that asset belongs in comparison_baseline. "
                "If the draft has a default benchmark but the current "
                "message states a different comparison asset, return the user-stated "
                "comparison asset. Return "
                "only JSON matching the schema."
            ),
        },
        {
            "role": "system",
            "content": (
                "Structured draft JSON: "
                f"{response.candidate_strategy_draft.model_dump(mode='json')}"
            ),
        },
        {"role": "user", "content": request.current_user_message},
    ]


def _response_from_stated_run_field_fidelity_audit(
    *,
    response: LLMInterpretationResponse,
    audit: StatedRunFieldFidelityAudit,
    current_message: str = "",
) -> LLMInterpretationResponse | None:
    repaired = response.model_copy(deep=True)
    draft = repaired.candidate_strategy_draft
    changed = False
    if audit.capital_amount is not None and draft.capital_amount != audit.capital_amount:
        draft.capital_amount = audit.capital_amount
        draft.field_provenance["capital_amount"] = "starting_capital"
        changed = True
    if audit.recurring_contribution_amount is not None:
        recurring_amount = float(audit.recurring_contribution_amount)
        if draft.capital_amount != recurring_amount:
            draft.capital_amount = recurring_amount
            changed = True
        if draft.field_provenance.get("capital_amount") != "recurring_contribution":
            draft.field_provenance["capital_amount"] = "recurring_contribution"
            changed = True
    if audit.cadence:
        cadence = _supported_dca_cadence_value(audit.cadence)
        if cadence is not None:
            if draft.cadence != cadence:
                draft.cadence = cadence
                changed = True
            if draft.field_provenance.get("cadence") != "explicit_user":
                draft.field_provenance["cadence"] = "explicit_user"
                changed = True
    if audit.timeframe and draft.timeframe != audit.timeframe:
        draft.timeframe = audit.timeframe
        changed = True
    if audit.date_range not in (None, "", [], {}):
        audited_date_range: Any = audit.date_range
        del current_message
        expected_date_range = _date_range_from_intent_or_bounded_evidence(draft)
        if (
            isinstance(expected_date_range, dict)
            and not has_partial_explicit_date_range(expected_date_range)
            and isinstance(audited_date_range, dict)
            and _normalized_stated_field(audited_date_range)
            != _normalized_stated_field(expected_date_range)
        ):
            audited_date_range = expected_date_range
        date_range, date_changed = _date_range_with_fidelity_audit(
            current=draft.date_range,
            audited=audited_date_range,
        )
        if date_changed:
            draft.date_range = date_range
            changed = True
    if audit.comparison_baseline:
        baseline = str(audit.comparison_baseline).strip().upper()
        if baseline:
            if draft.comparison_baseline != baseline:
                draft.comparison_baseline = baseline
                changed = True
            if draft.field_provenance.get("comparison_baseline") != (
                "stated_run_field_fidelity_audit"
            ):
                draft.field_provenance["comparison_baseline"] = (
                    "stated_run_field_fidelity_audit"
                )
                changed = True
    if not changed:
        return None
    repaired.reason_codes = list(
        dict.fromkeys(
            [
                *repaired.reason_codes,
                "stated_run_field_fidelity_audit",
            ]
        )
    )
    return repaired


def _stated_run_field_audit_omitted_expected_fields(
    *,
    response: LLMInterpretationResponse,
    audit: StatedRunFieldFidelityAudit,
    request: InterpretationRequest,
) -> bool:
    draft = response.candidate_strategy_draft
    del request
    expected_date_range = _date_range_from_intent_or_bounded_evidence(draft)
    if expected_date_range is None and isinstance(draft.date_range, dict):
        expected_date_range = draft.date_range
    if (
        not _llm_value_is_empty(draft.date_range)
        and expected_date_range is not None
        and audit.date_range in (None, "", [], {})
    ):
        return True
    return False
