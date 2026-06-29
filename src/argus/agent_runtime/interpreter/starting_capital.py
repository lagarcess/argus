"""Stated-starting-capital audit helpers.

Behavior-preserving relocation from llm_interpreter.py (issue #131)."""

from __future__ import annotations

import json
from typing import Any

from argus.agent_runtime.interpreter.audits import StatedStartingCapitalAudit
from argus.agent_runtime.interpreter.run_field_audits import (
    _draft_contains_structured_capital_context,
    _text_contains_capital_audit_signal,
)
from argus.agent_runtime.interpreter.shared import (
    _TOTAL_CAPITAL_SOURCES,
    _capital_source,
    _llm_strategy_draft_has_concrete_execution_target,
)
from argus.agent_runtime.llm_interpreter_types import (
    FocusedStrategyExtraction,
    LLMInterpretationResponse,
    LLMStrategyDraft,
)
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.strategy_contract import canonical_strategy_type


def _response_needs_stated_starting_capital_recheck(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    if response.intent not in {"strategy_drafting", "backtest_execution"}:
        return False
    if response.semantic_turn_act in {
        "approval",
        "result_followup",
        "unsupported_request",
    }:
        return False
    draft = response.candidate_strategy_draft
    if canonical_strategy_type(draft.strategy_type) == "dca_accumulation":
        return False
    if _draft_has_grounded_non_dca_starting_capital(draft):
        return False
    if not _llm_strategy_draft_has_concrete_execution_target(draft):
        return False
    return _text_contains_capital_audit_signal(
        request.current_user_message,
        draft=draft,
    ) or _draft_contains_structured_capital_context(draft)


def _draft_has_grounded_non_dca_starting_capital(draft: LLMStrategyDraft) -> bool:
    if canonical_strategy_type(draft.strategy_type) == "dca_accumulation":
        return False
    if draft.capital_amount is not None:
        return True
    field_provenance = draft.field_provenance or {}
    if (
        draft.initial_capital is not None
        and _capital_source(field_provenance, "initial_capital") in _TOTAL_CAPITAL_SOURCES
    ):
        return True
    return (
        draft.total_capital is not None
        and _capital_source(field_provenance, "total_capital") in _TOTAL_CAPITAL_SOURCES
    )


def _stated_starting_capital_messages(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are Argus's focused starting-capital verifier. The broad "
                "run-field audit may have omitted a money amount. Decide only "
                "whether the current user message explicitly states starting "
                "capital for the runnable idea. Return starting_capital as a "
                "normalized number only when the message uses the amount as the "
                "cash to test, invest, allocate, put on, or use as capital. This "
                "is language-agnostic: normalize numeric magnitude shorthand "
                "such as 100k -> 100000 and 2.5m -> 2500000 when it is the "
                "allocation amount. Include confidence; use high confidence for "
                "an exact literal amount from the current message. For example, "
                "a non-recurring buy-and-hold request that says 'con 10000 dolares' "
                "should return starting_capital 10000 with high confidence. "
                "Use structured draft prose as supporting "
                "evidence when it says an amount from the current message is "
                "starting capital but the numeric field is missing; the current "
                "user message remains authoritative. Treat draft prose that captures "
                "a user-stated starting-capital amount while capital_amount is null "
                "as a contradiction to reconcile from the current message, not as "
                "evidence that no capital was stated. A standalone numeric magnitude "
                "at the end of an otherwise complete strategy, asset, and "
                "date-window request is a starting-capital candidate when it is "
                "not serving as a date, lookback window, percentage, indicator "
                "parameter, share count, or asset identifier. Do not require a "
                "currency symbol. Return null for dates, calendar years, "
                "indicator periods, lookback windows, percentages, share counts, "
                "asset names, ticker symbols, or benchmark names. For DCA or "
                "recurring buys, do not return per-purchase contribution here. "
                "Do not copy default assumptions from the draft. If unsure, "
                "return null with low confidence. Return only JSON matching the "
                "schema."
            ),
        },
        {
            "role": "system",
            "content": (
                "Draft prose evidence JSON: "
                f"{json.dumps(_starting_capital_prose_evidence_payload(response), ensure_ascii=False)}"
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


def _starting_capital_prose_evidence_payload(
    response: LLMInterpretationResponse,
) -> dict[str, Any]:
    draft = response.candidate_strategy_draft
    return {
        "raw_user_phrasing": draft.raw_user_phrasing,
        "strategy_thesis": draft.strategy_thesis,
        "evidence_spans": draft.evidence_spans,
        "date_range_raw_text": draft.date_range_raw_text,
        "capital_amount": draft.capital_amount,
        "field_provenance": dict(draft.field_provenance or {}),
    }


def _response_from_stated_starting_capital_audit(
    *,
    response: LLMInterpretationResponse,
    audit: StatedStartingCapitalAudit,
) -> LLMInterpretationResponse | None:
    if audit.starting_capital is None or audit.confidence < 0.8:
        return None
    repaired = response.model_copy(deep=True)
    draft = repaired.candidate_strategy_draft
    if canonical_strategy_type(draft.strategy_type) == "dca_accumulation":
        return None
    if draft.capital_amount == audit.starting_capital and draft.field_provenance.get(
        "capital_amount"
    ) == "starting_capital":
        return None
    draft.capital_amount = float(audit.starting_capital)
    draft.field_provenance["capital_amount"] = "starting_capital"
    repaired.reason_codes = list(
        dict.fromkeys(
            [
                *repaired.reason_codes,
                "stated_run_field_fidelity_audit",
                "stated_starting_capital_recheck",
            ]
        )
    )
    return repaired


def _focused_strategy_extraction_has_material_fields(
    extraction: FocusedStrategyExtraction,
) -> bool:
    if not extraction.is_testable_strategy:
        return False
    return any(
        [
            bool(extraction.strategy_type),
            bool(extraction.asset_universe),
            bool(extraction.asset_class),
            bool(extraction.timeframe),
            bool(extraction.date_range),
            extraction.date_range_intent is not None,
            bool(extraction.comparison_baseline),
            extraction.capital_amount is not None,
            extraction.recurring_contribution is not None,
            bool(extraction.cadence),
            bool(extraction.entry_rule),
            bool(extraction.exit_rule),
            bool(extraction.rule_spec),
            bool(extraction.indicator),
            extraction.indicator_period is not None,
            extraction.entry_threshold is not None,
            extraction.exit_threshold is not None,
            bool(extraction.entry_logic),
            bool(extraction.exit_logic),
        ]
    )
