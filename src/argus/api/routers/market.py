from __future__ import annotations

from fastapi import APIRouter, Depends
from loguru import logger

from argus.api.dependencies import current_user
from argus.api.schemas import MarketSession, MarketSessionResponse, User
from argus.domain.market_data.market_session import resolve_market_session

router = APIRouter(prefix="/api/v1", tags=["market"])


@router.get("/market/session", response_model=MarketSessionResponse)
def get_market_session(
    user: User = Depends(current_user),  # noqa: B008
) -> MarketSessionResponse:
    """Backend-owned session truth for surfaces that speak about the market.

    Eastern time and the real trading calendar both live behind this, so no
    caller has to know the difference between a holiday and a Thursday.
    """
    del user
    try:
        snapshot = resolve_market_session()
    except Exception as exc:
        logger.warning("Market session unavailable", error=str(exc))
        return MarketSessionResponse(session=None)
    if snapshot is None:
        return MarketSessionResponse(session=None)
    return MarketSessionResponse(
        session=MarketSession(
            phase=snapshot.phase,
            is_market_day=snapshot.is_market_day,
            as_of=snapshot.as_of,
        )
    )
