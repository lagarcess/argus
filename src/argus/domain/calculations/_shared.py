"""What every calculation declaration shares: argument bases, facts and failures.

Presenters build facts from typed results; the declaration layer owns
editability, the retained unknown, units and provenance. Money is rounded
once here, at the reader boundary, so a card and a decision print the same
digits; the typed result keeps full precision.
"""

from __future__ import annotations

from calendar import monthrange
from collections.abc import Sequence
from datetime import date, timedelta
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from argus.domain.finance.outcomes import NoSolution
from argus.domain.home_country import currency_codes
from argus.domain.tool_contracts import (
    LocalizedText,
    ToolFact,
    ToolFactSource,
    ToolInputFact,
    ToolRepair,
    ToolScalar,
    ToolVisual,
    ToolVisualPoint,
)
from argus.domain.tool_declaration import ToolInvocationError, ToolPolicy

MONEY_DECIMALS = 2
PERCENT_DECIMALS = 2
FIELD_LABEL_PREFIX = "tools.calc.fields"
UNIT_CURRENCY_KEY = "tools.calc.units.currency"
UNIT_PERCENT_KEY = "chat.tools.units.percent"
UNIT_MONTHS_KEY = "tools.calc.units.months"
UNIT_YEARS_KEY = "tools.calc.units.years"
UNIT_MULTIPLE_KEY = "tools.calc.units.multiple"
NOTE_PREFIX = "tools.calc.notes"
# The most periods a plan's arguments accept; a solved count past it is no plan.
MAX_PERIODS = 1200
REPAIR_PREFIX = "tools.calc.repairs"
# The one argument name that identifies an asset a calculation is about.
SYMBOL_FIELD = "symbol"
# A required input neither the user nor a page supplied.
MISSING_INPUT_CODE = "missing_input"


def _tender_currency(value: str) -> str:
    code = value.strip().upper()
    if code not in currency_codes():
        raise ValueError("currency must be an ISO 4217 code in use")
    return code


Currency = Annotated[str, AfterValidator(_tender_currency)]
Symbol = Annotated[str | None, Field(default=None, max_length=24)]


class CalculationArguments(BaseModel):
    """Typed inputs, the currency they are counted in, and where each came from."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    currency: Currency
    sources: dict[str, ToolFactSource] = Field(default_factory=dict)


class CalculationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


def free_policy(*editable: str, driving: Sequence[str] = ()) -> ToolPolicy:
    """A free calculation: local, never confirmed, instantly recomputed, with the
    inputs that drive its result named most telling first."""
    return ToolPolicy(
        execution="local",
        external_calls=0,
        confirmation="never",
        editable_fields=tuple(editable),
        driving_fields=tuple(driving),
        retain_unknown=True,
        public_receipt="typed_facts",
    )


def text(locale_key: str, **interpolation: ToolScalar) -> LocalizedText:
    return LocalizedText(locale_key=locale_key, interpolation_args=dict(interpolation))


def field_label(name: str) -> LocalizedText:
    return text(f"{FIELD_LABEL_PREFIX}.{name}")


def currency_unit(currency: str) -> LocalizedText:
    return text(UNIT_CURRENCY_KEY, code=currency)


def money_fact(name: str, amount: float, currency: str) -> ToolFact:
    return ToolFact(
        name=name,
        label=field_label(name),
        value=round(amount, MONEY_DECIMALS),
        unit=currency_unit(currency),
    )


def percent_fact(name: str, fraction: float) -> ToolFact:
    return ToolFact(
        name=name,
        label=field_label(name),
        value=round(fraction * 100.0, PERCENT_DECIMALS),
        unit=text(UNIT_PERCENT_KEY),
    )


def number_fact(
    name: str, value: ToolScalar, unit: LocalizedText | None = None
) -> ToolFact:
    return ToolFact(name=name, label=field_label(name), value=value, unit=unit)


def input_fact(
    name: str, value: ToolScalar, unit: LocalizedText | None = None
) -> ToolInputFact:
    """The declaration fills editability, the unknown flag and provenance."""
    return ToolInputFact(name=name, label=field_label(name), value=value, unit=unit)


def period_unit(per_year: int) -> LocalizedText | None:
    """What one period counts at a frequency: months at twelve a year, years at
    one; any other frequency is a plain count of periods."""
    if per_year == 12:
        return text(UNIT_MONTHS_KEY)
    if per_year == 1:
        return text(UNIT_YEARS_KEY)
    return None


def money_input(name: str, value: float | None, currency: str) -> ToolInputFact:
    return input_fact(name, value, currency_unit(currency))


def percent_input(name: str, value: float | None) -> ToolInputFact:
    return input_fact(name, value, text(UNIT_PERCENT_KEY))


def note(code: str, **interpolation: ToolScalar) -> LocalizedText:
    return text(f"{NOTE_PREFIX}.{code}", **interpolation)


def no_solution(
    outcome: NoSolution,
    *,
    repair_label: str | None = None,
) -> ToolInvocationError:
    """A typed outcome naming the field, with the computed repair as a tap."""
    repair = None
    if outcome.repair:
        repair = ToolRepair(
            label=text(f"{REPAIR_PREFIX}.{repair_label or outcome.code}"),
            changes={
                name: round(value, MONEY_DECIMALS)
                for name, value in outcome.repair.items()
            },
        )
    return ToolInvocationError(
        "invalid", code=outcome.code, fields=(outcome.field,), repair=repair
    )


def known(value: float | None, field: str) -> float:
    if value is None:
        raise ToolInvocationError("invalid", code="exactly_one_unknown", fields=(field,))
    return value


def required(value: float | None, field: str) -> float:
    """An input no source supplied yet; the card keeps it blank and typeable."""
    if value is None:
        raise ToolInvocationError("invalid", code=MISSING_INPUT_CODE, fields=(field,))
    return value


def pct(value: float) -> float:
    """A percentage argument as the fraction the math uses."""
    return value / 100.0


# Frequencies a whole number of days apart: fortnightly, weekly and daily.
_DAYS_PER_PERIOD = {26: 14, 52: 7, 365: 1}


def dated_path(
    start: date,
    periods_per_year: int,
    values: Sequence[float],
    *,
    currency: str,
    base_value: float | None = None,
) -> ToolVisual | None:
    """A value per period from ``start``, stepped by the period length: whole
    months for a frequency that divides the year into months, whole days for a
    fortnightly, weekly or daily one. Any other frequency has no dated path."""
    if len(values) < 2 or not periods_per_year:
        return None
    months = 12 // periods_per_year if 12 % periods_per_year == 0 else 0
    days = _DAYS_PER_PERIOD.get(periods_per_year, 0)
    if not months and not days:
        return None
    series: list[ToolVisualPoint] = []
    for index, value in enumerate(values, start=1):
        if months:
            total = start.month - 1 + index * months
            year, month = start.year + total // 12, total % 12 + 1
            when = date(year, month, min(start.day, monthrange(year, month)[1]))
        else:
            when = start + timedelta(days=index * days)
        series.append(ToolVisualPoint(time=when.isoformat(), value=float(value)))
    return ToolVisual(
        kind="value_path", currency=currency, base_value=base_value, series=series
    )


def rounded(value: float, decimals: int = MONEY_DECIMALS) -> float:
    return round(value, decimals)


def dump(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")
