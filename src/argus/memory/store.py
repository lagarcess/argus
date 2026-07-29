"""Owner-typed canonical storage for the isolated memory lifecycle."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from threading import Condition, RLock
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


@dataclass(frozen=True, slots=True)
class CanonicalRecordMutation:
    """One owner-scoped canonical mutation and its prior derivative pointer."""

    before: MemoryRecord
    after: MemoryRecord | None
    provider_ref: str | None
    reconciliation_generation: int | None = None
    cleanup_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ProviderCleanupTarget:
    """Inspectable derivative cleanup work retained after canonical mutation."""

    record_id: str
    provider_ref: str


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

    def get_record(
        self, owner: RegisteredMemoryOwner, record_id: str
    ) -> MemoryRecord | None: ...

    def edit_record(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str,
        *,
        value: str | None,
        label: str | None,
    ) -> CanonicalRecordMutation | None: ...

    def delete_record(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str,
    ) -> CanonicalRecordMutation | None: ...

    def set_provider_ref(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str,
        provider_ref: str,
    ) -> bool: ...

    def get_provider_ref(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str,
    ) -> str | None: ...

    def compare_and_set_provider_ref(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str,
        *,
        expected_record: MemoryRecord,
        expected_provider_ref: str | None,
        reconciliation_generation: int,
        provider_ref: str,
    ) -> bool: ...

    def finish_record_reconciliation(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str,
        reconciliation_generation: int,
    ) -> bool: ...

    def wait_for_reconciliation_turn(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str,
        reconciliation_generation: int,
    ) -> bool: ...

    def inflight_reconciliation_generations(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str,
    ) -> tuple[int, ...]: ...

    def track_provider_cleanup_target(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str,
        provider_ref: str,
    ) -> None: ...

    def resolve_provider_cleanup_target(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str,
        provider_ref: str,
    ) -> bool: ...

    def list_provider_cleanup_targets(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str | None = None,
    ) -> tuple[ProviderCleanupTarget, ...]: ...


class InMemoryCanonicalMemoryStore:
    """Deterministic stand-in for future canonical persistence."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._reconciliation_condition = Condition(self._lock)
        self._candidates: dict[str, dict[str, MemoryCandidate]] = {}
        self._settings: dict[str, MemoryConsentSettings] = {}
        self._receipts: dict[str, dict[str, ConfirmedMemoryConsentReceipt]] = {}
        self._records: dict[str, dict[str, MemoryRecord]] = {}
        self._provider_refs: dict[str, dict[str, str]] = {}
        self._cleanup_targets: dict[tuple[str, str], set[str]] = {}
        self._reconciliation_generations: dict[tuple[str, str], int] = {}
        self._inflight_reconciliations: dict[tuple[str, str], set[int]] = {}
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

    def get_record(
        self, owner: RegisteredMemoryOwner, record_id: str
    ) -> MemoryRecord | None:
        with self._lock:
            return self._records.get(owner.owner_id, {}).get(record_id)

    def edit_record(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str,
        *,
        value: str | None,
        label: str | None,
    ) -> CanonicalRecordMutation | None:
        with self._reconciliation_condition:
            records = self._records.get(owner.owner_id, {})
            current = records.get(record_id)
            if current is None:
                return None
            updated = MemoryRecord.model_validate(
                {
                    field_name: (
                        value
                        if field_name == "value" and value is not None
                        else label
                        if field_name == "label" and label is not None
                        else getattr(current, field_name)
                    )
                    for field_name in MemoryRecord.model_fields
                }
            )
            if updated == current:
                raise ValueError("memory edit must change value or label")
            records[record_id] = updated
            reconciliation_key = (owner.owner_id, record_id)
            reconciliation_generation = (
                self._reconciliation_generations.get(reconciliation_key, 0) + 1
            )
            self._reconciliation_generations[reconciliation_key] = (
                reconciliation_generation
            )
            self._inflight_reconciliations.setdefault(
                reconciliation_key,
                set(),
            ).add(reconciliation_generation)
            return CanonicalRecordMutation(
                before=current,
                after=updated,
                provider_ref=self._provider_refs.get(owner.owner_id, {}).get(record_id),
                reconciliation_generation=reconciliation_generation,
            )

    def delete_record(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str,
    ) -> CanonicalRecordMutation | None:
        with self._reconciliation_condition:
            reconciliation_key = (owner.owner_id, record_id)
            self._reconciliation_condition.wait_for(
                lambda: not self._inflight_reconciliations.get(reconciliation_key)
            )
            records = self._records.get(owner.owner_id, {})
            current = records.get(record_id)
            if current is None:
                return None
            provider_refs = self._provider_refs.get(owner.owner_id, {})
            provider_ref = provider_refs.get(record_id)
            cleanup_refs = set(self._cleanup_targets.get(reconciliation_key, set()))
            if provider_ref is not None:
                cleanup_refs.add(provider_ref)
            if cleanup_refs:
                self._cleanup_targets[reconciliation_key] = cleanup_refs

            updated_records = dict(records)
            del updated_records[record_id]
            updated_provider_refs = dict(provider_refs)
            updated_provider_refs.pop(record_id, None)

            self._records[owner.owner_id] = updated_records
            if updated_provider_refs:
                self._provider_refs[owner.owner_id] = updated_provider_refs
            else:
                self._provider_refs.pop(owner.owner_id, None)
            return CanonicalRecordMutation(
                before=current,
                after=None,
                provider_ref=provider_ref,
                cleanup_refs=tuple(sorted(cleanup_refs)),
            )

    def set_provider_ref(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str,
        provider_ref: str,
    ) -> bool:
        if not provider_ref:
            raise ValueError("provider ref must not be empty")
        with self._lock:
            if record_id not in self._records.get(owner.owner_id, {}):
                return False
            self._provider_refs.setdefault(owner.owner_id, {})[record_id] = provider_ref
            return True

    def get_provider_ref(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str,
    ) -> str | None:
        with self._lock:
            return self._provider_refs.get(owner.owner_id, {}).get(record_id)

    def compare_and_set_provider_ref(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str,
        *,
        expected_record: MemoryRecord,
        expected_provider_ref: str | None,
        reconciliation_generation: int,
        provider_ref: str,
    ) -> bool:
        if not provider_ref:
            raise ValueError("provider ref must not be empty")
        with self._lock:
            current_record = self._records.get(owner.owner_id, {}).get(record_id)
            current_provider_ref = self._provider_refs.get(owner.owner_id, {}).get(
                record_id
            )
            reconciliation_key = (owner.owner_id, record_id)
            if (
                current_record != expected_record
                or current_provider_ref != expected_provider_ref
                or reconciliation_generation
                not in self._inflight_reconciliations.get(reconciliation_key, set())
            ):
                return False
            targets = self._cleanup_targets.get(reconciliation_key)
            if targets is not None:
                targets.discard(provider_ref)
                if not targets:
                    self._cleanup_targets.pop(reconciliation_key, None)
            if current_provider_ref is not None and current_provider_ref != provider_ref:
                self._cleanup_targets.setdefault(reconciliation_key, set()).add(
                    current_provider_ref
                )
            self._provider_refs.setdefault(owner.owner_id, {})[record_id] = provider_ref
            return True

    def finish_record_reconciliation(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str,
        reconciliation_generation: int,
    ) -> bool:
        with self._reconciliation_condition:
            reconciliation_key = (owner.owner_id, record_id)
            inflight = self._inflight_reconciliations.get(reconciliation_key)
            if inflight is None or reconciliation_generation not in inflight:
                return False
            inflight.remove(reconciliation_generation)
            if not inflight:
                self._inflight_reconciliations.pop(reconciliation_key, None)
            self._reconciliation_condition.notify_all()
            return True

    def wait_for_reconciliation_turn(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str,
        reconciliation_generation: int,
    ) -> bool:
        with self._reconciliation_condition:
            reconciliation_key = (owner.owner_id, record_id)

            def _is_turn_or_finished() -> bool:
                inflight = self._inflight_reconciliations.get(reconciliation_key)
                return (
                    inflight is None
                    or reconciliation_generation not in inflight
                    or reconciliation_generation == min(inflight)
                )

            self._reconciliation_condition.wait_for(_is_turn_or_finished)
            return reconciliation_generation in self._inflight_reconciliations.get(
                reconciliation_key,
                set(),
            )

    def inflight_reconciliation_generations(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str,
    ) -> tuple[int, ...]:
        with self._lock:
            return tuple(
                sorted(
                    self._inflight_reconciliations.get(
                        (owner.owner_id, record_id),
                        set(),
                    )
                )
            )

    def track_provider_cleanup_target(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str,
        provider_ref: str,
    ) -> None:
        if not provider_ref:
            raise ValueError("provider ref must not be empty")
        with self._lock:
            self._cleanup_targets.setdefault(
                (owner.owner_id, record_id),
                set(),
            ).add(provider_ref)

    def resolve_provider_cleanup_target(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str,
        provider_ref: str,
    ) -> bool:
        with self._lock:
            key = (owner.owner_id, record_id)
            targets = self._cleanup_targets.get(key)
            if targets is None or provider_ref not in targets:
                return False
            targets.remove(provider_ref)
            if not targets:
                self._cleanup_targets.pop(key, None)
            return True

    def list_provider_cleanup_targets(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str | None = None,
    ) -> tuple[ProviderCleanupTarget, ...]:
        with self._lock:
            return tuple(
                ProviderCleanupTarget(
                    record_id=target_record_id,
                    provider_ref=provider_ref,
                )
                for (owner_id, target_record_id), provider_refs in sorted(
                    self._cleanup_targets.items()
                )
                if owner_id == owner.owner_id
                and (record_id is None or target_record_id == record_id)
                for provider_ref in sorted(provider_refs)
            )
