from tests.financial_recording import scenarios

NO_ACTIVITY = {
    "income": 0,
    "income_by_category": {},
    "moved_in_from_outside_scope": 0,
    "moved_out_of_scope": 0,
    "purchases": 0,
    "refunds": 0,
    "spending": 0,
    "spending_by_category": {},
}


def test_a_large_opening_balance_is_known_and_not_income():
    result = scenarios.clavito_large_opening()
    assert result["balance"] == {
        "state": "known",
        "amount": 25_000_000,
        "as_of": "2026-09-01T09:00:00-04:00",
        "basis": "opening",
    }
    assert result["totals"] == {"DOP": NO_ACTIVITY}


def test_a_blank_opening_stays_unknown_and_unknown_totals_are_not_zero():
    result = scenarios.blank_opening_unknown()
    assert result["nickname"] is None
    assert result["balance_before"] == {"state": "unknown", "activity_since_tracking": 0}
    assert result["balance_after"] == {
        "state": "unknown",
        "activity_since_tracking": -85_000,
    }
    assert result["totals"]["DOP"]["spending"] == 85_000
    dop = result["position"]["DOP"]
    assert (dop["assets"], dop["liabilities"], dop["net"]) == (None, None, None)
    assert dop["coverage"]["accounts_unknown"] == ["acct-1"]


def test_account_edit_rules_follow_the_final_baseline():
    assert scenarios.account_edit_rules() == {
        "trimmed": "Clavito",
        "blank_clears_nickname": None,
        "long_nickname": "InvalidInput:nickname_invalid",
        "currency_on_empty": "USD",
        "currency_on_opened": "InvalidInput:currency_locked",
        "nature_flip_on_opened": "InvalidInput:nature_change_requires_empty_account",
        "same_nature_on_opened": "savings",
        "type_after_activity": "InvalidInput:type_locked",
        "stale_version": "StaleVersion",
        "archived_version": 3,
        "archived_draft_issues": {"account_archived": "notice"},
        "archived_draft_confirm": "ok",
        "correct_on_archived": "ok",
        "archived_still_in_totals": 13_500,
    }


def test_archived_accounts_stay_in_totals_and_unknown_sides_stay_unknown():
    result = scenarios.unknown_coverage_disclosure()
    dop = result["position"]["DOP"]
    assert (dop["assets"], dop["liabilities"], dop["net"]) == (1_080_000, 0, 1_080_000)
    coverage = dop["coverage"]
    assert coverage["accounts_known"] == ["acct-1", "acct-4"]
    assert coverage["accounts_unknown"] == ["acct-3"]
    assert coverage["archived_included"] == ["acct-4"]
    assert [
        (gap["recorded"], gap["remaining"]) for gap in coverage["unexplained_gaps"]
    ] == [(-10_000, -10_000)]
    assert result["spending"] == 10_000
    assert result["unknown_asset_side"] == [None, -300_000, None]


def test_first_slice_create_reopen_edit_needs_no_category_catalog():
    result = scenarios.first_slice_create_reopen_edit()
    assert result["reopened"] == {
        "nickname": "Cuenta nomina",
        "type": "checking",
        "currency": "DOP",
        "balance": {
            "state": "known",
            "amount": 1_250_000,
            "as_of": "2026-09-01T09:00:00-04:00",
            "basis": "opening",
        },
        "version": 1,
    }
    assert result["unnamed_account"] == [
        None,
        {"state": "unknown", "activity_since_tracking": 0},
    ]
    assert result["catalog_untouched"] is True
    assert result["edited"] == ["Nomina", "savings", 2]
    assert result["stale_edit"] == "StaleVersion"
    assert result["balance_after_opening_correction"] == 1_200_000
    assert result["totals_after_opening_correction"] == [0, 0]
    assert result["opening_revisions"] == 2


def test_changing_the_opening_date_reviews_affected_history():
    assert scenarios.opening_date_correction() == {
        "balance_before": 90_000,
        "unreviewed_date_change": "ReviewRequired:opening_date_reorders_activity",
        "balance_after": 100_000,
        "spending": 10_000,
        "revisions": [
            ["2026-09-05T09:00:00-04:00", None],
            ["2026-09-07T09:00:00-04:00", "balance was on the 7th"],
        ],
    }
