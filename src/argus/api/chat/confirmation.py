from __future__ import annotations

from datetime import date
from typing import Any
from uuid import uuid4

from argus.agent_runtime.confirmation_artifacts import (
    confirmation_id_from_payload,
    stable_payload_hash,
    validate_confirmation_execution_payload,
)
from argus.agent_runtime.strategy_contract import (
    display_strategy_slug,
    display_strategy_type,
    executable_strategy_type,
    resolve_date_range,
)
from argus.domain.engine_launch.display import format_timeframe_data_label


def runtime_confirmation_card(
    runtime_result: dict[str, Any],
    *,
    confirmation_id: str | None = None,
    conversation_id: str | None = None,
    format_confirmation_period_func: Any | None = None,
    language: str = "en",
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

    launch_payload = payload.get("launch_payload")
    if not isinstance(launch_payload, dict):
        launch_payload = {}
    assumptions = _confirmation_assumptions(
        strategy=strategy,
        optional_parameters=optional_parameters,
        launch_payload=launch_payload,
        language=language,
    )
    summary_period = _confirmation_period_without_parentheses(date_range)
    summary = _confirmation_summary(
        assets=assets,
        strategy=strategy,
        strategy_label=strategy_label,
        period=summary_period,
    )
    active_confirmation_id = confirmation_id_from_payload(
        payload,
        fallback=confirmation_id or f"confirmation-{uuid4()}",
    )
    execution_validation = validate_confirmation_execution_payload(payload)
    is_ready_to_run = execution_validation.executable
    owner_conversation_id = conversation_id.strip() if conversation_id else None
    action_payload = {
        "confirmation_id": active_confirmation_id,
        "artifact_id": active_confirmation_id,
        "launch_payload_hash": stable_payload_hash(
            execution_validation.launch_payload
        ),
    }
    if owner_conversation_id:
        action_payload["conversation_id"] = owner_conversation_id
    actions = [
        {
            "id": "change-dates",
            "type": "change_dates",
            "label": "Change dates",
            "presentation": "confirmation",
            "payload": action_payload,
        },
        {
            "id": "change-asset",
            "type": "change_asset",
            "label": "Change asset",
            "presentation": "confirmation",
            "payload": action_payload,
        },
        {
            "id": "adjust-assumptions",
            "type": "adjust_assumptions",
            "label": "Adjust assumptions",
            "presentation": "confirmation",
            "payload": action_payload,
        },
        {
            "id": "cancel-confirmation",
            "type": "cancel_confirmation",
            "label": "Cancel",
            "presentation": "confirmation",
            "payload": action_payload,
        },
    ]
    if is_ready_to_run:
        actions.insert(
            0,
            {
                "id": "run-backtest",
                "type": "run_backtest",
                "label": "Run backtest",
                "presentation": "confirmation",
                "payload": action_payload,
            },
        )
    return {
        "confirmation_id": active_confirmation_id,
        "confirmation_state": "active",
        "title": title,
        "statusLabel": "Ready to run" if is_ready_to_run else "Needs change",
        "summary": summary,
        "rows": rows,
        "assumptions": assumptions,
        "actions": actions,
    }


def _confirmation_assumptions(
    *,
    strategy: dict[str, Any],
    optional_parameters: dict[str, Any],
    launch_payload: dict[str, Any] | None = None,
    language: str = "en",
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
        assumptions.append(format_timeframe_data_label(timeframe, language=language))
    fees = _optional_parameter_value(optional_parameters, "fees")
    if fees in (0, 0.0, "0", "0.0"):
        assumptions.append("No fees")
    slippage = _optional_parameter_value(optional_parameters, "slippage")
    if slippage in (0, 0.0, "0", "0.0"):
        assumptions.append("No slippage")
    benchmark_assumption = _confirmation_benchmark_assumption(
        strategy=strategy,
        optional_parameters=optional_parameters,
        launch_payload=launch_payload or {},
    )
    if benchmark_assumption:
        assumptions.append(benchmark_assumption)
    return assumptions


def _confirmation_benchmark_assumption(
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
            return f"Benchmark: {value.strip().upper()}"
    asset_class = strategy.get("asset_class")
    if asset_class == "crypto":
        return "Benchmark: BTC"
    if asset_class == "equity":
        return "Benchmark: SPY"
    return None


def _confirmation_summary(
    *,
    assets: str,
    strategy: dict[str, Any],
    strategy_label: str,
    period: str,
) -> str:
    strategy_type = executable_strategy_type(strategy)
    if strategy_type == "buy_and_hold":
        return f"Ready to test buy-and-hold for {assets} over {period}."
    if _strategy_type_uses_cadence(strategy_type):
        return f"Ready to test recurring buys for {assets} over {period}."
    return f"Ready to test {assets} with {_summary_strategy_phrase(strategy_label)} over {period}."


def _summary_strategy_phrase(strategy_label: str) -> str:
    phrases = {
        "RSI Threshold": "an RSI threshold",
        "Dip Buying": "a dip-buying rule",
        "Indicator Threshold": "an indicator threshold",
        "Signal Strategy": "a signal strategy",
        "Moving Average Crossover": "a moving-average crossover",
    }
    return phrases.get(strategy_label, strategy_label.strip().lower())


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
