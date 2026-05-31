from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from argus.agent_runtime.confirmation_artifacts import confirmation_artifact_reference
from argus.agent_runtime.stages.interpret import StructuredInterpretation, interpret_stage
from argus.agent_runtime.state.models import (
    ArtifactReference,
    ConfirmationPayload,
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
    confirmation_payload: ConfirmationPayload | dict[str, Any] | None = None,
):
    interpreter = RecordingInterpreter(response)
    state = RunState.new(
        current_user_message=message,
        recent_thread_history=[],
        action_context=action_context,
    )
    if confirmation_payload is not None:
        state.confirmation_payload = ConfirmationPayload.model_validate(
            confirmation_payload
        )
    result = interpret_stage(
        state=state,
        user=UserState(user_id="user-1"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata=selected_thread_metadata or {},
        structured_interpreter=interpreter,
    )
    return result, interpreter


def _validated_confirmation_payload(
    strategy: StrategySummary,
    *,
    optional_parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    symbol = strategy.asset_universe[0] if strategy.asset_universe else "AAPL"
    benchmark_symbol = "BTC" if strategy.asset_class == "crypto" else "SPY"
    return {
        "strategy": strategy.model_dump(mode="python"),
        "optional_parameters": optional_parameters or {},
        "launch_payload": {
            "strategy_type": strategy.strategy_type or "buy_and_hold",
            "symbol": symbol,
            "symbols": list(strategy.asset_universe or [symbol]),
            "timeframe": strategy.timeframe or "1D",
            "date_range": (
                strategy.date_range
                if isinstance(strategy.date_range, dict)
                else {"start": "2025-05-14", "end": "2026-05-14"}
            ),
            "sizing_mode": strategy.sizing_mode or "capital_amount",
            "capital_amount": strategy.capital_amount or 1000,
            "benchmark_symbol": strategy.comparison_baseline or benchmark_symbol,
        },
        "validation": {"executable": True},
    }


def _task_snapshot_with_confirmation(strategy: StrategySummary) -> TaskSnapshot:
    payload = _validated_confirmation_payload(strategy)
    reference = confirmation_artifact_reference(
        confirmation_id="confirmation-test",
        confirmation_payload=payload,
    )
    return TaskSnapshot(
        pending_strategy_summary=strategy,
        active_confirmation_reference=reference,
        artifact_references=[reference],
    )


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
        snapshot=_task_snapshot_with_confirmation(pending),
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
        snapshot=_task_snapshot_with_confirmation(pending),
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


def test_adjust_assumptions_capital_answer_patches_visible_draft(monkeypatch) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Nvidia.",
        asset_universe=["NVDA"],
        asset_class="equity",
        date_range={"start": "2024-07-03", "end": "2024-08-13"},
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User supplied an assumption change for starting capital.",
        candidate_strategy_draft=StrategySummary(capital_amount=5000),
        semantic_turn_act="answer_pending_need",
    )

    result, _ = _interpret(
        message="Use $5,000 starting capital",
        response=response,
        snapshot=_task_snapshot_with_confirmation(pending),
        selected_thread_metadata={
            "last_stage_outcome": "await_user_reply",
            "requested_field": "assumption",
        },
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["NVDA"]
    assert strategy.date_range == {"start": "2024-07-03", "end": "2024-08-13"}
    assert strategy.capital_amount is None
    assert result.patch["optional_parameter_status"]["initial_capital"] == 5000


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


def test_dca_without_cadence_does_not_silently_default_to_monthly(monkeypatch) -> None:
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
        user_goal_summary="User wants recurring Apple buys but did not choose cadence.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="dca_accumulation",
            strategy_thesis="Buy Apple recurring.",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range="past year",
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = _interpret(
        message="buy Apple over the past year with recurring buys",
        response=response,
        snapshot=None,
    )

    assert result.outcome == "needs_clarification"
    assert result.decision.candidate_strategy_draft.cadence is None
    assert result.decision.missing_required_fields == ["capital_amount", "cadence"]


def test_explicit_last_month_overrides_model_default_period(monkeypatch) -> None:
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
        user_goal_summary="User wants to buy and hold BABA for the last month.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold BABA.",
            asset_universe=["BABA"],
            asset_class="equity",
            date_range="last month",
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = _interpret(
        message="try buy and hold BABA for the last month",
        response=response,
        snapshot=None,
    )

    assert result.outcome == "ready_for_confirmation"
    assert result.decision.candidate_strategy_draft.date_range == "last month"


def test_explicit_unresolved_date_phrase_blocks_confirmation(monkeypatch) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="User wants to buy and hold BABA for an unclear period.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold BABA.",
            asset_universe=["BABA"],
            asset_class="equity",
            date_range=None,
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = _interpret(
        message="try buy and hold BABA for the last fortnight",
        response=response,
        snapshot=None,
    )

    assert result.outcome == "needs_clarification"
    assert result.decision.missing_required_fields == ["date_range"]
    assert result.decision.candidate_strategy_draft.date_range is None


def test_dca_recurring_amount_from_user_text_is_preserved(monkeypatch) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "crypto"),
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="User wants weekly BTC recurring buys.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="dca_accumulation",
            strategy_thesis="Buy Bitcoin weekly.",
            asset_universe=["BTC"],
            asset_class="crypto",
            date_range="last 6 months",
            cadence="weekly",
            capital_amount=20000,
            extra_parameters={
                "field_provenance": {
                    "capital_amount": "recurring_contribution",
                }
            },
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = _interpret(
        message="try dca on bitcoin over the last 6 months investing 20000 every week",
        response=response,
        snapshot=None,
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.capital_amount == 20000
    assert strategy.cadence == "weekly"


def test_dca_recurring_amount_grounded_by_current_message_without_provenance(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="User wants weekly NVDA recurring buys.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="dca_accumulation",
            strategy_thesis="Buy NVIDIA weekly in 2024.",
            asset_universe=["NVDA"],
            asset_class="equity",
            date_range="2024",
            cadence="weekly",
            capital_amount=250,
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = _interpret(
        message="What if I bought $250 of NVDA every week in 2024?",
        response=response,
        snapshot=None,
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["NVDA"]
    assert strategy.cadence == "weekly"
    assert strategy.capital_amount == 250
    assert result.decision.missing_required_fields == []


def test_dca_recurring_amount_grounding_handles_different_cadence_and_asset(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="User wants monthly MSFT recurring buys.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="dca_accumulation",
            strategy_thesis="Buy Microsoft monthly in 2025.",
            asset_universe=["MSFT"],
            asset_class="equity",
            date_range="2025",
            cadence="monthly",
            capital_amount=75,
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = _interpret(
        message="buy 75 dollars of MSFT each month in 2025",
        response=response,
        snapshot=None,
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["MSFT"]
    assert strategy.cadence == "monthly"
    assert strategy.capital_amount == 75
    assert result.decision.missing_required_fields == []


def test_dca_tsla_monthly_recurring_contribution_does_not_ask_total_budget(
    monkeypatch,
) -> None:
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
        user_goal_summary="User wants monthly TSLA recurring buys.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="dca_accumulation",
            strategy_thesis="Buy Tesla monthly.",
            asset_universe=["TSLA"],
            asset_class="equity",
            date_range="last year",
            cadence="monthly",
            capital_amount=500,
            extra_parameters={
                "field_provenance": {
                    "capital_amount": "recurring_contribution",
                    "cadence": "explicit_user",
                }
            },
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = _interpret(
        message="test buying $500 of TSLA every month last year",
        response=response,
        snapshot=None,
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["TSLA"]
    assert strategy.cadence == "monthly"
    assert strategy.capital_amount == 500
    assert result.decision.missing_required_fields == []
    assert result.decision.unsupported_constraints == []


def test_dca_contribution_cap_does_not_overwrite_recurring_contribution(
    monkeypatch,
) -> None:
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
        user_goal_summary="User wants quarterly MSFT recurring buys with a cap.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="dca_accumulation",
            strategy_thesis="Buy Microsoft quarterly.",
            asset_universe=["MSFT"],
            asset_class="equity",
            date_range={"start": "2021-01-01", "end": "2023-12-31"},
            cadence="quarterly",
            capital_amount=750,
            extra_parameters={
                "contribution_cap": 9000,
                "field_provenance": {
                    "capital_amount": "recurring_contribution",
                    "cadence": "explicit_user",
                    "contribution_cap": "cap",
                },
            },
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = _interpret(
        message=(
            "try buying $750 of MSFT quarterly from 2021 through 2023 with a "
            "$9,000 cap"
        ),
        response=response,
        snapshot=None,
    )

    assert result.outcome == "needs_clarification"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["MSFT"]
    assert strategy.cadence == "quarterly"
    assert strategy.capital_amount == 750
    assert result.decision.missing_required_fields == []
    assert result.patch["optional_parameter_status"]["initial_capital"] == 9000
    constraints = result.patch["optional_parameter_status"]["unsupported_constraints"]
    assert constraints[0]["category"] == "unsupported_dca_starting_principal"
    assert constraints[0]["raw_value"] == "$9,000 contribution cap"
    assert "contribution cap" in constraints[0]["explanation"]
    assert "starting principal" not in constraints[0]["explanation"]


def test_dca_same_turn_starting_principal_does_not_overwrite_recurring(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "crypto"),
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User wants weekly BTC recurring buys with principal.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="dca_accumulation",
            strategy_thesis="Buy Bitcoin weekly.",
            asset_universe=["BTC"],
            asset_class="crypto",
            date_range="last 6 months",
            cadence="weekly",
            capital_amount=20000,
            extra_parameters={
                "initial_capital": 100000,
                "field_provenance": {
                    "capital_amount": "recurring_contribution",
                },
            },
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = _interpret(
        message=(
            "try dca on BTC over the last 6 months investing 20000 every week "
            "with 100k starting principal"
        ),
        response=response,
        snapshot=None,
    )

    assert result.outcome == "needs_clarification"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.capital_amount == 20000
    assert strategy.cadence == "weekly"
    assert result.patch["optional_parameter_status"]["initial_capital"] == 100000
    constraints = result.patch["optional_parameter_status"]["unsupported_constraints"]
    assert constraints[0]["category"] == "unsupported_dca_starting_principal"


def test_dca_period_count_is_not_misclassified_as_recurring_money(monkeypatch) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "crypto"),
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User wants weekly Bitcoin buys but gave no contribution.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="dca_accumulation",
            strategy_thesis="Buy Bitcoin weekly.",
            asset_universe=["BTC"],
            asset_class="crypto",
            date_range="last 6 months",
            cadence="weekly",
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = _interpret(
        message="buy Bitcoin every week over the last 6 months",
        response=response,
        snapshot=None,
    )

    assert result.outcome == "needs_clarification"
    assert result.decision.candidate_strategy_draft.capital_amount is None
    assert result.decision.missing_required_fields == ["capital_amount"]


def test_runnable_buy_and_hold_draft_is_not_blocked_by_redundant_clarification(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="User wants to test BABA buy and hold.",
        assistant_response=(
            "Would you like to backtest buying and holding BABA shares at the "
            "start of last month and selling at the end?"
        ),
        candidate_strategy_draft=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold BABA.",
            asset_universe=["BABA"],
            asset_class="equity",
            date_range="last month",
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = _interpret(
        message="try buy and hold BABA for the last month",
        response=response,
        snapshot=None,
    )

    assert result.outcome == "ready_for_confirmation"
    assert result.decision.candidate_strategy_draft.date_range in {
        "last month",
        "past month",
    }


def test_dca_total_capital_and_recurring_contribution_keep_separate_roles(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "crypto"),
    )
    pending = StrategySummary(
        strategy_type="dca_accumulation",
        strategy_thesis="Buy Bitcoin weekly.",
        asset_universe=["BTC"],
        asset_class="crypto",
        date_range="last 6 months",
        cadence="weekly",
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User clarified total capital and recurring amount.",
        candidate_strategy_draft=StrategySummary(
            capital_amount=20000,
            extra_parameters={
                "initial_capital": 100000,
                "field_provenance": {
                    "capital_amount": "recurring_contribution",
                },
            },
        ),
        semantic_turn_act="answer_pending_need",
    )

    result, _ = _interpret(
        message="my total capital is 100k and the recurrent buys will be 20k weekly",
        response=response,
        snapshot=TaskSnapshot(pending_strategy_summary=pending),
        selected_thread_metadata={
            "last_stage_outcome": "await_user_reply",
            "requested_field": "capital_amount",
        },
    )

    assert result.outcome == "needs_clarification"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.capital_amount == 20000
    assert result.patch["optional_parameter_status"]["initial_capital"] == 100000
    assert result.decision.missing_required_fields == []
    constraints = result.patch["optional_parameter_status"]["unsupported_constraints"]
    assert constraints[0]["category"] == "unsupported_dca_starting_principal"
    assert "starting principal" in constraints[0]["explanation"]
    assert "recurring contribution" in constraints[0]["explanation"]
    labels = [option["label"] for option in constraints[0]["simplification_options"]]
    assert labels == [
        "Run recurring buys only",
        "Adjust recurring contribution",
        "Use buy and hold with starting capital",
    ]


def test_dca_starting_principal_recovery_copy_is_specific() -> None:
    from argus.agent_runtime.stages.compose import compose_response_intent
    from argus.agent_runtime.state.models import ResponseIntent, RunState

    state = RunState.new(
        current_user_message="my total capital is 100k",
        recent_thread_history=[],
    )
    state.response_intent = ResponseIntent(
        kind="unsupported_recovery",
        semantic_needs=["simplification_choice"],
        facts={
            "unsupported_constraints": [
                {
                    "category": "unsupported_dca_starting_principal",
                    "raw_value": "$100,000 starting principal",
                    "explanation": (
                        "I understand the $100,000 as starting principal, but "
                        "the current DCA backtest can only execute the recurring "
                        "contribution."
                    ),
                    "simplification_options": [
                        {"label": "Run recurring buys only"},
                        {"label": "Adjust recurring contribution"},
                        {"label": "Use buy and hold with starting capital"},
                    ],
                }
            ]
        },
        options=[
            {"label": "Run recurring buys only"},
            {"label": "Adjust recurring contribution"},
            {"label": "Use buy and hold with starting capital"},
        ],
    )

    copy = compose_response_intent(state)

    assert copy is not None
    assert "current DCA backtest can only execute the recurring contribution" in copy
    assert "run the recurring-buy simulation only" in copy
    assert "adjust the recurring contribution" in copy
    assert "switch to buy and hold with the starting capital" in copy


def test_unsupported_strategy_recovery_copy_uses_sentence_case_options() -> None:
    from argus.agent_runtime.stages.compose import compose_response_intent
    from argus.agent_runtime.state.models import ResponseIntent, RunState

    state = RunState.new(
        current_user_message="Test Apple when news sentiment turns positive.",
        recent_thread_history=[],
    )
    state.response_intent = ResponseIntent(
        kind="unsupported_recovery",
        semantic_needs=["simplification_choice"],
        facts={
            "unsupported_constraints": [
                {
                    "category": "unsupported_strategy_logic",
                    "explanation": (
                        "This idea depends on strategy logic that is not executable yet."
                    ),
                }
            ]
        },
        options=[
            {"label": "Use a supported RSI threshold rule"},
            {"label": "Compare with buy and hold"},
            {"label": "Use a supported moving-average crossover"},
        ],
    )

    copy = compose_response_intent(state)

    assert copy is not None
    assert "I can use a supported RSI threshold rule" in copy
    assert "Compare with" not in copy


def test_dca_confirmation_card_uses_recurring_contribution_not_total_capital() -> None:
    from argus.api.chat.confirmation import runtime_confirmation_card

    card = runtime_confirmation_card(
        {
            "stage_outcome": "await_approval",
            "confirmation_payload": {
                "strategy": {
                    "strategy_type": "dca_accumulation",
                    "strategy_thesis": "Buy Bitcoin weekly.",
                    "asset_universe": ["BTC"],
                    "asset_class": "crypto",
                    "date_range": "last 6 months",
                    "cadence": "weekly",
                    "capital_amount": 20000,
                },
                "optional_parameters": {
                    "initial_capital": {"value": 100000, "source": "user"}
                },
            },
        }
    )

    assert card is not None
    rows = {row["label"]: row["value"] for row in card["rows"]}
    assert rows["Contribution"] == "$20,000"
    assert "$20,000 recurring contribution" in card["assumptions"]
    assert "$100,000 recurring contribution" not in card["assumptions"]


def test_dca_total_capital_alone_does_not_satisfy_recurring_contribution(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "crypto"),
    )
    pending = StrategySummary(
        strategy_type="dca_accumulation",
        strategy_thesis="Buy Bitcoin weekly.",
        asset_universe=["BTC"],
        asset_class="crypto",
        date_range="last 6 months",
        cadence="weekly",
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User supplied total capital only.",
        candidate_strategy_draft=StrategySummary(
            extra_parameters={
                "initial_capital": 100000,
                "field_provenance": {"capital_amount": "total_capital"},
            },
        ),
        semantic_turn_act="answer_pending_need",
    )

    result, _ = _interpret(
        message="my total capital is 100k",
        response=response,
        snapshot=TaskSnapshot(pending_strategy_summary=pending),
        selected_thread_metadata={
            "last_stage_outcome": "await_user_reply",
            "requested_field": "capital_amount",
        },
    )

    assert result.outcome == "needs_clarification"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.capital_amount is None
    assert result.decision.missing_required_fields == ["capital_amount"]
    assert result.patch["optional_parameter_status"]["initial_capital"] == 100000


def test_dca_budget_language_does_not_become_recurring_contribution(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "crypto"),
    )
    pending = StrategySummary(
        strategy_type="dca_accumulation",
        strategy_thesis="Buy Bitcoin monthly.",
        asset_universe=["BTC"],
        asset_class="crypto",
        date_range="last 6 months",
        cadence="monthly",
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User supplied a total budget only.",
        candidate_strategy_draft=StrategySummary(
            extra_parameters={
                "initial_capital": 100000,
                "field_provenance": {"capital_amount": "total_capital"},
            },
        ),
        semantic_turn_act="answer_pending_need",
    )

    result, _ = _interpret(
        message="I have 100k to invest in BTC monthly",
        response=response,
        snapshot=TaskSnapshot(pending_strategy_summary=pending),
        selected_thread_metadata={
            "last_stage_outcome": "await_user_reply",
            "requested_field": "capital_amount",
        },
    )

    assert result.outcome == "needs_clarification"
    assert result.decision.candidate_strategy_draft.capital_amount is None
    assert result.decision.missing_required_fields == ["capital_amount"]
    assert result.patch["optional_parameter_status"]["initial_capital"] == 100000


def test_dca_max_budget_language_preserves_separate_recurring_contribution(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "crypto"),
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User supplied a max budget and weekly recurring amount.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="dca_accumulation",
            strategy_thesis="Buy Bitcoin weekly.",
            asset_universe=["BTC"],
            asset_class="crypto",
            date_range="last 6 months",
            cadence="weekly",
            capital_amount=20000,
            extra_parameters={
                "max_budget": 100000,
                "field_provenance": {
                    "capital_amount": "recurring_contribution",
                },
            },
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = _interpret(
        message="try dca bitcoin with a max 100k budget and buy 20k weekly",
        response=response,
        snapshot=None,
    )

    assert result.outcome == "needs_clarification"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.capital_amount == 20000
    assert result.patch["optional_parameter_status"]["initial_capital"] == 100000
    constraints = result.patch["optional_parameter_status"]["unsupported_constraints"]
    assert constraints[0]["category"] == "unsupported_dca_starting_principal"
    assert constraints[0]["raw_value"] == "$100,000 maximum budget"
    assert "maximum budget" in constraints[0]["explanation"]
    assert "starting principal" not in constraints[0]["explanation"]


def test_may_date_reference_blocks_default_past_year_confirmation(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="User wants to test AAPL in May 2025.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold AAPL.",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range=None,
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = _interpret(
        message="test AAPL May 2025",
        response=response,
        snapshot=None,
    )

    assert result.outcome == "needs_clarification"
    assert result.decision.candidate_strategy_draft.date_range is None
    assert result.decision.missing_required_fields == ["date_range"]


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
    assert all(not isinstance(item, dict) for item in strategy.resolution_provenance)


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


def test_requested_asset_answer_resolves_google_through_provider_path(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    provider_queries: list[str] = []
    provider_assets = {
        "google": ResolvedAssetStub("GOOGL", "equity", name="Alphabet Inc."),
        "googl": ResolvedAssetStub("GOOGL", "equity", name="Alphabet Inc."),
    }

    def _asset(symbol: str) -> ResolvedAssetStub:
        provider_queries.append(symbol)
        return provider_assets[symbol.strip().lower()]

    monkeypatch.setattr(interpret_module, "resolve_asset", _asset)
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
        user_goal_summary="User supplied the replacement asset.",
        candidate_strategy_draft=StrategySummary(),
        semantic_turn_act="answer_pending_need",
    )

    result, _ = _interpret(
        message="google",
        response=response,
        snapshot=TaskSnapshot(pending_strategy_summary=pending),
        selected_thread_metadata={
            "last_stage_outcome": "await_user_reply",
            "requested_field": "asset_universe",
        },
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert provider_queries[0] == "google"
    assert "AAPL" not in provider_queries
    assert strategy.asset_universe == ["GOOGL"]
    assert strategy.asset_class == "equity"
    assert strategy.date_range == "past year"
    assert strategy.capital_amount == 10000


def test_requested_asset_answer_ignores_unrelated_llm_draft_fields(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub("GOOGL", "equity")
        if symbol.strip().lower() == "google"
        else ResolvedAssetStub(symbol.strip().upper(), "equity"),
    )
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Apple.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        capital_amount=10000,
    )
    pending.resolution_provenance = [
        {
            "field": "date_range",
            "raw_text": "2024 dates",
            "source": "llm_extraction",
            "candidate_kind": "asset",
            "resolution_status": "resolved",
            "confidence": "high",
        },
        {
            "field": "asset_universe[0]",
            "raw_text": "Apple",
            "source": "llm_extraction",
            "candidate_kind": "asset",
            "resolution_status": "resolved",
            "canonical_symbol": "AAPL",
            "asset_class": "equity",
            "validated_by": "provider_catalog",
            "confidence": "high",
        },
    ]
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User supplied the replacement asset.",
        candidate_strategy_draft=StrategySummary(
            date_range={"start": "2023-01-01", "end": "2023-12-31"},
            capital_amount=25000,
        ),
        semantic_turn_act="answer_pending_need",
    )

    result, _ = _interpret(
        message="google",
        response=response,
        snapshot=TaskSnapshot(pending_strategy_summary=pending),
        selected_thread_metadata={
            "last_stage_outcome": "await_user_reply",
            "requested_field": "asset_universe",
        },
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["GOOGL"]
    assert strategy.asset_class == "equity"
    assert strategy.date_range == {"start": "2024-01-01", "end": "2024-12-31"}
    assert strategy.capital_amount == 10000
    assert any(
        item.field == "date_range" and item.raw_text == "2024 dates"
        for item in strategy.resolution_provenance
    )
    assert all(
        item.raw_text != "Apple" for item in strategy.resolution_provenance
    )


def test_requested_asset_answer_with_explicit_asset_ignores_unrelated_draft_fields(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    provider_queries: list[str] = []

    def _asset(symbol: str) -> ResolvedAssetStub:
        provider_queries.append(symbol)
        return ResolvedAssetStub("GOOGL", "equity")

    monkeypatch.setattr(interpret_module, "resolve_asset", _asset)
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Apple.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        capital_amount=10000,
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User supplied the replacement asset.",
        candidate_strategy_draft=StrategySummary(
            asset_universe=["google"],
            date_range={"start": "2023-01-01", "end": "2023-12-31"},
            capital_amount=25000,
        ),
        semantic_turn_act="answer_pending_need",
    )

    result, _ = _interpret(
        message="google",
        response=response,
        snapshot=TaskSnapshot(pending_strategy_summary=pending),
        selected_thread_metadata={
            "last_stage_outcome": "await_user_reply",
            "requested_field": "asset_universe",
        },
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert provider_queries[0] == "google"
    assert "AAPL" not in provider_queries
    assert strategy.asset_universe == ["GOOGL"]
    assert strategy.asset_class == "equity"
    assert strategy.date_range == {"start": "2024-01-01", "end": "2024-12-31"}
    assert strategy.capital_amount == 10000


def test_requested_asset_answer_resolves_ticker_through_provider_path(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    provider_queries: list[str] = []

    def _asset(symbol: str) -> ResolvedAssetStub:
        provider_queries.append(symbol)
        return ResolvedAssetStub(symbol.strip().upper(), "equity")

    monkeypatch.setattr(interpret_module, "resolve_asset", _asset)
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
        user_goal_summary="User supplied the replacement asset.",
        candidate_strategy_draft=StrategySummary(),
        semantic_turn_act="answer_pending_need",
    )

    result, _ = _interpret(
        message="msft",
        response=response,
        snapshot=TaskSnapshot(pending_strategy_summary=pending),
        selected_thread_metadata={
            "last_stage_outcome": "await_user_reply",
            "requested_field": "asset_universe",
        },
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert provider_queries[0] == "msft"
    assert "AAPL" not in provider_queries
    assert strategy.asset_universe == ["MSFT"]
    assert strategy.asset_class == "equity"
    assert strategy.date_range == "past year"
    assert strategy.capital_amount == 10000


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


def test_natural_language_approval_does_not_execute_from_missing_field_state(
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


def test_natural_language_approval_executes_only_after_confirmation_card(
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
        snapshot=_task_snapshot_with_confirmation(pending),
        selected_thread_metadata={"last_stage_outcome": "await_approval"},
        confirmation_payload=_validated_confirmation_payload(pending),
    )

    assert result.outcome == "ready_to_respond"
    response_text = result.patch["assistant_response"].lower()
    assert "visible card" in response_text
    assert "simulation" in response_text
    assert "confirmation_payload" not in result.patch


def test_confirmation_replay_without_material_change_defers_to_card_action(
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
        strategy_thesis="Buy and hold Tesla.",
        asset_universe=["TSLA"],
        asset_class="equity",
        date_range={"start": "2025-05-14", "end": "2026-05-14"},
        capital_amount=10000,
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User wants to run the visible confirmation.",
        candidate_strategy_draft=pending.model_copy(
            update={"raw_user_phrasing": "yes run it"}
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = _interpret(
        message="yes run it",
        response=response,
        snapshot=_task_snapshot_with_confirmation(pending),
        selected_thread_metadata={"last_stage_outcome": "await_approval"},
        confirmation_payload=_validated_confirmation_payload(pending),
    )

    assert result.outcome == "ready_to_respond"
    response_text = result.patch["assistant_response"].lower()
    assert "visible card" in response_text
    assert "simulation" in response_text
    assert "confirmation_payload" not in result.patch
    assert "text_action_deferred_to_confirmation_card" in result.decision.reason_codes


def test_run_backtest_action_approves_pending_confirmation_without_llm(
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
        confirmation_payload=_validated_confirmation_payload(pending),
    )

    assert interpreter.requests == []
    assert result.outcome == "approved_for_execution"
    assert result.patch["confirmation_payload"]["strategy"]["asset_universe"] == ["AAPL"]


def test_run_backtest_action_preserves_visible_confirmation_optional_parameters(
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
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range="past year",
    )
    optional_parameters = {
        "initial_capital": {"value": 2500, "source": "user"},
        "timeframe": {"value": "1D", "source": "default"},
    }

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
        confirmation_payload=_validated_confirmation_payload(
            pending,
            optional_parameters=optional_parameters,
        ),
    )

    assert interpreter.requests == []
    assert result.outcome == "approved_for_execution"
    assert (
        result.patch["confirmation_payload"]["optional_parameters"] == optional_parameters
    )


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
    assert "retry" in result.patch["assistant_response"].lower()
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
    assert result.patch["candidate_strategy_draft"]["asset_universe"] == ["AAPL"]
    assert result.patch["response_intent"]["facts"]["latest_run_id"] == "run-1"


def test_pending_refinement_blocks_latest_result_followup_capture(monkeypatch) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module
    from argus.agent_runtime.stages import interpret_actions as action_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )

    async def _bad_followup(**_: object) -> str:
        return "Try next: change the date range."

    monkeypatch.setattr(
        action_module,
        "_compose_result_followup_with_timeout",
        _bad_followup,
    )
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Apple.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range="past year",
    )
    result_reference = ArtifactReference(
        artifact_kind="backtest_result",
        artifact_id="run-1",
        metadata={
            "result_card": {"title": "AAPL buy and hold"},
            "config_snapshot": {
                "resolved_strategy": pending.model_dump(mode="python")
            },
        },
    )
    response = StructuredInterpretation(
        intent="results_explanation",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="Model incorrectly treated a refinement answer as next steps.",
        semantic_turn_act="result_followup",
        result_followup_focus="next_experiment",
        artifact_target="latest_result",
    )

    result, _ = _interpret(
        message="run it over the last 6 years starting in feb",
        response=response,
        snapshot=TaskSnapshot(
            pending_strategy_summary=pending,
            latest_backtest_result_reference=result_reference,
        ),
        selected_thread_metadata={
            "last_stage_outcome": "await_user_reply",
            "requested_field": "refinement",
            "source_result_run_id": "run-1",
        },
    )

    assert result.outcome == "needs_clarification"
    assert result.decision.artifact_target == "pending_refinement"
    assert result.decision.semantic_turn_act == "answer_pending_need"
    assert result.decision.missing_required_fields == ["refinement"]
    assert "pending_refinement_overrode_latest_result" in result.decision.reason_codes


def test_latest_result_followup_requires_validated_artifact_target(monkeypatch) -> None:
    from argus.agent_runtime.stages import interpret_actions as action_module

    async def _grounded_followup(**_: object) -> str:
        return "This answer used the latest result facts."

    monkeypatch.setattr(
        action_module,
        "_compose_result_followup_with_timeout",
        _grounded_followup,
    )

    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Bitcoin.",
        asset_universe=["BTC"],
        asset_class="crypto",
        date_range="2024 to today",
    )
    result_reference = ArtifactReference(
        artifact_kind="backtest_result",
        artifact_id="run-btc",
        metadata={
            "result_card": {"title": "BTC buy and hold"},
            "config_snapshot": {
                "resolved_strategy": pending.model_dump(mode="python")
            },
        },
    )
    response = StructuredInterpretation(
        intent="results_explanation",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asked why this result happened.",
        semantic_turn_act="result_followup",
        result_followup_focus="why_underperformed",
        artifact_target="latest_result",
    )

    result, _ = _interpret(
        message="why did this happen?",
        response=response,
        snapshot=TaskSnapshot(
            latest_task_type="results_explanation",
            completed=True,
            confirmed_strategy_summary=pending,
            latest_backtest_result_reference=result_reference,
        ),
    )

    assert result.decision.artifact_target == "latest_result"
    assert result.decision.semantic_turn_act == "result_followup"


def test_standalone_market_context_question_does_not_attach_to_latest_result() -> None:
    result_reference = ArtifactReference(
        artifact_kind="backtest_result",
        artifact_id="run-btc",
        metadata={
            "result_card": {"title": "BTC buy and hold"},
            "metrics": {"total_return_pct": 75.5},
        },
    )
    response = StructuredInterpretation(
        intent="unsupported_or_out_of_scope",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User asked for broad market movers.",
        assistant_response=(
            "I do not run a market-movers feed here. I can help turn one of those "
            "ideas into a historical test instead."
        ),
        semantic_turn_act="unsupported_request",
        artifact_target="none",
    )

    result, _ = _interpret(
        message="what are the top market movers?",
        response=response,
        snapshot=TaskSnapshot(latest_backtest_result_reference=result_reference),
    )

    assert result.outcome == "ready_to_respond"
    assert result.decision.artifact_target == "none"
    assert result.decision.semantic_turn_act == "unsupported_request"
    assert result.patch["assistant_response"] == response.assistant_response


def test_context_curiosity_does_not_silently_inherit_latest_result(monkeypatch) -> None:
    async def _context_answer(**_: object) -> str:
        return (
            "Corporate actions are useful when they are tied to a symbol and period. "
            "Pick an equity ticker and I can use those events as context around a test."
        )

    monkeypatch.setattr(
        "argus.agent_runtime.stages.interpret.invoke_openrouter_chat_completion",
        _context_answer,
    )
    result_reference = ArtifactReference(
        artifact_kind="backtest_result",
        artifact_id="run-btc",
        metadata={
            "result_card": {"title": "BTC buy and hold"},
            "metrics": {"total_return_pct": 75.5},
        },
    )
    response = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asked for corporate event context.",
        semantic_turn_act="educational_question",
        context_question_focus="corporate_events",
        artifact_target="none",
    )

    result, _ = _interpret(
        message="what can you tell me about corporate events?",
        response=response,
        snapshot=TaskSnapshot(latest_backtest_result_reference=result_reference),
    )

    assert result.outcome == "ready_to_respond"
    assert result.decision.artifact_target == "none"
    assert result.decision.context_question_focus == "corporate_events"
    assert "Execution limits" not in result.patch["assistant_response"]


def test_new_vague_strategy_does_not_inherit_hidden_snapshot_assets(monkeypatch) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    hidden_prior = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold WANT and GOLY.",
        asset_universe=["WANT", "GOLY"],
        asset_class="equity",
        date_range="past year",
    )
    response = StructuredInterpretation(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="User wants to create a new strategy.",
        assistant_response=(
            "I see you're looking at WANT and GOLY. Which rule should I test?"
        ),
        candidate_strategy_draft=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Create a new strategy.",
            asset_universe=["WANT", "GOLY"],
            asset_class="equity",
        ),
        semantic_turn_act="new_idea",
        artifact_target="none",
    )

    result, _ = _interpret(
        message="I want to create a new strategy.",
        response=response,
        snapshot=TaskSnapshot(pending_strategy_summary=hidden_prior),
    )

    assert result.outcome == "needs_clarification"
    assert result.decision.artifact_target == "none"
    assert result.decision.candidate_strategy_draft.asset_universe == []
    assert result.decision.missing_required_fields == ["asset_universe", "date_range"]
    assert result.patch.get("assistant_response") != response.assistant_response


def test_new_strategy_keeps_explicit_cashtag_symbol_context(monkeypatch) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    hidden_prior = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Prior TSLA idea.",
        asset_universe=["TSLA"],
        asset_class="equity",
        date_range="past year",
    )
    response = StructuredInterpretation(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="User wants a fresh TSLA strategy.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Fresh TSLA idea.",
            asset_universe=["TSLA"],
            asset_class="equity",
        ),
        missing_required_fields=["date_range"],
        confidence=0.81,
        semantic_turn_act="new_idea",
        artifact_target="none",
    )

    result, _ = _interpret(
        message="I want to create a $tsla strategy",
        response=response,
        snapshot=TaskSnapshot(pending_strategy_summary=hidden_prior),
    )

    assert result.outcome == "needs_clarification"
    assert result.decision.candidate_strategy_draft.asset_universe == ["TSLA"]
    assert "hidden_artifact_asset_context_cleared" not in result.decision.reason_codes


def test_dca_total_budget_clarification_names_recurring_execution_detail() -> None:
    from argus.agent_runtime.stages.compose import compose_response_intent
    from argus.agent_runtime.state.models import ResponseIntent, RunState

    state = RunState.new(
        current_user_message=(
            "I would like to invest in LYFT over 5 years feb 2020-feb 2025, "
            "$200,000 of capital"
        ),
        recent_thread_history=[],
    )
    state.response_intent = ResponseIntent(
        kind="clarification",
        semantic_needs=["sizing_amount", "schedule"],
        requested_fields=["capital_amount", "cadence"],
        facts={
            "strategy": StrategySummary(
                strategy_type="dca_accumulation",
                strategy_thesis="Recurring buys for LYFT.",
                asset_universe=["LYFT"],
                asset_class="equity",
                date_range={"start": "2020-02-01", "end": "2025-02-28"},
                extra_parameters={"initial_capital": 200000},
            ).model_dump(mode="python")
        },
    )

    copy = compose_response_intent(state)

    assert copy is not None
    assert "LYFT" in copy
    assert "recurring" in copy.lower()
    assert "how much" in copy.lower()
    assert "how often" in copy.lower()
    assert "total budget" in copy.lower()
    assert "one more detail" not in copy.lower()


def test_dca_total_budget_clarification_does_not_reask_known_cadence() -> None:
    from argus.agent_runtime.stages.compose import compose_response_intent
    from argus.agent_runtime.state.models import ResponseIntent, RunState

    state = RunState.new(
        current_user_message=(
            "I would like to invest in LYFT monthly over 5 years, "
            "$200,000 total"
        ),
        recent_thread_history=[],
    )
    state.response_intent = ResponseIntent(
        kind="clarification",
        semantic_needs=["sizing_amount"],
        requested_fields=["capital_amount"],
        facts={
            "strategy": StrategySummary(
                strategy_type="dca_accumulation",
                strategy_thesis="Monthly recurring buys for LYFT.",
                asset_universe=["LYFT"],
                asset_class="equity",
                date_range={"start": "2020-02-01", "end": "2025-02-28"},
                cadence="monthly",
                extra_parameters={"total_capital": 200000},
            ).model_dump(mode="python")
        },
    )

    copy = compose_response_intent(state)

    assert copy is not None
    copy_lower = copy.lower()
    assert "how much" in copy_lower
    assert "total budget" in copy_lower
    assert "how often" not in copy_lower


def test_supported_bollinger_capability_is_not_recovered_as_unsupported() -> None:
    from argus.agent_runtime.capabilities.answers import compose_capability_answer
    from argus.agent_runtime.capabilities.contract import (
        build_default_capability_contract,
    )

    answer = compose_capability_answer(
        focus="supported_indicators",
        contract=build_default_capability_contract(),
    )

    assert "Bollinger Bands" in answer
    assert "executable" in answer.lower()


def test_invalid_date_answer_after_pending_clarification_asks_for_correction(
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
        strategy_thesis="Buy and hold Apple against QQQ.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        comparison_baseline="QQQ",
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User supplied an end date before the pending start date.",
        candidate_strategy_draft=StrategySummary(
            date_range={"end": "2023-12-31"},
        ),
        semantic_turn_act="answer_pending_need",
    )

    result, _ = _interpret(
        message="end of 2023",
        response=response,
        snapshot=TaskSnapshot(pending_strategy_summary=pending),
        selected_thread_metadata={
            "last_stage_outcome": "await_user_reply",
            "requested_field": "date_range",
        },
    )

    assert result.outcome == "needs_clarification"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["AAPL"]
    assert strategy.comparison_baseline == "QQQ"
    assert result.decision.missing_required_fields == ["date_range"]
    assert any(
        constraint.category == "invalid_date_range"
        for constraint in result.decision.unsupported_constraints
    )
    assert "invalid_date_range_requires_correction" in result.decision.reason_codes


def test_interpreter_unavailable_pending_date_answer_uses_date_contract_fallback(
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
        strategy_thesis="Buy and hold Apple against QQQ.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range={"start": "2024-01-01"},
        comparison_baseline="QQQ",
    )

    result, _ = _interpret(
        message="end of 2023",
        response=None,
        snapshot=TaskSnapshot(pending_strategy_summary=pending),
        selected_thread_metadata={
            "last_stage_outcome": "await_user_reply",
            "requested_field": "date_range",
        },
    )

    assert result.outcome == "needs_clarification"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["AAPL"]
    assert strategy.comparison_baseline == "QQQ"
    assert strategy.date_range == {
        "start": "2024-01-01",
        "end": "2023-12-31",
    }
    assert result.decision.missing_required_fields == ["date_range"]
    assert any(
        constraint.category == "invalid_date_range"
        for constraint in result.decision.unsupported_constraints
    )
    assert "deterministic_pending_date_answer_fallback" in result.decision.reason_codes
    assert "llm_interpreter_unavailable" not in result.decision.reason_codes


def test_fresh_complete_restatement_after_failed_clarification_starts_confirmation(
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
        strategy_thesis="Buy and hold Apple against QQQ.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        comparison_baseline="QQQ",
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User restated a complete executable idea.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold Microsoft against QQQ.",
            asset_universe=["MSFT"],
            asset_class="equity",
            date_range={"start": "2024-01-01", "end": "2024-12-31"},
            comparison_baseline="QQQ",
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = _interpret(
        message="Actually test MSFT vs QQQ from Jan 1 2024 to Dec 31 2024",
        response=response,
        snapshot=TaskSnapshot(pending_strategy_summary=pending),
        selected_thread_metadata={
            "last_stage_outcome": "await_user_reply",
            "requested_field": "date_range",
        },
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["MSFT"]
    assert strategy.comparison_baseline == "QQQ"
    assert strategy.date_range == {"start": "2024-01-01", "end": "2024-12-31"}
    assert "fresh_complete_restatement_started_new_confirmation" in (
        result.decision.reason_codes
    )
    assert "assistant_response" not in result.patch


def test_fresh_complete_restatement_preserves_user_stated_benchmark(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    def _asset(symbol: str) -> ResolvedAssetStub:
        normalized = symbol.upper()
        if normalized not in {"AAPL", "QQQ", "SPY"}:
            raise ValueError(symbol)
        return ResolvedAssetStub(normalized, "equity")

    monkeypatch.setattr(interpret_module, "resolve_asset", _asset)
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Apple against QQQ.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range={"start": "2024-01-01"},
        comparison_baseline="QQQ",
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User restated a complete executable idea.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold Apple over 2024.",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range={"start": "2024-01-01", "end": "2024-12-31"},
            comparison_baseline="SPY",
        ),
        semantic_turn_act="retry_failed_action",
    )

    result, _ = _interpret(
        message=(
            "if i bought AAPL at the start of 2024 until the end of 2024, "
            "how did it compare with QQQ?"
        ),
        response=response,
        snapshot=TaskSnapshot(pending_strategy_summary=pending),
        selected_thread_metadata={
            "last_stage_outcome": "await_user_reply",
            "requested_field": "date_range",
        },
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["AAPL"]
    assert strategy.comparison_baseline == "QQQ"
    assert "user_stated_benchmark_preserved" in result.decision.reason_codes


def test_fresh_complete_restatement_after_failed_date_followup_keeps_strategy_route(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    def _asset(symbol: str) -> ResolvedAssetStub:
        normalized = symbol.upper()
        if normalized not in {"AAPL", "QQQ", "IWM"}:
            raise ValueError(symbol)
        return ResolvedAssetStub(normalized, "equity")

    monkeypatch.setattr(interpret_module, "resolve_asset", _asset)
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Apple against QQQ.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range={"start": "2024-01-01", "end": "2023-12-31"},
        comparison_baseline="QQQ",
    )
    response = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User restated a complete executable idea.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold Apple against QQQ over 2024.",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range={"start": "2024-01-01", "end": "2024-12-31"},
            comparison_baseline="QQQ",
        ),
        semantic_turn_act="result_followup",
        result_followup_focus="assumptions",
    )

    result, _ = _interpret(
        message=(
            "if i bought AAPL at the start of 2024 until the end of 2024, "
            "how did it compare with QQQ?"
        ),
        response=response,
        snapshot=TaskSnapshot(pending_strategy_summary=pending),
        selected_thread_metadata={
            "last_stage_outcome": "needs_clarification",
            "fallback_source": "pending_strategy_metadata",
        },
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["AAPL"]
    assert strategy.date_range == {"start": "2024-01-01", "end": "2024-12-31"}
    assert strategy.comparison_baseline == "QQQ"
    assert "fresh_restatement_followup_route_repaired" in result.decision.reason_codes
    assert "assistant_response" not in result.patch


def test_fresh_complete_restatement_route_repair_handles_different_benchmark(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    def _asset(symbol: str) -> ResolvedAssetStub:
        normalized = symbol.upper()
        if normalized not in {"MSFT", "IWM"}:
            raise ValueError(symbol)
        return ResolvedAssetStub(normalized, "equity")

    monkeypatch.setattr(interpret_module, "resolve_asset", _asset)
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Microsoft against IWM.",
        asset_universe=["MSFT"],
        asset_class="equity",
        date_range={"start": "2025-01-01"},
        comparison_baseline="IWM",
    )
    response = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User restated a complete executable idea.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold Microsoft against IWM over 2025.",
            asset_universe=["MSFT"],
            asset_class="equity",
            date_range={"start": "2025-01-01", "end": "2025-12-31"},
            comparison_baseline="IWM",
        ),
        semantic_turn_act="result_followup",
    )

    result, _ = _interpret(
        message="compare MSFT with IWM from Jan 1 2025 to Dec 31 2025",
        response=response,
        snapshot=TaskSnapshot(pending_strategy_summary=pending),
        selected_thread_metadata={
            "last_stage_outcome": "needs_clarification",
            "fallback_source": "pending_strategy_metadata",
        },
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["MSFT"]
    assert strategy.date_range == {"start": "2025-01-01", "end": "2025-12-31"}
    assert strategy.comparison_baseline == "IWM"


def test_partial_explicit_date_range_requires_endpoint_clarification(
    monkeypatch,
) -> None:
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
        user_goal_summary="User supplied a start date and benchmark but no end date.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold Apple against QQQ.",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range={"start": "2024-01-01"},
            comparison_baseline="QQQ",
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = _interpret(
        message="if i bought AAPL at the start of 2024 how did it compare with QQQ?",
        response=response,
        snapshot=None,
    )

    assert result.outcome == "needs_clarification"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["AAPL"]
    assert strategy.comparison_baseline == "QQQ"
    assert result.decision.missing_required_fields == ["date_range"]
    assert "partial_date_range_requires_clarification" in (
        result.decision.reason_codes
    )


def test_partial_explicit_date_range_requires_endpoint_clarification_variation(
    monkeypatch,
) -> None:
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
        user_goal_summary="User supplied a start date and benchmark but no end date.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold Microsoft against IWM.",
            asset_universe=["MSFT"],
            asset_class="equity",
            date_range={"from": "2025-01-01"},
            comparison_baseline="IWM",
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = _interpret(
        message="compare MSFT with IWM from the beginning of 2025",
        response=response,
        snapshot=None,
    )

    assert result.outcome == "needs_clarification"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["MSFT"]
    assert strategy.comparison_baseline == "IWM"
    assert result.decision.missing_required_fields == ["date_range"]
    assert "partial_date_range_requires_clarification" in (
        result.decision.reason_codes
    )


def test_focused_strategy_extraction_preserves_user_stated_benchmark() -> None:
    from argus.agent_runtime.llm_interpreter import (
        _response_from_focused_strategy_extraction,
    )
    from argus.agent_runtime.llm_interpreter_types import FocusedStrategyExtraction
    from argus.agent_runtime.stages.interpret_types import InterpretationRequest

    request = InterpretationRequest(
        current_user_message=(
            "If I bought AAPL at the start of 2024, how did it compare with QQQ?"
        ),
        user=UserState(user_id="user-1"),
    )
    extraction = FocusedStrategyExtraction(
        is_testable_strategy=True,
        requires_clarification=True,
        user_goal_summary="User wants to compare Apple with QQQ.",
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Apple against QQQ.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range={"start": "2024-01-01"},
        comparison_baseline="QQQ",
        missing_required_fields=["date_range"],
    )

    response = _response_from_focused_strategy_extraction(
        extraction=extraction,
        request=request,
    )

    draft = response.candidate_strategy_draft
    assert draft.asset_universe == ["AAPL"]
    assert draft.comparison_baseline == "QQQ"
    assert draft.date_range == {"start": "2024-01-01"}
    assert response.missing_required_fields == ["date_range"]


def test_stated_run_fidelity_removes_inferred_date_endpoint_and_restores_benchmark() -> None:
    from argus.agent_runtime.llm_interpreter import (
        StatedRunFieldFidelityAudit,
        _response_from_stated_run_field_fidelity_audit,
    )
    from argus.agent_runtime.llm_interpreter_types import (
        LLMInterpretationResponse,
        LLMStrategyDraft,
    )

    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User wants to compare Apple with QQQ.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "If I bought AAPL at the start of 2024, how did it compare with QQQ?"
            ),
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold Apple against QQQ.",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range={"start": "2024-01-01", "end": "today"},
            comparison_baseline=None,
        ),
        semantic_turn_act="new_idea",
    )
    audit = StatedRunFieldFidelityAudit(
        date_range={"start": "2024-01-01"},
        comparison_baseline="QQQ",
    )

    repaired = _response_from_stated_run_field_fidelity_audit(
        response=response,
        audit=audit,
    )

    assert repaired is not None
    draft = repaired.candidate_strategy_draft
    assert draft.date_range == {"start": "2024-01-01"}
    assert draft.comparison_baseline == "QQQ"
    assert "stated_run_field_fidelity_audit" in repaired.reason_codes


def test_stated_run_fidelity_audit_uses_current_message_context() -> None:
    from argus.agent_runtime.llm_interpreter import (
        _response_needs_stated_run_field_fidelity_audit,
    )
    from argus.agent_runtime.llm_interpreter_types import (
        LLMInterpretationResponse,
        LLMStrategyDraft,
    )
    from argus.agent_runtime.stages.interpret_types import InterpretationRequest

    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User wants to compare Apple with QQQ.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="buy_and_hold",
            strategy_thesis="AAPL buy and hold",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range={"start": "2024-01-02", "end": "2024-12-31"},
            comparison_baseline="SPY",
        ),
        semantic_turn_act="new_idea",
    )
    request = InterpretationRequest(
        current_user_message=(
            "if i bought AAPL at the start of 2024 until the end of 2024, "
            "how did it compare with QQQ?"
        ),
        user=UserState(user_id="user-1"),
    )

    assert _response_needs_stated_run_field_fidelity_audit(
        response=response,
        request=request,
    )


def test_stated_run_fidelity_audit_skips_complete_aligned_comparison() -> None:
    from argus.agent_runtime.llm_interpreter import (
        _response_needs_stated_run_field_fidelity_audit,
    )
    from argus.agent_runtime.llm_interpreter_types import (
        LLMInterpretationResponse,
        LLMStrategyDraft,
    )
    from argus.agent_runtime.stages.interpret_types import InterpretationRequest

    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User wants to compare Apple with SPY.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="buy_and_hold",
            strategy_thesis="AAPL buy and hold",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range={"start": "2024-01-01", "end": "2025-12-31"},
            comparison_baseline="SPY",
        ),
        semantic_turn_act="new_idea",
    )
    request = InterpretationRequest(
        current_user_message=(
            "If I bought AAPL at the start of 2024 and held through the end of "
            "2025, how would it compare with SPY?"
        ),
        user=UserState(user_id="user-1"),
    )

    assert not _response_needs_stated_run_field_fidelity_audit(
        response=response,
        request=request,
    )


def test_stated_run_fidelity_audit_catches_repaired_default_window_and_benchmark() -> None:
    from argus.agent_runtime.llm_interpreter import (
        _response_needs_stated_run_field_fidelity_audit,
    )
    from argus.agent_runtime.llm_interpreter_types import (
        LLMInterpretationResponse,
        LLMStrategyDraft,
    )
    from argus.agent_runtime.stages.interpret_types import InterpretationRequest

    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User wants to compare Apple with QQQ.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="buy_and_hold",
            strategy_thesis="AAPL buy and hold over the default window.",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range="past year",
            comparison_baseline="SPY",
        ),
        semantic_turn_act="new_idea",
        assistant_response=(
            "Do you want to compare AAPL against QQQ from January 1, 2024 to today?"
        ),
        reason_codes=["focused_strategy_extraction_repair"],
    )
    request = InterpretationRequest(
        current_user_message=(
            "if i bought AAPL at the start of 2024 how did it compare with QQQ?"
        ),
        user=UserState(user_id="user-1"),
    )

    assert _response_needs_stated_run_field_fidelity_audit(
        response=response,
        request=request,
    )


def test_stated_run_fidelity_audit_handles_retry_restatement_benchmark() -> None:
    from argus.agent_runtime.llm_interpreter import (
        _response_needs_stated_run_field_fidelity_audit,
    )
    from argus.agent_runtime.llm_interpreter_types import (
        LLMInterpretationResponse,
        LLMStrategyDraft,
    )
    from argus.agent_runtime.stages.interpret_types import InterpretationRequest

    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User restated a complete executable idea.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="buy_and_hold",
            strategy_thesis="AAPL buy and hold over 2024.",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range={"start": "2024-01-01", "end": "2024-12-31"},
            comparison_baseline="SPY",
        ),
        semantic_turn_act="retry_failed_action",
    )
    request = InterpretationRequest(
        current_user_message=(
            "if i bought AAPL at the start of 2024 until the end of 2024, "
            "how did it compare with QQQ?"
        ),
        user=UserState(user_id="user-1"),
    )

    assert _response_needs_stated_run_field_fidelity_audit(
        response=response,
        request=request,
    )


def test_current_message_contract_repair_preserves_partial_date_and_benchmark(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as llm_module
    from argus.agent_runtime.llm_interpreter import (
        _response_from_current_message_run_field_contract,
    )
    from argus.agent_runtime.llm_interpreter_types import (
        LLMInterpretationResponse,
        LLMStrategyDraft,
    )
    from argus.agent_runtime.stages.interpret_types import InterpretationRequest

    def _asset(query: str) -> ResolvedAssetStub:
        normalized = query.strip().upper()
        if normalized not in {"AAPL", "QQQ"}:
            raise ValueError(query)
        return ResolvedAssetStub(normalized, "equity", name=normalized, raw_symbol=normalized)

    monkeypatch.setattr(llm_module, "resolve_asset", _asset)
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User wants to compare Apple with QQQ.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="buy_and_hold",
            strategy_thesis="AAPL buy and hold over the default window.",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range="past year",
            comparison_baseline="SPY",
        ),
        semantic_turn_act="new_idea",
        reason_codes=["focused_strategy_extraction_repair"],
    )
    request = InterpretationRequest(
        current_user_message=(
            "if i bought AAPL at the start of 2024 how did it compare with QQQ?"
        ),
        user=UserState(user_id="user-1"),
    )

    repaired = _response_from_current_message_run_field_contract(
        response=response,
        request=request,
    )

    assert repaired is not None
    draft = repaired.candidate_strategy_draft
    assert draft.asset_universe == ["AAPL"]
    assert draft.comparison_baseline == "QQQ"
    assert draft.date_range == {"start": "2024-01-01"}
    assert repaired.requires_clarification
    assert repaired.missing_required_fields == ["date_range"]
    assert repaired.assistant_response is None
    assert "current_message_run_field_contract_repair" in repaired.reason_codes


def test_current_message_contract_repair_preserves_full_natural_date_range(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as llm_module
    from argus.agent_runtime.llm_interpreter import (
        _response_from_current_message_run_field_contract,
    )
    from argus.agent_runtime.llm_interpreter_types import (
        LLMInterpretationResponse,
        LLMStrategyDraft,
    )
    from argus.agent_runtime.stages.interpret_types import InterpretationRequest

    def _asset(query: str) -> ResolvedAssetStub:
        normalized = query.strip().upper()
        if normalized not in {"AAPL", "SPY"}:
            raise ValueError(query)
        return ResolvedAssetStub(
            normalized,
            "equity",
            name=normalized,
            raw_symbol=normalized,
        )

    monkeypatch.setattr(llm_module, "resolve_asset", _asset)
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="User wants to compare Apple with SPY.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="buy_and_hold",
            strategy_thesis="AAPL buy and hold through end of 2025.",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range=None,
            comparison_baseline="SPY",
        ),
        semantic_turn_act="new_idea",
        missing_required_fields=["date_range"],
    )
    request = InterpretationRequest(
        current_user_message=(
            "If I bought AAPL at the start of 2024 and held through the end "
            "of 2025, how would it compare with SPY?"
        ),
        user=UserState(user_id="user-1"),
    )

    repaired = _response_from_current_message_run_field_contract(
        response=response,
        request=request,
    )

    assert repaired is not None
    draft = repaired.candidate_strategy_draft
    assert draft.date_range == {"start": "2024-01-01", "end": "2025-12-31"}
    assert draft.comparison_baseline == "SPY"
    assert not repaired.requires_clarification
    assert repaired.missing_required_fields == []
    assert repaired.assistant_response is None
    assert "current_message_run_field_contract_repair" in repaired.reason_codes


def test_current_message_contract_repair_preserves_calendar_year_date_range(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as llm_module
    from argus.agent_runtime.llm_interpreter import (
        _response_from_current_message_run_field_contract,
    )
    from argus.agent_runtime.llm_interpreter_types import (
        LLMInterpretationResponse,
        LLMStrategyDraft,
    )
    from argus.agent_runtime.stages.interpret_types import InterpretationRequest

    def _asset(query: str) -> ResolvedAssetStub:
        normalized = query.strip().upper()
        if normalized != "NVDA":
            raise ValueError(query)
        return ResolvedAssetStub(
            normalized,
            "equity",
            name=normalized,
            raw_symbol=normalized,
        )

    monkeypatch.setattr(llm_module, "resolve_asset", _asset)
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="User wants weekly NVDA recurring buys.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="dca_accumulation",
            strategy_thesis="Weekly NVDA recurring buys.",
            asset_universe=["NVDA"],
            asset_class="equity",
            date_range={"end": "2024-12-31"},
            cadence=None,
            capital_amount=None,
            total_capital=250,
            field_provenance={"total_capital": "total_budget"},
        ),
        semantic_turn_act="new_idea",
        missing_required_fields=["date_range", "capital_amount", "cadence"],
    )
    request = InterpretationRequest(
        current_user_message="What if I bought $250 of NVDA every week in 2024?",
        user=UserState(user_id="user-1"),
    )

    repaired = _response_from_current_message_run_field_contract(
        response=response,
        request=request,
    )

    assert repaired is not None
    draft = repaired.candidate_strategy_draft
    assert draft.date_range == {"start": "2024-01-01", "end": "2024-12-31"}
    assert draft.cadence == "weekly"
    assert draft.capital_amount == 250
    assert draft.total_capital is None
    assert draft.field_provenance["capital_amount"] == "recurring_contribution"
    assert not repaired.requires_clarification
    assert repaired.missing_required_fields == []
    assert "current_message_run_field_contract_repair" in repaired.reason_codes


def test_current_message_contract_repair_handles_other_symbols_and_year(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as llm_module
    from argus.agent_runtime.llm_interpreter import (
        _response_from_current_message_run_field_contract,
    )
    from argus.agent_runtime.llm_interpreter_types import (
        LLMInterpretationResponse,
        LLMStrategyDraft,
    )
    from argus.agent_runtime.stages.interpret_types import InterpretationRequest

    def _asset(query: str) -> ResolvedAssetStub:
        normalized = query.strip().upper()
        if normalized not in {"MSFT", "IWM"}:
            raise ValueError(query)
        return ResolvedAssetStub(normalized, "equity", name=normalized, raw_symbol=normalized)

    monkeypatch.setattr(llm_module, "resolve_asset", _asset)
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User wants to compare Microsoft with IWM.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="buy_and_hold",
            strategy_thesis="MSFT buy and hold over the default window.",
            asset_universe=["MSFT"],
            asset_class="equity",
            date_range="past year",
            comparison_baseline="SPY",
        ),
        semantic_turn_act="new_idea",
        reason_codes=["focused_strategy_extraction_repair"],
    )
    request = InterpretationRequest(
        current_user_message="compare MSFT with IWM from the beginning of 2025",
        user=UserState(user_id="user-1"),
    )

    repaired = _response_from_current_message_run_field_contract(
        response=response,
        request=request,
    )

    assert repaired is not None
    draft = repaired.candidate_strategy_draft
    assert draft.asset_universe == ["MSFT"]
    assert draft.comparison_baseline == "IWM"
    assert draft.date_range == {"start": "2025-01-01"}
    assert "current_message_run_field_contract_repair" in repaired.reason_codes


def test_stated_run_fidelity_audit_skips_aligned_focused_repair() -> None:
    from argus.agent_runtime.llm_interpreter import (
        _response_needs_stated_run_field_fidelity_audit,
    )
    from argus.agent_runtime.llm_interpreter_types import (
        LLMInterpretationResponse,
        LLMStrategyDraft,
    )
    from argus.agent_runtime.stages.interpret_types import InterpretationRequest

    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User wants to compare Apple with SPY.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="buy_and_hold",
            strategy_thesis="AAPL buy and hold.",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range={"start": "2024-01-01", "end": "2025-12-31"},
            comparison_baseline="SPY",
        ),
        semantic_turn_act="new_idea",
        reason_codes=["focused_strategy_extraction_repair"],
    )
    request = InterpretationRequest(
        current_user_message=(
            "If I bought AAPL at the start of 2024 and held through the end of "
            "2025, how would it compare with SPY?"
        ),
        user=UserState(user_id="user-1"),
    )

    assert not _response_needs_stated_run_field_fidelity_audit(
        response=response,
        request=request,
    )


def test_pending_date_answer_uses_stated_run_fidelity_audit() -> None:
    from argus.agent_runtime.llm_interpreter import (
        _response_needs_stated_run_field_fidelity_audit,
    )
    from argus.agent_runtime.llm_interpreter_types import (
        LLMInterpretationResponse,
        LLMStrategyDraft,
    )
    from argus.agent_runtime.stages.interpret_types import InterpretationRequest

    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User supplied the requested end date.",
        candidate_strategy_draft=LLMStrategyDraft(
            date_range={"start": "2023-12-31", "end": "2023-12-31"},
        ),
        semantic_turn_act="answer_pending_need",
    )
    request = InterpretationRequest(
        current_user_message="end of 2023",
        selected_thread_metadata={
            "last_stage_outcome": "await_user_reply",
            "requested_field": "date_range",
        },
        user=UserState(user_id="user-1"),
    )

    assert _response_needs_stated_run_field_fidelity_audit(
        response=response,
        request=request,
    )


def test_pending_non_date_answer_does_not_use_stated_run_fidelity_audit() -> None:
    from argus.agent_runtime.llm_interpreter import (
        _response_needs_stated_run_field_fidelity_audit,
    )
    from argus.agent_runtime.llm_interpreter_types import (
        LLMInterpretationResponse,
        LLMStrategyDraft,
    )
    from argus.agent_runtime.stages.interpret_types import InterpretationRequest

    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User supplied the requested asset.",
        candidate_strategy_draft=LLMStrategyDraft(asset_universe=["MSFT"]),
        semantic_turn_act="answer_pending_need",
    )
    request = InterpretationRequest(
        current_user_message="MSFT",
        selected_thread_metadata={
            "last_stage_outcome": "await_user_reply",
            "requested_field": "asset_universe",
        },
        user=UserState(user_id="user-1"),
    )

    assert not _response_needs_stated_run_field_fidelity_audit(
        response=response,
        request=request,
    )


def test_runnable_clarification_candidate_still_uses_stated_run_fidelity_audit() -> None:
    from argus.agent_runtime.llm_interpreter import (
        _response_needs_stated_run_field_fidelity_audit,
    )
    from argus.agent_runtime.llm_interpreter_types import (
        LLMInterpretationResponse,
        LLMStrategyDraft,
    )
    from argus.agent_runtime.stages.interpret_types import InterpretationRequest

    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="User wants to compare Apple with QQQ.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="buy_and_hold",
            strategy_thesis="AAPL buy and hold",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range={"start": "2024-01-01", "end": "2026-05-31"},
            comparison_baseline=None,
        ),
        semantic_turn_act="new_idea",
    )
    request = InterpretationRequest(
        current_user_message=(
            "if i bought AAPL at the start of 2024 how did it compare with QQQ?"
        ),
        user=UserState(user_id="user-1"),
    )

    assert _response_needs_stated_run_field_fidelity_audit(
        response=response,
        request=request,
    )


def test_stated_run_fidelity_continues_when_expected_date_is_omitted() -> None:
    from argus.agent_runtime.llm_interpreter import (
        StatedRunFieldFidelityAudit,
        _stated_run_field_audit_omitted_expected_fields,
    )
    from argus.agent_runtime.llm_interpreter_types import (
        LLMInterpretationResponse,
        LLMStrategyDraft,
    )
    from argus.agent_runtime.stages.interpret_types import InterpretationRequest

    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="User wants to compare Apple with QQQ.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="buy_and_hold",
            strategy_thesis="AAPL buy and hold",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range={"start": "2024-01-01", "end": "2026-05-31"},
        ),
        semantic_turn_act="new_idea",
    )
    request = InterpretationRequest(
        current_user_message=(
            "if i bought AAPL at the start of 2024 how did it compare with QQQ?"
        ),
        user=UserState(user_id="user-1"),
    )
    audit = StatedRunFieldFidelityAudit(comparison_baseline="QQQ")

    assert _stated_run_field_audit_omitted_expected_fields(
        response=response,
        audit=audit,
        request=request,
    )


def test_benchmark_symbol_is_removed_from_asset_universe_and_kept_as_benchmark(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    def _asset(symbol: str) -> ResolvedAssetStub:
        normalized = symbol.upper()
        return ResolvedAssetStub(normalized, "crypto")

    monkeypatch.setattr(interpret_module, "resolve_asset", _asset)
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User wants to test ETH against BTC.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold ETH against BTC.",
            asset_universe=["ETH", "BTC"],
            asset_class="crypto",
            date_range={"start": "2024-01-01", "end": "2024-12-31"},
            comparison_baseline="BTC",
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = _interpret(
        message="test ETH vs BTC in 2024",
        response=response,
        snapshot=None,
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["ETH"]
    assert strategy.comparison_baseline == "BTC"
    assert "benchmark_symbol_removed_from_asset_universe" in (
        result.decision.reason_codes
    )
    from argus.agent_runtime.stages.execute import _launch_payload

    launch_state = RunState.new(current_user_message="", recent_thread_history=[])
    launch_state.candidate_strategy_draft = strategy
    launch_payload = _launch_payload(launch_state)
    assert launch_payload["symbols"] == ["ETH"]
    assert launch_payload["benchmark_symbol"] == "BTC"


def test_benchmark_only_asset_universe_requires_traded_asset(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    def _asset(symbol: str) -> ResolvedAssetStub:
        normalized = symbol.upper()
        return ResolvedAssetStub(normalized, "crypto")

    monkeypatch.setattr(interpret_module, "resolve_asset", _asset)
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User wants a crypto backtest against BTC.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Compare a crypto asset against BTC.",
            asset_universe=["BTC"],
            asset_class="crypto",
            date_range={"start": "2024-01-01", "end": "2024-12-31"},
            comparison_baseline="BTC",
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = _interpret(
        message="test it against BTC in 2024",
        response=response,
        snapshot=None,
    )

    assert result.outcome == "needs_clarification"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == []
    assert strategy.comparison_baseline == "BTC"
    assert "asset_universe" in result.decision.missing_required_fields
    assert "benchmark_symbol_removed_from_asset_universe" in (
        result.decision.reason_codes
    )
