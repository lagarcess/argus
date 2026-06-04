from __future__ import annotations

from typing import Any

from argus.agent_runtime.capabilities.contract import CapabilityContract
from argus.agent_runtime.rule_specs import executable_rule_spec_from_strategy
from argus.agent_runtime.state.models import StrategySummary
from argus.agent_runtime.strategy_contract import (
    executable_strategy_type,
    has_partial_explicit_date_range,
)


def missing_required_fields_for_strategy(
    strategy: StrategySummary,
    *,
    contract: CapabilityContract,
) -> list[str]:
    strategy_type = executable_strategy_type(strategy)
    if strategy_type == "signal_strategy" and not strategy_has_executable_signal_rule(
        strategy
    ):
        payload = strategy.model_dump(mode="python")
        missing: list[str] = []
        for field_name in ("strategy_thesis", "asset_universe"):
            value = payload.get(field_name)
            if isinstance(value, list):
                if not value:
                    missing.append(field_name)
                continue
            if value is None or value == "":
                missing.append(field_name)
        missing.append("entry_logic")
        return list(dict.fromkeys(missing))

    required = list(contract.required_fields)
    if strategy_type == "dca_accumulation":
        required = [
            field_name
            for field_name in required
            if field_name not in {"entry_logic", "exit_logic"}
        ]
        if strategy.capital_amount is None:
            required.append("capital_amount")
        if strategy.cadence is None:
            required.append("cadence")
    if strategy_type == "buy_and_hold":
        required = ["asset_universe", "date_range"]
    if strategy_type == "signal_strategy":
        required = [
            field_name for field_name in required if field_name != "exit_logic"
        ]

    missing: list[str] = []
    payload = strategy.model_dump(mode="python")
    for field_name in required:
        value = payload.get(field_name)
        if isinstance(value, list):
            if not value:
                missing.append(field_name)
        elif field_name == "date_range" and has_partial_explicit_date_range(value):
            missing.append(field_name)
        elif value is None or value == "":
            missing.append(field_name)
    if strategy_type == "signal_strategy" and not strategy_has_executable_signal_rule(
        strategy
    ):
        missing.append("entry_logic")
    return list(dict.fromkeys(missing))


def strategy_has_executable_signal_rule(strategy: StrategySummary) -> bool:
    return valid_rule_spec_from_strategy(strategy) is not None


def valid_rule_spec_from_strategy(strategy: StrategySummary) -> dict[str, Any] | None:
    return executable_rule_spec_from_strategy(strategy)
