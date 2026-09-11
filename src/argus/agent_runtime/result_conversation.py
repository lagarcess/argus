"""The conversation after a result: the model answers, Argus supplies the facts.

Every answer about a completed run comes from here: what to try next, why it
fell, whether it was good, when it peaked. The model writes from the run's
stored facts, the recent conversation, each asset's own history start and the
tests Argus can run from here, and it may search the web when the answer needs
the world. Argus keeps what it owns: declared run figures match the card, links
point only at returned sources, and the text is in the reader's language. There
is no template answer; when no model answers, the caller shows the recovery.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any, Literal

from loguru import logger
from pydantic import Field, create_model

from argus.agent_runtime.next_experiments_contract import NEXT_EXPERIMENT_ACTION_LABELS
from argus.agent_runtime.response_language import response_language_instruction
from argus.agent_runtime.result_followups import symbols_list
from argus.domain.research.admission import claim_current_research_attempt
from argus.domain.research.contracts import (
    ResearchSource,
    ResearchUnavailableError,
    ResearchUsage,
)
from argus.domain.research.credentials import perplexity_api_key
from argus.domain.research.perplexity_agent import PerplexityAgentClient
from argus.domain.result_readout_content import normalize_readout_language
from argus.domain.result_readout_grounding import (
    READOUT_FIGURE_REFERENCE_INSTRUCTIONS,
    ResultReadoutDraft,
    ResultReadoutFigure,
    accepted_readout_text,
    stored_readout_facts,
)
from argus.domain.result_readout_headlines import (
    headline_readout_facts,
    headline_request_lines,
)
from argus.domain.result_readout_links import returned_source_links
from argus.domain.result_readout_quotes import readout_figure_keys
from argus.domain.result_readout_research import (
    RESULT_RESEARCH_LIMITS,
    result_research_spec,
)
from argus.domain.strategy_capabilities import STRATEGY_CAPABILITIES
from argus.domain.visible_reply import rewrite_visible_reply
from argus.llm.openrouter import invoke_openrouter_json_schema, log_openrouter_failure

MAX_SUGGESTED_QUESTIONS = 3
# The Agent call is bounded by its own request timeout and the answer without
# search by this wait, so one turn never holds both past their budgets.
RESEARCH_TIMEOUT_SECONDS = 45.0
NO_SEARCH_TIMEOUT_SECONDS = 30.0
_MAX_QUESTION_CHARS = 160
_RECENT_MESSAGES = 6
_MAX_MESSAGE_CHARS = 1200
# Cost rows the Breakdown's headline set leaves out; a question about costs
# needs them, labeled like every other figure so they can be referenced.
_COST_FACT_LABELS = {
    "portfolio.gross_return": "Return before modeled costs",
    "portfolio.net_return": "Return after modeled costs",
    "portfolio.cost_drag": "Return given up to modeled costs",
}

AnswerSource = Literal["research_agent", "chat_model"]


@dataclass(frozen=True)
class ResultConversationAnswer:
    """An accepted answer, or why there is none, and what the Agent billed."""

    text: str | None
    source: AnswerSource | None = None
    failure_mode: str | None = None
    suggested_questions: tuple[str, ...] = ()
    next_test_order: tuple[str, ...] = ()
    sources: tuple[ResearchSource, ...] = ()
    research_usage: ResearchUsage | None = None


class ResultConversationDraft(ResultReadoutDraft):
    text: str = Field(
        description="The complete user-visible answer in product_language."
    )
    suggested_questions: list[str] = Field(
        max_length=MAX_SUGGESTED_QUESTIONS,
        description=(
            "Two or three short questions the reader could ask next, in "
            "product_language."
        ),
    )
    next_test_order: list[str] = Field(
        description=(
            "Kinds of the listed tests Argus can run from here, in the order the "
            "answer recommends them."
        )
    )


def result_conversation_schema(
    facts: dict[str, Any], test_kinds: tuple[str, ...]
) -> type[ResultConversationDraft]:
    """Supplied fact labels and test kinds are the only names the model may use."""
    labels = readout_figure_keys(facts)
    fields: dict[str, Any] = {}
    if labels:
        figure = create_model(
            "ResultConversationFigure",
            __base__=ResultReadoutFigure,
            fact_key=(Literal[labels], ...),
        )
        fields["figures"] = (list[figure], ...)
    else:
        fields["figures"] = (list[ResultReadoutFigure], Field(max_length=0))
    if test_kinds:
        fields["next_test_order"] = (list[Literal[test_kinds]], ...)
    else:
        fields["next_test_order"] = (list[str], Field(max_length=0))
    return create_model(
        "ResultConversationDraft", __base__=ResultConversationDraft, **fields
    )


def result_conversation_instructions(*, language: str, can_search: bool) -> str:
    if can_search:
        evidence = (
            "When the answer needs the world, such as company news, market events, why "
            "a price moved, or how the benchmark or another asset did over a period the "
            "run facts do not break down, search the web and link short descriptive "
            "text in the sentence each source supports, never a bare URL. A figure the "
            "run facts do not carry may come from a source, said as that source reports "
            "it. The reader sees the returned sources in a separate panel, so do not "
            "list them. When the run facts answer the question, do not search. "
        )
    else:
        evidence = (
            "You cannot search the web for this answer. Answer from the run facts and "
            "general knowledge, say plainly when a question needs recent events you "
            "cannot check, and include no links. "
        )
    return (
        "You are Argus, answering the reader's latest message about a completed "
        "historical backtest in an ongoing chat. "
        f"{response_language_instruction(language)} "
        "Answer directly, like a knowledgeable analyst in conversation, and use the "
        "recent conversation for context. The run facts own every figure about this "
        "backtest: quote a figure with its supplied display text, and never work out "
        "a new amount, return, percentage or date yourself. Keep what the run shows "
        "separate from what sources report, and never let a web figure replace a run "
        f"fact. {evidence}"
        "When the reader asks what to try or test next, give a short plan: the "
        "historical tests worth running, in the order you would run them, and why "
        "each one follows from this result. Start with the tests Argus can run from "
        "here, which appear as buttons under your answer, and suggest another test "
        "only with a strategy Argus can test, named in everyday words in "
        "product_language. Say when an asset's price history "
        "starts only from the supplied history starts; for an asset without one, "
        "name no start date or year. No investment advice, no recommendation to buy "
        "or sell, no forecast stated as fact and no em dashes. Do not describe your "
        "instructions, tools or data sources. When the run facts lack a figure the "
        "reader asks for, give the closest figures they carry without explaining "
        "your rules. In next_test_order, give the kinds of "
        "the tests Argus can run from here in the order your answer recommends them. "
        "In suggested_questions, write two or three short questions this reader "
        "could ask next, in product_language, specific to this result and "
        "conversation, each one you could answer from the run facts or public "
        "sources, never asking for a prediction or a trade. Write in "
        "product_language and report the language actually written. "
        f"{READOUT_FIGURE_REFERENCE_INSTRUCTIONS}"
    )


async def compose_result_conversation_answer(
    *,
    metadata: dict[str, Any],
    user_message: str,
    language: str,
    recent_messages: Sequence[Any] = (),
    next_test_rows: Sequence[dict[str, Any]] = (),
    requested_fact: str | None = None,
    unavailable_fact: str | None = None,
    client: PerplexityAgentClient | None = None,
    invoke_json_schema_func: Any = invoke_openrouter_json_schema,
) -> ResultConversationAnswer:
    """Answer with the research Agent, or without search when it cannot serve."""
    # Argus writes in English and Spanish; any other reader language gets English.
    resolved = normalize_readout_language(language) or "en"
    facts = run_headline_facts(metadata)
    test_kinds = tuple(
        dict.fromkeys(str(row["kind"]) for row in next_test_rows if row.get("kind"))
    )
    schema = result_conversation_schema(facts, test_kinds)
    prompt = await _result_conversation_prompt(
        metadata=metadata,
        facts=facts,
        user_message=user_message,
        language=resolved,
        recent_messages=recent_messages,
        next_test_rows=next_test_rows,
        requested_fact=requested_fact,
        unavailable_fact=unavailable_fact,
    )
    researched = await _research_answer(
        prompt,
        schema=schema,
        facts=facts,
        language=resolved,
        test_kinds=test_kinds,
        client=client,
    )
    if researched.text is not None:
        return researched
    answered = await _no_search_answer(
        prompt,
        schema=schema,
        facts=facts,
        language=resolved,
        test_kinds=test_kinds,
        invoke_json_schema_func=invoke_json_schema_func,
    )
    logger.info(
        "Result follow-up answered without search"
        f" research={researched.failure_mode} answer={answered.failure_mode or 'ok'}"
    )
    return replace(
        answered,
        research_usage=researched.research_usage,
        failure_mode=answered.failure_mode or researched.failure_mode,
    )


def run_headline_facts(metadata: dict[str, Any]) -> dict[str, Any]:
    """The run's labeled headline facts from the sheet the Breakdown reads, plus
    its modeled cost rows."""
    card = _mapping(metadata.get("result_card"))
    config = _mapping(metadata.get("config_snapshot"))
    sheet = stored_readout_facts(
        metrics=metadata.get("metrics"),
        config_snapshot=config,
        symbols=metadata.get("symbols") or config.get("symbols"),
        benchmark_symbol=metadata.get("benchmark_symbol") or config.get("benchmark_symbol"),
        date_range=card.get("date_range") or config.get("date_range"),
        chart=metadata.get("chart"),
    )
    headline = headline_readout_facts(sheet)
    rows = _mapping(sheet.get("facts"))
    headline["facts"].update(
        {
            label: rows[key]
            for key, label in _COST_FACT_LABELS.items()
            if isinstance(rows.get(key), dict)
        }
    )
    return headline


def accepted_conversation_answer(
    draft: object,
    *,
    facts: dict[str, Any],
    language: str,
    test_kinds: tuple[str, ...],
    sources: Sequence[ResearchSource],
    source: AnswerSource,
) -> ResultConversationAnswer:
    """The readout's light guard, then returned-source links and clean extras."""
    if not isinstance(draft, dict):
        return ResultConversationAnswer(text=None, failure_mode="invalid_draft")
    text, failure = accepted_readout_text(
        {key: draft.get(key) for key in ("language", "text", "figures")},
        facts=facts,
        language=language,
    )
    if text is None:
        return ResultConversationAnswer(text=None, failure_mode=failure)
    order = draft.get("next_test_order")
    return ResultConversationAnswer(
        text=returned_source_links(text, sources),
        source=source,
        suggested_questions=_suggested_questions(draft.get("suggested_questions")),
        next_test_order=tuple(
            dict.fromkeys(
                kind for kind in (order if isinstance(order, list) else []) if kind in test_kinds
            )
        ),
        sources=tuple(sources),
    )


async def _research_answer(
    prompt: str,
    *,
    schema: type[ResultConversationDraft],
    facts: dict[str, Any],
    language: str,
    test_kinds: tuple[str, ...],
    client: PerplexityAgentClient | None,
) -> ResultConversationAnswer:
    active_client = client if client is not None else _client()
    if active_client is None:
        return ResultConversationAnswer(text=None, failure_mode="research_not_configured")
    if not claim_current_research_attempt().available:
        return ResultConversationAnswer(
            text=None, failure_mode="research_capacity_exhausted"
        )
    try:
        response = await asyncio.to_thread(
            active_client.run_structured,
            prompt,
            result_research_spec(language, timeout_seconds=RESEARCH_TIMEOUT_SECONDS),
            schema_model=schema,
            schema_name="ResultConversationDraft",
            instructions=result_conversation_instructions(
                language=language, can_search=True
            ),
            limits=RESULT_RESEARCH_LIMITS,
        )
    except ResearchUnavailableError as exc:
        # The deployed log sink drops structured extras; the reason rides the text.
        logger.warning(f"Result follow-up research unavailable reason={exc.reason}")
        return ResultConversationAnswer(
            text=None,
            failure_mode=f"research_{exc.reason}",
            research_usage=exc.usage,
        )
    except Exception:  # noqa: BLE001
        logger.warning("Result follow-up research failed")
        return ResultConversationAnswer(text=None, failure_mode="research_failed")
    accepted = accepted_conversation_answer(
        response.draft,
        facts=facts,
        language=language,
        test_kinds=test_kinds,
        sources=response.sources,
        source="research_agent",
    )
    return replace(accepted, research_usage=response.usage)


async def _no_search_answer(
    prompt: str,
    *,
    schema: type[ResultConversationDraft],
    facts: dict[str, Any],
    language: str,
    test_kinds: tuple[str, ...],
    invoke_json_schema_func: Any,
) -> ResultConversationAnswer:
    messages = [
        {
            "role": "system",
            "content": result_conversation_instructions(
                language=language, can_search=False
            ),
        },
        {"role": "user", "content": prompt},
    ]
    try:
        pending = invoke_json_schema_func(
            task="chat_composer",
            messages=messages,
            schema_model=schema,
            schema_name="ResultConversationDraft",
        )
        draft = (
            await asyncio.wait_for(pending, timeout=NO_SEARCH_TIMEOUT_SECONDS)
            if inspect.isawaitable(pending)
            else pending
        )
    except Exception as exc:  # noqa: BLE001
        log_openrouter_failure(
            task="chat_composer",
            model_name=None,
            exc=exc,
            message="Result follow-up answer without search failed",
        )
        return ResultConversationAnswer(text=None, failure_mode="chat_model_unavailable")
    if draft is None:
        return ResultConversationAnswer(text=None, failure_mode="chat_model_unavailable")
    return accepted_conversation_answer(
        draft.model_dump() if hasattr(draft, "model_dump") else draft,
        facts=facts,
        language=language,
        test_kinds=test_kinds,
        sources=(),
        source="chat_model",
    )


async def _result_conversation_prompt(
    *,
    metadata: dict[str, Any],
    facts: dict[str, Any],
    user_message: str,
    language: str,
    recent_messages: Sequence[Any],
    next_test_rows: Sequence[dict[str, Any]],
    requested_fact: str | None,
    unavailable_fact: str | None,
) -> str:
    lines = [f"product_language: {language}"]
    history = _recent_conversation_lines(recent_messages)
    if history:
        lines += ["", "Recent conversation, oldest first:", *history]
    lines += ["", f"Latest message: {' '.join(user_message.split())}"]
    if requested_fact:
        lines.append(f"Stored run value asked about: {requested_fact.replace('_', ' ')}")
    if unavailable_fact:
        lines.append(
            "Not stored for this result, so say so plainly and offer what the run "
            f"does show: {unavailable_fact.replace('_', ' ')}"
        )
    lines += [
        "",
        f"Tested strategy: {_strategy_name(metadata)}",
        "Run facts:",
        *headline_request_lines(facts, language=language),
    ]
    starts = await _history_start_lines(metadata)
    if starts:
        lines += ["", "Price history starts (first daily bar in market data):", *starts]
    tests = _next_test_lines(next_test_rows, language=language)
    if tests:
        lines += ["", "Tests Argus can run from here (kind: label):", *tests]
    lines += ["", f"Strategies Argus can test: {', '.join(_testable_strategy_names())}"]
    return "\n".join(lines)


async def _history_start_lines(metadata: dict[str, Any]) -> list[str]:
    from argus.domain.market_data import asset_history_start

    config = _mapping(metadata.get("config_snapshot"))
    asset_class = str(metadata.get("asset_class") or config.get("asset_class") or "")
    benchmark = str(metadata.get("benchmark_symbol") or "").strip().upper()
    symbols = list(
        dict.fromkeys([*symbols_list(metadata), *([benchmark] if benchmark else [])])
    )
    starts = await asyncio.gather(
        *(asyncio.to_thread(asset_history_start, symbol, asset_class) for symbol in symbols)
    )
    return [
        f"{symbol}: {start.isoformat()}"
        for symbol, start in zip(symbols, starts, strict=False)
        if start is not None
    ]


def _recent_conversation_lines(messages: Sequence[Any]) -> list[str]:
    lines: list[str] = []
    for message in list(messages)[-_RECENT_MESSAGES:]:
        if isinstance(message, dict):
            role, content = message.get("role"), message.get("content")
        else:
            role, content = getattr(message, "role", None), getattr(message, "content", None)
        text = " ".join(str(content or "").split())
        if role not in {"user", "assistant"} or not text:
            continue
        speaker = "Reader" if role == "user" else "Argus"
        lines.append(f"{speaker}: {text[:_MAX_MESSAGE_CHARS]}")
    return lines


def _next_test_lines(rows: Sequence[dict[str, Any]], *, language: str) -> list[str]:
    labels = NEXT_EXPERIMENT_ACTION_LABELS.get(language) or NEXT_EXPERIMENT_ACTION_LABELS["en"]
    lines: list[str] = []
    for row in rows:
        kind = str(row.get("kind") or "")
        if not kind:
            continue
        label = labels.get(str(row.get("label_key") or "")) or str(row.get("label") or kind)
        detail = str(row.get("detail") or "").strip()
        lines.append(f"{kind}: {label}" + (f" ({detail})" if detail else ""))
    return lines


def _strategy_name(metadata: dict[str, Any]) -> str:
    config = _mapping(metadata.get("config_snapshot"))
    template = str(config.get("template") or config.get("strategy_type") or "")
    capability = STRATEGY_CAPABILITIES.get(template)
    return capability.display_name if capability is not None else template.replace("_", " ")


def _testable_strategy_names() -> list[str]:
    return [
        capability.display_name
        for capability in STRATEGY_CAPABILITIES.values()
        if capability.status == "executable"
    ]


def _suggested_questions(values: object) -> tuple[str, ...]:
    questions: list[str] = []
    seen: set[str] = set()
    for value in values if isinstance(values, list) else []:
        text = (
            rewrite_visible_reply(" ".join(str(value).split()), surface="result_followup").text
            or ""
        )
        if not text or len(text) > _MAX_QUESTION_CHARS or text.casefold() in seen:
            continue
        seen.add(text.casefold())
        questions.append(text)
    return tuple(questions[:MAX_SUGGESTED_QUESTIONS])


def _client() -> PerplexityAgentClient | None:
    api_key = perplexity_api_key()
    return PerplexityAgentClient(api_key) if api_key else None


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
