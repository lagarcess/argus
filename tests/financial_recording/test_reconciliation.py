from tests.financial_recording import scenarios

OBSERVED_7500 = {
    "state": "known",
    "amount": 750_000,
    "as_of": "2026-09-05T18:00:00-04:00",
    "basis": "user_check",
}


def test_observation_leaves_an_unexplained_gap_outside_spending():
    assert scenarios.observation_gap() == {
        "balance": OBSERVED_7500,
        "gaps": [[-50_000, "unexplained"]],
        "spending": 200_000,
        "income": 0,
    }


def test_late_explanation_closes_the_gap_without_moving_the_balance():
    assert scenarios.late_explanation() == {
        "balance": OBSERVED_7500,
        "gaps": [[0, "unexplained"]],
        "spending": 250_000,
        "income": 0,
    }


def test_expense_after_the_observation_moves_the_balance():
    result = scenarios.new_expense_after_observation()
    assert result["balance"]["amount"] == 700_000
    assert result["spending"] == 300_000
    assert result["gaps"] == [[0, "unexplained"]]


def test_partial_explanation_shrinks_the_gap():
    assert scenarios.partial_reconciliation() == {
        "gaps_before": [[-50_000, "unexplained"]],
        "gaps_after": [[-20_000, "unexplained"]],
        "balance": 950_000,
    }


def test_backdated_correction_moves_the_gap_and_keeps_history():
    result = scenarios.backdated_correction()
    assert result["gaps_before"] == [[-50_000, "unexplained"]]
    assert result["gaps"] == [[-40_000, "unexplained"]]
    assert result["balance"] == OBSERVED_7500
    assert result["spending"] == 210_000
    assert result["revisions"] == [[200_000, None], [210_000, "receipt shows 2,100"]]
    assert result["stale_correction"] == "StaleVersion"


def test_each_gap_is_measured_from_the_previous_anchor_only():
    assert scenarios.two_observations() == {
        "gaps_before": [[-100_000, "unexplained"], [-20_000, "unexplained"]],
        "gaps_after": [[-100_000, "unexplained"], [0, "unexplained"]],
        "balance": 850_000,
    }


def test_same_day_order_blocks_until_placed_and_each_placement_differs():
    result = scenarios.same_day_order()
    assert result["unresolved"] == {
        "issues": {"observation_order_unknown": "blocking"},
        "confirm": "ReviewRequired:observation_order_unknown",
        "gaps": [[-100_000, "unexplained"]],
        "balance": 900_000,
    }
    assert result["before"] == {
        "issues": {},
        "confirm": "ok",
        "gaps": [[0, "unexplained"]],
        "balance": 900_000,
    }
    assert result["after"] == {
        "issues": {},
        "confirm": "ok",
        "gaps": [[-100_000, "unexplained"]],
        "balance": 800_000,
    }
