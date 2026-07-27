from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from loguru import logger

from argus.api import state as api_state
from argus.domain.discovery_search import discovery_search_config
from argus.domain.usage_counter_reader import UsageCounterReader, align_usage_period
from argus.domain.usage_limits import (
    QuotaExceededError,
    read_memory_usage,
    settle_memory_usage,
)

DISCOVERY_USAGE_RESOURCE = "discovery_searches"


def discovery_usage_limits() -> list[tuple[str, int]]:
    config = discovery_search_config()
    return [("hour", config.hourly_limit), ("day", config.daily_limit)]


def discovery_allowance_available(user_id: str) -> bool:
    """Backend-derived pre-turn availability truth for grounded discovery.

    A read, not a charge: settlement happens only after a Search attempt.
    Flag-off short-circuits to True so ordinary turns never pay the read.
    """

    config = discovery_search_config()
    if not config.enabled:
        return True
    now = datetime.now(timezone.utc)
    try:
        if api_state.supabase_gateway is not None:
            reader = UsageCounterReader()
            reader.client = api_state.supabase_gateway.client
            for period, limit_count in discovery_usage_limits():
                rows = reader.list_current_usage_counters(
                    user_id=user_id,
                    resources=(DISCOVERY_USAGE_RESOURCE,),
                    period=period,
                    at=now,
                )
                used = int(rows[0].get("used_count", 0)) if rows else 0
                if used >= limit_count:
                    return False
            return True
        for period, limit_count in discovery_usage_limits():
            start, _ = align_usage_period(now, period)
            row = read_memory_usage(
                api_state.store.usage_counters,
                user_id=user_id,
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
) -> None:
    """Charge the attempt counter and append the research spend row.

    Best-effort attempt accounting after the terminal message commits; failures
    are logged and never break the user turn.
    """

    if not isinstance(usage, dict) or usage.get("search_attempted") is not True:
        return
    _charge_discovery_attempt(user_id=user_id)
    _append_research_ledger_row(
        usage=usage,
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message_id,
        request_id=request_id,
    )


def _charge_discovery_attempt(*, user_id: str) -> None:
    limits = discovery_usage_limits()
    try:
        if api_state.supabase_gateway is not None:
            api_state.supabase_gateway.check_and_increment_usage_limits(
                user_id=user_id,
                resource=DISCOVERY_USAGE_RESOURCE,
                limits=limits,
            )
        else:
            settle_memory_usage(
                api_state.store.usage_counters,
                user_id=user_id,
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
