from __future__ import annotations

import pandas as pd
import pytest
from argus.domain.backtesting.cards import build_result_card
from argus.domain.backtesting.coverage import (
    MarketDataCoverageError,
    prepare_market_data,
)
from argus.domain.backtesting.runner import compute_alpha_metrics


def _bars(prices: list[float]) -> pd.DataFrame:
    index = pd.bdate_range("2025-01-02", periods=len(prices), tz="UTC")
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


def _config(
    *,
    template: str,
    periods: int,
    fee_bps: float,
    slippage_bps: float,
    parameters: dict[str, object] | None = None,
) -> dict[str, object]:
    index = pd.bdate_range("2025-01-02", periods=periods)
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
        "parameters": parameters or {},
        "_execution_realism": {
            "enabled": True,
            "fee_bps": fee_bps,
            "slippage_bps": slippage_bps,
        },
    }


def _run_with_signals(
    *,
    config: dict[str, object],
    strategy_prices: list[float],
    benchmark_prices: list[float],
    entries: list[bool],
    exits: list[bool],
) -> dict[str, object]:
    strategy_bars = _bars(strategy_prices)
    benchmark = pd.Series(
        benchmark_prices,
        index=strategy_bars.index,
        dtype=float,
    )
    def signal_builder(*_: object) -> tuple[pd.Series, pd.Series]:
        return (
            pd.Series(entries, index=strategy_bars.index, dtype=bool),
            pd.Series(exits, index=strategy_bars.index, dtype=bool),
        )
    return compute_alpha_metrics(
        config,
        fetch_ohlcv_func=lambda **_: strategy_bars,
        build_signals_func=signal_builder,
        build_benchmark_curve_func=lambda *_args, **_kwargs: {
            "equity_curve": (benchmark / benchmark.iloc[0]).tolist(),
        },
    )


def test_single_bar_window_is_rejected_before_metrics_are_computed() -> None:
    one_bar = _bars([100.0])

    with pytest.raises(MarketDataCoverageError) as exc_info:
        prepare_market_data(
            _config(
                template="buy_and_hold",
                periods=1,
                fee_bps=10.0,
                slippage_bps=5.0,
            ),
            fetch_ohlcv_func=lambda **_: one_bar,
        )

    assert exc_info.value.code == "insufficient_common_data"


def test_strategy_that_never_enters_preserves_cash_and_reports_zero_fills(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "true")
    config = _config(
        template="signal_strategy",
        periods=3,
        fee_bps=10.0,
        slippage_bps=5.0,
    )
    metrics = _run_with_signals(
        config=config,
        strategy_prices=[100.0, 105.0, 110.0],
        benchmark_prices=[100.0, 105.0, 110.0],
        entries=[False, False, False],
        exits=[False, False, False],
    )
    aggregate = metrics["aggregate"]
    fee = 10.0 / 10_000.0
    slippage = 5.0 / 10_000.0
    expected_benchmark_return = (
        110.0 / (100.0 * (1.0 + slippage) * (1.0 + fee)) - 1.0
    ) * 100.0

    assert aggregate["performance"]["total_return_pct"] == 0.0
    assert aggregate["performance"]["profit"] == 0.0
    assert aggregate["performance"]["annualized_return_pct"] == 0.0
    assert aggregate["performance"]["benchmark_return_pct"] == pytest.approx(
        expected_benchmark_return, abs=0.01
    )
    assert aggregate["performance"]["delta_vs_benchmark_pct"] == pytest.approx(
        -expected_benchmark_return, abs=0.01
    )
    assert aggregate["efficiency"] == {
        "win_rate": 0.0,
        "total_trades": 0,
        "profit_factor": 0.0,
        "sharpe_ratio": 0.0,
    }
    assert aggregate["risk"] == {"max_drawdown_pct": 0.0, "volatility_pct": 0.0}
    assert aggregate["performance"]["portfolio_value_range"] == {
        "peak_value": 1_000.0,
        "lowest_value": 1_000.0,
        "currency": "USD",
        "source": "strategy_portfolio_equity_close",
    }
    card = build_result_card(config, metrics)
    assert "win_rate" not in {row["key"] for row in card["rows"]}


def test_dca_strategy_and_benchmark_share_one_contribution_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "true")
    fee = 10.0 / 10_000.0
    slippage = 5.0 / 10_000.0
    contribution = 1_000.0
    strategy_prices = [100.0, 110.0, 90.0]
    benchmark_prices = [100.0, 105.0, 95.0]
    entries = [True, False, True]
    config = _config(
        template="dca_accumulation",
        periods=3,
        fee_bps=10.0,
        slippage_bps=5.0,
        parameters={"dca_cadence": "monthly"},
    )

    metrics = _run_with_signals(
        config=config,
        strategy_prices=strategy_prices,
        benchmark_prices=benchmark_prices,
        entries=entries,
        exits=[False, False, False],
    )
    performance = metrics["aggregate"]["performance"]

    # Independent cash ledger: each side receives exactly two $1,000 deposits.
    def cash_per_strategy_share(price: float) -> float:
        return price * (1.0 + slippage) * (1.0 + fee)
    strategy_shares = sum(
        contribution / cash_per_strategy_share(strategy_prices[index])
        for index in (0, 2)
    )
    expected_strategy_value = strategy_shares * strategy_prices[-1]

    normalized_benchmark = [price / benchmark_prices[0] for price in benchmark_prices]
    benchmark_shares = sum(
        contribution / cash_per_strategy_share(normalized_benchmark[index])
        for index in (0, 2)
    )
    expected_benchmark_value = benchmark_shares * normalized_benchmark[-1]
    invested_cash = contribution * 2
    expected_strategy_return = (expected_strategy_value / invested_cash - 1.0) * 100.0
    expected_benchmark_return = (
        expected_benchmark_value / invested_cash - 1.0
    ) * 100.0

    assert performance["total_return_pct"] == pytest.approx(
        expected_strategy_return, abs=0.01
    )
    assert performance["benchmark_return_pct"] == pytest.approx(
        expected_benchmark_return, abs=0.01
    )
    assert performance["delta_vs_benchmark_pct"] == pytest.approx(
        expected_strategy_return - expected_benchmark_return,
        abs=0.01,
    )
    assert performance["profit"] == pytest.approx(
        expected_strategy_value - invested_cash, abs=0.01
    )
    assert metrics["aggregate"]["efficiency"]["total_trades"] == 2

    lump_sum_benchmark_return = (
        normalized_benchmark[-1]
        / ((1.0 + slippage) * (1.0 + fee))
        - 1.0
    ) * 100.0
    assert performance["benchmark_return_pct"] != pytest.approx(
        lump_sum_benchmark_return, abs=0.01
    )


def test_short_dca_window_can_lose_money_when_fees_exceed_the_gain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "true")
    fee = 200.0 / 10_000.0
    slippage = 100.0 / 10_000.0
    contribution = 1_000.0
    config = _config(
        template="dca_accumulation",
        periods=2,
        fee_bps=200.0,
        slippage_bps=100.0,
        parameters={"dca_cadence": "monthly"},
    )
    metrics = _run_with_signals(
        config=config,
        strategy_prices=[100.0, 101.0],
        benchmark_prices=[100.0, 102.0],
        entries=[True, False],
        exits=[False, False],
    )
    performance = metrics["aggregate"]["performance"]

    shares = contribution / (100.0 * (1.0 + slippage) * (1.0 + fee))
    expected_ending_value = shares * 101.0
    expected_net_return = (expected_ending_value / contribution - 1.0) * 100.0
    expected_gross_return = 1.0

    assert performance["total_return_pct"] == pytest.approx(
        expected_net_return, abs=0.01
    )
    assert performance["profit"] == pytest.approx(
        expected_ending_value - contribution, abs=0.01
    )
    assert performance["execution_realism"]["gross_total_return_pct"] == 1.0
    assert performance["execution_realism"]["net_total_return_pct"] == pytest.approx(
        expected_net_return, abs=0.01
    )
    assert performance["execution_realism"]["return_drag_pct"] == pytest.approx(
        expected_gross_return - expected_net_return, abs=0.01
    )
    assert metrics["aggregate"]["efficiency"]["total_trades"] == 1
