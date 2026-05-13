from __future__ import annotations

from argus.agent_runtime.stages.interpret import (
    InterpretationRequest,
    StructuredInterpretation,
    interpret_stage,
)
from argus.agent_runtime.state.models import (
    RunState,
    StrategySummary,
    TaskSnapshot,
    UserState,
)


class ResolvedAssetStub:
    def __init__(self, canonical_symbol: str, asset_class: str) -> None:
        self.canonical_symbol = canonical_symbol
        self.asset_class = asset_class


def _patch_resolve_asset(monkeypatch) -> None:
    from argus.agent_runtime.extraction import structured as extraction_module
    from argus.agent_runtime.stages import interpret as interpret_module

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        return ResolvedAssetStub(symbol.upper(), "equity")

    monkeypatch.setattr(interpret_module, "resolve_asset", resolve_stub)
    monkeypatch.setattr(extraction_module, "resolve_asset", resolve_stub)


def _interpret_with(response: StructuredInterpretation):
    def interpreter(_request: InterpretationRequest) -> StructuredInterpretation:
        return response

    return interpreter


def test_partial_strategy_from_mock_interpreter_waits_for_missing_fields(
    monkeypatch,
) -> None:
    _patch_resolve_asset(monkeypatch)

    result = interpret_stage(
        state=RunState.new(
            current_user_message="test RSI on Apple",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1"),
        latest_task_snapshot=None,
        structured_interpreter=_interpret_with(
            StructuredInterpretation(
                intent="strategy_drafting",
                task_relation="new_task",
                requires_clarification=True,
                user_goal_summary="User wants an RSI idea but no period yet.",
                candidate_strategy_draft=StrategySummary(
                    strategy_type="indicator_threshold",
                    strategy_thesis="Buy Apple when RSI is oversold.",
                    asset_universe=["AAPL"],
                    asset_class="equity",
                    entry_logic="RSI drops below 30",
                    exit_logic="RSI rises above 55",
                ),
                missing_required_fields=["date_range"],
                semantic_turn_act="new_idea",
            )
        ),
    )

    assert result.outcome == "needs_clarification"
    assert result.decision is not None
    assert result.decision.candidate_strategy_draft.asset_universe == ["AAPL"]
    assert result.decision.missing_required_fields == ["date_range"]


def test_ready_strategy_from_mock_interpreter_reaches_confirmation(monkeypatch) -> None:
    _patch_resolve_asset(monkeypatch)

    result = interpret_stage(
        state=RunState.new(
            current_user_message="test RSI on Apple last year",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1"),
        latest_task_snapshot=None,
        structured_interpreter=_interpret_with(
            StructuredInterpretation(
                intent="backtest_execution",
                task_relation="new_task",
                requires_clarification=False,
                user_goal_summary="User supplied an executable RSI idea.",
                candidate_strategy_draft=StrategySummary(
                    strategy_type="indicator_threshold",
                    strategy_thesis="Buy Apple when RSI is oversold.",
                    asset_universe=["AAPL"],
                    asset_class="equity",
                    date_range="last year",
                    entry_logic="RSI drops below 30",
                    exit_logic="RSI rises above 55",
                ),
                semantic_turn_act="new_idea",
            )
        ),
    )

    assert result.outcome == "ready_for_confirmation"
    assert result.decision is not None
    assert result.decision.semantic_turn_act == "new_idea"


def test_approval_uses_llm_semantic_turn_act_not_state_machine_confirmation(
    monkeypatch,
) -> None:
    _patch_resolve_asset(monkeypatch)

    pending = StrategySummary(
        strategy_type="indicator_threshold",
        strategy_thesis="Buy Apple when RSI is oversold.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range="last year",
        entry_logic="RSI drops below 30",
        exit_logic="RSI rises above 55",
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message="yes run it",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1"),
        latest_task_snapshot=TaskSnapshot(
            latest_task_type="backtest_execution",
            completed=False,
            pending_strategy_summary=pending,
        ),
        structured_interpreter=_interpret_with(
            StructuredInterpretation(
                intent="backtest_execution",
                task_relation="continue",
                requires_clarification=False,
                user_goal_summary="User approved the pending strategy.",
                semantic_turn_act="approval",
            )
        ),
    )

    assert result.outcome == "approved_for_execution"
    assert result.patch["confirmation_payload"]["strategy"] == pending.model_dump(
        mode="python"
    )
