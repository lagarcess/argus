from __future__ import annotations

from datetime import date
from typing import Any

from argus.domain.backtesting.rules import (
    required_warmup_bars,
    rule_spec_from_moving_average_crossover_rules,
    validate_rule_spec,
)
from argus.domain.engine_launch.models import LaunchBacktestRequest
from argus.domain.indicators import normalize_indicator_parameters

_LAUNCH_TEMPLATE_BY_STRATEGY_TYPE: dict[str, str] = {
    "buy_and_hold": "buy_and_hold",
    "dca_accumulation": "dca_accumulation",
    "signal_strategy": "signal_strategy",
    # indicator_threshold maps explicitly to the rsi_mean_reversion engine template.
    "indicator_threshold": "rsi_mean_reversion",
}


def normalize_template_name(request: LaunchBacktestRequest) -> str:
    # Explicit map (no silent catch-all). The four LaunchStrategyType values are all
    # covered; anything unexpected fails loudly instead of being rewritten to RSI.
    template = _LAUNCH_TEMPLATE_BY_STRATEGY_TYPE.get(request.strategy_type)
    if template is None:
        raise ValueError("unsupported_strategy_type")
    return template


def validate_launch_supported(request: LaunchBacktestRequest) -> None:
    if request.risk_rules:
        raise ValueError("unsupported_risk_rules")

    if request.strategy_type not in {"indicator_threshold", "signal_strategy"}:
        return

    rule_spec = rule_spec_from_request(request)
    validate_rule_spec(rule_spec)
    _validate_rule_window(request=request, rule_spec=rule_spec)


def indicator_threshold_parameters(request: LaunchBacktestRequest) -> dict[str, Any]:
    parameters = _indicator_threshold_parameters(request)
    if parameters is None:
        raise ValueError("unsupported_indicator_threshold")
    return parameters


def rule_spec_from_request(request: LaunchBacktestRequest) -> dict[str, Any]:
    if request.rule_spec is not None:
        return request.rule_spec
    if request.strategy_type == "indicator_threshold":
        parameters = indicator_threshold_parameters(request)
        rule_spec = parameters.get("rule_spec")
        if isinstance(rule_spec, dict):
            return rule_spec
    if request.entry_rule and request.exit_rule:
        rule_spec = rule_spec_from_moving_average_crossover_rules(
            entry_rule=request.entry_rule,
            exit_rule=request.exit_rule,
        )
        if rule_spec is not None:
            return rule_spec
    raise ValueError("missing_rule_group")


def _validate_rule_window(
    *,
    request: LaunchBacktestRequest,
    rule_spec: dict[str, Any],
) -> None:
    warmup_bars = required_warmup_bars(rule_spec)
    if warmup_bars <= 0:
        return
    if _estimated_window_bars(request) <= warmup_bars:
        raise ValueError("indicator_data_insufficient")


def _estimated_window_bars(request: LaunchBacktestRequest) -> int:
    try:
        start = date.fromisoformat(request.date_range.start)
        end = date.fromisoformat(request.date_range.end)
    except ValueError as exc:
        raise ValueError("invalid_date_range") from exc

    calendar_days = max((end - start).days, 0)
    timeframe = request.timeframe.strip().lower()
    if timeframe in {"1d", "1day", "daily"}:
        return max(int(calendar_days * 5 / 7), 1)

    intraday_hours = {
        "1h": 1,
        "2h": 2,
        "4h": 4,
        "6h": 6,
        "12h": 12,
    }
    hours = intraday_hours.get(timeframe)
    if hours is None:
        raise ValueError("unsupported_timeframe")
    return max(int(calendar_days * (24 / hours)), 1)


def _indicator_threshold_parameters(
    request: LaunchBacktestRequest,
) -> dict[str, Any] | None:
    if not request.entry_rule or not request.exit_rule:
        return None

    entry_indicator = str(request.entry_rule.get("indicator") or "rsi")
    exit_indicator = str(request.exit_rule.get("indicator") or entry_indicator)
    entry_operator = str(request.entry_rule.get("operator") or "").strip().lower()
    exit_operator = str(request.exit_rule.get("operator") or "").strip().lower()
    if entry_operator != "below" or exit_operator != "above":
        return None
    if entry_indicator.strip().lower() != exit_indicator.strip().lower():
        return None

    entry_period = request.entry_rule.get("period") or request.entry_rule.get(
        "indicator_period"
    )
    exit_period = request.exit_rule.get("period") or request.exit_rule.get(
        "indicator_period"
    )
    if entry_period is not None and exit_period is not None:
        try:
            if int(float(entry_period)) != int(float(exit_period)):
                return None
        except (TypeError, ValueError):
            return None

    indicator_inputs = {
        **request.parameters,
        "entry_threshold": request.entry_rule.get("threshold"),
        "exit_threshold": request.exit_rule.get("threshold"),
    }
    if entry_period is not None or exit_period is not None:
        indicator_inputs["indicator_period"] = entry_period or exit_period

    try:
        parameters = normalize_indicator_parameters(
            entry_indicator,
            indicator_inputs,
        )
    except ValueError:
        return None
    period = int(parameters["indicator_period"])
    indicator = str(parameters["indicator"])
    parameters["rule_spec"] = {
        "entry": {
            "conditions": [
                {
                    "left": {
                        "kind": "indicator",
                        "key": indicator,
                        "period": period,
                    },
                    "operator": "lte",
                    "right": float(parameters["entry_threshold"]),
                }
            ]
        },
        "exit": {
            "conditions": [
                {
                    "left": {
                        "kind": "indicator",
                        "key": indicator,
                        "period": period,
                    },
                    "operator": "gte",
                    "right": float(parameters["exit_threshold"]),
                }
            ]
        },
    }
    return parameters

