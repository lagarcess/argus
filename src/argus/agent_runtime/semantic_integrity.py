from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from argus.agent_runtime.state.models import (
    SimplificationOption,
    StrategySummary,
    UnsupportedConstraint,
)
from argus.agent_runtime.strategy_contract import (
    executable_strategy_type,
    normalize_date_range_candidate,
    resolve_date_range,
)


@dataclass(frozen=True)
class SemanticConstraintEvidence:
    explicit_date_reference: bool = False
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
    current_user_message: str,
    selected_thread_metadata: dict[str, Any],
    optional_parameter_values: dict[str, Any] | None = None,
) -> SemanticIntegrityReport:
    """Preserve explicit user constraints before a draft can reach confirmation."""

    updated = strategy.model_copy(deep=True)
    optional_values = dict(optional_parameter_values or {})
    blocking_missing_fields: list[str] = []
    unsupported_constraints: list[UnsupportedConstraint] = []
    reason_codes: list[str] = []
    evidence = SemanticConstraintEvidence(
        explicit_date_reference=_contains_explicit_date_reference(current_user_message),
        normalized_date_range=normalize_date_range_candidate(
            None,
            raw_user_phrasing=current_user_message,
        ),
    )

    if evidence.explicit_date_reference:
        if evidence.normalized_date_range is not None:
            updated.date_range = evidence.normalized_date_range
            reason_codes.append("semantic_date_constraint_preserved")
        elif _date_range_looks_like_default(updated.date_range):
            updated.date_range = None
            blocking_missing_fields.append("date_range")
            reason_codes.append("semantic_date_constraint_unresolved")

    money_evidence = _money_role_evidence(
        current_user_message=current_user_message,
        requested_field=str(selected_thread_metadata.get("requested_field") or ""),
    )
    evidence = SemanticConstraintEvidence(
        explicit_date_reference=evidence.explicit_date_reference,
        normalized_date_range=evidence.normalized_date_range,
        recurring_contribution=money_evidence.recurring_contribution,
        total_capital=money_evidence.total_capital,
        recurring_cadence=_recurring_cadence_evidence(current_user_message),
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
        if evidence.recurring_cadence is not None:
            updated.cadence = evidence.recurring_cadence
            reason_codes.append("semantic_recurring_cadence_preserved")

    return SemanticIntegrityReport(
        strategy=updated,
        optional_parameter_values=optional_values,
        blocking_missing_fields=list(dict.fromkeys(blocking_missing_fields)),
        unsupported_constraints=_dedupe_unsupported_constraints(unsupported_constraints),
        reason_codes=list(dict.fromkeys(reason_codes)),
        evidence=evidence,
    )


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


def _contains_explicit_date_reference(message: str) -> bool:
    normalized = _normalized_text(message)
    if not normalized:
        return False
    return bool(
        re.search(
            r"\b(?:since|ytd|year to date|from|between|through|until|"
            r"past|last|previous|ago|jan|january|feb|february|mar|march|"
            r"apr|april|may|jun|june|jul|july|aug|august|sep|sept|"
            r"september|oct|october|nov|november|dec|december)\b",
            normalized,
        )
    )


def _date_range_looks_like_default(value: Any) -> bool:
    if value in (None, "", [], {}):
        return True
    if not isinstance(value, str):
        return False
    normalized = value.strip().lower().replace("_", " ")
    if normalized in {"past year", "last year", "past 1 year", "last 1 year"}:
        return True
    return resolve_date_range(value).used_default


@dataclass(frozen=True)
class _MoneyRoleEvidence:
    recurring_contribution: float | None = None
    total_capital: float | None = None


def _money_role_evidence(
    *,
    current_user_message: str,
    requested_field: str,
) -> _MoneyRoleEvidence:
    normalized = _normalized_text(current_user_message)
    recurring: float | None = None
    total: float | None = None
    matches = list(_iter_amount_matches(normalized))
    for index, match in enumerate(matches):
        value = _amount_value(match.group("amount"), match.group("suffix"))
        if value is None:
            continue
        start, end = match.span()
        previous_end = matches[index - 1].end() if index > 0 else max(0, start - 48)
        next_start = (
            matches[index + 1].start() if index + 1 < len(matches) else len(normalized)
        )
        before = normalized[max(previous_end, start - 48) : start]
        after = normalized[end : min(next_start, end + 72)]
        if _is_time_count_context(after=after):
            continue
        strong_recurring = _is_strong_recurring_context(before=before, after=after)
        if (
            _is_total_capital_context(
                before=before,
                after=after,
            )
            and not strong_recurring
        ):
            total = value
            continue
        if strong_recurring or _is_recurring_context(before=before, after=after):
            recurring = value

    if requested_field == "capital_amount" and recurring is None and total is None:
        if len(matches) == 1:
            match = matches[0]
            recurring = _amount_value(match.group("amount"), match.group("suffix"))

    return _MoneyRoleEvidence(
        recurring_contribution=recurring,
        total_capital=total,
    )


def _iter_amount_matches(text: str) -> Any:
    return re.finditer(
        r"(?<![a-z0-9])\$?\s*(?P<amount>\d+(?:,\d{3})*(?:\.\d+)?)\s*"
        r"(?P<suffix>k|m|thousand|million)?(?![a-z0-9])",
        text,
    )


def _is_time_count_context(*, after: str) -> bool:
    return bool(
        re.match(
            r"\s*(?:day|days|week|weeks|month|months|quarter|quarters|year|years)\b",
            after,
        )
    )


def _amount_value(raw_amount: str | None, suffix: str | None) -> float | None:
    if not raw_amount:
        return None
    try:
        value = float(raw_amount.replace(",", ""))
    except ValueError:
        return None
    multiplier = {
        "k": 1_000.0,
        "thousand": 1_000.0,
        "m": 1_000_000.0,
        "million": 1_000_000.0,
    }.get(str(suffix or "").lower(), 1.0)
    return value * multiplier


def _is_total_capital_context(*, before: str, after: str) -> bool:
    context = f"{before} {after}"
    return bool(
        re.search(
            r"\b(?:total capital|total budget|overall budget|starting capital|"
            r"initial capital|starting principal|initial principal|my total|"
            r"account size|portfolio size|investment budget|total investment|"
            r"total amount|overall amount|overall capital|available capital|"
            r"available budget|budget|total|overall|max|maximum|cap|capped|"
            r"ceiling|limit|limited)\b",
            context,
        )
        or re.search(
            r"\b(?:i|we)?\s*(?:have|got|with|using|use)\b.*\b(?:to invest|"
            r"available|as budget|as a budget)\b",
            context,
        )
    )


def _is_strong_recurring_context(*, before: str, after: str) -> bool:
    context = f"{before} {after}"
    cadence_pattern = (
        r"\b(?:daily|weekly|monthly|quarterly|yearly|annually|each day|"
        r"every day|per day|each week|every week|per week|each month|"
        r"every month|per month|each quarter|every quarter|per quarter|"
        r"each year|every year|per year)\b"
    )
    recurring_verb_pattern = (
        r"\b(?:recurring|recurrent|contribution|contribute|investing|buy|"
        r"buys|purchase|purchases|dca)\b"
    )
    return bool(
        re.match(rf"\s*{cadence_pattern}", after)
        or re.search(r"\b(?:each|every|per)\b", after)
        or (
            re.search(recurring_verb_pattern, context)
            and re.search(cadence_pattern, context)
        )
    )


def _is_recurring_context(*, before: str, after: str) -> bool:
    context = f"{before} {after}"
    return bool(
        re.search(
            r"\b(?:recurring|recurrent|contribution|contribute|buy|buys|"
            r"purchase|purchases|each week|every week|per week|each month|"
            r"every month|per month|each day|every day|per day|each year|"
            r"every year|per year)\b",
            context,
        )
    )


def _normalized_text(value: str) -> str:
    lowered = value.lower()
    lowered = re.sub(r"[^a-z0-9$.,\s]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _recurring_cadence_evidence(message: str) -> str | None:
    normalized = _normalized_text(message)
    if re.search(r"\b(?:daily|each day|every day|per day)\b", normalized):
        return "daily"
    if re.search(r"\b(?:weekly|each week|every week|per week)\b", normalized):
        return "weekly"
    if re.search(r"\b(?:monthly|each month|every month|per month)\b", normalized):
        return "monthly"
    if re.search(r"\b(?:yearly|annually|each year|every year|per year)\b", normalized):
        return "yearly"
    return None
