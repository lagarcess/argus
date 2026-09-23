"""Validated service records and private persistence helpers."""

from __future__ import annotations

import csv
import io
import json
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import Depends
from fastapi.responses import Response
from pydantic import Field, model_validator

from ..store import Store
from .common import (
    CURRENCY_DIGITS,
    Context,
    Evidence,
    Model,
    NonNegativeAmount,
    PlatformError,
    get_context,
    get_store,
    identifier,
    minor_units,
    now,
)

StoreDependency = Annotated[Store, Depends(get_store)]
ContextDependency = Annotated[Context, Depends(get_context)]

Text = Annotated[str, Field(min_length=1, max_length=200, pattern=r"\S")]
Percent = Annotated[Decimal, Field(ge=0, le=100, allow_inf_nan=False)]


class CurrencyModel(Model):
    currency: str = "USD"

    @model_validator(mode="after")
    def known_currency(self):
        if self.currency not in CURRENCY_DIGITS:
            raise ValueError("unsupported_currency")
        return self


class CreditAccount(CurrencyModel):
    name: Text
    balance: NonNegativeAmount
    credit_limit: NonNegativeAmount
    apr_pct: Annotated[Decimal, Field(ge=0, le=1000, allow_inf_nan=False)]
    minimum_payment: NonNegativeAmount
    as_of: date

    @model_validator(mode="after")
    def money_precision(self):
        for value in (self.balance, self.credit_limit, self.minimum_payment):
            minor_units(value, self.currency)
        return self


class Payoff(Model):
    account_id: Text
    extra_monthly_payment: NonNegativeAmount = Decimal("0")


class Organizer(CurrencyModel):
    country: Annotated[str, Field(pattern=r"^[A-Z]{2}$")]
    year: Annotated[int, Field(ge=1900, le=2100)]


class TaxItem(Model):
    organizer_id: Text
    kind: Literal["income", "expense", "document", "checklist"]
    title: Text
    amount: NonNegativeAmount | None = None
    effective_on: date

    @model_validator(mode="after")
    def financial_amount(self):
        if (self.kind in ("income", "expense")) != (self.amount is not None):
            raise ValueError("amount_required_only_for_financial_items")
        return self


class Completion(Model):
    completed: bool


class OrganizerStatus(Model):
    status: Literal["open", "complete"]


class TaxScenario(Model):
    organizer_id: Text
    user_rate_pct: Percent


class EstateAsset(CurrencyModel):
    name: Text
    value: NonNegativeAmount
    as_of: date

    @model_validator(mode="after")
    def precision(self):
        minor_units(self.value, self.currency)
        return self


class Contact(Model):
    name: Text
    relationship: Text
    email: (
        Annotated[str, Field(max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")]
        | None
    ) = None


class Share(Model):
    contact_id: Text
    share_pct: Annotated[Decimal, Field(gt=0, le=100, allow_inf_nan=False)]


class Beneficiaries(Model):
    shares: Annotated[list[Share], Field(max_length=100)]

    @model_validator(mode="after")
    def allocation(self):
        if sum((s.share_pct for s in self.shares), Decimal(0)) > 100:
            raise ValueError("beneficiary_total_exceeds_100")
        if len({s.contact_id for s in self.shares}) != len(self.shares):
            raise ValueError("duplicate_beneficiary")
        return self


class Document(Model):
    title: Text
    location: Text
    effective_on: date


class Checklist(Model):
    title: Text


class Reservation(Model):
    slot_id: Text
    request_key: Text


class Reschedule(Model):
    slot_id: Text


class Membership(Model):
    plan_id: Literal["monthly", "annual"]
    request_key: Text


class Enrollment(Model):
    code: Text


class Benefit(Model):
    benefit_id: Literal["learning", "wellness", "planning"]


# These names are private constants; no request selects a table or arbitrary payload.
TABLES = (
    "p_credit_accounts",
    "p_credit_reports",
    "p_tax_organizers",
    "p_tax_items",
    "p_tax_scenarios",
    "p_estate_assets",
    "p_estate_contacts",
    "p_estate_beneficiaries",
    "p_estate_documents",
    "p_estate_checklist",
    "p_service_memberships",
    "p_membership_receipts",
    "p_employer_enrollments",
)


def rows(db, table, household):
    return [
        json.loads(r["document"])
        for r in db.execute(
            f"SELECT document FROM {table} WHERE household_id=? ORDER BY rowid",
            (household,),
        )
    ]


def record(db, table, household, record_id):
    row = db.execute(
        f"SELECT document FROM {table} WHERE household_id=? AND id=?",
        (household, record_id),
    ).fetchone()
    if row is None:
        raise PlatformError("record_not_found", 404)
    return json.loads(row["document"])


def save(db, table, household, document):
    db.execute(
        f"INSERT INTO {table}(id,household_id,document) VALUES(?,?,?) ON CONFLICT(household_id,id) DO UPDATE SET document=excluded.document",
        (document["id"], household, json.dumps(document)),
    )
    return document


def new_record(payload, prefix):
    return {
        "id": identifier(prefix),
        **payload.model_dump(mode="json"),
        "recorded_at": now().isoformat(),
    }


def evidence(record_id, as_of, kind="user", method=None):
    return Evidence(
        id=f"source-{record_id}",
        kind=kind,
        title="Local synthetic fixture"
        if kind == "synthetic"
        else "Calculation from recorded inputs"
        if kind == "calculated"
        else "User recorded value",
        as_of=as_of,
        recorded_at=now(),
        method=method,
    ).model_dump(mode="json")


def csv_download(filename, headers, data):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in data:
        writer.writerow(
            [
                (
                    "'" + v
                    if v.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "\n"))
                    else v
                )
                if isinstance(v, str)
                else v
                for v in row
            ]
        )
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
    )


def json_download(filename, data):
    return Response(
        json.dumps(data, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}.json"'},
    )
