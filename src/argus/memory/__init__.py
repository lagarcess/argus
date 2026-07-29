"""Isolated, default-off personalization-memory domain."""

from argus.memory.contracts import (
    ConfirmationResult,
    ConfirmedMemoryConsentReceipt,
    MemoryCandidate,
    MemoryCategory,
    MemoryProvenance,
    MemoryRecord,
    MemorySourceKind,
    ProposalResult,
    SavedDecisionSource,
)
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
    "MemoryCategory",
    "MemoryProvenance",
    "MemoryRecord",
    "MemoryService",
    "MemoryServiceConfig",
    "MemorySourceKind",
    "MemorySubject",
    "PersonalizationMemoryUnavailable",
    "ProposalResult",
    "RegisteredMemoryOwner",
    "SavedDecisionSource",
    "require_registered",
]
