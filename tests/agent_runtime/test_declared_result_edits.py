"""A declared edit keeps its supplied facts when it inherits the run window."""

from __future__ import annotations

import pytest
from argus.agent_runtime import llm_interpreter
from argus.agent_runtime.artifact_edit_planner import (
    ArtifactAssumptionEditPlan,
    EditOperation,
)
from argus.agent_runtime.interpreter.artifact_assumption_edit import (
    _response_from_artifact_assumption_edit_plan,
)
from argus.agent_runtime.profile.response_profile import (
    resolve_effective_response_profile,
)
from argus.agent_runtime.stages.interpret_internal.result_artifact_patch import (
    _deterministic_result_artifact_patch_stage_result_if_applicable,
)
from argus.agent_runtime.stages.interpret_types import InterpretDecision
from argus.agent_runtime.stages.tool_execution import execute_tool_calls_async
from argus.agent_runtime.state.models import (
    RunState,
    StrategySummary,
    UnsupportedConstraint,
    UserState,
)

from tests.agent_runtime.test_interpret_stage import _latest_dca_result_snapshot
from tests.evals.measurement_eval_harness import load_eval_cases


@pytest.mark.asyncio
@pytest.mark.parametrize("language", ["english", "spanish"])
@pytest.mark.parametrize("planned", [False, True])
async def test_declared_capital_edit_survives_inherited_result_window(
    monkeypatch: pytest.MonkeyPatch, language: str, planned: bool
) -> None:
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "false")
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "synthetic_unit_fixture")
    monkeypatch.setenv("ARGUS_ASSET_PROVIDER_MODE", "synthetic_unit_fixture")
    case = next(
        case
        for case in load_eval_cases()
        if case.id == f"messy_{language}_post_result_fact_then_capital_edit_issue_160"
    )
    amount = case.expected.capital_amount

    async def audited_response(*, response, request, **_):
        if not planned:
            return response
        return _response_from_artifact_assumption_edit_plan(
            plan=ArtifactAssumptionEditPlan(
                outcome="ready_to_confirm",
                operations=[EditOperation(op="set", target="capital", number=amount)],
            ),
            request=request,
            primary_draft=response.candidate_strategy_draft,
        )

    monkeypatch.setattr(
        llm_interpreter, "_audited_response_ready_for_runtime", audited_response
    )
    result = await execute_tool_calls_async(
        state=RunState(
            current_user_message=case.prompt,
            intent="calculate",
            task_relation="continue",
            semantic_turn_act="refine_current_idea",
            recent_thread_history=case.recent_thread_history,
            tool_calls=[
                {
                    "call_id": "capital-edit",
                    "tool_name": "backtest",
                    "arguments": {
                        "strategy": {
                            "strategy_type": case.expected.strategy_type,
                            "asset_universe": list(case.expected.assets),
                            "capital_amount": amount,
                            "field_provenance": {"capital_amount": "explicit_user"},
                        }
                    },
                }
            ],
        ),
        tool=object(),
        user=UserState(user_id="declared-edit", language_preference=case.user_language),
        latest_task_snapshot=case.snapshot,
        selected_thread_metadata=case.thread_metadata,
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = StrategySummary.model_validate(result.patch["candidate_strategy_draft"])
    assert strategy.capital_amount == amount
    assert strategy.date_range == case.expected.date_range
    assert strategy.asset_universe == list(case.expected.assets)


@pytest.mark.parametrize(
    "supplied",
    [
        {"entry_logic": "incomplete signal"},
        {"strategy_type": "options_straddle"},
        {"requested_strategy_template": "moving_average_crossover"},
        {"capital_amount": 0},
    ],
)
def test_date_recovery_preserves_unresolved_strategy_blockers(supplied: dict) -> None:
    strategy = StrategySummary.model_validate(
        {
            "strategy_type": "signal_strategy",
            "date_range": {"start": "2019-10-01", "end": "2025-10-31"},
            **supplied,
        }
    )
    blocker = UnsupportedConstraint(
        category="unsupported_strategy_logic",
        raw_value="unresolved supplied strategy",
        explanation="The supplied strategy is not yet executable.",
    )
    result = _deterministic_result_artifact_patch_stage_result_if_applicable(
        decision=InterpretDecision(
            intent="calculate",
            task_relation="continue",
            semantic_turn_act="refine_current_idea",
            user_goal_summary="Refine the completed run",
            requires_clarification=True,
            confidence=0.9,
            effective_response_profile=resolve_effective_response_profile(
                user=UserState(user_id="declared-edit")
            ),
            candidate_strategy_draft=strategy,
            unsupported_constraints=[blocker],
        ),
        snapshot=_latest_dca_result_snapshot(),
        current_user_message="",
    )

    assert result is not None
    assert result.outcome == "needs_clarification"
    assert result.decision is not None
    assert (
        result.decision.candidate_strategy_draft.strategy_type == strategy.strategy_type
    )
    assert result.decision.unsupported_constraints == [blocker]
