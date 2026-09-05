"""The client prints shared result figures with the backend's own rounding (#533).

`web/test-fixtures/tenth-figure-parity.json` is one table read by this test and
by `web/__tests__/result-figures.test.ts`; a drift on either side fails here or
there, never silently on a screen.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_FIXTURE = Path(__file__).resolve().parents[1] / (
    "web/test-fixtures/tenth-figure-parity.json"
)
_ROWS = json.loads(_FIXTURE.read_text())["rows"]


@pytest.mark.parametrize("row", _ROWS, ids=[str(row["value"]) for row in _ROWS])
def test_backend_fixed_point_formatting_matches_the_shared_table(
    row: dict[str, object],
) -> None:
    assert f"{float(row['value']):.1f}" == row["text"]


def test_the_table_covers_the_ties_the_two_runtimes_break_differently() -> None:
    values = {float(row["value"]) for row in _ROWS}
    assert {46.25, -46.25, 46.15, 0.15, 46.35, 0.05, 0.04} <= values
