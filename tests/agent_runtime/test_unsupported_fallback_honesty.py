"""Degraded unsupported-recovery copy must state the real capability boundary.

Invariant under test: when clarification generation fails, the deterministic
fallback may not claim a recognized strategy "does not define when to buy or
sell" — that is only true of genuinely incomplete rules, and no unsupported
reason code represents that situation. The fallback speaks from the typed
reason code alone; user prose is never inspected.
"""

from __future__ import annotations

from argus.agent_runtime.capabilities.contract import (
    build_default_capability_contract,
)
from argus.agent_runtime.stages.clarify import clarify_stage
from argus.agent_runtime.state.models import RunState, StrategySummary

MOMENTUM_MESSAGE = (
    "Backtest $10,000 in AAPL from January 2, 2022 through January 2, 2025 "
    "using a momentum breakout strategy."
)
NEWS_MESSAGE = (
    "Backtest $10,000 in AAPL, buying when news sentiment turns positive and "
    "selling when it turns negative."
)

_SUPPORTED_ALTERNATIVE_OPTIONS = [
    {
        "label": "Use a supported RSI threshold rule",
        "replacement_values": {"simplify_logic": "rsi_only"},
    },
    {
        "label": "Compare with buy and hold",
        "replacement_values": {"strategy_type": "buy_and_hold"},
    },
    {
        "label": "Use a supported moving-average crossover",
        "replacement_values": {
            "strategy_type": "signal_strategy",
            "rule_family": "moving_average_crossover",
        },
    },
]


class RecordingClarifier:
    def __init__(self, question: str | None) -> None:
        self.question = question
        self.requests: list[object] = []

    def __call__(self, request):
        self.requests.append(request)
        return self.question


def _unsupported_state(
    *,
    message: str,
    category: str,
    raw_value: str,
    explanation: str,
) -> RunState:
    state = RunState.new(current_user_message=message, recent_thread_history=[])
    state.intent = "strategy_drafting"
    state.candidate_strategy_draft = StrategySummary(
        strategy_type="signal_strategy",
        asset_universe=["AAPL"],
        asset_class="equity",
        capital_amount=10000,
    )
    state.optional_parameter_status = {
        "unsupported_constraints": [
            {
                "category": category,
                "raw_value": raw_value,
                "explanation": explanation,
                "simplification_options": list(_SUPPORTED_ALTERNATIVE_OPTIONS),
            }
        ]
    }
    return state


def test_momentum_generation_failure_fallback_is_capability_honest() -> None:
    """A recognized momentum breakout defines its own entries and exits; the
    degraded copy must say Argus cannot run it, not that it is undefined."""

    result = clarify_stage(
        state=_unsupported_state(
            message=MOMENTUM_MESSAGE,
            category="unsupported_strategy_logic",
            raw_value="a momentum breakout strategy",
            explanation="Momentum breakout rules are not executable yet.",
        ),
        contract=build_default_capability_contract(),
        clarification_generator=RecordingClarifier(None),
        language="en",
    )
    prompt = result.patch["assistant_prompt"]
    assert result.outcome == "await_user_reply"
    assert "does not define" not in prompt
    assert "a momentum breakout strategy" in prompt
    assert "can't run" in prompt
    assert "Use a supported RSI threshold rule" in prompt
    assert "Compare with buy and hold" in prompt
    assert "Use a supported moving-average crossover" in prompt
    clarification = result.patch["clarification"]
    assert clarification["kind"] == "unsupported_recovery"
    assert clarification["reason_code"] == "unsupported_strategy_logic"
    assert clarification["prompt_source"] == "degraded_fallback"
    assert [option["id"] for option in clarification["options"]] == [
        "rsi_threshold",
        "buy_and_hold",
        "moving_average_crossover",
    ]
    assert result.patch.get("confirmation_payload") is None


def test_news_sentiment_generation_failure_fallback_is_capability_honest() -> None:
    """A typed news/sentiment reason gets the news boundary statement without
    claiming the rule is undefined or that any news access exists."""

    result = clarify_stage(
        state=_unsupported_state(
            message=NEWS_MESSAGE,
            category="sentiment_news_rule",
            raw_value="buying when news sentiment turns positive",
            explanation="News and sentiment execution rules are not supported.",
        ),
        contract=build_default_capability_contract(),
        clarification_generator=RecordingClarifier(None),
        language="en",
    )
    prompt = result.patch["assistant_prompt"]
    assert result.outcome == "await_user_reply"
    assert "does not define" not in prompt
    assert "news or sentiment" in prompt
    assert "can't test" in prompt
    assert "Search" not in prompt
    assert "Use a supported RSI threshold rule" in prompt
    clarification = result.patch["clarification"]
    assert clarification["reason_code"] == "sentiment_news_rule"
    assert clarification["prompt_source"] == "degraded_fallback"
    assert result.patch.get("confirmation_payload") is None


def test_other_unsupported_reasons_never_claim_rule_is_undefined() -> None:
    """No unsupported reason code represents an incomplete rule, so the
    "does not define" claim may not survive for any category."""

    result = clarify_stage(
        state=_unsupported_state(
            message="Backtest AAPL with a max drawdown guard of 3%.",
            category="risk_control_rule",
            raw_value="a max drawdown guard of 3%",
            explanation="Risk-control overlays are not executable yet.",
        ),
        contract=build_default_capability_contract(),
        clarification_generator=RecordingClarifier(None),
        language="en",
    )
    prompt = result.patch["assistant_prompt"]
    assert "does not define" not in prompt
    assert "a max drawdown guard of 3%" in prompt
    assert result.patch["clarification"]["prompt_source"] == "degraded_fallback"


def test_future_and_granularity_fallbacks_are_unchanged() -> None:
    future_state = _unsupported_state(
        message="What will BTC be worth in ten years?",
        category="future_performance",
        raw_value="in ten years",
        explanation="Argus cannot predict future performance.",
    )
    future_result = clarify_stage(
        state=future_state,
        contract=build_default_capability_contract(),
        clarification_generator=RecordingClarifier(None),
        language="en",
    )
    future_prompt = future_result.patch["assistant_prompt"]
    assert "cannot predict future performance" in future_prompt

    granularity_state = _unsupported_state(
        message="Backtest AAPL on 5-minute bars.",
        category="unsupported_time_granularity",
        raw_value="5-minute bars",
        explanation="Only daily or 1-hour bars are supported.",
    )
    granularity_result = clarify_stage(
        state=granularity_state,
        contract=build_default_capability_contract(),
        clarification_generator=RecordingClarifier(None),
        language="en",
    )
    granularity_prompt = granularity_result.patch["assistant_prompt"]
    assert "5-minute bars is not a supported bar size." in granularity_prompt


def test_successful_generation_still_owns_the_voice() -> None:
    """The degraded copy is failure-only: model-generated recovery prose is
    carried byte-exactly when generation succeeds."""

    generated = "Argus can't run momentum breakouts yet - want a supported test?"
    result = clarify_stage(
        state=_unsupported_state(
            message=MOMENTUM_MESSAGE,
            category="unsupported_strategy_logic",
            raw_value="a momentum breakout strategy",
            explanation="Momentum breakout rules are not executable yet.",
        ),
        contract=build_default_capability_contract(),
        clarification_generator=RecordingClarifier(generated),
        language="en",
    )
    assert result.patch["assistant_prompt"] == generated
    assert result.patch["clarification"]["prompt_source"] == "llm_generated"
