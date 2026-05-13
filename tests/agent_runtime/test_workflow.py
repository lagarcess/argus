from __future__ import annotations

import pytest
from argus.agent_runtime.graph.workflow import build_workflow
from argus.agent_runtime.runtime import run_agent_turn, stream_agent_turn_events
from argus.agent_runtime.stages.interpret import (
    InterpretationRequest,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import StrategySummary, TaskSnapshot, UserState
from langgraph.checkpoint.memory import MemorySaver


class ResolvedAssetStub:
    def __init__(self, canonical_symbol: str, asset_class: str) -> None:
        self.canonical_symbol = canonical_symbol
        self.asset_class = asset_class


class RsiConfirmationInterpreter:
    async def ainvoke(self, request: InterpretationRequest) -> StructuredInterpretation:
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


class RunnableDraftClarifyingInterpreter:
    async def ainvoke(self, request: InterpretationRequest) -> StructuredInterpretation:
        return StructuredInterpretation(
            intent="backtest_execution",
            task_relation="continue",
            requires_clarification=True,
            user_goal_summary="User supplied the missing asset for a runnable draft.",
            candidate_strategy_draft=StrategySummary(
                raw_user_phrasing=request.current_user_message,
                strategy_type="buy_and_hold",
                strategy_thesis="Buy and hold Apple.",
                asset_universe=["AAPL"],
                asset_class="equity",
                date_range="last year",
            ),
            confidence=0.94,
            semantic_turn_act="answer_pending_need",
        )


class AssetAnswerInterpreter:
    async def ainvoke(self, request: InterpretationRequest) -> StructuredInterpretation:
        return StructuredInterpretation(
            intent="backtest_execution",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User supplied the replacement asset.",
            candidate_strategy_draft=StrategySummary(asset_universe=["TSLA"]),
            confidence=0.94,
            semantic_turn_act="answer_pending_need",
        )


class ConversationalInterpreter:
    async def ainvoke(self, request: InterpretationRequest) -> StructuredInterpretation:
        return StructuredInterpretation(
            intent="conversation_followup",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User asked a product question.",
            assistant_response="I help turn investing ideas into supported backtests.",
            confidence=0.94,
            semantic_turn_act="educational_question",
        )


class ApprovalInterpreter:
    def __init__(self) -> None:
        self.seen_snapshots: list[object] = []

    async def ainvoke(self, request: InterpretationRequest) -> StructuredInterpretation:
        self.seen_snapshots.append(request.latest_task_snapshot)
        if len(self.seen_snapshots) == 1:
            return StructuredInterpretation(
                intent="backtest_execution",
                task_relation="new_task",
                requires_clarification=False,
                user_goal_summary="User is drafting a buy and hold backtest.",
                candidate_strategy_draft=StrategySummary(
                    raw_user_phrasing=request.current_user_message,
                    strategy_type="buy_and_hold",
                    strategy_thesis=request.current_user_message,
                    asset_universe=["BTC"],
                    asset_class="crypto",
                    date_range="last year",
                ),
                confidence=0.94,
                semantic_turn_act="new_idea",
            )
        return StructuredInterpretation(
            intent="backtest_execution",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User approved the pending strategy.",
            candidate_strategy_draft=StrategySummary(),
            confidence=0.96,
            semantic_turn_act="approval",
        )


@pytest.mark.asyncio
async def test_workflow_requires_confirmation_before_execute(monkeypatch) -> None:
    from argus.agent_runtime import resolution as resolution_module

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        return ResolvedAssetStub(symbol.upper(), "equity")

    monkeypatch.setattr(resolution_module, "resolve_market_asset", resolve_stub)

    workflow = build_workflow(
        structured_interpreter=RsiConfirmationInterpreter(),
        checkpointer=MemorySaver(),
    )
    user = UserState(user_id="u1", expertise_level="advanced")

    result = await run_agent_turn(
        workflow=workflow,
        user=user,
        thread_id="thread-1",
        message=(
            "Backtest Tesla when RSI drops below 30 and exit above 55 "
            "over the last year"
        ),
    )

    assert result["stage_outcome"] == "await_approval"
    assert result["confirmation_payload"]["strategy"]["asset_universe"] == ["TSLA"]
    assert result["pending_strategy"]["strategy"]["asset_universe"] == ["TSLA"]
    assert result["pending_strategy"]["missing_required_fields"] == []
    assert "I read this as" in result["assistant_prompt"]


@pytest.mark.asyncio
async def test_workflow_confirms_runnable_draft_instead_of_optional_settings_prompt(
    monkeypatch,
) -> None:
    from argus.agent_runtime import resolution as resolution_module

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        return ResolvedAssetStub(symbol.upper(), "equity")

    monkeypatch.setattr(resolution_module, "resolve_market_asset", resolve_stub)

    workflow = build_workflow(
        structured_interpreter=RunnableDraftClarifyingInterpreter(),
        checkpointer=MemorySaver(),
    )
    user = UserState(user_id="u1", expertise_level="beginner")

    result = await run_agent_turn(
        workflow=workflow,
        user=user,
        thread_id="thread-optional-defaults",
        message="yes AAPL stock",
        fallback_latest_task_snapshot=TaskSnapshot(
            pending_strategy_summary=StrategySummary(
                strategy_type="buy_and_hold",
                strategy_thesis="Hold Apple stock for one year.",
                asset_class="equity",
                date_range="last year",
            )
        ),
        fallback_selected_thread_metadata={"last_stage_outcome": "await_user_reply"},
    )

    assert result["stage_outcome"] == "await_approval"
    assert result["confirmation_payload"]["strategy"]["asset_universe"] == ["AAPL"]
    assert (
        result["confirmation_payload"]["optional_parameters"]["initial_capital"]["value"]
        == 1000.0
    )
    assert "optional_parameter_choices" not in result


@pytest.mark.asyncio
async def test_workflow_clears_requested_field_after_chip_answer_confirmation(
    monkeypatch,
) -> None:
    from argus.agent_runtime import resolution as resolution_module

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        return ResolvedAssetStub(symbol.upper(), "equity")

    monkeypatch.setattr(resolution_module, "resolve_market_asset", resolve_stub)

    workflow = build_workflow(
        structured_interpreter=AssetAnswerInterpreter(),
        checkpointer=MemorySaver(),
    )
    user = UserState(user_id="u1", expertise_level="beginner")
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Nvidia.",
        asset_universe=["NVDA"],
        asset_class="equity",
        date_range="last year",
    )

    prompt_result = await run_agent_turn(
        workflow=workflow,
        user=user,
        thread_id="thread-chip-answer",
        message="Change asset",
        action_context={
            "type": "change_asset",
            "label": "Change asset",
            "presentation": "confirmation",
            "payload": {},
        },
        fallback_latest_task_snapshot=TaskSnapshot(
            pending_strategy_summary=pending,
        ),
        fallback_selected_thread_metadata={"last_stage_outcome": "await_approval"},
    )

    assert prompt_result["stage_outcome"] == "await_user_reply"
    assert prompt_result["pending_strategy"]["requested_field"] == "asset_universe"

    answer_result = await run_agent_turn(
        workflow=workflow,
        user=user,
        thread_id="thread-chip-answer",
        message="TSLA",
    )

    assert answer_result["stage_outcome"] == "await_approval"
    assert answer_result["confirmation_payload"]["strategy"]["asset_universe"] == ["TSLA"]
    assert answer_result["pending_strategy"]["requested_field"] is None
    assert answer_result["pending_strategy"]["missing_required_fields"] == []


@pytest.mark.asyncio
async def test_workflow_routes_from_stage_outcome_without_persisting_route() -> None:
    workflow = build_workflow(
        structured_interpreter=ConversationalInterpreter(),
        checkpointer=MemorySaver(),
    )

    result = await run_agent_turn(
        workflow=workflow,
        user=UserState(user_id="u1", expertise_level="beginner"),
        thread_id="thread-1",
        message="what can you do?",
    )
    assert result["stage_outcome"] == "ready_to_respond"
    assert result["assistant_response"] == (
        "I help turn investing ideas into supported backtests."
    )
    assert "route" not in result


@pytest.mark.asyncio
async def test_workflow_streams_stage_events_and_final_payload() -> None:
    workflow = build_workflow(
        structured_interpreter=ConversationalInterpreter(),
        checkpointer=MemorySaver(),
    )
    user = UserState(user_id="u1", expertise_level="advanced")

    events = [
        event
        async for event in stream_agent_turn_events(
            workflow=workflow,
            user=user,
            thread_id="thread-events",
            message="what can you do?",
        )
    ]

    assert events[0] == {"type": "stage_start", "stage": "interpret"}
    assert {"type": "stage_outcome", "outcome": "ready_to_respond"} in events
    assert events[-1]["type"] == "final"
    assert events[-1]["payload"]["assistant_response"] == (
        "I help turn investing ideas into supported backtests."
    )


@pytest.mark.asyncio
async def test_workflow_preserves_pending_draft_after_interpreter_recovery() -> None:
    workflow = build_workflow(checkpointer=MemorySaver())
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Apple.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range="past year",
        capital_amount=10000,
    )

    result = await run_agent_turn(
        workflow=workflow,
        user=UserState(user_id="u1", expertise_level="beginner"),
        thread_id="thread-recovery",
        message="actually make it NVDA",
        fallback_latest_task_snapshot=TaskSnapshot(
            latest_task_type="backtest_execution",
            completed=False,
            pending_strategy_summary=pending,
        ),
        fallback_selected_thread_metadata={"last_stage_outcome": "await_approval"},
    )

    assert result["stage_outcome"] == "ready_to_respond"
    assert "AAPL" in result["assistant_response"]
    state_snapshot = await workflow.aget_state(
        {"configurable": {"thread_id": "thread-recovery"}}
    )
    snapshot = state_snapshot.values["latest_task_snapshot"]
    assert snapshot.completed is False
    assert snapshot.pending_strategy_summary is not None
    assert snapshot.pending_strategy_summary.asset_universe == ["AAPL"]
    assert snapshot.confirmed_strategy_summary is None


@pytest.mark.asyncio
async def test_workflow_uses_checkpointer_for_thread_state(monkeypatch) -> None:
    from argus.agent_runtime import resolution as resolution_module

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        asset_class = "crypto" if symbol.upper() == "BTC" else "equity"
        return ResolvedAssetStub(symbol.upper(), asset_class)

    monkeypatch.setattr(resolution_module, "resolve_market_asset", resolve_stub)

    interpreter = ApprovalInterpreter()
    workflow = build_workflow(
        structured_interpreter=interpreter,
        checkpointer=MemorySaver(),
    )
    user = UserState(user_id="u1", expertise_level="advanced")

    first = await run_agent_turn(
        workflow=workflow,
        user=user,
        thread_id="thread-checkpoint",
        message="Buy and hold Bitcoin over the last year.",
    )
    second = await run_agent_turn(
        workflow=workflow,
        user=user,
        thread_id="thread-checkpoint",
        message="yes, run it",
    )

    assert first["stage_outcome"] == "await_approval"
    assert interpreter.seen_snapshots[0] is None
    snapshot = interpreter.seen_snapshots[1]
    assert snapshot is not None
    assert snapshot.pending_strategy_summary is not None
    assert snapshot.pending_strategy_summary.asset_universe == ["BTC"]
    assert second["stage_outcome"] == "end_run"
