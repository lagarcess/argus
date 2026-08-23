"""DCA benchmark fills execute only at observed benchmark prices (#469).

Benchmark alignment accepts interior gaps at 80% coverage and forward-fills
them for marking, but a forward-filled price is never an executable fill
price: a deposit landing on a gap bar keeps its date and buys at the next
observed close, idling as cash until then. Every expected value here is
derived from prices and cash flows alone.
"""

from __future__ import annotations

import pandas as pd
import pytest
from argus.domain.backtesting.execution import _dca_equity_curve
from argus.domain.backtesting.runner import build_benchmark_curve, compute_alpha_metrics

FEE = 10.0 / 10_000.0
SLIPPAGE = 5.0 / 10_000.0

INDEX5 = pd.bdate_range("2025-01-06", periods=5, tz="UTC")


def _cash_per_share(price: float) -> float:
    return price * (1.0 + SLIPPAGE) * (1.0 + FEE)


def _bars(prices: list[float], index: pd.DatetimeIndex) -> pd.DataFrame:
    close = pd.Series(prices, index=index, dtype=float)
    return pd.DataFrame(
        {
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "volume": 1_000.0,
        },
        index=index,
    )


def _dca_config(
    index: pd.DatetimeIndex,
    *,
    contribution: float = 100.0,
    symbols: list[str] | None = None,
) -> dict[str, object]:
    return {
        "template": "dca_accumulation",
        "asset_class": "equity",
        "symbols": symbols or ["AAPL"],
        "timeframe": "1D",
        "start_date": index[0].date().isoformat(),
        "end_date": index[-1].date().isoformat(),
        "allocation_method": "equal_weight",
        "benchmark_symbol": "SPY",
        "parameters": {"dca_cadence": "daily"},
        "dca_capital": {
            "schema_version": "dca_capital_v1",
            "starting_capital": 0.0,
            "contribution": contribution,
        },
        "_execution_realism": {
            "enabled": True,
            "fee_bps": 10.0,
            "slippage_bps": 5.0,
        },
    }


def _run_with_gappy_benchmark(
    config: dict[str, object],
    *,
    bars_by_symbol: dict[str, pd.DataFrame],
    benchmark_series: pd.Series,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, object]:
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "true")
    return compute_alpha_metrics(
        config,
        fetch_ohlcv_func=lambda *, symbol, **_: bars_by_symbol[symbol],
        build_signals_func=lambda _config, data: (
            pd.Series(True, index=data.index, dtype=bool),
            pd.Series(False, index=data.index, dtype=bool),
        ),
        build_benchmark_curve_func=lambda cfg, idx: build_benchmark_curve(
            cfg,
            idx,
            fetch_price_series_func=lambda **_: benchmark_series,
        ),
    )


# --- The audit's worked example (D7), through real alignment ---------------


def test_audit_gap_example_buys_at_the_next_observed_price(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Benchmark [100, 100, missing, 200, 200] at exactly 80% coverage."""
    benchmark_observed = pd.Series(
        [100.0, 100.0, 200.0, 200.0], index=INDEX5[[0, 1, 3, 4]], dtype=float
    )
    metrics = _run_with_gappy_benchmark(
        _dca_config(INDEX5),
        bars_by_symbol={"AAPL": _bars([100.0] * 5, INDEX5)},
        benchmark_series=benchmark_observed,
        monkeypatch=monkeypatch,
    )
    performance = metrics["aggregate"]["performance"]

    # Independent ledger on the normalized benchmark path [1, 1, gap, 2, 2]:
    # the gap-day $100 keeps its date but buys at the next observed price 2.
    shares = 2 * (100.0 / _cash_per_share(1.0)) + 3 * (100.0 / _cash_per_share(2.0))
    expected_value = shares * 2.0
    expected_return = (expected_value / 500.0 - 1.0) * 100.0
    stale_fill_return = (
        (3 * (100.0 / _cash_per_share(1.0)) + 2 * (100.0 / _cash_per_share(2.0)))
        * 2.0
        / 500.0
        - 1.0
    ) * 100.0

    assert performance["benchmark_return_pct"] == pytest.approx(expected_return, abs=0.01)
    assert performance["benchmark_return_pct"] != pytest.approx(
        stale_fill_return, abs=0.01
    )
    assert performance["delta_vs_benchmark_pct"] == pytest.approx(
        performance["total_return_pct"] - performance["benchmark_return_pct"],
        abs=0.01,
    )


def test_below_threshold_coverage_is_still_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    benchmark_observed = pd.Series(
        [100.0, 200.0, 200.0], index=INDEX5[[0, 1, 4]], dtype=float
    )

    with pytest.raises(ValueError, match="benchmark_data_unavailable"):
        _run_with_gappy_benchmark(
            _dca_config(INDEX5),
            bars_by_symbol={"AAPL": _bars([100.0] * 5, INDEX5)},
            benchmark_series=benchmark_observed,
            monkeypatch=monkeypatch,
        )


# --- The fill policy, from first principles --------------------------------


def test_deposits_keep_their_dates_while_buys_defer() -> None:
    index = pd.bdate_range("2025-01-06", periods=4, tz="UTC")
    close = pd.Series([10.0, 10.0, 20.0, 20.0], index=index, dtype=float)
    observed = pd.Series([True, False, True, True], index=index, dtype=bool)
    entries = pd.Series(True, index=index, dtype=bool)

    result = _dca_equity_curve(
        close=close,
        entries=entries,
        contribution=100.0,
        fees=FEE,
        slippage=SLIPPAGE,
        observed=observed,
    )

    # Deposits stay on their own bars for the cash-flow ledger.
    assert result.external_flows.tolist() == [100.0, 100.0, 100.0, 100.0]
    assert result.invested_capital == 400.0
    assert result.deferred_fill_count == 1

    # Bar 1's deposit idles as cash at its marked bar, then buys at bar 2's
    # observed price alongside bar 2's own deposit.
    shares_bar0 = 100.0 / _cash_per_share(10.0)
    equity_bar1 = shares_bar0 * 10.0 + 100.0
    shares_after_bar2 = shares_bar0 + 200.0 / _cash_per_share(20.0)
    equity_bar2 = shares_after_bar2 * 20.0
    shares_after_bar3 = shares_after_bar2 + 100.0 / _cash_per_share(20.0)

    assert result.equity_curve.iloc[1] == pytest.approx(equity_bar1, rel=1e-12)
    assert result.equity_curve.iloc[2] == pytest.approx(equity_bar2, rel=1e-12)
    assert result.equity_curve.iloc[3] == pytest.approx(
        shares_after_bar3 * 20.0, rel=1e-12
    )


def test_consecutive_gap_deposits_fill_together_at_the_next_observed_price() -> None:
    index = pd.bdate_range("2025-01-06", periods=5, tz="UTC")
    close = pd.Series([10.0, 10.0, 10.0, 40.0, 40.0], index=index, dtype=float)
    observed = pd.Series([True, False, False, True, True], index=index, dtype=bool)

    result = _dca_equity_curve(
        close=close,
        entries=pd.Series(True, index=index, dtype=bool),
        contribution=100.0,
        fees=FEE,
        slippage=SLIPPAGE,
        observed=observed,
    )

    # Two gap-day deposits both execute at bar 3's observed price, never at
    # the forward-filled 10.
    shares = 100.0 / _cash_per_share(10.0) + 300.0 / _cash_per_share(40.0)
    assert result.deferred_fill_count == 2
    assert result.equity_curve.iloc[3] == pytest.approx(shares * 40.0, rel=1e-12)
    assert result.equity_curve.iloc[1] == pytest.approx(
        (100.0 / _cash_per_share(10.0)) * 10.0 + 100.0, rel=1e-12
    )


def test_trailing_unobserved_deposit_stays_cash() -> None:
    index = pd.bdate_range("2025-01-06", periods=3, tz="UTC")
    close = pd.Series([10.0, 10.0, 10.0], index=index, dtype=float)
    observed = pd.Series([True, True, False], index=index, dtype=bool)

    result = _dca_equity_curve(
        close=close,
        entries=pd.Series(True, index=index, dtype=bool),
        contribution=100.0,
        fees=FEE,
        slippage=SLIPPAGE,
        observed=observed,
    )

    shares = 200.0 / _cash_per_share(10.0)
    assert result.deferred_fill_count == 1
    assert result.invested_capital == 300.0
    assert result.equity_curve.iloc[-1] == pytest.approx(shares * 10.0 + 100.0, rel=1e-12)


def test_fully_observed_benchmark_matches_the_unmasked_simulation() -> None:
    index = pd.bdate_range("2025-01-06", periods=4, tz="UTC")
    close = pd.Series([10.0, 12.0, 11.0, 13.0], index=index, dtype=float)
    entries = pd.Series([True, False, True, False], index=index, dtype=bool)

    unmasked = _dca_equity_curve(
        close=close,
        entries=entries,
        contribution=250.0,
        fees=FEE,
        slippage=SLIPPAGE,
    )
    masked = _dca_equity_curve(
        close=close,
        entries=entries,
        contribution=250.0,
        fees=FEE,
        slippage=SLIPPAGE,
        observed=pd.Series(True, index=index, dtype=bool),
    )

    assert masked.deferred_fill_count == 0
    assert masked.equity_curve.tolist() == unmasked.equity_curve.tolist()
    assert masked.invested_capital == unmasked.invested_capital


# --- Multi-symbol: gaps defer per symbol -----------------------------------


def test_multi_symbol_gaps_defer_per_symbol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Symbol A's index exposes the benchmark gap; symbol B's does not."""
    index_a = INDEX5
    index_b = INDEX5[[0, 1, 3, 4]]
    benchmark_observed = pd.Series(
        [100.0, 100.0, 200.0, 200.0], index=INDEX5[[0, 1, 3, 4]], dtype=float
    )
    config = _dca_config(INDEX5, symbols=["AAPL", "MSFT"])

    metrics = _run_with_gappy_benchmark(
        config,
        bars_by_symbol={
            "AAPL": _bars([100.0] * 5, index_a),
            "MSFT": _bars([100.0] * 4, index_b),
        },
        benchmark_series=benchmark_observed,
        monkeypatch=monkeypatch,
    )

    # Equal weight splits the $100 contribution to $50 per symbol.
    per_symbol = 50.0
    normalized = {1.0: _cash_per_share(1.0), 2.0: _cash_per_share(2.0)}

    # A sees five bars; its gap-day deposit defers to the next observed 2.
    shares_a = 2 * (per_symbol / normalized[1.0]) + 3 * (per_symbol / normalized[2.0])
    expected_a = (shares_a * 2.0 / (5 * per_symbol) - 1.0) * 100.0
    # B's own bars are all observed benchmark bars; nothing defers.
    shares_b = 2 * (per_symbol / normalized[1.0]) + 2 * (per_symbol / normalized[2.0])
    expected_b = (shares_b * 2.0 / (4 * per_symbol) - 1.0) * 100.0

    assert metrics["by_symbol"]["AAPL"]["performance"][
        "benchmark_return_pct"
    ] == pytest.approx(expected_a, abs=0.01)
    assert metrics["by_symbol"]["MSFT"]["performance"][
        "benchmark_return_pct"
    ] == pytest.approx(expected_b, abs=0.01)
