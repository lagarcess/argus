from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from argus.agent_runtime.stages.interpret import StructuredInterpretation, interpret_stage
from argus.agent_runtime.state.models import (
    ArtifactReference,
    RunState,
    StrategySummary,
    TaskSnapshot,
    UserState,
)


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


def test_non_dca_capital_answer_updates_initial_capital_assumption(monkeypatch) -> None:
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
        user_goal_summary="User supplied the requested starting capital.",
        candidate_strategy_draft=StrategySummary(capital_amount=10000),
        semantic_turn_act="answer_pending_need",
    )

    result, _ = _interpret(
        message="ten thousand",
        response=response,
        snapshot=TaskSnapshot(pending_strategy_summary=pending),
        selected_thread_metadata={
            "last_stage_outcome": "await_user_reply",
            "requested_field": "initial_capital",
        },
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["AAPL"]
    assert strategy.date_range == "past year"
    assert strategy.capital_amount is None
    assert result.patch["optional_parameter_status"]["initial_capital"] == 10000


def test_buy_and_hold_without_capital_is_ready_for_confirmation(monkeypatch) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User wants to buy and hold Apple over the past year.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold Apple.",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range="past year",
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = _interpret(
        message="let's try a buy and hold on apple over the last year",
        response=response,
        snapshot=None,
    )

    assert result.outcome == "ready_for_confirmation"
    assert result.decision.missing_required_fields == []
    assert result.decision.candidate_strategy_draft.capital_amount is None


def test_buy_and_hold_ignores_spurious_missing_capital(monkeypatch) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User wants to buy and hold Apple over the past year.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold Apple.",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range="past year",
        ),
        missing_required_fields=["capital_amount"],
        semantic_turn_act="new_idea",
    )

    result, _ = _interpret(
        message="let's try a buy and hold on apple over the last year",
        response=response,
        snapshot=None,
    )

    assert result.outcome == "ready_for_confirmation"
    assert result.decision.missing_required_fields == []
    assert result.decision.candidate_strategy_draft.capital_amount is None


def test_dca_without_recurring_amount_still_requires_amount(monkeypatch) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User wants recurring Apple buys.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="dca_accumulation",
            strategy_thesis="Buy Apple every month.",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range="past year",
            cadence="monthly",
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = _interpret(
        message="buy Apple every month over the past year",
        response=response,
        snapshot=None,
    )

    assert result.outcome == "needs_clarification"
    assert result.decision.missing_required_fields == ["capital_amount"]


def test_refine_current_idea_preserves_prior_date_and_capital(monkeypatch) -> None:
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
    pending.resolution_provenance = [
        {
            "field": "asset_universe[0]",
            "raw_text": "AAPL",
            "source": "llm_extraction",
            "candidate_kind": "asset",
            "resolution_status": "resolved",
            "canonical_symbol": "AAPL",
            "asset_class": "equity",
            "validated_by": "provider_catalog",
            "confidence": "high",
        }
    ]
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="refine",
        requires_clarification=False,
        user_goal_summary="User changed the asset to Nvidia.",
        candidate_strategy_draft=StrategySummary(asset_universe=["NVDA"]),
        semantic_turn_act="refine_current_idea",
    )

    result, _ = _interpret(
        message="actually make it NVDA",
        response=response,
        snapshot=TaskSnapshot(pending_strategy_summary=pending),
        selected_thread_metadata={"last_stage_outcome": "await_approval"},
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["NVDA"]
    assert strategy.asset_class == "equity"
    assert strategy.date_range == "past year"
    assert strategy.capital_amount == 10000
    assert all(
        not isinstance(item, dict) for item in strategy.resolution_provenance
    )


def test_change_asset_answer_patches_requested_field_only(monkeypatch) -> None:
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
        user_goal_summary="User supplied the replacement asset.",
        candidate_strategy_draft=StrategySummary(asset_universe=["NVDA"]),
        semantic_turn_act="answer_pending_need",
    )

    result, _ = _interpret(
        message="NVDA",
        response=response,
        snapshot=TaskSnapshot(pending_strategy_summary=pending),
        selected_thread_metadata={
            "last_stage_outcome": "await_user_reply",
            "requested_field": "asset_universe",
        },
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.strategy_type == "buy_and_hold"
    assert strategy.asset_universe == ["NVDA"]
    assert strategy.date_range == "past year"
    assert strategy.capital_amount is None


def test_affirmative_asset_clarification_uses_pending_resolution_candidate(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Apple.",
        asset_universe=["Apple"],
        asset_class="equity",
        date_range="past year",
    )
    pending.resolution_provenance = [
        {
            "field": "asset_universe[0]",
            "raw_text": "Apple",
            "source": "llm_extraction",
            "candidate_kind": "asset",
            "resolution_status": "ambiguous",
            "canonical_symbol": "AAPL",
            "asset_class": "equity",
            "validated_by": "provider_catalog",
            "confidence": "medium",
        }
    ]
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=True,
        user_goal_summary="User affirmed the pending asset clarification.",
        candidate_strategy_draft=StrategySummary(),
        semantic_turn_act="answer_pending_need",
    )

    result, _ = _interpret(
        message="yes",
        response=response,
        snapshot=TaskSnapshot(pending_strategy_summary=pending),
        selected_thread_metadata={
            "last_stage_outcome": "await_user_reply",
            "requested_field": "asset_universe",
            "pending_resolution": {
                "field": "asset_universe",
                "raw_value": "Apple",
                "candidate_normalized_value": "AAPL",
                "asset_class": "equity",
            },
        },
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["AAPL"]
    assert strategy.asset_class == "equity"
    assert strategy.date_range == "past year"
    assert result.decision.missing_required_fields == []
    assert result.decision.requires_clarification is False


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


def test_run_backtest_action_approves_pending_confirmation_without_llm(monkeypatch) -> None:
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

    result, interpreter = _interpret(
        message="run backtest",
        response=None,
        snapshot=TaskSnapshot(pending_strategy_summary=pending),
        selected_thread_metadata={"last_stage_outcome": "await_approval"},
        action_context={
            "type": "run_backtest",
            "label": "Run backtest",
            "presentation": "confirmation",
            "payload": {},
        },
    )

    assert interpreter.requests == []
    assert result.outcome == "approved_for_execution"
    assert result.patch["confirmation_payload"]["strategy"]["asset_universe"] == ["AAPL"]


def test_run_backtest_action_from_missing_field_state_returns_confirmation() -> None:
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Apple.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range="past year",
    )

    result, interpreter = _interpret(
        message="run backtest",
        response=None,
        snapshot=TaskSnapshot(pending_strategy_summary=pending),
        selected_thread_metadata={"last_stage_outcome": "await_user_reply"},
        action_context={
            "type": "run_backtest",
            "label": "Run backtest",
            "presentation": "confirmation",
            "payload": {},
        },
    )

    assert interpreter.requests == []
    assert result.outcome == "ready_for_confirmation"
    assert "confirmation_payload" not in result.patch
    assert result.patch["candidate_strategy_draft"]["asset_universe"] == ["AAPL"]


def test_change_asset_action_prompts_for_replacement_without_llm() -> None:
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Apple.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range="past year",
        capital_amount=10000,
    )

    result, interpreter = _interpret(
        message="change asset",
        response=None,
        snapshot=TaskSnapshot(pending_strategy_summary=pending),
        selected_thread_metadata={"last_stage_outcome": "await_approval"},
        action_context={
            "type": "change_asset",
            "label": "Change asset",
            "presentation": "confirmation",
            "payload": {},
        },
    )

    assert interpreter.requests == []
    assert result.outcome == "await_user_reply"
    assert result.patch["requested_field"] == "asset_universe"
    assert result.patch["missing_required_fields"] == ["asset_universe"]
    assert "asset" in result.patch["assistant_prompt"].lower()
    assert result.patch["candidate_strategy_draft"]["asset_universe"] == ["AAPL"]


def test_model_unavailable_recovery_mentions_active_pending_draft() -> None:
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Apple.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range="past year",
        capital_amount=10000,
    )

    result, interpreter = _interpret(
        message="actually make it NVDA",
        response=None,
        snapshot=TaskSnapshot(pending_strategy_summary=pending),
        selected_thread_metadata={"last_stage_outcome": "await_approval"},
    )

    assert len(interpreter.requests) == 1
    assert result.outcome == "ready_to_respond"
    assert "AAPL" in result.patch["assistant_response"]
    assert "draft" in result.patch["assistant_response"].lower()
    assert "try again" in result.patch["assistant_response"].lower()
    assert "interpretation model" not in result.patch["assistant_response"].lower()


def test_refine_strategy_result_action_prompts_for_change_without_llm() -> None:
    confirmed = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Microsoft.",
        asset_universe=["MSFT"],
        asset_class="equity",
        date_range="past year",
    )
    reference = ArtifactReference(
        artifact_kind="backtest_result",
        artifact_id="run-1",
        metadata={
            "asset_class": "equity",
            "config_snapshot": {
                "template": "buy_and_hold",
                "symbols": ["AAPL"],
                "date_range": "past year",
                "resolved_strategy": {
                    "strategy_type": "buy_and_hold",
                    "strategy_thesis": "Buy and hold Apple.",
                    "asset_universe": ["AAPL"],
                    "asset_class": "equity",
                    "date_range": "past year",
                },
            },
        },
    )

    result, interpreter = _interpret(
        message="refine this strategy",
        response=None,
        snapshot=TaskSnapshot(
            latest_task_type="results_explanation",
            completed=True,
            confirmed_strategy_summary=confirmed,
            latest_backtest_result_reference=reference,
        ),
        action_context={
            "type": "refine_strategy",
            "label": "Refine strategy",
            "presentation": "result",
            "payload": {"run_id": "run-1"},
        },
    )

    assert interpreter.requests == []
    assert result.outcome == "await_user_reply"
    assert result.patch["requested_field"] == "refinement"
    assert "change" in result.patch["assistant_prompt"].lower()
    assert result.patch["candidate_strategy_draft"]["asset_universe"] == ["MSFT"]
    assert result.patch["response_intent"]["facts"]["latest_run_id"] == "run-1"
