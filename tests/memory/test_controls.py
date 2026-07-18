"""User-control tests: edit, delete, enable/disable, reset."""

from datetime import datetime, timedelta, timezone

import pytest
from argus.memory.contracts import MemoryCategory
from argus.memory.provider import DeterministicFakeMemoryProvider
from argus.memory.service import (
    ExplicitMemoryRequest,
    MemoryService,
    MemoryServiceConfig,
    ProposalStatus,
)
from argus.memory.store import InMemoryCanonicalMemoryStore
from pydantic import ValidationError

NOW = datetime(2026, 7, 18, 3, 0, 0, tzinfo=timezone.utc)


class DeleteFailsProvider(DeterministicFakeMemoryProvider):
    def delete(self, user_id: str, provider_ref: str) -> None:
        raise RuntimeError("delete down")

    def reset(self, user_id: str) -> None:
        raise RuntimeError("reset down")


def _service(
    provider: DeterministicFakeMemoryProvider | None = None,
) -> tuple[MemoryService, InMemoryCanonicalMemoryStore, DeterministicFakeMemoryProvider]:
    store = InMemoryCanonicalMemoryStore()
    fake = provider or DeterministicFakeMemoryProvider()
    ticker = iter(range(1, 1000))
    service = MemoryService(
        store=store,
        provider=fake,
        config=MemoryServiceConfig(globally_enabled=True),
        clock=lambda: NOW,
        id_factory=lambda: f"id-{next(ticker)}",
    )
    return service, store, fake


def _confirmed(
    service: MemoryService,
    store: InMemoryCanonicalMemoryStore,
    user_id: str = "user-a",
) -> str:
    service.enable(user_id)
    store.mark_prompted(
        user_id,
        MemoryCategory.PERSONALIZATION_PREFERENCE,
        NOW - timedelta(days=30),
    )
    proposed = service.propose_from_explicit_request(
        user_id,
        ExplicitMemoryRequest(
            text="Remember that I prefer SPY as my default benchmark",
            label="Prefers SPY benchmark",
            category=MemoryCategory.PERSONALIZATION_PREFERENCE,
            conversation_id="conv-1",
        ),
    )
    assert proposed.status is ProposalStatus.PROPOSED
    assert proposed.candidate is not None
    record = service.confirm(user_id, proposed.candidate.id)
    assert record is not None
    return record.id


class TestEdit:
    def test_edit_updates_value_label_and_timestamp(self) -> None:
        service, store, fake = _service()
        record_id = _confirmed(service, store)
        updated = service.edit(
            "user-a",
            record_id,
            value="Prefers QQQ as the default benchmark",
            label="Prefers QQQ benchmark",
        )
        assert updated is not None
        assert updated.value == "Prefers QQQ as the default benchmark"
        assert updated.label == "Prefers QQQ benchmark"
        stored = store.get_record("user-a", record_id)
        assert stored is not None
        assert stored.value == updated.value

    def test_edit_reprojects_to_the_provider(self) -> None:
        service, store, _fake = _service()
        record_id = _confirmed(service, store)
        service.edit(
            "user-a",
            record_id,
            value="Prefers QQQ as the default benchmark",
            label="Prefers QQQ benchmark",
        )
        results = service.retrieve("user-a", "QQQ benchmark")
        assert [item.record.id for item in results] == [record_id]

    def test_edit_is_owner_scoped(self) -> None:
        service, store, _fake = _service()
        record_id = _confirmed(service, store)
        assert service.edit("user-b", record_id, value="hijack") is None

    def test_invalid_edits_never_enter_the_canonical_record(self) -> None:
        service, store, _fake = _service()
        record_id = _confirmed(service, store)
        before = store.get_record("user-a", record_id)
        assert before is not None
        with pytest.raises(ValidationError):
            service.edit("user-a", record_id, value="")
        with pytest.raises(ValidationError):
            service.edit("user-a", record_id, value="   ")
        with pytest.raises(ValidationError):
            service.edit("user-a", record_id, label="")
        with pytest.raises(ValidationError):
            service.edit("user-a", record_id, label="  \t ")
        with pytest.raises(ValidationError):
            service.edit("user-a", record_id, label="x" * 121)
        assert store.get_record("user-a", record_id) == before

    def test_edit_normalizes_surrounding_whitespace(self) -> None:
        service, store, _fake = _service()
        record_id = _confirmed(service, store)
        updated = service.edit("user-a", record_id, label="  Prefers QQQ benchmark  ")
        assert updated is not None
        assert updated.label == "Prefers QQQ benchmark"


class TestDelete:
    def test_delete_removes_canonical_and_provider_state(self) -> None:
        service, store, fake = _service()
        record_id = _confirmed(service, store)
        assert service.delete("user-a", record_id) is True
        assert store.get_record("user-a", record_id) is None
        assert fake.indexed_refs("user-a") == set()
        assert service.retrieve("user-a", "SPY benchmark") == []

    def test_delete_survives_provider_failure(self) -> None:
        service, store, _fake = _service(provider=DeleteFailsProvider())
        record_id = _confirmed(service, store)
        assert service.delete("user-a", record_id) is True
        assert store.get_record("user-a", record_id) is None

    def test_delete_is_owner_scoped(self) -> None:
        service, store, _fake = _service()
        record_id = _confirmed(service, store)
        assert service.delete("user-b", record_id) is False
        assert store.get_record("user-a", record_id) is not None


class TestDisableAndReset:
    def test_disable_stops_proposals_and_retrieval(self) -> None:
        service, store, _fake = _service()
        _confirmed(service, store)
        service.disable("user-a")
        assert service.retrieve("user-a", "SPY benchmark") == []
        proposed = service.propose_from_explicit_request(
            "user-a",
            ExplicitMemoryRequest(
                text="Remember I like BTC",
                label="Likes BTC",
                category=MemoryCategory.PERSONALIZATION_PREFERENCE,
            ),
        )
        assert proposed.status is ProposalStatus.REJECTED_POLICY

    def test_reset_removes_only_that_users_memories(self) -> None:
        service, store, fake = _service()
        _confirmed(service, store, "user-a")
        keep_id = _confirmed(service, store, "user-b")
        removed = service.reset("user-a")
        assert removed == 1
        assert store.list_records("user-a") == []
        assert fake.indexed_refs("user-a") == set()
        assert store.get_record("user-b", keep_id) is not None
        assert fake.indexed_refs("user-b") != set()

    def test_reset_survives_provider_failure(self) -> None:
        service, store, _fake = _service(provider=DeleteFailsProvider())
        _confirmed(service, store)
        assert service.reset("user-a") == 1
        assert store.list_records("user-a") == []

    def test_enable_then_disable_round_trip_is_explicit(self) -> None:
        service, store, _fake = _service()
        assert store.get_settings("user-a").enabled is False
        service.enable("user-a")
        assert store.get_settings("user-a").enabled is True
        service.disable("user-a")
        assert store.get_settings("user-a").enabled is False
