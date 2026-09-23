"""Public confirmed-finance artifacts; domain models own command arguments."""

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from .common import Evidence, Model


class CommandExecution(Model):
    scope: Literal["local_record", "scheduled_paper", "recorded_bill_payment"] = (
        "local_record"
    )
    real_money: Literal[False] = False
    scheduled_after_confirmation: bool = False


class CommandDeclaration(Model):
    name: str
    title_key: str
    description: str
    input_schema: dict[str, Any]
    target_page: str
    target_query: dict[str, str] = Field(default_factory=dict)
    requires_confirmation: Literal[True] = True
    execution: CommandExecution = Field(default_factory=CommandExecution)


class CommandField(Model):
    key: str
    value: str | int | bool | list[str]
    kind: Literal["text", "number", "money", "date", "list"] = "text"
    currency: str | None = None
    editable: bool = True


class CommandTarget(Model):
    page: str
    record_id: str | None = None
    query: dict[str, str] = Field(default_factory=dict)


class CommandCurrency(Model):
    kind: Literal["account", "record", "explicit", "ui_default"]
    code: str
    record_id: str | None = None
    source_id: str | None = None
    stated_request_id: str | None = None


class Proposal(Model):
    proposal_id: str
    conversation_id: str
    command_name: str
    revision: int
    status: Literal["pending", "superseded", "consumed", "cancelled"]
    title_key: str
    fields: list[CommandField]
    arguments: dict[str, Any]
    currency: list[CommandCurrency]
    evidence: list[Evidence]
    target: CommandTarget
    execution: CommandExecution = Field(default_factory=CommandExecution)
    created_at: datetime
    expires_at: datetime


class CommandReceipt(Model):
    receipt_id: str
    proposal_id: str
    conversation_id: str
    command_name: str
    revision: int
    title_key: str
    fields: list[CommandField]
    evidence: list[Evidence]
    target: CommandTarget
    execution: CommandExecution = Field(default_factory=CommandExecution)
    record_id: str
    created_at: datetime


class RecordReference(Model):
    record_id: str = Field(min_length=1, max_length=160)
