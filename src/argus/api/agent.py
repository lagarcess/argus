import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from loguru import logger

from argus.api.auth import check_rate_limit
from argus.api.drafter import draft_strategy
from argus.api.exceptions import DraftingError
from argus.api.schemas import AgentDraftRequest, AgentDraftResponse
from argus.config import get_supabase_client
from argus.domain.schemas import UserResponse
from argus.market.data_provider import retry_with_backoff

router = APIRouter(
    prefix="/api/v1/agent",
    tags=["Agent"],
)


@router.post("/draft", response_model=AgentDraftResponse, status_code=status.HTTP_200_OK)
def create_agent_draft(
    request: AgentDraftRequest,
    response: Response,
    user: UserResponse = Depends(check_rate_limit),  # noqa: B008
):
    """Generates a strategy draft from natural language."""
    request_id = str(uuid.uuid4())
    logger.info(
        "Received AI draft request",
        request_id=request_id,
        user_id=user.id,
        prompt_length=len(request.prompt),
    )

    try:
        # Check quota and decrement
        supabase = get_supabase_client()

        try:
            # Manually retry using our decorator if needed, or just let postgrest throw
            @retry_with_backoff(max_retries=3)
            def _call_rpc():
                return supabase.rpc(
                    "decrement_ai_draft_quota", {"user_uuid": user.id}
                ).execute()

            _call_rpc()
        except Exception as e:
            error_msg = str(e)
            if "P0001" in error_msg or "quota" in error_msg.lower():
                logger.warning(
                    "User AI draft quota exhausted",
                    request_id=request_id,
                    user_id=user.id,
                )
                raise HTTPException(
                    status_code=402, detail="Payment Required: AI draft quota exhausted."
                ) from e
            logger.error(f"Failed to decrement quota: {e}", request_id=request_id)
            raise HTTPException(
                status_code=500, detail="Internal server error while verifying quota."
            ) from e

        # Call the Drafter
        draft_output = draft_strategy(request.prompt)

        logger.info(
            "Successfully generated AI draft",
            request_id=request_id,
            user_id=user.id,
            strategy_name=draft_output.strategy.name,
        )

        return AgentDraftResponse(
            draft=draft_output.strategy, ai_explanation=draft_output.ai_explanation
        )

    except DraftingError as de:
        logger.error(f"Drafting error: {de}", request_id=request_id)
        raise HTTPException(
            status_code=500,
            detail="Failed to generate strategy draft due to reasoning engine error.",
        ) from de
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in draft generation", request_id=request_id)
        raise HTTPException(
            status_code=500, detail="An unexpected error occurred."
        ) from e
