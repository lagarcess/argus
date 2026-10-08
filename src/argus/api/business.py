"""Business pilot wiring: the default-off gate and each request's scope.

Default-off behind ``ARGUS_BUSINESS_PILOT_ENABLED`` and nested inside the
document surface, since every Business receipt is a document draft. The flag is
checked first, before authentication, so an off surface is a 404 to everyone.
The scope always comes from ``resolve_business_scope``, never from the client.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request

from argus.api.dependencies import problem
from argus.api.documents import (
    NO_STORE,
    DocumentContext,
    require_document_context,
    require_document_surface,
)
from argus.api.ingestion import IngestionContext, require_ingestion_context
from argus.api.whatsapp import whatsapp_runtime
from argus.domain.business.config import business_pilot_enabled
from argus.domain.business.scope import BusinessScope, resolve_business_scope
from argus.domain.business.service import BusinessService
from argus.domain.ingestion.documents.service import DocumentsService
from argus.domain.ingestion.hub import IngestionHub
from argus.domain.ingestion.reconcile.service import ReconciliationService


def unavailable_problem(request: Request) -> HTTPException:
    return problem(
        request,
        status_code=404,
        code="business_unavailable",
        title="Not Found",
        detail="Business is not available.",
        headers=NO_STORE,
    )


def require_business_surface(request: Request) -> None:
    if not business_pilot_enabled():
        raise unavailable_problem(request)


@dataclass(frozen=True)
class BusinessContext:
    scope: BusinessScope
    service: BusinessService


def _captured(person_id: str) -> frozenset[str]:
    runtime = whatsapp_runtime()
    if runtime is None:
        return frozenset()
    return runtime.intake.store.captured_connections(destination_owner_id=person_id)


def _context(
    request: Request, documents: DocumentsService, hub: IngestionHub, user_id: str
) -> BusinessContext:
    if not isinstance(hub.sink, ReconciliationService):
        raise unavailable_problem(request)
    return BusinessContext(
        resolve_business_scope(user_id),
        BusinessService(documents, hub.sink, _captured),
    )


def require_business(
    request: Request,
    _surface: None = Depends(require_business_surface),  # noqa: B008
    documents: DocumentsService = Depends(require_document_surface),  # noqa: B008
    context: IngestionContext = Depends(require_ingestion_context),  # noqa: B008
) -> BusinessContext:
    return _context(request, documents, context.hub, context.user_id)


def require_business_document_write(
    request: Request,
    _surface: None = Depends(require_business_surface),  # noqa: B008
    context: DocumentContext = Depends(require_document_context),  # noqa: B008
) -> BusinessContext:
    """Uploads and preparation share the document surface's rate limits."""

    return _context(request, context.service, context.service.hub, context.user_id)
