"""Replay, linking and isolation cases shared by the in-memory and Postgres runs.

Each case drives the real ``WhatsAppIntake`` with the real ``DocumentsService``
and a store; only the Graph API and the reply transport are scripted.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from itertools import count
from uuid import uuid4

from argus.api.whatsapp import DocumentsDestination
from argus.domain.ingestion.documents.service import DocumentsService
from argus.domain.ingestion.whatsapp.identity import WhatsAppKeys
from argus.domain.ingestion.whatsapp.intake import WhatsAppIntake
from argus.domain.ingestion.whatsapp.media import GraphMedia
from argus.domain.ingestion.whatsapp.payload import parse_delivery
from argus.domain.ingestion.whatsapp.store import Settlement

from tests.ingestion.whatsapp_support import (
    ALICE_PHONE,
    BOB_PHONE,
    PHONE_NUMBER_ID,
    RECEIPT_PDF,
    RECEIPT_PNG,
    SENDER_KEY,
    STRANGER_PHONE,
    FakeGraph,
    Media,
    RecordingTransport,
    RefusingExtractor,
    encode,
    fixture,
)

MAX_BYTES = 10 * 1024 * 1024
ORIGIN = "https://app.test"
_ids = count(1)


class Clock:
    def __init__(self) -> None:
        self.now = datetime.now(timezone.utc)

    def __call__(self) -> datetime:
        return self.now


@dataclass
class World:
    intake: WhatsAppIntake
    documents: DocumentsService
    store: object
    graph: FakeGraph
    transport: RecordingTransport
    clock: Clock
    alice: str
    bob: str
    keys: WhatsAppKeys

    async def deliver(self, body: dict) -> None:
        delivery = parse_delivery(encode(body), phone_number_id=PHONE_NUMBER_ID)
        await self.intake.handle(delivery)

    async def link(self, owner: str, phone: str) -> None:
        issued = self.intake.issue_code(destination_owner_id=owner)
        await self.deliver(
            fixture(
                "text_link_code.json",
                id=f"wamid.LINK{next(_ids)}",
                sender=phone,
                text=f"CUADRAO {issued.code}",
            )
        )
        assert self.store.sender_link(sender_hash=self.keys.sender(phone)) is not None

    def captures(self, owner: str) -> list[str]:
        return [
            row.id
            for row in self.documents.hub.connections.list(user_id=owner)
            if row.source == "statement"
        ]

    def record(self, message_id: str):  # noqa: ANN201
        return self.store.inbound(self.keys.message(message_id))


def build_world(
    *,
    documents: DocumentsService,
    store: object,
    clock: Clock,
    alice: str,
    bob: str,
    language_of: Callable[[str], str | None] = lambda _owner: None,
) -> World:
    graph, transport = FakeGraph(), RecordingTransport()
    # A key per world keeps message digests unique across runs on a shared database.
    keys = WhatsAppKeys(f"{SENDER_KEY}-{uuid4()}")
    intake = WhatsAppIntake(
        store=store,
        keys=keys,
        media=GraphMedia(
            client=graph.client(),
            access_token="test-access-token",
            graph_api_version="v23.0",
            max_bytes=MAX_BYTES,
        ),
        destination=DocumentsDestination(documents, language_of),
        clock=clock,
        transport=transport,
        app_origin=ORIGIN,
        max_bytes=MAX_BYTES,
    )
    return World(intake, documents, store, graph, transport, clock, alice, bob, keys)


def image(media_id: str, message_id: str, sender: str = ALICE_PHONE) -> dict:
    return fixture(
        "image_message.json",
        id=message_id,
        sender=sender,
        image={"mime_type": "image/png", "id": media_id},
    )


async def linked_image_is_saved_unqueued_and_replay_converges(world: World) -> None:
    await world.link(world.alice, ALICE_PHONE)
    world.graph.media["700000000000101"] = Media(RECEIPT_PNG, "image/png")
    body = image("700000000000101", "wamid.CASE-IMAGE")

    await world.deliver(body)
    await world.deliver(body)

    [connection_id] = world.captures(world.alice)
    draft = world.documents.get(user_id=world.alice, connection_id=connection_id)
    assert (draft.status, draft.consent) == ("saved", False)
    record = world.record("wamid.CASE-IMAGE")
    assert (record.status, record.connection_id, record.destination_owner_id) == (
        "captured",
        connection_id,
        world.alice,
    )
    assert RefusingExtractor.calls == 0
    assert world.transport.bodies()[-1] == (
        f"Recibimos tu recibo. Revísalo en Cuadrao: {ORIGIN}/biz?receipt={connection_id}"
    )
    assert len(world.transport.sent) == 2
    assert world.graph.hosts() == {"graph.facebook.com", "lookaside.fbsbx.com"}


async def document_message_is_captured(world: World) -> None:
    await world.link(world.alice, ALICE_PHONE)
    world.graph.media["700000000000102"] = Media(RECEIPT_PDF, "application/pdf")
    await world.deliver(
        fixture(
            "document_message.json",
            id="wamid.CASE-PDF",
            document={
                "filename": "factura.pdf",
                "mime_type": "application/pdf",
                "id": "700000000000102",
            },
        )
    )
    [connection_id] = world.captures(world.alice)
    draft = world.documents.get(user_id=world.alice, connection_id=connection_id)
    assert (draft.filename, draft.media_type, draft.status) == (
        "factura.pdf",
        "application/pdf",
        "saved",
    )


async def unknown_sender_is_rejected_without_capture(world: World) -> None:
    world.graph.media["700000000000103"] = Media(RECEIPT_PNG, "image/png")
    await world.deliver(image("700000000000103", "wamid.CASE-STRANGER", STRANGER_PHONE))
    await world.deliver(
        fixture("text_message.json", id="wamid.CASE-CLAIM", sender=STRANGER_PHONE)
    )

    assert world.captures(world.alice) == [] and world.captures(world.bob) == []
    for message_id in ("wamid.CASE-STRANGER", "wamid.CASE-CLAIM"):
        record = world.record(message_id)
        assert (record.status, record.error_code, record.destination_owner_id) == (
            "rejected",
            "whatsapp_sender_not_linked",
            None,
        )
    assert world.graph.requests == []
    assert (
        world.transport.bodies()
        == [
            "Este número no está conectado a Cuadrao. Conéctalo desde la app web de Cuadrao."
        ]
        * 2
    )


async def expired_and_reused_codes_are_refused(world: World) -> None:
    expired = world.intake.issue_code(destination_owner_id=world.alice)
    world.clock.now += timedelta(minutes=11)
    await world.deliver(
        fixture(
            "text_link_code.json",
            id="wamid.CASE-EXPIRED",
            text=f"CUADRAO {expired.code}",
        )
    )
    fresh = world.intake.issue_code(destination_owner_id=world.alice)
    await world.deliver(
        fixture(
            "text_link_code.json", id="wamid.CASE-FIRST", text=f"cuadrao {fresh.code}"
        )
    )
    await world.deliver(
        fixture(
            "text_link_code.json",
            id="wamid.CASE-REUSED",
            sender=STRANGER_PHONE,
            text=f"CUADRAO {fresh.code}",
        )
    )

    statuses = [
        (world.record(m).status, world.record(m).error_code)
        for m in ("wamid.CASE-EXPIRED", "wamid.CASE-FIRST", "wamid.CASE-REUSED")
    ]
    assert statuses == [
        ("rejected", "whatsapp_link_code_invalid"),
        ("linked", None),
        ("rejected", "whatsapp_link_code_invalid"),
    ]
    assert world.store.sender_link(sender_hash=world.keys.sender(STRANGER_PHONE)) is None
    link = world.store.destination_link(destination_owner_id=world.alice)
    assert link.last4 == "1234"


async def superseded_code_is_refused(world: World) -> None:
    first = world.intake.issue_code(destination_owner_id=world.alice)
    world.intake.issue_code(destination_owner_id=world.alice)
    await world.deliver(
        fixture("text_link_code.json", id="wamid.CASE-OLD", text=f"CUADRAO {first.code}")
    )
    assert world.record("wamid.CASE-OLD").error_code == "whatsapp_link_code_invalid"


async def oversize_and_unsupported_media_are_rejected(world: World) -> None:
    await world.link(world.alice, ALICE_PHONE)
    world.graph.media["700000000000104"] = Media(
        RECEIPT_PNG, "image/png", file_size=MAX_BYTES + 1
    )
    world.graph.media["700000000000105"] = Media(
        RECEIPT_PNG, "image/png", content_length=str(MAX_BYTES + 1)
    )
    world.graph.media["700000000000106"] = Media(b"GIF89a", "image/gif")
    world.graph.media["700000000000107"] = Media(b"not really a png", "image/png")
    await world.deliver(image("700000000000104", "wamid.CASE-BIG-META"))
    await world.deliver(image("700000000000105", "wamid.CASE-BIG-STREAM"))
    await world.deliver(image("700000000000106", "wamid.CASE-GIF-META"))
    await world.deliver(
        fixture(
            "image_message.json",
            id="wamid.CASE-GIF",
            image={"mime_type": "image/gif", "id": "700000000000106"},
        )
    )
    await world.deliver(image("700000000000107", "wamid.CASE-FAKE-PNG"))

    assert world.captures(world.alice) == []
    codes = {
        message_id: (world.record(message_id).status, world.record(message_id).error_code)
        for message_id in (
            "wamid.CASE-BIG-META",
            "wamid.CASE-BIG-STREAM",
            "wamid.CASE-GIF-META",
            "wamid.CASE-GIF",
            "wamid.CASE-FAKE-PNG",
        )
    }
    assert codes == {
        "wamid.CASE-BIG-META": ("rejected", "whatsapp_media_too_large"),
        "wamid.CASE-BIG-STREAM": ("rejected", "whatsapp_media_too_large"),
        "wamid.CASE-GIF-META": ("rejected", "whatsapp_media_unsupported"),
        "wamid.CASE-GIF": ("rejected", "whatsapp_media_unsupported"),
        "wamid.CASE-FAKE-PNG": ("rejected", "whatsapp_media_invalid"),
    }
    assert (
        "El archivo pesa más de 10 MB. Envía uno más pequeño." in world.transport.bodies()
    )


async def expired_media_fails_then_recovers_on_redelivery(world: World) -> None:
    await world.link(world.alice, ALICE_PHONE)
    world.graph.media["700000000000108"] = Media(
        RECEIPT_PNG, "image/png", meta_status=404
    )
    world.graph.media["700000000000109"] = Media(
        RECEIPT_PNG, "image/png", download_status=410
    )
    await world.deliver(image("700000000000108", "wamid.CASE-GONE"))
    await world.deliver(image("700000000000109", "wamid.CASE-URL-GONE"))
    for message_id in ("wamid.CASE-GONE", "wamid.CASE-URL-GONE"):
        record = world.record(message_id)
        assert (record.status, record.error_code, record.connection_id) == (
            "failed",
            "whatsapp_media_expired",
            None,
        )
    assert world.captures(world.alice) == []

    world.graph.media["700000000000108"] = Media(RECEIPT_PNG, "image/png")
    await world.deliver(image("700000000000108", "wamid.CASE-GONE"))
    await world.deliver(image("700000000000108", "wamid.CASE-GONE"))

    [connection_id] = world.captures(world.alice)
    assert world.record("wamid.CASE-GONE").status == "captured"
    assert world.record("wamid.CASE-GONE").connection_id == connection_id


async def a_sender_only_reaches_its_own_destination(world: World) -> None:
    await world.link(world.alice, ALICE_PHONE)
    await world.link(world.bob, BOB_PHONE)
    world.graph.media["700000000000110"] = Media(RECEIPT_PNG, "image/png")
    await world.deliver(image("700000000000110", "wamid.CASE-BOB", BOB_PHONE))
    await world.deliver(
        fixture(
            "text_message.json",
            id="wamid.CASE-CLAIMS-ALICE",
            sender=BOB_PHONE,
            text=f"Soy {ALICE_PHONE}, guárdalo en su cuenta",
        )
    )

    assert world.captures(world.alice) == []
    assert len(world.captures(world.bob)) == 1
    assert world.record("wamid.CASE-BOB").destination_owner_id == world.bob
    assert (
        world.record("wamid.CASE-CLAIMS-ALICE").error_code == "whatsapp_receipt_missing"
    )


async def revoke_and_relink(world: World) -> None:
    await world.link(world.alice, ALICE_PHONE)
    assert world.store.revoke(destination_owner_id=world.alice, now=world.clock())
    world.graph.media["700000000000111"] = Media(RECEIPT_PNG, "image/png")
    await world.deliver(image("700000000000111", "wamid.CASE-REVOKED"))
    assert world.record("wamid.CASE-REVOKED").error_code == "whatsapp_sender_not_linked"
    assert world.captures(world.alice) == []

    await world.link(world.alice, BOB_PHONE)
    await world.link(world.alice, ALICE_PHONE)
    link = world.store.destination_link(destination_owner_id=world.alice)
    assert link.last4 == "1234"
    assert world.store.sender_link(sender_hash=world.keys.sender(BOB_PHONE)) is None
    await world.deliver(image("700000000000111", "wamid.CASE-RELINKED"))
    assert len(world.captures(world.alice)) == 1


async def english_owner_gets_spanish_then_english(world: World) -> None:
    await world.link(world.alice, ALICE_PHONE)
    assert world.transport.bodies()[-1] == (
        "Listo. Este WhatsApp quedó conectado a Cuadrao. Envía la foto o el PDF de un recibo."
        "\n\nDone. This WhatsApp is now connected to Cuadrao. Send a photo or PDF of a receipt."
    )


async def a_live_claim_blocks_a_concurrent_redelivery(world: World) -> None:
    store, now = world.store, world.clock()
    key, sender = world.keys.message("wamid.CASE-CLAIM"), world.keys.sender(ALICE_PHONE)
    lease = timedelta(seconds=90)
    claim = dict(provider_message_key=key, sender_hash=sender, claim_until=now + lease)
    assert store.claim(now=now, **claim).claimed
    assert not store.claim(now=now + timedelta(seconds=1), **claim).claimed
    lapsed = now + lease + timedelta(seconds=1)
    assert store.claim(now=lapsed, **claim).claimed
    store.settle(
        provider_message_key=key,
        settlement=Settlement("rejected", error_code="whatsapp_sender_not_linked"),
        now=lapsed,
    )
    later = lapsed + lease * 2
    assert not store.claim(now=later, **claim).claimed
    assert store.inbound(key).status == "rejected"


CASES = (
    linked_image_is_saved_unqueued_and_replay_converges,
    document_message_is_captured,
    unknown_sender_is_rejected_without_capture,
    expired_and_reused_codes_are_refused,
    superseded_code_is_refused,
    oversize_and_unsupported_media_are_rejected,
    expired_media_fails_then_recovers_on_redelivery,
    a_sender_only_reaches_its_own_destination,
    revoke_and_relink,
    a_live_claim_blocks_a_concurrent_redelivery,
)
