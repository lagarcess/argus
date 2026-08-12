from __future__ import annotations

from datetime import date, datetime, time
from math import sqrt

import pandas as pd
import pytest
from argus.agent_runtime.result_fact_enrichment import enriched_result_fact_entries
from argus.domain.backtesting.cards import build_result_card
from argus.domain.backtesting.charts import build_result_chart
from argus.domain.backtesting.coverage import (
    MarketDataCoverageError,
    build_metric_time_basis,
    prepare_market_data,
)
from argus.domain.backtesting.runner import compute_alpha_metrics
from argus.domain.market_data.capabilities import EquityMarketSession


def _bars(
    prices: list[float],
    *,
    index: pd.DatetimeIndex | None = None,
) -> pd.DataFrame:
    if index is None:
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
    asset_class: str = "equity",
    timeframe: str = "1D",
    index: pd.DatetimeIndex | None = None,
    symbols: list[str] | None = None,
    benchmark_symbol: str | None = None,
    starting_capital: float = 1_000.0,
) -> dict[str, object]:
    config_index = (
        index
        if index is not None
        else pd.bdate_range("2025-01-02", periods=periods, tz="UTC")
    )
    selected_symbols = symbols or ["AAPL"]
    return {
        "template": template,
        "asset_class": asset_class,
        "symbols": selected_symbols,
        "timeframe": timeframe,
        "start_date": config_index[0].date().isoformat(),
        "end_date": config_index[-1].date().isoformat(),
        "starting_capital": starting_capital,
        "allocation_method": "equal_weight",
        "benchmark_symbol": benchmark_symbol
        or ("SPY" if asset_class == "equity" else "BTC"),
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
    index: pd.DatetimeIndex | None = None,
) -> dict[str, object]:
    strategy_bars = _bars(strategy_prices, index=index)
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
        "win_rate": None,
        "total_trades": 0,
        "profit_factor": None,
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
        contribution / cash_per_strategy_share(strategy_prices[index]) for index in (0, 2)
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
    expected_benchmark_return = (expected_benchmark_value / invested_cash - 1.0) * 100.0

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
    assert metrics["aggregate"]["efficiency"]["win_rate"] is None
    assert metrics["aggregate"]["efficiency"]["profit_factor"] is None

    lump_sum_benchmark_return = (
        normalized_benchmark[-1] / ((1.0 + slippage) * (1.0 + fee)) - 1.0
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

    assert performance["total_return_pct"] == pytest.approx(expected_net_return, abs=0.01)
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


@pytest.mark.parametrize(
    ("fee_bps", "slippage_bps"),
    [(0.0, 0.0), (10.0, 5.0)],
)
def test_closed_trade_efficiency_uses_net_realized_pnl_in_both_metric_paths(
    monkeypatch: pytest.MonkeyPatch,
    fee_bps: float,
    slippage_bps: float,
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "true")
    config = _config(
        template="signal_strategy",
        periods=5,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
    )
    metrics = _run_with_signals(
        config=config,
        strategy_prices=[100.0, 80.0, 110.0, 100.0, 90.0],
        benchmark_prices=[100.0] * 5,
        entries=[True, False, False, True, False],
        exits=[False, False, True, False, True],
    )

    fee = fee_bps / 10_000.0
    slippage = slippage_bps / 10_000.0
    first_shares = 1_000.0 / (100.0 * (1.0 + slippage) * (1.0 + fee))
    first_proceeds = first_shares * 110.0 * (1.0 - slippage) * (1.0 - fee)
    winning_pnl = first_proceeds - 1_000.0
    second_shares = first_proceeds / (100.0 * (1.0 + slippage) * (1.0 + fee))
    second_proceeds = second_shares * 90.0 * (1.0 - slippage) * (1.0 - fee)
    losing_pnl = second_proceeds - first_proceeds
    expected_profit_factor = winning_pnl / abs(losing_pnl)

    efficiency = metrics["aggregate"]["efficiency"]
    assert efficiency["win_rate"] == 0.5
    assert efficiency["profit_factor"] == pytest.approx(
        expected_profit_factor,
        abs=0.01,
    )


@pytest.mark.parametrize(
    ("prices", "exits", "expected_win_rate", "expected_profit_factor"),
    [
        ([100.0, 80.0, 110.0], [False, False, True], 1.0, None),
        ([100.0, 120.0, 90.0], [False, False, True], 0.0, 0.0),
        ([100.0, 80.0, 110.0], [False, False, False], None, None),
        ([100.0, 110.0, 100.0], [False, False, True], 0.0, None),
    ],
    ids=["winning", "losing", "open", "breakeven"],
)
def test_closed_trade_efficiency_has_typed_boundary_states(
    monkeypatch: pytest.MonkeyPatch,
    prices: list[float],
    exits: list[bool],
    expected_win_rate: float | None,
    expected_profit_factor: float | None,
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "true")
    metrics = _run_with_signals(
        config=_config(
            template="signal_strategy",
            periods=3,
            fee_bps=0.0,
            slippage_bps=0.0,
        ),
        strategy_prices=prices,
        benchmark_prices=[100.0] * 3,
        entries=[True, False, False],
        exits=exits,
    )

    efficiency = metrics["aggregate"]["efficiency"]
    assert efficiency["win_rate"] == expected_win_rate
    assert efficiency["profit_factor"] == expected_profit_factor


def test_same_bar_exit_and_reentry_share_one_execution_truth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "true")
    fee = 0.01
    slippage = 0.005
    config = _config(
        template="signal_strategy",
        periods=3,
        fee_bps=100.0,
        slippage_bps=50.0,
    )
    strategy_prices = [100.0, 110.0, 90.0]
    entries = [True, True, False]
    exits = [False, True, False]
    metrics = _run_with_signals(
        config=config,
        strategy_prices=strategy_prices,
        benchmark_prices=[100.0] * 3,
        entries=entries,
        exits=exits,
    )
    bars = _bars(strategy_prices)
    chart = build_result_chart(
        config,
        fetch_ohlcv_func=lambda **_: bars,
        build_signals_func=lambda *_: (
            pd.Series(entries, index=bars.index, dtype=bool),
            pd.Series(exits, index=bars.index, dtype=bool),
        ),
    )

    first_shares = 1_000.0 / (100.0 * (1.0 + slippage) * (1.0 + fee))
    first_exit_proceeds = first_shares * 110.0 * (1.0 - slippage) * (1.0 - fee)
    second_shares = first_exit_proceeds / (110.0 * (1.0 + slippage) * (1.0 + fee))
    ending_value = second_shares * 90.0
    expected_total_return_pct = (ending_value / 1_000.0 - 1.0) * 100.0

    efficiency = metrics["aggregate"]["efficiency"]
    assert efficiency["total_trades"] == 3
    assert efficiency["win_rate"] == 1.0
    assert efficiency["profit_factor"] is None
    assert metrics["aggregate"]["performance"]["total_return_pct"] == pytest.approx(
        expected_total_return_pct,
        abs=0.01,
    )
    assert chart["series"][-1]["value"] == pytest.approx(ending_value, abs=0.01)


def test_multi_symbol_efficiency_combines_closed_trade_pnl() -> None:
    index = pd.bdate_range("2025-01-02", periods=2, tz="UTC")
    bars_by_symbol = {
        "AAPL": _bars([100.0, 110.0], index=index),
        "MSFT": _bars([100.0, 90.0], index=index),
    }
    entries = pd.Series([True, False], index=index, dtype=bool)
    exits = pd.Series([False, True], index=index, dtype=bool)
    config = _config(
        template="signal_strategy",
        periods=2,
        fee_bps=0.0,
        slippage_bps=0.0,
        index=index,
        symbols=["AAPL", "MSFT"],
        starting_capital=2_000.0,
    )

    metrics = compute_alpha_metrics(
        config,
        fetch_ohlcv_func=lambda *, symbol, **_: bars_by_symbol[symbol],
        build_signals_func=lambda *_: (entries, exits),
        build_benchmark_curve_func=lambda *_args, **_kwargs: {
            "equity_curve": [1.0, 1.0],
        },
    )

    assert metrics["by_symbol"]["AAPL"]["efficiency"]["win_rate"] == 1.0
    assert metrics["by_symbol"]["AAPL"]["efficiency"]["profit_factor"] is None
    assert metrics["by_symbol"]["MSFT"]["efficiency"]["win_rate"] == 0.0
    assert metrics["by_symbol"]["MSFT"]["efficiency"]["profit_factor"] == 0.0
    assert metrics["aggregate"]["efficiency"]["win_rate"] == 0.5
    assert metrics["aggregate"]["efficiency"]["profit_factor"] == 1.0


def test_open_positions_are_omitted_from_card_and_result_fact_bank() -> None:
    index = pd.bdate_range("2025-01-02", periods=3, tz="UTC")
    bars_by_symbol = {
        "AAPL": _bars([100.0, 90.0, 110.0], index=index),
        "MSFT": _bars([100.0, 110.0, 90.0], index=index),
    }
    entries = pd.Series([True, False, False], index=index, dtype=bool)
    exits = pd.Series([False, False, False], index=index, dtype=bool)
    config = _config(
        template="signal_strategy",
        periods=3,
        fee_bps=0.0,
        slippage_bps=0.0,
        index=index,
        symbols=["AAPL", "MSFT"],
        starting_capital=2_000.0,
    )
    metrics = compute_alpha_metrics(
        config,
        fetch_ohlcv_func=lambda *, symbol, **_: bars_by_symbol[symbol],
        build_signals_func=lambda *_: (entries, exits),
        build_benchmark_curve_func=lambda *_args, **_kwargs: {
            "equity_curve": [1.0, 1.0, 1.0],
        },
    )

    efficiency = metrics["aggregate"]["efficiency"]
    assert efficiency["total_trades"] == 2
    assert efficiency["win_rate"] is None
    assert efficiency["profit_factor"] is None
    assert "win_rate" not in {
        row["key"] for row in build_result_card(config, metrics)["rows"]
    }
    facts = enriched_result_fact_entries({"metrics": metrics})
    assert "win_rate" not in facts
    assert "profit_factor" not in facts


@pytest.mark.parametrize(
    ("fee_bps", "slippage_bps"),
    [(0.0, 0.0), (10.0, 5.0)],
)
def test_annualized_return_uses_elapsed_time_in_both_metric_paths(
    monkeypatch: pytest.MonkeyPatch,
    fee_bps: float,
    slippage_bps: float,
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "true")
    index = pd.DatetimeIndex(
        ["2025-01-01", "2025-07-01", "2025-12-31"],
        tz="UTC",
    )
    metrics = _run_with_signals(
        config=_config(
            template="signal_strategy",
            periods=3,
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
            asset_class="crypto",
            index=index,
        ),
        strategy_prices=[100.0, 100.0, 110.0],
        benchmark_prices=[100.0] * 3,
        entries=[True, False, False],
        exits=[False, False, False],
        index=index,
    )

    fee = fee_bps / 10_000.0
    slippage = slippage_bps / 10_000.0
    shares = 1_000.0 / (100.0 * (1.0 + slippage) * (1.0 + fee))
    total_return = shares * 110.0 / 1_000.0 - 1.0
    elapsed_years = 364.0 / 365.2425
    expected_annualized = ((1.0 + total_return) ** (1.0 / elapsed_years) - 1.0) * 100.0

    performance = metrics["aggregate"]["performance"]
    assert performance["total_return_pct"] == pytest.approx(
        total_return * 100.0,
        abs=0.01,
    )
    assert performance["annualized_return_pct"] == pytest.approx(
        expected_annualized,
        abs=0.01,
    )


@pytest.mark.parametrize(
    ("fee_bps", "slippage_bps"),
    [(0.0, 0.0), (10.0, 5.0)],
)
def test_two_bar_annualization_uses_the_single_elapsed_interval(
    monkeypatch: pytest.MonkeyPatch,
    fee_bps: float,
    slippage_bps: float,
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "true")
    index = pd.DatetimeIndex(["2025-01-01", "2025-01-02"], tz="UTC")
    metrics = _run_with_signals(
        config=_config(
            template="signal_strategy",
            periods=2,
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
            asset_class="crypto",
            index=index,
        ),
        strategy_prices=[100.0, 101.0],
        benchmark_prices=[100.0, 100.0],
        entries=[True, False],
        exits=[False, False],
        index=index,
    )

    fee = fee_bps / 10_000.0
    slippage = slippage_bps / 10_000.0
    shares = 1_000.0 / (100.0 * (1.0 + slippage) * (1.0 + fee))
    total_return = shares * 101.0 / 1_000.0 - 1.0
    expected_annualized = ((1.0 + total_return) ** 365.2425 - 1.0) * 100.0

    assert metrics["aggregate"]["performance"]["annualized_return_pct"] == pytest.approx(
        expected_annualized, abs=0.01
    )


def test_continuous_daily_dispersion_uses_a_calendar_year() -> None:
    index = pd.DatetimeIndex(
        ["2025-01-01", "2025-01-02", "2025-01-03"],
        tz="UTC",
    )
    metrics = _run_with_signals(
        config=_config(
            template="signal_strategy",
            periods=3,
            fee_bps=0.0,
            slippage_bps=0.0,
            asset_class="crypto",
            index=index,
        ),
        strategy_prices=[100.0, 100.0, 110.0],
        benchmark_prices=[100.0] * 3,
        entries=[True, False, False],
        exits=[False, False, False],
        index=index,
    )

    # Returns are [0, 0, 0.10], whose sample standard deviation is 0.10/sqrt(3).
    expected_volatility = (0.10 / sqrt(3.0)) * sqrt(365.2425) * 100.0
    expected_sharpe = sqrt(365.2425 / 3.0)

    assert metrics["aggregate"]["risk"]["volatility_pct"] == pytest.approx(
        expected_volatility,
        abs=0.01,
    )
    assert metrics["aggregate"]["efficiency"]["sharpe_ratio"] == pytest.approx(
        expected_sharpe,
        abs=0.01,
    )


def test_currency_pair_daily_dispersion_uses_provider_continuous_calendar() -> None:
    index = pd.DatetimeIndex(
        ["2025-01-01", "2025-01-02", "2025-01-03"],
        tz="UTC",
    )
    metrics = _run_with_signals(
        config=_config(
            template="signal_strategy",
            periods=3,
            fee_bps=0.0,
            slippage_bps=0.0,
            asset_class="currency_pair",
            index=index,
            symbols=["EURUSD"],
            benchmark_symbol="EURUSD",
        ),
        strategy_prices=[100.0, 100.0, 110.0],
        benchmark_prices=[100.0] * 3,
        entries=[True, False, False],
        exits=[False, False, False],
        index=index,
    )

    provider_days_per_year = 365.2425
    expected_volatility = (0.10 / sqrt(3.0)) * sqrt(provider_days_per_year) * 100.0
    expected_sharpe = sqrt(provider_days_per_year / 3.0)

    assert metrics["aggregate"]["risk"]["volatility_pct"] == pytest.approx(
        expected_volatility,
        abs=0.01,
    )
    assert metrics["aggregate"]["efficiency"]["sharpe_ratio"] == pytest.approx(
        expected_sharpe,
        abs=0.01,
    )


@pytest.mark.parametrize(
    ("asset_class", "timeframe", "expected_periods_per_year"),
    [
        ("equity", "1D", 252.0),
        ("equity", "1h", 1_638.0),
        ("equity", "2h", 819.0),
        ("equity", "4h", 409.5),
        ("equity", "6h", 273.0),
        ("equity", "12h", 252.0),
        ("crypto", "1D", 365.2425),
        ("crypto", "1h", 8_765.82),
        ("crypto", "2h", 4_382.91),
        ("crypto", "4h", 2_191.455),
        ("crypto", "6h", 1_460.97),
        ("crypto", "12h", 730.485),
        ("currency_pair", "1D", 365.2425),
        ("currency_pair", "1h", 8_765.82),
        ("currency_pair", "4h", 2_191.455),
    ],
)
def test_metric_time_basis_covers_every_asset_and_timeframe(
    asset_class: str,
    timeframe: str,
    expected_periods_per_year: float,
) -> None:
    session_date = date(2025, 1, 2)
    equity_sessions = (
        EquityMarketSession(
            provider="test-calendar",
            session_date=session_date,
            opens_at=datetime.combine(session_date, time(9, 30)),
            closes_at=datetime.combine(session_date, time(16, 0)),
        ),
    )
    index = pd.DatetimeIndex(["2025-01-02T14:30:00Z", "2025-01-03T14:30:00Z"])

    basis = build_metric_time_basis(
        asset_class=asset_class,
        timeframe=timeframe,
        effective_index=index,
        equity_market_sessions=equity_sessions,
    )

    assert basis.periods_per_year == pytest.approx(expected_periods_per_year)


def test_equity_time_basis_uses_only_sessions_in_the_effective_window() -> None:
    effective_date = date(2025, 1, 2)
    outside_date = date(2025, 7, 3)
    sessions = (
        EquityMarketSession(
            provider="test-calendar",
            session_date=effective_date,
            opens_at=datetime.combine(effective_date, time(9, 30)),
            closes_at=datetime.combine(effective_date, time(16, 0)),
        ),
        EquityMarketSession(
            provider="test-calendar",
            session_date=outside_date,
            opens_at=datetime.combine(outside_date, time(9, 30)),
            closes_at=datetime.combine(outside_date, time(13, 0)),
        ),
    )
    index = pd.DatetimeIndex(["2025-01-02T14:30:00Z", "2025-01-02T20:30:00Z"])

    basis = build_metric_time_basis(
        asset_class="equity",
        timeframe="1h",
        effective_index=index,
        equity_market_sessions=sessions,
    )

    assert tuple(
        session.session_date for session in basis.equity_market_sessions or ()
    ) == (effective_date,)
    assert basis.periods_per_year == 1_638.0


def test_equity_intraday_dispersion_uses_real_sessions_and_early_closes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    sessions = tuple(
        EquityMarketSession(
            provider="test-calendar",
            session_date=session_date,
            opens_at=datetime.combine(
                session_date,
                time(9, 30),
            ),
            closes_at=datetime.combine(
                session_date,
                time(13, 0) if session_date == date(2025, 1, 3) else time(16, 0),
            ),
        )
        for session_date in (date(2025, 1, 2), date(2025, 1, 3))
    )

    def market_calendar(
        *,
        start_date: date,
        end_date: date,
    ) -> tuple[EquityMarketSession, ...]:
        return tuple(
            session
            for session in sessions
            if start_date <= session.session_date <= end_date
        )

    index = pd.DatetimeIndex(
        [
            *pd.date_range("2025-01-02T14:30:00Z", periods=7, freq="h"),
            *pd.date_range("2025-01-03T14:30:00Z", periods=4, freq="h"),
        ]
    )
    strategy_bars = _bars([100.0, 110.0, *([110.0] * 9)], index=index)
    benchmark_bars = _bars([100.0] * 11, index=index)
    config = _config(
        template="signal_strategy",
        periods=11,
        fee_bps=0.0,
        slippage_bps=0.0,
        timeframe="1h",
        index=index,
    )
    prepared = prepare_market_data(
        config,
        fetch_ohlcv_func=lambda *, symbol, **_: (
            strategy_bars if symbol == "AAPL" else benchmark_bars
        ),
        fetch_market_calendar_func=market_calendar,
    )
    entries = pd.Series([True, *([False] * 10)], index=index, dtype=bool)
    exits = pd.Series(False, index=index, dtype=bool)
    metrics = compute_alpha_metrics(
        config,
        build_signals_func=lambda *_: (entries, exits),
        prepared_market_data=prepared,
    )

    # One 390-minute session and one 210-minute early close average 300 minutes.
    # The shared equity basis is 252 * 300 / 60 = 1,260 hourly periods.
    expected_periods_per_year = 1_260.0
    expected_volatility = (0.10 / sqrt(11.0)) * sqrt(expected_periods_per_year) * 100.0
    expected_sharpe = sqrt(expected_periods_per_year / 11.0)

    assert metrics["aggregate"]["risk"]["volatility_pct"] == pytest.approx(
        expected_volatility,
        abs=0.01,
    )
    assert metrics["aggregate"]["efficiency"]["sharpe_ratio"] == pytest.approx(
        expected_sharpe,
        abs=0.01,
    )
