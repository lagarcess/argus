"""Owner-typed canonical storage for the isolated memory lifecycle."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from threading import RLock
from typing import Protocol

from argus.memory.contracts import (
    ConfirmationResult,
    ConfirmedMemoryConsentReceipt,
    MemoryCandidate,
    MemoryCategory,
    MemoryConsentSettings,
    MemoryProposalTrigger,
    MemoryRecord,
)
from argus.memory.subject import RegisteredMemoryOwner


@dataclass(frozen=True, slots=True)
class ProposalHistorySnapshot:
    """Prompt and decline history used by one proactive policy decision."""

    last_proactive_prompt_at: datetime | None
    last_declined_at: datetime | None


class CanonicalMemoryStore(Protocol):
    def add_candidate_with_prompt(
        self,
        owner: RegisteredMemoryOwner,
        candidate: MemoryCandidate,
        *,
        proactive_prompt_at: datetime | None,
        expected_history: ProposalHistorySnapshot | None,
    ) -> bool: ...

    def get_candidate(
        self, owner: RegisteredMemoryOwner, candidate_id: str
    ) -> MemoryCandidate | None: ...

    def decline_candidate_with_history(
        self,
        owner: RegisteredMemoryOwner,
        candidate_id: str,
        *,
        declined_at: datetime | None,
    ) -> bool: ...

    def discard_candidate(
        self, owner: RegisteredMemoryOwner, candidate_id: str
    ) -> bool: ...

    def list_candidates(
        self, owner: RegisteredMemoryOwner
    ) -> tuple[MemoryCandidate, ...]: ...

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

    def get_settings(self, owner: RegisteredMemoryOwner) -> MemoryConsentSettings: ...

    def set_settings(
        self,
        owner: RegisteredMemoryOwner,
        settings: MemoryConsentSettings,
    ) -> MemoryConsentSettings: ...

    def enable_categories(
        self,
        owner: RegisteredMemoryOwner,
        categories: frozenset[MemoryCategory],
    ) -> MemoryConsentSettings: ...

    def last_proactive_prompt_at(
        self,
        owner: RegisteredMemoryOwner,
        category: MemoryCategory,
    ) -> datetime | None: ...

    def mark_proactive_prompt(
        self,
        owner: RegisteredMemoryOwner,
        category: MemoryCategory,
        at: datetime,
    ) -> None: ...

    def last_declined_at(
        self,
        owner: RegisteredMemoryOwner,
        category: MemoryCategory,
    ) -> datetime | None: ...

    def mark_declined(
        self,
        owner: RegisteredMemoryOwner,
        category: MemoryCategory,
        at: datetime,
    ) -> None: ...

    def list_consent_receipts(
        self, owner: RegisteredMemoryOwner
    ) -> tuple[ConfirmedMemoryConsentReceipt, ...]: ...

    def list_records(self, owner: RegisteredMemoryOwner) -> tuple[MemoryRecord, ...]: ...


class InMemoryCanonicalMemoryStore:
    """Deterministic stand-in for future canonical persistence."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._candidates: dict[str, dict[str, MemoryCandidate]] = {}
        self._settings: dict[str, MemoryConsentSettings] = {}
        self._receipts: dict[str, dict[str, ConfirmedMemoryConsentReceipt]] = {}
        self._records: dict[str, dict[str, MemoryRecord]] = {}
        self._proactive_prompts: dict[tuple[str, MemoryCategory], datetime] = {}
        self._declines: dict[tuple[str, MemoryCategory], datetime] = {}

    def add_candidate_with_prompt(
        self,
        owner: RegisteredMemoryOwner,
        candidate: MemoryCandidate,
        *,
        proactive_prompt_at: datetime | None,
        expected_history: ProposalHistorySnapshot | None,
    ) -> bool:
        candidate = MemoryCandidate.model_validate(
            {
                field_name: getattr(candidate, field_name)
                for field_name in MemoryCandidate.model_fields
            }
        )
        if candidate.owner_id != owner.owner_id:
            raise ValueError("candidate owner must match registered owner")
        is_proactive = candidate.trigger is not MemoryProposalTrigger.EXPLICIT_REQUEST
        if is_proactive != (proactive_prompt_at is not None):
            raise ValueError(
                "proactive candidates require one atomic prompt-history timestamp"
            )
        if is_proactive != (expected_history is not None):
            raise ValueError("proactive candidates require the policy history snapshot")
        with self._lock:
            candidates = self._candidates.setdefault(owner.owner_id, {})
            if candidate.id in candidates:
                raise ValueError(f"candidate already exists: {candidate.id}")
            history_key = (owner.owner_id, candidate.category)
            if expected_history is not None and (
                self._proactive_prompts.get(history_key)
                != expected_history.last_proactive_prompt_at
                or self._declines.get(history_key) != expected_history.last_declined_at
            ):
                return False
            candidates[candidate.id] = candidate
            if proactive_prompt_at is None:
                return True
            previous = self._proactive_prompts.get(history_key)
            had_previous = history_key in self._proactive_prompts
            try:
                self._proactive_prompts[history_key] = proactive_prompt_at
            except BaseException:
                candidates.pop(candidate.id, None)
                self._restore_history_entry(
                    self._proactive_prompts,
                    history_key,
                    previous=previous,
                    had_previous=had_previous,
                )
                raise
            return True

    def get_candidate(
        self, owner: RegisteredMemoryOwner, candidate_id: str
    ) -> MemoryCandidate | None:
        with self._lock:
            return self._candidates.get(owner.owner_id, {}).get(candidate_id)

    def decline_candidate_with_history(
        self,
        owner: RegisteredMemoryOwner,
        candidate_id: str,
        *,
        declined_at: datetime | None,
    ) -> bool:
        with self._lock:
            candidates = self._candidates.get(owner.owner_id, {})
            candidate = candidates.get(candidate_id)
            if candidate is None:
                return False
            is_proactive = candidate.trigger is not MemoryProposalTrigger.EXPLICIT_REQUEST
            if is_proactive != (declined_at is not None):
                raise ValueError(
                    "proactive declines require one atomic history timestamp"
                )

            history_key = (owner.owner_id, candidate.category)
            previous = self._declines.get(history_key)
            had_previous = history_key in self._declines
            del candidates[candidate_id]
            if declined_at is None:
                return True
            try:
                self._declines[history_key] = declined_at
            except BaseException:
                candidates[candidate_id] = candidate
                self._restore_history_entry(
                    self._declines,
                    history_key,
                    previous=previous,
                    had_previous=had_previous,
                )
                raise
            return True

    def discard_candidate(self, owner: RegisteredMemoryOwner, candidate_id: str) -> bool:
        with self._lock:
            return (
                self._candidates.get(owner.owner_id, {}).pop(candidate_id, None)
                is not None
            )

    def list_candidates(
        self, owner: RegisteredMemoryOwner
    ) -> tuple[MemoryCandidate, ...]:
        with self._lock:
            return tuple(self._candidates.get(owner.owner_id, {}).values())

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
            settings = self._settings.get(
                owner.owner_id,
                MemoryConsentSettings(),
            )
            confirmed_scope = set(settings.enabled_categories)
            confirmed_scope.update(candidate.opt_in_scope)
            if candidate.category not in confirmed_scope:
                return ConfirmationResult(created=False)

            receipt = ConfirmedMemoryConsentReceipt(
                id=id_factory(),
                owner_id=owner.owner_id,
                candidate_id=candidate.id,
                scope=frozenset(confirmed_scope),
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
                provenance_refs=candidate.provenance_refs,
                consent_receipt=receipt,
                created_at=confirmed_at,
            )
            existing_records = self._records.get(owner.owner_id, {})
            if record.id in existing_records:
                raise ValueError(f"memory record id already exists: {record.id}")

            receipts = dict(existing_receipts)
            receipts[receipt.id] = receipt
            records = dict(existing_records)
            records[record.id] = record
            result = ConfirmationResult(
                created=True,
                record=record,
                consent_receipt=receipt,
            )

            self._settings[owner.owner_id] = MemoryConsentSettings(
                enabled=True,
                enabled_categories=frozenset(confirmed_scope),
            )
            self._receipts[owner.owner_id] = receipts
            self._records[owner.owner_id] = records
            del candidates[candidate_id]
            return result

    def enabled_categories(
        self, owner: RegisteredMemoryOwner
    ) -> frozenset[MemoryCategory]:
        return self.get_settings(owner).enabled_categories

    def get_settings(self, owner: RegisteredMemoryOwner) -> MemoryConsentSettings:
        with self._lock:
            return self._settings.get(owner.owner_id, MemoryConsentSettings())

    def set_settings(
        self,
        owner: RegisteredMemoryOwner,
        settings: MemoryConsentSettings,
    ) -> MemoryConsentSettings:
        with self._lock:
            self._settings[owner.owner_id] = settings
            return settings

    def enable_categories(
        self,
        owner: RegisteredMemoryOwner,
        categories: frozenset[MemoryCategory],
    ) -> MemoryConsentSettings:
        if not categories:
            raise ValueError("enable requires at least one category")
        with self._lock:
            current = self._settings.get(owner.owner_id, MemoryConsentSettings())
            settings = MemoryConsentSettings(
                enabled=True,
                enabled_categories=current.enabled_categories | categories,
            )
            self._settings[owner.owner_id] = settings
            return settings

    def last_proactive_prompt_at(
        self,
        owner: RegisteredMemoryOwner,
        category: MemoryCategory,
    ) -> datetime | None:
        with self._lock:
            return self._proactive_prompts.get((owner.owner_id, category))

    def mark_proactive_prompt(
        self,
        owner: RegisteredMemoryOwner,
        category: MemoryCategory,
        at: datetime,
    ) -> None:
        with self._lock:
            self._proactive_prompts[(owner.owner_id, category)] = at

    def last_declined_at(
        self,
        owner: RegisteredMemoryOwner,
        category: MemoryCategory,
    ) -> datetime | None:
        with self._lock:
            return self._declines.get((owner.owner_id, category))

    def mark_declined(
        self,
        owner: RegisteredMemoryOwner,
        category: MemoryCategory,
        at: datetime,
    ) -> None:
        with self._lock:
            self._declines[(owner.owner_id, category)] = at

    @staticmethod
    def _restore_history_entry(
        history: dict[tuple[str, MemoryCategory], datetime],
        key: tuple[str, MemoryCategory],
        *,
        previous: datetime | None,
        had_previous: bool,
    ) -> None:
        if had_previous:
            assert previous is not None
            dict.__setitem__(history, key, previous)
        else:
            dict.pop(history, key, None)

    def list_consent_receipts(
        self, owner: RegisteredMemoryOwner
    ) -> tuple[ConfirmedMemoryConsentReceipt, ...]:
        with self._lock:
            return tuple(self._receipts.get(owner.owner_id, {}).values())

    def list_records(self, owner: RegisteredMemoryOwner) -> tuple[MemoryRecord, ...]:
        with self._lock:
            return tuple(self._records.get(owner.owner_id, {}).values())
