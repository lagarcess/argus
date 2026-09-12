"""Numbers on screen add up: a gap or cost drag an answer can state is the
difference of the two figures shown beside it, dollar costs are facts, and a
run's trades are named for what they were, in both workspace languages."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from argus.agent_runtime.result_conversation import run_headline_facts
from argus.domain.display_figure import display_difference
from argus.domain.result_readout_display_values import readout_display_value
from argus.domain.result_readout_grounding import stored_readout_facts
from babel.numbers import parse_decimal

LANGUAGES = ("en", "es-419")


def _metadata(performance: dict[str, Any], efficiency: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbols": ["SPY"],
        "benchmark_symbol": "SPY",
        "config_snapshot": {
            "template": "indicator_threshold",
            "symbols": ["SPY"],
            "benchmark_symbol": "SPY",
            "date_range": {"start": "2020-07-27", "end": "2026-09-10"},
        },
        "metrics": {"aggregate": {"performance": performance, "efficiency": efficiency}},
    }


def _shown(row: dict[str, Any], language: str) -> Decimal:
    display = readout_display_value(row, language=language)
    assert display is not None
    text = display["text"].replace("$", "").replace("%", "").replace(" pp", "")
    return parse_decimal(text, locale=language.replace("-", "_"))


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_stated_benchmark_gap_is_the_difference_of_the_shown_returns(
    language: str,
) -> None:
    # The engine gap from unrounded returns prints 80.1; the shown returns differ by 80.0.
    metadata = _metadata(
        {
            "total_return_pct": 54.44,
            "benchmark_return_pct": 134.44,
            "delta_vs_benchmark_pct": -80.06,
        },
        {"total_trades": 30},
    )

    facts = run_headline_facts(metadata)["facts"]

    total = _shown(facts["Total return on starting capital"], language)
    benchmark = _shown(facts["Benchmark return"], language)
    gap = _shown(facts["Return difference versus benchmark"], language)
    assert (total, benchmark) == (Decimal("54.4"), Decimal("134.4"))
    assert gap == abs(total - benchmark) == Decimal("80.0")


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_stated_cost_drag_is_the_difference_of_the_shown_before_and_after_returns(
    language: str,
) -> None:
    # Engine drag 0.58 prints 0.6; the shown 269.7% and 269.2% differ by 0.5.
    metadata = _metadata(
        {
            "total_return_pct": 269.16,
            "benchmark_return_pct": 38.4,
            "delta_vs_benchmark_pct": 230.76,
            "execution_realism": {
                "enabled": True,
                "fee_bps": 5.0,
                "slippage_bps": 10.0,
                "gross_total_return_pct": 269.74,
                "net_total_return_pct": 269.16,
                "return_drag_pct": 0.58,
                "modeled_fee_cost": 2.35,
                "modeled_slippage_cost": 4.7,
                "modeled_cost_total": 7.05,
            },
        },
        {"total_trades": 37, "buy_fills": 37, "sell_fills": 0},
    )

    facts = run_headline_facts(metadata)["facts"]

    before = _shown(facts["Return before modeled costs"], language)
    after = _shown(facts["Return after modeled costs"], language)
    drag = _shown(facts["Return given up to modeled costs"], language)
    assert (before, after, drag) == (Decimal("269.7"), Decimal("269.2"), Decimal("0.5"))
    assert drag == before - after
    fees = _shown(facts["Modeled fees in money"], language)
    slippage = _shown(facts["Modeled slippage in money"], language)
    total = _shown(facts["Modeled fees and slippage in money"], language)
    assert (fees, slippage, total) == (Decimal("2.35"), Decimal("4.70"), Decimal("7.05"))
    assert total == fees + slippage


def test_a_monthly_buy_run_names_purchases_not_purchases_and_sales() -> None:
    metadata = _metadata(
        {"total_return_pct": 269.16, "benchmark_return_pct": 38.4},
        {"total_trades": 37, "buy_fills": 37, "sell_fills": 0},
    )

    facts = run_headline_facts(metadata)["facts"]

    assert facts["Purchases"]["value"] == 37
    assert facts["Sales"]["value"] == 0
    assert facts["Trades executed"]["value"] == 37
    assert "Purchases and sales" not in facts


def test_a_gap_without_both_returns_keeps_the_stored_value() -> None:
    sheet = stored_readout_facts(
        metrics={"aggregate": {"performance": {"delta_vs_benchmark_pct": 12.34}}},
        config_snapshot={"template": "buy_and_hold", "symbols": ["AAPL"]},
        symbols=["AAPL"],
        benchmark_symbol="SPY",
        date_range={"start": "2024-01-02", "end": "2024-12-31"},
        chart=None,
    )

    assert sheet["facts"]["portfolio.benchmark_gap"]["value"] == 12.34


@pytest.mark.parametrize(
    ("minuend", "subtrahend", "shown"),
    [
        (54.44, 134.44, -80.0),
        (269.74, 269.16, 0.5),
        (389.94, 68.04, 321.9),
        (None, 1.0, None),
    ],
)
def test_display_difference_subtracts_what_a_reader_sees(
    minuend: float | None, subtrahend: float, shown: float | None
) -> None:
    assert display_difference(minuend, subtrahend) == shown
