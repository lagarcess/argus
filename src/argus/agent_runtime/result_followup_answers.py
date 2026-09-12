"""Stage patches for answers about the latest result.

Every answer is written by `compose_result_conversation_answer`, and the one
list of next steps under it comes from `result_next_steps`: the result's tests
and the model's questions in the order the answer recommends. A turn no model
answered gets the retryable recovery, and the Agent's invoice rides the
research sidecar either way so the ledger records it.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from loguru import logger

from argus.agent_runtime.next_experiments import next_experiments_sidecar
from argus.agent_runtime.recovery_messages import (
    recovery_message,
    recovery_state_stage_patch,
)
from argus.agent_runtime.research_grounded import returned_sources_research_sidecar
from argus.agent_runtime.result_conversation import (
    ResultConversationAnswer,
    compose_result_conversation_answer,
)
from argus.agent_runtime.result_fact_enrichment import metric_number
from argus.agent_runtime.result_followups import (
    MAX_DRAWDOWN_METRIC_PATHS,
    benchmark_gap_metric,
)
from argus.agent_runtime.result_next_steps import next_steps_patch, offered_test_steps


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
    return {
        **patch,
        **result_answer_sidecars(answer, rows, offer_tests=focus == "next_experiment"),
    }


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
        benchmark_delta=benchmark_gap_metric(metadata),
        max_drawdown=metric_number(metadata, paths=MAX_DRAWDOWN_METRIC_PATHS),
        language=language,
        source_run_id=source_run_id,
    )


def result_answer_sidecars(
    answer: ResultConversationAnswer,
    rows: dict[str, Any] | None,
    *,
    offer_tests: bool = False,
) -> dict[str, Any]:
    """The research invoice with its sources, and the list of next steps.

    A reader who asked what to try next is offered the result's tests even when
    no model listed any.
    """
    sidecars: dict[str, Any] = {}
    if answer.research_usage is not None:
        served = answer.source == "research_agent"
        sidecars["research"] = returned_sources_research_sidecar(
            sources=answer.sources if served else (),
            usage=answer.research_usage,
            degraded_code=None if served else "result_followup_research_unused",
        )
    steps = answer.next_steps if answer.text is not None else ()
    if not steps and offer_tests:
        if answer.text is not None:
            logger.info("Result follow-up listed no next steps; offering the tests")
        steps = offered_test_steps(rows)
    return {**sidecars, **next_steps_patch(rows, steps)}


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
