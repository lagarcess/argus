from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Request

from argus.api.app_setup import cors_allow_origins
from argus.api.dependencies import current_user, problem
from argus.api.guest_access import account_context
from argus.api.rate_limits import SlidingWindowLimiter
from argus.api.schemas import GuestFunnelClientEventRequest, SuccessResponse, User
from argus.observability.guest_funnel import capture_guest_funnel_event

router = APIRouter(prefix="/api/v1", tags=["analytics"])
GUEST_EVENT_ATTEMPT_LIMIT = 20
_GUEST_EVENT_WINDOW_SECONDS = 10 * 60
_GUEST_EVENT_LIMITER = SlidingWindowLimiter()


def reset_guest_event_limiter_for_tests() -> None:
    _GUEST_EVENT_LIMITER.reset()


@router.post("/analytics/guest-events", response_model=SuccessResponse)
def guest_funnel_event(
    payload: GuestFunnelClientEventRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    user: User = Depends(current_user),  # noqa: B008
) -> SuccessResponse:
    origin = request.headers.get("origin")
    if origin and origin not in cors_allow_origins():
        raise problem(
            request,
            status_code=403,
            code="csrf_origin_rejected",
            title="Request Rejected",
            detail="This analytics request did not come from an allowed origin.",
        )
    if account_context(request).kind != "guest":
        raise problem(
            request,
            status_code=403,
            code="guest_account_required",
            title="Guest Session Required",
            detail="This event is available only for a verified guest session.",
        )
    retry_after = _GUEST_EVENT_LIMITER.record_or_retry_after(
        keys=(f"guest-event:user:{user.id}",),
        limit=GUEST_EVENT_ATTEMPT_LIMIT,
        window_seconds=_GUEST_EVENT_WINDOW_SECONDS,
    )
    if retry_after is not None:
        raise problem(
            request,
            status_code=429,
            code="too_many_requests",
            title="Too Many Requests",
            detail="Too many guest analytics events. Please wait before trying again.",
            headers={"Retry-After": str(retry_after)},
        )
    background_tasks.add_task(
        capture_guest_funnel_event,
        payload.event,
        user_id=user.id,
        language=payload.language,
        surface=payload.surface,
        strategy_category=payload.strategy_category,
        conversion_reason=payload.conversion_reason,
        terminal_outcome=payload.terminal_outcome,
    )
    return SuccessResponse(success=True)
