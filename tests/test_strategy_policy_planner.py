import pytest
from argus.domain.orchestrator import (
    StrategyIntent,
    SlotValue,
    plan_strategy_action,
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
