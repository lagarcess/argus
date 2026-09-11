"""Display-ready figures for composers; the supplied fact row stays untouched."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any, TypedDict

from babel.dates import format_date
from babel.numbers import format_decimal

from argus.domain.display_figure import DISPLAY_DECIMALS, display_figure
from argus.domain.result_readout_content import normalize_readout_language

_CURRENCY_POLICY = json.loads(
    Path(__file__).with_name("result_display_policy.json").read_text()
)
_CURRENCY_DIGITS = _CURRENCY_POLICY["currency_fraction_digits"]
_CURRENCY_ROUNDING = {"halfExpand": ROUND_HALF_UP}[
    _CURRENCY_POLICY["currency_rounding_mode"]
]


class ReadoutDisplayValue(TypedDict):
    value: float | str
    text: str
    unit: str


def readout_display_value(
    row: Mapping[str, Any], *, language: str
) -> ReadoutDisplayValue | None:
    """Match card precision, with unsigned drawdowns and the run's USD currency.

    ``value`` is the display-ready reference, not a replacement for the stored
    row's value. Date references keep ISO form while ``text`` is localized.
    """
    normalized = normalize_readout_language(language)
    if normalized is None:
        return None
    locale = normalized.replace("-", "_")
    value, unit = row.get("value"), row.get("unit")
    if unit in {"date", "timestamp"}:
        if not isinstance(value, str):
            return None
        try:
            date = datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError:
            return None
        return {
            "value": value,
            "text": format_date(date, format="long", locale=locale),
            "unit": unit,
        }
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        return None
    presentation = row.get("presentation") or []
    if "absolute_magnitude" in presentation:
        value = abs(value)
    if unit == "ratio" and "fraction_as_percent" in presentation:
        value, unit = value * 100, "percent"
    if unit == "currency":
        # Current engine charts and card money are USD. Do not silently relabel
        # a future account currency as dollars.
        if row.get("currency", "USD") != "USD":
            return None
        try:
            amount = Decimal(str(value)).quantize(
                Decimal(1).scaleb(-_CURRENCY_DIGITS), rounding=_CURRENCY_ROUNDING
            )
        except InvalidOperation:
            return None
        pattern = "#,##0" + ("." + "0" * _CURRENCY_DIGITS if _CURRENCY_DIGITS else "")
        number = format_decimal(abs(amount), format=pattern, locale=locale)
        return {
            "value": float(amount),
            "unit": unit,
            "text": f"{'-' if amount.is_signed() else ''}${number}",
        }
    if unit in {"percent", "percentage_points"}:
        rounded = display_figure(value)
        assert rounded is not None
        number = format_decimal(
            rounded, format="#,##0." + "0" * DISPLAY_DECIMALS, locale=locale
        )
        return {
            "value": rounded,
            "text": number + ("%" if unit == "percent" else " pp"),
            "unit": unit,
        }
    if unit in {"count", "ratio", "basis_points", "indicator_points"}:
        rounded = value if unit == "count" else round(value, 2)
        number = format_decimal(rounded, format="#,##0.##", locale=locale)
        return {
            "value": rounded,
            "unit": unit,
            "text": number + (" bps" if unit == "basis_points" else ""),
        }
    return None
