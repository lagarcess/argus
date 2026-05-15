from __future__ import annotations

import inspect
import json
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from argus.agent_runtime.stages.interpret_types import ResultFollowupFocus
from argus.domain.engine_launch.result_facts import (
    execution_note,
    resolved_rule_summary,
    runnable_next_tests,
)
from argus.llm.openrouter import invoke_openrouter_json_schema, log_openrouter_failure


class ResultFollowupPart(BaseModel):
    kind: Literal["text", "fact"]
    text: str = ""
    fact_id: str | None = None


class ResultFollowupDraft(BaseModel):
    parts: list[ResultFollowupPart] = Field(default_factory=list)


async def compose_result_followup_response(
    *,
    metadata: dict[str, Any],
    focus: ResultFollowupFocus,
    user_message: str,
    invoke_json_schema_func=invoke_openrouter_json_schema,
    log_openrouter_failure_func=log_openrouter_failure,
) -> str | None:
    fact_bank = result_followup_fact_bank(metadata)
    if not fact_bank:
        return None
    required_fact_ids = required_result_followup_fact_ids(
        fact_bank=fact_bank,
        focus=focus,
    )
    try:
        raw_response = invoke_json_schema_func(
            task="result_summary",
            messages=result_followup_llm_messages(
                fact_bank=fact_bank,
                focus=focus,
                user_message=user_message,
                required_fact_ids=required_fact_ids,
            ),
            schema_model=ResultFollowupDraft,
            schema_name="ResultFollowupDraft",
        )
        if inspect.isawaitable(raw_response):
            raw_response = await raw_response
    except Exception as exc:
        log_openrouter_failure_func(
            task="result_summary",
            model_name=None,
            exc=exc,
            message="LLM result follow-up failed; using grounded fallback",
        )
        return None

    draft = coerce_result_followup_draft(raw_response)
    if draft is None:
        return None
    return render_result_followup_draft(
        draft=draft,
        fact_bank=fact_bank,
        required_fact_ids=required_fact_ids,
        focus=focus,
    )


def result_followup_llm_messages(
    *,
    fact_bank: dict[str, str],
    focus: ResultFollowupFocus,
    user_message: str,
    required_fact_ids: set[str],
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are Argus, a chat-first investing backtest copilot. Answer the "
                "user's follow-up using only the supplied fact_bank. Be conversational, "
                "specific, and useful; do not sound like a fixed template. Put every "
                "run-specific symbol, date, percentage, drawdown, benchmark, rule, "
                "trade count, assumption, caveat, and next-test option in a fact part. "
                "Use fact parts inline where the exact value belongs, and use text parts "
                "for interpretation, education, and transitions. Text parts must not "
                "repeat raw fact values; they should say what the fact means, while "
                "fact parts provide the exact symbols, dates, returns, and caveats. Do not "
                "start with a block of consecutive fact parts; weave facts into a short "
                "answer. Correct "
                "false premises directly. Explain what happened from metrics separately "
                "from plausible non-causal market interpretation. Offer only next tests "
                "listed in runnable_next_tests. Do not invent trades, prices, support, "
                "indicators, predictions, investment advice, or unsupported mechanics."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "question": user_message,
                    "focus": focus,
                    "fact_bank": fact_bank,
                    "required_fact_ids": sorted(required_fact_ids),
                },
                default=str,
            ),
        },
    ]


def coerce_result_followup_draft(value: Any) -> ResultFollowupDraft | None:
    if isinstance(value, ResultFollowupDraft):
        return value
    try:
        return ResultFollowupDraft.model_validate(value)
    except (TypeError, ValidationError):
        return None


def render_result_followup_draft(
    *,
    draft: ResultFollowupDraft,
    fact_bank: dict[str, str],
    required_fact_ids: set[str],
    focus: ResultFollowupFocus,
) -> str | None:
    if not draft.parts or len(draft.parts) > 24:
        return None
    body = ""
    fact_ids: list[str] = []
    used_fact_ids: set[str] = set()
    pending_fact_ids: list[str] = []
    text_parts = 0
    for part in draft.parts:
        if part.kind == "text":
            if text_reuses_fact_value(part.text, fact_bank=fact_bank):
                return None
            body = append_sentence_piece(
                body,
                render_result_followup_fact_line(
                    pending_fact_ids,
                    fact_bank=fact_bank,
                ),
            )
            pending_fact_ids = []
            body = append_sentence_piece(body, part.text)
            if normalize_text(part.text):
                text_parts += 1
            continue
        fact_id = str(part.fact_id or "").strip()
        if fact_id not in fact_bank:
            return None
        pending_fact_ids.append(fact_id)
        if fact_id not in used_fact_ids:
            fact_ids.append(fact_id)
            used_fact_ids.add(fact_id)
    body = append_sentence_piece(
        body,
        render_result_followup_fact_line(
            pending_fact_ids,
            fact_bank=fact_bank,
        ),
    )

    if text_parts == 0:
        return None
    if not required_fact_ids.issubset(used_fact_ids):
        return None
    body = normalize_text(body)
    if not body:
        return None
    rendered = apply_result_followup_fact_guardrails(
        body,
        fact_bank=fact_bank,
        focus=focus,
    )
    if len(rendered.split()) > 240:
        return None
    return rendered.strip()


def text_reuses_fact_value(text: Any, *, fact_bank: dict[str, str]) -> bool:
    normalized_text = comparable_text(text)
    if not normalized_text:
        return False
    exact_text = normalize_text(text).lower()
    for value in fact_bank.values():
        cleaned = clean_fragment(value)
        if len(cleaned) < 3:
            continue
        if cleaned.lower() in exact_text:
            return True
        comparable_value = comparable_text(cleaned)
        if len(comparable_value) >= 3 and comparable_value in normalized_text:
            return True
    return False


def render_result_followup_fact_line(
    fact_ids: list[str],
    *,
    fact_bank: dict[str, str],
) -> str:
    unique_fact_ids = list(dict.fromkeys(fact_ids))
    if not unique_fact_ids:
        return ""
    if len(unique_fact_ids) == 1:
        fact_id = unique_fact_ids[0]
        value = clean_fragment(fact_bank.get(fact_id))
        return value
    fragments = [
        clean_fragment(fact_bank[fact_id])
        for fact_id in unique_fact_ids
        if fact_bank.get(fact_id)
    ]
    if not fragments:
        return ""
    return "; ".join(fragments)


def _labeled_fact_fragment(fact_id: str, value: str) -> str:
    labels = {
        "symbols": "Asset",
        "strategy": "Strategy",
        "date_range": "Period",
        "benchmark_symbol": "Benchmark",
        "total_return": "Strategy return",
        "benchmark_return": "Benchmark return",
        "benchmark_delta": "Gap versus benchmark",
        "max_drawdown": "Max drawdown",
        "trade_count": "Trades",
        "starting_capital": "Starting capital",
        "assumptions": "Assumptions",
    }
    label = labels.get(fact_id)
    cleaned = clean_fragment(value)
    return f"{label}: {cleaned}" if label else cleaned


def result_followup_fact_bank_for_focus(
    *,
    fact_bank: dict[str, str],
    focus: ResultFollowupFocus,
) -> dict[str, str]:
    filtered = dict(fact_bank)
    if focus == "why_underperformed" and filtered.get("strategy") == "buy and hold":
        filtered.pop("trade_count", None)
    return filtered


def result_followup_fact_bank(metadata: dict[str, Any]) -> dict[str, str]:
    config = config_snapshot(metadata)
    fact_bank: dict[str, str] = {}
    symbols = symbols_label(metadata)
    if symbols:
        fact_bank["symbols"] = symbols
    strategy = strategy_label(config.get("template") or config.get("strategy_type"))
    if strategy:
        fact_bank["strategy"] = strategy
    date_range = date_range_label(config.get("date_range") or metadata.get("date_range"))
    if date_range:
        fact_bank["date_range"] = date_range
    benchmark = str(
        config.get("benchmark_symbol") or metadata.get("benchmark_symbol") or ""
    ).strip()
    if benchmark:
        fact_bank["benchmark_symbol"] = benchmark
    total_return = metric_number(
        metadata,
        paths=(("metrics", "aggregate", "performance", "total_return_pct"),),
    )
    if total_return is not None:
        fact_bank["total_return"] = format_percent(total_return)
    benchmark_return = metric_number(
        metadata,
        paths=(
            ("metrics", "aggregate", "performance", "benchmark_return_pct"),
            ("metrics", "benchmark_metrics", "aggregate", "total_return_pct"),
        ),
    )
    if benchmark_return is not None:
        fact_bank["benchmark_return"] = format_percent(benchmark_return)
    benchmark_delta = metric_number(
        metadata,
        paths=(("metrics", "aggregate", "performance", "delta_vs_benchmark_pct"),),
    )
    if benchmark_delta is not None:
        fact_bank["benchmark_delta"] = format_percent(benchmark_delta)
    drawdown = metric_number(
        metadata,
        paths=(
            ("metrics", "aggregate", "risk", "max_drawdown_pct"),
            ("metrics", "aggregate", "max_drawdown_pct"),
        ),
    )
    if drawdown is not None:
        fact_bank["max_drawdown"] = format_percent(drawdown, signed=False)
    trade_count = metric_number(
        metadata,
        paths=(("metrics", "aggregate", "efficiency", "total_trades"),),
    )
    if trade_count is not None:
        fact_bank["trade_count"] = f"{int(trade_count)} trades"
    rule_summary = str(resolved_rule_summary(metadata) or "").strip()
    if rule_summary:
        fact_bank["rule_summary"] = rule_summary
    note = str(execution_note(metadata) or "").strip()
    if note:
        fact_bank["execution_note"] = note
    capital = capital_label(config)
    if capital:
        fact_bank["starting_capital"] = capital
    assumptions = assumptions_from_result_metadata(metadata)
    if assumptions:
        fact_bank["assumptions"] = "; ".join(clean_fragment(item) for item in assumptions)
    fact_bank["caveat"] = "Historical simulation evidence, not a prediction or trading recommendation"
    fact_bank["runnable_next_tests"] = runnable_next_tests(metadata)
    return fact_bank


def required_result_followup_fact_ids(
    *,
    fact_bank: dict[str, str],
    focus: ResultFollowupFocus,
) -> set[str]:
    required: set[str] = {"caveat"}
    if "symbols" in fact_bank:
        required.add("symbols")
    if focus == "max_drawdown":
        required.update(fact_id for fact_id in ("max_drawdown",) if fact_id in fact_bank)
    elif focus == "what_tested":
        for fact_id in (
            "strategy",
            "date_range",
            "benchmark_symbol",
            "rule_summary",
            "execution_note",
            "assumptions",
        ):
            if fact_id in fact_bank:
                required.add(fact_id)
    elif focus == "why_underperformed":
        for fact_id in (
            "total_return",
            "benchmark_symbol",
            "benchmark_return",
            "benchmark_delta",
            "execution_note",
        ):
            if fact_id in fact_bank:
                required.add(fact_id)
    elif focus == "next_experiment":
        required.add("runnable_next_tests")
    elif focus == "assumptions":
        for fact_id in ("assumptions", "starting_capital", "benchmark_symbol"):
            if fact_id in fact_bank:
                required.add(fact_id)
    return required


def fallback_result_followup_response(
    *,
    metadata: dict[str, Any],
    focus: ResultFollowupFocus,
) -> str | None:
    fact_bank = result_followup_fact_bank(metadata)
    if not fact_bank:
        return None
    fact_bank = result_followup_fact_bank_for_focus(
        fact_bank=fact_bank,
        focus=focus,
    )
    if focus == "max_drawdown" and "max_drawdown" in fact_bank:
        return (
            f"The max drawdown was {fact_bank['max_drawdown']} for "
            f"{fact_bank.get('symbols', 'this run')}."
        )
    if focus == "what_tested":
        return fallback_what_tested_response(fact_bank)
    if focus == "next_experiment":
        return fact_bank["runnable_next_tests"] + "."
    if focus == "assumptions" and "assumptions" in fact_bank:
        return "The run used: " + fact_bank["assumptions"] + "."
    if focus == "why_underperformed":
        return fallback_performance_response(fact_bank)
    return fallback_performance_response(fact_bank)


def apply_result_followup_fact_guardrails(
    response: str,
    *,
    fact_bank: dict[str, str],
    focus: ResultFollowupFocus | Literal["general"],
) -> str:
    cleaned = normalize_text(response)
    if not cleaned:
        return cleaned
    if focus != "why_underperformed":
        return cleaned
    delta_number = as_float(fact_bank.get("benchmark_delta"))
    if delta_number is None or delta_number <= 0:
        return cleaned
    lower = cleaned.lower()
    if "did not underperform" in lower or "outperform" in lower:
        return cleaned
    return "It did not underperform in this run. " + cleaned


def fallback_performance_response(fact_bank: dict[str, str]) -> str | None:
    if not any(
        fact_bank.get(key)
        for key in ("total_return", "benchmark_return", "benchmark_delta")
    ):
        return None
    symbols = fact_bank.get("symbols") or "the strategy"
    strategy = fact_bank.get("strategy") or "strategy"
    date_range = fact_bank.get("date_range")
    total_return = fact_bank.get("total_return")
    benchmark = fact_bank.get("benchmark_symbol")
    benchmark_return = fact_bank.get("benchmark_return")
    benchmark_delta = fact_bank.get("benchmark_delta")
    delta_number = as_float(benchmark_delta)
    if delta_number is not None and delta_number > 0:
        if benchmark:
            intro = f"{symbols} beat {benchmark} in this run."
        else:
            intro = f"{symbols} beat the benchmark in this run."
    elif delta_number is not None and delta_number < 0:
        if benchmark:
            intro = f"{symbols} lagged {benchmark} in this run."
        else:
            intro = f"{symbols} lagged the benchmark in this run."
    else:
        intro = "Here is the performance context for this run."
    context = f"The run used {article_for(strategy)} {strategy} strategy on {symbols}"
    if date_range:
        context += f" over {date_range}"
    pieces = [intro, context + "."]
    if total_return:
        pieces.append(f"The strategy returned {total_return}.")
    if benchmark and benchmark_return:
        pieces.append(f"{benchmark} returned {benchmark_return}.")
    elif benchmark:
        pieces.append(f"The benchmark was {benchmark}.")
    if benchmark_delta:
        pieces.append(f"The gap versus the benchmark was {benchmark_delta}.")
    if delta_number is not None and delta_number < 0:
        pieces.append(
            "For this kind of historical comparison, that mainly says the chosen "
            "asset and holding window were weaker than the benchmark; it is not "
            "causal proof by itself."
        )
    elif delta_number is not None and delta_number > 0:
        pieces.append(
            "That is a relative-performance fact from the run, not proof that the "
            "same edge would persist."
        )
    if fact_bank.get("execution_note"):
        pieces.append(clean_fragment(fact_bank["execution_note"]) + ".")
    if fact_bank.get("caveat"):
        pieces.append(clean_fragment(fact_bank["caveat"]) + ".")
    return " ".join(piece.strip() for piece in pieces if piece.strip())


def fallback_what_tested_response(fact_bank: dict[str, str]) -> str:
    symbols = fact_bank.get("symbols") or "the selected asset"
    strategy = fact_bank.get("strategy") or "strategy"
    parts = [
        f"I tested {symbols} with {article_for(strategy)} {strategy} strategy",
    ]
    if fact_bank.get("date_range"):
        parts.append(f"over {fact_bank['date_range']}")
    if fact_bank.get("benchmark_symbol"):
        parts.append(f"against {fact_bank['benchmark_symbol']}")
    sentence = " ".join(parts).strip() + "."
    extras = [
        fact_bank.get("rule_summary"),
        fact_bank.get("execution_note"),
    ]
    if fact_bank.get("total_return"):
        extras.append(f"The strategy returned {fact_bank['total_return']}")
    if fact_bank.get("benchmark_symbol") and fact_bank.get("benchmark_return"):
        extras.append(
            f"{fact_bank['benchmark_symbol']} returned {fact_bank['benchmark_return']}"
        )
    elif fact_bank.get("benchmark_symbol"):
        extras.append(f"The benchmark was {fact_bank['benchmark_symbol']}")
    if fact_bank.get("benchmark_delta"):
        extras.append(f"The gap versus the benchmark was {fact_bank['benchmark_delta']}")
    if fact_bank.get("assumptions"):
        extras.append(f"Assumptions: {fact_bank['assumptions']}")
    extra_text = " ".join(clean_fragment(item) + "." for item in extras if item)
    return (sentence + " " + extra_text).strip()


def article_for(label: str) -> str:
    stripped = label.strip()
    if not stripped:
        return "a"
    first_word = stripped.split()[0]
    if first_word.isupper() and first_word[0] in {
        "A",
        "E",
        "F",
        "H",
        "I",
        "L",
        "M",
        "N",
        "O",
        "R",
        "S",
        "X",
    }:
        return "an"
    return "an" if stripped[0].lower() in {"a", "e", "i", "o", "u"} else "a"


def append_sentence_piece(current: str, piece: str) -> str:
    cleaned = normalize_text(piece)
    if not cleaned:
        return current
    if not current:
        return cleaned
    if cleaned[:1] in {".", ",", ";", ":", "!", "?", ")", "%"}:
        return current.rstrip() + cleaned
    return current.rstrip() + " " + cleaned


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def comparable_text(value: Any) -> str:
    normalized = normalize_text(value).lower()
    return " ".join(
        "".join(char if char.isalnum() else " " for char in normalized).split()
    )


def clean_fragment(value: Any) -> str:
    return str(value or "").strip().rstrip(".; ")


def config_snapshot(metadata: dict[str, Any]) -> dict[str, Any]:
    config = metadata.get("config_snapshot")
    return dict(config) if isinstance(config, dict) else {}


def metric_number(
    metadata: dict[str, Any],
    *,
    paths: tuple[tuple[str, ...], ...],
) -> float | None:
    for path in paths:
        value: Any = metadata
        for key in path:
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(key)
        number = as_float(value)
        if number is not None:
            return number
    return None


def as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace("%", "").replace("+", "").replace(",", "")
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def format_percent(value: float, *, signed: bool = True) -> str:
    sign = "+" if signed and value > 0 else ""
    return f"{sign}{value:.1f}%"


def symbols_label(metadata: dict[str, Any]) -> str:
    symbols = metadata.get("symbols")
    if not isinstance(symbols, list) or not symbols:
        symbols = config_snapshot(metadata).get("symbols")
    if isinstance(symbols, list):
        values = [str(symbol).strip().upper() for symbol in symbols if str(symbol)]
        if values:
            return ", ".join(values)
    return ""


def strategy_label(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    labels = {
        "buy_and_hold": "buy and hold",
        "dca_accumulation": "recurring buy",
        "indicator_threshold": "indicator threshold",
        "rsi_mean_reversion": "RSI mean reversion",
        "signal_strategy": "signal strategy",
    }
    return labels.get(value.strip(), value.strip().replace("_", " "))


def date_range_label(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if not isinstance(value, dict):
        return None
    display = value.get("display")
    if isinstance(display, str) and display.strip():
        return display.strip()
    start = value.get("start")
    end = value.get("end")
    if start and end:
        return f"{start} to {end}"
    return None


def capital_label(config: dict[str, Any]) -> str | None:
    value = config.get("starting_capital") or config.get("initial_capital")
    number = as_float(value)
    if number is not None and number > 0:
        return f"${number:,.0f}"
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def assumptions_from_result_metadata(metadata: dict[str, Any]) -> list[str]:
    card = metadata.get("result_card")
    if isinstance(card, dict):
        assumptions = card.get("assumptions")
        if isinstance(assumptions, list):
            return [str(item) for item in assumptions if str(item).strip()]
    assumptions = metadata.get("assumptions")
    if isinstance(assumptions, list):
        return [str(item) for item in assumptions if str(item).strip()]
    return []
