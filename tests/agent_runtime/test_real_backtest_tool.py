from __future__ import annotations

import pytest

from argus.agent_runtime.tools.real_backtest import RealBacktestTool
from argus.domain.engine_launch.adapter import LaunchExecutionAdapterResult
from argus.domain.engine_launch.models import LaunchExecutionEnvelope


def test_real_backtest_tool_returns_success_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = RealBacktestTool()

    monkeypatch.setattr(
        "argus.agent_runtime.tools.real_backtest.run_launch_backtest",
        lambda request: LaunchExecutionAdapterResult(
            envelope=LaunchExecutionEnvelope(
                execution_status="succeeded",
                resolved_strategy={
                    "strategy_type": "buy_and_hold",
                    "symbol": "TSLA",
                },
                resolved_parameters={"timeframe": "1D"},
                metrics={"aggregate": {"performance": {"total_return_pct": 12.5}}},
                benchmark_metrics={"symbol": "SPY"},
                assumptions=["Starting capital: $10,000."],
                caveats=["1D bars only."],
                provider_metadata={"provider": "alpaca"},
            ),
            result_card={"title": "TSLA Buy and Hold"},
            explanation_context={
                "strategy_type": "buy_and_hold",
                "assumptions": ["Starting capital: $10,000."],
            },
        ),
    )

    result = tool.run(
        {
            "strategy_type": "buy_and_hold",
            "symbol": "TSLA",
            "timeframe": "1D",
            "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
            "entry_rule": None,
            "exit_rule": None,
            "sizing_mode": "capital_amount",
            "capital_amount": 10000.0,
            "position_size": None,
            "cadence": None,
            "parameters": {},
            "risk_rules": [],
            "benchmark_symbol": "SPY",
        }
    )

    assert result["success"] is True
    assert result["payload"]["envelope"]["execution_status"] == "succeeded"
    assert result["payload"]["result_card"]["title"] == "TSLA Buy and Hold"
    assert result["payload"]["explanation_context"]["strategy_type"] == "buy_and_hold"
    assert result["error_type"] is None


def test_real_backtest_tool_maps_blocked_unsupported_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = RealBacktestTool()

    monkeypatch.setattr(
        "argus.agent_runtime.tools.real_backtest.run_launch_backtest",
        lambda request: LaunchExecutionAdapterResult(
            envelope=LaunchExecutionEnvelope(
                execution_status="blocked_unsupported",
                resolved_strategy={
                    "strategy_type": "indicator_threshold",
                    "symbol": "TSLA",
                },
                resolved_parameters={"timeframe": "1D"},
                metrics={},
                benchmark_metrics={},
                failure_category="unsupported_capability",
                failure_reason="unsupported_indicator_threshold",
            ),
        ),
    )

    result = tool.run(
        {
            "strategy_type": "indicator_threshold",
            "symbol": "TSLA",
            "timeframe": "1D",
            "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
            "entry_rule": {"indicator": "rsi", "operator": "below", "threshold": 25},
            "exit_rule": {"indicator": "rsi", "operator": "above", "threshold": 60},
            "sizing_mode": "capital_amount",
            "capital_amount": 10000.0,
            "position_size": None,
            "cadence": None,
            "parameters": {},
            "risk_rules": [],
            "benchmark_symbol": "SPY",
        }
    )

    assert result["success"] is False
    assert result["error_type"] == "unsupported_capability"
    assert result["error_message"] == "unsupported_indicator_threshold"
    assert result["retryable"] is False
    assert result["capability_context"]["execution_status"] == "blocked_unsupported"


def test_real_backtest_tool_maps_validation_error() -> None:
    tool = RealBacktestTool()

    result = tool.run(
        {
            "strategy_type": "buy_and_hold",
            "symbol": "TSLA",
            "timeframe": "1D",
            "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
            "entry_rule": None,
            "exit_rule": None,
            "sizing_mode": "capital_amount",
            "capital_amount": None,
            "position_size": None,
            "cadence": None,
            "parameters": {},
            "risk_rules": [],
            "benchmark_symbol": "SPY",
        }
    )

    assert result["success"] is False
    assert result["error_type"] == "parameter_validation_error"
    assert result["error_message"] == "capital_amount_required"
