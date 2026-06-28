from __future__ import annotations

from argus.agent_runtime.artifact_edit_planner import (
    EditOperation,
    apply_edit_operations,
)
from argus.agent_runtime.llm_interpreter_types import LLMDateRangeIntent


def test_add_and_remove_in_one_turn():
    resolved = apply_edit_operations(
        [
            EditOperation(op="add", target="asset", symbols=["amzn"]),
            EditOperation(op="remove", target="asset", symbols=["tsla"]),
        ],
        current_asset_universe=["AAPL", "TSLA"],
    )
    assert resolved.asset_universe == ["AAPL", "AMZN"]
    assert resolved.asset_universe_operation == "replace"
    assert "add.asset" in resolved.applied
    assert "remove.asset" in resolved.applied


def test_compound_date_and_asset_edit_is_not_dropped():
    # The canonical failing case: "change the start date and add AMZN".
    intent = LLMDateRangeIntent(kind="calendar_year", year=2026)
    resolved = apply_edit_operations(
        [
            EditOperation(op="add", target="asset", symbols=["AMZN"]),
            EditOperation(op="set", target="date_window", date_window=intent),
        ],
        current_asset_universe=["AAPL"],
    )
    assert resolved.asset_universe == ["AAPL", "AMZN"]
    assert resolved.date_window is intent
    assert "add.asset" in resolved.applied
    assert "set.date_window" in resolved.applied
    assert resolved.unsupported == []


def test_replace_asset_universe():
    resolved = apply_edit_operations(
        [EditOperation(op="replace", target="asset", symbols=["QQQ", "SPY"])],
        current_asset_universe=["AAPL", "TSLA"],
    )
    assert resolved.asset_universe == ["QQQ", "SPY"]
    assert resolved.asset_universe_operation == "replace"


def test_benchmark_and_scalars_in_one_turn():
    resolved = apply_edit_operations(
        [
            EditOperation(op="set", target="benchmark", value="qqq"),
            EditOperation(op="set", target="capital", number=5000),
            EditOperation(op="set", target="fees", number=0.001),
            EditOperation(op="set", target="slippage", number=0.0005),
        ],
    )
    assert resolved.comparison_baseline == "QQQ"
    assert resolved.initial_capital == 5000
    assert resolved.fee_rate == 0.001
    assert resolved.slippage == 0.0005
    assert resolved.asset_universe is None  # untouched


def test_unsupported_operation_is_named_not_dropped():
    resolved = apply_edit_operations(
        [
            EditOperation(op="add", target="asset", symbols=["AMZN"]),
            EditOperation(op="remove", target="capital"),  # nonsensical → unsupported
        ],
        current_asset_universe=["AAPL"],
    )
    assert resolved.asset_universe == ["AAPL", "AMZN"]
    assert "add.asset" in resolved.applied
    assert "remove.capital" in resolved.unsupported


def test_clear_assets():
    resolved = apply_edit_operations(
        [EditOperation(op="clear", target="asset")],
        current_asset_universe=["AAPL", "TSLA"],
    )
    assert resolved.asset_universe == []
    assert resolved.asset_universe_operation == "replace"
    assert "clear.asset" in resolved.applied


def test_empty_operations_makes_no_changes():
    resolved = apply_edit_operations([], current_asset_universe=["AAPL"])
    assert not resolved.has_changes()
    assert resolved.asset_universe is None
