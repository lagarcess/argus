from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from argus.agent_runtime.rule_specs import (
    indicator_threshold_rule,
    opposite_moving_average_crossover_rule,
    strategy_rule,
)
from argus.agent_runtime.state.models import StrategySummary

RuntimeLocale = Literal["en", "es-419"]


@dataclass(frozen=True)
class LocaleCatalog:
    optional_parameter_labels: dict[str, str]
    indicator_rule_template: str
    moving_average_rule_template: str
    actions: dict[str, str]
    indicator_directions: dict[str, tuple[str, str]]
    moving_average_directions: dict[str, str]
    day_unit_singular: str
    day_unit_plural: str
    unknown_setting_label: str


_CATALOGS: dict[RuntimeLocale, LocaleCatalog] = {
    "en": LocaleCatalog(
        optional_parameter_labels={},
        indicator_rule_template="{action} when {indicator_label} {direction} {threshold} {suffix}",
        moving_average_rule_template=(
            "{action} when {fast_period}-{fast_unit} {fast_indicator} "
            "{direction} {slow_period}-{slow_unit} {slow_indicator}"
        ),
        actions={
            "entry": "Buy",
            "exit": "Sell",
        },
        indicator_directions={
            "above": ("rises to", "or above"),
            "below": ("drops to", "or below"),
        },
        moving_average_directions={
            "bullish": "crosses above",
            "bearish": "crosses below",
        },
        day_unit_singular="day",
        day_unit_plural="day",
        unknown_setting_label="Unnamed setting",
    ),
    "es-419": LocaleCatalog(
        optional_parameter_labels={
            "initial_capital": "capital inicial",
            "timeframe": "temporalidad",
            "fees": "comisiones",
            "slippage": "deslizamiento",
            "benchmark": "referencia",
            "comparison_baseline": "referencia",
        },
        indicator_rule_template="{action} cuando {indicator_label} {direction} {threshold} {suffix}",
        moving_average_rule_template=(
            "{action} cuando {fast_indicator} de {fast_period} {fast_unit} "
            "{direction} {slow_indicator} de {slow_period} {slow_unit}"
        ),
        actions={
            "entry": "Comprar",
            "exit": "Vender",
        },
        indicator_directions={
            "above": ("sube a", "o más"),
            "below": ("cae a", "o menos"),
        },
        moving_average_directions={
            "bullish": "cruza por encima de",
            "bearish": "cruza por debajo de",
        },
        day_unit_singular="día",
        day_unit_plural="días",
        unknown_setting_label="supuesto",
    ),
}


def runtime_locale(language: str | None) -> RuntimeLocale:
    normalized = str(language or "").strip().lower()
    return "es-419" if normalized.startswith("es") else "en"


def optional_parameter_display_label(
    field_name: str,
    label: Any,
    *,
    language: str | None,
) -> str:
    locale = runtime_locale(language)
    normalized_field = str(field_name or "").strip()
    catalog = _CATALOGS[locale]
    localized = catalog.optional_parameter_labels.get(normalized_field)
    if localized:
        return localized

    normalized_label = str(label or "").strip()
    if locale == "en" and normalized_label:
        return normalized_label

    fallback = normalized_field.replace("_", " ").strip()
    return fallback or catalog.unknown_setting_label


def asset_universe_operation_clarification_message(*, language: str | None) -> str:
    locale = runtime_locale(language)
    if locale == "es-419":
        return (
            "¿Quieres agregar esos activos a la estrategia actual o reemplazar "
            "los activos actuales con ellos?"
        )
    return (
        "Do you want to add those assets to the current strategy, or replace "
        "the current assets with them?"
    )


def confirmation_rule_display_value(
    strategy: StrategySummary | dict[str, Any],
    *,
    side: str,
    fallback_value: Any,
    language: str | None,
) -> str | None:
    locale = runtime_locale(language)
    indicator_rule = indicator_threshold_rule(strategy, side)
    indicator_text = indicator_rule_display_value(
        indicator_rule,
        side=side,
        locale=locale,
    )
    if indicator_text is not None:
        return indicator_text

    crossover_rule = strategy_rule(strategy, side)
    if crossover_rule is None and side == "exit":
        crossover_rule = opposite_moving_average_crossover_rule(
            strategy_rule(strategy, "entry")
        )
    crossover_text = moving_average_rule_display_value(
        crossover_rule,
        side=side,
        locale=locale,
    )
    if crossover_text is not None:
        return crossover_text

    fallback_text = str(fallback_value or "").strip()
    return fallback_text or None


def indicator_rule_display_value(
    rule: dict[str, Any] | None,
    *,
    side: str,
    locale: RuntimeLocale,
) -> str | None:
    if not rule:
        return None
    indicator = str(rule.get("indicator") or "").upper()
    if not indicator:
        return None
    threshold = _compact_number(rule.get("threshold"))
    if threshold is None:
        return None
    catalog = _CATALOGS[locale]
    period = _compact_number(rule.get("period"))
    indicator_label = f"{indicator}({period})" if period is not None else indicator
    operator = str(rule.get("operator") or "below")
    direction, suffix = catalog.indicator_directions.get(
        operator,
        catalog.indicator_directions["below"],
    )
    action = catalog.actions["exit" if side == "exit" else "entry"]
    return catalog.indicator_rule_template.format(
        action=action,
        indicator_label=indicator_label,
        direction=direction,
        threshold=threshold,
        suffix=suffix,
    )


def moving_average_rule_display_value(
    rule: dict[str, Any] | None,
    *,
    side: str,
    locale: RuntimeLocale,
) -> str | None:
    if not rule or rule.get("type") != "moving_average_crossover":
        return None
    fast_period = _compact_number(rule.get("fast_period"))
    slow_period = _compact_number(rule.get("slow_period"))
    if fast_period is None or slow_period is None:
        return None
    catalog = _CATALOGS[locale]
    fast_indicator = str(rule.get("fast_indicator") or "sma").upper()
    slow_indicator = str(rule.get("slow_indicator") or fast_indicator).upper()
    direction = catalog.moving_average_directions.get(
        str(rule.get("direction") or "bullish"),
        catalog.moving_average_directions["bullish"],
    )
    action = catalog.actions["exit" if side == "exit" else "entry"]
    fast_unit = _day_unit(catalog, fast_period)
    slow_unit = _day_unit(catalog, slow_period)
    return catalog.moving_average_rule_template.format(
        action=action,
        fast_indicator=fast_indicator,
        fast_period=fast_period,
        fast_unit=fast_unit,
        direction=direction,
        slow_indicator=slow_indicator,
        slow_period=slow_period,
        slow_unit=slow_unit,
    )


def _day_unit(catalog: LocaleCatalog, value: str) -> str:
    return catalog.day_unit_singular if value == "1" else catalog.day_unit_plural


def _compact_number(value: Any) -> str | None:
    if not isinstance(value, int | float) or isinstance(value, bool):
        return None
    numeric = float(value)
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:g}"
