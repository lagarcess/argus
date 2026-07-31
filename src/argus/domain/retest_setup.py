"""Canonical reconstruction of a stored run as a retestable supported setup.

One server-owned extractor serves Omnisearch action eligibility, typed retest
admission, and deterministic tests, so the two surfaces cannot drift apart.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, cast

RETEST_CONTRACT_VERSION = "argus_retest_run/v1"
RETEST_WINDOW_POLICY = "same_duration_ending_today"

RETEST_STRATEGY_TYPES = (
    "buy_and_hold",
    "dca_accumulation",
    "indicator_threshold",
    "signal_strategy",
)
RETEST_CADENCES = (
    "daily",
    "weekly",
    "biweekly",
    "monthly",
    "quarterly",
)
RETEST_ASSET_CLASSES = ("equity", "crypto", "currency_pair")
RETEST_PARAMETER_KEYS = (
    "indicator",
    "indicator_period",
    "entry_threshold",
    "exit_threshold",
    "fast_period",
    "slow_period",
    "moving_average_type",
)
_MAX_SYMBOLS = 5


@dataclass(frozen=True)
class RetestSetup:
    """Executable truth reloaded from a stored run, moved to a fresh window."""

    source_run_id: str
    strategy_type: str
    symbols: tuple[str, ...]
    asset_class: str
    timeframe: str
    original_start: date
    original_end: date
    start: date
    end: date
    sizing_mode: str
    benchmark_symbol: str
    capital_amount: float | None = None
    position_size: float | None = None
    cadence: str | None = None
    recurring_contribution: float | None = None
    starting_principal: float | None = None
    entry_rule: dict[str, Any] | None = None
    exit_rule: dict[str, Any] | None = None
    rule_spec: dict[str, Any] | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    execution_realism: dict[str, Any] | None = None

    @property
    def duration_days(self) -> int:
        return (self.original_end - self.original_start).days


def retest_setup_from_run(
    run: Mapping[str, Any] | None,
    *,
    today: date,
) -> RetestSetup | None:
    """Rebuild a stored run's supported setup on a window ending at ``today``."""
    if run is None:
        return None
    run_id = _text(run.get("id"))
    config = _config(run)
    resolved_strategy = _mapping(config.get("resolved_strategy"))
    resolved_parameters = _mapping(config.get("resolved_parameters"))
    resolved_engine_config = _mapping(resolved_parameters.get("engine_config"))
    snapshot_engine_config = _mapping(config.get("engine_config"))
    strategy_type = _text(
        resolved_strategy.get("strategy_type") or config.get("template")
    )
    if strategy_type not in RETEST_STRATEGY_TYPES or run_id is None:
        return None

    symbols = _run_symbols(run)
    asset_class = _text(resolved_strategy.get("asset_class") or run.get("asset_class"))
    timeframe = _text(resolved_parameters.get("timeframe") or config.get("timeframe"))
    benchmark_symbol = _text(
        resolved_parameters.get("benchmark_symbol")
        or config.get("benchmark_symbol")
        or run.get("benchmark_symbol")
    )
    original_start, original_end = _run_date_span(run)
    if (
        not symbols
        or len(symbols) > _MAX_SYMBOLS
        or asset_class not in RETEST_ASSET_CLASSES
        or timeframe is None
        or benchmark_symbol is None
        or original_start is None
        or original_end is None
        or original_end < original_start
    ):
        return None

    sizing_mode = _text(resolved_parameters.get("sizing_mode"))
    capital_amount = _number(
        resolved_parameters.get("capital_amount")
        or config.get("starting_capital")
        or config.get("capital_amount")
    )
    position_size = _number(resolved_parameters.get("position_size"))
    if sizing_mode is None:
        sizing_mode = "position_size" if position_size is not None else "capital_amount"
    if sizing_mode == "capital_amount":
        position_size = None
        if capital_amount is None:
            return None
    elif sizing_mode == "position_size":
        capital_amount = None
        if position_size is None:
            return None
    else:
        return None
    cadence = _text(resolved_parameters.get("cadence") or config.get("cadence"))
    if strategy_type == "dca_accumulation":
        if cadence not in RETEST_CADENCES:
            return None
        recurring_contribution = _consistent_number(
            resolved_parameters.get("recurring_contribution"),
            resolved_engine_config.get("recurring_contribution"),
            snapshot_engine_config.get("recurring_contribution"),
        )
        starting_principal = _consistent_number(
            resolved_parameters.get("starting_principal"),
            resolved_engine_config.get("starting_principal"),
            snapshot_engine_config.get("starting_principal"),
            allow_zero=True,
        )
        if (
            recurring_contribution is None
            or starting_principal != 0
            or capital_amount != recurring_contribution
        ):
            return None
    else:
        cadence = None
        recurring_contribution = None
        starting_principal = None

    execution_realism_valid, execution_realism = _consistent_mapping(
        resolved_engine_config.get("_execution_realism"),
        snapshot_engine_config.get("_execution_realism"),
        resolved_parameters.get("_execution_realism"),
        resolved_parameters.get("execution_realism"),
        config.get("_execution_realism"),
    )
    if not execution_realism_valid:
        return None

    return RetestSetup(
        source_run_id=run_id,
        strategy_type=strategy_type,
        symbols=tuple(symbols),
        asset_class=asset_class,
        timeframe=timeframe,
        original_start=original_start,
        original_end=original_end,
        start=today - timedelta(days=(original_end - original_start).days),
        end=today,
        sizing_mode=sizing_mode,
        benchmark_symbol=benchmark_symbol,
        capital_amount=capital_amount,
        position_size=position_size,
        cadence=cadence,
        recurring_contribution=recurring_contribution,
        starting_principal=starting_principal,
        entry_rule=_mapping_or_none(resolved_strategy.get("entry_rule")),
        exit_rule=_mapping_or_none(resolved_strategy.get("exit_rule")),
        rule_spec=_mapping_or_none(
            resolved_strategy.get("rule_spec")
            or resolved_parameters.get("rule_spec")
            or config.get("rule_spec")
        ),
        parameters={
            key: resolved_parameters[key]
            for key in RETEST_PARAMETER_KEYS
            if key in resolved_parameters
            and isinstance(resolved_parameters[key], (str, int, float, bool))
        },
        execution_realism=execution_realism,
    )


def _run_symbols(run: Mapping[str, Any]) -> list[str]:
    symbols = _text_list(run.get("symbols"))
    if symbols:
        return symbols
    card = run.get("conversation_result_card")
    return _text_list(card.get("symbols")) if isinstance(card, dict) else []


def _config(run: Mapping[str, Any]) -> Mapping[str, Any]:
    value = run.get("config_snapshot")
    return value if isinstance(value, dict) else {}


def _run_date_span(run: Mapping[str, Any]) -> tuple[date | None, date | None]:
    config = _config(run)
    config_date_range = _mapping(config.get("date_range"))
    card = run.get("conversation_result_card")
    date_range = card.get("date_range") if isinstance(card, dict) else None
    if not isinstance(date_range, dict):
        date_range = {}
    return (
        _date(
            config.get("start_date")
            or config_date_range.get("start")
            or date_range.get("start")
        ),
        _date(
            config.get("end_date")
            or config_date_range.get("end")
            or date_range.get("end")
        ),
    )


def _date(value: object) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    return None


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _text_list(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    items: list[str] = []
    for item in value:
        text = _text(item)
        if text and text not in items:
            items.append(text)
    return items


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _mapping_or_none(value: object) -> dict[str, Any] | None:
    return dict(value) if isinstance(value, Mapping) else None


def _consistent_mapping(*values: object) -> tuple[bool, dict[str, Any] | None]:
    present = [value for value in values if value is not None]
    if not present:
        return True, None
    if any(not isinstance(value, Mapping) for value in present):
        return False, None
    mappings = [dict(cast(Mapping[str, Any], value)) for value in present]
    if any(value != mappings[0] for value in mappings[1:]):
        return False, None
    return True, mappings[0]


def _consistent_number(*values: object, allow_zero: bool = False) -> float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    parsed = [
        _nonnegative_number(value) if allow_zero else _number(value)
        for value in present
    ]
    if any(value is None for value in parsed):
        return None
    numbers = cast(list[float], parsed)
    if any(value != numbers[0] for value in numbers[1:]):
        return None
    return numbers[0]


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if value > 0 else None


def _nonnegative_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if value >= 0 else None
