from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import pandas as pd

from argus.domain.backtesting.config import _execution_realism_feature_enabled


@dataclass(frozen=True)
class ExecutionEvent:
    timestamp: pd.Timestamp
    symbol: str
    event_type: Literal[
        "signal", "order_intent", "fill", "ignored_signal", "position_snapshot"
    ]
    side: Literal["buy", "sell"] | None = None
    action: Literal["open", "add", "close", "hold", "ignore"] | None = None
    reason: str | None = None


def _execution_realism_settings(config: dict[str, Any]) -> dict[str, float | bool]:
    if not _execution_realism_feature_enabled():
        return {"enabled": False, "fees": 0.0, "slippage": 0.0}
    raw = config.get("_execution_realism") or {}
    enabled = bool(raw.get("enabled", False))
    fee_bps = float(raw.get("fee_bps", 0.0))
    slippage_bps = float(raw.get("slippage_bps", 0.0))
    if not enabled:
        fee_bps = 0.0
        slippage_bps = 0.0
    return {
        "enabled": enabled,
        "fees": fee_bps / 10000.0,
        "slippage": slippage_bps / 10000.0,
    }


def _build_long_only_execution_ledger(
    *,
    symbol: str,
    entries: pd.Series,
    exits: pd.Series,
    allow_accumulation: bool,
) -> list[ExecutionEvent]:
    """Reduce raw strategy signals into executed long-only events.

    Strategy signals are intent candidates. This ledger is the canonical source
    for user-facing trade events because it applies position state and execution
    policy before a buy/sell can appear in the UI.
    """

    normalized_entries = entries.fillna(False).astype(bool)
    normalized_exits = exits.fillna(False).astype(bool)
    timestamps = normalized_entries.index.union(normalized_exits.index).sort_values()
    events: list[ExecutionEvent] = []
    holding = False

    for timestamp in timestamps:
        ts = pd.Timestamp(timestamp)
        has_entry = bool(normalized_entries.get(timestamp, False))
        has_exit = bool(normalized_exits.get(timestamp, False))
        if not has_entry and not has_exit:
            continue

        if has_exit:
            events.append(
                ExecutionEvent(
                    timestamp=ts,
                    symbol=symbol,
                    event_type="signal",
                    side="sell",
                )
            )
            if holding:
                events.append(
                    ExecutionEvent(
                        timestamp=ts,
                        symbol=symbol,
                        event_type="order_intent",
                        side="sell",
                        action="close",
                    )
                )
                events.append(
                    ExecutionEvent(
                        timestamp=ts,
                        symbol=symbol,
                        event_type="fill",
                        side="sell",
                        action="close",
                    )
                )
                holding = False
            else:
                events.append(
                    ExecutionEvent(
                        timestamp=ts,
                        symbol=symbol,
                        event_type="ignored_signal",
                        side="sell",
                        action="ignore",
                        reason="exit_signal_while_flat",
                    )
                )

        if has_entry:
            events.append(
                ExecutionEvent(
                    timestamp=ts,
                    symbol=symbol,
                    event_type="signal",
                    side="buy",
                )
            )
            if not holding:
                events.append(
                    ExecutionEvent(
                        timestamp=ts,
                        symbol=symbol,
                        event_type="order_intent",
                        side="buy",
                        action="open",
                    )
                )
                events.append(
                    ExecutionEvent(
                        timestamp=ts,
                        symbol=symbol,
                        event_type="fill",
                        side="buy",
                        action="open",
                    )
                )
                holding = True
            elif allow_accumulation:
                events.append(
                    ExecutionEvent(
                        timestamp=ts,
                        symbol=symbol,
                        event_type="order_intent",
                        side="buy",
                        action="add",
                    )
                )
                events.append(
                    ExecutionEvent(
                        timestamp=ts,
                        symbol=symbol,
                        event_type="fill",
                        side="buy",
                        action="add",
                    )
                )
            else:
                events.append(
                    ExecutionEvent(
                        timestamp=ts,
                        symbol=symbol,
                        event_type="ignored_signal",
                        side="buy",
                        action="ignore",
                        reason="entry_signal_while_already_long",
                    )
                )

        events.append(
            ExecutionEvent(
                timestamp=ts,
                symbol=symbol,
                event_type="position_snapshot",
                action="hold" if holding else "close",
            )
        )

    return events


def _execution_fill_count(
    execution_events: list[ExecutionEvent], *, side: str | None = None
) -> int:
    return sum(
        1
        for event in execution_events
        if event.event_type == "fill" and (side is None or event.side == side)
    )


def _dca_equity_curve(
    *,
    close: pd.Series,
    entries: pd.Series,
    contribution: float,
    fees: float = 0.0,
    slippage: float = 0.0,
) -> tuple[pd.Series, float]:
    entry_mask = entries.reindex(close.index).fillna(False).astype(bool)
    fill_price = close * (1.0 + slippage)
    cash_per_share = fill_price * (1.0 + fees)
    shares_bought = (contribution / cash_per_share).where(entry_mask, 0.0)
    cumulative_shares = shares_bought.cumsum()
    equity = cumulative_shares * close
    invested_capital = float(entry_mask.sum()) * contribution
    if invested_capital <= 0:
        invested_capital = contribution
    return equity.astype(float), invested_capital
