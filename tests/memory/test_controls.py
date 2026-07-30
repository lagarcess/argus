from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Event, Lock
from typing import Any

import pytest
from argus.memory.contracts import (
    MemoryCandidateDraft,
    MemoryCategory,
    MemoryConsentSettings,
    MemoryControlResult,
    MemoryEdit,
    MemoryOperationContext,
    MemoryProposalTrigger,
    MemoryProvenance,
    MemoryRecord,
    MemorySensitivityFlag,
    MemorySourceKind,
    MemoryUsePurpose,
    SavedDecisionSource,
    SensitivityAssessment,
    SensitivityStatus,
)
from argus.memory.provider import (
    MemoryRetrievalProvider,
    ProviderCleanupResult,
    ProviderProjectionResult,
    ProviderReconciliationStatus,
    ProviderSearchResult,
    ProviderSearchStatus,
)
from argus.memory.service import MemoryService, MemoryServiceConfig
from argus.memory.store import InMemoryCanonicalMemoryStore, ReconciliationClaim
from argus.memory.subject import MemoryAccountKind, MemorySubject, RegisteredMemoryOwner
from pydantic import ValidationError

NOW = datetime(2026, 7, 29, 20, 0, tzinfo=timezone.utc)
OWNER_ID = "663b52b0-ac1c-4df4-bc6d-b1d211e27be7"
OTHER_OWNER_ID = "8e388f5d-b0e7-4575-9a90-9042f0fbc355"
SUBJECT = MemorySubject(owner_id=OWNER_ID, kind=MemoryAccountKind.REGISTERED)
OTHER_SUBJECT = MemorySubject(
    owner_id=OTHER_OWNER_ID,
    kind=MemoryAccountKind.REGISTERED,
)
OWNER = RegisteredMemoryOwner(owner_id=OWNER_ID)
CLEAR = SensitivityAssessment(status=SensitivityStatus.CLEAR)


def _ids() -> Iterator[str]:
    index = 0
    while True:
        index += 1
        yield f"control-{index:03d}"


class _ProviderSpy(MemoryRetrievalProvider):
    def __init__(
        self,
        *,
        projection: object = ProviderProjectionResult(
            status=ProviderReconciliationStatus.NOT_APPLICABLE
        ),
        cleanup: object = ProviderCleanupResult(
            status=ProviderReconciliationStatus.NOT_APPLICABLE
        ),
        reset: object = ProviderCleanupResult(
            status=ProviderReconciliationStatus.NOT_APPLICABLE
        ),
        store: InMemoryCanonicalMemoryStore | None = None,
    ) -> None:
        self.projection = projection
        self.cleanup = cleanup
        self.reset_outcome = reset
        self.store = store
        self.project_calls: list[tuple[RegisteredMemoryOwner, MemoryRecord]] = []
        self.delete_calls: list[tuple[RegisteredMemoryOwner, str]] = []
        self.reset_calls: list[RegisteredMemoryOwner] = []
        self.project_observed_canonical = False
        self.delete_observed_canonical_absent = False
        self.reset_observed_canonical_empty = False

    def project(
        self,
        owner: RegisteredMemoryOwner,
        record: MemoryRecord,
    ) -> ProviderProjectionResult:
        self.project_calls.append((owner, record))
        if self.store is not None:
            self.project_observed_canonical = (
                self.store.get_record(owner, record.id) == record
            )
        if isinstance(self.projection, BaseException):
            raise self.projection
        return self.projection  # type: ignore[return-value]

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
        self.delete_calls.append((owner, provider_ref))
        if self.store is not None:
            self.delete_observed_canonical_absent = (
                self.store.get_record(owner, self._record_id_for_ref(provider_ref))
                is None
                and self.store.get_provider_ref(
                    owner,
                    self._record_id_for_ref(provider_ref),
                )
                is None
            )
        if isinstance(self.cleanup, BaseException):
            raise self.cleanup
        return self.cleanup  # type: ignore[return-value]

    def reset(self, owner: RegisteredMemoryOwner) -> ProviderCleanupResult:
        self.reset_calls.append(owner)
        if self.store is not None:
            self.reset_observed_canonical_empty = (
                self.store.get_settings(owner) == MemoryConsentSettings()
                and self.store.list_candidates(owner) == ()
                and self.store.list_consent_receipts(owner) == ()
                and self.store.list_records(owner) == ()
                and self.store.list_provider_cleanup_targets(owner) == ()
            )
        if isinstance(self.reset_outcome, BaseException):
            raise self.reset_outcome
        return self.reset_outcome  # type: ignore[return-value]

    def _record_id_for_ref(self, provider_ref: str) -> str:
        assert self.store is not None
        for record in self.store.list_records(OWNER):
            if self.store.get_provider_ref(OWNER, record.id) == provider_ref:
                return record.id
        return "control-003"


class _BlockingStatefulProvider(_ProviderSpy):
    def __init__(self, *, new_ref_cleanup: object) -> None:
        super().__init__()
        self.project_started = Event()
        self.allow_project = Event()
        self.delete_called = Event()
        self.refs = {"projection-old"}
        self._refs_lock = Lock()
        self._new_ref_cleanup = new_ref_cleanup

    def project(
        self,
        owner: RegisteredMemoryOwner,
        record: MemoryRecord,
    ) -> ProviderProjectionResult:
        del owner, record
        self.project_started.set()
        if not self.allow_project.wait(timeout=5):
            raise TimeoutError("test did not release provider projection")
        with self._refs_lock:
            self.refs.add("projection-new")
        return ProviderProjectionResult(
            status=ProviderReconciliationStatus.SYNCHRONIZED,
            provider_ref="projection-new",
        )

    def delete(
        self,
        owner: RegisteredMemoryOwner,
        provider_ref: str,
    ) -> ProviderCleanupResult:
        del owner
        self.delete_calls.append((OWNER, provider_ref))
        self.delete_called.set()
        outcome: object
        if provider_ref == "projection-new":
            outcome = self._new_ref_cleanup
        else:
            outcome = ProviderCleanupResult(
                status=ProviderReconciliationStatus.SYNCHRONIZED
            )
        if isinstance(outcome, BaseException):
            raise outcome
        if (
            isinstance(outcome, ProviderCleanupResult)
            and outcome.status is ProviderReconciliationStatus.SYNCHRONIZED
        ):
            with self._refs_lock:
                self.refs.discard(provider_ref)
        return outcome  # type: ignore[return-value]


class _SameRefOutOfOrderProvider(_ProviderSpy):
    def __init__(self) -> None:
        super().__init__()
        self.first_started = Event()
        self.allow_first = Event()
        self.second_started = Event()
        self.refs: set[str] = set()
        self._refs_lock = Lock()

    def project(
        self,
        owner: RegisteredMemoryOwner,
        record: MemoryRecord,
    ) -> ProviderProjectionResult:
        del owner
        if record.value == "First concurrent edit.":
            self.first_started.set()
            if not self.allow_first.wait(timeout=5):
                raise TimeoutError("test did not release first edit projection")
        elif record.value == "Second concurrent edit.":
            self.second_started.set()
        with self._refs_lock:
            self.refs.add("shared-update-ref")
        return ProviderProjectionResult(
            status=ProviderReconciliationStatus.SYNCHRONIZED,
            provider_ref="shared-update-ref",
        )

    def delete(
        self,
        owner: RegisteredMemoryOwner,
        provider_ref: str,
    ) -> ProviderCleanupResult:
        del owner
        with self._refs_lock:
            self.refs.discard(provider_ref)
        return ProviderCleanupResult(status=ProviderReconciliationStatus.SYNCHRONIZED)


class _DistinctRefFailureProvider(_SameRefOutOfOrderProvider):
    def project(
        self,
        owner: RegisteredMemoryOwner,
        record: MemoryRecord,
    ) -> ProviderProjectionResult:
        del owner
        if record.value == "First concurrent edit.":
            self.first_started.set()
            if not self.allow_first.wait(timeout=5):
                raise TimeoutError("test did not release first edit projection")
            provider_ref = "loser-distinct-ref"
        else:
            self.second_started.set()
            provider_ref = "winner-distinct-ref"
        with self._refs_lock:
            self.refs.add(provider_ref)
        return ProviderProjectionResult(
            status=ProviderReconciliationStatus.SYNCHRONIZED,
            provider_ref=provider_ref,
        )

    def delete(
        self,
        owner: RegisteredMemoryOwner,
        provider_ref: str,
    ) -> ProviderCleanupResult:
        del owner
        if provider_ref == "loser-distinct-ref":
            return ProviderCleanupResult(
                status=ProviderReconciliationStatus.RECONCILIATION_REQUIRED
            )
        with self._refs_lock:
            self.refs.discard(provider_ref)
        return ProviderCleanupResult(status=ProviderReconciliationStatus.SYNCHRONIZED)


class _CrossOwnerBlockingProvider(_ProviderSpy):
    def __init__(self) -> None:
        super().__init__()
        self.first_owner_started = Event()
        self.allow_first_owner = Event()
        self.second_owner_started = Event()

    def project(
        self,
        owner: RegisteredMemoryOwner,
        record: MemoryRecord,
    ) -> ProviderProjectionResult:
        del record
        if owner.owner_id == OWNER_ID:
            self.first_owner_started.set()
            if not self.allow_first_owner.wait(timeout=5):
                raise TimeoutError("test did not release first owner")
        else:
            self.second_owner_started.set()
        return ProviderProjectionResult(
            status=ProviderReconciliationStatus.SYNCHRONIZED,
            provider_ref=f"projection-{owner.owner_id}",
        )


class _ResetAwareBlockingProvider(_BlockingStatefulProvider):
    def __init__(self) -> None:
        super().__init__(
            new_ref_cleanup=ProviderCleanupResult(
                status=ProviderReconciliationStatus.SYNCHRONIZED
            )
        )
        self.reset_called = Event()

    def reset(self, owner: RegisteredMemoryOwner) -> ProviderCleanupResult:
        del owner
        with self._refs_lock:
            self.refs.clear()
        self.reset_called.set()
        return ProviderCleanupResult(status=ProviderReconciliationStatus.SYNCHRONIZED)


class _BlockingDeleteProvider(_ProviderSpy):
    def __init__(self) -> None:
        super().__init__()
        self.delete_started = Event()
        self.allow_delete = Event()
        self.reset_called = Event()
        self.refs = {"projection-delete"}

    def delete(
        self,
        owner: RegisteredMemoryOwner,
        provider_ref: str,
    ) -> ProviderCleanupResult:
        del owner
        self.delete_started.set()
        if not self.allow_delete.wait(timeout=5):
            raise TimeoutError("test did not release provider delete")
        self.refs.discard(provider_ref)
        return ProviderCleanupResult(status=ProviderReconciliationStatus.SYNCHRONIZED)

    def reset(self, owner: RegisteredMemoryOwner) -> ProviderCleanupResult:
        del owner
        self.refs.clear()
        self.reset_called.set()
        return ProviderCleanupResult(status=ProviderReconciliationStatus.SYNCHRONIZED)


class _BlockingConfirmationResetProvider(_ProviderSpy):
    def __init__(self) -> None:
        super().__init__()
        self.project_started = Event()
        self.allow_project = Event()
        self.reset_called = Event()
        self.refs: set[str] = set()

    def project(
        self,
        owner: RegisteredMemoryOwner,
        record: MemoryRecord,
    ) -> ProviderProjectionResult:
        del owner, record
        self.project_started.set()
        if not self.allow_project.wait(timeout=5):
            raise TimeoutError("test did not release confirmation projection")
        self.refs.add("projection-confirmed")
        return ProviderProjectionResult(
            status=ProviderReconciliationStatus.SYNCHRONIZED,
            provider_ref="projection-confirmed",
        )

    def delete(
        self,
        owner: RegisteredMemoryOwner,
        provider_ref: str,
    ) -> ProviderCleanupResult:
        del owner
        self.refs.discard(provider_ref)
        return ProviderCleanupResult(status=ProviderReconciliationStatus.SYNCHRONIZED)

    def reset(self, owner: RegisteredMemoryOwner) -> ProviderCleanupResult:
        del owner
        self.refs.clear()
        self.reset_called.set()
        return ProviderCleanupResult(status=ProviderReconciliationStatus.SYNCHRONIZED)


class _NoClaimStore(InMemoryCanonicalMemoryStore):
    def claim_reconciliation_turn(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str,
        reconciliation_generation: int,
    ) -> ReconciliationClaim | None:
        del owner, record_id, reconciliation_generation
        return None


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
    subject: MemorySubject = SUBJECT,
    label: str = "Lower drawdown choice",
    value: str = "Keep the lower drawdown choice for later comparison.",
) -> MemoryRecord:
    proposal = service.propose(
        subject,
        MemoryCandidateDraft(
            category=MemoryCategory.EXPLICIT_DECISION_NOTE,
            value=value,
            label=label,
            future_benefit="Argus can revisit the confirmed choice later.",
            provenance=(
                MemoryProvenance(
                    source_kind=MemorySourceKind.DECISION_NOTE,
                    source_id=f"decision-{subject.owner_id}",
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
        subject,
        proposal.candidate.id,
        sensitivity=CLEAR,
        context=MemoryOperationContext.ORDINARY,
    )
    assert confirmation.created is True
    assert confirmation.record is not None
    return confirmation.record


def test_provider_is_not_called_without_an_exact_reconciliation_claim() -> None:
    store = _NoClaimStore()
    provider = _ProviderSpy()
    service = _service(store, provider)

    record = _confirm_one(service)

    assert store.get_record(OWNER, record.id) == record
    assert provider.project_calls == []
    assert provider.delete_calls == []


def test_reused_provider_ref_is_never_deleted_for_a_different_record() -> None:
    """Catches failed projection cleanup deleting another record's live ref."""
    store = InMemoryCanonicalMemoryStore()
    provider = _ProviderSpy(
        projection=ProviderProjectionResult(
            status=ProviderReconciliationStatus.SYNCHRONIZED,
            provider_ref="provider-reused",
        ),
        cleanup=ProviderCleanupResult(status=ProviderReconciliationStatus.SYNCHRONIZED),
    )
    service = _service(store, provider)
    first = _confirm_one(service, label="First", value="First decision.")

    second = _confirm_one(service, label="Second", value="Second decision.")

    assert store.get_provider_ref(OWNER, first.id) == "provider-reused"
    assert store.get_provider_ref(OWNER, second.id) is None
    assert provider.delete_calls == []


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("owner_id", OTHER_OWNER_ID),
        ("category", MemoryCategory.WORKFLOW_PREFERENCE),
        ("provenance", ()),
        ("consent_receipt", None),
        ("created_at", NOW),
        ("record_id", "replacement-id"),
    ),
)
def test_edit_contract_forbids_canonical_identity_and_evidence_fields(
    field: str,
    value: object,
) -> None:
    """Catches permissive edit inputs that can overwrite canonical ownership."""
    payload: dict[str, Any] = {
        "label": "Updated label",
        "sensitivity": CLEAR,
        field: value,
    }

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        MemoryEdit.model_validate(payload)


def test_edit_requires_current_typed_sensitivity_and_one_nonblank_change() -> None:
    """Catches stale/default sensitivity and empty edit payloads reaching storage."""
    with pytest.raises(ValidationError):
        MemoryEdit(label="Updated label")  # type: ignore[call-arg]
    with pytest.raises(ValidationError, match="edit requires"):
        MemoryEdit(sensitivity=CLEAR)
    with pytest.raises(ValidationError, match="must not be blank"):
        MemoryEdit(label="   ", sensitivity=CLEAR)
    with pytest.raises(ValidationError, match="must not be blank"):
        MemoryEdit(value="\t", sensitivity=CLEAR)


@pytest.mark.parametrize(
    "sensitivity",
    (
        SensitivityAssessment(),
        SensitivityAssessment(
            status=SensitivityStatus.RESTRICTED,
            flags=frozenset({MemorySensitivityFlag.ACCOUNT_BALANCE}),
        ),
    ),
)
def test_unassessed_or_sensitive_edit_is_atomic_before_provider(
    sensitivity: SensitivityAssessment,
) -> None:
    """Catches a fail-open sensitivity check mutating truth or derivative state."""
    store = InMemoryCanonicalMemoryStore()
    setup = _service(store)
    original = _confirm_one(setup)
    provider = _ProviderSpy(
        projection=ProviderProjectionResult(
            status=ProviderReconciliationStatus.SYNCHRONIZED,
            provider_ref="provider-updated",
        )
    )
    service = _service(store, provider)

    with pytest.raises(ValueError, match="clear sensitivity"):
        service.edit(
            SUBJECT,
            original.id,
            MemoryEdit(label="Unsafe update", sensitivity=sensitivity),
        )

    assert store.get_record(OWNER, original.id) == original
    assert provider.project_calls == []
    assert provider.delete_calls == []


def test_disabled_owner_can_inspect_explain_and_edit_without_reenabling() -> None:
    """Catches Data Controls becoming inaccessible after memory is disabled."""
    store = InMemoryCanonicalMemoryStore()
    setup = _service(store)
    original = _confirm_one(setup)
    store.set_settings(OWNER, MemoryConsentSettings())
    service = _service(store)

    result = service.edit(
        SUBJECT,
        original.id,
        MemoryEdit(label="My lower drawdown choice", sensitivity=CLEAR),
    )

    assert result.changed is True
    assert result.record is not None
    assert result.record.label == "My lower drawdown choice"
    assert result.provider_status is ProviderReconciliationStatus.NOT_APPLICABLE
    assert service.inspect(SUBJECT) == (result.record,)
    explanation = service.explain(SUBJECT, original.id)
    assert explanation is not None
    assert explanation.provenance == original.provenance_refs
    assert store.get_settings(OWNER) == MemoryConsentSettings()


def test_edit_preserves_all_noneditable_canonical_fields() -> None:
    """Catches edit reconstruction that mutates provenance, consent, or identity."""
    store = InMemoryCanonicalMemoryStore()
    service = _service(store)
    original = _confirm_one(service)

    result = service.edit(
        SUBJECT,
        original.id,
        MemoryEdit(
            label="Revised label",
            value="Revised value.",
            sensitivity=CLEAR,
        ),
    )

    assert result.record is not None
    assert result.record.model_dump(
        exclude={"label", "revision", "updated_at", "value"},
    ) == original.model_dump(
        exclude={"label", "revision", "updated_at", "value"},
    )


def test_blank_or_unchanged_edit_leaves_canonical_and_provider_state_unchanged() -> None:
    """Catches no-op edits being projected or reported as a canonical change."""
    store = InMemoryCanonicalMemoryStore()
    setup = _service(store)
    original = _confirm_one(setup)
    store.set_provider_ref(OWNER, original.id, "provider-original")
    provider = _ProviderSpy()
    service = _service(store, provider)

    with pytest.raises(ValueError, match="must change"):
        service.edit(
            SUBJECT,
            original.id,
            MemoryEdit(label=original.label, sensitivity=CLEAR),
        )

    assert store.get_record(OWNER, original.id) == original
    assert store.get_provider_ref(OWNER, original.id) == "provider-original"
    assert provider.project_calls == []
    assert provider.delete_calls == []


def test_store_rolls_back_when_reconstructed_record_is_invalid() -> None:
    """Catches partial mutation when canonical record validation rejects an edit."""
    store = InMemoryCanonicalMemoryStore()
    service = _service(store)
    original = _confirm_one(service)

    with pytest.raises(ValidationError):
        store.edit_record(
            OWNER,
            original.id,
            label="x" * 121,
            value=None,
        )

    assert store.get_record(OWNER, original.id) == original


def test_concurrent_disjoint_edits_do_not_lose_an_owner_change() -> None:
    """Catches read-modify-write outside the owner-typed store lock."""
    store = InMemoryCanonicalMemoryStore()
    service = _service(store)
    original = _confirm_one(service)

    with ThreadPoolExecutor(max_workers=2) as executor:
        label_result = executor.submit(
            store.edit_record,
            OWNER,
            original.id,
            label="Concurrent label",
            value=None,
        )
        value_result = executor.submit(
            store.edit_record,
            OWNER,
            original.id,
            label=None,
            value="Concurrent value.",
        )
        mutations = (label_result.result(), value_result.result())

    for mutation in sorted(
        mutations,
        key=lambda item: (
            0
            if item is None or item.reconciliation_generation is None
            else item.reconciliation_generation
        ),
    ):
        assert mutation is not None
        assert mutation.reconciliation_generation is not None
        claim = store.claim_reconciliation_turn(
            OWNER,
            original.id,
            mutation.reconciliation_generation,
        )
        assert claim is not None
        assert store.finish_reconciliation_claim(
            OWNER,
            claim,
            succeeded=True,
            error_code=None,
            completed_at=NOW,
        )

    record = store.get_record(OWNER, original.id)
    assert record is not None
    assert record.label == "Concurrent label"
    assert record.value == "Concurrent value."


def test_edit_projects_only_after_canonical_commit_and_proves_synchronization() -> None:
    """Catches derivative projection preceding canonical truth."""
    store = InMemoryCanonicalMemoryStore()
    setup = _service(store)
    original = _confirm_one(setup)
    provider = _ProviderSpy(
        store=store,
        projection=ProviderProjectionResult(
            status=ProviderReconciliationStatus.SYNCHRONIZED,
            provider_ref="projection-edited",
        ),
    )
    service = _service(store, provider)

    result = service.edit(
        SUBJECT,
        original.id,
        MemoryEdit(value="Use the revised lower-drawdown choice.", sensitivity=CLEAR),
    )

    assert provider.project_observed_canonical is True
    assert result.changed is True
    assert result.record == store.get_record(OWNER, original.id)
    assert result.provider_status is ProviderReconciliationStatus.SYNCHRONIZED
    assert store.get_provider_ref(OWNER, original.id) == "projection-edited"


@pytest.mark.parametrize(
    "projection",
    (
        RuntimeError("secret reprojection failure"),
        None,
        {"status": "synchronized"},
        ProviderProjectionResult(
            status=ProviderReconciliationStatus.RECONCILIATION_REQUIRED
        ),
    ),
)
def test_edit_provider_failure_never_blocks_canonical_truth(
    projection: object,
) -> None:
    """Catches derivative errors escaping or rolling back a canonical edit."""
    store = InMemoryCanonicalMemoryStore()
    setup = _service(store)
    original = _confirm_one(setup)
    provider = _ProviderSpy(projection=projection)
    service = _service(store, provider)

    result = service.edit(
        SUBJECT,
        original.id,
        MemoryEdit(label="Canonical edit survives", sensitivity=CLEAR),
    )

    assert result.changed is True
    assert result.record == store.get_record(OWNER, original.id)
    assert result.record is not None
    assert result.record.label == "Canonical edit survives"
    assert result.provider_status is ProviderReconciliationStatus.RECONCILIATION_REQUIRED


def test_edit_cleans_replaced_projection_and_reports_stale_cleanup() -> None:
    """Catches a new projection hiding an old derivative copy that was not erased."""
    store = InMemoryCanonicalMemoryStore()
    setup = _service(store)
    original = _confirm_one(setup)
    store.set_provider_ref(OWNER, original.id, "projection-old")
    provider = _ProviderSpy(
        projection=ProviderProjectionResult(
            status=ProviderReconciliationStatus.SYNCHRONIZED,
            provider_ref="projection-new",
        ),
        cleanup=ProviderCleanupResult(
            status=ProviderReconciliationStatus.RECONCILIATION_REQUIRED
        ),
    )
    service = _service(store, provider)

    result = service.edit(
        SUBJECT,
        original.id,
        MemoryEdit(label="New canonical label", sensitivity=CLEAR),
    )

    assert provider.delete_calls == [(OWNER, "projection-old")]
    assert store.get_provider_ref(OWNER, original.id) == "projection-new"
    assert result.provider_status is ProviderReconciliationStatus.RECONCILIATION_REQUIRED


def test_edit_with_existing_projection_requires_proven_reprojection() -> None:
    """Catches NOT_APPLICABLE hiding a derivative copy made stale by an edit."""
    store = InMemoryCanonicalMemoryStore()
    setup = _service(store)
    original = _confirm_one(setup)
    store.set_provider_ref(OWNER, original.id, "projection-old")
    service = _service(store, _ProviderSpy())

    result = service.edit(
        SUBJECT,
        original.id,
        MemoryEdit(label="Canonical label changed", sensitivity=CLEAR),
    )

    assert result.provider_status is ProviderReconciliationStatus.RECONCILIATION_REQUIRED
    assert store.get_provider_ref(OWNER, original.id) == "projection-old"


def test_delete_waits_for_inflight_edit_and_cleans_its_projection() -> None:
    """Catches delete claiming success while a prior edit can create a late ref."""
    store = InMemoryCanonicalMemoryStore()
    setup = _service(store)
    original = _confirm_one(setup)
    store.set_provider_ref(OWNER, original.id, "projection-old")
    provider = _BlockingStatefulProvider(
        new_ref_cleanup=ProviderCleanupResult(
            status=ProviderReconciliationStatus.SYNCHRONIZED
        )
    )
    service = _service(store, provider)
    delete_entered = Event()
    delete_completed = Event()

    def _delete() -> MemoryControlResult:
        delete_entered.set()
        try:
            return service.delete(SUBJECT, original.id)
        finally:
            delete_completed.set()

    with ThreadPoolExecutor(max_workers=2) as executor:
        edit_future = executor.submit(
            service.edit,
            SUBJECT,
            original.id,
            MemoryEdit(value="First edit.", sensitivity=CLEAR),
        )
        assert provider.project_started.wait(timeout=1)
        delete_future = executor.submit(_delete)
        assert delete_entered.wait(timeout=1)
        delete_finished_before_projection = delete_completed.wait(timeout=0.1)
        provider.allow_project.set()
        edit_result = edit_future.result(timeout=2)
        delete_result = delete_future.result(timeout=2)

    assert delete_finished_before_projection is False
    assert edit_result.provider_status is ProviderReconciliationStatus.SYNCHRONIZED
    assert delete_result.provider_status is ProviderReconciliationStatus.SYNCHRONIZED
    assert store.get_record(OWNER, original.id) is None
    assert store.get_provider_ref(OWNER, original.id) is None
    assert store.list_provider_cleanup_targets(OWNER, original.id) == ()
    assert provider.refs == set()
    assert provider.delete_calls == [
        (OWNER, "projection-old"),
        (OWNER, "projection-new"),
    ]


@pytest.mark.parametrize(
    "new_ref_cleanup",
    (
        RuntimeError("secret late cleanup failure"),
        None,
        {"unexpected": "shape"},
        ProviderCleanupResult(
            status=ProviderReconciliationStatus.RECONCILIATION_REQUIRED
        ),
    ),
)
def test_failed_delete_of_inflight_edit_projection_retains_reconciliation_target(
    new_ref_cleanup: object,
) -> None:
    """Catches a failed late-ref cleanup becoming an untracked provider orphan."""
    store = InMemoryCanonicalMemoryStore()
    setup = _service(store)
    original = _confirm_one(setup)
    store.set_provider_ref(OWNER, original.id, "projection-old")
    provider = _BlockingStatefulProvider(new_ref_cleanup=new_ref_cleanup)
    service = _service(store, provider)

    with ThreadPoolExecutor(max_workers=2) as executor:
        edit_future = executor.submit(
            service.edit,
            SUBJECT,
            original.id,
            MemoryEdit(value="First edit.", sensitivity=CLEAR),
        )
        assert provider.project_started.wait(timeout=1)
        delete_future = executor.submit(service.delete, SUBJECT, original.id)
        provider.allow_project.set()
        edit_result = edit_future.result(timeout=2)
        delete_result = delete_future.result(timeout=2)

    assert edit_result.provider_status is ProviderReconciliationStatus.SYNCHRONIZED
    assert (
        delete_result.provider_status
        is ProviderReconciliationStatus.RECONCILIATION_REQUIRED
    )
    assert store.get_record(OWNER, original.id) is None
    assert provider.refs == {"projection-new"}
    targets = store.list_provider_cleanup_targets(OWNER, original.id)
    assert {target.provider_ref for target in targets} == {"projection-new"}
    assert (
        store.list_provider_cleanup_targets(
            RegisteredMemoryOwner(owner_id=OTHER_OWNER_ID),
            original.id,
        )
        == ()
    )


def test_same_record_edit_reconciliation_runs_in_mutation_generation_order() -> None:
    """Catches a losing edit deleting the update-in-place ref owned by its winner."""
    store = InMemoryCanonicalMemoryStore()
    setup = _service(store)
    original = _confirm_one(setup)
    provider = _SameRefOutOfOrderProvider()
    service = _service(store, provider)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(
            service.edit,
            SUBJECT,
            original.id,
            MemoryEdit(value="First concurrent edit.", sensitivity=CLEAR),
        )
        assert provider.first_started.wait(timeout=1)
        second_future = executor.submit(
            service.edit,
            SUBJECT,
            original.id,
            MemoryEdit(value="Second concurrent edit.", sensitivity=CLEAR),
        )
        second_projected_before_first_settled = provider.second_started.wait(timeout=0.1)
        provider.allow_first.set()
        first_result = first_future.result(timeout=2)
        second_result = second_future.result(timeout=2)

    assert second_projected_before_first_settled is False
    assert (
        first_result.provider_status
        is ProviderReconciliationStatus.RECONCILIATION_REQUIRED
    )
    assert second_result.provider_status is ProviderReconciliationStatus.SYNCHRONIZED
    canonical = store.get_record(OWNER, original.id)
    assert canonical is not None
    assert canonical.value == "Second concurrent edit."
    assert store.get_provider_ref(OWNER, original.id) == "shared-update-ref"
    assert provider.refs == {"shared-update-ref"}
    assert store.list_provider_cleanup_targets(OWNER, original.id) == ()
    assert store.inflight_reconciliation_generations(OWNER, original.id) == ()


def test_newer_edit_reports_older_distinct_cleanup_target_truthfully() -> None:
    """Catches a winner claiming synchronization while an older orphan remains."""
    store = InMemoryCanonicalMemoryStore()
    setup = _service(store)
    original = _confirm_one(setup)
    provider = _DistinctRefFailureProvider()
    service = _service(store, provider)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(
            service.edit,
            SUBJECT,
            original.id,
            MemoryEdit(value="First concurrent edit.", sensitivity=CLEAR),
        )
        assert provider.first_started.wait(timeout=1)
        second_future = executor.submit(
            service.edit,
            SUBJECT,
            original.id,
            MemoryEdit(value="Second concurrent edit.", sensitivity=CLEAR),
        )
        provider.allow_first.set()
        first_result = first_future.result(timeout=2)
        second_result = second_future.result(timeout=2)

    assert (
        first_result.provider_status
        is ProviderReconciliationStatus.RECONCILIATION_REQUIRED
    )
    assert (
        second_result.provider_status
        is ProviderReconciliationStatus.RECONCILIATION_REQUIRED
    )
    assert store.get_provider_ref(OWNER, original.id) == "winner-distinct-ref"
    assert provider.refs == {"loser-distinct-ref", "winner-distinct-ref"}
    targets = store.list_provider_cleanup_targets(OWNER, original.id)
    assert {target.provider_ref for target in targets} == {"loser-distinct-ref"}
    assert store.inflight_reconciliation_generations(OWNER, original.id) == ()


def test_reconciliation_ordering_is_independent_across_owners() -> None:
    """Catches per-record ordering accidentally becoming one global provider lock."""
    store = InMemoryCanonicalMemoryStore()
    setup = _service(store)
    first = _confirm_one(setup)
    second = _confirm_one(setup, subject=OTHER_SUBJECT)
    provider = _CrossOwnerBlockingProvider()
    service = _service(store, provider)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(
            service.edit,
            SUBJECT,
            first.id,
            MemoryEdit(value="First owner edit.", sensitivity=CLEAR),
        )
        assert provider.first_owner_started.wait(timeout=1)
        second_future = executor.submit(
            service.edit,
            OTHER_SUBJECT,
            second.id,
            MemoryEdit(value="Second owner edit.", sensitivity=CLEAR),
        )
        second_owner_progressed = provider.second_owner_started.wait(timeout=1)
        provider.allow_first_owner.set()
        first_result = first_future.result(timeout=2)
        second_result = second_future.result(timeout=2)

    assert second_owner_progressed is True
    assert first_result.provider_status is ProviderReconciliationStatus.SYNCHRONIZED
    assert second_result.provider_status is ProviderReconciliationStatus.SYNCHRONIZED


def test_unknown_and_cross_owner_controls_are_identical_and_provider_inert() -> None:
    """Catches record-id enumeration or cross-owner derivative calls."""
    store = InMemoryCanonicalMemoryStore()
    setup = _service(store)
    record = _confirm_one(setup)
    provider = _ProviderSpy()
    service = _service(store, provider)

    unknown_edit = service.edit(
        SUBJECT,
        "unknown-record",
        MemoryEdit(label="Not found", sensitivity=CLEAR),
    )
    cross_owner_edit = service.edit(
        OTHER_SUBJECT,
        record.id,
        MemoryEdit(label="Cross owner", sensitivity=CLEAR),
    )
    unknown_delete = service.delete(SUBJECT, "unknown-record")
    cross_owner_delete = service.delete(OTHER_SUBJECT, record.id)

    assert unknown_edit == cross_owner_edit
    assert unknown_delete == cross_owner_delete
    assert unknown_edit.changed is False
    assert unknown_delete.changed is False
    assert unknown_edit.provider_status is ProviderReconciliationStatus.NOT_APPLICABLE
    assert unknown_delete.provider_status is ProviderReconciliationStatus.NOT_APPLICABLE
    assert provider.project_calls == []
    assert provider.delete_calls == []
    assert store.get_record(OWNER, record.id) == record


def test_delete_without_projection_is_canonical_and_not_applicable() -> None:
    """Catches unnecessary provider cleanup for a never-projected record."""
    store = InMemoryCanonicalMemoryStore()
    setup = _service(store)
    record = _confirm_one(setup)
    store.set_settings(OWNER, MemoryConsentSettings())
    provider = _ProviderSpy()
    service = _service(store, provider)

    result = service.delete(SUBJECT, record.id)

    assert result.changed is True
    assert result.record is None
    assert result.provider_status is ProviderReconciliationStatus.NOT_APPLICABLE
    assert store.get_record(OWNER, record.id) is None
    assert provider.delete_calls == []
    assert store.get_settings(OWNER) == MemoryConsentSettings()


def test_delete_canonical_first_and_proves_derivative_cleanup() -> None:
    """Catches provider cleanup preceding the canonical delete."""
    store = InMemoryCanonicalMemoryStore()
    setup = _service(store)
    record = _confirm_one(setup)
    store.set_provider_ref(OWNER, record.id, "projection-delete")
    provider = _ProviderSpy(
        store=store,
        cleanup=ProviderCleanupResult(status=ProviderReconciliationStatus.SYNCHRONIZED),
    )
    service = _service(store, provider)

    result = service.delete(SUBJECT, record.id)

    assert provider.delete_observed_canonical_absent is True
    assert provider.delete_calls == [(OWNER, "projection-delete")]
    assert result.changed is True
    assert result.provider_status is ProviderReconciliationStatus.SYNCHRONIZED


@pytest.mark.parametrize(
    "cleanup",
    (
        RuntimeError("secret cleanup failure"),
        None,
        {"unexpected": "shape"},
        ProviderCleanupResult(status=ProviderReconciliationStatus.NOT_APPLICABLE),
        ProviderCleanupResult(
            status=ProviderReconciliationStatus.RECONCILIATION_REQUIRED
        ),
    ),
)
def test_delete_provider_failure_never_blocks_canonical_deletion(
    cleanup: object,
) -> None:
    """Catches derivative cleanup failures escaping or restoring deleted truth."""
    store = InMemoryCanonicalMemoryStore()
    setup = _service(store)
    record = _confirm_one(setup)
    store.set_provider_ref(OWNER, record.id, "projection-delete")
    provider = _ProviderSpy(cleanup=cleanup)
    service = _service(store, provider)

    result = service.delete(SUBJECT, record.id)

    assert result.changed is True
    assert result.record is None
    assert result.provider_status is ProviderReconciliationStatus.RECONCILIATION_REQUIRED
    assert store.get_record(OWNER, record.id) is None
    assert store.get_provider_ref(OWNER, record.id) is None


def _add_pending_saved_decision(
    service: MemoryService,
) -> None:
    proposal = service.propose_saved_decision(
        SUBJECT,
        SavedDecisionSource(
            label="Keep this decision pending",
            value="Revisit the lower-drawdown alternative.",
            provenance=MemoryProvenance(
                source_kind=MemorySourceKind.DECISION_NOTE,
                source_id="decision-pending-control",
                source_version="1",
            ),
        ),
        sensitivity=CLEAR,
        context=MemoryOperationContext.ORDINARY,
    )
    assert proposal is not None


def test_disable_atomically_clears_scope_candidates_and_prompt_history_only() -> None:
    """Catches disable erasing records or leaving proposal state retrievable."""
    store = InMemoryCanonicalMemoryStore()
    setup = _service(store)
    record = _confirm_one(setup)
    _add_pending_saved_decision(setup)
    store.mark_declined(
        OWNER,
        MemoryCategory.WORKFLOW_PREFERENCE,
        NOW,
    )
    store.set_provider_ref(OWNER, record.id, "projection-retained")
    receipt = record.consent_receipt
    provider = _ProviderSpy()
    service = _service(store, provider)

    result = service.disable(SUBJECT)

    assert result == MemoryControlResult(
        changed=True,
        provider_status=ProviderReconciliationStatus.NOT_APPLICABLE,
    )
    assert store.get_settings(OWNER) == MemoryConsentSettings()
    assert store.list_candidates(OWNER) == ()
    for category in MemoryCategory:
        assert store.last_proactive_prompt_at(OWNER, category) is None
        assert store.last_declined_at(OWNER, category) is None
    assert store.list_records(OWNER) == (record,)
    assert store.list_consent_receipts(OWNER) == (receipt,)
    assert store.get_provider_ref(OWNER, record.id) == "projection-retained"
    assert service.inspect(SUBJECT) == (record,)
    assert service.explain(SUBJECT, record.id) is not None
    assert (
        service.retrieve(
            SUBJECT,
            "lower drawdown",
            MemoryUsePurpose.REVISIT_SAVED_DECISION,
        )
        == ()
    )
    assert provider.project_calls == []
    assert provider.delete_calls == []
    assert provider.reset_calls == []

    assert service.disable(SUBJECT) == MemoryControlResult(
        changed=False,
        provider_status=ProviderReconciliationStatus.NOT_APPLICABLE,
    )


def test_disable_is_owner_scoped_and_keeps_controls_available() -> None:
    """Catches one owner's disable clearing another owner or blocking record control."""
    store = InMemoryCanonicalMemoryStore()
    setup = _service(store)
    first = _confirm_one(setup)
    second = _confirm_one(setup, subject=OTHER_SUBJECT)
    service = _service(store)

    service.disable(SUBJECT)
    edited = service.edit(
        SUBJECT,
        first.id,
        MemoryEdit(label="Still inspectable", sensitivity=CLEAR),
    )

    assert edited.changed is True
    assert store.get_settings(OWNER) == MemoryConsentSettings()
    assert (
        store.get_record(
            RegisteredMemoryOwner(owner_id=OTHER_OWNER_ID),
            second.id,
        )
        == second
    )
    assert store.get_settings(RegisteredMemoryOwner(owner_id=OTHER_OWNER_ID)).enabled


def test_reset_clears_complete_owner_state_before_provider_reset() -> None:
    """Catches reset leaving canonical, proposal, or reconciliation bookkeeping."""
    store = InMemoryCanonicalMemoryStore()
    setup = _service(store)
    record = _confirm_one(setup)
    _add_pending_saved_decision(setup)
    store.mark_declined(
        OWNER,
        MemoryCategory.WORKFLOW_PREFERENCE,
        NOW,
    )
    store.set_provider_ref(OWNER, record.id, "projection-current")
    store.track_provider_cleanup_target(
        OWNER,
        record.id,
        "projection-stale",
    )
    first_mutation = store.edit_record(
        OWNER,
        record.id,
        label="First mutation generation",
        value=None,
    )
    assert first_mutation is not None
    assert first_mutation.reconciliation_generation == 2
    first_claim = store.claim_reconciliation_turn(OWNER, record.id, 2)
    assert first_claim is not None
    assert store.finish_reconciliation_claim(
        OWNER,
        first_claim,
        succeeded=True,
        error_code=None,
        completed_at=NOW,
    )
    provider = _ProviderSpy(
        store=store,
        reset=ProviderCleanupResult(status=ProviderReconciliationStatus.SYNCHRONIZED),
    )
    service = _service(store, provider)

    result = service.reset(SUBJECT)

    assert result == MemoryControlResult(
        changed=True,
        provider_status=ProviderReconciliationStatus.SYNCHRONIZED,
    )
    assert provider.reset_calls == [OWNER]
    assert provider.reset_observed_canonical_empty is True
    assert store.get_settings(OWNER) == MemoryConsentSettings()
    assert store.list_candidates(OWNER) == ()
    assert store.list_consent_receipts(OWNER) == ()
    assert store.list_records(OWNER) == ()
    assert store.get_provider_ref(OWNER, record.id) is None
    assert store.list_provider_cleanup_targets(OWNER) == ()
    assert store.inflight_reconciliation_generations(OWNER, record.id) == ()
    for category in MemoryCategory:
        assert store.last_proactive_prompt_at(OWNER, category) is None
        assert store.last_declined_at(OWNER, category) is None

    fresh = _confirm_one(service)
    fresh_mutation = store.edit_record(
        OWNER,
        fresh.id,
        label="Fresh generation after reset",
        value=None,
    )
    assert fresh_mutation is not None
    assert fresh_mutation.reconciliation_generation == 2
    fresh_claim = store.claim_reconciliation_turn(OWNER, fresh.id, 2)
    assert fresh_claim is not None
    assert store.finish_reconciliation_claim(
        OWNER,
        fresh_claim,
        succeeded=True,
        error_code=None,
        completed_at=NOW,
    )


def test_in_memory_reconciliation_requires_the_exact_claim() -> None:
    store = InMemoryCanonicalMemoryStore(
        reconciliation_token_factory=lambda: "in-memory-exact",
    )
    service = _service(store)
    record = _confirm_one(service)
    mutation = store.edit_record(
        OWNER,
        record.id,
        label="Claimed edit",
        value=None,
    )
    assert mutation is not None
    assert mutation.reconciliation_generation is not None
    claim = store.claim_reconciliation_turn(
        OWNER,
        record.id,
        mutation.reconciliation_generation,
    )
    assert claim is not None
    stale = ReconciliationClaim(
        record_id=claim.record_id,
        generation=claim.generation,
        operation=claim.operation,
        claim_token="in-memory-stale",
    )

    assert not store.finish_reconciliation_claim(
        OWNER,
        stale,
        succeeded=True,
        error_code=None,
        completed_at=NOW,
    )
    assert store.finish_reconciliation_claim(
        OWNER,
        claim,
        succeeded=True,
        error_code=None,
        completed_at=NOW,
    )


def test_reset_requires_reconciliation_when_known_projection_is_not_applicable() -> None:
    """Catches a provider no-op claiming cleanup for a known derivative copy."""
    store = InMemoryCanonicalMemoryStore()
    setup = _service(store)
    record = _confirm_one(setup)
    store.set_provider_ref(OWNER, record.id, "projection-known")
    provider = _ProviderSpy(
        reset=ProviderCleanupResult(status=ProviderReconciliationStatus.NOT_APPLICABLE)
    )
    service = _service(store, provider)

    result = service.reset(SUBJECT)

    assert result.provider_status is ProviderReconciliationStatus.RECONCILIATION_REQUIRED


def test_empty_reset_is_inert_and_provider_free() -> None:
    """Catches an already-zero reset making an unnecessary provider call."""
    store = InMemoryCanonicalMemoryStore()
    provider = _ProviderSpy()
    service = _service(store, provider)

    result = service.reset(SUBJECT)

    assert result == MemoryControlResult(
        changed=False,
        provider_status=ProviderReconciliationStatus.NOT_APPLICABLE,
    )
    assert provider.reset_calls == []


def test_reset_is_owner_scoped() -> None:
    """Catches reset clearing destination-owned memory for a different account."""
    store = InMemoryCanonicalMemoryStore()
    setup = _service(store)
    first = _confirm_one(setup)
    second = _confirm_one(setup, subject=OTHER_SUBJECT)
    service = _service(store)

    service.reset(SUBJECT)

    assert store.get_record(OWNER, first.id) is None
    other_owner = RegisteredMemoryOwner(owner_id=OTHER_OWNER_ID)
    assert store.get_record(other_owner, second.id) == second
    assert store.get_settings(other_owner).enabled


def test_reset_waits_for_inflight_edit_before_owner_provider_reset() -> None:
    """Catches a late edit projection surviving an owner-wide reset."""
    store = InMemoryCanonicalMemoryStore()
    setup = _service(store)
    record = _confirm_one(setup)
    store.set_provider_ref(OWNER, record.id, "projection-old")
    provider = _ResetAwareBlockingProvider()
    service = _service(store, provider)

    with ThreadPoolExecutor(max_workers=2) as executor:
        edit_future = executor.submit(
            service.edit,
            SUBJECT,
            record.id,
            MemoryEdit(value="Blocked edit before reset.", sensitivity=CLEAR),
        )
        assert provider.project_started.wait(timeout=1)
        reset_future = executor.submit(service.reset, SUBJECT)
        reset_ran_before_edit_settled = provider.reset_called.wait(timeout=0.1)
        provider.allow_project.set()
        edit_result = edit_future.result(timeout=2)
        reset_result = reset_future.result(timeout=2)

    assert reset_ran_before_edit_settled is False
    assert edit_result.provider_status is ProviderReconciliationStatus.SYNCHRONIZED
    assert reset_result.provider_status is ProviderReconciliationStatus.SYNCHRONIZED
    assert store.list_records(OWNER) == ()
    assert store.list_provider_cleanup_targets(OWNER) == ()
    assert provider.refs == set()


def test_reset_waits_for_inflight_delete_cleanup() -> None:
    """Catches reset racing ahead of a prior canonical-first provider delete."""
    store = InMemoryCanonicalMemoryStore()
    setup = _service(store)
    record = _confirm_one(setup)
    store.set_provider_ref(OWNER, record.id, "projection-delete")
    provider = _BlockingDeleteProvider()
    service = _service(store, provider)

    with ThreadPoolExecutor(max_workers=2) as executor:
        delete_future = executor.submit(service.delete, SUBJECT, record.id)
        assert provider.delete_started.wait(timeout=1)
        reset_future = executor.submit(service.reset, SUBJECT)
        reset_ran_before_delete_settled = provider.reset_called.wait(timeout=0.1)
        provider.allow_delete.set()
        delete_result = delete_future.result(timeout=2)
        reset_result = reset_future.result(timeout=2)

    assert reset_ran_before_delete_settled is False
    assert delete_result.provider_status is ProviderReconciliationStatus.SYNCHRONIZED
    assert reset_result.provider_status is ProviderReconciliationStatus.SYNCHRONIZED
    assert provider.refs == set()


def test_reset_waits_for_inflight_confirmation_projection() -> None:
    """Catches a late confirmation projection surviving an owner-wide reset."""
    store = InMemoryCanonicalMemoryStore()
    provider = _BlockingConfirmationResetProvider()
    service = _service(store, provider)
    proposal = service.propose(
        SUBJECT,
        MemoryCandidateDraft(
            category=MemoryCategory.EXPLICIT_DECISION_NOTE,
            value="Confirm before reset.",
            label="Confirmation reset race",
            future_benefit="Argus can revisit the confirmed decision.",
            provenance=(
                MemoryProvenance(
                    source_kind=MemorySourceKind.DECISION_NOTE,
                    source_id="decision-confirm-reset-race",
                    source_version="1",
                ),
            ),
            trigger=MemoryProposalTrigger.EXPLICIT_REQUEST,
            sensitivity=CLEAR,
        ),
        MemoryOperationContext.ORDINARY,
    )
    assert proposal is not None

    with ThreadPoolExecutor(max_workers=2) as executor:
        confirm_future = executor.submit(
            service.confirm,
            SUBJECT,
            proposal.candidate.id,
            sensitivity=CLEAR,
            context=MemoryOperationContext.ORDINARY,
        )
        assert provider.project_started.wait(timeout=1)
        committed = store.list_records(OWNER)
        assert len(committed) == 1
        record_id = committed[0].id
        reset_future = executor.submit(service.reset, SUBJECT)
        reset_ran_before_confirmation_settled = provider.reset_called.wait(timeout=0.1)
        provider.allow_project.set()
        confirmation = confirm_future.result(timeout=2)
        reset_result = reset_future.result(timeout=2)

    assert reset_ran_before_confirmation_settled is False
    assert confirmation.created is True
    assert reset_result.provider_status is ProviderReconciliationStatus.SYNCHRONIZED
    assert store.get_settings(OWNER) == MemoryConsentSettings()
    assert store.list_candidates(OWNER) == ()
    assert store.list_consent_receipts(OWNER) == ()
    assert store.list_records(OWNER) == ()
    assert store.get_provider_ref(OWNER, record_id) is None
    assert store.list_provider_cleanup_targets(OWNER) == ()
    assert store.inflight_reconciliation_generations(OWNER, record_id) == ()
    assert provider.refs == set()


def test_confirmation_replay_creates_no_provider_work_or_generation() -> None:
    """Catches inert confirmation replay creating derivative or pending work."""
    store = InMemoryCanonicalMemoryStore()
    provider = _ProviderSpy()
    service = _service(store, provider)
    proposal = service.propose(
        SUBJECT,
        MemoryCandidateDraft(
            category=MemoryCategory.EXPLICIT_DECISION_NOTE,
            value="Confirm once.",
            label="One confirmation",
            future_benefit="Argus can revisit the confirmed decision.",
            provenance=(
                MemoryProvenance(
                    source_kind=MemorySourceKind.DECISION_NOTE,
                    source_id="decision-confirm-once",
                    source_version="1",
                ),
            ),
            trigger=MemoryProposalTrigger.EXPLICIT_REQUEST,
            sensitivity=CLEAR,
        ),
        MemoryOperationContext.ORDINARY,
    )
    assert proposal is not None
    first = service.confirm(
        SUBJECT,
        proposal.candidate.id,
        sensitivity=CLEAR,
        context=MemoryOperationContext.ORDINARY,
    )
    assert first.record is not None

    replay = service.confirm(
        SUBJECT,
        proposal.candidate.id,
        sensitivity=CLEAR,
        context=MemoryOperationContext.ORDINARY,
    )

    assert replay.created is False
    assert len(provider.project_calls) == 1
    assert store.inflight_reconciliation_generations(OWNER, first.record.id) == ()
