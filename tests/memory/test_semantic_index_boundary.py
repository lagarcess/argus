"""What the derivative index is allowed to learn, and when.

Four properties, each proved against the real pipeline rather than the
provider in isolation:

1. Mem0 only ever sees confirmed content; proposals and declines never reach
   it, because projection happens after canonical confirmation.
2. The categorical never-stored classes, broker credentials and raw
   conversation, are suppressed in code before storage, so they never become a
   record and therefore never reach the index.
3. The index gate independently refuses anything it cannot prove is confirmed,
   so a corrupted store cannot feed the index either.
4. A search answer carries ranked canonical ids and no content.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone

import pytest
from argus.api.personalization_memory_index import (
    RECORD_ID_METADATA_KEY,
    Mem0MemoryProvider,
)
from argus.memory.contracts import (
    MemoryCandidateDraft,
    MemoryCategory,
    MemoryOperationContext,
    MemoryProposalTrigger,
    MemoryProvenance,
    MemorySensitivityFlag,
    MemorySourceKind,
    MemoryUsePurpose,
    ProviderReconciliationStatus,
    SensitivityAssessment,
    SensitivityStatus,
)
from argus.memory.index_policy import IndexRefusal, index_eligibility
from argus.memory.service import MemoryService, MemoryServiceConfig
from argus.memory.store import InMemoryCanonicalMemoryStore
from argus.memory.subject import MemoryAccountKind, MemorySubject, RegisteredMemoryOwner

NOW = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)
OWNER_ID = "3f8a1d02-6c4b-4a7e-9d51-2b0e7c3a5f18"
OTHER_OWNER_ID = "9c2f5b74-1e83-4d06-a5f9-70d8b4e21c6a"
SUBJECT = MemorySubject(owner_id=OWNER_ID, kind=MemoryAccountKind.REGISTERED)
OWNER = RegisteredMemoryOwner(owner_id=OWNER_ID)
CLEAR = SensitivityAssessment(status=SensitivityStatus.CLEAR)


class _RecordingMem0:
    """Stands in for the Mem0 client and records everything it is handed."""

    def __init__(self, search_results: list[dict] | None = None) -> None:
        self.added: list[dict] = []
        self.searched: list[dict] = []
        self.deleted: list[str] = []
        self.reset_calls: list[str] = []
        self._search_results = search_results or []

    def add(self, *, messages, user_id, metadata, infer):  # noqa: ANN001
        self.added.append(
            {
                "messages": messages,
                "user_id": user_id,
                "metadata": metadata,
                "infer": infer,
            }
        )
        return {"results": [{"id": f"mem0-{len(self.added)}", "event": "ADD"}]}

    def search(self, query, *, top_k, filters, threshold):  # noqa: ANN001
        self.searched.append(
            {
                "query": query,
                "top_k": top_k,
                "filters": filters,
                "threshold": threshold,
            }
        )
        return {"results": self._search_results}

    def delete(self, memory_id):  # noqa: ANN001
        self.deleted.append(memory_id)

    def delete_all(self, user_id=None):  # noqa: ANN001
        self.reset_calls.append(user_id)


class _StubEmbedder:
    dimensions = 4

    def embed(self, text: str) -> list[float]:
        del text
        return [0.0, 0.0, 0.0, 0.0]

    def last_usage(self):
        from argus.llm.memory_embedding import EmbeddingUsage

        return EmbeddingUsage()


def _ids() -> Iterator[str]:
    index = 0
    while True:
        index += 1
        yield f"generated-{index:03d}"


def _service(
    store: InMemoryCanonicalMemoryStore,
    provider: object | None = None,
) -> MemoryService:
    generated = _ids()
    return MemoryService(
        store=store,
        provider=provider,  # type: ignore[arg-type]
        config=MemoryServiceConfig(available=True),
        clock=lambda: NOW,
        id_factory=lambda: next(generated),
    )


def _draft(
    *,
    value: str = "Kept the lower drawdown ETH variant after comparing both.",
    label: str = "ETH drawdown choice",
    sensitivity: SensitivityAssessment = CLEAR,
) -> MemoryCandidateDraft:
    return MemoryCandidateDraft(
        category=MemoryCategory.EXPLICIT_DECISION_NOTE,
        value=value,
        label=label,
        future_benefit="Argus can revisit the confirmed choice later.",
        provenance=(
            MemoryProvenance(
                source_kind=MemorySourceKind.DECISION_NOTE,
                source_id="decision-index-test",
                source_version="1",
            ),
        ),
        trigger=MemoryProposalTrigger.EXPLICIT_REQUEST,
        sensitivity=sensitivity,
    )


def _provider(mem0: _RecordingMem0) -> Mem0MemoryProvider:
    return Mem0MemoryProvider(embedder=_StubEmbedder(), memory=mem0)


def test_proposing_never_reaches_mem0_because_nothing_is_confirmed_yet() -> None:
    """Catches unconfirmed candidate content being indexed at proposal time."""
    mem0 = _RecordingMem0()
    service = _service(InMemoryCanonicalMemoryStore(), _provider(mem0))

    proposal = service.propose(SUBJECT, _draft(), MemoryOperationContext.ORDINARY)

    assert proposal is not None
    assert mem0.added == []


def test_declining_a_candidate_never_reaches_mem0() -> None:
    """Catches a declined proposal leaving content behind in the index."""
    mem0 = _RecordingMem0()
    service = _service(InMemoryCanonicalMemoryStore(), _provider(mem0))
    proposal = service.propose(SUBJECT, _draft(), MemoryOperationContext.ORDINARY)
    assert proposal is not None

    assert service.decline(SUBJECT, proposal.candidate.id) is True
    assert mem0.added == []


def test_only_confirmation_hands_mem0_the_exact_confirmed_text() -> None:
    """Catches the index receiving anything other than confirmed record text."""
    mem0 = _RecordingMem0()
    service = _service(InMemoryCanonicalMemoryStore(), _provider(mem0))
    proposal = service.propose(SUBJECT, _draft(), MemoryOperationContext.ORDINARY)
    assert proposal is not None
    assert mem0.added == []

    confirmation = service.confirm(
        SUBJECT,
        proposal.candidate.id,
        context=MemoryOperationContext.ORDINARY,
    )

    assert confirmation.created is True
    assert confirmation.record is not None
    assert len(mem0.added) == 1
    call = mem0.added[0]
    assert call["user_id"] == OWNER_ID
    assert call["metadata"] == {RECORD_ID_METADATA_KEY: confirmation.record.id}
    # infer=False is the parameter that keeps Mem0's extraction pipeline out of
    # the path; Argus owns extraction and storage.
    assert call["infer"] is False
    indexed = call["messages"][0]["content"]
    assert confirmation.record.value in indexed
    assert confirmation.record.label in indexed


@pytest.mark.parametrize(
    "flag",
    (
        MemorySensitivityFlag.BROKER_CREDENTIAL,
        MemorySensitivityFlag.RAW_CONVERSATION,
    ),
)
def test_never_stored_classes_never_reach_the_index(
    flag: MemorySensitivityFlag,
) -> None:
    """Catches a categorically never-stored class being vectorized."""
    mem0 = _RecordingMem0()
    store = InMemoryCanonicalMemoryStore()
    service = _service(store, _provider(mem0))

    restricted = SensitivityAssessment(
        status=SensitivityStatus.RESTRICTED,
        flags=frozenset({flag}),
    )
    proposal = service.propose(
        SUBJECT,
        _draft(sensitivity=restricted),
        MemoryOperationContext.ORDINARY,
    )

    # Suppressed before storage, so there is no candidate, no record, and
    # nothing the index could ever be handed.
    assert proposal is None
    assert store.list_records(OWNER) == ()
    assert mem0.added == []


@pytest.mark.parametrize(
    "context",
    (
        MemoryOperationContext.BROKER,
        MemoryOperationContext.RESTRICTED_FINANCIAL,
        MemoryOperationContext.EXPORT,
    ),
)
def test_restricted_contexts_never_reach_the_index(
    context: MemoryOperationContext,
) -> None:
    """Catches a restricted-context turn indexing content."""
    mem0 = _RecordingMem0()
    service = _service(InMemoryCanonicalMemoryStore(), _provider(mem0))

    assert service.propose(SUBJECT, _draft(), context) is None
    assert mem0.added == []


def test_index_gate_refuses_a_record_it_cannot_prove_is_confirmed() -> None:
    """Catches a corrupted store feeding the index behind the service's back."""
    mem0 = _RecordingMem0()
    store = InMemoryCanonicalMemoryStore()
    service = _service(store, _provider(mem0))
    proposal = service.propose(SUBJECT, _draft(), MemoryOperationContext.ORDINARY)
    assert proposal is not None
    confirmation = service.confirm(
        SUBJECT,
        proposal.candidate.id,
        context=MemoryOperationContext.ORDINARY,
    )
    assert confirmation.record is not None
    record = confirmation.record

    # A record whose consent receipt does not cover it is not confirmed.
    forged = record.model_copy(
        update={
            "consent_receipt": record.consent_receipt.model_copy(
                update={"candidate_id": "some-other-candidate"}
            )
        }
    )
    decision = index_eligibility(OWNER, forged)

    assert decision.allowed is False
    assert decision.refusal is IndexRefusal.UNCONFIRMED


def test_index_gate_refuses_another_owners_record() -> None:
    """Catches cross-owner projection putting one user's memory in another's index."""
    mem0 = _RecordingMem0()
    store = InMemoryCanonicalMemoryStore()
    service = _service(store, _provider(mem0))
    proposal = service.propose(SUBJECT, _draft(), MemoryOperationContext.ORDINARY)
    assert proposal is not None
    confirmation = service.confirm(
        SUBJECT,
        proposal.candidate.id,
        context=MemoryOperationContext.ORDINARY,
    )
    assert confirmation.record is not None

    other = RegisteredMemoryOwner(owner_id=OTHER_OWNER_ID)
    decision = index_eligibility(other, confirmation.record)

    assert decision.allowed is False
    assert decision.refusal is IndexRefusal.OWNER_MISMATCH


def test_refused_projection_declines_without_calling_mem0() -> None:
    """Catches a refused record still being sent to the vendor client."""
    mem0 = _RecordingMem0()
    store = InMemoryCanonicalMemoryStore()
    service = _service(store, _provider(mem0))
    proposal = service.propose(SUBJECT, _draft(), MemoryOperationContext.ORDINARY)
    assert proposal is not None
    confirmation = service.confirm(
        SUBJECT,
        proposal.candidate.id,
        context=MemoryOperationContext.ORDINARY,
    )
    assert confirmation.record is not None
    mem0.added.clear()

    other = RegisteredMemoryOwner(owner_id=OTHER_OWNER_ID)
    result = _provider(mem0).project(other, confirmation.record)

    assert result.status is ProviderReconciliationStatus.NOT_APPLICABLE
    assert mem0.added == []


def test_search_answer_carries_ranked_ids_and_no_indexed_content() -> None:
    """Catches provider-held text reaching the service instead of canonical text."""
    mem0 = _RecordingMem0(
        search_results=[
            {
                "id": "mem0-1",
                "memory": "stale text the index happens to hold",
                "score": 0.82,
                "metadata": {RECORD_ID_METADATA_KEY: "record-1"},
            }
        ]
    )

    result = _provider(mem0).search(OWNER, "eth drawdown", 3)

    assert [(hit.record_id, hit.score) for hit in result.hits] == [("record-1", 0.82)]
    # The hit model has no content field at all, so indexed text cannot cross.
    assert not hasattr(result.hits[0], "memory")
    assert "content" not in result.hits[0].model_dump()


def test_search_scopes_every_query_to_one_owner() -> None:
    """Catches an unscoped query ranking another account's memories."""
    mem0 = _RecordingMem0()

    _provider(mem0).search(OWNER, "eth drawdown", 2)

    assert mem0.searched[0]["filters"] == {"user_id": OWNER_ID}
    assert mem0.searched[0]["top_k"] == 2


def test_hits_without_a_canonical_record_id_are_dropped() -> None:
    """Catches index rows that predate or bypass the record-id join being trusted."""
    mem0 = _RecordingMem0(
        search_results=[
            {"id": "mem0-1", "score": 0.9, "metadata": {}},
            {"id": "mem0-2", "score": 0.8},
            {"id": "mem0-3", "score": 0.7, "metadata": {RECORD_ID_METADATA_KEY: "ok"}},
        ]
    )

    result = _provider(mem0).search(OWNER, "eth", 5)

    assert [hit.record_id for hit in result.hits] == ["ok"]


def test_reset_and_delete_scope_to_the_owner() -> None:
    """Catches control operations clearing more of the index than one account."""
    mem0 = _RecordingMem0()
    provider = _provider(mem0)

    provider.delete(OWNER, "mem0-1")
    provider.reset(OWNER)

    assert mem0.deleted == ["mem0-1"]
    assert mem0.reset_calls == [OWNER_ID]


def test_retrieval_uses_canonical_text_even_when_the_index_is_stale() -> None:
    """Catches the user being shown index text instead of canonical truth."""
    store = InMemoryCanonicalMemoryStore()
    setup = _service(store)
    proposal = setup.propose(SUBJECT, _draft(), MemoryOperationContext.ORDINARY)
    assert proposal is not None
    confirmation = setup.confirm(
        SUBJECT,
        proposal.candidate.id,
        context=MemoryOperationContext.ORDINARY,
    )
    assert confirmation.record is not None
    record_id = confirmation.record.id

    mem0 = _RecordingMem0(
        search_results=[
            {
                "id": "mem0-1",
                "memory": "STALE INDEX TEXT",
                "score": 0.95,
                "metadata": {RECORD_ID_METADATA_KEY: record_id},
            }
        ]
    )
    service = _service(store, _provider(mem0))

    retrieved = service.retrieve(
        SUBJECT,
        "which eth variant did I keep",
        MemoryUsePurpose.REVISIT_SAVED_DECISION,
    )

    assert len(retrieved) == 1
    assert retrieved[0].record.value == confirmation.record.value
    assert "STALE INDEX TEXT" not in retrieved[0].record.value
