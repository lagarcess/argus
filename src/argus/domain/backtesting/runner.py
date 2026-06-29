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
    portfolio_value_summary,
)
from argus.domain.backtesting.signals import _build_signals
from argus.domain.market_data import fetch_ohlcv, fetch_price_series

_MIN_BENCHMARK_OBSERVATION_COVERAGE = 0.8


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
    aligned, coverage = _align_benchmark_series(
        benchmark_series,
        target_index,
    )
    if aligned.empty:
        raise ValueError("market_data_unavailable")
    normalized = aligned / float(aligned.iloc[0])
    return {
        "symbol": benchmark_symbol,
        "equity_curve": normalized.tolist(),
        "total_return_pct": round((float(normalized.iloc[-1]) - 1.0) * 100.0, 2),
        "coverage": coverage,
    }


def _align_benchmark_series(
    benchmark_series: pd.Series,
    target_index: pd.DatetimeIndex,
) -> tuple[pd.Series, dict[str, Any]]:
    target = pd.DatetimeIndex(target_index)
    if target.empty:
        raise ValueError("market_data_unavailable")
    target = target.unique().sort_values()

    benchmark = pd.Series(benchmark_series).dropna().astype(float)
    if benchmark.empty:
        raise ValueError("market_data_unavailable")
    benchmark.index = _coerce_index_timezone(benchmark.index, target)
    benchmark = benchmark[~benchmark.index.duplicated(keep="last")].sort_index()

    first_target = target[0]
    last_target = target[-1]
    if benchmark.index[0] > first_target or benchmark.index[-1] < last_target:
        raise ValueError("benchmark_data_unavailable")

    observed_points = int(benchmark.reindex(target).notna().sum())
    target_points = int(len(target))
    observed_ratio = observed_points / target_points
    min_ratio = 1.0 if target_points <= 2 else _MIN_BENCHMARK_OBSERVATION_COVERAGE
    if observed_ratio < min_ratio:
        raise ValueError("benchmark_data_unavailable")

    aligned = (
        benchmark.reindex(benchmark.index.union(target))
        .sort_index()
        .ffill()
        .reindex(target)
    )
    if aligned.isna().any():
        raise ValueError("benchmark_data_unavailable")
    return aligned, {
        "observed_points": observed_points,
        "target_points": target_points,
        "observed_ratio": round(observed_ratio, 4),
    }


def _coerce_index_timezone(
    index: pd.Index,
    target: pd.DatetimeIndex,
) -> pd.DatetimeIndex:
    coerced = pd.DatetimeIndex(index)
    if target.tz is None:
        if coerced.tz is not None:
            return coerced.tz_convert("UTC").tz_localize(None)
        return coerced
    if coerced.tz is None:
        return coerced.tz_localize(target.tz)
    return coerced.tz_convert(target.tz)


def compute_alpha_metrics(
    config: dict[str, Any],
    *,
    fetch_ohlcv_func=fetch_ohlcv,
    build_signals_func=_build_signals,
    build_benchmark_curve_func=build_benchmark_curve,
) -> dict[str, Any]:
    by_symbol: dict[str, Any] = {}
    symbol_equity_curves: list[pd.Series] = []
    benchmark_equity_curves: list[pd.Series] = []
    gross_symbol_equity_curves: list[pd.Series] = []
    periods_per_year = _periods_per_year(config["timeframe"])
    start = date.fromisoformat(config["start_date"])
    end = date.fromisoformat(config["end_date"])
    allocation_capital = float(config["starting_capital"]) / len(config["symbols"])
    realism = _execution_realism_settings(config)
    has_modeled_costs = _execution_realism_has_costs(realism)
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
                fees=float(realism["fees"]),
                slippage=float(realism["slippage"]),
            )
            benchmark_equity, benchmark_invested_capital = _dca_equity_curve(
                close=benchmark_normalized,
                entries=entries,
                contribution=allocation_capital,
            )
            if has_modeled_costs:
                gross_symbol_equity, _ = _dca_equity_curve(
                    close=close,
                    entries=entries,
                    contribution=allocation_capital,
                )
                gross_symbol_equity_curves.append(gross_symbol_equity)
            invested_capital = max(invested_capital, benchmark_invested_capital)
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
            if has_modeled_costs:
                gross_portfolio = vbt.Portfolio.from_signals(
                    close=close,
                    entries=entries,
                    exits=exits,
                    fees=0.0,
                    slippage=0.0,
                    init_cash=allocation_capital,
                    freq=_vbt_freq(config["timeframe"]),
                    accumulate=False,
                )
                gross_symbol_equity_curves.append(
                    pd.Series(
                        gross_portfolio.value().values,
                        index=close.index,
                        dtype=float,
                    )
                )
            benchmark_equity = benchmark_normalized * allocation_capital
            if has_modeled_costs:
                # Equity-based math captures the entry-cost hit at t0 that a
                # pct_change return series cannot see.
                by_symbol[symbol] = _compute_metrics_from_equity(
                    strategy_equity=symbol_equity,
                    benchmark_equity=benchmark_equity,
                    invested_capital=allocation_capital,
                    periods_per_year=periods_per_year,
                    trade_count=_execution_fill_count(execution_events),
                )
            else:
                # No modeled costs: keep the legacy returns-based computation
                # bit-for-bit so flag-off output stays byte-identical.
                by_symbol[symbol] = _compute_metrics(
                    strategy_returns=symbol_equity.pct_change().fillna(0.0),
                    benchmark_returns=benchmark_equity.pct_change().fillna(0.0),
                    allocation_capital=allocation_capital,
                    periods_per_year=periods_per_year,
                    trade_count=_execution_fill_count(execution_events),
                )

        symbol_equity_curves.append(symbol_equity)
        benchmark_equity_curves.append(benchmark_equity)

    aggregate_strategy_equity = (
        pd.concat(symbol_equity_curves, axis=1).ffill().bfill().sum(axis=1)
    )
    aggregate_benchmark_equity = (
        pd.concat(benchmark_equity_curves, axis=1).ffill().bfill().sum(axis=1)
    )
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
        aggregate_invested = float(config["starting_capital"])
        if has_modeled_costs:
            aggregate_metrics = _compute_metrics_from_equity(
                strategy_equity=aggregate_strategy_equity,
                benchmark_equity=aggregate_benchmark_equity,
                invested_capital=aggregate_invested,
                periods_per_year=periods_per_year,
                trade_count=trade_count,
            )
        else:
            aggregate_metrics = _compute_metrics(
                strategy_returns=aggregate_strategy_equity.pct_change().fillna(0.0),
                benchmark_returns=aggregate_benchmark_equity.pct_change().fillna(0.0),
                allocation_capital=aggregate_invested,
                periods_per_year=periods_per_year,
                trade_count=trade_count,
            )
    if has_modeled_costs and gross_symbol_equity_curves:
        gross_aggregate_equity = (
            pd.concat(gross_symbol_equity_curves, axis=1).ffill().bfill().sum(axis=1)
        )
        gross_metrics = _compute_metrics_from_equity(
            strategy_equity=gross_aggregate_equity,
            benchmark_equity=aggregate_benchmark_equity,
            invested_capital=aggregate_invested,
            periods_per_year=periods_per_year,
            trade_count=trade_count,
        )
        aggregate_metrics.setdefault("performance", {})[
            "execution_realism"
        ] = _execution_realism_performance_summary(
            realism=realism,
            gross_performance=gross_metrics["performance"],
            net_performance=aggregate_metrics["performance"],
        )
    value_summary = portfolio_value_summary(aggregate_strategy_equity)
    if value_summary is not None:
        aggregate_metrics.setdefault("performance", {})[
            "portfolio_value_range"
        ] = value_summary

    return {
        "aggregate": aggregate_metrics,
        "by_symbol": by_symbol,
    }


def _execution_realism_has_costs(realism: dict[str, float | bool]) -> bool:
    return bool(realism["enabled"]) and (
        float(realism["fees"]) > 0.0 or float(realism["slippage"]) > 0.0
    )


def _execution_realism_performance_summary(
    *,
    realism: dict[str, float | bool],
    gross_performance: dict[str, Any],
    net_performance: dict[str, Any],
) -> dict[str, Any]:
    gross_return = float(gross_performance["total_return_pct"])
    net_return = float(net_performance["total_return_pct"])
    return {
        "enabled": True,
        "fee_bps": round(float(realism["fees"]) * 10000.0, 4),
        "slippage_bps": round(float(realism["slippage"]) * 10000.0, 4),
        "gross_total_return_pct": gross_return,
        "net_total_return_pct": net_return,
        "return_drag_pct": round(gross_return - net_return, 2),
    }
