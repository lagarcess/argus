from __future__ import annotations

from collections.abc import Callable

import pytest
from argus.agent_runtime.result_followups import result_followup_fact_bank
from argus.agent_runtime.stages.explain import _quick_take_fact_bank
from argus.api.chat.breakdown import result_breakdown_fact_bank
from argus.domain.engine import build_result_card

LanguageRenderer = Callable[[str], tuple[str, ...]]
BENCHMARK_RETURN_POINTS = 9.1
BENCHMARK_DELTA_POINTS = 9.3
TOTAL_RETURN_POINTS = BENCHMARK_RETURN_POINTS + BENCHMARK_DELTA_POINTS


def _run_performance() -> dict[str, float]:
    return {
        "profit": 184.0,
        "total_return_pct": TOTAL_RETURN_POINTS,
        "benchmark_return_pct": BENCHMARK_RETURN_POINTS,
        "delta_vs_benchmark_pct": BENCHMARK_DELTA_POINTS,
    }


def _result_card_comparison(language: str) -> tuple[str, ...]:
    card = build_result_card(
        {
            "template": "buy_and_hold",
            "asset_class": "equity",
            "symbols": ["AAPL"],
            "start_date": "2024-01-02",
            "end_date": "2024-03-01",
            "starting_capital": 1_000,
            "benchmark_symbol": "SPY",
        },
        {
            "aggregate": {
                "performance": _run_performance(),
                "risk": {"max_drawdown_pct": -6.2},
                "efficiency": {"win_rate": 0.0, "total_trades": 1},
            }
        },
        language=language,
    )
    comparison = next(row for row in card["rows"] if row["key"] == "benchmark_delta")
    return (comparison["value"],)


def _result_followup_comparison(language: str) -> tuple[str, ...]:
    facts = result_followup_fact_bank(
        {
            "symbols": ["AAPL"],
            "benchmark_symbol": "SPY",
            "metrics": {"aggregate": {"performance": _run_performance()}},
            "result_card": {
                "rows": [
                    {
                        "key": "benchmark_delta",
                        "value": "Beat by 9.3 percentage points",
                    }
                ]
            },
        },
        language=language,
    )
    assert "benchmark_delta" not in facts
    return (
        facts["benchmark_comparison"],
        facts["benchmark_delta_magnitude"],
        facts["relative_performance"],
    )


def _quick_take_comparison(language: str) -> tuple[str, ...]:
    facts = _quick_take_fact_bank(
        context={},
        result_payload={
            "total_return": TOTAL_RETURN_POINTS / 100,
            "benchmark_return": BENCHMARK_RETURN_POINTS / 100,
        },
        explanation_context={},
        language=language,
    )
    return (
        facts["benchmark_comparison"],
        facts["benchmark_delta_magnitude"],
    )


def _breakdown_comparison(language: str) -> tuple[str, ...]:
    facts = result_breakdown_fact_bank(
        {
            "symbols": ["AAPL"],
            "benchmark_symbol": "SPY",
            "raw_metrics": {"aggregate": {"performance": _run_performance()}},
        },
        language=language,
    )
    return (
        facts["benchmark_comparison"],
        facts["benchmark_delta_magnitude"],
    )


@pytest.mark.parametrize(
    "render_comparison",
    [
        pytest.param(_result_card_comparison, id="result-card"),
        pytest.param(_result_followup_comparison, id="result-followup"),
        pytest.param(_quick_take_comparison, id="quick-take"),
        pytest.param(_breakdown_comparison, id="breakdown"),
    ],
)
def test_each_benchmark_comparison_is_rendered_for_the_reader(
    render_comparison: LanguageRenderer,
) -> None:
    english = render_comparison("en")
    spanish = render_comparison("es-419")

    assert english != spanish
    assert len(english) == len(spanish)
    expected_delta = f"{BENCHMARK_DELTA_POINTS:.1f}"
    for english_value, spanish_value in zip(english, spanish, strict=True):
        assert english_value != spanish_value
        assert expected_delta in english_value
        assert expected_delta in spanish_value
        assert "percentage points" in english_value
        assert "puntos porcentuales" in spanish_value
