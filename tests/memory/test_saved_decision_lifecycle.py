from __future__ import annotations

from datetime import datetime, timezone

import pytest
from argus.memory.contracts import (
    MemoryCategory,
    MemoryProvenance,
    MemorySourceKind,
    SavedDecisionSource,
)
from argus.memory.service import MemoryService, MemoryServiceConfig
from argus.memory.store import InMemoryCanonicalMemoryStore
from argus.memory.subject import (
    MemoryAccountKind,
    MemorySubject,
    PersonalizationMemoryUnavailable,
    RegisteredMemoryOwner,
    require_registered,
)
from pydantic import ValidationError

OWNER_ID = "b5980428-51d2-49ec-a36f-b3aa48193c66"
NOW = datetime(2026, 7, 29, 15, 30, tzinfo=timezone.utc)
SAVED_DECISION_SCOPE = frozenset(
    {
        MemoryCategory.EXPLICIT_DECISION_NOTE,
        MemoryCategory.PAST_SESSION_ANCHOR,
    }
)


def _saved_decision_source() -> SavedDecisionSource:
    return SavedDecisionSource(
        label="Revisit the lower-drawdown version",
        value="The high-drawdown version was rejected.",
        provenance=MemoryProvenance(
            source_kind=MemorySourceKind.DECISION_NOTE,
            source_id="decision-note-42",
            source_version="1",
        ),
    )


def _service(
    store: InMemoryCanonicalMemoryStore,
) -> tuple[MemoryService, MemorySubject]:
    return _service_with_ids(
        store,
        ("candidate-1", "consent-1", "record-1"),
    )


def _service_with_ids(
    store: InMemoryCanonicalMemoryStore,
    ids: tuple[str, ...],
) -> tuple[MemoryService, MemorySubject]:
    generated_ids = iter(ids)
    service = MemoryService(
        config=MemoryServiceConfig(available=True),
        clock=lambda: NOW,
        id_factory=lambda: next(generated_ids),
        store=store,
    )
    subject = MemorySubject(
        owner_id=OWNER_ID,
        kind=MemoryAccountKind.REGISTERED,
    )
    return service, subject


def _canonical_state(
    store: InMemoryCanonicalMemoryStore,
    owner: RegisteredMemoryOwner,
) -> tuple[
    frozenset[MemoryCategory],
    tuple[object, ...],
    tuple[object, ...],
]:
    return (
        store.enabled_categories(owner),
        store.list_consent_receipts(owner),
        store.list_records(owner),
    )


def test_saved_decision_confirmation_creates_one_provenance_backed_record() -> None:
    """Catches confirmation that loses provenance or creates duplicate records."""
    store = InMemoryCanonicalMemoryStore()
    service, subject = _service(store)
    owner = require_registered(subject)

    proposal = service.propose_saved_decision(subject, _saved_decision_source())

    assert proposal.candidate.opt_in_scope == SAVED_DECISION_SCOPE
    assert store.enabled_categories(owner) == frozenset()
    assert store.list_records(owner) == ()
    assert store.list_consent_receipts(owner) == ()

    confirmation = service.confirm(subject, proposal.candidate.id)

    assert confirmation.created is True
    assert confirmation.record is not None
    assert confirmation.consent_receipt is not None
    assert store.enabled_categories(owner) == SAVED_DECISION_SCOPE
    assert store.list_records(owner) == (confirmation.record,)
    assert store.list_consent_receipts(owner) == (confirmation.consent_receipt,)
    assert store.get_candidate(owner, proposal.candidate.id) is None

    record = confirmation.record
    assert record.owner_id == OWNER_ID
    assert record.category is MemoryCategory.EXPLICIT_DECISION_NOTE
    assert record.provenance == proposal.candidate.source.provenance
    assert record.created_at == NOW
    assert record.consent_receipt.confirmed is True
    assert record.consent_receipt.schema_version == "argus.memory-consent/v1"
    assert record.consent_receipt.scope == SAVED_DECISION_SCOPE
    assert "provider" not in record.model_dump()

    with pytest.raises(ValidationError):
        record.owner_id = "64de9c04-b0af-4d11-8986-28c72e1ac174"


def test_declined_saved_decision_never_creates_a_record() -> None:
    """Catches decline paths that persist consent, records, or category enablement."""
    store = InMemoryCanonicalMemoryStore()
    service, subject = _service(store)
    owner = require_registered(subject)
    proposal = service.propose_saved_decision(subject, _saved_decision_source())

    assert service.decline(subject, proposal.candidate.id) is True
    assert service.decline(subject, proposal.candidate.id) is False

    assert store.get_candidate(owner, proposal.candidate.id) is None
    assert store.enabled_categories(owner) == frozenset()
    assert store.list_consent_receipts(owner) == ()
    assert store.list_records(owner) == ()


def test_repeated_confirmation_is_inert() -> None:
    """Catches confirmation replay that creates a second receipt or record."""
    store = InMemoryCanonicalMemoryStore()
    service, subject = _service(store)
    owner = require_registered(subject)
    proposal = service.propose_saved_decision(subject, _saved_decision_source())

    first = service.confirm(subject, proposal.candidate.id)
    repeated = service.confirm(subject, proposal.candidate.id)

    assert first.created is True
    assert repeated.created is False
    assert repeated.record is None
    assert repeated.consent_receipt is None
    assert len(store.list_records(owner)) == 1
    assert len(store.list_consent_receipts(owner)) == 1


def test_receipt_id_collision_rejects_without_mutating_canonical_state() -> None:
    """Catches receipt-ID reuse that overwrites prior consent and consumes a candidate."""
    store = InMemoryCanonicalMemoryStore()
    service, subject = _service_with_ids(
        store,
        (
            "candidate-1",
            "consent-shared",
            "record-1",
            "candidate-2",
            "consent-shared",
            "record-2",
        ),
    )
    owner = require_registered(subject)
    first = service.propose_saved_decision(subject, _saved_decision_source())
    assert service.confirm(subject, first.candidate.id).created is True
    second = service.propose_saved_decision(subject, _saved_decision_source())
    before = _canonical_state(store, owner)

    with pytest.raises(ValueError, match="consent receipt id already exists"):
        service.confirm(subject, second.candidate.id)

    assert store.get_candidate(owner, second.candidate.id) == second.candidate
    assert _canonical_state(store, owner) == before


def test_record_id_collision_rejects_without_mutating_canonical_state() -> None:
    """Catches record-ID reuse that overwrites memory and consumes a candidate."""
    store = InMemoryCanonicalMemoryStore()
    service, subject = _service_with_ids(
        store,
        (
            "candidate-1",
            "consent-1",
            "record-shared",
            "candidate-2",
            "consent-2",
            "record-shared",
        ),
    )
    owner = require_registered(subject)
    first = service.propose_saved_decision(subject, _saved_decision_source())
    assert service.confirm(subject, first.candidate.id).created is True
    second = service.propose_saved_decision(subject, _saved_decision_source())
    before = _canonical_state(store, owner)

    with pytest.raises(ValueError, match="memory record id already exists"):
        service.confirm(subject, second.candidate.id)

    assert store.get_candidate(owner, second.candidate.id) == second.candidate
    assert _canonical_state(store, owner) == before


def test_cross_owner_confirm_and_decline_cannot_consume_candidate() -> None:
    """Catches owner lookup that lets another account consume a pending candidate."""
    store = InMemoryCanonicalMemoryStore()
    service, subject = _service(store)
    owner = require_registered(subject)
    proposal = service.propose_saved_decision(subject, _saved_decision_source())
    other_subject = MemorySubject(
        owner_id="2bfab090-4075-4b52-8dd4-7a7eb725b6ba",
        kind=MemoryAccountKind.REGISTERED,
    )

    assert service.confirm(other_subject, proposal.candidate.id).created is False
    assert service.decline(other_subject, proposal.candidate.id) is False
    assert store.get_candidate(owner, proposal.candidate.id) == proposal.candidate
    assert _canonical_state(store, owner) == (frozenset(), (), ())


def test_registered_default_off_proposal_creates_no_state() -> None:
    """Catches default-off service access that creates a candidate or consent state."""
    store = InMemoryCanonicalMemoryStore()

    def explode() -> object:
        raise AssertionError("default-off proposal must not call clock or id factory")

    service = MemoryService(
        store=store,
        clock=explode,  # type: ignore[arg-type]
        id_factory=explode,  # type: ignore[arg-type]
    )
    subject = MemorySubject(
        owner_id=OWNER_ID,
        kind=MemoryAccountKind.REGISTERED,
    )
    owner = require_registered(subject)

    with pytest.raises(PersonalizationMemoryUnavailable):
        service.propose_saved_decision(subject, _saved_decision_source())

    assert store.get_candidate(owner, "candidate-1") is None
    assert _canonical_state(store, owner) == (frozenset(), (), ())


def test_confirmation_replay_calls_neither_clock_nor_id_factory() -> None:
    """Catches inert replay that still consumes time or identity dependencies."""
    store = InMemoryCanonicalMemoryStore()
    calls = {"clock": 0, "id_factory": 0}
    generated_ids = iter(("candidate-1", "consent-1", "record-1"))

    def clock() -> datetime:
        calls["clock"] += 1
        return NOW

    def id_factory() -> str:
        calls["id_factory"] += 1
        return next(generated_ids)

    service = MemoryService(
        config=MemoryServiceConfig(available=True),
        clock=clock,
        id_factory=id_factory,
        store=store,
    )
    subject = MemorySubject(
        owner_id=OWNER_ID,
        kind=MemoryAccountKind.REGISTERED,
    )
    proposal = service.propose_saved_decision(subject, _saved_decision_source())
    assert service.confirm(subject, proposal.candidate.id).created is True
    before_replay = dict(calls)

    repeated = service.confirm(subject, proposal.candidate.id)

    assert repeated.created is False
    assert calls == before_replay


def test_id_factory_failure_leaves_candidate_and_canonical_state_unchanged() -> None:
    """Catches partial receipt persistence when record ID generation fails."""
    store = InMemoryCanonicalMemoryStore()
    generated_ids: list[str | RuntimeError] = [
        "candidate-1",
        "consent-1",
        RuntimeError("record id unavailable"),
    ]

    def id_factory() -> str:
        generated = generated_ids.pop(0)
        if isinstance(generated, RuntimeError):
            raise generated
        return generated

    service = MemoryService(
        config=MemoryServiceConfig(available=True),
        clock=lambda: NOW,
        id_factory=id_factory,
        store=store,
    )
    subject = MemorySubject(
        owner_id=OWNER_ID,
        kind=MemoryAccountKind.REGISTERED,
    )
    owner = require_registered(subject)
    proposal = service.propose_saved_decision(subject, _saved_decision_source())
    before = _canonical_state(store, owner)

    with pytest.raises(RuntimeError, match="record id unavailable"):
        service.confirm(subject, proposal.candidate.id)

    assert store.get_candidate(owner, proposal.candidate.id) == proposal.candidate
    assert _canonical_state(store, owner) == before


def test_record_validation_failure_leaves_canonical_state_unchanged() -> None:
    """Catches partial consent persistence when memory-record validation fails."""
    store = InMemoryCanonicalMemoryStore()
    service, subject = _service_with_ids(
        store,
        ("candidate-1", "consent-1", ""),
    )
    owner = require_registered(subject)
    proposal = service.propose_saved_decision(subject, _saved_decision_source())
    before = _canonical_state(store, owner)

    with pytest.raises(ValidationError):
        service.confirm(subject, proposal.candidate.id)

    assert store.get_candidate(owner, proposal.candidate.id) == proposal.candidate
    assert _canonical_state(store, owner) == before
