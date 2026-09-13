from __future__ import annotations

from fastapi import APIRouter, Depends
from loguru import logger

from argus.api.demonstrated_interest import demonstrated_interest
from argus.api.dependencies import current_user
from argus.api.schemas import (
    DemonstratedInterest,
    MarketSession,
    MarketSessionResponse,
    User,
)
from argus.domain.market_data.market_session import resolve_market_session

router = APIRouter(prefix="/api/v1", tags=["market"])


@router.get("/market/session", response_model=MarketSessionResponse)
def get_market_session(
    user: User = Depends(current_user),  # noqa: B008
) -> MarketSessionResponse:
    """Backend-owned session truth, and what the caller has shown interest in.

    Eastern time and the real trading calendar live behind this, so no caller
    has to know a holiday from a Thursday.
    """
    interest = _interest_or_none(user.id)
    try:
        snapshot = resolve_market_session()
    except Exception as exc:
        logger.warning("Market session unavailable", error=str(exc))
        snapshot = None
    if snapshot is None:
        return MarketSessionResponse(session=None, interest=interest)
    return MarketSessionResponse(
        session=MarketSession(
            phase=snapshot.phase,
            is_market_day=snapshot.is_market_day,
            as_of=snapshot.as_of,
        ),
        interest=interest,
    )


def _interest_or_none(user_id: str) -> DemonstratedInterest | None:
    try:
        return demonstrated_interest(user_id)
    except Exception as exc:
        logger.warning(
            "Demonstrated interest unavailable", error=str(exc), user_id=user_id
        )
        return None
