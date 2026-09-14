"""The precision a result's money is shown with, read from the shared policy.

Whole dollars read correctly once a portfolio has reached the policy's
``currency_cents_below``; under it one rounded dollar is a large share of every
figure, so an amount that is not whole shows its cents. The web applies the
same JSON through ``web/lib/result-money.ts``.
"""

from __future__ import annotations

import json
import math
from importlib.resources import files
from typing import Any

RESULT_DISPLAY_POLICY: dict[str, Any] = json.loads(
    files("argus_display_contract").joinpath("result_display_policy.json").read_text()
)
CURRENCY_FRACTION_DIGITS: int = RESULT_DISPLAY_POLICY["currency_fraction_digits"]
_CENTS_BELOW = float(RESULT_DISPLAY_POLICY["currency_cents_below"])


def result_money_fraction_digits(value: float, *, peak_value: float | None) -> int:
    """Digits for one amount of a result whose portfolio peaked at ``peak_value``."""
    if peak_value is None or abs(peak_value) >= _CENTS_BELOW:
        return CURRENCY_FRACTION_DIGITS
    if round(abs(value) * 100) % 100 == 0:
        return CURRENCY_FRACTION_DIGITS
    return 2


def series_peak_value(points: Any) -> float | None:
    """The highest value in a stored portfolio series of ``{time, value}`` points."""
    if not isinstance(points, list):
        return None
    values = [
        float(point["value"])
        for point in points
        if isinstance(point, dict)
        and isinstance(point.get("value"), int | float)
        and not isinstance(point.get("value"), bool)
        and math.isfinite(point["value"])
    ]
    return max(values) if values else None
