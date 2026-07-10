from __future__ import annotations

from typing import Any

import pandas as pd

from argus.domain.backtesting.rules import compile_rule_signals, resolve_series
from argus.domain.indicators import (
    executable_indicator_spec,
    normalize_indicator_parameters,
)


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
    if spec is None:
        raise ValueError("unsupported_indicator")
    return resolve_series(
        data,
        {
            "kind": "indicator",
            "key": spec.key,
            "period": period,
            "field": fallback_col,
        },
    )


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
        elif cadence == "biweekly":
            elapsed_days = pd.Series(
                (index - index[0]).days,
                index=index,
            )
            windows = elapsed_days // 14
            entries = windows != windows.shift(1)
        elif cadence == "monthly":
            # Entry on the first day of each month present in data
            months = _index_period_series(index, freq="M")
            entries = months != months.shift(1)
        elif cadence == "quarterly":
            quarters = _index_period_series(index, freq="Q")
            entries = quarters != quarters.shift(1)
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
        rule_spec = indicator_params.get("rule_spec") or _legacy_rsi_rule_spec(
            indicator_params
        )
        return compile_rule_signals(
            rule_spec,
            data=data,
            indicator_resolver=resolve_indicator_series_func,
        )

    if template == "signal_strategy":
        rule_spec = (config.get("parameters") or {}).get("rule_spec")
        return compile_rule_signals(
            rule_spec,
            data=data,
            indicator_resolver=resolve_indicator_series_func,
        )

    if template == "moving_average_crossover":
        fast = resolve_indicator_series_func(data, indicator="sma", period=20)
        slow = resolve_indicator_series_func(data, indicator="sma", period=50)
        entries = (fast > slow) & (fast.shift(1) <= slow.shift(1))
        exits = (fast < slow) & (fast.shift(1) >= slow.shift(1))
        return entries.fillna(False).astype(bool), exits.fillna(False).astype(bool)

    # momentum_breakout / trend_follow are draft templates (status="draft" in the
    # capability registry) with no supported path: they are excluded from
    # ALLOWED_TEMPLATES and the StrategyTemplate API enum, so they never reach here.
    # Their orphaned handlers were retired; an unknown template raises below.

    if template == "buy_the_dip":
        dip = close.pct_change().fillna(0.0) <= -0.03
        entries = dip.fillna(False)
        exits = entries.shift(5).fillna(False)
        return entries.astype(bool), exits.astype(bool)

    raise ValueError("unsupported_template")


def _legacy_rsi_rule_spec(indicator_params: dict[str, Any]) -> dict[str, Any]:
    indicator = str(indicator_params["indicator"])
    period = int(indicator_params["indicator_period"])
    return {
        "entry": {
            "conditions": [
                {
                    "left": {
                        "kind": "indicator",
                        "key": indicator,
                        "period": period,
                    },
                    "operator": "lte",
                    "right": float(indicator_params["entry_threshold"]),
                }
            ]
        },
        "exit": {
            "conditions": [
                {
                    "left": {
                        "kind": "indicator",
                        "key": indicator,
                        "period": period,
                    },
                    "operator": "gte",
                    "right": float(indicator_params["exit_threshold"]),
                }
            ]
        },
    }


def _index_period_series(index: pd.Index, *, freq: str) -> pd.Series:
    datetime_index = pd.DatetimeIndex(index)
    if datetime_index.tz is not None:
        datetime_index = datetime_index.tz_convert(None)
    return pd.Series(datetime_index.to_period(freq), index=index)
