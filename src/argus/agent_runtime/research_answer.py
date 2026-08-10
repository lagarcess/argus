"""The research rail router: one classifier owns question shape.

Spec section 11b: everything question-shaped that was previously split
between grounded discovery and the research rail converges here. Knowledge
turns enter through ``research_answer_stage_result``; typed asset-discovery
turns enter through ``discovery_turn_stage_result``; one classification
decides the shape either way, and discovery's asset-finding is dispatched as
an operation of the rail (``research_find``) beside quotes, fundamentals,
comparisons, screening, and market stats. Flag off, both entries keep the
exact pre-rail behavior.

Deterministic code owns everything after the classification: config
selection, provider calls, resolver gates on every candidate, and the typed
runnable rows. The model may rank, explain, and format; it never mints a
symbol, strategy, action, or ask.
"""

from __future__ import annotations

from typing import Literal

from loguru import logger
from pydantic import BaseModel, Field

from argus.agent_runtime import research_grounded as grounded

# Re-exported composition surface: the job lifecycle and tests reach these
# through the router module, which stays the rail's single import facade.
from argus.agent_runtime.research_grounded import (  # noqa: F401
    RESEARCH_SCHEMA_VERSION,
    compose_completed_research,
    research_failure_note,
    research_prompt_for_job,
    store_research_packet_for_job,
)
from argus.agent_runtime.stages.interpret_types import (
    AssetDiscoveryRequest,
    InterpretDecision,
    StageResult,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import RunState, UserState
from argus.domain.research.config import research_rail_enabled
from argus.llm.openrouter import invoke_openrouter_json_schema

# Shapes that survey the market rather than a named asset: the user names no
# subject, so the provider's own grounded result supplies the candidates.
_MARKET_SURVEY_KINDS = frozenset({"market_pulse", "screening", "sector_radar"})


class ResearchQueryExtraction(BaseModel):
    """LLM classification of a question turn's shape and subjects.

    Extends the legacy knowledge classification; the legacy kinds keep their
    exact meaning so flag-on turns retain every pre-rail behavior.
    """

    question_kind: Literal[
        "live_quote",
        "company_lookup",
        "cross_company",
        "etf_constituents",
        "market_pulse",
        "screening",
        "sector_radar",
        "find_assets",
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
    discovery_category: str | None = None
    screening_criteria: list[str] = Field(default_factory=list)
    sector_of_interest: str | None = None


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
    return await _dispatch(
        query,
        interpretation=interpretation,
        state=state,
        user=user,
        discovery_request=None,
        decision=None,
    )


async def discovery_turn_stage_result(
    *,
    interpretation: StructuredInterpretation,
    decision: InterpretDecision,
    state: RunState,
    user: UserState,
) -> StageResult | None:
    """Own every typed asset-discovery turn.

    Flag off, this is exactly the pre-rail composer path. Flag on, the rail's
    classifier decides the real shape: a comparison of named assets becomes
    grounded research, everything discovery-shaped runs the find operation
    with the interpreter's own typed request. The typed act is an entry
    funnel, never a second router.
    """
    from argus.agent_runtime.discovery import discovery_stage_result_for

    if not research_rail_enabled():
        return await discovery_stage_result_for(
            interpretation=interpretation, decision=decision, state=state, user=user
        )
    if decision.semantic_turn_act != "asset_discovery":
        return None
    query = await _classify_research_question(
        message=state.current_user_message,
        language=user.language_preference,
    )
    request = decision.asset_discovery
    if query is None or not _is_research_shaped(query.question_kind):
        # Classifier unavailable, or it agrees the turn is discovery-shaped:
        # the find operation runs with the interpreter's typed request, so a
        # routing hiccup can never lose a discovery turn.
        from argus.agent_runtime.research_find import find_assets_stage_result

        return await find_assets_stage_result(
            request=request,
            interpretation=interpretation,
            decision=decision,
            state=state,
            user=user,
        )
    return await _dispatch(
        query,
        interpretation=interpretation,
        state=state,
        user=user,
        discovery_request=request,
        decision=decision,
    )


# Kinds that divert a typed discovery act into grounded research. The
# interpreter's act says "the user wants assets"; the classifier says what
# kind of answer that is. Only a bare ask for names stays with the find
# operation, because only that ask wants names and nothing else: a screen
# must apply its conditions and a sector question must report the sector.
_FIND_OPERATION_KINDS = frozenset({"find_assets"})


def _is_research_shaped(question_kind: str) -> bool:
    return question_kind not in _FIND_OPERATION_KINDS | {"concept", "none"}


async def _dispatch(
    query: ResearchQueryExtraction,
    *,
    interpretation: StructuredInterpretation,
    state: RunState,
    user: UserState,
    discovery_request: AssetDiscoveryRequest | None,
    decision: InterpretDecision | None,
) -> StageResult | None:
    if query.question_kind in ("market_stats", "current_external"):
        return await _legacy_kind_result(
            query=query, interpretation=interpretation, state=state, user=user
        )
    if query.question_kind in _MARKET_SURVEY_KINDS:
        if not state.research_allowance_available:
            return await grounded.exhausted_result(
                query=query,
                subjects=[],
                interpretation=interpretation,
                state=state,
                user=user,
            )
        return await grounded.grounded_result(
            query=query,
            subjects=_resolved_subjects(query),
            shape="balanced",
            interpretation=interpretation,
            state=state,
            user=user,
        )
    if query.question_kind == "find_assets":
        from argus.agent_runtime.research_find import find_assets_stage_result

        return await find_assets_stage_result(
            request=discovery_request or _request_from_query(query),
            interpretation=interpretation,
            decision=decision,
            state=state,
            user=user,
        )
    if query.question_kind in ("concept", "none"):
        return None
    subjects = _resolved_subjects(query)
    off_coverage = [s for s in subjects if s["asset_class"] != "equity"]
    if off_coverage or query.asset_class_hint in ("crypto", "currency_pair"):
        return await grounded.off_coverage_result(
            query=query,
            subjects=subjects,
            interpretation=interpretation,
            state=state,
            user=user,
        )
    if not state.research_allowance_available:
        return await grounded.exhausted_result(
            query=query,
            subjects=subjects,
            interpretation=interpretation,
            state=state,
            user=user,
        )
    shape = grounded.shape_for_kind(query.question_kind)
    if shape == "thorough":
        return grounded.thorough_job_result(
            query=query,
            subjects=subjects,
            interpretation=interpretation,
            user=user,
            message=state.current_user_message,
        )
    return await grounded.grounded_result(
        query=query,
        subjects=subjects,
        shape=shape,
        interpretation=interpretation,
        state=state,
        user=user,
    )


def _request_from_query(query: ResearchQueryExtraction) -> AssetDiscoveryRequest:
    """Deterministic find request for a knowledge-entry discovery shape.

    Anchors come from the resolver, never from raw model text; the cheap
    verified-rows path stays the default (needs_current_facts=False), with
    the escalation row offering the source-backed search."""
    anchors = [s["symbol"] for s in _resolved_subjects(query)][:5]
    return AssetDiscoveryRequest(
        relationship="peer" if anchors else "category",
        category_description=(query.discovery_category or "").strip()[:200] or None,
        anchor_symbols=anchors,
        asset_class_hint=query.asset_class_hint,
        needs_current_facts=False,
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
        "as a question, or asks multi-year trend analysis across them, and "
        "the user has named every asset involved.\n"
        "- etf_constituents: asks what an ETF or fund holds, its "
        "constituents, top holdings or their weights, or whether and how "
        "much of a named asset is inside it.\n"
        "- market_pulse: asks what the market or an index is doing right "
        "now, or which assets are moving, gaining, losing, or most active "
        "today.\n"
        "- screening: the user states any condition an asset must satisfy, "
        "such as a valuation, yield, size, growth, margin, or performance "
        "threshold. The condition decides this kind, not the phrasing: "
        "'show me', 'find me', and 'what are' all count. "
        "screening_criteria: each stated condition in the user's own words, "
        "one per entry, including the category or sector when they named "
        "one.\n"
        "- sector_radar: asks what is happening in an industry, sector, or "
        "theme, how it is performing, or what is driving it. "
        "sector_of_interest: the sector or theme named.\n"
        "- find_assets: asks only for names or ideas of assets by similarity "
        "or category, stating no condition they must satisfy and asking "
        "nothing about how they are performing, and the user has not named "
        "all the assets they want. If the user states any threshold or "
        "condition, it is screening, not find_assets. "
        "discovery_category: the user's own category or theme phrase, when "
        "one exists.\n"
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
