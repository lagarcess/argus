"""The one rounding a shared result figure receives before a reader prints it.

The engine persists returns and the benchmark gap to two decimals; readers show
one. Python's float rounding is that single implementation: ``round`` and
``format(..., ".1f")`` produce the same correctly rounded digits, ties to even,
so the figures shipped to clients and every backend-voiced copy of the same
fact carry identical digits. Clients print what they receive and add locale
separators only (#533).
"""

from __future__ import annotations

DISPLAY_DECIMALS = 1


def display_figure(value: object) -> float | None:
    try:
        if value is None or value == "":
            return None
        return round(float(value), DISPLAY_DECIMALS)
    except (TypeError, ValueError):
        return None
