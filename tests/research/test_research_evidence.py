"""Metering locks: flat turn meter, classed ledger rows, honest ceiling."""

from __future__ import annotations

from typing import Any

import pytest
from argus.api import state as api_state
from argus.api.chat import research_evidence as evidence


class _LedgerGateway:
    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []

    def create_cost_ledger_entry(self, *, entry: dict[str, Any]) -> dict[str, Any]:
        self.entries.append(entry)
        return entry


@pytest.fixture
def memory_store(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(api_state, "supabase_gateway", None)
    api_state.store.usage_counters.clear()
    yield api_state.store
    api_state.store.usage_counters.clear()


def _research(
    capability_class: str = "fast_quote", cache_status: str = "miss"
) -> dict[str, Any]:
    return {
        "capability_class": capability_class,
        "shape": "fast",
        "usage": {
            "cache_status": cache_status,
            "cost_usd": 0.005,
            "invocations": 1,
            "latency_ms": 640,
        },
    }


def test_flag_off_never_reads_the_ceiling(monkeypatch, memory_store) -> None:
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "false")
    assert evidence.research_allowance_available("user-1") is True


def test_ceiling_read_is_not_a_charge(memory_store) -> None:
    assert evidence.research_allowance_available("user-1") is True
    assert memory_store.usage_counters == {}


def test_ceiling_trips_after_the_configured_daily_limit(
    monkeypatch, memory_store
) -> None:
    monkeypatch.setenv("ARGUS_RESEARCH_GLOBAL_DAILY_CEILING", "2")
    assert evidence.research_allowance_available("user-1") is True
    evidence.charge_research_ceiling()
    assert evidence.research_allowance_available("user-2") is True
    evidence.charge_research_ceiling()
    # The ceiling is shared: a third user meets the honest limit.
    assert evidence.research_allowance_available("user-3") is False


def test_provider_attempts_charge_and_cache_hits_do_not(
    monkeypatch, memory_store
) -> None:
    monkeypatch.setenv("ARGUS_RESEARCH_GLOBAL_DAILY_CEILING", "1")
    evidence.record_research_turn_evidence(
        research=_research(cache_status="hit"),
        user_id="user-1",
        conversation_id="c1",
        message_id="m1",
        request_id="r1",
    )
    assert evidence.research_allowance_available("user-1") is True
    evidence.record_research_turn_evidence(
        research=_research(cache_status="miss"),
        user_id="user-2",
        conversation_id="c2",
        message_id="m2",
        request_id="r2",
    )
    assert evidence.research_allowance_available("user-3") is False


def test_every_research_turn_records_its_capability_class(monkeypatch) -> None:
    gateway = _LedgerGateway()
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)

    for capability_class, cache_status in (
        ("fast_quote", "miss"),
        ("balanced_lookup", "hit"),
        ("thorough_research", "miss"),
        ("screening", "miss"),
        ("peer_expansion", "bypass"),
    ):
        evidence.record_research_turn_evidence(
            research=_research(capability_class, cache_status),
            user_id="user-1",
            conversation_id="c1",
            message_id=f"m-{capability_class}",
            request_id="r1",
        )

    recorded = [
        (e["task"], e["usage_metadata"]["capability_class"]) for e in gateway.entries
    ]
    assert recorded == [
        ("fast_quote", "fast_quote"),
        ("balanced_lookup", "balanced_lookup"),
        ("thorough_research", "thorough_research"),
        ("screening", "screening"),
        ("peer_expansion", "peer_expansion"),
    ]
    for entry in gateway.entries:
        assert entry["feature_area"] == "research_rail"
        assert entry["source"] == "research"
    # Cache hits and bypasses record class truth with zero billable quantity.
    by_message = {e["message_id"]: e for e in gateway.entries}
    assert by_message["m-balanced_lookup"]["billable_quantity"] == 0
    assert by_message["m-peer_expansion"]["billable_quantity"] == 0
    assert by_message["m-fast_quote"]["billable_quantity"] == 1


def test_ceiling_read_failure_fails_closed(monkeypatch) -> None:
    class ExplodingGateway:
        @property
        def client(self):
            raise RuntimeError("no database")

    monkeypatch.setattr(api_state, "supabase_gateway", ExplodingGateway())
    assert evidence.research_allowance_available("user-1") is False
