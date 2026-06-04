from __future__ import annotations

from enum import StrEnum


class RetryLifecycleDecision(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"


SUPERSEDING_ARTIFACT_KINDS = frozenset(
    {
        "confirmation",
        "backtest_result",
        "saved_strategy",
        "cancelled_confirmation",
    }
)


def retry_lifecycle_after_artifact_event(
    *,
    retry_artifact_id: str | None,
    latest_failed_artifact_id: str | None,
    new_artifact_kind: str | None,
) -> RetryLifecycleDecision:
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
