from __future__ import annotations

from pathlib import Path

from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.llm_clarifier import (
    ClarificationResponse,
    OpenRouterClarificationGenerator,
)
from argus.agent_runtime.stages.clarify import clarify_stage
from argus.agent_runtime.stages.compose import compose_response_intent
from argus.agent_runtime.stages.confirm import confirm_stage
from argus.agent_runtime.state.models import ResponseIntent, RunState, StrategySummary
from argus.llm import openrouter


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

    assert result.outcome == "await_user_reply"
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

    assert result.outcome == "await_user_reply"
    assert result.patch["assistant_prompt"] == "Should I run those as separate tests?"
    assert result.patch["response_intent"]["kind"] == "unsupported_recovery"
    assert clarifier.requests[0].unsupported_constraints[0]["category"] == (
        "unsupported_asset_mix"
    )


def test_clarify_routes_interpreter_prefill_through_target_aware_generator() -> None:
    state = RunState.new(
        current_user_message="Run the MACD part only",
        recent_thread_history=[],
    )
    state.intent = "strategy_drafting"
    state.missing_required_fields = ["entry_logic"]
    assistant_prompt = (
        "I can run the MACD crossover now, but the volume jump needs a definition."
    )
    state.candidate_strategy_draft = StrategySummary(
        strategy_type="signal_strategy",
        strategy_thesis="Test BTC when MACD turns bullish and volume jumps.",
        asset_universe=["BTC"],
        date_range="last 6 months",
    )
    clarifier = RecordingClarifier("Generic fallback question")

    result = clarify_stage(
        state=state,
        contract=build_default_capability_contract(),
        clarification_generator=clarifier,
        prefilled_assistant_prompt=assistant_prompt,
    )

    assert result.outcome == "await_user_reply"
    assert result.patch["assistant_prompt"] == clarifier.question
    assert result.patch["requested_field"] == "entry_logic"
    assert clarifier.requests[0].missing_required_fields == ["entry_logic"]


def test_beginner_guidance_uses_interpreter_prefill_without_second_llm() -> None:
    state = RunState.new(
        current_user_message="I want to create a new strategy.",
        recent_thread_history=[],
    )
    state.intent = "beginner_guidance"
    assistant_prompt = (
        "Happy to start there. Pick an asset and a rough timeframe, or choose "
        "buy-and-hold, recurring buys, RSI, or a moving-average crossover."
    )
    clarifier = RecordingClarifier("This should not be used.")

    result = clarify_stage(
        state=state,
        contract=build_default_capability_contract(),
        clarification_generator=clarifier,
        prefilled_assistant_prompt=assistant_prompt,
    )

    assert result.outcome == "await_user_reply"
    assert result.patch["assistant_prompt"] == assistant_prompt
    assert result.patch["response_intent"]["kind"] == "beginner_guidance"
    assert clarifier.requests == []


def test_rule_clarification_preserves_known_asset_context() -> None:
    state = RunState.new(
        current_user_message=(
            "Can you test Nvidia using MACD and RSI together and only buy if volume "
            "is above average?"
        ),
        recent_thread_history=[],
    )
    strategy = StrategySummary(
        strategy_type="signal_strategy",
        strategy_thesis="Test Nvidia using MACD and RSI with volume confirmation.",
        asset_universe=["NVDA"],
        asset_class="equity",
        entry_logic="MACD, RSI, and volume confirmation",
    )
    state.response_intent = ResponseIntent(
        kind="clarification",
        semantic_needs=["rule_definition"],
        requested_fields=["entry_logic"],
        facts={"strategy": strategy.model_dump(mode="python")},
    )

    prompt = compose_response_intent(state)

    assert prompt is not None
    assert "NVDA" in prompt
    assert "simplified into one supported rule" in prompt
    assert "keep the full rule as a draft" in prompt


def test_multi_field_signal_clarification_uses_plain_language() -> None:
    state = RunState.new(
        current_user_message="buy when the 50 crosses the 200",
        recent_thread_history=[],
    )
    strategy = StrategySummary(
        strategy_type="signal_strategy",
        strategy_thesis="Buy when the 50-day moving average crosses the 200-day.",
        entry_logic="50 crosses 200",
    )
    state.response_intent = ResponseIntent(
        kind="clarification",
        semantic_needs=["asset_target", "period"],
        requested_fields=["asset_universe", "date_range"],
        facts={"strategy": strategy.model_dump(mode="python")},
    )

    prompt = compose_response_intent(state)

    assert prompt is not None
    assert "What should I test it on" in prompt
    assert "date window" in prompt
    assert "signal-rule" not in prompt
    assert "direction" not in prompt


def test_clarify_unsupported_recovery_uses_generator_over_prefilled_copy() -> None:
    state = RunState.new(
        current_user_message="Test Apple when news sentiment turns positive.",
        recent_thread_history=[],
    )
    state.intent = "unsupported_or_out_of_scope"
    state.optional_parameter_status = {
        "unsupported_constraints": [
            {
                "category": "unsupported_strategy_logic",
                "raw_value": "news sentiment turns positive",
                "explanation": "Sentiment/news signals are not executable yet.",
                "simplification_options": [
                    {"label": "Use a supported RSI threshold rule"},
                    {"label": "Compare with buy and hold"},
                ],
            }
        ]
    }
    clarifier = RecordingClarifier(
        "I understand the Apple sentiment idea over the past year, but sentiment is "
        "not executable yet. I can use RSI or compare with buy-and-hold. Which "
        "direction should I use?"
    )

    result = clarify_stage(
        state=state,
        contract=build_default_capability_contract(),
        clarification_generator=clarifier,
        prefilled_assistant_prompt="Please simplify the strategy.",
    )

    assert result.outcome == "await_user_reply"
    assert result.patch["assistant_prompt"] == clarifier.question
    assert clarifier.requests[0].unsupported_constraints[0]["category"] == (
        "unsupported_strategy_logic"
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


def test_clarifier_system_prompt_guides_unsupported_recovery_context() -> None:
    clarifier = OpenRouterClarificationGenerator()
    request = clarifier.request_model(
        current_user_message="Test Apple when news sentiment turns positive.",
        candidate_strategy_draft=StrategySummary(
            strategy_thesis="Use sentiment as the entry signal for Apple.",
            asset_universe=["AAPL"],
            date_range="past year",
            entry_logic="news sentiment turns positive",
        ),
        unsupported_constraints=[
            {
                "category": "unsupported_strategy_logic",
                "raw_value": "news sentiment turns positive",
                "explanation": "Sentiment/news signals are not executable yet.",
                "simplification_options": [
                    {"label": "Use a supported RSI threshold rule"},
                    {"label": "Compare with buy and hold"},
                ],
            }
        ],
        response_intent={"kind": "unsupported_recovery"},
    )

    messages = clarifier._messages(request)
    system_prompt = messages[0].content
    context = messages[1].content

    assert "unsupported_recovery" in system_prompt
    assert "asset, period, and unsupported rule" in system_prompt
    assert "simplification_options" in system_prompt
    assert "Do not claim the unsupported part is executable" in system_prompt
    assert "AAPL" in context
    assert "news sentiment turns positive" in context


def test_clarifier_system_prompt_keeps_vague_ideas_on_supported_proxies() -> None:
    clarifier = OpenRouterClarificationGenerator()
    request = clarifier.request_model(
        current_user_message="What if I bought Tesla when it looked cheap?",
        candidate_strategy_draft=StrategySummary(
            strategy_type="buy_and_hold",
            asset_universe=["TSLA"],
        ),
        missing_required_fields=["date_range"],
        response_intent={"kind": "clarification", "semantic_needs": ["period"]},
    )

    system_prompt = clarifier._messages(request)[0].content

    assert "do not write a numbered requirements list" in system_prompt.lower()
    assert "buy-and-hold baseline" in system_prompt
    assert "supported RSI threshold" in system_prompt
    assert "supported moving average crossover" in system_prompt
    assert "Acknowledge valid finance concepts" in system_prompt
    assert "P/E" in system_prompt
    assert "current engine cannot execute P/E as a rule yet" in system_prompt
    assert "Translate that concept to the closest supported proxy" in system_prompt
    assert "name P/E or valuation as valid context" in system_prompt
    assert "equity launch history starts in 2016" in system_prompt
    assert "bounded recent-data window" in system_prompt
    assert "do not silently widen the timeframe" in system_prompt
    assert "Do not mention provider names" in system_prompt
    assert "candle counts" in system_prompt
    assert "Do not ask the user to define a moving-average trigger again" in system_prompt
    assert "the 50 crosses the 200" in system_prompt
    assert "Do not use headings or numbered lists" in system_prompt


def test_openrouter_clarifier_uses_structured_response_contract(monkeypatch) -> None:
    observed = {}
    openrouter.clear_openrouter_route_receipts()
    monkeypatch.setenv("ARGUS_CHAT_MODEL", "chat/primary")
    monkeypatch.setenv("ARGUS_CHAT_FALLBACK_MODEL", "chat/fallback")

    async def fake_json_schema(
        *, task, messages, schema_model, schema_name, model_name=None
    ):
        observed["task"] = task
        observed["messages"] = messages
        observed["schema_model"] = schema_model
        observed["schema_name"] = schema_name
        observed["model_name"] = model_name
        openrouter.record_openrouter_route_receipt(
            task=task,
            model_name=model_name,
            mode="json_schema",
            schema_name=schema_name,
            latency_ms=42,
            outcome="succeeded",
            token_usage={"input_tokens": 21, "output_tokens": 16},
        )
        return ClarificationResponse(
            question=(
                "Cheap can mean valuation, like P/E. For TSLA, I can use the "
                "closest runnable proxy: buy-and-hold over a window you care "
                "about. Which date window should I use?"
            ),
            question_targets=["period"],
            directly_asks_user=True,
        )

    monkeypatch.setattr(
        "argus.agent_runtime.llm_clarifier.invoke_openrouter_json_schema",
        fake_json_schema,
    )

    clarifier = OpenRouterClarificationGenerator()
    question = clarifier(
        clarifier.request_model(
            current_user_message="What if I bought Tesla when it looked cheap?",
            candidate_strategy_draft=StrategySummary(
                strategy_type="buy_and_hold",
                asset_universe=["TSLA"],
            ),
            missing_required_fields=["date_range"],
            response_intent={
                "kind": "clarification",
                "semantic_needs": ["period"],
            },
            language="en",
        )
    )

    assert question is not None
    assert "TSLA" in question
    assert "P/E" in question
    assert "date window" in question.lower()
    assert "missing_required_fields" not in question
    assert observed["task"] == "clarification"
    assert observed["schema_model"] is ClarificationResponse
    assert observed["schema_name"] == "ClarificationResponse"
    assert observed["model_name"] is None
    assert any("P/E" in message["content"] for message in observed["messages"])
    receipts = openrouter.get_openrouter_route_receipts()
    assert receipts[-1].task == "clarification"
    assert receipts[-1].tier == "chat"
    assert receipts[-1].outcome == "succeeded"
    assert receipts[-1].token_usage == {"input_tokens": 21, "output_tokens": 16}


def test_openrouter_clarifier_rejects_questions_outside_runtime_needs(
    monkeypatch,
) -> None:
    openrouter.clear_openrouter_route_receipts()
    monkeypatch.setenv("ARGUS_CHAT_MODEL", "chat/primary")
    monkeypatch.setenv("ARGUS_CHAT_FALLBACK_MODEL", "chat/fallback")
    calls: list[str | None] = []

    async def fake_json_schema(
        *, task, messages, schema_model, schema_name, model_name=None
    ):
        del task, messages, schema_model, schema_name
        calls.append(model_name)
        if model_name is None:
            return ClarificationResponse(
                question=(
                    "Could you specify the exact trigger for the crossover before "
                    "I test it?"
                ),
                question_targets=["rule_definition"],
                directly_asks_user=True,
            )
        return ClarificationResponse(
            question=(
                "That crossover is clear enough to test. What asset should I use, "
                "and what date window should I use?"
            ),
            question_targets=["asset_target", "period"],
            directly_asks_user=True,
        )

    monkeypatch.setattr(
        "argus.agent_runtime.llm_clarifier.invoke_openrouter_json_schema",
        fake_json_schema,
    )

    clarifier = OpenRouterClarificationGenerator()
    question = clarifier(
        clarifier.request_model(
            current_user_message="buy when the 50 crosses the 200",
            candidate_strategy_draft=StrategySummary(
                strategy_type="signal_strategy",
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
            ),
            missing_required_fields=["asset_universe", "date_range"],
            response_intent={
                "kind": "clarification",
                "semantic_needs": ["asset_target", "period"],
            },
        )
    )

    assert question is not None
    assert "What asset" in question
    assert "date window" in question
    assert calls == [None, "chat/fallback"]
    receipts = openrouter.get_openrouter_route_receipts()
    assert receipts[-1].model == "chat/primary"
    assert receipts[-1].failure_mode == "contract_violation"


def test_default_unsupported_strategy_options_are_concrete() -> None:
    contract = build_default_capability_contract()

    options = contract.get_simplification_options("unsupported_strategy_logic")
    labels = [option.label for option in options]

    assert labels == [
        "Use a supported RSI threshold rule",
        "Compare with buy and hold",
        "Use a supported moving-average crossover",
    ]


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
    assert result.patch["assistant_prompt"] is None
    assert result.patch["confirmation_payload"]["strategy"]["asset_universe"] == ["TSLA"]
    assert result.patch["confirmation_payload"]["strategy"]["entry_logic"] == (
        "RSI drops below 30"
    )
    assert "$1,000 starting capital" in result.patch["candidate_strategy_draft"][
        "assumptions"
    ]
    assert "1D bars" in result.patch["candidate_strategy_draft"]["assumptions"]


def test_confirm_stage_does_not_require_thesis_for_buy_and_hold() -> None:
    state = RunState.new(
        current_user_message="Backtest buy and hold Apple over the past year.",
        recent_thread_history=[],
    )
    state.candidate_strategy_draft = StrategySummary(
        raw_user_phrasing="Backtest buy and hold Apple over the past year.",
        strategy_type="buy_and_hold",
        strategy_thesis=None,
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range="past year",
    )

    result = confirm_stage(state=state, contract=build_default_capability_contract())

    assert result.outcome == "await_approval"
    assert result.patch["missing_required_fields"] == []
    strategy = result.patch["confirmation_payload"]["strategy"]
    assert strategy["strategy_type"] == "buy_and_hold"
    assert strategy["asset_universe"] == ["AAPL"]


def test_confirm_stage_uses_product_language_for_data_window_limits() -> None:
    state = RunState.new(
        current_user_message="Backtest Apple since 2015.",
        recent_thread_history=[],
    )
    state.candidate_strategy_draft = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Apple.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range={"start": "2015-01-01", "end": "2016-01-15"},
    )

    result = confirm_stage(state=state, contract=build_default_capability_contract())

    assert result.outcome == "needs_clarification"
    assert result.patch["assistant_prompt"] is None
    assert result.patch["requested_field"] == "date_range"
    constraint = result.patch["optional_parameter_status"][
        "unsupported_constraints"
    ][0]
    assert constraint["category"] == "data_window_unavailable"
    assert "provider" not in constraint["explanation"].lower()
    assert any(
        "2016" in option["label"]
        for option in constraint["simplification_options"]
    )


def test_confirm_stage_prioritizes_data_window_before_missing_rule_details() -> None:
    state = RunState.new(
        current_user_message="test EUR/USD 1h from Jan 2025 to Feb 2025",
        recent_thread_history=[],
    )
    state.candidate_strategy_draft = StrategySummary(
        strategy_thesis="Test EUR/USD with a long hourly window.",
        asset_universe=["EURUSD"],
        asset_class="currency_pair",
        timeframe="1h",
        date_range={"start": "2025-01-01", "end": "2025-02-15"},
    )

    result = confirm_stage(state=state, contract=build_default_capability_contract())

    assert result.outcome == "needs_clarification"
    assert result.patch["assistant_prompt"] is None
    assert result.patch["requested_field"] == "date_range"
    assert result.patch["missing_required_fields"] == ["date_range"]
    constraints = result.patch["optional_parameter_status"]["unsupported_constraints"]
    assert constraints[0]["category"] == "data_window_unavailable"


def test_confirm_stage_resolves_indicator_from_strategy_type_alias() -> None:
    state = RunState.new(
        current_user_message="Backtest Tesla RSI",
        recent_thread_history=[],
    )
    state.candidate_strategy_draft = StrategySummary(
        strategy_type="rsi_threshold",
        strategy_thesis="Backtest Tesla RSI.",
        asset_universe=["TSLA"],
        asset_class="equity",
        date_range="last year",
        entry_logic="RSI drops below 30",
        exit_logic="RSI rises above 55",
    )

    result = confirm_stage(state=state, contract=build_default_capability_contract())

    launch_payload = result.patch["confirmation_payload"]["launch_payload"]
    assert result.outcome == "await_approval"
    assert launch_payload["strategy_type"] == "indicator_threshold"
    assert launch_payload["entry_rule"]["indicator"] == "rsi"
    assert launch_payload["exit_rule"]["indicator"] == "rsi"


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

    assert result.outcome == "needs_clarification"
    assert result.patch["requested_field"] == "fees"
    assert result.patch["assistant_prompt"] is None
    constraint = result.patch["optional_parameter_status"][
        "unsupported_constraints"
    ][0]
    assert constraint["category"] == "unsupported_execution_assumption"
    assert constraint["raw_value"] == "custom trading fees"


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


def test_confirm_stage_clarifies_non_executable_signal_rule_before_date() -> None:
    state = RunState.new(
        current_user_message="Test buying SPY when it starts rising.",
        recent_thread_history=[],
    )
    state.candidate_strategy_draft = StrategySummary(
        strategy_type="signal_strategy",
        strategy_thesis="Buy SPY when it starts rising.",
        asset_universe=["SPY"],
        asset_class="equity",
        entry_logic="starts rising",
        entry_rule={"type": "price_momentum", "direction": "up"},
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

    assert result.outcome == "needs_clarification"
    assert result.patch["assistant_prompt"] is None
    assert result.patch["requested_field"] == "date_range"
    constraint = result.patch["optional_parameter_status"][
        "unsupported_constraints"
    ][0]
    assert constraint["category"] == "data_window_too_short_for_rule"
    assert any(
        option["label"] == "Use a longer date range"
        for option in constraint["simplification_options"]
    )
