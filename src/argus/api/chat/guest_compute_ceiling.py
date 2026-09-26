"""Silent anti-abuse ceiling on guest compute turns.

Conversation is compute: free, unlimited in the product surface, never an
allowance. An anonymous endpoint still cannot be unbounded, so a guest's
ordinary turns count against two daily ceilings, and the guest hits
whichever is lower:

- visitor-keyed (trusted client IP)
- session-keyed (authenticated guest workspace / anonymous user id)

Both units are claimed atomically before any model work, the same way
research claims before spend. The claim runs after the conversation is
resolved and after every stale or replayed action is rejected, so a 404 or
a rejected replay never costs a unit (#692). A claim that is admitted
stands even if the turn errors before any LLM spend: releasing it is
possible, but keeping it is the simpler fail-closed anti-abuse choice. Signed-in accounts claim a
separate per-user daily ceiling in ``registered_compute_ceiling``.
Nothing here is rendered or promised.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import Request
from loguru import logger

from argus.api import state as api_state
from argus.api.chat.registered_compute_ceiling import (
    check_registered_compute_ceiling,
)
from argus.api.dependencies import dev_memory_fallback_enabled, problem
from argus.api.guest_access import AccountContext, account_context, client_identity
from argus.api.schemas import User
from argus.domain.usage_limits import (
    COMPUTE_CLAIM_UNAVAILABLE_DETAIL,
    COMPUTE_CLAIM_UNAVAILABLE_RETRY_AFTER_SECONDS,
    COMPUTE_TURN_CEILING_DETAIL,
    GUEST_COMPUTE_CEILING_RESOURCE,
    align_usage_period,
    guest_compute_ceiling_limits,
    guest_session_ceiling_limits,
)
from argus.domain.visitor_usage import (
    guest_session_compute_key,
    memory_visitor_within_limits,
    settle_memory_visitor_usage,
    visitor_key_for,
)

_MEMORY_CLAIM_LOCK = threading.Lock()


@dataclass(frozen=True)
class GuestComputeAdmission:
    available: bool
    visitor_exhausted: bool = False
    session_exhausted: bool = False
    error: bool = False


def claim_guest_compute_turn(
    *,
    visitor_key: str,
    session_key: str,
) -> GuestComputeAdmission:
    """Atomically claim one visitor unit and one session unit, or neither."""
    now = datetime.now(timezone.utc)
    visitor_limits = guest_compute_ceiling_limits()
    session_limits = guest_session_ceiling_limits()
    try:
        if api_state.supabase_gateway is not None:
            return _claim_supabase_guest_compute(
                visitor_key=visitor_key,
                session_key=session_key,
                visitor_limits=visitor_limits,
                session_limits=session_limits,
            )
        return _claim_memory_guest_compute(
            visitor_key=visitor_key,
            session_key=session_key,
            visitor_limits=visitor_limits,
            session_limits=session_limits,
            now=now,
        )
    except Exception as exc:
        if dev_memory_fallback_enabled() and api_state.supabase_gateway is not None:
            logger.warning(
                "Guest compute claim failed; using dev memory fallback",
                error=str(exc),
            )
            try:
                return _claim_memory_guest_compute(
                    visitor_key=visitor_key,
                    session_key=session_key,
                    visitor_limits=visitor_limits,
                    session_limits=session_limits,
                    now=now,
                )
            except Exception as memory_exc:
                logger.warning(
                    "Guest compute memory claim failed; "
                    "returning claim unavailable",
                    error=str(memory_exc),
                )
                return GuestComputeAdmission(available=False, error=True)
        logger.warning(
            "Guest compute claim failed; returning claim unavailable",
            error=str(exc),
        )
        return GuestComputeAdmission(available=False, error=True)


def check_guest_compute_ceiling(request: Request, user: User) -> None:
    """Claim one turn before model work; 429 once either daily ceiling is reached.

    Guests claim the visitor and session ceilings. Signed-in accounts claim
    the per-user daily ceiling. Both refusals raise the same 429 copy.
    """
    context = account_context(request)
    if context.kind != "guest":
        check_registered_compute_ceiling(request, user)
        return
    now = datetime.now(timezone.utc)
    admission = claim_guest_compute_turn(
        visitor_key=visitor_key_for(client_identity(request)),
        session_key=guest_session_compute_key(context.user_id),
    )
    if admission.available:
        return
    if admission.error:
        logger.warning(
            "Guest compute claim unavailable",
            user_id=user.id,
            failure_classification="claim_unavailable",
        )
        raise problem(
            request,
            status_code=503,
            code="guest_compute_claim_unavailable",
            title="Service Temporarily Unavailable",
            detail=COMPUTE_CLAIM_UNAVAILABLE_DETAIL,
            headers={
                "Retry-After": str(COMPUTE_CLAIM_UNAVAILABLE_RETRY_AFTER_SECONDS),
            },
        )
    _, day_end = align_usage_period(now, "day")
    logger.warning(
        "Guest compute ceiling reached",
        user_id=user.id,
        failure_classification="abuse_ceiling",
        visitor_exhausted=admission.visitor_exhausted,
        session_exhausted=admission.session_exhausted,
    )
    raise problem(
        request,
        status_code=429,
        code="too_many_requests",
        title="Too Many Requests",
        detail=COMPUTE_TURN_CEILING_DETAIL,
        headers={"Retry-After": str(max(int((day_end - now).total_seconds()), 1))},
    )


def guest_compute_settlement(
    account: AccountContext,
    *,
    is_run_backtest_turn: bool,
    visitor_key: str,
) -> dict[str, object] | None:
    """The unit is claimed before model work. Terminal settlement is a no-op so
    a completed turn cannot double-count, and a failed turn keeps the claim."""
    del account, is_run_backtest_turn, visitor_key
    return None


def _claim_supabase_guest_compute(
    *,
    visitor_key: str,
    session_key: str,
    visitor_limits: list[tuple[str, int]],
    session_limits: list[tuple[str, int]],
) -> GuestComputeAdmission:
    gateway = api_state.supabase_gateway
    if gateway is None:
        raise RuntimeError("Supabase gateway is required for the durable claim.")
    client = gateway.client
    result = client.rpc(
        "claim_guest_compute_usage",
        {
            "p_visitor_key": visitor_key,
            "p_session_key": session_key,
            "p_resource": GUEST_COMPUTE_CEILING_RESOURCE,
            "p_visitor_limit": dict(visitor_limits)["day"],
            "p_session_limit": dict(session_limits)["day"],
        },
    ).execute()
    payload = getattr(result, "data", None)
    if not isinstance(payload, dict):
        raise TypeError("Guest compute claim returned no object")
    return GuestComputeAdmission(
        available=payload.get("available") is True,
        visitor_exhausted=payload.get("visitor_exhausted") is True,
        session_exhausted=payload.get("session_exhausted") is True,
    )


def _claim_memory_guest_compute(
    *,
    visitor_key: str,
    session_key: str,
    visitor_limits: list[tuple[str, int]],
    session_limits: list[tuple[str, int]],
    now: datetime,
) -> GuestComputeAdmission:
    """Process-local twin of claim_guest_compute_usage."""
    counters: dict[tuple[str, str, str], dict[str, Any]] = (
        api_state.store.visitor_usage_counters
    )
    with _MEMORY_CLAIM_LOCK:
        visitor_within = memory_visitor_within_limits(
            counters,
            visitor_key=visitor_key,
            resource=GUEST_COMPUTE_CEILING_RESOURCE,
            limits=list(visitor_limits),
            now=now,
        )
        session_within = memory_visitor_within_limits(
            counters,
            visitor_key=session_key,
            resource=GUEST_COMPUTE_CEILING_RESOURCE,
            limits=list(session_limits),
            now=now,
        )
        if not visitor_within or not session_within:
            return GuestComputeAdmission(
                available=False,
                visitor_exhausted=not visitor_within,
                session_exhausted=not session_within,
            )
        settle_memory_visitor_usage(
            counters,
            visitor_key=visitor_key,
            resource=GUEST_COMPUTE_CEILING_RESOURCE,
            limits=list(visitor_limits),
            now=now,
        )
        settle_memory_visitor_usage(
            counters,
            visitor_key=session_key,
            resource=GUEST_COMPUTE_CEILING_RESOURCE,
            limits=list(session_limits),
            now=now,
        )
        return GuestComputeAdmission(available=True)
