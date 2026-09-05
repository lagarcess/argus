"""Language-neutral confirmation facts shared by cards and artifact answers."""

from __future__ import annotations

from typing import Any

from argus.agent_runtime.strategy_contract import executable_strategy_type
from argus.domain.backtesting.config import (
    _execution_realism_feature_enabled,
    _normalize_execution_realism,
)
from argus.domain.dca_capital import supported_contribution_period


def confirmation_display_facts(
    *,
    strategy: dict[str, Any],
    optional_parameters: dict[str, Any],
    launch_payload: dict[str, Any],
) -> dict[str, Any]:
    facts: dict[str, Any] = {}
    strategy_type = executable_strategy_type(strategy)
    capital = confirmation_display_capital(
        strategy=strategy,
        optional_parameters=optional_parameters,
        launch_payload=launch_payload,
        strategy_type=strategy_type,
    )
    if strategy_type_uses_cadence(strategy_type):
        facts["starting_capital"] = confirmation_dca_starting_capital(optional_parameters)
        if capital is not None:
            facts["recurring_contribution"] = capital
        period = supported_contribution_period(strategy.get("cadence"))
        if period is not None:
            facts["contribution_period"] = period
    elif capital is not None:
        facts["capital"] = capital
    timeframe = _optional_parameter_value(optional_parameters, "timeframe")
    if timeframe is None:
        timeframe = strategy.get("timeframe") or launch_payload.get("timeframe")
    if timeframe:
        facts["timeframe"] = timeframe
    adjustment = _data_availability_adjustment(strategy)
    if adjustment is not None:
        facts["data_through"] = adjustment.get("through")
    costs = _confirmation_execution_costs(
        strategy=strategy,
        optional_parameters=optional_parameters,
        launch_payload=launch_payload,
    )
    if costs is not None:
        facts.update(costs)
    else:
        for key in ("fees", "slippage"):
            value = _optional_parameter_value(optional_parameters, key)
            if value is not None:
                facts[key] = value
    benchmark = _confirmation_benchmark_symbol(
        strategy=strategy,
        optional_parameters=optional_parameters,
        launch_payload=launch_payload,
    )
    if benchmark:
        facts["benchmark_symbol"] = benchmark
    return facts


def confirmation_display_capital(
    *,
    strategy: dict[str, Any],
    optional_parameters: dict[str, Any],
    launch_payload: dict[str, Any],
    strategy_type: str,
) -> float | None:
    strategy_capital = _numeric_money_value(strategy.get("capital_amount"))
    if strategy_type_uses_cadence(strategy_type):
        return strategy_capital
    return (
        strategy_capital
        or _numeric_money_value(
            _optional_parameter_value(optional_parameters, "initial_capital")
        )
        or _numeric_money_value(launch_payload.get("capital_amount"))
        or _numeric_money_value(launch_payload.get("starting_capital"))
    )


def confirmation_dca_starting_capital(optional_parameters: dict[str, Any]) -> float:
    """Only a stated seed counts; the recurring-plan default is zero."""
    entry = optional_parameters.get("initial_capital")
    if not isinstance(entry, dict) or str(entry.get("source") or "") != "user":
        return 0.0
    value = entry.get("value")
    if not isinstance(value, int | float) or isinstance(value, bool) or value < 0:
        return 0.0
    return float(value)


def strategy_type_uses_cadence(strategy_type: str) -> bool:
    normalized = strategy_type.strip().lower().replace("-", "_").replace(" ", "_")
    return normalized in {
        "dca_accumulation",
        "dca",
        "recurring_accumulation",
        "recurring_buys",
    }


def _numeric_money_value(value: Any) -> float | None:
    if not isinstance(value, int | float) or isinstance(value, bool):
        return None
    amount = float(value)
    return amount if amount > 0 else None


def _data_availability_adjustment(strategy: dict[str, Any]) -> dict[str, Any] | None:
    extra_parameters = strategy.get("extra_parameters")
    if not isinstance(extra_parameters, dict):
        return None
    adjustment = extra_parameters.get("data_availability_adjustment")
    if not isinstance(adjustment, dict):
        return None
    if adjustment.get("kind") not in {
        "latest_complete_daily_data",
        "latest_complete_market_data",
    }:
        return None
    through = adjustment.get("through")
    if not isinstance(through, str):
        return None
    date_range = strategy.get("date_range")
    if isinstance(date_range, dict):
        end = date_range.get("end") or date_range.get("to")
        if end not in (None, "") and str(end) != through:
            return None
    return adjustment


def _confirmation_benchmark_symbol(
    *,
    strategy: dict[str, Any],
    optional_parameters: dict[str, Any],
    launch_payload: dict[str, Any],
) -> str | None:
    for value in (
        strategy.get("comparison_baseline"),
        strategy.get("benchmark_symbol"),
        _optional_parameter_value(optional_parameters, "benchmark_symbol"),
        launch_payload.get("benchmark_symbol"),
    ):
        if isinstance(value, str) and value.strip():
            return value.strip().upper()
    if strategy.get("asset_class") == "crypto":
        return "BTC"
    if strategy.get("asset_class") == "equity":
        return "SPY"
    return None


def _confirmation_execution_costs(
    *,
    strategy: dict[str, Any],
    optional_parameters: dict[str, Any],
    launch_payload: dict[str, Any],
) -> dict[str, float] | None:
    if not _execution_realism_feature_enabled():
        return None
    launch_realism = launch_payload.get("_execution_realism")
    if isinstance(launch_realism, dict):
        try:
            realism = _normalize_execution_realism(launch_realism)
        except ValueError:
            realism = {"enabled": False, "fee_bps": 0.0, "slippage_bps": 0.0}
    else:
        realism = {"enabled": False, "fee_bps": 0.0, "slippage_bps": 0.0}
    if bool(realism["enabled"]):
        costs = {
            "fees": float(realism["fee_bps"]) / 10000.0,
            "slippage": float(realism["slippage_bps"]) / 10000.0,
        }
        if costs["fees"] > 0.0 or costs["slippage"] > 0.0:
            return costs
    extra_parameters = strategy.get("extra_parameters")
    if isinstance(extra_parameters, dict):
        costs = {
            "fees": _optional_float(extra_parameters.get("fee_rate")) or 0.0,
            "slippage": _optional_float(extra_parameters.get("slippage")) or 0.0,
        }
        if costs["fees"] > 0.0 or costs["slippage"] > 0.0:
            return costs
    costs = {
        "fees": _optional_float(_optional_parameter_value(optional_parameters, "fees"))
        or 0.0,
        "slippage": _optional_float(
            _optional_parameter_value(optional_parameters, "slippage")
        )
        or 0.0,
    }
    return costs if costs["fees"] > 0.0 or costs["slippage"] > 0.0 else None


def _optional_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_parameter_value(optional_parameters: dict[str, Any], key: str) -> Any:
    value = optional_parameters.get(key)
    return value.get("value") if isinstance(value, dict) else None
