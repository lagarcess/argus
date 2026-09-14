"""Differences between two computed answers are computed once, in Python."""

from __future__ import annotations

import pytest
from argus.domain.computation_compare import ComparisonKindMismatch, card_differences

from tests.domain.calculations.support import run_calculation


def _multiple(price: float, currency: str = "USD"):
    return run_calculation(
        "price_multiple",
        {
            "currency": currency,
            "symbol": "AAPL",
            "price": price,
            "per_share": 6,
            "multiple": None,
        },
    )


def test_right_minus_left_for_every_shared_numeric_fact_in_one_unit() -> None:
    differences = card_differences(_multiple(150), _multiple(180))
    by_key = {(item.section, item.name): item for item in differences}
    answer = next(item for item in differences if item.section == "answer")
    assert (answer.left, answer.right, answer.difference) == (25.0, 30.0, 5.0)
    price = by_key[("input", "price")]
    assert (price.left, price.right, price.difference) == (150.0, 180.0, 30.0)
    assert ("input", "symbol") not in by_key


def test_money_in_another_currency_has_no_difference_and_kinds_never_mix() -> None:
    differences = card_differences(_multiple(150), _multiple(150, currency="DOP"))
    assert all(item.name != "price" for item in differences)
    assert any(item.section == "answer" for item in differences)
    ratio = run_calculation(
        "debt_to_income",
        {
            "currency": "USD",
            "monthly_debt_payments": 1500,
            "monthly_income": 5000,
            "ratio_pct": None,
        },
    )
    with pytest.raises(ComparisonKindMismatch):
        card_differences(_multiple(150), ratio)


def test_a_card_that_did_not_solve_compares_its_inputs_only() -> None:
    failed = run_calculation(
        "price_multiple",
        {
            "currency": "USD",
            "symbol": "AAPL",
            "price": 150,
            "per_share": 0,
            "multiple": None,
        },
    )
    assert failed.outcome.status != "succeeded"
    differences = card_differences(_multiple(150), failed)
    assert {item.section for item in differences} == {"input"}



def _ranking(key_label: str = "Expense ratio", items: list[dict] | None = None):
    return run_calculation(
        "ranked_comparison",
        {
            "currency": "USD",
            "key_label": key_label,
            "key_kind": "percent",
            "prefer": "lower",
            "items": items
            or [
                {"label": "Fund A", "symbol": "AAAA", "value": 0.1},
                {"label": "Fund B", "symbol": "BBBB", "value": 0.2},
            ],
        },
    )


def test_rankings_line_up_only_over_the_same_items_by_the_same_measure() -> None:
    changed = [
        {"label": "Fund A", "symbol": "AAAA", "value": 0.15},
        {"label": "Fund B", "symbol": "BBBB", "value": 0.2},
    ]
    assert card_differences(_ranking(), _ranking(items=changed))
    with pytest.raises(ComparisonKindMismatch):
        card_differences(_ranking(), _ranking(key_label="Five-year return"))
    other_items = [
        {"label": "Fund C", "symbol": "CCCC", "value": 0.1},
        {"label": "Fund B", "symbol": "BBBB", "value": 0.2},
    ]
    with pytest.raises(ComparisonKindMismatch):
        card_differences(_ranking(), _ranking(items=other_items))


def test_a_reordered_ranking_lines_each_item_up_with_itself() -> None:
    reordered = [
        {"label": "Fund A", "symbol": "AAAA", "value": 0.3},
        {"label": "Fund B", "symbol": "BBBB", "value": 0.25},
    ]
    differences = card_differences(_ranking(), _ranking(items=reordered))
    pairs = {(item.left, item.right) for item in differences}
    assert pairs == {(0.1, 0.3), (0.2, 0.25)}


def test_a_reordered_ranking_lines_each_gap_up_with_its_item() -> None:
    left = [
        {"label": "Fund A", "symbol": "AAAA", "value": 0.1},
        {"label": "Fund B", "symbol": "BBBB", "value": 0.2},
        {"label": "Fund C", "symbol": "CCCC", "value": 0.3},
    ]
    right = [
        {"label": "Fund A", "symbol": "AAAA", "value": 0.2},
        {"label": "Fund B", "symbol": "BBBB", "value": 0.15},
        {"label": "Fund C", "symbol": "CCCC", "value": 0.35},
    ]
    differences = card_differences(_ranking(items=left), _ranking(items=right))
    gaps = [item for item in differences if item.name.startswith("gap_")]
    assert [(item.left, item.right) for item in gaps] == [(0.2, 0.2)]
