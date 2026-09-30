"""Current logical spending and its contributors share one inclusion decision."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Spending:
    contributors: list[dict[str, Any]]
    purchases: int
    refunds: int

    @property
    def net(self) -> int:
        return self.purchases - self.refunds


def spending(
    activities: list[dict[str, Any]],
    *,
    currency: str,
    start: datetime,
    end: datetime,
    account_ids: set[str] | None = None,
    category_ids: set[str] | None = None,
    include_uncategorized: bool = False,
) -> Spending:
    by_id = {a["activity_id"]: a for a in activities}
    contributors = []
    for item in activities:
        if item["kind"] not in {"expense", "refund"} or item["currency"] != currency:
            continue
        if not start <= item["occurred_at"] < end:
            continue
        original = (
            by_id.get(item["purchase_activity_id"]) if item["kind"] == "refund" else None
        )
        scope = original if original is not None else item
        if account_ids is not None and scope["legs"][0]["account_id"] not in account_ids:
            continue
        if category_ids is not None:
            category = scope["category_id"]
            if category not in category_ids and not (
                category is None and include_uncategorized
            ):
                continue
        contributors.append(item)
    contributors.sort(key=lambda a: (a["occurred_at"], a["activity_id"]), reverse=True)
    return Spending(
        contributors,
        sum(a["amount_minor"] for a in contributors if a["kind"] == "expense"),
        sum(a["amount_minor"] for a in contributors if a["kind"] == "refund"),
    )
