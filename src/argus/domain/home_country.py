"""A profile's home country and currency, declared in Settings.

The country is an officially assigned ISO 3166-1 alpha-2 code, read from the
table the IANA time zone database ships (tzdata's ``iso3166.tab``), so the set
moves when the standard does. The currency it implies is the first tender
currency CLDR records there with no end date (babel). A user may override the
currency, and the profile resolves to the override when there is one.

Decision 8: both are stated, never inferred. Nothing here reads a message, an
address or a request.
"""

from __future__ import annotations

from datetime import date
from functools import cache
from importlib.resources import files
from typing import Annotated, Any

from babel.numbers import get_territory_currencies
from pydantic import AfterValidator, BeforeValidator, Field


@cache
def country_codes() -> frozenset[str]:
    """Every officially assigned ISO 3166-1 alpha-2 code."""
    table = files("tzdata").joinpath("zoneinfo", "iso3166.tab")
    return frozenset(
        line.split("\t", 1)[0]
        for line in table.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    )


def _in_use(country: str) -> list[str]:
    """The tender currencies CLDR records for a country with no end date, in
    CLDR's order. The record decides, never the calendar, so these codes change
    only with the installed data."""
    return [
        entry["currency"]
        for entry in get_territory_currencies(
            country,
            start_date=date.min,
            end_date=date.max,
            tender=True,
            include_details=True,
        )
        if entry["to"] is None
    ]


def country_currency(country: str) -> str | None:
    """The ISO 4217 currency a country implies, or None where CLDR lists none."""
    in_use = _in_use(country)
    return in_use[0] if in_use else None


def currency_codes() -> frozenset[str]:
    """Every currency in use in some country, which is what an override may name."""
    return frozenset(code for country in country_codes() for code in _in_use(country))


def resolved_currency(country: str | None, override: str | None) -> str | None:
    """The currency a profile counts in: the override, else the country's."""
    if override is not None:
        return override
    if country is None:
        return None
    return country_currency(country)


def _code(value: Any) -> Any:
    """Codes compare upper case, and a blank value is no choice."""
    if not isinstance(value, str):
        return value
    return value.strip().upper() or None


def _assigned_country(value: str | None) -> str | None:
    if value is not None and value not in country_codes():
        raise ValueError("country must be an assigned ISO 3166-1 alpha-2 code")
    return value


def _tender_currency(value: str | None) -> str | None:
    if value is not None and value not in currency_codes():
        raise ValueError("currency must be an ISO 4217 code in use")
    return value


# A stored code only has to have the right shape, so a code the standards later
# retire still loads; an edit is held to the current codes. Normalizing wraps
# the optional type, so a blank edit clears the setting.
CountryCode = Annotated[
    Annotated[str, Field(pattern=r"^[A-Z]{2}$")] | None,
    BeforeValidator(_code),
]
CurrencyCode = Annotated[
    Annotated[str, Field(pattern=r"^[A-Z]{3}$")] | None,
    BeforeValidator(_code),
]
AssignedCountryCode = Annotated[CountryCode, AfterValidator(_assigned_country)]
TenderCurrencyCode = Annotated[CurrencyCode, AfterValidator(_tender_currency)]
