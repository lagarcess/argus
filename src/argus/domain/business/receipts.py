"""A receipt as the Business owner sees it, composed from the facts its owners hold.

``receipt_review`` decides status, fields and the recorded expense. This module
only shapes that review for the Business wire and derives updates from it. It
stores nothing.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from argus.domain.ingestion.documents.models import DocumentDraft, ExtractionBatch
from argus.domain.ingestion.documents.service import entered_by_owner
from argus.domain.ingestion.receipt_review import (
    ReceiptReview,
    ReceiptStatus,
    receipt_review,
)

Channel = Literal["web", "whatsapp"]
REVIEW_FIELDS = (
    "merchant",
    "occurred_on",
    "amount",
    "currency",
    "category_id",
    "account_id",
)
AWAITING_REVIEW: frozenset[ReceiptStatus] = frozenset(
    {"saved", "queued", "preparing", "review_ready"}
)
CLOSED: frozenset[ReceiptStatus] = frozenset({"confirmed", "dismissed"})
# What a receipt nobody has read needs before the owner can save it by hand.
UNREAD_NEEDS = ("account_id", "amount", "currency", "occurred_on")
_UPDATE_KINDS: Mapping[str, str] = {
    "review_ready": "receipt_ready",
    "needs_attention": "receipt_needs_attention",
    "confirmed": "expense_confirmed",
}


@dataclass(frozen=True)
class Receipt:
    draft: DocumentDraft
    review: ReceiptReview
    channel: Channel
    entered_by_owner: bool = False

    @property
    def id(self) -> str:
        return self.draft.connection_id

    @property
    def status(self) -> ReceiptStatus:
        # Prepared, yet with no single purchase to confirm: the owner must look.
        if self.review.status == "review_ready" and self.review.blocker is not None:
            return "needs_attention"
        return self.review.status

    @property
    def error_code(self) -> str | None:
        if self.status == "needs_attention" and self.review.error_code is None:
            return self.review.blocker
        return self.review.error_code

    @property
    def version(self) -> int:
        """The import event's version; 0 while there is no purchase to review."""

        return self.review.event_version or 0

    @property
    def enterable(self) -> bool:
        """The owner may fill it in by hand: never read and not being read, or
        entered by hand before its purchase reached review."""

        if self.entered_by_owner:
            return self.review.blocker == "no_purchase_found"
        return self.review.blocker == "not_prepared" and self.draft.status not in (
            "queued",
            "preparing",
        )

    @property
    def missing_fields(self) -> list[str]:
        if self.enterable:
            return list(UNREAD_NEEDS)
        return [name for name in self.review.missing if name in REVIEW_FIELDS]

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "channel": self.channel,
            "filename": self.draft.filename,
            "media_type": self.draft.media_type,
            "size_bytes": self.draft.size_bytes,
            "received_at": self.draft.created_at,
            "status": self.status,
            "error_code": self.error_code,
            "expense_id": self.review.expense_id,
            **review_fields(self.review),
        }

    def detail(self) -> dict[str, Any]:
        return {
            **self.summary(),
            "version": self.version,
            "evidence": None if self.entered_by_owner else evidence(self.review),
            "missing_fields": self.missing_fields,
        }


def review_fields(review: ReceiptReview) -> dict[str, str | None]:
    """The review's proposal under the Business wire names.

    The only reader of ``ReceiptFields``, so a rename there changes one place.
    """

    fields = review.fields
    if fields is None:
        return dict.fromkeys(REVIEW_FIELDS)
    return {
        "merchant": fields.note,
        "occurred_on": fields.occurred_on,
        "amount": fields.amount,
        "currency": fields.currency,
        "category_id": fields.category_id,
        "account_id": fields.account_id,
    }


def compose(
    draft: DocumentDraft,
    batch: ExtractionBatch | None,
    events: Iterable[Mapping[str, Any]],
    channel: Channel,
) -> Receipt:
    return Receipt(
        draft, receipt_review(draft, batch, events), channel, entered_by_owner(batch)
    )


def evidence(review: ReceiptReview) -> dict[str, Any] | None:
    """What the receipt itself says. Review corrections never change it."""

    read = (review.evidence or {}).get("receipt")
    if read is None:
        return None
    return {
        "merchant": read["merchant"],
        "occurred_on": read["occurred_on"],
        "total": read["total"],
        "currency": read["currency"],
        "tax": read["tax"],
        "tip": read["tip"],
        "service": read["service"],
        "lines": [
            {"description": item["description"] or "", "amount": item["total"]}
            for item in read["items"]
        ],
    }


def updates(
    receipts: Iterable[Receipt], confirmed_at: Mapping[str, datetime]
) -> list[dict[str, Any]]:
    """Newest first. ``confirmed_at`` maps an expense id to when it was recorded."""

    items = []
    for receipt in receipts:
        kind = _UPDATE_KINDS.get(receipt.status)
        if kind is None:
            continue
        expense_id = receipt.review.expense_id
        items.append(
            {
                "id": f"{kind}:{receipt.id}",
                "kind": kind,
                "occurred_at": confirmed_at.get(
                    expense_id or "", receipt.draft.updated_at
                ),
                "receipt_id": receipt.id,
                "expense_id": expense_id,
                "error_code": receipt.error_code,
                "label": review_fields(receipt.review)["merchant"]
                or receipt.draft.filename,
            }
        )
    return sorted(items, key=lambda item: item["occurred_at"], reverse=True)
