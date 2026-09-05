"""The research rail dispatcher: the primary interpreter owns question shape.

Spec section 11b: everything question-shaped that was previously split
between grounded discovery and the research rail converges here. Knowledge
turns enter through ``research_answer_stage_result``; typed asset-discovery
turns enter through ``discovery_turn_stage_result``; the primary interpretation
supplies the shape either way, and discovery's asset-finding is dispatched as
an operation of the rail (``research_find``) beside quotes, fundamentals,
comparisons, screening, and market stats. Flag off, both entries keep the
exact pre-rail behavior.

Deterministic code owns everything after the classification: config
selection, provider calls, resolver gates on every candidate, and the typed
runnable rows. The model may rank, explain, and format; it never mints a
symbol, strategy, action, or ask.
"""

from __future__ import annotations

from argus.agent_runtime import research_grounded as grounded
from argus.agent_runtime.interpreter.research_routing import (
    primary_research_query,
    research_turn_has_conflicting_owner,
)

# Re-exported composition surface: the job lifecycle and tests reach these
# through the router module, which stays the rail's single import facade.
from argus.agent_runtime.research_grounded import (  # noqa: F401
    RESEARCH_SCHEMA_VERSION,
    compose_completed_research,
    research_capacity_exhausted_for_job,
    research_failure_note,
    research_prompt_for_job,
    store_research_packet_for_job,
)
from argus.agent_runtime.research_query import ResearchQueryExtraction
from argus.agent_runtime.stages.interpret_types import (
    AssetDiscoveryRequest,
    InterpretDecision,
    StageResult,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import RunState, UserState
from argus.domain.research.config import research_rail_enabled

# Shapes that survey the market rather than a named asset: the user names no
# subject, so the provider's own grounded result supplies the candidates.
_MARKET_SURVEY_KINDS = frozenset({"market_pulse", "screening", "sector_radar"})


async def research_answer_stage_result(
    *,
    interpretation: StructuredInterpretation,
    state: RunState,
    user: UserState,
) -> StageResult | None:
    """Route a knowledge-shaped turn through the research rail.

    Returns None without a supported primary-interpreter question payload.
    """
    if not research_rail_enabled():
        return None
    query = primary_research_query(interpretation)
    if query is None:
        return None
    return await _dispatch(
        query,
        interpretation=interpretation,
        state=state,
        user=user,
        discovery_request=interpretation.asset_discovery,
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

    Flag off, this is exactly the pre-rail composer path. Flag on, the primary
    interpretation supplies the shape: a comparison of named assets becomes
    grounded research, everything discovery-shaped runs the find operation
    with the interpreter's own typed request.
    """
    from argus.agent_runtime.discovery import discovery_stage_result_for

    if not research_rail_enabled():
        return await discovery_stage_result_for(
            interpretation=interpretation, decision=decision, state=state, user=user
        )
    if research_turn_has_conflicting_owner(interpretation):
        return None
    if (
        decision.asset_discovery is None
        and decision.semantic_turn_act != "asset_discovery"
    ):
        return None
    query = interpretation.research_query
    request = decision.asset_discovery
    if query is None or query.question_kind not in _TYPED_DISCOVERY_DIVERT_KINDS:
        # No primary question shape, or the turn stays discovery-shaped: the
        # find operation runs with the interpreter's typed request, so a
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


# Kinds that divert a typed discovery act into grounded research: shapes
# whose answer is genuinely something other than candidate assets (a named
# comparison, one company's story, a quote, holdings, stats, news). Survey
# kinds (screening, sector_radar, market_pulse) deliberately do NOT divert a
# typed discovery turn: "find me stocks that recently IPO'ed" states a
# condition and is still an ask for candidate assets, and the discovery
# escalation chip promises the discovery surface, not a narrative (#344).
_TYPED_DISCOVERY_DIVERT_KINDS = frozenset(
    {
        "live_quote",
        "company_lookup",
        "cross_company",
        "etf_constituents",
        "market_stats",
        "current_external",
    }
)


async def _dispatch(
    query: ResearchQueryExtraction,
    *,
    interpretation: StructuredInterpretation,
    state: RunState,
    user: UserState,
    discovery_request: AssetDiscoveryRequest | None,
    decision: InterpretDecision | None,
) -> StageResult | None:
    # One gate above every rail shape. The rail has eight question kinds and
    # three of them reach a statistics readout by different routes, so
    # deciding this per kind guarantees the next kind added forgets it. A
    # typed refusal that already names an asset and the user's window keeps
    # its recovery route whatever the classifier decided this turn is.
    from argus.agent_runtime import knowledge_answer as ka

    if ka.refusal_route_survives_classification(interpretation):
        ka.note_refusal_route_kept(interpretation)
        return None
    if query.question_kind in ("market_stats", "current_external"):
        return await _legacy_kind_result(
            query=query,
            interpretation=interpretation,
            state=state,
            user=user,
            decision=decision,
        )
    if query.question_kind in _MARKET_SURVEY_KINDS:
        return await grounded.grounded_result(
            query=query,
            subjects=_resolved_subjects(query),
            shape="balanced",
            interpretation=interpretation,
            state=state,
            user=user,
            decision=decision,
        )
    if query.question_kind == "find_assets":
        from argus.agent_runtime.research_find import find_assets_stage_result

        return await find_assets_stage_result(
            request=discovery_request,
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
            decision=decision,
        )
    shape = grounded.shape_for_query(query)
    if shape == "thorough":
        return grounded.thorough_job_result(
            query=query,
            subjects=subjects,
            interpretation=interpretation,
            user=user,
            message=state.current_user_message,
            decision=decision,
        )
    return await grounded.grounded_result(
        query=query,
        subjects=subjects,
        shape=shape,
        interpretation=interpretation,
        state=state,
        user=user,
        decision=decision,
    )


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
    decision: InterpretDecision | None = None,
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
        decision=decision,
    )
