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
        extracted={"symbols": ["AAPL"], "template": "rsi_mean_reversion"}
    )
    assert ready.ready_to_run is True

    # Missing symbols
    missing_symbols = orchestrator.assess_strategy_readiness(
        extracted={"symbols": [], "template": "rsi_mean_reversion"}
    )
    assert missing_symbols.ready_to_run is False
    assert "symbols" in missing_symbols.missing_fields

    # Missing template
    missing_template = orchestrator.assess_strategy_readiness(
        extracted={"symbols": ["AAPL"], "template": None}
    )
    assert missing_template.ready_to_run is False
    assert "template" in missing_template.missing_fields

    # Spanish prompt
    spanish = orchestrator.assess_strategy_readiness(
        extracted={"symbols": []}, language="es-419"
    )
    assert "¿Que simbolo" in spanish.clarification_prompt or "Que simbolo" in spanish.clarification_prompt


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
