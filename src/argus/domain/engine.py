from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd

from argus.domain.backtesting import cards as _cards
from argus.domain.backtesting import charts as _charts
from argus.domain.backtesting import config as _config
from argus.domain.backtesting import execution as _execution
from argus.domain.backtesting import metrics as _metrics
from argus.domain.backtesting import runner as _runner
from argus.domain.backtesting import signals as _signals
from argus.domain.backtesting.config import (
    ALLOWED_TEMPLATES,
    ALLOWED_TIMEFRAMES,
    STABLECOINS,
    AssetClass,
    SymbolAsset,
)
from argus.domain.backtesting.execution import ExecutionEvent
from argus.domain.market_data import fetch_ohlcv, fetch_price_series, resolve_asset

__all__ = [
    "ALLOWED_TEMPLATES",
    "ALLOWED_TIMEFRAMES",
    "STABLECOINS",
    "AssetClass",
    "ExecutionEvent",
    "SymbolAsset",
    "build_benchmark_curve",
    "build_result_card",
    "build_result_chart",
    "classify_symbol",
    "compute_alpha_metrics",
    "default_benchmark",
    "fetch_ohlcv",
    "fetch_price_series",
    "normalize_backtest_config",
    "resolve_asset",
    "validate_backtest_config",
]


def classify_symbol(symbol: str) -> SymbolAsset:
    return _config.classify_symbol(symbol, resolve_asset_func=resolve_asset)


def default_benchmark(asset_class: AssetClass, symbols: list[str] | None = None) -> str:
    return _config.default_benchmark(asset_class, symbols)


def _normalize_timeframe(timeframe: str | None) -> str:
    return _config._normalize_timeframe(timeframe)


def _to_date(value: str | date | datetime) -> date:
    return _config._to_date(value)


def _periods_per_year(timeframe: str) -> float:
    return _config._periods_per_year(timeframe)


def _vbt_freq(timeframe: str) -> str:
    return _config._vbt_freq(timeframe)


def _execution_realism_feature_enabled() -> bool:
    return _config._execution_realism_feature_enabled()


def _normalize_execution_realism(raw: Any) -> dict[str, Any]:
    return _config._normalize_execution_realism(raw)


def normalize_backtest_config(payload: dict[str, Any]) -> dict[str, Any]:
    return _config.normalize_backtest_config(
        payload,
        classify_symbol_func=classify_symbol,
        default_benchmark_func=default_benchmark,
    )


def validate_backtest_config(config: dict[str, Any]) -> None:
    return _config.validate_backtest_config(config)


def _resolve_indicator_series(
    data: pd.DataFrame,
    *,
    indicator: str,
    period: int,
    fallback_col: str = "close",
) -> pd.Series:
    return _signals._resolve_indicator_series(
        data,
        indicator=indicator,
        period=period,
        fallback_col=fallback_col,
    )


def _build_signals(
    config: dict[str, Any], data: pd.DataFrame
) -> tuple[pd.Series, pd.Series]:
    return _signals._build_signals(
        config,
        data,
        resolve_indicator_series_func=_resolve_indicator_series,
    )


def _index_period_series(index: pd.Index, *, freq: str) -> pd.Series:
    return _signals._index_period_series(index, freq=freq)


def _execution_realism_settings(config: dict[str, Any]) -> dict[str, float | bool]:
    return _execution._execution_realism_settings(config)


def _compute_profit_factor(returns: pd.Series) -> float:
    return _metrics._compute_profit_factor(returns)


def _compute_sharpe(returns: pd.Series, periods_per_year: float) -> float:
    return _metrics._compute_sharpe(returns, periods_per_year)


def _max_drawdown_pct(equity_curve: pd.Series) -> float:
    return _metrics._max_drawdown_pct(equity_curve)


def _annualized_return_pct(
    total_return: float, periods: int, periods_per_year: float
) -> float:
    return _metrics._annualized_return_pct(total_return, periods, periods_per_year)


def _build_long_only_execution_ledger(
    *,
    symbol: str,
    entries: pd.Series,
    exits: pd.Series,
    allow_accumulation: bool,
) -> list[ExecutionEvent]:
    return _execution._build_long_only_execution_ledger(
        symbol=symbol,
        entries=entries,
        exits=exits,
        allow_accumulation=allow_accumulation,
    )


def _execution_fill_count(
    execution_events: list[ExecutionEvent], *, side: str | None = None
) -> int:
    return _execution._execution_fill_count(execution_events, side=side)


def _compute_metrics(
    *,
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series,
    allocation_capital: float,
    periods_per_year: float,
    trade_count: int,
) -> dict[str, Any]:
    return _metrics._compute_metrics(
        strategy_returns=strategy_returns,
        benchmark_returns=benchmark_returns,
        allocation_capital=allocation_capital,
        periods_per_year=periods_per_year,
        trade_count=trade_count,
    )


def _compute_metrics_from_equity(
    *,
    strategy_equity: pd.Series,
    benchmark_equity: pd.Series,
    invested_capital: float,
    periods_per_year: float,
    trade_count: int,
) -> dict[str, Any]:
    return _metrics._compute_metrics_from_equity(
        strategy_equity=strategy_equity,
        benchmark_equity=benchmark_equity,
        invested_capital=invested_capital,
        periods_per_year=periods_per_year,
        trade_count=trade_count,
    )


def _dca_equity_curve(
    *,
    close: pd.Series,
    entries: pd.Series,
    contribution: float,
) -> tuple[pd.Series, float]:
    return _execution._dca_equity_curve(
        close=close,
        entries=entries,
        contribution=contribution,
    )


def build_benchmark_curve(
    config: dict[str, Any], target_index: pd.DatetimeIndex
) -> dict[str, Any]:
    return _runner.build_benchmark_curve(
        config,
        target_index,
        fetch_price_series_func=fetch_price_series,
    )


def compute_alpha_metrics(config: dict[str, Any]) -> dict[str, Any]:
    # Compatibility note: the underlying runner still uses Portfolio.from_signals.
    return _runner.compute_alpha_metrics(
        config,
        fetch_ohlcv_func=fetch_ohlcv,
        build_signals_func=_build_signals,
        build_benchmark_curve_func=build_benchmark_curve,
    )


def build_result_chart(config: dict[str, Any]) -> dict[str, Any]:
    return _charts.build_result_chart(
        config,
        fetch_ohlcv_func=fetch_ohlcv,
        build_signals_func=_build_signals,
    )


def _collect_execution_fill_events(
    events: dict[str, dict[str, set[str]]],
    *,
    symbol: str,
    execution_events: list[ExecutionEvent],
) -> None:
    return _charts._collect_execution_fill_events(
        events,
        symbol=symbol,
        execution_events=execution_events,
    )


def _chart_time_key(timestamp: Any) -> str:
    return _charts._chart_time_key(timestamp)


def _chart_markers_from_events(
    events: dict[str, dict[str, set[str]]],
) -> list[dict[str, Any]]:
    return _charts._chart_markers_from_events(events)


def _event_label(prefix: str, symbols: list[str]) -> str:
    return _charts._event_label(prefix, symbols)


def _thin_chart_markers(
    markers: list[dict[str, Any]], *, limit: int
) -> list[dict[str, Any]]:
    return _charts._thin_chart_markers(markers, limit=limit)


def _format_money(value: float) -> str:
    return _cards._format_money(value)


def build_result_card(
    config: dict[str, Any],
    metrics: dict[str, Any],
    language: str = "en",
    chart: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _cards.build_result_card(config, metrics, language=language, chart=chart)


def _should_show_win_rate(config: dict[str, Any], efficiency: dict[str, Any]) -> bool:
    return _cards._should_show_win_rate(config, efficiency)
