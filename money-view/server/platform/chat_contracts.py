"""Closed local conversation inputs. Models propose; typed commands own writes."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import Field, JsonValue, model_validator

from server.argus_core.tool_contracts import ToolResultCard

from .assistant_contracts import Action, Fact
from .command_contracts import CommandField, CommandReceipt, CommandTarget, Proposal
from .common import CURRENCY_DIGITS, Evidence, Model


class ReadParameters(Model):
    currency: str | None = None
    month: str | None = None


class ReadPlan(Model):
    kind: Literal["read"] = "read"
    action: Action
    parameters: ReadParameters = Field(default_factory=ReadParameters)


class RecordReadPlan(Model):
    kind: Literal["records"] = "records"
    resource: Literal["accounts", "transactions"]
    account_id: str | None = Field(default=None, max_length=128)
    record_id: str | None = Field(default=None, max_length=128)
    currency: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    category: str | None = Field(default=None, max_length=120)
    limit: int = Field(default=20, ge=1, le=50)
    offset: int = Field(default=0, ge=0, le=100_000)


class CalculationPlan(Model):
    kind: Literal["calculation"] = "calculation"
    tool_name: str = Field(min_length=1, max_length=80)
    artifact_id: str | None = Field(default=None, max_length=128)
    arguments: dict[str, JsonValue]


class ProposalPlan(Model):
    kind: Literal["proposal"] = "proposal"
    command_name: str = Field(min_length=1, max_length=80)
    arguments: dict[str, JsonValue]


class RevisionPlan(Model):
    kind: Literal["revise_proposal"] = "revise_proposal"
    proposal_id: str = Field(min_length=1, max_length=128)
    revision: int = Field(ge=1)
    changes: dict[str, JsonValue] = Field(min_length=1)


class ClarificationPlan(Model):
    kind: Literal["clarify"] = "clarify"
    question: str = Field(min_length=1, max_length=2000)


class UnsupportedPlan(Model):
    kind: Literal["unsupported"] = "unsupported"
    reason: str = Field(min_length=1, max_length=1000)


TurnPlan = Annotated[
    ReadPlan
    | RecordReadPlan
    | CalculationPlan
    | ProposalPlan
    | RevisionPlan
    | ClarificationPlan
    | UnsupportedPlan,
    Field(discriminator="kind"),
]
PreparedAction = Annotated[
    ReadPlan | RecordReadPlan | CalculationPlan | ProposalPlan | RevisionPlan,
    Field(discriminator="kind"),
]


class PlannedTurn(Model):
    plan: TurnPlan


class Mention(Model):
    record_kind: str | None = Field(default=None, max_length=40)
    kind: Literal["account", "record"]
    id: str = Field(min_length=1, max_length=128)


class TurnRequest(Model):
    turn_id: str = Field(min_length=1, max_length=128)
    conversation_id: str | None = Field(default=None, max_length=128)
    text: str | None = Field(default=None, min_length=1, max_length=4000)
    action: PreparedAction | None = None
    locale: Literal["es-419", "en"] = "es-419"
    currency: str | None = None
    default_currency: str | None = None
    account_id: str | None = Field(default=None, max_length=128)
    mentions: list[Mention] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def one_input(self):
        if (self.text is None) == (self.action is None):
            raise ValueError("exactly_one_text_or_action")
        if any(
            value is not None and value not in CURRENCY_DIGITS
            for value in (self.currency, self.default_currency)
        ):
            raise ValueError("unsupported_currency")
        return self


class ConversationCreate(Model):
    title: str = Field(default="Argus", min_length=1, max_length=120)


class ConversationPatch(Model):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    pinned: bool | None = None
    state: Literal["active", "archived", "trashed"] | None = None

    @model_validator(mode="after")
    def nonempty(self):
        if not self.model_fields_set or any(
            getattr(self, key) is None for key in self.model_fields_set
        ):
            raise ValueError("empty_update")
        if self.title is not None and not self.title.strip():
            raise ValueError("empty_title")
        return self


class ConfirmProposal(Model):
    expected_revision: int = Field(ge=1)


class PatchProposal(Model):
    expected_revision: int = Field(ge=1)
    changes: dict[str, JsonValue] = Field(min_length=1)
    request_id: str = Field(min_length=1, max_length=128)


class CancelProposal(Model):
    expected_revision: int = Field(ge=1)


# Public transcript projections. Stored receipts are immutable snapshots.


class Conversation(Model):
    id: str
    household_id: str
    user_id: str
    title: str
    state: Literal["active", "archived", "trashed"]
    pinned: bool
    created_at: str
    updated_at: str


class ReadCard(Model):
    kind: Literal["read"] = "read"
    action: Action
    code: Literal["grounded_records", "no_records"]
    facts: list[Fact]


class CalculationCard(Model):
    kind: Literal["calculation"] = "calculation"
    card: ToolResultCard
    evidence: list[Evidence] = Field(default_factory=list)


class RecordRow(Model):
    record_id: str
    title: str
    fields: list[CommandField]
    evidence: list[Evidence]
    target: CommandTarget


class RecordCard(Model):
    kind: Literal["records"] = "records"
    resource: Literal["accounts", "transactions"]
    query: RecordReadPlan
    rows: list[RecordRow]
    total: int
    limit: int
    offset: int


class ProposalCard(Model):
    kind: Literal["proposal"] = "proposal"
    proposal: Proposal


class ReceiptCard(Model):
    kind: Literal["receipt"] = "receipt"
    receipt: CommandReceipt


Card = Annotated[
    ReadCard | RecordCard | CalculationCard | ProposalCard | ReceiptCard,
    Field(discriminator="kind"),
]


class ChatMessage(Model):
    id: str
    role: Literal["user", "assistant"]
    turn_id: str
    text: str | None = None
    code: str
    cards: list[Card] = Field(default_factory=list)
    created_at: str


class FinalEvent(Model):
    type: Literal["final"] = "final"
    turn_id: str
    conversation_id: str
    status: Literal[
        "completed", "model_unavailable", "interrupted", "in_progress", "failed"
    ]
    code: str
    message: ChatMessage | None = None
