"""Payload-gated discovery promotion at the interpreter (#344).

The asset_discovery payload, not the semantic_turn_act label, routes
discovery; these tests pin the promotion, its vetoes, and the unroutable
payload drop."""

# ruff: noqa: F403, F405
from tests.agent_runtime._llm_interpreter_common import *


@pytest.mark.asyncio
async def test_discovery_payload_promotes_an_explicit_educational_act(
    monkeypatch,
) -> None:
    """A discovery request is often also a question; the payload routes it."""
    from argus.agent_runtime import llm_interpreter as interpreter_module
    from argus.agent_runtime.stages.interpret_types import AssetDiscoveryRequest

    discovery = AssetDiscoveryRequest(
        relationship="category",
        category_description="cryptos that are trending",
        asset_class_hint="crypto",
        needs_current_facts=True,
    )
    response = LLMInterpretationResponse(
        intent="conversation_followup",
        task_relation="new_task",
        user_goal_summary="Find trending cryptos to test.",
        semantic_turn_act="educational_question",
        context_question_focus="market_movers",
        asset_discovery=discovery,
    )

    async def audited_response(**_kwargs):
        raise AssertionError("a payload-routed turn must bypass strategy audits")

    monkeypatch.setattr(
        interpreter_module,
        "_audited_response_ready_for_runtime",
        audited_response,
    )

    repaired = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message="find me cryptos that are trending",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    assert repaired.semantic_turn_act == "asset_discovery"
    assert repaired.asset_discovery == discovery
    assert repaired.intent == "conversation_followup"
    assert repaired.context_question_focus is None
    assert "discovery_payload_act_promoted" in repaired.reason_codes


@pytest.mark.asyncio
async def test_capability_focus_vetoes_promotion_and_clears_the_payload(
    monkeypatch,
) -> None:
    """A support question keeps its route; the stray payload cannot linger,
    because knowledge answering stands down on payload presence."""
    from argus.agent_runtime import llm_interpreter as interpreter_module
    from argus.agent_runtime.stages.interpret_types import AssetDiscoveryRequest

    response = LLMInterpretationResponse(
        intent="conversation_followup",
        task_relation="new_task",
        user_goal_summary="Ask whether Argus can find stocks.",
        semantic_turn_act="educational_question",
        capability_question_focus="assets",
        asset_discovery=AssetDiscoveryRequest(
            relationship="category",
            category_description="new stocks",
            asset_class_hint="equity",
            needs_current_facts=False,
        ),
    )

    async def audited_response(**kwargs):
        return kwargs["response"]

    monkeypatch.setattr(
        interpreter_module,
        "_audited_response_ready_for_runtime",
        audited_response,
    )

    repaired = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message="does argus support finding new stocks?",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    assert repaired.semantic_turn_act == "educational_question"
    assert repaired.asset_discovery is None
    assert "discovery_payload_dropped_unroutable" in repaired.reason_codes


@pytest.mark.asyncio
async def test_result_followup_focus_vetoes_promotion_and_clears_the_payload(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module
    from argus.agent_runtime.stages.interpret_types import AssetDiscoveryRequest

    response = LLMInterpretationResponse(
        intent="conversation_followup",
        task_relation="continue",
        user_goal_summary="Ask what to try next.",
        semantic_turn_act="result_followup",
        result_followup_focus="next_experiment",
        asset_discovery=AssetDiscoveryRequest(
            relationship="category",
            category_description="something new",
            asset_class_hint="equity",
            needs_current_facts=False,
        ),
    )

    async def audited_response(**kwargs):
        return kwargs["response"]

    monkeypatch.setattr(
        interpreter_module,
        "_audited_response_ready_for_runtime",
        audited_response,
    )

    repaired = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message="ok what should I try next?",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    assert repaired.semantic_turn_act == "result_followup"
    assert repaired.asset_discovery is None
    assert "discovery_payload_dropped_unroutable" in repaired.reason_codes


@pytest.mark.asyncio
async def test_unpromotable_acts_keep_their_route_and_drop_the_payload(
    monkeypatch,
) -> None:
    """Approval, retry, and unsupported all act on prior state; a stray
    payload never redirects them."""
    from argus.agent_runtime import llm_interpreter as interpreter_module
    from argus.agent_runtime.stages.interpret_types import AssetDiscoveryRequest

    async def audited_response(**kwargs):
        return kwargs["response"]

    monkeypatch.setattr(
        interpreter_module,
        "_audited_response_ready_for_runtime",
        audited_response,
    )

    for act in ("approval", "retry_failed_action", "unsupported_request"):
        response = LLMInterpretationResponse(
            intent="conversation_followup",
            task_relation="continue",
            user_goal_summary="Continue the pending action.",
            semantic_turn_act=act,
            asset_discovery=AssetDiscoveryRequest(
                relationship="category",
                category_description="tech stocks",
                asset_class_hint="equity",
                needs_current_facts=False,
            ),
        )
        repaired = await interpreter_module._response_ready_for_runtime(
            response=response,
            preferred_model="test-model",
            request=InterpretationRequest(
                current_user_message="go ahead",
                recent_thread_history=[],
                latest_task_snapshot=None,
                user=UserState(user_id="u1"),
            ),
        )
        assert repaired.semantic_turn_act == act
        assert repaired.asset_discovery is None
        assert "discovery_payload_dropped_unroutable" in repaired.reason_codes
