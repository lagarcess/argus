"""Grounded research composition: packet in, finished turn out.

The router (``research_answer``) decides the question shape; this module owns
everything after that decision for the grounded shapes: config selection, the
provider call, the shared cache, verified peers, runnable rows, and the typed
research sidecar. The model may rank, explain, and format; it never mints a
symbol, strategy, action, or ask.

Truth boundary (spec section 4, same standing as the S10 memory lock):
research informs the reader, Argus providers execute the simulation. Nothing
returned by finance_search may reach a backtest; a test launched from a
research answer re-grounds through Argus market-data providers. This module
therefore never writes strategy, confirmation, or execution state: its stage
patch carries prose, sidecars, and rows only.

Coverage (spec section 5, probe-verified 2026-08-07): equities and ETFs route
to finance_search. Crypto and currency pairs never do: the live probe showed
"BTC" resolving to an ETF proxy and FX quotes returning empty, so a figure
about them answers from Argus's own Kraken-backed data with an honest coverage
note, and a claim about them (a forecast, a company story, why it moved) is
grounded on public pages with the finance tool left out (decision 10).
"""

from __future__ import annotations

import asyncio
import re
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING, Any

from loguru import logger

from argus.agent_runtime.profile.response_profile import (
    resolve_effective_response_profile,
)
from argus.agent_runtime.research_rows import (
    honest_no_next_line,
    research_next_experiment_rows,
    verified_peers,
)
from argus.agent_runtime.stages.interpret_types import (
    InterpretDecision,
    StageResult,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import (
    RunState,
    StrategySummary,
    UserState,
)
from argus.agent_runtime.substage_events import emit_substage
from argus.domain.market_data.new_york_clock import new_york_today
from argus.domain.research.admission import claim_current_research_attempt
from argus.domain.research.cache import (
    cache_get,
    cache_put,
    research_cache_key,
    ttl_for_packet,
)
from argus.domain.research.config import (
    ResearchConfigSpec,
    capability_class_for_shape,
    retrieval_spec,
)
from argus.domain.research.contracts import (
    MAX_PEER_PAIRS,
    CapabilityClass,
    QuestionShape,
    ResearchNamePair,
    ResearchPacket,
    ResearchUnavailableError,
    ResearchUsage,
    combined_research_usage,
)
from argus.domain.research.source_selection import (
    question_date,
    select_public_sources,
)

if TYPE_CHECKING:
    from argus.agent_runtime.research_answer import ResearchQueryExtraction

RESEARCH_SCHEMA_VERSION = "argus_research/v1"
# The sidecar's public surface, declared once so the documented example in
# docs/API_CONTRACT.md can be held against it rather than described in prose
# and drifting. `degraded` appears only on a degraded turn.
RESEARCH_SIDECAR_KEYS = frozenset(
    {
        "schema_version",
        "capability_class",
        "shape",
        "sources",
        "rows",
        "retrieved_at",
        "anchor_symbols",
        "peers",
        "usage",
        "follow_up",
        "degraded",
    }
)
SURVEY_CANDIDATE_SCAN_LIMIT = 32


def scenario_contract_applies(
    query: ResearchQueryExtraction, interpretation: StructuredInterpretation
) -> bool:
    """Whether this turn is a computed scenario (decision 10).

    Two independent typed facts say so and either is enough: the research
    query's ``scenario_question`` bit, or a ``future_window`` horizon the
    interpreter typed on the draft. Neither reads the message; a read that
    carries neither is an ordinary lookup and takes the recorded contract."""
    from argus.agent_runtime.interpreter.draft_shape import (
        strategy_draft_future_horizon,
    )

    return bool(getattr(query, "scenario_question", False)) or (
        strategy_draft_future_horizon(interpretation.candidate_strategy_draft) is not None
    )


def _cache_key_for(
    *,
    query: ResearchQueryExtraction,
    subjects: list[dict[str, str]],
    shape: QuestionShape,
    capability_class: CapabilityClass,
    message: str,
    language: str,
    scenario: bool = False,
) -> str:
    """One key recipe for every shape, so a packet stored by the thorough job
    finalizer serves the same question asked inline later."""
    return research_cache_key(
        capability_class=capability_class,
        shape=shape,
        symbols=tuple(s["symbol"] for s in subjects),
        period_key=(query.period_of_interest or "").strip().lower() or "current",
        question_fingerprint=" ".join(message.lower().split()),
        language=language,
        contract="scenario" if scenario else "retrieval",
    )


class _TurnSpend:
    """Every provider response one turn read, adopted, retried away, or
    rejected unread.

    Composition publishes at most one packet; the turn paid for all of them,
    so the spend it reports is their sum. The single seam that calls the
    provider records here, which is what keeps a later retry from losing its
    invoice by forgetting to add itself.
    """

    def __init__(self) -> None:
        self._usages: list[ResearchUsage] = []

    async def run(
        self, client: Any, prompt: str, spec: ResearchConfigSpec
    ) -> ResearchPacket:
        try:
            packet = await asyncio.to_thread(client.run_research, prompt, spec)
        except ResearchUnavailableError as exc:
            if exc.usage is not None:
                self._usages.append(exc.usage)
            raise
        self._usages.append(packet.usage)
        return packet

    @property
    def total(self) -> ResearchUsage | None:
        """What this turn paid, or None when it reached no provider."""
        return combined_research_usage(self._usages) if self._usages else None

    def reported(self, published: ResearchUsage) -> ResearchUsage:
        """The usage a composed turn reports: what it paid, or the served
        packet's own when it paid nothing, because a cache hit is free."""
        total = self.total
        if total is None:
            return published
        # The model names who produced the published answer; the numbers
        # beside it are the turn's, not one response's.
        return total.model_copy(update={"model": published.model or total.model})


async def grounded_result(
    *,
    query: ResearchQueryExtraction,
    subjects: list[dict[str, str]],
    shape: QuestionShape,
    interpretation: StructuredInterpretation,
    state: RunState,
    user: UserState,
    decision: InterpretDecision | None = None,
    provider_finance: bool = True,
) -> StageResult | None:
    scenario = scenario_contract_applies(query, interpretation)
    publisher_sources_required = requires_publisher_sources(query) or scenario
    question_as_of_date = question_date()
    capability_class = capability_class_for_shape(
        shape, screening=is_market_survey(query.question_kind)
    )
    language = language_tag(user.language_preference)
    spec = retrieval_spec(
        shape,
        question_kind=query.question_kind,
        closed_period=query.period_is_closed_window,
        language_tag=language,
        scenario=scenario,
    )
    if not provider_finance:
        # Crypto and currency pairs are outside the finance tool's coverage
        # (module docstring); a claim about them is grounded on public pages.
        spec = spec.model_copy(
            update={
                "tools": tuple(tool for tool in spec.tools if tool != "finance_search")
            }
        )
    prompt = _research_prompt(
        message=state.current_user_message,
        subjects=subjects,
        period=query.period_of_interest,
        language=language,
        question_kind=query.question_kind,
        criteria=list(getattr(query, "screening_criteria", []) or []),
        sector=getattr(query, "sector_of_interest", None),
        publisher_sources_required=publisher_sources_required,
        scenario=scenario,
    )
    key = _cache_key_for(
        query=query,
        subjects=subjects,
        shape=shape,
        capability_class=capability_class,
        message=state.current_user_message,
        language=language,
        scenario=scenario,
    )
    cache_status = "miss"
    spend = _TurnSpend()
    packet = cache_get(key)
    if packet is not None:
        cache_status = "hit"
    else:
        client = _client()
        if client is None:
            return unavailable_result(
                query=query,
                subjects=subjects,
                interpretation=interpretation,
                state=state,
                user=user,
                decision=decision,
                reason="not_configured",
                shape=shape,
            )
        admission = claim_current_research_attempt()
        if not admission.available:
            return await exhausted_result(
                query=query,
                subjects=subjects,
                interpretation=interpretation,
                state=state,
                user=user,
                decision=decision,
                guest_allowance_exhausted=admission.guest_exhausted,
                shape=shape,
            )
        emit_substage("research_search", detail=shape)
        try:
            packet = await spend.run(client, prompt, spec)
        except ResearchUnavailableError as exc:
            # The deployed log sink drops structured extras, so the reason and
            # detail must live in the message itself to be diagnosable.
            logger.warning(
                "Research provider unavailable"
                f" reason={exc.reason} detail={exc.detail or ''} shape={shape}",
            )
            return unavailable_result(
                query=query,
                subjects=subjects,
                interpretation=interpretation,
                state=state,
                user=user,
                decision=decision,
                reason=exc.reason,
                usage=spend.total,
                shape=shape,
            )
        retry_prompt: str | None = None
        if is_market_survey(query.question_kind) and not _has_figures(packet):
            # Asking again is deterministic escalation, not a second router:
            # a vague survey ("anything moving today?") lets the model answer
            # from memory, or retrieve and still state no figure, however
            # firmly the prompt asks, so the retry states the concrete
            # question the shape actually means. One retry only; if it still
            # comes back without figures the answer says so.
            logger.info(
                "Survey retried with the concrete ask"
                f" kind={query.question_kind}"
                f" reason={'no_retrieval' if not _retrieval_happened(packet) else 'no_rows'}"
            )
            retry_prompt = _survey_retry_prompt(
                question_kind=query.question_kind,
                message=state.current_user_message,
                language=language,
            )
        if retry_prompt is not None:
            try:
                retried = await spend.run(client, retry_prompt, spec)
            except ResearchUnavailableError:
                retried = None
            if retried is not None and (
                _has_figures(retried)
                or (_retrieval_happened(retried) and not _retrieval_happened(packet))
            ):
                packet = retried
        if publisher_sources_required and not _packet_has_public_sources(
            packet,
            query=query,
            question_as_of_date=question_as_of_date,
        ):
            # A narrative turn can land on finance-only evidence even though
            # balanced retrieval exposes public search. Retry once with that
            # provider-only channel removed, then fail closed if no public
            # publisher evidence survives.
            public_spec = spec.model_copy(
                update={
                    "tools": tuple(
                        tool for tool in spec.tools if tool != "finance_search"
                    )
                }
            )
            try:
                retried = await spend.run(
                    client,
                    _publisher_source_retry_prompt(prompt, language=language),
                    public_spec,
                )
            except ResearchUnavailableError:
                retried = None
            if retried is not None and _packet_has_public_sources(
                retried,
                query=query,
                question_as_of_date=question_as_of_date,
            ):
                packet = retried
    if publisher_sources_required and not _packet_has_public_sources(
        packet,
        query=query,
        question_as_of_date=question_as_of_date,
    ):
        # The claim is not publishable, but the packet is real and was paid
        # for: compose the honest note from it the way the thorough path
        # does, so the spend it cost reaches the sidecar and the ledger. It
        # is still never stored; a withheld-for-want-of-a-publisher packet
        # has nothing a later identical question could be served from.
        return _packet_stage_result(
            packet=packet.model_copy(update={"usage": spend.reported(packet.usage)}),
            subjects=subjects,
            shape=shape,
            capability_class=capability_class,
            language=language,
            interpretation=interpretation,
            user=user,
            cache_status=cache_status,
            period_of_interest=query.period_of_interest,
            question_kind=query.question_kind,
            period_start_date=_coerce_date(query.period_start_date),
            question_as_of_date=question_as_of_date,
            decision=decision,
            withheld_code="research_unavailable_missing_public_sources",
            scenario=scenario,
        )
    result = _packet_stage_result(
        packet=packet.model_copy(update={"usage": spend.reported(packet.usage)}),
        subjects=subjects,
        shape=shape,
        capability_class=capability_class,
        language=language,
        interpretation=interpretation,
        user=user,
        cache_status=cache_status,
        period_of_interest=query.period_of_interest,
        question_kind=query.question_kind,
        period_start_date=_coerce_date(query.period_start_date),
        question_as_of_date=question_as_of_date,
        decision=decision,
        scenario=scenario,
    )
    if cache_status == "miss":
        # The response's own packet is what is stored, not the turn-total copy
        # the sidecar reports: a later hit served from this record paid for one
        # response, not for the retries this turn happened to run.
        ttl_seconds = _cache_ttl(
            packet,
            withheld=_sidecar_withheld(result.stage_patch["research"]),
            question_kind=query.question_kind,
            closed_period=query.period_is_closed_window,
            scenario=scenario,
        )
        if ttl_seconds is not None:
            cache_put(key, packet, ttl_seconds=ttl_seconds)
    return result


def _packet_stage_result(
    *,
    packet: ResearchPacket,
    subjects: list[dict[str, str]],
    shape: QuestionShape,
    capability_class: CapabilityClass,
    language: str,
    interpretation: StructuredInterpretation,
    user: UserState,
    cache_status: str,
    period_of_interest: str | None = None,
    question_kind: str | None = None,
    period_start_date: date | None = None,
    question_as_of_date: date | None = None,
    decision: InterpretDecision | None = None,
    withheld_code: str | None = None,
    scenario: bool = False,
) -> StageResult:
    """Grounded packet to finished turn: verified peers, runnable rows, typed
    sidecar. One composition whether the packet came from the provider or the
    shared cache, for any shape.

    A retrieved answer publishes. A packet that did not retrieve is withheld
    for that first, since it has no page to find a publisher on.
    ``withheld_code`` is a reason the caller already established and the
    packet cannot show for itself, such as a claim whose retrieval kept no
    public publisher; a survey is also withheld when it names nothing the
    resolver verifies."""
    survey = is_market_survey(question_kind)
    answer = published_answer(packet, language)
    degraded_code = (
        _not_grounded_code(packet, survey=survey)
        or withheld_code
        or _scenario_inputs_code(packet, scenario=scenario)
    )
    peers: list[dict[str, str]] = []
    if degraded_code is None:
        # A withheld answer shows no peer, so a reason already established
        # spares the resolver a pass over names nothing will render.
        candidates = list(packet.name_pairs)
        if survey:
            # A survey's answer names its assets in the results, and often
            # only in its own tables; the resolver still gates every one.
            from argus.domain.research.perplexity_agent import (
                symbols_from_answer_tables,
            )

            seen = {pair.symbol.upper() for pair in candidates}
            for symbol in (
                *packet.tickers,
                *(row.symbol for row in packet.rows if row.symbol),
                *symbols_from_answer_tables(packet.answer_markdown),
            ):
                if symbol.upper() in seen:
                    continue
                seen.add(symbol.upper())
                candidates.append(ResearchNamePair(symbol=symbol, name=symbol))
        peers = verified_peers(
            candidates,
            exclude={s["symbol"] for s in subjects},
            # Surveys name many assets and lead with whatever moved most,
            # which is often untradable here; look past those before giving
            # up.
            scan_limit=SURVEY_CANDIDATE_SCAN_LIMIT if survey else MAX_PEER_PAIRS,
        )
    if degraded_code is None and survey:
        # A survey that retrieved is grounded when its prose names an asset
        # the resolver verifies; a name nothing here can trade is not one.
        named_symbols = _named_verified_symbols(
            packet.answer_markdown, [*subjects, *peers]
        )
        if named_symbols:
            subjects = [s for s in subjects if s["symbol"] in named_symbols]
            peers = [p for p in peers if p["symbol"] in named_symbols]
        else:
            degraded_code = "survey_synthesis_incomplete"
    if degraded_code is not None:
        # The subjects the user named stay testable; a survey named none.
        answer = _withheld_note(language, code=degraded_code, question_kind=question_kind)
        peers = []
        if survey:
            subjects = []
    if not subjects and peers:
        # A survey names no subject: what the provider found, once the
        # resolver verifies it, is what the user can test. Promoting the
        # first verified name keeps every answer one tap from a test.
        subjects = peers[:1]
        peers = peers[1:]
    rows = research_next_experiment_rows(
        subjects=subjects,
        peers=peers,
        language=language,
        entry_rule=getattr(interpretation.candidate_strategy_draft, "entry_rule", None),
    )
    if not rows and subjects:
        answer = f"{answer}\n\n{honest_no_next_line(language)}"
    return research_stage_result(
        answer=answer,
        interpretation=interpretation,
        user=user,
        capability_class=capability_class,
        shape=shape,
        packet=packet,
        peers=peers,
        rows=rows,
        subjects=subjects,
        cache_status=cache_status,
        period_of_interest=period_of_interest,
        degraded_code=degraded_code,
        question_kind=question_kind,
        decision=decision,
        period_start_date=period_start_date,
        question_as_of_date=question_as_of_date,
    )


def thorough_job_result(
    *,
    query: ResearchQueryExtraction,
    subjects: list[dict[str, str]],
    interpretation: StructuredInterpretation,
    user: UserState,
    message: str,
    decision: InterpretDecision | None = None,
) -> StageResult:
    """Thorough runs never block chat: the stage returns a typed job request
    and the API layer owns submission, polling, and the follow-up message
    through the existing job lifecycle. The shared cache sits in front: a
    packet stored by an earlier job finalizer answers the same question
    inline, with no job, no wait, and no provider spend."""
    language = language_tag(user.language_preference)
    capability_class = capability_class_for_shape(
        "thorough", screening=is_market_survey(query.question_kind)
    )
    scenario = scenario_contract_applies(query, interpretation)
    key = _cache_key_for(
        query=query,
        subjects=subjects,
        shape="thorough",
        capability_class=capability_class,
        message=message,
        language=language,
        scenario=scenario,
    )
    cached = cache_get(key)
    if cached is not None:
        return _packet_stage_result(
            packet=cached,
            subjects=subjects,
            shape="thorough",
            capability_class=capability_class,
            language=language,
            interpretation=interpretation,
            user=user,
            cache_status="hit",
            period_of_interest=query.period_of_interest,
            question_kind=query.question_kind,
            scenario=scenario,
            period_start_date=_coerce_date(query.period_start_date),
            question_as_of_date=question_date(),
            decision=decision,
        )
    subject_labels = ", ".join(f"{s['name']} [{s['symbol']}]" for s in subjects[:3])
    if language == "es-419":
        working = (
            "Estoy investigando esto a fondo"
            + (f" sobre {subject_labels}" if subject_labels else "")
            + ". Te aviso aquí cuando el resultado esté listo."
        )
    else:
        working = (
            "I'm researching this thoroughly"
            + (f" on {subject_labels}" if subject_labels else "")
            + ". I'll post the result here when it's ready."
        )
    decision = carried_decision(
        decision,
        interpretation=interpretation,
        user=user,
        reason_code=f"research_answer_{capability_class}",
    )
    return StageResult(
        outcome="ready_to_respond",
        decision=decision,
        stage_patch={
            "assistant_response": working,
            "research_job_request": {
                "capability_class": capability_class,
                "shape": "thorough",
                "language": language,
                "question": message,
                "subjects": subjects,
                "period_of_interest": query.period_of_interest,
                "period_is_closed_window": query.period_is_closed_window,
                "period_start_date": (
                    query.period_start_date.isoformat()
                    if query.period_start_date is not None
                    else None
                ),
                "question_as_of_date": question_date().isoformat(),
                "question_kind": query.question_kind,
                "requires_publisher_sources": requires_publisher_sources(query)
                or scenario,
                "scenario_question": scenario,
                # The exact key computed at classification time; completion
                # paths store under it verbatim so later identical questions
                # hit without recomputation drift.
                "cache_key": key,
            },
        },
    )


async def off_coverage_result(
    *,
    query: ResearchQueryExtraction,
    subjects: list[dict[str, str]],
    interpretation: StructuredInterpretation,
    state: RunState,
    user: UserState,
    decision: InterpretDecision | None = None,
) -> StageResult | None:
    """Crypto and currency pairs degrade honestly: Argus's own provider data
    for figures, an explicit coverage note, and a runnable next step."""
    language = language_tag(user.language_preference)
    focus = [s for s in subjects if s["asset_class"] != "equity"] or subjects
    facts: dict[str, Any] = {}
    for subject in focus[:2]:
        closed = await _latest_close(subject["symbol"], subject["asset_class"])
        if closed is not None:
            facts[subject["symbol"]] = closed["text"]
    note = _coverage_note(language)
    if facts:
        from argus.agent_runtime import knowledge_answer as ka

        fact_lines = {**facts, "coverage_note": note}
        answer = await ka._voiced_answer(
            message=state.current_user_message,
            language=user.language_preference,
            facts=fact_lines,
            fallback="\n\n".join([*facts.values(), f"*{note}*"]),
            user=user,
        )
    else:
        answer = note
    if answer is None:
        answer = note
    peers: list[dict[str, str]] = []
    rows = research_next_experiment_rows(
        subjects=focus or subjects, peers=peers, language=language
    )
    if not rows and (focus or subjects):
        answer = f"{answer}\n\n{honest_no_next_line(language)}"
    packet = ResearchPacket(answer_markdown=answer)
    shape = shape_for_query(query)
    return research_stage_result(
        answer=answer,
        interpretation=interpretation,
        user=user,
        capability_class=capability_class_for_shape(
            shape,
            screening=is_market_survey(query.question_kind),
        ),
        shape=shape,
        packet=packet,
        peers=peers,
        rows=rows,
        subjects=focus or subjects,
        cache_status="bypass",
        degraded_code="asset_class_not_covered",
        period_of_interest=query.period_of_interest,
        decision=decision,
    )


async def exhausted_result(
    *,
    query: ResearchQueryExtraction,
    subjects: list[dict[str, str]],
    interpretation: StructuredInterpretation,
    state: RunState,
    user: UserState,
    guest_allowance_exhausted: bool,
    shape: QuestionShape,
    decision: InterpretDecision | None = None,
) -> StageResult | None:
    """Ceiling exhaustion is an honest, localized note, not a silent
    disappearance: the answer still comes from Argus's own data or model
    knowledge, and still ends somewhere runnable. ``shape`` is the shape the
    turn was actually selected for, so the sidecar and the ledger record the
    work that was attempted rather than a shape re-derived from the query."""
    language = language_tag(user.language_preference)
    note = research_capacity_exhausted_note(
        language,
        guest_allowance=guest_allowance_exhausted,
    )
    from argus.agent_runtime import knowledge_answer as ka

    answer: str | None = None
    if subjects:
        legacy = ka.KnowledgeQueryExtraction(
            question_kind="market_stats",
            symbols=[s["symbol"] for s in subjects],
            date_range_raw_text=query.date_range_raw_text or query.period_of_interest,
        )
        answer = await ka._market_stats_answer(
            query=legacy,
            interpretation=interpretation,
            message=state.current_user_message,
            language=user.language_preference,
            user=user,
        )
    if answer is None:
        answer = note
    else:
        answer = f"{answer}\n\n*{note}*"
    rows = research_next_experiment_rows(subjects=subjects, peers=[], language=language)
    packet = ResearchPacket(answer_markdown=answer)
    return research_stage_result(
        answer=answer,
        interpretation=interpretation,
        user=user,
        capability_class=capability_class_for_shape(
            shape,
            screening=is_market_survey(query.question_kind),
        ),
        shape=shape,
        packet=packet,
        peers=[],
        rows=rows,
        subjects=subjects,
        cache_status="bypass",
        degraded_code="research_capacity_exhausted",
        period_of_interest=query.period_of_interest,
        decision=decision,
    )


def unavailable_result(
    *,
    query: ResearchQueryExtraction,
    subjects: list[dict[str, str]],
    interpretation: StructuredInterpretation,
    state: RunState,
    user: UserState,
    reason: str,
    shape: QuestionShape,
    decision: InterpretDecision | None = None,
    usage: ResearchUsage | None = None,
) -> StageResult | None:
    """The honest note when no packet survived.

    ``usage`` is the spend of the responses the turn read and rejected. There
    is no packet to compose from, so the note's own carries it instead: a turn
    that reached the provider is a miss that cost what it cost, and only a
    turn that never called one bypasses the meter."""
    del state
    language = language_tag(user.language_preference)
    # No reason reaching here has a note of its own: a claim withheld for want
    # of a publisher has a real packet and composes through _packet_stage_result.
    note = _unavailable_note(language)
    rows = research_next_experiment_rows(subjects=subjects, peers=[], language=language)
    if not rows and subjects:
        note = f"{note}\n\n{honest_no_next_line(language)}"
    packet = ResearchPacket(
        answer_markdown=note, usage=usage if usage is not None else ResearchUsage()
    )
    return research_stage_result(
        answer=note,
        interpretation=interpretation,
        user=user,
        capability_class=capability_class_for_shape(
            shape,
            screening=is_market_survey(query.question_kind),
        ),
        shape=shape,
        packet=packet,
        peers=[],
        rows=rows,
        subjects=subjects,
        cache_status="bypass" if usage is None else "miss",
        degraded_code=f"research_unavailable_{reason}",
        period_of_interest=query.period_of_interest,
        decision=decision,
    )


def shape_for_kind(kind: str) -> QuestionShape:
    if kind == "live_quote":
        return "fast"
    if kind in (
        "company_lookup",
        "etf_constituents",
        "current_external",
    ) or is_market_survey(kind):
        return "balanced"
    return "thorough"


def requires_publisher_sources(query: ResearchQueryExtraction) -> bool:
    """Whether publishing the requested claim requires a public publisher.

    Company reads and current external facts ("why is it moving") are
    claim-shaped by definition. The explicit classifier bit is the
    multilingual escape hatch for a mixed quote plus narrative request that
    might otherwise retain the quote kind.
    """
    return (
        bool(getattr(query, "requires_publisher_sources", False))
        # A computed scenario is grounded on published inputs, whatever kind
        # the question was typed as (decision 10).
        or bool(getattr(query, "scenario_question", False))
        or query.question_kind in ("company_lookup", "current_external")
    )


def shape_for_query(query: ResearchQueryExtraction) -> QuestionShape:
    shape = shape_for_kind(query.question_kind)
    if shape == "fast" and requires_publisher_sources(query):
        return "balanced"
    return shape


async def _latest_close(symbol: str, asset_class: str) -> dict[str, str] | None:
    try:
        from datetime import timedelta

        from argus.domain.market_data.provider import fetch_price_series

        end = new_york_today()
        start = end - timedelta(days=14)
        series = await asyncio.to_thread(
            fetch_price_series, symbol, asset_class, start, end, "1d"
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("Off-coverage close fetch failed", symbol=symbol, error=str(exc))
        return None
    values = series.tolist() if hasattr(series, "tolist") else list(series or [])
    closes = [float(v) for v in values if v is not None]
    if not closes:
        return None
    index = getattr(series, "index", None)
    as_of = ""
    try:
        if index is not None and len(index) > 0:
            as_of = str(index[-1])[:10]
    except Exception:  # noqa: BLE001
        as_of = ""
    return {
        "text": f"{symbol}: {closes[-1]:,.2f}" + (f" (as of {as_of})" if as_of else ""),
        "as_of": as_of,
    }


def _client():
    from argus.domain.research.credentials import perplexity_api_key
    from argus.domain.research.perplexity_agent import PerplexityAgentClient

    api_key = perplexity_api_key()
    if not api_key:
        return None
    return PerplexityAgentClient(api_key)


# Survey shapes name no subject, so the answer must carry the assets it found
# and the conditions it actually applied; a screen that ignores the stated
# threshold is worse than no screen.
# A survey answered from memory is the one failure the shape cannot have, so
# the instruction asks for retrieved figures. It never names a mechanism:
# asking the model to account for which tool it used is what produced
# answers narrating "the requested finance_search tool was not available".
# Whether retrieval happened is a typed fact on the packet, and the honest
# line renders from that, not from the model explaining itself.
_SURVEY_TOOL_REQUIREMENT = (
    "Retrieve these figures from current market data before answering; do "
    "not answer from memory. If you cannot retrieve them, say only that you "
    "could not retrieve current figures, with no explanation of why."
)

_SURVEY_GUIDANCE: dict[str, str] = {
    "market_pulse": (
        "Report what the market is actually doing right now: name the "
        "specific gainers, losers, and most active names with their real "
        "figures and the as-of time. Name the tickers explicitly."
    ),
    "screening": (
        "Apply every stated condition and say plainly which condition each "
        "named asset satisfies, with the figure that proves it. Name the "
        "tickers explicitly. If a condition cannot be evaluated from "
        "available data, say so rather than dropping it silently."
    ),
    "sector_radar": (
        "Explain what is actually happening in this sector right now: how it "
        "is performing, what is driving it, and which names lead or lag, with "
        "real figures. Name the tickers explicitly. This is sector analysis, "
        "not a list of company descriptions."
    ),
}


_SURVEY_RETRY_LINES: dict[str, str] = {
    "market_pulse": (
        "Retrieve today's top gainers, top losers, and most active US-listed "
        "stocks with their percentage moves, prices, and volumes."
    ),
    "screening": (
        "Retrieve current fundamentals for candidate assets and report the "
        "figure that proves each stated condition."
    ),
    "sector_radar": (
        "Retrieve current performance figures for this sector's leading "
        "names and its sector ETFs."
    ),
}


def _survey_retry_prompt(
    *, question_kind: str | None, message: str, language: str
) -> str:
    """The concrete question the shape means, asked first.

    The first attempt led with the user's vague words and the model answered
    from memory. Leading with the data request is what gets the tool called;
    the user's words follow as context, not as the whole ask."""
    lines = [_SURVEY_RETRY_LINES.get(str(question_kind or ""), "")]
    lines.append(f"The user asked: {message.strip()}")
    lines.append(
        "Lead with the figures you retrieve and state their as-of time. If "
        "retrieval fails, say only that you could not retrieve current "
        "figures. Do not write a sources line, include links, or name any "
        "tool, provider, or internal system."
    )
    lines.append(
        "Responde en español latinoamericano (es-419)."
        if language == "es-419"
        else "Answer in English."
    )
    return "\n".join(line for line in lines if line)


def _publisher_source_retry_prompt(prompt: str, *, language: str) -> str:
    lines = [
        prompt,
        "Retry the same question. Ground every claim in a public publisher, "
        "regulatory filing, investor-relations page, or company page. If no "
        "such page is available, answer only that the claim could not be "
        "verified. Do not write a sources or citations line and do not include "
        "links.",
        (
            "Responde en español latinoamericano (es-419)."
            if language == "es-419"
            else "Answer in English."
        ),
    ]
    return "\n".join(lines)


def _retrieval_happened(packet: ResearchPacket) -> bool:
    # The provider's output is the retrieval record. Invoice counts are
    # billing: unknown (None) and zero are both absence of evidence here.
    usage = packet.usage
    return bool(
        packet.tool_results
        or packet.sources
        or usage.finance_search_invocations
        or usage.web_search_invocations
        or usage.fetch_url_invocations
    )


def _has_figures(packet: ResearchPacket) -> bool:
    """Whether a survey packet carries a figure to build on: a typed
    answer's rows, or for a prose answer the fact that it retrieved at all.
    This drives the one concrete retry, never a refusal."""
    if not _retrieval_happened(packet):
        return False
    return bool(packet.rows) if packet.typed_answer else True


def _sidecar_withheld(sidecar: dict[str, Any]) -> bool:
    """Whether the composed turn withheld its answer: the sidecar's typed
    ``degraded`` state, the same fact the ledger and the client read."""
    return bool(sidecar.get("degraded"))


def _cache_ttl(
    packet: ResearchPacket,
    *,
    withheld: bool,
    question_kind: str | None,
    closed_period: bool,
    scenario: bool = False,
) -> float | None:
    """How long the shared cache serves this packet, or None to not store it.

    One owner for both composition paths, fed by what composition actually
    produced: a published packet serves for its class TTL, a withheld packet
    that retrieved for that TTL capped at a day, and a packet that never
    retrieved is not stored, published or not: a model that did not look is
    evidence about the model and not about the world, and the shared cache
    holds provider packets about public markets, never one turn's prose for
    every other user."""
    if not _retrieval_happened(packet):
        return None
    return ttl_for_packet(
        question_kind=question_kind,
        categories=packet.categories,
        closed_period=closed_period,
        withheld=withheld,
        scenario=scenario,
    )


def published_answer(packet: ResearchPacket, language: str) -> str:
    """The answer as the reader gets it: the prose the provider wrote and,
    under it, the figures the model wrote with no citation, named from their
    own typed subject and label. An answer is never withheld for a row; a
    figure without a source is said to be one, beneath the answer."""
    if not packet.unsourced_rows:
        return packet.answer_markdown
    figures = [
        " ".join(part for part in (row.subject.strip(), row.label.strip()) if part)
        for row in packet.unsourced_rows
    ]
    note = _unsourced_figure_note(language, figures=figures)
    return f"{packet.answer_markdown}\n\n{note}"


def _not_grounded_code(packet: ResearchPacket, *, survey: bool) -> str | None:
    """The withholding a packet shows for itself, on either composition path: a
    response that retrieved nothing has no source for anything it says."""
    if _retrieval_happened(packet):
        return None
    return "survey_not_grounded" if survey else "research_not_grounded"


def _scenario_inputs_code(packet: ResearchPacket, *, scenario: bool) -> str | None:
    """A computed scenario publishes only on cited inputs (decision 10).

    The provider's schema allows an answer with no rows, and a page in
    ``sources`` proves retrieval, not that a forecast, target or multiple the
    arithmetic used was read from it. At least one input row must cite a
    public page; the current price alone, read from the provider's own
    finance page, is not a forecast."""
    if not scenario:
        return None
    if any(row.source_url for row in packet.rows):
        return None
    logger.info(
        "Scenario withheld: no input row cites a public page"
        f" rows={len(packet.rows)} unsourced={len(packet.unsourced_rows)}"
        f" sources={len(packet.sources)}"
    )
    return "scenario_inputs_uncited"


def _withheld_note(language: str, *, code: str, question_kind: str | None) -> str:
    """The honest line for a withheld answer, keyed by its degraded code."""
    if code == "research_unavailable_missing_public_sources":
        return _missing_public_source_note(language)
    if code == "research_not_grounded":
        return _not_grounded_note(language)
    if code == "scenario_inputs_uncited":
        return _scenario_inputs_uncited_note(language)
    return _survey_recovery_note(
        language,
        question_kind=question_kind,
        retrieval_happened=code != "survey_not_grounded",
    )


def _packet_has_public_sources(
    packet: ResearchPacket,
    *,
    query: ResearchQueryExtraction,
    question_as_of_date: date,
) -> bool:
    return bool(
        select_public_sources(
            packet.sources,
            question_kind=query.question_kind,
            period_start=_coerce_date(query.period_start_date),
            question_as_of=question_as_of_date,
        )
    )


def is_market_survey(question_kind: str | None) -> bool:
    return str(question_kind or "") in _SURVEY_GUIDANCE


def _research_prompt(
    *,
    message: str,
    subjects: list[dict[str, str]],
    period: str | None,
    language: str,
    question_kind: str | None = None,
    criteria: list[str] | None = None,
    sector: str | None = None,
    publisher_sources_required: bool = False,
    scenario: bool = False,
) -> str:
    """Documented prompt guidance: business question first, then tickers and
    the time window; state the desired outcome, let the tool pick fields."""
    lines = [message.strip()]
    if subjects:
        lines.append(
            "Tickers: " + ", ".join(f"{s['name']} ({s['symbol']})" for s in subjects)
        )
    if sector:
        lines.append(f"Sector or theme: {sector}")
    for condition in criteria or []:
        lines.append(f"Required condition: {condition}")
    if period:
        lines.append(f"Time window: {period}")
    survey_guidance = _SURVEY_GUIDANCE.get(str(question_kind or ""))
    if survey_guidance:
        lines.append(survey_guidance)
        lines.append(_SURVEY_TOOL_REQUIREMENT)
    if publisher_sources_required:
        lines.append(
            "Ground every narrative or causal claim in at least one public "
            "publisher, filing, investor-relations, or company page before "
            "answering. If no such page is available, say only that the "
            "claim could not be verified."
        )
    if scenario:
        lines.append(
            "The answer is a set of scenarios you compute from published inputs, "
            "as the instructions describe: inputs rowed with their pages, the "
            "arithmetic written out, labeled ranges from low to high, no single "
            "number as the future, no advice."
        )
    lines.append(
        "Answer the question directly for a curious non-expert, leading with "
        "the answer. Use compact tables only where they genuinely help. State "
        "the as-of date for any current figure. If a figure is unavailable, "
        "say so plainly; never estimate a live number. No investment advice. "
        "Do not write a sources or citations line and do not include links: "
        "the interface lists sources beside your answer. Never name tools, "
        "providers, models, or internal systems."
    )
    if language == "es-419":
        lines.append("Responde en español latinoamericano (es-419).")
    else:
        lines.append("Answer in English.")
    return "\n".join(lines)


def language_tag(language_preference: str | None) -> str:
    return "es-419" if str(language_preference or "").startswith("es") else "en"


def _coverage_note(language: str) -> str:
    if language == "es-419":
        return (
            "La investigación de mercado en vivo cubre acciones y ETFs, así "
            "que para este activo uso los datos propios de Argus."
        )
    return (
        "Live market research covers stocks and ETFs, so for this asset I "
        "use Argus's own market data."
    )


def research_capacity_exhausted_note(
    language: str, *, guest_allowance: bool = False
) -> str:
    """Name the bound that actually closed, never a more flattering one."""
    if guest_allowance:
        if language == "es-419":
            return (
                "Usaste tus consultas de investigación gratis de hoy, así que "
                "respondo con los datos propios de Argus y lo que ya sé. Crea "
                "una cuenta para seguir investigando; probar ideas sigue "
                "disponible."
            )
        return (
            "You've used today's free research questions, so this answer "
            "comes from Argus's own data and what I already know. Create an "
            "account to keep researching; testing ideas is still available."
        )
    if language == "es-419":
        return (
            "La capacidad compartida de investigación de hoy se agotó, así "
            "que respondo con los datos propios de Argus y lo que ya sé. "
            "Vuelve a preguntar mañana para una lectura en vivo; probar ideas "
            "sigue disponible."
        )
    return (
        "Today's shared research capacity is used up, so this answer comes "
        "from Argus's own data and what I already know. Ask again tomorrow "
        "for a live read; testing ideas is still available."
    )


def _named_verified_symbols(answer: str, assets: list[dict[str, str]]) -> set[str]:
    """Verified subjects the answer concretely names.

    Survey prompts require explicit tickers. Matching only resolver-verified
    ticker tokens keeps this validation language-independent and prevents a
    typed candidate hidden in provider metadata from becoming the subject of
    user copy that never actually named it.
    """
    named: set[str] = set()
    for asset in assets:
        symbol = str(asset.get("symbol") or "").upper()
        if not symbol:
            continue
        token_pattern = rf"(?<!\w){re.escape(symbol)}(?!\w)"
        if not re.search(token_pattern, answer):
            continue
        if len(symbol) > 2 or _short_symbol_is_unambiguous(
            answer,
            symbol=symbol,
            asset_name=str(asset.get("name") or ""),
        ):
            named.add(symbol)
    return named


def _short_symbol_is_unambiguous(
    answer: str,
    *,
    symbol: str,
    asset_name: str,
) -> bool:
    escaped = re.escape(symbol)
    if re.search(rf"\${escaped}(?!\w)", answer):
        return True
    if re.search(rf"\(\s*{escaped}\s*\)", answer):
        return True
    if re.search(rf"\|\s*{escaped}\s*\|", answer):
        return True
    if not asset_name:
        return False
    token_pattern = rf"(?<!\w){escaped}(?!\w)"
    folded_name = asset_name.casefold()
    return any(
        folded_name in line.casefold() and re.search(token_pattern, line)
        for line in answer.splitlines()
    )


def _survey_recovery_note(
    language: str,
    *,
    question_kind: str | None,
    retrieval_happened: bool,
) -> str:
    kind = str(question_kind or "")
    if language == "es-419":
        if not retrieval_happened:
            return {
                "market_pulse": "No pude recuperar los movimientos del mercado de hoy.",
                "screening": (
                    "No pude recuperar datos actuales para aplicar las condiciones "
                    "solicitadas."
                ),
                "sector_radar": (
                    "No pude recuperar los líderes y rezagados actuales del sector."
                ),
            }.get(kind, "No pude recuperar los datos de mercado solicitados.")
        return {
            "market_pulse": (
                "Encontré fuentes, pero no pude extraer de ellas los movimientos "
                "del mercado de hoy."
            ),
            "screening": (
                "Encontré fuentes, pero no pude extraer activos que cumplan las "
                "condiciones solicitadas."
            ),
            "sector_radar": (
                "Encontré fuentes, pero no pude extraer los líderes y rezagados "
                "actuales del sector."
            ),
        }.get(kind, "Encontré fuentes, pero no pude extraer los activos solicitados.")
    if not retrieval_happened:
        return {
            "market_pulse": "I couldn't retrieve today's market movers.",
            "screening": (
                "I couldn't retrieve current data to apply the requested conditions."
            ),
            "sector_radar": (
                "I couldn't retrieve the sector's current leaders and laggards."
            ),
        }.get(kind, "I couldn't retrieve the requested market data.")
    return {
        "market_pulse": (
            "I found sources, but could not extract today's market movers from them."
        ),
        "screening": (
            "I found sources, but could not extract assets that satisfy the "
            "requested conditions."
        ),
        "sector_radar": (
            "I found sources, but could not extract the sector's current leaders "
            "and laggards."
        ),
    }.get(kind, "I found sources, but could not extract the requested assets.")


def _unavailable_note(language: str) -> str:
    if language == "es-419":
        return (
            "No pude completar la búsqueda de datos en este momento, así que "
            "no voy a citar cifras en vivo. Probar una idea con datos "
            "históricos sigue disponible."
        )
    return (
        "I couldn't complete the data lookup just now, so I won't quote live "
        "figures. Testing an idea against historical data is still available."
    )


def _missing_public_source_note(language: str) -> str:
    if language == "es-419":
        return (
            "No pude verificar esa explicación con una fuente pública, así que "
            "no la presentaré como un hecho."
        )
    return (
        "I couldn't verify that explanation with a public source, so I won't "
        "present it as fact."
    )


def _scenario_inputs_uncited_note(language: str) -> str:
    if language == "es-419":
        return (
            "Encontré páginas sobre esto, pero ninguno de los insumos que un "
            "escenario necesita (un pronóstico publicado, un objetivo o un "
            "múltiplo) llegó con su cita, así que no voy a calcular un rango con "
            "ellos. Puedes preguntar de nuevo, o probar la idea con datos históricos."
        )
    return (
        "I found pages on this, but none of the inputs a scenario needs (a "
        "published forecast, target or multiple) came with its citation, so I "
        "won't compute a range from them. You can ask again, or test the idea "
        "against historical data."
    )


def _not_grounded_note(language: str) -> str:
    if language == "es-419":
        return "No pude recuperar los datos para responder esta pregunta."
    return "I couldn't retrieve the data to answer this question."


def _unsourced_figure_note(language: str, *, figures: list[str]) -> str:
    """The line under an answer naming the figures it could not tie to a
    source. The figures stay in the answer; only their standing is said."""
    named = [figure for figure in figures if figure]
    if language == "es-419":
        if named:
            return f"No pude vincular {_joined(named, 'ni')} a una fuente."
        return "No pude vincular todas las cifras de esta respuesta a una fuente."
    if named:
        return f"I couldn't tie {_joined(named, 'or')} to a source."
    return "I couldn't tie every figure in this answer to a source."


def _joined(items: list[str], conjunction: str) -> str:
    if len(items) == 1:
        return items[0]
    return f"{', '.join(items[:-1])} {conjunction} {items[-1]}"


def retrieval_spec_for_job(job_request: dict[str, Any]) -> ResearchConfigSpec:
    """The thorough configuration with the job's own retrieval parameters,
    rebuilt from the typed job request the same way the prompt is."""
    return retrieval_spec(
        "thorough",
        question_kind=str(job_request.get("question_kind") or "cross_company"),
        closed_period=bool(job_request.get("period_is_closed_window")),
        language_tag=str(job_request.get("language") or "en"),
        scenario=bool(job_request.get("scenario_question")),
    )


def research_prompt_for_job(job_request: dict[str, Any]) -> str:
    """Rebuild the documented prompt from the typed job request."""
    subjects = [
        {
            "symbol": str(s.get("symbol") or ""),
            "name": str(s.get("name") or s.get("symbol") or ""),
            "asset_class": str(s.get("asset_class") or "equity"),
        }
        for s in job_request.get("subjects") or []
        if isinstance(s, dict) and s.get("symbol")
    ]
    return _research_prompt(
        message=str(job_request.get("question") or ""),
        subjects=subjects,
        period=job_request.get("period_of_interest"),
        language=str(job_request.get("language") or "en"),
        question_kind=str(job_request.get("question_kind") or "cross_company"),
        publisher_sources_required=bool(job_request.get("requires_publisher_sources")),
        scenario=bool(job_request.get("scenario_question")),
    )


def store_research_packet_for_job(
    job_request: dict[str, Any],
    packet: ResearchPacket,
    composed: dict[str, Any],
) -> None:
    """Store a completed thorough packet in the shared cache so the same
    question answers inline for its class TTL, withheld or not, under the
    one rule ``_cache_ttl`` owns, read from the answer composition produced.
    A packet lacking a required public source is not stored: the inline hit
    path re-derives that requirement and the thorough one does not. Both
    completion paths call this after ``compose_completed_research``."""
    key = str(job_request.get("cache_key") or "")
    question_kind = str(job_request.get("question_kind") or "cross_company")
    if not key:
        return
    if job_request.get("requires_publisher_sources") and not typed_sources(
        packet,
        question_kind=question_kind,
        period_start_date=job_request.get("period_start_date"),
        question_as_of_date=job_request.get("question_as_of_date"),
    ):
        return
    ttl_seconds = _cache_ttl(
        packet,
        withheld=_sidecar_withheld(composed["research"]),
        question_kind=question_kind,
        closed_period=bool(job_request.get("period_is_closed_window")),
        scenario=bool(job_request.get("scenario_question")),
    )
    if ttl_seconds is not None:
        cache_put(key, packet, ttl_seconds=ttl_seconds)


def compose_completed_research(
    *,
    job_request: dict[str, Any],
    packet: ResearchPacket,
) -> dict[str, Any]:
    """Compose the finalized thorough answer: verified peers, runnable rows,
    and the typed research sidecar. Shared by the job finalizer and the dev
    synchronous fallback so both paths produce identical artifacts."""
    language = str(job_request.get("language") or "en")
    subjects = [
        {
            "symbol": str(s.get("symbol") or ""),
            "name": str(s.get("name") or s.get("symbol") or ""),
            "asset_class": str(s.get("asset_class") or "equity"),
        }
        for s in job_request.get("subjects") or []
        if isinstance(s, dict) and s.get("symbol")
    ]
    question_kind = str(job_request.get("question_kind") or "cross_company")
    sources = typed_sources(
        packet,
        question_kind=question_kind,
        period_start_date=job_request.get("period_start_date"),
        question_as_of_date=job_request.get("question_as_of_date"),
    )
    degraded_code = (
        _not_grounded_code(packet, survey=is_market_survey(question_kind))
        or (
            "research_unavailable_missing_public_sources"
            if job_request.get("requires_publisher_sources") and not sources
            else None
        )
        or _scenario_inputs_code(
            packet, scenario=bool(job_request.get("scenario_question"))
        )
    )
    peers = (
        []
        if degraded_code is not None
        else verified_peers(packet.name_pairs, exclude={s["symbol"] for s in subjects})
    )
    if not subjects and peers:
        # A survey names no subject: what the provider found, once the
        # resolver verifies it, is what the user can test. Promoting the
        # first verified name keeps every answer one tap from a test.
        subjects = peers[:1]
        peers = peers[1:]
    rows = research_next_experiment_rows(
        subjects=subjects, peers=peers, language=language
    )
    answer = (
        _withheld_note(language, code=degraded_code, question_kind=question_kind)
        if degraded_code is not None
        else published_answer(packet, language)
    )
    if not rows and subjects:
        answer = f"{answer}\n\n{honest_no_next_line(language)}"
    capability_class = str(job_request.get("capability_class") or "thorough_research")
    return {
        "answer": answer,
        "research": build_research_sidecar(
            capability_class=capability_class,
            shape="thorough",
            sources=sources,
            retrieved_rows=typed_rows(packet),
            retrieved_at=packet.retrieved_at.isoformat(),
            subjects=subjects,
            peers=peers,
            usage={
                "invocations": packet.usage.invocations,
                "latency_ms": packet.usage.latency_ms,
                "cost_usd": packet.usage.cost_usd,
                # Composition only ever runs on a packet a provider run produced;
                # cache hits answer inline and never reach a job.
                "cache_status": "miss",
            },
            period_of_interest=(
                str(job_request.get("period_of_interest"))
                if job_request.get("period_of_interest")
                else None
            ),
            degraded_code=degraded_code,
        ),
        "next_experiments": rows,
    }


def research_failure_note(language: str) -> str:
    if language == "es-419":
        return (
            "No pude terminar esa investigación a fondo. No voy a citar "
            "cifras que no verifiqué; puedes preguntar de nuevo, o probar la "
            "idea con datos históricos ahora mismo."
        )
    return (
        "I couldn't finish that thorough research run. I won't quote figures "
        "I didn't verify; you can ask again, or test the idea against "
        "historical data right now."
    )


def research_capacity_exhausted_for_job(
    job_request: dict[str, Any],
    *,
    guest_allowance_exhausted: bool,
) -> dict[str, Any]:
    """Build the honest terminal payload when a thorough claim loses."""

    language = language_tag(str(job_request.get("language") or "en"))
    subjects = [
        subject
        for subject in job_request.get("subjects") or []
        if isinstance(subject, dict) and subject.get("symbol")
    ]
    return {
        "answer": research_capacity_exhausted_note(
            language,
            guest_allowance=guest_allowance_exhausted,
        ),
        "research": build_research_sidecar(
            capability_class=str(
                job_request.get("capability_class") or "thorough_research"
            ),
            shape="thorough",
            sources=[],
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            subjects=subjects,
            peers=[],
            usage={
                "invocations": 0,
                "latency_ms": None,
                "cost_usd": None,
                "cache_status": "bypass",
            },
            period_of_interest=(
                str(job_request["period_of_interest"])
                if job_request.get("period_of_interest")
                else None
            ),
            degraded_code="research_capacity_exhausted",
        ),
    }


def research_billed_failure_evidence(
    job_request: dict[str, Any],
    *,
    reason: str,
    usage: ResearchUsage,
) -> dict[str, Any]:
    """The cost ledger's view of a thorough run that was billed and whose
    answer could not be read.

    Not the turn's sidecar: the failure note carries none, and nothing here
    reaches a reader. It exists so a run Argus paid for is recorded as spend
    rather than disappearing with the answer nobody could parse."""
    return build_research_sidecar(
        capability_class=str(job_request.get("capability_class") or "thorough_research"),
        shape="thorough",
        sources=[],
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        subjects=[],
        peers=[],
        usage={
            "invocations": usage.invocations,
            "latency_ms": usage.latency_ms,
            "cost_usd": usage.cost_usd,
            "cache_status": "miss",
        },
        period_of_interest=None,
        degraded_code=f"research_unavailable_{reason}",
    )


def carried_decision(
    decision: InterpretDecision | None,
    *,
    interpretation: StructuredInterpretation,
    user: UserState,
    reason_code: str,
) -> InterpretDecision:
    """The typed decision is the turn's identity; a serving operation may add
    its reason code but never relabel the act or drop the discovery payload.

    A rail diversion that rebuilt the decision used to overwrite a typed
    asset_discovery turn with semantic_turn_act=educational_question and
    asset_discovery=None (#344): the user's request survived, its identity
    did not."""
    if decision is None:
        return research_decision(interpretation, user, reason_code)
    return decision.model_copy(
        update={
            "reason_codes": list(dict.fromkeys([*decision.reason_codes, reason_code]))
        }
    )


def research_decision(
    interpretation: StructuredInterpretation,
    user: UserState,
    reason_code: str,
) -> InterpretDecision:
    return InterpretDecision(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary=interpretation.user_goal_summary,
        candidate_strategy_draft=StrategySummary(),
        missing_required_fields=[],
        optional_parameter_opportunity=[],
        confidence=0.85,
        arbitration_mode="deterministic",
        reason_codes=[reason_code],
        effective_response_profile=resolve_effective_response_profile(
            user=user,
            explicit_overrides=None,
        ),
        semantic_turn_act="educational_question",
    )


def typed_sources(
    packet: ResearchPacket,
    *,
    question_kind: str | None = None,
    period_start_date: date | str | None = None,
    question_as_of_date: date | str | None = None,
) -> list[dict[str, Any]]:
    """Sources in the one shape the typed panel renders.

    Same fields grounded discovery already emits, so one surface serves every
    shape. The title is the publisher's domain because the packet carries no
    title, and inventing one would be the same defect as letting the model
    write its own citation line. Only URLs the packet returned appear here.
    """
    from urllib.parse import urlparse

    selected = select_public_sources(
        packet.sources,
        question_kind=question_kind,
        period_start=_coerce_date(period_start_date),
        question_as_of=_coerce_date(question_as_of_date),
    )
    entries: list[dict[str, Any]] = []
    for source in selected:
        domain = urlparse(source.url).netloc.lower()
        if not domain:
            continue
        entries.append(
            {
                # The publisher's own title when the citation carried one;
                # the domain otherwise, because inventing a title would be
                # the same defect as letting the model write the citation.
                "title": source.title or domain,
                "domain": domain,
                "url": source.url,
                "source_date": source.source_date,
            }
        )
    return entries


def typed_rows(packet: ResearchPacket) -> list[dict[str, Any]]:
    """Every figure the answer states, in the one shape the sidecar carries:
    cited rows first, then the rows the model wrote with no citation. A
    citation is the model's own. It is null for a figure read from the
    provider's finance data, scrubbed at parse time so nothing here can name
    the provider, and null for a figure the turn names beneath the answer as
    having no source."""
    return [row.model_dump() for row in (*packet.rows, *packet.unsourced_rows)]


def _coerce_date(value: date | str | None) -> date | None:
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def research_follow_up_block(
    *,
    subjects: list[dict[str, str]],
    peers: list[dict[str, str]],
    shape: str,
    period_of_interest: str | None,
    category: str | None = None,
) -> dict[str, Any]:
    """Typed producer seam for the memory program (spec sections 11 and 11b).

    The rail emits what memory must be able to record — research subjects,
    the comparison set when subjects were compared, peer suggestions, and the
    open thread — in a consumable shape. This block is not a memory record and
    carries none of the four categories in ``argus.memory.contracts``.
    Consumption ships in the memory lane; nothing here writes memory."""
    open_thread: dict[str, Any] = {
        "shape": shape,
        "period_of_interest": period_of_interest,
    }
    if category:
        open_thread["category"] = category
    return {
        "schema_version": "argus_research_follow_up/v1",
        "subjects": [
            {
                "symbol": s["symbol"],
                "name": s.get("name") or s["symbol"],
                "asset_class": s.get("asset_class") or "equity",
            }
            for s in subjects
        ],
        "comparison_set": ([s["symbol"] for s in subjects] if len(subjects) >= 2 else []),
        "peer_suggestions": [p["symbol"] for p in peers if p.get("symbol")],
        "open_thread": open_thread,
    }


def build_research_sidecar(
    *,
    capability_class: str,
    shape: str,
    sources: list[dict[str, Any]],
    retrieved_at: str,
    subjects: list[dict[str, str]],
    peers: list[dict[str, str]],
    usage: dict[str, Any],
    period_of_interest: str | None,
    category: str | None = None,
    degraded_code: str | None = None,
    retrieved_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the only supported research sidecar shape."""
    sidecar: dict[str, Any] = {
        "schema_version": RESEARCH_SCHEMA_VERSION,
        "capability_class": capability_class,
        "shape": shape,
        "sources": sources,
        # A degraded turn carries no rows: the documented shape, enforced by
        # the builder rather than remembered by every producer.
        "rows": [] if degraded_code else list(retrieved_rows or []),
        "retrieved_at": retrieved_at,
        "anchor_symbols": [subject["symbol"] for subject in subjects],
        "peers": peers,
        "usage": usage,
        "follow_up": research_follow_up_block(
            subjects=subjects,
            peers=peers,
            shape=shape,
            period_of_interest=period_of_interest,
            category=category,
        ),
    }
    if degraded_code:
        sidecar["degraded"] = {"code": degraded_code}
    assert set(sidecar) <= RESEARCH_SIDECAR_KEYS, "undocumented research sidecar key"
    return sidecar


def research_stage_result(
    *,
    answer: str,
    interpretation: StructuredInterpretation,
    user: UserState,
    capability_class: CapabilityClass,
    shape: QuestionShape,
    packet: ResearchPacket,
    peers: list[dict[str, str]],
    rows: dict[str, Any] | None,
    subjects: list[dict[str, str]],
    cache_status: str,
    degraded_code: str | None = None,
    period_of_interest: str | None = None,
    question_kind: str | None = None,
    period_start_date: date | str | None = None,
    question_as_of_date: date | str | None = None,
    decision: InterpretDecision | None = None,
) -> StageResult:
    decision = carried_decision(
        decision,
        interpretation=interpretation,
        user=user,
        reason_code=f"research_answer_{capability_class}",
    )
    stage_patch: dict[str, Any] = {
        "assistant_response": answer,
        "research": build_research_sidecar(
            capability_class=capability_class,
            shape=shape,
            sources=typed_sources(
                packet,
                question_kind=question_kind,
                period_start_date=period_start_date,
                question_as_of_date=question_as_of_date,
            ),
            retrieved_rows=typed_rows(packet),
            retrieved_at=packet.retrieved_at.isoformat(),
            subjects=subjects,
            peers=peers,
            usage={
                "invocations": packet.usage.invocations,
                "latency_ms": packet.usage.latency_ms,
                "cost_usd": packet.usage.cost_usd,
                "cache_status": cache_status,
            },
            period_of_interest=period_of_interest,
            degraded_code=degraded_code,
        ),
    }
    if rows is not None:
        stage_patch["next_experiments"] = rows
    return StageResult(
        outcome="ready_to_respond",
        decision=decision,
        stage_patch=stage_patch,
    )
