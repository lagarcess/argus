"""Stage patches for answers about the latest result.

Every answer is written by `compose_result_conversation_answer`. A what-next
answer keeps the result's Try next rows as its actions, in the order the answer
recommends them; any other answer wears the typed heading for its focus. A turn
no model answered gets the retryable recovery, still carrying the rows, and the
Agent's invoice rides the research sidecar either way so the ledger records it.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from argus.agent_runtime.next_experiments import next_experiments_sidecar
from argus.agent_runtime.recovery_messages import (
    recovery_message,
    recovery_state_stage_patch,
)
from argus.agent_runtime.research_grounded import returned_sources_research_sidecar
from argus.agent_runtime.response_style import result_followup_response_intent
from argus.agent_runtime.result_conversation import (
    ResultConversationAnswer,
    compose_result_conversation_answer,
)
from argus.agent_runtime.result_fact_enrichment import metric_number
from argus.agent_runtime.result_followups import (
    BENCHMARK_DELTA_METRIC_PATHS,
    MAX_DRAWDOWN_METRIC_PATHS,
)

SUGGESTED_QUESTIONS_VERSION = "argus_suggested_questions/v1"


async def answered_result_followup_patch(
    *,
    metadata: dict[str, Any],
    focus: str,
    user_message: str,
    language: str,
    recent_messages: Sequence[Any] = (),
    source_run_id: str | None = None,
) -> dict[str, Any]:
    """Stage patch answering the reader's message about the latest result."""
    rows = result_next_experiments(
        metadata, language=language, source_run_id=source_run_id
    )
    answer = await compose_result_conversation_answer(
        metadata=metadata,
        user_message=user_message,
        language=language,
        recent_messages=recent_messages,
        next_test_rows=rows["rows"] if rows is not None else (),
    )
    patch = (
        unavailable_result_followup_patch(language=language)
        if answer.text is None
        else {"assistant_response": answer.text}
    )
    if answer.text is not None and focus != "next_experiment":
        patch["response_intent"] = result_followup_response_intent(focus)
    if focus == "next_experiment" and rows is not None:
        # The Try next section is the heading; no result chrome is added.
        patch["next_experiments"] = ordered_next_experiments(
            rows, answer.next_test_order
        )
    return {**patch, **result_answer_sidecars(answer)}


def result_next_experiments(
    metadata: dict[str, Any],
    *,
    language: str,
    source_run_id: str | None,
) -> dict[str, Any] | None:
    """The latest result's full Try next offer (#590).

    An explicit ask gets the whole offer: spec §4.3's non-repetition rule
    restrains unsolicited re-offers, not an answer to a question. The message
    has no card, so the sidecar names its run and a continuity row keeps its
    typed action.
    """
    return next_experiments_sidecar(
        metadata,
        benchmark_delta=metric_number(metadata, paths=BENCHMARK_DELTA_METRIC_PATHS),
        max_drawdown=metric_number(metadata, paths=MAX_DRAWDOWN_METRIC_PATHS),
        language=language,
        source_run_id=source_run_id,
    )


def ordered_next_experiments(
    sidecar: dict[str, Any], order: Sequence[str]
) -> dict[str, Any]:
    """Rows in the answer's recommended order; unranked rows keep theirs after."""
    rank = {kind: index for index, kind in enumerate(order)}
    rows = sorted(sidecar["rows"], key=lambda row: rank.get(row["kind"], len(rank)))
    return {**sidecar, "rows": rows}


def result_answer_sidecars(answer: ResultConversationAnswer) -> dict[str, Any]:
    """The research invoice with its sources, and the questions offered to tap."""
    sidecars: dict[str, Any] = {}
    if answer.research_usage is not None:
        served = answer.source == "research_agent"
        sidecars["research"] = returned_sources_research_sidecar(
            sources=answer.sources if served else (),
            usage=answer.research_usage,
            degraded_code=None if served else "result_followup_research_unused",
        )
    if answer.text is not None and answer.suggested_questions:
        sidecars["suggested_questions"] = {
            "version": SUGGESTED_QUESTIONS_VERSION,
            "questions": list(answer.suggested_questions),
        }
    return sidecars


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
