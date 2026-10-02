"""Bounded byte uploads feed the existing import review queue."""

from __future__ import annotations

from dataclasses import asdict
from typing import Literal

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, ConfigDict

from argus.api.dependencies import problem
from argus.api.documents import DocumentContext, require_document_context
from argus.domain.ingestion.connections import ConnectionNotFound
from argus.domain.ingestion.documents.models import DocumentExtractionError
from argus.domain.ingestion.documents.service import DocumentServiceError
from argus.domain.ingestion.gmail.attachments import MAX_ATTACHMENT_BYTES

router = APIRouter(prefix="/financial-documents", tags=["financial-documents"])


class DocumentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    connection_id: str
    status: Literal["review_ready"]
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
        )
    if isinstance(error, (DocumentServiceError, DocumentExtractionError)):
        unavailable = error.retryable or error.code in {
            "missing_vision_model",
            "missing_api_key",
            "document_tools_unavailable",
        }
        status = 503 if unavailable else 422
        if error.code == "document_busy":
            status = 409
        if error.code == "document_disconnected":
            status = 410
        return problem(
            request,
            status_code=status,
            code=error.code,
            title="Document unavailable" if unavailable else "Document needs attention",
            detail="The document could not be prepared for review. Retry or upload a clearer copy.",
        )
    return problem(
        request,
        status_code=503,
        code="document_extraction_unavailable",
        title="Document unavailable",
        detail="Document extraction is temporarily unavailable.",
    )


@router.post(
    "",
    response_model=DocumentResponse,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                media: {"schema": {"type": "string", "format": "binary"}}
                for media in ("application/pdf", "image/jpeg", "image/png")
            },
        }
    },
)
async def upload_document(
    request: Request,
    filename: str | None = Header(default=None, alias="X-Document-Filename"),
    consent: str | None = Header(default=None, alias="X-Extraction-Consent"),
    context: DocumentContext = Depends(require_document_context),  # noqa: B008
) -> dict[str, object]:
    if consent != "true":
        raise problem(
            request,
            status_code=422,
            code="document_extraction_consent_required",
            title="Confirmation required",
            detail="Confirm sending this document to the extraction provider before uploading.",
        )
    media_type = request.headers.get("content-type", "").split(";", 1)[0].strip()
    if media_type not in {"application/pdf", "image/jpeg", "image/png"}:
        raise problem(
            request,
            status_code=415,
            code="document_media_type_unsupported",
            title="Unsupported document",
            detail="Upload a PDF, JPEG or PNG file.",
        )
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > MAX_ATTACHMENT_BYTES:
            raise problem(
                request,
                status_code=413,
                code="document_too_large",
                title="Document too large",
                detail="Upload a document of at most 10 MiB.",
            )
        content.extend(chunk)
    try:
        outcome = await context.service.upload(
            user_id=context.user_id,
            content=bytes(content),
            filename=filename or "document",
            media_type=media_type,
        )
        return asdict(outcome)
    except Exception as error:
        raise _failure(request, error) from None


@router.post("/{connection_id}/resume", response_model=DocumentResponse)
async def resume_document(
    request: Request,
    connection_id: str,
    context: DocumentContext = Depends(require_document_context),  # noqa: B008
) -> dict[str, object]:
    try:
        return asdict(
            await context.service.resume(
                user_id=context.user_id,
                connection_id=connection_id,
            )
        )
    except Exception as error:
        raise _failure(request, error) from None
