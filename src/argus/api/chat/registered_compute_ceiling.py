"""Silent anti-abuse ceiling on signed-in compute turns.

Conversation is compute: free in the usage panel, never an allowance. A
signed-in account still cannot run unbounded LLM spend, so ordinary turns
claim one daily unit against ``user:<account id>`` at turn start. The unit
is claimed atomically before any model work, the same way guest compute
and research claim before spend. A claim that is admitted stands even if
the turn errors: releasing it is possible, but wiring a refund through
every errored chat path is not free, so the claim stays. Nothing here is
rendered or promised.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import Request
from loguru import logger

from argus.api import state as api_state
from argus.api.dependencies import dev_memory_fallback_enabled, problem
from argus.api.schemas import User
from argus.domain.usage_limits import (
    COMPUTE_CLAIM_UNAVAILABLE_DETAIL,
    COMPUTE_CLAIM_UNAVAILABLE_RETRY_AFTER_SECONDS,
    COMPUTE_TURN_CEILING_DETAIL,
    REGISTERED_COMPUTE_CEILING_RESOURCE,
    align_usage_period,
    registered_compute_ceiling_limits,
)
from argus.domain.visitor_usage import (
    memory_visitor_within_limits,
    registered_account_usage_key,
    settle_memory_visitor_usage,
)

_MEMORY_CLAIM_LOCK = threading.Lock()


@dataclass(frozen=True)
class RegisteredComputeAdmission:
    available: bool
    exhausted: bool = False
    error: bool = False


def claim_registered_compute_turn(*, account_key: str) -> RegisteredComputeAdmission:
    """Atomically claim one signed-in daily compute unit, or none."""
    now = datetime.now(timezone.utc)
    limits = registered_compute_ceiling_limits()
    try:
        if api_state.supabase_gateway is not None:
            return _claim_supabase_registered_compute(account_key=account_key, limits=limits)
        return _claim_memory_registered_compute(
            account_key=account_key, limits=limits, now=now
        )
    except Exception as exc:
        if dev_memory_fallback_enabled() and api_state.supabase_gateway is not None:
            logger.warning(
                "Registered compute claim failed; using dev memory fallback",
                error=str(exc),
            )
            try:
                return _claim_memory_registered_compute(
                    account_key=account_key, limits=limits, now=now
                )
            except Exception as memory_exc:
                logger.warning(
                    "Registered compute memory claim failed; "
                    "returning claim unavailable",
                    error=str(memory_exc),
                )
                return RegisteredComputeAdmission(available=False, error=True)
        logger.warning(
            "Registered compute claim failed; returning claim unavailable",
            error=str(exc),
        )
        return RegisteredComputeAdmission(available=False, error=True)


def check_registered_compute_ceiling(request: Request, user: User) -> None:
    """Claim one turn at entry; 429 once the daily ceiling is reached."""
    now = datetime.now(timezone.utc)
    admission = claim_registered_compute_turn(
        account_key=registered_account_usage_key(user.id),
    )
    if admission.available:
        return
    if admission.error:
        logger.warning(
            "Registered compute claim unavailable",
            user_id=user.id,
            failure_classification="claim_unavailable",
        )
        raise problem(
            request,
            status_code=503,
            code="registered_compute_claim_unavailable",
            title="Service Temporarily Unavailable",
            detail=COMPUTE_CLAIM_UNAVAILABLE_DETAIL,
            headers={
                "Retry-After": str(COMPUTE_CLAIM_UNAVAILABLE_RETRY_AFTER_SECONDS),
            },
        )
    _, day_end = align_usage_period(now, "day")
    logger.warning(
        "Registered compute ceiling reached",
        user_id=user.id,
        failure_classification="abuse_ceiling",
    )
    raise problem(
        request,
        status_code=429,
        code="too_many_requests",
        title="Too Many Requests",
        detail=COMPUTE_TURN_CEILING_DETAIL,
        headers={"Retry-After": str(max(int((day_end - now).total_seconds()), 1))},
    )


def _claim_supabase_registered_compute(
    *,
    account_key: str,
    limits: list[tuple[str, int]],
) -> RegisteredComputeAdmission:
    gateway = api_state.supabase_gateway
    if gateway is None:
        raise RuntimeError("Supabase gateway is required for the durable claim.")
    result = gateway.client.rpc(
        "claim_registered_compute_usage",
        {
            "p_account_key": account_key,
            "p_resource": REGISTERED_COMPUTE_CEILING_RESOURCE,
            "p_limit": dict(limits)["day"],
        },
    ).execute()
    payload = getattr(result, "data", None)
    if not isinstance(payload, dict):
        raise TypeError("Registered compute claim returned no object")
    return RegisteredComputeAdmission(
        available=payload.get("available") is True,
        exhausted=payload.get("available") is not True,
    )


def _claim_memory_registered_compute(
    *,
    account_key: str,
    limits: list[tuple[str, int]],
    now: datetime,
) -> RegisteredComputeAdmission:
    """Process-local twin of claim_registered_compute_usage."""
    counters: dict[tuple[str, str, str], dict[str, Any]] = (
        api_state.store.visitor_usage_counters
    )
    with _MEMORY_CLAIM_LOCK:
        within = memory_visitor_within_limits(
            counters,
            visitor_key=account_key,
            resource=REGISTERED_COMPUTE_CEILING_RESOURCE,
            limits=list(limits),
            now=now,
        )
        if not within:
            return RegisteredComputeAdmission(available=False, exhausted=True)
        settle_memory_visitor_usage(
            counters,
            visitor_key=account_key,
            resource=REGISTERED_COMPUTE_CEILING_RESOURCE,
            limits=list(limits),
            now=now,
        )
        return RegisteredComputeAdmission(available=True)
