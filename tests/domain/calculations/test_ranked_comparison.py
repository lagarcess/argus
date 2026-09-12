from __future__ import annotations

from tests.domain.calculations.support import run_calculation


def test_items_rank_by_the_stated_key_with_ties_and_no_recommendation() -> None:
    card = run_calculation(
        "ranked_comparison",
        {
            "currency": "DOP",
            "key_label": "Annual rate",
            "key_kind": "percent",
            "prefer": "lower",
            "items": [
                {"label": "Card A", "value": 24.9},
                {"label": "Card B", "value": 18.5},
                {"label": "Card C", "value": 18.5, "symbol": None},
            ],
        },
    )
    assert card.outcome.status == "succeeded"
    rows = card.outcome.result["rows"]
    assert [(row["label"], row["rank"]) for row in rows] == [
        ("Card B", 1),
        ("Card C", 1),
        ("Card A", 3),
    ]
    assert card.presentation.answer.label.interpolation_args == {
        "rank": 1,
        "label": "Card B",
    }
    assert card.presentation.answer.unit.locale_key == "chat.tools.units.percent"
    assert [note.locale_key for note in card.presentation.notes] == [
        "tools.calc.notes.ranked_not_recommended"
    ]


def test_fewer_than_two_items_is_invalid() -> None:
    card = run_calculation(
        "ranked_comparison",
        {
            "currency": "USD",
            "key_label": "Fee",
            "prefer": "lower",
            "items": [{"label": "Only", "value": 1}],
        },
    )
    assert card.outcome.status == "invalid"
