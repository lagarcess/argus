from __future__ import annotations

from typing import Any

from argus.agent_runtime.state.models import StrategySummary
from argus.domain.backtesting.rules import (
    canonicalize_rule_spec,
    rule_spec_from_moving_average_crossover_rules,
    rule_spec_from_signal_rule,
    validate_rule_spec,
)
from argus.domain.indicators import (
    executable_indicator_spec,
    normalize_indicator_parameters,
)

_BASE_INDICATOR_PARAMETER_KEYS = frozenset(
    {
        "indicator",
        "indicator_period",
        "entry_threshold",
        "exit_threshold",
    }
)


def strategy_rule(
    strategy: StrategySummary | dict[str, Any],
    side: str,
) -> dict[str, Any] | None:
    payload = _strategy_payload(strategy)
    direct = payload.get("entry_rule" if side == "entry" else "exit_rule")
    if isinstance(direct, dict) and direct:
        return dict(direct)
    extra_parameters = payload.get("extra_parameters")
    if not isinstance(extra_parameters, dict):
        return None
    nested = extra_parameters.get("entry_rule" if side == "entry" else "exit_rule")
    if isinstance(nested, dict) and nested:
        return dict(nested)
    return None


def rule_spec_from_strategy(
    strategy: StrategySummary | dict[str, Any],
) -> dict[str, Any] | None:
    payload = _strategy_payload(strategy)
    direct = payload.get("rule_spec")
    if isinstance(direct, dict) and direct:
        return dict(direct)
    extra_parameters = payload.get("extra_parameters")
    if not isinstance(extra_parameters, dict):
        return None
    nested = extra_parameters.get("rule_spec")
    if isinstance(nested, dict) and nested:
        return dict(nested)
    return None


def executable_rule_spec_from_strategy(
    strategy: StrategySummary | dict[str, Any],
) -> dict[str, Any] | None:
    rule_spec = rule_spec_from_strategy(strategy)
    if rule_spec is not None:
        try:
            validate_rule_spec(rule_spec)
        except ValueError:
            try:
                converted = rule_spec_from_signal_rule(rule_spec)
                return canonicalize_rule_spec(converted) if converted else None
            except (TypeError, ValueError):
                return None
        return canonicalize_rule_spec(rule_spec)

    try:
        generated = rule_spec_from_moving_average_crossover_rules(
            entry_rule=strategy_rule(strategy, "entry"),
            exit_rule=strategy_rule(strategy, "exit"),
        )
        return canonicalize_rule_spec(generated) if generated else None
    except (TypeError, ValueError):
        pass

    try:
        generated = rule_spec_from_signal_rule(strategy_rule(strategy, "entry"))
        return canonicalize_rule_spec(generated) if generated else None
    except (TypeError, ValueError):
        return None


def indicator_threshold_rule(
    strategy: StrategySummary | dict[str, Any],
    side: str,
) -> dict[str, Any] | None:
    raw_parameters = indicator_parameters_from_strategy(strategy)
    if not raw_parameters:
        return None
    indicator = raw_parameters.get("indicator")
    try:
        parameters = normalize_indicator_parameters(
            str(indicator or "rsi"),
            raw_parameters,
        )
    except ValueError:
        return None
    threshold_key = "entry_threshold" if side == "entry" else "exit_threshold"
    threshold = parameters.get(threshold_key)
    if threshold is None:
        return None
    return {
        "indicator": parameters["indicator"],
        "operator": "below" if side == "entry" else "above",
        "period": int(parameters["indicator_period"]),
        "threshold": float(threshold),
    }


def indicator_parameters_from_strategy(
    strategy: StrategySummary | dict[str, Any],
) -> dict[str, Any]:
    payload = _strategy_payload(strategy)
    extra_parameters = payload.get("extra_parameters")
    if not isinstance(extra_parameters, dict):
        return {}

    raw_parameters = extra_parameters.get("indicator_parameters")
    parameters = dict(raw_parameters) if isinstance(raw_parameters, dict) else {}
    indicator = _indicator_key_from_parameters(
        strategy_type=payload.get("strategy_type"),
        extra_parameters=extra_parameters,
        nested_parameters=parameters,
    )
    if indicator is not None:
        parameters["indicator"] = indicator

    for key in _indicator_parameter_keys(indicator):
        value = extra_parameters.get(key)
        if value is not None:
            parameters[key] = value
    return parameters


def opposite_moving_average_crossover_rule(
    rule: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if rule is None or rule.get("type") != "moving_average_crossover":
        return None
    opposite = dict(rule)
    opposite["direction"] = (
        "bearish" if rule.get("direction") == "bullish" else "bullish"
    )
    return opposite


def moving_average_crossover_text(rule: dict[str, Any] | None) -> str | None:
    if rule is None or rule.get("type") != "moving_average_crossover":
        return None
    fast_period = _int_or_none(rule.get("fast_period"))
    slow_period = _int_or_none(rule.get("slow_period"))
    if fast_period is None or slow_period is None:
        return None
    fast_indicator = str(rule.get("fast_indicator") or "sma").upper()
    slow_indicator = str(rule.get("slow_indicator") or fast_indicator).upper()
    direction = "below" if rule.get("direction") == "bearish" else "above"
    return (
        f"{fast_period}-day {fast_indicator} crosses {direction} "
        f"{slow_period}-day {slow_indicator}"
    )


def _strategy_payload(strategy: StrategySummary | dict[str, Any]) -> dict[str, Any]:
    if isinstance(strategy, StrategySummary):
        return strategy.model_dump(mode="python")
    return dict(strategy)


def _indicator_key_from_parameters(
    *,
    strategy_type: Any,
    extra_parameters: dict[str, Any],
    nested_parameters: dict[str, Any],
) -> str | None:
    raw_indicator = extra_parameters.get("indicator") or nested_parameters.get(
        "indicator"
    )
    if isinstance(raw_indicator, str) and raw_indicator.strip():
        spec = executable_indicator_spec(raw_indicator.strip())
        return spec.key if spec is not None else raw_indicator.strip()
    raw_strategy_type = extra_parameters.get("raw_strategy_type")
    if isinstance(raw_strategy_type, str) and raw_strategy_type.strip():
        spec = executable_indicator_spec(raw_strategy_type.strip())
        if spec is not None:
            return spec.key
    if isinstance(strategy_type, str) and strategy_type.strip():
        spec = executable_indicator_spec(strategy_type.strip())
        if spec is not None:
            return spec.key
    return None


def _indicator_parameter_keys(indicator: str | None) -> set[str]:
    keys = set(_BASE_INDICATOR_PARAMETER_KEYS)
    spec = executable_indicator_spec(indicator or "")
    if spec is not None:
        keys.update(parameter.key for parameter in spec.parameter_schema)
    return keys


def _int_or_none(value: Any) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None
