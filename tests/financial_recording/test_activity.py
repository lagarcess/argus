from tests.financial_recording import scenarios
from tests.financial_recording.scenarios import Scene


def test_transfer_to_an_unknown_account_is_an_issue_not_a_crash():
    scene = Scene()
    checking = scene.account("Corriente", "checking", "DOP", "100.00")
    draft = scene.act("transfer", checking, "10.00", 2, counter_account_id="acct-99")
    assert scene.issues(draft) == {"account_unknown": "blocking"}
    assert scene.store.preview(draft.id).basis == {checking.id: 1}


def test_expense_beyond_known_balance_confirms_with_a_notice():
    result = scenarios.expense_beyond_known_balance()
    assert result["issues"] == {
        "known": {"negative_asset_balance": "notice"},
        "unknown": {},
    }
    assert (result["confirm_known"], result["confirm_unknown"]) == ("ok", "ok")
    assert result["balances"]["known"]["amount"] == -5000
    assert result["balances"]["unknown"] == {
        "state": "unknown",
        "activity_since_tracking": -4000,
    }


def test_income_is_totalled_by_category_and_categories_follow_the_kind():
    result = scenarios.income_with_category()
    assert result["mismatch_issues"] == {"category_kind_mismatch": "blocking"}
    assert result["mismatch_confirm"] == "ReviewRequired:category_kind_mismatch"
    assert result["activity_records"] == 3
    dop = result["totals"]["DOP"]
    assert dop["income"] == 1_820_000
    assert dop["income_by_category"] == {"remittance": 1_800_000, "other": 20_000}
    assert dop["spending"] == 30_000
    assert dop["spending_by_category"] == {"other": 30_000}


def test_same_currency_transfer_moves_money_without_income_or_spending():
    result = scenarios.same_currency_transfer()
    assert result["balances"] == {"checking": 1_500_000, "savings": 600_000}
    assert (result["net_before"], result["net_after"]) == (2_100_000, 2_100_000)
    both = result["totals_both"]["DOP"]
    savings = result["totals_savings_only"]["DOP"]
    checking = result["totals_checking_only"]["DOP"]
    assert [both["income"], both["spending"], both["moved_in_from_outside_scope"]] == [
        0,
        0,
        0,
    ]
    assert [savings["income"], savings["moved_in_from_outside_scope"]] == [0, 500_000]
    assert [checking["spending"], checking["moved_out_of_scope"]] == [0, 500_000]
    assert result["to_same_account"] == {"counter_account_same": "blocking"}


def test_card_purchase_is_spending_once_and_its_payment_is_not():
    result = scenarios.credit_card_purchase_then_payment()
    assert result["after_purchase"]["card"] == -300_000
    assert result["after_purchase"]["totals"]["DOP"]["spending"] == 300_000
    paid = result["after_payment"]
    assert (paid["card"], paid["checking"]) == (0, 700_000)
    assert paid["totals"]["DOP"]["spending"] == 300_000
    assert paid["totals"]["DOP"]["income"] == 0
    row = result["card_statement_payment_row"]
    assert row["issues"] == {"possible_duplicate": "blocking"}
    assert row["matches"] == [row["payment_record"]]


def test_overdraft_loan_payment_and_card_interest():
    assert scenarios.overdraft_and_debt() == {
        "overdraft_issues": {"negative_asset_balance": "notice"},
        "balances": {"checking": -100_000, "loan": -2_100_000, "card": -104_500},
        "payment_to_asset_issues": {"counter_not_liability": "blocking"},
        "totals": {"interest": 4500, "uncategorized": 150_000},
        "position": {"assets": -100_000, "liabilities": -2_204_500, "net": -2_304_500},
    }


def test_cross_currency_movement_blocks_and_never_converts():
    assert scenarios.cross_currency_transfer_unresolved() == {
        "transfer_issues": {"cross_currency_unresolved": "blocking"},
        "payment_issues": {"cross_currency_unresolved": "blocking"},
        "confirm": "ReviewRequired:cross_currency_unresolved",
        "balances": [1_000_000, 10_000, -5000],
    }
