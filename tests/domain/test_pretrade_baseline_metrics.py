"""Risk metrics anchor at the pre-trade capital baseline (#468).

The metric series starts from the cash that funds the run (the bankroll, or
the first funded bar's deposits), never from the post-fill first mark: a
first-bar execution cost is a real fall from that baseline, dispersion uses
one return per actual bar interval with no fabricated zero, and fewer than
two real intervals report null dispersion instead of a fake 0%. Every
expected value here is derived from prices and cash flows alone.
"""

from __future__ import annotations

from math import sqrt

import numpy as np
import pandas as pd
import pytest
from argus.domain.backtesting.coverage import build_metric_time_basis
from argus.domain.backtesting.metrics import (
    _baseline_anchored_series,
    _compute_dca_metrics,
)
from argus.domain.backtesting.runner import build_benchmark_curve, compute_alpha_metrics

FEE = 200.0 / 10_000.0
SLIPPAGE = 100.0 / 10_000.0
COST_KEEP_RATIO = 1.0 / ((1.0 + SLIPPAGE) * (1.0 + FEE))


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


def _fixed_config(
    index: pd.DatetimeIndex,
    *,
    template: str = "buy_and_hold",
    with_costs: bool = True,
) -> dict[str, object]:
    return {
        "template": template,
        "asset_class": "equity",
        "symbols": ["AAPL"],
        "timeframe": "1D",
        "start_date": index[0].date().isoformat(),
        "end_date": index[-1].date().isoformat(),
        "starting_capital": 1_000.0,
        "allocation_method": "equal_weight",
        "benchmark_symbol": "SPY",
        "parameters": {},
        "_execution_realism": {
            "enabled": with_costs,
            "fee_bps": 200.0 if with_costs else 0.0,
            "slippage_bps": 100.0 if with_costs else 0.0,
        },
    }


def _run(
    config: dict[str, object],
    *,
    prices: list[float],
    entries: list[bool],
    index: pd.DatetimeIndex,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, object]:
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "true")
    strategy_bars = _bars(prices, index)
    return compute_alpha_metrics(
        config,
        fetch_ohlcv_func=lambda **_: strategy_bars,
        build_signals_func=lambda *_: (
            pd.Series(entries, index=index, dtype=bool),
            pd.Series(False, index=index, dtype=bool),
        ),
        build_benchmark_curve_func=lambda cfg, idx: build_benchmark_curve(
            cfg, idx, fetch_price_series_func=lambda **_: pd.Series(1.0, index=idx)
        ),
    )


def _sample_std(values: list[float]) -> float:
    return float(np.std(np.array(values), ddof=1))


# --- The issue's independent proof: flat price, first-bar buy, costs -------


def test_first_bar_entry_cost_reaches_drawdown_volatility_and_sharpe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """$1,000 at flat 100 with 2% fees and 1% slippage loses 2.93% at entry."""
    index = pd.bdate_range("2025-01-06", periods=5, tz="UTC")
    metrics = _run(
        _fixed_config(index),
        prices=[100.0] * 5,
        entries=[True, False, False, False, False],
        index=index,
        monkeypatch=monkeypatch,
    )
    aggregate = metrics["aggregate"]

    entry_return = COST_KEEP_RATIO - 1.0
    period_returns = [entry_return, 0.0, 0.0, 0.0]
    expected_volatility = _sample_std(period_returns) * sqrt(252.0) * 100.0
    expected_sharpe = (
        float(np.mean(period_returns)) / _sample_std(period_returns) * sqrt(252.0)
    )

    assert aggregate["performance"]["total_return_pct"] == pytest.approx(
        entry_return * 100.0, abs=0.01
    )
    assert aggregate["risk"]["max_drawdown_pct"] == pytest.approx(
        entry_return * 100.0, abs=0.01
    )
    assert aggregate["risk"]["volatility_pct"] == pytest.approx(
        expected_volatility, abs=0.01
    )
    assert aggregate["efficiency"]["sharpe_ratio"] == pytest.approx(
        expected_sharpe, abs=0.01
    )


def test_no_fabricated_zero_return_joins_the_dispersion_sample(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Equity [1000, 1100, 990] has two real intervals, +10% and -10%."""
    index = pd.bdate_range("2025-01-06", periods=3, tz="UTC")
    metrics = _run(
        _fixed_config(index, with_costs=False),
        prices=[100.0, 110.0, 99.0],
        entries=[True, False, False],
        index=index,
        monkeypatch=monkeypatch,
    )
    aggregate = metrics["aggregate"]

    # The audit's worked number: std([0.10, -0.10]) * sqrt(252) = 224.50%.
    # The retired convention printed 158.75% by averaging in a zero that
    # never happened.
    expected_volatility = _sample_std([0.10, -0.10]) * sqrt(252.0) * 100.0
    assert aggregate["risk"]["volatility_pct"] == pytest.approx(
        expected_volatility, abs=0.01
    )
    assert aggregate["risk"]["volatility_pct"] == pytest.approx(224.50, abs=0.01)
    assert aggregate["risk"]["max_drawdown_pct"] == pytest.approx(-10.0, abs=0.01)
    assert aggregate["efficiency"]["sharpe_ratio"] == pytest.approx(0.0, abs=0.01)


def test_later_entry_keeps_the_cash_period_and_counts_entry_cost_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index = pd.bdate_range("2025-01-06", periods=5, tz="UTC")
    metrics = _run(
        _fixed_config(index, template="signal_strategy"),
        prices=[100.0] * 5,
        entries=[False, False, True, False, False],
        index=index,
        monkeypatch=monkeypatch,
    )
    aggregate = metrics["aggregate"]

    # Two real cash intervals at 0%, the entry-cost interval, then flat.
    entry_return = COST_KEEP_RATIO - 1.0
    period_returns = [0.0, 0.0, entry_return, 0.0]
    expected_volatility = _sample_std(period_returns) * sqrt(252.0) * 100.0

    assert aggregate["risk"]["max_drawdown_pct"] == pytest.approx(
        entry_return * 100.0, abs=0.01
    )
    assert aggregate["risk"]["volatility_pct"] == pytest.approx(
        expected_volatility, abs=0.01
    )
    assert aggregate["performance"]["total_return_pct"] == pytest.approx(
        entry_return * 100.0, abs=0.01
    )


def test_two_bar_window_reports_null_dispersion_not_zero_risk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fees exceeding the gain: a negative net return cannot ride 0% risk."""
    index = pd.bdate_range("2025-01-06", periods=2, tz="UTC")
    metrics = _run(
        _fixed_config(index),
        prices=[100.0, 101.0],
        entries=[True, False],
        index=index,
        monkeypatch=monkeypatch,
    )
    aggregate = metrics["aggregate"]

    net_return = COST_KEEP_RATIO * 1.01 - 1.0
    assert net_return < 0.0
    assert aggregate["performance"]["total_return_pct"] == pytest.approx(
        net_return * 100.0, abs=0.01
    )
    # One real interval: the entry cost is a drawdown fact, and dispersion
    # is undefined rather than a reassuring zero.
    assert aggregate["risk"]["max_drawdown_pct"] == pytest.approx(
        (COST_KEEP_RATIO - 1.0) * 100.0, abs=0.01
    )
    assert aggregate["risk"]["volatility_pct"] is None
    assert aggregate["efficiency"]["sharpe_ratio"] is None


# --- The shared convention on the contributions path -----------------------


def test_dca_first_deposit_cost_drag_enters_risk_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "true")
    index = pd.bdate_range("2025-01-06", periods=4, tz="UTC")
    config = {
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
            "starting_capital": 0.0,
            "contribution": 1_000.0,
        },
        "_execution_realism": {
            "enabled": True,
            "fee_bps": 200.0,
            "slippage_bps": 100.0,
        },
    }
    strategy_bars = _bars([50.0] * 4, index)
    metrics = compute_alpha_metrics(
        config,
        fetch_ohlcv_func=lambda **_: strategy_bars,
        build_signals_func=lambda *_: (
            pd.Series([True, False, True, False], index=index, dtype=bool),
            pd.Series(False, index=index, dtype=bool),
        ),
        build_benchmark_curve_func=lambda cfg, idx: build_benchmark_curve(
            cfg, idx, fetch_price_series_func=lambda **_: pd.Series(1.0, index=idx)
        ),
    )
    aggregate = metrics["aggregate"]

    # Flat prices: every loss is modeled cost. The first deposit falls from
    # the baseline by keep-1; the second deposit drags its interval by
    # (keep-1)/keep of prior equity; the wealth trough is 2*(keep-1).
    first_interval = COST_KEEP_RATIO - 1.0
    deposit_interval = (COST_KEEP_RATIO - 1.0) / COST_KEEP_RATIO
    period_returns = [0.0, deposit_interval, 0.0]
    period_returns[0] = (1.0 + first_interval) * (1.0 + 0.0) - 1.0
    expected_volatility = _sample_std(period_returns) * sqrt(252.0) * 100.0

    assert aggregate["performance"]["total_return_pct"] == pytest.approx(
        first_interval * 100.0, abs=0.01
    )
    assert aggregate["risk"]["max_drawdown_pct"] == pytest.approx(
        2.0 * first_interval * 100.0, abs=0.01
    )
    assert aggregate["risk"]["volatility_pct"] == pytest.approx(
        expected_volatility, abs=0.01
    )


def test_dca_funded_after_the_first_bar_anchors_at_the_first_deposit() -> None:
    """Bars before any capital exists carry no return observations."""
    index = pd.bdate_range("2025-01-06", periods=4, tz="UTC")
    equity = pd.Series([0.0, 0.0, 100.0, 80.0], index=index, dtype=float)
    flows = pd.Series([0.0, 0.0, 100.0, 0.0], index=index, dtype=float)

    anchored = _baseline_anchored_series(equity, flows)
    metrics = _compute_dca_metrics(
        strategy_equity=equity,
        benchmark_equity=pd.Series([0.0, 0.0, 100.0, 100.0], index=index),
        external_flows=flows,
        invested_capital=100.0,
        time_basis=build_metric_time_basis(
            asset_class="equity",
            timeframe="1D",
            effective_index=index,
        ),
        trade_count=1,
    )

    # One real interval after funding: dispersion undefined, drawdown real.
    assert anchored.period_returns.tolist() == pytest.approx([-0.2], abs=1e-12)
    assert metrics["risk"]["volatility_pct"] is None
    assert metrics["efficiency"]["sharpe_ratio"] is None
    assert metrics["risk"]["max_drawdown_pct"] == pytest.approx(-20.0, abs=0.01)
    assert metrics["performance"]["total_return_pct"] == pytest.approx(-20.0, abs=0.01)


# --- One metric path for both realism flag states --------------------------


def test_flag_states_share_one_metric_path_at_the_rounding_tie_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 20-bar triangle 96 -> 114 -> 97.8 puts the exact total return on the
    # 1.875% rounding tie, where the retired returns-based float path and
    # the equity/invested ratio round apart. One metric path owns both flag
    # states (#468), so the tie resolves as the equity ratio either way.
    prices = [96.0 + 1.8 * step for step in range(11)] + [
        114.0 - 1.8 * step for step in range(1, 10)
    ]
    index = pd.bdate_range("2025-01-06", periods=len(prices), tz="UTC")
    config = _fixed_config(index, with_costs=False)
    config["starting_capital"] = 10_000.0

    def run() -> dict[str, object]:
        return compute_alpha_metrics(
            config,
            fetch_ohlcv_func=lambda **_: _bars(prices, index),
            build_signals_func=lambda *_: (
                pd.Series([True] + [False] * (len(prices) - 1), index=index),
                pd.Series(False, index=index, dtype=bool),
            ),
            build_benchmark_curve_func=lambda cfg, idx: build_benchmark_curve(
                cfg, idx, fetch_price_series_func=lambda **_: pd.Series(1.0, index=idx)
            ),
        )

    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "false")
    flag_off = run()
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "true")
    flag_on_costless = run()

    assert flag_off["aggregate"]["performance"]["total_return_pct"] == 1.88
    assert flag_on_costless["aggregate"] == flag_off["aggregate"]
    assert flag_on_costless["by_symbol"] == flag_off["by_symbol"]
