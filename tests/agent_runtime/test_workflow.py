from __future__ import annotations

from argus.agent_runtime.graph.workflow import (
    WorkflowStageOutcome,
    build_workflow,
)
from argus.agent_runtime.runtime import run_agent_turn
from argus.agent_runtime.session.manager import InMemorySessionManager
from argus.agent_runtime.stages.interpret import (
    InterpretationRequest,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import RunState, StrategySummary, UserState


class ResolvedAssetStub:
    def __init__(self, canonical_symbol: str, asset_class: str) -> None:
        self.canonical_symbol = canonical_symbol
        self.asset_class = asset_class


def rsi_confirmation_interpreter(
    request: InterpretationRequest,
) -> StructuredInterpretation:
    return StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User is ready to confirm an RSI backtest.",
        candidate_strategy_draft=StrategySummary(
            raw_user_phrasing=request.current_user_message,
            strategy_type="rsi_threshold",
            strategy_thesis=request.current_user_message,
            asset_universe=["TSLA"],
            asset_class="equity",
            date_range="last year",
            entry_logic="RSI drops below 30",
            exit_logic="RSI rises above 55",
        ),
        confidence=0.94,
        semantic_turn_act="new_idea",
    )


def conversational_interpreter(
    request: InterpretationRequest,
) -> StructuredInterpretation:
    return StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asked a product question.",
        assistant_response="I help turn investing ideas into supported backtests.",
        confidence=0.94,
        semantic_turn_act="educational_question",
    )


def test_workflow_requires_confirmation_before_execute(monkeypatch) -> None:
    from argus.agent_runtime.extraction import structured as extraction_module
    from argus.agent_runtime.stages import interpret as interpret_module

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        return ResolvedAssetStub(symbol.upper(), "equity")

    monkeypatch.setattr(interpret_module, "resolve_asset", resolve_stub)
    monkeypatch.setattr(extraction_module, "resolve_asset", resolve_stub)

    workflow = build_workflow(structured_interpreter=rsi_confirmation_interpreter)
    manager = InMemorySessionManager()
    user = UserState(user_id="u1", expertise_level="advanced")

    result = run_agent_turn(
        workflow=workflow,
        session_manager=manager,
        user=user,
        thread_id="thread-1",
        message=(
            "Backtest Tesla when RSI drops below 30 and exit above 55 "
            "over the last year"
        ),
    )

    assert result["stage_outcome"] == "await_approval"
    assert result["confirmation_payload"]["strategy"]["asset_universe"] == ["TSLA"]
    assert "I read this as" in result["assistant_prompt"]


def test_workflow_routes_from_stage_outcome_without_persisting_route() -> None:
    workflow = build_workflow(structured_interpreter=conversational_interpreter)
    initial_state = {
        "run_state": RunState.new(
            current_user_message="what can you do?",
            recent_thread_history=[],
        ),
        "user": UserState(user_id="u1", expertise_level="beginner"),
        "latest_task_snapshot": None,
    }

    result = workflow.invoke(initial_state)

    assert result["stage_outcome"] is WorkflowStageOutcome.READY_TO_RESPOND
    assert result["assistant_response"] == (
        "I help turn investing ideas into supported backtests."
    )
    assert "route" not in result


def test_workflow_persists_llm_first_thread_history() -> None:
    workflow = build_workflow(structured_interpreter=conversational_interpreter)
    manager = InMemorySessionManager()
    user = UserState(user_id="u1", expertise_level="advanced")

    run_agent_turn(
        workflow=workflow,
        session_manager=manager,
        user=user,
        thread_id="thread-history",
        message="what can you do?",
    )

    thread = manager.load_thread(user_id=user.user_id, thread_id="thread-history")

    assert len(thread.message_history) == 2
    assert thread.message_history[0].role == "user"
    assert thread.message_history[1].role == "assistant"
    assert thread.latest_task_snapshot is not None
    assert thread.latest_task_snapshot.completed is True
