"""Registered research calls retain one provider, cache and source boundary."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, get_args

import pytest
from argus.agent_runtime import research_grounded as grounded
from argus.agent_runtime.stages.interpret_types import AssetDiscoveryRelationship
from argus.agent_runtime.state.models import RunState, UserState
from argus.domain.research.admission import (
    ResearchAttemptAdmission,
    research_attempt_admission_context,
)
from argus.domain.research.contracts import (
    ResearchPacket,
    ResearchSource,
    ResearchUsage,
    RetrievedRow,
)
from faker import Faker
from pydantic import ValidationError

FAKE = Faker()


def _context() -> SimpleNamespace:
    return SimpleNamespace(
        state=RunState.new(
            current_user_message=FAKE.sentence(), recent_thread_history=[]
        ),
        user=UserState(user_id=FAKE.uuid4(), language_preference="en"),
        stage_result=None,
    )


def _packet(symbol: str = "AAPL") -> ResearchPacket:
    publisher_url = "https://www.reuters.com/markets/company-data"
    observed = datetime.now(timezone.utc)
    value = float(FAKE.pydecimal(left_digits=3, right_digits=2, positive=True))
    row = RetrievedRow(
        subject=symbol,
        symbol=symbol,
        label="share price",
        value=value,
        kind="currency",
        unit="USD",
        as_of=observed.date().isoformat(),
        source_url=publisher_url,
    )
    return ResearchPacket(
        answer_markdown=f"{symbol} is {value} USD.",
        rows=(row,),
        typed_answer=True,
        categories=("quote",),
        sources=(ResearchSource(url=publisher_url, source_date=row.as_of),),
        usage=ResearchUsage(invocations=1, finance_search_invocations=1),
        retrieved_at=observed,
    )


class _ResearchClient:
    def __init__(self, *packets: ResearchPacket) -> None:
        self.packets = iter(packets)
        self.calls: list[tuple[str, Any]] = []

    def run_research(self, prompt: str, spec: Any) -> ResearchPacket:
        self.calls.append((prompt, spec))
        return next(self.packets)


def _wire(monkeypatch: pytest.MonkeyPatch, *packets: ResearchPacket) -> _ResearchClient:
    client = _ResearchClient(*packets)
    monkeypatch.setattr(grounded, "_client", lambda: client)
    # Coverage/runnable-row suggestions are outside this provider-call contract.
    monkeypatch.setattr(grounded, "research_next_experiment_rows", lambda **_: None)
    return client


def test_repeated_tool_calls_use_their_arguments_and_the_shared_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime.research_tools import FastQuoteArguments, fast_quote

    first_packet, second_packet = _packet("AAPL"), _packet("MSFT")
    client = _wire(monkeypatch, first_packet, second_packet)
    first = FastQuoteArguments(
        request="Read AAPL's current share price", symbols=["AAPL"]
    )
    second = FastQuoteArguments(
        request="Read MSFT's current share price", symbols=["MSFT"]
    )
    context = _context()
    claims: list[bool] = []

    def claim() -> ResearchAttemptAdmission:
        claims.append(True)
        return ResearchAttemptAdmission(available=True)

    async def invoke():
        with research_attempt_admission_context(claim):
            a = await fast_quote(first, context=context)
            b = await fast_quote(second, context=context)
            cached = await fast_quote(first, context=context)
        return a, b, cached

    a, b, cached = asyncio.run(invoke())
    assert a.rows == cached.rows == first_packet.rows
    assert b.rows == second_packet.rows
    assert len(client.calls) == 2
    # The allowance counts one research question/turn. Existing admission
    # owns that grain even when the model needs two retrieval operations.
    assert len(claims) == 1
    assert first.request in client.calls[0][0]
    assert second.request not in client.calls[0][0]
    assert context.state.current_user_message not in client.calls[0][0]
    assert context.stage_result.stage_patch["research"]["usage"]["cache_status"] == "hit"
    assert "candidate_strategy_draft" not in context.stage_result.stage_patch
    assert "confirmed_strategy_summary" not in context.stage_result.stage_patch


def test_balanced_call_preserves_typed_freshness_without_classifying_the_question(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime.research_tools import (
        BalancedLookupArguments,
        balanced_lookup,
    )

    client = _wire(monkeypatch, _packet())
    context = _context()
    args = BalancedLookupArguments(
        request="Read the latest source-backed figures",
        symbols=["AAPL"],
        data_class="analyst_estimates",
    )
    result = asyncio.run(balanced_lookup(args, context=context))
    assert result.sources
    assert client.calls[0][1].shape == "balanced"
    assert client.calls[0][1].recency == "month"
    assert "question_kind" not in args.model_dump()
    assert (
        context.stage_result.stage_patch["research"]["capability_class"]
        == "balanced_lookup"
    )


def test_missing_publisher_sources_is_failure_without_an_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime.research_tools import (
        BalancedLookupArguments,
        balanced_lookup,
    )
    from argus.domain.tool_declaration import ToolInvocationError

    no_sources = _packet().model_copy(update={"sources": ()})
    client = _wire(monkeypatch, no_sources, no_sources)
    context = _context()
    with pytest.raises(ToolInvocationError) as failure:
        asyncio.run(
            balanced_lookup(
                BalancedLookupArguments(
                    request="Read company growth drivers", symbols=["AAPL"]
                ),
                context=context,
            )
        )
    assert (
        failure.value.outcome.failure.code
        == "research_unavailable_missing_public_sources"
    )
    assert len(client.calls) == 2
    assert context.stage_result.stage_patch["research"]["rows"] == []
    assert (
        no_sources.answer_markdown
        not in context.stage_result.stage_patch["assistant_response"]
    )


def test_thorough_call_retains_job_lifecycle_without_inline_provider_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime.research_tools import (
        ThoroughResearchArguments,
        thorough_research,
    )

    client = _wire(monkeypatch)
    context = _context()
    args = ThoroughResearchArguments(
        request="Read the source-backed financial comparison",
        symbols=["AAPL", "MSFT"],
        data_class="filings_transcripts",
    )
    result = asyncio.run(thorough_research(args, context=context))
    assert result.status == "pending"
    assert result.answer is None and not result.rows
    assert client.calls == []
    job = context.stage_result.stage_patch["research_job_request"]
    assert job["question"] == args.request
    assert job["data_class"] == args.data_class
    assert job["capability_class"] == "thorough_research"
    assert grounded.retrieval_spec_for_job(job).recency is None


def test_screening_keeps_every_explicit_condition_in_the_provider_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime.research_tools import ScreeningArguments, screening

    client = _wire(monkeypatch, _packet())
    context = _context()
    conditions = ["P/E below 20", "positive operating cash flow"]
    args = ScreeningArguments(
        request="Read companies meeting these conditions", criteria=conditions
    )
    asyncio.run(screening(args, context=context))
    prompt, spec = client.calls[0]
    assert all(condition in prompt for condition in conditions)
    assert spec.shape == "balanced" and spec.recency == "week"
    assert context.stage_result.stage_patch["research"]["capability_class"] == "screening"


def test_peer_expansion_requires_a_typed_anchor_or_category() -> None:
    from argus.agent_runtime.research_tools import PeerExpansionArguments

    with pytest.raises(ValidationError):
        PeerExpansionArguments(request="Find alternatives", relationship="peer")
    args = PeerExpansionArguments(
        request="Find related assets", relationship="peer", anchor_symbols=["AAPL"]
    )
    assert "question_kind" not in args.model_json_schema()["properties"]


@pytest.mark.parametrize(
    "catalog_state",
    [
        {"tool_calls": [SimpleNamespace(tool_name="fast_quote")]},
        {"uses_tool_catalog": True},
    ],
)
def test_registered_calls_are_not_reinterpreted_by_legacy_research_routes(
    catalog_state: dict[str, Any],
) -> None:
    from argus.agent_runtime.interpreter.research_routing import primary_research_query
    from argus.agent_runtime.research_query import ResearchQueryExtraction
    from argus.agent_runtime.stages.interpret_types import StructuredInterpretation

    interpretation = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        user_goal_summary="Read quotes",
        research_query=ResearchQueryExtraction(
            question_kind="live_quote", symbols=["AAPL"]
        ),
    ).model_copy(update=catalog_state)
    assert primary_research_query(interpretation) is None


def test_pending_research_card_has_no_answer() -> None:
    from argus.agent_runtime.research_tools import (
        ResearchToolResult,
        ThoroughResearchArguments,
        research_card_presentation,
    )
    from argus.domain.tool_contracts import ToolOutcome

    presentation = research_card_presentation(
        ThoroughResearchArguments(request="Read public reports"),
        ToolOutcome(
            status="succeeded",
            result=ResearchToolResult(status="pending").model_dump(mode="json"),
        ),
    )
    assert presentation.answer is None
    assert presentation.rows == []
    assert presentation.narrative is None
    assert presentation.sources == []
    assert presentation.notes


def test_completed_research_presentation_keeps_cited_narrative_and_typed_figures() -> (
    None
):
    from argus.agent_runtime.research_tools import (
        FastQuoteArguments,
        ResearchToolResult,
        research_card_presentation,
    )
    from argus.domain.tool_contracts import ToolOutcome

    packet = _packet()
    result = ResearchToolResult(
        answer=packet.answer_markdown, rows=packet.rows, sources=packet.sources
    )
    presentation = research_card_presentation(
        FastQuoteArguments(request="Read the latest share price", symbols=["AAPL"]),
        ToolOutcome(status="succeeded", result=result.model_dump(mode="json")),
    )
    assert presentation.answer.value == packet.rows[0].value
    assert presentation.narrative == packet.answer_markdown
    assert presentation.sources == list(packet.sources)


@pytest.mark.parametrize("relationship", get_args(AssetDiscoveryRelationship))
def test_peer_expansion_calls_existing_discovery_and_returns_verified_rows(
    monkeypatch: pytest.MonkeyPatch, relationship: AssetDiscoveryRelationship
) -> None:
    from argus.agent_runtime.research_tools import PeerExpansionArguments, peer_expansion

    from tests.research.test_research_router_absorption import (
        _FakeSearchProvider,
        _search_packet,
        _wire_find,
    )

    packet = _search_packet()
    provider = _FakeSearchProvider(packet)
    _wire_find(monkeypatch, provider=provider)
    context = _context()
    result = asyncio.run(
        peer_expansion(
            PeerExpansionArguments(
                request="Find cybersecurity companies",
                relationship=relationship,
                anchor_symbols=[] if relationship == "category" else ["PANW"],
                category_description="cybersecurity",
                needs_current_facts=True,
            ),
            context=context,
        )
    )
    assert [peer.symbol for peer in result.peers] == ["CRWD"]
    assert (
        context.stage_result.stage_patch["research"]["capability_class"]
        == "peer_expansion"
    )
    assert context.stage_result.stage_patch["discovery"]["relationship"] == relationship
    assert result.relationship == relationship
    assert provider.calls
    assert [source.url for source in result.sources] == [
        source.url for source in packet.results
    ]
    assert "candidate_strategy_draft" not in context.stage_result.stage_patch


def test_peer_expansion_cache_distinguishes_typed_relationships(monkeypatch) -> None:
    from argus.agent_runtime.research_tools import PeerExpansionArguments, peer_expansion

    from tests.research.test_research_router_absorption import (
        _FakeSearchProvider,
        _search_packet,
        _wire_find,
    )

    provider = _FakeSearchProvider(_search_packet())
    _wire_find(monkeypatch, provider=provider)
    context = _context()
    common = {
        "request": "Find candidate assets around this business",
        "anchor_symbols": ["PANW"],
        "needs_current_facts": True,
    }

    async def invoke():
        results = []
        for relationship in ("peer", "comparison", "comparison"):
            result = await peer_expansion(
                PeerExpansionArguments(relationship=relationship, **common),
                context=context,
            )
            results.append(
                (
                    result.relationship,
                    context.stage_result.stage_patch["research"]["usage"]["cache_status"],
                )
            )
        return results

    results = asyncio.run(invoke())
    assert len(provider.calls) == 2
    assert results == [("peer", "miss"), ("comparison", "miss"), ("comparison", "hit")]


def test_disabled_research_fails_before_provider_or_quota_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime.research_tools import get_research_declarations

    client = _wire(monkeypatch)
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "false")
    tool = next(item for item in get_research_declarations() if item.name == "fast_quote")
    outcome = asyncio.run(
        tool.invoke(
            {"request": "Read the price", "symbols": ["AAPL"]},
            context=_context(),
        )
    )
    assert outcome.status == "unavailable"
    assert outcome.result is None
    assert client.calls == []


def test_pending_result_cannot_carry_completed_facts() -> None:
    from argus.agent_runtime.research_tools import ResearchToolResult

    with pytest.raises(ValidationError):
        ResearchToolResult(status="pending", answer=FAKE.sentence(), rows=_packet().rows)


def test_registered_retrieval_withholds_prose_without_typed_figures(monkeypatch) -> None:
    from argus.agent_runtime.research_tools import get_research_declarations

    packet = _packet().model_copy(update={"rows": (), "typed_answer": False})
    _wire(monkeypatch, packet)
    context = _context()
    declaration = next(
        tool for tool in get_research_declarations() if tool.name == "fast_quote"
    )
    outcome = asyncio.run(
        declaration.invoke(
            {"request": "Read the quote", "symbols": ["AAPL"]},
            context=context,
        )
    )
    assert outcome.status == "bounded"
    assert outcome.result is None
    assert (
        packet.answer_markdown
        not in context.stage_result.stage_patch["assistant_response"]
    )
    assert (
        context.stage_result.stage_patch["research"]["degraded"]["code"]
        == "research_figures_unverified"
    )


def test_catalog_zero_calls_never_fall_back_to_a_question_classifier(monkeypatch) -> None:
    from argus.agent_runtime import knowledge_answer as knowledge
    from argus.agent_runtime.stages.interpret_types import StructuredInterpretation

    async def unexpected(**_: Any):
        raise AssertionError("zero catalog calls must remain zero calls")

    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "false")
    monkeypatch.setattr(knowledge, "_classify_question", unexpected)
    interpretation = StructuredInterpretation(
        intent="explain",
        task_relation="continue",
        user_goal_summary="Explain a concept",
        semantic_turn_act="educational_question",
    ).model_copy(update={"uses_tool_catalog": True})
    context = _context()
    result = asyncio.run(
        knowledge.knowledge_answer_stage_result(
            interpretation=interpretation,
            state=context.state,
            user=context.user,
            snapshot=None,
            selected_thread_metadata={},
        )
    )
    assert result is None
