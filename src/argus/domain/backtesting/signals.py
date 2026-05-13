from __future__ import annotations

import inspect
from typing import Any

import pandas as pd

from argus.domain.indicators import (
    executable_indicator_spec,
    normalize_indicator_parameters,
)

try:  # noqa: SIM105
    import pandas_ta_classic  # noqa: F401
except Exception:  # pragma: no cover - accessor may already be available
    pass


def _resolve_indicator_series(
    data: pd.DataFrame,
    *,
    indicator: str,
    period: int,
    fallback_col: str = "close",
) -> pd.Series:
    if fallback_col not in data.columns:
        raise ValueError("market_data_unavailable")

    spec = executable_indicator_spec(indicator)
    name = spec.key if spec is not None else indicator.strip().lower()
    ta_accessor = getattr(data, "ta", None)
    if ta_accessor is None:
        raise ValueError("unsupported_indicator")
    accessor = getattr(ta_accessor, name, None)
    if accessor is None:
        raise ValueError("unsupported_indicator")

    kwargs: dict[str, Any] = {"append": True}
    try:
        params = inspect.signature(accessor).parameters
    except (TypeError, ValueError):
        params = {}

    if "length" in params:
        kwargs["length"] = period
    elif "window" in params:
        kwargs["window"] = period
    elif "period" in params:
        kwargs["period"] = period

    if "close" in params:
        kwargs["close"] = data[fallback_col]

    accessor(**kwargs)

    candidates: list[str] = []
    if spec is not None:
        selector = spec.output_selector.format(period=period).upper()
        candidates = [col for col in data.columns if selector == col.upper()]

    upper = name.upper()
    if not candidates:
        candidates = [
            col for col in data.columns if upper in col.upper() and str(period) in col
        ]
    if not candidates:
        candidates = [col for col in data.columns if upper in col.upper()]
    if not candidates:
        raise ValueError("unsupported_indicator")
    return data[candidates[-1]].astype(float)


def _build_signals(
    config: dict[str, Any],
    data: pd.DataFrame,
    *,
    resolve_indicator_series_func=_resolve_indicator_series,
) -> tuple[pd.Series, pd.Series]:
    close = data["close"].astype(float)
    template = config["template"]
    index = close.index

    if template == "buy_and_hold":
        entries = pd.Series(False, index=index, dtype=bool)
        entries.iloc[0] = True
        exits = pd.Series(False, index=index, dtype=bool)
        return entries.astype(bool), exits.astype(bool)

    if template == "dca_accumulation":
        cadence = config.get("parameters", {}).get("dca_cadence", "weekly").lower()
        entries = pd.Series(False, index=index, dtype=bool)

        if cadence == "daily":
            entries[:] = True
        elif cadence == "weekly":
            # Entry on the first day of each week present in data
            weeks = _index_period_series(index, freq="W")
            entries = weeks != weeks.shift(1)
        elif cadence == "monthly":
            # Entry on the first day of each month present in data
            months = _index_period_series(index, freq="M")
            entries = months != months.shift(1)
        elif cadence == "quarterly":
            entries.iloc[::3] = True
        else:
            # Fallback to single entry if unknown cadence
            entries.iloc[0] = True

        exits = pd.Series(False, index=index, dtype=bool)
        return entries.astype(bool), exits.astype(bool)

    if template == "rsi_mean_reversion":
        indicator_params = normalize_indicator_parameters(
            "rsi",
            config.get("parameters"),
        )
        rsi = resolve_indicator_series_func(
            data,
            indicator=str(indicator_params["indicator"]),
            period=int(indicator_params["indicator_period"]),
        )
        entries = (rsi <= float(indicator_params["entry_threshold"])).fillna(False)
        exits = (rsi >= float(indicator_params["exit_threshold"])).fillna(False)
        return entries.astype(bool), exits.astype(bool)

    if template == "moving_average_crossover":
        fast = resolve_indicator_series_func(data, indicator="sma", period=20)
        slow = resolve_indicator_series_func(data, indicator="sma", period=50)
        entries = (fast > slow) & (fast.shift(1) <= slow.shift(1))
        exits = (fast < slow) & (fast.shift(1) >= slow.shift(1))
        return entries.fillna(False).astype(bool), exits.fillna(False).astype(bool)

    if template == "momentum_breakout":
        rolling_high = close.rolling(20).max().shift(1)
        rolling_mid = close.rolling(20).mean()
        entries = close >= rolling_high
        exits = close < rolling_mid
        return entries.fillna(False).astype(bool), exits.fillna(False).astype(bool)

    if template == "trend_follow":
        trend = close > close.rolling(50).mean()
        entries = trend & ~trend.shift(1).fillna(False)
        exits = (~trend) & trend.shift(1).fillna(False)
        return entries.fillna(False).astype(bool), exits.fillna(False).astype(bool)

    if template == "buy_the_dip":
        dip = close.pct_change().fillna(0.0) <= -0.03
        entries = dip.fillna(False)
        exits = entries.shift(5).fillna(False)
        return entries.astype(bool), exits.astype(bool)

    raise ValueError("unsupported_template")


def _index_period_series(index: pd.Index, *, freq: str) -> pd.Series:
    datetime_index = pd.DatetimeIndex(index)
    if datetime_index.tz is not None:
        datetime_index = datetime_index.tz_convert(None)
    return pd.Series(datetime_index.to_period(freq), index=index)
