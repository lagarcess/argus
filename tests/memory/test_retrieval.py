from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone

import pytest
from argus.memory.contracts import (
    MemoryCandidateDraft,
    MemoryCategory,
    MemoryConsentSettings,
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
from argus.memory.policy import MemoryPolicy
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

NOW = datetime(2026, 7, 29, 18, 0, tzinfo=timezone.utc)
OWNER_A = "5e1ab68c-4410-47e5-a503-145c93715a77"
OWNER_B = "1170e91c-5f07-4514-9e71-b8dce6274c85"


def _subject(owner_id: str = OWNER_A) -> MemorySubject:
    return MemorySubject(owner_id=owner_id, kind=MemoryAccountKind.REGISTERED)


def _ids() -> Iterator[str]:
    index = 0
    while True:
        index += 1
        yield f"id-{index:03d}"


class _StaticProvider(MemoryRetrievalProvider):
    def __init__(self, result: ProviderSearchResult) -> None:
        self.result = result
        self.search_calls = 0

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
        self.search_calls += 1
        return self.result

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


def _service(
    store: InMemoryCanonicalMemoryStore,
    *,
    provider: MemoryRetrievalProvider | None = None,
) -> MemoryService:
    generated_ids = _ids()
    return MemoryService(
        store=store,
        provider=provider,
        config=MemoryServiceConfig(available=True),
        policy=MemoryPolicy(),
        clock=lambda: NOW,
        id_factory=lambda: next(generated_ids),
    )


def _remember(
    service: MemoryService,
    subject: MemorySubject,
    *,
    category: MemoryCategory,
    label: str,
    value: str,
    source_id: str,
) -> str:
    proposal = service.propose(
        subject,
        MemoryCandidateDraft(
            category=category,
            value=value,
            label=label,
            future_benefit="Argus can revisit this confirmed choice later.",
            provenance=(
                MemoryProvenance(
                    source_kind=MemorySourceKind.DECISION_NOTE,
                    source_id=source_id,
                    source_version="1",
                ),
            ),
            trigger=MemoryProposalTrigger.EXPLICIT_REQUEST,
            sensitivity=SensitivityAssessment(status=SensitivityStatus.CLEAR),
        ),
        MemoryOperationContext.ORDINARY,
    )
    assert proposal is not None
    confirmation = service.confirm(
        subject,
        proposal.candidate.id,
        sensitivity=SensitivityAssessment(status=SensitivityStatus.CLEAR),
        context=MemoryOperationContext.ORDINARY,
    )
    assert confirmation.created is True
    assert confirmation.record is not None
    return confirmation.record.id


def test_use_purpose_cannot_represent_runtime_or_canonical_truth_influence() -> None:
    """Catches a broad purpose enum that allows memory into protected decisions."""
    for forbidden in (
        "interpretation",
        "routing",
        "simulation",
        "confirmation",
        "execution",
        "metrics",
        "canonical_evidence",
        "recommendation",
    ):
        with pytest.raises(ValueError):
            MemoryUsePurpose(forbidden)


def test_canonical_fallback_is_stable_relevant_and_default_bounded() -> None:
    """Catches unbounded or insertion-ordered fallback instead of stable relevance."""
    store = InMemoryCanonicalMemoryStore()
    service = _service(store)
    subject = _subject()
    _remember(
        service,
        subject,
        category=MemoryCategory.EXPLICIT_DECISION_NOTE,
        label="Lower drawdown baseline",
        value="Keep the lower drawdown baseline for comparison.",
        source_id="decision-1",
    )
    _remember(
        service,
        subject,
        category=MemoryCategory.PAST_SESSION_ANCHOR,
        label="Drawdown review",
        value="Revisit the drawdown review.",
        source_id="decision-2",
    )
    _remember(
        service,
        subject,
        category=MemoryCategory.EXPLICIT_DECISION_NOTE,
        label="Lower volatility",
        value="Compare lower volatility against the baseline.",
        source_id="decision-3",
    )
    _remember(
        service,
        subject,
        category=MemoryCategory.EXPLICIT_DECISION_NOTE,
        label="Unrelated momentum note",
        value="Review momentum later.",
        source_id="decision-4",
    )

    retrieved = service.retrieve(
        subject,
        "lower drawdown baseline",
        MemoryUsePurpose.COMPARE_SAVED_DECISIONS,
    )

    assert len(retrieved) == 3
    assert [item.record.label for item in retrieved] == [
        "Lower drawdown baseline",
        "Lower volatility",
        "Drawdown review",
    ]
    assert all(
        item.selection_reason is MemorySelectionReason.CANONICAL_TOKEN_MATCH
        for item in retrieved
    )


@pytest.mark.parametrize("limit", (0, -1, 11))
def test_retrieval_rejects_limits_outside_the_closed_bound(limit: int) -> None:
    """Catches caller-controlled retrieval that can be empty or exceed ten records."""
    service = _service(InMemoryCanonicalMemoryStore())

    with pytest.raises(ValueError, match="between 1 and 10"):
        service.retrieve(
            _subject(),
            "drawdown",
            MemoryUsePurpose.REVISIT_SAVED_DECISION,
            limit=limit,
        )


def test_inspect_and_explain_rehydrate_only_owner_canonical_truth() -> None:
    """Catches cross-owner explain or provider-shaped data replacing canonical truth."""
    store = InMemoryCanonicalMemoryStore()
    service = _service(store)
    own_record_id = _remember(
        service,
        _subject(OWNER_A),
        category=MemoryCategory.EXPLICIT_DECISION_NOTE,
        label="Owner A decision",
        value="Owner A chose the lower drawdown case.",
        source_id="decision-owner-a",
    )
    other_record_id = _remember(
        service,
        _subject(OWNER_B),
        category=MemoryCategory.EXPLICIT_DECISION_NOTE,
        label="Owner B decision",
        value="Owner B chose the higher return case.",
        source_id="decision-owner-b",
    )

    inspected = service.inspect(_subject(OWNER_A))
    explanation = service.explain(_subject(OWNER_A), own_record_id)

    assert [record.id for record in inspected] == [own_record_id]
    assert explanation is not None
    assert explanation.record_id == own_record_id
    assert explanation.provenance == inspected[0].provenance_refs
    assert explanation.consent_receipt_id == inspected[0].consent_receipt.id
    assert explanation.confirmed_at == inspected[0].consent_receipt.confirmed_at
    assert service.explain(_subject(OWNER_A), other_record_id) is None


def test_provider_hits_are_rehydrated_filtered_deduplicated_and_stably_ranked() -> None:
    """Catches provider ids bypassing owner, scope, dedupe, or canonical rehydration."""
    store = InMemoryCanonicalMemoryStore()
    setup_service = _service(store)
    allowed_id = _remember(
        setup_service,
        _subject(OWNER_A),
        category=MemoryCategory.EXPLICIT_DECISION_NOTE,
        label="Canonical allowed label",
        value="Canonical allowed value.",
        source_id="allowed-source",
    )
    out_of_scope_id = _remember(
        setup_service,
        _subject(OWNER_A),
        category=MemoryCategory.WORKFLOW_PREFERENCE,
        label="Wrong retrieval purpose",
        value="This category is enabled but not valid for saved-decision use.",
        source_id="wrong-purpose-source",
    )
    consent_out_of_scope_id = _remember(
        setup_service,
        _subject(OWNER_A),
        category=MemoryCategory.PAST_SESSION_ANCHOR,
        label="Outside active consent",
        value="This saved-decision category is no longer enabled.",
        source_id="outside-consent-source",
    )
    cross_owner_id = _remember(
        setup_service,
        _subject(OWNER_B),
        category=MemoryCategory.EXPLICIT_DECISION_NOTE,
        label="Other owner",
        value="Must never cross the owner boundary.",
        source_id="other-owner-source",
    )
    store.set_settings(
        RegisteredMemoryOwner(owner_id=OWNER_A),
        MemoryConsentSettings(
            enabled=True,
            enabled_categories=frozenset(
                {
                    MemoryCategory.EXPLICIT_DECISION_NOTE,
                    MemoryCategory.WORKFLOW_PREFERENCE,
                }
            ),
        ),
    )
    provider = _StaticProvider(
        ProviderSearchResult(
            status=ProviderSearchStatus.ANSWERED,
            hits=(
                ProviderHit(record_id="unknown-record", score=100.0),
                ProviderHit(record_id=cross_owner_id, score=90.0),
                ProviderHit(record_id=out_of_scope_id, score=80.0),
                ProviderHit(record_id=consent_out_of_scope_id, score=70.0),
                ProviderHit(record_id=allowed_id, score=1.0),
                ProviderHit(record_id=allowed_id, score=99.0),
            ),
        )
    )
    service = _service(store, provider=provider)

    retrieved = service.retrieve(
        _subject(OWNER_A),
        "provider content is not canonical",
        MemoryUsePurpose.REVISIT_SAVED_DECISION,
        limit=10,
    )

    assert len(retrieved) == 1
    assert retrieved[0].record.id == allowed_id
    assert retrieved[0].record.label == "Canonical allowed label"
    assert retrieved[0].record.value == "Canonical allowed value."
    assert retrieved[0].record.provenance.source_id == "allowed-source"
    assert retrieved[0].selection_reason is MemorySelectionReason.PROVIDER_RANKED


def test_disabled_or_restricted_scope_returns_no_memory_before_provider() -> None:
    """Catches retrieval from disabled or restricted contexts invoking a provider."""
    store = InMemoryCanonicalMemoryStore()
    setup_service = _service(store)
    _remember(
        setup_service,
        _subject(),
        category=MemoryCategory.EXPLICIT_DECISION_NOTE,
        label="Saved decision",
        value="A confirmed saved decision.",
        source_id="saved-decision",
    )
    provider = _StaticProvider(
        ProviderSearchResult(status=ProviderSearchStatus.UNAVAILABLE)
    )
    service = _service(store, provider=provider)
    owner = RegisteredMemoryOwner(owner_id=OWNER_A)
    store.set_settings(owner, MemoryConsentSettings())

    assert (
        service.retrieve(
            _subject(),
            "decision",
            MemoryUsePurpose.REVISIT_SAVED_DECISION,
        )
        == ()
    )
    store.set_settings(
        owner,
        MemoryConsentSettings(
            enabled=True,
            enabled_categories=frozenset({MemoryCategory.EXPLICIT_DECISION_NOTE}),
        ),
    )
    for context in (
        MemoryOperationContext.BROKER,
        MemoryOperationContext.EXPORT,
        MemoryOperationContext.RESTRICTED_FINANCIAL,
    ):
        assert (
            service.retrieve(
                _subject(),
                "decision",
                MemoryUsePurpose.REVISIT_SAVED_DECISION,
                context,
            )
            == ()
        )
    assert provider.search_calls == 0
