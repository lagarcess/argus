from datetime import datetime

import pytest
from faker import Faker

from tests.financial_recording import scenarios
from tests.financial_recording.derive import DEFAULT_TZ, Provenance, balance
from tests.financial_recording.model import ReviewRequired, StalePreview, Store

NOW = datetime(2026, 9, 2, 10, tzinfo=DEFAULT_TZ)


def test_duplicate_submission_writes_once():
    assert scenarios.duplicate_submission() == {
        "accounts": 1,
        "same_account_returned": True,
        "create_changed_body": "IdempotencyConflict",
        "record_ids": ["rec-4", "rec-4", "rec-4"],
        "same_key_different_body": "IdempotencyConflict",
        "activity_records": 1,
        "balance": 90_000,
    }


def test_stale_preview_never_writes_and_a_fresh_one_writes_once():
    assert scenarios.stale_preview_two_confirms() == {
        "stale_attempts": ["StalePreview", "StalePreview"],
        "activity_records_after_stale": 1,
        "fresh_confirm_record": "rec-6",
        "activity_records": 2,
        "balance": 70_000,
    }


def test_batch_confirm_is_all_or_nothing():
    fake = Faker("es")
    fake.seed_instance(20260902)
    store = Store(lambda: NOW)
    cash = store.create_account(
        fake.first_name(), "cash", "DOP", "100.00", idempotency_key="create"
    )
    source = Provenance("manual", NOW)
    fields = {"kind": "expense", "account_id": cash.id, "occurred_on": "2026-09-02"}
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
    cash = store.create_account("Efectivo", "cash", "DOP", "100.00", idempotency_key="c")
    source = Provenance("document", NOW, {"digest": "d1", "row": 1})
    fields = {
        "kind": "expense",
        "account_id": cash.id,
        "amount": "10.00",
        "occurred_on": "2026-09-02",
    }
    first = store.draft(fields, source)
    store.reject(first.id)
    second = store.draft(fields, source)
    assert store.preview(second.id).issues == ()
    stale = store.preview(second.id)
    store.edit_draft(second.id, amount="12.00")
    with pytest.raises(StalePreview):
        store.confirm(stale, "k")
    store.confirm(store.preview(second.id), "k")
    assert balance(store.book, cash.id).amount == 8_800
