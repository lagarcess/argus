"""Replay, linking and isolation cases shared by the in-memory and Postgres runs.

Each case drives the real ``WhatsAppIntake`` with the real ``DocumentsService``
and a store; only the Graph API and the reply transport are scripted.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from itertools import count
from uuid import uuid4

import pytest
from argus.api.whatsapp import DocumentsDestination
from argus.domain.ingestion.documents.service import DocumentsService
from argus.domain.ingestion.whatsapp.identity import WhatsAppKeys
from argus.domain.ingestion.whatsapp.intake import (
    CLAIM_SECONDS,
    SERVICE_WINDOW,
    DeliveryInFlight,
    WhatsAppIntake,
)
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

    async def deliver(self, body: dict, sent_at: datetime | None = None) -> None:
        raw = encode(body, sent_at or self.clock.now)
        await self.intake.handle(parse_delivery(raw, phone_number_id=PHONE_NUMBER_ID))

    def issue(self, owner: str, language: str = "es-419"):  # noqa: ANN201
        return self.intake.issue_code(destination_owner_id=owner, reply_language=language)

    async def link(self, owner: str, phone: str, language: str = "es-419") -> None:
        issued = self.issue(owner, language)
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
        destination=DocumentsDestination(documents),
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
        "Recibimos tu recibo y lo guardamos en tu bandeja. "
        f"Revísalo y confírmalo en Cuadrao: {ORIGIN}/biz?receipt={connection_id}"
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
            "Este número no está conectado a Cuadrao. "
            "Conéctalo desde Cuadrao en la web y vuelve a enviar el recibo."
        ]
        * 2
    )


async def expired_and_reused_codes_are_refused(world: World) -> None:
    expired = world.issue(world.alice)
    world.clock.now += timedelta(minutes=11)
    await world.deliver(
        fixture(
            "text_link_code.json",
            id="wamid.CASE-EXPIRED",
            text=f"CUADRAO {expired.code}",
        )
    )
    fresh = world.issue(world.alice)
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
    first = world.issue(world.alice)
    world.issue(world.alice)
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
        "El archivo pesa más de 10 MB. Envía una foto o un PDF más pequeño."
        in world.transport.bodies()
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


async def english_owner_gets_english_only(world: World) -> None:
    await world.link(world.alice, ALICE_PHONE, "en")
    world.graph.media["700000000000115"] = Media(RECEIPT_PNG, "image/png")
    await world.deliver(image("700000000000115", "wamid.CASE-ENGLISH"))
    await world.deliver(image("700000000000115", "wamid.CASE-ENGLISH-AGAIN"))
    [connection_id] = world.captures(world.alice)
    link = f"{ORIGIN}/biz?receipt={connection_id}"
    assert world.transport.bodies() == [
        "Done. This WhatsApp is now connected to your business in Cuadrao. "
        "Send a photo or PDF of a receipt here.",
        "We got your receipt and saved it to your inbox. "
        f"Review and confirm it in Cuadrao: {link}",
        "This receipt is already in your inbox, so we didn't save it twice. "
        f"Review it in Cuadrao: {link}",
    ]


async def same_bytes_in_a_new_message_get_the_duplicate_reply(world: World) -> None:
    await world.link(world.alice, ALICE_PHONE)
    world.graph.media["700000000000116"] = Media(RECEIPT_PNG, "image/png")
    await world.deliver(image("700000000000116", "wamid.CASE-FIRST-COPY"))
    await world.deliver(image("700000000000116", "wamid.CASE-SECOND-COPY"))
    await world.deliver(image("700000000000116", "wamid.CASE-SECOND-COPY"))

    [connection_id] = world.captures(world.alice)
    link = f"{ORIGIN}/biz?receipt={connection_id}"
    for message_id in ("wamid.CASE-FIRST-COPY", "wamid.CASE-SECOND-COPY"):
        record = world.record(message_id)
        assert (record.status, record.connection_id) == ("captured", connection_id)
    assert world.transport.bodies()[1:] == [
        "Recibimos tu recibo y lo guardamos en tu bandeja. "
        f"Revísalo y confírmalo en Cuadrao: {link}",
        "Ya tenemos este recibo en tu bandeja, así que no lo guardamos dos veces. "
        f"Revísalo en Cuadrao: {link}",
    ]


async def a_live_claim_blocks_a_concurrent_redelivery(world: World) -> None:
    store, now = world.store, world.clock()
    key, sender = world.keys.message("wamid.CASE-CLAIM"), world.keys.sender(ALICE_PHONE)
    lease = timedelta(seconds=90)

    def claim(at: datetime):  # noqa: ANN202
        return store.claim(
            provider_message_key=key, sender_hash=sender, now=at, claim_until=at + lease
        )

    first = claim(now)
    assert first.claimed
    assert not claim(now + timedelta(seconds=1)).claimed
    lapsed = now + lease + timedelta(seconds=1)
    second = claim(lapsed)
    assert second.claimed
    settled = Settlement("rejected", error_code="whatsapp_sender_not_linked")
    assert not store.settle(
        provider_message_key=key,
        claim_until=first.record.claim_until,
        settlement=settled,
        now=lapsed,
    )
    assert store.inbound(key).status == "received"
    assert store.settle(
        provider_message_key=key,
        claim_until=second.record.claim_until,
        settlement=settled,
        now=lapsed,
    )
    assert not claim(lapsed + lease * 2).claimed
    assert store.inbound(key).status == "rejected"


async def redelivery_during_a_live_claim_asks_for_retry(world: World) -> None:
    await world.link(world.alice, ALICE_PHONE)
    world.graph.media["700000000000112"] = Media(RECEIPT_PNG, "image/png")
    now = world.clock()
    claimed = world.store.claim(
        provider_message_key=world.keys.message("wamid.CASE-INFLIGHT"),
        sender_hash=world.keys.sender(ALICE_PHONE),
        now=now,
        claim_until=now + timedelta(seconds=CLAIM_SECONDS),
    )
    assert claimed.claimed
    world.clock.now += timedelta(seconds=30)
    with pytest.raises(DeliveryInFlight):
        await world.deliver(image("700000000000112", "wamid.CASE-INFLIGHT"))
    assert world.captures(world.alice) == []

    world.clock.now += timedelta(seconds=CLAIM_SECONDS)
    await world.deliver(image("700000000000112", "wamid.CASE-INFLIGHT"))
    [connection_id] = world.captures(world.alice)
    assert world.record("wamid.CASE-INFLIGHT").connection_id == connection_id


async def slow_processing_times_out_as_failed_and_recovers(world: World) -> None:
    await world.link(world.alice, ALICE_PHONE)
    world.graph.media["700000000000113"] = Media(RECEIPT_PNG, "image/png")
    media = world.intake.media

    class Stalled:
        async def fetch(self, media_id: str):  # noqa: ANN202
            await asyncio.sleep(5)

    world.intake.media, world.intake.processing_seconds = Stalled(), 0.05
    with pytest.raises(asyncio.TimeoutError):
        await world.deliver(image("700000000000113", "wamid.CASE-SLOW"))
    record = world.record("wamid.CASE-SLOW")
    assert (record.status, record.error_code, record.claim_until) == (
        "failed",
        "whatsapp_processing_timeout",
        None,
    )

    world.intake.media = media
    await world.deliver(image("700000000000113", "wamid.CASE-SLOW"))
    assert world.record("wamid.CASE-SLOW").status == "captured"
    assert len(world.captures(world.alice)) == 1


async def revoking_also_ends_unused_codes(world: World) -> None:
    pending = world.issue(world.alice)
    world.store.revoke(destination_owner_id=world.alice, now=world.clock())
    await world.deliver(
        fixture(
            "text_link_code.json",
            id="wamid.CASE-AFTER-REVOKE",
            text=f"CUADRAO {pending.code}",
        )
    )
    assert (
        world.record("wamid.CASE-AFTER-REVOKE").error_code == "whatsapp_link_code_invalid"
    )
    assert world.store.destination_link(destination_owner_id=world.alice) is None


async def no_reply_outside_the_service_window(world: World) -> None:
    await world.link(world.alice, ALICE_PHONE)
    replies = len(world.transport.sent)
    world.graph.media["700000000000114"] = Media(RECEIPT_PNG, "image/png")
    await world.deliver(
        image("700000000000114", "wamid.CASE-OLD-MESSAGE"),
        sent_at=world.clock.now - SERVICE_WINDOW - timedelta(minutes=1),
    )
    assert world.record("wamid.CASE-OLD-MESSAGE").status == "captured"
    assert len(world.transport.sent) == replies
    await world.deliver(
        image("700000000000114", "wamid.CASE-RECENT"),
        sent_at=world.clock.now - SERVICE_WINDOW + timedelta(minutes=1),
    )
    assert len(world.transport.sent) == replies + 1


async def a_failed_code_answers_in_the_senders_linked_language(world: World) -> None:
    await world.link(world.alice, ALICE_PHONE, "en")
    await world.deliver(
        fixture(
            "text_link_code.json", id="wamid.CASE-BAD-LINKED", text="CUADRAO ZZZZ2222"
        )
    )
    await world.deliver(
        fixture(
            "text_link_code.json",
            id="wamid.CASE-BAD-STRANGER",
            sender=STRANGER_PHONE,
            text="CUADRAO ZZZZ2222",
        )
    )
    assert world.transport.bodies()[-2:] == [
        "That code has expired or was already used. Create a new one in Cuadrao.",
        "Ese código venció o ya se usó. Crea uno nuevo en Cuadrao.",
    ]


async def one_failing_message_does_not_stop_the_rest(world: World) -> None:
    await world.link(world.alice, ALICE_PHONE)
    world.graph.media["700000000000117"] = Media(RECEIPT_PNG, "image/png")
    world.graph.media["700000000000118"] = Media(RECEIPT_PDF, "application/pdf")
    original = world.intake.destination.capture

    attempts: list[str] = []
    failing = True

    async def fail_png(**kwargs):  # noqa: ANN003, ANN202
        attempts.append(kwargs["media_type"])
        if failing and kwargs["media_type"] == "image/png":
            raise RuntimeError("storage hiccup")
        return await original(**kwargs)

    world.intake.destination.capture = fail_png
    body = image("700000000000117", "wamid.CASE-BATCH-1")
    second = fixture(
        "document_message.json",
        id="wamid.CASE-BATCH-2",
        document={"mime_type": "application/pdf", "id": "700000000000118"},
    )
    messages = body["entry"][0]["changes"][0]["value"]["messages"]
    messages.append(second["entry"][0]["changes"][0]["value"]["messages"][0])

    with pytest.raises(RuntimeError, match="storage hiccup"):
        await world.deliver(body)
    assert world.record("wamid.CASE-BATCH-1").status == "failed"
    assert world.record("wamid.CASE-BATCH-2").status == "captured"
    assert len(world.captures(world.alice)) == 1

    failing = False
    await world.deliver(body)
    await world.deliver(body)
    assert attempts == ["image/png", "application/pdf", "image/png"]
    assert world.record("wamid.CASE-BATCH-1").status == "captured"
    assert len(world.captures(world.alice)) == 2


async def media_urls_off_the_meta_allowlist_are_never_fetched(world: World) -> None:
    await world.link(world.alice, ALICE_PHONE)
    untrusted = {
        "700000000000121": "http://lookaside.fbsbx.com/whatsapp_business/attachments/",
        "700000000000122": "https://attacker.example/whatsapp_business/attachments/",
        "700000000000123": "https://lookaside.fbsbx.com.attacker.example/x",
        "700000000000124": "https://lookaside.fbsbx.com:8443/whatsapp_business/",
        "700000000000125": "https://user:pw@lookaside.fbsbx.com/whatsapp_business/",
    }
    for media_id, url in untrusted.items():
        world.graph.media[media_id] = Media(RECEIPT_PNG, "image/png", url=url)
        await world.deliver(image(media_id, f"wamid.CASE-HOST-{media_id}"))
        record = world.record(f"wamid.CASE-HOST-{media_id}")
        assert (record.status, record.error_code) == (
            "failed",
            "whatsapp_media_untrusted",
        )
    assert world.graph.hosts() == {"graph.facebook.com"}
    assert world.captures(world.alice) == []


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
    redelivery_during_a_live_claim_asks_for_retry,
    slow_processing_times_out_as_failed_and_recovers,
    revoking_also_ends_unused_codes,
    no_reply_outside_the_service_window,
    same_bytes_in_a_new_message_get_the_duplicate_reply,
    a_failed_code_answers_in_the_senders_linked_language,
    one_failing_message_does_not_stop_the_rest,
    media_urls_off_the_meta_allowlist_are_never_fetched,
)
