"""One receipt's review, composed from facts other owners already hold.

The draft owns capture and preparation status, the extraction batch owns the
immutable evidence and whether the document is a receipt, and the import event
owns the editable proposal and its link to recorded activity. Nothing here
stores a copy of any of them.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import cache
from typing import Any, Literal, get_args

from argus.domain.ingestion.documents.models import (
    RECEIPT_PURCHASE_AMBIGUOUS,
    DocumentDraft,
    DraftStatus,
    ExtractionBatch,
)
from argus.domain.ingestion.documents.store import DocumentStore
from argus.domain.ingestion.reconcile.matching import ACTIVITY_EVIDENCE
from argus.domain.ingestion.reconcile.model import EventState
from argus.domain.ingestion.reconcile.recording import missing_fields, recorded_note
from argus.domain.ingestion.reconcile.store import ImportTx

ReceiptStatus = DraftStatus | Literal["confirmed", "dismissed"]
# Why a receipt has no single purchase to review yet.
Blocker = Literal[
    "not_prepared",
    "receipt_purchase_ambiguous",
    "no_purchase_found",
    "several_purchases_found",
]
# The import event states ``receipt_review`` reads; list events with these.
RECEIPT_EVENT_STATES: tuple[EventState, ...] = get_args(EventState)
_EVENT_STATUS: dict[str, ReceiptStatus] = {
    "accepted": "confirmed",
    "dismissed": "dismissed",
}


@dataclass(frozen=True)
class ReceiptFields:
    """The proposal the person reviews.

    ``note`` is what ``accept`` records as the activity note: the person's
    note, else the merchant the receipt shows. ``amount`` is the normalized
    decimal string import events carry, so compare it by value.
    """

    note: str | None
    occurred_on: str | None
    amount: str | None
    currency: str | None
    category_id: str | None
    account_id: str | None


@dataclass(frozen=True)
class ReceiptReview:
    receipt_id: str
    status: ReceiptStatus
    error_code: str | None
    fields: ReceiptFields | None
    # Fields the person must still supply. Empty means the fields are complete,
    # not that accept will succeed: preview still checks the request.
    missing: tuple[str, ...]
    blocker: Blocker | None
    evidence: dict[str, Any] | None
    event_id: str | None
    event_version: int | None
    expense_id: str | None


def _is_receipt(batch: ExtractionBatch | None) -> bool:
    return batch is not None and batch.receipt is not None


def _from_receipt(
    source: str, live: bool, connection_id: str, is_receipt: Callable[[str], bool]
) -> bool:
    """The one test for an observation that a receipt document still holds."""

    return live and source == "statement" and is_receipt(connection_id)


def receipt_review(
    draft: DocumentDraft,
    batch: ExtractionBatch | None,
    events: Iterable[dict[str, Any]],
) -> ReceiptReview:
    """``events`` are import event views listed with ``RECEIPT_EVENT_STATES``."""

    def this_receipt(connection_id: str) -> bool:
        return connection_id == draft.connection_id and _is_receipt(batch)

    purchases = [
        event
        for event in events
        if event["evidence"] in ACTIVITY_EVIDENCE
        and any(
            _from_receipt(o["source"], o["live"], o["connection_id"], this_receipt)
            for o in event["observations"]
        )
    ]
    blocker: Blocker | None = None
    if batch is None:
        blocker = "not_prepared"
    elif any(issue.code == RECEIPT_PURCHASE_AMBIGUOUS for issue in batch.issues):
        blocker = RECEIPT_PURCHASE_AMBIGUOUS
    elif not purchases:
        blocker = "no_purchase_found"
    elif len(purchases) > 1:
        blocker = "several_purchases_found"
    evidence = (
        None
        if batch is None
        else {
            "receipt": batch.receipt.model_dump(mode="json") if batch.receipt else None,
            "issues": [issue.code for issue in batch.issues],
        }
    )
    if blocker is not None:
        return ReceiptReview(
            receipt_id=draft.connection_id,
            status=draft.status,
            error_code=draft.error_code,
            fields=None,
            missing=(),
            blocker=blocker,
            evidence=evidence,
            event_id=None,
            event_version=None,
            expense_id=None,
        )
    [event] = purchases
    facts = event["facts"]
    status = _EVENT_STATUS.get(event["state"], draft.status)
    return ReceiptReview(
        receipt_id=draft.connection_id,
        status=status,
        error_code=draft.error_code,
        fields=ReceiptFields(
            note=recorded_note(event),
            occurred_on=facts["occurred_on"],
            amount=facts["amount"],
            currency=facts["currency"],
            category_id=event["resolution"].get("category_id"),
            account_id=facts["account_id"],
        ),
        missing=tuple(missing_fields(event)),
        blocker=None,
        evidence=evidence,
        event_id=event["id"],
        event_version=event["version"],
        expense_id=event["activity_id"],
    )


def receipt_ids(
    tx: ImportTx,
    documents: DocumentStore,
    user_id: str,
    activity_ids: Iterable[str],
) -> dict[str, str]:
    """Activity id to the receipt (document connection) it was recorded from.

    An activity recorded by hand, evidenced by no receipt or by several, or
    whose receipt was disconnected, has no entry.
    """

    @cache
    def is_receipt(connection_id: str) -> bool:
        return _is_receipt(documents.get(user_id=user_id, connection_id=connection_id))

    events = tx.activity_links()
    found = {}
    for activity_id in activity_ids:
        event_id = events.get(activity_id)
        if event_id is None:
            continue
        held = {
            o.connection_id
            for o in tx.observations(event_id)
            if _from_receipt(o.source, o.live, o.connection_id, is_receipt)
        }
        if len(held) == 1:
            found[activity_id] = held.pop()
    return found
