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
from argus.domain.calculations._shared import field_label
from argus.domain.calculations.answer_request import (
    ANSWER_CALCULATION_INSTRUCTIONS,
    AnswerCalculation,
    all_properties_required,
    calculation_kinds_clause,
)
from argus.domain.research.contracts import ResearchSource, RetrievedRow
from argus.llm.openrouter import (
    invoke_openrouter_json_schema_sync,
    openrouter_structured_model_candidates,
    resolve_openrouter_api_key,
)

PENDING_PAYLOAD_KEY = "calculation"
CALCULATED_ANSWER_REASON_CODE = "calculated_answer"
PENDING_REPLY_REASON_CODE = "calculation_pending_reply"
INPUT_MISSING_REASON_CODE = "calculation_input_missing"
# Recorded when a voiced answer only restated the user's question; it is never
# published, and the caller's honest note stands in.
ANSWER_RESTATED_QUESTION_REASON_CODE = "answer_restated_question"
# A research answer's calculation that needs figures only the reader knows is
# offered under the answer, and taken through a typed action.
CALCULATION_OFFER_KEY = "calculation_offer"
CALCULATION_OFFER_ACTION = "calculation_offer"
CALCULATION_OFFERED_REASON_CODE = "calculation_offered"
CALCULATION_OFFER_TAKEN_REASON_CODE = "calculation_offer_taken"
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
    "plain question asking for all of them and nothing else: never for a figure "
    "the calculation produces, such as an effective annual rate. Name a currency only when "
    "the user stated one. "
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
    missing_inputs: tuple[str, ...] = ()


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
    offered: bool = False,
    evidence: Sequence[RetrievedRow] = (),
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
            offered=offered,
        )
    )
    if voiced is None:
        return None
    if _restates(message, voiced.lead):
        if ANSWER_RESTATED_QUESTION_REASON_CODE not in notes:
            notes.append(ANSWER_RESTATED_QUESTION_REASON_CODE)
        logger.info(
            "Voiced answer only restated the question",
            failure_classification=ANSWER_RESTATED_QUESTION_REASON_CODE,
        )
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
        evidence=evidence,
    )
    return answer_from_published(
        voiced.calculation,
        published,
        prose=prose,
        language=language,
        retrieved=retrieved,
        evidence=evidence,
    )


def answer_from_published(
    request: AnswerCalculation,
    published: PublishedCalculation | None,
    *,
    prose: str,
    language: str,
    retrieved: Sequence[ResearchSource],
    evidence: Sequence[RetrievedRow] = (),
) -> CalculatedAnswer | None:
    """The answer a published calculation makes: its card and prose, or the one
    question for a figure only the user knows; None when inputs were not found."""
    if published is None or published.not_looked_up:
        return None
    if published.question_field is not None:
        field = published.question_field
        owed = published.owed or (field,)
        return CalculatedAnswer(
            answer_text=missing_inputs_lead(language),
            patch={},
            template=None,
            question_field=field,
            missing_inputs=tuple(owed),
            pending={
                PENDING_PAYLOAD_KEY: request.model_dump(mode="json"),
                "requested_field": field,
                "requested_fields": list(owed),
                "evidence": [row.model_dump(mode="json") for row in evidence],
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
    offered: bool = False,
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
        offered=offered,
        evidence=[
            RetrievedRow.model_validate(row)
            for row in ((pending or {}).get("evidence") or [])
            if isinstance(row, dict)
        ],
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
    from argus.agent_runtime.answer_calculation import cards_in, record_unsourced_figures

    record_unsourced_figures(
        answered.answer_text,
        cited=[],
        cards=cards_in(answered.patch),
        notes=interpretation.reason_codes,
        message=state.current_user_message,
    )
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


async def calculation_offer_stage_result(
    *,
    state: RunState,
    user: UserState,
    selected_thread_metadata: dict[str, Any],
) -> StageResult | None:
    """The reader took a research answer's offered calculation: one plain
    question for the figures only they know, with the cited ones kept, which the
    reply completes like any pending calculation."""
    action = state.structured_action
    if action is None or action.type != CALCULATION_OFFER_ACTION:
        return None
    from argus.agent_runtime.recovery_messages import recovery_message
    from argus.agent_runtime.research_grounded import research_decision
    from argus.agent_runtime.state.models import StrategySummary

    interpretation = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="new_task",
        user_goal_summary=state.current_user_message,
        semantic_turn_act="educational_question",
        candidate_strategy_draft=StrategySummary(),
        reason_codes=[CALCULATION_OFFER_TAKEN_REASON_CODE],
    )
    offer = selected_thread_metadata.get(CALCULATION_OFFER_KEY)
    if not isinstance(offer, dict) or not isinstance(
        offer.get(PENDING_PAYLOAD_KEY), dict
    ):
        return StageResult(
            outcome="ready_to_respond",
            decision=research_decision(
                interpretation, user, CALCULATION_OFFER_TAKEN_REASON_CODE
            ),
            stage_patch={
                "assistant_response": recovery_message(
                    "artifact_action_invalid_state", language=user.language_preference
                )
            },
        )
    asked = await calculated_answer_stage_result(
        interpretation=interpretation,
        state=state,
        user=user,
        pending=offer,
        offered=True,
    )
    if asked is not None and asked.outcome == "await_user_reply":
        return asked
    field = str(offer.get("requested_field") or "")
    return question_stage_result(
        CalculatedAnswer(
            answer_text=missing_inputs_lead(user.language_preference),
            patch={},
            template=None,
            question_field=field,
            pending=offer,
            missing_inputs=tuple(offer.get("requested_fields") or [field]),
        ),
        decision=research_decision(interpretation, user, INPUT_MISSING_REASON_CODE),
    )


def pending_calculation_reply(
    interpretation: StructuredInterpretation, metadata: dict[str, Any]
) -> dict[str, Any] | None:
    """A reply to the answer's one question completes its calculation, unless
    the primary read routed the reply to an action of its own."""
    from argus.agent_runtime.interpreter.research_routing import (
        research_turn_has_conflicting_owner,
    )

    pending = pending_calculation(metadata)
    if pending is None or interpretation.asset_discovery is not None:
        return None
    return None if research_turn_has_conflicting_owner(interpretation) else pending


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
    owed = list(answered.missing_inputs or (field,))
    return StageResult(
        outcome="await_user_reply",
        decision=decision,
        stage_patch={
            "assistant_prompt": answered.answer_text,
            "requested_field": field,
            "missing_required_fields": owed,
            "clarification": {
                "kind": "clarification",
                "reason_code": INPUT_MISSING_REASON_CODE,
                # Display transport: the app writes the question from the typed
                # missing inputs and their label keys, in the reader's language.
                "prompt_source": "degraded_fallback",
                "requested_field": field,
                "requested_fields": owed,
                "missing_inputs": [
                    {"name": name, "label": field_label(name).model_dump(mode="json")}
                    for name in owed
                ],
                "semantic_needs": [],
                "payload": answered.pending or {},
                "options": [],
            },
        },
    )


def missing_inputs_lead(language: str) -> str:
    """The stored line of a question for figures only the user knows; the app
    names each figure from the typed missing inputs."""
    if str(language or "").startswith("es"):
        return "Para calcularlo, necesito algunos de tus propios datos."
    return "To work this out, I need a few of your own figures."


def _restates(message: str, lead: str) -> bool:
    """Whether a lead is the user's own question and nothing more."""

    def plain(text: str) -> str:
        return "".join(ch for ch in str(text).casefold() if ch.isalnum())

    return bool(plain(lead)) and plain(lead) == plain(message)


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
    offered: bool = False,
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
            "The lookup for this answer failed: say so plainly in one short sentence, "
            "then answer what you can from the user's figures, Argus market data and "
            "assumptions you state. Never restate the question as the answer.\n"
        )
    if pending:
        calculation = pending.get(PENDING_PAYLOAD_KEY) or {}
        payload = json.dumps(calculation, ensure_ascii=False)
        if offered:
            context.append(
                "The reader chose to work this out with their own figures. Keep "
                f"this {calculation.get('kind')} calculation and the inputs it "
                "already holds with their sources, and ask one plain question for "
                f"every figure only the reader knows: {payload}\n"
            )
        else:
            context.append(
                f"Argus asked the user for {', '.join(pending.get('requested_fields') or [str(pending.get('requested_field'))])} of a "
                f"{calculation.get('kind')} calculation. Keep that kind and its inputs "
                f"so far, and fill the answered figure: {payload}\n"
            )
    return [
        {"role": "system", "content": "".join(context)},
        {"role": "user", "content": str(message)},
    ]
