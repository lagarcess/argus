from tests.financial_recording import scenarios
from tests.financial_recording.scenes import Scene

BLOCKING = "blocking"


def test_transfer_to_an_unknown_account_is_an_issue_not_a_crash():
    scene = Scene()
    checking = scene.account("Corriente", "checking", "DOP", "100.00")
    draft = scene.act("transfer", checking, "10.00", 2, counter_account_id="acct-99")
    assert scene.issues(draft) == {"account_unknown": BLOCKING}
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


def test_income_is_totalled_by_category_and_category_is_not_the_kind():
    result = scenarios.income_with_category()
    dop = result["totals"]["DOP"]
    assert (dop["income"], dop["income_by_category"]) == (
        1_800_000,
        {"remittance": 1_800_000},
    )
    assert dop["spending_by_category"] == {"uncategorized": 30_000}
    assert result["category_on_wrong_kind"] == {"category_kind_mismatch": BLOCKING}
    assert result["category_on_transfer"] == {"category_not_applicable": BLOCKING}


def test_same_currency_transfer_moves_money_without_income_or_spending():
    result = scenarios.same_currency_transfer()
    assert result["balances"] == {"checking": 1_500_000, "savings": 600_000}
    assert (result["net_before"], result["net_after"]) == (2_100_000, 2_100_000)
    both = result["totals_both"]["DOP"]
    assert [both["income"], both["spending"], both["moved_in_from_outside_scope"]] == [
        0,
        0,
        0,
    ]
    savings = result["totals_savings_only"]["DOP"]
    assert [savings["income"], savings["moved_in_from_outside_scope"]] == [0, 500_000]
    checking = result["totals_checking_only"]["DOP"]
    assert [checking["spending"], checking["moved_out_of_scope"]] == [0, 500_000]
    assert result["to_same_account"] == {"counter_account_same": BLOCKING}


def test_card_purchase_is_spending_once_and_its_payment_is_not():
    result = scenarios.credit_card_purchase_then_payment()
    assert result["after_purchase"]["card"] == -300_000
    paid = result["after_payment"]
    assert (paid["card"], paid["checking"]) == (0, 700_000)
    assert (paid["totals"]["DOP"]["spending"], paid["totals"]["DOP"]["income"]) == (
        300_000,
        0,
    )
    row = result["card_statement_payment_row"]
    assert row["issues"] == {"possible_duplicate": BLOCKING}
    assert row["matches"] == [row["payment_record"]]


def test_overdraft_debt_payment_and_card_interest():
    assert scenarios.overdraft_and_debt() == {
        "balances": [-100_000, -2_100_000, -204_500],
        "spending_by_category": {"interest_charge": 4500, "uncategorized": 150_000},
        "position": {"assets": -100_000, "liabilities": -2_304_500, "net": -2_404_500},
    }


def test_cross_currency_movement_blocks_and_never_converts():
    assert scenarios.cross_currency_transfer_unresolved() == {
        "transfer_issues": {"cross_currency_unresolved": BLOCKING},
        "payment_issues": {"cross_currency_unresolved": BLOCKING},
        "confirm": "ReviewRequired:cross_currency_unresolved",
        "balances": [1_000_000, 10_000, -5000],
    }


def test_linked_legs_change_vanish_and_return_together():
    result = scenarios.linked_correction_and_removal()
    assert result["recorded"] == [900_000, 100_000, 0]
    assert result["amount_corrected"] == [850_000, 150_000, 0]
    assert result["counter_corrected"] == [850_000, 0, 150_000]
    assert (result["stale_correction"], result["after_stale"]) == (
        "StaleVersion",
        [850_000, 0, 150_000],
    )
    assert result["moved_to_other_currency"] == "InvalidInput:currency_mismatch"
    assert result["removed"] == [1_000_000, 0, 0]
    assert result["restored_same_record"] is True
    assert result["restored"] == [850_000, 0, 150_000]
    assert result["history"] == [
        [100_000, None, False, "person-1"],
        [150_000, "amount was 1,500", False, "person-1"],
        [150_000, "went to Meta", False, "person-2"],
        [150_000, "never happened", True, "person-2"],
        [150_000, "it did happen", False, "person-2"],
    ]
