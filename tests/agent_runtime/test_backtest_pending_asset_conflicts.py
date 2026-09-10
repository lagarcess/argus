"""Known facts follow the same pending-artifact owner as confirmation."""

from __future__ import annotations

import json
import socket
from copy import deepcopy
from pathlib import Path

import pytest
from argus.agent_runtime import llm_interpreter
from argus.agent_runtime.interpreter.backtest_calls import _known_input_conflicts
from argus.agent_runtime.llm_interpreter_types import (
    LLMInterpretationResponse,
    LLMStrategyDraft,
)
from argus.agent_runtime.semantic_integrity import DECLARED_TOOL_INPUT_CONFLICT
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.state.models import UserState

from tests.evals.measurement_eval_harness import load_eval_cases


@pytest.fixture(autouse=True)
def provider_free(monkeypatch):
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "false")
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "synthetic_unit_fixture")
    monkeypatch.setenv("ARGUS_ASSET_PROVIDER_MODE", "synthetic_unit_fixture")

    def unexpected_network(*args, **kwargs):
        pytest.fail("Pending-asset comparison must not call a provider")

    async def unexpected_model(**kwargs):
        pytest.fail("Pending-asset comparison must not read a model")

    monkeypatch.setattr(socket.socket, "connect", unexpected_network)
    monkeypatch.setattr(socket.socket, "connect_ex", unexpected_network)
    monkeypatch.setattr(socket, "create_connection", unexpected_network)
    monkeypatch.setattr(
        llm_interpreter, "invoke_openrouter_json_schema", unexpected_model
    )


@pytest.fixture
def pending_amount(faker):
    case_id = "dca_capital_semantics_prebaked_chip_spanish_pesos_reaches_ready_to_run"
    artifact = (
        Path(__file__).parents[2]
        / "docs/reports/evidence/registry/live-measurement-third.json"
    )
    row = next(
        row for row in json.loads(artifact.read_text())["results"] if row["id"] == case_id
    )
    case = next(case for case in load_eval_cases() if case.id == case_id)
    before = LLMInterpretationResponse(
        intent="calculate",
        task_relation="continue",
        semantic_turn_act=row["typed_outcome"]["semantic_turn_act"],
        user_goal_summary="",
        candidate_strategy_draft=LLMStrategyDraft.model_validate(
            row["typed_outcome"]["tool_calls"][0]["arguments"]["strategy"]
        ),
    )
    request = InterpretationRequest(
        current_user_message=case.followup_prompt,
        recent_thread_history=[],
        latest_task_snapshot=case.snapshot,
        selected_thread_metadata={},
        user=UserState(user_id=faker.uuid4()),
    )
    # The call and pending artifact are retained. This is a controlled
    # continuation, not a reconstruction of the unretained focused reply.
    after = before.model_copy(deep=True)
    after.candidate_strategy_draft.asset_universe = list(
        case.snapshot.pending_strategy_summary.asset_universe
    )
    return before, after, request


def test_pending_amount_uses_canonical_asset_without_mutating_either_read(pending_amount):
    before, after, request = pending_amount
    originals = [deepcopy(value.model_dump()) for value in (before, after, request)]

    assert _known_input_conflicts(before, after, request=request) == []

    assert [value.model_dump() for value in (before, after, request)] == originals
    assert before.candidate_strategy_draft.asset_universe != (
        after.candidate_strategy_draft.asset_universe
    )


@pytest.mark.parametrize("asset_change", ["requested_asset_answer", "replace_assets"])
def test_explicit_asset_changes_remain_conflicts(pending_amount, asset_change):
    before, after, request = pending_amount
    if asset_change == "requested_asset_answer":
        request.selected_thread_metadata = {"requested_field": "asset_universe"}
    else:
        for response in (before, after):
            response.candidate_strategy_draft.asset_universe_operation = "replace"

    conflicts = _known_input_conflicts(before, after, request=request)

    assert {field.field_name for field in conflicts} == {"asset_universe"}
    assert all(field.reason_code == DECLARED_TOOL_INPUT_CONFLICT for field in conflicts)


@pytest.mark.parametrize(
    "changed_fact", ["capital_amount", "initial_capital", "fee_rate", "slippage"]
)
def test_pending_asset_normalization_keeps_money_and_cost_conflicts(
    pending_amount, changed_fact
):
    before, after, request = pending_amount
    amount = before.candidate_strategy_draft.capital_amount
    if changed_fact == "capital_amount":
        changes = {"capital_amount": amount * 2, "recurring_contribution": amount * 2}
    else:
        values = before.candidate_strategy_draft.model_dump()
        values[changed_fact] = 0
        before.candidate_strategy_draft = LLMStrategyDraft.model_validate(values)
        changes = {changed_fact: amount if changed_fact == "initial_capital" else 0.001}
    values = after.candidate_strategy_draft.model_dump()
    values.update(changes)
    after.candidate_strategy_draft = LLMStrategyDraft.model_validate(values)

    conflicts = _known_input_conflicts(before, after, request=request)

    assert changed_fact in {field.field_name for field in conflicts}
    assert all(field.reason_code == DECLARED_TOOL_INPUT_CONFLICT for field in conflicts)
