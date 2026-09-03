"""Private invoice anomalies; the API owns the optional persistence adapter."""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from typing import Any

from loguru import logger
from pydantic import BaseModel, ConfigDict

from argus.domain.research.contracts import ResearchPricingError, ResearchUsage


class UnpricedResearchSpend(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider_response_id: str | None
    usage: ResearchUsage
    reported_cost: dict[str, Any]
    reason: str
    detail: str
    reported_component_usd: float | None
    expected_min_usd: float | None
    expected_max_usd: float | None


UnpricedSpendRecorder = Callable[[UnpricedResearchSpend], None]
_recorder: UnpricedSpendRecorder | None = None


def set_unpriced_spend_recorder(recorder: UnpricedSpendRecorder | None) -> None:
    """Process-scoped adapter, installed and removed by the API lifespan."""
    global _recorder
    _recorder = recorder


def unpriced_spend(
    *, document: dict[str, Any], usage: ResearchUsage, error: ResearchPricingError
) -> UnpricedResearchSpend:
    """Allowlist billing numbers; never copy prompts, output or arbitrary metadata."""
    raw_usage = document.get("usage")
    raw_cost = raw_usage.get("cost") if isinstance(raw_usage, dict) else None
    cost = raw_cost if isinstance(raw_cost, dict) else {}
    amounts = {
        key: value
        for key in (
            "input_cost",
            "output_cost",
            "cache_creation_cost",
            "cache_read_cost",
            "tool_calls_cost",
            "total_cost",
        )
        if isinstance(value := cost.get(key), (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    }
    return UnpricedResearchSpend(
        provider_response_id=str(document.get("id") or "")[:200] or None,
        usage=usage,
        reported_cost={
            **amounts,
            "currency": "USD" if cost.get("currency") == "USD" else None,
        },
        reason=error.reason,
        detail=error.detail,
        reported_component_usd=float(error.reported)
        if error.reported is not None
        else None,
        expected_min_usd=float(error.expected_min)
        if error.expected_min is not None
        else None,
        expected_max_usd=float(error.expected_max)
        if error.expected_max is not None
        else None,
    )


def record_unpriced_spend(spend: UnpricedResearchSpend) -> None:
    # The deployed log sink drops structured extras. Keep safe evidence in
    # the message as well, even if persistence is unavailable.
    evidence = json.dumps(spend.model_dump(mode="json"), sort_keys=True)
    logger.error("research_cost_unpriced {}", evidence)
    if _recorder is None:
        logger.error("research_cost_unrecorded recorder=unconfigured {}", evidence)
        return
    try:
        _recorder(spend)
    except Exception:  # noqa: BLE001
        # An observer must never recreate the answer-blocking defect.
        logger.error("research_cost_unrecorded recorder=failed {}", evidence)
