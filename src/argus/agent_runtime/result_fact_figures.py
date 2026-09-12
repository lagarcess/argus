"""The rows of a run's typed fact sheet that state each stored fact a reader asks about.

A reply to a resolved fact question is accepted only when it declares these rows,
so a fact counts as stored for a run only when the sheet states every one of them.
Asset and benchmark facts are tickers: a reply must name each one as the answer's
facts give it.
"""

from __future__ import annotations

import math
from typing import Any

from argus.domain.result_readout_fact_sheet import resolve_readout_fact
from argus.domain.result_readout_quotes import readout_figure_keys

# Stated to the model as tickers in text; a reply names each one as a whole word.
TICKER_FACT_IDS: frozenset[str] = frozenset({"symbols", "benchmark_symbol"})
# Text from the run record that the card shows; no reply check applies to it.
UNCHECKED_TEXT_FACT_IDS: frozenset[str] = frozenset({"strategy"})

# Companion facts offered beside the asked fact so date and value pairs stay
# grounded on the same curve point.
PAIRED_FACT_IDS: dict[str, tuple[str, ...]] = {
    "peak_date": ("peak_date", "peak_value"),
    "peak_value": ("peak_value", "peak_date"),
    "drawdown_date": ("drawdown_date", "drawdown_depth", "max_drawdown"),
    "max_drawdown": ("max_drawdown", "drawdown_date"),
    "lowest_date": ("lowest_date", "lowest_value"),
    "lowest_value": ("lowest_value", "lowest_date"),
    "final_value": ("final_value", "final_date"),
    "fee_bps": ("fee_bps", "slippage_bps"),
    "slippage_bps": ("slippage_bps", "fee_bps"),
    "gross_total_return": (
        "gross_total_return",
        "net_total_return",
        "return_drag",
    ),
    "net_total_return": (
        "net_total_return",
        "gross_total_return",
        "return_drag",
    ),
    "return_drag": (
        "return_drag",
        "gross_total_return",
        "net_total_return",
    ),
}

_SHEET_ROWS: dict[str, tuple[str, ...]] = {
    "total_return": ("portfolio.total_return",),
    "benchmark_return": ("portfolio.benchmark_return",),
    "benchmark_delta": ("portfolio.benchmark_gap",),
    "max_drawdown": ("portfolio.max_drawdown",),
    "drawdown_depth": ("portfolio.max_drawdown",),
    "drawdown_date": ("portfolio.drawdown.trough_date",),
    "peak_date": ("portfolio.peak_date",),
    "peak_value": ("portfolio.peak_equity",),
    "lowest_value": ("portfolio.lowest_equity",),
    "final_value": ("portfolio.ending_equity",),
    "annualized_return": ("portfolio.annualized_return",),
    "profit": ("portfolio.profit",),
    "volatility": ("portfolio.annualized_volatility",),
    "win_rate": ("portfolio.win_rate",),
    "profit_factor": ("portfolio.profit_factor",),
    "sharpe_ratio": ("portfolio.sharpe_ratio",),
    "trade_count": ("portfolio.executed_fills",),
    "starting_capital": ("configuration.starting_capital",),
    "date_range": ("window.start", "window.end"),
    "fee_bps": ("configuration.fee_bps",),
    "slippage_bps": ("configuration.slippage_bps",),
    "gross_total_return": ("portfolio.gross_return",),
    "net_total_return": ("portfolio.net_return",),
    "return_drag": ("portfolio.cost_drag",),
}


def stated_fact_rows(sheet: dict[str, Any], fact_key: str) -> dict[str, dict[str, Any]]:
    """Each sheet row stating ``fact_key``, by sheet key; empty when any is missing."""
    keys = _SHEET_ROWS.get(fact_key) or _close_time_keys(sheet, fact_key)
    rows = {key: resolve_readout_fact(sheet, key) for key in keys}
    stated = {key: row for key, row in rows.items() if isinstance(row, dict)}
    if not keys or len(readout_figure_keys({"facts": stated})) != len(keys):
        return {}
    return stated


def stated_tickers(facts: dict[str, Any], fact_key: str) -> tuple[str, ...]:
    """The tickers the answer's facts give the model for an asset or benchmark fact."""
    if fact_key not in TICKER_FACT_IDS:
        return ()
    values = (
        facts.get("symbols") if fact_key == "symbols" else [facts.get("benchmark_symbol")]
    )
    if not isinstance(values, list):
        return ()
    return tuple(
        value.strip() for value in values if isinstance(value, str) and value.strip()
    )


def reply_names_ticker(text: str, ticker: str) -> bool:
    """Whether ``ticker`` appears in ``text`` with no letter or digit touching it."""
    start = text.find(ticker)
    while start != -1:
        end = start + len(ticker)
        before = text[start - 1] if start > 0 else ""
        after = text[end] if end < len(text) else ""
        if not before.isalnum() and not after.isalnum():
            return True
        start = text.find(ticker, start + 1)
    return False


def _close_time_keys(sheet: dict[str, Any], fact_key: str) -> tuple[str, ...]:
    series = _mapping(_mapping(sheet.get("series")).get("portfolio_equity"))
    points = series.get("points")
    if not isinstance(points, list) or not points:
        return ()
    if fact_key == "final_date":
        return (f"chart.portfolio_equity.{len(points) - 1}.time",)
    if fact_key != "lowest_date":
        return ()
    closes = [
        (index, point["value"])
        for index, point in enumerate(points)
        if isinstance(point, dict) and _finite(point.get("value"))
    ]
    stored = _mapping(_mapping(sheet.get("facts")).get("portfolio.lowest_equity"))
    if not closes or not _finite(stored.get("value")):
        return ()
    # As for the peak date: the first lowest close, only when it is the stored lowest.
    index, value = min(closes, key=lambda close: close[1])
    if abs(value - stored["value"]) > 0.005:
        return ()
    return (f"chart.portfolio_equity.{index}.time",)


def _finite(value: object) -> bool:
    return (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
