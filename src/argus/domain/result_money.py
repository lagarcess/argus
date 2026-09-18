"""The precision a result's money is shown with, decided once per run.

The result card decides from the run's own portfolio peak and stores the
digits as ``currency_fraction_digits``; the card rows, the web and the readout
read that stored value and round half up, per the policy the web reads too
(``web/lib/result-money.ts``).
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal
from importlib.resources import files
from typing import Any

RESULT_DISPLAY_POLICY: dict[str, Any] = json.loads(
    files("argus_display_contract").joinpath("result_display_policy.json").read_text()
)
CURRENCY_FRACTION_DIGITS: int = RESULT_DISPLAY_POLICY["currency_fraction_digits"]
CURRENCY_ROUNDING = {"halfExpand": ROUND_HALF_UP}[
    RESULT_DISPLAY_POLICY["currency_rounding_mode"]
]
_CENTS_BELOW = float(RESULT_DISPLAY_POLICY["currency_cents_below"])
_CENTS_DIGITS = 2
_STORED_KEY = "currency_fraction_digits"


def run_currency_fraction_digits(peak_value: object) -> int:
    """Cents for a run whose portfolio never reached the policy threshold."""
    if (
        isinstance(peak_value, int | float)
        and not isinstance(peak_value, bool)
        and math.isfinite(peak_value)
        and abs(peak_value) < _CENTS_BELOW
    ):
        return _CENTS_DIGITS
    return CURRENCY_FRACTION_DIGITS


def stored_currency_fraction_digits(record: object) -> int:
    """The digits a result card or readout sheet carries; the policy default
    for anything stored before the decision existed."""
    digits = record.get(_STORED_KEY) if isinstance(record, Mapping) else None
    if (
        isinstance(digits, int)
        and not isinstance(digits, bool)
        and 0 <= digits <= _CENTS_DIGITS
    ):
        return digits
    return CURRENCY_FRACTION_DIGITS


def with_currency_fraction_digits(record: dict[str, Any], digits: int) -> dict[str, Any]:
    record[_STORED_KEY] = digits
    return record


def rounded_result_money(value: float, *, fraction_digits: int) -> Decimal:
    return Decimal(str(value)).quantize(
        Decimal(1).scaleb(-fraction_digits), rounding=CURRENCY_ROUNDING
    )


def format_result_money(value: float, *, fraction_digits: int) -> str:
    amount = rounded_result_money(value, fraction_digits=fraction_digits)
    sign = "-" if amount < 0 else ""
    return f"{sign}${abs(amount):,.{fraction_digits}f}"
