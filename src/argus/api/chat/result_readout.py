"""Composition eligibility for persisted result readouts, never a read hook."""

from argus.api.chat.breakdown import (
    ResultBreakdownMessage,
    result_breakdown_message_with_metadata,
)
from argus.api.schemas import BacktestRun
from argus.domain.result_readout_content import stored_readout_metadata


def compose_result_breakdown(
    run: BacktestRun | None, *, language: str = "en"
) -> ResultBreakdownMessage:
    if run is not None and not stored_readout_metadata(run.conversation_result_card):
        return ResultBreakdownMessage(
            text="",
            source="deterministic_fallback",
            fallback_used=True,
            failure_mode="legacy_result",
        )
    return result_breakdown_message_with_metadata(run, language=language)
