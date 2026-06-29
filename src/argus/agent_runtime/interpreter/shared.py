"""Cross-cutting low-level helpers and constants shared across interpreter modules.

Behavior-preserving relocation (issue #131). These leaf helpers (date/comparison
evidence extraction, strategy-draft shape predicates, provenance field bases, value
checks) call no other interpreter top-level symbol, so this module is an import sink
that every other interpreter module depends on without cycles."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from argus.agent_runtime.llm_interpreter_types import LLMStrategyDraft
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.domain.slot_normalizer import normalize_parameter_value
from argus.domain.strategy_capabilities import STRATEGY_CAPABILITIES
from argus.nlp.natural_time import (
    date_range_evidence_has_explicit_endpoints,
    dateparser_languages_for_user_language,
    resolve_date_range_intent,
    resolve_date_range_text,
)

_DATE_EVIDENCE_SPAN_KEYS = (
    "date_range",
    "date_range_raw_text",
    "date_range_intent",
    "date_window",
    "period",
    "temporal_window",
    "time_window",
    "window",
)


_COMPARISON_BASELINE_EVIDENCE_KEYS = (
    "baseline",
    "benchmark",
    "comparison_baseline",
    "comparison_baseline_evidence",
    "comparison_target",
    "reference",
)


_EXECUTABLE_TIMEFRAMES = {"1h", "2h", "4h", "6h", "12h", "1D"}


_TOTAL_CAPITAL_SOURCES = {
    "user",
    "explicit_user",
    "prior",
    "initial_capital",
    "starting_capital",
    "starting_principal",
    "initial_lump_sum",
    "initial_lump",
    "lump_sum",
    "total_capital",
    "total_budget",
    "max_budget",
    "investment_budget",
    "cap",
    "contribution_cap",
    "capital_cap",
    "investment_cap",
}


_RECURRING_CAPITAL_SOURCES = {
    "user",
    "explicit_user",
    "prior",
    "recurring_contribution",
    "contribution_amount",
    "periodic_contribution",
    "dca_contribution",
}


def _field_path_base(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    for separator in ("[", "."):
        text = text.split(separator, 1)[0]
    return text.strip()


def _selected_requested_field_base(request: InterpretationRequest) -> str:
    return _field_path_base(request.selected_thread_metadata.get("requested_field"))


def _supported_dca_cadence_value(value: Any) -> str | None:
    normalized_value = normalize_parameter_value(
        "dca_accumulation",
        "dca_cadence",
        value,
    )
    normalized = str(normalized_value or "").strip().casefold()
    if not normalized:
        return None
    capability = STRATEGY_CAPABILITIES.get("dca_accumulation")
    cadence_spec = capability.parameters.get("dca_cadence") if capability else None
    if cadence_spec is None:
        return None
    for allowed in cadence_spec.allowed_values:
        candidate = str(allowed).strip().casefold()
        if normalized == candidate:
            return candidate
    return None


def _draft_has_semantic_date_window_evidence(draft: LLMStrategyDraft) -> bool:
    if not _llm_value_is_empty(draft.date_range_raw_text):
        return True
    evidence_spans = _draft_semantic_evidence_spans(draft)
    return any(
        not _llm_value_is_empty(evidence_spans.get(key))
        for key in _DATE_EVIDENCE_SPAN_KEYS
    )


def _draft_has_comparison_baseline_evidence(draft: LLMStrategyDraft) -> bool:
    evidence_spans = _draft_semantic_evidence_spans(draft)
    return any(
        not _llm_value_is_empty(evidence_spans.get(key))
        for key in _COMPARISON_BASELINE_EVIDENCE_KEYS
    )


def _draft_semantic_evidence_spans(draft: LLMStrategyDraft) -> dict[str, str]:
    evidence_spans: dict[str, str] = {
        str(key): str(value)
        for key, value in (draft.evidence_spans or {}).items()
        if not _llm_value_is_empty(value)
    }
    extra_evidence_spans = (draft.extra_parameters or {}).get("evidence_spans")
    if isinstance(extra_evidence_spans, Mapping):
        for key, value in extra_evidence_spans.items():
            normalized_key = str(key)
            if normalized_key not in evidence_spans and not _llm_value_is_empty(value):
                evidence_spans[normalized_key] = str(value)
    return evidence_spans


def _llm_strategy_draft_has_concrete_execution_target(
    draft: LLMStrategyDraft,
) -> bool:
    return any(
        [
            bool(draft.asset_universe),
            bool(draft.asset_class),
            bool(draft.date_range),
            bool(draft.timeframe),
            bool(draft.cadence),
            draft.capital_amount is not None,
            draft.total_capital is not None,
            draft.initial_capital is not None,
            bool(draft.position_size),
            bool(draft.risk_rules),
            bool(draft.comparison_baseline),
        ]
    )


def _natural_time_language_candidates_from_hints(
    *language_hints: str | None,
) -> tuple[tuple[str, ...] | None, ...]:
    hinted_languages: list[tuple[str, ...] | None] = []
    for language in language_hints:
        if not str(language or "").strip():
            continue
        hints = dateparser_languages_for_user_language(language)
        if hints not in hinted_languages:
            hinted_languages.append(hints)
    if None not in hinted_languages:
        hinted_languages.append(None)
    return tuple(hinted_languages)


def _normalized_stated_field(value: Any) -> str:
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, default=str)
    return str(value or "").strip()


def _date_range_with_fidelity_audit(
    *,
    current: Any,
    audited: Any,
) -> tuple[Any, bool]:
    if _llm_value_is_empty(current):
        return audited, True
    if _normalized_stated_field(audited) == _normalized_stated_field(current):
        return current, False
    if isinstance(current, dict) and isinstance(audited, dict):
        if _date_range_audit_has_partial_endpoint(audited):
            return audited, _normalized_stated_field(audited) != _normalized_stated_field(
                current
            )
        merged = dict(current)
        changed = False
        for key, audited_value in audited.items():
            if audited_value in (None, "", [], {}):
                continue
            current_value = merged.get(key)
            if current_value not in (None, "", [], {}) and _date_value_is_less_specific(
                audited_value,
                current_value,
            ):
                continue
            if _normalized_stated_field(current_value) != _normalized_stated_field(
                audited_value
            ):
                merged[key] = audited_value
                changed = True
        return merged, changed
    if isinstance(audited, dict):
        return audited, True
    return current, False


def _date_range_audit_has_partial_endpoint(value: dict[str, Any]) -> bool:
    start = value.get("start") or value.get("from")
    end = value.get("end") or value.get("to")
    return (start not in (None, "", [], {})) != (end not in (None, "", [], {}))


def _date_value_is_less_specific(candidate: Any, existing: Any) -> bool:
    candidate_text = str(candidate or "").strip()
    existing_text = str(existing or "").strip()
    if not candidate_text or not existing_text:
        return False
    if candidate_text.casefold() in {"today", "current", "now"}:
        return False
    if existing_text.casefold() in {"today", "current", "now"}:
        return True
    candidate_digits = sum(1 for char in candidate_text if char.isdigit())
    existing_digits = sum(1 for char in existing_text if char.isdigit())
    return candidate_digits < existing_digits and existing_text.startswith(
        candidate_text
    )


def _llm_value_is_empty(value: Any) -> bool:
    return value in (None, "", [], {})


def _llm_strategy_draft_has_rule_or_indicator_fields(
    draft: LLMStrategyDraft,
) -> bool:
    return any(
        [
            bool(draft.entry_logic),
            bool(draft.exit_logic),
            bool(draft.entry_rule),
            bool(draft.exit_rule),
            bool(draft.rule_spec),
            bool(draft.indicator),
            draft.indicator_period is not None,
            draft.entry_threshold is not None,
            draft.exit_threshold is not None,
        ]
    )


def _llm_strategy_draft_has_extractable_fields(draft: LLMStrategyDraft) -> bool:
    return any(
        [
            bool(draft.strategy_type),
            bool(draft.strategy_thesis),
            bool(draft.asset_universe),
            bool(draft.cadence),
            bool(draft.entry_logic),
            bool(draft.exit_logic),
            bool(draft.entry_rule),
            bool(draft.exit_rule),
            bool(draft.rule_spec),
            bool(draft.indicator),
            draft.indicator_period is not None,
            draft.entry_threshold is not None,
            draft.exit_threshold is not None,
            bool(draft.date_range),
            draft.capital_amount is not None,
            draft.position_size is not None,
            bool(draft.risk_rules),
            bool(draft.extra_parameters),
        ]
    )


def _has_complete_date_range_payload(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    start = value.get("start") or value.get("from")
    end = value.get("end") or value.get("to")
    return bool(start not in (None, "", [], {}) and end not in (None, "", [], {}))


def _date_range_from_intent_or_bounded_evidence(
    draft: LLMStrategyDraft,
    *,
    language: str | None = None,
) -> dict[str, str] | None:
    intent_resolution = resolve_date_range_intent(draft.date_range_intent)
    explicit_bounded = _date_range_from_bounded_evidence(
        draft,
        language=language,
        require_explicit_endpoint_evidence=True,
    )
    if (
        intent_resolution is not None
        and explicit_bounded is not None
        and _normalized_stated_field(intent_resolution.payload)
        != _normalized_stated_field(explicit_bounded)
    ):
        return explicit_bounded
    if intent_resolution is not None:
        return intent_resolution.payload
    bounded = _date_range_from_bounded_evidence(draft, language=language)
    if bounded is not None:
        return bounded
    return None


def _date_range_from_bounded_evidence(
    draft: LLMStrategyDraft,
    *,
    language: str | None = None,
    require_explicit_endpoint_evidence: bool = False,
) -> dict[str, str] | None:
    evidence_candidates = _bounded_date_evidence_candidates(draft)
    if not evidence_candidates:
        return None
    language_candidates = _natural_time_language_candidates_from_hints(
        draft.language,
        language,
    )
    for candidate in evidence_candidates:
        for languages in language_candidates:
            resolved = resolve_date_range_text(candidate, languages=languages)
            if resolved is not None:
                if (
                    require_explicit_endpoint_evidence
                    and not date_range_evidence_has_explicit_endpoints(
                        resolved.evidence_spans
                    )
                ):
                    continue
                return resolved.payload
    return None


def _bounded_date_evidence_candidates(draft: LLMStrategyDraft) -> list[str]:
    candidates: list[str] = []
    if draft.date_range_raw_text:
        candidates.append(draft.date_range_raw_text)
    evidence_spans = _draft_semantic_evidence_spans(draft)
    for key in _DATE_EVIDENCE_SPAN_KEYS:
        value = evidence_spans.get(key)
        if value:
            candidates.append(value)
    return list(dict.fromkeys(str(item).strip() for item in candidates if str(item).strip()))


def _capital_source(field_provenance: dict[str, str], key: str) -> str:
    if not isinstance(field_provenance, dict):
        return ""
    return str(field_provenance.get(key) or "").strip()
