"""Confirm without a re-attestation reuses the stored, digest-bound assessment.

The stored candidate's own sensitivity still passes the policy preflight, so a
restricted candidate can never be minted into a record by omitting the
parameter, and restricted contexts still suppress first.
"""

from __future__ import annotations

from datetime import datetime, timezone

from argus.memory.contracts import (
    MemoryCandidate,
    MemoryCandidateDraft,
    MemoryCategory,
    MemoryOperationContext,
    MemoryProposalTrigger,
    MemoryProvenance,
    MemorySensitivityFlag,
    MemorySourceKind,
    SavedDecisionSource,
    SensitivityAssessment,
    SensitivityStatus,
    bind_sensitivity_assessment,
)
from argus.memory.service import MemoryService, MemoryServiceConfig
from argus.memory.store import InMemoryCanonicalMemoryStore
from argus.memory.subject import (
    MemoryAccountKind,
    MemorySubject,
    require_registered,
)

SUBJECT = MemorySubject(
    owner_id="owner-confirm-stored",
    kind=MemoryAccountKind.REGISTERED,
)


def _service(store: InMemoryCanonicalMemoryStore) -> MemoryService:
    return MemoryService(
        store=store,
        config=MemoryServiceConfig(available=True),
    )


def _provenance() -> MemoryProvenance:
    return MemoryProvenance(
        source_kind=MemorySourceKind.MESSAGE,
        source_id="message-1",
        source_version="1",
    )


def _draft(sensitivity: SensitivityAssessment) -> MemoryCandidateDraft:
    return MemoryCandidateDraft(
        category=MemoryCategory.WORKFLOW_PREFERENCE,
        value="Show assumptions before results.",
        label="Assumptions first",
        future_benefit="Argus can keep the preferred review order.",
        provenance=(_provenance(),),
        trigger=MemoryProposalTrigger.EXPLICIT_REQUEST,
        sensitivity=sensitivity,
    )


def test_confirm_without_reattestation_mints_a_record_for_clear_candidates() -> None:
    store = InMemoryCanonicalMemoryStore()
    service = _service(store)
    service.enable(SUBJECT, frozenset({MemoryCategory.WORKFLOW_PREFERENCE}))
    proposal = service.propose(
        SUBJECT,
        _draft(SensitivityAssessment(status=SensitivityStatus.CLEAR)),
        MemoryOperationContext.ORDINARY,
    )
    assert proposal is not None

    result = service.confirm(
        SUBJECT,
        proposal.candidate.id,
        context=MemoryOperationContext.ORDINARY,
    )

    assert result.created is True
    assert result.record is not None
    assert result.record.candidate_id == proposal.candidate.id


def test_confirm_without_reattestation_suppresses_restricted_candidates() -> None:
    """A tampered or future-relaxed store cannot leak restricted content into
    a record just because the caller omitted the assessment."""
    store = InMemoryCanonicalMemoryStore()
    service = _service(store)
    service.enable(SUBJECT, frozenset({MemoryCategory.WORKFLOW_PREFERENCE}))

    restricted = bind_sensitivity_assessment(
        SensitivityAssessment(
            status=SensitivityStatus.RESTRICTED,
            flags=frozenset({MemorySensitivityFlag.ACCOUNT_BALANCE}),
        ),
        category=MemoryCategory.WORKFLOW_PREFERENCE,
        label="Assumptions first",
        value="Show assumptions before results.",
        future_benefit="Argus can keep the preferred review order.",
    )
    candidate = MemoryCandidate(
        id="candidate-restricted",
        owner_id=SUBJECT.owner_id,
        category=MemoryCategory.WORKFLOW_PREFERENCE,
        source=SavedDecisionSource(
            label="Assumptions first",
            value="Show assumptions before results.",
            provenance=_provenance(),
        ),
        future_benefit="Argus can keep the preferred review order.",
        provenance_refs=(_provenance(),),
        trigger=MemoryProposalTrigger.EXPLICIT_REQUEST,
        sensitivity=restricted,
        proposed_context=MemoryOperationContext.ORDINARY,
        created_at=datetime.now(timezone.utc),
    )
    assert store.add_candidate_with_prompt(
        require_registered(SUBJECT),
        candidate,
        proactive_prompt_at=None,
        expected_history=None,
    )

    result = service.confirm(
        SUBJECT,
        candidate.id,
        context=MemoryOperationContext.ORDINARY,
    )

    assert result.created is False
    assert result.record is None
    assert service.inspect(SUBJECT) == ()


def test_confirm_without_reattestation_suppresses_restricted_contexts() -> None:
    store = InMemoryCanonicalMemoryStore()
    service = _service(store)
    service.enable(SUBJECT, frozenset({MemoryCategory.WORKFLOW_PREFERENCE}))
    proposal = service.propose(
        SUBJECT,
        _draft(SensitivityAssessment(status=SensitivityStatus.CLEAR)),
        MemoryOperationContext.ORDINARY,
    )
    assert proposal is not None

    result = service.confirm(
        SUBJECT,
        proposal.candidate.id,
        context=MemoryOperationContext.BROKER,
    )

    assert result.created is False
    assert service.inspect(SUBJECT) == ()
