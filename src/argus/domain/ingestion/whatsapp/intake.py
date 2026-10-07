"""One signed delivery in, one durable record per message, at most one capture.

The destination for a capture is read only from the active sender link that
matches the HMAC of the signed ``from`` field. Message text, filenames and
captions never choose an owner, and a phone number typed in text proves
nothing. Captures are saved with ``consent=False``: AI preparation waits for
the owner's choice in the web app.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from loguru import logger

from argus.domain.ingestion.whatsapp.identity import (
    WhatsAppKeys,
    last4,
    link_code_in,
    looks_like_link_attempt,
    mint_code,
    ref,
)
from argus.domain.ingestion.whatsapp.media import (
    ACCEPTED_MEDIA_TYPES,
    FetchedMedia,
    MediaRejected,
    MediaUnavailable,
)
from argus.domain.ingestion.whatsapp.payload import (
    Delivery,
    InboundMessage,
    MediaMessage,
    TextMessage,
)
from argus.domain.ingestion.whatsapp.replies import (
    ReplyFailed,
    ReplyTransport,
    compose_reply,
    reply_key,
    reply_payload,
    review_url,
)
from argus.domain.ingestion.whatsapp.store import Settlement, WhatsAppStore

CLAIM_SECONDS = 90
CODE_TTL = timedelta(minutes=10)


class CaptureRejected(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class CaptureFailed(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class IntakeDestination(Protocol):
    """Where a linked sender's receipt lands. Pending the Business boundary."""

    async def capture(
        self, *, owner_id: str, content: bytes, filename: str, media_type: str
    ) -> str: ...

    def language(self, owner_id: str) -> str | None: ...


class MediaSource(Protocol):
    async def fetch(self, media_id: str) -> FetchedMedia: ...


@dataclass(frozen=True)
class IssuedCode:
    code: str
    expires_at: datetime


class WhatsAppIntake:
    def __init__(
        self,
        *,
        store: WhatsAppStore,
        keys: WhatsAppKeys,
        media: MediaSource,
        destination: IntakeDestination,
        clock: Callable[[], datetime],
        transport: ReplyTransport | None = None,
        app_origin: str | None = None,
        max_bytes: int,
    ) -> None:
        self.store, self.keys, self.media = store, keys, media
        self.destination, self.clock = destination, clock
        self.transport, self.app_origin, self.max_bytes = transport, app_origin, max_bytes

    def issue_code(self, *, destination_owner_id: str) -> IssuedCode:
        """A new single-use code; any earlier unused code for this owner stops working."""

        code = mint_code()
        now = self.clock()
        expires_at = now + CODE_TTL
        self.store.issue_code(
            destination_owner_id=destination_owner_id,
            code_digest=self.keys.code(code),
            now=now,
            expires_at=expires_at,
        )
        return IssuedCode(code, expires_at)

    async def handle(self, delivery: Delivery) -> None:
        logger.info(
            "WhatsApp delivery verified",
            messages=len(delivery.messages),
            ignored_messages=delivery.ignored_messages,
            statuses=delivery.statuses,
            other_numbers=delivery.other_numbers,
        )
        for message in delivery.messages:
            await self._one(message)

    async def _one(self, message: InboundMessage) -> None:
        sender = self.keys.sender(message.sender)
        key = self.keys.message(message.id)
        now = self.clock()
        claim = await asyncio.to_thread(
            self.store.claim,
            provider_message_key=key,
            sender_hash=sender,
            now=now,
            claim_until=now + timedelta(seconds=CLAIM_SECONDS),
        )
        log = logger.bind(message_ref=ref(key), sender_ref=ref(sender))
        if not claim.claimed:
            log.info("WhatsApp message replayed", status=claim.record.status)
            return
        try:
            settlement = await self._decide(message, sender)
        except Exception as error:
            await self._settle(
                key, Settlement("failed", error_code="whatsapp_processing_failed")
            )
            log.warning("WhatsApp message failed", failure_mode=type(error).__name__)
            raise
        await self._settle(key, settlement)
        log.info(
            "WhatsApp message settled",
            status=settlement.status,
            error_code=settlement.error_code,
        )
        await self._reply(message, settlement, log)

    async def _settle(self, key: bytes, settlement: Settlement) -> None:
        await asyncio.to_thread(
            self.store.settle,
            provider_message_key=key,
            settlement=settlement,
            now=self.clock(),
        )

    async def _decide(self, message: InboundMessage, sender: bytes) -> Settlement:
        if isinstance(message, TextMessage) and looks_like_link_attempt(message.body):
            code = link_code_in(message.body)
            owner = None
            if code is not None:
                owner = await asyncio.to_thread(
                    self.store.redeem_code,
                    code_digest=self.keys.code(code),
                    sender_hash=sender,
                    last4=last4(message.sender),
                    now=self.clock(),
                )
            if owner is None:
                return Settlement("rejected", error_code="whatsapp_link_code_invalid")
            return Settlement("linked", destination_owner_id=owner)
        link = await asyncio.to_thread(self.store.sender_link, sender_hash=sender)
        if link is None:
            return Settlement("rejected", error_code="whatsapp_sender_not_linked")
        owner = link.destination_owner_id
        if isinstance(message, TextMessage):
            return Settlement("rejected", owner, error_code="whatsapp_receipt_missing")
        return await self._capture(message, owner)

    async def _capture(self, message: MediaMessage, owner: str) -> Settlement:
        if message.mime_type not in ACCEPTED_MEDIA_TYPES:
            return Settlement("rejected", owner, error_code="whatsapp_media_unsupported")
        try:
            fetched = await self.media.fetch(message.media_id)
            connection_id = await self.destination.capture(
                owner_id=owner,
                content=fetched.content,
                filename=message.filename,
                media_type=fetched.mime_type,
            )
        except (MediaRejected, CaptureRejected) as error:
            return Settlement("rejected", owner, error_code=error.code)
        except (MediaUnavailable, CaptureFailed) as error:
            return Settlement("failed", owner, error_code=error.code)
        return Settlement("captured", owner, connection_id)

    async def _reply(self, message: InboundMessage, settlement: Settlement, log) -> None:  # noqa: ANN001
        if self.transport is None:
            return
        url = None
        if settlement.status == "captured":
            if not self.app_origin:
                log.warning("WhatsApp acknowledgement skipped: no app origin")
                return
            url = review_url(self.app_origin, settlement.connection_id or "")
        owner = settlement.destination_owner_id
        language = (
            await asyncio.to_thread(self.destination.language, owner) if owner else None
        )
        body = compose_reply(
            reply_key(settlement.status, settlement.error_code),
            language=language,
            review_url=url,
            limit_mb=self.max_bytes // (1024 * 1024),
        )
        try:
            await self.transport.send(
                reply_payload(to=message.sender, in_reply_to=message.id, body=body)
            )
        except ReplyFailed as error:
            log.warning("WhatsApp acknowledgement not sent", failure_mode=str(error))
