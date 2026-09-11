"""Explicit model drafts for result-composer tests, independent of validation."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

FigureFixture = tuple[str, float | str]


def readout_draft(
    text: str,
    figures: Sequence[FigureFixture] = (),
    *,
    language: str = "en",
) -> dict[str, Any]:
    """Keep only the fact key and the value declared by the draft."""
    return {
        "language": language,
        "text": text,
        "figures": [
            {
                "fact_key": row[0],
                "value": row[1],
            }
            for row in figures
        ],
    }


def scalar_leaves(value: object, prefix: str = "") -> dict[str, object]:
    """Expected stored scalars, independent of the composer projection."""
    if isinstance(value, dict):
        return {
            path: leaf
            for key, child in value.items()
            for path, leaf in scalar_leaves(
                child, f"{prefix}.{key}" if prefix else key
            ).items()
        }
    return {prefix: value}


def stored_scalar_values(sheet: dict[str, Any]) -> dict[str, object]:
    """Inspect the labeled transport through its declared storage provenance."""
    values = {}
    for row in sheet["facts"].values():
        provenance = row["provenance"]
        if provenance["kind"] != "stored":
            continue
        for path in [provenance["path"], *provenance.get("also_stored_at", [])]:
            values[path] = row["value"]
    for group in sheet["context"].values():
        values.update(group["values"])
    return values
