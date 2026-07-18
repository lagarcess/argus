"""Regression tests: the no-op/unavailable provider must not disable memory.

An absent provider abstains (``None``); the service then falls back to
bounded canonical matching. A live provider answering ``[]`` is a real
"no matches" answer and must NOT trigger the fallback.
"""

from datetime import datetime, timedelta, timezone

from argus.memory.contracts import (
    ConsentGrant,
    ConsentState,
    MemoryCategory,
    MemoryRecord,
    MemorySourceRef,
)
from argus.memory.policy import UserMemorySettings
from argus.memory.provider import (
    DeterministicFakeMemoryProvider,
    NoOpMemoryProvider,
)
from argus.memory.service import (
    ExplicitMemoryRequest,
    MemoryService,
    MemoryServiceConfig,
)
from argus.memory.store import InMemoryCanonicalMemoryStore

NOW = datetime(2026, 7, 18, 3, 0, 0, tzinfo=timezone.utc)


def _service(
    provider: object,
) -> tuple[MemoryService, InMemoryCanonicalMemoryStore]:
    store = InMemoryCanonicalMemoryStore()
    ticker = iter(range(1, 1000))
    service = MemoryService(
        store=store,
        provider=provider,  # type: ignore[arg-type]
        config=MemoryServiceConfig(globally_enabled=True),
        clock=lambda: NOW,
        id_factory=lambda: f"id-{next(ticker)}",
    )
    return service, store


def _confirm_preference(
    service: MemoryService,
    store: InMemoryCanonicalMemoryStore,
    text: str,
    label: str,
) -> str:
    # Back-date the cooldown mark so repeated seeding is not suppressed.
    store.mark_prompted(
        "user-a",
        MemoryCategory.PERSONALIZATION_PREFERENCE,
        NOW - timedelta(days=30),
    )
    result = service.propose_from_explicit_request(
        "user-a",
        ExplicitMemoryRequest(
            text=text,
            label=label,
            category=MemoryCategory.PERSONALIZATION_PREFERENCE,
        ),
    )
    assert result.candidate is not None, result
    record = service.confirm("user-a", result.candidate.id)
    assert record is not None
    return record.id


class TestNoOpProviderFallback:
    def test_noop_provider_does_not_mint_provider_refs(self) -> None:
        service, _store = _service(NoOpMemoryProvider())
        service.enable("user-a", [MemoryCategory.PERSONALIZATION_PREFERENCE])
        result = service.propose_from_explicit_request(
            "user-a",
            ExplicitMemoryRequest(
                text="Remember that I prefer SPY as my default benchmark",
                label="Prefers SPY benchmark",
                category=MemoryCategory.PERSONALIZATION_PREFERENCE,
            ),
        )
        assert result.candidate is not None
        record = service.confirm("user-a", result.candidate.id)
        assert record is not None
        assert record.provider_ref is None

    def test_noop_provider_falls_back_to_bounded_canonical_retrieval(
        self,
    ) -> None:
        service, store = _service(NoOpMemoryProvider())
        service.enable("user-a", [MemoryCategory.PERSONALIZATION_PREFERENCE])
        expected = _confirm_preference(
            service,
            store,
            "Remember that I prefer SPY as my default benchmark",
            "Prefers SPY benchmark",
        )
        _confirm_preference(
            service,
            store,
            "Prefers concise result summaries",
            "Concise summaries",
        )
        results = service.retrieve("user-a", "which benchmark do I prefer")
        assert [item.record.id for item in results] == [expected]
        assert all("canonical store matched" in item.why_selected for item in results)

    def test_noop_fallback_is_bounded(self) -> None:
        service, store = _service(NoOpMemoryProvider())
        service.enable("user-a", [MemoryCategory.PERSONALIZATION_PREFERENCE])
        for index in range(5):
            _confirm_preference(
                service,
                store,
                f"Benchmark preference variant {index} mentions benchmark",
                f"Benchmark note {index}",
            )
        results = service.retrieve("user-a", "benchmark")
        assert len(results) == 3  # default retrieval limit

    def test_delete_and_reset_work_without_provider_refs(self) -> None:
        service, store = _service(NoOpMemoryProvider())
        service.enable("user-a", [MemoryCategory.PERSONALIZATION_PREFERENCE])
        record_id = _confirm_preference(
            service,
            store,
            "Remember that I prefer SPY as my default benchmark",
            "Prefers SPY benchmark",
        )
        assert service.delete("user-a", record_id) is True
        _confirm_preference(
            service,
            store,
            "Prefers concise result summaries",
            "Concise summaries",
        )
        assert service.reset("user-a") == 1
        assert store.list_records("user-a") == []

    def test_live_provider_answering_empty_is_not_a_fallback(self) -> None:
        # A record the provider never indexed: the fake provider ANSWERS []
        # for it, so canonical fallback must not resurrect it.
        service, store = _service(DeterministicFakeMemoryProvider())
        store.set_settings(
            "user-a",
            UserMemorySettings(
                enabled=True,
                enabled_categories=[MemoryCategory.PERSONALIZATION_PREFERENCE],
            ),
        )
        store.add_record(
            MemoryRecord(
                id="mem-unindexed",
                user_id="user-a",
                category=MemoryCategory.PERSONALIZATION_PREFERENCE,
                value="Prefers SPY as the default benchmark",
                label="Prefers SPY benchmark",
                source_refs=[MemorySourceRef(kind="explicit_request", ref_id="req-1")],
                consent=ConsentGrant(state=ConsentState.CONFIRMED, decided_at=NOW),
                stored_reason="seeded outside the provider index",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        assert service.retrieve("user-a", "SPY benchmark") == []
