"""Document extraction wiring and registered-owner admission."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Request

from argus.api import state as api_state
from argus.api.dependencies import problem
from argus.api.ingestion import (
    IngestionContext,
    require_ingestion_context,
    require_ingestion_surface,
    unavailable_problem,
)
from argus.api.rate_limits import SlidingWindowLimiter
from argus.domain.ingestion.documents.config import DocumentExtractionSettings
from argus.domain.ingestion.documents.extractor import DocumentExtractor
from argus.domain.ingestion.documents.service import DocumentsService
from argus.domain.ingestion.documents.store import InMemoryDocumentStore
from argus.domain.ingestion.hub import IngestionHub

_service: DocumentsService | None = None
_minute = SlidingWindowLimiter()
_day = SlidingWindowLimiter()


def documents_service() -> DocumentsService | None:
    return _service


def configure_documents(service: DocumentsService | None) -> None:
    global _service
    _service = service
    _minute.reset()
    _day.reset()


def start_documents(app: object, hub: IngestionHub | None) -> None:
    if hub is None:
        configure_documents(None)
        return
    pool = getattr(getattr(app, "state", None), "financial_accounts_pool", None)
    if api_state.PERSISTENCE_MODE == "supabase":
        if pool is None:
            configure_documents(None)
            return
        from argus.domain.ingestion.documents.store_postgres import PostgresDocumentStore

        store = PostgresDocumentStore(pool)
    else:
        store = InMemoryDocumentStore(hub.connections)
    # Register cleanup even when extraction is off, so disconnect still erases it.
    service = DocumentsService(hub, store, DocumentExtractor())
    configure_documents(service)


def require_document_surface(
    request: Request,
    hub: IngestionHub = Depends(require_ingestion_surface),  # noqa: B008
) -> DocumentsService:
    service = documents_service()
    if (
        not DocumentExtractionSettings().enabled
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
                headers={"Retry-After": str(retry)},
            )
    return DocumentContext(service, context.user_id)
