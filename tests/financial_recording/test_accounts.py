from tests.financial_recording import scenarios

NO_ACTIVITY = {
    "spending": 0,
    "income": 0,
    "moved_in_from_outside_scope": 0,
    "moved_out_of_scope": 0,
    "spending_by_category": {},
    "income_by_category": {},
}


def test_large_opening_is_a_known_balance_and_never_income():
    result = scenarios.clavito_large_opening()
    assert result["balance"] == {
        "state": "known",
        "amount": 25_000_000,
        "as_of": "2026-09-01T09:00:00-04:00",
        "basis": "opening",
    }
    assert result["totals"] == {"DOP": NO_ACTIVITY}


def test_blank_opening_stays_unknown_after_spending():
    result = scenarios.blank_opening_unknown()
    assert result["balance_before"] == {"state": "unknown", "activity_since_tracking": 0}
    assert result["balance_after"] == {
        "state": "unknown",
        "activity_since_tracking": -85_000,
    }
    assert result["totals"]["DOP"]["spending"] == 85_000
    assert result["totals"]["DOP"]["income"] == 0
    dop = result["position"]["DOP"]
    assert (dop["assets"], dop["liabilities"], dop["net"]) == (None, None, None)
    assert dop["coverage"]["accounts_known"] == []
    assert dop["coverage"]["accounts_unknown"] == ["acct-1"]


def test_account_edit_rules():
    assert scenarios.account_edit_rules() == {
        "trimmed": "Clavito",
        "blank_name": "InvalidInput:nickname_invalid",
        "currency_on_empty": "USD",
        "currency_on_used": "InvalidInput:currency_locked",
        "nature_flip_on_used": "InvalidInput:nature_change_requires_empty_account",
        "same_nature_on_used": "savings",
        "stale_version": "StaleVersion",
        "archived_version": 3,
        "archived_draft_issues": {"account_archived": "blocking"},
        "correct_on_archived": "ok",
    }


def test_create_reopen_edit_then_correct_the_opening():
    result = scenarios.first_slice_create_reopen_edit()
    assert result["reopened"] == {
        "nickname": "Cuenta nomina",
        "version": 1,
        "balance": 1_250_000,
    }
    assert result["edited"] == {
        "nickname": "Nomina",
        "type": "savings",
        "version": 2,
        "balance": 1_250_000,
    }
    corrected = result["after_opening_correction"]
    assert corrected["balance"]["amount"] == 1_300_000
    assert corrected["balance"]["basis"] == "opening"
    assert corrected["version"] == 3
    assert corrected["totals"] == {"DOP": NO_ACTIVITY}
