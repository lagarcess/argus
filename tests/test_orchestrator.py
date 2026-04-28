from __future__ import annotations

from typing import Any

import pytest
from argus.domain import orchestrator
from argus.domain.market_data.assets import ResolvedAsset
from argus.domain.orchestrator import (
    ChatTurnIntent,
    ExtractedSlot,
    SlotValue,
    StrategyDraft,
    StrategyIntentExtraction,
)


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


def test_dca_followup_reconstructs_slots_from_history_without_metadata(monkeypatch) -> None:
    def _empty_extract(message: str, model_name: str, history: list[dict[str, Any]] | None = None) -> StrategyIntentExtraction:
        return StrategyIntentExtraction()

    monkeypatch.setattr(orchestrator, "_extract_strategy_intent", _empty_extract)

    history = [
        {"role": "user", "content": "How would a simple DCA strategy perform on Tesla?"},
        {"role": "assistant", "content": "How often do you want Argus to buy: daily, weekly, or monthly?"},
        {"role": "user", "content": "weeklu"},
        {"role": "assistant", "content": "To run the DCA backtest, I need starting capital and timeframe."},
        {"role": "user", "content": "10k and one year, based on YTD"},
        {"role": "assistant", "content": "Please provide exact dates."},
        {"role": "user", "content": "take today as the ending date, and exactly a year back from today"},
        {"role": "assistant", "content": "How often do you want Argus to buy: daily, weekly, or monthly?"},
    ]

    decision = orchestrator.orchestrate_chat_turn(
        message="daily",
        history=history,
        language="en",
    )

    assert decision.intent == "run_backtest"
    assert decision.strategy_draft is not None
    assert decision.strategy_draft.template.value == "dca_accumulation"
    assert decision.strategy_draft.symbols.value == ["TSLA"]
    assert decision.strategy_draft.starting_capital.value == 10000
    assert decision.strategy_draft.parameters["dca_cadence"].value == "daily"


def test_neutral_message_is_answer_not_backtest_clarification(monkeypatch) -> None:
    def _empty_extract(
        message: str,
        model_name: str,
        history: list[dict[str, Any]] | None = None,
    ) -> StrategyIntentExtraction:
        return StrategyIntentExtraction()

    monkeypatch.setattr(orchestrator, "_extract_strategy_intent", _empty_extract)

    decision = orchestrator.orchestrate_chat_turn(
        message="hey",
        history=[],
        language="en",
    )

    assert decision.intent == "answer"
    assert decision.strategy_draft is None
    assert "strategy" not in decision.assistant_message.lower()


def test_chat_turn_intent_does_not_use_regex_fallback_without_provider(monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    def _fail_regex(message: str) -> StrategyIntentExtraction:  # noqa: ARG001
        raise AssertionError("regex fallback should not be used for chat intent")

    monkeypatch.setattr(orchestrator, "_extract_deterministic_intent", _fail_regex)

    intent = orchestrator.classify_chat_turn_intent(
        message="quiero ejecutar una estrategia",
        language="es-419",
    )

    assert intent.intent == "guide"
    assert intent.assistant_guidance_seed == "intent_unavailable"


def test_chat_turn_intent_does_not_use_regex_fallback_after_provider_failure(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    def _fail_model(model_name: str) -> object:  # noqa: ARG001
        raise RuntimeError("provider unavailable")

    def _fail_regex(message: str) -> StrategyIntentExtraction:  # noqa: ARG001
        raise AssertionError("regex fallback should not be used after provider failure")

    monkeypatch.setattr(orchestrator, "_build_model", _fail_model)
    monkeypatch.setattr(orchestrator, "_extract_deterministic_intent", _fail_regex)

    intent = orchestrator.classify_chat_turn_intent(
        message="quiero ejecutar una estrategia",
        language="es-419",
    )

    assert intent.intent == "guide"
    assert intent.assistant_guidance_seed == "intent_unavailable"


def test_setup_without_extracted_fields_gets_strategy_choices() -> None:
    message = orchestrator.assistant_message_for_chat_turn(
        ChatTurnIntent(intent="setup"),
        "quiero ejecutar una estrategia",
        "es-419",
    )

    assert "probar una estrategia" in message.lower()
    assert "comprar y mantener" in message.lower()
