"""Shared-cache privacy and collision regressions with synthetic provider data."""

from __future__ import annotations

import asyncio
from datetime import date

import pytest
from argus.agent_runtime import research_grounded as grounded
from argus.agent_runtime.research_query import ResearchQueryExtraction
from argus.agent_runtime.stages.interpret_types import StructuredInterpretation
from argus.agent_runtime.state.models import RunState
from argus.domain.research.cache import cache_stats
from faker import Faker

from tests.research.test_registered_research_tools import _context, _packet, _wire

FAKE = Faker()


@pytest.mark.parametrize(
    "changed",
    [
        {"screening_criteria": ["revenue growth above 20%"]},
        {"sector_of_interest": "healthcare"},
        {"period_of_interest": "2025"},
        {"period_is_closed_window": True},
        {"period_start_date": date(2025, 1, 2)},
        {"requires_publisher_sources": True},
        {"currency": "DOP"},
        {},
    ],
)
def test_freeform_requests_do_not_reuse_or_store_answers(monkeypatch, changed) -> None:
    """Identical prose is not proof that carried criteria or private facts agree."""
    context = _context()
    user = context.user.model_copy(update={"country": "DO", "currency": "USD"})
    query = ResearchQueryExtraction(
        question_kind="screening",
        screening_criteria=["revenue growth above 10%"],
        sector_of_interest="technology",
    )
    packets = [_packet(), _packet()]
    client = _wire(monkeypatch, *packets)
    interpretation = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        user_goal_summary="research",
        semantic_turn_act="educational_question",
    )
    state = RunState.new(
        current_user_message="Find matches for my criteria", recent_thread_history=[]
    )

    async def run(query, user):
        return await grounded.grounded_result(
            query=query,
            subjects=[],
            shape="balanced",
            interpretation=interpretation,
            state=state,
            user=user,
        )

    first = asyncio.run(run(query, user))
    second = asyncio.run(
        run(
            query.model_copy(
                update={k: v for k, v in changed.items() if k != "currency"}
            ),
            user.model_copy(update={"currency": changed.get("currency", user.currency)}),
        )
    )
    assert first is not None and second is not None
    assert len(client.calls) == 2
    assert (
        second.stage_patch["assistant_response"]
        != first.stage_patch["assistant_response"]
    )
    assert cache_stats()["entries"] == 0


@pytest.mark.parametrize("field", ["message", "screening_criteria", "sector_of_interest"])
def test_private_context_never_enters_shared_storage(monkeypatch, field) -> None:
    private = f"Private account {FAKE.uuid4()} balance {FAKE.pyint()}"
    context = _context()
    query = ResearchQueryExtraction(question_kind="company_lookup")
    message = "Explain these public market figures"
    if field == "message":
        message = private
    else:
        query = query.model_copy(
            update={field: [private] if field == "screening_criteria" else private}
        )
    packet = _packet().model_copy(update={"answer_markdown": private})
    client = _wire(monkeypatch, packet, packet)
    interpretation = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        user_goal_summary="research",
    )
    for _ in range(2):
        result = asyncio.run(
            grounded.grounded_result(
                query=query,
                subjects=[],
                shape="balanced",
                interpretation=interpretation,
                state=RunState.new(
                    current_user_message=message, recent_thread_history=[]
                ),
                user=context.user,
            )
        )
        assert result.stage_patch["research"]["usage"]["cache_status"] == "miss"
    assert len(client.calls) == 2
    assert private in client.calls[0][0]
    assert cache_stats() == {"entries": 0, "hits": 0, "misses": 0}


def _find_state(
    anchors=("AAPL",), *, validated_by="provider_catalog", asset_class="equity"
):
    from argus.agent_runtime.state.models import ResolutionProvenance

    state = RunState.new(current_user_message=FAKE.sentence(), recent_thread_history=[])
    state.resolution_provenance = [
        ResolutionProvenance(
            field="asset_universe",
            raw_text=symbol,
            source="llm_extraction",
            candidate_kind="asset",
            canonical_symbol=symbol,
            asset_class=asset_class,
            validated_by=validated_by,
        )
        for symbol in anchors
    ]
    return state


def _find(monkeypatch, requests, states):
    from argus.agent_runtime.research_find import find_assets_stage_result

    from tests.research.test_research_router_absorption import (
        _FakeSearchProvider,
        _search_packet,
        _wire_find,
    )

    provider = _FakeSearchProvider(_search_packet())
    _wire_find(monkeypatch, provider=provider)
    results = []
    for request, state in zip(requests, states, strict=True):
        results.append(
            asyncio.run(
                find_assets_stage_result(
                    request=request,
                    interpretation=StructuredInterpretation(
                        intent="conversation_followup",
                        task_relation="continue",
                        user_goal_summary="research",
                        semantic_turn_act="asset_discovery",
                    ),
                    decision=None,
                    state=state,
                    user=_context().user,
                )
            )
        )
    return provider, results


def test_verified_public_search_reuses_normalized_inputs_across_users(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages.interpret_types import AssetDiscoveryRequest

    request = AssetDiscoveryRequest(
        relationship="peer", anchor_symbols=["AAPL"], needs_current_facts=True
    )
    provider, results = _find(
        monkeypatch,
        [request, request.model_copy(update={"anchor_symbols": [" aapl ", " "]})],
        [_find_state(), _find_state()],
    )
    assert len(provider.calls) == 1
    assert [r.stage_patch["research"]["usage"]["cache_status"] for r in results] == [
        "miss",
        "hit",
    ]
    assert cache_stats()["entries"] == 1


@pytest.mark.parametrize(
    "change",
    [
        {"relationship": "comparison"},
        {"anchor_symbols": ["MSFT"]},
        {"asset_class_hint": "crypto"},
        {"anchor_symbols": ["MSFT", "AAPL"]},
    ],
)
def test_material_public_search_dimensions_do_not_collide(monkeypatch, change) -> None:
    from argus.agent_runtime.stages.interpret_types import AssetDiscoveryRequest

    request = AssetDiscoveryRequest(
        relationship="peer", anchor_symbols=["AAPL", "MSFT"], needs_current_facts=True
    )
    second = request.model_copy(update=change)
    provider, results = _find(
        monkeypatch,
        [request, second],
        [
            _find_state(("AAPL", "MSFT")),
            _find_state(
                ("AAPL", "MSFT"), asset_class=second.asset_class_hint or "equity"
            ),
        ],
    )
    assert len(provider.calls) == 2
    assert all(
        r.stage_patch["research"]["usage"]["cache_status"] == "miss" for r in results
    )


@pytest.mark.parametrize(
    "kind", ["category", "unknown", "client_mention", "unresolved", "wrong_class"]
)
def test_unproven_discovery_context_bypasses_shared_cache(monkeypatch, kind) -> None:
    from argus.agent_runtime.stages.interpret_types import AssetDiscoveryRequest

    request = AssetDiscoveryRequest(
        relationship="peer", anchor_symbols=["AAPL"], needs_current_facts=True
    )
    state = _find_state()
    if kind == "category":
        request.category_description = f"My private holdings {FAKE.uuid4()}"
    elif kind == "unknown":
        state.resolution_provenance = []
    elif kind == "client_mention":
        state.resolution_provenance[0].validated_by = "client_mention"
    elif kind == "unresolved":
        state.resolution_provenance[0].resolution_status = "ambiguous"
    else:
        state.resolution_provenance[0].asset_class = "crypto"
    provider, results = _find(monkeypatch, [request, request], [state, state])
    assert len(provider.calls) == 2
    assert all(
        r.stage_patch["research"]["usage"]["cache_status"] == "miss" for r in results
    )
    assert cache_stats()["entries"] == 0


def test_legacy_job_key_cannot_reenable_shared_answer_storage() -> None:
    from argus.domain.research.cache import research_cache_key

    for key in (
        FAKE.sha256(),
        research_cache_key(query="public query", provider_id="test", max_results=5),
    ):
        job = {"cache_key": key, "question": FAKE.sentence()}
        grounded.store_research_packet_for_job(job, _packet(), {"research": {}})
    assert cache_stats()["entries"] == 0


def test_model_backed_search_with_unmodeled_configuration_does_not_share(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages.interpret_types import AssetDiscoveryRequest

    monkeypatch.setenv("ARGUS_DISCOVERY_SEARCH_PROVIDER", "openrouter_web_search")
    request = AssetDiscoveryRequest(
        relationship="peer", anchor_symbols=["AAPL"], needs_current_facts=True
    )
    provider, _ = _find(monkeypatch, [request, request], [_find_state(), _find_state()])
    assert len(provider.calls) == 2
    assert cache_stats()["entries"] == 0


def test_shared_storage_rejects_freeform_packet_even_under_a_current_key() -> None:
    from argus.domain.research.cache import cache_get, cache_put, research_cache_key

    key = research_cache_key(
        query="public", provider_id="perplexity_direct", max_results=5
    )
    cache_put(key, _packet(), ttl_seconds=120.0)
    assert cache_get(key) is None
    assert cache_stats()["entries"] == 0
