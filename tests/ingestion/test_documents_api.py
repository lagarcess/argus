"""Upload through reviewed acceptance, with real preparation and a scripted provider response."""

from pathlib import Path
from uuid import uuid4

import pytest
from argus.api.documents import documents_service

from tests.ingestion.conftest import ALICE, BOB, GUEST, bearer

DOCUMENTS = "/api/v1/financial-documents"
IMPORTS = "/api/v1/financial-imports"


@pytest.fixture
def extraction(client, monkeypatch):
    from unittest.mock import AsyncMock

    from argus.domain.ingestion.documents import extractor as provider
    from argus.domain.ingestion.documents.config import DocumentExtractionSettings
    from argus.domain.ingestion.documents.models import ExtractionResult

    monkeypatch.setenv("ARGUS_DOCUMENT_EXTRACTION_ENABLED", "true")
    monkeypatch.setenv("ARGUS_VISION_MODEL", "test/vision")
    monkeypatch.setenv("OPENROUTER_API_KEY", "offline-test-key")
    result = ExtractionResult.model_validate(
        {
            "complete": True,
            "readable": True,
            "pages_read": [1],
            "observations": [
                {
                    "page": 1,
                    "row": 1,
                    "evidence": "transaction",
                    "status": "posted",
                    "amount": "250.50",
                    "currency": "DOP",
                    "occurred_on": "2026-09-10",
                    "direction": "outflow",
                    "kind_hint": "expense",
                    "account": {"name": "Cuenta de prueba", "currency": "DOP"},
                }
            ],
        }
    )
    invoke = AsyncMock(return_value=result)
    monkeypatch.setattr(provider, "invoke_openrouter_json_schema", invoke)
    monkeypatch.setattr(
        documents_service(),
        "extractor",
        provider.DocumentExtractor(
            DocumentExtractionSettings(enabled=True),
        ),
    )
    return invoke


def upload(client, token=ALICE, **headers):
    return client.post(
        DOCUMENTS,
        content=(
            Path(__file__).parents[1] / "document_extraction_fixtures/receipt-dop.png"
        ).read_bytes(),
        headers={
            **bearer(token),
            "Content-Type": "image/png",
            "X-Extraction-Consent": "true",
            **headers,
        },
    )


def test_upload_review_accept_and_duplicate_remain_one_activity(client, extraction):
    account = client.post(
        "/api/v1/financial-accounts",
        json={"type": "checking", "currency": "DOP", "nickname": "Personal"},
        headers={**bearer(ALICE), "Idempotency-Key": str(uuid4())},
    ).json()
    result = upload(client)
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "queued"
    prepared = client.get(
        f"{DOCUMENTS}/{result.json()['connection_id']}", headers=bearer(ALICE)
    ).json()
    assert len(prepared["preparation"]["candidates"]) == 1
    duplicate = upload(client)
    assert duplicate.json()["replayed"] is True
    assert duplicate.json()["connection_id"] == result.json()["connection_id"]
    assert extraction.await_count == 1
    current = client.get(
        f"/api/v1/financial-accounts/{account['id']}", headers=bearer(ALICE)
    ).json()
    assert current["version"] == account["version"]
    [event] = client.get(IMPORTS, headers=bearer(ALICE)).json()["items"]
    resolved = client.patch(
        f"{IMPORTS}/{event['id']}",
        headers=bearer(ALICE),
        json={
            "version": event["version"],
            "changes": {"account_id": account["id"]},
        },
    ).json()
    preview = client.post(
        f"{IMPORTS}/{event['id']}/preview", json={}, headers=bearer(ALICE)
    ).json()["preview"]
    assert preview["ready"] is True
    body = {
        "version": resolved["version"],
        "request": {
            **preview["reviewed_request"],
            "preview_token": preview["preview_token"],
        },
    }
    headers = {**bearer(ALICE), "Idempotency-Key": str(uuid4())}
    accepted = client.post(f"{IMPORTS}/{event['id']}/accept", json=body, headers=headers)
    assert accepted.status_code == 200, accepted.text
    activity = accepted.json()["activity"]
    assert activity["amount"] == "250.50"
    assert activity["currency"] == "DOP"
    replay = client.post(f"{IMPORTS}/{event['id']}/accept", json=body, headers=headers)
    assert replay.json()["activity"]["activity_id"] == activity["activity_id"]
    assert replay.json()["replayed"] is True
    assert client.get(IMPORTS, headers=bearer(ALICE)).json()["items"] == []


def test_uploads_and_resume_are_owner_scoped(client, extraction):
    first = upload(client).json()
    assert client.get(IMPORTS, headers=bearer(BOB)).json()["items"] == []
    other = client.post(
        f"{DOCUMENTS}/{first['connection_id']}/resume", headers=bearer(BOB)
    )
    assert other.status_code == 404
    second = upload(client, BOB)
    assert second.status_code == 200, second.text
    assert second.json()["connection_id"] != first["connection_id"]
    assert upload(client, GUEST).status_code == 403
    assert extraction.await_count == 2


def test_upload_without_consent_saves_and_rejects_bad_media_before_extraction(
    client, extraction
):
    assert upload(client, **{"X-Extraction-Consent": "false"}).json()["status"] == "saved"
    assert upload(client, **{"Content-Type": "text/html"}).status_code == 415
    assert extraction.await_count == 0


def test_document_flag_hides_route_before_auth(client, monkeypatch):
    monkeypatch.setenv("ARGUS_DOCUMENT_EXTRACTION_ENABLED", "false")
    assert client.post(DOCUMENTS, content=b"x").status_code == 404


def test_upload_size_is_bounded_before_extraction(client, extraction):
    from argus.domain.ingestion.gmail.attachments import MAX_ATTACHMENT_BYTES

    response = client.post(
        DOCUMENTS,
        content=b"x" * (MAX_ATTACHMENT_BYTES + 1),
        headers={
            **bearer(ALICE),
            "Content-Type": "image/png",
            "X-Extraction-Consent": "true",
        },
    )
    assert response.status_code == 413
    assert extraction.await_count == 0


def test_source_reopen_failure_and_explicit_recovery(client, extraction):
    from argus.domain.ingestion.documents.models import DocumentExtractionError

    original = extraction.return_value
    extraction.side_effect = DocumentExtractionError("missing_vision_model")
    captured = upload(client).json()
    connection = captured["connection_id"]
    draft = client.get(f"{DOCUMENTS}/{connection}", headers=bearer(ALICE))
    assert draft.json()["status"] == "needs_attention"
    assert draft.headers["cache-control"] == "no-store"
    assert draft.json()["source_available"] is True
    source = client.get(f"{DOCUMENTS}/{connection}/source", headers=bearer(ALICE))
    assert source.status_code == 200
    assert source.headers["cache-control"] == "no-store"
    assert source.headers["x-content-type-options"] == "nosniff"
    assert (
        source.content
        == (
            Path(__file__).parents[1] / "document_extraction_fixtures/receipt-dop.png"
        ).read_bytes()
    )
    assert (
        client.get(f"{DOCUMENTS}/{connection}/source", headers=bearer(BOB)).status_code
        == 404
    )
    duplicate = upload(client).json()
    assert (
        duplicate["connection_id"] == connection
        and duplicate["status"] == "needs_attention"
    )
    assert extraction.await_count == 1
    extraction.side_effect = None
    extraction.return_value = original
    recovered = client.post(
        f"{DOCUMENTS}/{connection}/prepare",
        headers={**bearer(ALICE), "X-Extraction-Consent": "true"},
    )
    assert recovered.status_code == 200
    completed = client.get(f"{DOCUMENTS}/{connection}", headers=bearer(ALICE)).json()
    assert completed["status"] == "review_ready"
    assert completed["connection_id"] == connection
    assert "metadata" not in completed["preparation"]
    assert extraction.await_count == 2
    listing = client.get(DOCUMENTS, headers=bearer(ALICE)).json()
    assert len(listing["items"]) == 1 and "preparation" not in listing["items"][0]


def test_capture_keeps_destination_before_preparation(client, extraction):
    import json

    proposal = {
        "requested_plan": "Trip",
        "split_method": "equal",
        "participant_ids": ["one", "two"],
    }
    captured = upload(
        client,
        **{"X-Extraction-Consent": "false", "X-Document-Proposal": json.dumps(proposal)},
    ).json()
    draft = client.get(
        f"{DOCUMENTS}/{captured['connection_id']}", headers=bearer(ALICE)
    ).json()
    assert draft["status"] == "saved" and draft["preparation"] is None
    assert draft["proposal"]["requested_plan"] == proposal["requested_plan"]
    assert draft["proposal"]["participant_ids"] == proposal["participant_ids"]
    extraction.assert_not_awaited()
