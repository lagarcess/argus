"""API request and response models for personalization-memory endpoints.

Requests accept only client-decidable fields; triggers, sensitivity, policy
versions, and content digests are owned by the backend. No request carries a
sensitivity claim: every API entry is unassessed until a backend proposal
boundary assesses content, and policy suppresses unassessed input. Responses
never echo owner ids and serialize category scopes as sorted lists so the
contract is deterministic.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from argus.memory.contracts import (
    MAX_MEMORY_FUTURE_BENEFIT_LENGTH,
    MAX_MEMORY_VALUE_LENGTH,
    ConfirmationResult,
    MemoryCandidate,
    MemoryCategory,
    MemoryConsentAction,
    MemoryConsentActionReceipt,
    MemoryConsentSchemaVersion,
    MemoryConsentSettings,
    MemoryControlResult,
    MemoryExplanation,
    MemoryOperationContext,
    MemoryProposalTrigger,
    MemoryProvenance,
    MemoryRecord,
    MemorySelectionReason,
    MemorySensitivityFlag,
    MemorySourceKind,
    MemoryUsePurpose,
    ProviderReconciliationStatus,
    RetrievedMemory,
    SavedDecisionSource,
    SensitivityAssessment,
    SensitivityStatus,
)


def _sorted_categories(categories: frozenset[MemoryCategory]) -> list[MemoryCategory]:
    return sorted(categories, key=lambda category: category.value)


class MemoryProvenanceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_kind: MemorySourceKind
    source_id: str = Field(min_length=1)
    source_version: str = Field(min_length=1)

    def to_domain(self) -> MemoryProvenance:
        return MemoryProvenance(
            source_kind=self.source_kind,
            source_id=self.source_id,
            source_version=self.source_version,
        )


class MemoryEnableRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    categories: list[MemoryCategory] = Field(min_length=1)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)


class MemoryProposeRequest(BaseModel):
    """Explicit user request to remember something; the trigger is not client data."""

    model_config = ConfigDict(extra="forbid")

    category: MemoryCategory
    value: str = Field(min_length=1, max_length=MAX_MEMORY_VALUE_LENGTH)
    label: str = Field(min_length=1, max_length=120)
    future_benefit: str = Field(
        min_length=1,
        max_length=MAX_MEMORY_FUTURE_BENEFIT_LENGTH,
    )
    provenance: list[MemoryProvenanceIn] = Field(min_length=1)
    context: MemoryOperationContext = MemoryOperationContext.ORDINARY


class MemoryProposeSavedDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=MAX_MEMORY_VALUE_LENGTH)
    provenance: MemoryProvenanceIn
    context: MemoryOperationContext = MemoryOperationContext.ORDINARY

    def to_source(self) -> SavedDecisionSource:
        return SavedDecisionSource(
            label=self.label,
            value=self.value,
            provenance=self.provenance.to_domain(),
        )


class MemoryConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context: MemoryOperationContext = MemoryOperationContext.ORDINARY


class MemoryRetrieveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=MAX_MEMORY_VALUE_LENGTH)
    purpose: MemoryUsePurpose
    context: MemoryOperationContext = MemoryOperationContext.ORDINARY
    limit: int = Field(default=3, ge=1, le=10)


class MemoryEditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_MEMORY_VALUE_LENGTH,
    )
    label: str | None = Field(default=None, min_length=1, max_length=120)

    @field_validator("value", "label")
    @classmethod
    def _reject_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("memory edit fields must not be blank")
        return value

    @model_validator(mode="after")
    def _require_change(self) -> "MemoryEditRequest":
        if self.value is None and self.label is None:
            raise ValueError("edit requires a value or label change")
        return self


class MemorySensitivityOut(BaseModel):
    status: SensitivityStatus
    flags: list[MemorySensitivityFlag]

    @classmethod
    def from_domain(cls, assessment: SensitivityAssessment) -> "MemorySensitivityOut":
        return cls(
            status=assessment.status,
            flags=sorted(assessment.flags, key=lambda flag: flag.value),
        )


class MemoryProvenanceOut(BaseModel):
    source_kind: MemorySourceKind
    source_id: str
    source_version: str

    @classmethod
    def from_domain(cls, provenance: MemoryProvenance) -> "MemoryProvenanceOut":
        return cls(
            source_kind=provenance.source_kind,
            source_id=provenance.source_id,
            source_version=provenance.source_version,
        )


class MemoryConsentSettingsResponse(BaseModel):
    enabled: bool
    enabled_categories: list[MemoryCategory]

    @classmethod
    def from_domain(
        cls,
        settings: MemoryConsentSettings,
    ) -> "MemoryConsentSettingsResponse":
        return cls(
            enabled=settings.enabled,
            enabled_categories=_sorted_categories(settings.enabled_categories),
        )


class MemoryConsentReceiptOut(BaseModel):
    id: str
    action: MemoryConsentAction
    candidate_id: str | None
    requested_scope: list[MemoryCategory]
    granted_scope: list[MemoryCategory]
    effective_scope: list[MemoryCategory]
    recorded_at: datetime

    @classmethod
    def from_domain(
        cls,
        receipt: MemoryConsentActionReceipt,
    ) -> "MemoryConsentReceiptOut":
        return cls(
            id=receipt.id,
            action=receipt.action,
            candidate_id=receipt.candidate_id,
            requested_scope=_sorted_categories(receipt.requested_scope),
            granted_scope=_sorted_categories(receipt.granted_scope),
            effective_scope=_sorted_categories(receipt.effective_scope),
            recorded_at=receipt.recorded_at,
        )


class MemoryCandidateOut(BaseModel):
    id: str
    category: MemoryCategory
    label: str
    value: str
    future_benefit: str
    provenance: list[MemoryProvenanceOut]
    trigger: MemoryProposalTrigger
    sensitivity: MemorySensitivityOut
    opt_in_scope: list[MemoryCategory]
    created_at: datetime

    @classmethod
    def from_domain(cls, candidate: MemoryCandidate) -> "MemoryCandidateOut":
        return cls(
            id=candidate.id,
            category=candidate.category,
            label=candidate.source.label,
            value=candidate.source.value,
            future_benefit=candidate.future_benefit,
            provenance=[
                MemoryProvenanceOut.from_domain(ref) for ref in candidate.provenance_refs
            ],
            trigger=candidate.trigger,
            sensitivity=MemorySensitivityOut.from_domain(candidate.sensitivity),
            opt_in_scope=_sorted_categories(candidate.opt_in_scope),
            created_at=candidate.created_at,
        )


class MemoryRecordOut(BaseModel):
    id: str
    candidate_id: str
    category: MemoryCategory
    label: str
    value: str
    provenance: list[MemoryProvenanceOut]
    consent_receipt: MemoryConsentReceiptOut
    revision: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, record: MemoryRecord) -> "MemoryRecordOut":
        return cls(
            id=record.id,
            candidate_id=record.candidate_id,
            category=record.category,
            label=record.label,
            value=record.value,
            provenance=[
                MemoryProvenanceOut.from_domain(ref) for ref in record.provenance_refs
            ],
            consent_receipt=MemoryConsentReceiptOut.from_domain(record.consent_receipt),
            revision=record.revision,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )


class MemoryProposalResponse(BaseModel):
    created: bool
    candidate: MemoryCandidateOut | None = None


class MemoryConfirmationResponse(BaseModel):
    created: bool
    record: MemoryRecordOut | None = None
    consent_receipt: MemoryConsentReceiptOut | None = None

    @classmethod
    def from_domain(cls, result: ConfirmationResult) -> "MemoryConfirmationResponse":
        return cls(
            created=result.created,
            record=(
                MemoryRecordOut.from_domain(result.record)
                if result.record is not None
                else None
            ),
            consent_receipt=(
                MemoryConsentReceiptOut.from_domain(result.consent_receipt)
                if result.consent_receipt is not None
                else None
            ),
        )


class MemoryDeclineResponse(BaseModel):
    declined: bool


class MemoryRecordsResponse(BaseModel):
    records: list[MemoryRecordOut]


class RetrievedMemoryOut(BaseModel):
    record: MemoryRecordOut
    selection_reason: MemorySelectionReason
    score: float
    provenance: list[MemoryProvenanceOut]

    @classmethod
    def from_domain(cls, retrieved: RetrievedMemory) -> "RetrievedMemoryOut":
        return cls(
            record=MemoryRecordOut.from_domain(retrieved.record),
            selection_reason=retrieved.selection_reason,
            score=retrieved.score,
            provenance=[
                MemoryProvenanceOut.from_domain(ref) for ref in retrieved.provenance
            ],
        )


class MemoryRetrievalResponse(BaseModel):
    memories: list[RetrievedMemoryOut]


class MemoryExplanationResponse(BaseModel):
    record_id: str
    category: MemoryCategory
    provenance: list[MemoryProvenanceOut]
    consent_receipt_id: str
    consent_schema_version: MemoryConsentSchemaVersion
    confirmed_at: datetime

    @classmethod
    def from_domain(cls, explanation: MemoryExplanation) -> "MemoryExplanationResponse":
        return cls(
            record_id=explanation.record_id,
            category=explanation.category,
            provenance=[
                MemoryProvenanceOut.from_domain(ref) for ref in explanation.provenance
            ],
            consent_receipt_id=explanation.consent_receipt_id,
            consent_schema_version=explanation.consent_schema_version,
            confirmed_at=explanation.confirmed_at,
        )


class MemoryControlResponse(BaseModel):
    changed: bool
    record: MemoryRecordOut | None = None
    provider_status: ProviderReconciliationStatus

    @classmethod
    def from_domain(cls, result: MemoryControlResult) -> "MemoryControlResponse":
        return cls(
            changed=result.changed,
            record=(
                MemoryRecordOut.from_domain(result.record)
                if result.record is not None
                else None
            ),
            provider_status=result.provider_status,
        )
