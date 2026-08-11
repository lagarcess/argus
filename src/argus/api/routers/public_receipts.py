"""The unauthenticated receipt read. Deliberately the smallest router in Argus.

This module holds exactly one capability: resolve a public id to a frozen
snapshot view. It has no auth dependency, no gateway, no store, and no name for a
conversation, message, run, artifact or memory record anywhere in it. That
absence is the construction proof that a public view cannot reach private data,
and it is asserted by test rather than left to review.

An unknown id and a revoked id both answer with the same tombstone: with
unguessable ids there is nothing to enumerate, and a viewer holding a stale link
deserves an honest page instead of a broken one.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Request, Response

from argus.api.dependencies import problem
from argus.api.guest_access import client_identity
from argus.api.public_excerpt_schemas import (
    PublicExcerptFunnelStage,
    PublicExcerptView,
)
from argus.api.public_excerpts import (
    public_excerpt_reader,
    require_evidence_receipt_sharing_enabled,
)
from argus.api.rate_limits import SlidingWindowLimiter
from argus.domain.public_excerpts import (
    PublicExcerptUnreadableError,
    revoked_public_view,
)
from argus.observability.product_events import capture_product_event

router = APIRouter(prefix="/api/v1/public", tags=["public-receipts"])

MAX_PUBLIC_ID_LENGTH = 64
FUNNEL_STAGE_LIMIT = 60
FUNNEL_STAGE_WINDOW_SECONDS = 3600

_FUNNEL_LIMITER = SlidingWindowLimiter()


def reset_receipt_funnel_limiter_for_tests() -> None:
    _FUNNEL_LIMITER.reset()


@router.get("/receipts/{public_id}", response_model=PublicExcerptView)
def read_public_receipt(public_id: str, request: Request) -> PublicExcerptView:
    """Read one frozen receipt. Deliberately counts nothing.

    This endpoint answers more than once per human visit, from the page's metadata
    pass, the page render, and the preview image, and a crawler expanding a pasted
    link hits it with nobody having opened anything. Views are reported by the
    rendered page instead, through /public/receipt-funnel.
    """
    require_evidence_receipt_sharing_enabled()
    if len(public_id) > MAX_PUBLIC_ID_LENGTH:
        # Bounded before it reaches storage, and answered like any other stale
        # link so an oversized id is not its own signal.
        return revoked_public_view(public_id[:MAX_PUBLIC_ID_LENGTH])
    try:
        return public_excerpt_reader().read_public_excerpt_view(public_id=public_id)
    except PublicExcerptUnreadableError as error:
        # A stored payload this build cannot parse answers as temporarily
        # unavailable, which is what it is. An uncaught validation error would
        # answer a stranger with a 500 on the first Argus page they ever see, and a
        # tombstone would tell them a live receipt is gone for good.
        raise problem(
            request,
            status_code=503,
            code="receipt_unavailable",
            title="Service Unavailable",
            detail=str(error),
            headers={"Retry-After": "120"},
        ) from error


@router.post("/receipt-funnel", status_code=204)
def record_receipt_funnel_stage(
    payload: PublicExcerptFunnelStage,
    request: Request,
    background_tasks: BackgroundTasks,
) -> Response:
    """Record one viewer-side funnel stage. Carries no id and stores nothing.

    Section 7.2 asks for the acquisition path to be observable end to end, and
    both viewer-side stages happen on a page nobody is signed in to. A marker on
    the guest entry url is ruled out by section 6: sharing adds no new parameter
    to that surface.

    Views are reported from the rendered page rather than counted on the read
    endpoint, because that endpoint answers metadata passes and preview-image
    renders too. A pasted link would otherwise log several views before any
    person opened it.
    """
    require_evidence_receipt_sharing_enabled()
    retry_after = _FUNNEL_LIMITER.record_or_retry_after(
        keys=(f"receipt-funnel:{client_identity(request)}",),
        limit=FUNNEL_STAGE_LIMIT,
        window_seconds=FUNNEL_STAGE_WINDOW_SECONDS,
    )
    if retry_after is not None:
        raise problem(
            request,
            status_code=429,
            code="too_many_requests",
            title="Too Many Requests",
            detail="Too many events from this client.",
            headers={"Retry-After": str(retry_after)},
        )
    background_tasks.add_task(
        capture_product_event,
        f"receipt_{payload.stage}",
        user_id=None,
        status=payload.stage,
    )
    return Response(status_code=204)
