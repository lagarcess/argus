"""Registered-only saved-decision memory service."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict

from argus.memory.contracts import (
    ConfirmationResult,
    MemoryCandidate,
    MemoryCategory,
    ProposalResult,
    SavedDecisionSource,
)
from argus.memory.store import CanonicalMemoryStore
from argus.memory.subject import (
    MemorySubject,
    PersonalizationMemoryUnavailable,
    require_registered,
)

SAVED_DECISION_OPT_IN_SCOPE = frozenset(
    {
        MemoryCategory.EXPLICIT_DECISION_NOTE,
        MemoryCategory.PAST_SESSION_ANCHOR,
    }
)


class MemoryAvailability(Protocol):
    @property
    def available(self) -> bool: ...


class Clock(Protocol):
    def __call__(self) -> datetime: ...


class IdFactory(Protocol):
    def __call__(self) -> str: ...


class MemoryServiceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    available: bool = False


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
        clock: Clock | Callable[[], datetime] = _utc_now,
        id_factory: IdFactory | Callable[[], str] = _new_id,
    ) -> None:
        self._store = store
        self._config = config if config is not None else MemoryServiceConfig()
        self._clock = clock
        self._id_factory = id_factory

    def propose_saved_decision(
        self, subject: MemorySubject, source: SavedDecisionSource
    ) -> ProposalResult:
        owner = require_registered(subject)
        self._require_available()
        candidate = MemoryCandidate(
            id=self._id_factory(),
            owner_id=owner.owner_id,
            category=MemoryCategory.EXPLICIT_DECISION_NOTE,
            source=source,
            opt_in_scope=SAVED_DECISION_OPT_IN_SCOPE,
            created_at=self._clock(),
        )
        self._store.add_candidate(owner, candidate)
        return ProposalResult(candidate=candidate)

    def confirm(self, subject: MemorySubject, candidate_id: str) -> ConfirmationResult:
        owner = require_registered(subject)
        self._require_available()
        return self._store.confirm_candidate(
            owner,
            candidate_id,
            clock=self._clock,
            id_factory=self._id_factory,
        )

    def decline(self, subject: MemorySubject, candidate_id: str) -> bool:
        owner = require_registered(subject)
        self._require_available()
        return self._store.decline_candidate(owner, candidate_id)

    def _require_available(self) -> None:
        if not self._config.available:
            raise PersonalizationMemoryUnavailable(
                "Personalization memory is not available."
            )
