"""Business pilot wiring: the default-off gate and each request's scope.

Default-off behind ``ARGUS_BUSINESS_PILOT_ENABLED`` and nested inside ingestion,
since every Business receipt is a document draft and an import. Document intake
off stops only upload and preparation; what the owner saved stays readable and
their review, confirm and hand entry keep working. The flag is
checked first, before authentication, so an off surface is a 404 to everyone.
The scope always comes from ``resolve_business_scope``, never from the client.
Until the person starts their space every Business route except the space
routes answers 404 ``business_space_missing``.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request

from argus.api.business_spaces import business_spaces, space_missing_problem
from argus.api.dependencies import problem
from argus.api.documents import (
    NO_STORE,
    DocumentContext,
    require_document_context,
    require_saved_documents,
)
from argus.api.ingestion import IngestionContext, require_ingestion_context
from argus.api.whatsapp import whatsapp_runtime
from argus.domain.business.config import business_pilot_enabled
from argus.domain.business.scope import BusinessScope, resolve_business_scope
from argus.domain.business.service import BusinessService
from argus.domain.business.spaces import SpaceStore
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
class BusinessPerson:
    person_id: str
    spaces: SpaceStore


def require_business_person(
    request: Request,
    _surface: None = Depends(require_business_surface),  # noqa: B008
    documents: DocumentsService = Depends(require_saved_documents),  # noqa: B008
    context: IngestionContext = Depends(require_ingestion_context),  # noqa: B008
) -> BusinessPerson:
    """The signed-in person and the space store, for the space routes."""

    spaces = business_spaces()
    if spaces is None or documents.hub is not context.hub:
        raise unavailable_problem(request)
    return BusinessPerson(context.user_id, spaces)


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
    spaces = business_spaces()
    if (
        not isinstance(hub.sink, ReconciliationService)
        or spaces is None
        or documents.hub is not hub
    ):
        raise unavailable_problem(request)
    scope = resolve_business_scope(spaces, user_id)
    if scope is None:
        raise space_missing_problem(request)
    return BusinessContext(scope, BusinessService(documents, hub.sink, _captured))


def require_business(
    request: Request,
    _surface: None = Depends(require_business_surface),  # noqa: B008
    documents: DocumentsService = Depends(require_saved_documents),  # noqa: B008
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
