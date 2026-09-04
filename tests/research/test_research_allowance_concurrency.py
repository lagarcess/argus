"""Regression proof for concurrent visitor-keyed research admission."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest

from argus.api import state as api_state
from argus.api.chat import research_evidence as evidence
from argus.domain.usage_limits import GUEST_RESEARCH_ALLOWANCE

GUEST = "visitor:concurrent-research-guest"


def _research() -> dict[str, Any]:
    return {
        "capability_class": "fast_quote",
        "shape": "fast",
        "usage": {
            "cache_status": "miss",
            "cost_usd": 0.005,
            "invocations": 1,
            "latency_ms": 640,
        },
    }


@pytest.fixture
def guest_store(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(api_state, "supabase_gateway", None)
    api_state.store.usage_counters.clear()
    api_state.store.visitor_usage_counters.clear()
    yield api_state.store
    api_state.store.usage_counters.clear()
    api_state.store.visitor_usage_counters.clear()


def test_same_visitor_turns_cannot_both_spend_the_final_slot(guest_store) -> None:
    for _ in range(GUEST_RESEARCH_ALLOWANCE - 1):
        evidence.charge_research_ceiling(guest_visitor_key=GUEST)
    simultaneous = threading.Barrier(2)
    provider_calls: list[str] = []
    provider_calls_lock = threading.Lock()

    def run_turn(turn_id: str) -> bool:
        allowance = evidence.research_allowance_for_turn(
            "guest-user",
            guest_visitor_key=GUEST,
        )
        simultaneous.wait(timeout=5)
        if not allowance.available:
            return False
        with provider_calls_lock:
            provider_calls.append(turn_id)
        evidence.record_research_turn_evidence(
            research=_research(),
            user_id="guest-user",
            conversation_id=None,
            message_id=turn_id,
            request_id=turn_id,
            guest_visitor_key=GUEST,
        )
        return True

    with ThreadPoolExecutor(max_workers=2) as executor:
        admitted = list(executor.map(run_turn, ("turn-1", "turn-2")))

    assert admitted.count(True) == 1
    assert len(provider_calls) == 1
