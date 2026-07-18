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
from typing import TypeVar

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
    RetrievedMemory,
    SensitivityFlag,
)
from argus.memory.policy import MemoryPolicy, PolicyDecision
from argus.memory.provider import MemoryRetrievalProvider
from argus.memory.store import CanonicalMemoryStore

T = TypeVar("T")

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


class MemoryExplanation(BaseModel):
    """Answers "why was this remembered/used?" from canonical fields only."""

    record_id: str
    stored_reason: str
    provenance: list[MemorySourceRef]
    consent_version: str
    confirmed_at: datetime
    last_used_at: datetime | None


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

    # -- retrieval ----------------------------------------------------------

    def retrieve(self, user_id: str, query: str) -> list[RetrievedMemory]:
        if not self._config.globally_enabled:
            return []
        if not self._store.get_settings(user_id).enabled:
            return []
        records = {
            record.id: record
            for record in self._store.list_records(user_id)
            if record.enabled
        }
        if not records:
            return []
        limit = self._config.retrieval_limit
        hits = self._try_provider(
            "search",
            lambda: self._provider.search(user_id, query, limit),
        )
        if hits is None:
            selected = self._canonical_matches(records, query, limit)
        else:
            selected = []
            for hit in hits:
                record = records.get(hit.record_id)
                if record is None:
                    continue
                matched = ", ".join(hit.matched_terms)
                selected.append((record, f"retrieval provider matched: {matched}"))
        now = self._clock()
        results: list[RetrievedMemory] = []
        for record, why in selected[:limit]:
            used = record.model_copy(update={"last_used_at": now})
            self._store.replace_record(used)
            results.append(
                RetrievedMemory(
                    record=used,
                    why_selected=why,
                    provenance=used.source_refs,
                )
            )
        return results

    @staticmethod
    def _canonical_matches(
        records: dict[str, MemoryRecord], query: str, limit: int
    ) -> list[tuple[MemoryRecord, str]]:
        query_tokens = {token for token in query.lower().split() if len(token) > 2}
        scored: list[tuple[float, str, MemoryRecord, str]] = []
        for record in records.values():
            haystack = f"{record.value} {record.label}".lower().split()
            matched = sorted(query_tokens & set(haystack))
            if matched:
                scored.append(
                    (
                        float(len(matched)),
                        record.id,
                        record,
                        "provider unavailable; canonical store matched: "
                        + ", ".join(matched),
                    )
                )
        scored.sort(key=lambda row: (-row[0], row[1]))
        return [(record, why) for _, _, record, why in scored[:limit]]

    def explain(self, user_id: str, record_id: str) -> MemoryExplanation | None:
        record = self._store.get_record(user_id, record_id)
        if record is None:
            return None
        return MemoryExplanation(
            record_id=record.id,
            stored_reason=record.stored_reason,
            provenance=record.source_refs,
            consent_version=record.consent.version,
            confirmed_at=record.consent.decided_at,
            last_used_at=record.last_used_at,
        )

    # -- provider fail-open -------------------------------------------------

    def _try_provider(self, action: str, call: Callable[[], T]) -> T | None:
        try:
            return call()
        except Exception as error:  # noqa: BLE001 - fail-open by contract
            logger.warning(
                "memory provider {} failed; continuing without provider: {}",
                action,
                error,
            )
            return None
