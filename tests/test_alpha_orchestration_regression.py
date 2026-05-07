from __future__ import annotations

import pytest
from argus.agent_runtime.graph.workflow import build_workflow
from argus.agent_runtime.runtime import run_agent_turn
from argus.agent_runtime.stages.interpret import (
    InterpretationRequest,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import (
    ConversationMessage,
    StrategySummary,
    UserState,
)
from langgraph.checkpoint.memory import MemorySaver


class ResolvedAssetStub:
    def __init__(self, canonical_symbol: str, asset_class: str) -> None:
        self.canonical_symbol = canonical_symbol
        self.asset_class = asset_class


@pytest.mark.asyncio
async def test_spanish_multiturn_strategy_context_uses_agent_runtime(monkeypatch) -> None:
    from argus.agent_runtime.extraction import structured as extraction_module
    from argus.agent_runtime.stages import interpret as interpret_module

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        return ResolvedAssetStub(symbol.upper(), "equity")

    monkeypatch.setattr(interpret_module, "resolve_asset", resolve_stub)
    monkeypatch.setattr(extraction_module, "resolve_asset", resolve_stub)

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

    class Interpreter:
        async def ainvoke(
            self, request: InterpretationRequest
        ) -> StructuredInterpretation:
            seen_requests.append(request)
            return next(responses)

    workflow = build_workflow(
        structured_interpreter=Interpreter(),
        checkpointer=MemorySaver(),
    )
    user = UserState(user_id="u1", language_preference="es-419")
    thread_id = "thread-spanish-context"

    first = await run_agent_turn(
        workflow=workflow,
        user=user,
        thread_id=thread_id,
        message="quiero probar un backtest",
    )
    second = await run_agent_turn(
        workflow=workflow,
        user=user,
        thread_id=thread_id,
        message="quiero probar una reversion a la media con RSI",
        recent_thread_history=[
            ConversationMessage(role="user", content="quiero probar un backtest"),
            ConversationMessage(
                role="assistant",
                content=str(first.get("assistant_prompt") or ""),
            ),
        ],
    )
    third = await run_agent_turn(
        workflow=workflow,
        user=user,
        thread_id=thread_id,
        message="Quiero GOOG, con capital de 10mil, 1 anio hacia atras desde hoy",
        recent_thread_history=[
            ConversationMessage(role="user", content="quiero probar un backtest"),
            ConversationMessage(
                role="assistant",
                content=str(first.get("assistant_prompt") or ""),
            ),
            ConversationMessage(
                role="user",
                content="quiero probar una reversion a la media con RSI",
            ),
            ConversationMessage(
                role="assistant",
                content=str(second.get("assistant_prompt") or ""),
            ),
        ],
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
