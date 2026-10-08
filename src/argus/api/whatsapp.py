"""WhatsApp intake wiring, exposure gate and the pending destination resolver.

Default-off behind ``ARGUS_WHATSAPP_INTAKE_ENABLED`` and nested inside the
document surface: a WhatsApp receipt is a saved document draft, so intake
cannot be on while documents are off. Every route answers 404 when off.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import httpx
from fastapi import Depends, HTTPException, Request
from loguru import logger

from argus.api import state as api_state
from argus.api.dependencies import problem
from argus.api.documents import documents_service
from argus.api.ingestion import IngestionContext, ingestion_hub, require_ingestion_context
from argus.domain.ingestion.documents.config import load_document_extraction_settings
from argus.domain.ingestion.documents.models import DocumentExtractionError
from argus.domain.ingestion.documents.service import (
    DocumentServiceError,
    DocumentsService,
)
from argus.domain.ingestion.whatsapp.config import (
    WhatsAppSettings,
    load_whatsapp_settings,
)
from argus.domain.ingestion.whatsapp.identity import WhatsAppKeys
from argus.domain.ingestion.whatsapp.intake import (
    Captured,
    CaptureFailed,
    CaptureRejected,
    WhatsAppIntake,
)
from argus.domain.ingestion.whatsapp.media import GraphMedia
from argus.domain.ingestion.whatsapp.replies import CloudApiTransport
from argus.domain.ingestion.whatsapp.store import InMemoryWhatsAppStore

WEBHOOK_PATH = "/api/v1/webhooks/whatsapp"


class _RedactWebhookQuery(logging.Filter):
    """uvicorn's access line carries the query string, and so the verify token."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if (
            isinstance(args, tuple)
            and len(args) >= 3
            and isinstance(args[2], str)
            and args[2].startswith(f"{WEBHOOK_PATH}?")
        ):
            record.args = (*args[:2], f"{WEBHOOK_PATH}?<redacted>", *args[3:])
        return True


_access_logger = logging.getLogger("uvicorn.access")
if not any(isinstance(f, _RedactWebhookQuery) for f in _access_logger.filters):
    _access_logger.addFilter(_RedactWebhookQuery())


def resolve_intake_destination(user_id: str) -> str:
    """The owner id WhatsApp receipts for this signed-in person land under.

    PENDING the Business boundary decision
    (docs/specs/lanes/cuadrao-business-boundary-proposal.md). Until it is
    approved the destination is the person. Under option A this becomes the
    business principal resolved through an active owner membership. Every
    WhatsApp route reads the destination here and nowhere else.
    """

    return user_id


_REJECTED_CAPTURE = {
    "document_too_large": "whatsapp_media_too_large",
    "unsupported_media_type": "whatsapp_media_unsupported",
}


class DocumentsDestination:
    """Saves the bytes as a document draft with ``consent=False``; never queues."""

    def __init__(self, documents: DocumentsService) -> None:
        self.documents = documents

    async def capture(
        self, *, owner_id: str, content: bytes, filename: str, media_type: str
    ) -> Captured:
        try:
            outcome = await self.documents.upload(
                user_id=owner_id,
                content=content,
                filename=filename,
                media_type=media_type,
                consent=False,
            )
        except DocumentExtractionError as error:
            raise CaptureRejected(
                _REJECTED_CAPTURE.get(error.code, "whatsapp_media_invalid")
            ) from None
        except DocumentServiceError:
            raise CaptureFailed("whatsapp_capture_failed") from None
        return Captured(outcome.connection_id, already_held=outcome.replayed)


@dataclass(frozen=True)
class WhatsAppRuntime:
    intake: WhatsAppIntake
    settings: WhatsAppSettings


_runtime: WhatsAppRuntime | None = None


def whatsapp_runtime() -> WhatsAppRuntime | None:
    return _runtime


def configure_whatsapp(runtime: WhatsAppRuntime | None) -> None:
    global _runtime
    _runtime = runtime


def build_whatsapp(
    settings: WhatsAppSettings,
    *,
    documents: DocumentsService,
    store,  # noqa: ANN001
    client: httpx.AsyncClient,
    app_origin: str | None = None,
) -> WhatsAppRuntime:
    access_token = settings.access_token.get_secret_value()
    max_bytes = load_document_extraction_settings().max_bytes
    transport = None
    if settings.outbound_enabled:
        transport = CloudApiTransport(
            client=client,
            access_token=access_token,
            phone_number_id=settings.phone_number_id,
            graph_api_version=settings.graph_api_version,
        )
    intake = WhatsAppIntake(
        store=store,
        keys=WhatsAppKeys(settings.sender_key.get_secret_value()),
        media=GraphMedia(
            client=client,
            access_token=access_token,
            graph_api_version=settings.graph_api_version,
            max_bytes=max_bytes,
        ),
        destination=DocumentsDestination(documents),
        clock=documents.hub.clock,
        transport=transport,
        app_origin=app_origin,
        max_bytes=max_bytes,
    )
    return WhatsAppRuntime(intake, settings)


def start_whatsapp(app: object) -> None:
    settings = load_whatsapp_settings()
    documents = documents_service()
    if not settings.intake_ready or documents is None:
        configure_whatsapp(None)
        return
    try:
        pool = getattr(getattr(app, "state", None), "financial_accounts_pool", None)
        if api_state.PERSISTENCE_MODE == "supabase":
            if pool is None:
                configure_whatsapp(None)
                return
            from argus.domain.ingestion.whatsapp.store_postgres import (
                PostgresWhatsAppStore,
            )

            store = PostgresWhatsAppStore(pool)
        else:
            store = InMemoryWhatsAppStore()
        configure_whatsapp(
            build_whatsapp(
                settings,
                documents=documents,
                store=store,
                client=httpx.AsyncClient(),
                app_origin=(os.getenv("ARGUS_APP_ORIGIN") or "").strip() or None,
            )
        )
    except Exception as exc:
        logger.warning(
            "WhatsApp intake failed to start; it stays off",
            failure_mode=type(exc).__name__,
        )
        configure_whatsapp(None)


def unavailable_problem(request: Request) -> HTTPException:
    return problem(
        request,
        status_code=404,
        code="whatsapp_unavailable",
        title="Not Found",
        detail="WhatsApp intake is not available.",
    )


def require_whatsapp_surface(request: Request) -> WhatsAppRuntime:
    """Flag first, before signatures or sessions, so an off surface looks absent."""

    runtime = whatsapp_runtime()
    documents = documents_service()
    if (
        runtime is None
        or not load_whatsapp_settings().intake_ready
        or not load_document_extraction_settings().enabled
        or documents is None
        or documents.hub is not ingestion_hub()
    ):
        raise unavailable_problem(request)
    return runtime


@dataclass(frozen=True)
class WhatsAppOwnerContext:
    runtime: WhatsAppRuntime
    destination_owner_id: str


def require_whatsapp_owner(
    runtime: WhatsAppRuntime = Depends(require_whatsapp_surface),  # noqa: B008
    context: IngestionContext = Depends(require_ingestion_context),  # noqa: B008
) -> WhatsAppOwnerContext:
    return WhatsAppOwnerContext(runtime, resolve_intake_destination(context.user_id))
