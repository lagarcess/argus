"""One stored-fact boundary for both model-written result readouts."""

from __future__ import annotations

import math
import re
from collections.abc import Iterator
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

READOUT_GROUNDING_INSTRUCTIONS = (
    "Use only run_facts for every figure and historical claim. The card owns "
    "the numbers; do not restate its figures or turn the readout into a metric "
    "inventory. Tell the historical story those facts support: the shape of the "
    "ride, what holding through it involved, and the tradeoff against the "
    "benchmark. Use a figure only when a sentence needs it to explain a point, "
    "rounding reasonably and using the required fact reference. When useful, "
    "suggest a next historical test by changing a supported input of this run, "
    "as a question to investigate rather than a recommendation to trade. "
    "A drawdown is a decline from a prior "
    "peak, not the ending loss. If illustrating the drop in money, use only the "
    "supplied starting-capital illustration and explicitly call it an illustration, "
    "never the actual dollar loss from the portfolio's peak. Contributions change "
    "the capital at risk. Stored chart data is optional; without it do not invent "
    "the path, recovery times or dates of extremes. Do not invent the holder's "
    "feelings or decisions. Trade counts are executed fills, "
    "not necessarily completed round trips; sampled markers are not a full ledger. "
    "Annualized return is historical, not a forecast. Costs may be in percentage "
    "points or basis points; do not invent dollar fees. Explain without a causal "
    "claim about why a price moved. No forecasts, forward scenarios, advice to "
    "buy or sell, or claims that a next test will improve results. No em dashes. "
    "Write all prose in product_language, "
    "translating source labels naturally; never copy internal fields or schema keys. "
    "Return the entire finished prose in text and report the language actually "
    "written. For every visible numeric occurrence, include a figures reference "
    "with its exact fact_key and canonical value from run_facts, its exact visible "
    "quote, and the one-based occurrence of that quote in text. Include the unit "
    "in quote when written, and quote the whole visible date, not just its year. "
    "Repeated figures need separate occurrences. The 500 "
    "inside the name S&P 500 is part of the name, not a numerical fact. Use an "
    "empty figures list when no figures are written."
)


class ResultReadoutFigure(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    fact_key: str = Field(description="The exact key of the supplied fact being quoted.")
    value: float | str = Field(
        description="Copy that fact's canonical value exactly, including ISO dates."
    )
    quote: str = Field(
        min_length=1,
        description="The exact visible numeric quote, including its unit when written.",
    )
    occurrence: int = Field(
        ge=1, description="The one-based occurrence of this exact quote in text."
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
        description="A fact reference for every visible numeric occurrence; empty when none are written."
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
    draft: object, *, facts: dict[str, Any], language: str
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
    if _internal_field_name(text, facts):
        return None, "internal_field_name"
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
    if _contradicting_comparison(text, facts):
        return None, "contradicting_benchmark_claim"
    return re.sub(r"[ \t]*—[ \t]*", ", ", text.strip()), None


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _leaves(value: object, path: str = "") -> Iterator[tuple[str, object]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _leaves(child, f"{path}.{key}")
    elif isinstance(value, list):
        for child in value:
            yield from _leaves(child, path)
    else:
        yield path, value


def _internal_field_name(text: str, facts: dict[str, Any]) -> bool:
    if re.search(r"\b[a-zA-Z][a-zA-Z0-9]*_[a-zA-Z0-9_]+\b", text):
        return True
    if re.search(
        r"\b(?:fact ids?|context packets?|route receipts?|schema keys?)\b", text, re.I
    ):
        return True
    schemas = {
        ResultReadoutDraft.__name__,
        ResultReadoutFigure.__name__,
        *(model.__name__ for model in ResultReadoutDraft.__subclasses__()),
    }
    if any(re.search(rf"\b{re.escape(name)}\b", text) for name in schemas):
        return True
    keys = {part for path, _ in _leaves(facts) for part in path.split(".") if part}
    keys.update(ResultReadoutDraft.model_fields)
    keys.update(ResultReadoutFigure.model_fields)
    return any(
        re.search(rf'`{re.escape(key)}`|"{re.escape(key)}"\s*:', text)
        or (
            key[:1].islower()
            and any(c.isupper() for c in key)
            and re.search(rf"\b{re.escape(key)}\b", text)
        )
        for key in keys
    )


_COMPARISON = re.compile(
    r"\b(?P<beat>beat|outperform\w*|ahead of|above|super[óoa]\w*|por encima|rindi[óo] más)\b|"
    r"\b(?P<lag>lag\w*|trail\w*|underperform\w*|behind|below|por debajo|detrás|detras|rindi[óo] menos)\b|"
    r"\b(?P<match>match\w*|in line with|igual[óoa]\w*|a la par)\b",
    re.I,
)


def _contradicting_comparison(text: str, facts: dict[str, Any]) -> bool:
    truth = facts.get("benchmark_comparison_claim")
    expected = {"beat_benchmark": 1, "lagged_benchmark": -1, "matched_benchmark": 0}.get(
        truth
    )
    benchmark = str(facts.get("benchmark_symbol") or "").casefold()
    if expected is None or not benchmark:
        return False
    strategy_symbols = {str(s).casefold() for s in facts.get("symbols") or []}
    roles = {
        **{symbol: "strategy" for symbol in strategy_symbols},
        "strategy": "strategy",
        "estrategia": "strategy",
        **{
            alias: "benchmark"
            for alias in (benchmark, "benchmark", "referencia", "índice", "indice")
        },
    }
    if benchmark in strategy_symbols:
        roles[benchmark] = "shared"
    role_pattern = re.compile(
        r"(?<!\w)(?:" + "|".join(re.escape(alias) for alias in roles) + r")(?!\w)"
    )
    for clause in re.split(r"(?<!\d)[.!?;\n](?!\d)", text.casefold()):
        mentions = list(role_pattern.finditer(clause))
        if not any(roles[mention.group()] != "strategy" for mention in mentions):
            continue
        explicit = [mention for mention in mentions if roles[mention.group()] != "shared"]
        for match in _COMPARISON.finditer(clause):
            claim = (
                1 if match.lastgroup == "beat" else -1 if match.lastgroup == "lag" else 0
            )
            prefix = clause[: match.start()]
            # Resolve which side is the subject, including inverted sentences
            # such as 'SPY beat DOCN' and ordinary strategy-first statements.
            subjects = [mention for mention in explicit if mention.end() <= match.start()]
            subject = roles[subjects[-1].group()] if subjects else None
            if subject is None and benchmark in strategy_symbols:
                # A shared ticker cannot own a side. An explicit object can
                # disambiguate it, as in 'SPY beat the RSI strategy'.
                objects = [
                    mention for mention in explicit if mention.start() >= match.end()
                ]
                if not objects:
                    continue
                subject = (
                    "strategy"
                    if roles[objects[0].group()] == "benchmark"
                    else "benchmark"
                )
            if subject == "benchmark":
                claim *= -1
            negated = bool(re.search(r"(?:\bnot|\bno|n['’]t)\s+(?:\w+\s+){0,2}$", prefix))
            if (negated and claim == expected) or (not negated and claim != expected):
                return True
    return False
