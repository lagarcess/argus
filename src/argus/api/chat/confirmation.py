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
from argus.domain.engine_launch.display import (
    format_data_through_label,
    format_date_range_label,
    format_timeframe_data_label,
)


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
    strategy_type = _localized_strategy_slug(strategy, language=language)
    strategy_label = _localized_strategy_label(strategy, language=language)
    if format_confirmation_period_func is not None:
        date_range = format_confirmation_period_func(strategy.get("date_range"))
    else:
        date_range = _format_confirmation_period(
            strategy.get("date_range"),
            language=language,
        )
    canonical_date_range = _confirmation_date_range_payload(
        strategy.get("date_range"),
        display=date_range,
    )
    title = _confirmation_title(
        assets=assets,
        strategy_type=strategy_type,
        language=language,
    )
    launch_payload = payload.get("launch_payload")
    if not isinstance(launch_payload, dict):
        launch_payload = {}
    canonical_strategy_type = executable_strategy_type(strategy)

    rows = [
        _confirmation_row("strategy", "Strategy", strategy_label),
        _confirmation_row("assets", "Assets", assets),
        _confirmation_row("period", "Period", date_range),
    ]
    if strategy.get("cadence") and _strategy_type_uses_cadence(canonical_strategy_type):
        rows.append(
            _confirmation_row("cadence", "Cadence", str(strategy["cadence"]).title())
        )
    if strategy.get("entry_logic"):
        rows.append(
            _confirmation_row(
                "buy_rule",
                "Buy rule",
                _format_confirmation_value(strategy["entry_logic"]),
            )
        )
    if strategy.get("exit_logic"):
        rows.append(
            _confirmation_row(
                "exit_rule",
                "Exit rule",
                _format_confirmation_value(strategy["exit_logic"]),
            )
        )
    display_capital = _confirmation_display_capital(
        strategy=strategy,
        optional_parameters=optional_parameters,
        launch_payload=launch_payload,
        strategy_type=canonical_strategy_type,
    )
    if display_capital is not None:
        capital_label = (
            "Contribution"
            if _strategy_type_uses_cadence(canonical_strategy_type)
            else "Starting capital"
        )
        rows.append(
            _confirmation_row(
                "contribution"
                if _strategy_type_uses_cadence(canonical_strategy_type)
                else "starting_capital",
                capital_label,
                f"${display_capital:,.0f}",
            )
        )

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
        language=language,
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
        "launch_payload_hash": stable_payload_hash(execution_validation.launch_payload),
    }
    if owner_conversation_id:
        action_payload["conversation_id"] = owner_conversation_id
    actions = [
        {
            "id": "change-dates",
            "type": "change_dates",
            "label": "Change dates",
            "labelKey": "chat.confirmation.actions.change_dates",
            "presentation": "confirmation",
            "payload": action_payload,
        },
        {
            "id": "change-asset",
            "type": "change_asset",
            "label": "Change asset",
            "labelKey": "chat.confirmation.actions.change_asset",
            "presentation": "confirmation",
            "payload": action_payload,
        },
        {
            "id": "adjust-assumptions",
            "type": "adjust_assumptions",
            "label": "Adjust assumptions",
            "labelKey": "chat.confirmation.actions.adjust_assumptions",
            "presentation": "confirmation",
            "payload": action_payload,
        },
        {
            "id": "cancel-confirmation",
            "type": "cancel_confirmation",
            "label": "Cancel",
            "labelKey": "chat.confirmation.actions.cancel",
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
                "labelKey": "chat.confirmation.actions.run_backtest",
                "presentation": "confirmation",
                "payload": action_payload,
            },
        )
    card = {
        "confirmation_id": active_confirmation_id,
        "confirmation_state": "active",
        "title": title,
        "status": "ready_to_run" if is_ready_to_run else "needs_change",
        "statusLabel": _confirmation_status_label(
            is_ready_to_run=is_ready_to_run,
            language=language,
        ),
        "strategy_type": canonical_strategy_type,
        "summary": summary,
        "rows": rows,
        "assumptions": assumptions,
        "actions": actions,
    }
    asset_class = _confirmation_asset_class(strategy)
    if asset_class is not None:
        card["asset_class"] = asset_class
    if canonical_date_range is not None:
        card["date_range"] = canonical_date_range
    return card


def _confirmation_asset_class(strategy: dict[str, Any]) -> str | None:
    asset_class = strategy.get("asset_class")
    if asset_class in {"equity", "crypto", "currency_pair"}:
        return str(asset_class)
    return None


def _confirmation_row(key: str, label: str, value: str) -> dict[str, str]:
    return {
        "key": key,
        "label": label,
        "labelKey": f"chat.confirmation.rows.{key}",
        "value": value,
    }


def _confirmation_display_capital(
    *,
    strategy: dict[str, Any],
    optional_parameters: dict[str, Any],
    launch_payload: dict[str, Any],
    strategy_type: str,
) -> float | None:
    strategy_capital = _numeric_money_value(strategy.get("capital_amount"))
    if _strategy_type_uses_cadence(strategy_type):
        return strategy_capital
    return (
        strategy_capital
        or _numeric_money_value(
            _optional_parameter_value(optional_parameters, "initial_capital")
        )
        or _numeric_money_value(launch_payload.get("capital_amount"))
        or _numeric_money_value(launch_payload.get("starting_capital"))
    )


def _numeric_money_value(value: Any) -> float | None:
    if not isinstance(value, int | float) or isinstance(value, bool):
        return None
    amount = float(value)
    return amount if amount > 0 else None


def _confirmation_date_range_payload(
    value: Any,
    *,
    display: str,
) -> dict[str, str] | None:
    try:
        resolved = resolve_date_range(value, today=_confirmation_today())
    except (TypeError, ValueError):
        return None
    return {
        "start": resolved.start.isoformat(),
        "end": resolved.end.isoformat(),
        "display": display,
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
            assumptions.append(
                _money_assumption(
                    float(strategy_capital),
                    role="recurring_contribution",
                    language=language,
                )
            )
        else:
            assumptions.append(
                _money_assumption(
                    float(strategy_capital),
                    role="starting_capital",
                    language=language,
                )
            )
    initial_capital = _optional_parameter_value(optional_parameters, "initial_capital")
    if isinstance(initial_capital, int | float) and not isinstance(
        strategy_capital, int | float
    ):
        if _strategy_type_uses_cadence(strategy_type) and strategy.get("capital_amount"):
            assumptions.append(
                _money_assumption(
                    float(strategy["capital_amount"]),
                    role="recurring_contribution",
                    language=language,
                )
            )
        else:
            assumptions.append(
                _money_assumption(
                    float(initial_capital),
                    role="starting_capital",
                    language=language,
                )
            )
    timeframe = _optional_parameter_value(optional_parameters, "timeframe")
    if timeframe:
        assumptions.append(format_timeframe_data_label(timeframe, language=language))
    data_through_assumption = _data_through_assumption(strategy, language=language)
    if data_through_assumption:
        assumptions.append(data_through_assumption)
    fees = _optional_parameter_value(optional_parameters, "fees")
    if fees in (0, 0.0, "0", "0.0"):
        assumptions.append("Sin comisiones" if _is_spanish(language) else "No fees")
    slippage = _optional_parameter_value(optional_parameters, "slippage")
    if slippage in (0, 0.0, "0", "0.0"):
        assumptions.append(
            "Sin deslizamiento" if _is_spanish(language) else "No slippage"
        )
    benchmark_assumption = _confirmation_benchmark_assumption(
        strategy=strategy,
        optional_parameters=optional_parameters,
        launch_payload=launch_payload or {},
        language=language,
    )
    if benchmark_assumption:
        assumptions.append(benchmark_assumption)
    return assumptions


def _data_through_assumption(
    strategy: dict[str, Any],
    *,
    language: str,
) -> str | None:
    adjustment = _data_availability_adjustment(strategy)
    if adjustment is None:
        return None
    return format_data_through_label(adjustment.get("through"), language=language) or None


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
    if not _data_adjustment_matches_strategy_end(strategy, through=through):
        return None
    return adjustment


def _data_adjustment_matches_strategy_end(
    strategy: dict[str, Any],
    *,
    through: str,
) -> bool:
    date_range = strategy.get("date_range")
    if not isinstance(date_range, dict):
        return True
    end = date_range.get("end") or date_range.get("to")
    return end in (None, "") or str(end) == through


def _confirmation_benchmark_assumption(
    *,
    strategy: dict[str, Any],
    optional_parameters: dict[str, Any],
    launch_payload: dict[str, Any],
    language: str = "en",
) -> str | None:
    for value in (
        strategy.get("comparison_baseline"),
        strategy.get("benchmark_symbol"),
        _optional_parameter_value(optional_parameters, "benchmark_symbol"),
        launch_payload.get("benchmark_symbol"),
    ):
        if isinstance(value, str) and value.strip():
            return _benchmark_assumption(value.strip().upper(), language=language)
    asset_class = strategy.get("asset_class")
    if asset_class == "crypto":
        return _benchmark_assumption("BTC", language=language)
    if asset_class == "equity":
        return _benchmark_assumption("SPY", language=language)
    return None


def _confirmation_summary(
    *,
    assets: str,
    strategy: dict[str, Any],
    strategy_label: str,
    period: str,
    language: str = "en",
) -> str:
    strategy_type = executable_strategy_type(strategy)
    if _is_spanish(language):
        if strategy_type == "buy_and_hold":
            return f"Listo para probar comprar y mantener {assets} del {period}."
        if _strategy_type_uses_cadence(strategy_type):
            return f"Listo para probar compras recurrentes de {assets} del {period}."
        return (
            f"Listo para probar {assets} con "
            f"{_summary_strategy_phrase(strategy_label, language=language)} del {period}."
        )
    if strategy_type == "buy_and_hold":
        return f"Ready to test buy-and-hold for {assets} over {period}."
    if _strategy_type_uses_cadence(strategy_type):
        return f"Ready to test recurring buys for {assets} over {period}."
    return (
        f"Ready to test {assets} with "
        f"{_summary_strategy_phrase(strategy_label, language=language)} over {period}."
    )


def _summary_strategy_phrase(strategy_label: str, *, language: str = "en") -> str:
    if _is_spanish(language):
        phrases = {
            "Umbral RSI": "un umbral RSI",
            "Compra en caidas": "una regla de compra en caidas",
            "Umbral de indicador": "un umbral de indicador",
            "Estrategia de senales": "una estrategia de senales",
            "Cruce de medias moviles": "un cruce de medias moviles",
        }
        return phrases.get(strategy_label, strategy_label.strip().lower())
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


def _format_confirmation_period(value: Any, *, language: str = "en") -> str:
    resolved = resolve_date_range(value, today=_confirmation_today())
    if _is_spanish(language):
        return format_date_range_label(resolved.start, resolved.end, language=language)
    return resolved.display


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


def _localized_strategy_label(
    strategy: dict[str, Any],
    *,
    language: str,
) -> str:
    if not _is_spanish(language):
        return display_strategy_type(strategy)
    labels = {
        "buy_and_hold": "Comprar y mantener",
        "dca_accumulation": "Compras recurrentes",
        "indicator_threshold": "Umbral de indicador",
        "signal_strategy": "Estrategia de senales",
    }
    return labels.get(executable_strategy_type(strategy), display_strategy_type(strategy))


def _localized_strategy_slug(
    strategy: dict[str, Any],
    *,
    language: str,
) -> str:
    if not _is_spanish(language):
        return display_strategy_slug(strategy)
    label = _localized_strategy_label(strategy, language=language)
    return label[:1].lower() + label[1:]


def _confirmation_title(*, assets: str, strategy_type: str, language: str) -> str:
    if _is_spanish(language):
        return f"{assets}: {strategy_type[:1].upper()}{strategy_type[1:]}".strip()
    return f"{assets} {strategy_type}".strip()


def _confirmation_status_label(*, is_ready_to_run: bool, language: str) -> str:
    if _is_spanish(language):
        return "Listo para ejecutar" if is_ready_to_run else "Necesita cambios"
    return "Ready to run" if is_ready_to_run else "Needs change"


def _money_assumption(value: float, *, role: str, language: str) -> str:
    if _is_spanish(language):
        label = (
            "aporte recurrente"
            if role == "recurring_contribution"
            else "capital inicial"
        )
        return f"${value:,.0f} {label}"
    label = (
        "recurring contribution"
        if role == "recurring_contribution"
        else "starting capital"
    )
    return f"${value:,.0f} {label}"


def _benchmark_assumption(symbol: str, *, language: str) -> str:
    prefix = "Referencia" if _is_spanish(language) else "Benchmark"
    return f"{prefix}: {symbol}"


def _is_spanish(language: str) -> bool:
    return (language or "en").lower().startswith("es")


def _confirmation_today() -> date:
    return date.today()
