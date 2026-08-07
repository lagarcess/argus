"""Research answers: finance_search grounding routed by question shape.

The interpreter decides the question shape through one LLM classification;
deterministic code owns everything after it: config selection, the provider
call, resolver gates on every candidate, and the typed runnable rows. The
model may rank, explain, and format; it never mints a symbol, strategy,
action, or ask.

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
from typing import Any, Literal

from loguru import logger
from pydantic import BaseModel, Field

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
    ttl_for,
)
from argus.domain.research.config import (
    RESEARCH_CONFIG_SPECS,
    capability_class_for_shape,
    research_rail_enabled,
)
from argus.domain.research.contracts import (
    CapabilityClass,
    QuestionShape,
    ResearchPacket,
    ResearchUnavailableError,
)
from argus.llm.openrouter import invoke_openrouter_json_schema

RESEARCH_SCHEMA_VERSION = "argus_research/v1"

_RESEARCH_KINDS = frozenset(
    {"live_quote", "company_lookup", "cross_company", "screening"}
)


class ResearchQueryExtraction(BaseModel):
    """LLM classification of a question turn's shape and subjects.

    Extends the legacy knowledge classification; the legacy kinds keep their
    exact meaning so flag-on turns retain every pre-rail behavior.
    """

    question_kind: Literal[
        "live_quote",
        "company_lookup",
        "cross_company",
        "screening",
        "market_stats",
        "current_external",
        "concept",
        "none",
    ]
    symbols: list[str] = Field(default_factory=list)
    asset_class_hint: Literal["equity", "crypto", "currency_pair"] | None = None
    period_of_interest: str | None = None
    period_is_closed_window: bool = False
    date_range_raw_text: str | None = None


async def research_answer_stage_result(
    *,
    interpretation: StructuredInterpretation,
    state: RunState,
    user: UserState,
) -> StageResult | None:
    """Route a knowledge-shaped turn through the research rail.

    Returns None when the turn is not a question the rail serves; the caller
    keeps its pre-rail behavior for that turn.
    """
    if not research_rail_enabled():
        return None
    query = await _classify_research_question(
        message=state.current_user_message,
        language=user.language_preference,
    )
    if query is None or query.question_kind in ("concept", "none"):
        return None
    if query.question_kind in ("market_stats", "current_external"):
        return await _legacy_kind_result(
            query=query, interpretation=interpretation, state=state, user=user
        )
    subjects = _resolved_subjects(query)
    off_coverage = [s for s in subjects if s["asset_class"] != "equity"]
    if off_coverage or query.asset_class_hint in ("crypto", "currency_pair"):
        return await _off_coverage_result(
            query=query,
            subjects=subjects,
            interpretation=interpretation,
            state=state,
            user=user,
        )
    if not state.research_allowance_available:
        return await _exhausted_result(
            query=query,
            subjects=subjects,
            interpretation=interpretation,
            state=state,
            user=user,
        )
    shape = _shape_for_kind(query.question_kind)
    if shape == "thorough":
        return _thorough_job_result(
            query=query,
            subjects=subjects,
            interpretation=interpretation,
            user=user,
            message=state.current_user_message,
        )
    return await _grounded_result(
        query=query,
        subjects=subjects,
        shape=shape,
        interpretation=interpretation,
        state=state,
        user=user,
    )


async def _classify_research_question(
    *,
    message: str,
    language: str | None,
) -> ResearchQueryExtraction | None:
    prompt = (
        "Classify the user's message for answering, not for execution.\n"
        "- live_quote: asks for a current or latest price, quote, level, "
        "market cap, valuation multiple, or pre/after-hours figure of a "
        "tradable asset right now.\n"
        "- company_lookup: asks about one company's history, financial "
        "statements, fundamentals, segments, earnings, filings, peers, "
        "business model, or how that specific company works or makes "
        "money.\n"
        "- cross_company: compares two or more companies, sectors, or funds "
        "as a question, or asks multi-year trend analysis across them.\n"
        "- screening: asks to find, list, or rank assets matching criteria, "
        "including gainers, losers, and most-active style asks.\n"
        "- market_stats: asks about the historical performance, statistics, "
        "or price behavior of specific tradable assets over a period.\n"
        "- current_external: asks about news, current events, macro facts, "
        "or anything needing fresh external information that is not a "
        "company or asset data question.\n"
        "- concept: asks what a general market term means or how a general "
        "mechanism works, with no specific company or asset as the "
        "subject.\n"
        "- none: anything else, including requests to run or build "
        "something.\n"
        "symbols: provider tickers for the assets discussed; map well-known "
        "indexes to their liquid proxy (S&P 500 -> SPY). asset_class_hint: "
        "the asset class the user is asking about, when clear. "
        "period_of_interest: the time window exactly as the user phrased "
        "it, if any. period_is_closed_window: true only when that window is "
        "entirely in the past, like a named year or a finished quarter. "
        "date_range_raw_text: same as period_of_interest.\n"
        f"User message ({language or 'unknown'}): {message}"
    )
    try:
        extraction = await invoke_openrouter_json_schema(
            task="knowledge_route",
            messages=[{"role": "user", "content": prompt}],
            schema_model=ResearchQueryExtraction,
            schema_name="ResearchQueryExtraction",
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("Research route classification failed", error=str(exc))
        return None
    if not isinstance(extraction, ResearchQueryExtraction):
        return None
    return extraction


def _shape_for_kind(kind: str) -> QuestionShape:
    if kind == "live_quote":
        return "fast"
    if kind == "company_lookup":
        return "balanced"
    return "thorough"


def _resolved_subjects(query: ResearchQueryExtraction) -> list[dict[str, str]]:
    """Deterministic guardrail: the resolver owns identity, class, and name."""
    subjects: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in query.symbols:
        candidate = str(raw).strip().upper()
        if not candidate or candidate in seen:
            continue
        try:
            from argus.domain.market_data.assets import resolve_asset

            resolved = resolve_asset(candidate)
        except Exception:  # noqa: BLE001
            continue
        symbol = resolved.canonical_symbol.upper()
        if symbol in seen:
            continue
        seen.add(candidate)
        seen.add(symbol)
        subjects.append(
            {
                "symbol": symbol,
                "name": resolved.name or symbol,
                "asset_class": resolved.asset_class,
            }
        )
    return subjects[:5]


async def _legacy_kind_result(
    *,
    query: ResearchQueryExtraction,
    interpretation: StructuredInterpretation,
    state: RunState,
    user: UserState,
) -> StageResult | None:
    # Lazy import: knowledge_answer imports this module, so the reverse edge
    # must stay function-scoped.
    from argus.agent_runtime import knowledge_answer as ka

    legacy = ka.KnowledgeQueryExtraction(
        question_kind=query.question_kind,  # type: ignore[arg-type]
        symbols=query.symbols,
        date_range_raw_text=query.date_range_raw_text or query.period_of_interest,
    )
    answer: str | None = None
    reason_code = ""
    if query.question_kind == "market_stats":
        answer = await ka._market_stats_answer(
            query=legacy,
            interpretation=interpretation,
            message=state.current_user_message,
            language=user.language_preference,
            user=user,
        )
        reason_code = "knowledge_answer_market_stats"
    if answer is None:
        answer = await ka._external_facts_answer(
            message=state.current_user_message,
            language=user.language_preference,
            user=user,
        )
        reason_code = "knowledge_answer_current_external"
    if answer is None:
        return None
    return ka._stage_result(
        answer=answer,
        reason_code=reason_code,
        interpretation=interpretation,
        query=legacy,
        user=user,
    )


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


async def _grounded_result(
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
        shape, screening=query.question_kind == "screening"
    )
    language = _language_tag(user.language_preference)
    prompt = _research_prompt(
        message=state.current_user_message,
        subjects=subjects,
        period=query.period_of_interest,
        language=language,
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
            return _unavailable_result(
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
            return _unavailable_result(
                query=query,
                subjects=subjects,
                interpretation=interpretation,
                state=state,
                user=user,
                reason=exc.reason,
            )
        cache_put(
            key,
            packet,
            ttl_seconds=ttl_for(
                capability_class, closed_period=query.period_is_closed_window
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
) -> StageResult:
    """Grounded packet to finished turn: verified peers, runnable rows, typed
    sidecar. One composition whether the packet came from the provider or the
    shared cache, for any shape."""
    peers = verified_peers(packet.name_pairs, exclude={s["symbol"] for s in subjects})
    rows = research_next_experiment_rows(
        subjects=subjects, peers=peers, language=language
    )
    answer = packet.answer_markdown
    if not rows:
        answer = f"{answer}\n\n{honest_no_next_line(language)}"
    return _research_stage_result(
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
    )


def _thorough_job_result(
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
    language = _language_tag(user.language_preference)
    capability_class = capability_class_for_shape(
        "thorough", screening=query.question_kind == "screening"
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
    decision = _decision(interpretation, user, f"research_answer_{capability_class}")
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
                # The exact key computed at classification time; completion
                # paths store under it verbatim so later identical questions
                # hit without recomputation drift.
                "cache_key": key,
            },
        },
    )


async def _off_coverage_result(
    *,
    query: ResearchQueryExtraction,
    subjects: list[dict[str, str]],
    interpretation: StructuredInterpretation,
    state: RunState,
    user: UserState,
) -> StageResult | None:
    """Crypto and currency pairs degrade honestly: Argus's own provider data
    for figures, an explicit coverage note, and a runnable next step."""
    language = _language_tag(user.language_preference)
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
    return _research_stage_result(
        answer=answer,
        interpretation=interpretation,
        user=user,
        capability_class=capability_class_for_shape(
            _shape_for_kind(query.question_kind),
            screening=query.question_kind == "screening",
        ),
        shape=_shape_for_kind(query.question_kind),
        packet=packet,
        peers=peers,
        rows=rows,
        subjects=focus or subjects,
        cache_status="bypass",
        degraded_code="asset_class_not_covered",
    )


async def _exhausted_result(
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
    language = _language_tag(user.language_preference)
    note = _exhausted_note(language)
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
    return _research_stage_result(
        answer=answer,
        interpretation=interpretation,
        user=user,
        capability_class=capability_class_for_shape(
            _shape_for_kind(query.question_kind),
            screening=query.question_kind == "screening",
        ),
        shape=_shape_for_kind(query.question_kind),
        packet=packet,
        peers=[],
        rows=rows,
        subjects=subjects,
        cache_status="bypass",
        degraded_code="research_capacity_exhausted",
    )


def _unavailable_result(
    *,
    query: ResearchQueryExtraction,
    subjects: list[dict[str, str]],
    interpretation: StructuredInterpretation,
    state: RunState,
    user: UserState,
    reason: str,
) -> StageResult | None:
    del state
    language = _language_tag(user.language_preference)
    note = _unavailable_note(language)
    rows = research_next_experiment_rows(subjects=subjects, peers=[], language=language)
    if not rows:
        note = f"{note}\n\n{honest_no_next_line(language)}"
    packet = ResearchPacket(answer_markdown=note)
    return _research_stage_result(
        answer=note,
        interpretation=interpretation,
        user=user,
        capability_class=capability_class_for_shape(
            _shape_for_kind(query.question_kind),
            screening=query.question_kind == "screening",
        ),
        shape=_shape_for_kind(query.question_kind),
        packet=packet,
        peers=[],
        rows=rows,
        subjects=subjects,
        cache_status="bypass",
        degraded_code=f"research_unavailable_{reason}",
    )


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
    import os

    from argus.domain.research.perplexity_agent import PerplexityAgentClient

    api_key = os.getenv("PERPLEXITY_API_KEY", "")
    if not api_key.strip():
        return None
    return PerplexityAgentClient(api_key)


def _research_prompt(
    *,
    message: str,
    subjects: list[dict[str, str]],
    period: str | None,
    language: str,
) -> str:
    """Documented prompt guidance: business question first, then tickers and
    the time window; state the desired outcome, let the tool pick fields."""
    lines = [message.strip()]
    if subjects:
        lines.append(
            "Tickers: " + ", ".join(f"{s['name']} ({s['symbol']})" for s in subjects)
        )
    if period:
        lines.append(f"Time window: {period}")
    lines.append(
        "Answer the question directly for a curious non-expert, leading with "
        "the answer. Use compact tables only where they genuinely help. State "
        "the as-of date for any current figure. If a figure is unavailable, "
        "say so plainly; never estimate a live number. No investment advice."
    )
    if language == "es-419":
        lines.append("Responde en español latinoamericano (es-419).")
    else:
        lines.append("Answer in English.")
    return "\n".join(lines)


def _language_tag(language_preference: str | None) -> str:
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


def _exhausted_note(language: str) -> str:
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
    capability_class = str(job_request.get("capability_class") or "thorough_research")
    cache_put(
        key,
        packet,
        ttl_seconds=ttl_for(
            capability_class,
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
    from argus.agent_runtime.research_rows import (
        honest_no_next_line as _no_next,
    )
    from argus.agent_runtime.research_rows import (
        research_next_experiment_rows as _rows,
    )
    from argus.agent_runtime.research_rows import (
        verified_peers as _peers,
    )

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
    peers = _peers(packet.name_pairs, exclude={s["symbol"] for s in subjects})
    rows = _rows(subjects=subjects, peers=peers, language=language)
    answer = packet.answer_markdown
    if not rows:
        answer = f"{answer}\n\n{_no_next(language)}"
    capability_class = str(job_request.get("capability_class") or "thorough_research")
    sidecar: dict[str, Any] = {
        "schema_version": RESEARCH_SCHEMA_VERSION,
        "capability_class": capability_class,
        "shape": "thorough",
        "sources": list(packet.sources),
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


def _decision(
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


def _research_stage_result(
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
) -> StageResult:
    decision = _decision(interpretation, user, f"research_answer_{capability_class}")
    sidecar: dict[str, Any] = {
        "schema_version": RESEARCH_SCHEMA_VERSION,
        "capability_class": capability_class,
        "shape": shape,
        "sources": list(packet.sources),
        "retrieved_at": packet.retrieved_at.isoformat(),
        "anchor_symbols": [s["symbol"] for s in subjects],
        "peers": peers,
        "usage": {
            "invocations": packet.usage.invocations,
            "latency_ms": packet.usage.latency_ms,
            "cost_usd": packet.usage.cost_usd,
            "cache_status": cache_status,
        },
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
