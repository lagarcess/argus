from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from argus.agent_runtime.stages.interpret import StageResult
from argus.agent_runtime.state.models import (
    ConfirmationPayload,
    FinalResponsePayload,
    ResponseProfile,
    RunState,
)
from argus.domain.engine_launch.result_facts import (
    execution_note as result_execution_note,
)
from argus.domain.engine_launch.result_facts import (
    resolved_rule_summary as result_rule_summary,
)
from argus.llm.openrouter import (
    build_openrouter_model,
    log_openrouter_failure,
    openrouter_task_timeout_seconds,
    record_openrouter_route_receipt,
)
from langchain_core.messages import HumanMessage, SystemMessage


def explain_stage(*, state: RunState) -> StageResult:
    result_payload = _result_payload(state)
    explanation_context = _explanation_context(state)
    profile = _response_profile(state)
    strategy = _strategy_payload(state)
    optional_parameters = _optional_parameters(state)
    tested_summary = _tested_summary(
        strategy=strategy,
        result_payload=result_payload,
        explanation_context=explanation_context,
    )
    assumption_summary = _assumption_summary(
        optional_parameters=optional_parameters,
        explanation_context=explanation_context,
    )
    caveat = _caveat_summary(explanation_context)
    result_facts = _result_facts_for_explanation(
        strategy=strategy,
        result_payload=result_payload,
        explanation_context=explanation_context,
    )
    execution_note = result_execution_note(result_facts)
    rule_summary = result_rule_summary(result_facts)

    total_return, benchmark_return, same_period = _resolved_return_metrics(
        result_payload=result_payload,
        explanation_context=explanation_context,
    )
    if total_return is None or benchmark_return is None:
        return StageResult(
            outcome="ready_to_respond",
            stage_patch={
                "assistant_response": _build_incomplete_result_response(
                    profile=profile,
                    tested_summary=tested_summary,
                    assumption_summary=assumption_summary,
                    caveat=caveat,
                    execution_note=execution_note,
                    rule_summary=rule_summary,
                )
            },
        )

    return StageResult(
        outcome="ready_to_respond",
        stage_patch={
            "assistant_response": _build_response(
                total_return=total_return,
                benchmark_return=benchmark_return,
                same_period=same_period,
                profile=profile,
                tested_summary=tested_summary,
                assumption_summary=assumption_summary,
                caveat=caveat,
                execution_note=execution_note,
                rule_summary=rule_summary,
            )
        },
    )


async def explain_stage_async(*, state: RunState) -> StageResult:
    fallback = explain_stage(state=state)
    fallback_text = fallback.stage_patch.get("assistant_response")
    if not isinstance(fallback_text, str) or not fallback_text:
        return fallback

    streamed_text = await _stream_llm_explanation(
        state=state,
        fallback_text=fallback_text,
    )
    if streamed_text is None:
        return fallback
    return StageResult(
        outcome=fallback.outcome,
        stage_patch={**fallback.stage_patch, "assistant_response": streamed_text},
    )


async def _stream_llm_explanation(
    *,
    state: RunState,
    fallback_text: str,
) -> str | None:
    model = build_openrouter_model("result_summary")
    if model is None:
        return None
    strategy = _strategy_payload(state)
    result_payload = _result_payload(state)
    explanation_context = _explanation_context(state)
    result_facts = _result_facts_for_explanation(
        strategy=strategy,
        result_payload=result_payload,
        explanation_context=explanation_context,
    )
    context = {
        "tested_summary": _tested_summary(
            strategy=strategy,
            result_payload=result_payload,
            explanation_context=explanation_context,
        ),
        "execution_note": result_execution_note(result_facts),
        "rule_summary": result_rule_summary(result_facts),
        "strategy": _canonical_strategy_context(strategy),
        "result": result_payload,
        "explanation_context": explanation_context,
        "fallback_text": fallback_text,
        "language": "use the user's current language preference if available",
    }
    messages = [
        SystemMessage(
            content=(
                "You are Argus explaining a completed historical backtest. "
                "Use only the supplied metrics and assumptions. Keep the response "
                "concise, natural, and beginner-friendly. Do not invent metrics, "
                "predictions, fees, slippage, or unsupported trading capabilities. "
                "Describe the tested strategy from tested_summary, not from raw "
                "user wording or strategy_thesis. "
                "If rule_summary is present, include it in the Test bullet. "
                "If execution_note is present, include it because it explains a "
                "flat or no-trade result. "
                "Format the answer as markdown: a bold 'Readout' label, one short "
                "takeaway paragraph, then 3 to 5 bullets for Test, Signal when "
                "execution_note is present, Next check for no-trade results, "
                "Assumptions, and Caveat. Keep it under 120 words. "
                "For no-trade results, say the strategy stayed in cash instead of "
                "using dramatic market timing language. "
                "Do not restate every result-card metric; interpret what matters."
            )
        ),
        HumanMessage(content=json.dumps(context, default=str, sort_keys=True)),
    ]
    started_at = time.perf_counter()
    try:
        chunks = await asyncio.wait_for(
            _collect_stream_chunks(model, messages),
            timeout=openrouter_task_timeout_seconds("result_summary"),
        )
    except Exception as exc:
        record_openrouter_route_receipt(
            task="result_summary",
            model_name=None,
            mode="chat_model",
            schema_name=None,
            latency_ms=_elapsed_ms(started_at),
            outcome="failed",
            failure_mode=type(exc).__name__,
        )
        log_openrouter_failure(
            task="result_summary",
            model_name=None,
            exc=exc,
            message="Result explanation streaming failed; using deterministic fallback",
        )
        return None
    text = "".join(chunks).strip()
    record_openrouter_route_receipt(
        task="result_summary",
        model_name=None,
        mode="chat_model",
        schema_name=None,
        latency_ms=_elapsed_ms(started_at),
        outcome="succeeded" if text else "failed",
        failure_mode=None if text else "empty_response",
    )
    return text or None


async def _collect_stream_chunks(model: Any, messages: list[Any]) -> list[str]:
    chunks: list[str] = []
    async for chunk in model.astream(messages):
        content = _chunk_content(chunk)
        if content:
            chunks.append(content)
    return chunks


def _chunk_content(chunk: Any) -> str:
    content = getattr(chunk, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)
    return ""


def _elapsed_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)


def _result_payload(state: RunState) -> dict[str, Any]:
    payload = state.final_response_payload
    if payload is None:
        return {}
    if isinstance(payload, FinalResponsePayload):
        return dict(payload.result or {})
    if isinstance(payload, dict):
        return dict(payload.get("result") or {})
    return {}


def _explanation_context(state: RunState) -> dict[str, Any]:
    payload = state.final_response_payload
    if payload is None:
        return {}
    if isinstance(payload, FinalResponsePayload):
        return dict(payload.explanation_context or {})
    if isinstance(payload, dict):
        return dict(payload.get("explanation_context") or {})
    return {}


def _response_profile(state: RunState) -> ResponseProfile | None:
    return state.effective_response_profile


def _strategy_payload(state: RunState) -> dict[str, Any]:
    payload = state.confirmation_payload
    if payload is None:
        return {}
    if isinstance(payload, ConfirmationPayload):
        return payload.strategy.model_dump(mode="python")
    strategy = payload.get("strategy") if isinstance(payload, dict) else None
    if isinstance(strategy, dict):
        return dict(strategy)
    return {}


def _result_facts_for_explanation(
    *,
    strategy: dict[str, Any],
    result_payload: dict[str, Any],
    explanation_context: dict[str, Any],
) -> dict[str, Any]:
    facts = dict(result_payload)
    if "metrics" not in facts and isinstance(explanation_context.get("metrics"), dict):
        facts["metrics"] = explanation_context["metrics"]
    if "benchmark_metrics" not in facts and isinstance(
        explanation_context.get("benchmark_metrics"),
        dict,
    ):
        facts["benchmark_metrics"] = explanation_context["benchmark_metrics"]
    if "resolved_strategy" not in facts:
        facts["resolved_strategy"] = {
            "strategy_type": strategy.get("strategy_type")
            or explanation_context.get("strategy_type"),
            "asset_universe": strategy.get("asset_universe"),
            "entry_rule": strategy.get("entry_rule"),
            "exit_rule": strategy.get("exit_rule"),
        }
    if "resolved_parameters" not in facts and isinstance(
        explanation_context.get("resolved_parameters"),
        dict,
    ):
        facts["resolved_parameters"] = explanation_context["resolved_parameters"]
    return facts


def _optional_parameters(state: RunState) -> dict[str, Any]:
    payload = state.confirmation_payload
    if payload is None:
        return {}
    if isinstance(payload, ConfirmationPayload):
        return payload.optional_parameters
    if isinstance(payload, dict):
        optional_parameters = payload.get("optional_parameters")
        if isinstance(optional_parameters, dict):
            return dict(optional_parameters)
    return {}


def _thesis(strategy: dict[str, Any]) -> str | None:
    thesis = strategy.get("strategy_thesis")
    if thesis is None:
        return None
    thesis_text = str(thesis).strip().rstrip(".")
    return thesis_text or None


def _tested_summary(
    *,
    strategy: dict[str, Any],
    result_payload: dict[str, Any],
    explanation_context: dict[str, Any],
) -> str | None:
    assets = _asset_summary(strategy)
    strategy_label = _strategy_label(
        strategy.get("strategy_type") or explanation_context.get("strategy_type")
    )
    period = _period_summary(
        strategy.get("date_range")
        or explanation_context.get("date_range")
        or result_payload.get("date_range")
    )
    if assets and strategy_label and period:
        return f"{assets} {strategy_label} over {period}"
    if assets and strategy_label:
        return f"{assets} {strategy_label}"
    if assets and period:
        return f"{assets} over {period}"
    thesis = _thesis(strategy)
    return f"the confirmed strategy: {thesis}" if thesis else None


def _canonical_strategy_context(strategy: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in strategy.items()
        if key not in {"raw_user_phrasing", "strategy_thesis"}
    }


def _asset_summary(strategy: dict[str, Any]) -> str | None:
    assets = strategy.get("asset_universe")
    if isinstance(assets, list):
        symbols = [str(symbol).strip() for symbol in assets if str(symbol).strip()]
        return ", ".join(symbols) if symbols else None
    if isinstance(assets, str) and assets.strip():
        return assets.strip()
    return None


def _strategy_label(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip()
    labels = {
        "buy_and_hold": "buy and hold",
        "dca_accumulation": "DCA accumulation",
        "indicator_threshold": "indicator threshold",
    }
    return labels.get(normalized, normalized.replace("_", " "))


def _period_summary(value: Any) -> str | None:
    if isinstance(value, str):
        period = value.strip()
        return period or None
    if isinstance(value, dict):
        display = value.get("display")
        if isinstance(display, str) and display.strip():
            return display.strip()
        start = value.get("start")
        end = value.get("end")
        if start and end:
            return f"{start} to {end}"
    return None


def _assumption_summary(
    *,
    optional_parameters: dict[str, Any],
    explanation_context: dict[str, Any],
) -> str:
    defaulted_labels: list[str] = []
    user_labels: list[str] = []
    assumptions = explanation_context.get("assumptions", [])

    for value in optional_parameters.values():
        if not isinstance(value, dict):
            continue
        label = str(value.get("label") or "Unnamed setting")
        source = str(value.get("source") or "")
        if source == "default":
            defaulted_labels.append(label)
        elif source == "user":
            user_labels.append(label)

    parts = []
    if isinstance(assumptions, list) and assumptions:
        assumption_text = _compact_sentence_list(assumptions, limit=3)
        if assumption_text:
            parts.append("Assumptions: " + assumption_text)
    elif defaulted_labels:
        parts.append("Defaults: " + ", ".join(defaulted_labels) + ".")
    if user_labels:
        parts.append("User-set options: " + ", ".join(user_labels) + ".")
    return " ".join(parts)


def _caveat_summary(explanation_context: dict[str, Any]) -> str:
    caveats = explanation_context.get("caveats", [])
    if not isinstance(caveats, list) or not caveats:
        return "This is a return comparison, not causal attribution."
    caveat_text = _compact_sentence_list(caveats, limit=2)
    if not caveat_text:
        return "This is a return comparison, not causal attribution."
    return f"This is a return comparison, not causal attribution. {caveat_text}"


def _build_response(
    *,
    total_return: float,
    benchmark_return: float,
    same_period: bool,
    profile: ResponseProfile | None,
    tested_summary: str | None,
    assumption_summary: str,
    caveat: str,
    execution_note: str | None,
    rule_summary: str | None,
) -> str:
    tone = profile.effective_tone if profile is not None else "friendly"
    verbosity = profile.effective_verbosity if profile is not None else "medium"
    expertise_mode = (
        profile.effective_expertise_mode if profile is not None else "beginner"
    )

    expertise_sentence = _expertise_sentence(expertise_mode)

    if verbosity == "low":
        return _result_readout_markdown(
            total_return=total_return,
            benchmark_return=benchmark_return,
            same_period=same_period,
            tested_summary=tested_summary,
            interpretation=expertise_sentence,
            assumption_summary=assumption_summary,
            caveat=caveat,
            execution_note=execution_note,
            rule_summary=rule_summary,
            compact=True,
        )

    return _result_readout_markdown(
        total_return=total_return,
        benchmark_return=benchmark_return,
        same_period=same_period,
        tested_summary=tested_summary,
        interpretation=expertise_sentence,
        assumption_summary=assumption_summary,
        caveat=caveat,
        execution_note=execution_note,
        rule_summary=rule_summary,
        compact=tone == "concise" and verbosity != "high",
    )


def _result_readout_markdown(
    *,
    total_return: float,
    benchmark_return: float,
    same_period: bool,
    tested_summary: str | None,
    interpretation: str,
    assumption_summary: str,
    caveat: str,
    execution_note: str | None,
    rule_summary: str | None,
    compact: bool,
) -> str:
    delta = total_return - benchmark_return
    takeaway = _readout_takeaway(
        total_return=total_return,
        benchmark_return=benchmark_return,
        same_period=same_period,
        delta=delta,
        execution_note=execution_note,
    )
    tested = _tested_readout_line(tested_summary, rule_summary)
    lines = [
        "**Readout**",
        "",
        takeaway,
        "",
        f"- **Test:** {tested}.",
    ]
    if execution_note:
        lines.append(f"- **Signal:** {_compact_execution_note(execution_note)}")
    else:
        lines.append(f"- **Interpretation:** {interpretation}")
    next_check = _next_check_line(execution_note=execution_note)
    if next_check:
        lines.append(f"- **Next check:** {next_check}")
    if assumption_summary:
        lines.append(f"- **Assumptions:** {_strip_leading_label(assumption_summary)}")
    lines.append(f"- **Caveat:** {caveat}")
    return "\n".join(lines)


def _readout_takeaway(
    *,
    total_return: float,
    benchmark_return: float,
    same_period: bool,
    delta: float,
    execution_note: str | None,
) -> str:
    benchmark_context = _benchmark_context_phrase(same_period)
    relative = _relative_performance_sentence(delta)
    if execution_note and abs(total_return) < 0.05:
        return (
            "No trade opened. The strategy stayed in cash because its entry "
            f"condition never fired; it returned {total_return:.1f}% while the "
            f"benchmark returned {benchmark_return:.1f}% {benchmark_context}; "
            f"it {relative}"
        )
    return (
        f"The strategy returned {total_return:.1f}% while the benchmark returned "
        f"{benchmark_return:.1f}% {benchmark_context}, so it {relative}"
    )


def _relative_performance_sentence(delta: float) -> str:
    if abs(delta) < 0.05:
        return "was effectively in line with the benchmark."
    direction = "outperformed" if delta > 0 else "lagged"
    return f"{direction} by {abs(delta):.1f} percentage points."


def _tested_readout_line(
    tested_summary: str | None,
    rule_summary: str | None,
) -> str:
    tested = (tested_summary or "the confirmed strategy").strip().rstrip(".")
    if not rule_summary:
        return tested
    rule = rule_summary.strip()
    if not rule:
        return tested
    return f"{tested}. {rule.rstrip('.')}"


def _compact_execution_note(execution_note: str) -> str:
    note = execution_note.strip()
    if note.startswith("No entry trades were executed") and (
        "entry condition did not trigger" in note
    ):
        return (
            "The entry condition did not trigger in this window, so no position "
            "was opened."
        )
    return note


def _next_check_line(*, execution_note: str | None) -> str | None:
    if execution_note and execution_note.startswith("No entry trades were executed"):
        return (
            "Loosen the entry threshold or widen the window before judging the "
            "idea."
        )
    return None


def _benchmark_context_phrase(same_period: bool) -> str:
    if same_period:
        return "over the same period"
    return "for the comparison window"


def _strip_leading_label(value: str) -> str:
    text = value.strip()
    if text.startswith("Assumptions:"):
        return text[len("Assumptions:") :].strip()
    return text


def _expertise_sentence(expertise_mode: str) -> str:
    if expertise_mode == "advanced":
        return "This is a return comparison only, without causal attribution."
    if expertise_mode == "intermediate":
        return "Use this as a direct benchmark comparison before deciding on refinements."
    return "Use this as an evidence check for the confirmed rule before refining it."


def _benchmark_scope_phrase(same_period: bool) -> str:
    if same_period:
        return "for the benchmark over the same period"
    return "for the reported benchmark"


def _build_incomplete_result_response(
    *,
    profile: ResponseProfile | None,
    tested_summary: str | None,
    assumption_summary: str,
    caveat: str,
    execution_note: str | None,
    rule_summary: str | None,
) -> str:
    tone = profile.effective_tone if profile is not None else "friendly"
    verbosity = profile.effective_verbosity if profile is not None else "medium"
    expertise_mode = (
        profile.effective_expertise_mode if profile is not None else "beginner"
    )
    tested_sentence = (
        f"This applies to {tested_summary}."
        if tested_summary is not None
        else "This applies to the confirmed strategy."
    )
    expertise_sentence = _expertise_sentence(expertise_mode)
    base = (
        "The result payload is incomplete, so I cannot report observed returns yet. "
        f"{tested_sentence} {expertise_sentence}"
    )
    execution_sentence = f" {execution_note}" if execution_note else ""
    if verbosity == "high":
        if tone == "friendly":
            return f"Here is the current status. {base}{execution_sentence} Assumptions and caveats: {assumption_summary} {caveat}"
        return f"{base}{execution_sentence} Assumptions and caveats: {assumption_summary} {caveat}"
    if verbosity == "low":
        return f"{base}{execution_sentence} Caveat: {assumption_summary} {caveat}"
    if tone == "concise":
        return f"{base}{execution_sentence} Caveat: {assumption_summary} {caveat}"
    return f"{base}{execution_sentence} Assumptions and caveat: {assumption_summary} {caveat}"


def _compact_sentence_list(values: list[Any], *, limit: int) -> str:
    sentences: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        text = " ".join(text.split())
        if len(text) > 140:
            text = text[:137].rstrip() + "..."
        if not text.endswith((".", "!", "?")):
            text += "."
        sentences.append(text)
        if len(sentences) >= limit:
            break
    return " ".join(sentences)


def _percent(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value) * 100
    except (TypeError, ValueError):
        return None


def _resolved_return_metrics(
    *,
    result_payload: dict[str, Any],
    explanation_context: dict[str, Any],
) -> tuple[float | None, float | None, bool]:
    metrics = explanation_context.get("metrics", {})
    benchmark_metrics = explanation_context.get("benchmark_metrics", {})
    total_return_pct = _nested_number(
        metrics,
        ("aggregate", "performance", "total_return_pct"),
    )
    if total_return_pct is None:
        total_return_pct = _nested_number(metrics, ("total_return_pct",))

    benchmark_return_pct = _nested_number(
        benchmark_metrics,
        ("aggregate", "total_return_pct"),
    )
    if benchmark_return_pct is None:
        benchmark_return_pct = _nested_number(
            benchmark_metrics,
            ("benchmark_return_pct",),
        )

    if total_return_pct is not None and benchmark_return_pct is not None:
        same_period = bool(
            explanation_context.get("comparable_same_period")
            or result_payload.get("comparable_same_period")
        )
        return total_return_pct, benchmark_return_pct, same_period

    return (
        _percent(result_payload.get("total_return")),
        _percent(result_payload.get("benchmark_return")),
        bool(result_payload.get("comparable_same_period")),
    )


def _nested_number(payload: Any, path: tuple[str, ...]) -> float | None:
    current = payload
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    try:
        if current is None or current == "":
            return None
        return float(current)
    except (TypeError, ValueError):
        return None
