"""Silent anti-abuse ceiling on guest compute turns.

Conversation is compute: free, unlimited in the product surface, never an
allowance. An anonymous endpoint still cannot be unbounded, so a guest's
ordinary turns count against a visitor-keyed daily ceiling sized so no real
person reaches it. Nothing here is rendered or promised, a registered account
carries no ceiling, and run actions are execution charged at admission.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Request
from loguru import logger

from argus.api import state as api_state
from argus.api.dependencies import dev_memory_fallback_enabled, problem
from argus.api.guest_access import AccountContext, account_context, client_identity
from argus.api.schemas import User
from argus.domain.usage_limits import (
    GUEST_COMPUTE_CEILING_LIMITS,
    GUEST_COMPUTE_CEILING_RESOURCE,
    align_usage_period,
)
from argus.domain.visitor_usage import (
    memory_visitor_within_limits,
    visitor_key_for,
    visitor_within_limits,
)


def check_guest_compute_ceiling(request: Request, user: User) -> None:
    """Non-consuming read at entry; 429 once the visitor's day is at the ceiling."""
    context = account_context(request)
    if context.kind != "guest":
        return
    now = datetime.now(timezone.utc)
    visitor_key = visitor_key_for(client_identity(request))
    try:
        if api_state.supabase_gateway is not None:
            within = visitor_within_limits(
                api_state.supabase_gateway.client,
                visitor_key=visitor_key,
                resource=GUEST_COMPUTE_CEILING_RESOURCE,
                limits=list(GUEST_COMPUTE_CEILING_LIMITS),
                now=now,
            )
        else:
            within = memory_visitor_within_limits(
                api_state.store.visitor_usage_counters,
                visitor_key=visitor_key,
                resource=GUEST_COMPUTE_CEILING_RESOURCE,
                limits=list(GUEST_COMPUTE_CEILING_LIMITS),
                now=now,
            )
    except Exception as exc:
        if not dev_memory_fallback_enabled():
            raise
        logger.warning(
            "Guest compute ceiling read failed; using dev memory fallback",
            error=str(exc),
            user_id=user.id,
        )
        return
    if within:
        return
    _, day_end = align_usage_period(now, "day")
    logger.warning(
        "Guest compute ceiling reached",
        user_id=user.id,
        failure_classification="abuse_ceiling",
    )
    raise problem(
        request,
        status_code=429,
        code="too_many_requests",
        title="Too Many Requests",
        detail="Too many conversation turns today.",
        headers={"Retry-After": str(max(int((day_end - now).total_seconds()), 1))},
    )


def guest_compute_settlement(
    account: AccountContext,
    *,
    is_run_backtest_turn: bool,
    visitor_key: str,
) -> dict[str, object] | None:
    """One turn unit against the visitor ceiling, settled with the durable
    terminal. Registered accounts and run actions settle nothing."""
    if account.kind != "guest" or is_run_backtest_turn:
        return None
    return {
        "resource": GUEST_COMPUTE_CEILING_RESOURCE,
        "limits": list(GUEST_COMPUTE_CEILING_LIMITS),
        "visitor_key": visitor_key,
    }
