"""Every semantic-recall failure degrades to canonical truth, never open.

Semantic recall is a quality upgrade over the canonical token match. When the
embedder, the vendor client, or the assessor fails, the user must still get a
correct, if less clever, answer, and no failure may widen what is stored or
shown.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone

import pytest
from argus.api.personalization_memory_index import (
    RECORD_ID_METADATA_KEY,
    Mem0MemoryProvider,
)
from argus.llm.memory_embedding import EmbeddingUsage, MemoryEmbeddingUnavailable
from argus.memory.contracts import (
    MemoryCandidateDraft,
    MemoryCategory,
    MemoryOperationContext,
    MemoryProposalTrigger,
    MemoryProvenance,
    MemorySelectionReason,
    MemorySourceKind,
    MemoryUsePurpose,
    SensitivityAssessment,
    SensitivityStatus,
)
from argus.memory.service import MemoryService, MemoryServiceConfig
from argus.memory.store import InMemoryCanonicalMemoryStore
from argus.memory.subject import MemoryAccountKind, MemorySubject, RegisteredMemoryOwner

NOW = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)
OWNER_ID = "3f8a1d02-6c4b-4a7e-9d51-2b0e7c3a5f18"
SUBJECT = MemorySubject(owner_id=OWNER_ID, kind=MemoryAccountKind.REGISTERED)
OWNER = RegisteredMemoryOwner(owner_id=OWNER_ID)
CLEAR = SensitivityAssessment(status=SensitivityStatus.CLEAR)
QUERY = "lower drawdown"
# Shares no token with the stored memory, so only a semantic index can match
# it. The A/B pair below depends on that.
SEMANTIC_QUERY = "gentler decline variant"


class _StubEmbedder:
    dimensions = 4

    def __init__(self, failure: Exception | None = None) -> None:
        self._failure = failure
        self.calls = 0

    def embed(self, text: str) -> list[float]:
        del text
        self.calls += 1
        if self._failure is not None:
            raise self._failure
        return [0.1, 0.2, 0.3, 0.4]

    def last_usage(self) -> EmbeddingUsage:
        return EmbeddingUsage()


class _Mem0Double:
    """Mem0 client double whose calls can be made to fail on demand."""

    def __init__(
        self,
        *,
        embedder: _StubEmbedder,
        search_results: list[dict] | None = None,
        add_failure: Exception | None = None,
        search_failure: Exception | None = None,
    ) -> None:
        self._embedder = embedder
        self._search_results = search_results or []
        self._add_failure = add_failure
        self._search_failure = search_failure
        self.added: list[dict] = []

    def add(self, *, messages, user_id, metadata, infer):  # noqa: ANN001
        if self._add_failure is not None:
            raise self._add_failure
        # The real client embeds before writing, so the double does too.
        self._embedder.embed(messages[0]["content"])
        self.added.append({"user_id": user_id, "metadata": metadata, "infer": infer})
        return {"results": [{"id": f"mem0-{len(self.added)}"}]}

    def search(self, query, *, top_k, filters, threshold):  # noqa: ANN001
        if self._search_failure is not None:
            raise self._search_failure
        self._embedder.embed(query)
        del top_k, filters, threshold
        return {"results": self._search_results}

    def delete(self, memory_id):  # noqa: ANN001
        del memory_id

    def delete_all(self, user_id=None):  # noqa: ANN001
        del user_id


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


def _confirm_one(service: MemoryService) -> str:
    proposal = service.propose(
        SUBJECT,
        MemoryCandidateDraft(
            category=MemoryCategory.EXPLICIT_DECISION_NOTE,
            value="Keep the lower drawdown choice for later comparison.",
            label="Lower drawdown choice",
            future_benefit="Argus can revisit the confirmed choice later.",
            provenance=(
                MemoryProvenance(
                    source_kind=MemorySourceKind.DECISION_NOTE,
                    source_id="decision-degradation-test",
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
        context=MemoryOperationContext.ORDINARY,
    )
    assert confirmation.created is True
    assert confirmation.record is not None
    return confirmation.record.id


@pytest.mark.parametrize(
    "failure",
    (
        MemoryEmbeddingUnavailable("timeout"),
        MemoryEmbeddingUnavailable("authentication_failed"),
        RuntimeError("vendor client exploded"),
    ),
)
def test_embedding_failure_at_search_falls_back_to_canonical_match(
    failure: Exception,
) -> None:
    """Catches a vectorization outage emptying recall instead of degrading it."""
    store = InMemoryCanonicalMemoryStore()
    record_id = _confirm_one(_service(store))
    embedder = _StubEmbedder(failure=failure)
    provider = Mem0MemoryProvider(
        embedder=embedder,
        memory=_Mem0Double(embedder=embedder),
    )

    retrieved = _service(store, provider).retrieve(
        SUBJECT,
        QUERY,
        MemoryUsePurpose.REVISIT_SAVED_DECISION,
    )

    assert [item.record.id for item in retrieved] == [record_id]
    assert retrieved[0].selection_reason is MemorySelectionReason.CANONICAL_TOKEN_MATCH


def test_vendor_search_failure_falls_back_to_canonical_match() -> None:
    """Catches an index outage failing the turn instead of degrading recall."""
    store = InMemoryCanonicalMemoryStore()
    record_id = _confirm_one(_service(store))
    embedder = _StubEmbedder()
    provider = Mem0MemoryProvider(
        embedder=embedder,
        memory=_Mem0Double(
            embedder=embedder,
            search_failure=RuntimeError("pgvector connection refused"),
        ),
    )

    retrieved = _service(store, provider).retrieve(
        SUBJECT,
        QUERY,
        MemoryUsePurpose.REVISIT_SAVED_DECISION,
    )

    assert [item.record.id for item in retrieved] == [record_id]
    assert retrieved[0].selection_reason is MemorySelectionReason.CANONICAL_TOKEN_MATCH


def test_indexing_failure_never_rolls_back_the_confirmed_memory() -> None:
    """Catches an index write failure costing the user a confirmed memory."""
    store = InMemoryCanonicalMemoryStore()
    embedder = _StubEmbedder()
    provider = Mem0MemoryProvider(
        embedder=embedder,
        memory=_Mem0Double(
            embedder=embedder,
            add_failure=RuntimeError("index write refused"),
        ),
    )

    record_id = _confirm_one(_service(store, provider))

    assert store.get_record(OWNER, record_id) is not None
    assert store.get_provider_ref(OWNER, record_id) is None


def test_successful_index_answers_semantically_rather_than_by_token_match() -> None:
    """Catches semantic recall silently never engaging."""
    store = InMemoryCanonicalMemoryStore()
    record_id = _confirm_one(_service(store))
    embedder = _StubEmbedder()
    provider = Mem0MemoryProvider(
        embedder=embedder,
        memory=_Mem0Double(
            embedder=embedder,
            search_results=[
                {
                    "id": "mem0-1",
                    "score": 0.77,
                    "metadata": {RECORD_ID_METADATA_KEY: record_id},
                }
            ],
        ),
    )

    retrieved = _service(store, provider).retrieve(
        SUBJECT,
        SEMANTIC_QUERY,
        MemoryUsePurpose.REVISIT_SAVED_DECISION,
    )

    assert [item.record.id for item in retrieved] == [record_id]
    assert retrieved[0].selection_reason is MemorySelectionReason.PROVIDER_RANKED


def test_token_match_alone_cannot_answer_the_semantic_query() -> None:
    """Pins the baseline the index improves on, so the previous test means something."""
    store = InMemoryCanonicalMemoryStore()
    _confirm_one(_service(store))

    retrieved = _service(store).retrieve(
        SUBJECT,
        SEMANTIC_QUERY,
        MemoryUsePurpose.REVISIT_SAVED_DECISION,
    )

    assert retrieved == ()


def test_unassessed_content_is_suppressed_before_storage_or_indexing() -> None:
    """Catches assessor failure failing open into stored, indexed content."""
    store = InMemoryCanonicalMemoryStore()
    embedder = _StubEmbedder()
    mem0 = _Mem0Double(embedder=embedder)
    service = _service(store, Mem0MemoryProvider(embedder=embedder, memory=mem0))

    # A failed classifier yields the default UNASSESSED assessment.
    proposal = service.propose(
        SUBJECT,
        MemoryCandidateDraft(
            category=MemoryCategory.EXPLICIT_DECISION_NOTE,
            value="Something the classifier could not reach a verdict on.",
            label="Unassessed note",
            future_benefit="Argus could revisit this later.",
            provenance=(
                MemoryProvenance(
                    source_kind=MemorySourceKind.DECISION_NOTE,
                    source_id="decision-unassessed",
                    source_version="1",
                ),
            ),
            trigger=MemoryProposalTrigger.EXPLICIT_REQUEST,
            sensitivity=SensitivityAssessment(),
        ),
        MemoryOperationContext.ORDINARY,
    )

    assert proposal is None
    assert store.list_records(OWNER) == ()
    assert mem0.added == []
