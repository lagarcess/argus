"""Display-ready figures for composers; the supplied fact row stays untouched."""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, TypedDict

from babel.dates import format_date
from babel.numbers import format_decimal

from argus.domain.display_figure import DISPLAY_DECIMALS, display_figure
from argus.domain.result_money import CURRENCY_FRACTION_DIGITS, CURRENCY_ROUNDING
from argus.domain.result_readout_content import normalize_readout_language


class ReadoutDisplayValue(TypedDict):
    value: float | str
    text: str
    unit: str


def readout_display_value(
    row: Mapping[str, Any],
    *,
    language: str,
    currency_fraction_digits: int = CURRENCY_FRACTION_DIGITS,
) -> ReadoutDisplayValue | None:
    """Match card precision, with unsigned drawdowns and the run's USD currency.

    ``value`` is the display-ready reference, not a replacement for the stored
    row's value. Date references keep ISO form while ``text`` is localized.
    ``currency_fraction_digits`` is the precision the run's result card stores.
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
        # Modeled costs are small amounts whose parts must add up, so they keep cents.
        digits = 2 if "currency_cents" in presentation else currency_fraction_digits
        try:
            amount = Decimal(str(value)).quantize(
                Decimal(1).scaleb(-digits), rounding=CURRENCY_ROUNDING
            )
        except InvalidOperation:
            return None
        pattern = "#,##0" + ("." + "0" * digits if digits else "")
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
