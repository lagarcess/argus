"""Guest denial happens at the API gate, before any memory code can run.

Mirrors tests/memory/test_guest_isolation.py: the configured service explodes
on any attribute access, so a passing test proves the denied request never
touched settings, cooldowns, candidates, consent, records, providers, or
memory events, even transiently.
"""

from __future__ import annotations

from inspect import getmembers, isfunction
from typing import cast
from uuid import UUID

import pytest
from api_matrix import ENDPOINT_CALLS, GUEST_USER_ID
from argus.api.personalization_memory import configure_memory_service
from argus.memory.service import MemoryService


class _ExplodingMemoryService:
    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"MemoryService.{name} must not be touched")


def _configure_exploding_service() -> None:
    configure_memory_service(cast(MemoryService, _ExplodingMemoryService()))


def test_endpoint_matrix_covers_every_service_operation() -> None:
    """Catches an endpoint or service method added without the other."""
    public_methods = {
        name
        for name, member in getmembers(MemoryService, predicate=isfunction)
        if not name.startswith("_")
    }
    covered = {call.operation for call in ENDPOINT_CALLS if call.operation is not None}
    assert covered == public_methods


def test_guest_is_denied_before_the_memory_subsystem_while_flag_is_on(
    memory_api,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Denial comes from account kind, not from the availability flag."""
    UUID(GUEST_USER_ID)
    monkeypatch.setenv("ARGUS_ENABLE_PERSONALIZATION_MEMORY", "true")
    _configure_exploding_service()

    for call in ENDPOINT_CALLS:
        response = memory_api.client.request(
            call.method,
            call.path,
            json=call.json,
            headers=memory_api.guest_headers,
        )
        assert response.status_code == 403, (call.operation, response.text)
        assert response.json()["code"] == "account_conversion_required"


def test_guest_is_denied_before_availability_while_flag_is_off(
    memory_api,
) -> None:
    """A Guest sees the account gate first, never the availability gate."""
    _configure_exploding_service()

    for call in ENDPOINT_CALLS:
        response = memory_api.client.request(
            call.method,
            call.path,
            json=call.json,
            headers=memory_api.guest_headers,
        )
        assert response.status_code == 403, (call.operation, response.text)
        assert response.json()["code"] == "account_conversion_required"


def test_unauthenticated_requests_never_reach_the_memory_subsystem(
    memory_api,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_PERSONALIZATION_MEMORY", "true")
    _configure_exploding_service()

    for call in ENDPOINT_CALLS:
        response = memory_api.client.request(call.method, call.path, json=call.json)
        assert response.status_code == 401, (call.operation, response.text)
