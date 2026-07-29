"""Registered-only saved-decision memory service."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from argus.memory.contracts import (
    ConfirmationResult,
    MemoryCandidate,
    MemoryCandidateDraft,
    MemoryCategory,
    MemoryConsentSettings,
    MemoryControlResult,
    MemoryEdit,
    MemoryExplanation,
    MemoryOperationContext,
    MemoryProposalTrigger,
    MemoryRecord,
    MemorySelectionReason,
    MemoryUsePurpose,
    ProposalResult,
    ProviderReconciliationStatus,
    RetrievedMemory,
    SavedDecisionSource,
    SensitivityAssessment,
    SensitivityStatus,
)
from argus.memory.policy import RESTRICTED_CONTEXTS, MemoryPolicy
from argus.memory.provider import (
    MemoryRetrievalProvider,
    NoOpMemoryProvider,
    ProviderCleanupResult,
    ProviderProjectionResult,
    ProviderSearchResult,
    ProviderSearchStatus,
)
from argus.memory.store import (
    CanonicalMemoryStore,
    CanonicalRecordMutation,
    ProposalHistorySnapshot,
)
from argus.memory.subject import (
    MemorySubject,
    PersonalizationMemoryUnavailable,
    RegisteredMemoryOwner,
    require_registered,
)


class MemoryAvailability(Protocol):
    @property
    def available(self) -> bool: ...

    @property
    def candidate_ttl(self) -> timedelta: ...


class Clock(Protocol):
    def __call__(self) -> datetime: ...


class IdFactory(Protocol):
    def __call__(self) -> str: ...


class MemoryServiceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    available: bool = False
    candidate_ttl: timedelta = Field(default=timedelta(days=1), gt=timedelta(0))


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid4().hex


class MemoryService:
    def __init__(
        self,
        *,
        store: CanonicalMemoryStore,
        provider: MemoryRetrievalProvider | None = None,
        config: MemoryAvailability | None = None,
        policy: MemoryPolicy | None = None,
        clock: Clock | Callable[[], datetime] = _utc_now,
        id_factory: IdFactory | Callable[[], str] = _new_id,
    ) -> None:
        self._store = store
        self._provider = provider if provider is not None else NoOpMemoryProvider()
        self._config = config if config is not None else MemoryServiceConfig()
        self._policy = policy if policy is not None else MemoryPolicy()
        self._clock = clock
        self._id_factory = id_factory

    def propose_saved_decision(
        self,
        subject: MemorySubject,
        source: SavedDecisionSource,
        *,
        sensitivity: SensitivityAssessment,
        context: MemoryOperationContext,
    ) -> ProposalResult | None:
        owner = require_registered(subject)
        draft = MemoryCandidateDraft(
            category=MemoryCategory.EXPLICIT_DECISION_NOTE,
            value=source.value,
            label=source.label,
            future_benefit="Argus can revisit and compare this saved decision later.",
            provenance=(source.provenance,),
            trigger=MemoryProposalTrigger.SAVED_DECISION,
            sensitivity=sensitivity,
        )
        if not self._policy.preflight(draft, context=context).allowed:
            return None
        self._require_available()
        return self._propose(owner, draft, context)

    def propose(
        self,
        subject: MemorySubject,
        draft: MemoryCandidateDraft,
        context: MemoryOperationContext,
    ) -> ProposalResult | None:
        owner = require_registered(subject)
        if not self._policy.preflight(draft, context=context).allowed:
            return None
        self._require_available()
        return self._propose(owner, draft, context)

    def enable(
        self,
        subject: MemorySubject,
        categories: frozenset[MemoryCategory],
    ) -> MemoryConsentSettings:
        owner = require_registered(subject)
        self._policy.validate_enable_scope(categories)
        self._require_available()
        return self._store.enable_categories(owner, categories)

    def confirm(
        self,
        subject: MemorySubject,
        candidate_id: str,
        *,
        sensitivity: SensitivityAssessment,
        context: MemoryOperationContext,
    ) -> ConfirmationResult:
        owner = require_registered(subject)
        if not self._policy.preflight_context(
            sensitivity=sensitivity,
            context=context,
        ).allowed:
            return ConfirmationResult(created=False)
        self._require_available()
        candidate = self._store.get_candidate(owner, candidate_id)
        if candidate is None:
            return ConfirmationResult(created=False)

        now = self._clock()
        if now - candidate.created_at >= self._config.candidate_ttl:
            self._store.discard_candidate(owner, candidate_id)
            return ConfirmationResult(created=False)

        decision = self._policy.evaluate(
            self._draft_from_candidate(
                candidate,
                sensitivity=sensitivity,
            ),
            self._store.get_settings(owner),
            context=context,
            last_proactive_prompt_at=None,
            last_declined_at=None,
            now=now,
        )
        if not decision.allowed or decision.opt_in_scope != candidate.opt_in_scope:
            self._store.discard_candidate(owner, candidate_id)
            return ConfirmationResult(created=False)
        mutation = self._store.confirm_candidate(
            owner,
            candidate_id,
            clock=lambda: now,
            id_factory=self._id_factory,
        )
        result = mutation.result
        if not result.created or result.record is None:
            return result
        reconciliation_generation = mutation.reconciliation_generation
        assert reconciliation_generation is not None
        try:
            has_reconciliation_turn = self._store.wait_for_reconciliation_turn(
                owner,
                result.record.id,
                reconciliation_generation,
            )
            if not has_reconciliation_turn:
                return result
            try:
                projection = ProviderProjectionResult.model_validate(
                    self._provider.project(owner, result.record)
                )
            except Exception:
                return result
            if projection.status is not ProviderReconciliationStatus.SYNCHRONIZED:
                return result
            assert projection.provider_ref is not None
            ref_committed = self._store.compare_and_set_provider_ref(
                owner,
                result.record.id,
                expected_record=result.record,
                expected_provider_ref=None,
                reconciliation_generation=reconciliation_generation,
                provider_ref=projection.provider_ref,
            )
            if not ref_committed:
                self._store.track_provider_cleanup_target(
                    owner,
                    result.record.id,
                    projection.provider_ref,
                )
                self._cleanup_provider_target(
                    owner,
                    result.record.id,
                    projection.provider_ref,
                )
        finally:
            self._store.finish_record_reconciliation(
                owner,
                result.record.id,
                reconciliation_generation,
            )
        return result

    def decline(self, subject: MemorySubject, candidate_id: str) -> bool:
        owner = require_registered(subject)
        self._require_available()
        candidate = self._store.get_candidate(owner, candidate_id)
        if candidate is None:
            return False
        declined_at = (
            None
            if candidate.trigger is MemoryProposalTrigger.EXPLICIT_REQUEST
            else self._clock()
        )
        return self._store.decline_candidate_with_history(
            owner,
            candidate_id,
            declined_at=declined_at,
        )

    def inspect(self, subject: MemorySubject) -> tuple[MemoryRecord, ...]:
        owner = require_registered(subject)
        return tuple(
            sorted(
                self._store.list_records(owner),
                key=lambda record: (record.created_at, record.id),
            )
        )

    def retrieve(
        self,
        subject: MemorySubject,
        query: str,
        purpose: MemoryUsePurpose,
        context: MemoryOperationContext = MemoryOperationContext.ORDINARY,
        *,
        limit: int = 3,
    ) -> tuple[RetrievedMemory, ...]:
        owner = require_registered(subject)
        if context in RESTRICTED_CONTEXTS:
            return ()
        self._require_available()
        if not isinstance(purpose, MemoryUsePurpose):
            raise TypeError("purpose must be a MemoryUsePurpose")
        if not 1 <= limit <= 10:
            raise ValueError("retrieval limit must be between 1 and 10")
        normalized_query = query.strip()
        if not normalized_query:
            return ()

        settings = self._store.get_settings(owner)
        if not settings.enabled:
            return ()
        allowed_categories = (
            self._categories_for_purpose(purpose) & settings.enabled_categories
        )
        if not allowed_categories:
            return ()
        records = {
            record.id: record
            for record in self._store.list_records(owner)
            if record.owner_id == owner.owner_id and record.category in allowed_categories
        }
        if not records:
            return ()

        provider_result = self._search_provider(
            owner,
            normalized_query,
            limit,
        )
        if (
            provider_result is not None
            and provider_result.status is ProviderSearchStatus.ANSWERED
        ):
            return self._rehydrate_provider_hits(
                records,
                provider_result,
                limit=limit,
            )
        return self._canonical_fallback(
            records.values(),
            normalized_query,
            limit=limit,
        )

    def explain(
        self,
        subject: MemorySubject,
        record_id: str,
    ) -> MemoryExplanation | None:
        owner = require_registered(subject)
        record = self._store.get_record(owner, record_id)
        if record is None:
            return None
        return MemoryExplanation(
            record_id=record.id,
            category=record.category,
            provenance=record.provenance_refs,
            consent_receipt_id=record.consent_receipt.id,
            consent_schema_version=record.consent_receipt.schema_version,
            confirmed_at=record.consent_receipt.confirmed_at,
        )

    def edit(
        self,
        subject: MemorySubject,
        record_id: str,
        edit: MemoryEdit,
    ) -> MemoryControlResult:
        owner = require_registered(subject)
        self._validate_record_id(record_id)
        self._validate_edit_sensitivity(edit.sensitivity)
        mutation = self._store.edit_record(
            owner,
            record_id,
            value=edit.value,
            label=edit.label,
        )
        if mutation is None:
            return MemoryControlResult(
                changed=False,
                provider_status=ProviderReconciliationStatus.NOT_APPLICABLE,
            )
        assert mutation.after is not None
        return MemoryControlResult(
            changed=True,
            record=mutation.after,
            provider_status=self._reconcile_edit(owner, mutation),
        )

    def delete(
        self,
        subject: MemorySubject,
        record_id: str,
    ) -> MemoryControlResult:
        owner = require_registered(subject)
        self._validate_record_id(record_id)
        mutation = self._store.delete_record(owner, record_id)
        if mutation is None:
            return MemoryControlResult(
                changed=False,
                provider_status=ProviderReconciliationStatus.NOT_APPLICABLE,
            )
        reconciliation_generation = mutation.reconciliation_generation
        assert reconciliation_generation is not None
        try:
            if not mutation.cleanup_refs:
                provider_status = ProviderReconciliationStatus.NOT_APPLICABLE
            else:
                cleanup_statuses = tuple(
                    self._cleanup_provider_target(
                        owner,
                        record_id,
                        provider_ref,
                    )
                    for provider_ref in mutation.cleanup_refs
                )
                provider_status = (
                    ProviderReconciliationStatus.SYNCHRONIZED
                    if all(
                        status is ProviderReconciliationStatus.SYNCHRONIZED
                        for status in cleanup_statuses
                    )
                    else ProviderReconciliationStatus.RECONCILIATION_REQUIRED
                )
        finally:
            reconciliation_finished = self._store.finish_record_reconciliation(
                owner,
                record_id,
                reconciliation_generation,
            )
        if not reconciliation_finished:
            provider_status = ProviderReconciliationStatus.RECONCILIATION_REQUIRED
        return MemoryControlResult(
            changed=True,
            provider_status=provider_status,
        )

    def disable(self, subject: MemorySubject) -> MemoryControlResult:
        owner = require_registered(subject)
        return MemoryControlResult(
            changed=self._store.disable(owner),
            provider_status=ProviderReconciliationStatus.NOT_APPLICABLE,
        )

    def reset(self, subject: MemorySubject) -> MemoryControlResult:
        owner = require_registered(subject)
        reset = self._store.reset(owner)
        if not reset.changed:
            return MemoryControlResult(
                changed=False,
                provider_status=ProviderReconciliationStatus.NOT_APPLICABLE,
            )
        try:
            cleanup = ProviderCleanupResult.model_validate(self._provider.reset(owner))
            provider_status = cleanup.status
        except Exception:
            provider_status = ProviderReconciliationStatus.RECONCILIATION_REQUIRED
        if (
            reset.provider_state_existed
            and provider_status is ProviderReconciliationStatus.NOT_APPLICABLE
        ):
            provider_status = ProviderReconciliationStatus.RECONCILIATION_REQUIRED
        return MemoryControlResult(
            changed=True,
            provider_status=provider_status,
        )

    def _propose(
        self,
        owner: RegisteredMemoryOwner,
        draft: MemoryCandidateDraft,
        context: MemoryOperationContext,
    ) -> ProposalResult | None:
        now = self._clock()
        last_proactive_prompt_at = self._store.last_proactive_prompt_at(
            owner,
            draft.category,
        )
        last_declined_at = self._store.last_declined_at(
            owner,
            draft.category,
        )
        decision = self._policy.evaluate(
            draft,
            self._store.get_settings(owner),
            context=context,
            last_proactive_prompt_at=last_proactive_prompt_at,
            last_declined_at=last_declined_at,
            now=now,
        )
        if not decision.allowed:
            return None

        candidate = MemoryCandidate(
            id=self._id_factory(),
            owner_id=owner.owner_id,
            category=draft.category,
            source=SavedDecisionSource(
                label=draft.label,
                value=draft.value,
                provenance=draft.provenance[0],
            ),
            future_benefit=draft.future_benefit,
            provenance_refs=draft.provenance,
            trigger=draft.trigger,
            sensitivity=draft.sensitivity,
            proposed_context=context,
            opt_in_scope=decision.opt_in_scope,
            created_at=now,
        )
        proactive_prompt_at = (
            None if draft.trigger is MemoryProposalTrigger.EXPLICIT_REQUEST else now
        )
        expected_history = (
            None
            if draft.trigger is MemoryProposalTrigger.EXPLICIT_REQUEST
            else ProposalHistorySnapshot(
                last_proactive_prompt_at=last_proactive_prompt_at,
                last_declined_at=last_declined_at,
            )
        )
        admitted = self._store.add_candidate_with_prompt(
            owner,
            candidate,
            proactive_prompt_at=proactive_prompt_at,
            expected_history=expected_history,
        )
        if not admitted:
            return None
        return ProposalResult(candidate=candidate)

    @staticmethod
    def _draft_from_candidate(
        candidate: MemoryCandidate,
        *,
        sensitivity: SensitivityAssessment,
    ) -> MemoryCandidateDraft:
        return MemoryCandidateDraft(
            category=candidate.category,
            value=candidate.source.value,
            label=candidate.source.label,
            future_benefit=candidate.future_benefit,
            provenance=candidate.provenance_refs,
            trigger=candidate.trigger,
            sensitivity=sensitivity,
        )

    def _require_available(self) -> None:
        if not self._config.available:
            raise PersonalizationMemoryUnavailable(
                "Personalization memory is not available."
            )

    @staticmethod
    def _validate_record_id(record_id: str) -> None:
        if not record_id.strip():
            raise ValueError("record id must not be blank")

    @staticmethod
    def _validate_edit_sensitivity(
        sensitivity: SensitivityAssessment,
    ) -> None:
        if sensitivity.status is not SensitivityStatus.CLEAR or sensitivity.flags:
            raise ValueError("memory edits require a current clear sensitivity result")

    def _reconcile_edit(
        self,
        owner: RegisteredMemoryOwner,
        mutation: CanonicalRecordMutation,
    ) -> ProviderReconciliationStatus:
        updated = mutation.after
        assert updated is not None
        reconciliation_generation = mutation.reconciliation_generation
        assert reconciliation_generation is not None
        try:
            has_reconciliation_turn = self._store.wait_for_reconciliation_turn(
                owner,
                updated.id,
                reconciliation_generation,
            )
            status = (
                self._reconcile_edit_generation(
                    owner,
                    mutation,
                    updated,
                    reconciliation_generation,
                )
                if has_reconciliation_turn
                else ProviderReconciliationStatus.RECONCILIATION_REQUIRED
            )
        finally:
            reconciliation_finished = self._store.finish_record_reconciliation(
                owner,
                updated.id,
                reconciliation_generation,
            )
        if not reconciliation_finished:
            return ProviderReconciliationStatus.RECONCILIATION_REQUIRED
        return status

    def _reconcile_edit_generation(
        self,
        owner: RegisteredMemoryOwner,
        mutation: CanonicalRecordMutation,
        updated: MemoryRecord,
        reconciliation_generation: int,
    ) -> ProviderReconciliationStatus:
        try:
            projection = ProviderProjectionResult.model_validate(
                self._provider.project(owner, updated)
            )
        except Exception:
            if mutation.provider_ref is not None:
                self._store.track_provider_cleanup_target(
                    owner,
                    updated.id,
                    mutation.provider_ref,
                )
            return ProviderReconciliationStatus.RECONCILIATION_REQUIRED

        if projection.status is not ProviderReconciliationStatus.SYNCHRONIZED:
            if (
                projection.status is ProviderReconciliationStatus.NOT_APPLICABLE
                and mutation.provider_ref is None
            ):
                return self._status_with_pending_cleanup(
                    owner,
                    updated.id,
                    ProviderReconciliationStatus.NOT_APPLICABLE,
                )
            if mutation.provider_ref is not None:
                self._store.track_provider_cleanup_target(
                    owner,
                    updated.id,
                    mutation.provider_ref,
                )
            return ProviderReconciliationStatus.RECONCILIATION_REQUIRED
        assert projection.provider_ref is not None
        ref_committed = self._store.compare_and_set_provider_ref(
            owner,
            updated.id,
            expected_record=updated,
            expected_provider_ref=mutation.provider_ref,
            reconciliation_generation=reconciliation_generation,
            provider_ref=projection.provider_ref,
        )
        if not ref_committed:
            self._store.track_provider_cleanup_target(
                owner,
                updated.id,
                projection.provider_ref,
            )
            self._cleanup_provider_target(
                owner,
                updated.id,
                projection.provider_ref,
            )
            return ProviderReconciliationStatus.RECONCILIATION_REQUIRED
        if (
            mutation.provider_ref is not None
            and mutation.provider_ref != projection.provider_ref
        ):
            cleanup_status = self._cleanup_provider_target(
                owner,
                updated.id,
                mutation.provider_ref,
            )
            if cleanup_status is not ProviderReconciliationStatus.SYNCHRONIZED:
                return cleanup_status
        return self._status_with_pending_cleanup(
            owner,
            updated.id,
            ProviderReconciliationStatus.SYNCHRONIZED,
        )

    def _status_with_pending_cleanup(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str,
        settled_status: ProviderReconciliationStatus,
    ) -> ProviderReconciliationStatus:
        if self._store.list_provider_cleanup_targets(owner, record_id):
            return ProviderReconciliationStatus.RECONCILIATION_REQUIRED
        return settled_status

    def _cleanup_provider_target(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str,
        provider_ref: str,
    ) -> ProviderReconciliationStatus:
        try:
            cleanup = ProviderCleanupResult.model_validate(
                self._provider.delete(owner, provider_ref)
            )
        except Exception:
            return ProviderReconciliationStatus.RECONCILIATION_REQUIRED
        if cleanup.status is ProviderReconciliationStatus.SYNCHRONIZED:
            resolved = self._store.resolve_provider_cleanup_target(
                owner,
                record_id,
                provider_ref,
            )
            if not resolved:
                return ProviderReconciliationStatus.RECONCILIATION_REQUIRED
            return ProviderReconciliationStatus.SYNCHRONIZED
        return ProviderReconciliationStatus.RECONCILIATION_REQUIRED

    def _search_provider(
        self,
        owner: RegisteredMemoryOwner,
        query: str,
        limit: int,
    ) -> ProviderSearchResult | None:
        try:
            result = self._provider.search(owner, query, limit)
            if result is None:
                return None
            return ProviderSearchResult.model_validate(result)
        except Exception:
            return None

    @staticmethod
    def _rehydrate_provider_hits(
        records: dict[str, MemoryRecord],
        result: ProviderSearchResult,
        *,
        limit: int,
    ) -> tuple[RetrievedMemory, ...]:
        selected: list[RetrievedMemory] = []
        seen: set[str] = set()
        for hit in sorted(result.hits, key=lambda item: (-item.score, item.record_id)):
            if hit.record_id in seen:
                continue
            seen.add(hit.record_id)
            record = records.get(hit.record_id)
            if record is None:
                continue
            selected.append(
                RetrievedMemory(
                    record=record,
                    selection_reason=MemorySelectionReason.PROVIDER_RANKED,
                    score=hit.score,
                    provenance=record.provenance_refs,
                )
            )
            if len(selected) == limit:
                break
        return tuple(selected)

    @staticmethod
    def _canonical_fallback(
        records: Iterable[MemoryRecord],
        query: str,
        *,
        limit: int,
    ) -> tuple[RetrievedMemory, ...]:
        query_tokens = MemoryService._tokens(query)
        if not query_tokens:
            return ()
        ranked: list[tuple[int, str, MemoryRecord]] = []
        for record in records:
            record_tokens = MemoryService._tokens(f"{record.label} {record.value}")
            score = len(query_tokens & record_tokens)
            if score:
                ranked.append((score, record.id, record))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        return tuple(
            RetrievedMemory(
                record=record,
                selection_reason=MemorySelectionReason.CANONICAL_TOKEN_MATCH,
                score=float(score),
                provenance=record.provenance_refs,
            )
            for score, _, record in ranked[:limit]
        )

    @staticmethod
    def _tokens(text: str) -> frozenset[str]:
        return frozenset(
            token for token in re.findall(r"\w+", text.casefold()) if len(token) > 2
        )

    @staticmethod
    def _categories_for_purpose(
        purpose: MemoryUsePurpose,
    ) -> frozenset[MemoryCategory]:
        if purpose is MemoryUsePurpose.INSPECT_MEMORY:
            return frozenset(MemoryCategory)
        return frozenset(
            {
                MemoryCategory.EXPLICIT_DECISION_NOTE,
                MemoryCategory.PAST_SESSION_ANCHOR,
            }
        )
