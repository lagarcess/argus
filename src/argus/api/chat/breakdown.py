from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from argus.agent_runtime.response_style import ARGUS_RESPONSE_STYLE_CONTRACT
from argus.api.schemas import BacktestRun
from argus.context.rendering import context_packet_fact_summary
from argus.domain.engine_launch.result_facts import (
    execution_note,
    resolved_rule_summary,
    runnable_next_tests,
    structured_next_experiments,
)
from argus.llm.openrouter import (
    invoke_openrouter_json_schema_sync,
    log_openrouter_failure,
)


class ResultBreakdownPart(BaseModel):
    kind: Literal["text", "fact"]
    text: str = ""
    fact_id: str | None = None


class ResultBreakdownSection(BaseModel):
    heading: str
    parts: list[ResultBreakdownPart] = Field(default_factory=list)


class ResultBreakdownDraft(BaseModel):
    sections: list[ResultBreakdownSection] = Field(default_factory=list)


RESULT_BREAKDOWN_LLM_TIMEOUT_SECONDS = 6.0


def result_breakdown_context(run: BacktestRun) -> dict[str, Any]:
    card = run.conversation_result_card
    result_facts = {
        "metrics": run.metrics,
        "config_snapshot": run.config_snapshot,
        "trades": run.trades or [],
    }
    return {
        "run_id": run.id,
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
        "context_packets": card.get("context_packets") if isinstance(card, dict) else None,
    }


def llm_result_breakdown_message(
    context: dict[str, Any],
    *,
    invoke_json_schema_func=invoke_openrouter_json_schema_sync,
    log_openrouter_failure_func=log_openrouter_failure,
    timeout_seconds: float = RESULT_BREAKDOWN_LLM_TIMEOUT_SECONDS,
) -> str | None:
    fact_bank = result_breakdown_fact_bank(context)
    required_fact_ids = _required_result_breakdown_fact_ids(fact_bank)
    context_packet_ids = _context_packet_ids_from_context(context)
    try:
        response = _invoke_breakdown_llm_with_budget(
            invoke_json_schema_func=invoke_json_schema_func,
            fact_bank=fact_bank,
            required_fact_ids=required_fact_ids,
            context_packet_ids=context_packet_ids,
            timeout_seconds=timeout_seconds,
        )
    except FutureTimeoutError:
        log_openrouter_failure_func(
            task="result_breakdown",
            model_name=None,
            exc=TimeoutError("Result breakdown LLM exceeded action budget"),
            message="LLM result breakdown timed out; using deterministic fallback",
        )
        return None
    except Exception as exc:
        log_openrouter_failure_func(
            task="result_breakdown",
            model_name=None,
            exc=exc,
            message="LLM result breakdown failed; using deterministic fallback",
        )
        return None
    draft = _coerce_result_breakdown_draft(response)
    if draft is None:
        return None
    return _render_result_breakdown_draft(
        draft=draft,
        fact_bank=fact_bank,
        required_fact_ids=required_fact_ids,
    )


def _invoke_breakdown_llm_with_budget(
    *,
    invoke_json_schema_func: Any,
    fact_bank: dict[str, str],
    required_fact_ids: set[str],
    context_packet_ids: list[str],
    timeout_seconds: float,
) -> object:
    def _invoke() -> object:
        return invoke_json_schema_func(
            task="result_breakdown",
            messages=_result_breakdown_llm_messages(
                fact_bank=fact_bank,
                required_fact_ids=required_fact_ids,
            ),
            schema_model=ResultBreakdownDraft,
            schema_name="ResultBreakdownDraft",
            context_packet_ids=context_packet_ids,
        )

    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="argus-breakdown")
    future = executor.submit(_invoke)
    try:
        return future.result(timeout=max(0.1, timeout_seconds))
    except FutureTimeoutError:
        future.cancel()
        raise
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _result_breakdown_llm_messages(
    *,
    fact_bank: dict[str, str],
    required_fact_ids: set[str],
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                f"{ARGUS_RESPONSE_STYLE_CONTRACT}\n\n"
                "You are Argus, an investing backtest copilot. Explain the stored "
                "backtest result using only the supplied fact_bank. Write for a "
                "normal person who is trying to keep exploring, not as a financial report. "
                "Start with one warm takeaway before details. Return flexible, "
                "non-template markdown sections and vary the section headings, "
                "order, and phrasing. Do not fill a fixed outline. Build "
                "each section from text parts and fact reference parts. Use text "
                "parts for educational framing and fact reference parts for every "
                "run-specific symbol, date, percentage, benchmark, assumption, rule, "
                "execution note, and caveat. Fact references render as polished "
                "canonical callouts, so do not manually copy or decorate fact values "
                "inside text parts. Keep the writing polished, conversational, and "
                "cohesive rather than fragmented. Do not expose fact_bank field names, "
                "context packet language, provider names, source plumbing, app internals, "
                "or implementation terms in user-facing prose. If context facts are "
                "available, describe them naturally as market or macro backdrop. Keep "
                "source/provider details internal unless they are part of a rendered "
                "canonical fact callout. Respect capability truth in next "
                "steps: runnable ideas must come from runnable_next_tests, while "
                "draft-only or future ideas must be clearly labeled that way. Promote "
                "discovery by naming one or two runnable next experiments, but do not "
                "invent causes, trades, prices, support, missing metrics, unsupported "
                "strategy mechanics, predictions, investment advice, advisory language, "
                "profitable-trade claims, or custom benchmark support. Avoid phrases like "
                "'investment decision-making', 'profitable trades', 'should buy', "
                "'should sell', and 'alternative benchmarks'. For no-trade runs, say "
                "the strategy stayed in cash because the entry condition did not trigger; "
                "do not imply the market stood still or that trades were missed. If "
                "context_packet_facts are present, treat them as possible backdrop only "
                "and include context_packet_limitations; do not claim causality unless "
                "the supplied fact directly supports it. Cover "
                "what was tested, what happened, benchmark comparison, risk or drawdown, "
                "assumptions, caveats, and one useful next test."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "fact_bank": fact_bank,
                    "required_fact_ids": sorted(required_fact_ids),
                },
                default=str,
            ),
        },
    ]


def result_breakdown_fact_bank(context: dict[str, Any]) -> dict[str, str]:
    fact_bank: dict[str, str] = {}
    title = str(context.get("title") or "").strip()
    if title:
        fact_bank["title"] = title

    symbols = context.get("symbols")
    symbols_text = (
        ", ".join(str(symbol).strip() for symbol in symbols if str(symbol).strip())
        if isinstance(symbols, list)
        else ""
    )
    if symbols_text:
        fact_bank["symbols"] = symbols_text

    date_range = _format_result_breakdown_date_range(context.get("date_range"))
    if date_range:
        fact_bank["date_range"] = date_range

    rule_summary = str(context.get("rule_summary") or "").strip()
    if rule_summary:
        fact_bank["rule_summary"] = rule_summary

    run_note = str(context.get("execution_note") or "").strip()
    if run_note:
        fact_bank["execution_note"] = run_note

    benchmark = str(context.get("benchmark_symbol") or "").strip()
    if benchmark:
        fact_bank["benchmark_symbol"] = benchmark

    total_return = _result_breakdown_metric(
        context,
        "total_return_pct",
        row_keys=("total_return_pct", "total_return"),
    )
    if total_return is not None:
        fact_bank["total_return"] = _format_result_breakdown_percent(total_return)

    benchmark_return = _result_breakdown_metric(
        context,
        "benchmark_return_pct",
        row_keys=("benchmark_return_pct", "benchmark_return"),
    )
    if benchmark_return is not None:
        fact_bank["benchmark_return"] = _format_result_breakdown_percent(benchmark_return)

    delta_vs_benchmark = _result_breakdown_metric(
        context,
        "delta_vs_benchmark_pct",
        row_keys=("delta_vs_benchmark_pct", "benchmark_delta"),
    )
    if delta_vs_benchmark is not None:
        fact_bank["benchmark_delta"] = _format_result_breakdown_percent(
            delta_vs_benchmark
        )

    max_drawdown = _result_breakdown_metric(
        context,
        "max_drawdown_pct",
        row_keys=("max_drawdown_pct", "max_drawdown"),
    )
    if max_drawdown is not None:
        fact_bank["max_drawdown"] = _format_result_breakdown_percent(max_drawdown)

    starting_capital = _result_breakdown_starting_capital(context)
    if starting_capital:
        fact_bank["starting_capital"] = starting_capital

    assumptions = context.get("assumptions")
    assumption_text = (
        " ".join(str(item).strip() for item in assumptions if str(item).strip())
        if isinstance(assumptions, list)
        else ""
    )
    if assumption_text:
        fact_bank["assumptions"] = assumption_text

    fact_bank.update(
        context_packet_fact_summary(
            _context_packets_from_context(context),
            symbols=_context_symbols(context),
        )
    )
    fact_bank["caveat"] = (
        "This is historical simulation evidence, not a prediction or trading "
        "recommendation."
    )
    fact_bank["runnable_next_tests"] = runnable_next_tests(
        {
            "config_snapshot": context.get("config_snapshot"),
            "symbols": context.get("symbols"),
        }
    )
    fact_bank["next_experiment_options"] = json.dumps(
        structured_next_experiments(
            {
                "config_snapshot": context.get("config_snapshot"),
                "symbols": context.get("symbols"),
            }
        ),
        default=str,
    )
    fact_bank["draft_only_or_future_tests"] = (
        "Draft-only or future support: DCA with separate starting principal, "
        "investment ceilings, and unsupported custom rules."
    )
    return fact_bank


def _context_packets_from_context(context: dict[str, Any]) -> list[dict[str, Any]]:
    packets = context.get("context_packets")
    if not isinstance(packets, list):
        return []
    return [packet for packet in packets if isinstance(packet, dict)]


def _context_symbols(context: dict[str, Any]) -> list[str]:
    symbols = context.get("symbols")
    if isinstance(symbols, list):
        return [str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()]
    config = context.get("config_snapshot")
    if isinstance(config, dict):
        config_symbols = config.get("symbols")
        if isinstance(config_symbols, list):
            return [
                str(symbol).strip().upper()
                for symbol in config_symbols
                if str(symbol).strip()
            ]
    return []


def _context_packet_ids_from_context(context: dict[str, Any]) -> list[str]:
    packet_ids: list[str] = []
    for packet in _context_packets_from_context(context):
        packet_id = str(packet.get("id") or "").strip()
        if packet_id and packet_id not in packet_ids:
            packet_ids.append(packet_id)
    return packet_ids


def _coerce_result_breakdown_draft(value: Any) -> ResultBreakdownDraft | None:
    if isinstance(value, ResultBreakdownDraft):
        return value
    try:
        return ResultBreakdownDraft.model_validate(value)
    except (TypeError, ValidationError):
        return None


def _render_result_breakdown_draft(
    *,
    draft: ResultBreakdownDraft,
    fact_bank: dict[str, str],
    required_fact_ids: set[str],
) -> str | None:
    if not draft.sections or len(draft.sections) > 6:
        return None

    used_fact_ids: set[str] = set()
    rendered_sections: list[str] = []
    for section in draft.sections:
        heading = _clean_result_breakdown_heading(section.heading)
        if not heading or not section.parts:
            return None
        body, section_fact_ids = _render_result_breakdown_parts(
            section.parts,
            fact_bank=fact_bank,
        )
        if not body:
            return None
        used_fact_ids.update(section_fact_ids)
        rendered_sections.append(f"### {heading}\n{body}")

    if not required_fact_ids.issubset(used_fact_ids):
        return None

    rendered_text = "\n\n".join(rendered_sections).strip()
    if len(rendered_text.split()) > 520:
        return None
    if _contains_user_visible_internal_breakdown_term(rendered_text):
        return None
    return rendered_text


INTERNAL_BREAKDOWN_TERMS = (
    "alpaca",
    "context packet",
    "context_packet",
    "data packet",
    "fact_bank",
    "fact id",
    "fact_id",
    "fred",
    "kraken",
    "provider",
    "route receipt",
    "source ids",
    "source_ids",
)


def _contains_user_visible_internal_breakdown_term(answer: str) -> bool:
    normalized = str(answer or "").casefold()
    return any(term in normalized for term in INTERNAL_BREAKDOWN_TERMS)


def _render_result_breakdown_parts(
    parts: list[ResultBreakdownPart],
    *,
    fact_bank: dict[str, str],
) -> tuple[str | None, set[str]]:
    body = ""
    fact_ids: list[str] = []
    used_fact_ids: set[str] = set()
    for part in parts:
        if part.kind == "text":
            body = _append_result_breakdown_piece(body, part.text)
            continue
        fact_id = str(part.fact_id or "").strip()
        if fact_id not in fact_bank:
            return None, used_fact_ids
        if fact_id not in used_fact_ids:
            fact_ids.append(fact_id)
            used_fact_ids.add(fact_id)
    body = _normalize_result_breakdown_body(body)
    fact_block = _render_result_breakdown_fact_block(fact_ids, fact_bank=fact_bank)
    if _result_breakdown_body_is_fragmentary(body, fact_ids):
        body = ""
    if body and fact_block:
        return f"{body}\n\n{fact_block}", used_fact_ids
    return (body or fact_block or None), used_fact_ids


def _render_result_breakdown_fact_block(
    fact_ids: list[str],
    *,
    fact_bank: dict[str, str],
) -> str:
    if not fact_ids:
        return ""
    remaining = list(fact_ids)
    lines: list[str] = []

    def _has(*ids: str) -> bool:
        return any(fact_id in remaining for fact_id in ids)

    def _consume(*ids: str) -> None:
        for fact_id in ids:
            if fact_id in remaining:
                remaining.remove(fact_id)

    if _has("title", "symbols", "date_range"):
        title = _sentence_fragment(fact_bank.get("title") or "Stored backtest")
        symbols = _sentence_fragment(fact_bank.get("symbols") or "")
        date_range = _sentence_fragment(fact_bank.get("date_range") or "")
        test_text = title
        if symbols and symbols.lower() not in title.lower():
            test_text = f"{test_text} on {symbols}"
        if date_range:
            test_text = f"{test_text}, {date_range}"
        lines.append(f"**Test:** {test_text}.")
        _consume("title", "symbols", "date_range")

    if _has("rule_summary"):
        lines.append(f"**Rule:** {fact_bank['rule_summary']}")
        _consume("rule_summary")

    if _has(
        "total_return",
        "benchmark_symbol",
        "benchmark_return",
        "benchmark_delta",
    ):
        performance_parts: list[str] = []
        if "total_return" in remaining:
            performance_parts.append(f"total return {fact_bank['total_return']}")
        benchmark = _sentence_fragment(fact_bank.get("benchmark_symbol") or "")
        if "benchmark_return" in remaining and benchmark:
            performance_parts.append(
                f"{benchmark} benchmark return {fact_bank['benchmark_return']}"
            )
        elif "benchmark_symbol" in remaining and benchmark:
            performance_parts.append(f"benchmark {benchmark}")
        if "benchmark_delta" in remaining:
            performance_parts.append(
                f"relative performance {fact_bank['benchmark_delta']}"
            )
        if performance_parts:
            lines.append(f"**Performance:** {'; '.join(performance_parts)}.")
        _consume(
            "total_return",
            "benchmark_symbol",
            "benchmark_return",
            "benchmark_delta",
        )

    if _has("max_drawdown"):
        lines.append(f"**Risk marker:** max drawdown {fact_bank['max_drawdown']}.")
        _consume("max_drawdown")

    if _has("execution_note"):
        lines.append(f"**Execution:** {fact_bank['execution_note']}")
        _consume("execution_note")

    if _has("starting_capital"):
        lines.append(f"**Starting capital:** {fact_bank['starting_capital']}.")
        _consume("starting_capital")

    if _has("assumptions"):
        lines.append(f"**Assumptions:** {fact_bank['assumptions']}")
        _consume("assumptions")

    if _has("caveat"):
        lines.append(f"**Keep in mind:** {fact_bank['caveat']}")
        _consume("caveat")

    if _has("runnable_next_tests"):
        lines.append(fact_bank["runnable_next_tests"])
        _consume("runnable_next_tests")

    if _has("draft_only_or_future_tests"):
        lines.append(fact_bank["draft_only_or_future_tests"])
        _consume("draft_only_or_future_tests")

    for fact_id in remaining:
        value = fact_bank.get(fact_id)
        if value:
            lines.append(_ensure_sentence(value))

    return "\n\n".join(_ensure_sentence(line) for line in lines if line.strip())


def _append_result_breakdown_piece(current: str, piece: str) -> str:
    cleaned = " ".join(str(piece or "").split())
    if not cleaned:
        return current
    if not current:
        return cleaned
    if cleaned[:1] in {".", ",", ";", ":", "!", "?", ")", "%"}:
        return current.rstrip() + cleaned
    if current[-1:] in {"(", "$", "/", "-"}:
        return current.rstrip() + cleaned
    return current.rstrip() + " " + cleaned


def _normalize_result_breakdown_body(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def _result_breakdown_body_is_fragmentary(body: str, fact_ids: list[str]) -> bool:
    if not body or not fact_ids:
        return False
    word_count = len([word for word in body.split(" ") if word.strip()])
    return word_count < 12


def _sentence_fragment(value: str) -> str:
    return str(value or "").strip().rstrip(".")


def _ensure_sentence(value: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        return ""
    if cleaned[-1:] in {".", "!", "?"}:
        return cleaned
    return f"{cleaned}."


def _required_result_breakdown_fact_ids(fact_bank: dict[str, str]) -> set[str]:
    required: set[str] = {"caveat"}
    for fact_id in (
        "title",
        "symbols",
        "date_range",
        "rule_summary",
        "execution_note",
        "total_return",
        "benchmark_symbol",
        "max_drawdown",
        "assumptions",
    ):
        if fact_id in fact_bank:
            required.add(fact_id)
    if "benchmark_return" in fact_bank:
        required.add("benchmark_return")
    if "benchmark_delta" in fact_bank:
        required.add("benchmark_delta")
    return required


def _clean_result_breakdown_heading(value: str) -> str:
    return str(value or "").strip().lstrip("#").strip()


def _result_breakdown_starting_capital(context: dict[str, Any]) -> str:
    config_snapshot = context.get("config_snapshot")
    if isinstance(config_snapshot, dict):
        raw_value = config_snapshot.get("initial_capital") or config_snapshot.get(
            "starting_capital"
        )
        if isinstance(raw_value, (int, float)) and raw_value > 0:
            return f"${raw_value:,.0f}"
        if isinstance(raw_value, str) and raw_value.strip():
            return raw_value.strip()

    assumptions = context.get("assumptions")
    if isinstance(assumptions, list):
        for assumption in assumptions:
            text = str(assumption).strip()
            if text.lower().startswith("starting capital"):
                return text.split(":", 1)[-1].strip().rstrip(".")
    return ""


def fallback_result_breakdown_message(context: dict[str, Any]) -> str:
    fact_bank = result_breakdown_fact_bank(context)
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
    delta_vs_benchmark = _result_breakdown_metric(
        context,
        "delta_vs_benchmark_pct",
        row_keys=("delta_vs_benchmark_pct", "benchmark_delta"),
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
        _format_result_breakdown_percent(delta_vs_benchmark)
        if delta_vs_benchmark is not None
        else "the stored benchmark spread"
    )
    drawdown_text = (
        _format_result_breakdown_percent(max_drawdown)
        if max_drawdown is not None
        else "the available risk data"
    )
    rule_summary = str(context.get("rule_summary") or "").strip()
    execution_summary = str(context.get("execution_note") or "").strip()
    assumption_bullets = "\n".join(f"- {line}" for line in assumption_lines)
    period_sentence = f" over {date_range}" if date_range else ""
    setup_lines = [
        f"{title} tested {symbols_text}{period_sentence} using the stored backtest configuration."
    ]
    if rule_summary:
        setup_lines.append(rule_summary)

    performance_lines = [
        (
            f"**Total return:** {total_return_text}. The comparison benchmark was "
            f"{benchmark or 'the stored benchmark'} at {benchmark_text}, leaving the "
            f"run at {delta_text} versus the benchmark."
        )
    ]
    if execution_summary:
        performance_lines.append(execution_summary)

    return (
        "### Quick Breakdown\n"
        f"**What was tested:** {' '.join(setup_lines)}\n\n"
        "**What the run showed:**\n"
        f"{' '.join(performance_lines)}\n\n"
        "**Risk to notice:** "
        f"Max drawdown was {drawdown_text}. This is the largest peak-to-trough "
        f"decline captured by the simulation.\n\n"
        "**Assumptions:**\n"
        f"{assumption_bullets}\n\n"
        "**Keep in mind:** "
        "Use this as historical simulation evidence, not a prediction or trading "
        f"recommendation. {_ensure_sentence(fact_bank['runnable_next_tests'])}"
    )


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


def result_breakdown_message(run: BacktestRun | None) -> str:
    if run is None:
        return (
            "I could not find the latest completed result for this conversation. "
            "Run the backtest again and I can break down the metrics from that result."
        )
    context = result_breakdown_context(run)
    return llm_result_breakdown_message(context) or fallback_result_breakdown_message(
        context
    )
