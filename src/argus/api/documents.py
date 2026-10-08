"""Document extraction wiring and registered-owner admission."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from urllib.parse import unquote

from fastapi import BackgroundTasks, Depends, HTTPException, Request
from loguru import logger

from argus.api import state as api_state
from argus.api.dependencies import problem
from argus.api.document_jobs import (
    document_jobs,
    start_document_jobs,
    stop_document_jobs,
)
from argus.api.ingestion import (
    IngestionContext,
    require_ingestion_context,
    require_ingestion_surface,
    unavailable_problem,
)
from argus.api.rate_limits import SlidingWindowLimiter
from argus.domain.ingestion.connections import ConnectionNotFound
from argus.domain.ingestion.documents.config import (
    SOURCE_MEDIA_TYPES,
    load_document_extraction_settings,
    load_document_job_settings,
)
from argus.domain.ingestion.documents.extractor import DocumentExtractor
from argus.domain.ingestion.documents.models import DocumentExtractionError
from argus.domain.ingestion.documents.service import (
    DocumentServiceError,
    DocumentsService,
)
from argus.domain.ingestion.documents.store import InMemoryDocumentStore
from argus.domain.ingestion.hub import IngestionHub
from argus.domain.owner_scope import OwnerScope

NO_STORE = {"Cache-Control": "no-store"}
_service: DocumentsService | None = None
_minute = SlidingWindowLimiter()
_day = SlidingWindowLimiter()


def documents_service() -> DocumentsService | None:
    return _service


def configure_documents(service: DocumentsService | None) -> None:
    global _service
    stop_document_jobs()
    _service = service
    _minute.reset()
    _day.reset()


def start_documents(app: object, hub: IngestionHub | None) -> None:
    if hub is None:
        configure_documents(None)
        return
    try:
        _start_documents(app, hub)
    except Exception as exc:
        logger.warning(
            "Document surface failed to start; other connectors stay available",
            failure_mode=type(exc).__name__,
        )
        configure_documents(None)


def _start_documents(app: object, hub: IngestionHub) -> None:
    pool = getattr(getattr(app, "state", None), "financial_accounts_pool", None)
    if api_state.PERSISTENCE_MODE == "supabase":
        gateway = api_state.supabase_gateway
        if pool is None or gateway is None:
            configure_documents(None)
            return
        from argus.domain.ingestion.documents.objects import SupabaseSourceObjects
        from argus.domain.ingestion.documents.store_postgres import PostgresDocumentStore

        store = PostgresDocumentStore(pool, SupabaseSourceObjects(gateway.client.storage))
    else:
        store = InMemoryDocumentStore(hub.connections)
    # Register cleanup even when extraction is off, so disconnect still erases it.
    jobs = load_document_job_settings()
    service = DocumentsService(
        hub, store, DocumentExtractor(), jobs_recover_interruptions=jobs.enabled
    )
    configure_documents(service)
    if jobs.enabled:
        start_document_jobs(service, jobs)


def require_document_surface(
    request: Request,
    hub: IngestionHub = Depends(require_ingestion_surface),  # noqa: B008
) -> DocumentsService:
    service = documents_service()
    if (
        not load_document_extraction_settings().enabled
        or service is None
        or service.hub is not hub
    ):
        raise unavailable_problem(request)
    return service


@dataclass(frozen=True)
class DocumentContext:
    service: DocumentsService
    user_id: str


def require_document_context(
    request: Request,
    service: DocumentsService = Depends(require_document_surface),  # noqa: B008
    context: IngestionContext = Depends(require_ingestion_context),  # noqa: B008
) -> DocumentContext:
    limits = ((_minute, 5, 60), (_day, 30, 86400)) if request.method == "POST" else ()
    for limiter, limit, seconds in limits:
        retry = limiter.record_or_retry_after(
            keys=(context.user_id,), limit=limit, window_seconds=seconds
        )
        if retry is not None:
            raise problem(
                request,
                status_code=429,
                code="document_rate_limited",
                title="Too Many Requests",
                detail="Wait before uploading another document.",
                headers={"Retry-After": str(retry), "Cache-Control": "no-store"},
            )
    return DocumentContext(service, context.user_id)


async def read_document_upload(request: Request) -> tuple[str, bytes]:
    """The media type and bounded raw bytes of an upload request body."""

    media_type = request.headers.get("content-type", "").split(";", 1)[0].strip()
    if media_type not in SOURCE_MEDIA_TYPES:
        raise problem(
            request,
            status_code=415,
            code="document_media_type_unsupported",
            title="Unsupported document",
            detail="Upload a PDF, JPEG or PNG file.",
            headers=NO_STORE,
        )
    limit = load_document_extraction_settings().max_bytes
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > limit:
            raise problem(
                request,
                status_code=413,
                code="document_too_large",
                title="Document too large",
                detail=f"Upload a document of at most {limit / 1048576:g} MiB.",
                headers=NO_STORE,
            )
        content.extend(chunk)
    return media_type, bytes(content)


def document_filename(header: str | None) -> str:
    """``X-Document-Filename`` is percent-encoded UTF-8 (``encodeURIComponent``),
    which is pure ASCII. Anything else is raw UTF-8, read by the server as
    latin-1: it is recovered and never percent-decoded, and bytes that are not
    UTF-8 become replacement characters rather than mojibake."""

    if not header:
        return "document"
    if header.isascii():
        return unquote(header, errors="replace")
    return header.encode("latin-1").decode("utf-8", errors="replace")


async def dispatch_preparation(
    service: DocumentsService,
    user_id: str,
    connection_id: str,
    background_tasks: BackgroundTasks,
    *,
    scope: OwnerScope,
) -> None:
    """A durable attempt when preparation jobs are on, else a background task.

    A job reads its scope from the connection; the background task is told it.
    """

    jobs = document_jobs()
    if jobs is None:
        background_tasks.add_task(
            service.background_prepare,
            user_id=user_id,
            connection_id=connection_id,
            scope=scope,
        )
        return
    # Recorded before the response, so a closed client cannot lose the intake.
    await asyncio.to_thread(jobs.start, user_id=user_id, connection_id=connection_id)


def document_problem(request: Request, error: Exception) -> HTTPException:
    if isinstance(error, ConnectionNotFound):
        return problem(
            request,
            status_code=404,
            code="financial_document_not_found",
            title="Not Found",
            detail="No such document.",
            headers=NO_STORE,
        )
    if isinstance(error, (DocumentServiceError, DocumentExtractionError)):
        unavailable = error.retryable or error.code in {
            "missing_vision_model",
            "missing_api_key",
            "document_tools_unavailable",
        }
        status = 503 if unavailable else 422
        if error.code in {
            "document_busy",
            "document_version_conflict",
            "document_entered_by_owner",
            "document_already_prepared",
        }:
            status = 409
        if error.code == "document_disconnected":
            status = 410
        return problem(
            request,
            status_code=status,
            code=error.code,
            title="Document unavailable" if unavailable else "Document needs attention",
            detail="The document could not be prepared for review. Retry or upload a clearer copy.",
            headers=NO_STORE,
        )
    return problem(
        request,
        status_code=503,
        code="document_extraction_unavailable",
        title="Document unavailable",
        detail="Document extraction is temporarily unavailable.",
        headers=NO_STORE,
    )
