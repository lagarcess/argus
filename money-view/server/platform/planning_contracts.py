"""Typed planning inputs. Currency precision is owned by common.minor_units."""
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .common import Model, NonNegativeAmount, PositiveAmount, minor_units

Currency = Annotated[str, Field(min_length=3, max_length=3)]
Label = Annotated[str, Field(min_length=1, max_length=120)]
Rate = Annotated[Decimal, Field(ge=-99, le=100, allow_inf_nan=False)]


class MoneyModel(Model):
    currency: Currency

    @model_validator(mode="after")
    def exact_money(self):
        if hasattr(self, "category"):
            from .ledger_contracts import CATEGORIES
            if CATEGORIES.get(self.category) != "expense":
                raise ValueError("invalid_category")
        for key in ("amount", "limit", "target_amount", "monthly_contribution", "initial_balance", "monthly_withdrawal"):
            if hasattr(self, key):
                minor_units(getattr(self, key), self.currency)
        return self


class BudgetInput(MoneyModel):
    category: Label
    month: Annotated[str, Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]
    limit: NonNegativeAmount

    @model_validator(mode="after")
    def valid_month(self):
        date.fromisoformat(self.month + "-01")
        return self


class BillInput(MoneyModel):
    name: Label
    account_id: Label
    category: Label
    amount: PositiveAmount
    cadence: Literal["weekly", "monthly", "quarterly", "yearly"] = "monthly"
    anchor_date: date


class PauseInput(Model):
    paused: bool


class PayInput(Model):
    due_date: date


class GoalInput(MoneyModel):
    name: Label
    target_date: date
    target_amount: PositiveAmount
    monthly_contribution: NonNegativeAmount = Decimal(0)


class Allocation(Model):
    account_id: Label
    amount: NonNegativeAmount


class AllocationInput(Model):
    allocations: list[Allocation] = Field(max_length=100)

    @model_validator(mode="after")
    def unique_accounts(self):
        if len({row.account_id for row in self.allocations}) != len(self.allocations):
            raise ValueError("duplicate_allocation_account")
        return self


class ScenarioInputs(MoneyModel):
    initial_balance: NonNegativeAmount = Decimal(0)
    monthly_contribution: NonNegativeAmount = Decimal(0)
    monthly_withdrawal: NonNegativeAmount = Decimal(0)
    horizon_years: int = Field(default=20, ge=1, le=100)
    annual_return_pct: Rate = Decimal(0)
    inflation_pct: Rate = Decimal(0)
    annual_fee_pct: Annotated[Decimal, Field(ge=0, le=20, allow_inf_nan=False)] = Decimal(0)
    contribution_start_month: int = Field(default=1, ge=1, le=1200)
    contribution_end_month: int | None = Field(default=None, ge=1, le=1200)
    withdrawal_start_month: int = Field(default=1, ge=1, le=1200)
    withdrawal_end_month: int | None = Field(default=None, ge=1, le=1200)
    timing: Literal["begin", "end"] = "end"

    @model_validator(mode="after")
    def ordered_windows(self):
        for flow in ("contribution", "withdrawal"):
            end = getattr(self, flow + "_end_month")
            if end is not None and end < getattr(self, flow + "_start_month"):
                raise ValueError("invalid_cash_flow_window")
        return self


Template = Literal["home", "kids", "job", "move", "marriage", "retirement", "sabbatical"]


class ScenarioInput(Model):
    name: Label
    template: Template
    inputs: ScenarioInputs
