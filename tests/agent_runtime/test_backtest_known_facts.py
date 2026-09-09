"""Declared repairs preserve semantic facts through the real graph decision."""

from __future__ import annotations

import json
import socket
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

import pytest
from argus.agent_runtime import llm_interpreter
from argus.agent_runtime.graph import workflow
from argus.agent_runtime.runtime import build_workflow_input
from argus.agent_runtime.stages.interpret_types import StageResult
from argus.agent_runtime.state.models import UserState
from argus.domain.tool_contracts import ToolCall
from langgraph.checkpoint.memory import MemorySaver


@lru_cache
def _retained_row(label):
    artifact = (
        Path(__file__).parents[2]
        / "docs/reports/evidence/registry/verification/262d670f/interleaved"
        / f"{label}.json"
    )
    return json.loads(artifact.read_text())["results"][0]


@pytest.fixture(autouse=True)
def provider_free(monkeypatch):
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "false")
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "synthetic_unit_fixture")

    async def unexpected_provider(**kwargs):
        raise AssertionError("Every model result must be controlled in this replay")

    monkeypatch.setattr(
        llm_interpreter, "invoke_openrouter_json_schema", unexpected_provider
    )

    def unexpected_network(*args, **kwargs):
        raise AssertionError("Network is forbidden in this replay")

    monkeypatch.setattr(socket.socket, "connect", unexpected_network)
    monkeypatch.setattr(socket.socket, "connect_ex", unexpected_network)
    monkeypatch.setattr(socket, "create_connection", unexpected_network)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "label,repair,conflict_field",
    [
        ("07-candidate-r1", "equivalent_dates", None),
        ("06-candidate-r1", "equivalent_money", None),
        ("07-candidate-r1", "changed_endpoint", "date_range"),
        ("06-candidate-r1", "changed_contribution", "capital_amount"),
        ("06-candidate-r1", "changed_zero_seed", "initial_capital"),
    ],
)
async def test_selected_call_repair_preserves_facts_through_graph(
    monkeypatch, faker, label, repair, conflict_field
):
    row = _retained_row(label)
    call = ToolCall.model_validate(deepcopy(row["typed_outcome"]["tool_calls"][0]))
    if repair == "changed_zero_seed":
        call.arguments["strategy"]["initial_capital"] = 0
    original = call.model_dump(mode="json")
    message = call.arguments["strategy"]["raw_user_phrasing"]
    repairs = []
    preparations = []
    execute_stage = workflow.execute_stage_async

    async def observe_execution(**kwargs):
        stage = await execute_stage(**kwargs)
        preparations.append(stage)
        return stage

    async def interpret(**kwargs):
        return StageResult(
            outcome="approved_for_execution",
            stage_patch={
                "intent": "calculate",
                "task_relation": "new_task",
                "semantic_turn_act": "new_idea",
                "tool_calls": [call],
            },
        )

    async def controlled_readiness(*, response, **kwargs):
        # The selected calls are retained. Full repaired provider replies were
        # not retained; these outputs isolate the observed carrier changes.
        repairs.append(response.model_copy(deep=True))
        after = response.model_copy(deep=True)
        draft = after.candidate_strategy_draft
        if repair in {"equivalent_dates", "changed_endpoint"}:
            draft.date_range_intent.confidence = 0.99
            if repair == "changed_endpoint":
                draft.date_range_intent.end = "2024-04-30"
        else:
            draft.date_range = row["typed_outcome"]["date_range"]
            draft.recurring_contribution = draft.capital_amount
            draft.capital_amount = draft.initial_capital
            if repair == "changed_contribution":
                draft.recurring_contribution = 300
                draft.capital_amount = 300
            elif repair == "changed_zero_seed":
                draft.initial_capital = 5000
            draft.field_provenance.update(draft.declared_capital_roles())
        return after

    monkeypatch.setattr(workflow, "interpret_stage_async", interpret)
    monkeypatch.setattr(workflow, "execute_stage_async", observe_execution)
    monkeypatch.setattr(
        llm_interpreter, "_audited_response_ready_for_runtime", controlled_readiness
    )
    graph = workflow.build_workflow(tool=object(), checkpointer=MemorySaver())
    result = await graph.ainvoke(
        build_workflow_input(user=UserState(user_id=faker.uuid4()), message=message),
        {"configurable": {"thread_id": faker.uuid4()}},
    )
    state = result["run_state"]

    assert len(repairs) == 1
    assert call.model_dump(mode="json") == original
    assert state.tool_calls == [call]
    ambiguities = state.optional_parameter_status.get("ambiguous_fields", [])
    if conflict_field is None:
        assert [stage.outcome for stage in preparations] == ["ready_for_confirmation"]
        assert result["stage_outcome"] == "await_approval"
        assert ambiguities == []
        assert state.confirmation_payload is not None
        if repair == "equivalent_money":
            assert state.candidate_strategy_draft.capital_amount == 200
            assert state.optional_parameter_status["initial_capital"] == 5000
    else:
        assert result["stage_outcome"] == "await_user_reply"
        assert state.confirmation_payload is None
        assert conflict_field in {item["field_name"] for item in ambiguities}
        assert all(
            item["reason_code"] == "declared_tool_input_conflict" for item in ambiguities
        )
        if repair == "changed_contribution":
            assert state.candidate_strategy_draft.capital_amount == 200
        elif repair == "changed_zero_seed":
            assert state.candidate_strategy_draft.extra_parameters["initial_capital"] == 0
        else:
            assert (
                state.candidate_strategy_draft.date_range
                == original["arguments"]["strategy"]["date_range"]
            )
