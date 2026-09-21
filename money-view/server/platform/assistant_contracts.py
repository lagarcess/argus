"""Typed question and receipt contracts for the contextual assistant."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field, model_validator

from .common import CURRENCY_DIGITS, Evidence, Model

Action = Literal[
    "spending",
    "budget_review",
    "net_worth",
    "goal_progress",
    "portfolio_review",
    "credit_review",
]
State = Literal["active", "archived", "trashed"]


class Parameters(Model):
    currency: str = "USD"
    month: str = Field(
        default_factory=lambda: date.today().strftime("%Y-%m"),
        pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
    )

    @model_validator(mode="after")
    def supported_currency(self) -> Parameters:
        if self.currency not in CURRENCY_DIGITS:
            raise ValueError("unsupported_currency")
        date.fromisoformat(self.month + "-01")
        if self.month.startswith("9999"):
            raise ValueError("unsupported_month")
        return self


class Ask(Model):
    action: Action | None = None
    message: str | None = Field(default=None, min_length=1, max_length=4000)
    parameters: Parameters = Field(default_factory=Parameters)
    locale: Literal["es-419", "en"] = "es-419"
    conversation_id: str | None = None
    page: str | None = Field(default=None, max_length=40)

    @model_validator(mode="after")
    def one_input(self) -> Ask:
        if (self.action is None) == (self.message is None):
            raise ValueError("exactly_one_action_or_message")
        return self


class SemanticChoice(Model):
    action: Action | None
    parameters: Parameters | None

    @model_validator(mode="after")
    def consistent_action(self) -> SemanticChoice:
        if (self.action is None) != (self.parameters is None):
            raise ValueError("action_requires_parameters")
        return self


class Target(Model):
    page: Literal[
        "spending",
        "budgets",
        "accounts",
        "goals",
        "investments",
        "credit",
        "transactions",
    ]
    query: dict[str, str] = Field(default_factory=dict)
    record_ids: list[str] = Field(default_factory=list)


class Fact(Model):
    key: str
    value: str
    unit: Literal["money", "percent", "count"] = "money"
    currency: str | None = None
    record_name: str | None = None
    notes: list[Literal["partial_unpriced_holdings"]] = Field(default_factory=list)
    source: Evidence
    target: Target


class ConversationUpdate(Model):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    state: State | None = None
    saved: bool | None = None

    @model_validator(mode="after")
    def nonempty(self) -> ConversationUpdate:
        if not self.model_fields_set or any(
            getattr(self, key) is None for key in self.model_fields_set
        ):
            raise ValueError("empty_update")
        if self.title is not None and not self.title.strip():
            raise ValueError("empty_title")
        return self


class NoticeUpdate(Model):
    state: Literal["unread", "read", "dismissed"]


class TrashAll(Model):
    confirmation: Literal["TRASH HOUSEHOLD CONVERSATIONS"]
