from datetime import datetime

from tests.financial_recording import scenarios, scenarios_lifecycle
from tests.financial_recording.derive import DEFAULT_TZ, position
from tests.financial_recording.model import Store

BLOCKING = "blocking"


def test_partial_refunds_stay_within_the_purchase_and_share_its_category():
    assert scenarios_lifecycle.refund_partial_and_limits() == {
        "over_limit": {"refund_exceeds_purchase": BLOCKING},
        "before_purchase": {"refund_before_purchase": BLOCKING},
        "other_category": {"refund_category_mismatch": BLOCKING},
        "spending": 0,
        "purchases": 100_000,
        "refunds": 100_000,
        "income": 0,
        "refund_shares_purchase_category": {"shopping": 0},
        "remove_purchase": "ReviewRequired:linked_refunds_present",
        "shrink_purchase": "ReviewRequired:refund_exceeds_purchase",
        "first_refund_removed": False,
        "balance": 500_000,
    }


def test_unlinked_cross_account_and_foreign_refunds_use_the_money_received():
    result = scenarios_lifecycle.refund_unlinked_and_cross_account()
    assert result["cross_account_balances"] == [-200_000, 185_000]
    dop = result["dop_totals"]
    assert [dop["purchases"], dop["refunds"], dop["spending"], dop["income"]] == [
        200_000,
        85_000,
        115_000,
        0,
    ]
    assert dop["spending_by_category"] == {
        "shopping": 150_000,
        "groceries": -25_000,
        "uncategorized": -10_000,
    }
    assert result["foreign_currency_link"] == {"refund_link_currency": BLOCKING}
    assert result["foreign_unlinked"] == "ok"
    usd = result["usd_totals_not_clamped"]
    assert [usd["purchases"], usd["refunds"], usd["spending"]] == [0, 1000, -1000]
    assert result["refund_on_investment"] == {"refund_account_unsupported": BLOCKING}
    assert result["refund_on_loan"] == {"refund_account_unsupported": BLOCKING}


def test_a_card_refund_can_leave_credit_in_your_favor():
    assert scenarios_lifecycle.card_refund_credit_balance() == {
        "standing_before": "owed",
        "balance_after": 20_000,
        "standing_after": "credit_in_your_favor",
        "liabilities_total": 20_000,
        "income": 0,
    }


def test_notes_reach_every_record_type_and_never_change_money():
    assert scenarios_lifecycle.notes_across_records() == {
        "longest_note_characters": 200,
        "note_too_long": {"note_too_long": BLOCKING},
        "notes_saved": ["devolución parcial", "saldo en la app"],
        "note_edit_keeps_money": [92_000, 92_000],
        "note_edit_revisions": 2,
        "notes_ignored_for_duplicates": {"possible_duplicate": BLOCKING},
        "note_edit_too_long": "ReviewRequired:note_too_long",
    }


def test_removal_and_restore_return_the_original_record():
    assert scenarios_lifecycle.removal_and_restore() == {
        "start": 70_000,
        "refund_removed": 60_000,
        "purchase_removed": 100_000,
        "restore_refund_first": "ReviewRequired:refund_purchase_removed",
        "stale_restore": "StaleVersion",
        "both_restored": 70_000,
        "same_record": True,
        "purchase_history": [
            [None, False],
            ["wrong account", True],
            ["right account after all", False],
        ],
        "spending": 30_000,
    }


def test_moving_an_account_between_spaces_creates_no_money():
    assert scenarios_lifecycle.spaces_and_account_moves() == {
        "moved_to": "business",
        "records_untouched": True,
        "personal_scope": ["acct-3", "acct-5"],
        "business_scope": ["acct-1"],
        "business_spending": 30_000,
        "business_balance": 170_000,
        "linked_account_move": "ReviewRequired:account_has_links",
    }


def test_custom_categories_have_stable_ids_and_stay_in_their_space():
    assert scenarios_lifecycle.custom_categories() == {
        "custom_in_personal": "InvalidInput:custom_category_space",
        "rename_keeps_identity": True,
        "renamed_label": "Materia prima",
        "totals_by_id_before_and_after_rename": [{"cat-5": 70_000}, {"cat-5": 70_000}],
        "business_category_on_personal_account": {"category_other_space": BLOCKING},
        "rename_default": "InvalidInput:default_category_fixed",
    }


def test_a_plan_occurrence_is_counted_once_and_its_status_is_derived():
    assert scenarios_lifecycle.plan_occurrence_counted_once() == {
        "planned": ["planned", {"DOP": -300_000}],
        "completed": ["completed", {}, 300_000],
        "second_payment_for_same_occurrence": {"expectation_already_fulfilled": BLOCKING},
        "after_refund": "completed",
        "after_amount_correction": "completed",
        "account_change_needs_review": "ReviewRequired:expectation_mismatch",
        "after_unlinking": ["planned", {"DOP": -300_000}],
    }


def test_owner_share_rounds_once_per_total_not_per_account():
    store = Store(lambda: datetime(2026, 9, 2, 10, tzinfo=DEFAULT_TZ))
    scope = [
        store.create_account(
            "cash", "DOP", "0.01", idempotency_key=key, ownership_share_bps=5000
        ).id
        for key in ("mitad-uno", "mitad-dos")
    ]
    shared = position(store.book, scope, weighting="owner_share")["DOP"]
    assert (shared.assets, shared.net) == (1, 1)


def test_positions_never_sum_across_currencies():
    result = scenarios.multiple_precisions()
    assert result["minor_units"] == [1500, 1234, 1050]
    assert result["positions"] == {"DOP": 1050, "JPY": 1500, "KWD": 1234}
    assert (result["jpy_fraction"], result["dop_three_decimals"]) == (
        "InvalidInput:amount_precision",
        "InvalidInput:amount_precision",
    )
    assert result["unknown_currency"] == "InvalidInput:currency_unsupported"


def test_edits_that_move_money_stop_for_review_and_keep_evidence():
    unexplained_zero = [[0, 0, "unexplained"]]
    assert scenarios_lifecycle.edits_that_move_money_need_review() == {
        "removing_a_check_others_depend_on": {
            "blocked": "ReviewRequired:inclusion_unanswered",
            "after_answering": "ok",
            "balance": 800_000,
            "gaps": unexplained_zero,
        },
        "redating_activity_into_a_check": {
            "before": [950_000, unexplained_zero],
            "unanswered": "ReviewRequired:inclusion_unanswered",
            "answered_not_included": [950_000, unexplained_zero],
        },
        "restoring_activity_the_check_never_saw": {
            "unanswered": "ReviewRequired:inclusion_unanswered",
            "balance": 950_000,
            "gaps": unexplained_zero,
        },
        "redating_a_check": {
            "unreviewed": "ReviewRequired:inclusion_changed",
            "balance": 900_000,
            "gaps": unexplained_zero,
        },
        "note_only_correction_keeps_evidence": {
            "before": [[-50_000, 0, "unexplained"]],
            "after": [[-50_000, 0, "unexplained"]],
        },
        "redating_the_opening_onto_untimed_activity": {
            "result": "ReviewRequired:inclusion_unanswered"
        },
        "purchase_edits_recheck_refunds": {
            "later_date": "ReviewRequired:refund_before_purchase",
            "other_category": "ReviewRequired:refund_category_mismatch",
        },
        "custom_category_blocks_a_move": {"move": "ReviewRequired:account_has_links"},
    }
