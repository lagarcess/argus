from __future__ import annotations

from types import SimpleNamespace

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
from argus.nlp.natural_time import resolve_date_range_intent
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

    def resolve_candidate_stub(
        symbol: str,
        *,
        field: str,
        source: str,
    ) -> SimpleNamespace:
        del field, source
        return SimpleNamespace(status="resolved", asset=resolve_stub(symbol))

    monkeypatch.setattr(interpret_module, "resolve_asset", resolve_stub)
    monkeypatch.setattr(
        extraction_module,
        "resolve_asset_candidate",
        resolve_candidate_stub,
    )

    date_range_intent = {
        "kind": "rolling_window",
        "count": 1,
        "unit": "year",
        "anchor": "today",
        "confidence": 0.95,
        "evidence": "1 anio hacia atras desde hoy",
    }
    resolved_date_range = resolve_date_range_intent(date_range_intent)
    assert resolved_date_range is not None

    # These injected responses validate downstream state application only. Real
    # interpreter classification must be validated separately by the live gate.
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
                    raw_user_phrasing=("quiero probar una reversion a la media con RSI"),
                    strategy_type="indicator_threshold",
                    strategy_thesis="Comprar cuando RSI indica sobreventa.",
                    entry_logic="RSI drops below 30",
                    exit_logic="RSI rises above 55",
                    extra_parameters={
                        "indicator": "rsi",
                        "indicator_parameters": {
                            "indicator": "rsi",
                            "indicator_period": 14,
                            "entry_threshold": 30,
                            "exit_threshold": 55,
                        },
                    },
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
                    date_range=resolved_date_range.payload,
                    sizing_mode="capital_amount",
                    capital_amount=10000,
                    extra_parameters={
                        "indicator": "rsi",
                        "indicator_parameters": {
                            "indicator": "rsi",
                            "indicator_period": 14,
                            "entry_threshold": 30,
                            "exit_threshold": 55,
                        },
                        "date_range_raw_text": "1 anio hacia atras desde hoy",
                        "date_range_intent": date_range_intent,
                        "evidence_spans": {
                            "asset_universe": "GOOG",
                            "capital_amount": "10mil",
                            "date_range": "1 anio hacia atras desde hoy",
                        },
                        "field_provenance": {
                            "asset_universe": "explicit_user",
                            "capital_amount": "starting_capital",
                            "date_range": "explicit_user",
                        },
                    },
                ),
                semantic_turn_act="answer_pending_need",
                reason_codes=["artifact_assumption_edit_planned"],
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
    confirmed_strategy = third["confirmation_payload"]["strategy"]
    confirmed_range = confirmed_strategy["date_range"]
    assert confirmed_range["start"] == resolved_date_range.payload["start"]
    if confirmed_range["end"] != resolved_date_range.payload["end"]:
        availability_adjustment = confirmed_strategy["extra_parameters"][
            "data_availability_adjustment"
        ]
        assert (
            availability_adjustment["original_end"]
            == (resolved_date_range.payload["end"])
        )
        assert availability_adjustment["through"] == confirmed_range["end"]
    assert confirmed_strategy["extra_parameters"]["date_range_intent"] == (
        date_range_intent
    )
    assert confirmed_strategy["extra_parameters"]["field_provenance"] == {
        "asset_universe": "explicit_user",
        "capital_amount": "starting_capital",
        "date_range": "explicit_user",
    }
    assert confirmed_strategy["extra_parameters"]["evidence_spans"] == {
        "asset_universe": "GOOG",
        "capital_amount": "10mil",
        "date_range": "1 anio hacia atras desde hoy",
    }
    assert confirmed_strategy["capital_amount"] == 10000
    assert third["confirmation_payload"]["validation"]["status"] == "ready_to_run"
    assert seen_requests[1].latest_task_snapshot is not None
    assert seen_requests[2].latest_task_snapshot is not None
    assert len(seen_requests[2].recent_thread_history) >= 2
