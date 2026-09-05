"""Every reader of a completed result quotes the engine's benchmark gap (#533).

The engine rounds the two returns and publishes their difference beside them
as ``delta_vs_benchmark_pct``. Subtracting the rounded returns again can land a
tenth of a point away, so the card said 46.4 while the Quick Take, the
deterministic readout, and the Try next reason said 46.3 on one screen.
"""

from __future__ import annotations

import pytest
from argus.agent_runtime.stages.explain import (
    _quick_take_fact_bank,
    _quick_take_relative_truth,
    explain_stage,
)
from argus.agent_runtime.state.models import ResponseProfile, RunState
from argus.domain.backtesting.cards import build_result_card

# The issue's own shape: 53.44 - 7.1 = 46.34 prints 46.3, the engine gap
# 46.35 prints 46.4.
TOTAL_RETURN_PCT = 53.44
BENCHMARK_RETURN_PCT = 7.1
ENGINE_DELTA_PCT = 46.35


def _engine_metrics(delta: float = ENGINE_DELTA_PCT) -> dict[str, object]:
    return {
        "aggregate": {
            "performance": {
                "total_return_pct": TOTAL_RETURN_PCT,
                "benchmark_return_pct": BENCHMARK_RETURN_PCT,
                "delta_vs_benchmark_pct": delta,
                "profit": 534.4,
            },
            "risk": {"max_drawdown_pct": -18.35},
            "efficiency": {"win_rate": 0.0, "total_trades": 1},
        }
    }


def _explanation_context(delta: float = ENGINE_DELTA_PCT) -> dict[str, object]:
    return {
        "metrics": _engine_metrics(delta),
        "benchmark_metrics": {"aggregate": {"total_return_pct": BENCHMARK_RETURN_PCT}},
        "benchmark_symbol": "SPY",
    }


def _card_comparison() -> str:
    card = build_result_card(
        {
            "template": "buy_and_hold",
            "asset_class": "equity",
            "symbols": ["AAPL"],
            "start_date": "2023-01-03",
            "end_date": "2024-12-31",
            "starting_capital": 1_000,
            "benchmark_symbol": "SPY",
        },
        _engine_metrics(),
    )
    return next(row["value"] for row in card["rows"] if row["key"] == "benchmark_delta")


def _completed_state(explanation_context: dict[str, object]) -> RunState:
    state = RunState.new(current_user_message="run it", recent_thread_history=[])
    state.effective_response_profile = ResponseProfile(
        effective_tone="concise",
        effective_verbosity="low",
        effective_expertise_mode="advanced",
    )
    state.confirmation_payload = {
        "strategy": {"strategy_thesis": "Hold AAPL"},
        "optional_parameters": {},
    }
    state.final_response_payload = {
        "result": {"metrics": explanation_context["metrics"]},
        "explanation_context": explanation_context,
    }
    return state


def test_quick_take_facts_quote_the_card_gap_not_a_subtraction() -> None:
    facts = _quick_take_fact_bank(
        context={},
        result_payload={},
        explanation_context=_explanation_context(),
        language="en",
    )

    assert _card_comparison() == "Beat by 46.4 percentage points"
    assert facts["benchmark_comparison"] == _card_comparison()
    assert facts["benchmark_delta_magnitude"] == "46.4 percentage points"
    assert facts["total_return"] == "+53.4%"
    assert facts["benchmark_return"] == "+7.1%"


def test_deterministic_readout_and_try_next_reason_quote_the_engine_gap() -> None:
    result = explain_stage(state=_completed_state(_explanation_context()))

    readout = result.patch["assistant_response"]
    assert "outperformed by 46.4 percentage points" in readout
    assert "46.3" not in readout
    assert result.patch["next_experiments"]["rows"][0]["why"] == {
        "code": "beat_benchmark",
        "params": {"points": 46.4},
    }


@pytest.mark.parametrize(
    ("delta", "claim"),
    [(0.06, "beat_benchmark"), (-0.06, "lagged_benchmark"), (0.02, "matched_benchmark")],
)
def test_relative_truth_follows_the_engine_gap_not_the_rounded_returns(
    delta: float, claim: str
) -> None:
    # 53.44 - 7.1 stays 46.34 whatever the engine gap says; the claim the LLM
    # draft is held to must come from the gap itself.
    context = _explanation_context(delta)
    assert (
        _quick_take_relative_truth(result_payload={}, explanation_context=context)
        == claim
    )


def test_an_engine_block_without_its_gap_makes_no_comparison_claim() -> None:
    context = _explanation_context()
    del context["metrics"]["aggregate"]["performance"]["delta_vs_benchmark_pct"]

    facts = _quick_take_fact_bank(
        context={}, result_payload={}, explanation_context=context, language="en"
    )
    result = explain_stage(state=_completed_state(context))

    assert "benchmark_comparison" not in facts
    assert "benchmark_delta_magnitude" not in facts
    assert facts["total_return"] == "+53.4%"
    assert _quick_take_relative_truth(result_payload={}, explanation_context=context) == (
        "unknown"
    )
    readout = result.patch["assistant_response"]
    assert readout.startswith(
        "The strategy returned 53.4% while SPY returned 7.1% for the comparison window."
    )
    assert "percentage points" not in readout
    assert all("why" not in row for row in result.patch["next_experiments"]["rows"])


def test_legacy_fraction_payloads_still_derive_their_only_comparison() -> None:
    # Offline tools publish two fractions and no engine block; their
    # difference is the only comparison that shape carries.
    facts = _quick_take_fact_bank(
        context={},
        result_payload={"total_return": 0.14, "benchmark_return": 0.09},
        explanation_context={},
        language="en",
    )

    assert facts["benchmark_comparison"] == "Beat by 5.0 percentage points"
