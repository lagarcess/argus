"""Small reader-facing projection of the canonical run fact sheet."""

from __future__ import annotations

from datetime import datetime, timezone
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
    "portfolio.peak_date": "Highest portfolio value reached",
    "portfolio.executed_fills": "Trades executed",
    "portfolio.purchase_fills": "Purchases",
    "portfolio.sale_fills": "Sales",
    "portfolio.completed_trades": "Completed buy-and-sell pairs",
    "configuration.fee_bps": "Fee per trade",
    "configuration.slippage_bps": "Slippage per trade",
    "portfolio.drawdown.peak_date": "Worst drop began",
    "portfolio.drawdown.trough_date": "Worst drop ended",
    "portfolio.drawdown.peak_equity": "Portfolio value before the worst drop",
    "portfolio.drawdown.trough_equity": "Portfolio value at the bottom of the worst drop",
    "portfolio.drawdown.dollar_loss": "Dollar decline during the worst drop",
}

# Event membership derives labels from the same map used by figure references.
_EVENTS = {
    "portfolio.drawdown.peak_date": ("portfolio.drawdown.peak_equity",),
    "portfolio.drawdown.trough_date": (
        "portfolio.drawdown.trough_equity",
        "portfolio.drawdown.dollar_loss",
    ),
    "portfolio.peak_date": ("portfolio.peak_equity",),
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
    facts = sheet["facts"]

    def line(label: str) -> str:
        row = facts[label]
        display = readout_display_value(row, language=language)
        return f"{label}: {display['text'] if display else row['value']}"

    events = []
    grouped = set()
    for date_key, value_keys in _EVENTS.items():
        date_label = _HEADLINES[date_key]
        value = facts.get(date_label, {}).get("value")
        if not isinstance(value, str):
            continue
        try:
            date = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            continue
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        labels = [date_label, *(_HEADLINES[key] for key in value_keys)]
        labels = [
            label for label in labels if facts.get(label, {}).get("value") is not None
        ]
        events.append((date, "; ".join(line(label) for label in labels)))
        grouped.update(labels)
    for label, row in facts.items():
        value = row.get("value")
        if value is None or label in grouped:
            continue
        lines.append(line(label))
    if events:
        lines.append("Recorded events in chronological order (earliest to latest):")
        lines.extend(text for _, text in sorted(events, key=lambda event: event[0]))
    return lines
