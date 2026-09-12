"""A calculation turn through the real workflow and the chat stream.

The stub interpreter stands in for the model's typed read; everything after it
is the production graph, router and store. The stored assistant message carries
the card and the ``metadata.computation`` marker derived from it, and a missing
input is asked once and merged when the user answers on the next turn.
"""

from __future__ import annotations

import json
from typing import Any

from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.graph.workflow import build_workflow
from argus.agent_runtime.interpreter.calculation_request import CalculationRequest
from argus.agent_runtime.stages.interpret_types import StructuredInterpretation
from argus.agent_runtime.state.models import StrategySummary
from argus.api import state as api_state
from argus.api.main import app
from fastapi.testclient import TestClient


class _ScriptedInterpreter:
    """One typed read per turn, in order."""

    def __init__(self, reads: list[StructuredInterpretation]) -> None:
        self.reads = list(reads)
        self.requests: list[Any] = []

    async def ainvoke(self, request: Any) -> StructuredInterpretation:
        self.requests.append(request)
        return self.reads.pop(0)


def _read(
    calculation: dict[str, Any],
    *,
    lead: str,
    clarify: bool = False,
    missing: list[str] | None = None,
) -> StructuredInterpretation:
    return StructuredInterpretation(
        intent="conversation_followup",
        task_relation="new_task",
        user_goal_summary="compute a saving plan",
        semantic_turn_act="educational_question",
        requires_clarification=clarify,
        missing_required_fields=list(missing or []),
        assistant_response=lead,
        candidate_strategy_draft=StrategySummary(),
        calculation=CalculationRequest.model_validate(calculation),
    )


def _stream(client: TestClient, conversation_id: str, message: str) -> dict[str, Any]:
    response = client.post(
        "/api/v1/chat/stream",
        json={"conversation_id": conversation_id, "message": message},
    )
    assert response.status_code == 200, response.text
    finals = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: {")
    ]
    return next(frame["payload"] for frame in finals if frame.get("type") == "final")


def _client_with(monkeypatch, interpreter: _ScriptedInterpreter) -> TestClient:
    client = TestClient(app)
    client.post("/api/v1/dev/reset")
    checkpointer = api_state.build_agent_runtime_checkpointer()
    workflow = build_workflow(
        contract=build_default_capability_contract(),
        structured_interpreter=interpreter,
        checkpointer=checkpointer,
    )
    monkeypatch.setattr(app.state, "agent_runtime_checkpointer", checkpointer, raising=False)
    monkeypatch.setattr(app.state, "agent_runtime_workflow", workflow, raising=False)
    return client


def test_a_calculation_turn_stores_its_card_and_marker(monkeypatch) -> None:
    interpreter = _ScriptedInterpreter(
        [
            _read(
                {
                    "kind": "time_value",
                    "inputs": {
                        "direction": "save",
                        "present_value": 10_000,
                        "payment": 0,
                        "annual_rate_pct": 5,
                        "periods": 120,
                    },
                    "solve_for": "future_value",
                },
                lead="Here is what that plan grows to.",
            )
        ]
    )
    client = _client_with(monkeypatch, interpreter)
    conversation_id = client.post("/api/v1/conversations", json={}).json()[
        "conversation"
    ]["id"]
    final = _stream(client, conversation_id, "10,000 at 5% for ten years, what do I get?")
    assert final["tool_result_cards"][0]["tool_name"] == "time_value"

    messages = client.get(f"/api/v1/conversations/{conversation_id}/messages").json()[
        "items"
    ]
    stored = messages[-1]
    assert stored["role"] == "assistant"
    assert stored["content"] == "Here is what that plan grows to."
    card = stored["metadata"]["tool_result_cards"][0]
    assert card["outcome"]["status"] == "succeeded"
    assert stored["metadata"]["computation"] == {
        "kind": "time_value",
        "inputs": card["arguments"],
    }
    rows = stored["metadata"]["next_experiments"]["rows"]
    assert [row["kind"] for row in rows] == ["calculation_market_counterfactual"]
    assert stored["metadata"]["next_steps"]["items"] == [
        {"type": "test", "kind": "calculation_market_counterfactual"}
    ]
    assert not api_state.store.backtest_runs


def test_a_missing_input_is_asked_once_and_the_reply_computes(monkeypatch) -> None:
    interpreter = _ScriptedInterpreter(
        [
            _read(
                {
                    "kind": "time_value",
                    "inputs": {
                        "direction": "save",
                        "present_value": 0,
                        "payment": 500,
                        "annual_rate_pct": 5,
                    },
                    "solve_for": "future_value",
                },
                lead="For how many months would you save?",
                clarify=True,
                missing=["periods"],
            ),
            _read(
                {"kind": "time_value", "inputs": {"periods": 240}},
                lead="Here is that plan.",
            ),
        ]
    )
    client = _client_with(monkeypatch, interpreter)
    conversation_id = client.post("/api/v1/conversations", json={}).json()[
        "conversation"
    ]["id"]
    _stream(client, conversation_id, "If I save 500 a month at 5%, what do I end up with?")
    messages = client.get(f"/api/v1/conversations/{conversation_id}/messages").json()[
        "items"
    ]
    asked = messages[-1]
    assert asked["content"] == "For how many months would you save?"
    assert "tool_result_cards" not in asked["metadata"]
    assert asked["metadata"]["clarification"]["payload"]["calculation"]["kind"] == (
        "time_value"
    )

    _stream(client, conversation_id, "20 years")
    selected = interpreter.requests[1].selected_thread_metadata
    assert selected["last_stage_outcome"] == "await_user_reply"
    messages = client.get(f"/api/v1/conversations/{conversation_id}/messages").json()[
        "items"
    ]
    answered = messages[-1]
    card = answered["metadata"]["tool_result_cards"][0]
    assert card["outcome"]["status"] == "succeeded"
    assert card["arguments"]["periods"] == 240
    assert card["arguments"]["payment"] == 500
    assert answered["metadata"]["computation"]["kind"] == "time_value"
