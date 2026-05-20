from __future__ import annotations

import inspect
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from argus.agent_runtime.response_style import ARGUS_RESPONSE_STYLE_CONTRACT
from argus.agent_runtime.stages.interpret_types import ResultFollowupFocus
from argus.context.rendering import context_packet_fact_summary
from argus.domain.engine_launch.result_facts import (
    execution_note,
    resolved_rule_summary,
    runnable_next_tests,
    structured_next_experiments,
)
from argus.llm.openrouter import (
    OpenRouterTask,
    invoke_openrouter_json_schema,
    log_openrouter_failure,
    record_openrouter_route_receipt,
)

RelativePerformanceClaim = Literal[
    "beat_benchmark",
    "lagged_benchmark",
    "matched_benchmark",
    "not_applicable",
    "unknown",
]
CausalAttributionClaim = Literal["none", "directly_supported", "unsupported"]


class ResultFollowupDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relative_performance_claim: RelativePerformanceClaim = Field(
        description=(
            "Structured claim about strategy performance versus benchmark. Use the "
            "supplied relative_performance_truth when it is known."
        )
    )
    causal_attribution_claim: CausalAttributionClaim = Field(
        default="none",
        description=(
            "Use unsupported if the answer claims or implies that a rule, macro "
            "condition, news item, or context packet caused/helped/avoided the "
            "performance without a directly supplied causal fact. Use directly_supported "
            "only when fact_bank directly supports causality. Otherwise use none."
        ),
    )
    answer: str = Field(
        description=(
            "Conversational interpretation using only fact_bank values. Include exact "
            "run facts when they help answer the user. Do not mention software, "
            "routing, provider paths, or implementation changes unless fact_bank "
            "explicitly contains that fact."
        )
    )
    fact_ids: list[str] = Field(
        description=(
            "Fact IDs from fact_bank that the renderer must attach. Include every "
            "required_fact_id and do not invent IDs."
        )
    )
    next_experiment_option_kinds: list[str] = Field(
        default_factory=list,
        description=(
            "For next_experiment focus, optional supported option kinds copied from "
            "next_experiment_options. The runtime renders option labels from the "
            "structured fact bank, not from freeform text."
        ),
    )


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
    use_context_route = result_followup_uses_context_route(
        fact_bank=fact_bank,
        focus=focus,
    )
    required_fact_ids = required_result_followup_fact_ids(
        fact_bank=fact_bank,
        focus=focus,
        include_context=use_context_route,
    )
    context_packet_ids = context_packet_ids_from_fact_bank(fact_bank)
    llm_task = result_followup_llm_task(
        fact_bank=fact_bank,
        focus=focus,
    )
    try:
        raw_response = invoke_json_schema_func(
            task=llm_task,
            messages=result_followup_llm_messages(
                fact_bank=fact_bank,
                focus=focus,
                user_message=user_message,
                required_fact_ids=required_fact_ids,
            ),
            schema_model=ResultFollowupDraft,
            schema_name="ResultFollowupDraft",
            context_packet_ids=context_packet_ids,
        )
        if inspect.isawaitable(raw_response):
            raw_response = await raw_response
    except Exception as exc:
        log_openrouter_failure_func(
            task=llm_task,
            model_name=None,
            exc=exc,
            message="LLM result follow-up failed; using grounded fallback",
        )
        return None

    draft = coerce_result_followup_draft(raw_response)
    if draft is None:
        record_result_followup_fallback_receipt(
            task=llm_task,
            failure_mode="invalid_result_followup_draft",
            context_packet_ids=context_packet_ids,
        )
        return None
    if draft.causal_attribution_claim == "unsupported":
        record_result_followup_fallback_receipt(
            task=llm_task,
            failure_mode="unsupported_causal_attribution_claim",
            context_packet_ids=context_packet_ids,
        )
        return fallback_result_followup_response(metadata=metadata, focus=focus)
    rendered = render_result_followup_draft(
        draft=draft,
        fact_bank=fact_bank,
        required_fact_ids=required_fact_ids,
        focus=focus,
    )
    if rendered is None:
        record_result_followup_fallback_receipt(
            task=llm_task,
            failure_mode="result_followup_draft_rejected",
            context_packet_ids=context_packet_ids,
        )
        return None
    claim_failure = result_followup_claim_failure(
        draft=draft,
        fact_bank=fact_bank,
        focus=focus,
    )
    if claim_failure:
        record_result_followup_fallback_receipt(
            task=llm_task,
            failure_mode=claim_failure,
            context_packet_ids=context_packet_ids,
        )
        return fallback_result_followup_response(metadata=metadata, focus=focus)
    return rendered


def result_followup_llm_task(
    *,
    fact_bank: dict[str, str],
    focus: ResultFollowupFocus,
) -> OpenRouterTask:
    if result_followup_uses_context_route(fact_bank=fact_bank, focus=focus):
        return "result_breakdown"
    return "result_summary"


def result_followup_uses_context_route(
    *,
    fact_bank: dict[str, str],
    focus: ResultFollowupFocus,
) -> bool:
    return bool(
        fact_bank.get("context_packet_facts")
        and focus in {"general", "why_underperformed"}
    )


def record_result_followup_fallback_receipt(
    *,
    task: OpenRouterTask,
    failure_mode: str,
    context_packet_ids: list[str] | None = None,
) -> None:
    record_openrouter_route_receipt(
        task=task,
        model_name=None,
        mode="json_schema",
        schema_name="ResultFollowupDraft",
        latency_ms=0,
        outcome="failed",
        failure_mode=failure_mode,
        context_packet_ids=context_packet_ids,
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
                f"{ARGUS_RESPONSE_STYLE_CONTRACT}\n\n"
                "You are Argus, a chat-first investing backtest copilot. Answer the "
                "user's follow-up using only the supplied fact_bank. Be conversational, "
                "specific, and useful; do not sound like a fixed template. Return a "
                "short natural-language answer plus fact_ids. The answer should use "
                "the supplied facts naturally, while fact_ids tells the runtime which "
                "symbols, dates, percentages, drawdowns, benchmarks, caveats, context "
                "facts, and next-test options ground the answer. fact_ids must include every "
                "fact_id in required_fact_ids; do not omit required fact ids even when "
                "they feel repetitive. Do not invent fact ids. Do not expose fact_bank "
                "keys or schema names in the answer, including benchmark_delta, "
                "total_return, max_drawdown, context_packet_facts, fact_ids, or "
                "relative_performance_claim; translate them into plain language. Fact "
                "IDs are grounding metadata; they do not mean every fact needs to be "
                "recited in the user-visible answer. Choose the one or two numbers "
                "that best answer the question unless the user explicitly asks for a "
                "full breakdown. Set the first sentence as a plain takeaway, not a "
                "metric recap. For "
                "why/how follow-ups, use one or two short paragraphs: first say what "
                "the simulation shows, then say what it cannot prove. Do not write "
                "like a report abstract. For next-experiment follow-ups, use a short "
                "lead-in and two or three bullets from the provided options. Set "
                "relative_performance_claim to the supplied relative_performance_truth "
                "when it is known, and keep the answer consistent with that claim. Set "
                "causal_attribution_claim to unsupported if your answer claims or implies "
                "that a strategy rule, macro backdrop, event, or context item caused, "
                "helped, avoided, drove, or explained performance beyond the supplied "
                "metrics. Correct "
                "false premises directly. Explain what happened from metrics separately "
                "from plausible non-causal market interpretation. Use context_packet_facts "
                "only as possible backdrop, never as proof of causality unless the fact "
                "directly says so. Disallowed topics unless fact_bank explicitly includes "
                "them: software changes, runtime changes, routing fixes, provider paths, "
                "implementation details, or app internals. Do not repeat, negate, or explain "
                "those terms just because the user mentioned them; treat them as irrelevant "
                "conversation context and answer the investing result. Suggest next tests "
                "when focus is next_experiment, or when user_message also asks what to try, "
                "compare, refine, or improve next. When you do, offer only tests listed in "
                "runnable_next_tests or next_experiment_options, and format them as two "
                "or three short, separate bullets or numbered lines. Do not invent trades, "
                "prices, support, indicators, "
                "predictions, investment advice, unsupported mechanics, or unsupported "
                "causes."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "question": result_followup_focus_question(focus),
                    "focus": focus,
                    "user_message": user_message,
                    "fact_bank": fact_bank,
                    "required_fact_ids": sorted(required_fact_ids),
                    "relative_performance_truth": relative_performance_truth(fact_bank),
                },
                default=str,
            ),
        },
    ]


def result_followup_focus_question(focus: ResultFollowupFocus) -> str:
    questions: dict[ResultFollowupFocus, str] = {
        "general": "Explain the latest run using the available grounded facts.",
        "why_underperformed": (
            "Explain the result versus the benchmark, correcting the premise if the "
            "strategy did not underperform."
        ),
        "max_drawdown": "Explain the max drawdown for the latest run.",
        "what_tested": "Explain what was tested in the latest run.",
        "next_experiment": "Suggest useful supported next experiments for this run.",
        "assumptions": "Explain the assumptions used by the latest run.",
    }
    return questions.get(focus, questions["general"])


def context_packet_ids_from_fact_bank(fact_bank: dict[str, str]) -> list[str]:
    raw = str(fact_bank.get("context_packet_ids") or "").strip()
    if not raw:
        return []
    packet_ids: list[str] = []
    for value in raw.split(","):
        packet_id = value.strip()
        if packet_id and packet_id not in packet_ids:
            packet_ids.append(packet_id)
    return packet_ids


def coerce_result_followup_draft(value: Any) -> ResultFollowupDraft | None:
    if isinstance(value, ResultFollowupDraft):
        return value
    try:
        return ResultFollowupDraft.model_validate(value)
    except (TypeError, ValidationError):
        return None


def result_followup_claim_failure(
    *,
    draft: ResultFollowupDraft,
    fact_bank: dict[str, str],
    focus: ResultFollowupFocus,
) -> str | None:
    if focus != "why_underperformed":
        return None
    truth = relative_performance_truth(fact_bank)
    if truth in {"not_applicable", "unknown"}:
        return None
    if draft.relative_performance_claim in {"not_applicable", "unknown"}:
        return "missing_relative_performance_claim"
    if draft.relative_performance_claim != truth:
        return "relative_performance_claim_contradiction"
    return None


def relative_performance_truth(
    fact_bank: dict[str, str],
) -> RelativePerformanceClaim:
    delta_number = as_float(fact_bank.get("benchmark_delta"))
    if delta_number is None:
        return "unknown"
    if delta_number > 0:
        return "beat_benchmark"
    if delta_number < 0:
        return "lagged_benchmark"
    return "matched_benchmark"


def render_result_followup_draft(
    *,
    draft: ResultFollowupDraft,
    fact_bank: dict[str, str],
    required_fact_ids: set[str],
    focus: ResultFollowupFocus,
) -> str | None:
    body = normalize_text(draft.answer)
    if not body:
        return None
    if draft.causal_attribution_claim == "unsupported":
        return None
    if contains_user_visible_internal_fact_name(body):
        return None
    if len(draft.fact_ids) > 36:
        return None
    used_fact_ids: set[str] = set()
    ordered_fact_ids: list[str] = []
    for fact_id_value in draft.fact_ids:
        fact_id = str(fact_id_value or "").strip()
        if fact_id not in fact_bank:
            return None
        if fact_id not in used_fact_ids:
            ordered_fact_ids.append(fact_id)
            used_fact_ids.add(fact_id)

    appendable_missing_fact_ids = appendable_missing_required_fact_ids(
        missing_fact_ids=required_fact_ids - used_fact_ids,
        fact_bank=fact_bank,
        focus=focus,
    )
    ordered_fact_ids.extend(appendable_missing_fact_ids)
    used_fact_ids.update(appendable_missing_fact_ids)
    body = append_sentence_piece(
        body,
        render_result_followup_fact_line(
            appendable_missing_fact_ids,
            fact_bank=fact_bank,
        ),
    )
    if not required_fact_ids.issubset(used_fact_ids):
        return None
    body = normalize_text(body)
    if not body:
        return None
    if focus == "next_experiment":
        return render_next_experiment_followup(
            draft=draft,
            fact_bank=fact_bank,
        )
    rendered = body
    max_words = 360 if fact_bank.get("context_packet_facts") else 240
    if len(rendered.split()) > max_words:
        return None
    return rendered.strip()


INTERNAL_FACT_NAMES = (
    "benchmark_delta",
    "total_return",
    "benchmark_return",
    "max_drawdown",
    "trade_count",
    "context_packet_facts",
    "context_packet_ids",
    "fact_bank",
    "fact_ids",
    "relative_performance_claim",
)


def contains_user_visible_internal_fact_name(answer: str) -> bool:
    normalized = answer.lower()
    return any(name in normalized for name in INTERNAL_FACT_NAMES)


def appendable_missing_required_fact_ids(
    *,
    missing_fact_ids: set[str],
    fact_bank: dict[str, str],
    focus: ResultFollowupFocus,
) -> list[str]:
    appendable_fact_ids = {
        "context_packet_facts",
        "context_packet_limitations",
        "caveat",
        "relative_performance",
    }
    if result_followup_uses_context_route(fact_bank=fact_bank, focus=focus):
        appendable_fact_ids.update(
            {
                "symbols",
                "strategy",
                "date_range",
                "benchmark_symbol",
                "total_return",
                "benchmark_return",
                "benchmark_delta",
                "max_drawdown",
                "trade_count",
                "rule_summary",
                "execution_note",
                "starting_capital",
                "assumptions",
            }
        )
    return [
        fact_id
        for fact_id in fact_bank
        if fact_id in missing_fact_ids and fact_id in appendable_fact_ids
    ]


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
        "relative_performance": "Relative performance",
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
        relative = relative_performance_label(
            symbols=symbols,
            benchmark=benchmark,
            delta=benchmark_delta,
        )
        if relative:
            fact_bank["relative_performance"] = relative
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
    context_facts = context_packet_fact_summary(
        _context_packets_from_metadata(metadata),
        symbols=symbols_list(metadata),
    )
    fact_bank.update(context_facts)
    fact_bank["caveat"] = (
        "Historical simulation evidence, not a prediction or trading recommendation"
    )
    fact_bank["runnable_next_tests"] = runnable_next_tests(metadata)
    fact_bank["next_experiment_options"] = json.dumps(
        structured_next_experiments(metadata),
        default=str,
    )
    return fact_bank


def required_result_followup_fact_ids(
    *,
    fact_bank: dict[str, str],
    focus: ResultFollowupFocus,
    include_context: bool = False,
) -> set[str]:
    required: set[str] = {"caveat"}
    has_context_facts = "context_packet_facts" in fact_bank
    has_context_limitations = "context_packet_limitations" in fact_bank
    if has_context_limitations:
        required.add("context_packet_limitations")
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
        for fact_id in ("relative_performance", "execution_note"):
            if fact_id in fact_bank:
                required.add(fact_id)
        if has_context_facts:
            required.add("context_packet_facts")
        if has_context_limitations:
            required.add("context_packet_limitations")
    elif focus == "general" and include_context:
        for fact_id in ("context_packet_facts",):
            if fact_id in fact_bank:
                required.add(fact_id)
        if has_context_limitations:
            required.add("context_packet_limitations")
    elif focus == "next_experiment":
        required.add("runnable_next_tests")
        required.add("next_experiment_options")
    elif focus == "assumptions":
        for fact_id in ("assumptions", "starting_capital", "benchmark_symbol"):
            if fact_id in fact_bank:
                required.add(fact_id)
    return required


def _context_packets_from_metadata(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    packets = metadata.get("context_packets") or metadata.get("attached_context_packets")
    if not isinstance(packets, list):
        return []
    return [packet for packet in packets if isinstance(packet, dict)]


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
        return fallback_next_experiment_response(fact_bank)
    if focus == "assumptions" and "assumptions" in fact_bank:
        return "The run used: " + fact_bank["assumptions"] + "."
    if focus == "why_underperformed":
        return fallback_performance_response(fact_bank)
    if focus == "general":
        return fallback_general_result_followup_response(fact_bank)
    return fallback_performance_response(fact_bank)


def fallback_next_experiment_response(fact_bank: dict[str, str]) -> str:
    options = structured_next_experiment_labels(fact_bank)
    if options:
        bullets = "\n".join(
            f"- {_ensure_sentence(_sentence_case(option))}" for option in options[:3]
        )
        return "A good next move is to isolate one assumption.\n\n" + bullets
    return _ensure_sentence(clean_fragment(fact_bank["runnable_next_tests"]))


def render_next_experiment_followup(
    *,
    draft: ResultFollowupDraft,
    fact_bank: dict[str, str],
) -> str | None:
    options = structured_next_experiment_options(fact_bank)
    if not options:
        return None
    selected_options = selected_next_experiment_options(
        options=options,
        selected_kinds=draft.next_experiment_option_kinds,
    )
    if not selected_options:
        selected_options = options[:3]
    bullets = "\n".join(
        f"- {_ensure_sentence(_sentence_case(str(option['label'])))}"
        for option in selected_options[:3]
    )
    return "A good next move is to isolate one assumption.\n\n" + bullets


def selected_next_experiment_options(
    *,
    options: list[dict[str, Any]],
    selected_kinds: list[str],
) -> list[dict[str, Any]]:
    by_kind = {
        str(option.get("kind") or ""): option
        for option in options
        if str(option.get("kind") or "")
    }
    selected: list[dict[str, Any]] = []
    for kind_value in selected_kinds:
        kind = str(kind_value or "").strip()
        option = by_kind.get(kind)
        if option is not None and option not in selected:
            selected.append(option)
    return selected


def structured_next_experiment_options(
    fact_bank: dict[str, str],
) -> list[dict[str, Any]]:
    raw_options = fact_bank.get("next_experiment_options")
    if not raw_options:
        return []
    try:
        parsed = json.loads(raw_options)
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    options: list[dict[str, Any]] = []
    for option in parsed:
        if not isinstance(option, dict):
            continue
        if option.get("contract") != "supported_backtest_experiment":
            continue
        label = clean_fragment(option.get("label"))
        kind = clean_fragment(option.get("kind"))
        if not label or not kind:
            continue
        options.append(
            {
                "kind": kind,
                "label": label,
                "contract": "supported_backtest_experiment",
            }
        )
    return options


def structured_next_experiment_labels(fact_bank: dict[str, str]) -> list[str]:
    labels: list[str] = []
    for option in structured_next_experiment_options(fact_bank):
        label = clean_fragment(option.get("label"))
        if label and label not in labels:
            labels.append(label)
    return labels


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
    relative_performance = fact_bank.get("relative_performance")
    if relative_performance:
        intro = _ensure_sentence(relative_performance)
    elif delta_number is not None and delta_number > 0:
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
        intro = "This run mostly tells us how the confirmed setup behaved."
    pieces = [intro]
    strategy_phrase = strategy_run_phrase(strategy)
    context_parts = [f"{article_for(strategy_phrase)} {strategy_phrase} on {symbols}"]
    if date_range:
        context_parts.append(f"over {date_range}")
    pieces.append("The setup was " + " ".join(context_parts) + ".")
    same_asset_benchmark = symbols_match_benchmark(symbols, benchmark)
    if same_asset_benchmark and strategy == "buy and hold" and benchmark:
        if total_return:
            pieces.append(f"It returned {total_return}.")
        pieces.append(
            f"Because the benchmark was also {benchmark}, this is mainly the "
            "asset's move over the window, not a separate strategy edge."
        )
    else:
        if total_return:
            pieces.append(f"The strategy returned {total_return}.")
        if benchmark and benchmark_return:
            pieces.append(f"{benchmark} returned {benchmark_return}.")
        elif benchmark:
            pieces.append(f"The benchmark was {benchmark}.")
    if benchmark_delta:
        pieces.append(f"The gap versus the benchmark was {benchmark_delta}.")
    if fact_bank.get("max_drawdown"):
        pieces.append(f"The max drawdown was {fact_bank['max_drawdown']}.")
    if delta_number is not None and delta_number < 0:
        pieces.append(
            "The useful read is that this confirmed rule did not keep up over that "
            "window; the run does not prove why."
        )
    elif delta_number is not None and delta_number > 0:
        pieces.append(
            "That is a relative-performance fact from the run, not proof the same "
            "edge would persist."
        )
    if fact_bank.get("execution_note"):
        pieces.append(clean_fragment(fact_bank["execution_note"]) + ".")
    append_context_backdrop(pieces, fact_bank)
    if fact_bank.get("caveat"):
        pieces.append("Use it as historical simulation evidence, not a prediction or recommendation.")
    return " ".join(piece.strip() for piece in pieces if piece.strip())


def fallback_general_result_followup_response(fact_bank: dict[str, str]) -> str | None:
    symbols = fact_bank.get("symbols") or "the latest run"
    strategy = fact_bank.get("strategy") or "strategy"
    strategy_phrase = strategy_run_phrase(strategy)
    pieces = [
        f"I’ve got the latest run: {symbols} with {article_for(strategy_phrase)} {strategy_phrase}.",
    ]
    if fact_bank.get("date_range"):
        pieces.append(f"Period: {fact_bank['date_range']}.")
    if fact_bank.get("total_return"):
        pieces.append(f"The strategy returned {fact_bank['total_return']}.")
    if fact_bank.get("benchmark_symbol") and fact_bank.get("benchmark_return"):
        pieces.append(
            f"{fact_bank['benchmark_symbol']} returned {fact_bank['benchmark_return']}."
        )
    elif fact_bank.get("benchmark_symbol"):
        pieces.append(f"Benchmark: {fact_bank['benchmark_symbol']}.")
    if fact_bank.get("benchmark_delta"):
        pieces.append(f"The gap versus the benchmark was {fact_bank['benchmark_delta']}.")
    if fact_bank.get("max_drawdown"):
        pieces.append(f"The max drawdown was {fact_bank['max_drawdown']}.")
    if fact_bank.get("execution_note"):
        pieces.append(clean_fragment(fact_bank["execution_note"]) + ".")
    append_context_backdrop(pieces, fact_bank)
    labels = structured_next_experiment_labels(fact_bank)
    if labels:
        pieces.append(
            "A useful next step would be to "
            + clean_fragment(labels[0]).lower()
            + "."
        )
    elif fact_bank.get("runnable_next_tests"):
        pieces.append(_ensure_sentence(clean_fragment(fact_bank["runnable_next_tests"])))
    if fact_bank.get("caveat"):
        pieces.append("Use it as historical simulation evidence, not a prediction or recommendation.")
    response = " ".join(piece.strip() for piece in pieces if piece.strip())
    return normalize_text(response) or None


def append_context_backdrop(pieces: list[str], fact_bank: dict[str, str]) -> None:
    if fact_bank.get("context_packet_facts"):
        pieces.append(
            "Careful backdrop: "
            + first_context_fragment(fact_bank["context_packet_facts"])
            + ". It can frame a follow-up question, but it does not prove "
            "causality or change the simulated trades."
        )
    elif fact_bank.get("context_packet_limitations"):
        pieces.append(clean_fragment(fact_bank["context_packet_limitations"]) + ".")


def symbols_match_benchmark(symbols: str, benchmark: str | None) -> bool:
    if not symbols or not benchmark:
        return False
    normalized_symbols = symbols.replace(" ", "").upper()
    normalized_benchmark = benchmark.strip().upper()
    return normalized_symbols == normalized_benchmark


def first_context_fragment(value: str) -> str:
    text = clean_fragment(value)
    if "; " in text:
        text = text.split("; ", 1)[0]
    return text


def fallback_what_tested_response(fact_bank: dict[str, str]) -> str:
    symbols = fact_bank.get("symbols") or "the selected asset"
    strategy = fact_bank.get("strategy") or "strategy"
    strategy_phrase = strategy_run_phrase(strategy)
    parts = [
        f"I tested {symbols} with {article_for(strategy_phrase)} {strategy_phrase}",
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


def strategy_run_phrase(label: str) -> str:
    phrase = _humanized_strategy_phrase(label)
    if not phrase:
        return "strategy"
    if phrase.endswith("strategy"):
        return phrase
    if phrase == "buy and hold":
        return "buy and hold strategy"
    return f"{phrase} strategy"


def _humanized_strategy_phrase(label: str) -> str:
    phrase = normalize_text(label).lower().replace("buy-and-hold", "buy and hold")
    if not phrase:
        return ""
    words = phrase.split()
    acronym_replacements = {
        "rsi": "RSI",
        "sma": "SMA",
        "ema": "EMA",
        "macd": "MACD",
    }
    return " ".join(acronym_replacements.get(word, word) for word in words)


def _ensure_sentence(value: str) -> str:
    cleaned = clean_fragment(value)
    if not cleaned:
        return ""
    return cleaned if cleaned.endswith((".", "!", "?")) else cleaned + "."


def _sentence_case(value: str) -> str:
    cleaned = clean_fragment(value)
    if not cleaned:
        return ""
    return cleaned[:1].upper() + cleaned[1:]


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


def clean_fragment(value: Any) -> str:
    return str(value or "").strip().rstrip(".; ")


def relative_performance_label(
    *,
    symbols: str,
    benchmark: str,
    delta: float,
) -> str | None:
    subject = symbols or "The strategy"
    benchmark_label = benchmark or "the benchmark"
    if delta > 0:
        return f"{subject} beat {benchmark_label} by {format_percent(delta)} in this run"
    if delta < 0:
        return (
            f"{subject} lagged {benchmark_label} by "
            f"{format_percent(abs(delta), signed=False)} in this run"
        )
    return f"{subject} matched {benchmark_label} in this run"


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
    values = symbols_list(metadata)
    return ", ".join(values)


def symbols_list(metadata: dict[str, Any]) -> list[str]:
    symbols = metadata.get("symbols")
    if not isinstance(symbols, list) or not symbols:
        symbols = config_snapshot(metadata).get("symbols")
    if isinstance(symbols, list):
        values = [str(symbol).strip().upper() for symbol in symbols if str(symbol)]
        if values:
            return values
    return []


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
