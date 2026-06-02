from __future__ import annotations

import json
from typing import Any, Literal

from argus.agent_runtime.response_style import (
    ARGUS_RESPONSE_STYLE_CONTRACT,
    with_response_heading,
)
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
from argus.domain.engine_launch.result_facts import (
    execution_note as result_execution_note,
)
from argus.domain.engine_launch.result_facts import (
    resolved_rule_summary as result_rule_summary,
)
from argus.domain.engine_launch.result_facts import structured_next_experiments
from argus.llm.openrouter import invoke_openrouter_json_schema
from pydantic import BaseModel, ConfigDict, Field, ValidationError

QuickTakeRelativeClaim = Literal[
    "beat_benchmark",
    "lagged_benchmark",
    "matched_benchmark",
    "unknown",
]
QuickTakeEmphasis = Literal[
    "comparison",
    "risk",
    "rule",
    "no_trade",
    "neutral",
]


class QuickTakeDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relative_performance_claim: QuickTakeRelativeClaim = Field(
        description=(
            "Structured claim about the strategy versus the benchmark. Use only "
            "the supplied benchmark comparison truth."
        )
    )
    takeaway: str = Field(
        description=(
            "One concise user-visible sentence interpreting the important result "
            "from supplied fact_bank facts only."
        )
    )
    tested_bullet: str = Field(
        description="Compact user-visible tested/setup bullet grounded in fact_bank."
    )
    meaning_bullet: str | None = Field(
        default=None,
        description=(
            "Optional user-visible interpretation bullet. Use facts only; do not "
            "invent causes or recommendations."
        ),
    )
    next_check_bullet: str | None = Field(
        default=None,
        description=(
            "Optional user-visible next-check bullet. It must correspond to an "
            "allowed_next_experiments kind when one is supplied."
        ),
    )
    assumption_bullet: str | None = Field(
        default=None,
        description="Optional compact assumption bullet grounded in fact_bank.",
    )
    caveat_bullet: str | None = Field(
        default=None,
        description="Optional compact caveat bullet grounded in fact_bank.",
    )
    next_experiment_option_kinds: list[str] = Field(
        default_factory=list,
        description=(
            "Optional supported next experiment kinds copied exactly from "
            "allowed_next_experiments. Do not invent kinds."
        ),
    )
    fact_ids: list[str] = Field(
        description=(
            "Fact IDs from fact_bank that ground this draft. Include every "
            "required_fact_id and do not invent IDs."
        )
    )


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
            stage_patch={
                "assistant_response": with_response_heading(
                    heading="Quick take",
                    body=response,
                )
            },
        )
    benchmark_symbol = _benchmark_contract(
        strategy=strategy,
        result_payload=result_payload,
        explanation_context=explanation_context,
    ).get("benchmark_symbol")
    response = _build_response(
        total_return=total_return,
        benchmark_return=benchmark_return,
        benchmark_symbol=str(benchmark_symbol or ""),
        same_period=same_period,
        profile=profile,
        tested_summary=tested_summary,
        assumption_summary=assumption_summary,
        caveat=caveat,
        execution_note=execution_note,
        rule_summary=rule_summary,
    )

    return StageResult(
        outcome="ready_to_respond",
        stage_patch={
            "assistant_response": with_response_heading(
                heading="Quick take",
                body=response,
            )
        },
    )


async def explain_stage_async(*, state: RunState) -> StageResult:
    fallback = explain_stage(state=state)
    fallback_text = fallback.stage_patch.get("assistant_response")
    if not isinstance(fallback_text, str) or not fallback_text:
        return fallback

    llm_text = await _llm_explanation(
        state=state,
        fallback_text=fallback_text,
    )
    if llm_text is None:
        return fallback
    return StageResult(
        outcome=fallback.outcome,
        stage_patch={
            **fallback.stage_patch,
            "assistant_response": with_response_heading(
                heading="Quick take",
                body=llm_text,
            ),
        },
    )


async def _llm_explanation(
    *,
    state: RunState,
    fallback_text: str,
) -> str | None:
    strategy = _strategy_payload(state)
    result_payload = _result_payload(state)
    explanation_context = _explanation_context(state)
    result_facts = _result_facts_for_explanation(
        strategy=strategy,
        result_payload=result_payload,
        explanation_context=explanation_context,
    )
    optional_parameters = _optional_parameters(state)
    tested_summary = _tested_summary(
        strategy=strategy,
        result_payload=result_payload,
        explanation_context=explanation_context,
    )
    execution_note = result_execution_note(result_facts)
    rule_summary = result_rule_summary(result_facts)
    assumption_summary = _assumption_summary(
        optional_parameters=optional_parameters,
        explanation_context=explanation_context,
    )
    caveat = _caveat_summary(explanation_context)
    allowed_next_experiments = structured_next_experiments(result_facts)
    benchmark_contract = _benchmark_contract(
        strategy=strategy,
        result_payload=result_payload,
        explanation_context=explanation_context,
    )
    fact_context = {
        "tested_summary": tested_summary,
        "execution_note": execution_note,
        "rule_summary": rule_summary,
        "assumption_summary": assumption_summary,
        "caveat": caveat,
        "benchmark_contract": benchmark_contract,
    }
    fact_bank = _quick_take_fact_bank(
        context=fact_context,
        result_payload=result_payload,
        explanation_context=explanation_context,
    )
    relative_performance_truth = _quick_take_relative_truth(
        result_payload=result_payload,
        explanation_context=explanation_context,
    )
    required_fact_ids = _required_quick_take_fact_ids(fact_bank)
    prompt_context = {
        "allowed_next_experiments": allowed_next_experiments,
        "benchmark_contract": benchmark_contract,
        "fact_bank": fact_bank,
        "language": "use the user's current language preference if available",
        "relative_performance_truth": relative_performance_truth,
        "required_fact_ids": sorted(required_fact_ids),
        "strategy": _canonical_strategy_context(strategy),
    }
    messages = [
        {
            "role": "system",
            "content": (
                f"{ARGUS_RESPONSE_STYLE_CONTRACT}\n\n"
                "You are writing a concise Quick Take for a completed historical "
                "backtest. Compose natural user-facing wording, but use only "
                "supplied fact_bank facts for metrics, symbols, dates, assumptions, "
                "and next-test labels. The result card answers what happened; your "
                "job is to explain what matters without duplicating every metric. "
                "Benchmark returns belong only to benchmark_contract.benchmark_symbol. "
                "Return structured fields so the runtime can validate fact usage; "
                "do not invent facts or supported next experiment kinds."
                " For user-facing beat/lagged wording, use benchmark_comparison "
                "or benchmark_delta_magnitude; do not phrase a lag as a negative "
                "percentage return. When using benchmark_comparison, include that "
                "fact phrase exactly."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                prompt_context,
                default=str,
                sort_keys=True,
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
        return _render_quick_take_draft(
            draft=draft,
            fallback_text=fallback_text,
            fact_bank=fact_bank,
            required_fact_ids=required_fact_ids,
            allowed_next_experiments=allowed_next_experiments,
            relative_performance_truth=relative_performance_truth,
        )
    except Exception as exc:
        # The OpenRouter helper records per-model route receipts. This local fallback
        # only preserves a recoverable answer when every configured model fails.
        _ = exc
        return None


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


def _quick_take_fact_bank(
    *,
    context: dict[str, Any],
    result_payload: dict[str, Any],
    explanation_context: dict[str, Any],
) -> dict[str, str]:
    fact_bank: dict[str, str] = {}
    for key in (
        "tested_summary",
        "execution_note",
        "rule_summary",
        "assumption_summary",
        "caveat",
    ):
        value = context.get(key)
        if isinstance(value, str) and value.strip():
            fact_bank[key] = value.strip()

    benchmark_contract = context.get("benchmark_contract")
    benchmark_symbol = (
        benchmark_contract.get("benchmark_symbol")
        if isinstance(benchmark_contract, dict)
        else None
    )
    if not benchmark_symbol:
        benchmark_symbol = _benchmark_contract(
            strategy={},
            result_payload=result_payload,
            explanation_context=explanation_context,
        ).get("benchmark_symbol")
    if benchmark_symbol:
        fact_bank["benchmark_symbol"] = str(benchmark_symbol)

    total_return, benchmark_return, _ = _resolved_return_metrics(
        result_payload=result_payload,
        explanation_context=explanation_context,
    )
    if total_return is not None:
        fact_bank["total_return"] = _format_percent_points(total_return)
    if benchmark_return is not None:
        fact_bank["benchmark_return"] = _format_percent_points(benchmark_return)
    if total_return is not None and benchmark_return is not None:
        comparison = benchmark_comparison_from_delta(total_return - benchmark_return)
        fact_bank["benchmark_delta_magnitude"] = comparison.magnitude_points
        fact_bank["benchmark_comparison"] = comparison.user_phrase
    fact_bank["caveat"] = fact_bank.get(
        "caveat",
        "Historical simulation evidence, not a prediction or trading recommendation",
    )
    return fact_bank


def _required_quick_take_fact_ids(fact_bank: dict[str, str]) -> set[str]:
    required = {"caveat"}
    for fact_id in (
        "tested_summary",
        "total_return",
        "benchmark_return",
        "benchmark_symbol",
    ):
        if fact_id in fact_bank:
            required.add(fact_id)
    if "benchmark_comparison" in fact_bank:
        required.add("benchmark_comparison")
    return required


def _quick_take_relative_truth(
    *,
    result_payload: dict[str, Any],
    explanation_context: dict[str, Any],
) -> QuickTakeRelativeClaim:
    total_return, benchmark_return, _ = _resolved_return_metrics(
        result_payload=result_payload,
        explanation_context=explanation_context,
    )
    if total_return is None or benchmark_return is None:
        return "unknown"
    delta = total_return - benchmark_return
    return benchmark_comparison_from_delta(delta).claim


def _format_percent_points(value: float) -> str:
    prefix = "+" if value > 0 else ""
    return f"{prefix}{value:.1f}%"


def _render_quick_take_draft(
    *,
    draft: QuickTakeDraft | dict[str, Any] | None,
    fallback_text: str,
    fact_bank: dict[str, str],
    required_fact_ids: set[str],
    allowed_next_experiments: Any,
    relative_performance_truth: QuickTakeRelativeClaim,
) -> str | None:
    response = _coerce_quick_take_draft(draft)
    if response is None:
        return None
    truth = relative_performance_truth
    if truth != "unknown" and response.relative_performance_claim != truth:
        return None
    used_fact_ids: set[str] = set()
    for fact_id_value in response.fact_ids:
        fact_id = str(fact_id_value or "").strip()
        if fact_id not in fact_bank:
            return None
        used_fact_ids.add(fact_id)
    if not required_fact_ids.issubset(used_fact_ids):
        return None
    if not _quick_take_mentions_required_visible_facts(
        draft=response,
        fact_bank=fact_bank,
    ):
        return None
    if not _next_check_kinds_are_supported(
        draft=response,
        allowed_next_experiments=allowed_next_experiments,
    ):
        return None

    lines = [_clean_quick_take_line(response.takeaway), ""]
    for bullet in (
        response.tested_bullet,
        response.meaning_bullet,
        response.next_check_bullet,
        response.assumption_bullet,
        response.caveat_bullet,
    ):
        line = _clean_quick_take_line(bullet)
        if line:
            lines.append(f"- {line}")
    body = "\n".join(line for line in lines if line is not None).strip()
    return body or fallback_text


def _coerce_quick_take_draft(value: Any) -> QuickTakeDraft | None:
    if isinstance(value, QuickTakeDraft):
        return value
    try:
        return QuickTakeDraft.model_validate(value)
    except (TypeError, ValidationError):
        return None


def _quick_take_mentions_required_visible_facts(
    *,
    draft: QuickTakeDraft,
    fact_bank: dict[str, str],
) -> bool:
    text = " ".join(
        line
        for line in (
            draft.takeaway,
            draft.tested_bullet,
            draft.meaning_bullet or "",
            draft.next_check_bullet or "",
            draft.assumption_bullet or "",
            draft.caveat_bullet or "",
        )
        if line
    )
    benchmark_symbol = fact_bank.get("benchmark_symbol")
    if benchmark_symbol and benchmark_symbol not in text:
        return False
    benchmark_comparison = fact_bank.get("benchmark_comparison")
    if benchmark_comparison and benchmark_comparison not in text:
        return False
    return True


def _next_check_kinds_are_supported(
    *,
    draft: QuickTakeDraft,
    allowed_next_experiments: Any,
) -> bool:
    if not isinstance(allowed_next_experiments, list):
        return not draft.next_experiment_option_kinds
    by_kind = {
        str(option.get("kind") or "")
        for option in allowed_next_experiments
        if isinstance(option, dict)
    }
    return all(
        str(kind_value or "").strip() in by_kind
        for kind_value in draft.next_experiment_option_kinds
    )


def _clean_quick_take_line(value: str | None) -> str:
    text = " ".join(str(value or "").split()).strip()
    return text.strip("- ").rstrip(".")


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
    return display_strategy_type({"strategy_type": value.strip()}).lower()


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
    delta = total_return - benchmark_return
    takeaway = _readout_takeaway(
        total_return=total_return,
        benchmark_return=benchmark_return,
        benchmark_symbol=benchmark_symbol,
        same_period=same_period,
        delta=delta,
        execution_note=execution_note,
    )
    tested = _tested_readout_line(tested_summary, rule_summary)
    lines = [
        takeaway,
        "",
        f"- Tested: {tested}.",
    ]
    if execution_note:
        lines.append(f"- Signal: {_compact_execution_note(execution_note)}")
    else:
        lines.append(f"- What that means: {interpretation}")
    next_check = next_check_override or _next_check_line(execution_note=execution_note)
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
    delta: float,
    execution_note: str | None,
) -> str:
    benchmark_context = _benchmark_context_phrase(same_period)
    benchmark_label = benchmark_symbol or "the benchmark"
    relative = _relative_performance_sentence(delta)
    if execution_note and abs(total_return) < 0.05:
        return (
            "No trade opened. The strategy stayed in cash because its entry "
            f"condition never fired; it returned {total_return:.1f}% while the "
            f"{benchmark_label} returned {benchmark_return:.1f}% {benchmark_context}; "
            f"it {relative}"
        )
    return (
        f"The strategy returned {total_return:.1f}% while {benchmark_label} returned "
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
