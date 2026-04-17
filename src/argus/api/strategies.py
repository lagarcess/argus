import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from loguru import logger

from argus.api.auth import auth_required, check_rate_limit
from argus.api.schemas import (
    PaginatedStrategiesResponse,
    StrategyCreate,
    StrategyResponse,
)
from argus.domain.persistence import PersistenceError, PersistenceService
from argus.domain.schemas import UserResponse

router = APIRouter(
    prefix="/api/v1/strategies",
    tags=["Strategies"],
)

persistence_service = PersistenceService()


@router.post("", response_model=StrategyResponse, status_code=status.HTTP_201_CREATED)
def create_strategy(
    strategy: StrategyCreate,
    response: Response,
    user: UserResponse = Depends(check_rate_limit),  # noqa: B008
):
    """Create a new strategy draft."""
    try:
        user_id_str = str(user.id)

        # Add rate limit headers mock (actual rate limit via check_rate_limit would normally set this in middleware)
        response.headers["X-RateLimit-Limit"] = "30"
        response.headers["X-RateLimit-Remaining"] = "29"
        response.headers["X-RateLimit-Reset"] = str(int(time.time() + 3600))

        strategy_data = strategy.model_dump(exclude_unset=True)
        db_strategy = persistence_service.save_strategy(
            user_id_str,
            strategy_data,
            strict=True,
        )

        if not db_strategy:
            raise HTTPException(
                status_code=500, detail="Failed to create strategy in database."
            )

        return db_strategy

    except HTTPException:
        raise
    except PersistenceError as e:
        logger.error(f"Persistence error creating strategy: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to create strategy in database.",
        ) from e
    except Exception as e:
        logger.error(f"Error creating strategy: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("", response_model=PaginatedStrategiesResponse)
def list_strategies(
    cursor: Optional[str] = Query(None, description="Base64 encoded cursor"),
    limit: int = Query(10, ge=1, le=100),
    user: UserResponse = Depends(auth_required),  # noqa: B008,
):
    """List all strategies for the current user."""
    try:
        user_id_str = str(user.id)
        result = persistence_service.list_strategies(
            user_id_str, limit, cursor, strict=True
        )
        if result is None:
            raise HTTPException(
                status_code=500,
                detail="Failed to fetch strategies from database.",
            )
        strategies, next_cursor = result

        return PaginatedStrategiesResponse(
            strategies=[StrategyResponse(**s) for s in strategies],
            next_cursor=next_cursor,
        )
    except PersistenceError as e:
        logger.error(f"Persistence error listing strategies: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch strategies from database.",
        ) from e
    except Exception as e:
        logger.error(f"Error listing strategies: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/{strategy_id}", response_model=StrategyResponse)
def get_strategy(strategy_id: str, user: UserResponse = Depends(auth_required)):  # noqa: B008
    """Get a specific strategy by ID."""
    user_id_str = str(user.id)
    db_strategy = persistence_service.get_strategy(strategy_id, user_id_str)

    if not db_strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    return db_strategy


@router.put("/{strategy_id}", response_model=StrategyResponse)
def update_strategy(
    strategy_id: str,
    strategy: StrategyCreate,
    user: UserResponse = Depends(auth_required),  # noqa: B008
):
    """Update a strategy. Returns 403 if it has already been executed."""
    user_id_str = str(user.id)

    # 1. Check if it exists and if it's executed
    db_strategy = persistence_service.get_strategy(strategy_id, user_id_str)
    if not db_strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    if db_strategy.get("executed_at") is not None:
        raise HTTPException(status_code=403, detail="Cannot modify an executed strategy.")

    # 2. Update
    strategy_data = strategy.model_dump(exclude_unset=True)
    updated_strategy = persistence_service.save_strategy(
        user_id_str, strategy_data, strategy_id, strict=True
    )

    if not updated_strategy:
        raise HTTPException(status_code=500, detail="Failed to update strategy.")

    return updated_strategy


@router.delete("/{strategy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_strategy(strategy_id: str, user: UserResponse = Depends(auth_required)):  # noqa: B008
    """Delete a strategy. Returns 403 if it has already been executed."""
    user_id_str = str(user.id)

    db_strategy = persistence_service.get_strategy(strategy_id, user_id_str)
    if not db_strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    if db_strategy.get("executed_at") is not None:
        raise HTTPException(status_code=403, detail="Cannot delete an executed strategy.")

    success = persistence_service.delete_strategy(strategy_id, user_id_str)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete strategy.")

    return Response(status_code=status.HTTP_204_NO_CONTENT)
