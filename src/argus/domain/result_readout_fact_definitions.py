"""Model-facing meanings and units for the shared readout fact-sheet owner."""

from typing import Any

from argus.domain.indicators import EXECUTABLE_INDICATORS

# Key, unit, meaning, basis. Definitions follow backtesting/metrics.py.
METRIC_DEFINITIONS = {
    "total_return_pct": (
        "total_return",
        "percent",
        "Historical return for the complete test window",
        "return_basis",
    ),
    "benchmark_return_pct": (
        "benchmark_return",
        "percent",
        "Benchmark historical total return for the same window and funding plan",
        "return_basis",
    ),
    "delta_vs_benchmark_pct": (
        "benchmark_gap",
        "percentage_points",
        "Strategy total return minus benchmark total return; not an annualized comparison",
        "same_window_total_return_difference",
    ),
    "profit": (
        "profit",
        "currency",
        "Ending account balance minus all money deposited",
        "nominal_money",
    ),
    "annualized_return_pct": (
        "annualized_return",
        "percent",
        "Historical annual return; not a forecast",
        "annual_return_basis",
    ),
    "max_drawdown_pct": (
        "max_drawdown",
        "percent",
        "Largest investment decline from an earlier high, excluding the effect of new deposits",
        "flow_adjusted_drawdown",
    ),
    "volatility_pct": (
        "annualized_volatility",
        "percent",
        "Variation in investment returns, expressed on an annual scale and excluding new deposits",
        "annualized_flow_adjusted_return_dispersion",
    ),
    "total_trades": (
        "executed_fills",
        "count",
        "Purchases and sales executed during the test",
        "execution_fills",
    ),
    "completed_trades": (
        "completed_trades",
        "count",
        "Completed buy-and-sell pairs recorded by the run",
        "closed_trade_ledger",
    ),
    "closed_trade_count": (
        "completed_trades",
        "count",
        "Completed buy-and-sell pairs recorded by the run",
        "closed_trade_ledger",
    ),
    "win_rate": (
        "win_rate",
        "ratio",
        "Fraction of completed trades with positive net profit; unavailable with no completed trades",
        "closed_trade_net_pnl",
    ),
    "profit_factor": (
        "profit_factor",
        "ratio",
        "Positive closed-trade profit divided by absolute closed-trade losses; unavailable when there are no losses",
        "closed_trade_net_pnl",
    ),
    "sharpe_ratio": (
        "sharpe_ratio",
        "ratio",
        "Average return relative to its variability, expressed on an annual scale",
        "annualized_flow_adjusted_return_ratio",
    ),
    "fee_bps": (
        "fee_bps",
        "basis_points",
        "Modeled fee rate on executions; not money paid",
        "execution_cost_rate",
    ),
    "slippage_bps": (
        "slippage_bps",
        "basis_points",
        "Modeled slippage rate on executions; not money paid",
        "execution_cost_rate",
    ),
    "gross_total_return_pct": (
        "gross_return",
        "percent",
        "Historical total return before modeled fees and slippage",
        "return_basis",
    ),
    "net_total_return_pct": (
        "net_return",
        "percent",
        "Historical total return after modeled fees and slippage",
        "return_basis",
    ),
    "return_drag_pct": (
        "cost_drag",
        "percentage_points",
        "Gross total return minus net total return due to modeled costs",
        "same_window_total_return_difference",
    ),
    "peak_value": (
        "peak_equity",
        "currency",
        "Highest account balance at a recorded close, including deposits",
        "nominal_equity_close",
    ),
    "lowest_value": (
        "lowest_equity",
        "currency",
        "Lowest account balance at a recorded close, including deposits",
        "nominal_equity_close",
    ),
    "observed_points": (
        "observed_points",
        "count",
        "Observed benchmark data points; aggregate count sums symbol comparisons",
        "benchmark_coverage",
    ),
    "target_points": (
        "target_points",
        "count",
        "Target benchmark comparison points; aggregate count sums symbol comparisons",
        "benchmark_coverage",
    ),
    "observed_ratio": (
        "observed_ratio",
        "ratio",
        "Observed benchmark points divided by target points; not chart completeness",
        "benchmark_coverage",
    ),
    "deferred_fill_count": (
        "deferred_fill_count",
        "count",
        "Benchmark contribution fills deferred until an observed price",
        "benchmark_coverage",
    ),
}

# Historical spelling, one semantic definition.
METRIC_ALIASES = {"volatility_annual_pct": "volatility_pct"}

UNKNOWN_CONFIG_MEANING = (
    "Stored execution setting; definition unavailable. "
    "Do not infer a different money role or metric."
)

MARKER_GROUP_MEANING = (
    "Recorded executed-fill groups, possibly sampled; not a full execution ledger, "
    "completed round trips, or proof of equity-series completeness."
)

CHART_BASE_VALUE_MEANING = (
    "First stored post-execution nominal portfolio equity close; includes any "
    "initial-period contributions and execution costs. Not the initial funding seed."
)

RULE_COMPARISONS = {
    "lt": "below",
    "lte": "at or below",
    "gt": "above",
    "gte": "at or above",
    "cross_above": "crossing above",
    "cross_below": "crossing below",
    "below": "below",
    "above": "above",
}


def rule_configuration_definition(
    config: dict[str, Any], path: str
) -> tuple[str, str, str] | None:
    """Name a setting only when its retained typed rule establishes its role."""
    parts = path.split(".")
    parent: Any = config
    for part in parts[:-1]:
        parent = parent[int(part)] if isinstance(parent, list) else parent[part]
    name = parts[-1]
    side = next((part for part in parts if part in {"entry", "exit"}), None)
    indicator, operator = None, None
    if "rule_spec" in parts and side and isinstance(parent, dict):
        if name == "period" and parent.get("kind") == "indicator":
            indicator = parent.get("key")
        elif name == "right":
            left = parent.get("left")
            if isinstance(left, dict) and left.get("kind") == "indicator":
                indicator, operator = left.get("key"), parent.get("operator")
    elif parts[:1] == ["resolved_strategy"] and len(parts) == 3:
        side = {"entry_rule": "entry", "exit_rule": "exit"}.get(parts[1])
        if side and isinstance(parent, dict):
            indicator, operator = parent.get("indicator"), parent.get("operator")
    elif name in {"entry_threshold", "exit_threshold"} and parts[:-1] in (
        [],
        ["parameters"],
    ):
        side = name.removesuffix("_threshold")
        rules = parent.get("rule_spec", {})
        group = rules.get(side, {}) if isinstance(rules, dict) else {}
        conditions = group.get("conditions") if isinstance(group, dict) else None
        if isinstance(conditions, list) and len(conditions) == 1:
            condition = conditions[0]
            left = condition.get("left") if isinstance(condition, dict) else None
            if (
                isinstance(left, dict)
                and left.get("kind") == "indicator"
                and condition.get("right") == parent[name]
                and parent.get("indicator") == left.get("key")
            ):
                indicator, operator = left.get("key"), condition.get("operator")
    spec = EXECUTABLE_INDICATORS.get(indicator) if isinstance(indicator, str) else None
    if not spec or not side:
        return None
    if name == "period" and any(
        parameter.key == "indicator_period" for parameter in spec.parameter_schema
    ):
        return (
            "count",
            f"Observed bars used to compute {indicator.upper()} for the retained {side} rule",
            "indicator_observation_window",
        )
    if (
        name in {"right", "threshold", "entry_threshold", "exit_threshold"}
        and indicator == "rsi"
        and isinstance(operator, str)
        and operator in RULE_COMPARISONS
    ):
        return (
            "indicator_points",
            f"Retained {side} rule RSI index level: RSI {RULE_COMPARISONS[operator]} this threshold; not a return percentage",
            "configured_indicator_threshold",
        )
    return None


CONFIG_DEFINITIONS = {
    "starting_capital": (
        "starting_capital",
        "currency",
        "Money invested initially; separate from periodic contributions",
    ),
    "initial_capital": (
        "starting_capital",
        "currency",
        "Money invested initially; separate from periodic contributions",
    ),
    "contribution": (
        "recurring_contribution",
        "currency",
        "Money added each contribution period; not the initial seed",
    ),
    "recurring_contribution": (
        "recurring_contribution",
        "currency",
        "Money added each contribution period; not the initial seed",
    ),
    "fee_bps": ("fee_bps", "basis_points", "Configured fee rate for each execution"),
    "slippage_bps": (
        "slippage_bps",
        "basis_points",
        "Configured slippage rate for each execution",
    ),
    "indicator_period": (
        "indicator_period",
        "count",
        "Number of observations used by the configured indicator",
    ),
    "fast_period": (
        "fast_period",
        "count",
        "Configured fast moving-average observation count",
    ),
    "slow_period": (
        "slow_period",
        "count",
        "Configured slow moving-average observation count",
    ),
    "rsi_period": ("rsi_period", "count", "Configured RSI observation count"),
}

FACT_PRESENTATIONS = {
    "win_rate": ["fraction_as_percent"],
    "observed_ratio": ["fraction_as_percent"],
    "max_drawdown_pct": ["absolute_magnitude"],
    "delta_vs_benchmark_pct": ["absolute_magnitude"],
    "fee_bps": ["basis_points_as_percentage_points"],
    "slippage_bps": ["basis_points_as_percentage_points"],
}
