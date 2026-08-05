"""Startup wiring constructs the service only when the flag allows it."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from argus.api import state as api_state
from argus.api.personalization_memory import (
    configure_memory_service,
    memory_service,
    start_personalization_memory,
    stop_personalization_memory,
)


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ARGUS_ENABLE_PERSONALIZATION_MEMORY", raising=False)
    configure_memory_service(None)
    yield
    configure_memory_service(None)


def _app() -> SimpleNamespace:
    return SimpleNamespace(state=SimpleNamespace())


def test_flag_off_constructs_nothing() -> None:
    app = _app()
    start_personalization_memory(app)
    assert memory_service() is None
    assert getattr(app.state, "personalization_memory_pool", None) is None


def test_memory_mode_wires_the_deterministic_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_PERSONALIZATION_MEMORY", "true")
    monkeypatch.setattr(api_state, "PERSISTENCE_MODE", "memory")
    app = _app()

    start_personalization_memory(app)
    assert memory_service() is not None

    stop_personalization_memory(app)
    assert memory_service() is None


def test_construction_failure_leaves_the_surface_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_PERSONALIZATION_MEMORY", "true")
    monkeypatch.setattr(api_state, "PERSISTENCE_MODE", "supabase")
    monkeypatch.setattr(api_state, "DATABASE_URL", "postgresql://invalid:1/nowhere")

    import psycopg_pool

    def _boom(*args: object, **kwargs: object) -> object:
        raise RuntimeError("pool refused")

    monkeypatch.setattr(psycopg_pool, "ConnectionPool", _boom)

    app = _app()
    start_personalization_memory(app)
    assert memory_service() is None
