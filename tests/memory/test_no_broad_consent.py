"""Regression tests: no code path creates broad or implicit consent.

Enabling memory always names an explicit, non-empty category scope; the
settings model rejects enabled-with-empty-scope; the store exposes no
enable helper that could widen consent silently.
"""

from datetime import datetime, timezone

import pytest
from argus.memory.contracts import MemoryCategory
from argus.memory.policy import UserMemorySettings
from argus.memory.provider import DeterministicFakeMemoryProvider
from argus.memory.service import MemoryService, MemoryServiceConfig
from argus.memory.store import InMemoryCanonicalMemoryStore
from pydantic import ValidationError

NOW = datetime(2026, 7, 18, 3, 0, 0, tzinfo=timezone.utc)


def _service() -> tuple[MemoryService, InMemoryCanonicalMemoryStore]:
    store = InMemoryCanonicalMemoryStore()
    service = MemoryService(
        store=store,
        provider=DeterministicFakeMemoryProvider(),
        config=MemoryServiceConfig(globally_enabled=True),
        clock=lambda: NOW,
    )
    return service, store


class TestNoBroadConsent:
    def test_enable_requires_a_non_empty_scope(self) -> None:
        service, store = _service()
        with pytest.raises(ValueError):
            service.enable("user-a", [])
        settings = store.get_settings("user-a")
        assert settings.enabled is False
        assert settings.enabled_categories == []

    def test_enable_grants_exactly_the_requested_categories(self) -> None:
        service, store = _service()
        service.enable("user-a", [MemoryCategory.WORKFLOW_PREFERENCE])
        settings = store.get_settings("user-a")
        assert settings.enabled_categories == [MemoryCategory.WORKFLOW_PREFERENCE]
        for category in MemoryCategory:
            if category is MemoryCategory.WORKFLOW_PREFERENCE:
                assert settings.consents_to(category)
            else:
                assert not settings.consents_to(category)

    def test_settings_model_rejects_enabled_without_scope(self) -> None:
        with pytest.raises(ValidationError):
            UserMemorySettings(enabled=True, enabled_categories=[])

    def test_store_exposes_no_implicit_enable_helper(self) -> None:
        assert not hasattr(InMemoryCanonicalMemoryStore(), "set_enabled")

    def test_disable_remains_simple_and_invalidates_pending(self) -> None:
        service, store = _service()
        service.enable("user-a", [MemoryCategory.EXPLICIT_DECISION_NOTE])
        service.disable("user-a")
        settings = store.get_settings("user-a")
        assert settings.enabled is False
        assert settings.enabled_categories == []
        assert store.list_candidates("user-a") == []
