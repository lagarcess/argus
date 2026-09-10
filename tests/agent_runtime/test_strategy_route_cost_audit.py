"""Cost grounding follows typed strategy work before confirmation."""

from __future__ import annotations

import socket
from copy import deepcopy
from typing import Any

import pytest
from argus.agent_runtime import llm_interpreter
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.graph import workflow
from argus.agent_runtime.runtime import build_workflow_input
from argus.agent_runtime.stages import confirm
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.state.models import UserState
from langgraph.checkpoint.memory import MemorySaver

# Exact primary content retained from c6c28fef's modeled-cost case. It supplied
# both costs without evidence spans, selected no tools, and labeled drafting a
# follow-up. Only the intent changes in the sibling taxonomy controls below.
_MESSAGE = (
    "Prepare a daily buy-and-hold confirmation for MSFT with $12,000 from "
    "January 3, 2023 through December 31, 2024, benchmark SPY, a 10 bps fee, "
    "and 5 bps slippage."
)
_PRIMARY: dict[str, Any] = {
    "intent": "follow_up",
    "task_relation": "new_task",
    "user_goal_summary": _MESSAGE,
    "tool_calls": [],
    "requires_clarification": False,
    "detected_user_language": "en",
    "candidate_strategy_draft": {
        "raw_user_phrasing": _MESSAGE,
        "language": "en",
        "requested_strategy_template": "buy_and_hold",
        "strategy_type": "buy_and_hold",
        "asset_universe": ["MSFT"],
        "asset_class": "equity",
        "timeframe": "1D",
        "date_range": {"start": "2023-01-03", "end": "2024-12-31"},
        "date_range_raw_text": "from January 3, 2023 through December 31, 2024",
        "capital_amount": 12000,
        "comparison_baseline": "SPY",
        "fee_rate": 0.001,
        "slippage": 0.0005,
    },
    "missing_required_fields": [],
    "assistant_response": (
        "Here's the prepared confirmation for your MSFT buy-and-hold strategy "
        "with the details you provided."
    ),
    "uses_latest_result_context": False,
    "confidence": 0.9,
    "reason_codes": [],
    "semantic_turn_act": "new_idea",
    "artifact_target": "active_confirmation",
}


@pytest.fixture(autouse=True)
def provider_free_cost_route(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ARGUS_STRUCTURED_MODEL", "primary/model")
    monkeypatch.setenv("ARGUS_STRUCTURED_FALLBACK_MODEL", "")
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "false")
    monkeypatch.setenv("ARGUS_ENABLE_PERSONALIZATION_MEMORY", "false")
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "true")
    attempts = []

    def forbidden_network(*args, **kwargs):
        attempts.append(True)
        raise AssertionError("Every provider response must be scripted")

    monkeypatch.setattr(socket.socket, "connect", forbidden_network)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden_network)
    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    monkeypatch.setattr(confirm, "_market_clock_for_strategy", lambda _: None)
    yield
    assert attempts == []


@pytest.mark.asyncio
@pytest.mark.parametrize("intent", ["follow_up", "explain"])
async def test_zero_call_strategy_costs_are_grounded_before_real_confirmation(
    monkeypatch: pytest.MonkeyPatch, intent: str
) -> None:
    primary = deepcopy(_PRIMARY)
    primary["intent"] = intent
    supplied = primary["candidate_strategy_draft"]
    expected_costs = {name: supplied[name] for name in ("fee_rate", "slippage")}
    audit = {
        "fee": {"rate": expected_costs["fee_rate"], "evidence_span": "10 bps fee"},
        "slippage": {
            "rate": expected_costs["slippage"],
            "evidence_span": "5 bps slippage",
        },
        "confidence": 0.98,
    }
    calls = []

    async def scripted_reply(*, schema_name, schema_model, **kwargs):
        calls.append(schema_name)
        assert schema_name in {
            "LLMInterpretationResponse",
            "StatedRunFieldFidelityAudit",
        }
        payload = primary if schema_name == "LLMInterpretationResponse" else audit
        return schema_model.model_validate(payload)

    monkeypatch.setattr(llm_interpreter, "invoke_openrouter_json_schema", scripted_reply)
    interpreter = llm_interpreter.OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    parsed = interpreter.response_model.model_validate(primary)
    assert parsed.candidate_strategy_draft.evidence_spans == {}
    assert parsed.tool_calls == []
    graph = workflow.build_workflow(
        tool=object(), structured_interpreter=interpreter, checkpointer=MemorySaver()
    )

    result = await graph.ainvoke(
        build_workflow_input(
            user=UserState(user_id="strategy-cost-route"), message=_MESSAGE
        ),
        {"configurable": {"thread_id": f"strategy-cost-route-{intent}"}},
    )

    state = result["run_state"]
    assert result["stage_outcome"] == "await_approval"
    assert state.intent == "calculate"
    assert state.tool_calls == []
    extras = state.candidate_strategy_draft.extra_parameters
    assert {name: extras.get(name) for name in expected_costs} == expected_costs
    assert {name: extras["field_provenance"].get(name) for name in expected_costs} == {
        name: "explicit_user" for name in expected_costs
    }
    assert state.confirmation_payload is not None
    launch = state.confirmation_payload.model_dump(mode="json")["launch_payload"]
    assert launch["_execution_realism"] == {
        "enabled": True,
        "fee_bps": expected_costs["fee_rate"] * 10_000,
        "slippage_bps": expected_costs["slippage"] * 10_000,
    }
    assert calls == ["LLMInterpretationResponse", "StatedRunFieldFidelityAudit"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("intent", "act"),
    [
        ("cannot", "new_idea"),
        ("cannot", "unsupported_request"),
        ("calculate", "unsupported_request"),
        ("explain", "unsupported_request"),
        ("follow_up", "unsupported_request"),
        ("calculate", "result_followup"),
        ("explain", "result_followup"),
        ("follow_up", "result_followup"),
        ("calculate", "approval"),
        ("explain", "approval"),
        ("follow_up", "approval"),
        ("explain", "educational_question"),
        ("follow_up", "educational_question"),
    ],
)
async def test_nonpreparation_turns_never_start_cost_audit(
    monkeypatch: pytest.MonkeyPatch, intent: str, act: str
) -> None:
    primary = deepcopy(_PRIMARY)
    primary.update(intent=intent, semantic_turn_act=act)
    interpreter = llm_interpreter.OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    response = interpreter.response_model.model_validate(primary)
    calls = []

    async def unexpected_audit(**kwargs):
        calls.append(kwargs["schema_name"])
        raise AssertionError("This turn does not prepare a strategy")

    monkeypatch.setattr(
        llm_interpreter, "invoke_openrouter_json_schema", unexpected_audit
    )

    result = await llm_interpreter._audit_stated_run_field_fidelity(
        response=response,
        preferred_model="",
        request=InterpretationRequest(
            current_user_message=_MESSAGE, user=UserState(user_id="audit-exclusion")
        ),
    )

    assert result is None
    assert calls == []
