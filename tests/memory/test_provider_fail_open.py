from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone

import pytest
from argus.memory.contracts import (
    MemoryCandidateDraft,
    MemoryCategory,
    MemoryOperationContext,
    MemoryProposalTrigger,
    MemoryProvenance,
    MemoryRecord,
    MemorySelectionReason,
    MemorySourceKind,
    MemoryUsePurpose,
    SensitivityAssessment,
    SensitivityStatus,
)
from argus.memory.provider import (
    MemoryRetrievalProvider,
    ProviderCleanupResult,
    ProviderHit,
    ProviderProjectionResult,
    ProviderReconciliationStatus,
    ProviderSearchResult,
    ProviderSearchStatus,
)
from argus.memory.service import MemoryService, MemoryServiceConfig
from argus.memory.store import InMemoryCanonicalMemoryStore
from argus.memory.subject import MemoryAccountKind, MemorySubject, RegisteredMemoryOwner

NOW = datetime(2026, 7, 29, 19, 0, tzinfo=timezone.utc)
OWNER_ID = "d5aa6db5-2cae-4e9a-b254-eb98e25bdd38"
SUBJECT = MemorySubject(owner_id=OWNER_ID, kind=MemoryAccountKind.REGISTERED)
CLEAR = SensitivityAssessment(status=SensitivityStatus.CLEAR)


def _ids() -> Iterator[str]:
    index = 0
    while True:
        index += 1
        yield f"generated-{index:03d}"


class _ProviderBase(MemoryRetrievalProvider):
    def project(
        self,
        owner: RegisteredMemoryOwner,
        record: MemoryRecord,
    ) -> ProviderProjectionResult:
        del owner, record
        return ProviderProjectionResult(
            status=ProviderReconciliationStatus.NOT_APPLICABLE
        )

    def search(
        self,
        owner: RegisteredMemoryOwner,
        query: str,
        limit: int,
    ) -> ProviderSearchResult:
        del owner, query, limit
        return ProviderSearchResult(status=ProviderSearchStatus.UNAVAILABLE)

    def delete(
        self,
        owner: RegisteredMemoryOwner,
        provider_ref: str,
    ) -> ProviderCleanupResult:
        del owner, provider_ref
        return ProviderCleanupResult(status=ProviderReconciliationStatus.NOT_APPLICABLE)

    def reset(self, owner: RegisteredMemoryOwner) -> ProviderCleanupResult:
        del owner
        return ProviderCleanupResult(status=ProviderReconciliationStatus.NOT_APPLICABLE)


class _AnsweredEmptyProvider(_ProviderBase):
    def search(
        self,
        owner: RegisteredMemoryOwner,
        query: str,
        limit: int,
    ) -> ProviderSearchResult:
        del owner, query, limit
        return ProviderSearchResult(
            status=ProviderSearchStatus.ANSWERED,
            hits=(),
        )


class _ExplodingSearchProvider(_ProviderBase):
    def search(
        self,
        owner: RegisteredMemoryOwner,
        query: str,
        limit: int,
    ) -> ProviderSearchResult:
        del owner, query, limit
        raise RuntimeError("secret provider diagnostic")


class _ExplodingProjectionProvider(_ProviderBase):
    def project(
        self,
        owner: RegisteredMemoryOwner,
        record: MemoryRecord,
    ) -> ProviderProjectionResult:
        del owner, record
        raise RuntimeError("secret projection diagnostic")


class _NoneProjectionProvider(_ProviderBase):
    def project(  # type: ignore[override]
        self,
        owner: RegisteredMemoryOwner,
        record: MemoryRecord,
    ) -> None:
        del owner, record
        return None


class _InvalidProjectionProvider(_ProviderBase):
    def project(  # type: ignore[override]
        self,
        owner: RegisteredMemoryOwner,
        record: MemoryRecord,
    ) -> object:
        del owner, record
        return {"status": "synchronized"}


class _CanonicalFirstProjectionProvider(_ProviderBase):
    def __init__(self, store: InMemoryCanonicalMemoryStore) -> None:
        self._store = store
        self.observed_canonical_record = False

    def project(
        self,
        owner: RegisteredMemoryOwner,
        record: MemoryRecord,
    ) -> ProviderProjectionResult:
        self.observed_canonical_record = (
            self._store.get_record(owner, record.id) == record
        )
        return ProviderProjectionResult(
            status=ProviderReconciliationStatus.SYNCHRONIZED,
            provider_ref="projection-1",
        )


class _ResetOutcomeProvider(_ProviderBase):
    def __init__(self, outcome: object) -> None:
        self.outcome = outcome
        self.calls: list[RegisteredMemoryOwner] = []

    def reset(self, owner: RegisteredMemoryOwner) -> ProviderCleanupResult:
        self.calls.append(owner)
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome  # type: ignore[return-value]


def _service(
    store: InMemoryCanonicalMemoryStore,
    provider: MemoryRetrievalProvider | None = None,
) -> MemoryService:
    generated_ids = _ids()
    return MemoryService(
        store=store,
        provider=provider,
        config=MemoryServiceConfig(available=True),
        clock=lambda: NOW,
        id_factory=lambda: next(generated_ids),
    )


def _confirm_one(
    service: MemoryService,
    *,
    label: str = "Lower drawdown choice",
    value: str = "Keep the lower drawdown choice for later comparison.",
) -> str:
    proposal = service.propose(
        SUBJECT,
        MemoryCandidateDraft(
            category=MemoryCategory.EXPLICIT_DECISION_NOTE,
            value=value,
            label=label,
            future_benefit="Argus can revisit the confirmed choice later.",
            provenance=(
                MemoryProvenance(
                    source_kind=MemorySourceKind.DECISION_NOTE,
                    source_id="decision-provider-test",
                    source_version="1",
                ),
            ),
            trigger=MemoryProposalTrigger.EXPLICIT_REQUEST,
            sensitivity=CLEAR,
        ),
        MemoryOperationContext.ORDINARY,
    )
    assert proposal is not None
    confirmation = service.confirm(
        SUBJECT,
        proposal.candidate.id,
        sensitivity=CLEAR,
        context=MemoryOperationContext.ORDINARY,
    )
    assert confirmation.created is True
    assert confirmation.record is not None
    return confirmation.record.id


@pytest.mark.parametrize(
    "provider",
    (_ProviderBase(), _ExplodingSearchProvider()),
)
def test_unavailable_or_failed_search_uses_bounded_canonical_fallback(
    provider: MemoryRetrievalProvider,
) -> None:
    """Catches provider failure breaking retrieval instead of safe canonical fallback."""
    store = InMemoryCanonicalMemoryStore()
    setup_service = _service(store)
    record_id = _confirm_one(setup_service)
    service = _service(store, provider)

    retrieved = service.retrieve(
        SUBJECT,
        "lower drawdown",
        MemoryUsePurpose.REVISIT_SAVED_DECISION,
    )

    assert [item.record.id for item in retrieved] == [record_id]
    assert retrieved[0].selection_reason is MemorySelectionReason.CANONICAL_TOKEN_MATCH


def test_answered_empty_is_definitive_when_the_index_covers_the_records() -> None:
    """Catches a valid empty provider answer being replaced by canonical matches."""
    store = InMemoryCanonicalMemoryStore()
    # A claimed projection; attaching a ref out of band would prove nothing.
    record_id = _confirm_one(_service(store, _CanonicalFirstProjectionProvider(store)))
    owner = RegisteredMemoryOwner(owner_id=OWNER_ID)
    assert store.get_provider_ref(owner, record_id) is not None
    assert record_id in store.settled_projection_record_ids(owner)
    service = _service(store, _AnsweredEmptyProvider())

    assert (
        service.retrieve(
            SUBJECT,
            "lower drawdown",
            MemoryUsePurpose.REVISIT_SAVED_DECISION,
        )
        == ()
    )


def test_answered_empty_is_not_definitive_for_records_the_index_lacks() -> None:
    """Catches an empty answer burying memories that were never projected."""
    store = InMemoryCanonicalMemoryStore()
    record_id = _confirm_one(_service(store))
    service = _service(store, _AnsweredEmptyProvider())

    retrieved = service.retrieve(
        SUBJECT,
        "lower drawdown",
        MemoryUsePurpose.REVISIT_SAVED_DECISION,
    )

    assert [item.record.id for item in retrieved] == [record_id]
    assert retrieved[0].selection_reason is MemorySelectionReason.CANONICAL_TOKEN_MATCH


@pytest.mark.parametrize(
    "provider",
    (
        _ExplodingProjectionProvider(),
        _NoneProjectionProvider(),
        _InvalidProjectionProvider(),
    ),
)
def test_projection_failure_never_rolls_back_or_exposes_canonical_confirmation(
    provider: MemoryRetrievalProvider,
) -> None:
    """Catches derivative projection failure undoing a confirmed canonical record."""
    store = InMemoryCanonicalMemoryStore()
    service = _service(store, provider)

    record_id = _confirm_one(service)

    owner = RegisteredMemoryOwner(owner_id=OWNER_ID)
    assert store.get_record(owner, record_id) is not None
    assert store.get_provider_ref(owner, record_id) is None
    assert store.inflight_reconciliation_generations(owner, record_id) == ()


def test_projection_runs_after_canonical_confirmation_and_retains_only_its_ref() -> None:
    """Catches provider projection preceding truth or replacing canonical record data."""
    store = InMemoryCanonicalMemoryStore()
    provider = _CanonicalFirstProjectionProvider(store)
    service = _service(store, provider)

    record_id = _confirm_one(service)

    owner = RegisteredMemoryOwner(owner_id=OWNER_ID)
    record = store.get_record(owner, record_id)
    assert provider.observed_canonical_record is True
    assert record is not None
    assert record.label == "Lower drawdown choice"
    assert record.value == "Keep the lower drawdown choice for later comparison."
    assert store.get_provider_ref(owner, record_id) == "projection-1"


def test_unavailable_search_result_cannot_smuggle_hits() -> None:
    """Catches an unavailable provider response carrying untrusted ranked ids."""
    with pytest.raises(ValueError, match="unavailable search cannot include hits"):
        ProviderSearchResult(
            status=ProviderSearchStatus.UNAVAILABLE,
            hits=(ProviderHit(record_id="smuggled", score=1.0),),
        )


def test_provider_reconciliation_models_reject_unknown_statuses() -> None:
    """Catches untyped provider outcomes being treated as successful cleanup."""
    with pytest.raises(ValueError):
        ProviderCleanupResult(status="maybe")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        ProviderProjectionResult(status="maybe")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("outcome", "expected"),
    (
        (
            RuntimeError("secret owner reset diagnostic"),
            ProviderReconciliationStatus.RECONCILIATION_REQUIRED,
        ),
        (None, ProviderReconciliationStatus.RECONCILIATION_REQUIRED),
        (
            {"unexpected": "shape"},
            ProviderReconciliationStatus.RECONCILIATION_REQUIRED,
        ),
        (
            ProviderCleanupResult(
                status=ProviderReconciliationStatus.RECONCILIATION_REQUIRED
            ),
            ProviderReconciliationStatus.RECONCILIATION_REQUIRED,
        ),
        (
            ProviderCleanupResult(status=ProviderReconciliationStatus.NOT_APPLICABLE),
            ProviderReconciliationStatus.RECONCILIATION_REQUIRED,
        ),
        (
            ProviderCleanupResult(status=ProviderReconciliationStatus.SYNCHRONIZED),
            ProviderReconciliationStatus.SYNCHRONIZED,
        ),
    ),
)
def test_reset_provider_outcome_is_fail_open_and_truthful(
    outcome: object,
    expected: ProviderReconciliationStatus,
) -> None:
    """Catches provider reset failures escaping or restoring canonical memory."""
    store = InMemoryCanonicalMemoryStore()
    setup = _service(store)
    record_id = _confirm_one(setup)
    owner = RegisteredMemoryOwner(owner_id=OWNER_ID)
    assert store.set_provider_ref(owner, record_id, "provider-reset-outcome")
    provider = _ResetOutcomeProvider(outcome)
    service = _service(store, provider)

    result = service.reset(SUBJECT)

    assert result.changed is True
    assert result.provider_status is expected
    assert provider.calls == [owner]
    assert store.get_settings(owner).enabled is False
    assert store.list_candidates(owner) == ()
    assert store.list_consent_receipts(owner) == ()
    assert store.get_record(owner, record_id) is None
    assert store.get_provider_ref(owner, record_id) is None
    if expected is ProviderReconciliationStatus.SYNCHRONIZED:
        assert store.list_provider_cleanup_targets(owner) == ()
    else:
        assert store.list_provider_cleanup_targets(owner) != ()
