"""Section 11b locks: one router, one cache, one meter, one provider layer.

Discovery's asset-finding is an operation of the rail. These tests pin the
absorption: the rail classifier owns question shape for both entries, a
comparison of named assets reaches grounded research from a typed discovery
act, find turns cache and meter through the research scheme, and the routing
classification can never be starved by the turn-call corridor.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import pytest
from argus.agent_runtime import research_answer as ra
from argus.agent_runtime import research_grounded as grounded
from argus.agent_runtime import turn_execution
from argus.agent_runtime.discovery import composer as composer_module
from argus.agent_runtime.discovery.contracts import (
    DiscoveryExtraction,
    ExtractedCandidate,
)
from argus.agent_runtime.stages.interpret_types import (
    AssetDiscoveryRequest,
    InterpretDecision,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import (
    ResponseProfile,
    RunState,
    StrategySummary,
    UserState,
)
from argus.domain.research.perplexity_agent import PerplexityAgentClient
from argus.domain.research.search import (
    SearchResultPacket,
    sanitize_search_result,
)
from argus.domain.research.search import selection as selection_module

from tests.research.conftest import RecordingTransport, agent_response

USER = UserState(user_id="rail-user", language_preference="en")


@dataclass(frozen=True)
class _Asset:
    canonical_symbol: str
    asset_class: str
    name: str = ""


def _interpretation() -> StructuredInterpretation:
    return StructuredInterpretation(
        intent="unsupported_or_out_of_scope",
        task_relation="new_task",
        user_goal_summary="question",
        semantic_turn_act="asset_discovery",
        requires_clarification=False,
        candidate_strategy_draft=StrategySummary(),
    )


def _decision(
    *,
    relationship: str = "comparison",
    category_description: str | None = None,
    anchor_symbols: list[str] | None = None,
    needs_current_facts: bool = True,
) -> InterpretDecision:
    return InterpretDecision(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="discovery",
        confidence=0.9,
        effective_response_profile=ResponseProfile(
            effective_tone="friendly",
            effective_verbosity="medium",
            effective_expertise_mode="beginner",
        ),
        semantic_turn_act="asset_discovery",
        asset_discovery=AssetDiscoveryRequest(
            relationship=relationship,
            category_description=category_description,
            anchor_symbols=anchor_symbols or [],
            asset_class_hint="equity",
            needs_current_facts=needs_current_facts,
        ),
    )


def _state(message: str, *, research_allowance: bool = True) -> RunState:
    state = RunState.new(current_user_message=message, recent_thread_history=[])
    state.research_allowance_available = research_allowance
    return state


def _search_packet() -> SearchResultPacket:
    results = [
        sanitize_search_result(
            title=f"Streaming rivals {index}",
            url=f"https://example.com/{index}",
            snippet="CrowdStrike leads the segment.",
            source_date="2026-08-01",
        )
        for index in range(3)
    ]
    return SearchResultPacket(
        results=[result for result in results if result is not None],
        retrieved_at=datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc),
        latency_ms=640,
        provider_id="perplexity_direct",
        cost_usd=0.005,
    )


class _FakeSearchProvider:
    def __init__(self, packet: SearchResultPacket) -> None:
        self._packet = packet
        self.calls: list[str] = []

    def search(self, query: str, *, max_results: int, timeout_seconds: float):
        self.calls.append(query)
        return self._packet


def _wire_find(
    monkeypatch: pytest.MonkeyPatch, *, provider: _FakeSearchProvider
) -> None:
    monkeypatch.setattr(
        selection_module,
        "search_provider_for_config",
        lambda **kwargs: provider,
        raising=True,
    )

    async def _fake_extract(**kwargs: Any) -> DiscoveryExtraction:
        return DiscoveryExtraction(
            candidates=[
                ExtractedCandidate(
                    name="CrowdStrike",
                    symbol_guess="CRWD",
                    reason_text="Named as a leading vendor.",
                    source_indices=[0],
                )
            ]
        )

    monkeypatch.setattr(composer_module, "extract_candidates", _fake_extract)
    monkeypatch.setattr(composer_module, "name_candidates", _fake_extract)

    async def _fake_voice(**kwargs: Any) -> str:
        return "Here is what I verified."

    monkeypatch.setattr(composer_module, "_voiced_discovery_response", _fake_voice)

    def _resolve(symbol: str, **_: Any) -> _Asset:
        cleaned = symbol.strip().upper()
        if cleaned != "CRWD":
            raise ValueError(f"unknown symbol {cleaned}")
        return _Asset("CRWD", "equity", name="CrowdStrike Holdings")

    monkeypatch.setattr(composer_module, "resolve_asset", _resolve)


def _classify(monkeypatch: pytest.MonkeyPatch, **fields: Any) -> None:
    async def classify(**_kwargs: Any) -> ra.ResearchQueryExtraction:
        return ra.ResearchQueryExtraction(**fields)

    monkeypatch.setattr(ra, "_classify_research_question", classify)


def test_named_comparison_on_a_discovery_act_reaches_grounded_research(
    monkeypatch,
) -> None:
    """The defect section 11b names: 'Compare Costco against Walmart and
    Target' arrives as a typed discovery act, and the rail classifier, not
    the act taxonomy, decides it is grounded cross-company research."""
    _classify(
        monkeypatch,
        question_kind="cross_company",
        symbols=["NFLX", "AAPL"],
    )
    result = asyncio.run(
        ra.discovery_turn_stage_result(
            interpretation=_interpretation(),
            decision=_decision(anchor_symbols=["NFLX"]),
            state=_state("Compare Netflix against Apple"),
            user=USER,
        )
    )
    assert result is not None
    # A thorough job request is the grounded-research artifact; the discovery
    # sidecar never appears because the find operation never ran.
    assert "research_job_request" in result.stage_patch
    assert "discovery" not in result.stage_patch


def test_discovery_shaped_turn_runs_the_find_operation_with_the_typed_request(
    monkeypatch,
) -> None:
    _classify(monkeypatch, question_kind="find_assets", symbols=[])
    provider = _FakeSearchProvider(_search_packet())
    _wire_find(monkeypatch, provider=provider)

    result = asyncio.run(
        ra.discovery_turn_stage_result(
            interpretation=_interpretation(),
            decision=_decision(
                relationship="category",
                category_description="cybersecurity stocks",
            ),
            state=_state("Find me cybersecurity stocks"),
            user=USER,
        )
    )
    assert result is not None
    assert provider.calls, "the find operation must run the search"
    discovery = result.stage_patch["discovery"]
    assert [c["symbol"] for c in discovery["candidates"]] == ["CRWD"]
    research = result.stage_patch["research"]
    assert research["shape"] == "find"
    assert research["capability_class"] == "screening"
    assert research["usage"]["cache_status"] == "miss"
    assert research["peers"][0]["symbol"] == "CRWD"
    assert research["memory"]["open_thread"]["category"] == "cybersecurity stocks"


def test_classifier_failure_never_loses_a_discovery_turn(monkeypatch) -> None:
    async def broken(**_kwargs: Any):
        return None

    monkeypatch.setattr(ra, "_classify_research_question", broken)
    provider = _FakeSearchProvider(_search_packet())
    _wire_find(monkeypatch, provider=provider)

    result = asyncio.run(
        ra.discovery_turn_stage_result(
            interpretation=_interpretation(),
            decision=_decision(
                relationship="category",
                category_description="cybersecurity stocks",
            ),
            state=_state("Find me cybersecurity stocks"),
            user=USER,
        )
    )
    assert result is not None
    assert result.stage_patch["discovery"]["candidates"]


def test_find_turns_share_the_research_cache_across_users(monkeypatch) -> None:
    """One cache: the second identical find question consumes no provider
    search, whoever asks it."""
    _classify(monkeypatch, question_kind="find_assets", symbols=[])
    provider = _FakeSearchProvider(_search_packet())
    _wire_find(monkeypatch, provider=provider)
    decision = _decision(
        relationship="category", category_description="cybersecurity stocks"
    )

    first = asyncio.run(
        ra.discovery_turn_stage_result(
            interpretation=_interpretation(),
            decision=decision,
            state=_state("Find me cybersecurity stocks"),
            user=USER,
        )
    )
    second = asyncio.run(
        ra.discovery_turn_stage_result(
            interpretation=_interpretation(),
            decision=decision,
            state=_state("Find me cybersecurity stocks"),
            user=UserState(user_id="someone-else", language_preference="en"),
        )
    )
    assert first is not None and second is not None
    assert len(provider.calls) == 1, "the shared cache must absorb the second search"
    assert second.stage_patch["research"]["usage"]["cache_status"] == "hit"
    assert second.stage_patch["research"]["usage"]["invocations"] == 0
    # The rendered discovery experience is unchanged on a hit.
    assert [
        c["symbol"] for c in second.stage_patch["discovery"]["candidates"]
    ] == ["CRWD"]


def test_exhausted_research_ceiling_degrades_find_to_cheap_verified_rows(
    monkeypatch,
) -> None:
    """One meter: the shared research ceiling gates the search; exhaustion
    still answers with resolver-verified rows, never a dead end."""
    _classify(monkeypatch, question_kind="find_assets", symbols=[])
    provider = _FakeSearchProvider(_search_packet())
    _wire_find(monkeypatch, provider=provider)

    result = asyncio.run(
        ra.discovery_turn_stage_result(
            interpretation=_interpretation(),
            decision=_decision(
                relationship="category",
                category_description="cybersecurity stocks",
            ),
            state=_state("Find me cybersecurity stocks", research_allowance=False),
            user=USER,
        )
    )
    assert result is not None
    assert provider.calls == [], "an exhausted ceiling must not search"
    research = result.stage_patch["research"]
    assert research["usage"]["cache_status"] == "bypass"
    assert research["usage"]["invocations"] == 0
    assert result.stage_patch["discovery"]["candidates"]


def test_knowledge_entry_find_shape_builds_a_deterministic_request(
    monkeypatch,
) -> None:
    _classify(
        monkeypatch,
        question_kind="find_assets",
        symbols=["AAPL"],
        discovery_category="AI stocks",
    )
    provider = _FakeSearchProvider(_search_packet())
    _wire_find(monkeypatch, provider=provider)

    result = asyncio.run(
        ra.research_answer_stage_result(
            interpretation=_interpretation(),
            state=_state("What are some AI stocks like Apple?"),
            user=USER,
        )
    )
    assert result is not None
    # Cheap verified rows are the default for knowledge-entry finds: no
    # search unless the interpreter said current facts are required.
    assert provider.calls == []
    research = result.stage_patch["research"]
    assert research["capability_class"] == "peer_expansion"
    assert research["anchor_symbols"] == ["AAPL"]


def test_flag_off_discovery_turns_take_the_pre_rail_composer_path(
    monkeypatch,
) -> None:
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "false")

    async def explode(**_kwargs: Any):
        raise AssertionError("the rail classifier must not run with the flag off")

    monkeypatch.setattr(ra, "_classify_research_question", explode)
    seen: dict[str, Any] = {}

    async def legacy(**kwargs: Any):
        seen.update(kwargs)
        return None

    import argus.agent_runtime.discovery as discovery_package

    monkeypatch.setattr(discovery_package, "discovery_stage_result_for", legacy)

    result = asyncio.run(
        ra.discovery_turn_stage_result(
            interpretation=_interpretation(),
            decision=_decision(),
            state=_state("Find me cybersecurity stocks"),
            user=USER,
        )
    )
    assert result is None
    assert seen, "flag off must delegate to the pre-rail composer wrapper"


def test_routing_classification_holds_a_reserved_permit(monkeypatch) -> None:
    """Trigger reliability at default configuration: with the corridor fully
    consumed by interpreter audits, the routing call still gets a permit;
    only the first one, and only with the rail on."""
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "true")
    with turn_execution.turn_execution_scope(entry_state={}) as execution:
        for _ in range(execution.call_allowance):
            assert turn_execution.reserve_provider_call("interpretation") is not None
        assert turn_execution.reserve_provider_call("interpretation") is None
        permit = turn_execution.reserve_provider_call("knowledge_route")
        assert permit is not None, "routing must never be starved by audits"
        assert turn_execution.reserve_provider_call("knowledge_route") is None, (
            "the reservation is one-shot; repeats compete in the corridor"
        )
        execution.terminal = "finished"

    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "false")
    with turn_execution.turn_execution_scope(entry_state={}) as execution:
        for _ in range(execution.call_allowance):
            assert turn_execution.reserve_provider_call("interpretation") is not None
        assert turn_execution.reserve_provider_call("knowledge_route") is None, (
            "flag off keeps the exact pre-rail competition"
        )
        execution.terminal = "finished"


def test_etf_constituents_shape_grounds_and_offers_holdings(monkeypatch) -> None:
    """Section 2's ETF constituents ability: the holdings table becomes
    resolver-verified pairs, so top constituents are offerable and exposure
    vehicles ground through the table instead of being dropped."""
    _classify(monkeypatch, question_kind="etf_constituents", symbols=["SPY"])
    holdings_table = (
        "## SPY ETF Holdings\n\n"
        "| etf | symbol | name | shares | weight | market_value |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| SPY | NVDA | NVIDIA CORP | 294,018,439 | 7.99 | 64,889,541,926 |\n"
        "| SPY | AAPL | APPLE INC | 178,303,413 | 6.88 | 55,826,450,339 |\n"
        "| SPY | MSFT | MICROSOFT CORP | 90,179,261 | 5.45 | 44,255,335,196 |\n"
    )
    document = agent_response(
        text="SPY's top holdings are NVDA, AAPL, and MSFT.", tickers=["SPY"]
    )
    document["output"][1]["results"][0] = {
        "category": "etf_holdings",
        "content": holdings_table,
        "sources": [],
        "tickers": ["SPY"],
    }
    document["output"][1]["categories"] = ["etf_holdings"]
    transport = RecordingTransport([document])
    monkeypatch.setattr(
        grounded, "_client", lambda: PerplexityAgentClient("k", transport=transport)
    )

    result = asyncio.run(
        ra.research_answer_stage_result(
            interpretation=_interpretation(),
            state=_state("What are the top holdings inside SPY?"),
            user=USER,
        )
    )
    assert result is not None
    sidecar = result.stage_patch["research"]
    assert sidecar["shape"] == "balanced"
    assert sidecar["capability_class"] == "balanced_lookup"
    # Weight order survives the parse; the resolver verified each holding.
    offered = [p["symbol"] for p in sidecar["peers"]]
    assert offered[:2] == ["NVDA", "AAPL"]
    rows = result.stage_patch["next_experiments"]["rows"]
    assert rows, "top constituents must be runnable"


def test_memory_producer_block_rides_every_research_sidecar(monkeypatch) -> None:
    _classify(
        monkeypatch,
        question_kind="cross_company",
        symbols=["NFLX", "AAPL"],
        period_of_interest="last three years",
    )
    transport = RecordingTransport([])
    monkeypatch.setattr(
        grounded, "_client", lambda: PerplexityAgentClient("k", transport=transport)
    )
    first = asyncio.run(
        ra.research_answer_stage_result(
            interpretation=_interpretation(),
            state=_state("Compare Netflix and Apple over three years"),
            user=USER,
        )
    )
    assert first is not None
    job_request = first.stage_patch["research_job_request"]

    from argus.domain.research.perplexity_agent import _packet_from_response

    packet = _packet_from_response(agent_response(text="Compared."), latency_ms=900)
    composed = ra.compose_completed_research(job_request=job_request, packet=packet)
    memory = composed["research"]["memory"]
    assert memory["schema_version"] == "argus_research_memory/v1"
    assert [s["symbol"] for s in memory["subjects"]] == ["NFLX", "AAPL"]
    assert memory["comparison_set"] == ["NFLX", "AAPL"]
    assert memory["open_thread"]["shape"] == "thorough"
    assert memory["open_thread"]["period_of_interest"] == "last three years"
