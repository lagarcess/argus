from __future__ import annotations

from enum import Enum
from typing import Any

from argus.domain.tool_contracts import ToolResultCard


class RetryLifecycleDecision(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"

    def __str__(self) -> str:
        return self.value


SUPERSEDING_ARTIFACT_KINDS = frozenset(
    {
        "confirmation",
        "backtest_result",
        "saved_strategy",
        "cancelled_confirmation",
    }
)


def has_completed_tool_answer(metadata: dict[str, Any]) -> bool:
    """A failed or pending call does not consume an existing retry or approval."""
    raw = metadata.get("tool_result_cards")
    if not isinstance(raw, list):
        return False
    return any(tool_card_has_completed_answer(value) for value in raw)


def tool_card_has_completed_answer(value: Any) -> bool:
    try:
        card = ToolResultCard.model_validate(value)
    except ValueError:
        return False
    return card.outcome.status == "succeeded" and (
        card.presentation.answer is not None
        or card.presentation.narrative is not None
        or card.presentation.visual is not None
    )


def retry_lifecycle_after_artifact_event(
    *,
    retry_artifact_id: str | None,
    latest_failed_artifact_id: str | None,
    new_artifact_kind: str | None,
    new_tool_result: Any = None,
) -> RetryLifecycleDecision:
    if _artifact_kind(
        new_artifact_kind
    ) == "tool_result" and tool_card_has_completed_answer(new_tool_result):
        return RetryLifecycleDecision.SUPERSEDED
    if _artifact_kind(new_artifact_kind) in SUPERSEDING_ARTIFACT_KINDS:
        return RetryLifecycleDecision.SUPERSEDED
    if retry_artifact_id and latest_failed_artifact_id:
        if retry_artifact_id != latest_failed_artifact_id:
            return RetryLifecycleDecision.EXPIRED
    return RetryLifecycleDecision.ACTIVE


def _artifact_kind(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None
