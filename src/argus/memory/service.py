"""Personalization-memory lifecycle service (walking skeleton).

Propose -> policy -> explicit confirmation -> canonical record -> bounded
retrieval with provenance -> edit/delete -> disable/reset. Provider calls are
fail-open; the global flag and per-user opt-in both default off.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from loguru import logger
from pydantic import BaseModel, Field

from argus.memory.contracts import (
    ConsentGrant,
    ConsentState,
    MemoryCandidate,
    MemoryCategory,
    MemoryRecord,
    MemorySourceRef,
    ProposalReason,
    SensitivityFlag,
)
from argus.memory.policy import MemoryPolicy, PolicyDecision
from argus.memory.provider import MemoryRetrievalProvider
from argus.memory.store import CanonicalMemoryStore

MEMORY_ENABLED_ENV = "ARGUS_MEMORY_ENABLED"


def memory_globally_enabled() -> bool:
    """Backend feature flag; only the literal string ``true`` enables it."""
    return os.getenv(MEMORY_ENABLED_ENV, "false").strip().lower() == "true"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex


class SavedDecisionSource(BaseModel):
    """Ids-only projection of a saved decision used to ground a proposal."""

    decision_note_id: str
    evidence_artifact_id: str
    decision_state: str
    note: str | None = None
    label: str = Field(min_length=1, max_length=120)
    locale: str = "en"


class ExplicitMemoryRequest(BaseModel):
    """A user-stated "remember this" request."""

    text: str = Field(min_length=1)
    label: str = Field(min_length=1, max_length=120)
    category: MemoryCategory
    conversation_id: str | None = None
    sensitivity_flags: list[SensitivityFlag] = Field(default_factory=list)
    locale: str = "en"


class ProposalStatus(str, Enum):
    PROPOSED = "proposed"
    REJECTED_GLOBAL_DISABLED = "rejected_global_disabled"
    REJECTED_POLICY = "rejected_policy"


class ProposalResult(BaseModel):
    status: ProposalStatus
    candidate: MemoryCandidate | None = None
    policy: PolicyDecision | None = None


@dataclass(frozen=True)
class MemoryServiceConfig:
    globally_enabled: bool = False
    retrieval_limit: int = 3
    policy: MemoryPolicy = field(default_factory=MemoryPolicy)


class MemoryService:
    """Owner-scoped memory lifecycle over a canonical store and a provider."""

    def __init__(
        self,
        *,
        store: CanonicalMemoryStore,
        provider: MemoryRetrievalProvider,
        config: MemoryServiceConfig | None = None,
        clock: Callable[[], datetime] = _utc_now,
        id_factory: Callable[[], str] = _new_id,
    ) -> None:
        self._store = store
        self._provider = provider
        self._config = config or MemoryServiceConfig(
            globally_enabled=memory_globally_enabled()
        )
        self._clock = clock
        self._new_id = id_factory

    # -- proposal -----------------------------------------------------------

    def propose_from_saved_decision(
        self, user_id: str, source: SavedDecisionSource
    ) -> ProposalResult:
        value = (
            f"Decision {source.decision_state} on saved evidence"
            f" {source.evidence_artifact_id}"
        )
        if source.note:
            value = f"{value}: {source.note}"
        candidate = MemoryCandidate(
            id=self._new_id(),
            user_id=user_id,
            category=MemoryCategory.EXPLICIT_DECISION_NOTE,
            proposed_value=value,
            label=source.label,
            future_benefit=("Argus can help revisit and compare this decision later"),
            source_refs=[
                MemorySourceRef(kind="decision_note", ref_id=source.decision_note_id),
                MemorySourceRef(
                    kind="evidence_artifact",
                    ref_id=source.evidence_artifact_id,
                ),
            ],
            confidence=1.0,
            proposal_reason=ProposalReason.SAVED_DECISION,
            locale=source.locale,
            created_at=self._clock(),
        )
        return self._propose(candidate)

    def propose_from_explicit_request(
        self, user_id: str, request: ExplicitMemoryRequest
    ) -> ProposalResult:
        source_refs = [MemorySourceRef(kind="explicit_request", ref_id=self._new_id())]
        if request.conversation_id:
            source_refs.append(
                MemorySourceRef(kind="conversation", ref_id=request.conversation_id)
            )
        candidate = MemoryCandidate(
            id=self._new_id(),
            user_id=user_id,
            category=request.category,
            proposed_value=request.text,
            label=request.label,
            future_benefit=("Argus can apply this preference without being re-told"),
            source_refs=source_refs,
            sensitivity_flags=request.sensitivity_flags,
            confidence=1.0,
            proposal_reason=ProposalReason.EXPLICIT_REQUEST,
            locale=request.locale,
            created_at=self._clock(),
        )
        return self._propose(candidate)

    def _propose(self, candidate: MemoryCandidate) -> ProposalResult:
        if not self._config.globally_enabled:
            return ProposalResult(status=ProposalStatus.REJECTED_GLOBAL_DISABLED)
        now = self._clock()
        decision = self._config.policy.evaluate(
            candidate,
            self._store.get_settings(candidate.user_id),
            last_prompted_at=self._store.last_prompted_at(
                candidate.user_id, candidate.category
            ),
            now=now,
        )
        if not decision.allowed:
            return ProposalResult(status=ProposalStatus.REJECTED_POLICY, policy=decision)
        self._store.add_candidate(candidate)
        self._store.mark_prompted(candidate.user_id, candidate.category, now)
        return ProposalResult(
            status=ProposalStatus.PROPOSED,
            candidate=candidate,
            policy=decision,
        )

    # -- confirmation -------------------------------------------------------

    def confirm(self, user_id: str, candidate_id: str) -> MemoryRecord | None:
        if not self._config.globally_enabled:
            return None
        candidate = self._store.get_candidate(user_id, candidate_id)
        if candidate is None:
            return None
        now = self._clock()
        record = MemoryRecord(
            id=self._new_id(),
            user_id=user_id,
            category=candidate.category,
            value=candidate.proposed_value,
            label=candidate.label,
            source_refs=candidate.source_refs,
            consent=ConsentGrant(state=ConsentState.CONFIRMED, decided_at=now),
            stored_reason=(
                f"User confirmed ({candidate.proposal_reason.value}):"
                f" {candidate.future_benefit}"
            ),
            created_at=now,
            updated_at=now,
        )
        provider_ref = self._try_provider(
            "project", lambda: self._provider.project(record)
        )
        if provider_ref is not None:
            record = record.model_copy(update={"provider_ref": provider_ref})
        self._store.add_record(record)
        self._store.discard_candidate(user_id, candidate_id)
        return record

    def decline(self, user_id: str, candidate_id: str) -> None:
        self._store.discard_candidate(user_id, candidate_id)

    # -- provider fail-open -------------------------------------------------

    def _try_provider(self, action: str, call: Callable[[], object]) -> object:
        try:
            return call()
        except Exception as error:  # noqa: BLE001 - fail-open by contract
            logger.warning(
                "memory provider {} failed; continuing without provider: {}",
                action,
                error,
            )
            return None
