# ruff: noqa: F403, F405
from __future__ import annotations

from argus.agent_runtime.graph.workflow import build_workflow
from argus.agent_runtime.profile.response_profile import (
    resolve_effective_response_profile,
)
from argus.agent_runtime.runtime import run_agent_turn
from argus.agent_runtime.stages.interpret_internal.latest_result_answer import (
    latest_result_answer_stage_result_if_applicable,
)
from argus.agent_runtime.stages.interpret_types import (
    InterpretDecision,
    StructuredInterpretation,
)
from langgraph.checkpoint.memory import MemorySaver

from tests.agent_runtime._llm_interpreter_common import *


def _latest_result_reference(*, include_curve: bool = True) -> ArtifactReference:
    metadata = {
        "run_id": "run-140",
        "conversation_id": "conversation-140",
        "strategy_id": "strategy-140",
        "asset_class": "equity",
        "symbols": ["COST", "TGT"],
        "benchmark_symbol": "SPY",
        "metrics": {
            "aggregate": {
                "performance": {
                    "total_return_pct": 28.4,
                    "portfolio_value_range": {
                        "peak_value": 14500.25,
                        "lowest_value": 9100.0,
                        "currency": "USD",
                        "source": "strategy_portfolio_equity_close",
                    },
                },
                "risk": {"max_drawdown_pct": -12.3},
            },
            "by_symbol": {},
        },
        "config_snapshot": {
            "template": "dca_accumulation",
            "symbols": ["COST", "TGT"],
            "date_range": {"start": "2020-02-01", "end": "2026-07-02"},
        },
    }
    if include_curve:
        metadata["chart"] = {
            "kind": "portfolio_equity",
            "currency": "USD",
            "series": [
                {"time": "2020-02-03", "value": 10000.0},
                {"time": "2021-11-09", "value": 14500.25},
                {"time": "2022-06-16", "value": 12716.72},
                {"time": "2026-07-02", "value": 13900.0},
            ],
            "value_summary": {
                "peak_value": 14500.25,
                "lowest_value": 10000.0,
                "currency": "USD",
                "source": "strategy_portfolio_equity_close",
            },
        }
    return ArtifactReference(
        artifact_kind="backtest_result",
        artifact_id="run-140",
        artifact_status="completed",
        metadata=metadata,
    )


def _decision(focus: str) -> InterpretDecision:
    user = UserState(user_id="u1")
    return InterpretDecision(
        intent="results_explanation",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asked about the latest result.",
        candidate_strategy_draft=StrategySummary(),
        missing_required_fields=[],
        optional_parameter_opportunity=[],
        confidence=0.9,
        arbitration_mode="structured_arbitration",
        reason_codes=["llm_interpreter_used"],
        effective_response_profile=resolve_effective_response_profile(
            user=user,
            explicit_overrides=None,
        ),
        semantic_turn_act="result_followup",
        result_followup_focus=focus,
        artifact_target="latest_result",
    )


def _snapshot(*, include_curve: bool = True, pending: bool = False) -> TaskSnapshot:
    reference = _latest_result_reference(include_curve=include_curve)
    return TaskSnapshot(
        latest_task_type="results_explanation",
        completed=True,
        pending_strategy_summary=(
            StrategySummary(
                strategy_type="dca_accumulation",
                strategy_thesis="Refine the latest result.",
                asset_universe=["COST", "TGT"],
                asset_class="equity",
                date_range={"start": "2020-02-01", "end": "2026-07-02"},
                cadence="monthly",
                extra_parameters={"recurring_contribution": 500},
            )
            if pending
            else None
        ),
        latest_backtest_result_reference=reference,
        artifact_references=[reference],
    )


class _StaticInterpreter:
    def __init__(self, response: StructuredInterpretation) -> None:
        self.response = response
        self.requests: list[InterpretationRequest] = []

    def __call__(self, request: InterpretationRequest) -> StructuredInterpretation:
        self.requests.append(request)
        return self.response


@pytest.mark.parametrize(
    "message",
    [
        "could you tell me what date this strategy was at peak value?",
        "what date did this strategy peak in value?",
    ],
)
def test_latest_result_peak_date_questions_answer_from_curve_facts(message: str) -> None:
    result = latest_result_answer_stage_result_if_applicable(
        decision=_decision("peak_date"),
        snapshot=_snapshot(),
        language="en",
    )

    assert result is not None
    answer = result.patch["assistant_response"]
    assert "2021-11-09" in answer
    assert "$14,500.25" in answer
    assert result.patch["result_run_id"] == "run-140"
    assert result.patch["latest_run_id"] == "run-140"
    assert result.patch["result_conversation_id"] == "conversation-140"
    assert "latest_result_fact_answer" in result.decision.reason_codes
    assert message


def test_latest_result_peak_value_question_answers_from_canonical_value() -> None:
    result = latest_result_answer_stage_result_if_applicable(
        decision=_decision("peak_value"),
        snapshot=_snapshot(),
        language="en",
    )

    assert result is not None
    answer = result.patch["assistant_response"]
    assert "$14,500.25" in answer
    assert "2021-11-09" in answer


def test_latest_result_fact_answer_uses_typed_turn_language() -> None:
    decision = _decision("peak_date").model_copy(
        update={
            "detected_user_language": "es-419",
            "candidate_strategy_draft": StrategySummary(
                extra_parameters={"language": "en"}
            )
        }
    )

    result = latest_result_answer_stage_result_if_applicable(
        decision=decision,
        snapshot=_snapshot(),
        language="en",
    )

    assert result is not None
    answer = result.patch["assistant_response"]
    # A peak_date question gets a date heading, not the value heading; the body
    # remaining in Spanish confirms the typed es-419 turn language was used.
    assert "Fecha máxima" in answer
    assert "El valor máximo de la cartera fue $14,500.25 el 2021-11-09" in answer
    assert "The peak portfolio value" not in answer


@pytest.mark.asyncio
async def test_workflow_latest_result_fact_answer_uses_typed_turn_language() -> None:
    interpreter = _StaticInterpreter(
        StructuredInterpretation(
            intent="results_explanation",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="El usuario preguntó por el punto máximo.",
            detected_user_language="es-419",
            semantic_turn_act="result_followup",
            result_followup_focus="peak_date",
            artifact_target="latest_result",
            confidence=0.9,
        )
    )
    workflow = build_workflow(
        structured_interpreter=interpreter,
        checkpointer=MemorySaver(),
    )

    result = await run_agent_turn(
        workflow=workflow,
        user=UserState(user_id="u1", language_preference="en"),
        thread_id="thread-issue-140-spanish-turn-language",
        message="¿En qué fecha alcanzó su punto máximo?",
        fallback_latest_task_snapshot=_snapshot(),
    )

    assert result["stage_outcome"] == "ready_to_respond"
    assert "Fecha máxima" in result["assistant_response"]
    assert "El valor máximo de la cartera fue $14,500.25 el 2021-11-09" in (
        result["assistant_response"]
    )
    assert "The peak portfolio value" not in result["assistant_response"]


def test_latest_result_drawdown_date_question_answers_from_curve_facts() -> None:
    result = latest_result_answer_stage_result_if_applicable(
        decision=_decision("drawdown_date"),
        snapshot=_snapshot(),
        language="en",
    )

    assert result is not None
    answer = result.patch["assistant_response"]
    assert "2022-06-16" in answer
    assert "12.3%" in answer


def test_latest_result_missing_peak_date_returns_typed_limitation() -> None:
    result = latest_result_answer_stage_result_if_applicable(
        decision=_decision("peak_date"),
        snapshot=_snapshot(include_curve=False),
        language="en",
    )

    assert result is not None
    assert "exact peak date is not available" in result.patch["assistant_response"]
    assert result.patch["response_intent"]["kind"] == "unsupported_recovery"
    assert result.patch["response_intent"]["facts"]["limitation_code"] == (
        "latest_result_metric_unavailable"
    )
    assert result.patch["response_intent"]["facts"]["requested_metric"] == "peak_date"
    assert "latest_result_fact_limitation" in result.decision.reason_codes


def test_latest_result_unknown_metric_returns_typed_limitation() -> None:
    result = latest_result_answer_stage_result_if_applicable(
        decision=_decision("result_card_fact").model_copy(
            update={"result_followup_fact_key": "sortino_ratio"}
        ),
        snapshot=_snapshot(),
        language="en",
    )

    assert result is not None
    assert "exact Sortino ratio is not available" in result.patch["assistant_response"]
    assert result.patch["response_intent"]["kind"] == "unsupported_recovery"
    facts = result.patch["response_intent"]["facts"]
    assert facts["limitation_code"] == "latest_result_metric_unavailable"
    assert facts["requested_metric"] == "sortino_ratio"
    assert "total_return" in facts["available_result_facts"]
    assert "latest_result_fact_limitation" in result.decision.reason_codes


def test_pending_refine_result_question_answers_without_clearing_pending_state() -> None:
    snapshot = _snapshot(pending=True)
    result = latest_result_answer_stage_result_if_applicable(
        decision=_decision("peak_date").model_copy(
            update={"artifact_target": "pending_refinement"}
        ),
        snapshot=snapshot,
        language="en",
    )

    assert result is not None
    assert result.outcome == "ready_to_respond"
    assert snapshot.pending_strategy_summary is not None
    assert snapshot.pending_strategy_summary.asset_universe == ["COST", "TGT"]
    assert result.patch["candidate_strategy_draft"]["asset_universe"] == []
    assert "requested_field" not in result.stage_patch
    assert result.patch["result_run_id"] == "run-140"


@pytest.mark.asyncio
async def test_workflow_refine_then_result_fact_answer_keeps_pending_state() -> None:
    interpreter = _StaticInterpreter(
        StructuredInterpretation(
            intent="results_explanation",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User asked about the latest result peak.",
            semantic_turn_act="result_followup",
            result_followup_focus="peak_date",
            artifact_target="latest_result",
            confidence=0.9,
        )
    )
    workflow = build_workflow(
        structured_interpreter=interpreter,
        checkpointer=MemorySaver(),
    )
    thread_id = "thread-issue-140-refine-fact"

    result = await run_agent_turn(
        workflow=workflow,
        user=UserState(user_id="u1"),
        thread_id=thread_id,
        message="what date did this strategy peak in value?",
        fallback_latest_task_snapshot=_snapshot(pending=True),
        fallback_selected_thread_metadata={
            "latest_task_type": "backtest_execution",
            "last_stage_outcome": "await_user_reply",
            "requested_field": "refinement",
            "source_result_run_id": "run-140",
        },
    )

    assert result["stage_outcome"] == "ready_to_respond"
    assert "2021-11-09" in result["assistant_response"]
    assert result["latest_run_id"] == "run-140"
    assert result["result_run_id"] == "run-140"
    state = await workflow.aget_state({"configurable": {"thread_id": thread_id}})
    snapshot = state.values["latest_task_snapshot"]
    assert snapshot.pending_strategy_summary is not None
    assert snapshot.pending_strategy_summary.asset_universe == ["COST", "TGT"]
    assert state.values["selected_thread_metadata"]["requested_field"] == "refinement"


@pytest.mark.asyncio
async def test_workflow_result_fact_limitation_exposes_response_intent() -> None:
    interpreter = _StaticInterpreter(
        StructuredInterpretation(
            intent="results_explanation",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User asked about an unavailable result metric.",
            semantic_turn_act="result_followup",
            result_followup_focus="result_card_fact",
            result_followup_fact_key="sortino_ratio",
            artifact_target="latest_result",
            confidence=0.9,
        )
    )
    workflow = build_workflow(
        structured_interpreter=interpreter,
        checkpointer=MemorySaver(),
    )

    result = await run_agent_turn(
        workflow=workflow,
        user=UserState(user_id="u1"),
        thread_id="thread-issue-140-unsupported-result-fact",
        message="What was the Sortino ratio?",
        fallback_latest_task_snapshot=_snapshot(),
    )

    assert result["stage_outcome"] == "ready_to_respond"
    assert result["response_intent"]["kind"] == "unsupported_recovery"
    facts = result["response_intent"]["facts"]
    assert facts["limitation_code"] == "latest_result_metric_unavailable"
    assert facts["requested_metric"] == "sortino_ratio"
