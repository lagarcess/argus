"""Exposure requires the flag AND an admin or developer allowlist role.

An ordinary registered 'user' role sees exactly the flag-off state, so the
surface stays invisible to the public even in a flag-on environment. Guests
never reach the role lookup at all.
"""

from __future__ import annotations

from typing import cast

import pytest
from api_matrix import ENDPOINT_CALLS
from argus.api.personalization_memory import configure_memory_service
from argus.memory.service import MemoryService
from argus.memory.store import InMemoryCanonicalMemoryStore


class _ExplodingMemoryService:
    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"MemoryService.{name} must not be touched")


@pytest.fixture
def flag_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_PERSONALIZATION_MEMORY", "true")


@pytest.mark.parametrize("role", ["user", None])
def test_non_developer_roles_see_the_flag_off_state(
    memory_api,
    flag_on,
    role: str | None,
) -> None:
    memory_api.gateway.private_alpha_role_for_email.return_value = role
    configure_memory_service(cast(MemoryService, _ExplodingMemoryService()))

    for call in ENDPOINT_CALLS:
        response = memory_api.client.request(
            call.method,
            call.path,
            json=call.json,
            headers=memory_api.registered_headers,
        )
        assert response.status_code == 404, (call.operation, role, response.text)
        assert response.json()["code"] == "personalization_memory_unavailable"


@pytest.mark.parametrize("role", ["admin", "developer"])
def test_admin_and_developer_roles_pass_the_gate(
    memory_api,
    flag_on,
    role: str,
) -> None:
    memory_api.gateway.private_alpha_role_for_email.return_value = role
    configure_memory_service(MemoryService(store=InMemoryCanonicalMemoryStore()))

    response = memory_api.client.post(
        "/api/v1/memory/enable",
        json={"categories": ["workflow_preference"]},
        headers=memory_api.registered_headers,
    )
    assert response.status_code == 200, response.text


def test_role_lookup_failure_fails_closed(memory_api, flag_on) -> None:
    memory_api.gateway.private_alpha_role_for_email.side_effect = RuntimeError(
        "allowlist unavailable"
    )
    configure_memory_service(cast(MemoryService, _ExplodingMemoryService()))

    response = memory_api.client.get(
        "/api/v1/memory/records",
        headers=memory_api.registered_headers,
    )
    assert response.status_code == 404, response.text
    assert response.json()["code"] == "personalization_memory_unavailable"


def test_admin_role_without_flag_stays_unavailable(memory_api) -> None:
    memory_api.gateway.private_alpha_role_for_email.return_value = "admin"
    configure_memory_service(cast(MemoryService, _ExplodingMemoryService()))

    response = memory_api.client.get(
        "/api/v1/memory/records",
        headers=memory_api.registered_headers,
    )
    assert response.status_code == 404, response.text
    assert response.json()["code"] == "personalization_memory_unavailable"


def test_guests_never_reach_the_role_lookup(memory_api, flag_on) -> None:
    memory_api.gateway.private_alpha_role_for_email.reset_mock()
    configure_memory_service(cast(MemoryService, _ExplodingMemoryService()))

    for call in ENDPOINT_CALLS:
        response = memory_api.client.request(
            call.method,
            call.path,
            json=call.json,
            headers=memory_api.guest_headers,
        )
        assert response.status_code == 403, (call.operation, response.text)

    availability = memory_api.client.get(
        "/api/v1/memory/availability",
        headers=memory_api.guest_headers,
    )
    assert availability.status_code == 403
    assert memory_api.gateway.private_alpha_role_for_email.call_count == 0


def test_availability_probe_reports_exposure_truth(
    memory_api,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_memory_service(MemoryService(store=InMemoryCanonicalMemoryStore()))

    flag_off = memory_api.client.get(
        "/api/v1/memory/availability",
        headers=memory_api.registered_headers,
    )
    assert flag_off.status_code == 200
    assert flag_off.json() == {"available": False}

    monkeypatch.setenv("ARGUS_ENABLE_PERSONALIZATION_MEMORY", "true")
    memory_api.gateway.private_alpha_role_for_email.return_value = "user"
    hidden = memory_api.client.get(
        "/api/v1/memory/availability",
        headers=memory_api.registered_headers,
    )
    assert hidden.json() == {"available": False}

    memory_api.gateway.private_alpha_role_for_email.return_value = "developer"
    exposed = memory_api.client.get(
        "/api/v1/memory/availability",
        headers=memory_api.registered_headers,
    )
    assert exposed.json() == {"available": True}
