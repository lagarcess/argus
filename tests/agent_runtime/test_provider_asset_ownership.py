"""Issue #241: `provider_resolved_assets` is runtime-owned, never model-owned.

`LLMStrategyDraft.extra_parameters` is model-writable. A hallucinated
`provider_resolved_assets` record must not masquerade as provider truth: the
provider-context normalization boundary strips any incoming value and only the
actual runtime provider-context rows repopulate it. Downstream consumers (the
refusal-conservation helper, canonical-asset repair) then trust the key.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest
from argus.agent_runtime.interpreter.asset_resolution_context import (
    _asset_mention_extraction_messages,
    provider_asset_resolution_context_from_extraction,
)
from argus.agent_runtime.interpreter.provider_context_assets import (
    response_with_canonical_interpreter_assets,
    response_with_provider_context_assets,
)
from argus.agent_runtime.interpreter.strategy_builder import _strategy_from_llm
from argus.agent_runtime.llm_interpreter_types import (
    LLMAssetMentionExtraction,
    LLMInterpretationResponse,
    LLMStrategyDraft,
    LLMUnsupportedConstraint,
)
from argus.agent_runtime.resolution import AssetResolution
from argus.agent_runtime.stages.interpret import (
    StructuredInterpretation,
    interpret_stage,
)
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.state.models import (
    ResolutionProvenance,
    RunState,
    UnsupportedConstraint,
    UserState,
)

FAKE_RECORD = {
    "raw_text": "Zorbcoin",
    "symbol": "ZORB",
    "asset_class": "crypto",
    "name": "Zorbcoin",
    "raw_symbol": "ZORB/USD",
    "provider": "alpaca",
    "exchange": "AssetExchange.CRYPTO",
}

BTC_CONTEXT_ROW = {
    "raw_text": "Bitcoin",
    "role": "traded_asset",
    "status": "resolved",
    "symbol": "BTC",
    "asset_class": "crypto",
    "name": "Bitcoin / US Dollar",
    "raw_symbol": "BTC/USD",
    "provider": "alpaca",
    "exchange": "AssetExchange.CRYPTO",
}


@dataclass(frozen=True)
class ResolvedAssetStub:
    canonical_symbol: str
    asset_class: str
    name: str = ""
    raw_symbol: str = ""


class RecordingInterpreter:
    def __init__(self, response: StructuredInterpretation | None) -> None:
        self.response = response

    def __call__(self, request):
        return self.response


def _stub_crypto_asset_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    def resolve_stub(symbol: str, **_: Any) -> ResolvedAssetStub:
        return ResolvedAssetStub(symbol.upper(), "crypto")

    monkeypatch.setattr(interpret_module, "resolve_asset", resolve_stub)


def _refusal_response_with_model_records() -> LLMInterpretationResponse:
    return LLMInterpretationResponse(
        intent="unsupported_or_out_of_scope",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="Predict Zorbcoin's future value.",
        assistant_response=(
            "I can't predict what Zorbcoin will be worth, and it is not in the "
            "supported market data."
        ),
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="buy_and_hold",
            asset_universe=[],
            asset_class="crypto",
            capital_amount=5000,
            extra_parameters={"provider_resolved_assets": [dict(FAKE_RECORD)]},
        ),
        unsupported_constraints=[
            LLMUnsupportedConstraint(
                category="unsupported_symbol",
                raw_value="Zorbcoin",
                explanation="Zorbcoin is not available in supported market data.",
            )
        ],
        semantic_turn_act="unsupported_request",
    )


def _context(rows: list[dict[str, Any]]) -> str:
    return json.dumps(
        {
            "asset_resolution_candidates": rows,
            "all_traded_asset_mentions_accounted_for": True,
        }
    )


def _extraction_asset_resolution(
    *,
    query: str,
    field: str,
    source: str,
    symbol: str | None,
    asset_class: str = "equity",
) -> AssetResolution:
    asset = (
        None
        if symbol is None
        else ResolvedAssetStub(
            canonical_symbol=symbol,
            asset_class=asset_class,
            name=query,
            raw_symbol=symbol,
        )
    )
    status = "resolved" if asset is not None else "unsupported"
    return AssetResolution(
        status=status,
        raw_text=query,
        asset=asset,
        candidates=(() if asset is None else (asset,)),
        provenance=ResolutionProvenance(
            field=field,
            raw_text=query,
            source=source,
            candidate_kind="asset",
            resolution_status=status,
            canonical_symbol=(None if asset is None else asset.canonical_symbol),
            asset_class=(None if asset is None else asset.asset_class),
            validated_by="provider_catalog",
            confidence="high",
        ),
    )


def test_model_supplied_provider_records_are_stripped_without_runtime_context() -> None:
    normalized = response_with_provider_context_assets(
        _refusal_response_with_model_records(),
        asset_resolution_context=None,
        include_unsupported_request=True,
    )
    extra = normalized.candidate_strategy_draft.extra_parameters or {}
    assert "provider_resolved_assets" not in extra
    assert normalized.candidate_strategy_draft.asset_universe == []


def test_fake_record_cannot_reach_pending_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_crypto_asset_resolution(monkeypatch)
    normalized = response_with_provider_context_assets(
        _refusal_response_with_model_records(),
        asset_resolution_context=None,
        include_unsupported_request=True,
    )
    strategy = _strategy_from_llm(normalized.candidate_strategy_draft)
    result = interpret_stage(
        state=RunState.new(
            current_user_message="If I put $5,000 into Zorbcoin, what will it become?",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1", expertise_level="advanced"),
        latest_task_snapshot=None,
        selected_thread_metadata={},
        structured_interpreter=RecordingInterpreter(
            StructuredInterpretation(
                intent="unsupported_or_out_of_scope",
                task_relation="new_task",
                requires_clarification=True,
                user_goal_summary="Predict Zorbcoin's future value.",
                candidate_strategy_draft=strategy,
                unsupported_constraints=[
                    UnsupportedConstraint(
                        category="unsupported_symbol",
                        raw_value="Zorbcoin",
                        explanation=(
                            "Zorbcoin is not available in supported market data."
                        ),
                    )
                ],
                semantic_turn_act="unsupported_request",
            )
        ),
    )
    assert result.outcome == "needs_clarification"
    assert result.patch.get("confirmation_payload") is None
    draft = result.decision.candidate_strategy_draft
    assert draft.asset_universe == []
    assert "ZORB" not in [str(s).upper() for s in draft.asset_universe]


def test_runtime_context_rows_still_inject_and_conserve_real_assets() -> None:
    normalized = response_with_provider_context_assets(
        _refusal_response_with_model_records(),
        asset_resolution_context=_context([dict(BTC_CONTEXT_ROW)]),
        include_unsupported_request=True,
    )
    draft = normalized.candidate_strategy_draft
    extra = draft.extra_parameters or {}
    records = extra.get("provider_resolved_assets")
    assert isinstance(records, list) and len(records) == 1
    assert records[0]["symbol"] == "BTC"
    # The fake model record is gone; only the runtime row survives.
    assert all(record["symbol"] != "ZORB" for record in records)
    assert draft.asset_universe == ["BTC"]


def test_runtime_context_asset_clears_stale_missing_asset_clarification() -> None:
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="Test Apple with $10,000.",
        assistant_response="Which asset should I test?",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="let's test apple with 10K",
            strategy_type="buy_and_hold",
            capital_amount=10000,
        ),
        missing_required_fields=["asset_universe", "date_range"],
        semantic_turn_act="new_idea",
    )
    apple_context_row = {
        "raw_text": "apple",
        "role": "traded_asset",
        "status": "resolved",
        "symbol": "AAPL",
        "asset_class": "equity",
        "name": "Apple Inc.",
        "raw_symbol": "AAPL",
        "provider": "alpaca",
        "exchange": "NASDAQ",
    }

    normalized = response_with_provider_context_assets(
        response,
        asset_resolution_context=_context([apple_context_row]),
    )

    draft = normalized.candidate_strategy_draft
    assert draft.asset_universe == ["AAPL"]
    assert draft.asset_class == "equity"
    assert normalized.missing_required_fields == ["date_range"]
    assert normalized.requires_clarification is True
    assert normalized.assistant_response is None
    assert "provider_context_resolved_missing_asset" in normalized.reason_codes


def test_mixed_resolved_and_ambiguous_context_keeps_stale_asset_blocker() -> None:
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="Test Apple and Sun with $10,000.",
        assistant_response="Which asset should I test?",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="let's test apple and sun with 10K",
            strategy_type="buy_and_hold",
            capital_amount=10000,
        ),
        missing_required_fields=["asset_universe", "date_range"],
        semantic_turn_act="new_idea",
    )
    resolved_apple_row = {
        "raw_text": "apple",
        "role": "traded_asset",
        "status": "resolved",
        "symbol": "AAPL",
        "asset_class": "equity",
        "name": "Apple Inc.",
        "raw_symbol": "AAPL",
        "provider": "alpaca",
        "exchange": "NASDAQ",
    }
    ambiguous_sun_row = {
        "raw_text": "Sun",
        "role": "traded_asset",
        "status": "ambiguous",
        "candidates": [
            {"symbol": "SUN", "asset_class": "equity"},
            {"symbol": "SUNE", "asset_class": "equity"},
        ],
    }

    normalized = response_with_provider_context_assets(
        response,
        asset_resolution_context=_context([resolved_apple_row, ambiguous_sun_row]),
    )

    assert normalized.candidate_strategy_draft.asset_universe == ["AAPL"]
    assert normalized.missing_required_fields == ["asset_universe", "date_range"]
    assert normalized.requires_clarification is True
    assert normalized.assistant_response is None
    assert normalized.ambiguous_fields
    assert "provider_context_resolved_missing_asset" not in normalized.reason_codes


def test_resolved_and_unsupported_extracted_mentions_keep_stale_asset_blocker() -> None:
    def resolve_candidate(
        query: str,
        *,
        field: str,
        source: str,
        **_: Any,
    ) -> AssetResolution:
        return _extraction_asset_resolution(
            query=query,
            field=field,
            source=source,
            symbol=("AAPL" if query == "Apple" else None),
        )

    context = provider_asset_resolution_context_from_extraction(
        LLMAssetMentionExtraction(
            asset_mentions=[
                {
                    "raw_text": "Apple",
                    "role": "traded_asset",
                    "mention_kind": "company_name",
                    "confidence": 0.9,
                },
                {
                    "raw_text": "fictional moon fund",
                    "role": "traded_asset",
                    "mention_kind": "company_name",
                    "confidence": 0.9,
                },
            ],
            all_traded_asset_mentions_included=True,
        ),
        resolve_asset_candidate=resolve_candidate,
    )
    assert context is not None
    payload = json.loads(context)
    assert payload["all_traded_asset_mentions_accounted_for"] is False

    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="Test Apple and fictional moon fund in 2024.",
        assistant_response="Which asset should I test?",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="test Apple and fictional moon fund in 2024",
            strategy_type="buy_and_hold",
            date_range={"start": "2024-01-01", "end": "2024-12-31"},
        ),
        missing_required_fields=["asset_universe"],
        semantic_turn_act="new_idea",
    )

    normalized = response_with_provider_context_assets(
        response,
        asset_resolution_context=context,
    )

    assert normalized.candidate_strategy_draft.asset_universe == ["AAPL"]
    assert normalized.missing_required_fields == ["asset_universe"]
    assert normalized.requires_clarification is True
    assert normalized.assistant_response == "Which asset should I test?"
    assert "provider_context_resolved_missing_asset" not in normalized.reason_codes


def test_capped_extraction_marks_uninspected_asset_mentions_incomplete() -> None:
    symbols = {
        "Apple": "AAPL",
        "Microsoft": "MSFT",
        "NVIDIA": "NVDA",
        "Amazon": "AMZN",
        "Meta": "META",
    }

    def resolve_candidate(
        query: str,
        *,
        field: str,
        source: str,
        **_: Any,
    ) -> AssetResolution:
        return _extraction_asset_resolution(
            query=query,
            field=field,
            source=source,
            symbol=symbols.get(query),
        )

    context = provider_asset_resolution_context_from_extraction(
        LLMAssetMentionExtraction(
            asset_mentions=[
                {
                    "raw_text": name,
                    "role": "traded_asset",
                    "mention_kind": "company_name",
                    "confidence": 0.9,
                }
                for name in [*symbols, "fictional moon fund"]
            ],
            all_traded_asset_mentions_included=True,
        ),
        resolve_asset_candidate=resolve_candidate,
    )

    assert context is not None
    payload = json.loads(context)
    assert [row["symbol"] for row in payload["asset_resolution_candidates"]] == list(
        symbols.values()
    )
    assert payload["all_traded_asset_mentions_accounted_for"] is False

    truncated_response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="Test a six-asset basket.",
        assistant_response="Ready to test the five resolved assets.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="buy_and_hold",
            asset_universe=list(symbols.values()),
            asset_class="equity",
            date_range={"start": "2024-01-01", "end": "2024-12-31"},
        ),
        semantic_turn_act="new_idea",
    )

    normalized = response_with_provider_context_assets(
        truncated_response,
        asset_resolution_context=context,
    )

    assert normalized.candidate_strategy_draft.asset_universe == list(symbols.values())
    assert normalized.missing_required_fields == ["asset_universe"]
    assert normalized.requires_clarification is True
    assert normalized.assistant_response is None
    assert "provider_context_incomplete_asset_mentions" in normalized.reason_codes

    stage_result = interpret_stage(
        state=RunState.new(
            current_user_message=(
                "Test Apple, Microsoft, NVIDIA, Amazon, Meta, and fictional moon fund."
            ),
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1"),
        latest_task_snapshot=None,
        selected_thread_metadata={},
        structured_interpreter=RecordingInterpreter(
            StructuredInterpretation(
                intent=normalized.intent,
                task_relation=normalized.task_relation,
                requires_clarification=normalized.requires_clarification,
                user_goal_summary=normalized.user_goal_summary,
                candidate_strategy_draft=_strategy_from_llm(
                    normalized.candidate_strategy_draft
                ),
                missing_required_fields=normalized.missing_required_fields,
                assistant_response=normalized.assistant_response,
                reason_codes=normalized.reason_codes,
                semantic_turn_act=normalized.semantic_turn_act,
            )
        ),
    )

    assert stage_result.outcome == "needs_clarification"
    assert stage_result.decision is not None
    assert stage_result.decision.missing_required_fields[0] == "asset_universe"
    assert stage_result.patch.get("confirmation_payload") is None

    unsupported_stage_result = interpret_stage(
        state=RunState.new(
            current_user_message=(
                "Test Apple, Microsoft, NVIDIA, Amazon, Meta, and fictional moon "
                "fund using lunar volatility."
            ),
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1"),
        latest_task_snapshot=None,
        selected_thread_metadata={},
        structured_interpreter=RecordingInterpreter(
            StructuredInterpretation(
                intent=normalized.intent,
                task_relation=normalized.task_relation,
                requires_clarification=normalized.requires_clarification,
                user_goal_summary=normalized.user_goal_summary,
                candidate_strategy_draft=_strategy_from_llm(
                    normalized.candidate_strategy_draft
                ),
                missing_required_fields=normalized.missing_required_fields,
                unsupported_constraints=[
                    UnsupportedConstraint(
                        category="unsupported_strategy_logic",
                        raw_value="lunar volatility",
                        explanation="That strategy logic is not executable.",
                    )
                ],
                assistant_response=normalized.assistant_response,
                reason_codes=[
                    *normalized.reason_codes,
                    "draft_only_indicator_text_preserved",
                ],
                semantic_turn_act=normalized.semantic_turn_act,
            )
        ),
    )

    assert unsupported_stage_result.outcome == "needs_clarification"
    assert unsupported_stage_result.decision is not None
    assert unsupported_stage_result.decision.missing_required_fields[0] == (
        "asset_universe"
    )
    assert unsupported_stage_result.patch.get("confirmation_payload") is None


def test_duplicate_resolved_symbol_does_not_consume_traded_asset_slot() -> None:
    symbols = {
        "Apple": "AAPL",
        "AAPL": "AAPL",
        "Microsoft": "MSFT",
        "NVIDIA": "NVDA",
        "Amazon": "AMZN",
        "Meta": "META",
    }
    resolved_fields: list[str] = []

    def resolve_candidate(
        query: str,
        *,
        field: str,
        source: str,
        **_: Any,
    ) -> AssetResolution:
        resolved_fields.append(field)
        return _extraction_asset_resolution(
            query=query,
            field=field,
            source=source,
            symbol=symbols[query],
        )

    context = provider_asset_resolution_context_from_extraction(
        LLMAssetMentionExtraction(
            asset_mentions=[
                {
                    "raw_text": name,
                    "role": "traded_asset",
                    "mention_kind": ("ticker" if name == "AAPL" else "company_name"),
                    "confidence": 0.9,
                }
                for name in symbols
            ],
            all_traded_asset_mentions_included=True,
        ),
        resolve_asset_candidate=resolve_candidate,
    )

    assert context is not None
    payload = json.loads(context)
    assert [row["symbol"] for row in payload["asset_resolution_candidates"]] == [
        "AAPL",
        "MSFT",
        "NVDA",
        "AMZN",
        "META",
    ]
    assert payload["all_traded_asset_mentions_accounted_for"] is True
    assert resolved_fields == [
        "asset_universe[0]",
        "asset_universe[1]",
        "asset_universe[1]",
        "asset_universe[2]",
        "asset_universe[3]",
        "asset_universe[4]",
    ]


def test_same_symbol_across_asset_classes_remains_a_mixed_asset_candidate() -> None:
    assets = {
        "BTC equity": ("BTC", "equity"),
        "Bitcoin": ("BTC", "crypto"),
    }
    resolved_fields: list[str] = []

    def resolve_candidate(
        query: str,
        *,
        field: str,
        source: str,
        **_: Any,
    ) -> AssetResolution:
        resolved_fields.append(field)
        symbol, asset_class = assets[query]
        return _extraction_asset_resolution(
            query=query,
            field=field,
            source=source,
            symbol=symbol,
            asset_class=asset_class,
        )

    context = provider_asset_resolution_context_from_extraction(
        LLMAssetMentionExtraction(
            asset_mentions=[
                {
                    "raw_text": "BTC equity",
                    "role": "traded_asset",
                    "mention_kind": "company_name",
                    "confidence": 0.9,
                },
                {
                    "raw_text": "Bitcoin",
                    "role": "traded_asset",
                    "mention_kind": "crypto",
                    "confidence": 0.9,
                },
            ],
            all_traded_asset_mentions_included=True,
        ),
        resolve_asset_candidate=resolve_candidate,
    )

    assert context is not None
    payload = json.loads(context)
    assert [
        (row["symbol"], row["asset_class"])
        for row in payload["asset_resolution_candidates"]
    ] == [("BTC", "equity"), ("BTC", "crypto")]
    assert payload["all_traded_asset_mentions_accounted_for"] is True
    assert resolved_fields == ["asset_universe[0]", "asset_universe[1]"]

    normalized = response_with_provider_context_assets(
        LLMInterpretationResponse(
            intent="strategy_drafting",
            task_relation="new_task",
            requires_clarification=False,
            user_goal_summary="Test the BTC equity and Bitcoin together.",
            candidate_strategy_draft=LLMStrategyDraft(
                strategy_type="buy_and_hold",
                asset_universe=["BTC"],
                asset_class="equity",
                capital_amount=10_000,
            ),
            semantic_turn_act="new_idea",
        ),
        asset_resolution_context=context,
    )
    canonicalized = response_with_canonical_interpreter_assets(
        normalized,
        resolve_asset_candidate=lambda *_args, **_kwargs: pytest.fail(
            "provider-backed strategy context should own canonicalization"
        ),
    )
    draft = canonicalized.candidate_strategy_draft
    assert draft.asset_class == "mixed"
    records = (draft.extra_parameters or {}).get("provider_resolved_assets") or []
    assert {(record["symbol"], record["asset_class"]) for record in records} == {
        ("BTC", "equity"),
        ("BTC", "crypto"),
    }

    from argus.agent_runtime import llm_interpreter as interpreter_module
    from argus.agent_runtime.stages import interpret as interpret_module

    strategy = _strategy_from_llm(draft)
    runtime_response = canonicalized.model_copy(deep=True)
    request = InterpretationRequest(
        current_user_message="Test the BTC equity and Bitcoin together.",
        user=UserState(user_id="u1"),
    )
    interpreter_module._validate_capability_boundaries(
        strategy=strategy,
        response=runtime_response,
        request=request,
    )
    assert strategy.asset_class == "mixed"
    assert any(
        item.category == "unsupported_asset_mix"
        for item in runtime_response.unsupported_constraints
    )

    stage_strategy = interpret_module._canonicalized_strategy(
        strategy,
        current_user_message=request.current_user_message,
        selected_thread_metadata={},
    )
    assert stage_strategy.asset_class == "mixed"


def test_extractor_truncation_signal_survives_alias_deduplication() -> None:
    symbols = {
        "Apple": "AAPL",
        "AAPL": "AAPL",
        "Microsoft": "MSFT",
        "NVIDIA": "NVDA",
        "Amazon": "AMZN",
        "Meta": "META",
    }

    def resolve_candidate(
        query: str,
        *,
        field: str,
        source: str,
        **_: Any,
    ) -> AssetResolution:
        return _extraction_asset_resolution(
            query=query,
            field=field,
            source=source,
            symbol=symbols[query],
        )

    context = provider_asset_resolution_context_from_extraction(
        LLMAssetMentionExtraction(
            asset_mentions=[
                {
                    "raw_text": name,
                    "role": "traded_asset",
                    "mention_kind": ("ticker" if name == "AAPL" else "company_name"),
                    "confidence": 0.9,
                }
                for name in symbols
            ],
            all_traded_asset_mentions_included=False,
        ),
        resolve_asset_candidate=resolve_candidate,
    )

    assert context is not None
    payload = json.loads(context)
    assert [row["symbol"] for row in payload["asset_resolution_candidates"]] == [
        "AAPL",
        "MSFT",
        "NVDA",
        "AMZN",
        "META",
    ]
    assert payload["all_traded_asset_mentions_accounted_for"] is False


def test_benchmark_does_not_consume_five_traded_asset_rows() -> None:
    symbols = {
        "SPY": "SPY",
        "Apple": "AAPL",
        "Microsoft": "MSFT",
        "NVIDIA": "NVDA",
        "Amazon": "AMZN",
        "Meta": "META",
    }
    resolved_fields: list[str] = []

    def resolve_candidate(
        query: str,
        *,
        field: str,
        source: str,
        **_: Any,
    ) -> AssetResolution:
        resolved_fields.append(field)
        return _extraction_asset_resolution(
            query=query,
            field=field,
            source=source,
            symbol=symbols[query],
        )

    context = provider_asset_resolution_context_from_extraction(
        LLMAssetMentionExtraction(
            asset_mentions=[
                {
                    "raw_text": "SPY",
                    "role": "benchmark",
                    "mention_kind": "ticker",
                    "confidence": 0.9,
                },
                *[
                    {
                        "raw_text": name,
                        "role": "traded_asset",
                        "mention_kind": "company_name",
                        "confidence": 0.9,
                    }
                    for name in ["Apple", "Microsoft", "NVIDIA", "Amazon", "Meta"]
                ],
            ],
            all_traded_asset_mentions_included=True,
        ),
        resolve_asset_candidate=resolve_candidate,
    )

    assert context is not None
    payload = json.loads(context)
    assert [row["symbol"] for row in payload["asset_resolution_candidates"]] == [
        "SPY",
        "AAPL",
        "MSFT",
        "NVDA",
        "AMZN",
        "META",
    ]
    assert payload["all_traded_asset_mentions_accounted_for"] is True
    assert resolved_fields == [
        "comparison_baseline",
        "asset_universe[0]",
        "asset_universe[1]",
        "asset_universe[2]",
        "asset_universe[3]",
        "asset_universe[4]",
    ]


def test_benchmark_only_rows_cannot_bypass_incomplete_asset_context() -> None:
    def resolve_candidate(
        query: str,
        *,
        field: str,
        source: str,
        **_: Any,
    ) -> AssetResolution:
        return _extraction_asset_resolution(
            query=query,
            field=field,
            source=source,
            symbol=("SPY" if query == "SPY" else None),
        )

    context = provider_asset_resolution_context_from_extraction(
        LLMAssetMentionExtraction(
            asset_mentions=[
                {
                    "raw_text": "SPY",
                    "role": "benchmark",
                    "mention_kind": "ticker",
                    "confidence": 0.9,
                },
                {
                    "raw_text": "fictional moon fund",
                    "role": "traded_asset",
                    "mention_kind": "company_name",
                    "confidence": 0.9,
                },
            ],
            all_traded_asset_mentions_included=True,
        ),
        resolve_asset_candidate=resolve_candidate,
    )
    assert context is not None
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="Test fictional moon fund against SPY.",
        assistant_response="Ready to test AAPL against SPY.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="buy_and_hold",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range={"start": "2024-01-01", "end": "2024-12-31"},
            comparison_baseline="SPY",
        ),
        semantic_turn_act="new_idea",
    )

    normalized = response_with_provider_context_assets(
        response,
        asset_resolution_context=context,
    )

    assert normalized.missing_required_fields == ["asset_universe"]
    assert normalized.requires_clarification is True
    assert normalized.assistant_response is None
    assert "provider_context_incomplete_asset_mentions" in normalized.reason_codes


def test_missing_completeness_measurement_is_not_explicit_incompleteness() -> None:
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="Test Apple in 2024.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="buy_and_hold",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range={"start": "2024-01-01", "end": "2024-12-31"},
        ),
        semantic_turn_act="new_idea",
    )
    legacy_context = json.dumps(
        {
            "asset_resolution_candidates": [
                {
                    "raw_text": "Apple",
                    "role": "traded_asset",
                    "status": "resolved",
                    "symbol": "AAPL",
                    "asset_class": "equity",
                    "name": "Apple Inc.",
                    "raw_symbol": "AAPL",
                    "provider": "alpaca",
                    "exchange": "NASDAQ",
                }
            ]
        }
    )

    normalized = response_with_provider_context_assets(
        response,
        asset_resolution_context=legacy_context,
    )

    assert normalized.requires_clarification is False
    assert normalized.missing_required_fields == []
    assert "provider_context_incomplete_asset_mentions" not in normalized.reason_codes


def test_unsupported_only_extraction_preserves_explicit_incompleteness() -> None:
    def resolve_candidate(
        query: str,
        *,
        field: str,
        source: str,
        **_: Any,
    ) -> AssetResolution:
        return _extraction_asset_resolution(
            query=query,
            field=field,
            source=source,
            symbol=None,
        )

    context = provider_asset_resolution_context_from_extraction(
        LLMAssetMentionExtraction(
            asset_mentions=[
                {
                    "raw_text": "fictional moon fund",
                    "role": "traded_asset",
                    "mention_kind": "company_name",
                    "confidence": 0.9,
                }
            ],
            all_traded_asset_mentions_included=True,
        ),
        resolve_asset_candidate=resolve_candidate,
    )

    assert context is not None
    assert json.loads(context) == {
        "all_traded_asset_mentions_accounted_for": False,
        "asset_resolution_candidates": [],
        "extraction_contract": (
            "Use resolved traded_asset/unknown rows as asset_universe candidates "
            "when the user is buying, holding, testing, or including them. Use "
            "benchmark rows only as comparison_baseline. If status is ambiguous, "
            "keep the raw_text in the relevant structured field and require an "
            "asset clarification instead of choosing a symbol."
        ),
    }


@pytest.mark.asyncio
async def test_artifact_edit_planning_cannot_drop_incomplete_asset_blocker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    symbols = ["AAPL", "MSFT", "NVDA", "AMZN", "META"]
    incomplete_context = json.dumps(
        {
            "asset_resolution_candidates": [
                {
                    "raw_text": symbol,
                    "role": "traded_asset",
                    "status": "resolved",
                    "symbol": symbol,
                    "asset_class": "equity",
                    "name": symbol,
                    "raw_symbol": symbol,
                    "provider": "alpaca",
                    "exchange": "NASDAQ",
                }
                for symbol in symbols
            ],
            "all_traded_asset_mentions_accounted_for": False,
        }
    )

    async def planned_response_stub(**kwargs: Any) -> LLMInterpretationResponse:
        normalized = kwargs["response"]
        assert normalized.missing_required_fields == ["asset_universe"]
        assert "provider_context_incomplete_asset_mentions" in normalized.reason_codes
        return LLMInterpretationResponse(
            intent="backtest_execution",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User refined the five resolved assets.",
            candidate_strategy_draft=LLMStrategyDraft(
                strategy_type="buy_and_hold",
                asset_universe=symbols,
                asset_class="equity",
                date_range={"start": "2024-01-01", "end": "2024-12-31"},
            ),
            reason_codes=["artifact_assumption_edit_planned"],
            semantic_turn_act="answer_pending_need",
        )

    monkeypatch.setattr(
        interpreter_module,
        "_ready_active_artifact_edit_planned_response",
        planned_response_stub,
    )
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="refine",
        requires_clarification=False,
        user_goal_summary="User refined a six-asset basket.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="buy_and_hold",
            asset_universe=symbols,
            asset_class="equity",
            date_range={"start": "2024-01-01", "end": "2024-12-31"},
        ),
        semantic_turn_act="refine_current_idea",
    )

    planned = await interpreter_module._audited_response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message="Keep those five and add fictional moon fund.",
            user=UserState(user_id="u1"),
        ),
        asset_resolution_context=incomplete_context,
    )

    assert planned.requires_clarification is True
    assert planned.missing_required_fields == ["asset_universe"]
    assert planned.assistant_response is None
    assert "artifact_assumption_edit_planned" in planned.reason_codes
    assert "provider_context_incomplete_asset_mentions" in planned.reason_codes


@pytest.mark.asyncio
async def test_artifact_edit_clarification_cannot_drop_incomplete_asset_blocker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    async def planned_response_stub(**kwargs: Any) -> LLMInterpretationResponse:
        normalized = kwargs["response"]
        assert normalized.missing_required_fields == ["asset_universe"]
        return LLMInterpretationResponse(
            intent="conversation_followup",
            task_relation="continue",
            requires_clarification=True,
            user_goal_summary="The artifact edit needs another assumption.",
            candidate_strategy_draft=LLMStrategyDraft(
                strategy_type="buy_and_hold",
                asset_universe=["AAPL", "MSFT", "NVDA", "AMZN", "META"],
                asset_class="equity",
                date_range={"start": "2024-01-01", "end": "2024-12-31"},
            ),
            missing_required_fields=["assumption"],
            assistant_response="Which fee should I use?",
            reason_codes=["artifact_assumption_edit_planned"],
            semantic_turn_act="answer_pending_need",
        )

    monkeypatch.setattr(
        interpreter_module,
        "_ready_active_artifact_edit_planned_response",
        planned_response_stub,
    )
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="refine",
        requires_clarification=False,
        user_goal_summary="User refined an incomplete six-asset basket.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="buy_and_hold",
            asset_universe=["AAPL", "MSFT", "NVDA", "AMZN", "META"],
            asset_class="equity",
            date_range={"start": "2024-01-01", "end": "2024-12-31"},
        ),
        semantic_turn_act="refine_current_idea",
    )

    planned = await interpreter_module._audited_response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message="Keep those and add fictional moon fund with fees.",
            user=UserState(user_id="u1"),
        ),
        asset_resolution_context=json.dumps(
            {"all_traded_asset_mentions_accounted_for": False}
        ),
    )

    assert planned.intent == "conversation_followup"
    assert planned.requires_clarification is True
    assert planned.missing_required_fields == ["asset_universe", "assumption"]
    assert planned.assistant_response is None
    assert "artifact_assumption_edit_planned" in planned.reason_codes
    assert "provider_context_incomplete_asset_mentions" in planned.reason_codes


@pytest.mark.asyncio
async def test_artifact_edit_unsupported_followup_keeps_planner_explanation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    async def unsupported_plan_stub(**_: Any) -> LLMInterpretationResponse:
        return LLMInterpretationResponse(
            intent="conversation_followup",
            task_relation="continue",
            requires_clarification=True,
            user_goal_summary="The requested artifact edit is unsupported.",
            candidate_strategy_draft=LLMStrategyDraft(
                strategy_type="buy_and_hold",
                asset_universe=["AAPL", "MSFT", "NVDA", "AMZN", "META"],
                asset_class="equity",
                date_range={"start": "2024-01-01", "end": "2024-12-31"},
            ),
            assistant_response="I cannot apply that change to this artifact.",
            reason_codes=["artifact_assumption_edit_planned"],
            semantic_turn_act="unsupported_request",
        )

    monkeypatch.setattr(
        interpreter_module,
        "_ready_active_artifact_edit_planned_response",
        unsupported_plan_stub,
    )
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="refine",
        requires_clarification=False,
        user_goal_summary="User requested an unsupported artifact edit.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="buy_and_hold",
            asset_universe=["AAPL", "MSFT", "NVDA", "AMZN", "META"],
            asset_class="equity",
            date_range={"start": "2024-01-01", "end": "2024-12-31"},
        ),
        semantic_turn_act="refine_current_idea",
    )

    planned = await interpreter_module._audited_response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message="Add a setting this artifact cannot represent.",
            user=UserState(user_id="u1"),
        ),
        asset_resolution_context=json.dumps(
            {"all_traded_asset_mentions_accounted_for": False}
        ),
    )

    assert planned.intent == "conversation_followup"
    assert planned.semantic_turn_act == "unsupported_request"
    assert planned.assistant_response == "I cannot apply that change to this artifact."
    assert planned.missing_required_fields == []
    assert planned.reason_codes == ["artifact_assumption_edit_planned"]


@pytest.mark.asyncio
async def test_late_artifact_edit_clarification_keeps_incomplete_asset_blocker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    async def no_initial_plan_stub(**_: Any) -> None:
        return None

    async def late_plan_stub(**_: Any) -> LLMInterpretationResponse:
        return LLMInterpretationResponse(
            intent="conversation_followup",
            task_relation="continue",
            requires_clarification=True,
            user_goal_summary="The replayed artifact edit needs clarification.",
            candidate_strategy_draft=LLMStrategyDraft(
                strategy_type="buy_and_hold",
                asset_universe=["AAPL", "MSFT", "NVDA", "AMZN", "META"],
                asset_class="equity",
                date_range={"start": "2024-01-01", "end": "2024-12-31"},
            ),
            missing_required_fields=["assumption"],
            assistant_response="Which fee should I use?",
            reason_codes=["artifact_assumption_edit_planned"],
            semantic_turn_act="answer_pending_need",
        )

    monkeypatch.setattr(
        interpreter_module,
        "_ready_active_artifact_edit_planned_response",
        no_initial_plan_stub,
    )
    monkeypatch.setattr(
        interpreter_module,
        "_response_replays_prior_strategy_without_current_turn_update",
        lambda **_: True,
    )
    monkeypatch.setattr(
        interpreter_module,
        "_plan_artifact_edit_response",
        late_plan_stub,
    )
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="refine",
        requires_clarification=False,
        user_goal_summary="User refined an incomplete six-asset basket.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="buy_and_hold",
            asset_universe=["AAPL", "MSFT", "NVDA", "AMZN", "META"],
            asset_class="equity",
            date_range={"start": "2024-01-01", "end": "2024-12-31"},
        ),
        semantic_turn_act="refine_current_idea",
    )

    planned = await interpreter_module._audited_response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message="Keep those and add fictional moon fund with fees.",
            user=UserState(user_id="u1"),
        ),
        asset_resolution_context=json.dumps(
            {"all_traded_asset_mentions_accounted_for": False}
        ),
    )

    assert planned.missing_required_fields == ["asset_universe", "assumption"]
    assert planned.assistant_response is None
    assert "artifact_assumption_edit_planned" in planned.reason_codes
    assert "provider_context_incomplete_asset_mentions" in planned.reason_codes


@pytest.mark.asyncio
async def test_artifact_edit_planning_does_not_reconcile_inherited_assets_against_current_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    complete_current_message_context = json.dumps(
        {
            "asset_resolution_candidates": [
                {
                    "raw_text": "Microsoft",
                    "role": "traded_asset",
                    "status": "resolved",
                    "symbol": "MSFT",
                    "asset_class": "equity",
                    "name": "Microsoft Corporation",
                    "raw_symbol": "MSFT",
                    "provider": "alpaca",
                    "exchange": "NASDAQ",
                }
            ],
            "all_traded_asset_mentions_accounted_for": True,
        }
    )

    async def planned_response_stub(**kwargs: Any) -> LLMInterpretationResponse:
        normalized = kwargs["response"]
        assert normalized.candidate_strategy_draft.asset_universe == ["MSFT"]
        assert normalized.requires_clarification is False
        return LLMInterpretationResponse(
            intent="backtest_execution",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User added Microsoft to the active Apple idea.",
            candidate_strategy_draft=LLMStrategyDraft(
                strategy_type="buy_and_hold",
                asset_universe=["AAPL", "MSFT"],
                asset_class="equity",
                date_range={"start": "2024-01-01", "end": "2024-12-31"},
            ),
            reason_codes=["artifact_assumption_edit_planned"],
            semantic_turn_act="answer_pending_need",
        )

    monkeypatch.setattr(
        interpreter_module,
        "_ready_active_artifact_edit_planned_response",
        planned_response_stub,
    )
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="refine",
        requires_clarification=False,
        user_goal_summary="User mentioned Microsoft.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="buy_and_hold",
            asset_universe=["MSFT"],
            asset_class="equity",
            date_range={"start": "2024-01-01", "end": "2024-12-31"},
        ),
        semantic_turn_act="refine_current_idea",
    )

    planned = await interpreter_module._audited_response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message="Add Microsoft.",
            user=UserState(user_id="u1"),
        ),
        asset_resolution_context=complete_current_message_context,
    )

    assert planned.intent == "backtest_execution"
    assert planned.requires_clarification is False
    assert planned.candidate_strategy_draft.asset_universe == ["AAPL", "MSFT"]
    assert planned.missing_required_fields == []
    assert planned.ambiguous_fields == []
    assert planned.reason_codes == ["artifact_assumption_edit_planned"]


@pytest.mark.asyncio
@pytest.mark.parametrize("model_name", [None, "primary/model"])
async def test_model_failure_artifact_edit_keeps_incomplete_asset_blocker(
    monkeypatch: pytest.MonkeyPatch,
    model_name: str | None,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module
    from argus.agent_runtime.capabilities.contract import (
        build_default_capability_contract,
    )

    symbols = ["AAPL", "MSFT", "NVDA", "AMZN", "META"]
    incomplete_context = json.dumps(
        {
            "asset_resolution_candidates": [
                {
                    "raw_text": symbol,
                    "role": "traded_asset",
                    "status": "resolved",
                    "symbol": symbol,
                    "asset_class": "equity",
                    "name": symbol,
                    "raw_symbol": symbol,
                    "provider": "alpaca",
                    "exchange": "NASDAQ",
                }
                for symbol in symbols
            ],
            "all_traded_asset_mentions_accounted_for": False,
        }
    )

    async def provider_context_stub(**_: Any) -> str:
        return incomplete_context

    async def planner_stub(**_: Any) -> LLMInterpretationResponse:
        return LLMInterpretationResponse(
            intent="backtest_execution",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User refined the active five-asset idea.",
            candidate_strategy_draft=LLMStrategyDraft(
                strategy_type="buy_and_hold",
                asset_universe=symbols,
                asset_class="equity",
                date_range={"start": "2024-01-01", "end": "2024-12-31"},
            ),
            reason_codes=["artifact_assumption_edit_planned"],
            semantic_turn_act="answer_pending_need",
        )

    monkeypatch.setattr(
        interpreter_module,
        "provider_asset_resolution_context_for_request",
        provider_context_stub,
    )
    monkeypatch.setattr(
        interpreter_module,
        "_plan_pending_artifact_assumption_edit",
        planner_stub,
    )
    if model_name is None:
        monkeypatch.setattr(
            interpreter_module,
            "openrouter_structured_model_candidates",
            lambda: ["primary/model"],
        )

        async def invoke_stub(**_: Any) -> None:
            raise TimeoutError("structured model timed out")

        monkeypatch.setattr(
            interpreter_module,
            "invoke_openrouter_json_schema",
            invoke_stub,
        )
    else:

        class TimeoutStructuredModel:
            async def ainvoke(self, _messages: Any) -> None:
                raise TimeoutError("structured model timed out")

        class TimeoutChatModel:
            def with_structured_output(self, _schema: Any) -> TimeoutStructuredModel:
                return TimeoutStructuredModel()

        def resolve_model(
            requested_model: str | None = None,
            fallback: bool = False,
            *,
            task: Any = None,
        ) -> str:
            del task
            if requested_model:
                return requested_model
            return "fallback/model" if fallback else "primary/model"

        monkeypatch.setattr(
            interpreter_module,
            "build_openrouter_model",
            lambda *args, **kwargs: TimeoutChatModel(),
        )
        monkeypatch.setattr(
            "argus.llm.openrouter.resolve_openrouter_model",
            resolve_model,
        )

    result = await interpreter_module.OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract(),
        model_name=model_name,
    ).ainvoke(
        InterpretationRequest(
            current_user_message=(
                "Keep those five and add fictional moon fund for 2024."
            ),
            user=UserState(user_id="u1"),
        )
    )

    assert result is not None
    assert result.requires_clarification is True
    assert result.missing_required_fields == ["asset_universe"]
    assert "artifact_assumption_edit_planned" in result.reason_codes
    assert "provider_context_incomplete_asset_mentions" in result.reason_codes


def test_extractor_contract_can_report_sixth_overflow_mention() -> None:
    request = InterpretationRequest(
        current_user_message=(
            "Test Apple, Microsoft, NVIDIA, Amazon, Meta, and fictional moon fund."
        ),
        user=UserState(user_id="u1"),
    )

    prompt = _asset_mention_extraction_messages(request)[0]["content"]
    extraction_schema = LLMAssetMentionExtraction.model_json_schema()
    schema = extraction_schema["properties"]["asset_mentions"]

    assert "Return at most six distinct mentions" in prompt
    assert "preserve traded-asset and unknown spans before benchmark spans" in prompt
    assert "overflow evidence" not in prompt
    assert "provider context" not in prompt
    assert schema["maxItems"] == 6
    assert "at most six distinct asset-like mentions" in schema["description"]
    assert "overflow" not in schema["description"]
    assert "all_traded_asset_mentions_included" in extraction_schema["required"]
    assert "all_traded_asset_mentions_included" in prompt


def test_underfilled_provider_context_keeps_stale_asset_blocker() -> None:
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="Hold NVDA and MSFT.",
        assistant_response="Which asset should I test?",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="hold NVDA and MSFT this year",
            strategy_type="buy_and_hold",
            asset_universe=["NVDA", "MSFT"],
            asset_class="equity",
            capital_amount=4000,
        ),
        missing_required_fields=["asset_universe", "date_range"],
        semantic_turn_act="new_idea",
    )
    resolved_nvda_row = {
        "raw_text": "NVDA",
        "role": "traded_asset",
        "status": "resolved",
        "symbol": "NVDA",
        "asset_class": "equity",
        "name": "NVIDIA",
        "raw_symbol": "NVDA",
        "provider": "alpaca",
        "exchange": "NASDAQ",
    }

    normalized = response_with_provider_context_assets(
        response,
        asset_resolution_context=_context([resolved_nvda_row]),
    )

    assert set(normalized.candidate_strategy_draft.asset_universe) == {"NVDA", "MSFT"}
    assert normalized.missing_required_fields == ["asset_universe", "date_range"]
    assert normalized.requires_clarification is True
    assert normalized.assistant_response is None
    assert any(
        field.reason_code == "asset_resolution_context_underfilled"
        for field in normalized.ambiguous_fields
    )
    assert "provider_context_resolved_missing_asset" not in normalized.reason_codes
    assert "provider_context_partial_preserved_fuller_draft" in normalized.reason_codes


def test_ambiguous_runtime_context_never_becomes_executable_identity() -> None:
    ambiguous_row = {
        "raw_text": "Sun",
        "role": "traded_asset",
        "status": "ambiguous",
        "candidates": [
            {"symbol": "SUN", "asset_class": "equity"},
            {"symbol": "SUNE", "asset_class": "equity"},
        ],
    }
    normalized = response_with_provider_context_assets(
        _refusal_response_with_model_records(),
        asset_resolution_context=_context([ambiguous_row]),
        include_unsupported_request=True,
    )
    draft = normalized.candidate_strategy_draft
    extra = draft.extra_parameters or {}
    assert "provider_resolved_assets" not in extra
    assert draft.asset_universe == []


def test_benchmark_role_rows_never_become_provider_records() -> None:
    """PR #266 review T5 counter-evidence: typed benchmark rows stay out."""

    benchmark_row = {
        "raw_text": "S&P 500",
        "role": "benchmark",
        "status": "resolved",
        "symbol": "SPY",
        "asset_class": "equity",
        "name": "SPDR S&P 500",
        "raw_symbol": "SPY",
        "provider": "alpaca",
        "exchange": "ARCA",
    }
    normalized = response_with_provider_context_assets(
        _refusal_response_with_model_records(),
        asset_resolution_context=_context([benchmark_row]),
        include_unsupported_request=True,
    )
    draft = normalized.candidate_strategy_draft
    assert "provider_resolved_assets" not in (draft.extra_parameters or {})
    assert draft.asset_universe == []


def test_partial_basket_context_preserves_fuller_draft_without_model_records() -> None:
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="Hold NVDA and MSFT.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="buy_and_hold",
            asset_universe=["NVDA", "MSFT"],
            asset_class="equity",
            capital_amount=4000,
            extra_parameters={"provider_resolved_assets": [dict(FAKE_RECORD)]},
        ),
    )
    nvda_row = {
        "raw_text": "NVDA",
        "role": "traded_asset",
        "status": "resolved",
        "symbol": "NVDA",
        "asset_class": "equity",
        "name": "NVIDIA",
        "raw_symbol": "NVDA",
        "provider": "alpaca",
        "exchange": "NASDAQ",
    }
    normalized = response_with_provider_context_assets(
        response,
        asset_resolution_context=_context([nvda_row]),
        include_unsupported_request=True,
    )
    draft = normalized.candidate_strategy_draft
    # The fuller model draft is preserved; runtime records replace the fake one.
    assert set(draft.asset_universe) == {"NVDA", "MSFT"}
    records = (draft.extra_parameters or {}).get("provider_resolved_assets") or []
    assert [record["symbol"] for record in records] == ["NVDA"]
