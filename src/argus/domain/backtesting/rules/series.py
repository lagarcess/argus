from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from argus.domain.indicator_execution import compute_indicator_output
from argus.domain.indicators import executable_indicator_spec

IndicatorResolver = Callable[..., pd.Series]


def resolve_series(
    data: pd.DataFrame,
    ref: dict[str, Any],
    *,
    indicator_resolver: IndicatorResolver | None = None,
) -> pd.Series:
    kind = str(ref.get("kind") or "price").lower()
    if kind == "price":
        return _column_series(data, str(ref.get("field") or "close"))
    if kind == "volume":
        return _column_series(data, str(ref.get("field") or "volume"))
    if kind == "indicator":
        return _indicator_series(
            data,
            ref,
            indicator_resolver=indicator_resolver,
        )
    raise ValueError("unsupported_indicator")


def _column_series(data: pd.DataFrame, field: str) -> pd.Series:
    if field not in data.columns:
        raise ValueError("market_data_unavailable")
    return data[field].astype(float)


def _indicator_series(
    data: pd.DataFrame,
    ref: dict[str, Any],
    *,
    indicator_resolver: IndicatorResolver | None,
) -> pd.Series:
    key = str(ref.get("key") or "").strip().lower()
    spec = executable_indicator_spec(key)
    if spec is None:
        raise ValueError("unsupported_indicator")
    period = int(float(ref.get("period", spec.default_period)))
    source_column = str(ref.get("field") or spec.required_columns[0])

    if (
        indicator_resolver is not None
        and spec.key in {"rsi", "sma", "ema"}
        and "output" not in ref
        and "parameters" not in ref
    ):
        return indicator_resolver(
            data,
            indicator=spec.key,
            period=period,
            fallback_col=source_column,
        ).astype(float)

    return compute_indicator_output(data, spec, ref)
