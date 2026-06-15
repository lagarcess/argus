from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd
import vectorbt as vbt

from argus.domain.backtesting.config import _vbt_freq
from argus.domain.backtesting.execution import (
    ExecutionEvent,
    _build_long_only_execution_ledger,
    _dca_equity_curve,
    _execution_realism_settings,
)
from argus.domain.backtesting.metrics import portfolio_value_summary
from argus.domain.backtesting.signals import _build_signals
from argus.domain.market_data import fetch_ohlcv


def build_result_chart(
    config: dict[str, Any],
    *,
    fetch_ohlcv_func=fetch_ohlcv,
    build_signals_func=_build_signals,
) -> dict[str, Any]:
    """Build a compact aggregate equity curve for result-card display."""

    start = date.fromisoformat(config["start_date"])
    end = date.fromisoformat(config["end_date"])
    allocation_capital = float(config["starting_capital"]) / len(config["symbols"])
    realism = _execution_realism_settings(config)
    is_dca = config["template"] == "dca_accumulation"
    symbol_equity_curves: list[pd.Series] = []
    events: dict[str, dict[str, set[str]]] = {}

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
        if is_dca:
            symbol_equity, _ = _dca_equity_curve(
                close=close,
                entries=entries,
                contribution=allocation_capital,
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
        symbol_equity_curves.append(symbol_equity)
        _collect_execution_fill_events(
            events, symbol=symbol, execution_events=execution_events
        )

    aggregate_equity = (
        pd.concat(symbol_equity_curves, axis=1).ffill().bfill().sum(axis=1).dropna()
    )
    series = [
        {"time": _chart_time_key(ts), "value": round(float(value), 2)}
        for ts, value in aggregate_equity.items()
    ]
    markers = _thin_chart_markers(_chart_markers_from_events(events), limit=80)
    chart = {
        "kind": "portfolio_equity",
        "series": series,
        "markers": markers,
        "currency": "USD",
        "base_value": series[0]["value"] if series else None,
        "attribution": "TradingView Lightweight Charts",
    }
    value_summary = portfolio_value_summary(aggregate_equity)
    if value_summary is not None:
        chart["value_summary"] = value_summary
    return chart


def _collect_execution_fill_events(
    events: dict[str, dict[str, set[str]]],
    *,
    symbol: str,
    execution_events: list[ExecutionEvent],
) -> None:
    for event in execution_events:
        if event.event_type != "fill":
            continue
        if event.side == "buy":
            key = _chart_time_key(event.timestamp)
            events.setdefault(key, {"entry": set(), "exit": set()})["entry"].add(symbol)
        elif event.side == "sell":
            key = _chart_time_key(event.timestamp)
            events.setdefault(key, {"entry": set(), "exit": set()})["exit"].add(symbol)


def _chart_time_key(timestamp: Any) -> str:
    ts = pd.Timestamp(timestamp)
    if ts.hour == 0 and ts.minute == 0 and ts.second == 0:
        return ts.strftime("%Y-%m-%d")
    return ts.strftime("%Y-%m-%dT%H:%M:%S")


def _chart_markers_from_events(
    events: dict[str, dict[str, set[str]]],
) -> list[dict[str, Any]]:
    markers: list[dict[str, Any]] = []
    for time_key in sorted(events):
        entry_symbols = sorted(events[time_key].get("entry", set()))
        exit_symbols = sorted(events[time_key].get("exit", set()))
        if entry_symbols:
            markers.append(
                {
                    "time": time_key,
                    "type": "entry",
                    "label": _event_label("Buy", entry_symbols),
                    "symbols": entry_symbols,
                }
            )
        if exit_symbols:
            markers.append(
                {
                    "time": time_key,
                    "type": "exit",
                    "label": _event_label("Sell", exit_symbols),
                    "symbols": exit_symbols,
                }
            )
    return markers


def _event_label(prefix: str, symbols: list[str]) -> str:
    if len(symbols) <= 3:
        return f"{prefix} {', '.join(symbols)}"
    return f"{prefix} {len(symbols)} symbols"


def _thin_chart_markers(
    markers: list[dict[str, Any]], *, limit: int
) -> list[dict[str, Any]]:
    if len(markers) <= limit:
        return markers
    indexes = sorted({round(i) for i in np.linspace(0, len(markers) - 1, limit)})
    return [markers[i] for i in indexes]
