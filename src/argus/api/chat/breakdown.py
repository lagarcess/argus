from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from argus.agent_runtime.response_language import response_language_instruction
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


class ResultBreakdownDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(
        default="",
        description=(
            "Fallback visible answer in product_language. Prefer answer_blocks for "
            "readability when possible."
        ),
    )
    answer_blocks: list[str] = Field(
        min_length=1,
        max_length=3,
        description=(
            "One to three short visible markdown blocks in product_language using "
            "only supplied fact_bank facts."
        ),
    )
    fact_ids: list[str] = Field(
        min_length=1,
        description=(
            "Fact IDs from fact_bank grounding the answer. Include every required "
            "fact ID and do not invent IDs."
        ),
    )


RESULT_BREAKDOWN_LLM_TIMEOUT_SECONDS = 28.0


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
    resolved_language = _response_language(language or context.get("language"))
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
    )


def _invoke_breakdown_llm_with_budget(
    *,
    invoke_json_schema_func: Any,
    fact_bank: dict[str, str],
    required_fact_ids: set[str],
    context_packet_ids: list[str],
    language: str,
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
    resolved_language = _response_language(language)
    return [
        {
            "role": "system",
            "content": (
                f"{ARGUS_RESPONSE_STYLE_CONTRACT}\n\n"
                "You are Argus, an investing backtest copilot. Explain the stored "
                "backtest result using only the supplied fact_bank. Write for a "
                "normal person who is trying to keep exploring, not as a financial report. "
                f"{response_language_instruction(resolved_language)} "
                "Do not leave untranslated English words in user-facing prose except "
                "tickers, symbols, currency codes, numbers, and standard abbreviations. "
                "When product_language is not English, translate finance terms instead "
                "of borrowing English terms like benchmark. "
                "For non-English product_language, literal English words such as "
                "benchmark, drawdown, back-test, backtest, setup, total return, risk, "
                "assumptions, and useful next check are language-quality failures. "
                "Some source fact values may be stored in English; translate their "
                "meaning into product_language in your visible section bodies. Do "
                "not judge source fact values, fact IDs, or schema keys as user-facing "
                "language. "
                "Do not return empty sections just because source fact values are "
                "stored in English; translate those source facts and return the "
                "completed breakdown. "
                "Write every user-facing answer block in product_language. "
                "Symbols, tickers, currency codes, numbers, and percentages can stay "
                "unchanged, but internal fact IDs and schema field names are never "
                "user-facing copy. "
                "Start with one warm takeaway before details. Return one to three "
                "concise, non-template answer_blocks and vary the phrasing. Keep the "
                "full breakdown under 220 words. Do not fill a fixed outline. Put all "
                "visible prose in answer_blocks and use the top-level fact_ids only as "
                "grounding metadata. fact_ids are not user-visible and do not render "
                "words. fact_ids must include every fact_id listed in required_fact_ids. "
                "Do not omit required fact IDs even when the visible answer already "
                "mentions the value. Do not leave fact_ids empty. Do not invent fact IDs. "
                "Do not put fact IDs, HTML comments, or metadata markers inside "
                "answer_blocks. "
                "Keep the writing polished, conversational, and "
                "cohesive rather than fragmented. Do not expose fact_bank field names, "
                "context packet language, provider names, source plumbing, app internals, "
                "or implementation terms in user-facing prose. If context facts are "
                "available, describe them naturally as market or macro backdrop. Keep "
                "source/provider details internal. Respect capability truth in next "
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
    resolved_language = _response_language(language or context.get("language"))
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


def _response_language(language: object) -> str:
    return str(language or "en").strip() or "en"


def _breakdown_caveat(*, language: str) -> str:
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
    return comparison.user_phrase


def _runnable_next_tests_label(
    options: list[dict[str, Any]],
    *,
    language: str,
) -> str:
    if not options:
        return (
            "Try next: change the date range, test the same supported setup on "
            "a different same-class asset, or simplify the idea into a supported "
            "RSI or SMA/EMA rule"
        )
    labels = ", ".join(str(option["label"]) for option in options[:-1])
    if len(options) > 1:
        labels = f"{labels}, or {options[-1]['label']}"
    else:
        labels = str(options[0]["label"])
    return f"Try next: {labels}"


def _draft_only_tests_label(*, language: str) -> str:
    return (
        "Draft-only or future support: DCA with separate starting principal, "
        "investment ceilings, and unsupported custom rules."
    )


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
    rendered_text = _render_result_breakdown_answer_body(draft)
    if not rendered_text:
        return None

    used_fact_ids: set[str] = set()
    for fact_id_value in draft.fact_ids:
        fact_id = str(fact_id_value or "").strip()
        if fact_id not in fact_bank:
            return None
        used_fact_ids.add(fact_id)

    if not required_fact_ids.issubset(used_fact_ids):
        return None

    if not _rendered_breakdown_mentions_required_facts(
        rendered_text=rendered_text,
        fact_bank=fact_bank,
        required_fact_ids=required_fact_ids,
    ):
        return None

    if len(rendered_text.split()) > 520:
        return None
    if _contains_disallowed_breakdown_heading(rendered_text):
        return None
    if _contains_user_visible_internal_breakdown_term(rendered_text):
        return None
    return rendered_text


def _render_result_breakdown_answer_body(draft: ResultBreakdownDraft) -> str | None:
    raw_blocks = draft.answer_blocks or ([draft.answer] if draft.answer else [])
    blocks: list[str] = []
    comment_fact_ids: set[str] = set()
    for raw_block in raw_blocks:
        block, block_comment_fact_ids = _strip_result_breakdown_fact_id_comments(
            raw_block,
        )
        comment_fact_ids.update(block_comment_fact_ids)
        cleaned = _normalize_result_breakdown_body(block)
        if cleaned:
            blocks.append(cleaned)
    if comment_fact_ids and not draft.fact_ids:
        draft.fact_ids.extend(sorted(comment_fact_ids))
    if not blocks:
        return None
    return "\n\n".join(blocks).strip()


def _rendered_breakdown_mentions_required_facts(
    *,
    rendered_text: str,
    fact_bank: dict[str, str],
    required_fact_ids: set[str],
) -> bool:
    if "symbols" in required_fact_ids and not _mentions_all_breakdown_symbols(
        rendered_text,
        fact_bank.get("symbols"),
    ):
        return False
    if "benchmark_symbol" in required_fact_ids and not _contains_breakdown_text(
        rendered_text,
        fact_bank.get("benchmark_symbol"),
    ):
        return False
    if "date_range" in required_fact_ids and not _contains_breakdown_fact_value(
        rendered_text,
        fact_bank.get("date_range"),
    ):
        return False
    return not _contains_unknown_breakdown_metric_number(
        rendered_text=rendered_text,
        fact_bank=fact_bank,
    )


def _mentions_all_breakdown_symbols(text: str, value: str | None) -> bool:
    symbols = [
        symbol.strip()
        for symbol in str(value or "").replace(" and ", ",").split(",")
        if symbol.strip()
    ]
    return all(_contains_breakdown_text(text, symbol) for symbol in symbols)


def _contains_breakdown_fact_value(text: str, value: str | None) -> bool:
    cleaned = str(value or "").strip()
    if not cleaned:
        return True
    if _contains_breakdown_text(text, cleaned):
        return True
    numeric_tokens = _breakdown_numeric_tokens(cleaned)
    if not numeric_tokens:
        return False
    text_tokens = set(_breakdown_numeric_tokens(text))
    return all(token in text_tokens for token in numeric_tokens)


def _contains_breakdown_text(text: str, value: str | None) -> bool:
    cleaned = str(value or "").strip()
    return not cleaned or cleaned.casefold() in str(text or "").casefold()


def _contains_unknown_breakdown_metric_number(
    *,
    rendered_text: str,
    fact_bank: dict[str, str],
) -> bool:
    allowed: set[str] = set()
    for fact_id in (
        "total_return",
        "benchmark_return",
        "benchmark_delta_magnitude",
        "benchmark_comparison",
        "max_drawdown",
    ):
        allowed.update(_breakdown_metric_numeric_tokens(fact_bank.get(fact_id)))
    if not allowed:
        return False
    return any(
        token not in allowed for token in _breakdown_metric_numeric_tokens(rendered_text)
    )


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


def _normalize_result_breakdown_body(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def _breakdown_metric_numeric_tokens(value: str | None) -> list[str]:
    text = str(value or "")
    tokens: list[str] = []
    for index, character in enumerate(text):
        if not (character.isdigit() or character in "+-"):
            continue
        token = _breakdown_numeric_token_starting_at(text, index)
        if token is None:
            continue
        raw_token, end = token
        suffix = text[end : end + 24].casefold()
        stripped_suffix = suffix.lstrip()
        if not (
            stripped_suffix.startswith("%")
            or stripped_suffix.startswith("percentage point")
            or stripped_suffix.startswith("pts")
            or stripped_suffix.startswith("puntos porcentual")
        ):
            continue
        normalized = _normalize_result_breakdown_number_token(raw_token)
        if normalized is None:
            continue
        try:
            metric_token = f"{abs(float(normalized)):.1f}"
        except ValueError:
            continue
        if metric_token not in tokens:
            tokens.append(metric_token)
    return tokens


def _breakdown_numeric_tokens(value: str | None) -> list[str]:
    text = str(value or "")
    tokens: list[str] = []
    for index, character in enumerate(text):
        if not (character.isdigit() or character in "+-"):
            continue
        token = _breakdown_numeric_token_starting_at(text, index)
        if token is None:
            continue
        raw_token, _ = token
        normalized = _normalize_result_breakdown_number_token(raw_token)
        if normalized is None:
            continue
        try:
            numeric_token = f"{float(normalized):.1f}"
        except ValueError:
            continue
        if numeric_token not in tokens:
            tokens.append(numeric_token)
    return tokens


def _breakdown_numeric_token_starting_at(
    text: str,
    index: int,
) -> tuple[str, int] | None:
    candidate = ""
    cursor = index
    if text[cursor] in "+-":
        candidate += text[cursor]
        cursor += 1
    seen_digit = False
    while cursor < len(text):
        character = text[cursor]
        if character.isdigit():
            seen_digit = True
            candidate += character
            cursor += 1
            continue
        if character in ".,":
            candidate += character
            cursor += 1
            continue
        break
    if not seen_digit:
        return None
    return candidate, cursor


def _normalize_result_breakdown_number_token(value: str) -> str | None:
    token = value.strip().strip(".,")
    if not token or not any(character.isdigit() for character in token):
        return None
    if "." in token and "," in token:
        decimal_separator = "." if token.rfind(".") > token.rfind(",") else ","
        thousands_separator = "," if decimal_separator == "." else "."
        token = token.replace(thousands_separator, "")
        if decimal_separator == ",":
            token = token.replace(",", ".")
        return token
    if "," in token:
        return _normalize_single_result_breakdown_separator_number(
            token,
            separator=",",
        )
    if "." in token:
        return _normalize_single_result_breakdown_separator_number(
            token,
            separator=".",
        )
    return token


def _normalize_single_result_breakdown_separator_number(
    value: str,
    *,
    separator: str,
) -> str:
    pieces = value.split(separator)
    if len(pieces) > 1 and all(len(piece) == 3 for piece in pieces[1:]):
        return "".join(pieces)
    if separator == ",":
        return value.replace(",", ".")
    return value


def _strip_result_breakdown_fact_id_comments(
    value: str,
) -> tuple[str, set[str]]:
    text = str(value or "")
    if "<!--" not in text:
        return text, set()

    fact_ids: set[str] = set()
    pieces: list[str] = []
    index = 0
    while index < len(text):
        start = text.find("<!--", index)
        if start == -1:
            pieces.append(text[index:])
            break
        end = text.find("-->", start + 4)
        if end == -1:
            pieces.append(text[index:])
            break
        pieces.append(text[index:start])
        candidate = text[start + 4 : end].strip()
        if candidate:
            fact_ids.add(candidate)
        index = end + 3
    return "".join(pieces), fact_ids


def _ensure_sentence(value: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        return ""
    if cleaned[-1:] in {".", "!", "?"}:
        return cleaned
    return f"{cleaned}."


def _required_result_breakdown_fact_ids(fact_bank: dict[str, str]) -> set[str]:
    # Required IDs are acceptance anchors, not the full fact surface; the model
    # still receives the complete fact bank for risk, assumptions, and next tests.
    required: set[str] = {"caveat"}
    for fact_id in (
        "title",
        "symbols",
        "date_range",
        "total_return",
        "benchmark_symbol",
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


def _contains_disallowed_breakdown_heading(value: str) -> bool:
    normalized = str(value or "").casefold()
    return "quick take" in normalized or "quick breakdown" in normalized


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
    resolved_language = _response_language(language or context.get("language"))
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
        else "the stored benchmark spread"
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
    prefix = "try next:"
    if text.casefold().startswith(prefix):
        return text[len(prefix) :].strip()
    return text


def _localized_rule_summary(context: dict[str, Any], *, language: str) -> str | None:
    raw_summary = str(context.get("rule_summary") or "").strip()
    return raw_summary or None


def _localized_execution_note(context: dict[str, Any], *, language: str) -> str | None:
    raw_note = str(context.get("execution_note") or "").strip()
    if not raw_note:
        return None
    return raw_note


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
    return normalized


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
