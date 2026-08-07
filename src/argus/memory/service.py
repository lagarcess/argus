"""Registered-only saved-decision memory service."""

from __future__ import annotations

import math
import os
import re
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Generic, Protocol, TypeVar
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError

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
    bind_sensitivity_assessment,
)
from argus.memory.policy import (
    RESTRICTED_CONTEXTS,
    MemoryPolicy,
    PolicyDecision,
    PolicyOutcome,
)
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
    ReconciliationClaim,
)
from argus.memory.subject import (
    MemorySubject,
    PersonalizationMemoryUnavailable,
    RegisteredMemoryOwner,
    require_registered,
)
from argus.memory.telemetry import (
    MemoryDomainEvent,
    MemoryEvalTraceSink,
    MemoryEventSink,
    MemoryOperation,
    MemoryOutcome,
    MemoryPolicyTrace,
    MemoryProviderReceiptSink,
    ProviderCallReceipt,
    ProviderCallStatus,
    ProviderOperation,
    reason_codes_for,
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


class Monotonic(Protocol):
    def __call__(self) -> float: ...


ProviderResultT = TypeVar(
    "ProviderResultT",
    ProviderProjectionResult,
    ProviderSearchResult,
    ProviderCleanupResult,
)


@dataclass(frozen=True)
class _ProviderCallOutcome(Generic[ProviderResultT]):
    result: ProviderResultT | None
    status: ProviderCallStatus
    latency_ms: int | None
    usage_units: int | None = None
    reported_cost_usd: Decimal | None = None


def _personalization_memory_feature_enabled() -> bool:
    # Off by default; this subsystem has no app wiring yet, so a future
    # caller must opt in explicitly once it integrates the service.
    return os.getenv("ARGUS_ENABLE_PERSONALIZATION_MEMORY", "").strip().lower() in {
        "true",
        "1",
        "on",
        "yes",
    }


class MemoryServiceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    available: bool = Field(default_factory=_personalization_memory_feature_enabled)
    candidate_ttl: timedelta = Field(default=timedelta(days=1), gt=timedelta(0))


SAVED_DECISION_FUTURE_BENEFIT = "Argus can revisit and compare this saved decision later."


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
        event_sink: MemoryEventSink | None = None,
        provider_receipt_sink: MemoryProviderReceiptSink | None = None,
        eval_trace_sink: MemoryEvalTraceSink | None = None,
        correlation_id_factory: IdFactory | Callable[[], str] = _new_id,
        monotonic: Monotonic | Callable[[], float] = time.monotonic,
    ) -> None:
        self._store = store
        self._provider = provider if provider is not None else NoOpMemoryProvider()
        self._config = config if config is not None else MemoryServiceConfig()
        self._policy = policy if policy is not None else MemoryPolicy()
        self._clock = clock
        self._id_factory = id_factory
        self._event_sink = event_sink
        self._provider_receipt_sink = provider_receipt_sink
        self._eval_trace_sink = eval_trace_sink
        self._correlation_id_factory = correlation_id_factory
        self._monotonic = monotonic

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
            future_benefit=SAVED_DECISION_FUTURE_BENEFIT,
            provenance=(source.provenance,),
            trigger=MemoryProposalTrigger.SAVED_DECISION,
            sensitivity=sensitivity,
        )
        preflight = self._policy.preflight(draft, context=context)
        correlation_id = self._safe_correlation_id()
        if not preflight.allowed:
            self._record_policy_trace(
                correlation_id,
                MemoryOperation.PROPOSE_SAVED_DECISION,
                preflight.outcome,
            )
            self._emit_event(
                correlation_id,
                MemoryOperation.PROPOSE_SAVED_DECISION,
                MemoryOutcome.SUPPRESSED,
                category=draft.category,
            )
            return None
        try:
            self._require_available()
        except PersonalizationMemoryUnavailable:
            self._record_policy_trace(
                correlation_id,
                MemoryOperation.PROPOSE_SAVED_DECISION,
                preflight.outcome,
            )
            self._emit_event(
                correlation_id,
                MemoryOperation.PROPOSE_SAVED_DECISION,
                MemoryOutcome.UNAVAILABLE,
                category=draft.category,
            )
            raise
        return self._propose(
            owner,
            draft,
            context,
            correlation_id=correlation_id,
            operation=MemoryOperation.PROPOSE_SAVED_DECISION,
        )

    def propose(
        self,
        subject: MemorySubject,
        draft: MemoryCandidateDraft,
        context: MemoryOperationContext,
    ) -> ProposalResult | None:
        owner = require_registered(subject)
        preflight = self._policy.preflight(draft, context=context)
        correlation_id = self._safe_correlation_id()
        if not preflight.allowed:
            self._record_policy_trace(
                correlation_id,
                MemoryOperation.PROPOSE,
                preflight.outcome,
            )
            self._emit_event(
                correlation_id,
                MemoryOperation.PROPOSE,
                MemoryOutcome.SUPPRESSED,
                category=draft.category,
            )
            return None
        try:
            self._require_available()
        except PersonalizationMemoryUnavailable:
            self._record_policy_trace(
                correlation_id,
                MemoryOperation.PROPOSE,
                preflight.outcome,
            )
            self._emit_event(
                correlation_id,
                MemoryOperation.PROPOSE,
                MemoryOutcome.UNAVAILABLE,
                category=draft.category,
            )
            raise
        return self._propose(
            owner,
            draft,
            context,
            correlation_id=correlation_id,
            operation=MemoryOperation.PROPOSE,
        )

    def enable(
        self,
        subject: MemorySubject,
        categories: frozenset[MemoryCategory],
        *,
        idempotency_key: str | None = None,
    ) -> MemoryConsentSettings:
        owner = require_registered(subject)
        self._policy.validate_enable_scope(categories)
        correlation_id = self._safe_correlation_id()
        self._require_available()
        mutation = self._store.enable_categories(
            owner,
            categories,
            clock=self._clock,
            id_factory=self._id_factory,
            idempotency_key=idempotency_key,
        )
        settings = mutation.settings
        self._emit_event(
            correlation_id,
            MemoryOperation.ENABLE,
            MemoryOutcome.ENABLED,
            safe_count=len(settings.enabled_categories),
        )
        return settings

    def confirm(
        self,
        subject: MemorySubject,
        candidate_id: str,
        *,
        sensitivity: SensitivityAssessment | None = None,
        context: MemoryOperationContext,
    ) -> ConfirmationResult:
        owner = require_registered(subject)
        # None confirms exactly what was proposed: the stored candidate's own
        # assessment is preflighted after load, so nothing skips the gate.
        if sensitivity is not None:
            preflight = self._policy.preflight_context(
                sensitivity=sensitivity,
                context=context,
            )
        elif context in RESTRICTED_CONTEXTS:
            preflight = PolicyDecision(
                allowed=False,
                outcome=PolicyOutcome.SUPPRESSED_CONTEXT,
            )
        else:
            preflight = PolicyDecision(
                allowed=True,
                outcome=PolicyOutcome.ALLOWED,
            )
        correlation_id = self._safe_correlation_id()
        if not preflight.allowed:
            self._record_policy_trace(
                correlation_id,
                MemoryOperation.CONFIRM,
                preflight.outcome,
            )
            self._emit_event(
                correlation_id,
                MemoryOperation.CONFIRM,
                MemoryOutcome.SUPPRESSED,
            )
            return ConfirmationResult(created=False)
        try:
            self._require_available()
        except PersonalizationMemoryUnavailable:
            self._record_policy_trace(
                correlation_id,
                MemoryOperation.CONFIRM,
                preflight.outcome,
            )
            self._emit_event(
                correlation_id,
                MemoryOperation.CONFIRM,
                MemoryOutcome.UNAVAILABLE,
            )
            raise
        candidate = self._store.get_candidate(owner, candidate_id)
        if candidate is None:
            self._record_policy_trace(
                correlation_id,
                MemoryOperation.CONFIRM,
                preflight.outcome,
            )
            self._emit_event(
                correlation_id,
                MemoryOperation.CONFIRM,
                MemoryOutcome.NO_CHANGE,
            )
            return ConfirmationResult(created=False)

        now = self._clock()
        if now - candidate.created_at >= self._config.candidate_ttl:
            self._store.discard_candidate(owner, candidate_id)
            self._record_policy_trace(
                correlation_id,
                MemoryOperation.CONFIRM,
                preflight.outcome,
            )
            self._emit_event(
                correlation_id,
                MemoryOperation.CONFIRM,
                MemoryOutcome.NO_CHANGE,
                category=candidate.category,
            )
            return ConfirmationResult(created=False)

        effective_sensitivity = sensitivity
        if effective_sensitivity is None:
            stored_preflight = self._policy.preflight_context(
                sensitivity=candidate.sensitivity,
                context=context,
            )
            if not stored_preflight.allowed:
                self._record_policy_trace(
                    correlation_id,
                    MemoryOperation.CONFIRM,
                    stored_preflight.outcome,
                )
                self._emit_event(
                    correlation_id,
                    MemoryOperation.CONFIRM,
                    MemoryOutcome.SUPPRESSED,
                    category=candidate.category,
                )
                return ConfirmationResult(created=False)
            effective_sensitivity = candidate.sensitivity

        try:
            bound_sensitivity = bind_sensitivity_assessment(
                effective_sensitivity,
                category=candidate.category,
                label=candidate.source.label,
                value=candidate.source.value,
                future_benefit=candidate.future_benefit,
            )
        except ValueError:
            bound_sensitivity = None
        if bound_sensitivity != candidate.sensitivity:
            self._record_policy_trace(
                correlation_id,
                MemoryOperation.CONFIRM,
                PolicyOutcome.SUPPRESSED_SENSITIVITY,
            )
            self._emit_event(
                correlation_id,
                MemoryOperation.CONFIRM,
                MemoryOutcome.SUPPRESSED,
                category=candidate.category,
            )
            return ConfirmationResult(created=False)

        decision = self._policy.evaluate(
            self._draft_from_candidate(candidate, sensitivity=bound_sensitivity),
            self._store.get_settings(owner),
            context=context,
            last_proactive_prompt_at=None,
            last_declined_at=None,
            now=now,
        )
        self._record_policy_trace(
            correlation_id,
            MemoryOperation.CONFIRM,
            decision.outcome,
        )
        if not decision.allowed or decision.opt_in_scope != candidate.opt_in_scope:
            self._store.discard_candidate(owner, candidate_id)
            self._emit_event(
                correlation_id,
                MemoryOperation.CONFIRM,
                MemoryOutcome.SUPPRESSED,
                category=candidate.category,
            )
            return ConfirmationResult(created=False)
        mutation = self._store.confirm_candidate(
            owner,
            candidate_id,
            clock=lambda: now,
            id_factory=self._id_factory,
        )
        result = mutation.result
        if not result.created or result.record is None:
            self._emit_event(
                correlation_id,
                MemoryOperation.CONFIRM,
                MemoryOutcome.NO_CHANGE,
                category=candidate.category,
            )
            return result
        self._emit_event(
            correlation_id,
            MemoryOperation.CONFIRM,
            MemoryOutcome.CONFIRMED,
            category=result.record.category,
        )
        reconciliation_generation = mutation.reconciliation_generation
        assert reconciliation_generation is not None
        claim = self._store.claim_reconciliation_turn(
            owner,
            result.record.id,
            reconciliation_generation,
        )
        if claim is None:
            return result
        reconciliation_status = ProviderReconciliationStatus.RECONCILIATION_REQUIRED
        try:
            projection_call = self._call_provider_project(
                owner,
                result.record,
                correlation_id,
            )
            projection = projection_call.result
            if projection is None:
                self._record_provider_receipt(
                    correlation_id,
                    ProviderOperation.PROJECT,
                    projection_call,
                    ProviderReconciliationStatus.RECONCILIATION_REQUIRED,
                )
                return result
            if projection.status is not ProviderReconciliationStatus.SYNCHRONIZED:
                reconciliation_status = projection.status
                self._record_provider_receipt(
                    correlation_id,
                    ProviderOperation.PROJECT,
                    projection_call,
                    projection.status,
                )
                return result
            assert projection.provider_ref is not None
            ref_committed = self._store.compare_and_set_provider_ref(
                owner,
                result.record.id,
                expected_record=result.record,
                expected_provider_ref=None,
                reconciliation_claim=claim,
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
                    correlation_id,
                )
            self._record_provider_receipt(
                correlation_id,
                ProviderOperation.PROJECT,
                projection_call,
                (
                    ProviderReconciliationStatus.SYNCHRONIZED
                    if ref_committed
                    else ProviderReconciliationStatus.RECONCILIATION_REQUIRED
                ),
            )
            reconciliation_status = (
                ProviderReconciliationStatus.SYNCHRONIZED
                if ref_committed
                else ProviderReconciliationStatus.RECONCILIATION_REQUIRED
            )
        finally:
            self._finish_reconciliation_claim(
                owner,
                claim,
                reconciliation_status,
            )
        return result

    def decline(self, subject: MemorySubject, candidate_id: str) -> bool:
        owner = require_registered(subject)
        correlation_id = self._safe_correlation_id()
        self._require_available()
        candidate = self._store.get_candidate(owner, candidate_id)
        if candidate is None:
            self._emit_event(
                correlation_id,
                MemoryOperation.DECLINE,
                MemoryOutcome.NO_CHANGE,
            )
            return False
        declined_at = (
            None
            if candidate.trigger is MemoryProposalTrigger.EXPLICIT_REQUEST
            else self._clock()
        )
        declined = self._store.decline_candidate_with_history(
            owner,
            candidate_id,
            declined_at=declined_at,
        )
        self._emit_event(
            correlation_id,
            MemoryOperation.DECLINE,
            MemoryOutcome.DECLINED if declined else MemoryOutcome.NO_CHANGE,
            category=candidate.category,
        )
        return declined

    def settings(self, subject: MemorySubject) -> MemoryConsentSettings:
        owner = require_registered(subject)
        return self._store.get_settings(owner)

    def inspect(self, subject: MemorySubject) -> tuple[MemoryRecord, ...]:
        owner = require_registered(subject)
        correlation_id = self._safe_correlation_id()
        records = tuple(
            sorted(
                self._store.list_records(owner),
                key=lambda record: (record.created_at, record.id),
            )
        )
        self._emit_event(
            correlation_id,
            MemoryOperation.INSPECT,
            MemoryOutcome.INSPECTED,
            safe_count=len(records),
        )
        return records

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
        correlation_id = self._safe_correlation_id()
        if context in RESTRICTED_CONTEXTS:
            self._emit_event(
                correlation_id,
                MemoryOperation.RETRIEVE,
                MemoryOutcome.SUPPRESSED,
            )
            return ()
        try:
            self._require_available()
        except PersonalizationMemoryUnavailable:
            self._emit_event(
                correlation_id,
                MemoryOperation.RETRIEVE,
                MemoryOutcome.UNAVAILABLE,
            )
            raise
        if not isinstance(purpose, MemoryUsePurpose):
            raise TypeError("purpose must be a MemoryUsePurpose")
        if not 1 <= limit <= 10:
            raise ValueError("retrieval limit must be between 1 and 10")
        normalized_query = query.strip()
        if not normalized_query:
            self._emit_retrieval_result(correlation_id, ())
            return ()

        settings = self._store.get_settings(owner)
        if not settings.enabled:
            self._emit_retrieval_result(correlation_id, ())
            return ()
        allowed_categories = (
            self._categories_for_purpose(purpose) & settings.enabled_categories
        )
        if not allowed_categories:
            self._emit_retrieval_result(correlation_id, ())
            return ()
        records = {
            record.id: record
            for record in self._store.list_records(owner)
            if record.owner_id == owner.owner_id and record.category in allowed_categories
        }
        if not records:
            self._emit_retrieval_result(correlation_id, ())
            return ()

        provider_result = self._search_provider(
            owner,
            normalized_query,
            limit,
            correlation_id,
        )
        if (
            provider_result is not None
            and provider_result.status is ProviderSearchStatus.ANSWERED
        ):
            result = self._rehydrate_provider_hits(
                records,
                provider_result,
                limit=limit,
            )
        else:
            result = self._canonical_fallback(
                records.values(),
                normalized_query,
                limit=limit,
            )
        self._emit_retrieval_result(correlation_id, result)
        return result

    def explain(
        self,
        subject: MemorySubject,
        record_id: str,
    ) -> MemoryExplanation | None:
        owner = require_registered(subject)
        correlation_id = self._safe_correlation_id()
        record = self._store.get_record(owner, record_id)
        if record is None:
            self._emit_event(
                correlation_id,
                MemoryOperation.EXPLAIN,
                MemoryOutcome.NO_CHANGE,
            )
            return None
        explanation = MemoryExplanation(
            record_id=record.id,
            category=record.category,
            provenance=record.provenance_refs,
            consent_receipt_id=record.consent_receipt.id,
            consent_schema_version=record.consent_receipt.schema_version,
            confirmed_at=record.consent_receipt.confirmed_at,
        )
        self._emit_event(
            correlation_id,
            MemoryOperation.EXPLAIN,
            MemoryOutcome.EXPLAINED,
            category=record.category,
        )
        return explanation

    def edit(
        self,
        subject: MemorySubject,
        record_id: str,
        edit: MemoryEdit,
    ) -> MemoryControlResult:
        owner = require_registered(subject)
        self._validate_record_id(record_id)
        self._validate_edit_sensitivity(edit.sensitivity)
        correlation_id = self._safe_correlation_id()
        mutation = self._store.edit_record(
            owner,
            record_id,
            value=edit.value,
            label=edit.label,
            clock=self._clock,
        )
        if mutation is None:
            self._emit_event(
                correlation_id,
                MemoryOperation.EDIT,
                MemoryOutcome.NO_CHANGE,
            )
            return MemoryControlResult(
                changed=False,
                provider_status=ProviderReconciliationStatus.NOT_APPLICABLE,
            )
        assert mutation.after is not None
        result = MemoryControlResult(
            changed=True,
            record=mutation.after,
            provider_status=self._reconcile_edit(
                owner,
                mutation,
                correlation_id,
            ),
        )
        self._emit_event(
            correlation_id,
            MemoryOperation.EDIT,
            MemoryOutcome.EDITED,
            category=mutation.after.category,
        )
        return result

    def delete(
        self,
        subject: MemorySubject,
        record_id: str,
    ) -> MemoryControlResult:
        owner = require_registered(subject)
        self._validate_record_id(record_id)
        correlation_id = self._safe_correlation_id()
        mutation = self._store.delete_record(owner, record_id)
        if mutation is None:
            self._emit_event(
                correlation_id,
                MemoryOperation.DELETE,
                MemoryOutcome.NO_CHANGE,
            )
            return MemoryControlResult(
                changed=False,
                provider_status=ProviderReconciliationStatus.NOT_APPLICABLE,
            )
        reconciliation_generation = mutation.reconciliation_generation
        assert reconciliation_generation is not None
        claim = self._store.claim_reconciliation_turn(
            owner,
            record_id,
            reconciliation_generation,
        )
        if claim is None:
            provider_status = ProviderReconciliationStatus.RECONCILIATION_REQUIRED
            reconciliation_finished = False
        else:
            provider_status = ProviderReconciliationStatus.RECONCILIATION_REQUIRED
            try:
                if not mutation.cleanup_refs:
                    provider_status = ProviderReconciliationStatus.NOT_APPLICABLE
                else:
                    cleanup_statuses = tuple(
                        self._cleanup_provider_target(
                            owner,
                            record_id,
                            provider_ref,
                            correlation_id,
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
                reconciliation_finished = self._finish_reconciliation_claim(
                    owner,
                    claim,
                    provider_status,
                )
        if not reconciliation_finished:
            provider_status = ProviderReconciliationStatus.RECONCILIATION_REQUIRED
        result = MemoryControlResult(
            changed=True,
            provider_status=provider_status,
        )
        self._emit_event(
            correlation_id,
            MemoryOperation.DELETE,
            MemoryOutcome.DELETED,
            category=mutation.before.category,
        )
        return result

    def disable(self, subject: MemorySubject) -> MemoryControlResult:
        owner = require_registered(subject)
        correlation_id = self._safe_correlation_id()
        changed = self._store.disable(owner)
        result = MemoryControlResult(
            changed=changed,
            provider_status=ProviderReconciliationStatus.NOT_APPLICABLE,
        )
        self._emit_event(
            correlation_id,
            MemoryOperation.DISABLE,
            MemoryOutcome.DISABLED if changed else MemoryOutcome.NO_CHANGE,
        )
        return result

    def reset(self, subject: MemorySubject) -> MemoryControlResult:
        owner = require_registered(subject)
        correlation_id = self._safe_correlation_id()
        reset = self._store.reset(owner)
        reconciliation_generation = reset.reconciliation_generation
        if reconciliation_generation is None:
            self._emit_event(
                correlation_id,
                MemoryOperation.RESET,
                MemoryOutcome.RESET if reset.changed else MemoryOutcome.NO_CHANGE,
            )
            return MemoryControlResult(
                changed=reset.changed,
                provider_status=ProviderReconciliationStatus.NOT_APPLICABLE,
            )
        claim = self._store.claim_reconciliation_turn(
            owner,
            "",
            reconciliation_generation,
        )
        if claim is None:
            return MemoryControlResult(
                changed=reset.changed,
                provider_status=(ProviderReconciliationStatus.RECONCILIATION_REQUIRED),
            )
        cleanup_call = self._call_provider_reset(owner, correlation_id)
        cleanup = cleanup_call.result
        provider_status = ProviderReconciliationStatus.RECONCILIATION_REQUIRED
        if (
            cleanup is not None
            and cleanup.status is ProviderReconciliationStatus.SYNCHRONIZED
            and self._store.complete_owner_reset(owner, claim)
        ):
            provider_status = ProviderReconciliationStatus.SYNCHRONIZED
        else:
            self._store.finish_reconciliation_claim(
                owner,
                claim,
                succeeded=False,
                error_code="provider_reconciliation_required",
                completed_at=self._clock(),
            )
        self._record_provider_receipt(
            correlation_id,
            ProviderOperation.RESET,
            cleanup_call,
            provider_status,
        )
        result = MemoryControlResult(
            changed=reset.changed,
            provider_status=provider_status,
        )
        self._emit_event(
            correlation_id,
            MemoryOperation.RESET,
            MemoryOutcome.RESET if reset.changed else MemoryOutcome.NO_CHANGE,
        )
        return result

    def _propose(
        self,
        owner: RegisteredMemoryOwner,
        draft: MemoryCandidateDraft,
        context: MemoryOperationContext,
        *,
        correlation_id: str | None,
        operation: MemoryOperation,
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
        self._record_policy_trace(
            correlation_id,
            operation,
            decision.outcome,
        )
        if not decision.allowed:
            self._emit_event(
                correlation_id,
                operation,
                MemoryOutcome.SUPPRESSED,
                category=draft.category,
            )
            return None

        bound_sensitivity = bind_sensitivity_assessment(
            draft.sensitivity,
            category=draft.category,
            label=draft.label,
            value=draft.value,
            future_benefit=draft.future_benefit,
        )
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
            sensitivity=bound_sensitivity,
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
            self._emit_event(
                correlation_id,
                operation,
                MemoryOutcome.NO_CHANGE,
                category=draft.category,
            )
            return None
        result = ProposalResult(candidate=candidate)
        self._emit_event(
            correlation_id,
            operation,
            MemoryOutcome.CANDIDATE_CREATED,
            category=draft.category,
        )
        return result

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

    def _finish_reconciliation_claim(
        self,
        owner: RegisteredMemoryOwner,
        claim: ReconciliationClaim,
        status: ProviderReconciliationStatus,
    ) -> bool:
        succeeded = status in {
            ProviderReconciliationStatus.SYNCHRONIZED,
            ProviderReconciliationStatus.NOT_APPLICABLE,
        }
        return self._store.finish_reconciliation_claim(
            owner,
            claim,
            succeeded=succeeded,
            error_code=None if succeeded else "provider_reconciliation_required",
            completed_at=self._clock(),
        )

    def _reconcile_edit(
        self,
        owner: RegisteredMemoryOwner,
        mutation: CanonicalRecordMutation,
        correlation_id: str | None,
    ) -> ProviderReconciliationStatus:
        updated = mutation.after
        assert updated is not None
        reconciliation_generation = mutation.reconciliation_generation
        assert reconciliation_generation is not None
        claim = self._store.claim_reconciliation_turn(
            owner,
            updated.id,
            reconciliation_generation,
        )
        if claim is None:
            return ProviderReconciliationStatus.RECONCILIATION_REQUIRED
        status = ProviderReconciliationStatus.RECONCILIATION_REQUIRED
        try:
            status = self._reconcile_edit_generation(
                owner,
                mutation,
                updated,
                claim,
                correlation_id,
            )
        finally:
            reconciliation_finished = self._finish_reconciliation_claim(
                owner,
                claim,
                status,
            )
        if not reconciliation_finished:
            return ProviderReconciliationStatus.RECONCILIATION_REQUIRED
        return status

    def _reconcile_edit_generation(
        self,
        owner: RegisteredMemoryOwner,
        mutation: CanonicalRecordMutation,
        updated: MemoryRecord,
        reconciliation_claim: ReconciliationClaim,
        correlation_id: str | None,
    ) -> ProviderReconciliationStatus:
        projection_call = self._call_provider_project(
            owner,
            updated,
            correlation_id,
        )
        projection = projection_call.result
        if projection is None:
            if mutation.provider_ref is not None:
                self._store.track_provider_cleanup_target(
                    owner,
                    updated.id,
                    mutation.provider_ref,
                )
            effective_status = ProviderReconciliationStatus.RECONCILIATION_REQUIRED
            self._record_provider_receipt(
                correlation_id,
                ProviderOperation.PROJECT,
                projection_call,
                effective_status,
            )
            return effective_status

        if projection.status is not ProviderReconciliationStatus.SYNCHRONIZED:
            if (
                projection.status is ProviderReconciliationStatus.NOT_APPLICABLE
                and mutation.provider_ref is None
            ):
                effective_status = self._status_with_pending_cleanup(
                    owner,
                    updated.id,
                    ProviderReconciliationStatus.NOT_APPLICABLE,
                )
            else:
                effective_status = ProviderReconciliationStatus.RECONCILIATION_REQUIRED
            if (
                effective_status is ProviderReconciliationStatus.RECONCILIATION_REQUIRED
                and mutation.provider_ref is not None
            ):
                self._store.track_provider_cleanup_target(
                    owner,
                    updated.id,
                    mutation.provider_ref,
                )
            self._record_provider_receipt(
                correlation_id,
                ProviderOperation.PROJECT,
                projection_call,
                effective_status,
            )
            return effective_status
        assert projection.provider_ref is not None
        ref_committed = self._store.compare_and_set_provider_ref(
            owner,
            updated.id,
            expected_record=updated,
            expected_provider_ref=mutation.provider_ref,
            reconciliation_claim=reconciliation_claim,
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
                correlation_id,
            )
            effective_status = ProviderReconciliationStatus.RECONCILIATION_REQUIRED
            self._record_provider_receipt(
                correlation_id,
                ProviderOperation.PROJECT,
                projection_call,
                effective_status,
            )
            return effective_status
        if (
            mutation.provider_ref is not None
            and mutation.provider_ref != projection.provider_ref
        ):
            cleanup_status = self._cleanup_provider_target(
                owner,
                updated.id,
                mutation.provider_ref,
                correlation_id,
            )
            if cleanup_status is not ProviderReconciliationStatus.SYNCHRONIZED:
                self._record_provider_receipt(
                    correlation_id,
                    ProviderOperation.PROJECT,
                    projection_call,
                    cleanup_status,
                )
                return cleanup_status
        effective_status = self._status_with_pending_cleanup(
            owner,
            updated.id,
            ProviderReconciliationStatus.SYNCHRONIZED,
        )
        self._record_provider_receipt(
            correlation_id,
            ProviderOperation.PROJECT,
            projection_call,
            effective_status,
        )
        return effective_status

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
        correlation_id: str | None,
    ) -> ProviderReconciliationStatus:
        if not self._store.track_provider_cleanup_target(
            owner,
            record_id,
            provider_ref,
        ):
            return ProviderReconciliationStatus.RECONCILIATION_REQUIRED
        cleanup_call = self._call_provider_delete(
            owner,
            provider_ref,
            correlation_id,
        )
        cleanup = cleanup_call.result
        if cleanup is None:
            effective_status = ProviderReconciliationStatus.RECONCILIATION_REQUIRED
        elif cleanup.status is ProviderReconciliationStatus.SYNCHRONIZED:
            resolved = self._store.resolve_provider_cleanup_target(
                owner,
                record_id,
                provider_ref,
            )
            effective_status = (
                ProviderReconciliationStatus.SYNCHRONIZED
                if resolved
                else ProviderReconciliationStatus.RECONCILIATION_REQUIRED
            )
        else:
            effective_status = ProviderReconciliationStatus.RECONCILIATION_REQUIRED
        self._record_provider_receipt(
            correlation_id,
            ProviderOperation.DELETE,
            cleanup_call,
            effective_status,
        )
        return effective_status

    def _search_provider(
        self,
        owner: RegisteredMemoryOwner,
        query: str,
        limit: int,
        correlation_id: str | None,
    ) -> ProviderSearchResult | None:
        search_call = self._call_provider_search(
            owner,
            query,
            limit,
            correlation_id,
        )
        self._record_provider_receipt(
            correlation_id,
            ProviderOperation.SEARCH,
            search_call,
            ProviderReconciliationStatus.NOT_APPLICABLE,
        )
        return search_call.result

    def _call_provider_project(
        self,
        owner: RegisteredMemoryOwner,
        record: MemoryRecord,
        correlation_id: str | None,
    ) -> _ProviderCallOutcome[ProviderProjectionResult]:
        started_at = self._provider_started_at(correlation_id)
        try:
            raw_result = self._provider.project(owner, record)
            result = self._validate_provider_result(
                ProviderProjectionResult,
                raw_result,
            )
        except Exception:
            result = None
        if result is None:
            return _ProviderCallOutcome(
                result=None,
                status=ProviderCallStatus.FAILED,
                latency_ms=self._provider_latency_ms(started_at),
            )
        return _ProviderCallOutcome(
            result=result,
            status=self._provider_call_status(result.status),
            latency_ms=self._provider_latency_ms(started_at),
            usage_units=result.usage_units,
            reported_cost_usd=result.reported_cost_usd,
        )

    def _call_provider_search(
        self,
        owner: RegisteredMemoryOwner,
        query: str,
        limit: int,
        correlation_id: str | None,
    ) -> _ProviderCallOutcome[ProviderSearchResult]:
        started_at = self._provider_started_at(correlation_id)
        try:
            raw_result = self._provider.search(owner, query, limit)
            result = self._validate_provider_result(ProviderSearchResult, raw_result)
        except Exception:
            result = None
        if result is None:
            return _ProviderCallOutcome(
                result=None,
                status=ProviderCallStatus.FAILED,
                latency_ms=self._provider_latency_ms(started_at),
            )
        return _ProviderCallOutcome(
            result=result,
            status=(
                ProviderCallStatus.SUCCEEDED
                if result.status is ProviderSearchStatus.ANSWERED
                else ProviderCallStatus.UNAVAILABLE
            ),
            latency_ms=self._provider_latency_ms(started_at),
            usage_units=result.usage_units,
            reported_cost_usd=result.reported_cost_usd,
        )

    def _call_provider_delete(
        self,
        owner: RegisteredMemoryOwner,
        provider_ref: str,
        correlation_id: str | None,
    ) -> _ProviderCallOutcome[ProviderCleanupResult]:
        started_at = self._provider_started_at(correlation_id)
        try:
            raw_result = self._provider.delete(owner, provider_ref)
            result = self._validate_provider_result(
                ProviderCleanupResult,
                raw_result,
            )
        except Exception:
            result = None
        if result is None:
            return _ProviderCallOutcome(
                result=None,
                status=ProviderCallStatus.FAILED,
                latency_ms=self._provider_latency_ms(started_at),
            )
        return _ProviderCallOutcome(
            result=result,
            status=self._provider_call_status(result.status),
            latency_ms=self._provider_latency_ms(started_at),
            usage_units=result.usage_units,
            reported_cost_usd=result.reported_cost_usd,
        )

    def _call_provider_reset(
        self,
        owner: RegisteredMemoryOwner,
        correlation_id: str | None,
    ) -> _ProviderCallOutcome[ProviderCleanupResult]:
        started_at = self._provider_started_at(correlation_id)
        try:
            raw_result = self._provider.reset(owner)
            result = self._validate_provider_result(
                ProviderCleanupResult,
                raw_result,
            )
        except Exception:
            result = None
        if result is None:
            return _ProviderCallOutcome(
                result=None,
                status=ProviderCallStatus.FAILED,
                latency_ms=self._provider_latency_ms(started_at),
            )
        return _ProviderCallOutcome(
            result=result,
            status=self._provider_call_status(result.status),
            latency_ms=self._provider_latency_ms(started_at),
            usage_units=result.usage_units,
            reported_cost_usd=result.reported_cost_usd,
        )

    @staticmethod
    def _validate_provider_result(
        model_type: type[ProviderResultT],
        raw_result: object,
    ) -> ProviderResultT | None:
        try:
            return model_type.model_validate(raw_result)
        except ValidationError:
            if isinstance(raw_result, BaseModel):
                payload = raw_result.model_dump()
            elif isinstance(raw_result, Mapping):
                payload = dict(raw_result)
            else:
                return None
            allowed_fields = set(model_type.model_fields)
            if not set(payload) <= allowed_fields:
                return None
            metric_payload = {
                field: payload.pop(field)
                for field in ("usage_units", "reported_cost_usd")
                if field in payload
            }
            try:
                sanitized = model_type.model_validate(payload).model_dump()
            except ValidationError:
                return None
            for field, value in metric_payload.items():
                try:
                    with_metric = model_type.model_validate({**sanitized, field: value})
                except ValidationError:
                    continue
                sanitized[field] = getattr(with_metric, field)
            return model_type.model_validate(sanitized)

    @staticmethod
    def _provider_call_status(
        reconciliation_status: ProviderReconciliationStatus,
    ) -> ProviderCallStatus:
        if reconciliation_status is ProviderReconciliationStatus.SYNCHRONIZED:
            return ProviderCallStatus.SUCCEEDED
        if reconciliation_status is ProviderReconciliationStatus.NOT_APPLICABLE:
            return ProviderCallStatus.UNAVAILABLE
        return ProviderCallStatus.FAILED

    def _safe_correlation_id(self) -> str | None:
        if (
            self._event_sink is None
            and self._provider_receipt_sink is None
            and self._eval_trace_sink is None
        ):
            return None
        try:
            correlation_id = self._correlation_id_factory()
        except Exception:
            return None
        if (
            not isinstance(correlation_id, str)
            or not correlation_id.strip()
            or len(correlation_id) > 128
        ):
            return None
        return correlation_id

    def _emit_event(
        self,
        correlation_id: str | None,
        operation: MemoryOperation,
        outcome: MemoryOutcome,
        *,
        category: MemoryCategory | None = None,
        safe_count: int | None = None,
    ) -> None:
        if correlation_id is None or self._event_sink is None:
            return
        try:
            self._event_sink.emit(
                MemoryDomainEvent(
                    correlation_id=correlation_id,
                    operation=operation,
                    outcome=outcome,
                    category=category,
                    safe_count=safe_count,
                )
            )
        except Exception:
            return

    def _record_policy_trace(
        self,
        correlation_id: str | None,
        operation: MemoryOperation,
        outcome: PolicyOutcome,
    ) -> None:
        if correlation_id is None or self._eval_trace_sink is None:
            return
        try:
            trace = MemoryPolicyTrace(
                correlation_id=correlation_id,
                operation=operation,
                outcome=outcome,
                reason_codes=reason_codes_for(outcome),
            )
            self._eval_trace_sink.record(trace)
        except Exception:
            return

    def _record_provider_receipt(
        self,
        correlation_id: str | None,
        operation: ProviderOperation,
        call: _ProviderCallOutcome[ProviderResultT],
        reconciliation_status: ProviderReconciliationStatus,
    ) -> None:
        if correlation_id is None or self._provider_receipt_sink is None:
            return
        try:
            receipt = ProviderCallReceipt(
                correlation_id=correlation_id,
                operation=operation,
                status=call.status,
                latency_ms=call.latency_ms,
                usage_units=call.usage_units,
                reported_cost_usd=call.reported_cost_usd,
                reconciliation_status=reconciliation_status,
            )
            self._provider_receipt_sink.record(receipt)
        except Exception:
            return

    def _safe_monotonic(self) -> float | None:
        try:
            value = self._monotonic()
        except Exception:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        normalized = float(value)
        if not math.isfinite(normalized):
            return None
        return normalized

    def _provider_started_at(self, correlation_id: str | None) -> float | None:
        if correlation_id is None or self._provider_receipt_sink is None:
            return None
        return self._safe_monotonic()

    def _provider_latency_ms(self, started_at: float | None) -> int | None:
        if started_at is None:
            return None
        finished_at = self._safe_monotonic()
        if finished_at is None or finished_at < started_at:
            return None
        return int((finished_at - started_at) * 1000)

    def _emit_retrieval_result(
        self,
        correlation_id: str | None,
        result: tuple[RetrievedMemory, ...],
    ) -> None:
        self._emit_event(
            correlation_id,
            MemoryOperation.RETRIEVE,
            MemoryOutcome.RETRIEVED,
            safe_count=len(result),
        )

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
