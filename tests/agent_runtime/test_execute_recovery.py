import inspect
import json
from datetime import date
from types import SimpleNamespace

import pytest
from argus.agent_runtime.graph.workflow import build_workflow
from argus.agent_runtime.recovery.policy import should_retry
from argus.agent_runtime.runtime import run_agent_turn
from argus.agent_runtime.stages.execute import execute_stage
from argus.agent_runtime.stages.explain import explain_stage, explain_stage_async
from argus.agent_runtime.stages.interpret import InterpretationRequest
from argus.agent_runtime.stages.interpret_types import StructuredInterpretation
from argus.agent_runtime.state.models import (
    ResponseProfile,
    RunState,
    StrategySummary,
    UserState,
)
from argus.agent_runtime.tools.backtest_stub import StubBacktestTool
from argus.agent_runtime.tools.real_backtest import RealBacktestTool
from argus.domain.engine_launch.adapter import LaunchExecutionAdapterResult
from argus.domain.engine_launch.models import LaunchExecutionEnvelope
from langgraph.checkpoint.memory import MemorySaver


def _assert_value_absent(value: object, forbidden: str) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            assert forbidden not in str(key)
            _assert_value_absent(nested, forbidden)
        return
    if isinstance(value, list):
        for nested in value:
            _assert_value_absent(nested, forbidden)
        return
    if isinstance(value, str):
        assert forbidden not in value


def test_parameter_validation_retries_only_for_mechanical_intent_preserving_fix() -> None:
    assert (
        should_retry(
            error_type="parameter_validation_error",
            retryable=True,
            attempt=1,
            max_retries=2,
            capability_context={
                "mechanical_correction_available": True,
                "intent_preserving": True,
                "corrected_payload": {"strategy": {"asset_universe": ["TSLA"]}},
            },
        )
        is True
    )
    assert (
        should_retry(
            error_type="parameter_validation_error",
            retryable=True,
            attempt=1,
            max_retries=2,
            capability_context={
                "mechanical_correction_available": False,
                "intent_preserving": True,
                "corrected_payload": {"strategy": {"asset_universe": ["TSLA"]}},
            },
        )
        is False
    )
    assert (
        should_retry(
            error_type="parameter_validation_error",
            retryable=True,
            attempt=1,
            max_retries=2,
            capability_context=None,
        )
        is False
    )


def test_execute_applies_mechanical_correction_before_retry() -> None:
    tool = StubBacktestTool(
        responses=[
            {
                "success": False,
                "error_type": "parameter_validation_error",
                "error_message": "Normalize asset symbol casing.",
                "retryable": True,
                "payload": None,
                "capability_context": {
                    "mechanical_correction_available": True,
                    "intent_preserving": True,
                    "corrected_payload": {"strategy": {"asset_universe": ["TSLA"]}},
                },
            },
            {
                "success": True,
                "payload": {"total_return": 0.14, "benchmark_return": 0.09},
                "error_type": None,
                "error_message": None,
                "retryable": False,
                "capability_context": {},
            },
        ]
    )
    state = RunState.new(current_user_message="run it", recent_thread_history=[])
    state.confirmation_payload = {"strategy": {"asset_universe": ["tsla"]}}

    result = execute_stage(state=state, tool=tool, max_retries=2)

    assert result.outcome == "execution_succeeded"
    assert tool.calls[0]["strategy_type"] == "buy_and_hold"
    assert tool.calls[0]["symbol"] == "TSLA"
    assert tool.calls[1] == {
        "strategy": {"asset_universe": ["TSLA"]},
        "language": "en",
    }
    assert result.patch["tool_call_records"][0]["payload"] == {}


def test_execute_does_not_retry_when_corrected_payload_changes_protected_intent_fields() -> (
    None
):
    tool = StubBacktestTool(
        responses=[
            {
                "success": False,
                "error_type": "parameter_validation_error",
                "error_message": "Attempted symbol normalization.",
                "retryable": True,
                "payload": None,
                "capability_context": {
                    "mechanical_correction_available": True,
                    "intent_preserving": True,
                    "corrected_payload": {"strategy": {"asset_universe": ["AAPL"]}},
                },
            },
        ]
    )
    state = RunState.new(current_user_message="run it", recent_thread_history=[])
    state.confirmation_payload = {"strategy": {"asset_universe": ["TSLA"]}}

    result = execute_stage(state=state, tool=tool, max_retries=2)

    assert result.outcome == "execution_failed_terminally"
    assert result.patch["failure_classification"] == "parameter_validation_error"
    assert len(tool.calls) == 1
    failed_reference = result.patch["latest_failed_action_reference"]
    metadata = failed_reference["metadata"]
    assert metadata["retryable"] is False
    assert metadata["recovery_mode"] == "reopen_confirmation"
    assert metadata["launch_payload"]["symbol"] == "TSLA"


def test_execute_retries_only_for_retryable_transient_failure() -> None:
    tool = StubBacktestTool(
        responses=[
            {
                "success": False,
                "error_type": "upstream_dependency_error",
                "error_message": "timeout",
                "retryable": True,
                "payload": None,
                "capability_context": {},
            },
            {
                "success": True,
                "payload": {"total_return": 0.14, "benchmark_return": 0.09},
                "error_type": None,
                "error_message": None,
                "retryable": False,
                "capability_context": {},
            },
        ]
    )
    state = RunState.new(current_user_message="run it", recent_thread_history=[])
    state.confirmation_payload = {"strategy": {"asset_universe": ["TSLA"]}}

    result = execute_stage(state=state, tool=tool, max_retries=2)

    assert result.outcome == "execution_succeeded"
    assert len(result.patch["tool_call_records"]) == 2
    assert result.patch["failure_classification"] is None
    assert result.patch["final_response_payload"]["result"]["total_return"] == 0.14
    assert result.patch["tool_call_records"][0]["error_message"] == "timeout"
    assert result.patch["tool_call_records"][0]["payload"] == {}


def test_execute_does_not_retry_unsupported_capability() -> None:
    tool = StubBacktestTool(
        responses=[
            {
                "success": False,
                "error_type": "unsupported_capability",
                "error_message": "options backtests not supported",
                "retryable": False,
                "payload": None,
                "capability_context": {},
            },
        ]
    )
    state = RunState.new(current_user_message="run it", recent_thread_history=[])
    state.confirmation_payload = {"strategy": {"asset_universe": ["TSLA"]}}

    result = execute_stage(state=state, tool=tool, max_retries=2)

    assert result.outcome == "needs_clarification"
    assert result.patch["failure_classification"] == "unsupported_capability"
    assert len(result.patch["tool_call_records"]) == 1
    assert "reframe this into a supported backtest" in result.patch["assistant_prompt"]
    assert "same-asset strategy" in result.patch["assistant_prompt"]


def test_execute_preserves_last_failure_class_when_retries_are_exhausted() -> None:
    tool = StubBacktestTool(
        responses=[
            {
                "success": False,
                "error_type": "service_overloaded",
                "error_message": "service busy",
                "retryable": True,
                "payload": None,
                "capability_context": {},
            },
            {
                "success": False,
                "error_type": "rate_limited",
                "error_message": "try later",
                "retryable": True,
                "payload": None,
                "capability_context": {},
            },
        ]
    )
    state = RunState.new(current_user_message="run it", recent_thread_history=[])
    state.confirmation_payload = {"strategy": {"asset_universe": ["TSLA"]}}

    result = execute_stage(state=state, tool=tool, max_retries=2)

    assert result.outcome == "execution_failed_terminally"
    assert result.patch["failure_classification"] == "upstream_dependency_error"
    assert "try later" not in result.patch["final_response_payload"]["error"]
    assert "try later" not in result.patch["assistant_prompt"]
    assert "temporary data or service issue" in result.patch["assistant_prompt"]


def test_execute_recovers_visible_dca_confirmation_when_market_data_is_unavailable() -> (
    None
):
    tool = StubBacktestTool(
        responses=[
            {
                "success": False,
                "error_type": "upstream_dependency_error",
                "error_message": "market_data_unavailable",
                "retryable": True,
                "payload": None,
                "capability_context": {},
            },
            {
                "success": False,
                "error_type": "upstream_dependency_error",
                "error_message": "market_data_unavailable",
                "retryable": True,
                "payload": None,
                "capability_context": {},
            },
        ]
    )
    state = RunState.new(current_user_message="Run backtest", recent_thread_history=[])
    state.confirmation_payload = {
        "strategy": {
            "strategy_type": "dca_accumulation",
            "strategy_thesis": "Invest $20,000 in BTC every week for 6 months.",
            "asset_universe": ["BTC"],
            "asset_class": "crypto",
            "date_range": {"start": "2025-11-12", "end": "2026-05-12"},
            "cadence": "weekly",
            "capital_amount": 20000,
            "sizing_mode": "capital_amount",
        },
        "optional_parameters": {
            "timeframe": {"value": "1D", "source": "default"},
            "initial_capital": {"value": 1000, "source": "default"},
        },
    }

    result = execute_stage(state=state, tool=tool, max_retries=2)

    assert result.outcome == "execution_failed_recoverably"
    assert result.patch["failure_classification"] == "upstream_dependency_error"
    prompt = result.patch["assistant_prompt"]
    assert "BTC recurring-buys draft" in prompt
    assert "market data" in prompt
    assert "try again" in prompt.lower()
    assert "market_data_unavailable" not in prompt
    assert result.patch["recovery"] == {
        "code": "execution_data_unavailable",
        "retryable": True,
        "params": {"data_kind": "market"},
    }
    assert result.patch["final_response_payload"]["error"] == prompt
    failed_reference = result.patch["latest_failed_action_reference"]
    assert failed_reference["artifact_kind"] == "failed_action"
    assert failed_reference["artifact_status"] == "failed"
    assert failed_reference["metadata"]["action_type"] == "run_backtest"
    assert failed_reference["metadata"]["failure_classification"] == (
        "upstream_dependency_error"
    )
    assert failed_reference["metadata"]["launch_payload"]["strategy_type"] == (
        "dca_accumulation"
    )
    assert failed_reference["metadata"]["launch_payload"]["symbol"] == "BTC"


def test_execute_recovers_visible_confirmation_when_benchmark_data_is_unavailable() -> (
    None
):
    tool = StubBacktestTool(
        responses=[
            {
                "success": False,
                "error_type": "upstream_dependency_error",
                "error_message": "benchmark_data_unavailable",
                "retryable": True,
                "payload": None,
                "capability_context": {"failure_detail": "benchmark_data_issue"},
            },
            {
                "success": False,
                "error_type": "upstream_dependency_error",
                "error_message": "benchmark_data_unavailable",
                "retryable": True,
                "payload": None,
                "capability_context": {"failure_detail": "benchmark_data_issue"},
            },
        ]
    )
    state = RunState.new(current_user_message="Run backtest", recent_thread_history=[])
    state.confirmation_payload = {
        "strategy": {
            "strategy_type": "buy_and_hold",
            "strategy_thesis": "Buy and hold TSLA in 2024.",
            "asset_universe": ["TSLA"],
            "asset_class": "equity",
            "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
            "capital_amount": 10000,
            "sizing_mode": "capital_amount",
        },
        "optional_parameters": {
            "timeframe": {"value": "1D", "source": "default"},
            "benchmark_symbol": {"value": "SPY", "source": "default"},
        },
    }

    result = execute_stage(state=state, tool=tool, max_retries=2)

    assert result.outcome == "execution_failed_recoverably"
    assert result.patch["failure_classification"] == "upstream_dependency_error"
    prompt = result.patch["assistant_prompt"]
    assert "TSLA buy-and-hold draft" in prompt
    assert "benchmark data" in prompt
    assert "try again" in prompt.lower()
    assert "benchmark_data_unavailable" not in prompt
    assert result.patch["recovery"] == {
        "code": "execution_data_unavailable",
        "retryable": True,
        "params": {"data_kind": "benchmark"},
    }
    assert result.patch["final_response_payload"]["error"] == prompt
    failed_reference = result.patch["latest_failed_action_reference"]
    assert failed_reference["metadata"]["action_type"] == "run_backtest"
    assert failed_reference["metadata"]["failure_classification"] == (
        "upstream_dependency_error"
    )
    assert failed_reference["metadata"]["launch_payload"]["symbol"] == "TSLA"


def test_execute_emits_market_data_recovery_code_for_spanish_confirmation() -> None:
    tool = StubBacktestTool(
        responses=[
            {
                "success": False,
                "error_type": "upstream_dependency_error",
                "error_message": "market_data_unavailable",
                "retryable": True,
                "payload": None,
                "capability_context": {"failure_detail": "market_data_issue"},
            },
            {
                "success": False,
                "error_type": "upstream_dependency_error",
                "error_message": "market_data_unavailable",
                "retryable": True,
                "payload": None,
                "capability_context": {"failure_detail": "market_data_issue"},
            },
        ]
    )
    state = RunState.new(current_user_message="Ejecutar backtest", recent_thread_history=[])
    state.confirmation_payload = {
        "strategy": {
            "strategy_type": "buy_and_hold",
            "strategy_thesis": "Comprar y mantener AAPL.",
            "asset_universe": ["AAPL"],
            "asset_class": "equity",
            "date_range": {"start": "2025-01-01", "end": "2025-06-01"},
            "capital_amount": 10000,
            "sizing_mode": "capital_amount",
        },
        "optional_parameters": {
            "timeframe": {"value": "1D", "source": "default"},
            "benchmark_symbol": {"value": "SPY", "source": "default"},
        },
    }

    result = execute_stage(state=state, tool=tool, max_retries=2, language="es-419")

    assert result.outcome == "execution_failed_recoverably"
    prompt = result.patch["assistant_prompt"]
    assert "AAPL buy-and-hold draft" in prompt
    assert "market data" in prompt
    assert "market_data_unavailable" not in prompt
    assert result.patch["recovery"] == {
        "code": "execution_data_unavailable",
        "retryable": True,
        "params": {"data_kind": "market"},
    }


def test_execute_emits_benchmark_data_recovery_code_for_spanish_confirmation() -> None:
    tool = StubBacktestTool(
        responses=[
            {
                "success": False,
                "error_type": "upstream_dependency_error",
                "error_message": "benchmark_data_unavailable",
                "retryable": True,
                "payload": None,
                "capability_context": {"failure_detail": "benchmark_data_issue"},
            },
            {
                "success": False,
                "error_type": "upstream_dependency_error",
                "error_message": "benchmark_data_unavailable",
                "retryable": True,
                "payload": None,
                "capability_context": {"failure_detail": "benchmark_data_issue"},
            },
        ]
    )
    state = RunState.new(current_user_message="Ejecutar backtest", recent_thread_history=[])
    state.confirmation_payload = {
        "strategy": {
            "strategy_type": "buy_and_hold",
            "strategy_thesis": "Comprar y mantener TSLA.",
            "asset_universe": ["TSLA"],
            "asset_class": "equity",
            "date_range": {"start": "2025-01-01", "end": "2025-06-01"},
            "capital_amount": 10000,
            "sizing_mode": "capital_amount",
        },
        "optional_parameters": {
            "timeframe": {"value": "1D", "source": "default"},
            "benchmark_symbol": {"value": "SPY", "source": "default"},
        },
    }

    result = execute_stage(state=state, tool=tool, max_retries=2, language="es-419")

    assert result.outcome == "execution_failed_recoverably"
    prompt = result.patch["assistant_prompt"]
    assert "TSLA buy-and-hold draft" in prompt
    assert "benchmark data" in prompt
    assert "benchmark_data_unavailable" not in prompt
    assert result.patch["recovery"] == {
        "code": "execution_data_unavailable",
        "retryable": True,
        "params": {"data_kind": "benchmark"},
    }


def test_execute_does_not_classify_unavailable_data_from_prose_only() -> None:
    tool = StubBacktestTool(
        responses=[
            {
                "success": False,
                "error_type": "upstream_dependency_error",
                "error_message": "Benchmark data was unavailable for that run.",
                "retryable": True,
                "payload": None,
                "capability_context": {},
            }
        ]
    )
    state = RunState.new(current_user_message="Run backtest", recent_thread_history=[])
    state.confirmation_payload = {
        "strategy": {
            "strategy_type": "buy_and_hold",
            "strategy_thesis": "Buy and hold TSLA.",
            "asset_universe": ["TSLA"],
            "asset_class": "equity",
            "date_range": {"start": "2025-01-01", "end": "2025-06-01"},
            "capital_amount": 10000,
            "sizing_mode": "capital_amount",
        },
        "optional_parameters": {
            "timeframe": {"value": "1D", "source": "default"},
            "benchmark_symbol": {"value": "SPY", "source": "default"},
        },
    }

    result = execute_stage(state=state, tool=tool, max_retries=1)

    assert result.outcome == "execution_failed_terminally"
    prompt = result.patch["assistant_prompt"]
    assert "temporary data or service issue" in prompt
    assert "could not get benchmark data" not in prompt


def test_execute_missing_required_input_returns_to_conversation() -> None:
    tool = StubBacktestTool(
        responses=[
            {
                "success": False,
                "error_type": "missing_required_input",
                "error_message": "I still need entry logic.",
                "retryable": False,
                "payload": None,
                "capability_context": {"missing_required_fields": ["entry_logic"]},
            },
        ]
    )
    state = RunState.new(current_user_message="run it", recent_thread_history=[])
    state.confirmation_payload = {"strategy": {"asset_universe": ["TSLA"]}}

    result = execute_stage(state=state, tool=tool, max_retries=2)

    assert result.outcome == "needs_clarification"
    assert result.patch["failure_classification"] == "missing_required_input"
    assert "one more executable detail" in result.patch["assistant_prompt"]
    assert "I still need entry logic" not in result.patch["assistant_prompt"]
    assert result.patch["missing_required_fields"] == ["entry_logic"]
    assert len(result.patch["tool_call_records"]) == 1


def test_real_backtest_tool_maps_failure_codes_to_user_safe_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_launch_backtest(request: object, *, language: str = "en") -> object:
        return LaunchExecutionAdapterResult(
            envelope=LaunchExecutionEnvelope(
                execution_status="blocked_invalid_input",
                resolved_strategy={"strategy_type": "signal_strategy", "symbol": "TSLA"},
                resolved_parameters={},
                metrics={},
                benchmark_metrics={},
                assumptions=[],
                caveats=[],
                artifact_references=[],
                provider_metadata={},
                failure_category="parameter_validation_error",
                failure_reason="missing_rule_group",
            )
        )

    monkeypatch.setattr(
        "argus.agent_runtime.tools.real_backtest.run_launch_backtest",
        fake_launch_backtest,
    )

    result = RealBacktestTool().run(
        {
            "strategy_type": "buy_and_hold",
            "symbol": "TSLA",
            "symbols": ["TSLA"],
            "timeframe": "1D",
            "date_range": {"start": "2025-01-01", "end": "2025-12-31"},
            "entry_rule": None,
            "exit_rule": None,
            "sizing_mode": "capital_amount",
            "capital_amount": 1000,
            "position_size": None,
            "cadence": None,
            "parameters": {},
            "risk_rules": [],
            "benchmark_symbol": "SPY",
        }
    )

    assert result["success"] is False
    assert result["error_message"] != "missing_rule_group"
    assert "complete executable entry and exit rule" in result["error_message"]
    assert "failure_reason" not in result["capability_context"]
    assert result["capability_context"]["failure_detail"] == "incomplete_rule"


def test_execute_stage_keeps_raw_failure_code_out_of_ui_error_metadata() -> None:
    tool = StubBacktestTool(
        responses=[
            {
                "success": False,
                "error_type": "parameter_validation_error",
                "error_message": "missing_rule_group",
                "retryable": False,
                "payload": None,
                "capability_context": {
                    "failure_reason": "missing_rule_group",
                    "failure_detail": "incomplete_rule",
                    "missing_required_fields": ["entry_logic"],
                },
            },
        ]
    )
    state = RunState.new(current_user_message="run it", recent_thread_history=[])
    state.confirmation_payload = {"strategy": {"asset_universe": ["TSLA"]}}

    result = execute_stage(state=state, tool=tool, max_retries=1)

    assert result.outcome == "execution_failed_terminally"
    _assert_value_absent(result.patch["final_response_payload"], "missing_rule_group")
    _assert_value_absent(result.patch["latest_failed_action_reference"], "missing_rule_group")
    _assert_value_absent(result.patch["tool_call_records"], "missing_rule_group")
    assert "not valid for the current backtest" in (
        result.patch["final_response_payload"]["error"]
    )
    assert "draft" not in result.patch["final_response_payload"]["error"].lower()
    assert "current setup" in result.patch["final_response_payload"]["error"]


def test_execute_future_end_date_returns_non_retryable_date_prompt() -> None:
    state = RunState.new(current_user_message="Run backtest", recent_thread_history=[])
    state.confirmation_payload = {
        "strategy": {
            "strategy_type": "buy_and_hold",
            "asset_universe": ["AAPL"],
            "date_range": {"start": "2026-01-01", "end": "2099-12-31"},
        },
        "optional_parameters": {
            "timeframe": {"value": "1D", "source": "default"},
            "initial_capital": {"value": 1000.0, "source": "default"},
            "benchmark_symbol": {"value": "QQQ", "source": "user"},
        },
    }

    result = execute_stage(state=state, tool=RealBacktestTool(), max_retries=1)

    assert result.outcome == "execution_failed_terminally"
    assert result.patch["failure_classification"] == "parameter_validation_error"
    prompt = result.patch["assistant_prompt"]
    assert "later than the latest date" in prompt
    failed_reference = result.patch["latest_failed_action_reference"]
    metadata = failed_reference["metadata"]
    assert metadata["retryable"] is False
    assert metadata["failure_classification"] == "parameter_validation_error"
    assert metadata["launch_payload"]["benchmark_symbol"] == "QQQ"
    assert metadata["recovery_mode"] == "reopen_confirmation"


def test_execute_ambiguous_user_intent_returns_to_conversation() -> None:
    tool = StubBacktestTool(
        responses=[
            {
                "success": False,
                "error_type": "ambiguous_user_intent",
                "error_message": "I cannot tell whether you want to continue or start over.",
                "retryable": False,
                "payload": None,
                "capability_context": {},
            },
        ]
    )
    state = RunState.new(current_user_message="do it", recent_thread_history=[])
    state.confirmation_payload = {"strategy": {"asset_universe": ["TSLA"]}}

    result = execute_stage(state=state, tool=tool, max_retries=2)

    assert result.outcome == "needs_clarification"
    assert result.patch["failure_classification"] == "ambiguous_user_intent"
    assert "current idea" in result.patch["assistant_prompt"].lower()
    assert "new backtest" in result.patch["assistant_prompt"].lower()
    assert len(result.patch["tool_call_records"]) == 1


def test_execute_stage_uses_real_backtest_tool_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = RealBacktestTool()
    state = RunState.new(current_user_message="Backtest Tesla", recent_thread_history=[])
    state.candidate_strategy_draft = {
        "strategy_thesis": "Buy and hold Tesla over the last year",
        "asset_universe": ["TSLA"],
        "date_range": "last 1 year",
    }
    state.confirmation_payload = {
        "strategy": {
            "strategy_thesis": "Buy and hold Tesla over the last year",
            "asset_universe": ["TSLA"],
            "date_range": "last 1 year",
        },
        "optional_parameters": {
            "timeframe": {"value": "1D", "source": "default"},
            "initial_capital": {"value": 1000.0, "source": "default"},
        },
    }

    observed_requests: list[dict[str, object]] = []

    def fake_run_launch_backtest(
        request,
        *,
        language: str = "en",
    ) -> LaunchExecutionAdapterResult:
        assert language == "en"
        observed_requests.append(request.model_dump(mode="python"))
        return LaunchExecutionAdapterResult(
            envelope=LaunchExecutionEnvelope(
                execution_status="succeeded",
                resolved_strategy={
                    "strategy_type": "buy_and_hold",
                    "symbol": "TSLA",
                },
                resolved_parameters={"timeframe": "1D"},
                metrics={
                    "aggregate": {"performance": {"total_return_pct": 12.5}},
                },
                benchmark_metrics={
                    "symbol": "SPY",
                    "aggregate": {"total_return_pct": 9.2},
                },
                assumptions=["Starting capital: $10,000."],
                caveats=["1D bars only."],
                provider_metadata={"provider": "alpaca"},
            ),
            result_card={"title": "TSLA Buy and Hold"},
            explanation_context={
                "strategy_type": "buy_and_hold",
                "metrics": {
                    "aggregate": {"performance": {"total_return_pct": 12.5}},
                },
                "benchmark_metrics": {
                    "aggregate": {"total_return_pct": 9.2},
                },
                "assumptions": ["Starting capital: $10,000."],
                "caveats": ["1D bars only."],
            },
        )

    monkeypatch.setattr(
        "argus.agent_runtime.tools.real_backtest.run_launch_backtest",
        fake_run_launch_backtest,
    )

    result = execute_stage(state=state, tool=tool, max_retries=1)

    assert result.outcome == "execution_succeeded"
    assert observed_requests[0]["strategy_type"] == "buy_and_hold"
    assert observed_requests[0]["symbol"] == "TSLA"
    assert (
        result.patch["final_response_payload"]["result_card"]["title"]
        == "TSLA Buy and Hold"
    )
    assert (
        result.patch["final_response_payload"]["explanation_context"]["strategy_type"]
        == "buy_and_hold"
    )


def test_execute_stage_normalizes_persisted_launch_payload_assumption_defaults() -> None:
    tool = StubBacktestTool(
        responses=[
            {
                "success": True,
                "payload": {"result_card": {"title": "TSLA RSI Mean Reversion"}},
                "error_type": None,
                "error_message": None,
                "retryable": False,
                "capability_context": {},
            },
        ]
    )
    state = RunState.new(current_user_message="Run backtest", recent_thread_history=[])
    state.confirmation_payload = {
        "strategy": {
            "strategy_type": "indicator_threshold",
            "asset_universe": ["TSLA"],
            "date_range": "past 3 months",
        },
        "optional_parameters": {
            "fees": {"value": 0.0, "source": "default"},
            "slippage": {"value": 0.0, "source": "default"},
            "engine_options": {"value": {}, "source": "default"},
        },
        "launch_payload": {
            "strategy_type": "indicator_threshold",
            "symbol": "TSLA",
            "symbols": ["TSLA"],
            "timeframe": "1D",
            "date_range": {"start": "2026-02-13", "end": "2026-05-13"},
            "entry_rule": {
                "indicator": "rsi",
                "operator": "below",
                "threshold": 20.0,
            },
            "exit_rule": {
                "indicator": "rsi",
                "operator": "above",
                "threshold": 60.0,
            },
            "sizing_mode": "capital_amount",
            "capital_amount": 1000.0,
            "position_size": None,
            "cadence": None,
            "parameters": {
                "fees": 0.0,
                "slippage": 0.0,
                "engine_options": {},
            },
            "risk_rules": [],
            "benchmark_symbol": "SPY",
            "language": "en",
        },
        "validation": {"status": "ready_to_run", "executable": True},
    }

    result = execute_stage(state=state, tool=tool, max_retries=1)

    assert result.outcome == "execution_succeeded"
    assert tool.calls[0]["parameters"] == {}


def test_execute_stage_passes_language_to_real_backtest_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = RealBacktestTool()
    state = RunState.new(current_user_message="Backtest Tesla", recent_thread_history=[])
    state.confirmation_payload = {
        "strategy": {
            "strategy_thesis": "Comprar y mantener Tesla durante el ultimo ano",
            "asset_universe": ["TSLA"],
            "date_range": "last 1 year",
        },
        "optional_parameters": {
            "timeframe": {"value": "1D", "source": "default"},
            "initial_capital": {"value": 1000.0, "source": "default"},
        },
    }

    observed_languages: list[str] = []

    def fake_run_launch_backtest(
        request,
        *,
        language: str = "en",
    ) -> LaunchExecutionAdapterResult:
        observed_languages.append(language)
        return LaunchExecutionAdapterResult(
            envelope=LaunchExecutionEnvelope(
                execution_status="succeeded",
                resolved_strategy={
                    "strategy_type": request.strategy_type,
                    "symbol": request.symbol,
                },
                resolved_parameters={"timeframe": request.timeframe},
                metrics={"aggregate": {"performance": {"total_return_pct": 12.5}}},
                benchmark_metrics={"symbol": request.benchmark_symbol},
                assumptions=[],
                caveats=[],
                provider_metadata={"provider": "alpaca"},
            ),
            result_card={"title": "TSLA comprar y mantener"},
            explanation_context={},
        )

    monkeypatch.setattr(
        "argus.agent_runtime.tools.real_backtest.run_launch_backtest",
        fake_run_launch_backtest,
    )

    result = execute_stage(
        state=state,
        tool=tool,
        max_retries=1,
        language="es-419",
    )

    assert result.outcome == "execution_succeeded"
    assert observed_languages == ["es-419"]


def test_execute_stage_uses_currency_pair_as_default_benchmark(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime.stages import execute as execute_module

    monkeypatch.setattr(
        execute_module,
        "resolve_asset",
        lambda symbol: SimpleNamespace(
            canonical_symbol="EURUSD",
            asset_class="currency_pair",
        ),
    )
    tool = StubBacktestTool(
        responses=[
            {
                "success": True,
                "payload": {"result_card": {"title": "EUR/USD Buy and Hold"}},
                "error_type": None,
                "error_message": None,
                "retryable": False,
                "capability_context": {},
            }
        ]
    )
    state = RunState.new(
        current_user_message="Backtest EUR/USD", recent_thread_history=[]
    )
    state.confirmation_payload = {
        "strategy": {
            "strategy_thesis": "Buy and hold EUR/USD over the last year",
            "asset_universe": ["EUR/USD"],
            "asset_class": "currency_pair",
            "date_range": "last 1 year",
        },
        "optional_parameters": {
            "timeframe": {"value": "1D", "source": "default"},
            "initial_capital": {"value": 1000.0, "source": "default"},
        },
    }

    execute_stage(state=state, tool=tool, max_retries=1)

    assert tool.calls[0]["benchmark_symbol"] == "EURUSD"


def test_execute_stage_prioritizes_explicit_strategy_benchmark_over_default_optional() -> None:
    tool = StubBacktestTool(
        responses=[
            {
                "success": True,
                "payload": {"result_card": {"title": "AAPL Buy and Hold"}},
                "error_type": None,
                "error_message": None,
                "retryable": False,
                "capability_context": {},
            }
        ]
    )
    state = RunState.new(
        current_user_message="Run backtest",
        recent_thread_history=[],
    )
    state.confirmation_payload = {
        "strategy": {
            "strategy_thesis": "Buy and hold AAPL against QQQ in 2024",
            "strategy_type": "buy_and_hold",
            "asset_universe": ["AAPL"],
            "asset_class": "equity",
            "comparison_baseline": "QQQ",
            "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
            "capital_amount": 1000.0,
        },
        "optional_parameters": {
            "timeframe": {"value": "1D", "source": "default"},
            "initial_capital": {"value": 1000.0, "source": "default"},
            "benchmark_symbol": {"value": "SPY", "source": "default"},
        },
    }

    execute_stage(state=state, tool=tool, max_retries=1)

    assert tool.calls[0]["benchmark_symbol"] == "QQQ"


def test_execute_stage_preserves_multi_symbol_launch_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = RealBacktestTool()
    state = RunState.new(
        current_user_message="Run backtest",
        recent_thread_history=[],
    )
    state.confirmation_payload = {
        "strategy": {
            "strategy_thesis": "Buy and hold SBUX and CMG year to date",
            "strategy_type": "buy_and_hold",
            "asset_universe": ["SBUX", "CMG"],
            "asset_class": "equity",
            "date_range": "year_to_date",
            "capital_amount": 100000.0,
        },
        "optional_parameters": {
            "timeframe": {"value": "1D", "source": "default"},
            "initial_capital": {"value": 1000.0, "source": "default"},
        },
    }

    observed_requests: list[dict[str, object]] = []

    def fake_run_launch_backtest(
        request,
        *,
        language: str = "en",
    ) -> LaunchExecutionAdapterResult:
        assert language == "en"
        observed_requests.append(request.model_dump(mode="python"))
        return LaunchExecutionAdapterResult(
            envelope=LaunchExecutionEnvelope(
                execution_status="succeeded",
                resolved_strategy={
                    "strategy_type": "buy_and_hold",
                    "symbol": "SBUX",
                    "asset_universe": ["SBUX", "CMG"],
                },
                resolved_parameters={"timeframe": "1D"},
                metrics={"aggregate": {"performance": {"total_return_pct": 25.0}}},
                benchmark_metrics={
                    "symbol": "SPY",
                    "aggregate": {"total_return_pct": 5.1},
                },
                assumptions=["Starting capital: $100,000."],
                caveats=["1D bars only."],
                provider_metadata={"provider": "alpaca"},
            ),
            result_card={
                "title": "SBUX, CMG Buy and Hold",
                "symbols": ["SBUX", "CMG"],
                "strategy_label": "Buy and Hold",
            },
            explanation_context={"strategy_type": "buy_and_hold"},
        )

    monkeypatch.setattr(
        "argus.agent_runtime.tools.real_backtest.run_launch_backtest",
        fake_run_launch_backtest,
    )

    result = execute_stage(state=state, tool=tool, max_retries=1)

    assert result.outcome == "execution_succeeded"
    assert observed_requests[0]["symbol"] == "SBUX"
    assert observed_requests[0]["symbols"] == ["SBUX", "CMG"]
    assert observed_requests[0]["capital_amount"] == 100000.0


def test_execute_stage_normalizes_user_facing_strategy_type_aliases() -> None:
    tool = StubBacktestTool(
        responses=[
            {
                "success": True,
                "payload": {"total_return": 0.14, "benchmark_return": 0.09},
                "error_type": None,
                "error_message": None,
                "retryable": False,
                "capability_context": {},
            },
        ]
    )
    state = RunState.new(current_user_message="Run backtest", recent_thread_history=[])
    state.confirmation_payload = {
        "strategy": {
            "strategy_type": "rsi_threshold",
            "strategy_thesis": "Run the supported RSI preset on Google.",
            "asset_universe": ["GOOGL"],
            "date_range": "past year",
            "entry_logic": "Buy when RSI(14) drops to 30 or below",
            "exit_logic": "Sell when RSI(14) rises to 55 or above",
            "extra_parameters": {
                "indicator": "rsi",
                "indicator_parameters": {
                    "indicator": "rsi",
                    "entry_threshold": 30,
                    "exit_threshold": 55,
                },
            },
        },
        "optional_parameters": {},
    }

    result = execute_stage(state=state, tool=tool, max_retries=1)

    assert result.outcome == "execution_succeeded"
    assert tool.calls[0]["strategy_type"] == "indicator_threshold"
    assert tool.calls[0]["entry_rule"]["threshold"] == 30.0
    assert tool.calls[0]["exit_rule"]["threshold"] == 55.0


def test_execute_stage_promotes_moving_average_crossover_to_signal_strategy() -> None:
    tool = StubBacktestTool(
        responses=[
            {
                "success": True,
                "payload": {"total_return": 0.14, "benchmark_return": 0.09},
                "error_type": None,
                "error_message": None,
                "retryable": False,
                "capability_context": {},
            },
        ]
    )
    state = RunState.new(current_user_message="Run backtest", recent_thread_history=[])
    state.confirmation_payload = {
        "strategy": {
            "strategy_type": "indicator_threshold",
            "strategy_thesis": "Buy Nvidia on a 50/200 moving-average crossover.",
            "asset_universe": ["NVDA"],
            "date_range": "past year",
            "entry_logic": (
                "50-day moving average crosses above the 200-day moving average"
            ),
            "entry_rule": {
                "type": "moving_average_crossover",
                "fast_indicator": "sma",
                "fast_period": 50,
                "slow_indicator": "sma",
                "slow_period": 200,
                "direction": "bullish",
            },
        },
        "optional_parameters": {},
    }

    result = execute_stage(state=state, tool=tool, max_retries=1)

    assert result.outcome == "execution_succeeded"
    assert tool.calls[0]["strategy_type"] == "signal_strategy"
    assert tool.calls[0]["entry_rule"] == {
        "type": "moving_average_crossover",
        "fast_indicator": "sma",
        "fast_period": 50,
        "slow_indicator": "sma",
        "slow_period": 200,
        "direction": "bullish",
    }
    assert tool.calls[0]["exit_rule"] == {
        "type": "moving_average_crossover",
        "fast_indicator": "sma",
        "fast_period": 50,
        "slow_indicator": "sma",
        "slow_period": 200,
        "direction": "bearish",
    }


def test_execute_stage_normalizes_dip_buying_and_canonical_date_range() -> None:
    tool = StubBacktestTool(
        responses=[
            {
                "success": True,
                "payload": {"total_return": 0.14, "benchmark_return": 0.09},
                "error_type": None,
                "error_message": None,
                "retryable": False,
                "capability_context": {},
            },
        ]
    )
    state = RunState.new(current_user_message="Run backtest", recent_thread_history=[])
    state.confirmation_payload = {
        "strategy": {
            "strategy_type": "dip_buying",
            "strategy_thesis": "Buy Apple on RSI-defined dips.",
            "asset_universe": ["AAPL"],
            "date_range": {"start": "2026-02-03", "end": "2026-05-03"},
            "entry_logic": "Buy when RSI <= 30",
            "exit_logic": "Sell when RSI >= 55",
        },
        "optional_parameters": {},
    }

    result = execute_stage(state=state, tool=tool, max_retries=1)

    assert result.outcome == "execution_succeeded"
    assert tool.calls[0]["strategy_type"] == "indicator_threshold"
    assert tool.calls[0]["date_range"] == {
        "start": "2026-02-03",
        "end": "2026-05-03",
    }


def test_execute_stage_resolves_structured_date_range_with_today(
) -> None:
    tool = StubBacktestTool(
        responses=[
            {
                "success": True,
                "payload": {"total_return": 0.14, "benchmark_return": 0.09},
                "error_type": None,
                "error_message": None,
                "retryable": False,
                "capability_context": {},
            },
        ]
    )
    state = RunState.new(current_user_message="Run backtest", recent_thread_history=[])
    state.confirmation_payload = {
        "strategy": {
            "strategy_type": "buy_and_hold",
            "strategy_thesis": "Buy and hold Bitcoin from January 1 last year to date.",
            "asset_universe": ["BTC"],
            "asset_class": "crypto",
            "date_range": {"start": "2025-01-01", "end": "today"},
        },
        "optional_parameters": {},
    }

    result = execute_stage(state=state, tool=tool, max_retries=1)

    assert result.outcome == "execution_succeeded"
    assert tool.calls[0]["date_range"] == {
        "start": "2025-01-01",
        "end": date.today().isoformat(),
    }


def test_execute_stage_uses_strategy_contribution_for_dca() -> None:
    tool = StubBacktestTool(
        responses=[
            {
                "success": True,
                "payload": {"total_return": 0.14, "benchmark_return": 0.09},
                "error_type": None,
                "error_message": None,
                "retryable": False,
                "capability_context": {},
            },
        ]
    )
    state = RunState.new(current_user_message="Run backtest", recent_thread_history=[])
    state.confirmation_payload = {
        "strategy": {
            "strategy_type": "dca_accumulation",
            "strategy_thesis": "Invest $500 in Bitcoin every month since 2021.",
            "asset_universe": ["BTC"],
            "asset_class": "crypto",
            "date_range": {"start": "2021-01-01", "end": date.today().isoformat()},
            "cadence": "monthly",
            "capital_amount": 500,
            "sizing_mode": "capital_amount",
        },
        "optional_parameters": {
            "initial_capital": {"value": 1000, "source": "default"},
            "timeframe": {"value": "1D", "source": "default"},
        },
    }

    result = execute_stage(state=state, tool=tool, max_retries=1)

    assert result.outcome == "execution_succeeded"
    assert tool.calls[0]["strategy_type"] == "dca_accumulation"
    assert tool.calls[0]["capital_amount"] == 500
    assert tool.calls[0]["cadence"] == "monthly"
    assert tool.calls[0]["date_range"] == {
        "start": "2021-01-01",
        "end": date.today().isoformat(),
    }


class RetryApprovalInterpreter:
    async def ainvoke(self, request: InterpretationRequest) -> StructuredInterpretation:
        return StructuredInterpretation(
            intent="backtest_execution",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User approved retrying the failed action.",
            candidate_strategy_draft=StrategySummary(),
            semantic_turn_act="retry_failed_action",
        )


@pytest.mark.asyncio
async def test_workflow_rebuilds_failed_action_retry_as_confirmation() -> None:
    tool = StubBacktestTool(
        responses=[
            {
                "success": False,
                "error_type": "upstream_dependency_error",
                "error_message": "market_data_unavailable",
                "retryable": True,
                "payload": None,
                "capability_context": {},
            },
        ]
    )
    workflow = build_workflow(
        structured_interpreter=RetryApprovalInterpreter(),
        tool=tool,
        max_retries=1,
        checkpointer=MemorySaver(),
    )
    launch_payload = {
        "strategy_type": "buy_and_hold",
        "symbol": "MSFT",
        "symbols": ["MSFT"],
        "timeframe": "1D",
        "date_range": {"start": "2025-05-13", "end": "2026-05-13"},
        "sizing_mode": "capital_amount",
        "capital_amount": 1000,
        "benchmark_symbol": "SPY",
        "language": "en",
    }

    result = await run_agent_turn(
        workflow=workflow,
        user=UserState(user_id="u1", language_preference="en"),
        thread_id="thread-retry-failed-action",
        message="Can you try again?",
        fallback_latest_task_snapshot={
            "latest_failed_action_reference": {
                "artifact_kind": "failed_action",
                "artifact_id": "failed-action-1",
                "artifact_status": "failed",
                "metadata": {
                    "action_type": "run_backtest",
                    "launch_payload": launch_payload,
                    "failure_classification": "upstream_dependency_error",
                    "error": "market_data_unavailable",
                    "retryable": True,
                },
            }
        },
    )

    assert result["stage_outcome"] == "await_approval"
    assert tool.calls == []
    confirmation_payload = result["confirmation_payload"]
    launch = confirmation_payload["launch_payload"]
    assert launch["symbol"] == "MSFT"
    assert launch["date_range"] == {"start": "2025-05-13", "end": "2026-05-13"}
    state_snapshot = await workflow.aget_state(
        {"configurable": {"thread_id": "thread-retry-failed-action"}}
    )
    snapshot = state_snapshot.values["latest_task_snapshot"]
    active_confirmation = snapshot.active_confirmation_reference
    assert active_confirmation is not None
    assert active_confirmation.artifact_kind == "confirmation"
    assert snapshot.latest_failed_action_reference is None


def test_execute_stage_translates_provider_window_limit_to_human_recovery() -> None:
    tool = StubBacktestTool(
        responses=[
            {
                "success": False,
                "error_type": "parameter_validation_error",
                "error_message": "kraken_ohlc_window_exceeded",
                "retryable": False,
                "payload": None,
                "capability_context": {},
            },
        ]
    )
    state = RunState.new(current_user_message="Run backtest", recent_thread_history=[])
    state.confirmation_payload = {
        "strategy": {
            "strategy_type": "buy_and_hold",
            "strategy_thesis": "Buy and hold Apple from 2020 to 2024.",
            "asset_universe": ["AAPL"],
            "date_range": {"start": "2020-02-07", "end": "2024-02-07"},
        },
        "optional_parameters": {},
    }

    result = execute_stage(state=state, tool=tool, max_retries=1)

    assert result.outcome == "execution_failed_terminally"
    prompt = result.patch["assistant_prompt"]
    assert "kraken_ohlc_window_exceeded" not in prompt
    assert "Kraken" not in prompt
    assert "provider" not in prompt.lower()
    assert "720" not in prompt
    assert "shorter window" in prompt
    assert "1h" in prompt


def test_execute_maps_unknown_tool_errors_into_runtime_taxonomy() -> None:
    tool = StubBacktestTool(
        responses=[
            {
                "success": False,
                "error_type": "worker_crashed",
                "error_message": "worker stopped unexpectedly",
                "retryable": False,
                "payload": None,
                "capability_context": {},
            },
        ]
    )
    state = RunState.new(current_user_message="run it", recent_thread_history=[])
    state.confirmation_payload = {"strategy": {"asset_universe": ["TSLA"]}}

    result = execute_stage(state=state, tool=tool, max_retries=2)

    assert result.outcome == "execution_failed_terminally"
    assert result.patch["failure_classification"] == "tool_execution_error"
    assert "worker stopped unexpectedly" not in result.patch["assistant_prompt"]
    assert "worker stopped unexpectedly" not in result.patch["final_response_payload"]["error"]
    assert "backtest could not complete" in result.patch["assistant_prompt"]


def test_explain_stage_uses_result_payload_without_fabricating() -> None:
    state = RunState.new(current_user_message="why", recent_thread_history=[])
    state.effective_response_profile = ResponseProfile(
        effective_tone="concise",
        effective_verbosity="low",
        effective_expertise_mode="advanced",
    )
    state.confirmation_payload = {
        "strategy": {"strategy_thesis": "Buy Tesla on pullbacks"},
        "optional_parameters": {
            "initial_capital": {"label": "Initial capital", "source": "default"},
        },
    }
    state.final_response_payload = {
        "result": {"total_return": 0.14, "benchmark_return": 0.09}
    }

    result = explain_stage(state=state)

    assert result.outcome == "ready_to_respond"
    assert "14.0%" in result.patch["assistant_response"]
    assert "9.0%" in result.patch["assistant_response"]
    assert "Buy Tesla on pullbacks" in result.patch["assistant_response"]
    assert "return comparison only" in result.patch["assistant_response"]
    assert "Keep in mind:" in result.patch["assistant_response"]
    assert "Defaults: Initial capital." in result.patch["assistant_response"]
    assert "same period" not in result.patch["assistant_response"].lower()
    assert "because" not in result.patch["assistant_response"].lower()


def test_explain_stage_reports_incomplete_result_payload_without_inventing_numbers() -> (
    None
):
    state = RunState.new(current_user_message="why", recent_thread_history=[])
    state.effective_response_profile = ResponseProfile(
        effective_tone="concise",
        effective_verbosity="medium",
        effective_expertise_mode="advanced",
    )
    state.confirmation_payload = {
        "strategy": {"strategy_thesis": "Buy Tesla on pullbacks"},
        "optional_parameters": {
            "initial_capital": {"label": "Initial capital", "source": "default"},
        },
    }
    state.final_response_payload = {
        "result": {"total_return": None, "benchmark_return": "not-a-number"}
    }

    result = explain_stage(state=state)

    assert result.outcome == "ready_to_respond"
    assert "incomplete" in result.patch["assistant_response"].lower()
    assert (
        "cannot report observed returns yet" in result.patch["assistant_response"].lower()
    )
    assert "0.0%" not in result.patch["assistant_response"]


def test_explain_stage_uses_execution_envelope_context() -> None:
    state = RunState.new(current_user_message="why", recent_thread_history=[])
    state.effective_response_profile = ResponseProfile(
        effective_tone="friendly",
        effective_verbosity="medium",
        effective_expertise_mode="beginner",
    )
    state.confirmation_payload = {
        "strategy": {"strategy_thesis": "Buy and hold Tesla over the last year"},
        "optional_parameters": {
            "initial_capital": {
                "label": "Initial capital",
                "source": "default",
            },
        },
    }
    state.final_response_payload = {
        "result": {
            "execution_status": "succeeded",
            "metrics": {"aggregate": {"performance": {"total_return_pct": 12.5}}},
        },
        "result_card": {"title": "TSLA Buy and Hold"},
        "explanation_context": {
            "metrics": {"aggregate": {"performance": {"total_return_pct": 12.5}}},
            "benchmark_metrics": {"aggregate": {"total_return_pct": 9.2}},
            "assumptions": ["Starting capital: $10,000."],
            "caveats": ["1D bars only."],
            "strategy_type": "buy_and_hold",
        },
    }

    result = explain_stage(state=state)

    assert result.outcome == "ready_to_respond"
    assert "12.5%" in result.patch["assistant_response"]
    assert "9.2%" in result.patch["assistant_response"]
    assert "Starting capital: $10,000." in result.patch["assistant_response"]
    assert "Daily data only." in result.patch["assistant_response"]
    assert "1D bars only." not in result.patch["assistant_response"]


def test_explain_stage_describes_canonical_run_not_stale_original_thesis() -> None:
    state = RunState.new(current_user_message="run backtest", recent_thread_history=[])
    state.effective_response_profile = ResponseProfile(
        effective_tone="friendly",
        effective_verbosity="medium",
        effective_expertise_mode="beginner",
    )
    state.confirmation_payload = {
        "strategy": {
            "strategy_type": "buy_and_hold",
            "strategy_thesis": "Test buying and holding Apple over the past year.",
            "asset_universe": ["NVDA"],
            "asset_class": "equity",
            "date_range": "past 6 months",
        },
        "optional_parameters": {
            "initial_capital": {
                "label": "Initial capital",
                "source": "default",
                "value": 1000.0,
            },
        },
    }
    state.final_response_payload = {
        "result": {
            "total_return": 0.139,
            "benchmark_return": 0.08,
            "comparable_same_period": False,
        },
        "result_card": {
            "title": "NVDA Buy and Hold",
            "date_range": {
                "start": "2025-11-12",
                "end": "2026-05-12",
                "display": "November 12, 2025 to May 12, 2026",
            },
        },
        "explanation_context": {
            "strategy_type": "buy_and_hold",
            "assumptions": ["Starting capital: $1,000.", "Benchmark: SPY."],
        },
    }

    result = explain_stage(state=state)
    text = result.patch["assistant_response"]

    assert "NVDA buy and hold over past 6 months" in text
    assert "Apple" not in text
    assert "past year" not in text
    assert "I tested:" not in text


def test_explain_stage_mentions_flat_signal_result_when_no_trades_executed() -> None:
    state = RunState.new(current_user_message="run it", recent_thread_history=[])
    state.effective_response_profile = ResponseProfile(
        effective_tone="friendly",
        effective_verbosity="medium",
        effective_expertise_mode="beginner",
    )
    state.confirmation_payload = {
        "strategy": {
            "strategy_type": "indicator_threshold",
            "strategy_thesis": "Test TSLA with RSI thresholds.",
            "asset_universe": ["TSLA"],
            "asset_class": "equity",
            "date_range": "last 3 months",
            "entry_logic": "Buy when RSI(14) drops to 20 or below",
            "exit_logic": "Sell when RSI(14) rises to 60 or above",
        },
        "optional_parameters": {
            "initial_capital": {
                "label": "Initial capital",
                "source": "default",
                "value": 1000.0,
            },
        },
    }
    state.final_response_payload = {
        "result": {
            "resolved_strategy": {"strategy_type": "indicator_threshold"},
            "metrics": {
                "aggregate": {
                    "performance": {
                        "total_return_pct": 0.0,
                        "benchmark_return_pct": 8.9,
                    },
                    "efficiency": {"total_trades": 0},
                }
            },
            "benchmark_metrics": {"aggregate": {"total_return_pct": 8.9}},
        },
        "explanation_context": {
            "strategy_type": "indicator_threshold",
            "metrics": {
                "aggregate": {
                    "performance": {
                        "total_return_pct": 0.0,
                        "benchmark_return_pct": 8.9,
                    },
                    "efficiency": {"total_trades": 0},
                }
            },
            "benchmark_metrics": {"aggregate": {"total_return_pct": 8.9}},
            "assumptions": ["Starting capital: $1,000.", "Benchmark: SPY."],
        },
    }

    result = explain_stage(state=state)
    text = result.patch["assistant_response"]

    assert "returned 0.0%" in text
    assert "no position was opened" in text
    assert "Next check" in text
    assert "stayed in cash" in text


def test_explain_stage_varies_with_profile_and_includes_caveats() -> None:
    state = RunState.new(current_user_message="why", recent_thread_history=[])
    state.effective_response_profile = ResponseProfile(
        effective_tone="friendly",
        effective_verbosity="high",
        effective_expertise_mode="beginner",
    )
    state.confirmation_payload = {
        "strategy": {"strategy_thesis": "Test a Tesla pullback idea"},
        "optional_parameters": {
            "initial_capital": {"label": "Initial capital", "source": "default"},
            "timeframe": {"label": "Timeframe", "source": "user"},
        },
    }
    state.final_response_payload = {
        "result": {"total_return": 0.14, "benchmark_return": 0.09}
    }

    result = explain_stage(state=state)
    response = result.patch["assistant_response"]

    assert result.outcome == "ready_to_respond"
    assert response.startswith("The strategy returned 14.0%")
    assert (
        "Tested: the confirmed strategy: Test a Tesla pullback idea."
        in response
    )
    assert "Defaults: Initial capital." in response
    assert "User-set options: Timeframe." in response
    assert "return comparison, not causal attribution" in response


def test_explain_stage_spanish_fallback_does_not_render_language_heading() -> None:
    state = RunState.new(current_user_message="por que", recent_thread_history=[])
    state.effective_response_profile = ResponseProfile(
        effective_tone="friendly",
        effective_verbosity="medium",
        effective_expertise_mode="beginner",
    )
    state.confirmation_payload = {
        "strategy": {
            "strategy_type": "buy_and_hold",
            "strategy_thesis": "Probar compra y mantener ETH",
            "asset_universe": ["ETH"],
            "date_range": {"start": "2024-01-01", "end": "2024-03-31"},
        },
        "optional_parameters": {
            "initial_capital": {"label": "Initial capital", "source": "default"},
            "timeframe": {"label": "Timeframe", "source": "user"},
        },
    }
    state.final_response_payload = {
        "result": {
            "total_return": 0.551,
            "benchmark_return": 0.614,
            "benchmark_symbol": "BTC",
        }
    }

    result = explain_stage(state=state, language="es-419")

    assert result.patch["assistant_response"].startswith("The strategy returned")
    assert not result.patch["assistant_response"].startswith("**Resumen rápido**")
    assert not result.patch["assistant_response"].startswith("**Quick take**")
    assert "- Tested: ETH buy and hold" in result.patch["assistant_response"]
    assert "1 de enero de 2024 al 31 de marzo de 2024" in result.patch[
        "assistant_response"
    ]
    assert "Defaults: capital inicial." in result.patch["assistant_response"]
    assert "User-set options: temporalidad." in result.patch["assistant_response"]
    assert "Initial capital" not in result.patch["assistant_response"]
    assert "Timeframe" not in result.patch["assistant_response"]


@pytest.mark.asyncio
async def test_explain_stage_async_validates_next_checks_without_rendering_them(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import explain as explain_module

    captured: dict[str, object] = {}

    async def fake_quick_take_plan(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {
            "relative_performance_claim": "lagged_benchmark",
            "takeaway": "The TSLA test Lagged by 87.8 percentage points against SPY, so the signal needs a tighter follow-up.",
            "tested_bullet": "Tested TSLA with the confirmed crossover over the supplied window.",
            "meaning_bullet": "The comparison is useful evidence, not a verdict.",
            "next_check_bullet": "Next check: adjust the signal periods.",
            "assumption_bullet": None,
            "caveat_bullet": "Historical simulation only.",
            "next_experiment_option_kinds": ["adjust_signal_periods"],
            "fact_ids": [
                "tested_summary",
                "total_return",
                "benchmark_return",
                "benchmark_symbol",
                "benchmark_comparison",
                "caveat",
            ],
        }

    monkeypatch.setattr(
        explain_module,
        "invoke_openrouter_json_schema",
        fake_quick_take_plan,
    )
    state = RunState.new(current_user_message="why", recent_thread_history=[])
    state.confirmation_payload = {
        "strategy": {
            "strategy_type": "signal_strategy",
            "strategy_thesis": "Test TSLA with a 50/200 crossover",
            "asset_universe": ["TSLA"],
            "date_range": {"start": "2022-01-01", "end": "2026-05-20"},
        },
        "optional_parameters": {},
    }
    state.final_response_payload = {
        "result": {
            "total_return": -0.326,
            "benchmark_return": 0.552,
            "benchmark_symbol": "SPY",
        }
    }

    result = await explain_stage_async(state=state)

    assert result.stage_patch["assistant_response"].startswith("The TSLA test")
    assert "adjust the signal periods" not in result.stage_patch["assistant_response"]
    assert "Next check" not in result.stage_patch["assistant_response"]
    assert result.stage_patch["assistant_response_source"] == "llm_explain_stage"
    assert result.stage_patch["assistant_response_fallback_used"] is False
    messages = captured["messages"]
    assert isinstance(messages, list)
    system_prompt = messages[0]["content"]
    assert "supported next experiment kinds" in system_prompt
    context = json.loads(messages[1]["content"])
    allowed_kinds = {
        option["kind"] for option in context["allowed_next_experiments"]
    }
    assert "adjust_signal_periods" in allowed_kinds
    assert "trend_filter" not in allowed_kinds
    assert "volatility_stop" not in allowed_kinds
    assert captured["schema_model"] is explain_module.QuickTakeDraft


@pytest.mark.asyncio
async def test_explain_stage_async_composes_spanish_quick_take_without_heading(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import explain as explain_module

    captured: dict[str, object] = {}

    async def fake_quick_take_plan(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {
            "relative_performance_claim": "lagged_benchmark",
            "takeaway": "ETH rindió +55.1%, pero quedó 6.3 puntos porcentuales detrás de BTC.",
            "tested_bullet": "Se probó comprar y mantener ETH en la ventana solicitada.",
            "meaning_bullet": "La comparación sirve como evidencia histórica, no como predicción.",
            "next_check_bullet": None,
            "assumption_bullet": None,
            "caveat_bullet": "Simulación histórica solamente.",
            "next_experiment_option_kinds": [],
            "fact_ids": [
                "tested_summary",
                "total_return",
                "benchmark_return",
                "benchmark_symbol",
                "benchmark_comparison",
                "caveat",
            ],
        }

    monkeypatch.setattr(
        explain_module,
        "invoke_openrouter_json_schema",
        fake_quick_take_plan,
    )
    state = RunState.new(current_user_message="por que", recent_thread_history=[])
    state.confirmation_payload = {
        "strategy": {
            "strategy_type": "buy_and_hold",
            "strategy_thesis": "Comprar y mantener ETH",
            "asset_universe": ["ETH"],
            "date_range": {"start": "2024-01-01", "end": "2024-03-31"},
        },
        "optional_parameters": {},
    }
    state.final_response_payload = {
        "result": {
            "total_return": 0.551,
            "benchmark_return": 0.614,
            "benchmark_symbol": "BTC",
        }
    }

    result = await explain_stage_async(state=state, language="es-419")

    assert result.stage_patch["assistant_response"].startswith("ETH rindió +55.1%")
    assert not result.stage_patch["assistant_response"].startswith("**Resumen rápido**")
    assert not result.stage_patch["assistant_response"].startswith("**Quick take**")
    assert "Se probó comprar y mantener ETH" in result.stage_patch[
        "assistant_response"
    ]
    assert result.stage_patch["assistant_response_source"] == "llm_explain_stage"
    messages = captured["messages"]
    assert isinstance(messages, list)
    assert "Answer in Spanish" in messages[0]["content"]
    context = json.loads(messages[1]["content"])
    assert context["language"] == "es-419"
    assert context["fact_bank"]["tested_summary"].startswith(
        "ETH buy and hold over 1 de enero de 2024"
    )
    assert "2024-01-01 to 2024-03-31" not in context["fact_bank"]["tested_summary"]


@pytest.mark.asyncio
async def test_explain_stage_async_drops_mixed_language_optional_spanish_quick_take(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import explain as explain_module

    async def fake_quick_take_plan(**_: object) -> dict[str, object]:
        return {
            "relative_performance_claim": "beat_benchmark",
            "takeaway": (
                "Comprar y mantener AAPL superó al benchmark SPY por "
                "23.6 puntos porcentuales."
            ),
            "tested_bullet": "total return for $AAPL",
            "meaning_bullet": "La comparación muestra total return, no una predicción.",
            "next_check_bullet": None,
            "assumption_bullet": None,
            "caveat_bullet": "Simulación histórica solamente.",
            "language_quality": "mixed_or_wrong_language",
            "next_experiment_option_kinds": [],
            "fact_ids": [
                "tested_summary",
                "total_return",
                "benchmark_return",
                "benchmark_symbol",
                "benchmark_comparison",
                "caveat",
            ],
        }

    monkeypatch.setattr(
        explain_module,
        "invoke_openrouter_json_schema",
        fake_quick_take_plan,
    )
    state = RunState.new(current_user_message="por que", recent_thread_history=[])
    state.confirmation_payload = {
        "strategy": {
            "strategy_type": "buy_and_hold",
            "strategy_thesis": "Comprar y mantener AAPL",
            "asset_universe": ["AAPL"],
            "date_range": {"start": "2025-06-14", "end": "2026-06-12"},
        },
        "optional_parameters": {},
    }
    state.final_response_payload = {
        "result": {
            "total_return": 0.467,
            "benchmark_return": 0.231,
            "benchmark_symbol": "SPY",
        }
    }

    result = await explain_stage_async(state=state, language="es-419")
    response = result.stage_patch["assistant_response"]

    assert response.startswith("Comprar y mantener AAPL")
    assert not response.startswith("**Resumen rápido**")
    assert not response.startswith("**Quick take**")
    assert "total return for" not in response
    assert "Simulación histórica solamente" not in response
    assert result.stage_patch["assistant_response_source"] == "llm_explain_stage"
    assert result.stage_patch["assistant_response_fallback_used"] is False


@pytest.mark.asyncio
async def test_explain_stage_async_renders_spanish_setup_from_canonical_facts(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import explain as explain_module

    captured: dict[str, object] = {}

    async def fake_quick_take_plan(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {
            "relative_performance_claim": "beat_benchmark",
            "takeaway": (
                "AAPL rindió +46.7%, superando a SPY por 23.6 puntos porcentuales."
            ),
            "tested_bullet": "Se probó comprar y mantener AAPL en la ventana confirmada.",
            "meaning_bullet": "La comparación sirve como evidencia histórica.",
            "next_check_bullet": None,
            "assumption_bullet": None,
            "caveat_bullet": "Simulación histórica solamente.",
            "language_quality": "matches_prompt_language",
            "next_experiment_option_kinds": [],
            "fact_ids": [
                "tested_summary",
                "rule_summary",
                "total_return",
                "benchmark_return",
                "benchmark_symbol",
                "benchmark_comparison",
                "caveat",
            ],
        }

    monkeypatch.setattr(
        explain_module,
        "invoke_openrouter_json_schema",
        fake_quick_take_plan,
    )
    state = RunState.new(current_user_message="por que", recent_thread_history=[])
    state.confirmation_payload = {
        "strategy": {
            "strategy_type": "buy_and_hold",
            "strategy_thesis": "Comprar y mantener AAPL",
            "asset_universe": ["AAPL"],
            "date_range": {"start": "2025-06-14", "end": "2026-06-12"},
        },
        "optional_parameters": {},
    }
    state.final_response_payload = {
        "result": {
            "total_return": 0.467,
            "benchmark_return": 0.231,
            "benchmark_symbol": "SPY",
        }
    }

    result = await explain_stage_async(state=state, language="es-419")
    response = result.stage_patch["assistant_response"]
    messages = captured["messages"]
    assert isinstance(messages, list)
    context = json.loads(messages[1]["content"])

    assert context["fact_bank"]["rule_summary"].startswith("Rule:")
    assert "Entry rule" not in response
    assert "benchmark SPY" not in response
    assert "superando a SPY por 23.6 puntos porcentuales" in response
    assert "Se probó comprar y mantener AAPL" in response
    assert result.stage_patch["assistant_response_source"] == "llm_explain_stage"
    assert result.stage_patch["assistant_response_fallback_used"] is False


@pytest.mark.asyncio
async def test_explain_stage_async_accepts_spanish_decimal_comma_benchmark_gap(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import explain as explain_module

    async def fake_quick_take_plan(**_: object) -> dict[str, object]:
        return {
            "relative_performance_claim": "lagged_benchmark",
            "takeaway": (
                "AAPL y MSFT rindieron 13,6% mientras SPY rindió 16,6%; "
                "quedaron por debajo por 3,1 puntos porcentuales."
            ),
            "tested_bullet": (
                "Se probó comprar y mantener AAPL y MSFT en la ventana confirmada."
            ),
            "meaning_bullet": "La comparación nombra SPY y la brecha frente a la referencia.",
            "next_check_bullet": None,
            "assumption_bullet": None,
            "caveat_bullet": "Simulación histórica solamente.",
            "language_quality": "matches_prompt_language",
            "next_experiment_option_kinds": [],
            "fact_ids": [
                "tested_summary",
                "total_return",
                "benchmark_return",
                "benchmark_comparison",
                "benchmark_symbol",
                "caveat",
            ],
        }

    monkeypatch.setattr(
        explain_module,
        "invoke_openrouter_json_schema",
        fake_quick_take_plan,
    )
    state = RunState.new(current_user_message="por que", recent_thread_history=[])
    state.confirmation_payload = {
        "strategy": {
            "strategy_type": "buy_and_hold",
            "asset_universe": ["AAPL", "MSFT"],
            "date_range": {"start": "2025-01-01", "end": "2026-06-05"},
        },
        "optional_parameters": {},
    }
    state.final_response_payload = {
        "result": {"total_return": 0.1356, "benchmark_return": 0.1663},
        "explanation_context": {"benchmark_symbol": "SPY"},
    }

    result = await explain_stage_async(state=state, language="es-419")
    response = result.stage_patch["assistant_response"]

    assert response.startswith("AAPL y MSFT rindieron")
    assert "SPY" in response
    assert "puntos porcentuales" in response
    assert result.stage_patch["assistant_response_source"] == "llm_explain_stage"
    assert result.stage_patch["assistant_response_fallback_used"] is False


@pytest.mark.asyncio
async def test_explain_stage_async_sends_benchmark_contract_for_grounded_comparison(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import explain as explain_module

    captured: dict[str, object] = {}

    async def fake_quick_take_plan(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {
            "relative_performance_claim": "lagged_benchmark",
            "takeaway": "TSLA lagged SPY in this historical test.",
            "tested_bullet": "Tested the confirmed TSLA crossover setup.",
            "meaning_bullet": "SPY is the benchmark comparison, not another tested asset.",
            "next_check_bullet": None,
            "assumption_bullet": None,
            "caveat_bullet": "Historical simulation only.",
            "next_experiment_option_kinds": [],
            "fact_ids": [
                "tested_summary",
                "total_return",
                "benchmark_return",
                "benchmark_comparison",
                "benchmark_symbol",
                "caveat",
            ],
        }

    monkeypatch.setattr(
        explain_module,
        "invoke_openrouter_json_schema",
        fake_quick_take_plan,
    )
    state = RunState.new(current_user_message="why", recent_thread_history=[])
    state.confirmation_payload = {
        "strategy": {
            "strategy_type": "signal_strategy",
            "strategy_thesis": "Test TSLA with a 50/200 crossover",
            "asset_universe": ["TSLA"],
            "date_range": {"start": "2022-01-01", "end": "2026-05-20"},
        },
        "optional_parameters": {},
    }
    state.final_response_payload = {
        "result": {"total_return": -0.326, "benchmark_return": 0.552},
        "explanation_context": {
            "benchmark_symbol": "SPY",
            "result_card": {
                "benchmark_symbol": "SPY",
                "context_packet_ids": ["packet-1"],
            },
        },
    }

    await explain_stage_async(state=state)

    messages = captured["messages"]
    assert isinstance(messages, list)
    system_prompt = messages[0]["content"]
    assert "Benchmark returns belong only to" in system_prompt
    context = json.loads(messages[1]["content"])
    assert context["benchmark_contract"] == {
        "benchmark_symbol": "SPY",
        "tested_symbols": ["TSLA"],
        "benchmark_is_tested_asset": False,
    }
    assert context["fact_bank"]["benchmark_comparison"] == (
        "Lagged by 87.8 percentage points"
    )
    assert context["fact_bank"]["benchmark_delta_magnitude"] == (
        "87.8 percentage points"
    )
    assert captured["context_packet_ids"] == ["packet-1"]


@pytest.mark.asyncio
async def test_explain_stage_async_renders_quick_take_from_canonical_facts(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import explain as explain_module

    async def fake_quick_take_plan(**_: object) -> dict[str, object]:
        return {
            "relative_performance_claim": "beat_benchmark",
            "takeaway": "AAPL beat QQQ by 8.1 percentage points in this historical test.",
            "tested_bullet": "Tested AAPL buy and hold over the confirmed 2024 window.",
            "meaning_bullet": "AAPL returned 35.0%, while QQQ returned 26.9%.",
            "next_check_bullet": None,
            "assumption_bullet": None,
            "caveat_bullet": "Historical simulation only.",
            "next_experiment_option_kinds": [],
            "fact_ids": [
                "tested_summary",
                "total_return",
                "benchmark_return",
                "benchmark_comparison",
                "benchmark_symbol",
                "caveat",
            ],
        }

    monkeypatch.setattr(
        explain_module,
        "invoke_openrouter_json_schema",
        fake_quick_take_plan,
    )
    state = RunState.new(current_user_message="why", recent_thread_history=[])
    state.confirmation_payload = {
        "strategy": {
            "strategy_type": "buy_and_hold",
            "strategy_thesis": "AAPL buy and hold against QQQ.",
            "asset_universe": ["AAPL"],
            "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
        },
        "optional_parameters": {},
    }
    state.final_response_payload = {
        "result": {"total_return": 0.35, "benchmark_return": 0.269},
        "explanation_context": {
            "benchmark_symbol": "QQQ",
            "result_card": {
                "benchmark_symbol": "QQQ",
                "rows": [
                    {
                        "key": "cash_value",
                        "label": "Ending value",
                        "value": "$1.0k -> $1.4k",
                    }
                ],
            },
        },
    }

    result = await explain_stage_async(state=state)
    response = result.stage_patch["assistant_response"]

    assert "$1,350" not in response
    assert "35.0%" in response
    assert "26.9%" in response
    assert "8.1 percentage points" in response


@pytest.mark.asyncio
async def test_explain_stage_async_rejects_mismatched_quick_take_return_values(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import explain as explain_module

    async def fake_quick_take_plan(**_: object) -> dict[str, object]:
        return {
            "relative_performance_claim": "beat_benchmark",
            "takeaway": "AAPL beat QQQ by 8.1 percentage points in this historical test.",
            "tested_bullet": "Tested AAPL buy and hold over the confirmed 2024 window.",
            "meaning_bullet": "AAPL returned +46.7%, while QQQ returned +38.6%.",
            "next_check_bullet": None,
            "assumption_bullet": None,
            "caveat_bullet": "Historical simulation only.",
            "next_experiment_option_kinds": [],
            "fact_ids": [
                "tested_summary",
                "total_return",
                "benchmark_return",
                "benchmark_comparison",
                "benchmark_symbol",
                "caveat",
            ],
        }

    monkeypatch.setattr(
        explain_module,
        "invoke_openrouter_json_schema",
        fake_quick_take_plan,
    )
    state = RunState.new(current_user_message="why", recent_thread_history=[])
    state.confirmation_payload = {
        "strategy": {
            "strategy_type": "buy_and_hold",
            "strategy_thesis": "AAPL buy and hold against QQQ.",
            "asset_universe": ["AAPL"],
            "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
        },
        "optional_parameters": {},
    }
    state.final_response_payload = {
        "result": {"total_return": 0.35, "benchmark_return": 0.269},
        "explanation_context": {"benchmark_symbol": "QQQ"},
    }

    result = await explain_stage_async(state=state)
    response = result.stage_patch["assistant_response"]

    assert result.stage_patch["assistant_response_fallback_used"] is True
    assert "46.7%" not in response
    assert "38.6%" not in response
    assert "35.0%" in response
    assert "26.9%" in response


@pytest.mark.asyncio
async def test_explain_stage_async_ignores_unknown_optional_fact_ids_after_required_facts(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import explain as explain_module

    async def fake_quick_take_plan(**_: object) -> dict[str, object]:
        return {
            "relative_performance_claim": "beat_benchmark",
            "takeaway": "AAPL beat QQQ by 8.1 percentage points in this historical test.",
            "tested_bullet": "Tested AAPL buy and hold over the confirmed 2024 window.",
            "meaning_bullet": "Optional metadata noise should not erase this grounded take.",
            "next_check_bullet": None,
            "assumption_bullet": None,
            "caveat_bullet": "Historical simulation only.",
            "next_experiment_option_kinds": [],
            "fact_ids": [
                "tested_summary",
                "total_return",
                "benchmark_return",
                "benchmark_comparison",
                "benchmark_symbol",
                "caveat",
                "optional_style_note",
            ],
        }

    monkeypatch.setattr(
        explain_module,
        "invoke_openrouter_json_schema",
        fake_quick_take_plan,
    )
    state = RunState.new(current_user_message="why", recent_thread_history=[])
    state.confirmation_payload = {
        "strategy": {
            "strategy_type": "buy_and_hold",
            "strategy_thesis": "AAPL buy and hold against QQQ.",
            "asset_universe": ["AAPL"],
            "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
        },
        "optional_parameters": {},
    }
    state.final_response_payload = {
        "result": {"total_return": 0.35, "benchmark_return": 0.269},
        "explanation_context": {"benchmark_symbol": "QQQ"},
    }

    result = await explain_stage_async(state=state)
    response = result.stage_patch["assistant_response"]

    assert "metadata noise should not erase this grounded take" in response


@pytest.mark.asyncio
async def test_explain_stage_async_accepts_natural_benchmark_gap_wording(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import explain as explain_module

    async def fake_quick_take_plan(**_: object) -> dict[str, object]:
        return {
            "relative_performance_claim": "lagged_benchmark",
            "takeaway": "AAPL trailed QQQ by 5.3 percentage points in this historical test.",
            "tested_bullet": "Tested AAPL buy and hold over the confirmed window.",
            "meaning_bullet": "The benchmark comparison is still visible without template wording.",
            "next_check_bullet": None,
            "assumption_bullet": None,
            "caveat_bullet": "Historical simulation only.",
            "next_experiment_option_kinds": [],
            "fact_ids": [
                "tested_summary",
                "total_return",
                "benchmark_return",
                "benchmark_comparison",
                "benchmark_symbol",
                "caveat",
            ],
        }

    monkeypatch.setattr(
        explain_module,
        "invoke_openrouter_json_schema",
        fake_quick_take_plan,
    )
    state = RunState.new(current_user_message="why", recent_thread_history=[])
    state.confirmation_payload = {
        "strategy": {
            "strategy_type": "buy_and_hold",
            "strategy_thesis": "AAPL buy and hold against QQQ.",
            "asset_universe": ["AAPL"],
            "date_range": {"start": "2026-01-01", "end": "2026-05-31"},
        },
        "optional_parameters": {},
    }
    state.final_response_payload = {
        "result": {"total_return": 0.151, "benchmark_return": 0.204},
        "explanation_context": {"benchmark_symbol": "QQQ"},
    }

    result = await explain_stage_async(state=state)
    response = result.stage_patch["assistant_response"]

    assert "QQQ" in response
    assert "trailed QQQ by 5.3 percentage points" in response
    assert "template wording" in response


@pytest.mark.asyncio
async def test_explain_stage_async_does_not_reject_grounded_copy_for_missing_fact_id(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import explain as explain_module

    async def fake_quick_take_plan(**_: object) -> dict[str, object]:
        return {
            "relative_performance_claim": "lagged_benchmark",
            "takeaway": (
                "AAPL and MSFT lagged SPY by 13.3 percentage points in this "
                "historical test."
            ),
            "tested_bullet": (
                "Tested AAPL and MSFT buy and hold over the confirmed window."
            ),
            "meaning_bullet": "The result still names SPY and the benchmark gap.",
            "next_check_bullet": None,
            "assumption_bullet": None,
            "caveat_bullet": "Historical simulation only.",
            "next_experiment_option_kinds": [],
            "fact_ids": [
                "tested_summary",
                "total_return",
                "benchmark_comparison",
                "benchmark_symbol",
                "caveat",
            ],
        }

    monkeypatch.setattr(
        explain_module,
        "invoke_openrouter_json_schema",
        fake_quick_take_plan,
    )
    state = RunState.new(current_user_message="why", recent_thread_history=[])
    state.confirmation_payload = {
        "strategy": {
            "strategy_type": "buy_and_hold",
            "asset_universe": ["AAPL", "MSFT"],
            "date_range": {"start": "2025-01-01", "end": "2026-06-05"},
        },
        "optional_parameters": {},
    }
    state.final_response_payload = {
        "result": {"total_return": 0.128, "benchmark_return": 0.261},
        "explanation_context": {"benchmark_symbol": "SPY"},
    }

    result = await explain_stage_async(state=state)
    response = result.stage_patch["assistant_response"]

    assert "SPY" in response
    assert "lagged SPY by 13.3 percentage points" in response
    assert result.stage_patch["assistant_response_source"] == "llm_explain_stage"
    assert result.stage_patch["assistant_response_fallback_used"] is False


@pytest.mark.asyncio
async def test_explain_stage_async_falls_back_when_required_fact_metadata_is_missing(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import explain as explain_module

    async def fake_quick_take_plan(**_: object) -> dict[str, object]:
        return {
            "relative_performance_claim": "lagged_benchmark",
            "takeaway": "The confirmed portfolio trailed the comparison in this test.",
            "tested_bullet": (
                "Tested AAPL and MSFT buy and hold over the confirmed window."
            ),
            "meaning_bullet": "The result is directional evidence, not a verdict.",
            "next_check_bullet": None,
            "assumption_bullet": None,
            "caveat_bullet": "Historical simulation only.",
            "next_experiment_option_kinds": [],
            "fact_ids": [
                "tested_summary",
                "total_return",
                "benchmark_comparison",
                "benchmark_symbol",
                "caveat",
            ],
        }

    monkeypatch.setattr(
        explain_module,
        "invoke_openrouter_json_schema",
        fake_quick_take_plan,
    )
    state = RunState.new(current_user_message="why", recent_thread_history=[])
    state.confirmation_payload = {
        "strategy": {
            "strategy_type": "buy_and_hold",
            "asset_universe": ["AAPL", "MSFT"],
            "date_range": {"start": "2025-01-01", "end": "2026-06-05"},
        },
        "optional_parameters": {},
    }
    state.final_response_payload = {
        "result": {"total_return": 0.1356, "benchmark_return": 0.1663},
        "explanation_context": {"benchmark_symbol": "SPY"},
    }

    result = await explain_stage_async(state=state)
    response = result.stage_patch["assistant_response"]

    assert "SPY" in response
    assert "lagged by 3.1 percentage points" in response
    assert "directional evidence" not in response
    assert result.stage_patch["assistant_response_source"] == "deterministic_fallback"
    assert result.stage_patch["assistant_response_fallback_used"] is True


@pytest.mark.asyncio
async def test_explain_stage_async_accepts_clean_copy_with_wrong_language_self_report(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import explain as explain_module

    async def fake_quick_take_plan(**_: object) -> dict[str, object]:
        return {
            "relative_performance_claim": "lagged_benchmark",
            "takeaway": (
                "A simple buy-and-hold of AAPL and MSFT returned +12.8%. "
                "That lagged SPY by 13.3 percentage points."
            ),
            "tested_bullet": (
                "AAPL, MSFT buy and hold over 2025-01-01 to 2026-06-05"
            ),
            "meaning_bullet": None,
            "next_check_bullet": None,
            "assumption_bullet": None,
            "caveat_bullet": None,
            "language_quality": "mixed_or_wrong_language",
            "next_experiment_option_kinds": [
                "change_date_range",
                "same_setup_peer_asset",
            ],
            "fact_ids": [
                "tested_summary",
                "total_return",
                "benchmark_return",
                "benchmark_comparison",
                "benchmark_symbol",
                "caveat",
            ],
        }

    monkeypatch.setattr(
        explain_module,
        "invoke_openrouter_json_schema",
        fake_quick_take_plan,
    )
    state = RunState.new(current_user_message="why", recent_thread_history=[])
    state.confirmation_payload = {
        "strategy": {
            "strategy_type": "buy_and_hold",
            "asset_universe": ["AAPL", "MSFT"],
            "date_range": {"start": "2025-01-01", "end": "2026-06-05"},
        },
        "optional_parameters": {},
    }
    state.final_response_payload = {
        "result": {"total_return": 0.1284, "benchmark_return": 0.2614},
        "explanation_context": {"benchmark_symbol": "SPY"},
    }

    result = await explain_stage_async(state=state)
    response = result.stage_patch["assistant_response"]

    assert "SPY" in response
    assert "That lagged SPY by 13.3 percentage points" in response
    assert result.stage_patch["assistant_response_source"] == "llm_explain_stage"
    assert result.stage_patch["assistant_response_fallback_used"] is False


@pytest.mark.asyncio
async def test_explain_stage_async_drops_optional_mixed_language_prose_without_fallback(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import explain as explain_module

    async def fake_quick_take_plan(**_: object) -> dict[str, object]:
        return {
            "relative_performance_claim": "lagged_benchmark",
            "takeaway": (
                "AAPL y MSFT rindieron 12.8% mientras SPY rindió 26.1%; "
                "quedaron por debajo por 13.3 puntos porcentuales."
            ),
            "tested_bullet": "total return for AAPL and MSFT",
            "meaning_bullet": "Keep in mind this is historical simulation only.",
            "next_check_bullet": None,
            "assumption_bullet": "Same period benchmark comparison.",
            "caveat_bullet": "Historical simulation only.",
            "language_quality": "mixed_or_wrong_language",
            "next_experiment_option_kinds": [],
            "fact_ids": [
                "tested_summary",
                "total_return",
                "benchmark_return",
                "benchmark_comparison",
                "benchmark_symbol",
                "caveat",
            ],
        }

    monkeypatch.setattr(
        explain_module,
        "invoke_openrouter_json_schema",
        fake_quick_take_plan,
    )
    state = RunState.new(current_user_message="por que", recent_thread_history=[])
    state.confirmation_payload = {
        "strategy": {
            "strategy_type": "buy_and_hold",
            "asset_universe": ["AAPL", "MSFT"],
            "date_range": {"start": "2025-01-01", "end": "2026-06-05"},
        },
        "optional_parameters": {},
    }
    state.final_response_payload = {
        "result": {"total_return": 0.1284, "benchmark_return": 0.2614},
        "explanation_context": {"benchmark_symbol": "SPY"},
    }

    result = await explain_stage_async(state=state, language="es-419")
    response = result.stage_patch["assistant_response"]

    assert response.startswith("AAPL y MSFT rindieron 12.8%")
    assert "Probado:" not in response
    assert "total return for" not in response
    assert "Keep in mind" not in response
    assert "Same period" not in response
    assert "Historical simulation only" not in response
    assert result.stage_patch["assistant_response_source"] == "llm_explain_stage"
    assert result.stage_patch["assistant_response_fallback_used"] is False


def test_explain_stage_quick_take_validation_has_no_language_fragment_blacklist() -> None:
    from argus.agent_runtime.stages import explain as explain_module

    source = inspect.getsource(explain_module)

    assert "english_fragments" not in source
    assert "_quick_take_matches_requested_language" not in source
    assert "import re" not in {line.strip() for line in source.splitlines()}


@pytest.mark.asyncio
async def test_explain_stage_async_accepts_supported_next_experiment_labels(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import explain as explain_module

    async def fake_quick_take_plan(**_: object) -> dict[str, object]:
        return {
            "relative_performance_claim": "lagged_benchmark",
            "takeaway": "AAPL and MSFT lagged SPY by 13.3 percentage points in this historical test.",
            "tested_bullet": "Tested AAPL and MSFT buy and hold over the confirmed window.",
            "meaning_bullet": "The result is grounded in the completed backtest run.",
            "next_check_bullet": "Next check: change the date range.",
            "assumption_bullet": None,
            "caveat_bullet": "Historical simulation only.",
            "next_experiment_option_kinds": ["change the date range"],
            "fact_ids": [
                "tested_summary",
                "total_return",
                "benchmark_return",
                "benchmark_comparison",
                "benchmark_symbol",
                "caveat",
            ],
        }

    monkeypatch.setattr(
        explain_module,
        "invoke_openrouter_json_schema",
        fake_quick_take_plan,
    )
    state = RunState.new(current_user_message="why", recent_thread_history=[])
    state.confirmation_payload = {
        "strategy": {
            "strategy_type": "buy_and_hold",
            "asset_universe": ["AAPL", "MSFT"],
            "date_range": {"start": "2025-01-01", "end": "2026-06-05"},
        },
        "optional_parameters": {},
    }
    state.final_response_payload = {
        "result": {"total_return": 0.128, "benchmark_return": 0.261},
        "explanation_context": {"benchmark_symbol": "SPY"},
    }

    result = await explain_stage_async(state=state)
    response = result.stage_patch["assistant_response"]

    assert "SPY" in response
    assert "lagged SPY by 13.3 percentage points" in response
    assert "change the date range" not in response
    assert "Next check" not in response
    assert result.stage_patch["assistant_response_source"] == "llm_explain_stage"
    assert result.stage_patch["assistant_response_fallback_used"] is False


@pytest.mark.asyncio
async def test_explain_stage_async_ignores_unrendered_next_experiment_kinds(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import explain as explain_module

    async def fake_quick_take_plan(**_: object) -> dict[str, object]:
        return {
            "relative_performance_claim": "lagged_benchmark",
            "takeaway": "AAPL and MSFT lagged SPY by 13.3 percentage points in this historical test.",
            "tested_bullet": "Tested AAPL and MSFT buy and hold over the confirmed window.",
            "meaning_bullet": "The result is grounded in the completed backtest run.",
            "next_check_bullet": "Next check: invent a new private metric.",
            "assumption_bullet": None,
            "caveat_bullet": "Historical simulation only.",
            "next_experiment_option_kinds": ["invent_private_metric"],
            "fact_ids": [
                "tested_summary",
                "total_return",
                "benchmark_return",
                "benchmark_comparison",
                "benchmark_symbol",
                "caveat",
            ],
        }

    monkeypatch.setattr(
        explain_module,
        "invoke_openrouter_json_schema",
        fake_quick_take_plan,
    )
    state = RunState.new(current_user_message="why", recent_thread_history=[])
    state.confirmation_payload = {
        "strategy": {
            "strategy_type": "buy_and_hold",
            "asset_universe": ["AAPL", "MSFT"],
            "date_range": {"start": "2025-01-01", "end": "2026-06-05"},
        },
        "optional_parameters": {},
    }
    state.final_response_payload = {
        "result": {"total_return": 0.128, "benchmark_return": 0.261},
        "explanation_context": {"benchmark_symbol": "SPY"},
    }

    result = await explain_stage_async(state=state)
    response = result.stage_patch["assistant_response"]

    assert "SPY" in response
    assert "lagged SPY by 13.3 percentage points" in response
    assert "invent a new private metric" not in response
    assert result.stage_patch["assistant_response_source"] == "llm_explain_stage"
    assert result.stage_patch["assistant_response_fallback_used"] is False


@pytest.mark.asyncio
async def test_explain_stage_async_replaces_signed_benchmark_delta_takeaway(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import explain as explain_module

    async def fake_quick_take_plan(**_: object) -> dict[str, object]:
        return {
            "relative_performance_claim": "lagged_benchmark",
            "takeaway": (
                "AAPL returned 15.1%, while QQQ returned 20.4% over the same "
                "period, about -5.3 percentage points versus the benchmark."
            ),
            "tested_bullet": "Tested AAPL buy and hold over the confirmed window.",
            "meaning_bullet": None,
            "next_check_bullet": None,
            "assumption_bullet": None,
            "caveat_bullet": "Historical simulation only.",
            "next_experiment_option_kinds": [],
            "fact_ids": [
                "tested_summary",
                "total_return",
                "benchmark_return",
                "benchmark_comparison",
                "benchmark_symbol",
                "caveat",
            ],
        }

    monkeypatch.setattr(
        explain_module,
        "invoke_openrouter_json_schema",
        fake_quick_take_plan,
    )
    state = RunState.new(current_user_message="why", recent_thread_history=[])
    state.confirmation_payload = {
        "strategy": {
            "strategy_type": "buy_and_hold",
            "strategy_thesis": "AAPL buy and hold against QQQ.",
            "asset_universe": ["AAPL"],
            "date_range": {"start": "2026-01-01", "end": "2026-05-31"},
        },
        "optional_parameters": {},
    }
    state.final_response_payload = {
        "result": {"total_return": 0.151, "benchmark_return": 0.204},
        "explanation_context": {"benchmark_symbol": "QQQ"},
    }

    result = await explain_stage_async(state=state)
    response = result.stage_patch["assistant_response"]

    assert "-5.3" not in response
    assert "lagged by 5.3 percentage points" in response
    assert result.stage_patch["assistant_response_source"] == "deterministic_fallback"
    assert result.stage_patch["assistant_response_fallback_used"] is True


@pytest.mark.asyncio
async def test_explain_stage_async_rejects_rendered_signed_benchmark_delta_copy(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import explain as explain_module

    async def fake_quick_take_plan(**_: object) -> dict[str, object]:
        return {
            "relative_performance_claim": "lagged_benchmark",
            "takeaway": "AAPL lagged QQQ by 5.3 percentage points in this historical test.",
            "tested_bullet": "Tested AAPL buy and hold over the confirmed window.",
            "meaning_bullet": "The strategy was -5.3 percentage points versus the benchmark.",
            "next_check_bullet": None,
            "assumption_bullet": None,
            "caveat_bullet": "Historical simulation only.",
            "next_experiment_option_kinds": [],
            "fact_ids": [
                "tested_summary",
                "total_return",
                "benchmark_return",
                "benchmark_comparison",
                "benchmark_symbol",
                "caveat",
            ],
        }

    monkeypatch.setattr(
        explain_module,
        "invoke_openrouter_json_schema",
        fake_quick_take_plan,
    )
    state = RunState.new(current_user_message="why", recent_thread_history=[])
    state.confirmation_payload = {
        "strategy": {
            "strategy_type": "buy_and_hold",
            "strategy_thesis": "AAPL buy and hold against QQQ.",
            "asset_universe": ["AAPL"],
            "date_range": {"start": "2026-01-01", "end": "2026-05-31"},
        },
        "optional_parameters": {},
    }
    state.final_response_payload = {
        "result": {"total_return": 0.151, "benchmark_return": 0.204},
        "explanation_context": {"benchmark_symbol": "QQQ"},
    }

    result = await explain_stage_async(state=state)
    response = result.stage_patch["assistant_response"]

    assert "-5.3" not in response
    assert "lagged by 5.3 percentage points" in response
    assert result.stage_patch["assistant_response_source"] == "deterministic_fallback"
    assert result.stage_patch["assistant_response_fallback_used"] is True
    assert (
        result.stage_patch["assistant_response_failure_mode"]
        == "quick_take_draft_rejected"
    )


@pytest.mark.asyncio
async def test_result_readout_preserves_route_receipt_capture_inside_running_loop(
    monkeypatch,
) -> None:
    from argus.agent_runtime import result_readout as result_readout_module
    from argus.agent_runtime.stages import explain as explain_module
    from argus.llm import openrouter

    async def fake_quick_take_plan(**_: object) -> dict[str, object]:
        openrouter.record_openrouter_route_receipt(
            task="result_summary",
            model_name="unit-test-model",
            mode="json_schema",
            schema_name="QuickTakeDraft",
            latency_ms=7,
            outcome="succeeded",
        )
        return {
            "relative_performance_claim": "beat_benchmark",
            "takeaway": "AAPL beat QQQ by 8.1 percentage points in this historical test.",
            "tested_bullet": "Tested AAPL buy and hold over the confirmed window.",
            "meaning_bullet": "The result is grounded in the completed backtest run.",
            "next_check_bullet": None,
            "assumption_bullet": None,
            "caveat_bullet": "Historical simulation only.",
            "next_experiment_option_kinds": [],
            "fact_ids": [
                "tested_summary",
                "total_return",
                "benchmark_return",
                "benchmark_comparison",
                "benchmark_symbol",
                "caveat",
            ],
        }

    monkeypatch.setattr(
        explain_module,
        "invoke_openrouter_json_schema",
        fake_quick_take_plan,
    )

    token = openrouter.begin_openrouter_route_receipt_capture()
    try:
        readout = result_readout_module.result_readout_with_metadata_from_backtest_payload(
            request={
                "strategy_type": "buy_and_hold",
                "symbols": ["AAPL"],
                "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
            },
            envelope={"total_return": 0.35, "benchmark_return": 0.269},
            result_card={"benchmark_symbol": "QQQ"},
            explanation_context={"benchmark_symbol": "QQQ"},
            language="en",
        )
    finally:
        receipts = openrouter.end_openrouter_route_receipt_capture(token)

    assert readout.source == "llm_explain_stage"
    assert readout.fallback_used is False
    assert [receipt.task for receipt in receipts] == ["result_summary"]


@pytest.mark.asyncio
async def test_explain_stage_async_sends_only_curated_facts_to_quick_take_llm(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import explain as explain_module

    captured: dict[str, object] = {}

    async def fake_quick_take_plan(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {
            "relative_performance_claim": "beat_benchmark",
            "takeaway": "AAPL beat QQQ by 8.1 percentage points in this historical test.",
            "tested_bullet": "Tested AAPL buy and hold over the confirmed 2024 window.",
            "meaning_bullet": "AAPL returned 35.0%, while QQQ returned 26.9%.",
            "next_check_bullet": None,
            "assumption_bullet": None,
            "caveat_bullet": "Historical simulation only.",
            "next_experiment_option_kinds": [],
            "fact_ids": [
                "tested_summary",
                "total_return",
                "benchmark_return",
                "benchmark_comparison",
                "benchmark_symbol",
                "caveat",
            ],
        }

    monkeypatch.setattr(
        explain_module,
        "invoke_openrouter_json_schema",
        fake_quick_take_plan,
    )
    state = RunState.new(current_user_message="why", recent_thread_history=[])
    state.confirmation_payload = {
        "strategy": {
            "strategy_type": "buy_and_hold",
            "strategy_thesis": "AAPL buy and hold against QQQ.",
            "asset_universe": ["AAPL"],
            "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
        },
        "optional_parameters": {},
    }
    state.final_response_payload = {
        "result": {
            "total_return": 0.35,
            "benchmark_return": 0.269,
            "metrics": {"sharpe_ratio": 1.45},
        },
        "explanation_context": {
            "benchmark_symbol": "QQQ",
            "metrics": {"sharpe_ratio": 1.45},
            "result_card": {"benchmark_symbol": "QQQ"},
        },
    }

    await explain_stage_async(state=state)

    messages = captured["messages"]
    assert isinstance(messages, list)
    context = json.loads(messages[1]["content"])
    assert set(context) == {
        "allowed_next_experiments",
        "benchmark_contract",
        "fact_bank",
        "language",
        "relative_performance_truth",
        "required_fact_ids",
        "strategy",
    }
    prompt_payload = messages[1]["content"].lower()
    assert "beat by 8.1 percentage points" in prompt_payload
    assert "sharpe" not in prompt_payload
    assert "result_card" not in prompt_payload


def test_explain_stage_varies_with_expertise_mode() -> None:
    beginner_state = RunState.new(current_user_message="why", recent_thread_history=[])
    beginner_state.effective_response_profile = ResponseProfile(
        effective_tone="concise",
        effective_verbosity="medium",
        effective_expertise_mode="beginner",
    )
    beginner_state.confirmation_payload = {
        "strategy": {"strategy_thesis": "Test a Tesla pullback idea"},
    }
    beginner_state.final_response_payload = {
        "result": {"total_return": 0.14, "benchmark_return": 0.09}
    }

    advanced_state = RunState.new(current_user_message="why", recent_thread_history=[])
    advanced_state.effective_response_profile = ResponseProfile(
        effective_tone="concise",
        effective_verbosity="medium",
        effective_expertise_mode="advanced",
    )
    advanced_state.confirmation_payload = {
        "strategy": {"strategy_thesis": "Test a Tesla pullback idea"},
    }
    advanced_state.final_response_payload = {
        "result": {"total_return": 0.14, "benchmark_return": 0.09}
    }

    beginner_result = explain_stage(state=beginner_state)
    advanced_result = explain_stage(state=advanced_state)

    assert beginner_result.patch["assistant_response"].startswith("The strategy returned")
    assert (
        "evidence check"
        in beginner_result.patch["assistant_response"].lower()
    )
    assert "keep in mind:" in beginner_result.patch["assistant_response"].lower()
    assert "return comparison only" in advanced_result.patch["assistant_response"].lower()
    assert "keep in mind:" in advanced_result.patch["assistant_response"].lower()


def test_explain_stage_deterministic_fallback_avoids_report_tone() -> None:
    state = RunState.new(current_user_message="why", recent_thread_history=[])
    state.effective_response_profile = ResponseProfile(
        effective_tone="friendly",
        effective_verbosity="medium",
        effective_expertise_mode="beginner",
    )
    state.confirmation_payload = {
        "strategy": {"strategy_thesis": "Test a Tesla pullback idea"},
    }
    state.final_response_payload = {
        "result": {"total_return": 0.14, "benchmark_return": 0.09}
    }

    result = explain_stage(state=state)
    response = result.patch["assistant_response"]

    assert response.startswith("The strategy returned")
    assert "Result card:" not in response
    assert "Breakdown:" not in response
    assert "1D bars" not in response
    assert "**Interpretation:**" not in response
    assert "**Caveat:**" not in response
    assert "Keep in mind:" in response


def test_explain_stage_uses_same_period_only_when_context_supports_it() -> None:
    supported_state = RunState.new(current_user_message="why", recent_thread_history=[])
    supported_state.effective_response_profile = ResponseProfile(
        effective_tone="concise",
        effective_verbosity="low",
        effective_expertise_mode="advanced",
    )
    supported_state.final_response_payload = {
        "result": {
            "total_return": 0.14,
            "benchmark_return": 0.09,
            "comparable_same_period": True,
        }
    }

    unsupported_state = RunState.new(current_user_message="why", recent_thread_history=[])
    unsupported_state.effective_response_profile = ResponseProfile(
        effective_tone="concise",
        effective_verbosity="low",
        effective_expertise_mode="advanced",
    )
    unsupported_state.final_response_payload = {
        "result": {"total_return": 0.14, "benchmark_return": 0.09}
    }

    supported_result = explain_stage(state=supported_state)
    unsupported_result = explain_stage(state=unsupported_state)

    assert "same period" in supported_result.patch["assistant_response"].lower()
    assert "same period" not in unsupported_result.patch["assistant_response"].lower()
