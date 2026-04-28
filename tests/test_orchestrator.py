from __future__ import annotations

import pytest

from argus.domain import orchestrator
from argus.domain.orchestrator import (
    ChatOrchestrationDecision,
    StrategyExtraction,
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


def test_orchestrate_chat_turn_uses_heuristic_without_provider(monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("AGENT_MODEL", raising=False)
    monkeypatch.delenv("AGENT_FALLBACK_MODEL", raising=False)

    decision = orchestrator.orchestrate_chat_turn(
        message="Backtest Tesla dips",
        language="en",
        onboarding_required=False,
        primary_goal=None,
    )

    assert decision.intent == "run_backtest"
    assert decision.strategy_intent is not None
    assert decision.strategy_intent.template.value in orchestrator.SUPPORTED_TEMPLATES


def test_orchestrate_chat_turn_uses_fallback_model_after_primary_failure(
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("AGENT_MODEL", "primary-model")
    monkeypatch.setenv("AGENT_FALLBACK_MODEL", "fallback-model")

    calls: list[str] = []

    def _fake_extract(*, model_name: str, **kwargs) -> ChatOrchestrationDecision:  # type: ignore[no-untyped-def]
        calls.append(model_name)
        if model_name == "primary-model":
            raise RuntimeError("primary failed")
        return ChatOrchestrationDecision(
            intent="run_backtest",
            assistant_message="Fallback model reply",
            strategy_intent=orchestrator.StrategyIntent(
                template=orchestrator.SlotValue(
                    value="rsi_mean_reversion", source="user_supplied"
                ),
                asset_class=orchestrator.SlotValue(value="equity", source="user_supplied"),
                symbols=orchestrator.SlotValue(value=["TSLA"], source="user_supplied"),
            ),
        )

    monkeypatch.setattr(orchestrator, "_llm_extract_decision", _fake_extract)

    decision = orchestrator.orchestrate_chat_turn(
        message="Test Tesla dip",
        language="en",
        onboarding_required=False,
        primary_goal="test_stock_idea",
    )

    assert decision.intent == "run_backtest"
    assert decision.assistant_message == "Fallback model reply"
    assert calls == ["primary-model", "fallback-model"]


def test_parse_onboarding_goal_hidden_protocol() -> None:
    assert orchestrator.parse_onboarding_goal("__ONBOARDING_SKIP__") == "surprise_me"
    assert (
        orchestrator.parse_onboarding_goal("__ONBOARDING_GOAL__:build_passive_strategy")
        == "build_passive_strategy"
    )
    assert (
        orchestrator.parse_onboarding_goal("__ONBOARDING_GOAL__:passive_strategy") is None
    )
    assert orchestrator.parse_onboarding_goal("__ONBOARDING_GOAL__:unknown") is None


def test_plan_strategy_action() -> None:
    # Ready case
    plan = orchestrator.plan_strategy_action(
        intent=orchestrator.StrategyIntent(
            template=orchestrator.SlotValue(value="rsi_mean_reversion", source="user_supplied"),
            symbols=orchestrator.SlotValue(value=["AAPL"], source="user_supplied"),
            asset_class=orchestrator.SlotValue(value="equity", source="user_supplied"),
        ),
        language="en"
    )
    assert plan.action == "run_backtest"

    # Missing symbols
    missing_symbols = orchestrator.plan_strategy_action(
        intent=orchestrator.StrategyIntent(
            template=orchestrator.SlotValue(value="rsi_mean_reversion", source="user_supplied"),
            symbols=orchestrator.SlotValue(value=[], source="missing"),
        ),
        language="en"
    )
    assert missing_symbols.action == "ask_clarification"
    assert "symbols" in missing_symbols.missing_fields

    # Missing template
    missing_template = orchestrator.plan_strategy_action(
        intent=orchestrator.StrategyIntent(
            template=orchestrator.SlotValue(value=None, source="missing"),
            symbols=orchestrator.SlotValue(value=["AAPL"], source="user_supplied"),
        ),
        language="en"
    )
    assert missing_template.action == "ask_clarification"
    assert "template" in missing_template.missing_fields

    # Spanish prompt
    spanish = orchestrator.plan_strategy_action(
        intent=orchestrator.StrategyIntent(
            template=orchestrator.SlotValue(value="rsi_mean_reversion", source="user_supplied"),
            symbols=orchestrator.SlotValue(value=[], source="missing"),
        ),
        language="es-419"
    )
    assert "activos" in spanish.message or "símbolos" in spanish.message


def test_orchestrate_chat_turn_passes_history(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("AGENT_MODEL", "primary-model")

    captured_history: list[dict[str, str]] | None = None

    def _fake_extract(*, history: list[dict[str, str]] | None = None, **kwargs) -> ChatOrchestrationDecision:  # type: ignore[no-untyped-def]
        nonlocal captured_history
        captured_history = history
        return ChatOrchestrationDecision(
            intent="run_backtest",
            assistant_message="ok",
            strategy=StrategyExtraction(
                template="rsi_mean_reversion",
                symbols=["TSLA"],
                asset_class="equity",
                parameters={},
            ),
        )

    monkeypatch.setattr(orchestrator, "_llm_extract_decision", _fake_extract)

    history = [
        {"role": "user", "content": "Tell me about TSLA"},
        {"role": "assistant", "content": "TSLA is a stock."},
    ]

    orchestrator.orchestrate_chat_turn(
        message="Backtest it",
        language="en",
        onboarding_required=False,
        primary_goal=None,
        history=history,
    )

    assert captured_history == history


def test_orchestrate_chat_turn_fallback_honors_primary_goal(monkeypatch) -> None:
    # Force fallback by disabling LLM provider
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("AGENT_MODEL", raising=False)

    # Case 1: Explore Crypto goal
    decision = orchestrator.orchestrate_chat_turn(
        message="i", # No symbols here
        language="en",
        onboarding_required=False,
        primary_goal="explore_crypto",
    )
    assert decision.intent == "education"
    assert "crypto" in decision.assistant_message.lower()

    # Case 2: Learn Basics goal
    decision = orchestrator.orchestrate_chat_turn(
        message="i",
        language="en",
        onboarding_required=False,
        primary_goal="learn_basics",
    )
    assert decision.intent == "education"
    assert "beginner-friendly" in decision.assistant_message.lower()


def test_plan_strategy_action_honors_pending_questions() -> None:
    # User message with only symbol
    message = "Tell me about AAPL"
    extraction = StrategyExtraction(**orchestrator._heuristic_extract(message))
    history = [{"role": "user", "content": message}]
    intent = orchestrator.build_strategy_intent(extraction, history)

    # Should ask for template
    plan = orchestrator.plan_strategy_action(intent, language="en")
    assert plan.action == "ask_clarification"
    assert "template" in plan.missing_fields


def test_plan_strategy_action_requires_dca_cadence() -> None:
    # DCA without cadence
    message = "DCA into AAPL"
    extraction = StrategyExtraction(
        symbols=["AAPL"], template="dca_accumulation", asset_class="equity"
    )
    history = [{"role": "user", "content": "DCA into AAPL"}]
    intent = orchestrator.build_strategy_intent(extraction, history)

    # Should ask for dca_cadence
    plan = orchestrator.plan_strategy_action(intent, language="en")
    assert plan.action == "ask_clarification"
    assert "dca_cadence" in plan.missing_fields

    # Normal flow would re-extract, but here we simulate
    extraction.parameters = {"dca_cadence": "weekly"}
    intent = orchestrator.build_strategy_intent(extraction, history)

    # Assess readiness using the intent and history
    plan = orchestrator.plan_strategy_action(intent, language="en")
    assert plan.action == "run_backtest"


def test_build_capability_prompt() -> None:
    prompt = orchestrator.build_capability_prompt()
    assert "Argus Alpha can run these supported templates:" in prompt
    assert "buy_the_dip" in prompt
    assert "rsi_mean_reversion" in prompt
    assert "aliases=" in prompt
    assert "parameters=" in prompt
