import pytest
from argus.domain.orchestrator import (
    StrategyIntent,
    SlotValue,
    plan_strategy_action,
    compile_backtest_payload,
)
from argus.domain.strategy_capabilities import STRATEGY_CAPABILITIES

def test_plan_requires_template():
    intent = StrategyIntent(
        template=SlotValue(value=None, source="missing"),
        symbols=SlotValue(value=["AAPL"], source="user_supplied"),
    )
    plan = plan_strategy_action(intent, "en")
    assert plan.action == "ask_clarification"
    assert "template" in plan.missing_fields
    assert "What kind of strategy" in plan.message

def test_plan_requires_symbols():
    intent = StrategyIntent(
        template=SlotValue(value="dca_accumulation", source="user_supplied"),
        symbols=SlotValue(value=[], source="missing"),
    )
    plan = plan_strategy_action(intent, "en")
    assert plan.action == "ask_clarification"
    assert "symbols" in plan.missing_fields
    assert "Which symbols" in plan.message

def test_plan_requires_dca_cadence():
    intent = StrategyIntent(
        template=SlotValue(value="dca_accumulation", source="user_supplied"),
        symbols=SlotValue(value=["AAPL"], source="user_supplied"),
        parameters={"dca_cadence": SlotValue(value=None, source="missing")}
    )
    plan = plan_strategy_action(intent, "en")
    assert plan.action == "ask_clarification"
    assert "dca_cadence" in plan.missing_fields
    assert "How often" in plan.message

def test_plan_resolves_aliases():
    intent = StrategyIntent(
        template=SlotValue(value="dca", source="user_supplied"), # Alias
        symbols=SlotValue(value=["AAPL"], source="user_supplied"),
        parameters={"dca_cadence": SlotValue(value="monthly", source="user_supplied")}
    )
    plan = plan_strategy_action(intent, "en")
    assert plan.action == "run_backtest"

def test_plan_ready_to_run():
    intent = StrategyIntent(
        template=SlotValue(value="rsi_mean_reversion", source="user_supplied"),
        symbols=SlotValue(value=["BTC"], source="user_supplied"),
    )
    plan = plan_strategy_action(intent, "en")
    assert plan.action == "run_backtest"

def test_plan_spanish_clarification():
    intent = StrategyIntent(
        template=SlotValue(value="dca_accumulation", source="user_supplied"),
        symbols=SlotValue(value=[], source="missing"),
    )
    plan = plan_strategy_action(intent, "es-419")
    assert plan.action == "ask_clarification"
    assert "¿Sobre qué activos" in plan.message

def test_compile_backtest_payload():
    intent = StrategyIntent(
        template=SlotValue(value="dca_accumulation", source="user_supplied"),
        symbols=SlotValue(value=["AAPL"], source="user_supplied"),
        parameters={"dca_cadence": SlotValue(value="weekly", source="user_supplied")}
    )
    payload = compile_backtest_payload(intent)
    assert payload["template"] == "dca_accumulation"
    assert payload["symbols"] == ["AAPL"]
    assert payload["parameters"]["dca_cadence"] == "weekly"
    assert payload["starting_capital"] == 10000 # Default
    assert payload["benchmark_symbol"] == "SPY" # Inferred

def test_compile_resolves_aliases_and_defaults():
    intent = StrategyIntent(
        template=SlotValue(value="dca", source="user_supplied"),
        symbols=SlotValue(value=["BTC"], source="user_supplied"),
        # dca_cadence missing
    )
    payload = compile_backtest_payload(intent)
    assert payload["template"] == "dca_accumulation"
    assert payload["parameters"]["dca_cadence"] == "monthly" # From registry default
    assert payload["benchmark_symbol"] == "BTC"
