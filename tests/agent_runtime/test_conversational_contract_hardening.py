from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from argus.agent_runtime.stages.interpret import StructuredInterpretation, interpret_stage
from argus.agent_runtime.state.models import RunState, StrategySummary, TaskSnapshot, UserState


@dataclass(frozen=True)
class ResolvedAssetStub:
    canonical_symbol: str
    asset_class: str
    name: str = ""
    raw_symbol: str = ""


class RecordingInterpreter:
    def __init__(self, response: StructuredInterpretation | None) -> None:
        self.response = response
        self.requests: list[Any] = []

    def __call__(self, request: Any) -> StructuredInterpretation | None:
        self.requests.append(request)
        return self.response


def _interpret(
    *,
    message: str,
    response: StructuredInterpretation | None,
    snapshot: TaskSnapshot | None,
    selected_thread_metadata: dict[str, Any] | None = None,
    action_context: dict[str, Any] | None = None,
):
    interpreter = RecordingInterpreter(response)
    state = RunState.new(
        current_user_message=message,
        recent_thread_history=[],
        action_context=action_context,
    )
    result = interpret_stage(
        state=state,
        user=UserState(user_id="user-1"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata=selected_thread_metadata or {},
        structured_interpreter=interpreter,
    )
    return result, interpreter


def test_answer_pending_need_preserves_prior_strategy_fields(monkeypatch) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Apple.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range="past year",
        capital_amount=None,
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User supplied the missing capital amount.",
        candidate_strategy_draft=StrategySummary(
            capital_amount=10000,
            sizing_mode="notional",
        ),
        semantic_turn_act="answer_pending_need",
    )

    result, _ = _interpret(
        message="ten thousand",
        response=response,
        snapshot=TaskSnapshot(pending_strategy_summary=pending),
        selected_thread_metadata={"last_stage_outcome": "await_user_reply"},
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.strategy_type == "buy_and_hold"
    assert strategy.asset_universe == ["AAPL"]
    assert strategy.asset_class == "equity"
    assert strategy.date_range == "past year"
    assert strategy.capital_amount == 10000


def test_natural_language_approval_does_not_execute_from_missing_field_state(monkeypatch) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Apple.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range="past year",
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="The user supplied capital, not approval.",
        candidate_strategy_draft=StrategySummary(capital_amount=10000),
        semantic_turn_act="approval",
    )

    result, _ = _interpret(
        message="ten thousand",
        response=response,
        snapshot=TaskSnapshot(pending_strategy_summary=pending),
        selected_thread_metadata={"last_stage_outcome": "await_user_reply"},
    )

    assert result.outcome == "ready_for_confirmation"
    assert "confirmation_payload" not in result.patch


def test_natural_language_approval_executes_only_after_confirmation_card(monkeypatch) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Apple.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range="past year",
        capital_amount=10000,
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User approved the visible confirmation.",
        candidate_strategy_draft=pending,
        semantic_turn_act="approval",
    )

    result, _ = _interpret(
        message="yes, run it",
        response=response,
        snapshot=TaskSnapshot(pending_strategy_summary=pending),
        selected_thread_metadata={"last_stage_outcome": "await_approval"},
    )

    assert result.outcome == "approved_for_execution"
    assert result.patch["confirmation_payload"]["strategy"]["asset_universe"] == ["AAPL"]
