"""The three shapes a latest-result follow-up answer takes.

A what-next follow-up answers with the result's Try next rows, any other
focus with the composer's prose under its typed heading, and both fall back
to the retryable recovery when nothing could be built.
"""

from __future__ import annotations

from typing import Any

from argus.agent_runtime.next_experiments import (
    next_experiments_lead_in,
    next_experiments_sidecar,
)
from argus.agent_runtime.recovery_messages import (
    recovery_message,
    recovery_state_stage_patch,
)
from argus.agent_runtime.response_style import result_followup_response_intent
from argus.agent_runtime.result_fact_enrichment import metric_number
from argus.agent_runtime.result_followups import (
    BENCHMARK_DELTA_METRIC_PATHS,
    MAX_DRAWDOWN_METRIC_PATHS,
)


def next_experiment_followup_patch(
    metadata: dict[str, Any],
    *,
    language: str = "en",
    source_run_id: str | None = None,
) -> dict[str, Any] | None:
    """Stage patch answering "what should I try next?" from the latest result.

    `next_experiments_sidecar` is the one owner of the rows (#590). An explicit
    ask gets the result's full offer: spec §4.3's non-repetition rule restrains
    unsolicited re-offers, not an answer to a question. The Try next section is
    the heading, so the patch carries no result chrome. The message has no
    card, so the sidecar names its run and a continuity row keeps its typed
    action. None when no row can be built.
    """
    sidecar = next_experiments_sidecar(
        metadata,
        benchmark_delta=metric_number(metadata, paths=BENCHMARK_DELTA_METRIC_PATHS),
        max_drawdown=metric_number(metadata, paths=MAX_DRAWDOWN_METRIC_PATHS),
        language=language,
        source_run_id=source_run_id,
    )
    if sidecar is None:
        return None
    return {
        "assistant_response": next_experiments_lead_in(language),
        "next_experiments": sidecar,
    }


def composed_result_followup_patch(
    response: str | None,
    *,
    focus: str,
) -> dict[str, Any] | None:
    """A composed answer wears the typed heading for its focus."""
    if response is None:
        return None
    return {
        "assistant_response": response,
        "response_intent": result_followup_response_intent(focus),
    }


def unavailable_result_followup_patch(*, language: str | None) -> dict[str, Any]:
    """Failure prose never wears result chrome; the recovery patch owns it."""
    return {
        "assistant_response": recovery_message(
            "latest_result_followup_unavailable",
            language=language,
        ),
        **recovery_state_stage_patch(
            "latest_result_followup_unavailable",
            language=language,
            retryable=True,
        ),
    }
