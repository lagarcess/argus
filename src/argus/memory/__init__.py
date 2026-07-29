"""Isolated, default-off personalization-memory domain."""

from argus.memory.contracts import (
    ConfirmationResult,
    ConfirmedMemoryConsentReceipt,
    MemoryCandidate,
    MemoryCandidateDraft,
    MemoryCategory,
    MemoryConsentSettings,
    MemoryOperationContext,
    MemoryProposalTrigger,
    MemoryProvenance,
    MemoryRecord,
    MemorySensitivityFlag,
    MemorySourceKind,
    MemorySourceRef,
    ProposalResult,
    SavedDecisionSource,
    SensitivityAssessment,
    SensitivityStatus,
)
from argus.memory.policy import MemoryPolicy, PolicyDecision, PolicyOutcome
from argus.memory.service import MemoryService, MemoryServiceConfig
from argus.memory.store import CanonicalMemoryStore, InMemoryCanonicalMemoryStore
from argus.memory.subject import (
    MemoryAccountKind,
    MemorySubject,
    PersonalizationMemoryUnavailable,
    RegisteredMemoryOwner,
    require_registered,
)

__all__ = [
    "CanonicalMemoryStore",
    "ConfirmationResult",
    "ConfirmedMemoryConsentReceipt",
    "InMemoryCanonicalMemoryStore",
    "MemoryAccountKind",
    "MemoryCandidate",
    "MemoryCandidateDraft",
    "MemoryCategory",
    "MemoryConsentSettings",
    "MemoryOperationContext",
    "MemoryPolicy",
    "MemoryProvenance",
    "MemoryProposalTrigger",
    "MemoryRecord",
    "MemorySensitivityFlag",
    "MemoryService",
    "MemoryServiceConfig",
    "MemorySourceKind",
    "MemorySourceRef",
    "MemorySubject",
    "PersonalizationMemoryUnavailable",
    "PolicyDecision",
    "PolicyOutcome",
    "ProposalResult",
    "RegisteredMemoryOwner",
    "SavedDecisionSource",
    "SensitivityAssessment",
    "SensitivityStatus",
    "require_registered",
]
