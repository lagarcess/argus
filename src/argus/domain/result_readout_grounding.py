"""One stored-fact boundary for both model-written result readouts."""

from __future__ import annotations

import math
import re
from collections.abc import Iterator
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from argus.domain.benchmark_comparison import benchmark_comparison_from_delta
from argus.domain.result_readout_facts import (
    engine_config_from_snapshot,
    result_readout_config,
)

READOUT_GROUNDING_INSTRUCTIONS = (
    "Use only run_facts for every figure and historical claim, rounding reasonably. "
    "Explain how the return compares with the benchmark and how rough the ride "
    "was when those facts are available. A drawdown is a decline from a prior "
    "peak, not the ending loss. If illustrating the drop in money, use only the "
    "supplied starting-capital illustration and explicitly call it an illustration, "
    "never the actual dollar loss from the portfolio's peak. Contributions change "
    "the capital at risk. Stored chart data is optional; without it do not invent "
    "the path, recovery times or dates of extremes. Trade counts are executed fills, "
    "not necessarily completed round trips; sampled markers are not a full ledger. "
    "Annualized return is historical, not a forecast. Costs may be in percentage "
    "points or basis points; do not invent dollar fees. Explain without a causal "
    "claim about why a price moved. No forecasts, forward scenarios, advice or "
    "recommendations. No em dashes. Write all prose in product_language, "
    "translating source labels naturally; never copy internal fields or schema keys. "
    "Return the entire finished prose in text."
)


class ResultReadoutDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(
        description="The complete user-visible readout in product_language."
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
    return facts


def accepted_readout_text(
    draft: object, *, facts: dict[str, Any]
) -> tuple[str | None, str | None]:
    """Accept all of the draft or none; punctuation normalization is lossless."""
    try:
        response = ResultReadoutDraft.model_validate(
            draft.model_dump() if isinstance(draft, BaseModel) else draft
        )
    except (TypeError, ValidationError):
        return None, "invalid_draft"
    text = re.sub(r"[ \t]*—[ \t]*", ", ", response.text.strip())
    if not text:
        return None, "empty_draft"
    if _internal_field_name(text, facts):
        return None, "internal_field_name"
    if _false_figure(text, facts):
        return None, "unknown_figure"
    if _contradicting_comparison(text, facts):
        return None, "contradicting_benchmark_claim"
    return text, None


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


_NUMBER = re.compile(r"(?<!\w)[-+−]?\d+(?:[.,]\d+)*(?:[eE][+-]?\d+|[kKmMbB](?!\w))?")


def _number(token: str, *, money: bool = False) -> tuple[float, int]:
    token = token.replace("−", "-")
    suffix = re.search(r"([eE][+-]?\d+|[kKmMbB])$", token)
    exponent = 0
    if suffix:
        scale = suffix.group()
        exponent = (
            int(scale[1:])
            if scale[0].lower() == "e"
            else {"k": 3, "m": 6, "b": 9}[scale.lower()]
        )
        token = token[: suffix.start()]
    if "." in token and "," in token:
        decimal = "." if token.rfind(".") > token.rfind(",") else ","
        token = token.replace("," if decimal == "." else ".", "").replace(decimal, ".")
    elif "," in token or "." in token:
        separator = "," if "," in token else "."
        pieces = token.split(separator)
        # A leading zero cannot be a thousands group (e.g. Sharpe 0.456).
        grouped = (
            ((money and separator == ",") or len(pieces) > 2)
            and pieces[0].lstrip("+-") != "0"
            and all(len(p) == 3 for p in pieces[1:])
        )
        token = "".join(pieces) if grouped else token.replace(separator, ".")
    decimals = len(token.rsplit(".", 1)[1]) if "." in token else 0
    try:
        return float(f"{token}e{exponent}"), decimals - exponent
    except ValueError:
        return math.nan, decimals


_PERCENT_RATIOS = {"win_rate", "observed_ratio"}


def _fact_unit(path: str) -> str:
    key = path.rsplit(".", 1)[-1]
    if "date" in path or key in {"time", "timestamp"}:
        return "date"
    if key.endswith(("_pct", "_percent")):
        return "percent"
    if key.endswith("_bps"):
        return "basis_points"
    if key.endswith(("_ratio", "_factor")) or key in _PERCENT_RATIOS:
        return "ratio"
    parts = set(key.split("_"))
    if parts & {
        "capital",
        "contribution",
        "contributions",
        "profit",
        "pnl",
        "price",
        "value",
        "values",
        "balance",
        "cash",
        "amount",
        "principal",
    }:
        return "currency"
    if parts & {
        "trades",
        "fills",
        "count",
        "period",
        "periods",
        "observations",
        "points",
        "signals",
        "days",
        "months",
        "years",
        "quantity",
        "size",
        "entries",
        "exits",
    }:
        return "count"
    return "scalar"


def _numeric_facts(facts: dict[str, Any]) -> Iterator[tuple[str, str, float]]:
    for path, value in _leaves(facts):
        unit = _fact_unit(path)
        if _finite_number(value):
            if unit == "basis_points":
                yield path, "percent", float(value) / 100
            else:
                yield path, unit, float(value)
            if path.rsplit(".", 1)[-1] in _PERCENT_RATIOS:
                yield path, "percent", float(value) * 100
        elif isinstance(value, str) and unit == "date":
            for match in _NUMBER.finditer(value):
                yield path, "date", abs(_number(match.group())[0])


_QUOTED_UNITS = {
    "currency": re.compile(
        r"[$€£]|\b(?:USD|EUR|GBP|dollars?|dólares?|capital|profit|balance|saldo|contribuci[oó]n)\b",
        re.I,
    ),
    "ratio": re.compile(r"\b(?:sharpe|ratio|profit factor|factor de beneficio)\b", re.I),
    "count": re.compile(
        r"\b(?:fills?|trades?|operations?|operaciones|periods?|períodos?|days?|días?|shares?|acciones)\b",
        re.I,
    ),
    "percent": re.compile(
        r"\b(?:return|rendimiento|volatility|volatilidad|drawdown|ca[ií]da)\b", re.I
    ),
}
_PERCENT_SUFFIX = re.compile(
    r"^\s*(?:%|percent(?:age points?)?\b|por ciento\b|puntos? porcentuales?\b|pp\b|pts\b)",
    re.I,
)
_BASIS_SUFFIX = re.compile(r"^\s*(?:bps\b|basis points?\b|puntos? b[aá]sicos?\b)", re.I)


def _quoted_unit(text: str, match: re.Match[str]) -> str:
    before, after = text[: match.start()], text[match.end() :]
    if _PERCENT_SUFFIX.match(after):
        return "percent"
    if _BASIS_SUFFIX.match(after):
        return "basis_points"
    if re.search(r"[$€£] ?$", before) or re.match(
        r"\s*(?:USD|EUR|GBP|dollars?|dólares?)\b", after, re.I
    ):
        return "currency"
    if _QUOTED_UNITS["count"].match(after.lstrip()):
        return "count"
    if re.match(r"\s*x\b", after):
        return "ratio"
    if any(
        date.start() <= match.start() < date.end()
        for date in re.finditer(r"\b\d{4}-\d{2}-\d{2}\b", text)
    ):
        return "date"
    # The nearest preceding unit label supplies the unit for a bare figure.
    # Stop at another figure so one metric's label cannot color the next one.
    previous = list(_NUMBER.finditer(before))
    local = before[previous[-1].end() :] if previous else before
    labels = [
        (label.start(), unit)
        for unit, pattern in _QUOTED_UNITS.items()
        for label in pattern.finditer(local)
    ]
    return max(labels)[1] if labels else "scalar"


def _false_figure(text: str, facts: dict[str, Any]) -> bool:
    allowed = list(_numeric_facts(facts))
    for match in _NUMBER.finditer(text):
        prefix = text[: match.start()].rsplit("\n", 1)[-1]
        if not prefix.strip() and text[match.end() : match.end() + 2] in {". ", ") "}:
            continue
        unit = _quoted_unit(text, match)
        number, decimals = _number(match.group(), money=unit == "currency")
        if not math.isfinite(number):
            return True
        tolerance = float(f"5e{-decimals - 1}") + 1e-8
        if unit == "basis_points":
            unit, number, tolerance = "percent", number / 100, tolerance / 100
        if unit == "date":
            number = abs(number)
        vicinity = text[max(0, match.start() - 70) : match.end() + 35].casefold()
        magnitude = not match.group().startswith(("+", "-", "−")) and bool(
            re.search(
                r"drop|drawdown|declin|loss|lost|fall|lag|trail|behind|underperform|caída|caida|pérd|perd|descens|debajo|detrás|detras|rezag",
                vicinity,
            )
        )
        compatible = {unit} if unit != "scalar" else {"scalar", "count", "ratio", "date"}
        if not any(
            fact_unit in compatible
            and (
                abs(number - value) <= tolerance
                or (
                    not match.group().startswith(("+", "-", "−"))
                    and (
                        magnitude
                        or path.endswith(("max_drawdown_pct", "delta_vs_benchmark_pct"))
                    )
                    and abs(number - abs(value)) <= tolerance
                )
            )
            for path, fact_unit, value in allowed
        ):
            return True
    return False


def _internal_field_name(text: str, facts: dict[str, Any]) -> bool:
    if re.search(r"\b[a-zA-Z][a-zA-Z0-9]*_[a-zA-Z0-9_]+\b", text):
        return True
    if re.search(
        r"\b(?:fact ids?|context packets?|route receipts?|schema keys?)\b", text, re.I
    ):
        return True
    schemas = {
        ResultReadoutDraft.__name__,
        *(model.__name__ for model in ResultReadoutDraft.__subclasses__()),
    }
    if any(re.search(rf"\b{re.escape(name)}\b", text) for name in schemas):
        return True
    keys = {part for path, _ in _leaves(facts) for part in path.split(".") if part}
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
    roles = {
        **{str(s).casefold(): "strategy" for s in facts.get("symbols") or []},
        "strategy": "strategy",
        "estrategia": "strategy",
        **{
            alias: "benchmark"
            for alias in (benchmark, "benchmark", "referencia", "índice", "indice")
        },
    }
    role_pattern = re.compile(
        r"(?<!\w)(?:" + "|".join(re.escape(alias) for alias in roles) + r")(?!\w)"
    )
    for clause in re.split(r"(?<!\d)[.!?;\n](?!\d)", text.casefold()):
        mentions = list(role_pattern.finditer(clause))
        if not any(roles[mention.group()] == "benchmark" for mention in mentions):
            continue
        for match in _COMPARISON.finditer(clause):
            claim = (
                1 if match.lastgroup == "beat" else -1 if match.lastgroup == "lag" else 0
            )
            prefix = clause[: match.start()]
            # Resolve which side is the subject, including inverted sentences
            # such as 'SPY beat DOCN' and ordinary strategy-first statements.
            subjects = [mention for mention in mentions if mention.end() <= match.start()]
            if subjects and roles[subjects[-1].group()] == "benchmark":
                claim *= -1
            negated = bool(re.search(r"(?:\bnot|\bno|n['’]t)\s+(?:\w+\s+){0,2}$", prefix))
            if (negated and claim == expected) or (not negated and claim != expected):
                return True
    return False
