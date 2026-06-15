from __future__ import annotations

from fastapi import APIRouter, Depends
from loguru import logger

from argus.api import state as api_state
from argus.api.dependencies import current_user
from argus.api.feedback_context import sanitize_feedback_context
from argus.api.schemas import FeedbackRequest, SuccessResponse, User
from argus.domain.store import utcnow

router = APIRouter(prefix="/api/v1", tags=["feedback"])


@router.post("/feedback", response_model=SuccessResponse)
def feedback(
    payload: FeedbackRequest,
    user: User = Depends(current_user),  # noqa: B008
) -> SuccessResponse:
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

    logger.info(
        "Feedback submitted",
        feedback_type=payload.type,
        feedback_source=context.get("source"),
        message_len=len(payload.message),
    )

    return SuccessResponse(success=True)
