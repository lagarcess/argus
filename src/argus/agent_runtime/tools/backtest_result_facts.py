"""Executed backtest facts for the registered card, independent of sharing."""

from __future__ import annotations

from datetime import date
from math import isfinite
from typing import Any, Literal

from argus.domain.backtesting.config import AssetClass, _normalize_execution_realism
from argus.domain.backtesting.rules.signals import (
    _opposite_moving_average_crossover_rule,
    rule_spec_from_moving_average_crossover_rules,
    rule_spec_from_signal_rule,
)
from argus.domain.dca_capital import dca_capital_plan_from_config
from argus.domain.indicators import normalize_indicator_parameters
from argus.domain.result_figures import result_display_figures
from argus.domain.result_readout_facts import engine_config_from_snapshot
from argus.domain.strategy_capabilities import STRATEGY_CAPABILITIES
from argus.domain.tool_contracts import PublicExcerptVisual, ToolContract, ToolScalar
from pydantic import (
    Field,
    StrictFloat,
    StrictInt,
    StrictStr,
    TypeAdapter,
    model_validator,
)

MetricKey = Literal[
    "cash_value",
    "total_return_pct",
    "contribution_return_pct",
    "max_drawdown_pct",
    "win_rate",
    "benchmark_return_pct",
    "delta_vs_benchmark_pct",
]


class BacktestMetric(ToolContract):
    key: MetricKey
    value: StrictStr = Field(min_length=1)


class BacktestFact(ToolContract):
    key: str
    value: ToolScalar = None


class BacktestDates(ToolContract):
    start: str
    end: str

    @model_validator(mode="after")
    def valid_window(self) -> BacktestDates:
        start, end = date.fromisoformat(self.start), date.fromisoformat(self.end)
        if start.isoformat() != self.start or end.isoformat() != self.end or start > end:
            raise ValueError("invalid_backtest_date_range")
        return self


class BacktestCardFacts(ToolContract):
    asset_class: AssetClass
    symbols: list[StrictStr] = Field(min_length=1, max_length=5)
    benchmark_symbol: StrictStr = Field(min_length=1)
    date_range: BacktestDates
    metrics: list[BacktestMetric] = Field(min_length=1)
    strategy_facts: list[BacktestFact] = Field(min_length=1)
    assumptions: list[BacktestFact]
    visual: PublicExcerptVisual | None = None


class CrossoverParameters(ToolContract):
    fast_indicator: str
    fast_period: StrictInt = Field(gt=0)
    slow_indicator: str
    slow_period: StrictInt = Field(gt=0)


def backtest_card_facts(
    *, result: dict[str, Any], card: dict[str, Any]
) -> BacktestCardFacts:
    """Project retained outputs only; never execute, resolve assets or load prices."""
    if result.get("execution_status") != "succeeded":
        raise ValueError("backtest_not_completed")
    engine = engine_config_from_snapshot(result)
    strategy = _mapping(result.get("resolved_strategy"))
    template = engine.get("template", strategy.get("strategy_type"))
    strategy_facts = _strategy_facts(template, engine=engine, strategy=strategy)
    benchmark = _required_text(engine.get("benchmark_symbol"))
    dates = _mapping(card.get("date_range"))
    return BacktestCardFacts.model_validate(
        {
            "asset_class": card.get("asset_class"),
            "symbols": card.get("symbols"),
            "benchmark_symbol": benchmark,
            "date_range": {"start": dates.get("start"), "end": dates.get("end")},
            "metrics": _metrics(
                card.get("rows"),
                result.get("metrics"),
                recurring=template == "dca_accumulation",
            ),
            "strategy_facts": strategy_facts,
            "assumptions": _assumptions(
                engine, benchmark=benchmark, recurring=template == "dca_accumulation"
            ),
            "visual": _visual(card.get("chart")),
        }
    )


def _metrics(rows: object, metrics: object, *, recurring: bool) -> list[BacktestMetric]:
    if not isinstance(rows, list):
        raise ValueError("missing_backtest_metrics")
    projected = []
    seen = set()
    for raw in rows:
        row = _mapping(raw)
        key = row.get("key")
        if key in seen:
            raise ValueError("duplicate_backtest_metric")
        seen.add(key)
        if key != "benchmark_delta":
            projected.append(
                BacktestMetric.model_validate({"key": key, "value": row.get("value")})
            )
    headline = "contribution_return_pct" if recurring else "total_return_pct"
    if not {headline, "max_drawdown_pct"}.issubset(seen):
        raise ValueError("incomplete_backtest_metrics")
    aggregate = _mapping(_mapping(metrics).get("aggregate"))
    performance = _mapping(aggregate.get("performance"))
    for key in ("total_return_pct", "benchmark_return_pct", "delta_vs_benchmark_pct"):
        _number(performance.get(key))
    _number(_mapping(aggregate.get("risk")).get("max_drawdown_pct"))
    figures = result_display_figures(metrics)
    if figures is None:
        raise ValueError("missing_backtest_metrics")
    # The engine card owns printable rows; its prose-only comparison is replaced
    # by the shared display figures, never by subtracting rounded card values.
    for key, suffix in (("benchmark_return_pct", "%"), ("delta_vs_benchmark_pct", "")):
        value = figures[key]
        if key not in seen:
            projected.append(
                BacktestMetric.model_validate(
                    {
                        "key": key,
                        "value": f"{value:+.1f}{suffix}"
                        if suffix
                        else _display_number(value),
                    }
                )
            )
    return projected


def _strategy_facts(
    template: object, *, engine: dict[str, Any], strategy: dict[str, Any]
) -> list[BacktestFact]:
    if template == "dca_accumulation":
        plan = dca_capital_plan_from_config(engine)
        return [
            BacktestFact(key="strategy_type", value="dca accumulation"),
            BacktestFact(key="cadence", value=plan.period),
        ]
    if template in {"buy_and_hold", "buy_the_dip"}:
        return [BacktestFact(key="strategy_type", value=str(template).replace("_", " "))]
    if template in {"rsi_mean_reversion", "indicator_threshold"}:
        parameters = {**engine, **_mapping(engine.get("parameters"))}
        keys = STRATEGY_CAPABILITIES["rsi_mean_reversion"].parameters
        retained = {key: parameters[key] for key in keys}
        for key in keys:
            if key != "indicator":
                _number(retained[key])
        normalized = normalize_indicator_parameters(retained["indicator"], retained)
        return [
            BacktestFact(
                key="strategy_type",
                value="rsi threshold"
                if template == "rsi_mean_reversion"
                else "indicator threshold",
            ),
            *(BacktestFact(key=key, value=normalized[key]) for key in keys),
        ]
    entry = _mapping(strategy.get("entry_rule"))
    if entry.get("type") == "moving_average_crossover":
        exit_rule = _mapping(strategy.get("exit_rule"))
        mirror = _opposite_moving_average_crossover_rule(entry)
        if mirror is None:
            raise ValueError("missing_backtest_rule")
        effective_exit = exit_rule if exit_rule else mirror
        entry_values = _crossover_values(entry)
        exit_values = _crossover_values(effective_exit)
        # The existing card text describes the mirrored direction. A different
        # direction cannot be represented by that binding and is withheld.
        if effective_exit.get("direction") != mirror.get("direction"):
            raise ValueError("unprojectable_backtest_rule")
        rule_spec_from_moving_average_crossover_rules(
            entry_rule=entry, exit_rule=effective_exit
        )
        values = dict(entry_values)
        if exit_values != entry_values:
            values.update({f"exit_{key}": value for key, value in exit_values.items()})
        return [
            BacktestFact(key="strategy_type", value="moving average crossover"),
            *(BacktestFact(key=key, value=value) for key, value in values.items()),
        ]
    if entry.get("type") == "macd_crossover":
        signal_keys = ("fast_period", "slow_period", "signal_period")
        values = {key: _number(entry[key]) for key in signal_keys}
        rule_spec_from_signal_rule(entry)
        return [
            BacktestFact(key="strategy_type", value="macd crossover"),
            *(BacktestFact(key=key, value=value) for key, value in values.items()),
        ]
    raise ValueError("unprojectable_backtest_strategy")


def _crossover_values(rule: dict[str, Any]) -> dict[str, Any]:
    if rule.get("type") != "moving_average_crossover" or "direction" not in rule:
        raise ValueError("missing_backtest_rule")
    return CrossoverParameters.model_validate(
        {key: rule[key] for key in CrossoverParameters.model_fields}
    ).model_dump()


def _assumptions(
    engine: dict[str, Any], *, benchmark: str, recurring: bool
) -> list[BacktestFact]:
    facts = []
    if recurring:
        plan = dca_capital_plan_from_config(engine)
        facts.extend(
            [
                BacktestFact(key="recurring_contribution", value=plan.contribution),
                BacktestFact(key="contribution_cadence", value=plan.period),
                BacktestFact(key="starting_principal", value=plan.starting_capital),
                BacktestFact(key="fractional_shares"),
            ]
        )
    facts.extend([BacktestFact(key="long_only"), BacktestFact(key="equal_weight")])
    raw = _mapping(engine.get("_execution_realism"))
    costs = _normalize_execution_realism(raw)
    if costs["enabled"]:
        for key in ("fee_bps", "slippage_bps"):
            _number(raw.get(key))
    modeled = costs["enabled"] and (costs["fee_bps"] > 0 or costs["slippage_bps"] > 0)
    if modeled:
        facts.extend(
            [
                BacktestFact(key=f"modeled_{key}", value=costs[key])
                for key in ("fee_bps", "slippage_bps")
            ]
        )
    else:
        facts.append(BacktestFact(key="no_costs"))
    facts.append(
        BacktestFact(
            key="benchmark_same_modeled_costs" if modeled else "benchmark",
            value=benchmark,
        )
    )
    return facts


def _visual(value: object) -> PublicExcerptVisual | None:
    if value is None:
        return None
    chart = _mapping(value)
    if chart.get("kind") != "portfolio_equity":
        raise ValueError("invalid_backtest_visual")
    visual = PublicExcerptVisual.model_validate(
        {key: chart[key] for key in PublicExcerptVisual.model_fields if key in chart}
    )
    if len(visual.series) < 2:
        return None
    return visual


def _number(value: object) -> float:
    number: float | int = TypeAdapter(StrictFloat | StrictInt).validate_python(value)
    # ToolContract also rejects non-finite numbers in the returned facts, but
    # metrics must be checked before a formatted string could conceal them.
    if not isfinite(number):
        raise ValueError("invalid_backtest_number")
    return float(number)


def _display_number(value: float) -> str:
    return str(int(value)) if value.is_integer() else str(value)


def _required_text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("missing_backtest_fact")
    return value


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
