"""Typed strategy work keeps its facts when the catalog selects zero calls."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest
from argus.agent_runtime import llm_interpreter as interpreter
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.interpreter import provider_context_assets
from argus.agent_runtime.interpreter.tool_calls import catalog_standalone_response
from argus.agent_runtime.llm_interpreter_types import (
    LLMInterpretationResponse,
    interpretation_response_model,
)
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.state.models import UserState
from argus.domain.tool_declaration import ToolCatalog
from faker import Faker

fake = Faker()


@pytest.fixture
def catalog_interpreter() -> interpreter.OpenRouterStructuredInterpreter:
    return interpreter.OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract(), tool_catalog=ToolCatalog(())
    )


def _response(**updates: Any) -> LLMInterpretationResponse:
    model = interpretation_response_model(ToolCatalog(()))
    return model.model_validate(
        {
            "intent": "explain",
            "task_relation": "new_task",
            "user_goal_summary": fake.sentence(),
            "assistant_response": fake.sentence(),
            "semantic_turn_act": "educational_question",
            **updates,
        }
    )


def _request() -> InterpretationRequest:
    return InterpretationRequest(
        current_user_message=fake.sentence(), user=UserState(user_id=fake.uuid4())
    )


def _asset_context(*, complete: bool = True) -> str:
    return json.dumps(
        {
            "asset_resolution_candidates": [
                {
                    "raw_text": "bitcoin",
                    "role": "traded_asset",
                    "status": "resolved",
                    "symbol": "BTC",
                    "asset_class": "crypto",
                    "name": "Bitcoin",
                    "raw_symbol": "BTC/USD",
                    "provider": "kraken",
                }
            ],
            "all_traded_asset_mentions_accounted_for": complete,
        }
    )


@pytest.mark.parametrize(
    "obligation",
    [
        {"requires_clarification": True},
        {"missing_required_fields": ["entry_rule"]},
        {
            "ambiguous_fields": [
                {
                    "field_name": "asset_universe",
                    "raw_value": "BTC",
                    "reason_code": "asset_resolution_ambiguous",
                }
            ]
        },
        {
            "unsupported_constraints": [
                {
                    "category": "unsupported_strategy_logic",
                    "raw_value": "opciones semanales",
                    "explanation": "This historical rule cannot execute.",
                }
            ]
        },
    ],
)
def test_empty_refusal_with_recovery_obligations_keeps_its_fields(
    catalog_interpreter: interpreter.OpenRouterStructuredInterpreter,
    obligation: dict[str, Any],
) -> None:
    response = _response(
        intent="cannot", semantic_turn_act="unsupported_request", **obligation
    )

    assert not catalog_standalone_response(response)
    runtime = catalog_interpreter._to_runtime_interpretation(response, request=_request())
    assert runtime.requires_clarification == response.requires_clarification
    assert runtime.missing_required_fields == response.missing_required_fields
    assert [item.raw_value for item in runtime.ambiguous_fields] == [
        item.raw_value for item in response.ambiguous_fields
    ]
    assert [item.raw_value for item in runtime.unsupported_constraints] == [
        item.raw_value for item in response.unsupported_constraints
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("intent", "act"),
    [("explain", "educational_question"), ("cannot", "unsupported_request")],
)
async def test_general_answer_with_asset_preflight_stays_standalone(
    intent: str, act: str
) -> None:
    response = _response(intent=intent, semantic_turn_act=act)
    prepared = await interpreter._response_ready_for_runtime(
        response=response,
        preferred_model="unused",
        request=_request(),
        asset_resolution_context=_asset_context(),
    )

    assert catalog_standalone_response(prepared)
    assert prepared.candidate_strategy_draft.asset_universe == []
    assert prepared.candidate_strategy_draft.asset_class is None
    assert prepared.assistant_response == response.assistant_response
    assert not prepared.requires_clarification


@pytest.mark.parametrize(
    ("intent", "act"),
    [
        ("explain", "new_idea"),
        ("follow_up", "answer_pending_need"),
        ("explain", "refine_current_idea"),
        ("follow_up", "approval"),
    ],
)
def test_strategy_route_retains_provider_identity_regardless_of_answer_intent(
    intent: str, act: str
) -> None:
    response = _response(
        intent=intent,
        semantic_turn_act=act,
        candidate_strategy_draft={
            "strategy_type": "buy_and_hold",
            "asset_universe": ["BTC"],
        },
    )
    prepared = provider_context_assets.response_with_provider_context_assets(
        response, asset_resolution_context=_asset_context()
    )

    assert prepared.candidate_strategy_draft.asset_class == "crypto"
    assert (
        prepared.candidate_strategy_draft.extra_parameters["provider_resolved_assets"][0][
            "raw_text"
        ]
        == "bitcoin"
    )


def test_strategy_route_canonicalizes_from_its_retained_provider_record() -> None:
    row = json.loads(_asset_context())["asset_resolution_candidates"][0]
    response = _response(
        semantic_turn_act="new_idea",
        candidate_strategy_draft={
            "strategy_type": "buy_and_hold",
            "asset_universe": ["BTC"],
            "extra_parameters": {"provider_resolved_assets": [row]},
        },
    )

    def no_second_resolution(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("The retained provider identity already resolves the asset")

    prepared = provider_context_assets.response_with_canonical_interpreter_assets(
        response, resolve_asset_candidate=no_second_resolution
    )
    assert prepared.candidate_strategy_draft.asset_class == "crypto"


@pytest.mark.parametrize(
    "context_handler",
    [
        provider_context_assets.response_with_provider_context_assets,
        provider_context_assets.carry_incomplete_asset_blocker,
    ],
)
def test_strategy_route_keeps_incomplete_asset_preflight_blocked(
    context_handler: Callable[..., LLMInterpretationResponse],
) -> None:
    response = _response(
        semantic_turn_act="new_idea",
        candidate_strategy_draft={
            "strategy_type": "buy_and_hold",
            "asset_universe": ["BTC"],
        },
    )
    prepared = context_handler(
        response, asset_resolution_context=_asset_context(complete=False)
    )

    assert prepared.requires_clarification
    assert "asset_universe" in prepared.missing_required_fields


@pytest.mark.parametrize("intent", ["explain", "follow_up", "calculate"])
def test_empty_strategy_route_cannot_pass_required_shape(intent: str) -> None:
    response = _response(intent=intent, semantic_turn_act="new_idea")
    assert not interpreter._structured_interpretation_has_required_shape(
        response, request=_request()
    )


def test_calculation_label_does_not_enrich_a_non_strategy_answer() -> None:
    response = _response(intent="calculate")
    prepared = provider_context_assets.response_with_provider_context_assets(
        response, asset_resolution_context=_asset_context()
    )
    assert prepared.candidate_strategy_draft.asset_universe == []


def test_existing_missing_act_normalization_retains_provider_identity() -> None:
    response = _response(
        intent="calculate",
        semantic_turn_act=None,
        candidate_strategy_draft={
            "strategy_type": "buy_and_hold",
            "asset_universe": ["BTC"],
        },
    )
    prepared = interpreter._normalize_response_for_runtime_context(
        response, request=_request(), asset_resolution_context=_asset_context()
    )
    assert prepared.semantic_turn_act == "new_idea"
    assert prepared.candidate_strategy_draft.asset_class == "crypto"


def test_non_strategy_answer_does_not_need_a_strategy_shape() -> None:
    assert interpreter._structured_interpretation_has_required_shape(
        _response(intent="calculate"), request=_request()
    )


def test_result_reference_without_a_result_preserves_draft_as_new_idea() -> None:
    response = _response(
        semantic_turn_act="result_followup",
        candidate_strategy_draft={
            "strategy_type": "buy_and_hold",
            "asset_universe": ["BTC"],
        },
    )
    prepared = interpreter._normalize_response_for_runtime_context(
        response, request=_request()
    )
    assert prepared.semantic_turn_act == "new_idea"
    assert prepared.intent == "calculate"
    assert prepared.candidate_strategy_draft.asset_universe == ["BTC"]


@pytest.mark.parametrize("outcome", ["ready_to_confirm", "needs_clarification"])
@pytest.mark.parametrize(
    "prior_act", ["unsupported_request", "educational_question", None]
)
def test_supported_signal_plan_replaces_stale_non_strategy_act(
    outcome: str, prior_act: str | None
) -> None:
    from argus.agent_runtime.interpreter.signal_rule import (
        _response_from_signal_rule_plan,
    )

    from tests.agent_runtime._llm_interpreter_common import _sma_50_200_crossover_plan

    plan = _sma_50_200_crossover_plan(strategy_thesis=fake.sentence())
    if outcome != "ready_to_confirm":
        plan = plan.model_copy(
            update={
                "outcome": outcome,
                "rule_spec": None,
                "assistant_response": fake.sentence(),
            }
        )
    repaired = _response_from_signal_rule_plan(
        response=_response(semantic_turn_act=prior_act), plan=plan
    )
    assert repaired.intent == "calculate"
    assert repaired.semantic_turn_act == "new_idea"


@pytest.mark.parametrize(
    "prior_act", ["new_idea", "answer_pending_need", "refine_current_idea", "approval"]
)
def test_supported_signal_plan_preserves_existing_strategy_act(prior_act: str) -> None:
    from argus.agent_runtime.interpreter.signal_rule import (
        _response_from_signal_rule_plan,
    )

    from tests.agent_runtime._llm_interpreter_common import _sma_50_200_crossover_plan

    repaired = _response_from_signal_rule_plan(
        response=_response(semantic_turn_act=prior_act),
        plan=_sma_50_200_crossover_plan(strategy_thesis=fake.sentence()),
    )
    assert repaired.semantic_turn_act == prior_act


def test_draft_only_signal_plan_keeps_unsupported_route() -> None:
    from argus.agent_runtime.interpreter.signal_rule import (
        _response_from_signal_rule_plan,
    )
    from argus.agent_runtime.signal_rule_repair import SignalRulePlan

    repaired = _response_from_signal_rule_plan(
        response=_response(semantic_turn_act="new_idea"),
        plan=SignalRulePlan(outcome="draft_only", assistant_response=fake.sentence()),
    )
    assert repaired.intent == "cannot"
    assert repaired.semantic_turn_act == "unsupported_request"


@pytest.mark.asyncio
@pytest.mark.parametrize("model_intent", ["explain", "follow_up", "calculate"])
async def test_zero_call_strategy_confirmation_uses_typed_route_intent(
    catalog_interpreter: interpreter.OpenRouterStructuredInterpreter,
    model_intent: str,
) -> None:
    from argus.agent_runtime.graph.workflow import build_workflow
    from argus.agent_runtime.runtime import run_agent_turn
    from langgraph.checkpoint.memory import MemorySaver

    message = "Hold bitcoin with $1000 from 2024-01-02 to 2024-03-28."
    response = _response(
        intent=model_intent,
        semantic_turn_act="new_idea",
        candidate_strategy_draft={
            "raw_user_phrasing": message,
            "strategy_type": "buy_and_hold",
            "asset_universe": ["BTC"],
            "capital_amount": 1000,
            "date_range": {"start": "2024-01-02", "end": "2024-03-28"},
        },
    )

    def structured_response(request: InterpretationRequest) -> Any:
        prepared = interpreter._normalize_response_for_runtime_context(
            response, request=request, asset_resolution_context=_asset_context()
        )
        return catalog_interpreter._to_runtime_interpretation(prepared, request=request)

    workflow = build_workflow(
        structured_interpreter=structured_response, checkpointer=MemorySaver()
    )
    thread_id = fake.uuid4()
    result = await run_agent_turn(
        workflow=workflow,
        user=UserState(user_id=fake.uuid4()),
        thread_id=thread_id,
        message=message,
    )
    terminal = await workflow.aget_state({"configurable": {"thread_id": thread_id}})

    assert result["stage_outcome"] == "await_approval"
    assert result["confirmation_payload"]["strategy"]["asset_class"] == "crypto"
    assert terminal.values["run_state"].intent == "calculate"
    assert terminal.values["run_state"].tool_calls == []
    assert response.intent == model_intent
    signals = terminal.values["run_state"].normalized_signals
    if model_intent != "calculate":
        repair = signals["strategy_route_intent_repair"]
        assert repair["original_model_intent"] == model_intent
        assert repair["repair_applied"] is True
        assert repair["changed_fields"] == ["intent"]
        assert repair["before_fingerprint"] != repair["after_fingerprint"]
    else:
        assert "strategy_route_intent_repair" not in signals


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("intent", "act"),
    [("explain", "educational_question"), ("cannot", "unsupported_request")],
)
async def test_general_zero_call_answer_keeps_intent_through_terminal_state(
    catalog_interpreter: interpreter.OpenRouterStructuredInterpreter,
    intent: str,
    act: str,
) -> None:
    from argus.agent_runtime.graph.workflow import build_workflow
    from argus.agent_runtime.runtime import run_agent_turn
    from langgraph.checkpoint.memory import MemorySaver

    response = _response(intent=intent, semantic_turn_act=act)

    def structured_response(request: InterpretationRequest) -> Any:
        return catalog_interpreter._to_runtime_interpretation(response, request=request)

    workflow = build_workflow(
        structured_interpreter=structured_response, checkpointer=MemorySaver()
    )
    thread_id = fake.uuid4()
    result = await run_agent_turn(
        workflow=workflow,
        user=UserState(user_id=fake.uuid4()),
        thread_id=thread_id,
        message=fake.sentence(),
    )
    terminal = await workflow.aget_state({"configurable": {"thread_id": thread_id}})

    assert result["stage_outcome"] == "ready_to_respond"
    assert result["assistant_response"] == response.assistant_response
    assert terminal.values["run_state"].intent == intent
    assert (
        "strategy_route_intent_repair"
        not in terminal.values["run_state"].normalized_signals
    )
