from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from argus.agent_runtime.response_style import ARGUS_RESPONSE_STYLE_CONTRACT
from argus.api.schemas import BacktestRun
from argus.context.rendering import context_packet_fact_summary
from argus.domain.benchmark_comparison import (
    benchmark_comparison_from_delta,
)
from argus.domain.engine_launch.result_facts import (
    execution_note,
    resolved_rule_summary,
    structured_next_experiments,
)
from argus.llm.openrouter import (
    invoke_openrouter_json_schema_sync,
    log_openrouter_failure,
)

Language = Literal["en", "es-419"]
ResultBreakdownLanguageQuality = Literal[
    "matches_prompt_language",
    "mixed_or_wrong_language",
]


class ResultBreakdownPart(BaseModel):
    kind: Literal["text", "fact"]
    text: str = ""
    fact_id: str | None = None


class ResultBreakdownSection(BaseModel):
    heading: str
    parts: list[ResultBreakdownPart] = Field(default_factory=list)


class ResultBreakdownDraft(BaseModel):
    language_quality: ResultBreakdownLanguageQuality = Field(
        description=(
            "Self-audit for every user-facing heading and text part. Use "
            "matches_prompt_language only when prose is fully written in "
            "product_language, allowing unchanged symbols, tickers, currency "
            "codes, numbers, and percentages. Use mixed_or_wrong_language if any "
            "user-facing phrase remains in a different language or copies internal "
            "schema/fact-id wording."
        )
    )
    sections: list[ResultBreakdownSection] = Field(default_factory=list)


RESULT_BREAKDOWN_LLM_TIMEOUT_SECONDS = 6.0


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
        "language": config_snapshot.get("language"),
    }


def llm_result_breakdown_message(
    context: dict[str, Any],
    *,
    language: str = "en",
    invoke_json_schema_func=invoke_openrouter_json_schema_sync,
    log_openrouter_failure_func=log_openrouter_failure,
    timeout_seconds: float = RESULT_BREAKDOWN_LLM_TIMEOUT_SECONDS,
) -> str | None:
    resolved_language = _resolve_language(language or context.get("language"))
    fact_bank = result_breakdown_fact_bank(context, language=resolved_language)
    required_fact_ids = _required_result_breakdown_fact_ids(fact_bank)
    context_packet_ids = _context_packet_ids_from_context(context)
    try:
        response = _invoke_breakdown_llm_with_budget(
            invoke_json_schema_func=invoke_json_schema_func,
            fact_bank=fact_bank,
            required_fact_ids=required_fact_ids,
            context_packet_ids=context_packet_ids,
            language=resolved_language,
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
        language=resolved_language,
    )


def _invoke_breakdown_llm_with_budget(
    *,
    invoke_json_schema_func: Any,
    fact_bank: dict[str, str],
    required_fact_ids: set[str],
    context_packet_ids: list[str],
    language: Language,
    timeout_seconds: float,
) -> object:
    def _invoke() -> object:
        return invoke_json_schema_func(
            task="result_breakdown",
            messages=_result_breakdown_llm_messages(
                fact_bank=fact_bank,
                required_fact_ids=required_fact_ids,
                language=language,
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
    language: str = "en",
) -> list[dict[str, str]]:
    resolved_language = _resolve_language(language)
    return [
        {
            "role": "system",
            "content": (
                f"{ARGUS_RESPONSE_STYLE_CONTRACT}\n\n"
                "You are Argus, an investing backtest copilot. Explain the stored "
                "backtest result using only the supplied fact_bank. Write for a "
                "normal person who is trying to keep exploring, not as a financial report. "
                "Write every user-facing heading and text part in product_language. "
                "If product_language starts with 'es', write user-facing prose in Spanish. "
                "Symbols, tickers, currency codes, numbers, and percentages can stay "
                "unchanged, but internal fact IDs and schema field names are never "
                "user-facing copy. Set language_quality to mixed_or_wrong_language if "
                "any rendered heading or text part mixes languages or copies internal "
                "schema/fact-id wording. "
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
                "label any section Quick Take or Quick Breakdown; this action is the "
                "deeper Explain result surface, not the first-glance readout. "
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
                "what was tested, what drove the observed result, benchmark comparison, "
                "risk or drawdown, assumptions, caveats, and one useful next test. "
                "Keep the breakdown clearly deeper than the Quick Take: setup, drivers, "
                "risk/assumptions, and next experiment should each have their own job."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "fact_bank": fact_bank,
                    "required_fact_ids": sorted(required_fact_ids),
                    "product_language": resolved_language,
                },
                default=str,
            ),
        },
    ]


def result_breakdown_fact_bank(
    context: dict[str, Any],
    *,
    language: str = "en",
) -> dict[str, str]:
    resolved_language = _resolve_language(language or context.get("language"))
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

    rule_summary = _localized_rule_summary(context, language=resolved_language)
    if rule_summary:
        fact_bank["rule_summary"] = rule_summary

    run_note = _localized_execution_note(context, language=resolved_language)
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
        comparison = benchmark_comparison_from_delta(delta_vs_benchmark)
        fact_bank["benchmark_delta_magnitude"] = comparison.magnitude_points
        fact_bank["benchmark_comparison"] = _benchmark_comparison_phrase(
            delta_vs_benchmark,
            language=resolved_language,
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
    fact_bank["caveat"] = _breakdown_caveat(language=resolved_language)
    next_options = structured_next_experiments(
        {
            "config_snapshot": context.get("config_snapshot"),
            "symbols": context.get("symbols"),
        }
    )
    fact_bank["runnable_next_tests"] = _runnable_next_tests_label(
        next_options,
        language=resolved_language,
    )
    fact_bank["next_experiment_options"] = json.dumps(
        next_options,
        default=str,
    )
    fact_bank["draft_only_or_future_tests"] = _draft_only_tests_label(
        language=resolved_language
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


def _resolve_language(language: object) -> Language:
    return "es-419" if str(language or "en").lower().startswith("es") else "en"


def _is_spanish(language: object) -> bool:
    return _resolve_language(language) == "es-419"


def _breakdown_caveat(*, language: str) -> str:
    if _is_spanish(language):
        return (
            "Esto es evidencia de simulación histórica, no una predicción ni una "
            "recomendación de inversión."
        )
    return (
        "This is historical simulation evidence, not a prediction or trading "
        "recommendation."
    )


def _benchmark_comparison_phrase(
    delta_vs_benchmark: float | int | None,
    *,
    language: str,
) -> str:
    comparison = benchmark_comparison_from_delta(delta_vs_benchmark)
    if not _is_spanish(language):
        return comparison.user_phrase
    if comparison.claim == "matched_benchmark":
        return "En línea con la referencia"
    magnitude = (
        "desconocido"
        if delta_vs_benchmark is None
        else f"{abs(float(delta_vs_benchmark)):.1f} puntos porcentuales"
    )
    if comparison.claim == "beat_benchmark":
        return f"Superó por {magnitude}"
    if comparison.claim == "lagged_benchmark":
        return f"Quedó por debajo por {magnitude}"
    return "Comparado con la referencia"


def _runnable_next_tests_label(
    options: list[dict[str, Any]],
    *,
    language: str,
) -> str:
    if not _is_spanish(language):
        if options:
            labels = ", ".join(str(option["label"]) for option in options[:-1])
            if len(options) > 1:
                labels = f"{labels}, or {options[-1]['label']}"
            else:
                labels = str(options[0]["label"])
            return f"Try next: {labels}"
        return (
            "Try next: change the date range, test the same supported setup on "
            "a different same-class asset, or simplify the idea into a supported "
            "RSI or SMA/EMA rule"
        )

    if not options:
        return (
            "Prueba siguiente: cambia el rango de fechas, prueba el mismo setup "
            "compatible en otro activo de la misma clase, o simplifica la idea a una "
            "regla RSI o SMA/EMA compatible"
        )
    labels = [_spanish_next_experiment_label(option) for option in options]
    if len(labels) == 1:
        return f"Prueba siguiente: {labels[0]}"
    return f"Prueba siguiente: {', '.join(labels[:-1])}, o {labels[-1]}"


def _spanish_next_experiment_label(option: dict[str, Any]) -> str:
    kind = str(option.get("kind") or "").strip()
    label = str(option.get("label") or "").strip()
    if kind == "change_date_range":
        return "cambia el rango de fechas"
    if kind == "same_setup_peer_asset":
        return "prueba el mismo setup en otro activo de la misma clase"
    if kind == "supported_rsi_threshold":
        return "prueba un umbral RSI compatible"
    if kind == "supported_ma_crossover":
        return "prueba un cruce SMA/EMA compatible"
    if kind == "adjust_indicator_thresholds":
        return "ajusta el periodo o los umbrales del indicador"
    if kind == "compare_buy_and_hold":
        return "compara con comprar y mantener"
    if kind == "same_rule_peer_asset":
        return "prueba la misma regla en otro activo de la misma clase"
    if kind == "adjust_signal_periods":
        return "ajusta los periodos o la dirección del cruce"
    if kind == "adjust_contribution_cadence":
        return "ajusta la cadencia de aportes"
    return label or "prueba una variante compatible"


def _draft_only_tests_label(*, language: str) -> str:
    if _is_spanish(language):
        return (
            "Soporte futuro o solo borrador: DCA con capital inicial separado, "
            "límites de inversión y reglas personalizadas no compatibles."
        )
    return (
        "Draft-only or future support: DCA with separate starting principal, "
        "investment ceilings, and unsupported custom rules."
    )


def _breakdown_fact_labels(language: str) -> dict[str, str]:
    if _is_spanish(language):
        return {
            "test": "Prueba",
            "rule": "Regla",
            "performance": "Rendimiento",
            "total_return": "rendimiento total",
            "benchmark_return": "rendimiento de {benchmark} {value}",
            "benchmark_symbol": "referencia {benchmark}",
            "risk_marker": "Riesgo",
            "max_drawdown": "peor caída",
            "execution": "Ejecución",
            "starting_capital": "Capital inicial",
            "assumptions": "Supuestos",
            "keep_in_mind": "Ten en cuenta",
        }
    return {
        "test": "Test",
        "rule": "Rule",
        "performance": "Performance",
        "total_return": "total return",
        "benchmark_return": "{benchmark} benchmark return {value}",
        "benchmark_symbol": "benchmark {benchmark}",
        "risk_marker": "Risk marker",
        "max_drawdown": "max drawdown",
        "execution": "Execution",
        "starting_capital": "Starting capital",
        "assumptions": "Assumptions",
        "keep_in_mind": "Keep in mind",
    }


def _coerce_result_breakdown_draft(value: Any) -> ResultBreakdownDraft | None:
    if isinstance(value, ResultBreakdownDraft):
        return value
    if isinstance(value, dict) and "language_quality" not in value:
        value = {**value, "language_quality": "matches_prompt_language"}
    try:
        return ResultBreakdownDraft.model_validate(value)
    except (TypeError, ValidationError):
        return None


def _render_result_breakdown_draft(
    *,
    draft: ResultBreakdownDraft,
    fact_bank: dict[str, str],
    required_fact_ids: set[str],
    language: str = "en",
) -> str | None:
    if draft.language_quality != "matches_prompt_language":
        return None
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
            language=language,
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
    language: str = "en",
) -> tuple[str | None, set[str]]:
    body = ""
    fact_ids: list[str] = []
    used_fact_ids: set[str] = set()
    inline_fact_scaffold = _result_breakdown_parts_use_inline_fact_scaffold(parts)
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
    fact_block = _render_result_breakdown_fact_block(
        fact_ids,
        fact_bank=fact_bank,
        language=language,
    )
    if _result_breakdown_body_is_fragmentary(
        body,
        fact_ids,
        inline_fact_scaffold=inline_fact_scaffold,
    ):
        body = ""
    if body and fact_block:
        return f"{body}\n\n{fact_block}", used_fact_ids
    return (body or fact_block or None), used_fact_ids


def _render_result_breakdown_fact_block(
    fact_ids: list[str],
    *,
    fact_bank: dict[str, str],
    language: str = "en",
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

    labels = _breakdown_fact_labels(language)
    if _has("title", "symbols", "date_range"):
        title = _sentence_fragment(fact_bank.get("title") or "Stored backtest")
        symbols = _sentence_fragment(fact_bank.get("symbols") or "")
        date_range = _sentence_fragment(fact_bank.get("date_range") or "")
        test_text = title
        if symbols and symbols.lower() not in title.lower():
            test_text = f"{test_text} on {symbols}"
        if date_range:
            test_text = f"{test_text}, {date_range}"
        lines.append(f"**{labels['test']}:** {test_text}.")
        _consume("title", "symbols", "date_range")

    if _has("rule_summary"):
        lines.append(f"**{labels['rule']}:** {fact_bank['rule_summary']}")
        _consume("rule_summary")

    if _has(
        "total_return",
        "benchmark_symbol",
        "benchmark_return",
        "benchmark_delta",
        "benchmark_comparison",
    ):
        performance_parts: list[str] = []
        if "total_return" in remaining:
            performance_parts.append(
                f"{labels['total_return']} {fact_bank['total_return']}"
            )
        benchmark = _sentence_fragment(fact_bank.get("benchmark_symbol") or "")
        if "benchmark_return" in remaining and benchmark:
            performance_parts.append(
                labels["benchmark_return"].format(
                    benchmark=benchmark,
                    value=fact_bank["benchmark_return"],
                )
            )
        elif "benchmark_symbol" in remaining and benchmark:
            performance_parts.append(labels["benchmark_symbol"].format(benchmark=benchmark))
        if "benchmark_comparison" in remaining:
            performance_parts.append(fact_bank["benchmark_comparison"])
        elif "benchmark_delta" in remaining:
            performance_parts.append(
                f"relative performance {fact_bank['benchmark_delta']}"
            )
        if performance_parts:
            lines.append(f"**{labels['performance']}:** {'; '.join(performance_parts)}.")
        _consume(
            "total_return",
            "benchmark_symbol",
            "benchmark_return",
            "benchmark_delta",
            "benchmark_comparison",
        )

    if _has("max_drawdown"):
        lines.append(
            f"**{labels['risk_marker']}:** "
            f"{labels['max_drawdown']} {fact_bank['max_drawdown']}."
        )
        _consume("max_drawdown")

    if _has("execution_note"):
        lines.append(f"**{labels['execution']}:** {fact_bank['execution_note']}")
        _consume("execution_note")

    if _has("starting_capital"):
        lines.append(f"**{labels['starting_capital']}:** {fact_bank['starting_capital']}.")
        _consume("starting_capital")

    if _has("assumptions"):
        lines.append(f"**{labels['assumptions']}:** {fact_bank['assumptions']}")
        _consume("assumptions")

    if _has("caveat"):
        lines.append(f"**{labels['keep_in_mind']}:** {fact_bank['caveat']}")
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


def _result_breakdown_body_is_fragmentary(
    body: str,
    fact_ids: list[str],
    *,
    inline_fact_scaffold: bool,
) -> bool:
    if not body or not fact_ids:
        return False
    if inline_fact_scaffold:
        return True
    word_count = len([word for word in body.split(" ") if word.strip()])
    return word_count < 12


def _result_breakdown_parts_use_inline_fact_scaffold(
    parts: list[ResultBreakdownPart],
) -> bool:
    for index, part in enumerate(parts):
        if part.kind != "fact":
            continue
        previous_text = _nearest_result_breakdown_text_part(parts, index, step=-1)
        next_text = _nearest_result_breakdown_text_part(parts, index, step=1)
        if previous_text and not _text_part_ends_standalone_sentence(previous_text):
            return True
        if next_text and _text_part_starts_inline_continuation(next_text):
            return True
    return False


def _nearest_result_breakdown_text_part(
    parts: list[ResultBreakdownPart],
    start_index: int,
    *,
    step: int,
) -> str:
    index = start_index + step
    while 0 <= index < len(parts):
        part = parts[index]
        if part.kind == "text":
            text = str(part.text or "").strip()
            if text:
                return text
        if part.kind == "fact":
            return ""
        index += step
    return ""


def _text_part_ends_standalone_sentence(value: str) -> bool:
    text = str(value or "").strip()
    return bool(text and text[-1] in {".", "!", "?"})


def _text_part_starts_inline_continuation(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    first = text[0]
    return first in {".", ",", ";", ":", ")", "%", "-", "–", "—"} or first.islower()


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
    if "benchmark_comparison" in fact_bank:
        required.add("benchmark_comparison")
    elif "benchmark_delta" in fact_bank:
        required.add("benchmark_delta")
    return required


def _clean_result_breakdown_heading(value: str) -> str:
    heading = str(value or "").strip().lstrip("#").strip()
    if heading.casefold() in {"quick take", "quick breakdown"}:
        return ""
    return heading


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


def fallback_result_breakdown_message(
    context: dict[str, Any],
    *,
    language: str = "en",
) -> str:
    resolved_language = _resolve_language(language or context.get("language"))
    fact_bank = result_breakdown_fact_bank(context, language=resolved_language)
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
        _benchmark_comparison_phrase(delta_vs_benchmark, language=resolved_language)
        if delta_vs_benchmark is not None
        else (
            "la diferencia guardada contra la referencia"
            if _is_spanish(resolved_language)
            else "the stored benchmark spread"
        )
    )
    drawdown_text = (
        _format_result_breakdown_percent(max_drawdown)
        if max_drawdown is not None
        else "the available risk data"
    )
    rule_summary = _localized_rule_summary(context, language=resolved_language)
    execution_summary = _localized_execution_note(context, language=resolved_language)
    assumption_text = "; ".join(line.rstrip(".") for line in assumption_lines)
    next_check_text = _strip_try_next_label(fact_bank["runnable_next_tests"])
    if _is_spanish(resolved_language):
        period_sentence = f" del {date_range}" if date_range else ""
        setup_lines = [
            (
                f"{title} probó {symbols_text}{period_sentence} usando la "
                "configuración guardada del backtest."
            )
        ]
        if rule_summary:
            setup_lines.append(rule_summary)

        performance_lines = [
            (
                f"**Rendimiento total:** {total_return_text}. La referencia de "
                f"comparación fue {benchmark or 'la referencia guardada'} con "
                f"{benchmark_text}. {delta_text} frente a la referencia. Esto es "
                "una comparación de retornos históricos, no una explicación causal "
                "de por qué ocurrió el movimiento."
            )
        ]
        if execution_summary:
            performance_lines.append(execution_summary)

        return (
            "Aquí tienes una lectura más detallada de la simulación completada.\n\n"
            f"**Configuración.** {' '.join(setup_lines)}\n\n"
            f"**Cómo leerlo.** {' '.join(performance_lines)}\n\n"
            f"**Riesgo y supuestos.** La peor caída fue {drawdown_text}, el mayor "
            "descenso pico-a-valle capturado por la simulación. La prueba usó "
            f"{assumption_text or 'la configuración guardada'}.\n\n"
            f"**Siguiente prueba útil.** {_ensure_sentence(next_check_text)}\n\n"
            "Úsalo como evidencia de simulación histórica, no como predicción ni "
            "recomendación de inversión."
        )

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
        f"**Useful next check.** {_ensure_sentence(next_check_text)}\n\n"
        "Use this as historical simulation evidence, not a prediction or trading "
        "recommendation."
    )


def _strip_try_next_label(value: str) -> str:
    text = str(value or "").strip()
    for prefix in ("try next:", "prueba siguiente:"):
        if text.casefold().startswith(prefix):
            return text[len(prefix) :].strip()
    return text


def _localized_rule_summary(context: dict[str, Any], *, language: str) -> str | None:
    raw_summary = str(context.get("rule_summary") or "").strip()
    if not _is_spanish(language):
        return raw_summary or None

    strategy_type = _context_strategy_type(context)
    if strategy_type == "buy_and_hold":
        return "Regla: compra al inicio del periodo y mantén hasta el final."
    if strategy_type == "dca_accumulation":
        cadence = _localized_cadence_label(_context_cadence(context), language=language)
        cadence_text = f" con frecuencia {cadence}" if cadence else ""
        return f"Regla: compra{cadence_text} y mantén hasta el final."
    if strategy_type in {"indicator_threshold", "signal_strategy"}:
        return "Regla: se usó la regla técnica guardada de la simulación."
    if raw_summary:
        return "Regla: se usó la regla guardada de la simulación."
    return None


def _localized_execution_note(context: dict[str, Any], *, language: str) -> str | None:
    raw_note = str(context.get("execution_note") or "").strip()
    if not raw_note:
        return None
    if not _is_spanish(language):
        return raw_note
    return (
        "No hubo operaciones de entrada; la estrategia permaneció en efectivo "
        "porque la condición de entrada no se activó en ese periodo."
    )


def _context_strategy_type(context: dict[str, Any]) -> str | None:
    candidates: list[Any] = [context.get("strategy_type")]
    config = context.get("config_snapshot")
    if isinstance(config, dict):
        candidates.extend(
            [
                config.get("strategy_type"),
                config.get("template"),
            ]
        )
        resolved_strategy = config.get("resolved_strategy")
        if isinstance(resolved_strategy, dict):
            candidates.append(resolved_strategy.get("strategy_type"))
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _context_cadence(context: dict[str, Any]) -> str | None:
    candidates: list[Any] = []
    config = context.get("config_snapshot")
    if isinstance(config, dict):
        candidates.append(config.get("cadence"))
        resolved_parameters = config.get("resolved_parameters")
        if isinstance(resolved_parameters, dict):
            candidates.append(resolved_parameters.get("cadence"))
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _localized_cadence_label(value: str | None, *, language: str) -> str | None:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    if not _is_spanish(language):
        return normalized
    labels = {
        "daily": "diaria",
        "weekly": "semanal",
        "biweekly": "quincenal",
        "monthly": "mensual",
        "quarterly": "trimestral",
    }
    return labels.get(normalized, normalized)


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
) -> ResultBreakdownMessage:
    resolved_language = _resolve_language(language)
    if run is None:
        if _is_spanish(resolved_language):
            return ResultBreakdownMessage(
                text=(
                    "No pude encontrar el resultado completado más reciente para "
                    "esta conversación. Ejecuta el backtest de nuevo y puedo "
                    "desglosar esas métricas."
                ),
                source="missing_result",
                fallback_used=True,
                failure_mode="missing_result",
            )
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
    context_language = _resolve_language(language or context.get("language"))
    llm_text = llm_result_breakdown_message(context, language=context_language)
    if llm_text:
        return ResultBreakdownMessage(
            text=llm_text,
            source="llm_breakdown_stage",
            fallback_used=False,
        )
    return ResultBreakdownMessage(
        text=fallback_result_breakdown_message(context, language=context_language),
        source="deterministic_fallback",
        fallback_used=True,
        failure_mode="llm_unavailable_or_contract_rejected",
    )
