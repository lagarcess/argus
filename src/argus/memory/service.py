"""Registered-only saved-decision memory service."""

from __future__ import annotations

from collections.abc import Callable
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
    MemoryOperationContext,
    MemoryProposalTrigger,
    ProposalResult,
    SavedDecisionSource,
    SensitivityAssessment,
)
from argus.memory.policy import MemoryPolicy
from argus.memory.store import CanonicalMemoryStore, ProposalHistorySnapshot
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
        config: MemoryAvailability | None = None,
        policy: MemoryPolicy | None = None,
        clock: Clock | Callable[[], datetime] = _utc_now,
        id_factory: IdFactory | Callable[[], str] = _new_id,
    ) -> None:
        self._store = store
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
        return self._store.confirm_candidate(
            owner,
            candidate_id,
            clock=lambda: now,
            id_factory=self._id_factory,
        )

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
