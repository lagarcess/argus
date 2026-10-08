"""A WhatsApp receipt joins the Business inbox and the same review and confirm path."""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import patch

import pytest
from argus.api import state as api_state
from argus.api.documents import documents_service
from argus.api.main import app
from argus.api.whatsapp import (
    build_whatsapp,
    configure_whatsapp,
    resolve_intake_destination,
    whatsapp_runtime,
)
from argus.domain.business.scope import BusinessScope, resolve_business_scope
from argus.domain.ingestion.whatsapp.store import InMemoryWhatsAppStore
from fastapi.testclient import TestClient

from tests.business.conftest import ALICE, BOB
from tests.business.receipt_stub import ReceiptStub
from tests.business.test_business_api import Owner
from tests.ingestion.test_whatsapp_api import link_alice, post
from tests.ingestion.whatsapp_cases import FORWARDED
from tests.ingestion.whatsapp_support import (
    DOCUMENT_FIXTURES,
    ENV,
    RECEIPT_PNG,
    FakeGraph,
    Media,
    fixture,
)


@pytest.fixture
def wa_biz(
    business_env, gateway, monkeypatch
) -> Iterator[tuple[TestClient, ReceiptStub]]:  # noqa: ANN001
    for name, value in ENV.items():
        monkeypatch.setenv(name, value)
    graph = FakeGraph({"700000000000001": Media(RECEIPT_PNG, "image/png")})
    with (
        patch.object(api_state, "supabase_gateway", gateway),
        patch("argus.api.dependencies.auth_session_is_active", return_value=True),
        TestClient(app) as test_client,
    ):
        runtime = whatsapp_runtime()
        assert runtime is not None
        configure_whatsapp(
            build_whatsapp(
                runtime.settings,
                documents=documents_service(),
                store=InMemoryWhatsAppStore(),
                client=graph.client(),
                app_origin="https://app.test",
            )
        )
        stub = ReceiptStub()
        monkeypatch.setattr(documents_service(), "extractor", stub)
        test_client.graph = graph
        yield test_client, stub


def test_scope_is_the_person_until_the_boundary_is_approved() -> None:
    assert resolve_business_scope("person-1") == BusinessScope("person-1", None)
    assert resolve_intake_destination("person-1") == "person-1"


def test_whatsapp_receipt_is_reviewed_and_confirmed_like_an_upload(wa_biz) -> None:  # noqa: ANN001
    client, stub = wa_biz
    alice, bob = Owner(client, ALICE), Owner(client, BOB)
    link_alice(client)
    assert post(client, fixture("image_message.json")).status_code == 200
    [captured] = alice.get("/receipts", view="inbox").json()["items"]
    assert (captured["channel"], captured["status"], captured["size_bytes"]) == (
        "whatsapp",
        "saved",
        len(RECEIPT_PNG),
    )
    assert stub.calls == []
    receipt_id = captured["id"]
    assert post(client, fixture("image_message.json")).status_code == 200
    assert [r["id"] for r in alice.get("/receipts", view="all").json()["items"]] == [
        receipt_id
    ]
    prepared = alice.post(
        f"/receipts/{receipt_id}/prepare", **{"X-Extraction-Consent": "true"}
    )
    assert prepared.status_code == 200, prepared.text
    detail = alice.detail(receipt_id)
    assert (detail["channel"], detail["status"]) == ("whatsapp", "review_ready")
    account = alice.account()
    version = alice.review(receipt_id, detail["version"], account_id=account).json()[
        "version"
    ]
    first = alice.confirm(receipt_id, version, "wa-confirm").json()
    second = alice.confirm(receipt_id, version, "wa-confirm").json()
    assert first["status"] == second["status"] == "confirmed"
    assert first["expense_id"] == second["expense_id"]
    window = {"from": "2026-10-01", "to": "2026-10-31"}
    assert [
        (e["id"], e["receipt_id"])
        for e in alice.get("/expenses", **window).json()["items"]
    ] == [(first["expense_id"], receipt_id)]
    assert bob.get(f"/receipts/{receipt_id}").status_code == 404


def test_forwards_and_captions_reach_the_inbox_like_a_direct_send(wa_biz) -> None:  # noqa: ANN001
    client, stub = wa_biz
    alice = Owner(client, ALICE)
    link_alice(client)
    for name, source, media_type, _filename in FORWARDED:
        body = fixture(name)
        message = body["entry"][0]["changes"][0]["value"]["messages"][0]
        client.graph.media[message[message["type"]]["id"]] = Media(
            (DOCUMENT_FIXTURES / source).read_bytes(), media_type
        )
        assert post(client, body).status_code == 200
    inbox = alice.get("/receipts", view="inbox").json()["items"]
    assert sorted((r["channel"], r["status"], r["media_type"]) for r in inbox) == [
        ("whatsapp", "saved", "application/pdf"),
        ("whatsapp", "saved", "image/jpeg"),
        ("whatsapp", "saved", "image/jpeg"),
        ("whatsapp", "saved", "image/png"),
    ]
    assert stub.calls == []
