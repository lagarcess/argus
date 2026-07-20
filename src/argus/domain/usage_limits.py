from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol


class QuotaExceededError(Exception):
    pass


USAGE_COUNTER_LOCK = threading.Lock()


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
