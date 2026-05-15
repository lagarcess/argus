from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from argus.agent_runtime.rule_specs import executable_rule_spec_from_strategy
from argus.agent_runtime.state.models import (
    SimplificationOption,
    StrategySummary,
    UnsupportedConstraint,
)
from argus.agent_runtime.strategy_contract import (
    executable_strategy_type,
    normalize_date_range_candidate,
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
) -> SemanticIntegrityReport:
    """Preserve typed LLM constraints before a draft can reach confirmation."""

    updated = strategy.model_copy(deep=True)
    optional_values = dict(optional_parameter_values or {})
    blocking_missing_fields: list[str] = []
    unsupported_constraints: list[UnsupportedConstraint] = []
    reason_codes: list[str] = []

    normalized_date_range = normalize_date_range_candidate(updated.date_range)
    if normalized_date_range not in (None, "", [], {}):
        if normalized_date_range != updated.date_range:
            updated.date_range = normalized_date_range
        reason_codes.append("semantic_date_constraint_preserved")

    requested_field = str(selected_thread_metadata.get("requested_field") or "")
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
                    money_evidence.total_capital
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


@dataclass(frozen=True)
class _MoneyRoleEvidence:
    recurring_contribution: float | None = None
    total_capital: float | None = None


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
    total = _first_number(
        extra,
        (
            "initial_capital",
            "starting_capital",
            "starting_principal",
            "total_capital",
            "total_budget",
            "max_budget",
            "investment_budget",
        ),
    )

    capital_source = str(field_provenance.get("capital_amount") or "").strip()
    if capital_source in {
        "initial_capital",
        "starting_capital",
        "starting_principal",
        "total_capital",
        "total_budget",
        "max_budget",
        "investment_budget",
    }:
        total = total if total is not None else _coerce_number(strategy.capital_amount)
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
    )


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
    for key in keys:
        value = _coerce_number(payload.get(key))
        if value is not None:
            return value
    return None


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
) -> UnsupportedConstraint:
    formatted = _format_money(total_capital)
    # TODO(dca-engine): Support starting principal, contribution ceilings, and
    # recurring contributions as separate DCA execution inputs across engine
    # launch models, LangGraph contracts, confirmation cards, result assumptions,
    # and capability wording.
    return UnsupportedConstraint(
        category="unsupported_dca_starting_principal",
        raw_value=f"{formatted} starting principal",
        explanation=(
            f"I understand {formatted} as starting principal, but the current "
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
