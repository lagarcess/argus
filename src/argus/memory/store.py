"""Owner-typed canonical storage for the isolated memory lifecycle."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from threading import RLock
from typing import Protocol

from argus.memory.contracts import (
    ConfirmationResult,
    ConfirmedMemoryConsentReceipt,
    MemoryCandidate,
    MemoryCategory,
    MemoryRecord,
)
from argus.memory.subject import RegisteredMemoryOwner


class CanonicalMemoryStore(Protocol):
    def add_candidate(
        self, owner: RegisteredMemoryOwner, candidate: MemoryCandidate
    ) -> None: ...

    def get_candidate(
        self, owner: RegisteredMemoryOwner, candidate_id: str
    ) -> MemoryCandidate | None: ...

    def decline_candidate(
        self, owner: RegisteredMemoryOwner, candidate_id: str
    ) -> bool: ...

    def confirm_candidate(
        self,
        owner: RegisteredMemoryOwner,
        candidate_id: str,
        *,
        clock: Callable[[], datetime],
        id_factory: Callable[[], str],
    ) -> ConfirmationResult: ...

    def enabled_categories(
        self, owner: RegisteredMemoryOwner
    ) -> frozenset[MemoryCategory]: ...

    def list_consent_receipts(
        self, owner: RegisteredMemoryOwner
    ) -> tuple[ConfirmedMemoryConsentReceipt, ...]: ...

    def list_records(self, owner: RegisteredMemoryOwner) -> tuple[MemoryRecord, ...]: ...


class InMemoryCanonicalMemoryStore:
    """Deterministic stand-in for future canonical persistence."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._candidates: dict[str, dict[str, MemoryCandidate]] = {}
        self._enabled: dict[str, set[MemoryCategory]] = {}
        self._receipts: dict[str, dict[str, ConfirmedMemoryConsentReceipt]] = {}
        self._records: dict[str, dict[str, MemoryRecord]] = {}

    def add_candidate(
        self, owner: RegisteredMemoryOwner, candidate: MemoryCandidate
    ) -> None:
        if candidate.owner_id != owner.owner_id:
            raise ValueError("candidate owner must match registered owner")
        with self._lock:
            candidates = self._candidates.setdefault(owner.owner_id, {})
            if candidate.id in candidates:
                raise ValueError(f"candidate already exists: {candidate.id}")
            candidates[candidate.id] = candidate

    def get_candidate(
        self, owner: RegisteredMemoryOwner, candidate_id: str
    ) -> MemoryCandidate | None:
        with self._lock:
            return self._candidates.get(owner.owner_id, {}).get(candidate_id)

    def decline_candidate(self, owner: RegisteredMemoryOwner, candidate_id: str) -> bool:
        with self._lock:
            return (
                self._candidates.get(owner.owner_id, {}).pop(candidate_id, None)
                is not None
            )

    def confirm_candidate(
        self,
        owner: RegisteredMemoryOwner,
        candidate_id: str,
        *,
        clock: Callable[[], datetime],
        id_factory: Callable[[], str],
    ) -> ConfirmationResult:
        with self._lock:
            candidates = self._candidates.get(owner.owner_id, {})
            candidate = candidates.get(candidate_id)
            if candidate is None:
                return ConfirmationResult(created=False)

            confirmed_at = clock()
            receipt = ConfirmedMemoryConsentReceipt(
                id=id_factory(),
                owner_id=owner.owner_id,
                candidate_id=candidate.id,
                scope=candidate.opt_in_scope,
                confirmed_at=confirmed_at,
            )
            existing_receipts = self._receipts.get(owner.owner_id, {})
            if receipt.id in existing_receipts:
                raise ValueError(f"consent receipt id already exists: {receipt.id}")

            record = MemoryRecord(
                id=id_factory(),
                owner_id=owner.owner_id,
                candidate_id=candidate.id,
                category=candidate.category,
                label=candidate.source.label,
                value=candidate.source.value,
                provenance=candidate.source.provenance,
                consent_receipt=receipt,
                created_at=confirmed_at,
            )
            existing_records = self._records.get(owner.owner_id, {})
            if record.id in existing_records:
                raise ValueError(f"memory record id already exists: {record.id}")

            enabled = set(self._enabled.get(owner.owner_id, set()))
            enabled.update(candidate.opt_in_scope)
            receipts = dict(existing_receipts)
            receipts[receipt.id] = receipt
            records = dict(existing_records)
            records[record.id] = record
            result = ConfirmationResult(
                created=True,
                record=record,
                consent_receipt=receipt,
            )

            self._enabled[owner.owner_id] = enabled
            self._receipts[owner.owner_id] = receipts
            self._records[owner.owner_id] = records
            del candidates[candidate_id]
            return result

    def enabled_categories(
        self, owner: RegisteredMemoryOwner
    ) -> frozenset[MemoryCategory]:
        with self._lock:
            return frozenset(self._enabled.get(owner.owner_id, set()))

    def list_consent_receipts(
        self, owner: RegisteredMemoryOwner
    ) -> tuple[ConfirmedMemoryConsentReceipt, ...]:
        with self._lock:
            return tuple(self._receipts.get(owner.owner_id, {}).values())

    def list_records(self, owner: RegisteredMemoryOwner) -> tuple[MemoryRecord, ...]:
        with self._lock:
            return tuple(self._records.get(owner.owner_id, {}).values())
