from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from argus.api import state as api_state
from argus.domain.discovery_search import discovery_search_config
from argus.domain.usage_counter_reader import UsageCounterReader, align_usage_period
from argus.domain.usage_limits import (
    GLOBAL_DISCOVERY_CEILING_SUBJECT,
    GUEST_DISCOVERY_ALLOWANCE_LIMITS,
    QuotaExceededError,
    global_discovery_daily_ceiling,
    read_memory_usage,
    settle_memory_usage,
)

DISCOVERY_USAGE_RESOURCE = "discovery_searches"
# Namespaced so a visitor key can never be mistaken for an account id.
_GUEST_SUBJECT_PREFIX = "visitor:"
# The global ceiling is charged against the same non-account table as visitors.
# usage_counters.user_id is a foreign key to profiles, so a synthetic global
# subject there fails to insert, the failure is swallowed as telemetry, and the
# ceiling silently never trips.
GLOBAL_CEILING_KEY = "global:discovery"


def _visitor_digest(identity: str) -> str:
    """Keyed digest of a visitor identifier, never the raw value.

    The counter only needs to tell visitors apart, not to name them. A raw IP
    in a primary key is a durable record of who visited; a keyed digest carries
    the same signal without retaining the address. Keyed rather than plain
    because an IPv4 space is small enough to brute-force a bare hash.
    """
    secret = os.getenv("ARGUS_VISITOR_KEY_SECRET", "argus-visitor-key").encode()
    return hmac.new(secret, identity.encode(), hashlib.sha256).hexdigest()[:32]


def discovery_usage_limits(*, is_guest: bool = False) -> list[tuple[str, int]]:
    if is_guest:
        return list(GUEST_DISCOVERY_ALLOWANCE_LIMITS)
    config = discovery_search_config()
    return [("hour", config.hourly_limit), ("day", config.daily_limit)]


def discovery_counter_subject(
    *,
    user_id: str,
    is_guest: bool,
    client_identity: str | None,
) -> str:
    """Who the discovery allowance is charged against.

    A registered account is a durable identity, so it is its own subject. A
    guest workspace is not: it lives ten minutes and renewal mints a fresh
    user_id, so charging a guest by user_id hands out a new allowance on a
    timer. Guests are charged against the visitor instead.

    Fails closed to a single shared bucket when the client identity is
    unavailable, because an unmetered allowance is the worse failure.
    """

    if not is_guest:
        return user_id
    identity = (client_identity or "").strip() or "unknown"
    return f"{_GUEST_SUBJECT_PREFIX}{_visitor_digest(identity)}"


VISITOR_USAGE_TABLE = "visitor_usage_counters"


def _visitor_within_limits(
    *,
    visitor_key: str,
    limits: list[tuple[str, int]],
    now: datetime,
) -> bool:
    """Visitor allowances live outside usage_counters.

    usage_counters.user_id is a foreign key to profiles, so it can only express
    an account-owned allowance. A visitor has no account, and keying a guest by
    its workspace user_id would reset the allowance every renewal.
    """
    client = api_state.supabase_gateway.client
    for period, limit_count in limits:
        start, _ = align_usage_period(now, period)
        rows = (
            client.table(VISITOR_USAGE_TABLE)
            .select("used_count")
            .eq("visitor_key", visitor_key)
            .eq("resource", DISCOVERY_USAGE_RESOURCE)
            .eq("period", period)
            .eq("period_start", start.isoformat())
            .limit(1)
            .execute()
            .data
        )
        used = int(rows[0].get("used_count", 0)) if rows else 0
        if used >= limit_count:
            return False
    return True


def _charge_visitor(*, visitor_key: str, limits: list[tuple[str, int]]) -> None:
    now = datetime.now(timezone.utc)
    windows = []
    for period, limit_count in limits:
        start, end = align_usage_period(now, period)
        windows.append(
            {
                "period": period,
                "limit": limit_count,
                "period_start": start.isoformat(),
                "period_end": end.isoformat(),
            }
        )
    api_state.supabase_gateway.client.rpc(
        "settle_visitor_usage",
        {
            "p_visitor_key": visitor_key,
            "p_resource": DISCOVERY_USAGE_RESOURCE,
            "p_windows": windows,
        },
    ).execute()


def _global_ceiling_available(*, now: datetime) -> bool:
    """The ceiling is charged where a non-account subject can actually persist."""
    limits = [("day", global_discovery_daily_ceiling())]
    if api_state.supabase_gateway is not None:
        return _visitor_within_limits(
            visitor_key=GLOBAL_CEILING_KEY, limits=limits, now=now
        )
    return _subject_within_limits(
        subject=GLOBAL_DISCOVERY_CEILING_SUBJECT, limits=limits, now=now
    )


def _charge_global_ceiling() -> None:
    limits = [("day", global_discovery_daily_ceiling())]
    try:
        if api_state.supabase_gateway is not None:
            _charge_visitor(visitor_key=GLOBAL_CEILING_KEY, limits=limits)
            return
    except Exception as exc:
        logger.warning(
            "Global discovery ceiling settlement failed",
            error=str(exc),
            failure_classification="telemetry_only",
        )
        return
    _charge_subject(subject=GLOBAL_DISCOVERY_CEILING_SUBJECT, limits=limits)


def _subject_within_limits(
    *,
    subject: str,
    limits: list[tuple[str, int]],
    now: datetime,
) -> bool:
    if api_state.supabase_gateway is not None:
        reader = UsageCounterReader()
        reader.client = api_state.supabase_gateway.client
        for period, limit_count in limits:
            rows = reader.list_current_usage_counters(
                user_id=subject,
                resources=(DISCOVERY_USAGE_RESOURCE,),
                period=period,
                at=now,
            )
            used = int(rows[0].get("used_count", 0)) if rows else 0
            if used >= limit_count:
                return False
        return True
    for period, limit_count in limits:
        start, _ = align_usage_period(now, period)
        row = read_memory_usage(
            api_state.store.usage_counters,
            user_id=subject,
            resource=DISCOVERY_USAGE_RESOURCE,
            period=period,
        )
        if (
            row is not None
            and row.get("period_start") == start
            and int(row.get("used_count", 0)) >= limit_count
        ):
            return False
    return True


def discovery_allowance_available(
    user_id: str,
    *,
    is_guest: bool = False,
    client_identity: str | None = None,
) -> bool:
    """Backend-derived pre-turn availability truth for grounded discovery.

    A read, not a charge: settlement happens only after a Search attempt.
    Flag-off short-circuits to True so ordinary turns never pay the read.

    Two independent bounds. The per-subject allowance shapes ordinary use; the
    global ceiling is what still holds when someone rotates identity faster
    than any per-subject limit can observe.
    """

    config = discovery_search_config()
    if not config.enabled:
        return True
    now = datetime.now(timezone.utc)
    try:
        if not _global_ceiling_available(now=now):
            logger.warning(
                "Grounded discovery stopped by the global daily ceiling",
                ceiling=global_discovery_daily_ceiling(),
            )
            return False
        subject = discovery_counter_subject(
            user_id=user_id, is_guest=is_guest, client_identity=client_identity
        )
        limits = discovery_usage_limits(is_guest=is_guest)
        if is_guest and api_state.supabase_gateway is not None:
            return _visitor_within_limits(
                visitor_key=subject, limits=limits, now=now
            )
        return _subject_within_limits(subject=subject, limits=limits, now=now)
    except Exception as exc:
        # Fail closed: without readable allowance truth, no spend is allowed.
        logger.warning(
            "Discovery allowance read failed; treating allowance as exhausted",
            error=str(exc),
        )
        return False


def record_discovery_search_evidence(
    *,
    usage: Any,
    user_id: str,
    conversation_id: str | None,
    message_id: str | None,
    request_id: str | None,
    is_guest: bool = False,
    client_identity: str | None = None,
) -> None:
    """Charge the attempt counter and append the research spend row.

    Best-effort attempt accounting after the terminal message commits; failures
    are logged and never break the user turn.
    """

    if not isinstance(usage, dict) or usage.get("search_attempted") is not True:
        return
    # Two bounds, two rules. The global ceiling counts every attempt because it
    # bounds provider spend and a failed call can still be billed. The user's
    # allowance is charged only for a usable result: a timeout, HTTP error, or
    # extraction/voicing failure is our outage, not the user's spend -- at a
    # guest allowance of two, one provider blip must not cost half of it.
    _charge_global_ceiling()
    if usage.get("fallback_code") is None:
        _charge_discovery_attempt(
            user_id=user_id,
            is_guest=is_guest,
            client_identity=client_identity,
        )
    _append_research_ledger_row(
        usage=usage,
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message_id,
        request_id=request_id,
    )


def _charge_discovery_attempt(
    *,
    user_id: str,
    is_guest: bool = False,
    client_identity: str | None = None,
) -> None:
    # The per-subject allowance only; the global ceiling is charged by the
    # caller on every attempt, usable or not.
    subject = discovery_counter_subject(
        user_id=user_id, is_guest=is_guest, client_identity=client_identity
    )
    limits = discovery_usage_limits(is_guest=is_guest)
    if is_guest and api_state.supabase_gateway is not None:
        try:
            _charge_visitor(visitor_key=subject, limits=limits)
        except Exception as exc:
            logger.warning(
                "Visitor discovery settlement failed",
                error=str(exc),
                failure_classification="telemetry_only",
            )
        return
    _charge_subject(subject=subject, limits=limits)


def _charge_subject(*, subject: str, limits: list[tuple[str, int]]) -> None:
    try:
        if api_state.supabase_gateway is not None:
            api_state.supabase_gateway.check_and_increment_usage_limits(
                user_id=subject,
                resource=DISCOVERY_USAGE_RESOURCE,
                limits=limits,
            )
        else:
            settle_memory_usage(
                api_state.store.usage_counters,
                user_id=subject,
                resource=DISCOVERY_USAGE_RESOURCE,
                limits=limits,
            )
    except QuotaExceededError:
        # Race edge: the pre-turn read passed and another turn used the last
        # unit. The attempt already happened; the counter stays clamped.
        logger.info(
            "Discovery attempt settled at the allowance ceiling",
            resource=DISCOVERY_USAGE_RESOURCE,
        )
    except Exception as exc:
        logger.warning(
            "Discovery usage settlement failed",
            error=str(exc),
            failure_classification="telemetry_only",
        )


def _append_research_ledger_row(
    *,
    usage: dict[str, Any],
    user_id: str,
    conversation_id: str | None,
    message_id: str | None,
    request_id: str | None,
) -> None:
    gateway = api_state.supabase_gateway
    if gateway is None:
        return
    provider_id = str(usage.get("provider_id") or "unknown")
    correlation_id = request_id or message_id or conversation_id or user_id
    entry = {
        "source": "research",
        "service": provider_id,
        "provider": provider_id,
        "feature_area": "discovery",
        "task": "discovery_search",
        "user_id": user_id,
        "conversation_id": conversation_id,
        "message_id": message_id,
        "request_id": request_id,
        "correlation_id": f"discovery:{correlation_id}",
        "usage_metadata": {
            key: usage.get(key)
            for key in (
                "result_count",
                "extracted_count",
                "validated_count",
                "unverified_count",
                "fallback_code",
            )
            if usage.get(key) is not None
        },
        "billable_unit": "request",
        "billable_quantity": 1,
        "cost_amount": usage.get("cost_usd"),
        "cost_source": (
            "provider_reported" if usage.get("cost_usd") is not None else "unavailable"
        ),
        "latency_ms": usage.get("latency_ms"),
        "status": "succeeded" if usage.get("fallback_code") is None else "failed",
    }
    try:
        gateway.create_cost_ledger_entry(entry=entry)
    except Exception as exc:
        logger.warning(
            "Discovery cost ledger persistence failed",
            error=str(exc),
            failure_classification="telemetry_only",
        )
