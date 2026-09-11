"""One stored-fact boundary for both model-written result readouts."""

from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from argus.domain.benchmark_comparison import benchmark_comparison_from_delta
from argus.domain.result_readout_content import (
    ReadoutLanguage,
    normalize_readout_language,
)
from argus.domain.result_readout_fact_sheet import build_labeled_fact_sheet
from argus.domain.result_readout_facts import (
    engine_config_from_snapshot,
    result_readout_config,
)
from argus.domain.result_readout_quotes import validate_figure_references
from argus.domain.visible_reply import rewrite_visible_reply

READOUT_RUN_GROUNDING_INSTRUCTIONS = (
    "Tell the story of this historical experience in plain language: what staying "
    "invested involved and the meaningful tradeoff against the benchmark. The card "
    "already carries the numbers. Choose a figure only when it makes a sentence "
    "clearer, and use its supplied display text and rounded value. Describe money "
    "lost only when recorded balances establish the actual loss. Keep deposits "
    "separate from investment gains, and compare the roughness of two investments "
    "only when both are measured. Let these accuracy choices guide your reasoning "
    "silently; give the reader the experience, not calculation methods, data "
    "availability commentary or explanations of your instructions. Describe what "
    "the strategy did in everyday language: buying once and holding, buying "
    "regularly, or buying and selling, as appropriate. Tell the holding "
    "experience without narrating record keeping. Stay within the evidence, "
    "without inventing a holder's feelings or decisions. Any next step is a "
    "question for another supported historical test, never a prediction or "
    "recommendation to trade. No forecasts, investment advice or em dashes. "
    "Write in product_language and report the language actually written. Put "
    "complete prose in text; keep fact names private in figures. For each run "
    "figure used, give its exact fact_key. In figures.value use a JSON number "
    "without currency symbols, percent signs or separators; only dates use an ISO "
    "string. One reference per fact is enough; no figures used means an empty list."
)


READOUT_GROUNDING_INSTRUCTIONS = (
    READOUT_RUN_GROUNDING_INSTRUCTIONS
    + " Use only run_facts. Explain the observed experience without claims about "
    "why market prices moved or outside research."
)


class ResultReadoutFigure(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    fact_key: str = Field(description="The exact key of the supplied fact being quoted.")
    value: float | str = Field(
        description="A JSON number at display precision (no symbols or separators), or an ISO date string. Never a formatted numeric string."
    )


class ResultReadoutDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    language: ReadoutLanguage = Field(
        description="The language actually written in text, not a copy of the requested language."
    )
    text: str = Field(
        description="The complete user-visible readout in product_language."
    )
    figures: list[ResultReadoutFigure] = Field(
        description="References for cited run figures; one per distinct fact, without occurrence bookkeeping."
    )


def stored_readout_facts(
    *,
    metrics: object,
    config_snapshot: object,
    symbols: object,
    benchmark_symbol: object,
    date_range: object = None,
    chart: object = None,
    comparison_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Keep every stored metric, with optional path data and explicit illustrations.

    The retained engine config owns execution inputs. Prose, identifiers and the
    sampled trade-marker list are not evidence for quoted numbers.
    """
    snapshot = result_readout_config(config_snapshot)
    config = engine_config_from_snapshot(snapshot)
    parameters = config.get("resolved_parameters")
    if config.get("template") == "dca_accumulation" and isinstance(parameters, dict):
        # Only the DCA reader projection reinterprets a legacy capital slot.
        # Other execution fields retain engine_config_from_snapshot precedence.
        config.update(
            {
                key: parameters[key]
                for key in ("starting_capital", "recurring_contribution", "cadence")
                if key in parameters
            }
        )
    config = {
        key: value
        for key, value in config.items()
        if key
        not in {
            "metrics",
            "benchmark_metrics",
            "trades",
            "chart",
            "engine_config",
            "resolved_parameters",
            "context_packets",
            "audit_context",
            "provider_metadata",
            "quick_take",
            "breakdown",
            "result_readout",
            "result_readout_content",
            "raw_user_phrasing",
            "strategy_thesis",
            "run_id",
            "conversation_id",
            "result_card",
        }
    }
    facts: dict[str, Any] = {
        "metrics": metrics if isinstance(metrics, dict) else {},
        "configuration": config,
        "symbols": symbols,
        "benchmark_symbol": benchmark_symbol,
        "date_range": date_range,
    }
    performance = _mapping(_mapping(facts["metrics"].get("aggregate")).get("performance"))
    facts["comparison"] = {
        key: value
        for key, value in {**(comparison_metrics or {}), **performance}.items()
        if key in {"total_return_pct", "benchmark_return_pct", "delta_vs_benchmark_pct"}
    }
    delta = facts["comparison"].get("delta_vs_benchmark_pct")
    facts["benchmark_comparison_claim"] = benchmark_comparison_from_delta(delta).claim
    if isinstance(chart, dict):
        facts["chart"] = {
            key: value for key, value in chart.items() if key != "attribution"
        }
    # DCA's seed and recurring contribution are different money roles. The
    # shared config reader derives the seed, including legacy engine shapes.
    capital = config.get("starting_capital", config.get("initial_capital"))
    aggregate = _mapping(facts["metrics"].get("aggregate"))
    drawdown = _mapping(aggregate.get("risk")).get("max_drawdown_pct")
    if drawdown is None:
        drawdown = performance.get("max_drawdown_pct")
    if _finite_number(capital) and capital > 0 and _finite_number(drawdown):
        facts["illustrations"] = {
            "drawdown_scaled_to_starting_capital": abs(drawdown) * capital / 100,
            "meaning": "Illustration using the starting capital, not the actual "
            "peak-to-trough dollar loss. Contributions change the capital at risk.",
        }
    return build_labeled_fact_sheet(facts)


def accepted_readout_text(
    draft: object,
    *,
    facts: dict[str, Any],
    language: str,
) -> tuple[str | None, str | None]:
    """Accept all of the draft or none; punctuation normalization is lossless."""
    try:
        response = ResultReadoutDraft.model_validate(
            draft.model_dump() if isinstance(draft, BaseModel) else draft
        )
    except (TypeError, ValidationError):
        return None, "invalid_draft"
    if response.language != normalize_readout_language(language):
        return None, "language_mismatch"
    text = response.text
    if not text.strip():
        return None, "empty_draft"
    try:
        figure_failure = validate_figure_references(
            text,
            [ref.model_dump() for ref in response.figures],
            facts=facts,
            language=response.language,
        )
    except (ValueError, OverflowError):
        # Malformed numbers/dates are rejected identically by both composers.
        return None, "invalid_figure_reference"
    if figure_failure:
        return None, figure_failure
    return rewrite_visible_reply(text.strip(), surface="result_readout").text, None


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )
