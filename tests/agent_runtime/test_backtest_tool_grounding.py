"""Backtest calls retain the structured facts observed in the first live gate."""

from __future__ import annotations

from typing import Any, get_args

import pytest
from argus.agent_runtime.capabilities.answers import capability_fact_packet
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.llm_interpreter import OpenRouterStructuredInterpreter
from argus.agent_runtime.stages.interpret_types import (
    CapabilityQuestionFocus,
    InterpretationRequest,
)
from argus.agent_runtime.state.models import RunState, StrategySummary, UserState
from argus.domain.capability_registry import get_tool_catalog
from pydantic import ValidationError


@pytest.fixture(autouse=True)
def _local_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "false")
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "synthetic_unit_fixture")
    monkeypatch.setenv("ARGUS_EXECUTION_REALISM_ENABLED", "true")
    monkeypatch.setattr(
        "argus.agent_runtime.stages.confirm._market_clock_for_strategy",
        lambda _asset_class: None,
    )


async def _prepared_call(strategy: dict[str, Any], *, message: str) -> Any:
    from argus.agent_runtime.stages.tool_execution import execute_tool_calls_async

    user = UserState(user_id="registry-grounding")
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    response = interpreter.response_model.model_validate(
        {
            "intent": "calculate",
            "task_relation": "new_task",
            "semantic_turn_act": "new_idea",
            "user_goal_summary": message,
            "tool_calls": [
                {
                    "call_id": "declared-backtest",
                    "tool_name": "backtest",
                    "arguments": {"strategy": strategy},
                }
            ],
        }
    )
    interpretation = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(current_user_message=message, user=user),
    )
    return await execute_tool_calls_async(
        state=RunState(
            current_user_message=message,
            intent=interpretation.intent,
            task_relation=interpretation.task_relation,
            semantic_turn_act=interpretation.semantic_turn_act,
            tool_calls=interpretation.tool_calls,
        ),
        tool=object(),
        user=user,
    )


def _dca_input(**overrides: Any) -> dict[str, Any]:
    return {
        "strategy_type": "dca_accumulation",
        "asset_universe": ["SPY"],
        "asset_class": "equity",
        "capital_amount": 200,
        "cadence": "monthly",
        "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
        **overrides,
    }


def test_backtest_schema_declares_extraction_facts_as_typed_arguments() -> None:
    declaration = get_tool_catalog().get("backtest")
    assert declaration is not None
    strategy_type = declaration.arguments_type.model_fields["strategy"].annotation
    fields = strategy_type.model_fields
    assert {"initial_capital", "total_capital", "recurring_contribution"} <= fields.keys()
    assert {"date_range_intent", "date_range_raw_text", "evidence_spans"} <= fields.keys()


@pytest.mark.asyncio
async def test_recorded_crossover_call_keeps_nested_dates_and_normalizes_rules() -> None:
    window = {"start": "2022-01-02", "end": "2025-01-02"}
    rule = {
        "type": "moving_average_crossover",
        "fast_indicator": "sma",
        "slow_indicator": "sma",
        "fast_period": 50,
        "slow_period": 200,
    }
    result = await _prepared_call(
        {
            "strategy_type": "signal_strategy",
            "requested_strategy_template": "moving_average_crossover",
            "asset_universe": ["AAPL"],
            "asset_class": "equity",
            "capital_amount": 10000,
            "date_range": None,
            "entry_rule": {**rule, "direction": "bullish"},
            "exit_rule": {**rule, "direction": "bearish"},
            "extra_parameters": {"date_range": window},
        },
        message="Backtest $10,000 in AAPL from January 2, 2022 through January 2, 2025 using a golden cross.",
    )
    assert result.outcome == "ready_for_confirmation"
    strategy = StrategySummary.model_validate(result.patch["candidate_strategy_draft"])
    assert strategy.date_range == window
    assert strategy.rule_spec is not None
    assert strategy.rule_spec["entry"]["conditions"][0]["operator"] == "cross_above"
    assert strategy.comparison_baseline == "SPY"


@pytest.mark.asyncio
@pytest.mark.parametrize("seed", [0, 1000, 5000])
async def test_declared_seed_is_not_silently_replaced_by_zero(seed: int) -> None:
    result = await _prepared_call(
        _dca_input(initial_capital=seed, recurring_contribution=200),
        message=f"Start with ${seed} in SPY and add $200 every month in 2024.",
    )
    assert result.outcome == "ready_for_confirmation"
    strategy = StrategySummary.model_validate(result.patch["candidate_strategy_draft"])
    assert strategy.extra_parameters["initial_capital"] == seed
    assert strategy.extra_parameters["recurring_contribution"] == 200
    assert (
        strategy.extra_parameters["field_provenance"]["initial_capital"]
        == "starting_capital"
    )


@pytest.mark.asyncio
async def test_tool_costs_use_the_same_grounded_evidence_as_pending_drafts() -> None:
    result = await _prepared_call(
        {
            "strategy_type": "buy_and_hold",
            "asset_universe": ["MSFT"],
            "asset_class": "equity",
            "capital_amount": 12000,
            "date_range": {"start": "2023-01-03", "end": "2024-12-31"},
            "evidence_spans": {"fee_rate": "10 bps fee", "slippage": "5 bps slippage"},
            "extra_parameters": {"fee_rate": 0.001, "slippage": 0.0005},
        },
        message="Test MSFT with $12,000, a 10 bps fee and 5 bps slippage from 2023-01-03 to 2024-12-31.",
    )
    assert result.outcome == "ready_for_confirmation"
    extra = result.patch["candidate_strategy_draft"]["extra_parameters"]
    assert extra["fee_rate"] == 0.001
    assert extra["slippage"] == 0.0005
    assert extra["field_provenance"]["fee_rate"] == "explicit_user"
    assert extra["field_provenance"]["slippage"] == "explicit_user"


@pytest.mark.asyncio
@pytest.mark.parametrize("contribution", [None, 200])
async def test_declared_contribution_ceiling_reaches_existing_recovery(
    contribution: int | None,
) -> None:
    from argus.agent_runtime.stages.clarify import clarify_stage_async

    message = "Test monthly purchases of SPY during 2024 with a $5,000 total investment ceiling."
    result = await _prepared_call(
        _dca_input(
            capital_amount=contribution,
            recurring_contribution=contribution,
            total_capital=5000,
        ),
        message=message,
    )
    assert result.outcome == "needs_clarification"
    assert result.patch["candidate_strategy_draft"]["capital_amount"] == contribution
    recovery = await clarify_stage_async(
        state=RunState.model_validate({"current_user_message": message, **result.patch}),
        contract=build_default_capability_contract(),
        clarification_generator=lambda _request: "Choose an alternative without the total ceiling.",
    )
    assert recovery.outcome == "await_user_reply"
    assert (
        recovery.patch["clarification"]["reason_code"]
        == "unsupported_dca_contribution_ceiling"
    )
    assert recovery.patch["clarification"]["kind"] == "unsupported_recovery"


@pytest.mark.parametrize("focus", get_args(CapabilityQuestionFocus))
def test_every_capability_packet_contains_the_effective_tool_catalog(focus: str) -> None:
    catalog = get_tool_catalog()
    packet = capability_fact_packet(
        focus=focus, contract=build_default_capability_contract(), tool_catalog=catalog
    )
    assert catalog.capability_text() in packet


@pytest.mark.asyncio
async def test_educational_fallback_composer_receives_declared_capability_truth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime.stages import interpret

    captured: dict[str, Any] = {}

    async def compose(**kwargs: Any) -> str:
        captured.update(kwargs)
        return "Catalog-grounded answer."

    monkeypatch.setattr(interpret, "invoke_openrouter_chat_completion", compose)
    await interpret._compose_general_educational_answer(
        current_user_message="Can Argus help me find new stocks to explore?"
    )
    assert get_tool_catalog().capability_text() in " ".join(
        item["content"] for item in captured["messages"]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("strategy_type", ["options_straddle", "news_sentiment"])
async def test_unsupported_declared_input_keeps_assets_and_dates_for_recovery(
    strategy_type: str,
) -> None:
    window = {"start": "2024-01-01", "end": "2024-12-31"}
    result = await _prepared_call(
        {
            "strategy_type": strategy_type,
            "asset_universe": ["TSLA"],
            "asset_class": "equity",
            "date_range": window,
            "capital_amount": 10000,
            "entry_logic": "The requested unsupported entry condition.",
            "exit_logic": "The requested unsupported exit condition.",
        },
        message="Prepare the historical test using the supplied strategy facts.",
    )
    assert result.outcome == "needs_clarification"
    assert result.patch["candidate_strategy_draft"]["asset_universe"] == ["TSLA"]
    assert result.patch["candidate_strategy_draft"]["date_range"] == window
    assert result.patch["optional_parameter_status"]["unsupported_constraints"]


@pytest.mark.asyncio
async def test_declared_period_longer_than_window_reaches_launch_validation() -> None:
    from argus.agent_runtime.stages.confirm import confirm_stage

    message = "DCA $500 quarterly into AAPL from January through February 2024."
    prepared = await _prepared_call(
        _dca_input(
            asset_universe=["AAPL"],
            capital_amount=500,
            recurring_contribution=500,
            cadence="quarterly",
            date_range={"start": "2024-01-01", "end": "2024-02-29"},
        ),
        message=message,
    )
    assert prepared.outcome == "ready_for_confirmation"
    result = confirm_stage(
        state=RunState.model_validate(
            {"current_user_message": message, **prepared.patch}
        ),
        contract=build_default_capability_contract(),
    )
    assert result.outcome == "needs_clarification"
    assert result.patch["launch_validation_code"] == "contribution_period_exceeds_window"


def test_conflicting_argument_and_extension_values_are_rejected() -> None:
    from argus.agent_runtime.backtest_input import BacktestStrategyInput

    with pytest.raises(ValidationError, match="Conflicting values"):
        BacktestStrategyInput.model_validate(
            _dca_input(initial_capital=0, extra_parameters={"initial_capital": 5000})
        )


def test_focused_repair_schema_can_express_every_declared_money_role() -> None:
    from argus.agent_runtime.llm_interpreter_types import FocusedStrategyExtraction

    assert {
        "initial_capital",
        "total_capital",
        "recurring_contribution",
    } <= FocusedStrategyExtraction.model_fields.keys()


def test_focused_repair_preserves_seed_contribution_and_ceiling_separately() -> None:
    from argus.agent_runtime.interpreter.focused_extraction import (
        response_from_focused_strategy_extraction,
    )
    from argus.agent_runtime.llm_interpreter_types import FocusedStrategyExtraction

    extraction = FocusedStrategyExtraction.model_validate(
        {
            **_dca_input(
                initial_capital=0,
                recurring_contribution=200,
                total_capital=5000,
                evidence_spans={
                    "initial_capital": "Start from zero",
                    "recurring_contribution": "contribute $200 monthly",
                    "total_capital": "up to $5,000 total",
                },
            ),
            "is_testable_strategy": True,
            "user_goal_summary": "A recurring plan with three different money roles.",
        }
    )
    response = response_from_focused_strategy_extraction(
        extraction=extraction,
        request=InterpretationRequest(
            current_user_message="Start from zero, contribute $200 monthly, up to $5,000 total.",
            user=UserState(user_id="focused-repair"),
        ),
        resolve_asset_candidate=lambda *_args, **_kwargs: None,
    )
    draft = response.candidate_strategy_draft
    assert draft.initial_capital == 0
    assert draft.recurring_contribution == 200
    assert draft.total_capital == 5000
    assert draft.field_provenance["initial_capital"] == "starting_capital"
    assert draft.field_provenance["total_capital"] == "total_capital"


def test_pending_draft_cost_candidate_reaches_existing_fidelity_owner() -> None:
    from argus.agent_runtime.llm_interpreter_types import LLMStrategyDraft

    draft = LLMStrategyDraft(fee_rate=0, slippage=0.0005)
    assert draft.extra_parameters["fee_rate"] == 0
    assert draft.extra_parameters["slippage"] == 0.0005
    assert draft._validated_execution_cost_evidence == {}
