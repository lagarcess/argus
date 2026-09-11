"""Small reader-facing projection of the canonical run fact sheet."""

from __future__ import annotations

from typing import Any

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
    "portfolio.executed_fills": "Executed fills",
    "portfolio.completed_trades": "Completed round trips",
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


def headline_request_lines(sheet: dict[str, Any]) -> list[str]:
    """Only these lines enter the provider request; full row metadata stays local."""
    lines = [
        f"Assets: {', '.join(sheet.get('symbols') or [])}",
        f"Benchmark: {sheet.get('benchmark_symbol') or 'not available'}",
    ]
    for label, row in sheet["facts"].items():
        value = row.get("value")
        unit = str(row.get("unit") or "").replace("_", " ")
        if value is None:
            if label == "Completed round trips":
                lines.append(
                    f"{label}: not available; fills do not establish completed trades"
                )
            continue
        if row.get("unit") == "currency":
            unit = row.get("currency") or unit
        elif row.get("unit") in {"date", "timestamp", "text", "count", "ratio"}:
            unit = ""
        lines.append(f"{label}: {value} {unit}".strip())
    return lines
