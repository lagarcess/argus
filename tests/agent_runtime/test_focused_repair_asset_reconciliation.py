"""A focused re-read never degrades a provider-grounded asset.

Live capture, 2026-08-15: on "let's test apple with 10K" the primary parse
returned AAPL with the preflight's provider record attached, then the focused
repair re-read the message as APPLE and its statement won the merge. APPLE is
symbol-shaped, so downstream resolution failed, the asset vanished, and
clarify asked for the asset the user had already supplied. The merge must
treat a repair entry matching a runtime preflight record as the same mention
and keep the record's canonical symbol.
"""

from __future__ import annotations

from argus.agent_runtime.interpreter.focused_extraction import (
    _merge_focused_repair_with_base,
)
from argus.agent_runtime.llm_interpreter_types import (
    LLMInterpretationResponse,
    LLMStrategyDraft,
)

_APPLE_RECORD = {
    "raw_text": "apple",
    "symbol": "AAPL",
    "asset_class": "equity",
    "name": "Apple Inc. Common Stock",
    "raw_symbol": "AAPL",
    "provider": "alpaca",
    "exchange": "AssetExchange.NASDAQ",
}


def _base_response() -> LLMInterpretationResponse:
    return LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="Test Apple with 10K",
        semantic_turn_act="new_idea",
        missing_required_fields=["date_range"],
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="let's test apple with 10K",
            strategy_type="buy_and_hold",
            asset_universe=["AAPL"],
            asset_class="equity",
            capital_amount=10000.0,
            evidence_spans={"asset_universe": "apple", "capital_amount": "with 10K"},
            extra_parameters={"provider_resolved_assets": [dict(_APPLE_RECORD)]},
        ),
    )


def _repaired_response(assets: list[str]) -> LLMInterpretationResponse:
    return LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="Test Apple with 10K",
        missing_required_fields=["date_range"],
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="let's test apple with 10K",
            strategy_type="buy_and_hold",
            strategy_thesis="Test Apple with 10K",
            asset_universe=list(assets),
            capital_amount=10000.0,
        ),
        reason_codes=["focused_strategy_extraction_repair"],
    )


def test_degraded_re_read_of_a_grounded_mention_keeps_the_canonical_symbol() -> None:
    merged = _merge_focused_repair_with_base(
        response=_repaired_response(["APPLE"]),
        base_response=_base_response(),
    )

    draft = merged.candidate_strategy_draft
    assert draft.asset_universe == ["AAPL"]
    assert (
        "focused_repair_assets_reconciled_with_provider_context" in merged.reason_codes
    )
    # The runtime-owned provider records ride along for later canonicalization.
    assert draft.extra_parameters["provider_resolved_assets"] == [_APPLE_RECORD]
    # Preservation stays field-general: the repair's own statements still win.
    assert draft.strategy_thesis == "Test Apple with 10K"
    assert draft.capital_amount == 10000.0


def test_genuinely_new_asset_statement_passes_through_untouched() -> None:
    merged = _merge_focused_repair_with_base(
        response=_repaired_response(["Nvidia"]),
        base_response=_base_response(),
    )

    draft = merged.candidate_strategy_draft
    assert draft.asset_universe == ["Nvidia"]
    assert (
        "focused_repair_assets_reconciled_with_provider_context"
        not in merged.reason_codes
    )


def test_matching_and_new_entries_reconcile_independently() -> None:
    merged = _merge_focused_repair_with_base(
        response=_repaired_response(["APPLE", "NVDA"]),
        base_response=_base_response(),
    )

    assert merged.candidate_strategy_draft.asset_universe == ["AAPL", "NVDA"]
    assert (
        "focused_repair_assets_reconciled_with_provider_context" in merged.reason_codes
    )
