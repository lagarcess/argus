from __future__ import annotations

from typing import Any

from argus.agent_runtime.state.models import StrategySummary


def draft_from_confirmation_payload(payload: dict[str, Any]) -> StrategySummary:
    strategy_values = _strategy_values(payload.get("strategy"))
    launch_values = _launch_payload_values(payload.get("launch_payload"))
    return _strategy_from_values(_preserving_merge(strategy_values, launch_values))


def draft_from_result_metadata(metadata: dict[str, Any]) -> StrategySummary:
    config = _dict(metadata.get("config_snapshot"))
    resolved_strategy = _strategy_values(config.get("resolved_strategy"))
    resolved_parameters = _dict(config.get("resolved_parameters"))
    values = dict(resolved_strategy)

    _fill_if_blank(values, "strategy_type", config.get("template"))
    _fill_if_blank(values, "asset_class", metadata.get("asset_class"))
    _fill_if_blank(
        values,
        "asset_universe",
        _symbols(config.get("symbols") or metadata.get("symbols")),
    )
    _fill_if_blank(
        values,
        "date_range",
        resolved_parameters.get("date_range") or config.get("date_range"),
    )
    _fill_if_blank(values, "timeframe", resolved_parameters.get("timeframe"))
    _fill_if_blank(values, "capital_amount", resolved_parameters.get("capital_amount"))
    _fill_if_blank(
        values,
        "capital_amount",
        resolved_parameters.get("recurring_contribution"),
    )
    _fill_if_blank(values, "cadence", resolved_parameters.get("cadence"))
    _fill_if_blank(
        values,
        "comparison_baseline",
        resolved_parameters.get("benchmark_symbol")
        or config.get("benchmark_symbol")
        or metadata.get("benchmark_symbol"),
    )

    return _strategy_from_values(values)


def draft_from_failed_launch_payload(payload: dict[str, Any]) -> StrategySummary:
    return _strategy_from_values(_launch_payload_values(payload))


def _strategy_values(value: Any) -> dict[str, Any]:
    payload = _dict(value)
    allowed = set(StrategySummary.model_fields)
    values = {
        key: field_value
        for key, field_value in payload.items()
        if key in allowed and not _blank(field_value)
    }
    if values.get("asset_universe"):
        values["asset_universe"] = _symbols(values["asset_universe"])
    if values.get("comparison_baseline"):
        values["comparison_baseline"] = _symbol(values["comparison_baseline"])
    return values


def _launch_payload_values(value: Any) -> dict[str, Any]:
    payload = _dict(value)
    values: dict[str, Any] = {}
    _fill_if_blank(values, "strategy_type", payload.get("strategy_type"))
    _fill_if_blank(values, "asset_class", payload.get("asset_class"))
    _fill_if_blank(
        values,
        "asset_universe",
        _symbols(payload.get("symbols") or payload.get("symbol")),
    )
    for field_name in (
        "timeframe",
        "date_range",
        "sizing_mode",
        "capital_amount",
        "position_size",
        "cadence",
        "entry_rule",
        "exit_rule",
        "rule_spec",
    ):
        _fill_if_blank(values, field_name, payload.get(field_name))
    _fill_if_blank(values, "comparison_baseline", payload.get("benchmark_symbol"))
    return values


def _preserving_merge(
    base: dict[str, Any],
    defaults: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(base)
    for key, value in defaults.items():
        _fill_if_blank(merged, key, value)
    return merged


def _strategy_from_values(values: dict[str, Any]) -> StrategySummary:
    allowed = set(StrategySummary.model_fields)
    payload = {
        key: value
        for key, value in values.items()
        if key in allowed and not _blank(value)
    }
    return StrategySummary.model_validate(payload)


def _fill_if_blank(values: dict[str, Any], key: str, value: Any) -> None:
    if _blank(values.get(key)) and not _blank(value):
        values[key] = _normalize_value(key, value)


def _normalize_value(key: str, value: Any) -> Any:
    if key == "asset_universe":
        return _symbols(value)
    if key == "comparison_baseline":
        return _symbol(value)
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _symbols(value: Any) -> list[str]:
    raw_values = value if isinstance(value, list) else [value]
    symbols: list[str] = []
    for item in raw_values:
        symbol = _symbol(item)
        if symbol is not None:
            symbols.append(symbol)
    return list(dict.fromkeys(symbols))


def _symbol(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    symbol = value.strip().upper().replace("-", "/")
    return symbol or None


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _blank(value: Any) -> bool:
    return value in (None, "", [], {})
