from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from argus.memory.contracts import (
    MAX_MEMORY_FUTURE_BENEFIT_LENGTH,
    MAX_MEMORY_VALUE_LENGTH,
    MemoryCandidate,
    MemoryCandidateDraft,
    MemoryCategory,
    MemoryConsentActionReceipt,
    MemoryConsentSettings,
    MemoryEdit,
    MemoryOperationContext,
    MemoryProposalTrigger,
    MemoryProvenance,
    MemorySourceKind,
    SavedDecisionSource,
    SensitivityAssessment,
    SensitivityStatus,
    memory_candidate_content_digest,
)
from argus.memory.policy import SAFE_MEMORY_CATEGORIES
from argus.memory.service import MemoryService, MemoryServiceConfig
from argus.memory.store import InMemoryCanonicalMemoryStore
from argus.memory.subject import (
    MemoryAccountKind,
    MemorySubject,
    RegisteredMemoryOwner,
)
from pydantic import ValidationError

NOW = datetime(2026, 7, 29, 22, 0, tzinfo=timezone.utc)
LATER = NOW + timedelta(minutes=5)
OWNER_ID = "ae333ee1-5a12-4181-87f4-e0a48fdf2e9c"
SUBJECT = MemorySubject(owner_id=OWNER_ID, kind=MemoryAccountKind.REGISTERED)
OWNER = RegisteredMemoryOwner(owner_id=OWNER_ID)
SAVED_DECISION_SCOPE = frozenset(
    {
        MemoryCategory.EXPLICIT_DECISION_NOTE,
        MemoryCategory.PAST_SESSION_ANCHOR,
    }
)


def _source() -> SavedDecisionSource:
    return SavedDecisionSource(
        label="Prefer the lower-drawdown version",
        value="Revisit the version with lower historical drawdown.",
        provenance=MemoryProvenance(
            source_kind=MemorySourceKind.DECISION_NOTE,
            source_id="decision-note-consent-integrity",
            source_version="2026-07-29T21:55:00Z",
        ),
    )


def _clear(*, content_digest: str | None = None) -> SensitivityAssessment:
    values: dict[str, object] = {"status": SensitivityStatus.CLEAR}
    if content_digest is not None:
        values["content_digest"] = content_digest
    return SensitivityAssessment.model_validate(values)


def _service(
    store: InMemoryCanonicalMemoryStore,
    ids: tuple[str, ...],
    *,
    now: datetime = NOW,
) -> MemoryService:
    generated_ids = iter(ids)
    return MemoryService(
        store=store,
        config=MemoryServiceConfig(available=True),
        clock=lambda: now,
        id_factory=lambda: next(generated_ids),
    )


def _propose(
    service: MemoryService,
):
    proposal = service.propose_saved_decision(
        SUBJECT,
        _source(),
        sensitivity=_clear(),
        context=MemoryOperationContext.ORDINARY,
    )
    assert proposal is not None
    return proposal


def test_direct_enable_records_exact_action_and_is_idempotent() -> None:
    store = InMemoryCanonicalMemoryStore()
    service = _service(store, ("receipt-direct",))
    requested = frozenset({MemoryCategory.WORKFLOW_PREFERENCE})

    settings = service.enable(
        SUBJECT,
        requested,
        idempotency_key="enable-workflow-1",
    )
    repeated = service.enable(
        SUBJECT,
        requested,
        idempotency_key="enable-workflow-1",
    )

    assert (
        settings
        == repeated
        == MemoryConsentSettings(
            enabled=True,
            enabled_categories=requested,
        )
    )
    assert store.list_consent_receipts(OWNER) == (
        MemoryConsentActionReceipt(
            id="receipt-direct",
            action="direct_enable",
            owner_id=OWNER_ID,
            requested_scope=requested,
            granted_scope=requested,
            effective_scope=requested,
            candidate_id=None,
            schema_version="argus.memory-consent/v1",
            policy_version="argus.memory-policy/v1",
            recorded_at=NOW,
            idempotency_key="enable-workflow-1",
        ),
    )
    receipt = store.list_consent_receipts(OWNER)[0]
    with pytest.raises(ValidationError):
        receipt.action = "candidate_confirmation"


def test_direct_enable_distinguishes_requested_granted_and_effective_scope() -> None:
    store = InMemoryCanonicalMemoryStore()
    service = _service(store, ("receipt-first", "receipt-expanded"))
    workflow = frozenset({MemoryCategory.WORKFLOW_PREFERENCE})
    expanded = workflow | frozenset({MemoryCategory.PAST_SESSION_ANCHOR})

    service.enable(SUBJECT, workflow, idempotency_key="enable-workflow")
    service.enable(SUBJECT, expanded, idempotency_key="expand-workflow")

    receipt = store.list_consent_receipts(OWNER)[1]
    assert receipt.requested_scope == expanded
    assert receipt.granted_scope == frozenset({MemoryCategory.PAST_SESSION_ANCHOR})
    assert receipt.effective_scope == expanded


def test_direct_enable_collision_rolls_back_settings_and_receipt() -> None:
    store = InMemoryCanonicalMemoryStore()
    service = _service(store, ("receipt-shared", "receipt-shared"))
    service.enable(
        SUBJECT,
        frozenset({MemoryCategory.WORKFLOW_PREFERENCE}),
        idempotency_key="enable-workflow",
    )
    first_receipts = store.list_consent_receipts(OWNER)
    assert service.disable(SUBJECT).changed is True

    with pytest.raises(ValueError, match="consent receipt id already exists"):
        service.enable(
            SUBJECT,
            frozenset({MemoryCategory.PERSONALIZATION_PREFERENCE}),
            idempotency_key="enable-personalization",
        )

    assert store.get_settings(OWNER) == MemoryConsentSettings()
    assert store.list_consent_receipts(OWNER) == first_receipts


def test_confirmation_records_exact_scope_and_receipt_lifecycle() -> None:
    store = InMemoryCanonicalMemoryStore()
    service = _service(store, ("candidate-1", "receipt-1", "record-1"))
    proposal = _propose(service)

    result = service.confirm(
        SUBJECT,
        proposal.candidate.id,
        sensitivity=_clear(),
        context=MemoryOperationContext.ORDINARY,
    )

    assert result.created is True
    assert result.record is not None
    assert result.consent_receipt is not None
    receipt = result.consent_receipt
    assert receipt.action == "candidate_confirmation"
    assert receipt.requested_scope == SAVED_DECISION_SCOPE
    assert receipt.granted_scope == SAVED_DECISION_SCOPE
    assert receipt.effective_scope == SAVED_DECISION_SCOPE
    assert receipt.candidate_id == proposal.candidate.id
    assert receipt.idempotency_key == proposal.candidate.id
    assert receipt.policy_version == "argus.memory-policy/v1"
    assert receipt.recorded_at == NOW
    assert result.record.revision == 1
    assert result.record.updated_at == NOW

    service.delete(SUBJECT, result.record.id)
    assert store.list_consent_receipts(OWNER) == (receipt,)
    service.disable(SUBJECT)
    assert store.list_consent_receipts(OWNER) == (receipt,)
    service.reset(SUBJECT)
    assert store.list_consent_receipts(OWNER) == ()


def test_confirmation_with_effective_consent_records_no_scope_grant() -> None:
    store = InMemoryCanonicalMemoryStore()
    service = _service(
        store,
        ("receipt-enable", "candidate-1", "receipt-confirm", "record-1"),
    )
    effective = frozenset({MemoryCategory.EXPLICIT_DECISION_NOTE})
    service.enable(SUBJECT, effective, idempotency_key="enable-decisions")
    proposal = _propose(service)
    assert proposal.candidate.opt_in_scope == frozenset()

    result = service.confirm(
        SUBJECT,
        proposal.candidate.id,
        sensitivity=_clear(),
        context=MemoryOperationContext.ORDINARY,
    )

    assert result.consent_receipt is not None
    assert result.consent_receipt.requested_scope == frozenset()
    assert result.consent_receipt.granted_scope == frozenset()
    assert result.consent_receipt.effective_scope == effective


def test_candidate_sensitivity_is_content_bound_and_revalidated() -> None:
    store = InMemoryCanonicalMemoryStore()
    service = _service(store, ("candidate-1", "receipt-1", "record-1"))
    proposal = _propose(service)
    candidate = proposal.candidate

    digest = memory_candidate_content_digest(
        category=candidate.category,
        label=candidate.source.label,
        value=candidate.source.value,
        future_benefit=candidate.future_benefit,
    )
    assert candidate.sensitivity.policy_version == "argus.memory-sensitivity/v1"
    assert candidate.sensitivity.content_digest == digest

    rejected = service.confirm(
        SUBJECT,
        candidate.id,
        sensitivity=_clear(content_digest=f"sha256:{'0' * 64}"),
        context=MemoryOperationContext.ORDINARY,
    )

    assert rejected.created is False
    assert store.get_candidate(OWNER, candidate.id) == candidate
    assert store.list_consent_receipts(OWNER) == ()
    assert store.list_records(OWNER) == ()


def test_candidate_content_is_bounded_and_primary_provenance_must_match() -> None:
    source = _source()

    with pytest.raises(ValidationError):
        MemoryCandidateDraft(
            category=MemoryCategory.EXPLICIT_DECISION_NOTE,
            value="v" * (MAX_MEMORY_VALUE_LENGTH + 1),
            label=source.label,
            future_benefit="Useful later.",
            provenance=(source.provenance,),
            trigger=MemoryProposalTrigger.EXPLICIT_REQUEST,
            sensitivity=_clear(),
        )
    with pytest.raises(ValidationError):
        MemoryCandidateDraft(
            category=MemoryCategory.EXPLICIT_DECISION_NOTE,
            value=source.value,
            label=source.label,
            future_benefit="b" * (MAX_MEMORY_FUTURE_BENEFIT_LENGTH + 1),
            provenance=(source.provenance,),
            trigger=MemoryProposalTrigger.EXPLICIT_REQUEST,
            sensitivity=_clear(),
        )

    store = InMemoryCanonicalMemoryStore()
    proposal = _propose(_service(store, ("candidate-1",)))
    alternate = MemoryProvenance(
        source_kind=MemorySourceKind.DECISION_NOTE,
        source_id="another-note",
        source_version="1",
    )
    candidate_values = proposal.candidate.model_dump()
    candidate_values["provenance_refs"] = (alternate,)
    with pytest.raises(ValidationError, match="primary provenance"):
        MemoryCandidate.model_validate(candidate_values)


def test_edit_advances_revision_and_preserves_canonical_identity() -> None:
    store = InMemoryCanonicalMemoryStore()
    setup = _service(store, ("candidate-1", "receipt-1", "record-1"))
    proposal = _propose(setup)
    confirmation = setup.confirm(
        SUBJECT,
        proposal.candidate.id,
        sensitivity=_clear(),
        context=MemoryOperationContext.ORDINARY,
    )
    assert confirmation.record is not None
    original = confirmation.record

    edited_result = _service(store, (), now=LATER).edit(
        SUBJECT,
        original.id,
        MemoryEdit(label="Updated label", sensitivity=_clear()),
    )

    assert edited_result.record is not None
    edited = edited_result.record
    assert edited.label == "Updated label"
    assert edited.revision == original.revision + 1
    assert edited.updated_at == LATER
    for field_name in (
        "id",
        "owner_id",
        "candidate_id",
        "category",
        "value",
        "provenance",
        "provenance_refs",
        "consent_receipt",
        "created_at",
    ):
        assert getattr(edited, field_name) == getattr(original, field_name)


def test_default_category_allowlist_is_literal_and_closed() -> None:
    assert SAFE_MEMORY_CATEGORIES == frozenset(
        {
            MemoryCategory.PERSONALIZATION_PREFERENCE,
            MemoryCategory.WORKFLOW_PREFERENCE,
            MemoryCategory.EXPLICIT_DECISION_NOTE,
            MemoryCategory.PAST_SESSION_ANCHOR,
        }
    )
