from __future__ import annotations

from argus.agent_runtime.graph.workflow import build_workflow
from argus.agent_runtime.runtime import run_agent_turn
from argus.agent_runtime.session.manager import InMemorySessionManager
from argus.agent_runtime.stages.interpret import (
    InterpretationRequest,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import StrategySummary, UserState


def test_spanish_multiturn_strategy_context_uses_agent_runtime() -> None:
    responses = iter(
        [
            StructuredInterpretation(
                intent="strategy_drafting",
                task_relation="new_task",
                requires_clarification=True,
                user_goal_summary="El usuario quiere probar un backtest.",
                candidate_strategy_draft=StrategySummary(
                    raw_user_phrasing="quiero probar un backtest",
                    strategy_thesis="El usuario quiere preparar un backtest.",
                ),
                missing_required_fields=["strategy_type", "asset_universe"],
                semantic_turn_act="new_idea",
            ),
            StructuredInterpretation(
                intent="strategy_drafting",
                task_relation="refine",
                requires_clarification=True,
                user_goal_summary="El usuario eligio una regla RSI.",
                candidate_strategy_draft=StrategySummary(
                    raw_user_phrasing=(
                        "quiero probar una reversion a la media con RSI"
                    ),
                    strategy_type="indicator_threshold",
                    strategy_thesis="Comprar cuando RSI indica sobreventa.",
                    entry_logic="RSI drops below 30",
                    exit_logic="RSI rises above 55",
                ),
                missing_required_fields=["asset_universe", "date_range"],
                semantic_turn_act="answer_pending_need",
            ),
            StructuredInterpretation(
                intent="backtest_execution",
                task_relation="refine",
                requires_clarification=False,
                user_goal_summary="El usuario completo activo, capital y periodo.",
                candidate_strategy_draft=StrategySummary(
                    raw_user_phrasing=(
                        "Quiero GOOG, con capital de 10mil, 1 anio hacia atras "
                        "desde hoy"
                    ),
                    strategy_type="indicator_threshold",
                    strategy_thesis="Comprar GOOG cuando RSI indica sobreventa.",
                    asset_universe=["GOOG"],
                    asset_class="equity",
                    entry_logic="RSI drops below 30",
                    exit_logic="RSI rises above 55",
                    date_range="last year",
                    sizing_mode="capital_amount",
                    capital_amount=10000,
                ),
                semantic_turn_act="answer_pending_need",
            ),
        ]
    )
    seen_requests: list[InterpretationRequest] = []

    def interpreter(request: InterpretationRequest) -> StructuredInterpretation:
        seen_requests.append(request)
        return next(responses)

    workflow = build_workflow(structured_interpreter=interpreter)
    manager = InMemorySessionManager()
    user = UserState(user_id="u1", language_preference="es-419")
    thread_id = "thread-spanish-context"

    first = run_agent_turn(
        workflow=workflow,
        session_manager=manager,
        user=user,
        thread_id=thread_id,
        message="quiero probar un backtest",
    )
    second = run_agent_turn(
        workflow=workflow,
        session_manager=manager,
        user=user,
        thread_id=thread_id,
        message="quiero probar una reversion a la media con RSI",
    )
    third = run_agent_turn(
        workflow=workflow,
        session_manager=manager,
        user=user,
        thread_id=thread_id,
        message="Quiero GOOG, con capital de 10mil, 1 anio hacia atras desde hoy",
    )

    assert first["stage_outcome"] == "await_user_reply"
    assert second["stage_outcome"] == "await_user_reply"
    assert third["stage_outcome"] == "await_approval"
    assert third["confirmation_payload"]["strategy"]["asset_universe"] == ["GOOG"]
    assert third["confirmation_payload"]["strategy"]["strategy_type"] == (
        "indicator_threshold"
    )
    assert seen_requests[1].latest_task_snapshot is not None
    assert seen_requests[2].latest_task_snapshot is not None
    assert len(seen_requests[2].recent_thread_history) >= 2
