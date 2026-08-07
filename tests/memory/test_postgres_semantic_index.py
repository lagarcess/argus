"""Real-Postgres proof for the derivative semantic memory index.

Runs the real Mem0 library against a real pgvector table: real SQL, real
distance ranking, real per-owner scoping. Only the vendor embedding call is
substituted, by a deterministic bag-of-words vector, so the check is free,
repeatable, and still exercises genuine semantic overlap rather than token
equality.
"""

from __future__ import annotations

import hashlib
import math
import os
from collections.abc import Iterator
from datetime import datetime, timezone

import pytest

DSN = os.getenv("ARGUS_DISPOSABLE_DATABASE_URL", "").strip()
pytestmark = pytest.mark.skipif(
    not DSN,
    reason="ARGUS_DISPOSABLE_DATABASE_URL is not configured",
)
pytest.importorskip("psycopg")
pytest.importorskip("mem0")

from argus.api.personalization_memory_index import (  # noqa: E402
    Mem0MemoryProvider,
)
from argus.llm.memory_embedding import (  # noqa: E402
    EmbeddingResult,
    EmbeddingUsage,
)
from argus.memory.contracts import (  # noqa: E402
    MemoryCategory,
    MemoryConsentActionReceipt,
    MemoryProvenance,
    MemoryRecord,
    MemorySourceKind,
    ProviderReconciliationStatus,
)
from argus.memory.provider import ProviderSearchStatus  # noqa: E402
from argus.memory.subject import RegisteredMemoryOwner  # noqa: E402

DIMENSIONS = 32
COLLECTION = "argus_memory_vectors_test"
OWNER_A_ID = "3f8a1d02-6c4b-4a7e-9d51-2b0e7c3a5f18"
OWNER_B_ID = "9c2f5b74-1e83-4d06-a5f9-70d8b4e21c6a"
OWNER_A = RegisteredMemoryOwner(owner_id=OWNER_A_ID)
OWNER_B = RegisteredMemoryOwner(owner_id=OWNER_B_ID)
NOW = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)

ETH_ID = "11111111-1111-4111-8111-111111111111"
SPY_ID = "22222222-2222-4222-8222-222222222222"
OTHER_ID = "33333333-3333-4333-8333-333333333333"

ETH_VALUE = "Rejected the higher drawdown ETH variant and kept the steadier one."
SPY_VALUE = "Always compare equity ideas against the SPY benchmark."


class _DeterministicEmbedder:
    """Bag-of-words unit vector: overlapping wording really does rank higher."""

    dimensions = DIMENSIONS

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * DIMENSIONS
        for token in text.casefold().split():
            slot = int(hashlib.sha256(token.encode()).hexdigest(), 16) % DIMENSIONS
            vector[slot] += 1.0
        norm = math.sqrt(sum(component * component for component in vector)) or 1.0
        return [component / norm for component in vector]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return self.embed_batch_with_usage(texts).vectors

    def embed_batch_with_usage(self, texts: list[str]) -> EmbeddingResult:
        return EmbeddingResult(
            [self.embed(text) for text in texts],
            EmbeddingUsage(total_tokens=7),
        )


def _record(owner_id: str, *, record_id: str, label: str, value: str) -> MemoryRecord:
    scope = frozenset({MemoryCategory.EXPLICIT_DECISION_NOTE})
    candidate_id = f"candidate-{record_id}"
    provenance = MemoryProvenance(
        source_kind=MemorySourceKind.DECISION_NOTE,
        source_id=f"decision-{record_id}",
        source_version="1",
    )
    return MemoryRecord(
        id=record_id,
        owner_id=owner_id,
        candidate_id=candidate_id,
        category=MemoryCategory.EXPLICIT_DECISION_NOTE,
        label=label,
        value=value,
        provenance=provenance,
        provenance_refs=(provenance,),
        consent_receipt=MemoryConsentActionReceipt(
            id=f"receipt-{record_id}",
            action="candidate_confirmation",
            owner_id=owner_id,
            candidate_id=candidate_id,
            requested_scope=scope,
            granted_scope=scope,
            effective_scope=scope,
            recorded_at=NOW,
            idempotency_key=f"key-{record_id}",
        ),
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.fixture
def provider() -> Iterator[Mem0MemoryProvider]:
    from psycopg_pool import ConnectionPool

    pool = ConnectionPool(DSN, min_size=1, max_size=4, open=True)
    with pool.connection() as connection:
        connection.execute(f"drop table if exists {COLLECTION}")
    try:
        yield Mem0MemoryProvider(
            embedder=_DeterministicEmbedder(),
            connection_pool=pool,
            collection_name=COLLECTION,
        )
    finally:
        with pool.connection() as connection:
            connection.execute(f"drop table if exists {COLLECTION}")
        pool.close()


def _seed(provider: Mem0MemoryProvider) -> dict[str, str]:
    refs: dict[str, str] = {}
    for owner, record in (
        (
            OWNER_A,
            _record(
                OWNER_A_ID,
                record_id=ETH_ID,
                label="ETH drawdown decision",
                value=ETH_VALUE,
            ),
        ),
        (
            OWNER_A,
            _record(
                OWNER_A_ID,
                record_id=SPY_ID,
                label="SPY benchmark preference",
                value=SPY_VALUE,
            ),
        ),
        (
            OWNER_B,
            _record(
                OWNER_B_ID, record_id=OTHER_ID, label="Another account", value=ETH_VALUE
            ),
        ),
    ):
        result = provider.project(owner, record)
        assert result.status is ProviderReconciliationStatus.SYNCHRONIZED
        assert result.provider_ref is not None
        refs[record.id] = result.provider_ref
    return refs


def test_projection_and_search_rank_the_right_memory_first(
    provider: Mem0MemoryProvider,
) -> None:
    """Catches the index failing to rank the relevant memory against real SQL."""
    _seed(provider)

    hits = provider.search(OWNER_A, "rejected higher drawdown ETH variant", 3).hits

    assert hits
    assert hits[0].record_id == ETH_ID
    assert hits[0].score > 0


def test_search_never_crosses_account_boundaries(
    provider: Mem0MemoryProvider,
) -> None:
    """Catches one account's query ranking another account's identical memory."""
    _seed(provider)

    a_hits = [hit.record_id for hit in provider.search(OWNER_A, ETH_VALUE, 5).hits]
    b_hits = [hit.record_id for hit in provider.search(OWNER_B, ETH_VALUE, 5).hits]

    assert OTHER_ID not in a_hits
    assert b_hits == [OTHER_ID]


def test_delete_removes_only_the_targeted_memory(
    provider: Mem0MemoryProvider,
) -> None:
    """Catches a delete leaving the memory searchable or clearing too much."""
    refs = _seed(provider)

    provider.delete(OWNER_A, refs[ETH_ID])

    remaining = [hit.record_id for hit in provider.search(OWNER_A, ETH_VALUE, 5).hits]
    assert ETH_ID not in remaining
    assert [hit.record_id for hit in provider.search(OWNER_A, SPY_VALUE, 5).hits] == [
        SPY_ID
    ]


def test_reset_clears_one_account_and_leaves_the_others(
    provider: Mem0MemoryProvider,
) -> None:
    """Catches a reset spilling past the account that asked for it."""
    _seed(provider)

    provider.reset(OWNER_A)

    assert provider.search(OWNER_A, ETH_VALUE, 5).hits == ()
    assert provider.search(OWNER_A, SPY_VALUE, 5).hits == ()
    assert [hit.record_id for hit in provider.search(OWNER_B, ETH_VALUE, 5).hits] == [
        OTHER_ID
    ]


def test_the_index_stores_no_row_for_a_refused_record(
    provider: Mem0MemoryProvider,
) -> None:
    """Catches the gate being bypassed once a real database is behind it."""
    foreign = _record(
        OWNER_B_ID,
        record_id=OTHER_ID,
        label="Another account",
        value=ETH_VALUE,
    )

    result = provider.project(OWNER_A, foreign)

    assert result.status is ProviderReconciliationStatus.NOT_APPLICABLE
    assert provider.search(OWNER_A, ETH_VALUE, 5).hits == ()


def test_an_owner_with_no_rows_cannot_speak(provider: Mem0MemoryProvider) -> None:
    """Catches a never-projected owner being answered as authoritatively empty."""
    answer = provider.search(OWNER_A, "anything at all", 3)

    assert answer.status is ProviderSearchStatus.UNAVAILABLE
    assert answer.hits == ()


def test_a_populated_owner_answers_on_its_own_authority(
    provider: Mem0MemoryProvider,
) -> None:
    """Catches a real populated index being downgraded to unavailable.

    Same provider, same database, same query. The only difference is whether
    the owner has rows, which is exactly the distinction the answer carries.
    The hit count is not asserted: the test embedder is a small hashed vector,
    so its similarity floor is an artifact of the double, not the product.
    """
    query = "zzzz qqqq vvvv unrelated tokens"
    before = provider.search(OWNER_A, query, 3)

    _seed(provider)
    after = provider.search(OWNER_A, query, 3)

    assert before.status is ProviderSearchStatus.UNAVAILABLE
    assert after.status is ProviderSearchStatus.ANSWERED
