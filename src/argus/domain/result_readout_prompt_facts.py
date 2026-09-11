"""Reader-ready values for composition; the original sheet still validates facts."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from argus.domain.result_readout_display_values import readout_display_value


def _prompt_row(row: dict[str, Any], language: str) -> dict[str, Any]:
    result = {
        key: deepcopy(row[key])
        for key in ("value", "unit", "currency", "meaning")
        if key in row
    }
    display = readout_display_value(row, language=language)
    if display is not None:
        result.update(value=display["value"], display=display["text"])
    return result


def readout_prompt_facts(sheet: dict[str, Any], *, language: str) -> dict[str, Any]:
    """Keep the run's evidence, without storage details or hypothetical losses."""
    result = {
        key: deepcopy(sheet.get(key))
        for key in ("symbols", "benchmark_symbol", "benchmark_comparison_claim")
    }
    result["facts"] = {
        key: _prompt_row(row, language)
        for key, row in (sheet.get("facts") or {}).items()
        if row.get("basis") != "starting_capital_illustration"
    }
    result["series"] = {}
    for key, series in (sheet.get("series") or {}).items():
        points = deepcopy(series.get("points") or [])
        if key == "portfolio_equity":
            for point in points:
                display = readout_display_value(
                    {
                        "value": point.get("value"),
                        "unit": series.get("unit"),
                        "currency": series.get("currency"),
                    },
                    language=language,
                )
                if display is not None:
                    point["value"] = display["value"]
            meaning = "Account balances at recorded closes, including deposits."
        else:
            meaning = "Recorded purchases and sales; the list can be a sample."
        result["series"][key] = {"meaning": meaning, "points": points}
    return result
