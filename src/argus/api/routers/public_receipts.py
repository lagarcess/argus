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
from argus.domain.public_excerpts import revoked_public_view
from argus.observability.product_events import capture_product_event

router = APIRouter(prefix="/api/v1/public", tags=["public-receipts"])

MAX_PUBLIC_ID_LENGTH = 64
FUNNEL_STAGE_LIMIT = 60
FUNNEL_STAGE_WINDOW_SECONDS = 3600

_FUNNEL_LIMITER = SlidingWindowLimiter()


def reset_receipt_funnel_limiter_for_tests() -> None:
    _FUNNEL_LIMITER.reset()


@router.get("/receipts/{public_id}", response_model=PublicExcerptView)
def read_public_receipt(
    public_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
) -> PublicExcerptView:
    require_evidence_receipt_sharing_enabled()
    if len(public_id) > MAX_PUBLIC_ID_LENGTH:
        # Bounded before it reaches storage, and answered like any other stale
        # link so an oversized id is not its own signal.
        view = revoked_public_view(public_id[:MAX_PUBLIC_ID_LENGTH])
    else:
        view = public_excerpt_reader().read_public_excerpt_view(public_id=public_id)
    # No actor, no source id. A view is never attributable to whoever shared it.
    # Deferred so a stranger hitting the page never waits on analytics.
    background_tasks.add_task(
        capture_product_event,
        "receipt_viewed",
        user_id=None,
        status=view.status,
    )
    return view


@router.post("/receipt-funnel", status_code=204)
def record_receipt_funnel_stage(
    payload: PublicExcerptFunnelStage,
    request: Request,
    background_tasks: BackgroundTasks,
) -> Response:
    """Record one viewer-side funnel stage. Carries no id and stores nothing.

    Section 7.2 asks for the acquisition path to be observable end to end, and
    the Try Argus tap happens on a page nobody is signed in to. The alternative,
    a marker on the guest entry url, is ruled out by section 6: sharing adds no
    new parameter to that surface.
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
        status="tapped",
    )
    return Response(status_code=204)
