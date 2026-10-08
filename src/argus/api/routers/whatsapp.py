"""WhatsApp webhook (Meta-signed, no session) and signed-in sender linking."""

from __future__ import annotations

import hmac
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import PlainTextResponse
from loguru import logger
from pydantic import BaseModel, ConfigDict

from argus.api.dependencies import problem
from argus.api.rate_limits import SlidingWindowLimiter
from argus.api.whatsapp import (
    WhatsAppOwnerContext,
    WhatsAppRuntime,
    require_whatsapp_owner,
    require_whatsapp_surface,
)
from argus.domain.ingestion.whatsapp.identity import link_message, signature_matches
from argus.domain.ingestion.whatsapp.payload import PayloadInvalid, parse_delivery

MAX_WEBHOOK_BYTES = 512 * 1024

webhook_router = APIRouter(prefix="/webhooks/whatsapp", tags=["whatsapp"])
link_router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])
_code_limiter = SlidingWindowLimiter()


class WebhookAck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    received: bool


class LinkCodeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message_text: str
    expires_at: datetime
    wa_me_url: str | None


class LinkStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    linked: bool
    last4: str | None = None
    linked_at: datetime | None = None


@webhook_router.get("", response_class=PlainTextResponse)
def verify_whatsapp_webhook(
    request: Request,
    mode: str | None = Query(default=None, alias="hub.mode", max_length=32),
    token: str | None = Query(default=None, alias="hub.verify_token", max_length=256),
    challenge: str | None = Query(default=None, alias="hub.challenge", max_length=128),
    runtime: WhatsAppRuntime = Depends(require_whatsapp_surface),  # noqa: B008
) -> PlainTextResponse:
    expected = runtime.settings.verify_token.get_secret_value()
    if (
        mode == "subscribe"
        and token is not None
        and challenge
        and challenge.isascii()
        and challenge.isalnum()
        and hmac.compare_digest(token.encode(), expected.encode())
    ):
        return PlainTextResponse(challenge)
    raise problem(
        request,
        status_code=403,
        code="whatsapp_webhook_verification_failed",
        title="Forbidden",
        detail="Webhook verification failed.",
    )


@webhook_router.post("", response_model=WebhookAck)
async def receive_whatsapp_webhook(
    request: Request,
    runtime: WhatsAppRuntime = Depends(require_whatsapp_surface),  # noqa: B008
) -> WebhookAck:
    """Signature checked over the raw bytes before any parsing.

    200 means every message in the delivery has a committed record. A failure
    after that answers 503 so Meta redelivers; the redelivery resumes the
    same record instead of starting a second capture.
    """

    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_WEBHOOK_BYTES:
            raise problem(
                request,
                status_code=413,
                code="whatsapp_webhook_too_large",
                title="Content Too Large",
                detail="Webhook body is larger than allowed.",
            )
    settings = runtime.settings
    if not signature_matches(
        settings.app_secret.get_secret_value(),
        request.headers.get("X-Hub-Signature-256"),
        bytes(body),
    ):
        logger.warning("WhatsApp webhook signature rejected")
        raise problem(
            request,
            status_code=401,
            code="whatsapp_webhook_rejected",
            title="Unauthorized",
            detail="Webhook could not be verified.",
        )
    try:
        delivery = parse_delivery(bytes(body), phone_number_id=settings.phone_number_id)
    except PayloadInvalid:
        logger.warning("WhatsApp webhook payload invalid")
        raise problem(
            request,
            status_code=400,
            code="whatsapp_webhook_invalid",
            title="Bad Request",
            detail="Webhook payload is not a WhatsApp messages change.",
        ) from None
    try:
        await runtime.intake.handle(delivery)
    except Exception as error:
        logger.warning(
            "WhatsApp delivery not finished; Meta will redeliver",
            failure_mode=type(error).__name__,
        )
        raise problem(
            request,
            status_code=503,
            code="whatsapp_webhook_retry",
            title="Service Unavailable",
            detail="Delivery recorded but not finished. Retry.",
        ) from None
    return WebhookAck(received=True)


@link_router.post("/link-codes", response_model=LinkCodeResponse, status_code=201)
async def create_whatsapp_link_code(
    request: Request,
    context: WhatsAppOwnerContext = Depends(require_whatsapp_owner),  # noqa: B008
) -> LinkCodeResponse:
    retry = _code_limiter.record_or_retry_after(
        keys=(context.destination_owner_id,), limit=5, window_seconds=600
    )
    if retry is not None:
        raise problem(
            request,
            status_code=429,
            code="whatsapp_link_code_rate_limited",
            title="Too Many Requests",
            detail="Wait before creating another WhatsApp code.",
            headers={"Retry-After": str(retry)},
        )
    issued = await run_in_threadpool(
        context.runtime.intake.issue_code,
        destination_owner_id=context.destination_owner_id,
    )
    text = link_message(issued.code)
    number = context.runtime.settings.wa_me_number
    return LinkCodeResponse(
        code=issued.code,
        message_text=text,
        expires_at=issued.expires_at,
        wa_me_url=f"https://wa.me/{number}?text={quote(text)}" if number else None,
    )


@link_router.get("/link", response_model=LinkStatusResponse)
async def get_whatsapp_link(
    context: WhatsAppOwnerContext = Depends(require_whatsapp_owner),  # noqa: B008
) -> LinkStatusResponse:
    link = await run_in_threadpool(
        context.runtime.intake.store.destination_link,
        destination_owner_id=context.destination_owner_id,
    )
    if link is None:
        return LinkStatusResponse(linked=False)
    return LinkStatusResponse(linked=True, last4=link.last4, linked_at=link.linked_at)


@link_router.delete("/link", status_code=204)
async def revoke_whatsapp_link(
    context: WhatsAppOwnerContext = Depends(require_whatsapp_owner),  # noqa: B008
) -> Response:
    intake = context.runtime.intake
    await run_in_threadpool(
        intake.store.revoke,
        destination_owner_id=context.destination_owner_id,
        now=intake.clock(),
    )
    return Response(status_code=204)
