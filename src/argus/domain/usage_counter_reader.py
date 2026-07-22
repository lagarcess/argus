from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


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


class UsageCounterReader:
    client: Any

    def list_current_usage_counters(
        self,
        *,
        user_id: str,
        resources: tuple[str, ...],
        period: str,
        at: datetime,
    ) -> list[dict[str, Any]]:
        if not resources:
            return []
        start, _ = align_usage_period(at, period)
        result = (
            self.client.table("usage_counters")
            .select("resource,limit_count,used_count,period_end")
            .eq("user_id", user_id)
            .eq("period", period)
            .eq("period_start", start.isoformat())
            .in_("resource", list(resources))
            .limit(len(resources))
            .execute()
        )
        return list(result.data or [])
