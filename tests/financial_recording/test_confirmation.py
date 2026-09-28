from datetime import datetime

import pytest
from faker import Faker

from tests.financial_recording import scenarios
from tests.financial_recording.derive import DEFAULT_TZ, Provenance, balance
from tests.financial_recording.model import StalePreview, Store
from tests.financial_recording.review import ReviewRequired

NOW = datetime(2026, 9, 2, 10, tzinfo=DEFAULT_TZ)
BLOCKING = "blocking"


def test_duplicate_submission_writes_once():
    assert scenarios.duplicate_submission() == {
        "accounts": 1,
        "same_account_returned": True,
        "create_changed_body": "IdempotencyConflict",
        "one_record_for_three_confirms": True,
        "same_key_different_body": "IdempotencyConflict",
        "activity_records": 1,
        "balance": 90_000,
    }


def test_stale_preview_never_writes_and_the_refreshed_preview_writes_once():
    assert scenarios.stale_preview_two_confirms() == {
        "stale_attempts": ["StalePreview", "StalePreview"],
        "activity_records_after_stale": 1,
        "draft_kept_for_the_refreshed_review": "100.00",
        "fresh_preview_effects": {"acct-1": -10_000},
        "activity_records": 2,
        "balance": 70_000,
    }


def test_batch_confirm_is_all_or_nothing():
    fake = Faker("es")
    fake.seed_instance(20260902)
    store = Store(lambda: NOW)
    cash = store.create_account(
        "cash", "DOP", "100.00", nickname=fake.first_name(), idempotency_key="create"
    )
    source = Provenance("manual", NOW)
    fields = {"kind": "expense", "account_id": cash.id, "occurred_on": "2026-09-03"}
    good = store.draft({**fields, "amount": "10.00"}, source)
    bad = store.draft({**fields, "amount": "10.001"}, source)
    previews = [store.preview(good.id), store.preview(bad.id)]

    with pytest.raises(ReviewRequired) as blocked:
        store.confirm_batch(previews, "batch")

    assert [item.code for item in blocked.value.issues] == ["amount_precision"]
    assert balance(store.book, cash.id).amount == 10_000
    assert store.state.drafts[good.id].status == "proposed"
    store.confirm_batch(previews[:1], "batch-good")
    assert balance(store.book, cash.id).amount == 9000


def test_a_rejected_draft_frees_its_source_and_an_edited_draft_needs_a_new_preview():
    store = Store(lambda: NOW)
    cash = store.create_account("cash", "DOP", "100.00", idempotency_key="c")
    source = Provenance("document", NOW, {"digest": "d1", "row": 1})
    fields = {
        "kind": "expense",
        "account_id": cash.id,
        "amount": "10.00",
        "occurred_on": "2026-09-03",
    }
    first = store.draft(fields, source)
    store.reject(first.id)
    second = store.draft(fields, source)
    assert store.preview(second.id).issues == ()
    stale = store.preview(second.id)
    store.edit_draft(second.id, amount="12.00")
    with pytest.raises(StalePreview) as refused:
        store.confirm(stale, "k")
    assert refused.value.fresh.effects == {cash.id: -1200}
    store.confirm(store.preview(second.id), "k")
    assert balance(store.book, cash.id).amount == 8_800


def test_a_debt_is_entered_as_the_amount_owed_and_stored_negative_once():
    store = Store(lambda: NOW)
    card = store.create_account("credit_card", "DOP", "2000.00", idempotency_key="k")
    assert balance(store.book, card.id).amount == -200_000


def test_equal_amount_alone_is_never_a_match():
    assert scenarios.equal_amount_not_a_match() == {
        "different_account": {},
        "different_day": {},
        "same_signature": {"possible_duplicate": BLOCKING},
        "confirm_unresolved": "ReviewRequired:possible_duplicate",
        "resolved_distinct": {"activity_records": 4, "spending": 150_000},
        "resolved_duplicate_of": {
            "activity_records": 3,
            "spending": 100_000,
            "confirm_returns_the_existing_record": True,
            "linked_methods": ["chat"],
        },
    }


def test_import_holds_flagged_rows_and_never_records_a_row_twice():
    result = scenarios.duplicate_import_vs_twins()
    assert result["first_import_issues"] == {
        "tx-dop-01": {},
        "tx-dop-02": {},
        "tx-dop-03": {"possible_duplicate": BLOCKING},
        "tx-dop-04": {},
        "tx-dop-05": {"counter_account_missing": BLOCKING},
        "tx-usd-01": {},
        "tx-currency": {"currency_unsupported": BLOCKING},
        "tx-date": {"date_invalid": BLOCKING},
        "tx-number": {"amount_invalid": BLOCKING},
        "tx-missing": {"field_missing": BLOCKING},
        "tx-household": {"field_missing": BLOCKING},
    }
    assert result["confirmed_in_batch"] == 5
    first = result["after_first_import"]["totals"]["DOP"]
    assert [first["purchases"], first["refunds"], first["spending"], first["income"]] == [
        25_100,
        2_550,
        22_550,
        120_000,
    ]
    assert result["reimport"]["confirm"] == "ReviewRequired:already_recorded"
    assert len(result["reimport"]["rows_already_recorded"]) == 11
    assert result["reimport"]["activity_records"] == 5
    assert result["overlap_issues"] == {
        "tx-dop-01": {"already_recorded": BLOCKING},
        "overlap-new": {},
    }
    assert result["household_row_after_picking_account"] == "ok"
    assert result["removed_row_reimport"] == {"already_recorded": BLOCKING}
    assert result["final"] == {"activity_records": 6, "dop_balance": 518_900}
    dop, usd = result["totals"]["DOP"], result["totals"]["USD"]
    assert [dop["spending"], dop["income"]] == [101_100, 120_000]
    assert [usd["spending"], usd["income"]] == [4000, 0]
