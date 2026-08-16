"""Canonical reconstruction of a stored run as a retestable supported setup.

One server-owned extractor serves Omnisearch action eligibility, typed retest
admission, and deterministic tests, so the two surfaces cannot drift apart.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from typing import Any, Literal, cast

from argus.domain.market_data.capabilities import (
    ALPACA_EQUITY_HISTORY_START,
    KRAKEN_MAX_OHLC_CANDLES,
    KRAKEN_OHLC_TIMEFRAME_MINUTES,
    AssetClass,
    latest_complete_data_adjustment,
    market_data_window_violation,
    validate_market_data_window,
)

RETEST_CONTRACT_VERSION = "argus_retest_run/v2"
RETEST_WINDOW_POLICY = "preserve_start_ending_latest_available"
LEGACY_RETEST_CONTRACT_VERSION = "argus_retest_run/v1"
LEGACY_RETEST_WINDOW_POLICY = "same_duration_ending_today"
RETEST_CONTRACT_PAIRS: frozenset[tuple[str, str]] = frozenset(
    {
        (RETEST_CONTRACT_VERSION, RETEST_WINDOW_POLICY),
        (LEGACY_RETEST_CONTRACT_VERSION, LEGACY_RETEST_WINDOW_POLICY),
    }
)

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
    """Executable truth reloaded from a stored run with a candidate new end."""

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
    starting_capital: float | None = None
    entry_rule: dict[str, Any] | None = None
    exit_rule: dict[str, Any] | None = None
    rule_spec: dict[str, Any] | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    execution_realism: dict[str, Any] | None = None

    @property
    def duration_days(self) -> int:
        return (self.original_end - self.original_start).days


RetestDossierState = Literal[
    "new_data_available",
    "no_new_data",
    "cant_do_it",
]
RetestWindowViolationCode = Literal[
    "provider_history_start_unavailable",
    "kraken_ohlc_window_exceeded",
    "provider_timeframe_unavailable",
]


@dataclass(frozen=True)
class RetestWindowRepair:
    kind: Literal["clamp_start"]
    start_date: date
    end_date: date


@dataclass(frozen=True)
class RetestDossierAvailability:
    state: RetestDossierState
    reason_code: RetestWindowViolationCode | None = None
    repair: RetestWindowRepair | None = None


def retest_dossier_availability(setup: RetestSetup) -> RetestDossierAvailability:
    """Compute the dossier button state without provider or LLM work."""
    effective_end = latest_complete_retest_end(setup)
    violation = market_data_window_violation(
        asset_class=cast(AssetClass, setup.asset_class),
        timeframe=setup.timeframe,
        start_date=setup.start,
        end_date=effective_end,
    )
    if violation is not None:
        code = cast(RetestWindowViolationCode, violation.code)
        return RetestDossierAvailability(
            state="cant_do_it",
            reason_code=code,
            repair=_repair_for_violation(
                setup,
                code=code,
                effective_end=effective_end,
            ),
        )
    if effective_end <= setup.original_end:
        return RetestDossierAvailability(state="no_new_data")
    return RetestDossierAvailability(state="new_data_available")


def repaired_retest_setup(
    setup: RetestSetup,
    availability: RetestDossierAvailability,
) -> RetestSetup:
    """Apply only the server-computed repair advertised by the dossier."""
    repair = availability.repair
    if repair is None:
        return setup
    return replace(setup, start=repair.start_date, end=repair.end_date)


def latest_complete_retest_end(setup: RetestSetup) -> date:
    """Return the provider-complete end shared by eligibility and admission."""
    adjustment = latest_complete_data_adjustment(
        asset_class=cast(AssetClass, setup.asset_class),
        timeframe=setup.timeframe,
        end_date=setup.end,
        today=setup.end,
    )
    return adjustment.through if adjustment is not None else setup.end


def _repair_for_violation(
    setup: RetestSetup,
    *,
    code: RetestWindowViolationCode,
    effective_end: date,
) -> RetestWindowRepair | None:
    if code == "provider_history_start_unavailable":
        repaired_start = ALPACA_EQUITY_HISTORY_START
    elif code == "kraken_ohlc_window_exceeded":
        interval = KRAKEN_OHLC_TIMEFRAME_MINUTES.get(setup.timeframe)
        if interval is None:
            return None
        maximum_span_minutes = KRAKEN_MAX_OHLC_CANDLES * interval - 24 * 60
        repaired_start = effective_end - timedelta(
            days=max(0, maximum_span_minutes // (24 * 60))
        )
    else:
        return None
    if repaired_start > effective_end:
        return None
    try:
        validate_market_data_window(
            asset_class=cast(AssetClass, setup.asset_class),
            timeframe=setup.timeframe,
            start_date=repaired_start,
            end_date=effective_end,
        )
    except ValueError:
        return None
    return RetestWindowRepair(
        kind="clamp_start",
        start_date=repaired_start,
        end_date=effective_end,
    )


EVIDENCE_IDENTITY_KEYS = ("evidence_artifact_id", "idea_id", "idea_version_id")


def has_finalized_evidence_identity(result_card: Mapping[str, Any] | None) -> bool:
    """The finalizer attaches evidence identity last, so its absence means the
    run/evidence tuple never completed and must not be replayed.

    Eligibility and admission share this predicate so the dossier cannot offer
    a retest that admission is guaranteed to reject.
    """
    if not isinstance(result_card, Mapping):
        return False
    return all(
        isinstance(result_card.get(key), str) and result_card[key].strip()
        for key in EVIDENCE_IDENTITY_KEYS
    )


def retest_setup_from_run(
    run: Mapping[str, Any] | None,
    *,
    today: date,
) -> RetestSetup | None:
    """Rebuild a stored run from its original start through candidate ``today``."""
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
        resolved_plan = _stored_dca_capital_plan(resolved_engine_config)
        snapshot_plan = _stored_dca_capital_plan(snapshot_engine_config)
        recurring_contribution = _consistent_number(
            resolved_parameters.get("recurring_contribution"),
            resolved_plan.contribution if resolved_plan else None,
            snapshot_plan.contribution if snapshot_plan else None,
        )
        starting_capital = _consistent_number(
            resolved_parameters.get("starting_capital"),
            resolved_plan.starting_capital if resolved_plan else None,
            snapshot_plan.starting_capital if snapshot_plan else None,
            allow_zero=True,
        )
        if (
            recurring_contribution is None
            or starting_capital is None
            or starting_capital < 0
            or capital_amount != recurring_contribution
        ):
            return None
    else:
        cadence = None
        recurring_contribution = None
        starting_capital = None

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
        start=original_start,
        end=today,
        sizing_mode=sizing_mode,
        benchmark_symbol=benchmark_symbol,
        capital_amount=capital_amount,
        position_size=position_size,
        cadence=cadence,
        recurring_contribution=recurring_contribution,
        starting_capital=starting_capital,
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


def _stored_dca_capital_plan(engine_config: Mapping[str, Any]) -> Any | None:
    """The stored config's plan, read through its own owner or refused."""
    from argus.domain.dca_capital import (
        DcaCapitalError,
        dca_capital_plan_from_config,
    )

    if not engine_config:
        return None
    try:
        return dca_capital_plan_from_config(dict(engine_config))
    except DcaCapitalError:
        return None


def _consistent_number(*values: object, allow_zero: bool = False) -> float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    parsed = [
        _nonnegative_number(value) if allow_zero else _number(value) for value in present
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
