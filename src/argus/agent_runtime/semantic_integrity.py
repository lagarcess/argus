from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from argus.agent_runtime.rule_specs import executable_rule_spec_from_strategy
from argus.agent_runtime.state.models import (
    SimplificationOption,
    StrategySummary,
    UnsupportedConstraint,
)
from argus.agent_runtime.strategy_contract import (
    executable_strategy_type,
    format_display_date,
    has_partial_explicit_date_range,
    normalize_date_range_candidate,
    resolve_date_range,
)


@dataclass(frozen=True)
class SemanticConstraintEvidence:
    explicit_date_reference: bool = False
    explicit_signal_rule_reference: bool = False
    normalized_date_range: str | dict[str, Any] | None = None
    recurring_contribution: float | None = None
    total_capital: float | None = None
    recurring_cadence: str | None = None


@dataclass(frozen=True)
class SemanticIntegrityReport:
    strategy: StrategySummary
    optional_parameter_values: dict[str, Any] = field(default_factory=dict)
    blocking_missing_fields: list[str] = field(default_factory=list)
    unsupported_constraints: list[UnsupportedConstraint] = field(default_factory=list)
    reason_codes: list[str] = field(default_factory=list)
    evidence: SemanticConstraintEvidence = field(
        default_factory=SemanticConstraintEvidence
    )


def conserve_semantic_constraints(
    *,
    strategy: StrategySummary,
    selected_thread_metadata: dict[str, Any],
    prior_strategy: StrategySummary | None = None,
    optional_parameter_values: dict[str, Any] | None = None,
    supported_timeframes: tuple[str, ...] = (),
) -> SemanticIntegrityReport:
    """Preserve typed LLM constraints before a draft can reach confirmation."""

    updated = strategy.model_copy(deep=True)
    optional_values = dict(optional_parameter_values or {})
    blocking_missing_fields: list[str] = []
    unsupported_constraints: list[UnsupportedConstraint] = []
    reason_codes: list[str] = []

    requested_field = str(selected_thread_metadata.get("requested_field") or "")
    normalized_date_range = normalize_date_range_candidate(updated.date_range)
    timeframe_as_date_range = explicit_date_range_value(
        updated.timeframe,
        supported_timeframes=supported_timeframes,
    )
    if _field_base(requested_field) == "date_range" and timeframe_as_date_range:
        if normalized_date_range in (None, "", [], {}):
            normalized_date_range = updated.timeframe
            updated.date_range = updated.timeframe
        updated.timeframe = None
        reason_codes.append("semantic_timeframe_reassigned_to_date_range")
    if normalized_date_range not in (None, "", [], {}):
        if normalized_date_range != updated.date_range:
            updated.date_range = normalized_date_range
        reason_codes.append("semantic_date_constraint_preserved")
    if has_partial_explicit_date_range(updated.date_range):
        blocking_missing_fields.append("date_range")
        reason_codes.append("partial_date_range_requires_clarification")
    invalid_date_constraint = _invalid_date_range_constraint(updated.date_range)
    if invalid_date_constraint is not None:
        unsupported_constraints.append(invalid_date_constraint)
        blocking_missing_fields.append("date_range")
        reason_codes.append("invalid_date_range_requires_correction")
    normalized_timeframe = _supported_timeframe_value(
        updated.timeframe,
        supported_timeframes=supported_timeframes,
    )
    if normalized_timeframe is not None:
        updated.timeframe = normalized_timeframe
        optional_values["timeframe"] = normalized_timeframe
        reason_codes.append("semantic_timeframe_constraint_preserved")

    structured_signal_rule_reference = _strategy_has_signal_rule_payload(updated)

    money_evidence = _structured_money_role_evidence(
        strategy=updated,
        requested_field=requested_field,
    )
    cadence = _structured_recurring_cadence(updated)
    evidence = SemanticConstraintEvidence(
        explicit_date_reference=normalized_date_range not in (None, "", [], {}),
        explicit_signal_rule_reference=structured_signal_rule_reference,
        normalized_date_range=normalized_date_range,
        recurring_contribution=money_evidence.recurring_contribution,
        total_capital=money_evidence.total_capital,
        recurring_cadence=cadence,
    )

    if executable_strategy_type(updated) == "dca_accumulation":
        if money_evidence.total_capital is not None:
            optional_values["initial_capital"] = money_evidence.total_capital
            unsupported_constraints.append(
                _unsupported_dca_starting_principal_constraint(
                    money_evidence.total_capital,
                    source=money_evidence.total_capital_source,
                )
            )
            reason_codes.append("semantic_dca_starting_principal_deferred")
        if money_evidence.recurring_contribution is not None:
            updated.capital_amount = money_evidence.recurring_contribution
            reason_codes.append("semantic_recurring_contribution_preserved")
        elif money_evidence.total_capital is not None:
            updated.capital_amount = None
            blocking_missing_fields.append("capital_amount")
            reason_codes.append("semantic_recurring_contribution_missing")
        if cadence is not None:
            updated.cadence = cadence
            reason_codes.append("semantic_recurring_cadence_preserved")

    return SemanticIntegrityReport(
        strategy=updated,
        optional_parameter_values=optional_values,
        blocking_missing_fields=list(dict.fromkeys(blocking_missing_fields)),
        unsupported_constraints=_dedupe_unsupported_constraints(unsupported_constraints),
        reason_codes=list(dict.fromkeys(reason_codes)),
        evidence=evidence,
    )


def filter_unsubstantiated_timeframe_constraints(
    *,
    constraints: list[UnsupportedConstraint],
    strategy: StrategySummary,
    selected_thread_metadata: dict[str, Any],
    supported_timeframes: tuple[str, ...] = (),
) -> tuple[list[UnsupportedConstraint], list[str]]:
    """Drop LLM constraints that mislabeled an explicit date answer as timeframe."""

    requested_field = _field_base(
        str(selected_thread_metadata.get("requested_field") or "")
    )
    if requested_field != "date_range":
        return constraints, []

    filtered: list[UnsupportedConstraint] = []
    removed = False
    for constraint in constraints:
        if not _is_timeframe_constraint(constraint):
            filtered.append(constraint)
            continue
        if strategy.timeframe in (None, "", [], {}) and _has_complete_date_range(
            strategy.date_range
        ):
            removed = True
            continue
        raw_value = constraint.raw_value or strategy.timeframe or strategy.date_range
        if explicit_date_range_value(
            raw_value,
            supported_timeframes=supported_timeframes,
        ):
            removed = True
            continue
        filtered.append(constraint)

    return (
        filtered,
        ["semantic_unsubstantiated_timeframe_constraint_removed"] if removed else [],
    )


@dataclass(frozen=True)
class _MoneyRoleEvidence:
    recurring_contribution: float | None = None
    total_capital: float | None = None
    total_capital_source: str | None = None


def _structured_money_role_evidence(
    *,
    strategy: StrategySummary,
    requested_field: str,
) -> _MoneyRoleEvidence:
    extra = dict(strategy.extra_parameters or {})
    field_provenance = extra.get("field_provenance")
    if not isinstance(field_provenance, dict):
        field_provenance = {}

    recurring = _first_number(
        extra,
        (
            "recurring_contribution",
            "contribution_amount",
            "periodic_contribution",
            "dca_contribution",
        ),
    )
    total_key, total = _first_number_with_key(
        extra,
        (
            "initial_capital",
            "starting_capital",
            "starting_principal",
            "initial_lump_sum",
            "initial_lump",
            "lump_sum",
            "total_capital",
            "total_budget",
            "max_budget",
            "investment_budget",
            "cap",
            "contribution_cap",
            "capital_cap",
            "investment_cap",
        ),
    )

    capital_source = str(field_provenance.get("capital_amount") or "").strip()
    if capital_source in {
        "initial_capital",
        "starting_capital",
        "starting_principal",
        "initial_lump_sum",
        "initial_lump",
        "lump_sum",
        "total_capital",
        "total_budget",
        "max_budget",
        "investment_budget",
        "cap",
        "contribution_cap",
        "capital_cap",
        "investment_cap",
    }:
        total = total if total is not None else _coerce_number(strategy.capital_amount)
        total_key = total_key or capital_source
    elif capital_source in {
        "recurring_contribution",
        "contribution_amount",
        "periodic_contribution",
        "dca_contribution",
        "user",
        "explicit_user",
    }:
        recurring = recurring if recurring is not None else _coerce_number(
            strategy.capital_amount
        )
    elif (
        requested_field == "capital_amount"
        and total is None
        and recurring is None
        and strategy.capital_amount is not None
    ):
        recurring = _coerce_number(strategy.capital_amount)
    elif (
        requested_field != "capital_amount"
        and total is None
        and recurring is None
        and strategy.capital_amount is not None
    ):
        recurring = _coerce_number(strategy.capital_amount)

    return _MoneyRoleEvidence(
        recurring_contribution=recurring,
        total_capital=total,
        total_capital_source=total_key or capital_source or None,
    )


def explicit_date_range_value(
    value: Any,
    *,
    supported_timeframes: tuple[str, ...] = (),
) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    if _is_supported_timeframe_value(value, supported_timeframes=supported_timeframes):
        return False
    try:
        resolution = resolve_date_range(value)
    except Exception:
        return False
    return not resolution.used_default


def _has_complete_date_range(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    start = value.get("start")
    end = value.get("end")
    return bool(start not in (None, "", [], {}) and end not in (None, "", [], {}))


def _is_supported_timeframe_value(
    value: str,
    *,
    supported_timeframes: tuple[str, ...],
) -> bool:
    return (
        _supported_timeframe_value(value, supported_timeframes=supported_timeframes)
        is not None
    )


def _supported_timeframe_value(
    value: Any,
    *,
    supported_timeframes: tuple[str, ...],
) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    for supported in supported_timeframes:
        supported_value = str(supported).strip()
        if normalized == supported_value.lower():
            return supported_value
    return None


def _is_timeframe_constraint(constraint: UnsupportedConstraint) -> bool:
    category = constraint.category.strip().lower()
    return category in {"unsupported_time_granularity", "unsupported_timeframe"}


def _field_base(field_name: str) -> str:
    return field_name.split("[", 1)[0]


def _structured_recurring_cadence(strategy: StrategySummary) -> str | None:
    if strategy.cadence in {"daily", "weekly", "monthly", "quarterly", "yearly"}:
        return strategy.cadence
    extra = dict(strategy.extra_parameters or {})
    cadence = extra.get("recurring_cadence") or extra.get("cadence")
    if cadence in {"daily", "weekly", "monthly", "quarterly", "yearly"}:
        return str(cadence)
    return None


def _strategy_has_signal_rule_payload(strategy: StrategySummary) -> bool:
    return executable_rule_spec_from_strategy(strategy) is not None


def _first_number(payload: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    _, value = _first_number_with_key(payload, keys)
    return value


def _first_number_with_key(
    payload: dict[str, Any],
    keys: tuple[str, ...],
) -> tuple[str | None, float | None]:
    for key in keys:
        value = _coerce_number(payload.get(key))
        if value is not None:
            return key, value
    return None, None


def _coerce_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().removeprefix("$").replace(",", "")
        multiplier = 1.0
        lowered = cleaned.lower()
        for suffix, suffix_multiplier in (
            ("thousand", 1_000.0),
            ("million", 1_000_000.0),
            ("k", 1_000.0),
            ("m", 1_000_000.0),
        ):
            if lowered.endswith(suffix):
                multiplier = suffix_multiplier
                cleaned = cleaned[: -len(suffix)]
                break
        try:
            return float(cleaned) * multiplier
        except ValueError:
            return None
    return None


def _unsupported_dca_starting_principal_constraint(
    total_capital: float,
    *,
    source: str | None = None,
) -> UnsupportedConstraint:
    formatted = _format_money(total_capital)
    role_label = _dca_total_capital_role_label(source)
    # TODO(dca-engine): Support starting principal, contribution ceilings, and
    # recurring contributions as separate DCA execution inputs across engine
    # launch models, LangGraph contracts, confirmation cards, result assumptions,
    # and capability wording.
    return UnsupportedConstraint(
        category="unsupported_dca_starting_principal",
        raw_value=f"{formatted} {role_label}",
        explanation=(
            f"I understand {formatted} as a {role_label}, but the current "
            "DCA backtest can only execute the recurring contribution. Starting "
            "principal and contribution caps are not executable in the same DCA "
            "run yet."
        ),
        simplification_options=[
            SimplificationOption(
                label="Run recurring buys only",
                replacement_values={"ignore_initial_capital": True},
            ),
            SimplificationOption(
                label="Adjust recurring contribution",
                replacement_values={"requested_field": "capital_amount"},
            ),
            SimplificationOption(
                label="Use buy and hold with starting capital",
                replacement_values={
                    "strategy_type": "buy_and_hold",
                    "initial_capital": total_capital,
                },
            ),
        ],
    )


def _dca_total_capital_role_label(source: str | None) -> str:
    normalized = str(source or "").strip().lower()
    if normalized in {"cap", "contribution_cap", "capital_cap", "investment_cap"}:
        return "contribution cap"
    if normalized in {"initial_lump_sum", "initial_lump", "lump_sum"}:
        return "initial lump sum"
    if normalized == "max_budget":
        return "maximum budget"
    if normalized in {"total_capital", "total_budget", "investment_budget"}:
        return "total budget"
    return "starting principal"


def _invalid_date_range_constraint(value: Any) -> UnsupportedConstraint | None:
    if value in (None, "", [], {}):
        return None
    current_date = date.today()
    try:
        resolution = resolve_date_range(value, today=current_date)
    except Exception:
        return None
    if resolution.used_default:
        return None
    start = format_display_date(resolution.start)
    end = format_display_date(resolution.end)
    today = format_display_date(current_date)
    if resolution.start <= resolution.end <= current_date:
        return None
    if resolution.end > current_date:
        return UnsupportedConstraint(
            category="invalid_date_range",
            raw_value=_format_date_range_value(value),
            explanation=(
                f"I read the date window as {start} to {end}, but historical "
                f"backtests need an end date on or before {today}."
            ),
            simplification_options=[
                SimplificationOption(
                    label="Choose an end date on or before today",
                    replacement_values={"requested_field": "date_range"},
                ),
                SimplificationOption(
                    label="Use year to date",
                    replacement_values={"requested_field": "date_range"},
                ),
                SimplificationOption(
                    label="Use a different date window",
                    replacement_values={"requested_field": "date_range"},
                ),
            ],
        )
    return UnsupportedConstraint(
        category="invalid_date_range",
        raw_value=_format_date_range_value(value),
        explanation=(
            f"I read the date window as {start} to {end}, but the end date has "
            "to come after the start date."
        ),
        simplification_options=[
            SimplificationOption(
                label="Choose an end date after the start date",
                replacement_values={"requested_field": "date_range"},
            ),
            SimplificationOption(
                label="Choose a start date before the end date",
                replacement_values={"requested_field": "date_range"},
            ),
            SimplificationOption(
                label="Use a different date window",
                replacement_values={"requested_field": "date_range"},
            ),
        ],
    )


def _format_date_range_value(value: Any) -> str:
    if isinstance(value, dict):
        start = value.get("start") or value.get("from") or "?"
        end = value.get("end") or value.get("to") or "?"
        return f"{start} to {end}"
    return str(value)


def _dedupe_unsupported_constraints(
    constraints: list[UnsupportedConstraint],
) -> list[UnsupportedConstraint]:
    seen: set[tuple[str, str]] = set()
    deduped: list[UnsupportedConstraint] = []
    for constraint in constraints:
        key = (constraint.category, constraint.raw_value)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(constraint)
    return deduped


def _format_money(value: float) -> str:
    return f"${value:,.0f}"
