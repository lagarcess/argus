"""Deterministic result-fact enrichment for the latest-result fact bank.

Computes exact machine facts — equity-curve extrema, supplemental aggregate
metrics, and result-card rows — that ground LLM-composed follow-up answers.

This module must stay free of user-visible prose and per-language behavior:
values are formatted machine strings (numbers, dates, symbols); the LLM owns
all natural language. It is a leaf module: it must not import from
``result_followups`` (which imports it).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any


def metric_number(
    metadata: dict[str, Any],
    *,
    paths: tuple[tuple[str, ...], ...],
) -> float | None:
    for path in paths:
        value: Any = metadata
        for key in path:
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(key)
        number = as_float(value)
        if number is not None:
            return number
    return None


def as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace("%", "").replace("+", "").replace(",", "")
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def format_percent(value: float, *, signed: bool = True) -> str:
    sign = "+" if signed and value > 0 else ""
    return f"{sign}{value:.1f}%"


def format_money(value: float, *, currency: str = "USD") -> str:
    prefix = "$" if currency.upper() == "USD" else f"{currency.upper()} "
    rounded = round(float(value), 2)
    if abs(rounded - round(rounded)) < 0.005:
        return f"{prefix}{rounded:,.0f}"
    return f"{prefix}{rounded:,.2f}"


def format_decimal(value: float) -> str:
    return f"{float(value):.2f}".rstrip("0").rstrip(".")


def normalize_fact_key(value: Any) -> str | None:
    """Mechanical fact-key canonicalization: case and separators only.

    Deliberately not a synonym table — the interpreter contract is to emit
    canonical keys, and unknown keys route to the typed limitation path.
    """

    text = str(value or "").strip().casefold()
    if not text:
        return None
    for separator in ("-", " ", ".", "/"):
        text = text.replace(separator, "_")
    return "_".join(part for part in text.split("_") if part) or None


@dataclass(frozen=True)
class _CurvePoint:
    time: str
    value: float


def enriched_result_fact_entries(metadata: dict[str, Any]) -> dict[str, str]:
    """New fact-bank entries derived from stored result metadata.

    Callers merge these without overwriting canonical bank entries.
    """

    entries: dict[str, str] = {}
    currency = _currency(metadata)
    points = _curve_points(metadata)

    peak = _peak_point(points)
    if peak is not None:
        entries["peak_value"] = format_money(peak.value, currency=currency)
        entries["peak_date"] = peak.time
    else:
        peak_value = metric_number(metadata, paths=_PEAK_VALUE_FALLBACK_PATHS)
        if peak_value is not None:
            entries["peak_value"] = format_money(peak_value, currency=currency)

    lowest = _lowest_point(points)
    if lowest is not None:
        entries["lowest_value"] = format_money(lowest.value, currency=currency)
        entries["lowest_date"] = lowest.time
    else:
        lowest_value = metric_number(metadata, paths=_LOWEST_VALUE_FALLBACK_PATHS)
        if lowest_value is not None:
            entries["lowest_value"] = format_money(lowest_value, currency=currency)

    if points:
        final = points[-1]
        entries["final_value"] = format_money(final.value, currency=currency)
        entries["final_date"] = final.time

    trough = _drawdown_trough(points)
    if trough is not None:
        # Depth is computed at the same trough as the date so the pair always
        # describes one drawdown point; the aggregate metric stays available
        # separately as max_drawdown.
        entries["drawdown_date"] = trough[0]
        entries["drawdown_depth"] = format_percent(abs(trough[1]), signed=False)

    for key, value in _supplemental_metric_entries(metadata, currency=currency):
        entries.setdefault(key, value)
    for key, value in _result_card_row_entries(metadata):
        entries.setdefault(key, value)
    return entries


_PEAK_VALUE_FALLBACK_PATHS: tuple[tuple[str, ...], ...] = (
    ("chart", "value_summary", "peak_value"),
    ("result_card", "chart", "value_summary", "peak_value"),
    ("metrics", "aggregate", "performance", "portfolio_value_range", "peak_value"),
    ("value_summary", "peak_value"),
    ("value_extrema", "peak_value"),
)

_LOWEST_VALUE_FALLBACK_PATHS: tuple[tuple[str, ...], ...] = (
    ("chart", "value_summary", "lowest_value"),
    ("result_card", "chart", "value_summary", "lowest_value"),
    ("metrics", "aggregate", "performance", "portfolio_value_range", "lowest_value"),
    ("value_summary", "lowest_value"),
    ("value_extrema", "lowest_value"),
)


def _supplemental_metric_specs(
    currency: str,
) -> tuple[tuple[str, tuple[tuple[str, ...], ...], Callable[[float], str]], ...]:
    return (
        (
            "annualized_return",
            (("metrics", "aggregate", "performance", "annualized_return_pct"),),
            format_percent,
        ),
        (
            "profit",
            (("metrics", "aggregate", "performance", "profit"),),
            lambda value: format_money(value, currency=currency),
        ),
        (
            "volatility",
            (("metrics", "aggregate", "risk", "volatility_pct"),),
            lambda value: format_percent(value, signed=False),
        ),
        (
            "win_rate",
            (("metrics", "aggregate", "efficiency", "win_rate"),),
            lambda value: format_percent(value * 100.0, signed=False),
        ),
        (
            "profit_factor",
            (("metrics", "aggregate", "efficiency", "profit_factor"),),
            format_decimal,
        ),
        (
            "sharpe_ratio",
            (("metrics", "aggregate", "efficiency", "sharpe_ratio"),),
            format_decimal,
        ),
    )


def _supplemental_metric_entries(
    metadata: dict[str, Any],
    *,
    currency: str,
) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for key, paths, formatter in _supplemental_metric_specs(currency):
        value = metric_number(metadata, paths=paths)
        if value is not None:
            entries.append((key, formatter(value)))
    return entries


def _result_card_row_entries(metadata: dict[str, Any]) -> list[tuple[str, str]]:
    result_card = _mapping(metadata.get("result_card"))
    rows = result_card.get("rows")
    if not isinstance(rows, list):
        return []
    entries: list[tuple[str, str]] = []
    for item in rows:
        row = _mapping(item)
        key = normalize_fact_key(row.get("key"))
        value = str(row.get("value") or "").strip()
        if key and value:
            entries.append((key, value))
    return entries


def _curve_points(metadata: dict[str, Any]) -> list[_CurvePoint]:
    chart = _chart(metadata)
    raw_series = chart.get("series")
    if not isinstance(raw_series, list):
        return []
    points: list[_CurvePoint] = []
    for item in raw_series:
        point = _mapping(item)
        raw_time = point.get("time") or point.get("date") or point.get("timestamp")
        value = as_float(
            point.get("value")
            if "value" in point
            else point.get("portfolio_value", point.get("equity", point.get("y")))
        )
        if raw_time is None or value is None:
            continue
        points.append(_CurvePoint(time=str(raw_time), value=value))
    return points


def _peak_point(points: list[_CurvePoint]) -> _CurvePoint | None:
    if not points:
        return None
    return max(enumerate(points), key=lambda item: (item[1].value, -item[0]))[1]


def _lowest_point(points: list[_CurvePoint]) -> _CurvePoint | None:
    if not points:
        return None
    return min(enumerate(points), key=lambda item: (item[1].value, item[0]))[1]


def _drawdown_trough(points: list[_CurvePoint]) -> tuple[str, float] | None:
    if not points:
        return None
    running_peak = points[0].value
    worst: tuple[str, float] | None = None
    for point in points:
        if point.value > running_peak:
            running_peak = point.value
        if running_peak <= 0:
            continue
        drawdown_pct = (point.value / running_peak - 1.0) * 100.0
        if worst is None or drawdown_pct < worst[1]:
            worst = (point.time, drawdown_pct)
    return worst


def _chart(metadata: dict[str, Any]) -> dict[str, Any]:
    chart = _mapping(metadata.get("chart"))
    if chart:
        return dict(chart)
    result_card = _mapping(metadata.get("result_card"))
    return dict(_mapping(result_card.get("chart")))


def _currency(metadata: dict[str, Any]) -> str:
    chart = _chart(metadata)
    summary = _mapping(chart.get("value_summary"))
    value = str(
        chart.get("currency")
        or summary.get("currency")
        or _string_at(
            metadata,
            ("metrics", "aggregate", "performance", "portfolio_value_range", "currency"),
        )
        or "USD"
    ).strip()
    return value or "USD"


def _string_at(value: Mapping[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = value
    for part in path:
        current = _mapping(current).get(part)
        if current is None:
            return None
    return current


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}
