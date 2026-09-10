"""Labeled, individually addressable evidence for both result composers.

The engine owns values. This projection names their meaning and preserves their
grain; it never turns every number in a run into an interchangeable allowance.
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from copy import deepcopy
from datetime import datetime
from typing import Any

from argus.domain.capability_registry import ALLOWED_TEMPLATES
from argus.domain.dca_capital import DcaCapitalError, dca_capital_plan_from_config
from argus.domain.result_readout_fact_definitions import (
    CHART_BASE_VALUE_MEANING,
    CONFIG_DEFINITIONS,
    FACT_PRESENTATIONS,
    MARKER_GROUP_MEANING,
    METRIC_ALIASES,
    METRIC_DEFINITIONS,
    UNKNOWN_CONFIG_MEANING,
    rule_configuration_definition,
)


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _finite(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _leaves(value: object, path: str = "") -> Iterator[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _leaves(child, f"{path}.{key}" if path else str(key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _leaves(child, f"{path}.{index}")
    else:
        yield path, value


def _row(
    value: Any,
    unit: str,
    meaning: str,
    scope: str,
    basis: str,
    path: str,
    *,
    currency: str | None = None,
) -> dict[str, Any]:
    available = value is not None and not (
        isinstance(value, float) and not math.isfinite(value)
    )
    result = {
        "value": deepcopy(value) if available else None,
        "unit": unit,
        "meaning": meaning,
        "scope": scope,
        "basis": basis,
        "provenance": {"kind": "stored" if available else "unavailable", "path": path},
    }
    if unit == "currency" and currency:
        result["currency"] = currency
    return result


def _insert(rows: dict[str, Any], key: str, row: dict[str, Any]) -> None:
    existing = rows.get(key)
    if existing and existing["value"] == row["value"] and existing["unit"] == row["unit"]:
        existing["provenance"].setdefault("also_stored_at", []).append(
            row["provenance"]["path"]
        )
    elif existing:
        # A second stored number never silently overwrites the semantic owner.
        rows[row["provenance"]["path"]] = row
    else:
        rows[key] = row


def _unavailable(unit: str, meaning: str, basis: str, reason: str) -> dict[str, Any]:
    row = _row(None, unit, meaning, "aggregate_portfolio", basis, "")
    row["provenance"] = {"kind": "unavailable", "reason": reason}
    return row


def _return_basis(performance: dict[str, Any], config: dict[str, Any]) -> str:
    retained = performance.get("return_basis")
    if retained:
        return str(retained)
    template = config.get("template")
    if template == "dca_accumulation":
        return "contributions"
    if isinstance(template, str) and template in ALLOWED_TEMPLATES:
        return "fixed_capital"
    return "return_basis_unavailable"


def build_labeled_fact_sheet(raw_facts: dict[str, Any]) -> dict[str, Any]:
    """Label existing evidence once; missing evidence remains explicitly absent."""
    raw = deepcopy(raw_facts)
    chart = _mapping(raw.get("chart"))
    performance = _mapping(
        _mapping(_mapping(raw.get("metrics")).get("aggregate")).get("performance")
    )
    currency = chart.get("currency") or _mapping(
        performance.get("portfolio_value_range")
    ).get("currency")
    currency = currency if isinstance(currency, str) else None
    sheet = {
        key: deepcopy(raw.get(key))
        for key in ("symbols", "benchmark_symbol", "benchmark_comparison_claim")
    }
    sheet.update(
        schema_version="result_readout_facts/v1", facts={}, series={}, context={}
    )
    rows = sheet["facts"]
    metrics = _mapping(raw.get("metrics"))
    groups = [
        (
            "portfolio",
            "aggregate_portfolio",
            "metrics.aggregate",
            _mapping(metrics.get("aggregate")),
        )
    ]
    groups += [
        (
            f"symbol.{symbol}",
            f"symbol:{symbol}",
            f"metrics.by_symbol.{symbol}",
            _mapping(values),
        )
        for symbol, values in _mapping(metrics.get("by_symbol")).items()
    ]
    for prefix, scope, source, values in groups:
        return_basis = _return_basis(
            _mapping(values.get("performance")), _mapping(raw.get("configuration"))
        )
        for path, value in _leaves(values):
            name = path.rsplit(".", 1)[-1]
            definition = METRIC_DEFINITIONS.get(METRIC_ALIASES.get(name, name))
            if definition:
                suffix, unit, meaning, basis = definition
                if basis == "return_basis":
                    basis = (
                        "return_on_contributed_money"
                        if return_basis == "contributions"
                        else "return_on_fixed_capital"
                        if return_basis == "fixed_capital"
                        else "return_basis_unavailable"
                    )
                if basis == "annual_return_basis":
                    basis = (
                        "money_weighted_annual_return"
                        if return_basis == "contributions"
                        else "compounded_annual_return"
                        if return_basis == "fixed_capital"
                        else "return_basis_unavailable"
                    )
                key = f"{prefix}.{suffix}"
            else:
                key, unit, meaning, basis = (
                    f"{prefix}.metrics.{path}",
                    "unknown",
                    "Stored metric; definition unavailable. Do not infer its financial meaning.",
                    "definition_unavailable",
                )
                if isinstance(value, str):
                    unit = "text"
                elif isinstance(value, bool):
                    unit = "boolean"
            row = _row(
                value, unit, meaning, scope, basis, f"{source}.{path}", currency=currency
            )
            if definition and name in FACT_PRESENTATIONS:
                row["presentation"] = list(FACT_PRESENTATIONS[name])
            _insert(rows, key, row)
        rows.setdefault(
            f"{prefix}.completed_trades",
            _unavailable(
                "count",
                "Completed round-trip trade count",
                "closed_trade_ledger",
                "The completed-trade count is not persisted; executed fills and chart markers cannot establish it.",
            ),
        )
        rows[f"{prefix}.completed_trades"]["scope"] = scope
    for path, value in _leaves(
        {
            key: value
            for key, value in metrics.items()
            if key not in {"aggregate", "by_symbol"}
        }
    ):
        rows[f"metrics.{path}"] = _row(
            value,
            "unknown",
            "Stored metric; definition unavailable. Do not infer its financial meaning.",
            "metric_scope_unavailable",
            "definition_unavailable",
            f"metrics.{path}",
        )
    config = _mapping(raw.get("configuration"))
    for path, value in _leaves(config):
        name = path.rsplit(".", 1)[-1]
        basis = "executed_configuration"
        definition = rule_configuration_definition(config, path)
        if definition:
            key = f"configuration.{path}"
            unit, meaning, basis = definition
        elif name in CONFIG_DEFINITIONS:
            key, unit, meaning = CONFIG_DEFINITIONS[name]
            key = f"configuration.{key}"
        elif name == "capital_amount":
            role = (
                "recurring_contribution"
                if config.get("template") == "dca_accumulation"
                else "starting_capital"
            )
            key, unit = f"configuration.{role}", "currency"
            meaning = "Resolved launch money role; periodic contribution for DCA, otherwise initial capital"
        else:
            key = f"configuration.{path}"
            unit = (
                "boolean"
                if isinstance(value, bool)
                else "text"
                if isinstance(value, str)
                else "unknown"
            )
            meaning = UNKNOWN_CONFIG_MEANING
            if isinstance(value, str) and ("date" in path or name in {"start", "end"}):
                unit, meaning = (
                    "date",
                    "Recorded execution-window date; requested and effective windows remain distinct",
                )
        if unit in {"text", "boolean"} and meaning == UNKNOWN_CONFIG_MEANING:
            group = sheet["context"].setdefault(
                "execution_configuration",
                {
                    "scope": "execution_configuration",
                    "basis": "executed_configuration",
                    "meaning": UNKNOWN_CONFIG_MEANING,
                    "provenance": {"kind": "stored", "path": "configuration"},
                    "reference": "Each values key resolves to its typed text or boolean row.",
                    "values": {},
                },
            )
            group["values"][key] = deepcopy(value)
            continue
        row = _row(
            value,
            unit,
            meaning,
            "execution_configuration",
            basis,
            f"configuration.{path}",
            currency=currency,
        )
        if name in FACT_PRESENTATIONS and unit == "basis_points":
            row["presentation"] = list(FACT_PRESENTATIONS[name])
        _insert(rows, key, row)
    _capital_roles(rows, config, currency)
    for path, value in _leaves(raw.get("date_range")):
        if path in {"start", "end"}:
            rows[f"window.{path}"] = _row(
                value,
                "date",
                "Effective backtest window boundary",
                "aggregate_portfolio",
                "effective_window",
                f"date_range.{path}",
            )
    # Legacy comparison-only result shapes still expose every supplied figure.
    for name, value in _mapping(raw.get("comparison")).items():
        definition = METRIC_DEFINITIONS.get(name)
        if definition and f"portfolio.{definition[0]}" not in rows:
            suffix, unit, meaning, basis = definition
            rows[f"portfolio.{suffix}"] = _row(
                value, unit, meaning, "aggregate_portfolio", basis, f"comparison.{name}"
            )
            if name in FACT_PRESENTATIONS:
                rows[f"portfolio.{suffix}"]["presentation"] = list(
                    FACT_PRESENTATIONS[name]
                )
    _chart_facts(sheet, chart, currency)
    ending = _mapping(rows.get("portfolio.ending_equity")).get("value")
    profit = _mapping(rows.get("portfolio.profit")).get("value")
    rows["portfolio.invested_capital"] = _unavailable(
        "currency",
        "Total money invested, including initial seed and periodic contributions",
        "total_contributed_money",
        "Stored ending equity and profit are required to resolve the engine's invested-money identity.",
    )
    if _finite(ending) and _finite(profit) and ending - profit >= 0:
        row = rows["portfolio.invested_capital"]
        row["value"] = round(ending - profit, 2)
        row["provenance"] = {
            "kind": "derived",
            "owner": "ending_equity_minus_profit",
            "inputs": ["portfolio.ending_equity", "portfolio.profit"],
        }
        if currency:
            row["currency"] = currency
    illustration = _mapping(raw.get("illustrations")).get(
        "drawdown_scaled_to_starting_capital"
    )
    rows["portfolio.drawdown_illustration"] = _row(
        illustration,
        "currency",
        "Starting-capital-scaled illustration of the percentage drop, not the historical peak-to-trough dollar loss",
        "aggregate_portfolio",
        "starting_capital_illustration",
        "illustrations.drawdown_scaled_to_starting_capital",
        currency=currency,
    )
    if illustration is not None:
        rows["portfolio.drawdown_illustration"]["provenance"] = {
            "kind": "derived",
            "inputs": ["configuration.starting_capital", "portfolio.max_drawdown"],
            "owner": "stored_readout_facts",
        }
    _drawdown_facts(sheet, raw, chart, currency)
    return sheet


def _capital_roles(
    rows: dict[str, Any], config: dict[str, Any], currency: str | None
) -> None:
    if config.get("template") != "dca_accumulation":
        return
    try:
        plan = dca_capital_plan_from_config(config)
    except DcaCapitalError:
        return
    for key, value, meaning in (
        (
            "starting_capital",
            plan.starting_capital,
            "Initial seed; separate from every periodic contribution",
        ),
        (
            "recurring_contribution",
            plan.contribution,
            "Whole-plan money added each contribution period; not initial seed",
        ),
    ):
        source = f"configuration.dca_capital.{'contribution' if key == 'recurring_contribution' else key}"
        row = _row(
            value,
            "currency",
            meaning,
            "execution_configuration",
            "canonical_dca_capital_plan",
            source,
            currency=currency,
        )
        old = rows.get(f"configuration.{key}")
        if old and old["value"] == value:
            sources = [
                old["provenance"].get("path"),
                *old["provenance"].get("also_stored_at", []),
            ]
            row["provenance"]["also_stored_at"] = list(
                dict.fromkeys(path for path in sources if path and path != source)
            )
        if not isinstance(config.get("dca_capital"), dict):
            row["provenance"] = {
                "kind": "derived",
                "owner": "dca_capital_plan_from_config",
                "inputs": [
                    "configuration.starting_capital",
                    "configuration.recurring_contribution",
                ],
            }
        rows[f"configuration.{key}"] = row
    rows["configuration.contribution_period"] = _row(
        plan.period,
        "text",
        "Period between scheduled contributions",
        "execution_configuration",
        "canonical_dca_capital_plan",
        "configuration.parameters.dca_cadence",
    )


def _chart_facts(
    sheet: dict[str, Any], chart: dict[str, Any], currency: str | None
) -> None:
    rows = sheet["facts"]
    points = chart.get("series")
    if isinstance(points, list):
        sheet["series"]["portfolio_equity"] = {
            "unit": "currency",
            "currency": currency,
            "scope": "aggregate_portfolio",
            "basis": "nominal_equity_close",
            "meaning": "Dated nominal portfolio equity closes; deposits affect values. Not the flow-adjusted risk path.",
            "provenance": {"kind": "stored", "path": "chart.series"},
            "points": deepcopy(points),
            "point_reference": "chart.portfolio_equity.<zero-based-index>.value or .time",
        }
    markers = chart.get("markers")
    if isinstance(markers, list):
        sheet["series"]["execution_markers"] = {
            "scope": "aggregate_portfolio",
            "basis": "recorded_execution_groups",
            "meaning": MARKER_GROUP_MEANING,
            "provenance": {"kind": "stored", "path": "chart.markers"},
            "fields": {
                "time": "timestamp",
                "type": "text",
                "label": "text",
                "symbols": "text",
            },
            "point_reference": "chart.markers.<zero-based-index>.<field>, including .symbols.<index>",
            "points": deepcopy(markers),
        }
    for path, value in _leaves(
        {
            key: value
            for key, value in chart.items()
            if key not in {"series", "markers", "attribution"}
        }
    ):
        name = path.rsplit(".", 1)[-1]
        if name in {"peak_value", "lowest_value"}:
            suffix, unit, meaning, basis = METRIC_DEFINITIONS[name]
            key = f"portfolio.{suffix}"
        elif path == "base_value":
            key, unit, meaning, basis = (
                "chart.base_value",
                "currency",
                CHART_BASE_VALUE_MEANING,
                "first_nominal_equity_close",
            )
        else:
            key, basis = f"chart.{path}", "stored_chart_metadata"
            unit = (
                "boolean"
                if isinstance(value, bool)
                else "timestamp"
                if name == "time"
                else "text"
                if isinstance(value, str)
                else "unknown"
            )
            meaning = "Stored chart metadata; marker counts describe grouped, possibly sampled fills, not completed trades or curve completeness"
        _insert(
            rows,
            key,
            _row(
                value,
                unit,
                meaning,
                "aggregate_portfolio",
                basis,
                f"chart.{path}",
                currency=currency,
            ),
        )
    ordered = _ordered_points(points)
    rows["portfolio.ending_equity"] = _unavailable(
        "currency",
        "Nominal portfolio equity at the last stored observation",
        "nominal_equity_close",
        "No finite chronologically ordered stored chart is available.",
    )
    end = _mapping(rows.get("configuration.end_date")).get("value") or _mapping(
        rows.get("window.end")
    ).get("value")
    terminal_matches = bool(
        ordered and isinstance(end, str) and str(ordered[-1]["time"])[:10] == end[:10]
    )
    if ordered and terminal_matches:
        row = resolve_readout_fact(
            sheet, f"chart.portfolio_equity.{len(ordered) - 1}.value"
        )
        if row:
            rows["portfolio.ending_equity"] = {
                **row,
                "meaning": "Ending nominal portfolio equity at the final stored close; not peak equity",
            }


def resolve_readout_fact(sheet: dict[str, Any], fact_key: str) -> dict[str, Any] | None:
    """Resolve one scalar or typed chart cell, including inherited metadata."""
    row = _mapping(sheet.get("facts")).get(fact_key)
    if isinstance(row, dict):
        return deepcopy(row)
    context = _mapping(_mapping(sheet.get("context")).get("execution_configuration"))
    values = _mapping(context.get("values"))
    if fact_key in values:
        value = values[fact_key]
        return _row(
            value,
            "boolean" if isinstance(value, bool) else "text",
            context["meaning"],
            context["scope"],
            context["basis"],
            fact_key,
        )
    parts = fact_key.split(".")
    if len(parts) >= 4 and parts[:2] == ["chart", "markers"]:
        group = _mapping(_mapping(sheet.get("series")).get("execution_markers"))
        point = group.get("points")
        for segment in parts[2:]:
            if (
                isinstance(point, list)
                and segment.isdigit()
                and int(segment) < len(point)
            ):
                point = point[int(segment)]
            elif isinstance(point, dict) and segment in point:
                point = point[segment]
            else:
                return None
        if isinstance(point, (dict, list)):
            return None
        unit = (
            "timestamp"
            if parts[-1] == "time"
            else "boolean"
            if isinstance(point, bool)
            else "text"
            if isinstance(point, str)
            else "unknown"
        )
        return _row(
            point, unit, group["meaning"], group["scope"], group["basis"], fact_key
        )
    if (
        len(parts) != 4
        or parts[:2] != ["chart", "portfolio_equity"]
        or not parts[2].isdigit()
    ):
        return None
    series = _mapping(_mapping(sheet.get("series")).get("portfolio_equity"))
    points = series.get("points")
    index = int(parts[2])
    if (
        not isinstance(points, list)
        or index >= len(points)
        or not isinstance(points[index], dict)
    ):
        return None
    field = parts[3]
    if field not in points[index]:
        return None
    return _row(
        points[index][field],
        "timestamp"
        if field == "time"
        else series.get("unit", "unknown")
        if field == "value"
        else "unknown",
        "Time of a nominal equity close"
        if field == "time"
        else series.get("meaning", "Stored chart cell; definition unavailable"),
        "aggregate_portfolio",
        "nominal_equity_close",
        f"chart.series.{index}.{field}",
        currency=series.get("currency"),
    )


def _ordered_points(points: object) -> list[dict[str, Any]] | None:
    if not isinstance(points, list) or not points:
        return None
    previous: datetime | None = None
    for point in points:
        if (
            not isinstance(point, dict)
            or not _finite(point.get("value"))
            or point["value"] < 0
        ):
            return None
        try:
            timestamp = datetime.fromisoformat(str(point["time"]).replace("Z", "+00:00"))
            if previous is not None and timestamp <= previous:
                return None
        except (KeyError, ValueError, TypeError):
            return None
        previous = timestamp
    return points


def _drawdown_facts(
    sheet: dict[str, Any],
    raw: dict[str, Any],
    chart: dict[str, Any],
    currency: str | None,
) -> None:
    rows = sheet["facts"]
    performance = _mapping(
        _mapping(_mapping(raw.get("metrics")).get("aggregate")).get("performance")
    )
    reason = "Complete ordered fixed-capital chart evidence, its observation count and matching metric are required."
    return_basis = _return_basis(performance, _mapping(raw.get("configuration")))
    if return_basis == "contributions":
        reason = "The DCA flow-adjusted risk path and dated flows were not retained; nominal equity cannot establish these endpoints."
    elif return_basis != "fixed_capital":
        reason = "The funding basis is unavailable; nominal equity cannot establish fixed-capital drawdown endpoints."
    for key, unit in (
        ("peak_equity", "currency"),
        ("trough_equity", "currency"),
        ("peak_date", "timestamp"),
        ("trough_date", "timestamp"),
        ("dollar_loss", "currency"),
    ):
        rows[f"portfolio.drawdown.{key}"] = _unavailable(
            unit,
            "Endpoint of the largest chronological drawdown, not an independent whole-period extreme",
            "chronological_fixed_capital_drawdown",
            reason,
        )
    points = _ordered_points(chart.get("series"))
    capital = _mapping(rows.get("configuration.starting_capital")).get("value")
    target = _mapping(performance.get("benchmark_coverage")).get("target_points")
    stored = _mapping(rows.get("portfolio.max_drawdown")).get("value")
    series_summary = _mapping(chart.get("series_summary"))
    if (
        return_basis != "fixed_capital"
        or len(raw.get("symbols") or []) != 1
        or chart.get("kind") != "portfolio_equity"
        or chart.get("currency") != "USD"
        or not points
        or not _finite(capital)
        or capital <= 0
        or not _finite(stored)
        or not isinstance(target, int)
        or isinstance(target, bool)
        or target != len(points)
        or chart.get("sampled")
        or chart.get("complete") is False
        or series_summary.get("sampled")
        or series_summary.get("complete") is False
    ):
        return
    config = _mapping(raw.get("configuration"))
    try:
        window_start = datetime.fromisoformat(config["start_date"]).date()
        window_end = datetime.fromisoformat(config["end_date"]).date()
        if not all(
            window_start
            <= datetime.fromisoformat(point["time"].replace("Z", "+00:00")).date()
            <= window_end
            for point in points
        ):
            return
    except (KeyError, TypeError, ValueError):
        return
    # Engine chart writers retain every close. For one symbol, benchmark target
    # count is the independent observation count; its ratio alone proves nothing.
    peak = {"time": None, "value": capital}
    worst: tuple[float, dict[str, Any], dict[str, Any]] | None = None
    for point in points:
        if point["value"] > peak["value"]:
            peak = point
        drop = (point["value"] / peak["value"] - 1) * 100
        if worst is None or drop < worst[0]:
            worst = (drop, peak, point)
    if worst is None or abs(worst[0] - stored) > 0.005 + 1e-8 or worst[0] >= 0:
        return
    _, peak, trough = worst
    values = {
        "peak_equity": peak["value"],
        "trough_equity": trough["value"],
        "peak_date": peak["time"],
        "trough_date": trough["time"],
        "dollar_loss": round(peak["value"] - trough["value"], 2),
    }
    for key, value in values.items():
        row = rows[f"portfolio.drawdown.{key}"]
        if value is None:
            row["provenance"]["reason"] = (
                "The peak is the pre-trade funding baseline, not a timestamped observed close."
            )
            continue
        row["value"] = value
        row["provenance"] = {
            "kind": "derived",
            "owner": "ordered_fixed_capital_drawdown",
            "inputs": [
                "chart.portfolio_equity",
                "configuration.starting_capital",
                "portfolio.max_drawdown",
                "portfolio.target_points",
            ],
        }
        if row["unit"] == "currency" and currency:
            row["currency"] = currency
