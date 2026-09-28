from tests.financial_recording import scenarios

UNEXPLAINED = "unexplained"


def test_a_check_keeps_what_it_showed_and_stays_outside_spending():
    assert scenarios.observation_gap() == {
        "balance": 750_000,
        "gaps": [[-50_000, -50_000, UNEXPLAINED]],
        "spending": 200_000,
        "income": 0,
        "shown_at_confirmation": [800_000, -50_000],
    }


def test_late_activity_before_a_check_is_asked_and_counted_once():
    result = scenarios.late_explanation()
    assert result["asked_about_the_check"] is True
    assert result["confirm_unanswered"] == "ReviewRequired:inclusion_unanswered"
    assert result["explained_by_late_record"] is True
    assert (result["balance"], result["spending"], result["income"]) == (
        750_000,
        250_000,
        0,
    )
    assert result["gaps"] == [[-50_000, 0, UNEXPLAINED]]
    assert result["answered_not_included"] == {
        "balance": 700_000,
        "gaps": [[-50_000, -50_000, UNEXPLAINED]],
        "spending": 250_000,
        "income": 0,
        "explained_by_late_record": False,
    }


def test_new_activity_after_a_check_moves_the_balance_without_a_question():
    assert scenarios.new_expense_after_observation() == {
        "questions": [],
        "balance": 700_000,
        "gaps": [[-50_000, 0, UNEXPLAINED]],
        "spending": 300_000,
        "income": 0,
    }


def test_partial_explanation_keeps_the_remaining_difference():
    assert scenarios.partial_reconciliation() == {
        "gaps_before": [[-50_000, -50_000, UNEXPLAINED]],
        "gaps_after": [[-50_000, -20_000, UNEXPLAINED]],
        "balance": 950_000,
    }


def test_backdated_correction_moves_the_remainder_not_the_recorded_difference():
    result = scenarios.backdated_correction()
    assert result["gaps_before"] == [[-50_000, -50_000, UNEXPLAINED]]
    assert result["gaps"] == [[-50_000, -40_000, UNEXPLAINED]]
    assert (result["balance"], result["spending"]) == (750_000, 210_000)
    assert result["revisions"] == [
        [200_000, None, "person-1"],
        [210_000, "receipt shows 2,100", "person-1"],
    ]
    assert result["stale_correction"] == "StaleVersion"


def test_each_check_is_measured_from_the_one_before_it():
    assert scenarios.two_observations() == {
        "gaps_before": [
            [-100_000, -100_000, UNEXPLAINED],
            [-20_000, -20_000, UNEXPLAINED],
        ],
        "asked_only_the_later_check": True,
        "gaps_after": [[-100_000, -100_000, UNEXPLAINED], [-20_000, 0, UNEXPLAINED]],
        "balance": 850_000,
    }


def test_inclusion_answers_cover_older_activity_legs_and_sources():
    result = scenarios.older_activity_inclusion()
    same_day = result["same_day_after_timed_check"]
    assert same_day["included"] == {
        "asked": True,
        "gaps": [[-100_000, 0, UNEXPLAINED]],
        "balance": 900_000,
    }
    assert same_day["not_included"] == {
        "asked": True,
        "gaps": [[-100_000, -100_000, UNEXPLAINED]],
        "balance": 800_000,
    }
    assert result["older_than_two_checks"] == {
        "questions_in_date_order": True,
        "confirm": "ok",
        "gaps": [[0, 0, UNEXPLAINED], [-100_000, 0, UNEXPLAINED]],
        "balance": 900_000,
    }
    assert result["transfer_answers_each_leg"] == {
        "one_question_per_leg": True,
        "balances": [900_000, 600_000],
        "gaps": [[[-100_000, 0, UNEXPLAINED]], [[0, 0, UNEXPLAINED]]],
    }
    assert result["statement_rows_answer_from_source"] == {
        "row_issues": {},
        "confirm": "ok",
        "gaps": [[-50_000, 0, UNEXPLAINED]],
        "balance": 950_000,
    }
    assert result["same_day_as_opening"] == {
        "asked": True,
        "balance": 100_000,
        "spending": 20_000,
    }


def test_revaluation_is_not_income_and_share_weights_asset_and_debt_alike():
    assert scenarios.asset_revaluation_and_share() == {
        "estimate_basis": "value_estimate",
        "gaps": [[-10_000_000, -10_000_000, "revaluation"]],
        "totals": {
            "DOP": {
                "income": 0,
                "income_by_category": {},
                "moved_in_from_outside_scope": 0,
                "moved_out_of_scope": 0,
                "purchases": 0,
                "refunds": 0,
                "spending": 0,
                "spending_by_category": {},
            }
        },
        "full": {"assets": 90_000_000, "liabilities": -40_000_000, "net": 50_000_000},
        "owner_share": {
            "assets": 45_000_000,
            "liabilities": -20_000_000,
            "net": 25_000_000,
        },
        "loan_linked_to": True,
    }
