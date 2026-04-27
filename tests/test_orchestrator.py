from __future__ import annotations

from argus.domain import orchestrator
from argus.domain.orchestrator import (
    ChatOrchestrationDecision,
    StrategyExtraction,
)


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
    assert decision.strategy is not None
    assert decision.strategy.template in orchestrator.SUPPORTED_TEMPLATES


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
            strategy=StrategyExtraction(
                template="rsi_mean_reversion",
                asset_class="equity",
                symbols=["TSLA"],
                parameters={},
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


def test_assess_strategy_readiness() -> None:
    # Ready case
    ready = orchestrator.assess_strategy_readiness(
        extracted=StrategyExtraction(symbols=["AAPL"], template="rsi_mean_reversion", asset_class="equity"),
        language="en"
    )
    assert ready.ready_to_run is True

    # Missing symbols
    missing_symbols = orchestrator.assess_strategy_readiness(
        extracted=StrategyExtraction(symbols=[], template="rsi_mean_reversion", asset_class="equity"),
        language="en"
    )
    assert missing_symbols.ready_to_run is False
    assert "symbols" in missing_symbols.missing_fields

    # Missing template
    missing_template = orchestrator.assess_strategy_readiness(
        extracted=StrategyExtraction(symbols=["AAPL"], template=None, asset_class="equity"),
        language="en"
    )
    assert missing_template.ready_to_run is False
    assert "template" in missing_template.missing_fields

    # Spanish prompt
    spanish = orchestrator.assess_strategy_readiness(
        extracted=StrategyExtraction(symbols=[], template="rsi_mean_reversion", asset_class="equity"), 
        language="es-419"
    )
    assert "símbolos" in spanish.clarification_prompt or "simbolos" in spanish.clarification_prompt


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

    # Case 1: Explore Crypto goal
    decision = orchestrator.orchestrate_chat_turn(
        message="i", # No symbols here
        language="en",
        onboarding_required=False,
        primary_goal="explore_crypto",
    )
    assert decision.intent == "unsupported_request"
    assert "crypto" in decision.assistant_message.lower()

    # Case 2: Learn Basics goal
    decision = orchestrator.orchestrate_chat_turn(
        message="i",
        language="en",
        onboarding_required=False,
        primary_goal="learn_basics",
    )
    assert decision.intent == "unsupported_request"
    assert "beginner-friendly" in decision.assistant_message.lower()


def test_decide_run_readiness_honors_pending_questions() -> None:
    # Scenario: Assistant asked for dates, user didn't provide them.
    history = [
        {"role": "user", "content": "Test BTC"},
        {"role": "assistant", "content": "I can test BTC. For what period do you want to run it?"},
    ]

    # User just says "buy the dip" without dates
    draft = orchestrator.StrategyRunDraft(
        symbols=orchestrator.SlotValue(value=["BTC"], source="history_inferred"),
        template=orchestrator.SlotValue(value="buy_the_dip", source="user_supplied"),
        timeframe=orchestrator.SlotValue(value="1D", source="backend_default"),
        start_date=orchestrator.SlotValue(value="2024-01-01", source="backend_default"),
    )

    readiness = orchestrator.decide_run_readiness(draft, history, language="en")

    assert readiness.ready_to_run is False
    assert "time_preferences" in readiness.missing_fields
    assert "period" in readiness.clarification_prompt.lower()

    # Scenario: User explicitly says "use defaults"
    history.append({"role": "user", "content": "use standard defaults"})
    # Re-build draft logic would normally handle this, but for test we simulate
    readiness = orchestrator.decide_run_readiness(draft, history, language="en")
    assert readiness.ready_to_run is True


def test_decide_run_readiness_requires_dca_cadence() -> None:
    # Scenario: User says "DCA into BTC", but doesn't specify cadence.
    extraction = orchestrator.StrategyExtraction(
        symbols=["BTC"], 
        template="dca_accumulation", 
        asset_class="crypto"
    )
    history = [{"role": "user", "content": "DCA into BTC"}]
    draft = orchestrator.build_strategy_draft(extraction, history)
    
    readiness = orchestrator.decide_run_readiness(draft, history, language="en")
    
    assert readiness.ready_to_run is False
    assert "dca_cadence" in readiness.missing_fields
    assert "often" in readiness.clarification_prompt.lower()

    # Scenario: User specifies cadence
    history.append({"role": "user", "content": "weekly"})
    # Normal flow would re-extract, but here we simulate
    extraction.parameters = {"dca_cadence": "weekly"}
    draft = orchestrator.build_strategy_draft(extraction, history)
    
    readiness = orchestrator.decide_run_readiness(draft, history, language="en")
    assert readiness.ready_to_run is True
