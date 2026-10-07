"""One receipt's review, composed from facts other owners already hold.

The draft owns capture and preparation status, the extraction batch owns the
immutable evidence, and the import event owns the editable proposal and its
link to recorded activity. Nothing here stores a copy of any of them.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from argus.domain.ingestion.documents.models import (
    DocumentDraft,
    DraftStatus,
    ExtractionBatch,
)
from argus.domain.ingestion.reconcile.matching import ACTIVITY_EVIDENCE
from argus.domain.ingestion.reconcile.recording import missing_fields, recorded_note
from argus.domain.ingestion.reconcile.store import ImportTx

ReceiptStatus = DraftStatus | Literal["confirmed", "dismissed"]
# Why a receipt has no single purchase to review yet.
Blocker = Literal["not_prepared", "no_purchase_found", "receipt_purchase_ambiguous"]


@dataclass(frozen=True)
class ReceiptFields:
    """The proposal the person reviews; ``merchant`` is the note ``accept`` records."""

    merchant: str | None
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
    missing: tuple[str, ...]
    blocker: Blocker | None
    evidence: dict[str, Any] | None
    event_id: str | None
    event_version: int | None
    expense_id: str | None


def receipt_review(
    draft: DocumentDraft,
    batch: ExtractionBatch | None,
    events: Iterable[Mapping[str, Any]],
) -> ReceiptReview:
    """``events`` are import event views; only this receipt's purchases count."""

    purchases = [
        event
        for event in events
        if event["evidence"] in ACTIVITY_EVIDENCE
        and any(o["connection_id"] == draft.connection_id for o in event["observations"])
    ]
    evidence = (
        None
        if batch is None
        else {
            "receipt": batch.receipt.model_dump(mode="json") if batch.receipt else None,
            "issues": [issue.code for issue in batch.issues],
        }
    )
    blocker: Blocker | None = None
    if batch is None:
        blocker = "not_prepared"
    elif not purchases:
        blocker = "no_purchase_found"
    elif len(purchases) > 1:
        blocker = "receipt_purchase_ambiguous"
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
    status: ReceiptStatus = {"accepted": "confirmed", "dismissed": "dismissed"}.get(
        event["state"], draft.status
    )
    return ReceiptReview(
        receipt_id=draft.connection_id,
        status=status,
        error_code=draft.error_code,
        fields=ReceiptFields(
            merchant=recorded_note(event),
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
        expense_id=event["activity_id"] if event["state"] == "accepted" else None,
    )


def receipt_ids(tx: ImportTx, activity_ids: Iterable[str]) -> dict[str, str]:
    """Activity id to the receipt (document connection) it was recorded from.

    An activity recorded by hand, or from several documents, has no entry.
    """

    events = tx.activity_links()
    found = {}
    for activity_id in activity_ids:
        event_id = events.get(activity_id)
        if event_id is None:
            continue
        documents = {
            o.connection_id for o in tx.observations(event_id) if o.source == "statement"
        }
        if len(documents) == 1:
            found[activity_id] = documents.pop()
    return found
