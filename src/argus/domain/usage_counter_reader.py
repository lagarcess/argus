from __future__ import annotations

from datetime import datetime
from typing import Any

from argus.domain.usage_limits import align_usage_period

__all__ = ["UsageCounterReader", "align_usage_period"]


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
