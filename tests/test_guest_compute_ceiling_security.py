"""Forced-reject proofs for unspoofable visitor keys and atomic claims.

These cases must fail on the pre-fix guest ceiling (X-Forwarded-For identity
and read-then-settle) and pass on this branch.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
from types import SimpleNamespace
from typing import Any

import pytest
from argus.api import state as api_state
from argus.api.chat.guest_compute_ceiling import claim_guest_compute_turn
from argus.api.client_ip import resolve_client_ip
from argus.api.guest_access import client_identity, visitor_key_for_request
from argus.domain.usage_limits import GUEST_COMPUTE_CEILING_RESOURCE
from argus.domain.visitor_usage import (
    guest_session_compute_key,
    read_memory_visitor_used,
    visitor_key_for,
)

from tests.test_allowance_accounting import client, mock_gateway
from tests.test_client_ip import _request
from tests.test_guest_compute_ceiling import GUEST_HEADERS, TURN, _guest


def test_spoofed_xff_from_one_session_hits_the_same_cap(
    mock_gateway, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ARGUS_GUEST_SESSION_DAILY_TURN_CEILING", "50")
    fake = _guest(mock_gateway, monkeypatch, turns_today=299)

    first = client.post(
        "/api/v1/chat/stream",
        json=TURN,
        headers={**GUEST_HEADERS, "X-Forwarded-For": "198.51.100.1"},
    )
    second = client.post(
        "/api/v1/chat/stream",
        json=TURN,
        headers={**GUEST_HEADERS, "X-Forwarded-For": "198.51.100.2"},
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 429
    assert second.json()["code"] == "too_many_requests"
    assert second.json()["detail"] == "Too many conversation turns today."
    assert fake.claims == 1
    assert fake.visitor_used == 300


def test_session_cap_applies_when_the_trusted_ip_changes(
    mock_gateway, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ARGUS_GUEST_SESSION_DAILY_TURN_CEILING", "1")
    fake = _guest(mock_gateway, monkeypatch, turns_today=0, session_used=0)

    first = client.post(
        "/api/v1/chat/stream",
        json=TURN,
        headers={**GUEST_HEADERS, "CF-Connecting-IP": "203.0.113.10"},
    )
    second = client.post(
        "/api/v1/chat/stream",
        json=TURN,
        headers={**GUEST_HEADERS, "CF-Connecting-IP": "203.0.113.20"},
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 429
    assert second.json()["detail"] == "Too many conversation turns today."
    assert fake.claims == 1
    assert fake.session_used == 1


def test_concurrent_claims_at_one_remaining_accept_exactly_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api_state, "supabase_gateway", None)
    api_state.store.visitor_usage_counters.clear()
    monkeypatch.setenv("ARGUS_GUEST_SESSION_DAILY_TURN_CEILING", "2")
    visitor_key = visitor_key_for("203.0.113.80")
    session_key = guest_session_compute_key("guest-session-concurrent")
    first = claim_guest_compute_turn(
        visitor_key=visitor_key, session_key=session_key
    )
    assert first.available is True

    barrier = Barrier(8)
    results: list[bool] = []
    results_lock = Lock()

    def _race() -> None:
        barrier.wait(timeout=5)
        admission = claim_guest_compute_turn(
            visitor_key=visitor_key, session_key=session_key
        )
        with results_lock:
            results.append(admission.available)

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(lambda _: _race(), range(8)))

    assert results.count(True) == 1
    assert results.count(False) == 7
    used = read_memory_visitor_used(
        api_state.store.visitor_usage_counters,
        visitor_key=visitor_key,
        resource=GUEST_COMPUTE_CEILING_RESOURCE,
        period="day",
    )
    assert used == 2
    api_state.store.visitor_usage_counters.clear()


def test_concurrent_endpoint_claims_reject_the_overshoot(
    mock_gateway, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ARGUS_GUEST_SESSION_DAILY_TURN_CEILING", "50")
    fake = _guest(mock_gateway, monkeypatch, turns_today=299)
    barrier = Barrier(6)

    def _turn(xff: str) -> int:
        barrier.wait(timeout=5)
        response = client.post(
            "/api/v1/chat/stream",
            json=TURN,
            headers={**GUEST_HEADERS, "X-Forwarded-For": xff},
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=6) as executor:
        statuses = list(
            executor.map(_turn, [f"198.51.100.{index}" for index in range(6)])
        )

    assert statuses.count(200) == 1
    assert statuses.count(429) == 5
    assert fake.claims == 1
    assert fake.visitor_used == 300


def test_client_identity_is_stable_across_spoofed_xff() -> None:
    first = _request(
        headers={"X-Forwarded-For": "198.51.100.1"},
        peer="192.0.2.10",
    )
    second = _request(
        headers={"X-Forwarded-For": "198.51.100.2"},
        peer="192.0.2.10",
    )
    assert client_identity(first) == client_identity(second) == "192.0.2.10"
    assert visitor_key_for_request(first) == visitor_key_for_request(second)
    assert resolve_client_ip(first) == "192.0.2.10"
