from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from loguru import logger

from argus.agent_runtime.response_language import response_language_instruction
from argus.api.chat.research_evidence import record_result_breakdown_spend
from argus.api.schemas import BacktestRun
from argus.domain.benchmark_comparison import (
    benchmark_comparison_from_delta,
)
from argus.domain.engine_launch.display import (
    format_benchmark_comparison_phrase,
)
from argus.domain.engine_launch.result_facts import (
    execution_note,
    resolved_rule_summary,
)
from argus.domain.research.admission import claim_current_research_attempt
from argus.domain.research.config import ResearchConfigSpec
from argus.domain.research.contracts import (
    ResearchSource,
    ResearchUnavailableError,
    ResearchUsage,
)
from argus.domain.research.credentials import perplexity_api_key
from argus.domain.research.perplexity_agent import PerplexityAgentClient
from argus.domain.result_figures import shown_benchmark_gap
from argus.domain.result_readout_content import (
    normalize_readout_language,
)
from argus.domain.result_readout_grounding import (
    READOUT_RUN_GROUNDING_INSTRUCTIONS,
    stored_readout_facts,
)
from argus.domain.result_readout_headlines import (
    headline_readout_facts,
    headline_request_lines,
)
from argus.domain.result_readout_research import (
    RESULT_RESEARCH_LIMITS,
    result_research_spec,
)
from argus.domain.result_readout_sources import (
    BREAKDOWN_SOURCE_INSTRUCTIONS,
    accepted_breakdown_text,
    result_breakdown_schema,
)


def result_breakdown_spec(language: str) -> ResearchConfigSpec:
    return result_research_spec(language)


def _client() -> PerplexityAgentClient | None:
    api_key = perplexity_api_key()
    return PerplexityAgentClient(api_key) if api_key else None


@dataclass(frozen=True)
class ResultBreakdownMessage:
    text: str
    source: Literal[
        "llm_breakdown_stage",
        "deterministic_fallback",
        "missing_result",
    ]
    fallback_used: bool
    failure_mode: str | None = None
    usage: ResearchUsage | None = None
    sources: tuple[ResearchSource, ...] = ()


def result_breakdown_context(run: BacktestRun) -> dict[str, Any]:
    card = run.conversation_result_card
    result_facts = {
        "metrics": run.metrics,
        "config_snapshot": run.config_snapshot,
        "trades": run.trades or [],
    }
    config_snapshot = run.config_snapshot if isinstance(run.config_snapshot, dict) else {}
    return {
        "run_id": run.id,
        "chart": run.chart,
        "title": card.get("title") if isinstance(card, dict) else None,
        "asset_class": run.asset_class,
        "symbols": run.symbols,
        "benchmark_symbol": run.benchmark_symbol,
        "date_range": card.get("date_range") if isinstance(card, dict) else None,
        "metrics": card.get("rows") if isinstance(card, dict) else None,
        "assumptions": card.get("assumptions") if isinstance(card, dict) else None,
        "benchmark_note": card.get("benchmark_note") if isinstance(card, dict) else None,
        "config_snapshot": run.config_snapshot,
        "raw_metrics": run.metrics,
        "execution_note": execution_note(result_facts),
        "rule_summary": resolved_rule_summary(result_facts),
        "context_packets": card.get("context_packets")
        if isinstance(card, dict)
        else None,
        "language": config_snapshot.get("language"),
    }


def llm_result_breakdown_message(
    context: dict[str, Any],
    *,
    language: str = "en",
    client: PerplexityAgentClient | None = None,
) -> str | None:
    text, _, _, _ = _llm_result_breakdown_with_metadata(
        context,
        language=language,
        client=client,
    )
    return text


def _llm_result_breakdown_with_metadata(
    context: dict[str, Any],
    *,
    language: str = "en",
    client: PerplexityAgentClient | None = None,
) -> tuple[str | None, str | None, ResearchUsage | None, tuple[ResearchSource, ...]]:
    resolved_language = normalize_readout_language(language)
    if resolved_language is None:
        return None, "language_mismatch", None, ()
    facts = stored_readout_facts(
        metrics=context.get("raw_metrics", context.get("metrics")),
        config_snapshot=context.get("config_snapshot"),
        symbols=context.get("symbols"),
        benchmark_symbol=context.get("benchmark_symbol"),
        date_range=context.get("date_range"),
        chart=context.get("chart"),
    )
    messages = _result_breakdown_llm_messages(
        facts=facts,
        title=context.get("title"),
        language=resolved_language,
    )
    headline_facts = headline_readout_facts(facts)
    try:
        active_client = client if client is not None else _client()
        if active_client is None:
            return None, "llm_unavailable_or_contract_rejected", None, ()
        if not claim_current_research_attempt().available:
            return None, "research_capacity_exhausted", None, ()
        response = active_client.run_structured(
            messages[1]["content"],
            result_breakdown_spec(resolved_language),
            schema_model=result_breakdown_schema(headline_facts),
            schema_name="ResultBreakdownDraft",
            instructions=messages[0]["content"],
            limits=RESULT_RESEARCH_LIMITS,
        )
    except ResearchUnavailableError as exc:
        logger.warning("Result breakdown unavailable; using template", reason=exc.reason)
        return None, "llm_unavailable_or_contract_rejected", exc.usage, ()
    except Exception:  # noqa: BLE001
        logger.warning("Result breakdown failed; using template")
        return None, "llm_unavailable_or_contract_rejected", None, ()
    text, failure = accepted_breakdown_text(
        response.draft,
        facts=headline_facts,
        language=resolved_language,
        sources=response.sources,
    )
    return text, failure, response.usage, response.sources


def _result_breakdown_llm_messages(
    *,
    facts: dict[str, Any],
    title: str | None = None,
    language: str = "en",
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "Explain this historical backtest for a normal person. "
                f"{response_language_instruction(language)} "
                f"{READOUT_RUN_GROUNDING_INSTRUCTIONS} "
                "Use the supplied headline label as fact_key. "
                f"{BREAKDOWN_SOURCE_INSTRUCTIONS}"
            ),
        },
        {
            "role": "user",
            "content": (
                "What happened to these assets over the tested window and why? "
                "Search for sources. Explain what holding through it was like and "
                "how this test compared with the benchmark.\n\n"
                + (f"Strategy: {title}\n" if title else "")
                + "\n".join(
                    headline_request_lines(
                        headline_readout_facts(facts), language=language
                    )
                )
            ),
        },
    ]


def _response_language(language: object) -> str:
    return str(language or "en").strip() or "en"


def _benchmark_comparison_phrase(
    delta_vs_benchmark: float | int | None,
    *,
    language: str,
) -> str:
    comparison = benchmark_comparison_from_delta(delta_vs_benchmark)
    return format_benchmark_comparison_phrase(
        comparison.claim,
        comparison.magnitude_points,
        language=language,
    )


def fallback_result_breakdown_message(
    context: dict[str, Any],
    *,
    language: str = "en",
) -> str:
    resolved_language = _response_language(language or context.get("language"))
    total_return = _result_breakdown_metric(
        context,
        "total_return_pct",
        row_keys=("total_return_pct", "total_return"),
    )
    benchmark_return = _result_breakdown_metric(
        context,
        "benchmark_return_pct",
        row_keys=("benchmark_return_pct", "benchmark_return"),
    )
    max_drawdown = _result_breakdown_metric(
        context,
        "max_drawdown_pct",
        row_keys=("max_drawdown_pct", "max_drawdown"),
    )
    # The gap beside the two printed returns is their shown difference.
    delta_vs_benchmark = shown_benchmark_gap(
        total_return,
        benchmark_return,
        _result_breakdown_metric(
            context,
            "delta_vs_benchmark_pct",
            row_keys=("delta_vs_benchmark_pct", "benchmark_delta"),
        ),
    )
    assumptions = context.get("assumptions")
    assumption_lines = (
        [str(item).strip() for item in assumptions[:5] if str(item).strip()]
        if isinstance(assumptions, list)
        else []
    ) or ["The stored run settings were used."]
    benchmark = str(context.get("benchmark_symbol") or "").strip()
    symbols = context.get("symbols")
    symbols_text = (
        ", ".join(str(symbol).strip() for symbol in symbols if str(symbol).strip())
        if isinstance(symbols, list)
        else ""
    ) or "The available result"
    title = str(context.get("title") or "").strip() or f"{symbols_text} backtest"
    date_range = _format_result_breakdown_date_range(context.get("date_range"))
    total_return_text = (
        _format_result_breakdown_percent(total_return)
        if total_return is not None
        else "the available return"
    )
    benchmark_text = (
        _format_result_breakdown_percent(benchmark_return)
        if benchmark and benchmark_return is not None
        else "the available benchmark return"
    )
    delta_text = (
        _benchmark_comparison_phrase(delta_vs_benchmark, language=resolved_language)
        if delta_vs_benchmark is not None
        else "the stored benchmark spread"
    )
    drawdown_text = (
        _format_result_breakdown_percent(max_drawdown)
        if max_drawdown is not None
        else "the available risk data"
    )
    rule_summary = _stored_rule_summary(context)
    execution_summary = _stored_execution_note(context)
    assumption_text = "; ".join(line.rstrip(".") for line in assumption_lines)
    period_sentence = f" over {date_range}" if date_range else ""
    setup_lines = [
        f"{title} tested {symbols_text}{period_sentence} using the stored backtest configuration."
    ]
    if rule_summary:
        setup_lines.append(rule_summary)

    performance_lines = [
        (
            f"**Total return:** {total_return_text}. The comparison benchmark was "
            f"{benchmark or 'the stored benchmark'} at {benchmark_text}. "
            f"{delta_text} versus the benchmark. This is a comparison of "
            "historical returns, not an explanation of why the move happened."
        )
    ]
    if execution_summary:
        performance_lines.append(execution_summary)
    return (
        "Here's the deeper read on the completed run.\n\n"
        f"**Setup.** {' '.join(setup_lines)}\n\n"
        f"**How to read it.** {' '.join(performance_lines)}\n\n"
        f"**Risk and assumptions.** Max drawdown was {drawdown_text}, the largest "
        "peak-to-trough decline captured by the simulation. The run used "
        f"{assumption_text or 'the stored run settings'}.\n\n"
        "Use this as historical simulation evidence, not a prediction or trading "
        "recommendation."
    )


def _stored_rule_summary(context: dict[str, Any]) -> str | None:
    raw_summary = str(context.get("rule_summary") or "").strip()
    return raw_summary or None


def _stored_execution_note(context: dict[str, Any]) -> str | None:
    raw_note = str(context.get("execution_note") or "").strip()
    if not raw_note:
        return None
    return raw_note


def _result_breakdown_metric(
    context: dict[str, Any],
    metric_key: str,
    *,
    row_keys: tuple[str, ...],
) -> float | None:
    raw_metrics = context.get("raw_metrics")
    value = _nested_result_breakdown_number(
        raw_metrics,
        ("aggregate", "performance", metric_key),
    )
    if value is not None:
        return value

    rows = context.get("metrics")
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            key = str(row.get("key") or "").strip()
            if key not in row_keys:
                continue
            return _coerce_result_breakdown_number(row.get("value"))
    return None


def _nested_result_breakdown_number(
    payload: Any,
    path: tuple[str, ...],
) -> float | None:
    current = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return _coerce_result_breakdown_number(current)


def _coerce_result_breakdown_number(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(str(value).strip().rstrip("%"))
    except (TypeError, ValueError):
        return None


def _format_result_breakdown_percent(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f}%"


def _format_result_breakdown_date_range(value: Any) -> str:
    if isinstance(value, dict):
        display = value.get("display")
        if isinstance(display, str) and display.strip():
            return display.strip()
        start = value.get("start")
        end = value.get("end")
        if start and end:
            return f"{start} to {end}"
    if isinstance(value, str):
        return value.strip()
    return ""


def result_breakdown_message(
    run: BacktestRun | None,
    *,
    language: str = "en",
) -> str:
    return result_breakdown_message_with_metadata(run, language=language).text


def result_breakdown_message_with_metadata(
    run: BacktestRun | None,
    *,
    language: str = "en",
    client: PerplexityAgentClient | None = None,
) -> ResultBreakdownMessage:
    if run is None:
        return ResultBreakdownMessage(
            text=(
                "I could not find the latest completed result for this conversation. "
                "Run the backtest again and I can break down the metrics from that result."
            ),
            source="missing_result",
            fallback_used=True,
            failure_mode="missing_result",
        )
    context = result_breakdown_context(run)
    context_language = _response_language(language or context.get("language"))
    llm_text, failure_mode, usage, sources = _llm_result_breakdown_with_metadata(
        context,
        language=language,
        client=client,
    )
    if llm_text:
        return ResultBreakdownMessage(
            text=llm_text,
            source="llm_breakdown_stage",
            fallback_used=False,
            usage=usage,
            sources=sources,
        )
    return ResultBreakdownMessage(
        text=fallback_result_breakdown_message(context, language=context_language),
        source="deterministic_fallback",
        fallback_used=True,
        failure_mode=failure_mode or "llm_unavailable_or_contract_rejected",
        usage=usage,
        sources=sources,
    )


def result_breakdown_action(
    run: BacktestRun | None,
    *,
    language: str,
    user_id: str,
    conversation_id: str,
    request_id: str,
) -> ResultBreakdownMessage:
    """Keep received spend attached to the provider work, even after disconnect."""
    result = result_breakdown_message_with_metadata(run, language=language)
    record_result_breakdown_spend(
        usage=result.usage,
        failure_mode=result.failure_mode,
        user_id=user_id,
        conversation_id=conversation_id,
        request_id=request_id,
    )
    return result
