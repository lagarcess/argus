from __future__ import annotations

from collections.abc import Callable
from typing import cast
from uuid import UUID

import pytest
from argus.memory.contracts import (
    MemoryProvenance,
    MemorySourceKind,
    SavedDecisionSource,
)
from argus.memory.service import (
    Clock,
    IdFactory,
    MemoryAvailability,
    MemoryService,
)
from argus.memory.store import CanonicalMemoryStore
from argus.memory.subject import (
    MemoryAccountKind,
    MemorySubject,
    PersonalizationMemoryUnavailable,
)

GUEST_OWNER_ID = "9d9ec96b-6fd7-4d8f-b092-b518701674f8"


class _ExplodingDependency:
    @property
    def available(self) -> bool:
        raise AssertionError("config must not be inspected for a Guest")

    def __call__(self) -> object:
        raise AssertionError("clock/id factory must not be called for a Guest")

    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"store.{name} must not be inspected for a Guest")


def _saved_decision_source() -> SavedDecisionSource:
    return SavedDecisionSource(
        label="Keep the lower-drawdown version",
        value="The user rejected the higher-drawdown version.",
        provenance=MemoryProvenance(
            source_kind=MemorySourceKind.DECISION_NOTE,
            source_id="decision-note-guest-test",
            source_version="1",
        ),
    )


def _exploding_service() -> MemoryService:
    exploding = _ExplodingDependency()
    return MemoryService(
        config=cast(MemoryAvailability, exploding),
        clock=cast(Clock, exploding),
        id_factory=cast(IdFactory, exploding),
        store=cast(CanonicalMemoryStore, exploding),
    )


def test_guest_saved_decision_is_denied_before_dependencies() -> None:
    """Catches any service method that touches dependencies before the Guest gate."""
    service = _exploding_service()
    subject = MemorySubject(
        owner_id=GUEST_OWNER_ID,
        kind=MemoryAccountKind.GUEST,
    )
    calls: tuple[Callable[[], object], ...] = (
        lambda: service.propose_saved_decision(subject, _saved_decision_source()),
        lambda: service.confirm(subject, "candidate-1"),
        lambda: service.decline(subject, "candidate-1"),
    )

    for call in calls:
        with pytest.raises(PersonalizationMemoryUnavailable):
            call()


def test_guest_with_valid_owner_uuid_is_still_denied() -> None:
    """Catches authorization based on owner-id shape instead of account kind."""
    UUID(GUEST_OWNER_ID)
    service = _exploding_service()
    subject = MemorySubject(
        owner_id=GUEST_OWNER_ID,
        kind=MemoryAccountKind.GUEST,
    )

    with pytest.raises(PersonalizationMemoryUnavailable):
        service.propose_saved_decision(subject, _saved_decision_source())
