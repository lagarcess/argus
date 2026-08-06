"""Grounded knowledge answers for non-strategy turns.

The answer router: a facts question gets an answer from the most authoritative
source available, then the Try next surface. Own market data first, the
configured search provider for current external facts, and the interpreter's
own prose for concepts. Classification is an LLM call; nothing here routes on
keywords.
"""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any, Literal

from loguru import logger
from pydantic import BaseModel, Field

from argus.agent_runtime.interpreter.draft_shape import strategy_has_execution_evidence
from argus.agent_runtime.next_experiments import (
    NEXT_EXPERIMENT_ACTION_LABELS,
    NEXT_EXPERIMENTS_VERSION,
    next_experiment_label_key,
)
from argus.agent_runtime.profile.response_profile import (
    resolve_effective_response_profile,
)
from argus.agent_runtime.stages.interpret_types import (
    InterpretDecision,
    StageResult,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import (
    RunState,
    StrategySummary,
    TaskSnapshot,
    UserState,
)
from argus.agent_runtime.strategy_contract import resolve_date_range
from argus.domain.discovery_search.config import discovery_search_config
from argus.domain.discovery_search.contracts import SearchUnavailableError
from argus.domain.discovery_search.selection import search_provider_for_config
from argus.llm.openrouter import (
    build_openrouter_model,
    invoke_openrouter_json_schema,
    openrouter_task_timeout_seconds,
)

_KNOWLEDGE_INTENTS = frozenset(
    {"unsupported_or_out_of_scope", "conversation_followup", "beginner_guidance"}
)
# Acts owned by other surfaces (discovery, results, cards) never route here.
_KNOWLEDGE_ACTS = frozenset({"educational_question", "unsupported_request"})
_SEARCH_MAX_RESULTS = 5


class KnowledgeQueryExtraction(BaseModel):
    """LLM classification of a non-strategy turn's knowledge source."""

    question_kind: Literal["market_stats", "current_external", "concept", "none"]
    symbols: list[str] = Field(default_factory=list)
    date_range_raw_text: str | None = None


async def knowledge_answer_stage_result(
    *,
    interpretation: StructuredInterpretation,
    state: RunState,
    user: UserState,
    snapshot: TaskSnapshot | None,
    selected_thread_metadata: dict[str, Any],
) -> StageResult | None:
    if selected_thread_metadata.get("last_stage_outcome") == "await_user_reply":
        return None
    if interpretation.intent not in _KNOWLEDGE_INTENTS:
        return None
    if (
        interpretation.semantic_turn_act is not None
        and interpretation.semantic_turn_act not in _KNOWLEDGE_ACTS
    ):
        return None
    if getattr(interpretation, "asset_discovery", None) is not None:
        return None
    if strategy_has_execution_evidence(interpretation.candidate_strategy_draft):
        return None
    query = await _classify_question(
        message=state.current_user_message,
        language=user.language_preference,
    )
    if query is None or query.question_kind in ("concept", "none"):
        return None
    answer: str | None = None
    reason_code = ""
    if query.question_kind == "market_stats":
        answer = await _market_stats_answer(
            query=query,
            interpretation=interpretation,
            message=state.current_user_message,
            language=user.language_preference,
        )
        reason_code = "knowledge_answer_market_stats"
    if answer is None and query.question_kind in ("market_stats", "current_external"):
        answer = await _external_facts_answer(
            message=state.current_user_message,
            language=user.language_preference,
        )
        reason_code = "knowledge_answer_current_external"
    if answer is None:
        return None
    return _stage_result(
        answer=answer,
        reason_code=reason_code,
        interpretation=interpretation,
        query=query,
        user=user,
    )


async def _classify_question(
    *,
    message: str,
    language: str | None,
) -> KnowledgeQueryExtraction | None:
    prompt = (
        "Classify the user's message for answering, not for execution.\n"
        "- market_stats: asks about performance, statistics, price history, or "
        "behavior of specific tradable assets or indexes.\n"
        "- current_external: asks about news, current events, macro facts, or "
        "anything needing fresh external information.\n"
        "- concept: asks what something means or how something works.\n"
        "- none: anything else, including requests to run or build something.\n"
        "symbols: provider tickers for the assets discussed; map well-known "
        "indexes to their liquid proxy (S&P 500 -> SPY). date_range_raw_text: "
        "the period exactly as the user phrased it, if any.\n"
        f"User message ({language or 'unknown'}): {message}"
    )
    try:
        extraction = await invoke_openrouter_json_schema(
            task="knowledge_route",
            messages=[{"role": "user", "content": prompt}],
            schema_model=KnowledgeQueryExtraction,
            schema_name="KnowledgeQueryExtraction",
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("Knowledge route classification failed", error=str(exc))
        return None
    if not isinstance(extraction, KnowledgeQueryExtraction):
        return None
    return extraction


async def _market_stats_answer(
    *,
    query: KnowledgeQueryExtraction,
    interpretation: StructuredInterpretation,
    message: str,
    language: str | None,
) -> str | None:
    draft = interpretation.candidate_strategy_draft
    symbols = [
        symbol.strip().upper()
        for symbol in (query.symbols or draft.asset_universe or [])
        if str(symbol).strip()
    ]
    if not symbols:
        return None
    symbol = symbols[0]
    window = resolve_date_range(
        query.date_range_raw_text or draft.date_range or None
    )
    try:
        # Lazy: the API import boundary keeps the backtest compute stack out
        # of startup; these load only when a market-stats answer actually runs.
        from argus.domain.engine import classify_symbol
        from argus.domain.market_data.provider import fetch_price_series

        asset = classify_symbol(symbol)
        series = await asyncio.to_thread(
            fetch_price_series,
            symbol,
            asset.asset_class,
            window.start,
            window.end,
            "1d",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Knowledge answer market data fetch failed",
            symbol=symbol,
            error=str(exc),
        )
        return None
    facts = _series_facts(series=series, symbol=symbol, window_label=window.label,
                          start=window.start, end=window.end)
    if facts is None:
        return None
    return await _voiced_answer(
        message=message,
        language=language,
        facts=facts,
        fallback=_numeric_fallback(facts),
    )


def _series_facts(
    *,
    series: Any,
    symbol: str,
    window_label: str,
    start: date,
    end: date,
) -> dict[str, Any] | None:
    values = series.tolist() if hasattr(series, "tolist") else list(series or [])
    closes = [float(value) for value in values if value is not None]
    if len(closes) < 2:
        return None
    first, last = closes[0], closes[-1]
    total_return_pct = (last / first - 1.0) * 100.0
    peak = closes[0]
    max_drawdown_pct = 0.0
    for value in closes:
        peak = max(peak, value)
        drawdown = (value / peak - 1.0) * 100.0
        max_drawdown_pct = min(max_drawdown_pct, drawdown)
    daily_returns = [
        closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))
    ]
    mean = sum(daily_returns) / len(daily_returns)
    variance = sum((r - mean) ** 2 for r in daily_returns) / len(daily_returns)
    annualized_vol_pct = (variance**0.5) * (252**0.5) * 100.0
    return {
        "symbol": symbol,
        "window_label": window_label,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "sessions": len(closes),
        "total_return_pct": round(total_return_pct, 2),
        "max_drawdown_pct": round(max_drawdown_pct, 2),
        "annualized_volatility_pct": round(annualized_vol_pct, 2),
        "first_close": round(first, 2),
        "last_close": round(last, 2),
    }


def _numeric_fallback(facts: dict[str, Any]) -> str:
    return (
        f"{facts['symbol']} {facts['start']} → {facts['end']}: "
        f"total {facts['total_return_pct']:+.2f}%, "
        f"max drawdown {facts['max_drawdown_pct']:.2f}%, "
        f"volatility {facts['annualized_volatility_pct']:.2f}% (annualized)."
    )


async def _external_facts_answer(
    *,
    message: str,
    language: str | None,
) -> str | None:
    config = discovery_search_config()
    try:
        provider = search_provider_for_config(provider_id=config.provider_id)
        packet = await asyncio.to_thread(
            provider.search,
            message,
            max_results=_SEARCH_MAX_RESULTS,
            timeout_seconds=config.timeout_seconds,
        )
    except (SearchUnavailableError, Exception) as exc:  # noqa: BLE001
        logger.warning("Knowledge answer search unavailable", error=str(exc))
        return None
    if not packet.results:
        return None
    snippets = "\n".join(
        f"- {result.title}: {result.snippet} ({result.url})"
        for result in packet.results
    )
    facts = {"search_results": snippets, "provider": packet.provider_id}
    sources = "\n".join(
        f"- {result.url}" for result in packet.results[:3]
    )
    fallback = f"{packet.results[0].snippet}\n\nFuentes:\n{sources}"
    voiced = await _voiced_answer(
        message=message,
        language=language,
        facts=facts,
        fallback=fallback,
    )
    if voiced is None:
        return None
    if "http" not in voiced:
        voiced = f"{voiced}\n\n{sources}"
    return voiced


async def _voiced_answer(
    *,
    message: str,
    language: str | None,
    facts: dict[str, Any],
    fallback: str,
) -> str | None:
    model = build_openrouter_model("knowledge_voicing")
    if model is None:
        return fallback
    fact_lines = "\n".join(f"{key}: {value}" for key, value in facts.items())
    prompt = (
        "Answer the user's question directly using ONLY these facts. Reply in "
        f"the user's language ({language or 'the language of the question'}). "
        "2-4 sentences, concrete numbers, no advice, no invented data. If the "
        "facts include search results, cite the source URLs you used.\n"
        f"Question: {message}\nFacts:\n{fact_lines}"
    )
    try:
        response = await asyncio.wait_for(
            model.ainvoke([{"role": "user", "content": prompt}]),
            timeout=openrouter_task_timeout_seconds("knowledge_voicing"),
        )
        text = str(getattr(response, "content", "") or "").strip()
        return text or fallback
    except Exception as exc:  # noqa: BLE001
        logger.debug("Knowledge answer voicing failed", error=str(exc))
        return fallback


def _try_next_sidecar(
    *,
    query: KnowledgeQueryExtraction,
    interpretation: StructuredInterpretation,
    language: str | None,
) -> dict[str, Any] | None:
    symbols = [
        symbol.strip().upper()
        for symbol in (
            query.symbols or interpretation.candidate_strategy_draft.asset_universe
        )
        if str(symbol).strip()
    ]
    if not symbols:
        return None
    labels = NEXT_EXPERIMENT_ACTION_LABELS.get(
        "es-419" if str(language or "").startswith("es") else "en",
        NEXT_EXPERIMENT_ACTION_LABELS["en"],
    )
    english = NEXT_EXPERIMENT_ACTION_LABELS["en"]
    rows = []
    for kind in ("compare_buy_and_hold", "recurring_monthly_buys"):
        label_key = next_experiment_label_key(kind)
        rows.append(
            {
                "kind": kind,
                "label": english.get(label_key, kind),
                "label_key": label_key,
                "localized_label": labels.get(label_key),
            }
        )
    return {"version": NEXT_EXPERIMENTS_VERSION, "rows": rows}


def _stage_result(
    *,
    answer: str,
    reason_code: str,
    interpretation: StructuredInterpretation,
    query: KnowledgeQueryExtraction,
    user: UserState,
) -> StageResult:
    decision = InterpretDecision(
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
    stage_patch: dict[str, Any] = {"assistant_response": answer}
    sidecar = _try_next_sidecar(
        query=query,
        interpretation=interpretation,
        language=user.language_preference,
    )
    if sidecar is not None:
        stage_patch["next_experiments"] = sidecar
    return StageResult(
        outcome="ready_to_respond",
        decision=decision,
        stage_patch=stage_patch,
    )
