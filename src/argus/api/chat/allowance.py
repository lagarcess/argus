"""Chat-entry allowance checks and terminal settlement policy (#247).

Ordinary turns are checked non-consumingly at entry and settle exactly one
message unit at their durable terminal outcome; run actions charge the
simulation allowance at admission and skip message accounting.
"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from loguru import logger

from argus.api import state as api_state
from argus.api.dependencies import dev_memory_fallback_enabled, problem
from argus.api.schemas import User
from argus.domain.usage_limits import (
    MESSAGE_ALLOWANCE_LIMITS,
    QuotaExceededError,
    message_usage_settlement,
)


def check_message_allowance(request: Request, user: User) -> None:
    """Non-consuming hour+day check; 429 at entry when a window is exhausted."""
    if api_state.supabase_gateway is None:
        return
    try:
        api_state.supabase_gateway.check_usage_limits(
            user_id=user.id,
            resource="chat_messages",
            limits=MESSAGE_ALLOWANCE_LIMITS,
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
    except Exception as exc:
        if not dev_memory_fallback_enabled():
            raise
        logger.warning(
            "Supabase usage counter failed; using dev memory fallback",
            error=str(exc),
            user_id=user.id,
            resource="chat_messages",
        )


def ordinary_turn_settlement(*, is_run_backtest_turn: bool) -> dict[str, Any] | None:
    return None if is_run_backtest_turn else message_usage_settlement()
