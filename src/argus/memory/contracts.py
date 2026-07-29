"""Canonical contracts for the isolated personalization-memory lifecycle."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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


class MemoryProposalTrigger(str, Enum):
    SAVED_DECISION = "saved_decision"
    EXPLICIT_REQUEST = "explicit_request"
    ASSISTED_STABLE_PREFERENCE = "assisted_stable_preference"


class MemoryOperationContext(str, Enum):
    ORDINARY = "ordinary"
    BROKER = "broker"
    EXPORT = "export"
    RESTRICTED_FINANCIAL = "restricted_financial"


class MemoryUsePurpose(str, Enum):
    """Closed purposes that cannot change canonical investing behavior."""

    REVISIT_SAVED_DECISION = "revisit_saved_decision"
    COMPARE_SAVED_DECISIONS = "compare_saved_decisions"
    EXPLAIN_PRIOR_DECISION = "explain_prior_decision"
    INSPECT_MEMORY = "inspect_memory"


class MemorySelectionReason(str, Enum):
    PROVIDER_RANKED = "provider_ranked"
    CANONICAL_TOKEN_MATCH = "canonical_token_match"


class ProviderReconciliationStatus(str, Enum):
    SYNCHRONIZED = "synchronized"
    NOT_APPLICABLE = "not_applicable"
    RECONCILIATION_REQUIRED = "reconciliation_required"


class SensitivityStatus(str, Enum):
    UNASSESSED = "unassessed"
    CLEAR = "clear"
    RESTRICTED = "restricted"


class MemorySensitivityFlag(str, Enum):
    BROKER_CREDENTIAL = "broker_credential"
    ACCOUNT_BALANCE = "account_balance"
    EXACT_HOLDINGS = "exact_holdings"
    TAX_OR_LEGAL_STATUS = "tax_or_legal_status"
    IDENTIFYING_FINANCIAL_DETAIL = "identifying_financial_detail"
    HEALTH = "health"
    EMPLOYMENT = "employment"
    FAMILY = "family"
    RAW_CONVERSATION = "raw_conversation"


class MemoryProvenance(BaseModel):
    """Stable pointer to an Argus-owned canonical source."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_kind: MemorySourceKind
    source_id: str = Field(min_length=1)
    source_version: str = Field(min_length=1)


MemorySourceRef = MemoryProvenance


class SensitivityAssessment(BaseModel):
    """Typed sensitivity result supplied by a future proposal boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: SensitivityStatus = SensitivityStatus.UNASSESSED
    flags: frozenset[MemorySensitivityFlag] = frozenset()

    @model_validator(mode="after")
    def _validate_flags(self) -> "SensitivityAssessment":
        if self.flags and self.status is not SensitivityStatus.RESTRICTED:
            raise ValueError("sensitivity flags require restricted status")
        return self


class MemoryConsentSettings(BaseModel):
    """Explicit category scope; memory is unavailable by default."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool = False
    enabled_categories: frozenset[MemoryCategory] = frozenset()

    @model_validator(mode="after")
    def _validate_scope(self) -> "MemoryConsentSettings":
        if self.enabled != bool(self.enabled_categories):
            raise ValueError("enabled consent requires a non-empty category scope")
        return self


class MemoryCandidateDraft(BaseModel):
    """LLM-proposable facts; deterministic policy owns storage eligibility."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    category: MemoryCategory
    value: str = Field(min_length=1)
    label: str = Field(min_length=1, max_length=120)
    future_benefit: str = Field(min_length=1)
    provenance: tuple[MemorySourceRef, ...] = Field(min_length=1)
    trigger: MemoryProposalTrigger
    sensitivity: SensitivityAssessment


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
    future_benefit: str = Field(min_length=1)
    provenance_refs: tuple[MemorySourceRef, ...] = Field(min_length=1)
    trigger: MemoryProposalTrigger
    sensitivity: SensitivityAssessment
    proposed_context: MemoryOperationContext
    opt_in_scope: frozenset[MemoryCategory] = frozenset()
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
    provenance_refs: tuple[MemorySourceRef, ...] = Field(min_length=1)
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
        if self.provenance_refs[0] != self.provenance:
            raise ValueError("primary provenance must lead provenance refs")
        return self


class RetrievedMemory(BaseModel):
    """Canonical memory selected for one bounded, allowed use."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    record: MemoryRecord
    selection_reason: MemorySelectionReason
    score: float = Field(ge=0, allow_inf_nan=False)
    provenance: tuple[MemorySourceRef, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_canonical_provenance(self) -> "RetrievedMemory":
        if self.provenance != self.record.provenance_refs:
            raise ValueError("retrieval provenance must come from the canonical record")
        return self


class MemoryExplanation(BaseModel):
    """Inspectable proof of where and how a canonical memory was confirmed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    record_id: str = Field(min_length=1)
    category: MemoryCategory
    provenance: tuple[MemorySourceRef, ...] = Field(min_length=1)
    consent_receipt_id: str = Field(min_length=1)
    consent_schema_version: MemoryConsentSchemaVersion
    confirmed_at: datetime


class MemoryEdit(BaseModel):
    """Narrow user control that cannot replace canonical identity or evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    value: str | None = Field(default=None, min_length=1)
    label: str | None = Field(default=None, min_length=1, max_length=120)
    sensitivity: SensitivityAssessment

    @field_validator("value", "label")
    @classmethod
    def _reject_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("memory edit fields must not be blank")
        return value

    @model_validator(mode="after")
    def _require_change(self) -> "MemoryEdit":
        if self.value is None and self.label is None:
            raise ValueError("edit requires a value or label change")
        return self


class MemoryControlResult(BaseModel):
    """Canonical control result with truthful derivative reconciliation state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    changed: bool
    record: MemoryRecord | None = None
    provider_status: ProviderReconciliationStatus

    @model_validator(mode="after")
    def _validate_unchanged_shape(self) -> "MemoryControlResult":
        if not self.changed and self.record is not None:
            raise ValueError("unchanged controls cannot return a record")
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
