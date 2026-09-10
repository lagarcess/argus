"""Replay retained calls through the financial fact producers, without providers."""

from __future__ import annotations

import json
import socket
from functools import lru_cache
from pathlib import Path

import pytest
from argus.agent_runtime import llm_interpreter
from argus.agent_runtime.interpreter.audits import (
    DcaContractAudit,
    StatedRunFieldFidelityAudit,
)
from argus.agent_runtime.interpreter.backtest_calls import (
    _declare_money_roles,
    _ground_declared_costs,
)
from argus.agent_runtime.interpreter.dca_audits import (
    _response_from_dca_contract_audit,
)
from argus.agent_runtime.interpreter.focused_extraction import (
    response_from_focused_strategy_extraction,
)
from argus.agent_runtime.interpreter.run_field_audits import (
    _response_from_stated_run_field_fidelity_audit,
)
from argus.agent_runtime.interpreter.strategy_builder import _strategy_from_llm
from argus.agent_runtime.llm_interpreter_types import (
    FocusedStrategyExtraction,
    LLMInterpretationResponse,
    LLMStrategyDraft,
)
from argus.agent_runtime.semantic_integrity import (
    _DCA_CEILING_KEYS,
    _DCA_SEED_KEYS,
    conserve_semantic_constraints,
)
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.state.models import StrategySummary, UserState


@pytest.fixture(autouse=True)
def local_profile(monkeypatch):
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "false")
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "true")
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "synthetic_unit_fixture")

    def no_network(*args, **kwargs):
        raise AssertionError("Network is forbidden in financial projection tests")

    async def no_provider(**kwargs):
        raise AssertionError("Every model output must be controlled in this replay")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket.socket, "connect_ex", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(llm_interpreter, "invoke_openrouter_json_schema", no_provider)


@lru_cache
def retained_rows():
    path = (
        Path(__file__).parents[2]
        / "docs/reports/evidence/registry/live-measurement-third.json"
    )
    return {row["id"]: row for row in json.loads(path.read_text())["results"]}


def retained_response(case_id):
    call = retained_rows()[case_id]["typed_outcome"]["tool_calls"][0]
    draft = LLMStrategyDraft.model_validate(call["arguments"]["strategy"])
    _declare_money_roles(draft)
    return LLMInterpretationResponse(
        intent="calculate",
        task_relation="new_task",
        semantic_turn_act="new_idea",
        user_goal_summary=draft.raw_user_phrasing,
        candidate_strategy_draft=draft,
    )


@pytest.mark.parametrize(
    "case_id",
    [
        "natural_language_establishes_modeled_costs_issue_271",
        "capability_honesty_golden_cross_control_aapl",
        "messy_english_complete_sma_crossover_benchmark_issue_270",
    ],
)
def test_retained_non_dca_money_can_use_equivalent_typed_carriers(case_id):
    base = retained_response(case_id)
    delivered = retained_rows()[case_id]["typed_outcome"]["clarification"]["payload"][
        "strategy"
    ]
    amount = delivered["capital_amount"]
    # The primary is retained verbatim. This controlled focused projection
    # restates its known money or bounded quote in the canonical seed carrier.
    payload = base.candidate_strategy_draft.model_dump(mode="python")
    payload.update(
        is_testable_strategy=True,
        user_goal_summary=base.user_goal_summary,
        capital_amount=amount,
        initial_capital=amount,
        date_range=delivered["date_range"],
    )
    response = response_from_focused_strategy_extraction(
        extraction=FocusedStrategyExtraction.model_validate(payload),
        request=InterpretationRequest(
            current_user_message=base.user_goal_summary,
            user=UserState(user_id="retained-financial-projection"),
        ),
        base_response=base,
        resolve_asset_candidate=lambda *_args, **_kwargs: None,
    )
    assert response.ambiguous_fields == []
    assert response.candidate_strategy_draft.capital_amount == amount
    assert response.candidate_strategy_draft.initial_capital == amount


@pytest.mark.parametrize("value", [0, 12000])
@pytest.mark.parametrize("source", [None, "explicit_user", "starting_capital"])
def test_same_non_dca_amount_needs_no_second_role_quote(value, source):
    base = retained_response("natural_language_establishes_modeled_costs_issue_271")
    draft = base.candidate_strategy_draft
    draft.capital_amount = value
    draft.field_provenance = {} if source is None else {"capital_amount": source}
    draft.evidence_spans = {}
    extraction = FocusedStrategyExtraction(
        is_testable_strategy=True,
        user_goal_summary=base.user_goal_summary,
        strategy_type=draft.strategy_type,
        asset_universe=draft.asset_universe,
        initial_capital=value,
    )
    response = response_from_focused_strategy_extraction(
        extraction=extraction,
        request=InterpretationRequest(
            current_user_message=base.user_goal_summary,
            user=UserState(user_id="same-financial-fact"),
        ),
        base_response=base,
        resolve_asset_candidate=lambda *_args, **_kwargs: None,
    )
    assert response.ambiguous_fields == []
    assert response.candidate_strategy_draft.initial_capital == value


@pytest.mark.parametrize("strategy_type", ["buy_and_hold", "dca_accumulation"])
def test_canonical_amount_keeps_its_existing_field_fidelity_owner(strategy_type):
    extraction = FocusedStrategyExtraction(
        is_testable_strategy=True,
        user_goal_summary="A controlled canonical money-field read.",
        strategy_type=strategy_type,
        asset_universe=["SPY"],
        capital_amount=200,
        field_provenance={"capital_amount": "explicit_user"},
    )
    response = response_from_focused_strategy_extraction(
        extraction=extraction,
        request=InterpretationRequest(
            current_user_message=extraction.user_goal_summary,
            user=UserState(user_id="canonical-money-owner"),
        ),
        resolve_asset_candidate=lambda *_args, **_kwargs: None,
    )
    assert response.candidate_strategy_draft.capital_amount == extraction.capital_amount
    assert response.ambiguous_fields == []


@pytest.mark.parametrize(
    "case_id",
    [
        "dca_capital_semantics_stated_seed_reaches_ready_to_run_issue_455",
        "dca_capital_semantics_spanish_seed_and_contribution_issue_455",
    ],
)
@pytest.mark.parametrize("source", _DCA_SEED_KEYS)
def test_documented_dca_audit_seed_source_cannot_create_a_ceiling(case_id, source):
    base = retained_response(case_id)
    seed = base.candidate_strategy_draft.initial_capital
    audit = DcaContractAudit(
        is_recurring_buy_request=True,
        recurring_contribution_amount=200,
        cadence="monthly",
        total_budget_amount=seed,
        total_budget_source=source,
        confidence=1,
    )
    response = _response_from_dca_contract_audit(response=base, audit=audit)
    assert response is not None
    draft = response.candidate_strategy_draft
    assert draft.initial_capital == seed
    assert draft.total_capital is None
    assert "total_budget" not in draft.extra_parameters
    report = conserve_semantic_constraints(
        strategy=_strategy_from_llm(draft, base.user_goal_summary),
        selected_thread_metadata={},
    )
    assert report.evidence.total_capital == seed
    assert report.evidence.contribution_ceiling is None
    assert report.unsupported_constraints == []


@pytest.mark.parametrize("source", _DCA_CEILING_KEYS)
def test_documented_dca_audit_ceiling_source_keeps_a_real_ceiling(source):
    base = retained_response(
        "dca_capital_semantics_stated_seed_reaches_ready_to_run_issue_455"
    )
    audit = DcaContractAudit(
        is_recurring_buy_request=True,
        recurring_contribution_amount=200,
        cadence="monthly",
        total_budget_amount=9000,
        total_budget_source=source,
        confidence=1,
    )
    response = _response_from_dca_contract_audit(response=base, audit=audit)
    assert response is not None
    report = conserve_semantic_constraints(
        strategy=_strategy_from_llm(response.candidate_strategy_draft),
        selected_thread_metadata={},
    )
    assert report.evidence.total_capital == base.candidate_strategy_draft.initial_capital
    assert report.evidence.contribution_ceiling == audit.total_budget_amount
    assert report.unsupported_constraints


@pytest.mark.parametrize(
    "case_id",
    [
        "dca_capital_semantics_start_by_phrase_is_contribution_issue_455",
        "spanish_ui_english_user_msft_hold_h1_2024",
    ],
)
def test_retained_unstated_cost_defaults_do_not_create_clarifications(case_id):
    response = retained_response(case_id)
    _ground_declared_costs(response, current_message=response.user_goal_summary)
    assert response.ambiguous_fields == []
    assert not response.requires_clarification
    strategy = _strategy_from_llm(
        response.candidate_strategy_draft, response.user_goal_summary
    )
    assert "fee_rate" not in strategy.extra_parameters
    assert "slippage" not in strategy.extra_parameters


def test_declared_default_costs_cannot_clear_an_existing_artifact():
    response = retained_response("spanish_ui_english_user_msft_hold_h1_2024")
    prior = StrategySummary(
        extra_parameters={
            "fee_rate": 0.001,
            "slippage": 0.0005,
            "field_provenance": {
                "fee_rate": "explicit_user",
                "slippage": "explicit_user",
            },
        }
    )
    _ground_declared_costs(
        response,
        current_message=response.user_goal_summary,
        prior_strategy=prior,
    )
    assert response.requires_clarification
    assert {item.field_name for item in response.ambiguous_fields} == {
        "fee_rate",
        "slippage",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case_id",
    [
        "natural_language_establishes_modeled_costs_issue_271",
        "dca_capital_semantics_stated_seed_reaches_ready_to_run_issue_455",
        "dca_capital_semantics_spanish_seed_and_contribution_issue_455",
        "spanish_ui_english_user_msft_hold_h1_2024",
    ],
)
async def test_retained_financial_calls_reach_real_graph_confirmation(
    monkeypatch, faker, case_id
):
    from argus.agent_runtime.graph import workflow
    from argus.agent_runtime.runtime import build_workflow_input
    from argus.agent_runtime.stages.interpret_types import StageResult
    from argus.domain.tool_contracts import ToolCall
    from langgraph.checkpoint.memory import MemorySaver

    row = retained_rows()[case_id]
    call = ToolCall.model_validate(row["typed_outcome"]["tool_calls"][0])
    original = call.model_dump(mode="json")
    delivered = row["typed_outcome"]["clarification"]["payload"]["strategy"]
    extra = delivered["extra_parameters"]
    message = call.arguments["strategy"]["raw_user_phrasing"]

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

    async def controlled_readiness(*, response, request, **kwargs):
        # The original call is retained. Full sidecar bodies were not; these
        # controlled reads use the delivered values to exercise real producers.
        payload = response.candidate_strategy_draft.model_dump(mode="python")
        payload.update(
            is_testable_strategy=True,
            user_goal_summary=message,
            date_range=delivered["date_range"],
            capital_amount=delivered["capital_amount"],
            initial_capital=extra.get("initial_capital", delivered["capital_amount"]),
            recurring_contribution=extra.get("recurring_contribution"),
        )
        repaired = response_from_focused_strategy_extraction(
            extraction=FocusedStrategyExtraction.model_validate(payload),
            request=request,
            base_response=response,
            resolve_asset_candidate=lambda *_args, **_kwargs: None,
        )
        if delivered["strategy_type"] == "dca_accumulation":
            repaired = _response_from_dca_contract_audit(
                response=repaired,
                audit=DcaContractAudit(
                    is_recurring_buy_request=True,
                    recurring_contribution_amount=extra["recurring_contribution"],
                    cadence=delivered["cadence"],
                    total_budget_amount=extra["initial_capital"],
                    total_budget_source="starting_capital",
                    confidence=1,
                ),
            )
        costs = {}
        for field, audit_field in (("fee_rate", "fee"), ("slippage", "slippage")):
            if extra.get("field_provenance", {}).get(field) == "explicit_user":
                costs[audit_field] = {
                    "rate": extra[field],
                    "evidence_span": extra["evidence_spans"][field],
                }
        return (
            _response_from_stated_run_field_fidelity_audit(
                response=repaired,
                audit=StatedRunFieldFidelityAudit.model_validate(costs),
                current_message=message,
            )
            or repaired
        )

    monkeypatch.setattr(workflow, "interpret_stage_async", interpret)
    monkeypatch.setattr(
        llm_interpreter, "_audited_response_ready_for_runtime", controlled_readiness
    )
    graph = workflow.build_workflow(tool=object(), checkpointer=MemorySaver())
    result = await graph.ainvoke(
        build_workflow_input(user=UserState(user_id=faker.uuid4()), message=message),
        {"configurable": {"thread_id": faker.uuid4()}},
    )
    state = result["run_state"]
    assert result["stage_outcome"] == "await_approval"
    assert state.confirmation_payload is not None
    assert state.optional_parameter_status.get("ambiguous_fields", []) == []
    assert call.model_dump(mode="json") == original
    assert state.tool_calls == [call]
    if extra.get("initial_capital") is not None:
        assert (
            state.optional_parameter_status["initial_capital"] == extra["initial_capital"]
        )
