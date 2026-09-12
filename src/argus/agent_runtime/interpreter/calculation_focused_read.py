"""Focused calculation read: the backstop for a money question the primary
read did not map to a declared calculation.

The primary interpreter often fills the calculation payload for a money
question and still leaves its kind empty, asking follow-ups for figures Argus
could compute or retrieve; or it reads the question as a concept. This second
read asks one narrow question about the current message: which declared
calculation answers it, with which of the user's numbers and which published
inputs. It runs only on a typed contradiction in the primary read, never on
the message text, and records a reason code whenever it recovers a kind
(AGENTS.md: redundancy over an LLM read must be observable).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from argus.agent_runtime.interpreter.calculation_request import (
    CalculationRequest,
    all_properties_required,
    calculation_kinds_clause,
)
from argus.agent_runtime.interpreter.draft_shape import strategy_has_execution_evidence
from argus.llm.openrouter import invoke_openrouter_json_schema

KIND_MISSING_TRIGGER = "calculation_kind_missing"
UNROUTED_CONCEPT_TRIGGER = "calculation_unrouted_concept"
FOCUSED_READ_REASON_CODE = "calculation_recovered_by_focused_read"
_QUESTION_INTENTS = frozenset({"conversation_followup", "beginner_guidance"})
_QUESTION_ACTS = frozenset({None, "educational_question"})
_HISTORY_TURNS = 4

FOCUSED_CALCULATION_READ_GUIDANCE = (
    "Focused calculation read. Answer one narrow question about the current "
    "user message, in any language: does the user want a figure Argus can "
    "compute with one of the calculations listed below, from numbers the user "
    "stated and figures a published page states? A saving or loan payment, what "
    "a balance grows to, the time or rate a plan needs, what an income affords, "
    "a yield, a multiple, an effective rate, a debt ratio, the cost of a fee, a "
    "ranking of offers, a bond or certificate value, or what an investment will "
    "be worth all count. Set wants_a_computed_figure=false for requests to build "
    "or run a test over past market data, for concept education with no figure "
    "to compute, for questions about Argus itself and for social turns. When "
    "true, choose the closest kind even when inputs are missing. Put every "
    "number the user stated in inputs under the listed argument names: amounts "
    "as plain numbers, percentages as percent numbers (7 for 7 percent), counts "
    "of periods as integers, and the currency as an ISO 4217 code only when the "
    "user names one. Put in retrieve every listed input a published page states "
    "that the user did not: a product's price, a lender's or bank's published "
    "rate, the inflation rate where the user lives, an asset's price, earnings, "
    "growth forecast or multiple; never ask the user for those. Set solve_for "
    "to the one blank the user wants solved when the kind lists blanks. Fill "
    "follow_up_questions, at most three, only with figures or choices the user "
    "alone knows that the calculation still needs, in the user's words and "
    "language. Kinds and their inputs:\n"
)


class FocusedCalculationRead(BaseModel):
    """One narrow read: which declared calculation answers this message."""

    model_config = ConfigDict(json_schema_extra=all_properties_required)

    wants_a_computed_figure: bool = Field(
        description=(
            "True only when the current message asks for a figure one of the "
            "listed calculations computes, from the user's numbers or published "
            "figures, in any language."
        )
    )
    calculation: CalculationRequest | None = None


def focused_calculation_trigger(interpretation: Any) -> str | None:
    """The typed contradiction that justifies a second read, or None."""
    calculation = getattr(interpretation, "calculation", None)
    if calculation is not None:
        return KIND_MISSING_TRIGGER if calculation.kind is None else None
    query = getattr(interpretation, "research_query", None)
    if (
        query is not None
        and query.question_kind in ("concept", "none")
        and not query.symbols
        and interpretation.intent in _QUESTION_INTENTS
        and interpretation.semantic_turn_act in _QUESTION_ACTS
        and interpretation.asset_discovery is None
        and not interpretation.unsupported_constraints
        and interpretation.artifact_target in (None, "none")
        and not strategy_has_execution_evidence(interpretation.candidate_strategy_draft)
    ):
        return UNROUTED_CONCEPT_TRIGGER
    return None


async def focused_calculation_request(
    *, interpretation: Any, message: str, history: Sequence[Any]
) -> CalculationRequest | None:
    """A recovered calculation with a kind, or None when the read declines."""
    trigger = focused_calculation_trigger(interpretation)
    if trigger is None:
        return None
    try:
        read = await invoke_openrouter_json_schema(
            task="interpretation",
            messages=_read_messages(message, history),
            schema_model=FocusedCalculationRead,
            schema_name="FocusedCalculationRead",
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("Focused calculation read failed", error=str(exc))
        return None
    if (
        not isinstance(read, FocusedCalculationRead)
        or not read.wants_a_computed_figure
        or read.calculation is None
        or read.calculation.kind is None
    ):
        return None
    recovered = read.calculation
    primary = getattr(interpretation, "calculation", None)
    if primary is not None and primary.inputs:
        recovered = recovered.model_copy(
            update={"inputs": {**primary.inputs, **recovered.inputs}}
        )
    if FOCUSED_READ_REASON_CODE not in interpretation.reason_codes:
        interpretation.reason_codes.append(FOCUSED_READ_REASON_CODE)
    logger.info(
        f"Focused calculation read recovered a kind trigger={trigger} kind={recovered.kind}",
        failure_classification=FOCUSED_READ_REASON_CODE,
    )
    return recovered


def _read_messages(message: str, history: Sequence[Any]) -> list[dict[str, str]]:
    messages = [
        {
            "role": "system",
            "content": FOCUSED_CALCULATION_READ_GUIDANCE + calculation_kinds_clause(),
        }
    ]
    lines: list[str] = []
    for turn in list(history or [])[-_HISTORY_TURNS:]:
        if isinstance(turn, dict):
            role, content = str(turn.get("role") or ""), str(turn.get("content") or "")
        else:
            role = str(getattr(turn, "role", "") or "")
            content = str(getattr(turn, "content", "") or "")
        if role and content:
            lines.append(f"{role}: {content}")
    if lines:
        messages.append(
            {
                "role": "system",
                "content": "Recent conversation, oldest first:\n" + "\n".join(lines),
            }
        )
    messages.append({"role": "user", "content": str(message)})
    return messages
