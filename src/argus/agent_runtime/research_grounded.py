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
"BTC" resolving to an ETF proxy and FX quotes returning empty, so both classes
answer from Argus's own Kraken-backed data with an honest coverage note.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
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
from argus.domain.research.cache import (
    cache_get,
    cache_put,
    research_cache_key,
    ttl_for_packet,
)
from argus.domain.research.config import (
    RESEARCH_CONFIG_SPECS,
    capability_class_for_shape,
)
from argus.domain.research.contracts import (
    MAX_PEER_PAIRS,
    CapabilityClass,
    QuestionShape,
    ResearchNamePair,
    ResearchPacket,
    ResearchUnavailableError,
)

if TYPE_CHECKING:
    from argus.agent_runtime.research_answer import ResearchQueryExtraction

RESEARCH_SCHEMA_VERSION = "argus_research/v1"
SURVEY_CANDIDATE_SCAN_LIMIT = 32


def _cache_key_for(
    *,
    query: ResearchQueryExtraction,
    subjects: list[dict[str, str]],
    shape: QuestionShape,
    capability_class: CapabilityClass,
    message: str,
    language: str,
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
    )


async def grounded_result(
    *,
    query: ResearchQueryExtraction,
    subjects: list[dict[str, str]],
    shape: QuestionShape,
    interpretation: StructuredInterpretation,
    state: RunState,
    user: UserState,
) -> StageResult | None:
    spec = RESEARCH_CONFIG_SPECS[shape]
    capability_class = capability_class_for_shape(
        shape, screening=is_market_survey(query.question_kind)
    )
    language = language_tag(user.language_preference)
    prompt = _research_prompt(
        message=state.current_user_message,
        subjects=subjects,
        period=query.period_of_interest,
        language=language,
        question_kind=query.question_kind,
        criteria=list(getattr(query, "screening_criteria", []) or []),
        sector=getattr(query, "sector_of_interest", None),
    )
    key = _cache_key_for(
        query=query,
        subjects=subjects,
        shape=shape,
        capability_class=capability_class,
        message=state.current_user_message,
        language=language,
    )
    cache_status = "miss"
    packet = cache_get(key)
    if packet is not None:
        cache_status = "hit"
    else:
        emit_substage("research_search", detail=shape)
        client = _client()
        if client is None:
            return unavailable_result(
                query=query,
                subjects=subjects,
                interpretation=interpretation,
                state=state,
                user=user,
                reason="not_configured",
            )
        try:
            packet = await asyncio.to_thread(client.run_research, prompt, spec)
        except ResearchUnavailableError as exc:
            logger.warning(
                "Research provider unavailable", reason=exc.reason, shape=shape
            )
            return unavailable_result(
                query=query,
                subjects=subjects,
                interpretation=interpretation,
                state=state,
                user=user,
                reason=exc.reason,
            )
        if is_market_survey(query.question_kind) and packet.usage.invocations == 0:
            # Asking again is deterministic escalation, not a second router:
            # a vague survey ("anything moving today?") lets the model answer
            # from memory however firmly the prompt asks for the tool, so the
            # retry states the concrete question the shape actually means.
            # One retry only; if it still skips the tool the answer says so.
            try:
                retried = await asyncio.to_thread(
                    client.run_research,
                    _survey_retry_prompt(
                        question_kind=query.question_kind,
                        message=state.current_user_message,
                        language=language,
                    ),
                    spec,
                )
            except ResearchUnavailableError:
                retried = None
            if retried is not None and retried.usage.invocations > 0:
                packet = retried
        cache_put(
            key,
            packet,
            ttl_seconds=ttl_for_packet(
                question_kind=query.question_kind,
                categories=packet.categories,
                closed_period=query.period_is_closed_window,
            ),
        )
    return _packet_stage_result(
        packet=packet,
        subjects=subjects,
        shape=shape,
        capability_class=capability_class,
        language=language,
        interpretation=interpretation,
        user=user,
        cache_status=cache_status,
        period_of_interest=query.period_of_interest,
        question_kind=query.question_kind,
    )


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
) -> StageResult:
    """Grounded packet to finished turn: verified peers, runnable rows, typed
    sidecar. One composition whether the packet came from the provider or the
    shared cache, for any shape."""
    survey = is_market_survey(question_kind)
    candidates = list(packet.name_pairs)
    if survey:
        # A survey's answer names its assets in the results, and often only
        # in its own tables; the resolver still gates every one.
        from argus.domain.research.perplexity_agent import symbols_from_answer_tables

        seen = {pair.symbol.upper() for pair in candidates}
        for symbol in (
            *packet.tickers,
            *symbols_from_answer_tables(packet.answer_markdown),
        ):
            if symbol.upper() in seen:
                continue
            seen.add(symbol.upper())
            candidates.append(ResearchNamePair(symbol=symbol, name=symbol))
    peers = verified_peers(
        candidates,
        exclude={s["symbol"] for s in subjects},
        # Surveys name many assets and lead with whatever moved most, which
        # is often untradable here; look past those before giving up.
        scan_limit=SURVEY_CANDIDATE_SCAN_LIMIT if survey else MAX_PEER_PAIRS,
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
    answer = packet.answer_markdown
    # A survey that never called the tool answered from model knowledge, and
    # the one thing a market survey must not do is present that as current.
    ungrounded = survey and packet.usage.invocations == 0
    if ungrounded:
        answer = f"{answer}\n\n*{_ungrounded_survey_note(language)}*"
    elif packet.usage.invocations > 0 and not packet.sources:
        answer = f"{answer}\n\n*{unsourced_figures_note(language)}*"
    if not rows:
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
        degraded_code="survey_not_grounded" if ungrounded else None,
    )


def thorough_job_result(
    *,
    query: ResearchQueryExtraction,
    subjects: list[dict[str, str]],
    interpretation: StructuredInterpretation,
    user: UserState,
    message: str,
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
    key = _cache_key_for(
        query=query,
        subjects=subjects,
        shape="thorough",
        capability_class=capability_class,
        message=message,
        language=language,
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
    decision = research_decision(
        interpretation, user, f"research_answer_{capability_class}"
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
                "question_kind": query.question_kind,
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
    if not rows:
        answer = f"{answer}\n\n{honest_no_next_line(language)}"
    packet = ResearchPacket(answer_markdown=answer)
    return research_stage_result(
        answer=answer,
        interpretation=interpretation,
        user=user,
        capability_class=capability_class_for_shape(
            shape_for_kind(query.question_kind),
            screening=is_market_survey(query.question_kind),
        ),
        shape=shape_for_kind(query.question_kind),
        packet=packet,
        peers=peers,
        rows=rows,
        subjects=focus or subjects,
        cache_status="bypass",
        degraded_code="asset_class_not_covered",
        period_of_interest=query.period_of_interest,
    )


async def exhausted_result(
    *,
    query: ResearchQueryExtraction,
    subjects: list[dict[str, str]],
    interpretation: StructuredInterpretation,
    state: RunState,
    user: UserState,
) -> StageResult | None:
    """Ceiling exhaustion is an honest, localized note, not a silent
    disappearance: the answer still comes from Argus's own data or model
    knowledge, and still ends somewhere runnable."""
    language = language_tag(user.language_preference)
    note = _exhausted_note(
        language, guest_allowance=state.research_guest_allowance_exhausted
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
            shape_for_kind(query.question_kind),
            screening=is_market_survey(query.question_kind),
        ),
        shape=shape_for_kind(query.question_kind),
        packet=packet,
        peers=[],
        rows=rows,
        subjects=subjects,
        cache_status="bypass",
        degraded_code="research_capacity_exhausted",
        period_of_interest=query.period_of_interest,
    )


def unavailable_result(
    *,
    query: ResearchQueryExtraction,
    subjects: list[dict[str, str]],
    interpretation: StructuredInterpretation,
    state: RunState,
    user: UserState,
    reason: str,
) -> StageResult | None:
    del state
    language = language_tag(user.language_preference)
    note = _unavailable_note(language)
    rows = research_next_experiment_rows(subjects=subjects, peers=[], language=language)
    if not rows:
        note = f"{note}\n\n{honest_no_next_line(language)}"
    packet = ResearchPacket(answer_markdown=note)
    return research_stage_result(
        answer=note,
        interpretation=interpretation,
        user=user,
        capability_class=capability_class_for_shape(
            shape_for_kind(query.question_kind),
            screening=is_market_survey(query.question_kind),
        ),
        shape=shape_for_kind(query.question_kind),
        packet=packet,
        peers=[],
        rows=rows,
        subjects=subjects,
        cache_status="bypass",
        degraded_code=f"research_unavailable_{reason}",
        period_of_interest=query.period_of_interest,
    )


def shape_for_kind(kind: str) -> QuestionShape:
    if kind == "live_quote":
        return "fast"
    if kind in ("company_lookup", "etf_constituents") or is_market_survey(kind):
        return "balanced"
    return "thorough"


async def _latest_close(symbol: str, asset_class: str) -> dict[str, str] | None:
    try:
        from datetime import timedelta

        from argus.domain.market_data.provider import fetch_price_series

        end = datetime.now(timezone.utc).date()
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


def _exhausted_note(language: str, *, guest_allowance: bool = False) -> str:
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


def _ungrounded_survey_note(language: str) -> str:
    if language == "es-419":
        return (
            "No pude confirmar estas cifras con datos de mercado en vivo en "
            "este momento, así que trátalas como referencia general y no como "
            "el estado actual del mercado."
        )
    return (
        "I could not confirm these figures against live market data just now, "
        "so treat them as general background rather than the current state of "
        "the market."
    )


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
    )


def store_research_packet_for_job(
    job_request: dict[str, Any],
    packet: ResearchPacket,
) -> None:
    """Store a completed thorough packet in the shared cache so the same
    question answers inline for the six-hour class TTL (30 days when the
    asked-about window is closed). Both completion paths call this."""
    key = str(job_request.get("cache_key") or "")
    if not key:
        return
    cache_put(
        key,
        packet,
        ttl_seconds=ttl_for_packet(
            question_kind=str(job_request.get("question_kind") or "cross_company"),
            categories=packet.categories,
            closed_period=bool(job_request.get("period_is_closed_window")),
        ),
    )


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
    peers = verified_peers(packet.name_pairs, exclude={s["symbol"] for s in subjects})
    if not subjects and peers:
        # A survey names no subject: what the provider found, once the
        # resolver verifies it, is what the user can test. Promoting the
        # first verified name keeps every answer one tap from a test.
        subjects = peers[:1]
        peers = peers[1:]
    rows = research_next_experiment_rows(
        subjects=subjects, peers=peers, language=language
    )
    answer = packet.answer_markdown
    if not rows:
        answer = f"{answer}\n\n{honest_no_next_line(language)}"
    capability_class = str(job_request.get("capability_class") or "thorough_research")
    sidecar: dict[str, Any] = {
        "schema_version": RESEARCH_SCHEMA_VERSION,
        "capability_class": capability_class,
        "shape": "thorough",
        "sources": typed_sources(packet),
        "retrieved_at": packet.retrieved_at.isoformat(),
        "anchor_symbols": [s["symbol"] for s in subjects],
        "peers": peers,
        "usage": {
            "invocations": packet.usage.invocations,
            "latency_ms": packet.usage.latency_ms,
            "cost_usd": packet.usage.cost_usd,
            # Composition only ever runs on a packet a provider run produced;
            # cache hits answer inline and never reach a job.
            "cache_status": "miss",
        },
        "memory": research_memory_block(
            subjects=subjects,
            peers=peers,
            shape="thorough",
            period_of_interest=(
                str(job_request.get("period_of_interest"))
                if job_request.get("period_of_interest")
                else None
            ),
        ),
    }
    return {
        "answer": answer,
        "research": sidecar,
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


def typed_sources(packet: ResearchPacket) -> list[dict[str, Any]]:
    """Sources in the one shape the typed panel renders.

    Same fields grounded discovery already emits, so one surface serves every
    shape. The title is the publisher's domain because the packet carries no
    title, and inventing one would be the same defect as letting the model
    write its own citation line. Only URLs the packet returned appear here.
    """
    from urllib.parse import urlparse

    entries: list[dict[str, Any]] = []
    for source in packet.sources:
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


def unsourced_figures_note(language: str) -> str:
    """Said only when a grounded answer genuinely carries nothing to link.

    A pure market-data answer cites figures, not articles, and for those the
    line is true. It must never render when the packet did carry citations:
    Argus asserting there is nothing to open, while holding publisher URLs
    it discarded, is a worse failure than the sloppy prose it replaced."""
    if language == "es-419":
        return (
            "Estas cifras vienen de datos de mercado, no de artículos, así "
            "que no hay enlaces de fuentes para abrir."
        )
    return (
        "These figures come from market data rather than linked articles, so "
        "there are no source links to open."
    )


def research_memory_block(
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
    open thread — in a consumable shape. Consumption ships in the memory
    lane; nothing here writes memory."""
    open_thread: dict[str, Any] = {
        "shape": shape,
        "period_of_interest": period_of_interest,
    }
    if category:
        open_thread["category"] = category
    return {
        "schema_version": "argus_research_memory/v1",
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
) -> StageResult:
    decision = research_decision(
        interpretation, user, f"research_answer_{capability_class}"
    )
    sidecar: dict[str, Any] = {
        "schema_version": RESEARCH_SCHEMA_VERSION,
        "capability_class": capability_class,
        "shape": shape,
        "sources": typed_sources(packet),
        "retrieved_at": packet.retrieved_at.isoformat(),
        "anchor_symbols": [s["symbol"] for s in subjects],
        "peers": peers,
        "usage": {
            "invocations": packet.usage.invocations,
            "latency_ms": packet.usage.latency_ms,
            "cost_usd": packet.usage.cost_usd,
            "cache_status": cache_status,
        },
        "memory": research_memory_block(
            subjects=subjects,
            peers=peers,
            shape=shape,
            period_of_interest=period_of_interest,
        ),
    }
    if degraded_code:
        sidecar["degraded"] = {"code": degraded_code}
    stage_patch: dict[str, Any] = {
        "assistant_response": answer,
        "research": sidecar,
    }
    if rows is not None:
        stage_patch["next_experiments"] = rows
    return StageResult(
        outcome="ready_to_respond",
        decision=decision,
        stage_patch=stage_patch,
    )
