"""Issue #411: the primary interpretation owns research intent and shape."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from argus.agent_runtime import knowledge_answer as ka
from argus.agent_runtime import research_answer as ra
from argus.agent_runtime.interpreter.draft_shape import strategy_has_execution_evidence
from argus.agent_runtime.interpreter.research_routing import (
    primary_research_query,
    research_turn_has_conflicting_owner,
)
from argus.agent_runtime.llm_interpreter_types import LLMInterpretationResponse
from argus.agent_runtime.stages.interpret_types import StructuredInterpretation
from argus.agent_runtime.state.models import RunState, StrategySummary, UserState
from faker import Faker

fake = Faker()


def _interpretation(**overrides: Any) -> StructuredInterpretation:
    return StructuredInterpretation.model_validate(
        {
            "intent": "conversation_followup",
            "task_relation": "new_task",
            "user_goal_summary": "Compare companies",
            "semantic_turn_act": "educational_question",
            "research_query": {
                "question_kind": "cross_company",
                "symbols": ["PLTR", "LMT"],
            },
            **overrides,
        }
    )


@pytest.mark.parametrize("source", [None, "explicit_user", "inherited", "unknown"])
def test_strategy_type_is_not_a_default_without_positive_provenance(source):
    extra = {} if source is None else {"field_provenance": {"strategy_type": source}}
    draft = StrategySummary(strategy_type="buy_and_hold", extra_parameters=extra)
    assert strategy_has_execution_evidence(draft, include_defaults=False)


def test_user_evidence_outranks_a_conflicting_default_marker():
    draft = StrategySummary(
        strategy_type="buy_and_hold",
        extra_parameters={
            "field_provenance": {"strategy_type": "default"},
            "evidence_spans": {"strategy_type": "Buy and hold"},
        },
    )
    assert strategy_has_execution_evidence(draft, include_defaults=False)


def test_primary_response_retains_research_shape():
    response = LLMInterpretationResponse.model_validate(_interpretation().model_dump())
    assert response.research_query.question_kind == "cross_company"


def test_primary_question_survives_runtime_preparation_without_intent_repairs(
    monkeypatch,
):
    from argus.agent_runtime import llm_interpreter as li
    from argus.agent_runtime.capabilities.contract import (
        build_default_capability_contract,
    )
    from argus.agent_runtime.interpreter import discovery_focused_read
    from argus.agent_runtime.stages.interpret_types import InterpretationRequest

    calls = []

    async def reclassify(**kwargs):
        calls.append(kwargs.get("schema_name"))
        return None

    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "true")
    monkeypatch.setattr(li, "invoke_openrouter_json_schema", reclassify)
    monkeypatch.setattr(
        discovery_focused_read, "invoke_openrouter_json_schema", reclassify
    )
    # Exercise the actual preparation and projection, not an injected runtime result.
    response = LLMInterpretationResponse.model_validate(_interpretation().model_dump())
    request = InterpretationRequest(
        current_user_message="Compare PLTR to LMT",
        user=UserState(user_id=fake.uuid4()),
    )
    prepared = asyncio.run(
        li._response_ready_for_runtime(
            response=response,
            preferred_model="test",
            request=request,
        )
    )
    runtime = li.OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract(),
    )._to_runtime_interpretation(prepared, request=request)
    assert runtime.research_query == response.research_query
    assert calls == []


def test_rail_consumes_typed_shape_without_reading_intent_again(monkeypatch):
    captured = []

    async def dispatch(query, **kwargs):
        captured.append(query)
        return ka.StageResult(outcome="ready_to_respond")

    async def reject_second_read(**kwargs):
        raise AssertionError("research must not classify raw user text")

    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "true")
    monkeypatch.setattr(ra, "_dispatch", dispatch)
    monkeypatch.setattr(ka, "invoke_openrouter_json_schema", reject_second_read)
    interpretation = _interpretation()
    result = asyncio.run(
        ka.knowledge_answer_stage_result(
            interpretation=interpretation,
            state=RunState.new(
                current_user_message=fake.sentence(), recent_thread_history=[]
            ),
            user=UserState(user_id=fake.uuid4()),
            snapshot=None,
            selected_thread_metadata={},
        )
    )
    assert result is not None
    assert captured == [interpretation.research_query]


def test_stated_buy_and_hold_never_reaches_research_even_with_conflicting_query(
    monkeypatch,
):
    async def reject_claim(**kwargs):
        raise AssertionError("a stated build request belongs to the builder")

    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "true")
    monkeypatch.setattr(ra, "research_answer_stage_result", reject_claim)
    interpretation = _interpretation(
        intent="strategy_drafting",
        semantic_turn_act="new_idea",
        requires_clarification=True,
        candidate_strategy_draft=StrategySummary(
            strategy_type="buy_and_hold",
            asset_universe=["META"],
            extra_parameters={"evidence_spans": {"strategy_type": "Buy and hold"}},
        ),
    )
    assert (
        asyncio.run(
            ka.knowledge_answer_stage_result(
                interpretation=interpretation,
                state=RunState.new(
                    current_user_message="Buy and hold de meta", recent_thread_history=[]
                ),
                user=UserState(user_id=fake.uuid4()),
                snapshot=None,
                selected_thread_metadata={},
            )
        )
        is None
    )


@pytest.mark.parametrize(
    "response_type", [StructuredInterpretation, LLMInterpretationResponse]
)
@pytest.mark.parametrize(
    "owner",
    [
        {"intent": "strategy_drafting"},
        {"intent": "backtest_execution"},
        {"semantic_turn_act": "new_idea"},
    ],
)
def test_thin_strategy_request_owns_default_draft_despite_research_query(
    response_type, owner
):
    payload = _interpretation(
        **owner,
        research_query={"question_kind": "market_stats", "symbols": ["META"]},
    ).model_dump()
    provenance = {"strategy_type": "default"}
    payload["candidate_strategy_draft"] = {
        "strategy_type": "buy_and_hold",
        "asset_universe": ["META"],
        "date_range": {"start": "2020-01-01", "end": "2024-12-31"},
        **(
            {"field_provenance": provenance}
            if response_type is LLMInterpretationResponse
            else {"extra_parameters": {"field_provenance": provenance}}
        ),
    }
    interpretation = response_type.model_validate(payload)
    # The thin request has no stated strategy type or capital; typed turn
    # ownership must still outrank the contradictory question payload.
    assert not strategy_has_execution_evidence(
        interpretation.candidate_strategy_draft, include_defaults=False
    )
    assert primary_research_query(interpretation) is None


def test_default_draft_does_not_claim_a_genuine_research_question():
    interpretation = _interpretation(
        candidate_strategy_draft={
            "strategy_type": "buy_and_hold",
            "extra_parameters": {"field_provenance": {"strategy_type": "default"}},
        }
    )
    assert primary_research_query(interpretation) == interpretation.research_query


def test_results_explanation_intent_owns_turn_without_auxiliary_result_fields():
    interpretation = _interpretation(
        intent="results_explanation",
        semantic_turn_act=None,
        candidate_strategy_draft={},
        result_followup_focus=None,
        result_followup_fact_key=None,
        artifact_target=None,
    )

    assert research_turn_has_conflicting_owner(interpretation)
    assert primary_research_query(interpretation) is None


def test_results_explanation_never_dispatches_conflicting_external_research(
    monkeypatch,
):
    async def reject_dispatch(**kwargs):
        raise AssertionError("a result explanation belongs to the result route")

    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "true")
    monkeypatch.setattr(ra, "research_answer_stage_result", reject_dispatch)
    interpretation = _interpretation(
        intent="results_explanation",
        semantic_turn_act=None,
        candidate_strategy_draft={},
        result_followup_focus=None,
        result_followup_fact_key=None,
        artifact_target=None,
    )

    assert (
        asyncio.run(
            ka.knowledge_answer_stage_result(
                interpretation=interpretation,
                state=RunState.new(
                    current_user_message="Explain why my latest backtest performed this way",
                    recent_thread_history=[],
                ),
                user=UserState(user_id=fake.uuid4()),
                snapshot=None,
                selected_thread_metadata={},
            )
        )
        is None
    )


@pytest.mark.parametrize("entry", ["knowledge", "discovery"])
@pytest.mark.parametrize(
    "owner",
    [
        {"candidate_strategy_draft": {"strategy_type": "buy_and_hold"}},
        {"candidate_strategy_draft": {"cadence": "weekly", "capital_amount": 100}},
        {"intent": "strategy_drafting"},
        {"intent": "backtest_execution"},
        {"semantic_turn_act": "new_idea"},
        {"semantic_turn_act": "approval"},
        {"semantic_turn_act": "answer_pending_need"},
        {"semantic_turn_act": "refine_current_idea"},
        {"semantic_turn_act": "result_followup"},
        {"semantic_turn_act": "retry_failed_action"},
        {"artifact_target": "latest_result"},
    ],
)
def test_both_rail_entries_protect_existing_turn_owner(monkeypatch, entry, owner):
    from argus.agent_runtime import research_find

    async def reject(*args, **kwargs):
        raise AssertionError("another surface owns this turn")

    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "true")
    monkeypatch.setattr(ra, "_dispatch", reject)
    monkeypatch.setattr(research_find, "find_assets_stage_result", reject)
    interpretation = _interpretation(
        **{
            "semantic_turn_act": "asset_discovery",
            "asset_discovery": {"relationship": "peer", "anchor_symbols": ["META"]},
            **owner,
        }
    )
    kwargs = dict(
        interpretation=interpretation,
        state=RunState.new(
            current_user_message=fake.sentence(), recent_thread_history=[]
        ),
        user=UserState(user_id=fake.uuid4()),
    )
    if entry == "knowledge":
        result = asyncio.run(ra.research_answer_stage_result(**kwargs))
    else:
        decision = ra.grounded.research_decision(interpretation, kwargs["user"], "test")
        decision.asset_discovery = ra.AssetDiscoveryRequest(
            relationship="peer", anchor_symbols=["META"]
        )
        result = asyncio.run(ra.discovery_turn_stage_result(decision=decision, **kwargs))
    assert result is None


def test_find_without_discovery_payload_uses_missing_target_recovery(monkeypatch):
    from argus.agent_runtime import research_find

    requests = []

    async def find(**kwargs):
        requests.append(kwargs["request"])
        return ka.StageResult(outcome="ready_to_respond")

    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "true")
    monkeypatch.setattr(research_find, "find_assets_stage_result", find)
    interpretation = _interpretation(research_query={"question_kind": "find_assets"})
    asyncio.run(
        ra.research_answer_stage_result(
            interpretation=interpretation,
            state=RunState.new(
                current_user_message=fake.sentence(), recent_thread_history=[]
            ),
            user=UserState(user_id=fake.uuid4()),
        )
    )
    # Missing currentness is not permission to silently use the model's old facts.
    assert requests == [None]
