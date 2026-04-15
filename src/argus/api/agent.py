import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from postgrest import APIError

from argus.api.auth import check_ai_quota
from argus.api.drafter import draft_strategy
from argus.api.exceptions import DraftingError
from argus.api.schemas import AgentDraftRequest, AgentDraftResponse
from argus.config import get_supabase_client
from argus.domain.schemas import UserResponse

router = APIRouter(
    prefix="/api/v1/agent",
    tags=["Agent"],
)


def _is_quota_exhausted_error(exc: Exception) -> bool:
    """Helper to detect PostgreSQL P0001 quota exception from Supabase."""
    if isinstance(exc, APIError):
        return exc.code == "P0001"
    return "P0001" in str(exc) or "quota" in str(exc).lower()


@router.post("/draft", response_model=AgentDraftResponse, status_code=status.HTTP_200_OK)
def create_agent_draft(
    request: AgentDraftRequest,
    user: UserResponse = Depends(check_ai_quota),  # noqa: B008
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
        # Call the Drafter
        draft_output = draft_strategy(request.prompt)

        # Decrement quota only after a successful draft generation.
        try:
            supabase = get_supabase_client()
            supabase.rpc("decrement_ai_draft_quota", {"user_uuid": user.id}).execute()
        except ValueError as exc:
            logger.exception(
                "Supabase client misconfigured during AI draft quota decrement",
                request_id=request_id,
                user_id=user.id,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to verify AI draft quota.",
            ) from exc
        except Exception as exc:
            if _is_quota_exhausted_error(exc):
                logger.warning(
                    "User AI draft quota exhausted during RPC",
                    request_id=request_id,
                    user_id=user.id,
                )
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail={
                        "error": "QUOTA_EXCEEDED",
                        "message": "You have exhausted your AI draft quota.",
                        "upgrade_url": "/settings",
                    },
                ) from exc

            logger.exception(
                "Failed to decrement AI draft quota",
                request_id=request_id,
                user_id=user.id,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to verify AI draft quota.",
            ) from exc

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
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate strategy draft due to reasoning engine error.",
        ) from de
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        logger.exception("Unexpected error in draft generation", request_id=request_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        ) from e
