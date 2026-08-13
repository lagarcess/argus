"""How a launch payload gets its numbers: sizing mode, capital roles, seed.

Split out of stages/execute.py so the money a run is handed has one small home
next to the plan contract it must satisfy, rather than living inside the
execution loop.
"""

from __future__ import annotations

from typing import Any


def _resolve_sizing_mode(optional_parameters: dict[str, Any]) -> str:
    position_size = _resolve_position_size(optional_parameters)
    if position_size is not None:
        return "position_size"
    return "capital_amount"


def _resolve_capital_amount(
    strategy: dict[str, Any],
    optional_parameters: dict[str, Any],
    strategy_type: str,
) -> float | None:
    strategy_capital = _resolve_strategy_capital_amount(strategy)
    if strategy_capital is not None:
        return strategy_capital
    if strategy_type == "dca_accumulation":
        # The recurring contribution has one source. Starting capital is the
        # plan's other role and may never be spent as a contribution.
        return _resolve_nested_strategy_capital_amount(strategy)
    value = _resolve_optional_value(optional_parameters, "initial_capital")
    if value is None:
        return 1000.0
    return _as_optional_float(value)


def _resolve_dca_starting_capital(optional_parameters: dict[str, Any]) -> float:
    """The seed the plan buys with on day one.

    Only a seed the user actually stated counts. The shared bankroll default
    belongs to one-time positions; a recurring plan whose seed nobody named
    starts at $0 and its first contribution is the seed.
    """
    entry = optional_parameters.get("initial_capital")
    if not isinstance(entry, dict) or str(entry.get("source") or "") != "user":
        return 0.0
    value = _as_optional_float(entry.get("value"))
    return value if value is not None and value > 0.0 else 0.0


def _resolve_strategy_capital_amount(strategy: dict[str, Any]) -> float | None:
    return _as_optional_float(strategy.get("capital_amount"))


def _resolve_nested_strategy_capital_amount(strategy: dict[str, Any]) -> float | None:
    extra_parameters = strategy.get("extra_parameters")
    if not isinstance(extra_parameters, dict):
        return None
    for key in ("capital_amount", "recurring_amount", "contribution_amount"):
        amount = _as_optional_float(extra_parameters.get(key))
        if amount is not None:
            return amount
    return None


def _resolve_position_size(optional_parameters: dict[str, Any]) -> float | None:
    value = _resolve_optional_value(optional_parameters, "position_size")
    return _as_optional_float(value)


def _resolve_optional_value(
    optional_parameters: dict[str, Any],
    field_name: str,
    *,
    default: Any = None,
) -> Any:
    value = optional_parameters.get(field_name, default)
    if isinstance(value, dict) and "value" in value:
        return value.get("value")
    return value


def _as_optional_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
