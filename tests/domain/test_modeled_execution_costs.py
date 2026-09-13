"""A run's modeled cost dollars and fill sides come from its own fills.

Prices and capital are chosen so every fill trades whole shares. At 5 bps of
fees and 10 bps of slippage one share at 100 costs 100 * 1.001 * 1.0005 =
100.15005, so 10,015.005 buys exactly 100 shares at 100 or 50 at 200.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest
from argus.domain.backtesting.execution import (
    ExecutionEvent,
    _build_long_only_execution_ledger,
    _dca_equity_curve,
    _execute_long_only_ledger,
)
from argus.domain.backtesting.runner import build_benchmark_curve, compute_alpha_metrics

FEE_BPS = 5.0
SLIPPAGE_BPS = 10.0
FEE = FEE_BPS / 10_000.0
SLIPPAGE = SLIPPAGE_BPS / 10_000.0
HUNDRED_SHARES_AT_100 = 10_015.005
SEED_OF_200_SHARES_AT_100 = 20_030.01


def _index(periods: int) -> pd.DatetimeIndex:
    return pd.bdate_range("2025-01-06", periods=periods, tz="UTC")


def _bars(prices: list[float], index: pd.DatetimeIndex) -> pd.DataFrame:
    close = pd.Series(prices, index=index, dtype=float)
    return pd.DataFrame(
        {"open": close, "high": close, "low": close, "close": close, "volume": 1_000.0},
        index=index,
    )


def _realism(
    *,
    enabled: bool = True,
    fee_bps: float = FEE_BPS,
    slippage_bps: float = SLIPPAGE_BPS,
) -> dict[str, object]:
    return {"enabled": enabled, "fee_bps": fee_bps, "slippage_bps": slippage_bps}


def _fixed_config(
    index: pd.DatetimeIndex,
    *,
    symbols: list[str],
    starting_capital: float = HUNDRED_SHARES_AT_100,
    realism: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "template": "signal_strategy",
        "asset_class": "equity",
        "symbols": symbols,
        "timeframe": "1D",
        "start_date": index[0].date().isoformat(),
        "end_date": index[-1].date().isoformat(),
        "starting_capital": starting_capital,
        "allocation_method": "equal_weight",
        "benchmark_symbol": "SPY",
        "parameters": {},
        "_execution_realism": realism if realism is not None else _realism(),
    }


def _plan_config(
    index: pd.DatetimeIndex,
    *,
    realism: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "template": "dca_accumulation",
        "asset_class": "equity",
        "symbols": ["AAPL"],
        "timeframe": "1D",
        "start_date": index[0].date().isoformat(),
        "end_date": index[-1].date().isoformat(),
        "allocation_method": "equal_weight",
        "benchmark_symbol": "SPY",
        "parameters": {"dca_cadence": "monthly"},
        "dca_capital": {
            "schema_version": "dca_capital_v1",
            "starting_capital": SEED_OF_200_SHARES_AT_100,
            "contribution": HUNDRED_SHARES_AT_100,
        },
        "_execution_realism": realism if realism is not None else _realism(),
    }


def _run(
    config: dict[str, object],
    *,
    index: pd.DatetimeIndex,
    prices: dict[str, list[float]],
    entries: dict[str, list[bool]],
    exits: dict[str, list[bool]] | None = None,
) -> dict[str, Any]:
    frames = {symbol: _bars(values, index) for symbol, values in prices.items()}

    def signals(_: object, bars: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        symbol = next(name for name, frame in frames.items() if frame is bars)
        return (
            pd.Series(entries[symbol], index=index, dtype=bool),
            pd.Series((exits or {}).get(symbol, False), index=index, dtype=bool),
        )

    return compute_alpha_metrics(
        config,
        fetch_ohlcv_func=lambda *, symbol, **_: frames[symbol],
        build_signals_func=signals,
        build_benchmark_curve_func=lambda cfg, idx: build_benchmark_curve(
            cfg, idx, fetch_price_series_func=lambda **_: pd.Series(1.0, index=idx)
        ),
    )


def _long_only_ledger(
    index: pd.DatetimeIndex, *, entries: list[bool], exits: list[bool]
) -> list[ExecutionEvent]:
    return _build_long_only_execution_ledger(
        symbol="AAPL",
        entries=pd.Series(entries, index=index, dtype=bool),
        exits=pd.Series(exits, index=index, dtype=bool),
        allow_accumulation=False,
    )


def _fill_sides(efficiency: dict[str, Any]) -> tuple[int, int, int]:
    return efficiency["buy_fills"], efficiency["sell_fills"], efficiency["total_trades"]


def test_a_buy_spends_market_value_plus_slippage_and_fee() -> None:
    index = _index(2)
    result = _execute_long_only_ledger(
        execution_events=_long_only_ledger(
            index, entries=[True, False], exits=[False, False]
        ),
        close=pd.Series([100.0, 110.0], index=index),
        initial_capital=HUNDRED_SHARES_AT_100,
        fees=FEE,
        slippage=SLIPPAGE,
    )

    # 100 shares at 100: slippage 10,000 * 0.001, fee 10,000 * 1.001 * 0.0005.
    assert result.modeled_slippage_cost == pytest.approx(10.0)
    assert result.modeled_fee_cost == pytest.approx(5.005)
    assert HUNDRED_SHARES_AT_100 == pytest.approx(
        100 * 100.0 + result.modeled_slippage_cost + result.modeled_fee_cost
    )
    assert result.equity_curve.tolist() == pytest.approx([10_000.0, 11_000.0])


def test_a_sell_returns_market_value_minus_slippage_and_fee() -> None:
    index = _index(3)
    result = _execute_long_only_ledger(
        execution_events=_long_only_ledger(
            index, entries=[True, False, False], exits=[False, False, True]
        ),
        close=pd.Series([100.0, 105.0, 110.0], index=index),
        initial_capital=HUNDRED_SHARES_AT_100,
        fees=FEE,
        slippage=SLIPPAGE,
    )

    # 100 shares at 110: slippage 11,000 * 0.001, fee 11,000 * 0.999 * 0.0005.
    sell_slippage, sell_fee = 11.0, 5.4945
    proceeds = float(result.equity_curve.iloc[-1])
    assert result.modeled_slippage_cost == pytest.approx(10.0 + sell_slippage)
    assert result.modeled_fee_cost == pytest.approx(5.005 + sell_fee)
    assert proceeds == pytest.approx(100 * 110.0 - sell_slippage - sell_fee)
    assert proceeds == pytest.approx(10_983.5055)


def test_a_round_trip_run_records_cost_dollars_and_fill_sides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "true")
    index = _index(3)
    metrics = _run(
        _fixed_config(index, symbols=["AAPL"]),
        index=index,
        prices={"AAPL": [100.0, 105.0, 110.0]},
        entries={"AAPL": [True, False, False]},
        exits={"AAPL": [False, False, True]},
    )
    performance = metrics["aggregate"]["performance"]

    # Fees 5.005 + 5.4945 = 10.4995; slippage 10 + 11 = 21.
    assert performance["execution_realism"]["modeled_fee_cost"] == 10.5
    assert performance["execution_realism"]["modeled_slippage_cost"] == 21.0
    assert performance["execution_realism"]["modeled_cost_total"] == 31.5
    assert performance["profit"] == round(10_983.5055 - HUNDRED_SHARES_AT_100, 2)
    for efficiency in (
        metrics["aggregate"]["efficiency"],
        metrics["by_symbol"]["AAPL"]["efficiency"],
    ):
        assert _fill_sides(efficiency) == (1, 1, 2)
        assert all(
            isinstance(count, int) and not isinstance(count, bool)
            for count in _fill_sides(efficiency)
        )


def test_a_recurring_plan_buys_the_seed_and_each_contribution_with_costs() -> None:
    index = _index(3)
    result = _dca_equity_curve(
        close=pd.Series([100.0, 80.0, 200.0], index=index),
        entries=pd.Series([True, False, True], index=index),
        contribution=HUNDRED_SHARES_AT_100,
        starting_capital=SEED_OF_200_SHARES_AT_100,
        fees=FEE,
        slippage=SLIPPAGE,
    )

    # Bar 0 invests the seed and a contribution: 300 shares, market value
    # 30,000, slippage 30, fee 30,000 * 1.001 * 0.0005 = 15.015. Bar 2
    # invests a contribution: 50 shares at 200, slippage 10, fee 5.005.
    assert result.modeled_slippage_cost == pytest.approx(30.0 + 10.0)
    assert result.modeled_fee_cost == pytest.approx(15.015 + 5.005)
    assert result.invested_capital == pytest.approx(
        30_000.0 + 10_000.0 + result.modeled_slippage_cost + result.modeled_fee_cost
    )
    assert result.equity_curve.tolist() == pytest.approx([30_000.0, 24_000.0, 70_000.0])


def test_a_recurring_plan_run_counts_only_its_own_purchases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "true")
    index = _index(3)
    metrics = _run(
        _plan_config(index),
        index=index,
        prices={"AAPL": [100.0, 80.0, 200.0]},
        entries={"AAPL": [True, False, True]},
    )
    aggregate = metrics["aggregate"]

    # The benchmark buys on the same deposits, so counting it would double these.
    realism = aggregate["performance"]["execution_realism"]
    assert realism["modeled_fee_cost"] == 20.02
    assert realism["modeled_slippage_cost"] == 40.0
    assert realism["modeled_cost_total"] == 60.02
    for efficiency in (
        aggregate["efficiency"],
        metrics["by_symbol"]["AAPL"]["efficiency"],
    ):
        assert _fill_sides(efficiency) == (2, 0, 2)


def test_two_symbols_sum_their_cost_dollars_and_fills(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "true")
    index = _index(3)
    metrics = _run(
        _fixed_config(
            index,
            symbols=["AAPL", "MSFT"],
            starting_capital=2 * HUNDRED_SHARES_AT_100,
        ),
        index=index,
        prices={"AAPL": [100.0, 105.0, 110.0], "MSFT": [200.0, 190.0, 210.0]},
        entries={"AAPL": [True, False, False], "MSFT": [True, False, False]},
        exits={"AAPL": [False, False, True]},
    )

    # AAPL round trip: fees 10.4995, slippage 21. MSFT buys 50 shares at 200:
    # fee 10,000 * 1.001 * 0.0005 = 5.005, slippage 10.
    realism = metrics["aggregate"]["performance"]["execution_realism"]
    assert realism["modeled_fee_cost"] == 15.5
    assert realism["modeled_slippage_cost"] == 31.0
    assert realism["modeled_cost_total"] == 46.5
    assert _fill_sides(metrics["aggregate"]["efficiency"]) == (2, 1, 3)
    assert _fill_sides(metrics["by_symbol"]["AAPL"]["efficiency"]) == (1, 1, 2)
    assert _fill_sides(metrics["by_symbol"]["MSFT"]["efficiency"]) == (1, 0, 1)


@pytest.mark.parametrize(
    ("flag", "realism"),
    [
        ("true", _realism(enabled=False, fee_bps=0.0, slippage_bps=0.0)),
        ("true", _realism(fee_bps=0.0, slippage_bps=0.0)),
        ("false", _realism()),
    ],
    ids=["costs_not_requested", "zero_rates", "realism_switched_off"],
)
def test_idealized_runs_omit_cost_dollars_but_record_fill_sides(
    monkeypatch: pytest.MonkeyPatch,
    flag: str,
    realism: dict[str, object],
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", flag)
    index = _index(3)
    round_trip = _run(
        _fixed_config(index, symbols=["AAPL"], realism=realism),
        index=index,
        prices={"AAPL": [100.0, 105.0, 110.0]},
        entries={"AAPL": [True, False, False]},
        exits={"AAPL": [False, False, True]},
    )
    plan = _run(
        _plan_config(index, realism=realism),
        index=index,
        prices={"AAPL": [100.0, 80.0, 200.0]},
        entries={"AAPL": [True, False, True]},
    )

    for metrics, expected in ((round_trip, (1, 1, 2)), (plan, (2, 0, 2))):
        aggregate = metrics["aggregate"]
        assert "execution_realism" not in aggregate["performance"]
        assert _fill_sides(aggregate["efficiency"]) == expected
        assert _fill_sides(metrics["by_symbol"]["AAPL"]["efficiency"]) == expected
