from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from argus.agent_runtime.next_experiments import next_experiments_sidecar
from argus.agent_runtime.presentation_i18n import optional_parameter_display_label
from argus.agent_runtime.response_language import response_language_instruction
from argus.agent_runtime.response_style import ARGUS_RESPONSE_STYLE_CONTRACT
from argus.agent_runtime.stages.interpret import StageResult
from argus.agent_runtime.state.models import (
    ConfirmationPayload,
    FinalResponsePayload,
    ResponseProfile,
    RunState,
)
from argus.agent_runtime.strategy_contract import display_strategy_type
from argus.domain.benchmark_comparison import (
    benchmark_comparison_from_delta,
)
from argus.domain.engine_launch.display import (
    format_date_range_label,
    normalize_legacy_data_caveat,
)
from argus.domain.engine_launch.result_facts import (
    execution_note as result_execution_note,
)
from argus.domain.engine_launch.result_facts import (
    resolved_rule_summary as result_rule_summary,
)
from argus.domain.result_readout_content import normalize_readout_language
from argus.domain.result_readout_grounding import (
    READOUT_GROUNDING_INSTRUCTIONS,
    ResultReadoutDraft,
    accepted_readout_text,
    stored_readout_facts,
)
from argus.llm.openrouter import invoke_openrouter_json_schema

RESULT_READOUT_SOURCE_LLM = "llm_explain_stage"
RESULT_READOUT_SOURCE_DETERMINISTIC_FALLBACK = "deterministic_fallback"
RESULT_READOUT_FAILURE_LLM_UNAVAILABLE = "llm_unavailable_or_rejected"


@dataclass(frozen=True)
class _LLMExplanationResult:
    text: str | None
    failure_mode: str | None = None


class QuickTakeDraft(ResultReadoutDraft):
    """Complete first-glance model prose; the UI owns its frame."""


def explain_stage(*, state: RunState, language: str = "en") -> StageResult:
    result_payload = _result_payload(state)
    explanation_context = _explanation_context(state)
    profile = _response_profile(state)
    strategy = _strategy_payload(state)
    optional_parameters = _optional_parameters(state)
    tested_summary = _tested_summary(
        strategy=strategy,
        result_payload=result_payload,
        explanation_context=explanation_context,
        language=language,
    )
    assumption_summary = _assumption_summary(
        optional_parameters=optional_parameters,
        explanation_context=explanation_context,
        language=language,
    )
    caveat = _caveat_summary(explanation_context, language=language)
    result_facts = _result_facts_for_explanation(
        strategy=strategy,
        result_payload=result_payload,
        explanation_context=explanation_context,
    )
    execution_note = result_execution_note(result_facts)
    rule_summary = _display_rule_summary(
        strategy=strategy,
        result_facts=result_facts,
        rule_summary=result_rule_summary(result_facts),
    )

    returns = _resolved_return_metrics(
        result_payload=result_payload,
        explanation_context=explanation_context,
    )
    if returns.total_return is None or returns.benchmark_return is None:
        response = _build_incomplete_result_response(
            profile=profile,
            tested_summary=tested_summary,
            assumption_summary=assumption_summary,
            caveat=caveat,
            execution_note=execution_note,
            rule_summary=rule_summary,
        )
        return StageResult(
            outcome="ready_to_respond",
            stage_patch=_with_next_experiments(
                {"assistant_response": response},
                result_facts=result_facts,
                recent_user_messages=_recent_user_messages(state),
                previously_offered_kinds=state.prior_next_experiment_kinds,
                language=language,
            ),
        )
    benchmark_symbol = _benchmark_contract(
        strategy=strategy,
        result_payload=result_payload,
        explanation_context=explanation_context,
    ).get("benchmark_symbol")
    response = _build_response(
        total_return=returns.total_return,
        benchmark_return=returns.benchmark_return,
        benchmark_delta=returns.benchmark_delta,
        benchmark_symbol=str(benchmark_symbol or ""),
        same_period=returns.same_period,
        profile=profile,
        tested_summary=tested_summary,
        assumption_summary=assumption_summary,
        caveat=caveat,
        execution_note=execution_note,
        rule_summary=rule_summary,
    )

    return StageResult(
        outcome="ready_to_respond",
        stage_patch=_with_next_experiments(
            {"assistant_response": response},
            result_facts=result_facts,
            benchmark_delta=returns.benchmark_delta,
            max_drawdown=_max_drawdown_metric(result_payload),
            recent_user_messages=_recent_user_messages(state),
            previously_offered_kinds=state.prior_next_experiment_kinds,
            language=language,
        ),
    )


def _with_next_experiments(
    patch: dict[str, Any],
    *,
    result_facts: dict[str, Any],
    benchmark_delta: float | None = None,
    max_drawdown: float | None = None,
    recent_user_messages: list[str] | None = None,
    previously_offered_kinds: list[str] | None = None,
    language: str = "en",
) -> dict[str, Any]:
    sidecar = next_experiments_sidecar(
        result_facts,
        benchmark_delta=benchmark_delta,
        max_drawdown=max_drawdown,
        recent_user_messages=recent_user_messages,
        previously_offered_kinds=previously_offered_kinds,
        language=language,
    )
    if sidecar is None:
        return patch
    return {**patch, "next_experiments": sidecar}


def _recent_user_messages(state: RunState) -> list[str]:
    turns = [
        message.content
        for message in state.recent_thread_history
        if message.role == "user"
    ]
    turns.append(state.current_user_message)
    return turns[-8:]


def _max_drawdown_metric(result_payload: dict[str, Any]) -> float | None:
    metrics = result_payload.get("metrics")
    if not isinstance(metrics, dict):
        return None
    # Canonical engine shape first; flat keys are the legacy fallback.
    nested: Any = metrics
    for key in ("aggregate", "performance"):
        nested = nested.get(key) if isinstance(nested, dict) else None
    if isinstance(nested, dict):
        value = nested.get("max_drawdown_pct")
        if isinstance(value, (int, float)):
            return float(value)
    for key in ("max_drawdown_pct", "max_drawdown"):
        value = metrics.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


async def explain_stage_async(*, state: RunState, language: str = "en") -> StageResult:
    fallback = explain_stage(state=state, language=language)
    fallback_text = fallback.stage_patch.get("assistant_response")
    if not isinstance(fallback_text, str) or not fallback_text:
        return _with_response_source(
            fallback,
            source=RESULT_READOUT_SOURCE_DETERMINISTIC_FALLBACK,
            fallback_used=True,
            failure_mode=RESULT_READOUT_FAILURE_LLM_UNAVAILABLE,
        )

    llm_result = await _llm_explanation(
        state=state,
        fallback_text=fallback_text,
        language=language,
    )
    if llm_result.text is None:
        return _with_response_source(
            fallback,
            source=RESULT_READOUT_SOURCE_DETERMINISTIC_FALLBACK,
            fallback_used=True,
            failure_mode=llm_result.failure_mode
            or RESULT_READOUT_FAILURE_LLM_UNAVAILABLE,
        )
    return StageResult(
        outcome=fallback.outcome,
        stage_patch={
            **fallback.stage_patch,
            "assistant_response": llm_result.text,
            "assistant_response_source": RESULT_READOUT_SOURCE_LLM,
            "assistant_response_fallback_used": False,
        },
    )


def _with_response_source(
    result: StageResult,
    *,
    source: str,
    fallback_used: bool,
    failure_mode: str | None = None,
) -> StageResult:
    patch = {
        **result.stage_patch,
        "assistant_response_source": source,
        "assistant_response_fallback_used": fallback_used,
    }
    if failure_mode:
        patch["assistant_response_failure_mode"] = failure_mode
    return StageResult(
        outcome=result.outcome,
        decision=result.decision,
        stage_patch=patch,
    )


async def _llm_explanation(
    *,
    state: RunState,
    fallback_text: str,
    language: str,
) -> _LLMExplanationResult:
    del fallback_text
    normalized_language = normalize_readout_language(language)
    if normalized_language is None:
        return _LLMExplanationResult(text=None, failure_mode="language_mismatch")
    language = normalized_language
    strategy = _strategy_payload(state)
    result_payload = _result_payload(state)
    explanation_context = _explanation_context(state)
    result_facts = _result_facts_for_explanation(
        strategy=strategy,
        result_payload=result_payload,
        explanation_context=explanation_context,
    )
    returns = _resolved_return_metrics(
        result_payload=result_payload,
        explanation_context=explanation_context,
    )
    benchmark = _benchmark_contract(
        strategy=strategy,
        result_payload=result_payload,
        explanation_context=explanation_context,
    )
    result_card = explanation_context.get("result_card")
    chart = (
        result_card.get("chart")
        if isinstance(result_card, dict)
        else result_payload.get("chart")
    )
    facts = stored_readout_facts(
        metrics=result_facts.get("metrics"),
        config_snapshot=result_payload.get(
            "config_snapshot",
            {
                "resolved_strategy": _canonical_strategy_context(strategy),
                "resolved_parameters": result_facts.get("resolved_parameters", {}),
            },
        ),
        symbols=benchmark["tested_symbols"],
        benchmark_symbol=benchmark["benchmark_symbol"],
        date_range=result_payload.get("date_range", strategy.get("date_range")),
        chart=chart,
        comparison_metrics={
            "total_return_pct": returns.total_return,
            "benchmark_return_pct": returns.benchmark_return,
            "delta_vs_benchmark_pct": returns.benchmark_delta,
        },
    )
    messages = [
        {
            "role": "system",
            "content": (
                f"{ARGUS_RESPONSE_STYLE_CONTRACT}\n\n"
                "Write what belongs inside the Quick take frame of a completed "
                "historical backtest. Keep it short and first-glance: explain the "
                "most meaningful result and tradeoff for a person, rather than "
                "reciting the card. Save the deeper discussion for Breakdown. "
                "Do not add a heading or next experiments; the existing UI owns "
                "the frame and follow-up actions. "
                f"{response_language_instruction(language)} "
                f"{READOUT_GROUNDING_INSTRUCTIONS}"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {"run_facts": facts, "product_language": language},
                default=str,
            ),
        },
    ]
    try:
        draft = await invoke_openrouter_json_schema(
            task="result_summary",
            messages=messages,
            schema_model=QuickTakeDraft,
            schema_name="QuickTakeDraft",
            context_packet_ids=_context_packet_ids_from_explanation_context(
                explanation_context
            ),
        )
        rendered, failure = accepted_readout_text(draft, facts=facts, language=language)
        return _LLMExplanationResult(text=rendered, failure_mode=failure)
    except Exception:
        # OpenRouter owns per-model route receipts. No partial draft is exposed.
        return _LLMExplanationResult(
            text=None,
            failure_mode=RESULT_READOUT_FAILURE_LLM_UNAVAILABLE,
        )


def _context_packet_ids_from_explanation_context(
    explanation_context: dict[str, Any],
) -> list[str]:
    result_card = explanation_context.get("result_card")
    candidates: list[Any] = [explanation_context.get("context_packet_ids")]
    if isinstance(result_card, dict):
        candidates.append(result_card.get("context_packet_ids"))
    packet_ids: list[str] = []
    for candidate in candidates:
        values = candidate if isinstance(candidate, list) else [candidate]
        for value in values:
            packet_id = str(value or "").strip()
            if packet_id and packet_id not in packet_ids:
                packet_ids.append(packet_id)
    return packet_ids


def _benchmark_contract(
    *,
    strategy: dict[str, Any],
    result_payload: dict[str, Any],
    explanation_context: dict[str, Any],
) -> dict[str, Any]:
    tested_symbols = _symbol_list(strategy.get("asset_universe"))
    benchmark_symbol = _first_symbol(
        explanation_context.get("benchmark_symbol"),
        result_payload.get("benchmark_symbol"),
        _nested_dict_value(explanation_context, ("result_card", "benchmark_symbol")),
        _nested_dict_value(explanation_context, ("benchmark_metrics", "symbol")),
        _nested_dict_value(
            explanation_context,
            ("benchmark_metrics", "benchmark_symbol"),
        ),
        _nested_dict_value(explanation_context, ("config_snapshot", "benchmark_symbol")),
        _nested_dict_value(result_payload, ("benchmark_metrics", "symbol")),
        _nested_dict_value(result_payload, ("benchmark_metrics", "benchmark_symbol")),
    )
    tested_symbol_set = set(tested_symbols)
    return {
        "benchmark_symbol": benchmark_symbol,
        "tested_symbols": tested_symbols,
        "benchmark_is_tested_asset": bool(
            benchmark_symbol and benchmark_symbol in tested_symbol_set
        ),
    }


def _symbol_list(value: Any) -> list[str]:
    values = value if isinstance(value, list) else [value]
    symbols: list[str] = []
    for item in values:
        symbol = _clean_symbol(item)
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    return symbols


def _first_symbol(*values: Any) -> str:
    for value in values:
        symbol = _clean_symbol(value)
        if symbol:
            return symbol
    return ""


def _clean_symbol(value: Any) -> str:
    symbol = str(value or "").strip().upper()
    return symbol


def _nested_dict_value(payload: Any, path: tuple[str, ...]) -> Any:
    current = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


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


def _display_rule_summary(
    *,
    strategy: dict[str, Any],
    result_facts: dict[str, Any],
    rule_summary: str | None,
) -> str | None:
    strategy_type = str(
        strategy.get("strategy_type")
        or _dict_value(result_facts.get("resolved_strategy"), "strategy_type")
        or result_facts.get("strategy_type")
        or ""
    ).strip()
    resolved_parameters = (
        result_facts.get("resolved_parameters")
        if isinstance(result_facts.get("resolved_parameters"), dict)
        else {}
    )
    if strategy_type == "buy_and_hold":
        return "Rule: buy at the start of the period and hold through the end."
    if strategy_type == "dca_accumulation":
        cadence = _cadence_display_label(
            strategy.get("cadence") or resolved_parameters.get("cadence"),
        )
        cadence_phrase = f" on a {cadence} cadence" if cadence else ""
        return f"Rule: buy recurring contributions{cadence_phrase} and hold."
    if strategy_type == "indicator_threshold":
        indicator = str(
            resolved_parameters.get("indicator") or strategy.get("indicator") or ""
        ).strip()
        entry_threshold = resolved_parameters.get("entry_threshold")
        exit_threshold = resolved_parameters.get("exit_threshold")
        if indicator and entry_threshold is not None and exit_threshold is not None:
            label = indicator.upper()
            return (
                f"Rule: buy when {label} is at or below {entry_threshold}; "
                f"sell when it is at or above {exit_threshold}."
            )
    return rule_summary


def _dict_value(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return None


def _cadence_display_label(value: Any) -> str:
    cadence = str(value or "").strip().lower().replace("-", "_")
    if not cadence:
        return ""
    return cadence.replace("_", " ")


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
    language: str,
) -> str | None:
    assets = _asset_summary(strategy)
    strategy_label = _strategy_label(
        strategy.get("strategy_type") or explanation_context.get("strategy_type"),
    )
    period = _period_summary(
        strategy.get("date_range")
        or explanation_context.get("date_range")
        or result_payload.get("date_range"),
        language=language,
    )
    if assets and strategy_label and period:
        return f"{assets} {strategy_label} over {period}"
    if assets and strategy_label:
        return f"{assets} {strategy_label}"
    if assets and period:
        return f"{assets} over {period}"
    thesis = _thesis(strategy)
    if not thesis:
        return None
    return f"the confirmed strategy: {thesis}"


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
    return display_strategy_type({"strategy_type": value.strip()}).lower()


def _period_summary(value: Any, *, language: str) -> str | None:
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
            return format_date_range_label(start, end, language=language)
    return None


def _assumption_summary(
    *,
    optional_parameters: dict[str, Any],
    explanation_context: dict[str, Any],
    language: str,
) -> str:
    defaulted_labels: list[str] = []
    user_labels: list[str] = []
    assumptions = explanation_context.get("assumptions", [])

    for field_name, value in optional_parameters.items():
        if not isinstance(value, dict):
            continue
        label = optional_parameter_display_label(
            field_name,
            value.get("label"),
            language=language,
        )
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


def _caveat_summary(explanation_context: dict[str, Any], *, language: str) -> str:
    default = "This is a return comparison, not causal attribution."
    caveats = explanation_context.get("caveats", [])
    if not isinstance(caveats, list) or not caveats:
        return default
    caveat_text = _compact_sentence_list(
        [normalize_legacy_data_caveat(value, language=language) for value in caveats],
        limit=2,
    )
    if not caveat_text:
        return default
    return f"{default} {caveat_text}"


def _build_response(
    *,
    total_return: float,
    benchmark_return: float,
    benchmark_delta: float | None,
    benchmark_symbol: str,
    same_period: bool,
    profile: ResponseProfile | None,
    tested_summary: str | None,
    assumption_summary: str,
    caveat: str,
    execution_note: str | None,
    rule_summary: str | None,
    next_check_override: str | None = None,
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
            benchmark_delta=benchmark_delta,
            benchmark_symbol=benchmark_symbol,
            same_period=same_period,
            tested_summary=tested_summary,
            interpretation=expertise_sentence,
            assumption_summary=assumption_summary,
            caveat=caveat,
            execution_note=execution_note,
            rule_summary=rule_summary,
            next_check_override=next_check_override,
            compact=True,
        )

    return _result_readout_markdown(
        total_return=total_return,
        benchmark_return=benchmark_return,
        benchmark_delta=benchmark_delta,
        benchmark_symbol=benchmark_symbol,
        same_period=same_period,
        tested_summary=tested_summary,
        interpretation=expertise_sentence,
        assumption_summary=assumption_summary,
        caveat=caveat,
        execution_note=execution_note,
        rule_summary=rule_summary,
        next_check_override=next_check_override,
        compact=tone == "concise" and verbosity != "high",
    )


def _result_readout_markdown(
    *,
    total_return: float,
    benchmark_return: float,
    benchmark_delta: float | None,
    benchmark_symbol: str,
    same_period: bool,
    tested_summary: str | None,
    interpretation: str,
    assumption_summary: str,
    caveat: str,
    execution_note: str | None,
    rule_summary: str | None,
    next_check_override: str | None,
    compact: bool,
) -> str:
    takeaway = _readout_takeaway(
        total_return=total_return,
        benchmark_return=benchmark_return,
        benchmark_symbol=benchmark_symbol,
        same_period=same_period,
        delta=benchmark_delta,
        execution_note=execution_note,
    )
    tested = _tested_readout_line(
        tested_summary,
        rule_summary,
    )
    lines = [
        takeaway,
        "",
        f"- Tested: {tested}.",
    ]
    if execution_note:
        lines.append(f"- Signal: {_compact_execution_note(execution_note)}")
    else:
        lines.append(f"- What that means: {interpretation}")
    next_check = next_check_override or _next_check_line(
        execution_note=execution_note,
    )
    if next_check:
        lines.append(f"- Next check: {next_check}")
    if assumption_summary:
        lines.append(f"- Assumptions: {_strip_leading_label(assumption_summary)}")
    lines.append(f"- Keep in mind: {caveat}")
    return "\n".join(lines)


def _readout_takeaway(
    *,
    total_return: float,
    benchmark_return: float,
    benchmark_symbol: str,
    same_period: bool,
    delta: float | None,
    execution_note: str | None,
) -> str:
    benchmark_context = _benchmark_context_phrase(same_period)
    benchmark_label = benchmark_symbol or "the benchmark"
    relative = _relative_performance_sentence(delta)
    if execution_note and abs(total_return) < 0.05:
        return (
            "No trade opened. The strategy stayed in cash because its entry "
            f"condition never fired; it returned {total_return:.1f}% while the "
            f"{benchmark_label} returned {benchmark_return:.1f}% {benchmark_context}"
            + (f"; it {relative}" if relative else ".")
        )
    return (
        f"The strategy returned {total_return:.1f}% while {benchmark_label} returned "
        f"{benchmark_return:.1f}% {benchmark_context}"
        + (f", so it {relative}" if relative else ".")
    )


def _relative_performance_sentence(delta: float | None) -> str | None:
    # The domain comparison owns both the in-line cut and the printed magnitude.
    comparison = benchmark_comparison_from_delta(delta)
    if comparison.claim == "unknown":
        return None
    if comparison.claim == "matched_benchmark":
        return "was effectively in line with the benchmark."
    direction = "outperformed" if comparison.claim == "beat_benchmark" else "lagged"
    return f"{direction} by {comparison.magnitude_points}."


def _tested_readout_line(
    tested_summary: str | None,
    rule_summary: str | None,
) -> str:
    fallback = "the confirmed strategy"
    tested = (tested_summary or fallback).strip().rstrip(".")
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
            "Loosen the entry threshold or widen the window before judging the " "idea."
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


@dataclass(frozen=True)
class _ReturnMetrics:
    total_return: float | None
    benchmark_return: float | None
    benchmark_delta: float | None
    same_period: bool


def _resolved_return_metrics(
    *,
    result_payload: dict[str, Any],
    explanation_context: dict[str, Any],
) -> _ReturnMetrics:
    """The only reader of result payload shapes; every comparison derives from it."""
    metrics = explanation_context.get("metrics", {})
    benchmark_metrics = explanation_context.get("benchmark_metrics", {})
    engine_performance = _nested_dict(metrics, ("aggregate", "performance"))
    total_return_pct = _nested_number(engine_performance, ("total_return_pct",))
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
        return _ReturnMetrics(
            total_return=total_return_pct,
            benchmark_return=benchmark_return_pct,
            benchmark_delta=_benchmark_delta(
                engine_performance,
                total_return_pct=total_return_pct,
                benchmark_return_pct=benchmark_return_pct,
            ),
            same_period=same_period,
        )

    total_return = _percent(result_payload.get("total_return"))
    benchmark_return = _percent(result_payload.get("benchmark_return"))
    return _ReturnMetrics(
        total_return=total_return,
        benchmark_return=benchmark_return,
        benchmark_delta=_return_difference(total_return, benchmark_return),
        same_period=bool(result_payload.get("comparable_same_period")),
    )


def _benchmark_delta(
    engine_performance: dict[str, Any] | None,
    *,
    total_return_pct: float,
    benchmark_return_pct: float,
) -> float | None:
    # The engine publishes delta_vs_benchmark_pct beside the two returns it
    # rounded; subtracting those again can land a tenth away from it (#533).
    # Only payload shapes without an engine block leave subtraction as the
    # sole comparison available.
    if engine_performance is not None:
        return _nested_number(engine_performance, ("delta_vs_benchmark_pct",))
    return _return_difference(total_return_pct, benchmark_return_pct)


def _return_difference(
    total_return: float | None,
    benchmark_return: float | None,
) -> float | None:
    if total_return is None or benchmark_return is None:
        return None
    return total_return - benchmark_return


def _nested_dict(payload: Any, path: tuple[str, ...]) -> dict[str, Any] | None:
    current = payload
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current if isinstance(current, dict) else None


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
