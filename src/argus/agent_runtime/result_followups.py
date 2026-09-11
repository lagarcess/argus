from __future__ import annotations

import inspect
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from argus.agent_runtime.recovery_messages import recovery_message
from argus.agent_runtime.response_language import response_language_instruction
from argus.agent_runtime.response_style import ARGUS_RESPONSE_STYLE_CONTRACT
from argus.agent_runtime.result_fact_enrichment import (
    as_float,
    enriched_result_fact_entries,
    format_percent,
    metric_number,
)
from argus.context.rendering import context_packet_fact_summary
from argus.domain.benchmark_comparison import benchmark_comparison_from_delta
from argus.domain.engine_launch.display import (
    benchmark_comparison_from_legacy_phrase,
    format_benchmark_comparison_phrase,
    format_benchmark_magnitude_points,
    format_benchmark_signed_delta_points,
)
from argus.domain.engine_launch.result_facts import (
    execution_note,
    resolved_rule_summary,
    runnable_next_tests,
    structured_next_experiments,
)
from argus.llm.openrouter import (
    invoke_openrouter_json_schema,
    log_openrouter_failure,
)

INTERNAL_ONLY_FACT_IDS = frozenset({"benchmark_comparison_claim"})
# Engine metric paths every follow-up surface reads, so the Try next rows and
# the fact bank compare against the same figures.
BENCHMARK_DELTA_METRIC_PATHS = (
    ("metrics", "aggregate", "performance", "delta_vs_benchmark_pct"),
)
MAX_DRAWDOWN_METRIC_PATHS = (
    ("metrics", "aggregate", "risk", "max_drawdown_pct"),
    ("metrics", "aggregate", "max_drawdown_pct"),
)


class PrivateAlphaSaveDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(
        description=(
            "A short natural-language response. It must explain that the legacy "
            "Strategies library and Save action have been retired, that the run "
            "remains retrievable through the conversation or Recents/history, and "
            "that Refine idea is the supported way to continue testing it. Do not "
            "claim that a Strategy was created."
        )
    )
    answer_blocks: list[str] = Field(
        default_factory=list,
        description=(
            "Preferred user-visible response as one or two concise chat paragraphs. "
            "The renderer joins these blocks and uses them instead of answer when "
            "present."
        ),
    )
    fact_ids: list[str] = Field(
        description=(
            "Fact IDs from fact_bank grounding the answer. Must include "
            "save_surface_status and retrieval_path."
        )
    )
    claims_strategy_was_saved: bool = Field(
        description=(
            "True if the answer says or implies a Strategy was created, saved to "
            "Strategies, or stored in a hidden strategy library."
        )
    )
    points_to_hidden_surface: bool = Field(
        description=(
            "True if the answer tells the user to open Strategies, Collections, "
            "or another hidden private-alpha surface."
        )
    )


async def compose_private_alpha_save_response(
    *,
    metadata: dict[str, Any],
    user_message: str,
    language: str = "en",
    invoke_json_schema_func=invoke_openrouter_json_schema,
    log_openrouter_failure_func=log_openrouter_failure,
) -> str | None:
    fact_bank = result_followup_fact_bank(metadata, language=language)
    fact_bank["save_surface_status"] = (
        "The legacy Strategies library and Save action have been retired"
    )
    fact_bank["retrieval_path"] = (
        "Completed runs remain available in the current conversation and through "
        "Recents/history; Refine idea continues testing from the completed run"
    )
    required_fact_ids = {"save_surface_status", "retrieval_path"}
    context_packet_ids = context_packet_ids_from_fact_bank(fact_bank)
    try:
        raw_response = invoke_json_schema_func(
            task="chat_composer",
            messages=private_alpha_save_llm_messages(
                fact_bank=fact_bank,
                user_message=user_message,
                required_fact_ids=required_fact_ids,
                language=language,
            ),
            schema_model=PrivateAlphaSaveDraft,
            schema_name="PrivateAlphaSaveDraft",
            context_packet_ids=context_packet_ids,
        )
        if inspect.isawaitable(raw_response):
            raw_response = await raw_response
    except Exception as exc:
        log_openrouter_failure_func(
            task="chat_composer",
            model_name=None,
            exc=exc,
            message="LLM private-alpha save response failed; using guarded fallback",
        )
        return None

    draft = coerce_private_alpha_save_draft(raw_response)
    if draft is None:
        return None
    return render_private_alpha_save_draft(
        draft=draft,
        fact_bank=fact_bank,
        required_fact_ids=required_fact_ids,
    )


def private_alpha_save_llm_messages(
    *,
    fact_bank: dict[str, str],
    user_message: str,
    required_fact_ids: set[str],
    language: str = "en",
) -> list[dict[str, str]]:
    language_instruction = response_language_instruction(language)
    return [
        {
            "role": "system",
            "content": (
                f"{ARGUS_RESPONSE_STYLE_CONTRACT}\n\n"
                f"{language_instruction}\n\n"
                "The user is asking to save, bookmark, or keep the latest completed "
                "backtest result. The legacy Strategies library and Save action are "
                "retired, so do not claim a Strategy was created and do not imply "
                "that a hidden or disabled save surface still exists. Use the "
                "fact_bank as hard product truth, name the supported conversation, "
                "Recents, and Refine idea continuity path, and own the wording "
                "naturally. Keep the response short."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "user_message": user_message,
                    "fact_bank": fact_bank,
                    "required_fact_ids": sorted(required_fact_ids),
                },
                default=str,
            ),
        },
    ]


def coerce_private_alpha_save_draft(value: Any) -> PrivateAlphaSaveDraft | None:
    if isinstance(value, PrivateAlphaSaveDraft):
        return value
    try:
        return PrivateAlphaSaveDraft.model_validate(value)
    except (TypeError, ValidationError):
        return None


def render_private_alpha_save_draft(
    *,
    draft: PrivateAlphaSaveDraft,
    fact_bank: dict[str, str],
    required_fact_ids: set[str],
) -> str | None:
    if draft.claims_strategy_was_saved or draft.points_to_hidden_surface:
        return None
    body = _save_answer_body(draft)
    if not body or contains_user_visible_internal_fact_name(body):
        return None
    used_fact_ids: set[str] = set()
    for fact_id_value in draft.fact_ids:
        fact_id = str(fact_id_value or "").strip()
        if fact_id not in fact_bank:
            return None
        used_fact_ids.add(fact_id)
    if not required_fact_ids.issubset(used_fact_ids):
        return None
    body = normalize_response_body(body)
    if not body or len(body.split()) > 120:
        return None
    return body


def fallback_private_alpha_save_response(*, language: str | None = None) -> str:
    return recovery_message(
        "private_alpha_save_unavailable",
        language=language,
    )


def public_result_followup_fact_bank(fact_bank: dict[str, str]) -> dict[str, str]:
    return {
        fact_id: value
        for fact_id, value in fact_bank.items()
        if fact_id not in INTERNAL_ONLY_FACT_IDS
    }


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


MAX_UNSTRUCTURED_SAVE_WORDS = 56


def _save_answer_body(draft: PrivateAlphaSaveDraft) -> str | None:
    blocks: list[str] = []
    for block in draft.answer_blocks:
        cleaned = normalize_text(block)
        if cleaned:
            blocks.append(cleaned)
    if blocks:
        return "\n\n".join(blocks[:3])
    body = normalize_text(draft.answer)
    if not body:
        return None
    if len(body.split()) > MAX_UNSTRUCTURED_SAVE_WORDS:
        return None
    return body


def normalize_response_body(value: Any) -> str:
    blocks = [
        normalize_text(block)
        for block in str(value or "").split("\n\n")
        if normalize_text(block)
    ]
    return "\n\n".join(blocks)


INTERNAL_FACT_NAMES = (
    "benchmark_delta",
    "benchmark_comparison_claim",
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


def result_followup_fact_bank(
    metadata: dict[str, Any],
    *,
    language: str = "en",
) -> dict[str, str]:
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
    enriched_facts = enriched_result_fact_entries(metadata)
    benchmark_delta = metric_number(metadata, paths=BENCHMARK_DELTA_METRIC_PATHS)
    comparison = (
        benchmark_comparison_from_delta(benchmark_delta)
        if benchmark_delta is not None
        else benchmark_comparison_from_legacy_phrase(
            enriched_facts.get("benchmark_delta")
        )
    )
    if benchmark_delta is None and comparison is not None:
        benchmark_delta = as_float(comparison.signed_delta_percent)
    if comparison is not None:
        fact_bank["benchmark_comparison_claim"] = comparison.claim
        fact_bank["benchmark_comparison"] = format_benchmark_comparison_phrase(
            comparison.claim,
            comparison.magnitude_points,
            language=language,
        )
        if comparison.signed_delta_percent != "unknown":
            fact_bank["benchmark_delta"] = format_benchmark_signed_delta_points(
                comparison.signed_delta_percent,
                language=language,
            )
        if comparison.magnitude_points != "unknown":
            fact_bank["benchmark_delta_magnitude"] = format_benchmark_magnitude_points(
                comparison.magnitude_points,
                language=language,
            )
        if benchmark_delta is not None:
            relative = relative_performance_label(
                symbols=symbols,
                benchmark=benchmark,
                delta=benchmark_delta,
                language=language,
            )
            if relative:
                fact_bank["relative_performance"] = relative
    drawdown = metric_number(metadata, paths=MAX_DRAWDOWN_METRIC_PATHS)
    if drawdown is not None:
        fact_bank["max_drawdown"] = format_percent(drawdown, signed=False)
    trade_count = metric_number(
        metadata,
        paths=(("metrics", "aggregate", "efficiency", "total_trades"),),
    )
    if trade_count is not None:
        fact_bank["trade_count"] = f"{int(trade_count)} trades"
    fact_bank.update(execution_cost_fact_entries(metadata))
    # Deterministic enrichment (equity-curve extrema, supplemental metrics,
    # result-card rows). Canonical entries above win on key collisions.
    for fact_id, value in enriched_facts.items():
        # Stored cards may predate typed benchmark facts and contain English prose.
        # Normalize that compatibility value above before rendering it for the reader.
        if fact_id == "benchmark_delta":
            continue
        fact_bank.setdefault(fact_id, value)
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


def execution_cost_fact_entries(metadata: dict[str, Any]) -> dict[str, str]:
    result_card = _mapping(
        metadata.get("result_card") or metadata.get("conversation_result_card")
    )
    costs = _mapping(result_card.get("execution_costs"))
    if not costs:
        return {}

    entries: dict[str, str] = {}
    fee_bps = as_float(costs.get("fee_bps"))
    if fee_bps is not None:
        entries["fee_bps"] = _format_bps(fee_bps)
    slippage_bps = as_float(costs.get("slippage_bps"))
    if slippage_bps is not None:
        entries["slippage_bps"] = _format_bps(slippage_bps)
    gross_return = as_float(costs.get("gross_total_return_pct"))
    if gross_return is not None:
        entries["gross_total_return"] = format_percent(gross_return)
    net_return = as_float(costs.get("net_total_return_pct"))
    if net_return is not None:
        entries["net_total_return"] = format_percent(net_return)
    return_drag = as_float(costs.get("return_drag_pct"))
    if return_drag is not None:
        entries["return_drag"] = _format_percentage_points(abs(return_drag))
    benchmark_treatment = str(costs.get("benchmark_treatment") or "").strip()
    if benchmark_treatment == "same_modeled_costs":
        entries["benchmark_cost_treatment"] = "Benchmark used the same modeled costs"
    return entries


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _format_bps(value: float) -> str:
    rounded = round(float(value), 4)
    if abs(rounded - round(rounded)) < 0.0001:
        return f"{int(round(rounded))} bps"
    return f"{rounded:.4f}".rstrip("0").rstrip(".") + " bps"


def _format_percentage_points(value: float) -> str:
    return f"{float(value):.1f} percentage points"


def _context_packets_from_metadata(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    packets = metadata.get("context_packets") or metadata.get("attached_context_packets")
    if not isinstance(packets, list):
        return []
    return [packet for packet in packets if isinstance(packet, dict)]


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def clean_fragment(value: Any) -> str:
    return str(value or "").strip().rstrip(".; ")


def relative_performance_label(
    *,
    symbols: str,
    benchmark: str,
    delta: float,
    language: str = "en",
) -> str | None:
    comparison = benchmark_comparison_from_delta(delta)
    magnitude = format_benchmark_magnitude_points(
        comparison.magnitude_points,
        language=language,
    )
    if language.lower().startswith("es"):
        subject = f"El resultado de {symbols}" if symbols else "La estrategia"
        benchmark_label = benchmark or "la referencia"
        if comparison.claim == "beat_benchmark":
            return (
                f"{subject} superó a {benchmark_label} por {magnitude} "
                "en esta simulación"
            )
        if comparison.claim == "lagged_benchmark":
            return (
                f"{subject} quedó por debajo de {benchmark_label} por {magnitude} "
                "en esta simulación"
            )
        return f"{subject} quedó en línea con {benchmark_label} en esta simulación"

    subject = symbols or "The strategy"
    benchmark_label = benchmark or "the benchmark"
    if comparison.claim == "beat_benchmark":
        return f"{subject} beat {benchmark_label} by {magnitude} in this run"
    if comparison.claim == "lagged_benchmark":
        return f"{subject} lagged {benchmark_label} by {magnitude} in this run"
    return f"{subject} matched {benchmark_label} in this run"


def config_snapshot(metadata: dict[str, Any]) -> dict[str, Any]:
    config = metadata.get("config_snapshot")
    return dict(config) if isinstance(config, dict) else {}


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
