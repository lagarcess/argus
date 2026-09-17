"""Current provider resolution owns the asset clarification, not a stale flag."""

import json

import pytest
from argus.agent_runtime.interpreter.asset_resolution_context import (
    provider_asset_resolution_context_from_extraction,
)
from argus.agent_runtime.interpreter.provider_context_assets import (
    response_with_provider_context_assets,
)
from argus.agent_runtime.llm_interpreter_types import (
    LLMAssetMentionExtraction,
    LLMInterpretationResponse,
    LLMStrategyDraft,
)
from argus.agent_runtime.resolution import resolve_asset_candidate
from argus.domain.market_data import assets


@pytest.fixture
def catalog(monkeypatch):
    records = {
        symbol: assets.ResolvedAsset(symbol, "equity", name, symbol, "provider_catalog")
        for symbol, name in [("MRNA", "Moderna Inc."), ("F", "Ford Motor Company")]
    }
    monkeypatch.setattr(assets, "_refresh_asset_cache_if_needed", lambda: None)
    monkeypatch.setattr(assets, "_ASSET_ALIAS_MAP", records)
    monkeypatch.setattr(
        assets, "_resolve_live_provider_ticker", lambda symbol: records.get(symbol)
    )
    return records


@pytest.mark.parametrize("symbol", ["MRNA", "F"])
@pytest.mark.parametrize("prefix", ["@", "$"])
def test_typed_symbol_notation_cannot_create_missing_asset(catalog, symbol, prefix):
    raw = prefix + symbol.lower()
    context = provider_asset_resolution_context_from_extraction(
        LLMAssetMentionExtraction(
            asset_mentions=[
                {
                    "raw_text": raw,
                    "role": "traded_asset",
                    "mention_kind": "ticker",
                    "confidence": 1,
                }
            ],
            all_traded_asset_mentions_included=True,
        ),
        resolve_asset_candidate=resolve_asset_candidate,
    )
    payload = json.loads(context)
    assert payload["all_traded_asset_mentions_accounted_for"] is True
    assert payload["asset_resolution_candidates"][0]["symbol"] == symbol
    assert payload["asset_resolution_candidates"][0]["raw_text"] == raw


@pytest.mark.parametrize("capital", [None, 100])
def test_current_complete_resolution_retires_its_previous_blocker(catalog, capital):
    context = provider_asset_resolution_context_from_extraction(
        LLMAssetMentionExtraction(
            asset_mentions=[
                {
                    "raw_text": "MRNA",
                    "role": "traded_asset",
                    "mention_kind": "ticker",
                    "confidence": 1,
                }
            ],
            all_traded_asset_mentions_included=True,
        ),
        resolve_asset_candidate=resolve_asset_candidate,
    )
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="Test the stock",
        candidate_strategy_draft=LLMStrategyDraft(
            asset_universe=["MRNA"],
            asset_class="equity",
            strategy_type="buy_and_hold",
            capital_amount=capital,
            date_range={"start": "2026-08-16", "end": "2026-08-19"},
        ),
        missing_required_fields=[
            "asset_universe",
            *(["capital_amount"] if capital is None else []),
        ],
        reason_codes=["provider_context_incomplete_asset_mentions"],
    )
    resolved = response_with_provider_context_assets(
        response, asset_resolution_context=context
    )
    expected_missing = ["capital_amount"] if capital is None else []
    assert resolved.missing_required_fields == expected_missing
    assert resolved.requires_clarification is (capital is None)
    assert "provider_context_incomplete_asset_mentions" not in resolved.reason_codes

    from argus.agent_runtime.interpreter.strategy_builder import _strategy_from_llm
    from argus.agent_runtime.stages.interpret import (
        StructuredInterpretation,
        interpret_stage,
    )
    from argus.agent_runtime.state.models import RunState, UserState

    interpretation = StructuredInterpretation(
        intent=resolved.intent,
        task_relation=resolved.task_relation,
        requires_clarification=resolved.requires_clarification,
        user_goal_summary=resolved.user_goal_summary,
        candidate_strategy_draft=_strategy_from_llm(
            resolved.candidate_strategy_draft, "Test MRNA"
        ),
        missing_required_fields=resolved.missing_required_fields,
        reason_codes=resolved.reason_codes,
    )
    stage = interpret_stage(
        state=RunState.new(current_user_message="Test MRNA", recent_thread_history=[]),
        user=UserState(user_id="guest:resolved-reason"),
        latest_task_snapshot=None,
        structured_interpreter=lambda request: interpretation,
    )
    from argus.agent_runtime.capabilities.contract import (
        build_default_capability_contract,
    )
    from argus.agent_runtime.strategy_requirements import (
        missing_required_fields_for_strategy,
    )

    canonical_missing = missing_required_fields_for_strategy(
        stage.decision.candidate_strategy_draft,
        contract=build_default_capability_contract(),
    )
    assert stage.decision.missing_required_fields == canonical_missing
    assert "asset_universe" not in canonical_missing
    assert stage.patch.get("requested_field") == (
        canonical_missing[0] if canonical_missing else None
    )
