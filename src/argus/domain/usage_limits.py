from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol


class QuotaExceededError(Exception):
    pass


USAGE_COUNTER_LOCK = threading.Lock()

# One backend-owned allowance policy. Routers, admission, settlement, and the
# usage read surface must reference these windows instead of local literals.
MESSAGE_ALLOWANCE_LIMITS: list[tuple[str, int]] = [("hour", 60), ("day", 200)]
SIMULATION_ALLOWANCE_LIMITS: list[tuple[str, int]] = [("hour", 10), ("day", 50)]

MESSAGE_USAGE_RESOURCE = "chat_messages"
SIMULATION_USAGE_RESOURCE = "backtest_runs"


def message_usage_settlement() -> dict[str, Any]:
    """One message unit settled with a durable terminal product outcome."""
    return {
        "resource": MESSAGE_USAGE_RESOURCE,
        "limits": list(MESSAGE_ALLOWANCE_LIMITS),
    }


def settle_memory_usage(
    counters: dict[tuple[str, str, str], dict[str, Any]],
    *,
    user_id: str,
    resource: str,
    limits: list[tuple[str, int]],
    at: datetime | None = None,
) -> None:
    """In-memory twin of the database-owned settlement charge."""
    now = at or datetime.now(timezone.utc)
    for period, limit_count in limits:
        start, end = align_usage_period(now, period)
        key = (user_id, resource, period)
        row = counters.get(key)
        if row is None or row.get("period_start") != start:
            counters[key] = {
                "period_start": start,
                "period_end": end,
                "used_count": 1,
                "limit_count": limit_count,
            }
        else:
            row["used_count"] = int(row.get("used_count", 0)) + 1
            row["limit_count"] = limit_count


def read_memory_usage(
    counters: dict[tuple[str, str, str], dict[str, Any]],
    *,
    user_id: str,
    resource: str,
    period: str,
    at: datetime | None = None,
) -> dict[str, Any] | None:
    now = at or datetime.now(timezone.utc)
    start, _ = align_usage_period(now, period)
    row = counters.get((user_id, resource, period))
    if row is None or row.get("period_start") != start:
        return None
    return dict(row)


class UsageLimitGateway(Protocol):
    client: Any


def align_usage_period(dt: datetime, period: str) -> tuple[datetime, datetime]:
    if period == "minute":
        start = dt.replace(second=0, microsecond=0)
        end = start + timedelta(minutes=1)
    elif period == "hour":
        start = dt.replace(minute=0, second=0, microsecond=0)
        end = start + timedelta(hours=1)
    else:  # day
        start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
    return start, end


def check_usage_limits(
    self: UsageLimitGateway,
    *,
    user_id: str,
    resource: str,
    limits: list[tuple[str, int]],
) -> None:
    """Reject exhausted limits without creating or incrementing counters."""
    if not limits:
        return
    now = datetime.now(timezone.utc)
    with USAGE_COUNTER_LOCK:
        for period, limit_count in limits:
            start, _ = align_usage_period(now, period)
            response = (
                self.client.table("usage_counters")
                .select("used_count")
                .eq("user_id", user_id)
                .eq("resource", resource)
                .eq("period", period)
                .eq("period_start", start.isoformat())
                .limit(1)
                .execute()
            )
            rows = getattr(response, "data", None) or []
            row = rows[0] if isinstance(rows, list) and rows else None
            current_used = int(row.get("used_count", 0)) if row else 0
            if current_used >= limit_count:
                raise QuotaExceededError(
                    f"Quota exceeded for {resource} ({period})"
                )
