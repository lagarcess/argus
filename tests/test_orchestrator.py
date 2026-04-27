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
