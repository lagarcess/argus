"""Registered-only personalization-memory endpoints.

Each handler enters through the single memory API gate: a verified Guest is
denied with 403 account_conversion_required before any memory code runs, and
the default-off ARGUS_ENABLE_PERSONALIZATION_MEMORY flag plus an injected
service are both required before the subsystem is reachable at all.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from fastapi import APIRouter, Depends, Request

from argus.api.dependencies import problem
from argus.api.personalization_memory import (
    MemoryApiContext,
    personalization_memory_unavailable_problem,
    require_memory_api_context,
)
from argus.api.personalization_memory_schemas import (
    MemoryCandidateOut,
    MemoryConfirmationResponse,
    MemoryConfirmRequest,
    MemoryConsentSettingsResponse,
    MemoryControlResponse,
    MemoryDeclineResponse,
    MemoryEditRequest,
    MemoryEnableRequest,
    MemoryExplanationResponse,
    MemoryProposalResponse,
    MemoryProposeRequest,
    MemoryProposeSavedDecisionRequest,
    MemoryRecordOut,
    MemoryRecordsResponse,
    MemoryRetrievalResponse,
    MemoryRetrieveRequest,
    RetrievedMemoryOut,
)
from argus.memory.contracts import (
    MemoryCandidateDraft,
    MemoryEdit,
    MemoryProposalTrigger,
    SensitivityAssessment,
)
from argus.memory.subject import PersonalizationMemoryUnavailable

router = APIRouter(prefix="/api/v1", tags=["personalization-memory"])


def _unassessed_sensitivity() -> SensitivityAssessment:
    # Sensitivity is backend truth: no client claim is accepted, so every API
    # entry is unassessed and policy fails closed until a backend proposal
    # boundary assesses content.
    return SensitivityAssessment()


ResultT = TypeVar("ResultT")


def _run(request: Request, call: Callable[[], ResultT]) -> ResultT:
    try:
        return call()
    except PersonalizationMemoryUnavailable:
        raise personalization_memory_unavailable_problem(request) from None
    except ValueError:
        # The original message may quote request content; do not echo it.
        raise problem(
            request,
            status_code=400,
            code="invalid_memory_request",
            title="Invalid Memory Request",
            detail="The request is not valid for personalization memory.",
        ) from None


@router.post("/memory/enable", response_model=MemoryConsentSettingsResponse)
def enable_memory(
    payload: MemoryEnableRequest,
    request: Request,
    ctx: MemoryApiContext = Depends(require_memory_api_context),  # noqa: B008
) -> MemoryConsentSettingsResponse:
    settings = _run(
        request,
        lambda: ctx.service.enable(
            ctx.subject,
            frozenset(payload.categories),
            idempotency_key=payload.idempotency_key,
        ),
    )
    return MemoryConsentSettingsResponse.from_domain(settings)


@router.post("/memory/candidates", response_model=MemoryProposalResponse)
def propose_memory(
    payload: MemoryProposeRequest,
    request: Request,
    ctx: MemoryApiContext = Depends(require_memory_api_context),  # noqa: B008
) -> MemoryProposalResponse:
    draft = MemoryCandidateDraft(
        category=payload.category,
        value=payload.value,
        label=payload.label,
        future_benefit=payload.future_benefit,
        provenance=tuple(ref.to_domain() for ref in payload.provenance),
        trigger=MemoryProposalTrigger.EXPLICIT_REQUEST,
        sensitivity=_unassessed_sensitivity(),
    )
    result = _run(
        request,
        lambda: ctx.service.propose(ctx.subject, draft, payload.context),
    )
    if result is None:
        return MemoryProposalResponse(created=False)
    return MemoryProposalResponse(
        created=True,
        candidate=MemoryCandidateOut.from_domain(result.candidate),
    )


@router.post(
    "/memory/candidates/saved-decision",
    response_model=MemoryProposalResponse,
)
def propose_saved_decision_memory(
    payload: MemoryProposeSavedDecisionRequest,
    request: Request,
    ctx: MemoryApiContext = Depends(require_memory_api_context),  # noqa: B008
) -> MemoryProposalResponse:
    result = _run(
        request,
        lambda: ctx.service.propose_saved_decision(
            ctx.subject,
            payload.to_source(),
            sensitivity=_unassessed_sensitivity(),
            context=payload.context,
        ),
    )
    if result is None:
        return MemoryProposalResponse(created=False)
    return MemoryProposalResponse(
        created=True,
        candidate=MemoryCandidateOut.from_domain(result.candidate),
    )


@router.post(
    "/memory/candidates/{candidate_id}/confirm",
    response_model=MemoryConfirmationResponse,
)
def confirm_memory_candidate(
    candidate_id: str,
    payload: MemoryConfirmRequest,
    request: Request,
    ctx: MemoryApiContext = Depends(require_memory_api_context),  # noqa: B008
) -> MemoryConfirmationResponse:
    result = _run(
        request,
        lambda: ctx.service.confirm(
            ctx.subject,
            candidate_id,
            sensitivity=_unassessed_sensitivity(),
            context=payload.context,
        ),
    )
    return MemoryConfirmationResponse.from_domain(result)


@router.post(
    "/memory/candidates/{candidate_id}/decline",
    response_model=MemoryDeclineResponse,
)
def decline_memory_candidate(
    candidate_id: str,
    request: Request,
    ctx: MemoryApiContext = Depends(require_memory_api_context),  # noqa: B008
) -> MemoryDeclineResponse:
    declined = _run(request, lambda: ctx.service.decline(ctx.subject, candidate_id))
    return MemoryDeclineResponse(declined=declined)


@router.get("/memory/records", response_model=MemoryRecordsResponse)
def inspect_memory_records(
    request: Request,
    ctx: MemoryApiContext = Depends(require_memory_api_context),  # noqa: B008
) -> MemoryRecordsResponse:
    records = _run(request, lambda: ctx.service.inspect(ctx.subject))
    return MemoryRecordsResponse(
        records=[MemoryRecordOut.from_domain(record) for record in records]
    )


@router.get(
    "/memory/records/{record_id}/explanation",
    response_model=MemoryExplanationResponse,
)
def explain_memory_record(
    record_id: str,
    request: Request,
    ctx: MemoryApiContext = Depends(require_memory_api_context),  # noqa: B008
) -> MemoryExplanationResponse:
    explanation = _run(request, lambda: ctx.service.explain(ctx.subject, record_id))
    if explanation is None:
        raise problem(
            request,
            status_code=404,
            code="not_found",
            title="Not Found",
            detail="Memory record not found.",
        )
    return MemoryExplanationResponse.from_domain(explanation)


@router.post("/memory/retrieval", response_model=MemoryRetrievalResponse)
def retrieve_memories(
    payload: MemoryRetrieveRequest,
    request: Request,
    ctx: MemoryApiContext = Depends(require_memory_api_context),  # noqa: B008
) -> MemoryRetrievalResponse:
    retrieved = _run(
        request,
        lambda: ctx.service.retrieve(
            ctx.subject,
            payload.query,
            payload.purpose,
            payload.context,
            limit=payload.limit,
        ),
    )
    return MemoryRetrievalResponse(
        memories=[RetrievedMemoryOut.from_domain(memory) for memory in retrieved]
    )


@router.patch("/memory/records/{record_id}", response_model=MemoryControlResponse)
def edit_memory_record(
    record_id: str,
    payload: MemoryEditRequest,
    request: Request,
    ctx: MemoryApiContext = Depends(require_memory_api_context),  # noqa: B008
) -> MemoryControlResponse:
    edit = MemoryEdit(
        value=payload.value,
        label=payload.label,
        sensitivity=_unassessed_sensitivity(),
    )
    result = _run(request, lambda: ctx.service.edit(ctx.subject, record_id, edit))
    return MemoryControlResponse.from_domain(result)


@router.delete("/memory/records/{record_id}", response_model=MemoryControlResponse)
def delete_memory_record(
    record_id: str,
    request: Request,
    ctx: MemoryApiContext = Depends(require_memory_api_context),  # noqa: B008
) -> MemoryControlResponse:
    result = _run(request, lambda: ctx.service.delete(ctx.subject, record_id))
    return MemoryControlResponse.from_domain(result)


@router.post("/memory/disable", response_model=MemoryControlResponse)
def disable_memory(
    request: Request,
    ctx: MemoryApiContext = Depends(require_memory_api_context),  # noqa: B008
) -> MemoryControlResponse:
    result = _run(request, lambda: ctx.service.disable(ctx.subject))
    return MemoryControlResponse.from_domain(result)


@router.post("/memory/reset", response_model=MemoryControlResponse)
def reset_memory(
    request: Request,
    ctx: MemoryApiContext = Depends(require_memory_api_context),  # noqa: B008
) -> MemoryControlResponse:
    result = _run(request, lambda: ctx.service.reset(ctx.subject))
    return MemoryControlResponse.from_domain(result)
