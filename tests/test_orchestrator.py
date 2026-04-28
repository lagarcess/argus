from __future__ import annotations

import pytest
from typing import Any
from pydantic import BaseModel

from argus.domain import orchestrator
from argus.domain.orchestrator import (
    ChatOrchestrationDecision,
    StrategyIntentExtraction,
    StrategyDraft,
    SlotValue,
    ExtractedSlot,
)
from argus.domain.market_data.assets import ResolvedAsset

@pytest.fixture(autouse=True)
def mock_resolve_asset(monkeypatch):
    def _fake_resolve(symbol: str) -> ResolvedAsset:
        return ResolvedAsset(
            canonical_symbol=symbol.upper(),
            asset_class="equity",
            name=symbol,
            raw_symbol=symbol
        )
    monkeypatch.setattr(orchestrator, "resolve_asset", _fake_resolve)


def test_orchestrate_chat_turn_without_history(monkeypatch) -> None:
    # Disable LLM to force empty extraction
    def _fake_extract(message: str, model_name: str) -> StrategyIntentExtraction:
        return StrategyIntentExtraction(
            template=ExtractedSlot(value="buy_the_dip", confidence=1.0),
            symbols=ExtractedSlot(value=["TSLA"], confidence=1.0),
        )
    monkeypatch.setattr(orchestrator, "_extract_strategy_intent", _fake_extract)

    decision = orchestrator.orchestrate_chat_turn(
        message="Backtest Tesla dips",
        language="en",
        onboarding_required=False,
        primary_goal=None,
    )

    assert decision.intent == "run_backtest"
    assert decision.strategy_draft is not None
    assert decision.strategy_draft.template.value == "buy_the_dip"
    assert decision.strategy_draft.symbols.value == ["TSLA"]


def test_orchestrate_chat_turn_merges_history(monkeypatch) -> None:
    # 1. First turn: only symbols
    def _fake_extract_1(message: str, model_name: str) -> StrategyIntentExtraction:
        return StrategyIntentExtraction(
            symbols=ExtractedSlot(value=["AAPL"], confidence=1.0),
        )
    monkeypatch.setattr(orchestrator, "_extract_strategy_intent", _fake_extract_1)

    history = []
    decision1 = orchestrator.orchestrate_chat_turn(
        message="Apple",
        history=history,
        language="en",
    )
    assert decision1.intent == "clarify"
    assert "strategy" in decision1.assistant_message.lower() or "estrategia" in decision1.assistant_message.lower()
    
    # 2. Second turn: only template
    def _fake_extract_2(message: str, model_name: str) -> StrategyIntentExtraction:
        return StrategyIntentExtraction(
            template=ExtractedSlot(value="buy_the_dip", confidence=1.0),
        )
    monkeypatch.setattr(orchestrator, "_extract_strategy_intent", _fake_extract_2)

    # Simulate history with the previous draft in metadata
    history = [
        {"role": "user", "content": "Apple"},
        {"role": "assistant", "content": "What strategy?", "metadata": {"strategy_draft": decision1.strategy_draft.model_dump()}}
    ]
    
    decision2 = orchestrator.orchestrate_chat_turn(
        message="Buy the dip",
        history=history,
        language="en",
    )
    
    assert decision2.intent == "run_backtest"
    assert decision2.strategy_draft.template.value == "buy_the_dip"
    assert decision2.strategy_draft.symbols.value == ["AAPL"]


def test_plan_draft_action_parameter_clarification() -> None:
    # DCA without cadence
    draft = StrategyDraft(
        template=SlotValue(value="dca_accumulation", source="user_supplied"),
        symbols=SlotValue(value=["BTC"], source="user_supplied"),
        asset_class=SlotValue(value="crypto", source="backend_default"),
    )
    
    plan = orchestrator.plan_draft_action(draft, language="en")
    assert plan.action == "ask_clarification"
    assert "dca_cadence" in plan.missing_fields
    assert "daily, weekly, or monthly" in plan.message.lower() or "Argus makes a fixed-dollar purchase" in plan.message


def test_normalize_symbols_mappings() -> None:
    assert orchestrator.normalize_symbols(["Tesla", "Apple"]) == ["TSLA", "AAPL"]
    assert orchestrator.normalize_symbols(["Bitcoin"]) == ["BTC"]
    assert orchestrator.normalize_symbols(["BTCUSD", "ETH/USD"]) == ["BTCUSD", "ETH/USD"]


def test_infer_asset_class() -> None:
    assert orchestrator.infer_asset_class(["AAPL", "TSLA"]) == "equity"
    assert orchestrator.infer_asset_class(["BTC"]) == "crypto"
    assert orchestrator.infer_asset_class(["ETHUSD"]) == "crypto"


def test_compile_backtest_payload_defaults() -> None:
    draft = StrategyDraft(
        template=SlotValue(value="buy_the_dip", source="user_supplied"),
        symbols=SlotValue(value=["TSLA"], source="user_supplied"),
    )
    payload = orchestrator.compile_backtest_payload(draft)
    assert payload["template"] == "buy_the_dip"
    assert payload["asset_class"] == "equity"
    assert payload["benchmark_symbol"] == "SPY"
    assert payload["starting_capital"] == 10000
    assert "start_date" in payload
    assert "end_date" in payload


def test_canonical_template_aliases() -> None:
    assert orchestrator.canonical_template("buy the dip") == "buy_the_dip"
    assert orchestrator.canonical_template("rsi") == "rsi_mean_reversion"
    assert orchestrator.canonical_template("dca") == "dca_accumulation"
    assert orchestrator.canonical_template("unknown") is None
