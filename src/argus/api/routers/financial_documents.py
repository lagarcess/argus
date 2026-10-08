"""Bounded byte uploads feed the existing import review queue."""

from __future__ import annotations

from dataclasses import asdict
from urllib.parse import unquote

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query, Request, Response
from pydantic import BaseModel, ConfigDict, ValidationError

from argus.api.dependencies import problem
from argus.api.documents import DocumentContext, require_document_context
from argus.domain.ingestion.connections import ConnectionNotFound
from argus.domain.ingestion.documents.config import (
    SOURCE_MEDIA_TYPES,
    load_document_extraction_settings,
)
from argus.domain.ingestion.documents.models import (
    DocumentExtractionError,
    DraftProposal,
    DraftStatus,
)
from argus.domain.ingestion.documents.service import DocumentServiceError

router = APIRouter(prefix="/financial-documents", tags=["financial-documents"])
NO_STORE = {"Cache-Control": "no-store"}


class DocumentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    connection_id: str
    status: DraftStatus
    replayed: bool
    candidate_count: int


def _failure(request: Request, error: Exception) -> Exception:
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
        if error.code in {"document_busy", "document_version_conflict"}:
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


def _filename(header: str | None) -> str:
    """``X-Document-Filename`` is percent-encoded UTF-8 (``encodeURIComponent``),
    which is pure ASCII. Anything else is raw UTF-8, read by the server as
    latin-1: it is recovered and never percent-decoded, and bytes that are not
    UTF-8 become replacement characters rather than mojibake."""

    if not header:
        return "document"
    if header.isascii():
        return unquote(header, errors="replace")
    return header.encode("latin-1").decode("utf-8", errors="replace")


@router.post(
    "",
    response_model=DocumentResponse,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                media: {"schema": {"type": "string", "format": "binary"}}
                for media in SOURCE_MEDIA_TYPES
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
        raise _failure(
            request, DocumentServiceError("document_proposal_invalid")
        ) from None
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
    try:
        outcome = await context.service.upload(
            user_id=context.user_id,
            content=bytes(content),
            filename=_filename(filename),
            media_type=media_type,
            consent=consent == "true",
            proposal=destination,
        )
        if outcome.status == "queued":
            background_tasks.add_task(
                context.service.background_prepare,
                user_id=context.user_id,
                connection_id=outcome.connection_id,
            )
        return asdict(outcome)
    except Exception as error:
        raise _failure(request, error) from None


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
        background_tasks.add_task(
            context.service.background_prepare,
            user_id=context.user_id,
            connection_id=connection_id,
        )
        return asdict(outcome)
    except Exception as error:
        raise _failure(request, error) from None


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
        raise _failure(request, error) from None


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
        raise _failure(request, error) from None


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
        suffix = SOURCE_MEDIA_TYPES[draft.media_type]
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
        raise _failure(request, error) from None


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
        raise _failure(request, error) from None
