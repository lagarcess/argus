"""Canonical contracts for the isolated personalization-memory lifecycle."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

MemoryConsentSchemaVersion = Literal["argus.memory-consent/v1"]
MEMORY_CONSENT_SCHEMA_VERSION: MemoryConsentSchemaVersion = "argus.memory-consent/v1"


class MemoryCategory(str, Enum):
    PERSONALIZATION_PREFERENCE = "personalization_preference"
    WORKFLOW_PREFERENCE = "workflow_preference"
    EXPLICIT_DECISION_NOTE = "explicit_decision_note"
    PAST_SESSION_ANCHOR = "past_session_anchor"


class MemorySourceKind(str, Enum):
    EVIDENCE_ARTIFACT = "evidence_artifact"
    DECISION_NOTE = "decision_note"
    IDEA = "idea"
    IDEA_VERSION = "idea_version"
    CONVERSATION = "conversation"
    MESSAGE = "message"


class MemoryProvenance(BaseModel):
    """Stable pointer to an Argus-owned canonical source."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_kind: MemorySourceKind
    source_id: str = Field(min_length=1)
    source_version: str = Field(min_length=1)


class SavedDecisionSource(BaseModel):
    """Canonical saved-decision facts eligible for a memory proposal."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1)
    provenance: MemoryProvenance


class MemoryCandidate(BaseModel):
    """Pending opt-in proposal; it is not a durable memory record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    owner_id: str = Field(min_length=1)
    category: MemoryCategory
    source: SavedDecisionSource
    opt_in_scope: frozenset[MemoryCategory] = Field(min_length=1)
    created_at: datetime


class ConfirmedMemoryConsentReceipt(BaseModel):
    """Versioned evidence of explicit confirmation for one candidate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    schema_version: MemoryConsentSchemaVersion = MEMORY_CONSENT_SCHEMA_VERSION
    confirmed: Literal[True] = True
    owner_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    scope: frozenset[MemoryCategory] = Field(min_length=1)
    confirmed_at: datetime


class MemoryRecord(BaseModel):
    """Immutable canonical memory backed by confirmed consent and provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    owner_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    category: MemoryCategory
    label: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1)
    provenance: MemoryProvenance
    consent_receipt: ConfirmedMemoryConsentReceipt
    created_at: datetime

    @model_validator(mode="after")
    def _validate_confirmed_scope(self) -> "MemoryRecord":
        if self.consent_receipt.owner_id != self.owner_id:
            raise ValueError("consent owner must match memory owner")
        if self.consent_receipt.candidate_id != self.candidate_id:
            raise ValueError("consent candidate must match memory candidate")
        if self.category not in self.consent_receipt.scope:
            raise ValueError("memory category must be included in confirmed consent")
        return self


class ProposalResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate: MemoryCandidate


class ConfirmationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    created: bool
    record: MemoryRecord | None = None
    consent_receipt: ConfirmedMemoryConsentReceipt | None = None

    @model_validator(mode="after")
    def _validate_result_shape(self) -> "ConfirmationResult":
        has_outputs = self.record is not None and self.consent_receipt is not None
        if self.created != has_outputs:
            raise ValueError(
                "created confirmation results require one record and one receipt"
            )
        return self
