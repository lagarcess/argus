"""The no-search answer that owns its math.

When the user's own figures are enough, or a lookup failed, the answer comes
from one voicing call that returns prose and at most one typed calculation. Its
inputs may be the user's words, Argus market data for a current price, or
assumptions the answer states; a page only when it was retrieved for this
conversation. The answer step computes the card and fills the prose's figures
from it. A figure only the user knows becomes one plain question.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from loguru import logger
from pydantic import ConfigDict

from argus.agent_runtime.answer_calculation import (
    ANSWER_TEMPLATE_KEY,
    MarketClose,
    PublishedCalculation,
    latest_market_close,
    publish_calculation,
    states_a_figure,
)
from argus.agent_runtime.calculation_rows import market_counterfactual_rows
from argus.agent_runtime.knowledge_answer import VoicedAnswer
from argus.agent_runtime.result_next_steps import next_steps_patch, offered_test_steps
from argus.agent_runtime.stages.interpret_types import (
    InterpretDecision,
    StageResult,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import RunState, UserState
from argus.domain.calculations.answer_request import (
    ANSWER_CALCULATION_INSTRUCTIONS,
    AnswerCalculation,
    all_properties_required,
    calculation_kinds_clause,
)
from argus.domain.research.contracts import ResearchSource
from argus.llm.openrouter import (
    invoke_openrouter_json_schema_sync,
    openrouter_structured_model_candidates,
    resolve_openrouter_api_key,
)

PENDING_PAYLOAD_KEY = "calculation"
CALCULATED_ANSWER_REASON_CODE = "calculated_answer"
PENDING_REPLY_REASON_CODE = "calculation_pending_reply"
INPUT_MISSING_REASON_CODE = "calculation_input_missing"
_HISTORY_TURNS = 4

# Model-facing contract for the one no-search answer that computes.
NO_SEARCH_ANSWER_GUIDANCE = (
    "Answer the user's money question in their language. Nothing was looked "
    "up for this answer: use the user's own figures, the Argus market data "
    "listed below and assumptions you state plainly. When a figure computed "
    "from inputs answers or decides the question, always return calculation; "
    "never answer such a question with prose alone. A figure a page would "
    "publish that is not listed here, such as a product's price or a bank's "
    "rate, becomes an assumption: choose a typical value, mark it assumption "
    "and say plainly in the answer that you assumed it and that the user can "
    "change it. A figure only the user knows, such as their balance, payment, "
    "term, income or horizon, is never assumed: list each one with source user "
    "and a null value, still return calculation, and write the answer as one "
    "plain question asking for all of them. "
    "No advice, no forecast stated as fact, no em dashes, no headings, no "
    "tables. Compose lead (required), one short sentence that answers the "
    "question or asks the one question; bullets (optional, up to 4), short "
    "plain phrases; note (optional), one closing sentence, which mentions a "
    "lookup only when this message lists one that failed. "
)


def _calculation_first(schema: dict[str, Any]) -> None:
    """Every field is written, the calculation before the prose that references it."""
    all_properties_required(schema)
    properties = schema.get("properties") or {}
    if "calculation" in properties:
        schema["properties"] = {
            "calculation": properties["calculation"],
            **{
                name: value for name, value in properties.items() if name != "calculation"
            },
        }
        schema["required"] = list(schema["properties"])


class CalculatedVoicedAnswer(VoicedAnswer):
    """A voiced answer with the one calculation Argus computes for it."""

    model_config = ConfigDict(json_schema_extra=_calculation_first)

    calculation: AnswerCalculation | None = None


@dataclass(frozen=True)
class CalculatedAnswer:
    """An answer whose figures came from its card, or one plain question."""

    answer_text: str
    patch: dict[str, Any]
    template: dict[str, str] | None
    question_field: str | None
    pending: dict[str, Any] | None


def calculated_answer(
    *,
    message: str,
    language: str,
    user: UserState,
    notes: list[str],
    history: Sequence[Any] = (),
    market_facts: dict[str, str] | None = None,
    not_looked_up: Sequence[str] = (),
    pending: dict[str, Any] | None = None,
    subject_symbol: str | None = None,
    retrieved: Sequence[ResearchSource] = (),
    market_close: MarketClose = latest_market_close,
    lookup_failed: bool = False,
) -> CalculatedAnswer | None:
    """One voicing call and its computed calculation, or None when voicing failed."""
    if not resolve_openrouter_api_key():
        return None
    voiced = _voice(
        _messages(
            message=message,
            language=language,
            history=history,
            market_facts=market_facts or {},
            not_looked_up=not_looked_up,
            pending=pending,
            lookup_failed=lookup_failed,
        )
    )
    if voiced is None:
        return None
    prose = voiced.as_markdown()
    if voiced.calculation is None:
        return None if "{{" in prose else CalculatedAnswer(prose, {}, None, None, None)
    from argus.domain.capability_registry import get_tool_catalog

    published = publish_calculation(
        voiced.calculation,
        template=prose,
        language=language,
        catalog=get_tool_catalog(),
        retrieved=retrieved,
        currency=user.currency,
        subject_symbol=subject_symbol,
        market_close=market_close,
        notes=notes,
    )
    return answer_from_published(
        voiced.calculation,
        published,
        prose=prose,
        language=language,
        retrieved=retrieved,
    )


def answer_from_published(
    request: AnswerCalculation,
    published: PublishedCalculation | None,
    *,
    prose: str,
    language: str,
    retrieved: Sequence[ResearchSource],
) -> CalculatedAnswer | None:
    """The answer a published calculation makes: its card and prose, or the one
    question for a figure only the user knows; None when inputs were not found."""
    if published is None or published.not_looked_up:
        return None
    if published.question_field is not None:
        field = published.question_field
        asks = prose.strip() and "{{" not in prose and not states_a_figure(prose)
        return CalculatedAnswer(
            answer_text=prose.strip() if asks else question_text(field, language),
            patch={},
            template=None,
            question_field=field,
            pending={
                PENDING_PAYLOAD_KEY: request.model_dump(mode="json"),
                "requested_field": field,
                "retrieved": [source.model_dump(mode="json") for source in retrieved],
            },
        )
    return CalculatedAnswer(
        answer_text=published.answer_text or "",
        patch=published.patch,
        template=published.template,
        question_field=None,
        pending=None,
    )


async def calculated_answer_stage_result(
    *,
    interpretation: StructuredInterpretation,
    state: RunState,
    user: UserState,
    pending: dict[str, Any] | None = None,
) -> StageResult | None:
    """The no-search answer as a turn: its computed card under the prose, or one
    plain question for the figure only the user knows."""
    retrieved = [
        ResearchSource.model_validate(page)
        for page in ((pending or {}).get("retrieved") or [])
        if isinstance(page, dict) and page.get("url")
    ]
    answered = await asyncio.to_thread(
        calculated_answer,
        message=state.current_user_message,
        language=user.language_preference,
        user=user,
        notes=interpretation.reason_codes,
        history=state.recent_thread_history,
        pending=pending,
        retrieved=retrieved,
    )
    if answered is None:
        return None
    from argus.agent_runtime.research_grounded import research_decision

    code = PENDING_REPLY_REASON_CODE if pending else CALCULATED_ANSWER_REASON_CODE
    if answered.question_field is not None:
        return question_stage_result(
            answered,
            decision=research_decision(interpretation, user, INPUT_MISSING_REASON_CODE),
        )
    patch: dict[str, Any] = {**answered.patch, "assistant_response": answered.answer_text}
    if answered.template is not None:
        patch[ANSWER_TEMPLATE_KEY] = answered.template
    cards = (answered.patch.get("final_response_payload") or {}).get("tool_result_cards")
    if cards and cards[0].get("outcome", {}).get("status") == "succeeded":
        rows = market_counterfactual_rows(
            cards[0].get("arguments") or {}, language=user.language_preference
        )
        patch.update(next_steps_patch(rows, offered_test_steps(rows)))
    return StageResult(
        outcome="ready_to_respond",
        decision=research_decision(interpretation, user, code),
        stage_patch=patch,
    )


def pending_calculation(metadata: dict[str, Any]) -> dict[str, Any] | None:
    """The calculation a reply completes: the answer asked the user for one
    figure and is waiting for it."""
    if metadata.get("last_stage_outcome") != "await_user_reply":
        return None
    clarification = metadata.get("clarification")
    payload = clarification.get("payload") if isinstance(clarification, dict) else None
    if isinstance(payload, dict) and isinstance(payload.get(PENDING_PAYLOAD_KEY), dict):
        return payload
    return None


def question_stage_result(
    answered: CalculatedAnswer, *, decision: InterpretDecision | None
) -> StageResult:
    """One plain question for the figure only the user knows, with the pending
    calculation the reply completes."""
    field = str(answered.question_field)
    return StageResult(
        outcome="await_user_reply",
        decision=decision,
        stage_patch={
            "assistant_prompt": answered.answer_text,
            "requested_field": field,
            "missing_required_fields": [field],
            "clarification": {
                "kind": "clarification",
                "reason_code": INPUT_MISSING_REASON_CODE,
                "prompt_source": "llm_generated",
                "requested_field": field,
                "requested_fields": [field],
                "semantic_needs": [],
                "payload": answered.pending or {},
                "options": [],
            },
        },
    )


def question_text(field: str, language: str) -> str:
    """Argus's own plain question for one figure only the user knows."""
    label = field.replace("_pct", " (%)").replace("_", " ")
    if str(language or "").startswith("es"):
        return f"Para calcularlo me falta un dato: {label}. ¿Qué valor uso?"
    return f"To compute this I need one more value: {label}. What should I use?"


def _voice(messages: list[dict[str, str]]) -> CalculatedVoicedAnswer | None:
    for model_name in openrouter_structured_model_candidates():
        try:
            voiced = invoke_openrouter_json_schema_sync(
                task="knowledge_voicing",
                messages=messages,
                schema_model=CalculatedVoicedAnswer,
                schema_name="CalculatedVoicedAnswer",
                model_name=model_name,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Calculated answer voicing failed error={exc!r}")
            continue
        if isinstance(voiced, CalculatedVoicedAnswer) and voiced.lead.strip():
            return voiced
    return None


def _messages(
    *,
    message: str,
    language: str,
    history: Sequence[Any],
    market_facts: dict[str, str],
    not_looked_up: Sequence[str],
    pending: dict[str, Any] | None,
    lookup_failed: bool = False,
) -> list[dict[str, str]]:
    context = [
        NO_SEARCH_ANSWER_GUIDANCE,
        f"Reply in {language}. ",
        ANSWER_CALCULATION_INSTRUCTIONS,
        calculation_kinds_clause(),
    ]
    lines: list[str] = []
    for turn in list(history or [])[-_HISTORY_TURNS:]:
        role = str(
            getattr(turn, "role", "")
            or (turn.get("role") if isinstance(turn, dict) else "")
        )
        content = str(
            getattr(turn, "content", "")
            or (turn.get("content") if isinstance(turn, dict) else "")
        )
        if role and content:
            lines.append(f"{role}: {content}")
    if lines:
        context.append("Recent conversation, oldest first:\n" + "\n".join(lines) + "\n")
    if market_facts:
        context.append(
            "Argus market data:\n"
            + "\n".join(f"{name}: {value}" for name, value in market_facts.items())
            + "\n"
        )
    if not_looked_up:
        context.append(
            "Could not be looked up for this answer, so say so plainly: "
            + ", ".join(not_looked_up)
            + ".\n"
        )
    elif lookup_failed:
        context.append(
            "The lookup for this answer found nothing, so say plainly that "
            "published figures could not be looked up.\n"
        )
    if pending:
        calculation = pending.get(PENDING_PAYLOAD_KEY) or {}
        context.append(
            f"Argus asked the user for {pending.get('requested_field')} of a "
            f"{calculation.get('kind')} calculation. Keep that kind and its inputs so "
            f"far, and fill the answered figure: {json.dumps(calculation, ensure_ascii=False)}\n"
        )
    return [
        {"role": "system", "content": "".join(context)},
        {"role": "user", "content": str(message)},
    ]
