"""The calculation read: the one model read that maps a money question to a
declared calculation.

The primary interpreter routes the turn and never maps calculations; it only
marks ``computed_figure_decides``. This read runs after it on that mark, on a
reply to a pending calculation question, or before a refusal the primary chose,
never on an ordinary turn and never on the message text. It reads the current message with the recent conversation and
the declared catalogue, and records the signal and a reason code whenever its
read reaches the turn, or when a mark yields to the route the primary chose
(AGENTS.md: redundancy over an LLM read must be observable).
"""

from __future__ import annotations

import json
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

PENDING_REPLY_TRIGGER = "calculation_read_pending_reply"
MONEY_QUESTION_TRIGGER = "calculation_read_money_question"
BEFORE_REFUSAL_TRIGGER = "calculation_read_before_refusal"
ROUTE_KEPT_REASON_CODE = "calculation_read_skipped_for_route"
READ_MAPPED_REASON_CODE = "calculation_read_mapped"
_ROUTED_INTENTS = frozenset(
    {"backtest_execution", "results_explanation", "collection_management"}
)
_ROUTED_ACTS = frozenset(
    {
        "answer_pending_need",
        "refine_current_idea",
        "result_followup",
        "retry_failed_action",
        "approval",
        "asset_discovery",
    }
)
_HISTORY_TURNS = 4

FOCUSED_CALCULATION_READ_GUIDANCE = (
    "Calculation read. Read the current user message, in any language, and "
    "decide one thing: would a figure that one of the calculations below "
    "computes answer or decide it? Users rarely ask for a number. A money "
    "question about whether something is worth it, affordable, enough, "
    "cheaper, better, expensive or losing value, or about which of several "
    "products, accounts, currencies or options to choose, is decided by "
    "figures: choose the kind that computes the figure the decision turns on "
    "and set answered_by_a_calculation=true. Argus answers a choice by "
    "computing each option's figure, never by recommending one, so a choice "
    "among options counts even when the user asks what to pick. Direct "
    "requests for a payment, a balance, a rate, a time, a yield, a multiple, "
    "a ratio, a fee's cost, a ranking or a future value count too. Set it "
    "false for requests to build or run a test over past market data, such as "
    "buying or holding an asset over a past window; for whether to put money "
    "into a stock, fund or cryptocurrency, which Argus answers with the "
    "asset's history; for concept education with no figure to compute; for "
    "questions about Argus or a visible result; and for social turns. When "
    "true, choose the closest kind even when inputs are missing. A question "
    "that names no amount or no options yet still gets the kind that would "
    "decide it, with follow_up_questions asking for what only the user knows. "
    "An amount put in at a rate, such as a deposit, a certificate or a bond "
    "held to maturity, is a time_value plan with the amount as present_value. "
    "When Argus is waiting for the user's reply to a calculation, a message "
    "that answers it keeps that kind and puts only the answered figures in "
    "inputs. Put every number the user stated in inputs under the listed "
    "argument names: amounts as plain numbers, percentages as percent numbers "
    "(7 for 7 percent), counts of periods as integers, and the currency as an "
    "ISO 4217 code only when the user names one unambiguously. Put in "
    "retrieve every listed input a published page states that the user did "
    "not: a product's price, a lender's, bank's or card's published rate or "
    "fee, the inflation rate where the user lives, an asset's price, "
    "earnings, growth forecast or multiple. Never ask the user for a figure a "
    "page states. Set solve_for to the one blank the decision needs when the "
    "kind lists blanks. Fill follow_up_questions, at most three, only with "
    "figures or choices the user alone knows that the calculation still "
    "needs, such as their balance, payment, income, spending or horizon, in "
    "the user's words and language; a question too broad to name the amount "
    "or the options gets three such questions. Kinds and their inputs:\n"
)


class FocusedCalculationRead(BaseModel):
    """One narrow read: which declared calculation answers this message."""

    model_config = ConfigDict(json_schema_extra=all_properties_required)

    answered_by_a_calculation: bool = Field(
        description=(
            "True when a figure one of the listed calculations computes would "
            "answer or decide the current money question, even when the user "
            "asks for no number, in any language."
        )
    )
    calculation: CalculationRequest | None = None


def focused_calculation_trigger(
    interpretation: Any, *, pending: CalculationRequest | None = None
) -> str | None:
    """The typed signal that sends this turn to the calculation read, or None."""
    if pending is not None:
        return PENDING_REPLY_TRIGGER
    if _owned_by_another_route(interpretation):
        return None
    if getattr(interpretation, "computed_figure_decides", False):
        return MONEY_QUESTION_TRIGGER
    if (
        interpretation.intent == "unsupported_or_out_of_scope"
        or interpretation.unsupported_constraints
    ):
        # A refusal must never name a capability the user did not ask about.
        return BEFORE_REFUSAL_TRIGGER
    return None


def _owned_by_another_route(interpretation: Any) -> bool:
    """A marked turn the primary also routed to a runnable action keeps its route."""
    return (
        interpretation.asset_discovery is not None
        or interpretation.artifact_target not in (None, "none")
        or interpretation.result_followup_focus is not None
        or interpretation.capability_question_focus is not None
        or interpretation.context_question_focus is not None
        or interpretation.intent in _ROUTED_INTENTS
        or interpretation.semantic_turn_act in _ROUTED_ACTS
        or (
            interpretation.intent == "strategy_drafting"
            and not interpretation.unsupported_constraints
            and strategy_has_execution_evidence(interpretation.candidate_strategy_draft)
        )
    )


async def focused_calculation_request(
    *,
    interpretation: Any,
    message: str,
    history: Sequence[Any],
    pending: CalculationRequest | None = None,
) -> CalculationRequest | None:
    """The read's calculation, kind-less when it only asks follow-ups, or None."""
    trigger = focused_calculation_trigger(interpretation, pending=pending)
    if trigger is None:
        if getattr(interpretation, "computed_figure_decides", False):
            _record(interpretation, ROUTE_KEPT_REASON_CODE)
        return None
    try:
        read = await invoke_openrouter_json_schema(
            task="interpretation",
            messages=_read_messages(message, history, pending),
            schema_model=FocusedCalculationRead,
            schema_name="FocusedCalculationRead",
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("Calculation read failed", error=str(exc))
        return None
    if (
        not isinstance(read, FocusedCalculationRead)
        or not read.answered_by_a_calculation
        or read.calculation is None
    ):
        return None
    mapped = read.calculation
    if mapped.kind is None and not any(
        question.strip() for question in mapped.follow_up_questions
    ):
        return None
    for code in (trigger, READ_MAPPED_REASON_CODE):
        _record(interpretation, code)
    logger.info(
        f"Calculation read mapped the turn trigger={trigger} kind={mapped.kind}",
        failure_classification=READ_MAPPED_REASON_CODE,
    )
    return mapped


def _record(interpretation: Any, code: str) -> None:
    if code not in interpretation.reason_codes:
        interpretation.reason_codes.append(code)


def _read_messages(
    message: str,
    history: Sequence[Any],
    pending: CalculationRequest | None = None,
) -> list[dict[str, str]]:
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
    if pending is not None:
        known = json.dumps(pending.inputs, default=str, ensure_ascii=False)
        messages.append(
            {
                "role": "system",
                "content": (
                    f"Argus is waiting for the user's reply to a {pending.kind} "
                    f"calculation. Inputs so far: {known}"
                ),
            }
        )
    messages.append({"role": "user", "content": str(message)})
    return messages
