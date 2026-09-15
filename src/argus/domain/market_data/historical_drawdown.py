"""A dated drawdown observation from Argus's market-data provider.

Only this adapter supplies the close series; a calculation request never carries
prices. Provider limitations remain unavailable outcomes, not synthetic risk.
"""

from __future__ import annotations

import os
from calendar import monthrange
from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict

from argus.domain.market_data.assets import resolve_asset
from argus.domain.market_data.capabilities import market_data_window_violation
from argus.domain.market_data.new_york_clock import new_york_today
from argus.domain.tool_declaration import ToolInvocationError

DEFAULT_HISTORY_YEARS = 5
DAILY_TIMEFRAME = "1D"


class HistoricalDrawdownObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, frozen=True)

    symbol: str
    asset_class: Literal["equity", "crypto", "currency_pair"]
    max_drawdown_pct: float
    requested_start_date: date
    requested_end_date: date
    observed_start_date: date
    observed_end_date: date
    peak_date: str | None
    trough_date: str | None
    observations: int
    source: Literal["argus_market_data"] = "argus_market_data"
    timeframe: Literal["1D"] = "1D"
    price_basis: Literal["split_adjusted_close", "close"]
    default_window: bool


def observe_historical_drawdown(
    symbol: str, *, start_date: date | None, end_date: date | None
) -> HistoricalDrawdownObservation:
    """Fetch daily closes and use the engine's own drawdown math on that window."""
    import numpy as np
    import pandas as pd

    from argus.domain.backtesting.metrics import (
        BaselineAnchoredSeries,
        _max_drawdown_pct,
        _max_drawdown_window,
    )
    from argus.domain.market_data.provider import fetch_price_series

    if (
        os.getenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "").strip().lower()
        == "synthetic_unit_fixture"
    ):
        raise ToolInvocationError("unavailable", code="market_data_unavailable")
    today = new_york_today()
    end = end_date if end_date is not None else today - timedelta(days=1)
    year = end.year - DEFAULT_HISTORY_YEARS
    start = (
        start_date
        if start_date is not None
        else end.replace(year=year, day=min(end.day, monthrange(year, end.month)[1]))
    )
    if start >= end or end >= today:
        raise ToolInvocationError(
            "invalid", code="invalid_arguments", fields=("start_date", "end_date")
        )
    try:
        asset = resolve_asset(symbol)
    except ValueError as exc:
        raise ToolInvocationError(
            "unavailable", code="market_data_unavailable", fields=("symbol",)
        ) from exc
    violation = market_data_window_violation(
        asset_class=asset.asset_class,
        timeframe=DAILY_TIMEFRAME,
        start_date=start,
        end_date=end,
    )
    if violation is not None:
        raise ToolInvocationError(
            "unavailable", code=violation.code, fields=("start_date", "end_date")
        )
    try:
        closes = fetch_price_series(
            symbol=asset.canonical_symbol,
            asset_class=asset.asset_class,
            start_date=start,
            end_date=end,
            timeframe=DAILY_TIMEFRAME,
        )
        if (
            not isinstance(closes.index, pd.DatetimeIndex)
            or closes.index.has_duplicates
            or closes.index.hasnans
        ):
            raise ValueError("market_data_unavailable")
        closes = closes.sort_index()
        closes = closes[(closes.index.date >= start) & (closes.index.date <= end)]
        values = closes.to_numpy(dtype=float)
        if len(values) < 2 or not np.isfinite(values).all() or (values <= 0).any():
            raise ValueError("market_data_unavailable")
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise ToolInvocationError("unavailable", code="market_data_unavailable") from exc
    dates = tuple(stamp.date().isoformat() for stamp in closes.index)
    peak_date, trough_date = _max_drawdown_window(
        BaselineAnchoredSeries(
            period_returns=pd.Series(dtype=float),
            drawdown_path=closes,
            drawdown_dates=dates,
        )
    )
    return HistoricalDrawdownObservation(
        symbol=asset.canonical_symbol,
        asset_class=asset.asset_class,
        max_drawdown_pct=_max_drawdown_pct(closes),
        requested_start_date=start,
        requested_end_date=end,
        observed_start_date=closes.index[0].date(),
        observed_end_date=closes.index[-1].date(),
        peak_date=peak_date,
        trough_date=trough_date,
        observations=len(closes),
        price_basis="split_adjusted_close" if asset.asset_class == "equity" else "close",
        default_window=start_date is None or end_date is None,
    )
