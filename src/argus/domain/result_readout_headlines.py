"""Small reader-facing projection of the canonical run fact sheet."""

from __future__ import annotations

from typing import Any

from argus.domain.result_readout_display_values import readout_display_value

_HEADLINES = {
    "configuration.start_date": "Start date",
    "configuration.end_date": "End date",
    "window.start": "Start date",
    "window.end": "End date",
    "portfolio.total_return": "Total return",
    "portfolio.benchmark_return": "Benchmark return",
    "portfolio.benchmark_gap": "Return difference versus benchmark",
    "portfolio.annualized_return": "Annualized return",
    "portfolio.annualized_volatility": "Annualized volatility",
    "portfolio.sharpe_ratio": "Sharpe ratio",
    "portfolio.max_drawdown": "Worst drop from a prior high",
    "configuration.starting_capital": "Starting capital",
    "configuration.recurring_contribution": "Each recurring contribution",
    "configuration.contribution_period": "Contribution schedule",
    "portfolio.invested_capital": "Total money contributed",
    "portfolio.ending_equity": "Ending portfolio value",
    "portfolio.peak_equity": "Highest portfolio value",
    "portfolio.executed_fills": "Purchases and sales",
    "portfolio.completed_trades": "Completed buy-and-sell pairs",
    "configuration.fee_bps": "Fee per trade",
    "configuration.slippage_bps": "Slippage per trade",
    "portfolio.drawdown.peak_date": "Worst drop began",
    "portfolio.drawdown.trough_date": "Worst drop ended",
    "portfolio.drawdown.peak_equity": "Portfolio value before the worst drop",
    "portfolio.drawdown.trough_equity": "Portfolio value at the bottom of the worst drop",
}


def headline_readout_facts(sheet: dict[str, Any]) -> dict[str, Any]:
    """Keep scalar ownership for validation without transporting internal paths."""
    rows = sheet.get("facts") or {}
    selected = {}
    for key, label in _HEADLINES.items():
        row = rows.get(key)
        if not isinstance(row, dict):
            continue
        if key == "portfolio.total_return":
            label += (
                " on contributions"
                if row.get("basis") == "return_on_contributed_money"
                else " on starting capital"
            )
        if (
            key == "portfolio.max_drawdown"
            and rows.get("portfolio.total_return", {}).get("basis")
            == "return_on_contributed_money"
        ):
            label = "Largest investment decline excluding new deposits"
        if (
            key == "portfolio.annualized_return"
            and row.get("basis") == "money_weighted_annual_return"
        ):
            label = "Money-weighted annual return"
        selected[label] = row
    return {
        "symbols": sheet.get("symbols"),
        "benchmark_symbol": sheet.get("benchmark_symbol"),
        "facts": selected,
    }


def headline_request_lines(sheet: dict[str, Any], *, language: str = "en") -> list[str]:
    """Only these lines enter the provider request; full row metadata stays local."""
    lines = [
        f"Assets: {', '.join(sheet.get('symbols') or [])}",
        f"Benchmark: {sheet.get('benchmark_symbol') or 'not available'}",
    ]
    for label, row in sheet["facts"].items():
        value = row.get("value")
        if value is None:
            continue
        display = readout_display_value(row, language=language)
        lines.append(f"{label}: {display['text'] if display else value}")
    return lines
