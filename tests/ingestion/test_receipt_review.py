"""A receipt's review composed from its draft, evidence and import event."""

from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from argus.api.documents import documents_service
from argus.domain.ingestion.documents import extractor as provider
from argus.domain.ingestion.documents.config import DocumentExtractionSettings
from argus.domain.ingestion.documents.models import ExtractionResult
from argus.domain.ingestion.receipt_review import (
    ReceiptFields,
    receipt_ids,
    receipt_review,
)

from tests.ingestion.conftest import ALICE, bearer

DOCUMENTS = "/api/v1/financial-documents"
IMPORTS = "/api/v1/financial-imports"
RECEIPT = Path(__file__).parents[1] / "document_extraction_fixtures/receipt-dop.png"

PURCHASE = {
    "page": 1,
    "row": 1,
    "evidence": "transaction",
    "status": "posted",
    "amount": "1180.00",
    "currency": "DOP",
    "occurred_on": "2026-10-03",
    "direction": "outflow",
    "kind_hint": "expense",
    "merchant": "Ferreteria Ochoa",
}
DETAILS = {
    "merchant": "Ferreteria Ochoa",
    "occurred_on": "2026-10-03",
    "currency": "DOP",
    "items": [
        {"id": "1", "description": "Tornillos", "quantity": "2", "total": "300.00"},
        {"id": "2", "description": "Pintura", "quantity": "1", "total": "700.00"},
    ],
    "subtotal": "1000.00",
    "tax": "180.00",
    "total": "1180.00",
}


def _extract(monkeypatch, observations, receipt=DETAILS):
    monkeypatch.setenv("ARGUS_DOCUMENT_EXTRACTION_ENABLED", "true")
    monkeypatch.setenv("ARGUS_VISION_MODEL", "test/vision")
    monkeypatch.setenv("OPENROUTER_API_KEY", "offline-test-key")
    result = ExtractionResult.model_validate(
        {
            "complete": True,
            "readable": True,
            "pages_read": [1],
            "observations": observations,
            "receipt": receipt,
        }
    )
    monkeypatch.setattr(
        provider, "invoke_openrouter_json_schema", AsyncMock(return_value=result)
    )
    monkeypatch.setattr(
        documents_service(),
        "extractor",
        provider.DocumentExtractor(DocumentExtractionSettings(enabled=True)),
    )


def _upload(client, consent="true"):
    response = client.post(
        DOCUMENTS,
        content=RECEIPT.read_bytes(),
        headers={
            **bearer(ALICE),
            "Content-Type": "image/png",
            "X-Extraction-Consent": consent,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["connection_id"]


def _review(identities, receipt_id):
    service = documents_service()
    user = identities[ALICE]["id"]
    draft = service.get(user_id=user, connection_id=receipt_id)
    batch = service.store.get(user_id=user, connection_id=receipt_id)
    events = service.hub.sink.list(
        user_id=user, states=("open", "accepting", "accepted", "dismissed")
    )
    return receipt_review(draft, batch, events)


def test_line_items_make_one_purchase_at_the_receipt_total(
    client, monkeypatch, identities
):
    _extract(monkeypatch, [PURCHASE])
    receipt_id = _upload(client)
    user = identities[ALICE]["id"]
    batch = documents_service().store.get(user_id=user, connection_id=receipt_id)
    assert [str(c.amount) for c in batch.candidates] == ["1180"]
    assert [item.total for item in batch.receipt.items] == ["300.00", "700.00"]
    assert len(client.get(IMPORTS, headers=bearer(ALICE)).json()["items"]) == 1


def test_line_items_reported_as_purchases_yield_no_purchase(
    client, monkeypatch, identities
):
    rows = [
        {**PURCHASE, "row": 1, "amount": "300.00"},
        {**PURCHASE, "row": 2, "amount": "700.00"},
        {**PURCHASE, "row": 3, "amount": "1180.00"},
    ]
    _extract(monkeypatch, rows)
    receipt_id = _upload(client)
    user = identities[ALICE]["id"]
    batch = documents_service().store.get(user_id=user, connection_id=receipt_id)
    assert batch.candidates == ()
    assert [issue.code for issue in batch.issues] == ["receipt_purchase_ambiguous"]
    assert client.get(IMPORTS, headers=bearer(ALICE)).json()["items"] == []
    review = _review(identities, receipt_id)
    assert (review.status, review.error_code, review.blocker) == (
        "needs_attention",
        "receipt_purchase_ambiguous",
        "no_purchase_found",
    )
    assert review.fields is None
    assert review.evidence["receipt"]["total"] == "1180.00"


def test_saved_without_consent_is_not_prepared(client, monkeypatch, identities):
    _extract(monkeypatch, [PURCHASE])
    receipt_id = _upload(client, consent="false")
    review = _review(identities, receipt_id)
    assert (review.status, review.blocker, review.evidence, review.fields) == (
        "saved",
        "not_prepared",
        None,
        None,
    )


def test_review_corrects_and_confirms_without_rewriting_evidence(
    client, monkeypatch, identities
):
    _extract(monkeypatch, [PURCHASE])
    receipt_id = _upload(client)

    review = _review(identities, receipt_id)
    assert review.status == "review_ready"
    assert review.fields == ReceiptFields(
        merchant="Ferreteria Ochoa",
        occurred_on="2026-10-03",
        amount="1180",
        currency="DOP",
        category_id=None,
        account_id=None,
    )
    assert review.missing == ("account_id",)
    assert review.expense_id is None

    account = client.post(
        "/api/v1/financial-accounts",
        json={"type": "checking", "currency": "DOP", "nickname": "Caja"},
        headers={**bearer(ALICE), "Idempotency-Key": str(uuid4())},
    ).json()
    resolved = client.patch(
        f"{IMPORTS}/{review.event_id}",
        headers=bearer(ALICE),
        json={
            "version": review.event_version,
            "changes": {
                "account_id": account["id"],
                "note": "Ochoa Hardware",
                "amount": "1100.00",
            },
        },
    )
    assert resolved.status_code == 200, resolved.text
    corrected = _review(identities, receipt_id)
    assert (corrected.fields.merchant, corrected.fields.amount) == (
        "Ochoa Hardware",
        "1100",
    )
    assert corrected.missing == ()
    assert corrected.evidence == review.evidence
    assert corrected.evidence["receipt"]["merchant"] == "Ferreteria Ochoa"
    assert corrected.evidence["receipt"]["total"] == "1180.00"

    preview = client.post(
        f"{IMPORTS}/{review.event_id}/preview", json={}, headers=bearer(ALICE)
    ).json()["preview"]
    accepted = client.post(
        f"{IMPORTS}/{review.event_id}/accept",
        json={
            "version": corrected.event_version,
            "request": {
                **preview["reviewed_request"],
                "preview_token": preview["preview_token"],
            },
        },
        headers={**bearer(ALICE), "Idempotency-Key": str(uuid4())},
    )
    assert accepted.status_code == 200, accepted.text
    activity = accepted.json()["activity"]
    assert (activity["note"], activity["amount"]) == ("Ochoa Hardware", "1100.00")

    confirmed = _review(identities, receipt_id)
    assert (confirmed.status, confirmed.expense_id) == (
        "confirmed",
        activity["activity_id"],
    )

    store = documents_service().hub.sink.store
    with store.transaction(identities[ALICE]["id"]) as tx:
        assert receipt_ids(tx, [activity["activity_id"], str(uuid4())]) == {
            activity["activity_id"]: receipt_id
        }


def test_activity_recorded_by_hand_has_no_receipt(client, identities):
    store = documents_service().hub.sink.store
    with store.transaction(identities[ALICE]["id"]) as tx:
        assert receipt_ids(tx, [str(uuid4())]) == {}


@pytest.fixture(autouse=True)
def _surface(client):
    assert documents_service() is not None
