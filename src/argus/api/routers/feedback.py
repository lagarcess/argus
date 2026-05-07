from __future__ import annotations

from fastapi import APIRouter, Depends
from loguru import logger

from argus.api import state as api_state
from argus.api.dependencies import current_user
from argus.api.schemas import FeedbackRequest, SuccessResponse, User

router = APIRouter(prefix="/api/v1", tags=["feedback"])


@router.post("/feedback", response_model=SuccessResponse)
def feedback(
    payload: FeedbackRequest,
    user: User = Depends(current_user),  # noqa: B008
) -> SuccessResponse:
    if api_state.supabase_gateway is not None:
        api_state.supabase_gateway.create_feedback(
            user_id=user.id,
            feedback_type=payload.type,
            message=payload.message,
            context=payload.context,
        )
    else:
        api_state.store.feedback.append(
            {
                "user_id": user.id,
                "type": payload.type,
                "message": payload.message,
                "context": payload.context,
            }
        )

    logger.info(
        "Feedback submitted",
        feedback_type=payload.type,
        message_len=len(payload.message),
    )

    return SuccessResponse(success=True)
