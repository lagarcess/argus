from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Literal

import pandas as pd

from argus.domain.backtesting.config import (
    _execution_realism_feature_enabled,
    _normalize_execution_realism,
)


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


@dataclass(frozen=True)
class ClosedTrade:
    symbol: str
    opened_at: pd.Timestamp
    closed_at: pd.Timestamp
    net_pnl: float


@dataclass(frozen=True)
class LongOnlyExecutionResult:
    equity_curve: pd.Series
    closed_trades: tuple[ClosedTrade, ...]


def _execution_realism_settings(config: dict[str, Any]) -> dict[str, float | bool]:
    if not _execution_realism_feature_enabled():
        return {"enabled": False, "fees": 0.0, "slippage": 0.0}
    realism = _normalize_execution_realism(config.get("_execution_realism"))
    return {
        "enabled": bool(realism["enabled"]),
        "fees": float(realism["fee_bps"]) / 10000.0,
        "slippage": float(realism["slippage_bps"]) / 10000.0,
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


def _execute_long_only_ledger(
    *,
    execution_events: list[ExecutionEvent],
    close: pd.Series,
    initial_capital: float,
    fees: float,
    slippage: float,
) -> LongOnlyExecutionResult:
    """Value portfolio equity and completed positions from one fill ledger."""

    normalized_close = close.astype(float)
    if normalized_close.empty or not normalized_close.index.is_unique:
        raise ValueError("execution_price_unavailable")
    cash = float(initial_capital)
    if not isfinite(cash) or cash <= 0.0:
        raise ValueError("execution_capital_invalid")

    fills_by_timestamp: dict[pd.Timestamp, list[ExecutionEvent]] = {}
    fill_count = 0
    for event in execution_events:
        if event.event_type != "fill":
            continue
        fills_by_timestamp.setdefault(pd.Timestamp(event.timestamp), []).append(event)
        fill_count += 1

    open_symbol: str | None = None
    opened_at: pd.Timestamp | None = None
    opening_capital = 0.0
    shares = 0.0
    closed: list[ClosedTrade] = []
    equity_values: list[float] = []
    processed_fills = 0

    for timestamp, raw_price in normalized_close.items():
        market_price = float(raw_price)
        if not isfinite(market_price) or market_price <= 0.0:
            raise ValueError("execution_price_unavailable")
        for event in fills_by_timestamp.get(pd.Timestamp(timestamp), []):
            processed_fills += 1
            if event.action == "add":
                raise ValueError("execution_does_not_support_accumulation")

            if event.side == "buy" and event.action == "open":
                if opened_at is not None:
                    raise ValueError("execution_position_already_open")
                cash_per_share = market_price * (1.0 + slippage) * (1.0 + fees)
                if not isfinite(cash_per_share) or cash_per_share <= 0.0:
                    raise ValueError("execution_price_unavailable")
                open_symbol = event.symbol
                opened_at = event.timestamp
                opening_capital = cash
                shares = opening_capital / cash_per_share
                cash = 0.0
                continue

            if event.side == "sell" and event.action == "close":
                if opened_at is None or open_symbol is None:
                    raise ValueError("execution_position_not_open")
                gross_proceeds = shares * market_price * (1.0 - slippage)
                net_proceeds = gross_proceeds * (1.0 - fees)
                closed.append(
                    ClosedTrade(
                        symbol=open_symbol,
                        opened_at=opened_at,
                        closed_at=event.timestamp,
                        net_pnl=float(net_proceeds - opening_capital),
                    )
                )
                cash = net_proceeds
                open_symbol = None
                opened_at = None
                opening_capital = 0.0
                shares = 0.0
                continue

            raise ValueError("execution_fill_invalid")

        marked_value = shares * market_price if opened_at is not None else cash
        equity_values.append(float(marked_value))

    if processed_fills != fill_count:
        raise ValueError("execution_price_unavailable")

    return LongOnlyExecutionResult(
        equity_curve=pd.Series(
            equity_values,
            index=normalized_close.index,
            dtype=float,
        ),
        closed_trades=tuple(closed),
    )


def _dca_equity_curve(
    *,
    close: pd.Series,
    entries: pd.Series,
    contribution: float,
    starting_capital: float = 0.0,
    fees: float = 0.0,
    slippage: float = 0.0,
) -> tuple[pd.Series, float]:
    """Value a recurring plan. The seed buys once on the first bar.

    Every dollar is invested on its own date at the fill price after modeled
    costs, in fractional shares, so no cash waits for a whole share and the
    invested total is the seed plus one contribution per entry.
    """
    entry_mask = entries.reindex(close.index).fillna(False).astype(bool)
    fill_price = close * (1.0 + slippage)
    cash_per_share = fill_price * (1.0 + fees)
    shares_bought = (contribution / cash_per_share).where(entry_mask, 0.0)
    if starting_capital > 0.0 and not close.empty:
        seed_shares = starting_capital / float(cash_per_share.iloc[0])
        shares_bought = shares_bought.copy()
        shares_bought.iloc[0] = float(shares_bought.iloc[0]) + seed_shares
    cumulative_shares = shares_bought.cumsum()
    equity = cumulative_shares * close
    invested_capital = starting_capital + float(entry_mask.sum()) * contribution
    if invested_capital <= 0:
        invested_capital = contribution
    return equity.astype(float), invested_capital
