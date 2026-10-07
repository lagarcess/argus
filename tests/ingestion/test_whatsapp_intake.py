"""WhatsApp intake against in-memory stores; the same cases run on Postgres too."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from argus.domain.ingestion.connections import InMemoryConnectionRepository
from argus.domain.ingestion.documents.service import DocumentsService
from argus.domain.ingestion.documents.store import InMemoryDocumentStore
from argus.domain.ingestion.hub import IngestionHub
from argus.domain.ingestion.whatsapp.identity import link_code_in, signature_matches
from argus.domain.ingestion.whatsapp.payload import (
    MediaMessage,
    PayloadInvalid,
    TextMessage,
    parse_delivery,
)
from argus.domain.ingestion.whatsapp.replies import (
    REPLIES,
    compose_reply,
    reply_key,
    reply_payload,
)
from argus.domain.ingestion.whatsapp.store import InMemoryWhatsAppStore

from tests.ingestion import whatsapp_cases as cases
from tests.ingestion.whatsapp_support import (
    FIXTURES,
    PHONE_NUMBER_ID,
    RefusingExtractor,
    encode,
    fixture,
    sign,
)


def _world(language_of=lambda _owner: None) -> cases.World:  # noqa: ANN001
    clock = cases.Clock()
    connections = InMemoryConnectionRepository()
    hub = IngestionHub(connections, box=None, sink=None, clock=clock)
    documents = DocumentsService(
        hub, InMemoryDocumentStore(connections), RefusingExtractor()
    )
    return cases.build_world(
        documents=documents,
        store=InMemoryWhatsAppStore(),
        clock=clock,
        alice=str(uuid4()),
        bob=str(uuid4()),
        language_of=language_of,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("case", cases.CASES, ids=lambda case: case.__name__)
async def test_intake_case(case) -> None:  # noqa: ANN001
    await case(_world())


@pytest.mark.asyncio
async def test_english_owner_gets_spanish_then_english() -> None:
    await cases.english_owner_gets_spanish_then_english(_world(lambda _owner: "en"))


def test_signature_is_hmac_of_the_raw_body() -> None:
    raw = encode(fixture("image_message.json"))
    assert signature_matches("test-app-secret", sign(raw), raw)
    assert not signature_matches("test-app-secret", sign(raw, "other"), raw)
    assert not signature_matches("test-app-secret", sign(raw), raw + b" ")
    assert not signature_matches("test-app-secret", sign(raw)[7:], raw)
    assert not signature_matches("test-app-secret", None, raw)
    assert not signature_matches("test-app-secret", "sha256=ünïcode", raw)


def test_payload_projects_handled_types_and_ignores_the_rest() -> None:
    recorded = datetime(2026, 10, 7, 11, 0, tzinfo=timezone.utc)
    image = parse_delivery(
        (FIXTURES / "image_message.json").read_bytes(), phone_number_id=PHONE_NUMBER_ID
    )
    assert image.messages == (
        MediaMessage(
            id="wamid.SYNTHETIC0001",
            sender="15550101234",
            sent_at=recorded,
            media_id="700000000000001",
            mime_type="image/png",
            filename="whatsapp-image",
        ),
    )
    text = parse_delivery(
        (FIXTURES / "text_link_code.json").read_bytes(), phone_number_id=PHONE_NUMBER_ID
    )
    assert text.messages == (
        TextMessage("wamid.SYNTHETIC0003", "15550101234", recorded, "CUADRAO ABCD2345"),
    )
    audio = parse_delivery(
        encode(fixture("audio_message.json")), phone_number_id=PHONE_NUMBER_ID
    )
    assert (audio.messages, audio.ignored_messages) == ((), 1)
    status = parse_delivery(
        encode(fixture("status_delivered.json")), phone_number_id=PHONE_NUMBER_ID
    )
    assert (status.messages, status.statuses) == ((), 1)
    other = parse_delivery(
        encode(fixture("image_message.json")), phone_number_id="100000000000002"
    )
    assert (other.messages, other.other_numbers) == ((), 1)
    with pytest.raises(PayloadInvalid):
        parse_delivery(
            b'{"object": "page", "entry": []}', phone_number_id=PHONE_NUMBER_ID
        )
    with pytest.raises(PayloadInvalid):
        parse_delivery(
            encode(fixture("image_message.json", sender="+1 555")),
            phone_number_id=PHONE_NUMBER_ID,
        )


def test_link_token_is_an_exact_protocol_word_and_code() -> None:
    assert link_code_in("CUADRAO ABCD2345") == "ABCD2345"
    assert link_code_in("  cuadrao   abcd2345 ") == "ABCD2345"
    assert link_code_in("Hola CUADRAO ABCD2345") is None
    assert link_code_in("CUADRAO ABCD2345 gracias") is None
    assert link_code_in("CUADRAO ABCD234O") is None
    assert link_code_in("CUADRAO 15550101234") is None


def test_every_outcome_code_has_a_reply_without_long_dashes() -> None:
    codes = {
        "captured",
        "linked",
        "whatsapp_link_code_invalid",
        "whatsapp_sender_not_linked",
        "whatsapp_receipt_missing",
        "whatsapp_media_unsupported",
        "whatsapp_media_too_large",
        "whatsapp_media_invalid",
        "whatsapp_media_expired",
        "whatsapp_media_unavailable",
        "whatsapp_media_untrusted",
        "whatsapp_capture_failed",
        "whatsapp_processing_failed",
    }
    for code in codes:
        status = code if code in ("captured", "linked") else "rejected"
        assert reply_key(status, None if status != "rejected" else code) in REPLIES
    assert not any(
        "—" in line or "–" in line for pair in REPLIES.values() for line in pair
    )


def test_reply_is_spanish_first_and_adds_english_only_for_english_owners() -> None:
    url = "https://app.test/biz?receipt=abc"
    assert compose_reply("captured", language="es-419", review_url=url) == (
        "Recibimos tu recibo. Revísalo en Cuadrao: https://app.test/biz?receipt=abc"
    )
    assert compose_reply("captured", language="en", review_url=url) == (
        "Recibimos tu recibo. Revísalo en Cuadrao: https://app.test/biz?receipt=abc"
        "\n\nWe received your receipt. Review it in Cuadrao: https://app.test/biz?receipt=abc"
    )
    assert reply_payload(to="15550101234", in_reply_to="wamid.X", body="Hola") == {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": "15550101234",
        "context": {"message_id": "wamid.X"},
        "type": "text",
        "text": {"preview_url": False, "body": "Hola"},
    }
