"""The primary read's need for new facts owns research admission."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import pytest
from argus.agent_runtime import calculated_answer as ca
from argus.agent_runtime import knowledge_answer as ka
from argus.agent_runtime import research_answer as ra
from argus.agent_runtime.interpreter.research_routing import (
    concept_research_query,
    primary_read_is_arithmetic,
    primary_research_query,
)
from argus.agent_runtime.research_query import ResearchQueryExtraction
from argus.agent_runtime.stages.interpret_types import (
    StageResult,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import RunState, UserState
from faker import Faker

fake = Faker()


def _interpretation(
    kind: str = "company_lookup", **changes: Any
) -> StructuredInterpretation:
    return StructuredInterpretation.model_validate(
        {
            "intent": "conversation_followup",
            "task_relation": "continue",
            "user_goal_summary": "Explain the earlier answer",
            "semantic_turn_act": "educational_question",
            "research_query": {
                "question_kind": kind,
                "symbols": ["AAPL"],
                "requires_new_facts": False,
            },
            **changes,
        }
    )


def _kwargs(interpretation: StructuredInterpretation) -> dict[str, Any]:
    return {
        "interpretation": interpretation,
        "state": RunState.new(
            current_user_message=fake.sentence(), recent_thread_history=[]
        ),
        "user": UserState(user_id=fake.uuid4()),
    }


@pytest.mark.parametrize("kind", ["company_lookup", "concept", "none", "find_assets"])
def test_an_existing_subject_or_explanation_without_new_facts_is_no_search(
    kind: str,
) -> None:
    interpretation = _interpretation(kind)
    assert primary_read_is_arithmetic(interpretation)
    assert primary_research_query(interpretation) is None
    assert concept_research_query(interpretation) is None


@pytest.mark.parametrize("enabled", [True, False])
@pytest.mark.parametrize("answer_available", [True, False])
@pytest.mark.parametrize("kind", ["company_lookup", "concept"])
@pytest.mark.parametrize("recalculation", [True, False])
def test_knowledge_uses_no_search_even_when_voicing_fails(
    monkeypatch, enabled: bool, answer_available: bool, kind: str, recalculation: bool
) -> None:
    answer = StageResult(outcome="ready_to_respond") if answer_available else None
    no_search = AsyncMock(return_value=answer)
    research = AsyncMock(side_effect=AssertionError("No new facts means no research"))
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", str(enabled).lower())
    monkeypatch.setattr(ca, "calculated_answer_stage_result", no_search)
    monkeypatch.setattr(ra, "research_answer_stage_result", research)
    monkeypatch.setattr(ka, "_classify_question", research)
    monkeypatch.setattr(ka, "_external_facts_answer", research)
    interpretation = _interpretation(kind)
    interpretation.research_query.scenario_question = recalculation
    result = asyncio.run(
        ka.knowledge_answer_stage_result(
            **_kwargs(interpretation), snapshot=None, selected_thread_metadata={}
        )
    )
    assert result is answer
    no_search.assert_awaited_once()
    research.assert_not_awaited()


@pytest.mark.parametrize("entry", ["knowledge", "discovery"])
@pytest.mark.parametrize("enabled", [True, False])
def test_every_research_entry_respects_false_before_provider_selection(
    monkeypatch, entry: str, enabled: bool
) -> None:
    from argus.agent_runtime import discovery, research_find

    research = AsyncMock(side_effect=AssertionError("No new facts means no research"))
    no_search = AsyncMock(return_value=None)
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", str(enabled).lower())
    monkeypatch.setattr(ra, "_dispatch", research)
    monkeypatch.setattr(research_find, "find_assets_stage_result", research)
    monkeypatch.setattr(discovery, "discovery_stage_result_for", research)
    monkeypatch.setattr(ca, "calculated_answer_stage_result", no_search)
    interpretation = _interpretation(
        "find_assets",
        semantic_turn_act="asset_discovery",
        asset_discovery={"relationship": "peer", "anchor_symbols": ["AAPL"]},
    )
    kwargs = _kwargs(interpretation)
    if entry == "knowledge":
        result = asyncio.run(ra.research_answer_stage_result(**kwargs))
    else:
        decision = ra.grounded.research_decision(interpretation, kwargs["user"], "test")
        decision.asset_discovery = interpretation.asset_discovery
        result = asyncio.run(ra.discovery_turn_stage_result(decision=decision, **kwargs))
        no_search.assert_awaited_once()
    assert result is None
    research.assert_not_awaited()


@pytest.mark.parametrize(
    "owner",
    [
        {"intent": "backtest_execution"},
        {"intent": "strategy_drafting", "semantic_turn_act": "new_idea"},
        {
            "intent": "results_explanation",
            "semantic_turn_act": "result_followup",
            "artifact_target": "latest_result",
        },
    ],
)
def test_no_new_facts_cannot_steal_execution_or_existing_artifact_owner(
    monkeypatch, owner: dict[str, str]
) -> None:
    reject = AsyncMock(side_effect=AssertionError("The existing route owns this turn"))
    monkeypatch.setattr(ca, "calculated_answer_stage_result", reject)
    monkeypatch.setattr(ra, "research_answer_stage_result", reject)
    interpretation = _interpretation(**owner)
    assert not primary_read_is_arithmetic(interpretation)
    assert (
        asyncio.run(
            ka.knowledge_answer_stage_result(
                **_kwargs(interpretation), snapshot=None, selected_thread_metadata={}
            )
        )
        is None
    )
    reject.assert_not_awaited()


def test_a_new_external_fact_still_reaches_research(monkeypatch) -> None:
    research = AsyncMock(return_value=StageResult(outcome="ready_to_respond"))
    no_search = AsyncMock(side_effect=AssertionError("A new quote needs facts"))
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "true")
    monkeypatch.setattr(ra, "_dispatch", research)
    monkeypatch.setattr(ca, "calculated_answer_stage_result", no_search)
    interpretation = _interpretation(
        research_query={
            "question_kind": "live_quote",
            "symbols": ["AAPL"],
            "requires_new_facts": True,
        }
    )
    assert (
        asyncio.run(
            ka.knowledge_answer_stage_result(
                **_kwargs(interpretation), snapshot=None, selected_thread_metadata={}
            )
        )
        is not None
    )
    research.assert_awaited_once()
    no_search.assert_not_awaited()


def test_older_query_payloads_keep_existing_research_behavior() -> None:
    assert (
        ResearchQueryExtraction(question_kind="company_lookup").requires_new_facts is True
    )


def test_thorough_packet_composition_does_not_block_the_event_loop(monkeypatch) -> None:
    import threading

    main_thread = threading.get_ident()
    compose_threads = []

    def compose(**kwargs):
        compose_threads.append(threading.get_ident())
        return StageResult(outcome="ready_to_respond")

    monkeypatch.setattr(ra, "_resolved_subjects", lambda query: [])
    monkeypatch.setattr(ra.grounded, "scenario_contract_applies", lambda *args: False)
    monkeypatch.setattr(ra.grounded, "shape_for_query", lambda query: "thorough")
    monkeypatch.setattr(ra.grounded, "thorough_job_result", compose)
    interpretation = _interpretation(
        research_query={"question_kind": "company_lookup", "requires_new_facts": True}
    )
    asyncio.run(
        ra._dispatch(
            interpretation.research_query,
            **_kwargs(interpretation),
            discovery_request=None,
            decision=None,
        )
    )
    assert compose_threads and compose_threads[0] != main_thread
