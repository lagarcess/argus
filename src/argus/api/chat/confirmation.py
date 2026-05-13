from __future__ import annotations

from datetime import date
from typing import Any
from uuid import uuid4

from argus.agent_runtime.strategy_contract import (
    display_strategy_slug,
    display_strategy_type,
    executable_strategy_type,
    resolve_date_range,
)


def runtime_confirmation_card(
    runtime_result: dict[str, Any],
    *,
    confirmation_id: str | None = None,
    format_confirmation_period_func: Any | None = None,
) -> dict[str, Any] | None:
    if runtime_result.get("stage_outcome") != "await_approval":
        return None
    payload = runtime_result.get("confirmation_payload")
    if not isinstance(payload, dict):
        return None
    strategy = payload.get("strategy")
    if not isinstance(strategy, dict):
        return None
    optional_parameters = payload.get("optional_parameters")
    if not isinstance(optional_parameters, dict):
        optional_parameters = {}

    symbols = [
        str(symbol)
        for symbol in strategy.get("asset_universe", [])
        if str(symbol).strip()
    ]
    assets = ", ".join(symbols) if symbols else "Selected asset"
    strategy_type = display_strategy_slug(strategy)
    strategy_label = display_strategy_type(strategy)
    format_confirmation_period = (
        format_confirmation_period_func or _format_confirmation_period
    )
    date_range = format_confirmation_period(strategy.get("date_range"))
    title = f"{assets} {strategy_type}".strip()

    rows = [
        {"label": "Strategy", "value": strategy_label},
        {"label": "Assets", "value": assets},
        {"label": "Period", "value": date_range},
    ]
    canonical_strategy_type = executable_strategy_type(strategy)
    if strategy.get("cadence") and _strategy_type_uses_cadence(canonical_strategy_type):
        rows.append({"label": "Cadence", "value": str(strategy["cadence"]).title()})
    if strategy.get("entry_logic"):
        rows.append(
            {
                "label": "Buy rule",
                "value": _format_confirmation_value(strategy["entry_logic"]),
            }
        )
    if strategy.get("exit_logic"):
        rows.append(
            {
                "label": "Exit rule",
                "value": _format_confirmation_value(strategy["exit_logic"]),
            }
        )
    if strategy.get("capital_amount"):
        capital_label = (
            "Contribution"
            if _strategy_type_uses_cadence(canonical_strategy_type)
            else "Starting capital"
        )
        rows.append(
            {
                "label": capital_label,
                "value": f"${float(strategy['capital_amount']):,.0f}",
            }
        )

    assumptions = _confirmation_assumptions(
        strategy=strategy,
        optional_parameters=optional_parameters,
    )
    summary_period = _confirmation_period_without_parentheses(date_range)
    summary = (
        f"I read this as {assets} using {_article_for(strategy_type)} "
        f"{strategy_type} approach over {summary_period}."
    )
    active_confirmation_id = confirmation_id or f"confirmation-{uuid4()}"
    return {
        "confirmation_id": active_confirmation_id,
        "confirmation_state": "active",
        "title": title,
        "statusLabel": "Ready to run",
        "summary": summary,
        "rows": rows,
        "assumptions": assumptions,
        "actions": [
            {
                "id": "run-backtest",
                "type": "run_backtest",
                "label": "Run backtest",
                "presentation": "confirmation",
                "payload": {"confirmation_id": active_confirmation_id},
            },
            {
                "id": "change-dates",
                "type": "change_dates",
                "label": "Change dates",
                "presentation": "confirmation",
                "payload": {"confirmation_id": active_confirmation_id},
            },
            {
                "id": "change-asset",
                "type": "change_asset",
                "label": "Change asset",
                "presentation": "confirmation",
                "payload": {"confirmation_id": active_confirmation_id},
            },
            {
                "id": "adjust-assumptions",
                "type": "adjust_assumptions",
                "label": "Adjust assumptions",
                "presentation": "confirmation",
                "payload": {"confirmation_id": active_confirmation_id},
            },
            {
                "id": "cancel-confirmation",
                "type": "cancel_confirmation",
                "label": "Cancel",
                "presentation": "confirmation",
                "payload": {"confirmation_id": active_confirmation_id},
            },
        ],
    }


def _confirmation_assumptions(
    *,
    strategy: dict[str, Any],
    optional_parameters: dict[str, Any],
) -> list[str]:
    assumptions: list[str] = []
    strategy_type = executable_strategy_type(strategy)
    strategy_capital = strategy.get("capital_amount")
    if isinstance(strategy_capital, int | float):
        if _strategy_type_uses_cadence(strategy_type):
            assumptions.append(f"${float(strategy_capital):,.0f} recurring contribution")
        else:
            assumptions.append(f"${float(strategy_capital):,.0f} starting capital")
    initial_capital = _optional_parameter_value(optional_parameters, "initial_capital")
    if isinstance(initial_capital, int | float) and not isinstance(
        strategy_capital, int | float
    ):
        if _strategy_type_uses_cadence(strategy_type) and strategy.get("capital_amount"):
            assumptions.append(
                f"${float(strategy['capital_amount']):,.0f} recurring contribution"
            )
        else:
            assumptions.append(f"${float(initial_capital):,.0f} starting capital")
    timeframe = _optional_parameter_value(optional_parameters, "timeframe")
    if timeframe:
        assumptions.append(f"{timeframe} bars")
    fees = _optional_parameter_value(optional_parameters, "fees")
    if fees in (0, 0.0, "0", "0.0"):
        assumptions.append("No fees")
    slippage = _optional_parameter_value(optional_parameters, "slippage")
    if slippage in (0, 0.0, "0", "0.0"):
        assumptions.append("No slippage")
    asset_class = strategy.get("asset_class")
    if asset_class == "crypto":
        assumptions.append("Benchmark: BTC")
    elif asset_class == "equity":
        assumptions.append("Benchmark: SPY")
    return assumptions


def _optional_parameter_value(optional_parameters: dict[str, Any], key: str) -> Any:
    value = optional_parameters.get(key)
    if isinstance(value, dict):
        return value.get("value")
    return None


def _format_confirmation_value(value: Any) -> str:
    if isinstance(value, dict):
        start = value.get("start") or value.get("from")
        end = value.get("end") or value.get("to")
        if start and end:
            return f"{start} to {end}"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    if value is None or value == "":
        return "Default period"
    return str(value)


def _format_confirmation_period(value: Any) -> str:
    return resolve_date_range(value, today=_confirmation_today()).display


def _confirmation_period_without_parentheses(value: str) -> str:
    if "(" not in value or not value.endswith(")"):
        return value
    label, _, dates = value.partition("(")
    return f"{label.strip()}, {dates[:-1].strip()}"


def _strategy_type_uses_cadence(strategy_type: str) -> bool:
    normalized = strategy_type.strip().lower().replace("-", "_").replace(" ", "_")
    return normalized in {
        "dca",
        "dca_accumulation",
        "recurring_accumulation",
        "recurring_buys",
    }


def _article_for(value: str) -> str:
    return "an" if value[:1].lower() in {"a", "e", "i", "o", "u"} else "a"


def _confirmation_today() -> date:
    return date.today()
