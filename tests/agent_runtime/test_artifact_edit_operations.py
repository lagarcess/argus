from __future__ import annotations

import pytest
from argus.agent_runtime import artifact_edit_planner
from argus.agent_runtime.artifact_edit_planner import (
    ArtifactAssumptionEditPlan,
    EditOperation,
    apply_edit_operations,
    plan_artifact_assumption_edit,
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


def test_rsi_threshold_edits_are_typed_artifact_operations():
    resolved = apply_edit_operations(
        [
            EditOperation(
                op="set",
                target="indicator_entry_threshold",
                number=35,
            ),
            EditOperation(
                op="set",
                target="indicator_exit_threshold",
                number=65,
            ),
        ],
    )

    assert resolved.indicator_parameters == {
        "entry_threshold": 35.0,
        "exit_threshold": 65.0,
    }
    assert "set.indicator_entry_threshold" in resolved.applied
    assert "set.indicator_exit_threshold" in resolved.applied
    assert resolved.unsupported == []


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


def test_remove_asset_name_uses_symbol_resolver():
    resolved = apply_edit_operations(
        [EditOperation(op="remove", target="asset", symbols=["Microsoft"])],
        current_asset_universe=["AAPL", "MSFT", "TSLA"],
        asset_symbol_resolver=lambda raw: (
            "MSFT" if raw.casefold() == "microsoft" else None
        ),
    )

    assert resolved.asset_universe == ["AAPL", "TSLA"]
    assert resolved.asset_universe_operation == "replace"
    assert resolved.applied == ["remove.asset"]
    assert resolved.unsupported == []


def test_unresolved_remove_asset_name_is_unsupported_not_silent_noop():
    resolved = apply_edit_operations(
        [EditOperation(op="remove", target="asset", symbols=["Microsoft"])],
        current_asset_universe=["AAPL", "MSFT", "TSLA"],
        asset_symbol_resolver=lambda _raw: None,
    )

    assert resolved.asset_universe is None
    assert resolved.asset_universe_operation is None
    assert resolved.applied == []
    assert resolved.unsupported == ["remove.asset"]


@pytest.mark.asyncio
async def test_planner_keeps_company_name_asset_remove_for_later_resolution(
    monkeypatch,
):
    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: [],
    )

    async def invoke_stub(*, model_name, **kwargs):
        del model_name, kwargs
        return ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[
                EditOperation(
                    op="remove",
                    target="asset",
                    symbols=["Microsoft"],
                )
            ],
            confidence=0.91,
        )

    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    plan = await plan_artifact_assumption_edit(
        current_user_message="remove Microsoft",
        prior_strategy={
            "asset_universe": ["AAPL", "MSFT", "TSLA"],
            "capital_amount": 100000,
        },
        active_confirmation=None,
        preferred_model="preferred-model",
    )

    assert plan is not None
    assert [
        (operation.op, operation.target, operation.symbols)
        for operation in plan.operations
    ] == [
        ("remove", "asset", ["Microsoft"])
    ]
