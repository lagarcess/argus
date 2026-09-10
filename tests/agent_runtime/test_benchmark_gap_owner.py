"""Every reader of a completed result quotes the engine's benchmark gap (#533).

The engine rounds the two returns and publishes their difference beside them
as ``delta_vs_benchmark_pct``. Subtracting the rounded returns again can land a
tenth of a point away, so the card said 46.4 while the Quick Take, the
deterministic readout, and the Try next reason said 46.3 on one screen.
"""

from __future__ import annotations

import json

import pytest
from argus.agent_runtime.stages import explain as explain_module
from argus.agent_runtime.stages.explain import explain_stage
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


async def _composer_facts(monkeypatch, state: RunState) -> dict[str, object]:
    captured: dict[str, object] = {}
    text = "The ride was uneven."

    async def draft(**kwargs):
        captured.update(json.loads(kwargs["messages"][1]["content"])["run_facts"])
        return {"text": text}

    monkeypatch.setattr(explain_module, "invoke_openrouter_json_schema", draft)
    result = await explain_module.explain_stage_async(state=state)
    assert result.patch["assistant_response"] == text
    assert result.patch["assistant_response_fallback_used"] is False
    return captured


@pytest.mark.asyncio
async def test_quick_take_facts_quote_the_card_gap_not_a_subtraction(monkeypatch) -> None:
    facts = await _composer_facts(monkeypatch, _completed_state(_explanation_context()))

    assert _card_comparison() == "Beat by 46.4 percentage points"
    assert facts["comparison"] == {
        "delta_vs_benchmark_pct": ENGINE_DELTA_PCT,
        "total_return_pct": TOTAL_RETURN_PCT,
        "benchmark_return_pct": BENCHMARK_RETURN_PCT,
    }
    assert facts["comparison"]["delta_vs_benchmark_pct"] != pytest.approx(
        TOTAL_RETURN_PCT - BENCHMARK_RETURN_PCT
    )


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
@pytest.mark.asyncio
async def test_relative_truth_follows_the_engine_gap_not_the_rounded_returns(
    monkeypatch, delta: float, claim: str
) -> None:
    # 53.44 - 7.1 stays 46.34 whatever the engine gap says; the claim the LLM
    # draft is held to must come from the gap itself.
    context = _explanation_context(delta)
    facts = await _composer_facts(monkeypatch, _completed_state(context))
    assert facts["benchmark_comparison_claim"] == claim


@pytest.mark.asyncio
async def test_an_engine_block_without_its_gap_makes_no_comparison_claim(
    monkeypatch,
) -> None:
    context = _explanation_context()
    del context["metrics"]["aggregate"]["performance"]["delta_vs_benchmark_pct"]

    facts = await _composer_facts(monkeypatch, _completed_state(context))
    result = explain_stage(state=_completed_state(context))

    assert facts["comparison"].get("delta_vs_benchmark_pct") is None
    assert facts["comparison"]["total_return_pct"] == TOTAL_RETURN_PCT
    assert facts["benchmark_comparison_claim"] == "unknown"
    readout = result.patch["assistant_response"]
    assert readout.startswith(
        "The strategy returned 53.4% while SPY returned 7.1% for the comparison window."
    )
    assert "percentage points" not in readout
    assert all("why" not in row for row in result.patch["next_experiments"]["rows"])


@pytest.mark.asyncio
async def test_legacy_fraction_payloads_still_derive_their_only_comparison(
    monkeypatch,
) -> None:
    # Offline tools publish two fractions and no engine block; their
    # difference is the only comparison that shape carries.
    state = _completed_state(_explanation_context())
    state.final_response_payload = {
        "result": {"total_return": 0.14, "benchmark_return": 0.09},
        "explanation_context": {"benchmark_symbol": "SPY"},
    }
    facts = await _composer_facts(monkeypatch, state)

    assert facts["comparison"]["delta_vs_benchmark_pct"] == pytest.approx(5)
    assert facts["benchmark_comparison_claim"] == "beat_benchmark"
