"""A light value check for declared run references, without prose bookkeeping."""

from __future__ import annotations

import math
from datetime import datetime
from decimal import Decimal
from typing import Any

from argus.domain.result_readout_fact_sheet import resolve_readout_fact


def _finite(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def validate_figure_references(
    text: str,
    references: list[dict[str, Any]],
    *,
    facts: dict[str, Any],
    language: str,
) -> str | None:
    """Check only declared facts; unreferenced prose never fails this check."""
    for reference in references:
        row = resolve_readout_fact(facts, reference["fact_key"])
        if not row:
            return "invalid_figure_reference"
        expected, value = row.get("value"), reference["value"]
        unit = row.get("unit")
        if unit in {"date", "timestamp"}:
            if not isinstance(expected, str) or not isinstance(value, str):
                return "invalid_figure_reference"
            try:
                if (
                    datetime.fromisoformat(expected.replace("Z", "+00:00")).date()
                    != datetime.fromisoformat(value.replace("Z", "+00:00")).date()
                ):
                    return "invalid_figure_reference"
            except ValueError:
                return "invalid_figure_reference"
            continue
        if unit in {None, "unknown", "text", "boolean"} or not (
            _finite(expected) and _finite(value)
        ):
            return "invalid_figure_reference"
        # The precision of the declared visible number owns its rounding window.
        precision = Decimal(format(value, ".15g")).as_tuple().exponent
        tolerance = 0.0 if unit == "count" else 0.5 * 10 ** min(precision, 0) + 1e-8
        candidates = [expected]
        presentation = row.get("presentation") or []
        if "fraction_as_percent" in presentation:
            candidates.append(expected * 100)
        if "basis_points_as_percentage_points" in presentation:
            candidates.append(expected / 100)
        if "absolute_magnitude" in presentation:
            candidates += [abs(candidate) for candidate in candidates]
        if not any(abs(value - candidate) <= tolerance for candidate in candidates):
            return "invalid_figure_reference"
    return None
