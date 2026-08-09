"""Research rail metering: one flat meter for users, rich classes underneath.

For a signed-in account, research turns count as ordinary chat turns (spec
section 9) and the message allowance is the meter. A guest is the exception
(section 9b): ten free messages spent entirely on the most expensive shape is
not an allowance anyone sized, so a guest carries a small research allowance of
their own, keyed to the visitor. What this module owns:

- the shared global daily ceiling, a circuit breaker charged per provider
  attempt, readable before the turn and settled after it;
- the guest's own daily research allowance, read beside the ceiling and
  charged beside it, so both bounds settle from one place;
- capability-class instrumentation per research turn (fast_quote,
  balanced_lookup, thorough_research, screening, peer_expansion), recorded on
  the cost ledger whether or not a provider call happened, because the class
  mix is what makes natural tiers visible later.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from argus.api import state as api_state
from argus.domain.research.config import research_rail_enabled
from argus.domain.usage_limits import (
    GLOBAL_RESEARCH_CEILING_SUBJECT,
    GUEST_RESEARCH_VISITOR_LIMITS,
    QuotaExceededError,
    align_usage_period,
    global_research_daily_ceiling,
    read_memory_usage,
    settle_memory_usage,
)
from argus.domain.visitor_usage import (
    memory_visitor_within_limits,
    settle_memory_visitor_usage,
    settle_visitor_usage,
    visitor_key_for,
    visitor_within_limits,
)

RESEARCH_USAGE_RESOURCE = "research_searches"
# Charged against the visitor table when Supabase is live for the same reason
# as discovery: usage_counters.user_id FKs to profiles, so a synthetic global
# subject there would fail to insert and the ceiling would silently never trip.
GLOBAL_CEILING_KEY = "global:research"


def _ceiling_limits() -> list[tuple[str, int]]:
    return [("day", global_research_daily_ceiling())]


@dataclass(frozen=True)
class ResearchAllowance:
    """Which bound a turn is under, so the honest note can name the real one.

    ``guest_exhausted`` is only ever set with ``available`` false: a guest who
    spent their own allowance must not be told the shared capacity ran out,
    and a shared outage must not be blamed on the guest.
    """

    available: bool
    guest_exhausted: bool = False


def guest_research_visitor_key(
    *, is_guest: bool, client_identity: str | None
) -> str | None:
    """The subject a guest's research is charged against, or None for a user.

    Computed once at the request edge so everything downstream carries the
    keyed digest rather than the address, including the job row a background
    run settles from long after the request is gone.
    """
    return visitor_key_for(client_identity) if is_guest else None


def research_allowance_for_turn(
    user_id: str,
    *,
    guest_visitor_key: str | None = None,
) -> ResearchAllowance:
    """Backend-derived pre-turn allowance truth. A read, not a charge.

    Two bounds, both read here: the shared global circuit breaker, and, for a
    guest, that visitor's own daily research allowance. A signed-in user still
    meters research through their message allowance (spec section 9); a guest
    does not, because ten free messages spent entirely on the most expensive
    shape is not an allowance anyone sized.

    Flag-off short-circuits to available so ordinary turns never pay the read.
    Fails closed: without readable truth, no research spend is allowed, and
    the turn still answers through the honest exhausted path.
    """
    del user_id
    if not research_rail_enabled():
        return ResearchAllowance(available=True)
    now = datetime.now(timezone.utc)
    try:
        if api_state.supabase_gateway is not None:
            client = api_state.supabase_gateway.client
            if not visitor_within_limits(
                client,
                visitor_key=GLOBAL_CEILING_KEY,
                resource=RESEARCH_USAGE_RESOURCE,
                limits=_ceiling_limits(),
                now=now,
            ):
                return ResearchAllowance(available=False)
            if guest_visitor_key is None:
                return ResearchAllowance(available=True)
            within = visitor_within_limits(
                client,
                visitor_key=guest_visitor_key,
                resource=RESEARCH_USAGE_RESOURCE,
                limits=list(GUEST_RESEARCH_VISITOR_LIMITS),
                now=now,
            )
            return ResearchAllowance(available=within, guest_exhausted=not within)
        if not _memory_ceiling_available(now=now):
            return ResearchAllowance(available=False)
        if guest_visitor_key is None:
            return ResearchAllowance(available=True)
        within = memory_visitor_within_limits(
            api_state.store.visitor_usage_counters,
            visitor_key=guest_visitor_key,
            resource=RESEARCH_USAGE_RESOURCE,
            limits=list(GUEST_RESEARCH_VISITOR_LIMITS),
            now=now,
        )
        return ResearchAllowance(available=within, guest_exhausted=not within)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Research allowance read failed; treating capacity as exhausted",
            error=str(exc),
        )
        return ResearchAllowance(available=False)


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


def charge_research_ceiling(*, guest_visitor_key: str | None = None) -> None:
    """One unit per provider attempt, usable or not; cache hits never charge.

    A guest's attempt charges their own allowance as well as the shared
    breaker, through the same settlement the read above checks.
    """
    try:
        if api_state.supabase_gateway is not None:
            settle_visitor_usage(
                api_state.supabase_gateway.client,
                visitor_key=GLOBAL_CEILING_KEY,
                resource=RESEARCH_USAGE_RESOURCE,
                limits=_ceiling_limits(),
            )
            if guest_visitor_key is not None:
                settle_visitor_usage(
                    api_state.supabase_gateway.client,
                    visitor_key=guest_visitor_key,
                    resource=RESEARCH_USAGE_RESOURCE,
                    limits=list(GUEST_RESEARCH_VISITOR_LIMITS),
                )
            return
        settle_memory_usage(
            api_state.store.usage_counters,
            user_id=GLOBAL_RESEARCH_CEILING_SUBJECT,
            resource=RESEARCH_USAGE_RESOURCE,
            limits=_ceiling_limits(),
        )
        if guest_visitor_key is not None:
            settle_memory_visitor_usage(
                api_state.store.visitor_usage_counters,
                visitor_key=guest_visitor_key,
                resource=RESEARCH_USAGE_RESOURCE,
                limits=list(GUEST_RESEARCH_VISITOR_LIMITS),
            )
    except QuotaExceededError:
        logger.info(
            "Research attempt settled at the global ceiling",
            resource=RESEARCH_USAGE_RESOURCE,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Research ceiling settlement failed",
            error=str(exc),
            failure_classification="telemetry_only",
        )


def settle_research_turn(
    runtime_result: dict[str, Any],
    *,
    user_id: str,
    conversation_id: str | None,
    message_id: str | None,
    request_id: str | None,
    guest_visitor_key: str | None = None,
) -> None:
    """Post-terminal settlement for a turn that may carry a research sidecar."""
    research = runtime_result.get("research")
    if not isinstance(research, dict):
        return
    record_research_turn_evidence(
        research=research,
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message_id,
        request_id=request_id,
        guest_visitor_key=guest_visitor_key,
    )


def record_research_turn_evidence(
    *,
    research: Any,
    user_id: str,
    conversation_id: str | None,
    message_id: str | None,
    request_id: str | None,
    guest_visitor_key: str | None = None,
) -> None:
    """Post-terminal, best-effort: settle the ceiling for provider attempts
    and append one capability-classed ledger row for every research turn."""
    if not isinstance(research, dict):
        return
    usage = research.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    cache_status = str(usage.get("cache_status") or "miss")
    if cache_status == "miss":
        charge_research_ceiling(guest_visitor_key=guest_visitor_key)
    _append_ledger_row(
        research=research,
        usage=usage,
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message_id,
        request_id=request_id,
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
