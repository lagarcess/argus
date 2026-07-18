"""Retrieval tests: bounded set, provenance, why-selected, fail-open."""

from datetime import datetime, timezone

from argus.memory.contracts import MemoryCategory
from argus.memory.provider import DeterministicFakeMemoryProvider
from argus.memory.service import (
    ExplicitMemoryRequest,
    MemoryService,
    MemoryServiceConfig,
    SavedDecisionSource,
)
from argus.memory.store import InMemoryCanonicalMemoryStore

NOW = datetime(2026, 7, 18, 3, 0, 0, tzinfo=timezone.utc)


class SearchFailsProvider(DeterministicFakeMemoryProvider):
    """Projects fine but fails at search time."""

    def search(self, user_id: str, query: str, limit: int) -> list:
        raise RuntimeError("search down")


def _service(
    provider: object | None = None,
    retrieval_limit: int = 3,
) -> tuple[MemoryService, InMemoryCanonicalMemoryStore]:
    store = InMemoryCanonicalMemoryStore()
    ticker = iter(range(1, 1000))
    service = MemoryService(
        store=store,
        provider=provider or DeterministicFakeMemoryProvider(),
        config=MemoryServiceConfig(
            globally_enabled=True, retrieval_limit=retrieval_limit
        ),
        clock=lambda: NOW,
        id_factory=lambda: f"id-{next(ticker)}",
    )
    return service, store


def _confirm_memory(
    service: MemoryService,
    user_id: str,
    text: str,
    label: str,
) -> str:
    result = service.propose_from_explicit_request(
        user_id,
        ExplicitMemoryRequest(
            text=text,
            label=label,
            category=MemoryCategory.PERSONALIZATION_PREFERENCE,
            conversation_id="conv-1",
        ),
    )
    assert result.candidate is not None, result
    record = service.confirm(user_id, result.candidate.id)
    assert record is not None
    return record.id


def _seed_benchmark_memories(
    service: MemoryService, store: InMemoryCanonicalMemoryStore
) -> list[str]:
    store.set_enabled("user-a", True)
    ids = []
    specs = [
        ("Prefers SPY benchmark for equity ideas", "Prefers SPY benchmark"),
        ("Prefers BTC benchmark for crypto ideas", "Prefers BTC benchmark"),
        ("Wants drawdown explained before returns", "Drawdown first"),
        ("Benchmark comparisons should include SPY", "SPY comparisons"),
        ("Prefers concise result summaries", "Concise summaries"),
    ]
    for text, label in specs:
        # A shared cooldown would block seeding; widen the policy for setup.
        store.mark_prompted(
            "user-a",
            MemoryCategory.PERSONALIZATION_PREFERENCE,
            datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        ids.append(_confirm_memory(service, "user-a", text, label))
    return ids


class TestRetrieve:
    def test_returns_bounded_relevant_set_with_why_and_provenance(
        self,
    ) -> None:
        service, store = _seed_service()
        results = service.retrieve("user-a", "which benchmark do I prefer")
        assert 0 < len(results) <= 3
        for item in results:
            assert item.why_selected
            assert item.provenance == item.record.source_refs

    def test_retrieval_is_deterministic(self) -> None:
        service, _ = _seed_service()
        first = [r.record.id for r in service.retrieve("user-a", "benchmark")]
        second = [r.record.id for r in service.retrieve("user-a", "benchmark")]
        assert first == second

    def test_owner_scoping_holds(self) -> None:
        service, _ = _seed_service()
        assert service.retrieve("user-b", "benchmark") == []

    def test_disabled_user_retrieves_nothing(self) -> None:
        service, store = _seed_service()
        store.set_enabled("user-a", False)
        assert service.retrieve("user-a", "benchmark") == []

    def test_globally_disabled_service_retrieves_nothing(self) -> None:
        service, store = _seed_service()
        disabled = MemoryService(
            store=store,
            provider=DeterministicFakeMemoryProvider(),
            config=MemoryServiceConfig(globally_enabled=False),
            clock=lambda: NOW,
        )
        assert disabled.retrieve("user-a", "benchmark") == []

    def test_provider_search_failure_degrades_to_canonical_matching(
        self,
    ) -> None:
        service, _ = _seed_service(provider=SearchFailsProvider())
        results = service.retrieve("user-a", "SPY benchmark")
        assert results
        assert all("provider" in item.why_selected for item in results)

    def test_retrieval_updates_last_used_at(self) -> None:
        service, store = _seed_service()
        results = service.retrieve("user-a", "benchmark")
        assert results
        stored = store.get_record("user-a", results[0].record.id)
        assert stored is not None
        assert stored.last_used_at == NOW

    def test_disabled_record_is_not_retrieved(self) -> None:
        service, store = _seed_service()
        target = service.retrieve("user-a", "SPY benchmark")[0].record
        store.replace_record(target.model_copy(update={"enabled": False}))
        remaining = service.retrieve("user-a", "SPY benchmark")
        assert target.id not in [item.record.id for item in remaining]


def _seed_service(
    provider: object | None = None,
) -> tuple[MemoryService, InMemoryCanonicalMemoryStore]:
    service, store = _service(provider=provider)
    _seed_benchmark_memories(service, store)
    return service, store


class TestExplain:
    def test_explain_returns_reason_provenance_and_consent(self) -> None:
        service, store = _service()
        store.set_enabled("user-a", True)
        result = service.propose_from_saved_decision(
            "user-a",
            SavedDecisionSource(
                decision_note_id="dn-1",
                evidence_artifact_id="ev-1",
                decision_state="promising",
                label="ETH RSI idea promising",
            ),
        )
        assert result.candidate is not None
        record = service.confirm("user-a", result.candidate.id)
        assert record is not None
        explanation = service.explain("user-a", record.id)
        assert explanation is not None
        assert explanation.stored_reason == record.stored_reason
        assert explanation.provenance == record.source_refs
        assert explanation.consent_version == record.consent.version

    def test_explain_is_owner_scoped(self) -> None:
        service, store = _service()
        store.set_enabled("user-a", True)
        assert service.explain("user-b", "mem-unknown") is None
