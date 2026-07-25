from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from loguru import logger

from argus.api import state as api_state
from argus.api.dependencies import current_user, problem
from argus.api.feedback_context import sanitize_feedback_context
from argus.api.guest_access import account_context
from argus.api.guest_observability import emit_guest_funnel_event
from argus.api.schemas import FeedbackRequest, SuccessResponse, User
from argus.domain.store import utcnow
from argus.domain.supabase_gateway import QuotaExceededError
from argus.domain.usage_limits import FEEDBACK_USAGE_RESOURCE, allowance_windows

router = APIRouter(prefix="/api/v1", tags=["feedback"])


@router.post("/feedback", response_model=SuccessResponse)
def feedback(
    payload: FeedbackRequest,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
) -> SuccessResponse:
    account = account_context(request)
    context = sanitize_feedback_context(payload.context)
    if payload.type == "account_deletion_request":
        context.update(
            {
                "source": str(context.get("source") or "profile_modal"),
                "account_email": user.email,
                "profile_language": user.language,
                "request_user_id": user.id,
                "requested_at": utcnow().isoformat(),
            }
        )

    if api_state.supabase_gateway is not None:
        if account.kind == "guest":
            outcome = api_state.supabase_gateway.create_feedback_settling_usage(
                user_id=user.id,
                feedback_type=payload.type,
                message=payload.message,
                context=context,
                allowance_limits=allowance_windows(
                    account,
                    FEEDBACK_USAGE_RESOURCE,
                ),
            )
            if outcome.get("decision") != "accepted":
                emit_guest_funnel_event(
                    account=account,
                    kind="guest_limit_reached",
                    user_id=user.id,
                    surface="feedback",
                    capability_category="feedback",
                    terminal_outcome="limit_reached",
                )
                raise problem(
                    request,
                    status_code=403,
                    code="account_conversion_required",
                    title="Account Required",
                    detail="Sign in to submit more feedback.",
                )
        else:
            try:
                api_state.supabase_gateway.check_and_increment_usage_limits(
                    user_id=user.id,
                    resource="feedback",
                    limits=[("day", 50), ("hour", 20)],
                )
            except QuotaExceededError as exc:
                raise problem(
                    request,
                    status_code=429,
                    code="too_many_requests",
                    title="Quota Exceeded",
                    detail=str(exc),
                    headers={"Retry-After": "60"},
                ) from exc
            api_state.supabase_gateway.create_feedback(
                user_id=user.id,
                feedback_type=payload.type,
                message=payload.message,
                context=context,
            )
    else:
        api_state.store.feedback.append(
            {
                "user_id": user.id,
                "type": payload.type,
                "message": payload.message,
                "context": context,
            }
        )

    emit_guest_funnel_event(
        account=account,
        kind="guest_feedback_submitted",
        user_id=user.id,
        surface="feedback",
        capability_category="feedback",
        terminal_outcome="completed",
    )
    logger.info(
        "Feedback submitted",
        feedback_type=payload.type,
        feedback_source=context.get("source"),
        message_len=len(payload.message),
    )

    return SuccessResponse(success=True)
