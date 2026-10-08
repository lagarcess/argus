"""Bounded byte uploads feed the existing import review queue."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query, Request, Response
from pydantic import BaseModel, ConfigDict, ValidationError

from argus.api.documents import (
    NO_STORE,
    DocumentContext,
    dispatch_preparation,
    document_problem,
    read_document_upload,
    require_document_context,
)
from argus.domain.ingestion.documents.config import ACCEPTED_MEDIA_TYPES
from argus.domain.ingestion.documents.models import DraftProposal, DraftStatus
from argus.domain.ingestion.documents.service import DocumentServiceError

router = APIRouter(prefix="/financial-documents", tags=["financial-documents"])


class DocumentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    connection_id: str
    status: DraftStatus
    replayed: bool
    candidate_count: int


@router.post(
    "",
    response_model=DocumentResponse,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                media: {"schema": {"type": "string", "format": "binary"}}
                for media in ACCEPTED_MEDIA_TYPES
            },
        }
    },
)
async def upload_document(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    filename: str | None = Header(default=None, alias="X-Document-Filename"),
    proposal: str | None = Header(
        default=None, alias="X-Document-Proposal", max_length=8192
    ),
    consent: str | None = Header(default=None, alias="X-Extraction-Consent"),
    context: DocumentContext = Depends(require_document_context),  # noqa: B008
) -> dict[str, object]:
    response.headers.update(NO_STORE)
    try:
        destination = (
            DraftProposal.model_validate_json(proposal)
            if proposal is not None
            else DraftProposal()
        )
    except ValidationError:
        raise document_problem(
            request, DocumentServiceError("document_proposal_invalid")
        ) from None
    media_type, content = await read_document_upload(request)
    try:
        outcome = await context.service.upload(
            user_id=context.user_id,
            content=content,
            filename=filename or "document",
            media_type=media_type,
            consent=consent == "true",
            proposal=destination,
        )
        if outcome.status == "queued":
            await dispatch_preparation(
                context.service, context.user_id, outcome.connection_id, background_tasks
            )
        return asdict(outcome)
    except Exception as error:
        raise document_problem(request, error) from None


@router.post("/{connection_id}/prepare", response_model=DocumentResponse)
@router.post("/{connection_id}/resume", response_model=DocumentResponse)
async def resume_document(
    request: Request,
    connection_id: str,
    background_tasks: BackgroundTasks,
    consent: str | None = Header(default=None, alias="X-Extraction-Consent"),
    context: DocumentContext = Depends(require_document_context),  # noqa: B008
) -> dict[str, object]:
    try:
        outcome = context.service.queue(
            user_id=context.user_id,
            connection_id=connection_id,
            consent=consent == "true",
        )
        await dispatch_preparation(
            context.service, context.user_id, connection_id, background_tasks
        )
        return asdict(outcome)
    except Exception as error:
        raise document_problem(request, error) from None


def _draft(context: DocumentContext, connection_id: str) -> dict[str, object]:
    draft = context.service.get(user_id=context.user_id, connection_id=connection_id)
    batch = context.service.store.get(
        user_id=context.user_id, connection_id=connection_id
    )
    return {
        **draft.model_dump(mode="json"),
        "preparation": batch.model_dump(mode="json", exclude={"metadata"})
        if batch
        else None,
    }


@router.get("")
def list_documents(
    request: Request,
    response: Response,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    context: DocumentContext = Depends(require_document_context),  # noqa: B008
) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    try:
        items = []
        for connection in context.service.hub.connections.list(user_id=context.user_id):
            if connection.source == "statement" and connection.status != "disconnected":
                try:
                    items.append(
                        context.service.get(
                            user_id=context.user_id, connection_id=connection.id
                        ).model_dump(mode="json")
                    )
                except DocumentServiceError as error:
                    if error.code != "document_source_unavailable":
                        raise
        return {
            "items": items[offset : offset + limit],
            "next_offset": offset + limit if offset + limit < len(items) else None,
        }
    except Exception as error:
        raise document_problem(request, error) from None


@router.get("/{connection_id}")
def get_document(
    request: Request,
    response: Response,
    connection_id: str,
    context: DocumentContext = Depends(require_document_context),  # noqa: B008
) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    try:
        return _draft(context, connection_id)
    except Exception as error:
        raise document_problem(request, error) from None


@router.get("/{connection_id}/source")
def get_source(
    request: Request,
    connection_id: str,
    context: DocumentContext = Depends(require_document_context),  # noqa: B008
) -> Response:
    try:
        draft = context.service.get(user_id=context.user_id, connection_id=connection_id)
        content = context.service.source_bytes(
            user_id=context.user_id, connection_id=connection_id
        )
        suffix = {"application/pdf": "pdf", "image/png": "png", "image/jpeg": "jpg"}[
            draft.media_type
        ]
        return Response(
            content,
            media_type=draft.media_type,
            headers={
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Content-Disposition": f'attachment; filename="document.{suffix}"',
            },
        )
    except Exception as error:
        raise document_problem(request, error) from None


class ProposalUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int
    proposal: DraftProposal


@router.patch("/{connection_id}/proposal")
def update_proposal(
    request: Request,
    response: Response,
    connection_id: str,
    body: ProposalUpdate,
    context: DocumentContext = Depends(require_document_context),  # noqa: B008
) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    try:
        context.service.update_proposal(
            user_id=context.user_id,
            connection_id=connection_id,
            version=body.version,
            proposal=body.proposal,
        )
        return _draft(context, connection_id)
    except Exception as error:
        raise document_problem(request, error) from None
