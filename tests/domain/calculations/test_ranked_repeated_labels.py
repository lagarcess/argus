"""Ranked items that share a label keep their own symbols."""

from __future__ import annotations

from tests.domain.calculations.support import run_calculation


def test_items_that_share_a_label_keep_their_own_symbols() -> None:
    card = run_calculation(
        "ranked_comparison",
        {
            "currency": "USD",
            "key_label": "Expense ratio",
            "key_kind": "percent",
            "prefer": "lower",
            "items": [
                {"label": "Fund", "symbol": "AAAA", "value": 0.2},
                {"label": "Fund", "symbol": "BBBB", "value": 0.1},
            ],
        },
    )
    rows = card.outcome.result["rows"]
    assert [(row["symbol"], row["value"], row["rank"]) for row in rows] == [
        ("BBBB", 0.1, 1),
        ("AAAA", 0.2, 2),
    ]
