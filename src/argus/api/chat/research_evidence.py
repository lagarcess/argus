"""Research rail metering: one flat meter for users, rich classes underneath.

For a signed-in account, research turns count as ordinary chat turns (spec
section 9) and the message allowance is the meter. A guest is the exception
(section 9b): ten free messages spent entirely on the most expensive shape is
not an allowance anyone sized, so a guest carries a small research allowance of
their own, keyed to the visitor. What this module owns:

- the shared global daily ceiling, atomically claimed immediately before a
  cache miss enters provider work;
- the guest's own daily research allowance, claimed in that same transaction,
  so concurrent turns can never spend one remaining slot twice;
- capability-class instrumentation per research turn (fast_quote,
  balanced_lookup, thorough_research, screening, peer_expansion), recorded on
  the cost ledger whether or not a provider call happened, because the class
  mix is what makes natural tiers visible later.
- a bounded PostHog research event from that same sidecar, including degraded
  outcomes; analytics delivery is independent of ledger availability.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from argus.api import state as api_state
from argus.domain.research.admission import ResearchAttemptAdmission
from argus.domain.research.config import research_rail_enabled
from argus.domain.usage_limits import (
    GLOBAL_RESEARCH_CEILING_SUBJECT,
    GUEST_RESEARCH_VISITOR_LIMITS,
    align_usage_period,
    global_research_daily_ceiling,
    read_memory_usage,
    settle_memory_usage,
)
from argus.domain.visitor_usage import (
    memory_visitor_within_limits,
    settle_memory_visitor_usage,
    visitor_key_for,
)
from argus.observability.research_events import capture_research_turn_event

RESEARCH_USAGE_RESOURCE = "research_searches"
# Charged against the visitor table when Supabase is live for the same reason
# as discovery: usage_counters.user_id FKs to profiles, so a synthetic global
# subject there would fail to insert and the ceiling would silently never trip.
GLOBAL_CEILING_KEY = "global:research"
_MEMORY_CLAIM_LOCK = threading.Lock()


def _ceiling_limits() -> list[tuple[str, int]]:
    return [("day", global_research_daily_ceiling())]


def guest_research_visitor_key(
    *, is_guest: bool, client_identity: str | None
) -> str | None:
    """The subject a guest's research is charged against, or None for a user.

    Computed once at the request edge so everything downstream carries the
    keyed digest rather than the address, including the job row a background
    run settles from long after the request is gone.
    """
    return visitor_key_for(client_identity) if is_guest else None


def claim_research_provider_attempt(
    *,
    guest_visitor_key: str | None = None,
) -> ResearchAttemptAdmission:
    """Atomically claim capacity immediately before billable provider work.

    Two bounds are owned here: the shared global circuit breaker, and, for a
    guest, that visitor's own daily research allowance. A signed-in user still
    meters research through their message allowance (spec section 9); a guest
    does not, because ten free messages spent entirely on the most expensive
    shape is not an allowance anyone sized.

    Flag-off short-circuits to available. Fails closed: without writable truth,
    no research spend is allowed, and
    the turn still answers through the honest exhausted path.
    """
    if not research_rail_enabled():
        return ResearchAttemptAdmission(available=True)
    now = datetime.now(timezone.utc)
    try:
        if api_state.supabase_gateway is not None:
            client = api_state.supabase_gateway.client
            result = client.rpc(
                "claim_research_usage",
                {
                    "p_guest_visitor_key": guest_visitor_key,
                    "p_resource": RESEARCH_USAGE_RESOURCE,
                    "p_global_visitor_key": GLOBAL_CEILING_KEY,
                    "p_global_limit": global_research_daily_ceiling(),
                    "p_guest_limit": GUEST_RESEARCH_VISITOR_LIMITS[0][1],
                },
            ).execute()
            payload = getattr(result, "data", None)
            if not isinstance(payload, dict):
                raise TypeError("Research usage claim returned no object")
            return ResearchAttemptAdmission(
                available=payload.get("available") is True,
                guest_exhausted=payload.get("guest_exhausted") is True,
            )
        return _claim_memory_research_usage(
            guest_visitor_key=guest_visitor_key,
            now=now,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Research allowance claim failed; treating capacity as exhausted",
            error=str(exc),
        )
        return ResearchAttemptAdmission(available=False)


def _claim_memory_research_usage(
    *,
    guest_visitor_key: str | None,
    now: datetime,
) -> ResearchAttemptAdmission:
    """Process-local twin of the database transaction used in tests/dev."""

    with _MEMORY_CLAIM_LOCK:
        if guest_visitor_key is not None:
            guest_within = memory_visitor_within_limits(
                api_state.store.visitor_usage_counters,
                visitor_key=guest_visitor_key,
                resource=RESEARCH_USAGE_RESOURCE,
                limits=list(GUEST_RESEARCH_VISITOR_LIMITS),
                now=now,
            )
            if not guest_within:
                return ResearchAttemptAdmission(
                    available=False,
                    guest_exhausted=True,
                )
        if not _memory_ceiling_available(now=now):
            return ResearchAttemptAdmission(available=False)
        settle_memory_usage(
            api_state.store.usage_counters,
            user_id=GLOBAL_RESEARCH_CEILING_SUBJECT,
            resource=RESEARCH_USAGE_RESOURCE,
            limits=_ceiling_limits(),
            at=now,
        )
        if guest_visitor_key is not None:
            settle_memory_visitor_usage(
                api_state.store.visitor_usage_counters,
                visitor_key=guest_visitor_key,
                resource=RESEARCH_USAGE_RESOURCE,
                limits=list(GUEST_RESEARCH_VISITOR_LIMITS),
                now=now,
            )
        return ResearchAttemptAdmission(available=True)


def _memory_ceiling_available(*, now: datetime) -> bool:
    for period, limit_count in _ceiling_limits():
        start, _ = align_usage_period(now, period)
        row = read_memory_usage(
            api_state.store.usage_counters,
            user_id=GLOBAL_RESEARCH_CEILING_SUBJECT,
            resource=RESEARCH_USAGE_RESOURCE,
            period=period,
        )
        if (
            row is not None
            and row.get("period_start") == start
            and int(row.get("used_count", 0)) >= limit_count
        ):
            return False
    return True


def settle_research_turn(
    runtime_result: dict[str, Any],
    *,
    user_id: str,
    conversation_id: str | None,
    message_id: str | None,
    request_id: str | None,
) -> None:
    """Post-terminal evidence for a turn that may carry a research sidecar."""
    research = runtime_result.get("research")
    if not isinstance(research, dict):
        return
    record_research_turn_evidence(
        research=research,
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message_id,
        request_id=request_id,
    )


def record_research_turn_evidence(
    *,
    research: Any,
    user_id: str,
    conversation_id: str | None,
    message_id: str | None,
    request_id: str | None,
) -> None:
    """Append one capability-classed ledger row for every research turn."""
    if not isinstance(research, dict):
        return
    usage = research.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    _append_ledger_row(
        research=research,
        usage=usage,
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message_id,
        request_id=request_id,
    )
    capture_research_turn_event(
        research=research,
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message_id,
    )


def _append_ledger_row(
    *,
    research: dict[str, Any],
    usage: dict[str, Any],
    user_id: str,
    conversation_id: str | None,
    message_id: str | None,
    request_id: str | None,
) -> None:
    gateway = api_state.supabase_gateway
    if gateway is None:
        return
    capability_class = str(research.get("capability_class") or "unknown")
    correlation_id = request_id or message_id or conversation_id or user_id
    degraded = research.get("degraded")
    entry = {
        "source": "research",
        "service": "perplexity_agent",
        "provider": "perplexity_agent",
        "feature_area": "research_rail",
        "task": capability_class,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "message_id": message_id,
        "request_id": request_id,
        "correlation_id": f"research:{correlation_id}",
        "usage_metadata": {
            "capability_class": capability_class,
            "shape": research.get("shape"),
            "cache_status": cache_status_of(usage),
            "invocations": usage.get("invocations"),
            **(
                {"degraded_code": degraded.get("code")}
                if isinstance(degraded, dict) and degraded.get("code")
                else {}
            ),
        },
        "billable_unit": "request",
        "billable_quantity": 1 if cache_status_of(usage) == "miss" else 0,
        "cost_amount": usage.get("cost_usd"),
        "cost_source": (
            "provider_reported" if usage.get("cost_usd") is not None else "unavailable"
        ),
        "latency_ms": usage.get("latency_ms"),
        "status": "succeeded",
    }
    try:
        gateway.create_cost_ledger_entry(entry=entry)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Research cost ledger persistence failed",
            error=str(exc),
            failure_classification="telemetry_only",
        )


def cache_status_of(usage: dict[str, Any]) -> str:
    return str(usage.get("cache_status") or "miss")
