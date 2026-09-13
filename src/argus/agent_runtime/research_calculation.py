"""A research answer's calculation, and the answer when a lookup fails.

The research provider returns prose and at most one calculation; it computes
here through the answer step, with the pages this answer retrieved as the only
pages an input may cite. When the lookup fails or a page input was not found,
the no-search step answers from Argus market data and stated assumptions and
says what it could not look up: a failed lookup never becomes the answer.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from loguru import logger
from pydantic import ValidationError

from argus.agent_runtime.answer_calculation import (
    card_in,
    computed_answer_patch,
    latest_market_close,
    publish_calculation,
    render_offer_prose,
    resolve_calculation,
)
from argus.agent_runtime.calculated_answer import (
    CALCULATION_OFFERED_REASON_CODE,
    PENDING_PAYLOAD_KEY,
    CalculatedAnswer,
    answer_from_published,
    calculated_answer,
)
from argus.agent_runtime.state.models import UserState
from argus.domain.calculations.answer_request import AnswerCalculation
from argus.domain.research.contracts import ResearchPacket, ResearchSource
from argus.llm.openrouter import resolve_openrouter_api_key

CALCULATION_NOT_COMPUTED_CODE = "calculation_inputs_not_found"
# Recorded when an offered calculation's prose left out a sentence or table row
# that leaned on a result the offer cannot show.
OFFER_PROSE_TRIMMED_REASON_CODE = "offer_prose_results_dropped"
MALFORMED_CALCULATION_REASON_CODE = "answer_calculation_malformed"
# Degraded research an answer without a lookup may replace; a survey or a claim
# withheld for want of a publisher keeps its own honest note.
LOOKUP_FAILURE_CODES = frozenset(
    {"research_not_grounded", "scenario_inputs_uncited", CALCULATION_NOT_COMPUTED_CODE}
)
_MAX_MARKET_SUBJECTS = 3


@dataclass(frozen=True)
class NotComputed:
    """A calculation the answer returned but Argus could not compute from its sources."""

    code: str
    not_looked_up: tuple[str, ...]


def packet_answer(
    packet: ResearchPacket,
    *,
    subjects: Sequence[dict[str, str]],
    user: UserState,
    language: str,
    notes: list[str],
) -> CalculatedAnswer | NotComputed | None:
    """The answer's computed calculation, what it could not compute, or None
    when it returned no calculation and its prose stands on its own."""
    if packet.calculation is None:
        if "{{" in packet.answer_markdown:
            _note(notes, MALFORMED_CALCULATION_REASON_CODE)
            return NotComputed(CALCULATION_NOT_COMPUTED_CODE, ())
        return None
    try:
        request = AnswerCalculation.model_validate(packet.calculation)
    except ValidationError:
        _note(notes, MALFORMED_CALCULATION_REASON_CODE)
        return NotComputed(CALCULATION_NOT_COMPUTED_CODE, ())
    from argus.domain.capability_registry import get_tool_catalog

    retrieved = retrieved_pages(packet)
    published = publish_calculation(
        request,
        template=packet.answer_markdown,
        language=language,
        catalog=get_tool_catalog(),
        retrieved=retrieved,
        currency=user.currency,
        subject_symbol=_first_symbol(subjects),
        market_close=latest_market_close,
        notes=notes,
    )
    if published is None:
        return NotComputed(CALCULATION_NOT_COMPUTED_CODE, ())
    if published.not_looked_up:
        return NotComputed(CALCULATION_NOT_COMPUTED_CODE, published.not_looked_up)
    return answer_from_published(
        request,
        published,
        prose=packet.answer_markdown,
        language=language,
        retrieved=retrieved,
    )


def offered_calculation(
    prose: str,
    offer: dict[str, Any],
    *,
    subjects: Sequence[dict[str, str]],
    user: UserState,
    notes: list[str],
) -> tuple[str, dict[str, Any]] | None:
    """A research answer never turns into a question: its calculation is offered
    on the reader's own figures, and the prose stands with any input it already
    holds filled and each sentence that leans on a result the offer cannot show
    left out. None only when nothing of the prose is left."""
    if "{{" in prose:
        from argus.domain.capability_registry import get_tool_catalog

        try:
            request = AnswerCalculation.model_validate(offer.get(PENDING_PAYLOAD_KEY))
            resolved = resolve_calculation(
                request,
                catalog=get_tool_catalog(),
                retrieved=[
                    ResearchSource.model_validate(page)
                    for page in offer.get("retrieved") or []
                ],
                currency=user.currency,
                subject_symbol=_first_symbol(subjects),
                market_close=latest_market_close,
                notes=notes,
            )
            if resolved is None:
                return None
            prose, dropped = render_offer_prose(
                prose, card_in(computed_answer_patch(resolved))
            )
        except (ValidationError, KeyError, ValueError):
            return None
        if not prose.strip():
            return None
        if dropped:
            _note(notes, OFFER_PROSE_TRIMMED_REASON_CODE)
    if CALCULATION_OFFERED_REASON_CODE not in notes:
        notes.append(CALCULATION_OFFERED_REASON_CODE)
    logger.info(
        "Calculation offered on the reader's own figures",
        kind=(offer.get(PENDING_PAYLOAD_KEY) or {}).get("kind"),
        requested_field=offer.get("requested_field"),
    )
    return prose, offer


def answer_without_lookup(
    *,
    message: str,
    language: str,
    user: UserState,
    subjects: Sequence[dict[str, str]],
    not_looked_up: Sequence[str],
    notes: list[str],
) -> CalculatedAnswer | None:
    """The no-search answer from Argus market data and stated assumptions."""
    if not message.strip() or not resolve_openrouter_api_key():
        return None
    facts: dict[str, str] = {}
    for subject in list(subjects)[:_MAX_MARKET_SUBJECTS]:
        close = latest_market_close(subject["symbol"])
        if close is not None:
            facts[f"{subject['symbol']} latest close"] = f"{close[0]:,.2f} on {close[1]}"
    answered = calculated_answer(
        message=message,
        language=language,
        user=user,
        notes=notes,
        market_facts=facts,
        not_looked_up=not_looked_up,
        subject_symbol=_first_symbol(subjects),
        lookup_failed=True,
    )
    if answered is not None:
        logger.info(
            "Answered without the failed lookup",
            not_looked_up=list(not_looked_up),
            computed=bool(answered.patch),
        )
    return answered


def retrieved_pages(packet: ResearchPacket) -> list[ResearchSource]:
    """Every page this answer retrieved: its sources and its cited rows' pages."""
    pages = list(packet.sources)
    seen = {page.url for page in pages}
    for row in packet.rows:
        if row.source_url and row.source_url not in seen:
            seen.add(row.source_url)
            pages.append(
                ResearchSource(
                    url=row.source_url,
                    title=f"{row.subject} {row.label}".strip(),
                    source_date=row.as_of,
                )
            )
    return pages


def _first_symbol(subjects: Sequence[dict[str, Any]]) -> str | None:
    return next((str(s["symbol"]) for s in subjects if s.get("symbol")), None)


def _note(notes: list[str], code: str) -> None:
    if code not in notes:
        notes.append(code)
    logger.info("Research calculation guard {}", code, failure_classification=code)
