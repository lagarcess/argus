from __future__ import annotations

from pathlib import Path

from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.llm_clarifier import OpenRouterClarificationGenerator
from argus.agent_runtime.stages.clarify import clarify_stage
from argus.agent_runtime.stages.confirm import confirm_stage
from argus.agent_runtime.state.models import RunState, StrategySummary


class RecordingClarifier:
    def __init__(self, question: str | None) -> None:
        self.question = question
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        return self.question


def test_clarify_uses_generator_for_missing_required_fields() -> None:
    state = RunState.new(current_user_message="Backtest Tesla", recent_thread_history=[])
    state.intent = "strategy_drafting"
    state.missing_required_fields = ["asset_universe", "date_range"]
    state.candidate_strategy_draft = StrategySummary(strategy_type="buy_and_hold")
    clarifier = RecordingClarifier("Which asset and period should I use?")

    result = clarify_stage(
        state=state,
        contract=build_default_capability_contract(),
        clarification_generator=clarifier,
        language="en",
    )

    assert result.outcome == "needs_clarification"
    assert result.patch["assistant_prompt"] == "Which asset and period should I use?"
    assert result.patch["requested_fields"] == ["asset_universe", "date_range"]
    assert clarifier.requests[0].missing_required_fields == [
        "asset_universe",
        "date_range",
    ]
    assert clarifier.requests[0].language == "en"
    assert "asset_universe" not in result.patch["assistant_prompt"]


def test_clarify_uses_generator_for_unsupported_recovery() -> None:
    state = RunState.new(
        current_user_message="Backtest Tesla and Bitcoin together",
        recent_thread_history=[],
    )
    state.intent = "strategy_drafting"
    state.optional_parameter_status = {
        "unsupported_constraints": [
            {
                "category": "unsupported_asset_mix",
                "raw_value": "TSLA, BTC",
                "explanation": "Mixed asset classes are not supported.",
                "simplification_options": [
                    {"label": "Run separate tests", "replacement_values": {}}
                ],
            }
        ]
    }
    clarifier = RecordingClarifier("Should I run those as separate tests?")

    result = clarify_stage(
        state=state,
        contract=build_default_capability_contract(),
        clarification_generator=clarifier,
    )

    assert result.outcome == "needs_clarification"
    assert result.patch["assistant_prompt"] == "Should I run those as separate tests?"
    assert result.patch["response_intent"]["kind"] == "unsupported_recovery"
    assert clarifier.requests[0].unsupported_constraints[0]["category"] == (
        "unsupported_asset_mix"
    )


def test_clarifier_system_prompt_enforces_user_language() -> None:
    clarifier = OpenRouterClarificationGenerator()
    request = clarifier.request_model(
        current_user_message="Necesito probar Tesla",
        candidate_strategy_draft=StrategySummary(strategy_type="buy_and_hold"),
        missing_required_fields=["date_range"],
        language="es-419",
    )

    messages = clarifier._messages(request)
    system_prompt = messages[0].content

    assert (
        "Respond in the user's preferred language (e.g., Spanish if language is "
        "'es-419')."
    ) in system_prompt
    assert "es-419" in messages[1].content


def test_clarify_stage_does_not_contain_slot_prompt_strings() -> None:
    source = Path("src/argus/agent_runtime/stages/clarify.py").read_text().lower()
    forbidden = [
        "what should trigger the buy",
        "which asset should i test",
        "what time period should i test",
        "how much should each recurring purchase be",
        "should i keep working on the current idea",
    ]
    for phrase in forbidden:
        assert phrase not in source


def test_confirm_stage_still_builds_confirmation_card() -> None:
    state = RunState.new(
        current_user_message="Backtest Tesla RSI",
        recent_thread_history=[],
    )
    state.candidate_strategy_draft = StrategySummary(
        strategy_type="indicator_threshold",
        strategy_thesis="Backtest Tesla RSI.",
        asset_universe=["TSLA"],
        asset_class="equity",
        date_range="last year",
        entry_logic="RSI drops below 30",
        exit_logic="RSI rises above 55",
        extra_parameters={
            "indicator": "rsi",
            "indicator_parameters": {"indicator": "rsi"},
        },
    )

    result = confirm_stage(state=state, contract=build_default_capability_contract())

    assert result.outcome == "await_approval"
    assert result.patch["confirmation_payload"]["strategy"]["asset_universe"] == ["TSLA"]
    assert "$1,000 starting capital" in result.patch["candidate_strategy_draft"][
        "assumptions"
    ]
    assert "1D bars" in result.patch["candidate_strategy_draft"]["assumptions"]


def test_confirm_stage_persists_validated_launch_payload_before_ready() -> None:
    state = RunState.new(
        current_user_message="Backtest Tesla RSI",
        recent_thread_history=[],
    )
    state.candidate_strategy_draft = StrategySummary(
        strategy_type="indicator_threshold",
        strategy_thesis="Backtest Tesla RSI.",
        asset_universe=["TSLA"],
        asset_class="equity",
        date_range="last year",
        entry_logic="RSI(14) <= 20",
        exit_logic="RSI(14) >= 60",
        extra_parameters={
            "indicator": "rsi",
            "indicator_parameters": {
                "indicator": "rsi",
                "entry_threshold": 20,
                "exit_threshold": 60,
            },
        },
    )

    result = confirm_stage(state=state, contract=build_default_capability_contract())

    launch_payload = result.patch["confirmation_payload"]["launch_payload"]
    assert result.outcome == "await_approval"
    assert launch_payload["strategy_type"] == "indicator_threshold"
    assert launch_payload["symbols"] == ["TSLA"]
    assert launch_payload["entry_rule"] == {
        "indicator": "rsi",
        "operator": "below",
        "period": 14,
        "threshold": 20.0,
    }
    assert launch_payload["exit_rule"] == {
        "indicator": "rsi",
        "operator": "above",
        "period": 14,
        "threshold": 60.0,
    }
    assert launch_payload["parameters"] == {}


def test_confirm_stage_prefers_structured_indicator_parameters_for_launch() -> None:
    state = RunState.new(
        current_user_message="Use RSI entry 20 exit 60.",
        recent_thread_history=[],
    )
    state.candidate_strategy_draft = StrategySummary(
        strategy_type="indicator_threshold",
        strategy_thesis="Backtest Tesla RSI.",
        asset_universe=["TSLA"],
        asset_class="equity",
        date_range="last year",
        entry_logic="RSI threshold entry",
        exit_logic="RSI threshold exit",
        extra_parameters={
            "indicator": "rsi",
            "indicator_parameters": {
                "indicator": "rsi",
                "entry_threshold": 20,
                "exit_threshold": 60,
            },
        },
    )

    result = confirm_stage(state=state, contract=build_default_capability_contract())

    launch_payload = result.patch["confirmation_payload"]["launch_payload"]
    assert result.outcome == "await_approval"
    assert launch_payload["entry_rule"] == {
        "indicator": "rsi",
        "operator": "below",
        "period": 14,
        "threshold": 20.0,
    }
    assert launch_payload["exit_rule"] == {
        "indicator": "rsi",
        "operator": "above",
        "period": 14,
        "threshold": 60.0,
    }


def test_confirm_stage_prefers_typed_indicator_overrides_over_default_bundle() -> None:
    state = RunState.new(
        current_user_message="Use RSI entry 20 exit 60.",
        recent_thread_history=[],
    )
    state.candidate_strategy_draft = StrategySummary(
        strategy_type="indicator_threshold",
        strategy_thesis="Backtest Tesla RSI.",
        asset_universe=["TSLA"],
        asset_class="equity",
        date_range="last year",
        entry_logic="RSI threshold entry",
        exit_logic="RSI threshold exit",
        extra_parameters={
            "indicator": "rsi",
            "entry_threshold": 20,
            "exit_threshold": 60,
            "field_provenance": {
                "entry_threshold": "user",
                "exit_threshold": "user",
            },
            "indicator_parameters": {
                "indicator": "rsi",
                "indicator_period": 14,
                "entry_threshold": 30,
                "exit_threshold": 55,
            },
        },
    )

    result = confirm_stage(state=state, contract=build_default_capability_contract())

    launch_payload = result.patch["confirmation_payload"]["launch_payload"]
    assert result.outcome == "await_approval"
    assert launch_payload["entry_rule"] == {
        "indicator": "rsi",
        "operator": "below",
        "period": 14,
        "threshold": 20.0,
    }
    assert launch_payload["exit_rule"] == {
        "indicator": "rsi",
        "operator": "above",
        "period": 14,
        "threshold": 60.0,
    }


def test_confirm_stage_preserves_user_indicator_period_in_launch_payload() -> None:
    state = RunState.new(
        current_user_message="Use RSI 7 entry 20 exit 60.",
        recent_thread_history=[],
    )
    state.candidate_strategy_draft = StrategySummary(
        strategy_type="indicator_threshold",
        strategy_thesis="Backtest Tesla RSI.",
        asset_universe=["TSLA"],
        asset_class="equity",
        date_range="last year",
        entry_logic="RSI(7) threshold entry",
        exit_logic="RSI(7) threshold exit",
        extra_parameters={
            "indicator": "rsi",
            "indicator_parameters": {
                "indicator": "rsi",
                "indicator_period": 7,
                "entry_threshold": 20,
                "exit_threshold": 60,
            },
        },
    )

    result = confirm_stage(state=state, contract=build_default_capability_contract())

    launch_payload = result.patch["confirmation_payload"]["launch_payload"]
    assert result.outcome == "await_approval"
    assert launch_payload["entry_rule"]["period"] == 7
    assert launch_payload["exit_rule"]["period"] == 7


def test_confirm_stage_blocks_unsupported_nonzero_fee_assumption() -> None:
    state = RunState.new(
        current_user_message="Backtest Tesla with fees.",
        recent_thread_history=[],
    )
    state.candidate_strategy_draft = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Backtest Tesla with fees.",
        asset_universe=["TSLA"],
        asset_class="equity",
        date_range="last year",
    )
    state.optional_parameter_status = {"fees": 0.01}

    result = confirm_stage(state=state, contract=build_default_capability_contract())

    assert result.outcome == "await_user_reply"
    assert result.patch["requested_field"] == "fees"
    assert "fees" in result.patch["assistant_prompt"].lower()


def test_confirm_stage_clarifies_vague_signal_before_ready_card() -> None:
    state = RunState.new(
        current_user_message="Test buying SPY when it starts rising.",
        recent_thread_history=[],
    )
    state.candidate_strategy_draft = StrategySummary(
        strategy_type="signal_strategy",
        strategy_thesis="Buy SPY when it starts rising.",
        asset_universe=["SPY"],
        asset_class="equity",
        date_range="last month",
        entry_logic="starts rising",
    )

    result = confirm_stage(state=state, contract=build_default_capability_contract())

    assert result.outcome == "needs_clarification"
    assert result.patch["assistant_prompt"] is None
    assert result.patch["missing_required_fields"] == ["entry_logic"]


def test_confirm_stage_blocks_signal_rule_when_window_cannot_cover_warmup() -> None:
    state = RunState.new(
        current_user_message=(
            "Test SPY when the 50-day SMA crosses above the 200-day SMA last month."
        ),
        recent_thread_history=[],
    )
    state.candidate_strategy_draft = StrategySummary(
        strategy_type="signal_strategy",
        strategy_thesis="Backtest SPY moving-average crossover.",
        asset_universe=["SPY"],
        asset_class="equity",
        date_range="last month",
        entry_logic="50-day SMA crosses above 200-day SMA",
        exit_logic="50-day SMA crosses below 200-day SMA",
        entry_rule={
            "type": "moving_average_crossover",
            "fast_indicator": "sma",
            "fast_period": 50,
            "slow_indicator": "sma",
            "slow_period": 200,
            "direction": "bullish",
        },
    )

    result = confirm_stage(state=state, contract=build_default_capability_contract())

    assert result.outcome == "await_user_reply"
    assert "longer date range" in result.patch["assistant_prompt"].lower()
    assert result.patch["requested_field"] == "date_range"
