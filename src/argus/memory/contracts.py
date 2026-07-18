"""Typed contracts for personalization memory.

Canonical memory truth is Argus-owned; provider identifiers are derivative
metadata. A ``MemoryRecord`` exists only with confirmed consent.
See ``docs/specs/personalization-memory-program.md``.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class MemoryCategory(str, Enum):
    """Closed allowlist of storable memory categories (decision memo §15.3)."""

    PERSONALIZATION_PREFERENCE = "personalization_preference"
    WORKFLOW_PREFERENCE = "workflow_preference"
    EXPLICIT_DECISION_NOTE = "explicit_decision_note"
    AUTOMATION_INTENT = "automation_intent"
    PAST_SESSION_ANCHOR = "past_session_anchor"


class SensitivityFlag(str, Enum):
    """Content classes that must never become durable memory automatically."""

    BROKER_CREDENTIAL = "broker_credential"
    ACCOUNT_BALANCE = "account_balance"
    EXACT_HOLDINGS = "exact_holdings"
    TAX_LEGAL_STATUS = "tax_legal_status"
    IDENTIFYING_FINANCIAL_DETAIL = "identifying_financial_detail"
    HEALTH = "health"
    EMPLOYMENT = "employment"
    FAMILY = "family"
    RAW_CONVERSATION = "raw_conversation"


class ConsentState(str, Enum):
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    DECLINED = "declined"


CONSENT_VERSION = "v1"

SourceKind = Literal[
    "decision_note",
    "evidence_artifact",
    "conversation",
    "explicit_request",
]


class MemorySourceRef(BaseModel):
    """Provenance pointer to the Argus record a memory came from."""

    kind: SourceKind
    ref_id: str = Field(min_length=1)


class ProposalReason(str, Enum):
    EXPLICIT_REQUEST = "explicit_request"
    SAVED_DECISION = "saved_decision"


class MemoryCandidate(BaseModel):
    """A proposed memory. Never durable and never retrievable as memory."""

    id: str
    user_id: str
    category: MemoryCategory
    proposed_value: str = Field(min_length=1)
    label: str = Field(min_length=1, max_length=120)
    future_benefit: str = Field(min_length=1)
    source_refs: list[MemorySourceRef] = Field(min_length=1)
    sensitivity_flags: list[SensitivityFlag] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    proposal_reason: ProposalReason
    locale: str = "en"
    created_at: datetime


class ConsentGrant(BaseModel):
    state: ConsentState
    version: str = CONSENT_VERSION
    decided_at: datetime


class MemoryRecord(BaseModel):
    """A user-confirmed canonical memory owned by exactly one user."""

    id: str
    user_id: str
    category: MemoryCategory
    value: str = Field(min_length=1)
    label: str = Field(min_length=1, max_length=120)
    source_refs: list[MemorySourceRef] = Field(min_length=1)
    consent: ConsentGrant
    stored_reason: str = Field(min_length=1)
    enabled: bool = True
    created_at: datetime
    updated_at: datetime
    last_used_at: datetime | None = None
    provider_ref: str | None = None

    @model_validator(mode="after")
    def _require_confirmed_consent(self) -> "MemoryRecord":
        if self.consent.state is not ConsentState.CONFIRMED:
            raise ValueError("a MemoryRecord requires confirmed consent")
        return self


class RetrievedMemory(BaseModel):
    """A confirmed memory returned to a caller, with its selection rationale."""

    record: MemoryRecord
    why_selected: str = Field(min_length=1)
    provenance: list[MemorySourceRef]
