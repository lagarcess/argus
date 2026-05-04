from datetime import date

import pytest
from argus.agent_runtime.recovery.policy import should_retry
from argus.agent_runtime.stages.execute import execute_stage
from argus.agent_runtime.stages.explain import explain_stage
from argus.agent_runtime.state.models import ResponseProfile, RunState
from argus.agent_runtime.strategy_contract import resolve_date_range
from argus.agent_runtime.tools.backtest_stub import StubBacktestTool
from argus.agent_runtime.tools.real_backtest import RealBacktestTool
from argus.domain.engine_launch.adapter import LaunchExecutionAdapterResult
from argus.domain.engine_launch.models import LaunchExecutionEnvelope


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
    assert tool.calls[1] == {"strategy": {"asset_universe": ["TSLA"]}}
    assert result.patch["tool_call_records"][0]["payload"] == {}


def test_execute_does_not_retry_when_corrected_payload_changes_protected_intent_fields() -> None:
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
    assert "try later" in result.patch["final_response_payload"]["error"]
    assert "try later" in result.patch["assistant_prompt"]


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
    assert result.patch["assistant_prompt"] == "I still need entry logic."
    assert result.patch["missing_required_fields"] == ["entry_logic"]
    assert len(result.patch["tool_call_records"]) == 1


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
            "initial_capital": {"value": 10000.0, "source": "default"},
        },
    }

    observed_requests: list[dict[str, object]] = []

    def fake_run_launch_backtest(
        request,
    ) -> LaunchExecutionAdapterResult:
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
    assert result.patch["final_response_payload"]["result_card"]["title"] == "TSLA Buy and Hold"
    assert (
        result.patch["final_response_payload"]["explanation_context"]["strategy_type"]
        == "buy_and_hold"
    )


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
        },
        "optional_parameters": {},
    }

    result = execute_stage(state=state, tool=tool, max_retries=1)

    assert result.outcome == "execution_succeeded"
    assert tool.calls[0]["strategy_type"] == "indicator_threshold"


def test_execute_stage_normalizes_dip_buying_and_machine_date_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime.stages import execute as execute_module

    monkeypatch.setattr(
        execute_module,
        "resolve_date_range",
        lambda value: resolve_date_range(value, today=date(2026, 5, 3)),
    )
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
            "date_range": "last_3_months",
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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime.stages import execute as execute_module

    monkeypatch.setattr(
        execute_module,
        "resolve_date_range",
        lambda value: resolve_date_range(value, today=date(2026, 5, 3)),
    )
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
        "end": "2026-05-03",
    }


def test_execute_stage_uses_strategy_contribution_for_dca(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime.stages import execute as execute_module

    monkeypatch.setattr(
        execute_module,
        "resolve_date_range",
        lambda value: resolve_date_range(value, today=date(2026, 5, 3)),
    )
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
            "date_range": "since 2021",
            "cadence": "monthly",
            "capital_amount": 500,
            "sizing_mode": "capital_amount",
        },
        "optional_parameters": {
            "initial_capital": {"value": 10000, "source": "default"},
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
        "end": "2026-05-03",
    }


def test_execute_stage_translates_lookback_limit_to_human_recovery() -> None:
    tool = StubBacktestTool(
        responses=[
            {
                "success": False,
                "error_type": "parameter_validation_error",
                "error_message": "invalid_lookback_window",
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
    assert "invalid_lookback_window" not in prompt
    assert "longer than the current backtest engine supports" in prompt
    assert "up to 3 years" in prompt


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
    assert "Caveat:" in result.patch["assistant_response"]
    assert "Defaults: Initial capital." in result.patch["assistant_response"]
    assert "same period" not in result.patch["assistant_response"].lower()
    assert "because" not in result.patch["assistant_response"].lower()


def test_explain_stage_reports_incomplete_result_payload_without_inventing_numbers() -> None:
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
    assert "cannot report observed returns yet" in result.patch["assistant_response"].lower()
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
    assert "1D bars only." in result.patch["assistant_response"]


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

    assert result.outcome == "ready_to_respond"
    assert "I tested: Test a Tesla pullback idea." in result.patch["assistant_response"]
    assert "Defaults: Initial capital." in result.patch["assistant_response"]
    assert "User-set options: Timeframe." in result.patch["assistant_response"]
    assert "return comparison, not causal attribution" in result.patch["assistant_response"]


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

    assert (
        "simple benchmark comparison"
        in beginner_result.patch["assistant_response"].lower()
    )
    assert "caveat:" in beginner_result.patch["assistant_response"].lower()
    assert (
        "return comparison only"
        in advanced_result.patch["assistant_response"].lower()
    )
    assert "caveat:" in advanced_result.patch["assistant_response"].lower()


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
