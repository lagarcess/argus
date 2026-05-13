from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import vectorbt as vbt

from argus.domain.backtesting.config import _periods_per_year, _vbt_freq
from argus.domain.backtesting.execution import (
    _build_long_only_execution_ledger,
    _dca_equity_curve,
    _execution_fill_count,
    _execution_realism_settings,
)
from argus.domain.backtesting.metrics import (
    _compute_metrics,
    _compute_metrics_from_equity,
)
from argus.domain.backtesting.signals import _build_signals
from argus.domain.market_data import fetch_ohlcv, fetch_price_series


def build_benchmark_curve(
    config: dict[str, Any],
    target_index: pd.DatetimeIndex,
    *,
    fetch_price_series_func=fetch_price_series,
) -> dict[str, Any]:
    benchmark_symbol = config["benchmark_symbol"]
    benchmark_series = fetch_price_series_func(
        symbol=benchmark_symbol,
        asset_class=config["asset_class"],
        start_date=date.fromisoformat(config["start_date"]),
        end_date=date.fromisoformat(config["end_date"]),
        timeframe=config["timeframe"],
    )
    aligned = benchmark_series.reindex(target_index).ffill().bfill()
    if aligned.empty:
        raise ValueError("market_data_unavailable")
    normalized = aligned / float(aligned.iloc[0])
    return {
        "symbol": benchmark_symbol,
        "equity_curve": normalized.tolist(),
        "total_return_pct": round((float(normalized.iloc[-1]) - 1.0) * 100.0, 2),
    }


def compute_alpha_metrics(
    config: dict[str, Any],
    *,
    fetch_ohlcv_func=fetch_ohlcv,
    build_signals_func=_build_signals,
    build_benchmark_curve_func=build_benchmark_curve,
) -> dict[str, Any]:
    by_symbol: dict[str, Any] = {}
    symbol_returns: list[pd.Series] = []
    benchmark_returns_aligned: list[pd.Series] = []
    symbol_equity_curves: list[pd.Series] = []
    benchmark_equity_curves: list[pd.Series] = []
    periods_per_year = _periods_per_year(config["timeframe"])
    start = date.fromisoformat(config["start_date"])
    end = date.fromisoformat(config["end_date"])
    allocation_capital = float(config["starting_capital"]) / len(config["symbols"])
    realism = _execution_realism_settings(config)
    is_dca = config["template"] == "dca_accumulation"

    for symbol in config["symbols"]:
        bars = fetch_ohlcv_func(
            symbol=symbol,
            asset_class=config["asset_class"],
            start_date=start,
            end_date=end,
            timeframe=config["timeframe"],
        )
        close = bars["close"].astype(float)
        entries, exits = build_signals_func(config, bars)
        execution_events = _build_long_only_execution_ledger(
            symbol=symbol,
            entries=entries,
            exits=exits,
            allow_accumulation=is_dca,
        )

        benchmark_curve = build_benchmark_curve_func(config, close.index)
        benchmark_normalized = pd.Series(
            benchmark_curve["equity_curve"], index=close.index, dtype=float
        )
        if is_dca:
            symbol_equity, invested_capital = _dca_equity_curve(
                close=close,
                entries=entries,
                contribution=allocation_capital,
            )
            benchmark_equity, benchmark_invested_capital = _dca_equity_curve(
                close=benchmark_normalized,
                entries=entries,
                contribution=allocation_capital,
            )
            invested_capital = max(invested_capital, benchmark_invested_capital)
            strategy_returns = symbol_equity.pct_change().fillna(0.0)
            benchmark_returns = benchmark_equity.pct_change().fillna(0.0)
            by_symbol[symbol] = _compute_metrics_from_equity(
                strategy_equity=symbol_equity,
                benchmark_equity=benchmark_equity,
                invested_capital=invested_capital,
                periods_per_year=periods_per_year,
                trade_count=_execution_fill_count(execution_events, side="buy"),
            )
        else:
            portfolio = vbt.Portfolio.from_signals(
                close=close,
                entries=entries,
                exits=exits,
                fees=float(realism["fees"]),
                slippage=float(realism["slippage"]),
                init_cash=allocation_capital,
                freq=_vbt_freq(config["timeframe"]),
                accumulate=False,
            )

            symbol_equity = pd.Series(
                portfolio.value().values, index=close.index, dtype=float
            )
            strategy_returns = symbol_equity.pct_change().fillna(0.0)
            benchmark_equity = benchmark_normalized * allocation_capital
            benchmark_returns = benchmark_equity.pct_change().fillna(0.0)
            by_symbol[symbol] = _compute_metrics(
                strategy_returns=strategy_returns,
                benchmark_returns=benchmark_returns,
                allocation_capital=allocation_capital,
                periods_per_year=periods_per_year,
                trade_count=_execution_fill_count(execution_events),
            )

        symbol_returns.append(strategy_returns)
        benchmark_returns_aligned.append(benchmark_returns)
        symbol_equity_curves.append(symbol_equity)
        benchmark_equity_curves.append(benchmark_equity)

    aggregate_strategy_equity = (
        pd.concat(symbol_equity_curves, axis=1).ffill().bfill().sum(axis=1)
    )
    aggregate_benchmark_equity = (
        pd.concat(benchmark_equity_curves, axis=1).ffill().bfill().sum(axis=1)
    )
    aggregate_strategy_returns = aggregate_strategy_equity.pct_change().fillna(0.0)
    aggregate_benchmark_returns = aggregate_benchmark_equity.pct_change().fillna(0.0)

    trade_count = sum(row["efficiency"]["total_trades"] for row in by_symbol.values())
    if is_dca:
        aggregate_invested = allocation_capital * max(trade_count, 1)
        aggregate_metrics = _compute_metrics_from_equity(
            strategy_equity=aggregate_strategy_equity,
            benchmark_equity=aggregate_benchmark_equity,
            invested_capital=aggregate_invested,
            periods_per_year=periods_per_year,
            trade_count=trade_count,
        )
    else:
        aggregate_metrics = _compute_metrics(
            strategy_returns=aggregate_strategy_returns,
            benchmark_returns=aggregate_benchmark_returns,
            allocation_capital=float(config["starting_capital"]),
            periods_per_year=periods_per_year,
            trade_count=trade_count,
        )

    return {
        "aggregate": aggregate_metrics,
        "by_symbol": by_symbol,
    }
