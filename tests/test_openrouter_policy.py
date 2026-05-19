from __future__ import annotations

import asyncio
import inspect
import time
from typing import Any

import pytest
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.graph.workflow import build_workflow
from argus.agent_runtime.llm_interpreter import (
    FocusedStrategyExtraction,
    LLMInterpretationResponse,
    LLMStrategyDraft,
    OpenRouterStructuredInterpreter,
)
from argus.agent_runtime.runtime import run_agent_turn
from argus.agent_runtime.stages.interpret import InterpretationRequest
from argus.agent_runtime.state.models import (
    ConversationMessage,
    StrategySummary,
    TaskSnapshot,
    UserState,
)
from argus.domain.market_data import clear_asset_cache
from argus.llm import openrouter
from argus.llm.openrouter import (
    log_openrouter_failure,
    openrouter_structured_model_candidates,
    resolve_openrouter_structured_model,
)
from langgraph.checkpoint.memory import MemorySaver


@pytest.fixture(autouse=True)
def _provider_fixture_mode(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "synthetic_unit_fixture")
    clear_asset_cache()
    yield
    clear_asset_cache()


class FakeChatOpenRouter:
    calls: list[dict[str, Any]] = []
    invoked_messages: list[list[dict[str, str]]] = []
    structured_invoked_messages: list[list[dict[str, str]]] = []
    structured_response: object | None = None
    invoke_content: str | None = None

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.calls.append(kwargs)

    def with_structured_output(self, schema: object) -> "FakeStructuredModel":
        return FakeStructuredModel(schema)

    def invoke(self, messages: list[dict[str, str]]) -> object:
        self.invoked_messages.append(messages)
        return type(
            "FakeMessage",
            (),
            {
                "content": self.invoke_content
                or (
                    "This breakdown explains the stored metrics, benchmark, assumptions, "
                    "and caveats without inventing data. It is not a prediction."
                )
            },
        )()


class FakeStructuredModel:
    def __init__(self, schema: object | None = None) -> None:
        self.schema = schema

    def invoke(self, messages: list[dict[str, str]]) -> object:
        FakeChatOpenRouter.structured_invoked_messages.append(messages)
        if FakeChatOpenRouter.structured_response is not None:
            return FakeChatOpenRouter.structured_response
        schema_name = getattr(self.schema, "__name__", "")
        if schema_name == "ResultBreakdownDraft":
            return self.schema(  # type: ignore[misc, operator]
                sections=[
                    {
                        "heading": "Reading the run",
                        "parts": [
                            {
                                "kind": "text",
                                "text": "The tested result is ",
                            },
                            {"kind": "fact", "fact_id": "title"},
                            {
                                "kind": "text",
                                "text": ". The context to keep in view is ",
                            },
                            {"kind": "fact", "fact_id": "caveat"},
                        ],
                    },
                    {
                        "heading": "Benchmark and risk context",
                        "parts": [
                            {
                                "kind": "text",
                                "text": "Use the card metrics as the source of truth.",
                            },
                        ],
                    },
                ]
            )
        return LLMInterpretationResponse(
            intent="conversation_followup",
            task_relation="new_task",
            user_goal_summary="User asked what Argus can do.",
            assistant_response="Argus can explain ideas and help test them.",
        )

    async def ainvoke(self, _messages: list[object]) -> object:
        return self.invoke([])


class SlowBreakdownModel:
    def with_structured_output(self, _schema: object) -> "SlowBreakdownModel":
        return self

    def invoke(self, _messages: list[dict[str, str]]) -> object:
        time.sleep(0.2)
        return None


class SlowBreakdownSchemaClient:
    def __call__(self, **_kwargs: Any) -> object:
        time.sleep(0.2)
        return None


class FakeBreakdownSchemaClient:
    def __init__(self, response: object | None = None) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        if self.response is not None:
            return self.response
        schema = kwargs["schema_model"]
        return schema(
            sections=[
                {
                    "heading": "Reading the run",
                    "parts": [
                        {"kind": "text", "text": "The tested result is "},
                        {"kind": "fact", "fact_id": "title"},
                        {
                            "kind": "text",
                            "text": ". The context to keep in view is ",
                        },
                        {"kind": "fact", "fact_id": "caveat"},
                    ],
                },
                {
                    "heading": "Benchmark and risk context",
                    "parts": [
                        {
                            "kind": "text",
                            "text": "Use the card metrics as the source of truth.",
                        },
                    ],
                },
            ]
        )


class SlowStructuredInterpreterModel:
    def with_structured_output(self, _schema: object) -> "SlowStructuredInterpreterModel":
        return self

    async def ainvoke(self, _messages: list[object]) -> object:
        await asyncio.sleep(0.2)
        return LLMInterpretationResponse(
            intent="conversation_followup",
            task_relation="new_task",
            user_goal_summary="Slow response",
            assistant_response="This should time out.",
        )


def test_openrouter_factory_applies_task_token_budget(
    monkeypatch,
) -> None:
    FakeChatOpenRouter.calls.clear()
    FakeChatOpenRouter.structured_response = None
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("ARGUS_STRUCTURED_MODEL", "test/model")
    monkeypatch.setattr(openrouter, "ChatOpenRouter", FakeChatOpenRouter)

    model = openrouter.build_openrouter_model("interpretation")

    assert model is not None
    assert FakeChatOpenRouter.calls == [
        {
            "model_name": "test/model",
            "temperature": 0,
            "max_tokens": 3200,
            "timeout": 12,
            "max_retries": 1,
            "openrouter_api_key": "test-key",
        }
    ]


def test_openrouter_model_routing_uses_task_specific_tiers(monkeypatch) -> None:
    monkeypatch.setenv("ARGUS_UTILITY_MODEL", "utility/primary")
    monkeypatch.setenv("ARGUS_UTILITY_FALLBACK_MODEL", "utility/fallback")
    monkeypatch.setenv("ARGUS_CHAT_MODEL", "chat/primary")
    monkeypatch.setenv("ARGUS_CHAT_FALLBACK_MODEL", "chat/fallback")
    monkeypatch.setenv("ARGUS_STRUCTURED_MODEL", "structured/primary")
    monkeypatch.setenv("ARGUS_STRUCTURED_FALLBACK_MODEL", "structured/fallback")
    monkeypatch.setenv("ARGUS_CONTEXT_MODEL", "context/primary")
    monkeypatch.setenv("ARGUS_CONTEXT_FALLBACK_MODEL", "context/fallback")

    assert openrouter.resolve_openrouter_model(task="name_suggestion") == (
        "utility/primary"
    )
    assert (
        openrouter.resolve_openrouter_model(
            task="name_suggestion",
            fallback=True,
        )
        == "utility/fallback"
    )
    assert openrouter.resolve_openrouter_model(task="clarification") == "chat/primary"
    assert (
        openrouter.resolve_openrouter_model(
            task="clarification",
            fallback=True,
        )
        == "chat/fallback"
    )
    assert openrouter.resolve_openrouter_model(task="interpretation") == (
        "structured/primary"
    )
    assert (
        openrouter.resolve_openrouter_model(
            task="interpretation",
            fallback=True,
        )
        == "structured/fallback"
    )
    assert openrouter.resolve_openrouter_model(task="result_breakdown") == (
        "context/primary"
    )
    assert (
        openrouter.resolve_openrouter_model(
            task="result_breakdown",
            fallback=True,
        )
        == "context/fallback"
    )


def test_openrouter_structured_candidates_follow_task_tier(monkeypatch) -> None:
    monkeypatch.setenv("ARGUS_STRUCTURED_MODEL", "structured/primary")
    monkeypatch.setenv("ARGUS_STRUCTURED_FALLBACK_MODEL", "structured/fallback")
    monkeypatch.setenv("ARGUS_CONTEXT_MODEL", "context/primary")
    monkeypatch.setenv("ARGUS_CONTEXT_FALLBACK_MODEL", "context/fallback")
    monkeypatch.setenv("AGENT_STRUCTURED_MODEL", "legacy/structured")
    monkeypatch.setenv("AGENT_MODEL", "legacy/chat")
    monkeypatch.setenv("AGENT_FALLBACK_MODEL", "legacy/fallback")

    assert openrouter_structured_model_candidates(task="interpretation") == [
        "structured/primary",
        "structured/fallback",
        "legacy/structured",
        "legacy/chat",
        "legacy/fallback",
    ]
    assert openrouter_structured_model_candidates(task="result_breakdown") == [
        "context/primary",
        "context/fallback",
        "legacy/chat",
        "legacy/fallback",
    ]


def test_openrouter_factory_uses_context_model_for_result_breakdown(monkeypatch) -> None:
    FakeChatOpenRouter.calls.clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("ARGUS_CONTEXT_MODEL", "context/primary")
    monkeypatch.setattr(openrouter, "ChatOpenRouter", FakeChatOpenRouter)

    model = openrouter.build_openrouter_model("result_breakdown")

    assert model is not None
    assert FakeChatOpenRouter.calls[0]["model_name"] == "context/primary"


def test_openrouter_factory_returns_none_without_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    assert openrouter.build_openrouter_model("result_breakdown") is None


def test_structured_model_uses_configured_models_unless_explicitly_overridden(
    monkeypatch,
) -> None:
    monkeypatch.delenv("ARGUS_STRUCTURED_MODEL", raising=False)
    monkeypatch.delenv("ARGUS_STRUCTURED_FALLBACK_MODEL", raising=False)
    monkeypatch.delenv("AGENT_STRUCTURED_MODEL", raising=False)
    monkeypatch.setenv("AGENT_FALLBACK_MODEL", "deepseek/deepseek-v4-flash")
    monkeypatch.setenv("AGENT_MODEL", "qwen/qwen3.5-9b")

    assert resolve_openrouter_structured_model() == "qwen/qwen3.5-9b"
    assert openrouter_structured_model_candidates() == [
        "qwen/qwen3.5-9b",
        "deepseek/deepseek-v4-flash",
    ]

    monkeypatch.setenv("AGENT_STRUCTURED_MODEL", "custom/structured")

    assert resolve_openrouter_structured_model() == "custom/structured"
    assert openrouter_structured_model_candidates() == [
        "custom/structured",
        "qwen/qwen3.5-9b",
        "deepseek/deepseek-v4-flash",
    ]

    monkeypatch.delenv("AGENT_STRUCTURED_MODEL", raising=False)
    monkeypatch.delenv("AGENT_MODEL", raising=False)

    assert resolve_openrouter_structured_model() == "deepseek/deepseek-v4-flash"

    monkeypatch.setenv("ARGUS_STRUCTURED_MODEL", "argus/structured")

    assert resolve_openrouter_structured_model() == "argus/structured"


def test_structured_interpreter_uses_bounded_interpretation_profile(
    monkeypatch,
) -> None:
    FakeChatOpenRouter.calls.clear()
    FakeChatOpenRouter.structured_response = None
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(openrouter, "ChatOpenRouter", FakeChatOpenRouter)

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract(),
        model_name="custom/model",
    )
    result = interpreter(
        InterpretationRequest(
            current_user_message="what can you do?",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        )
    )

    assert result is not None
    assert interpreter.last_status == "used"
    assert FakeChatOpenRouter.calls[0] == {
        "model_name": "custom/model",
        "temperature": 0,
        "max_tokens": 3200,
        "timeout": 12,
        "max_retries": 1,
        "openrouter_api_key": "test-key",
    }


def test_result_breakdown_uses_direct_json_schema_client(monkeypatch) -> None:
    from argus.api.chat import breakdown as chat_service

    del monkeypatch
    fake_schema = FakeBreakdownSchemaClient()

    text = chat_service.llm_result_breakdown_message(
        {"title": "AAPL test"},
        invoke_json_schema_func=fake_schema,
    )

    assert text is not None
    assert fake_schema.calls[0]["task"] == "result_breakdown"
    assert fake_schema.calls[0]["schema_model"].__name__ == "ResultBreakdownDraft"
    assert fake_schema.calls[0]["schema_name"] == "ResultBreakdownDraft"


def test_result_breakdown_llm_has_hard_action_budget() -> None:
    from argus.api.chat.breakdown import llm_result_breakdown_message

    failures: list[dict[str, Any]] = []

    text = llm_result_breakdown_message(
        {"title": "AAPL test"},
        invoke_json_schema_func=SlowBreakdownSchemaClient(),
        log_openrouter_failure_func=lambda **kwargs: failures.append(kwargs),
        timeout_seconds=0.01,
    )

    assert text is None
    assert failures
    assert failures[0]["task"] == "result_breakdown"
    assert "timed out" in failures[0]["message"]


def test_default_interpreter_uses_direct_schema_client(monkeypatch) -> None:
    from argus.agent_runtime import llm_interpreter

    seen: dict[str, Any] = {}

    async def fake_direct_schema(**kwargs: Any) -> LLMInterpretationResponse:
        seen.update(kwargs)
        return LLMInterpretationResponse(
            intent="backtest_execution",
            task_relation="new_task",
            user_goal_summary="Backtest TSLA with RSI thresholds.",
            semantic_turn_act="new_idea",
            candidate_strategy_draft=LLMStrategyDraft(
                raw_user_phrasing=(
                    "Backtest TSLA using RSI entry at 20 or lower and exit at 60 "
                    "or higher over the last 3 months."
                ),
                strategy_type="rsi_mean_reversion",
                strategy_thesis="Use RSI thresholds on TSLA.",
                asset_universe=["TSLA"],
                date_range="last 3 months",
                indicator="rsi",
                entry_threshold=20,
                exit_threshold=60,
            ),
        )

    monkeypatch.setattr(
        llm_interpreter,
        "invoke_openrouter_json_schema",
        fake_direct_schema,
    )
    monkeypatch.setattr(
        llm_interpreter,
        "openrouter_structured_model_candidates",
        lambda: ["primary/model"],
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = interpreter(
        InterpretationRequest(
            current_user_message=(
                "Backtest TSLA using RSI entry at 20 or lower and exit at 60 "
                "or higher over the last 3 months."
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        )
    )

    assert result is not None
    assert seen["task"] == "interpretation"
    assert seen["schema_model"] is LLMInterpretationResponse
    assert result.candidate_strategy_draft.asset_universe == ["TSLA"]
    assert result.candidate_strategy_draft.extra_parameters["indicator"] == "rsi"
    assert (
        result.candidate_strategy_draft.extra_parameters["indicator_parameters"][
            "entry_threshold"
        ]
        == 20
    )
    assert seen["model_name"] == "primary/model"


def test_default_interpreter_retries_configured_structured_model_when_first_is_incomplete(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter

    calls: list[str] = []

    async def fake_direct_schema(**kwargs: Any) -> LLMInterpretationResponse:
        model_name = str(kwargs["model_name"])
        calls.append(model_name)
        if model_name == "primary/model":
            return LLMInterpretationResponse(
                intent="backtest_execution",
                task_relation="new_task",
                user_goal_summary="Backtest TSLA with RSI thresholds.",
                semantic_turn_act="new_idea",
            )
        return LLMInterpretationResponse(
            intent="backtest_execution",
            task_relation="new_task",
            user_goal_summary="Backtest TSLA with RSI thresholds.",
            semantic_turn_act="new_idea",
            candidate_strategy_draft=LLMStrategyDraft(
                raw_user_phrasing=(
                    "Backtest TSLA using RSI entry at 20 or lower and exit at 60 "
                    "or higher over the last 3 months."
                ),
                strategy_type="rsi_mean_reversion",
                strategy_thesis="Use RSI thresholds on TSLA.",
                asset_universe=["TSLA"],
                date_range="last 3 months",
                indicator="rsi",
                entry_threshold=20,
                exit_threshold=60,
            ),
        )

    monkeypatch.setattr(
        llm_interpreter,
        "invoke_openrouter_json_schema",
        fake_direct_schema,
    )
    monkeypatch.setattr(
        llm_interpreter,
        "openrouter_structured_model_candidates",
        lambda: ["primary/model", "fallback/model"],
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = interpreter(
        InterpretationRequest(
            current_user_message=(
                "Backtest TSLA using RSI entry at 20 or lower and exit at 60 "
                "or higher over the last 3 months."
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        )
    )

    assert result is not None
    assert calls == [
        "primary/model",
        "primary/model",
        "fallback/model",
        "fallback/model",
    ]
    assert interpreter.last_status == "fallback_used"
    assert result.candidate_strategy_draft.asset_universe == ["TSLA"]
    assert result.candidate_strategy_draft.extra_parameters["indicator"] == "rsi"


def test_default_interpreter_repairs_underfilled_new_signal_idea(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter

    seen_schema_names: list[str] = []

    async def fake_direct_schema(**kwargs: Any) -> object:
        seen_schema_names.append(kwargs["schema_name"])
        schema_model = kwargs["schema_model"]
        if schema_model is LLMInterpretationResponse:
            return LLMInterpretationResponse(
                intent="backtest_execution",
                task_relation="new_task",
                user_goal_summary=(
                    "Backtest Nvidia using a 50/200-day moving average crossover."
                ),
                semantic_turn_act="new_idea",
            )
        assert schema_model is FocusedStrategyExtraction
        return FocusedStrategyExtraction(
            is_testable_strategy=True,
            user_goal_summary=(
                "Backtest NVDA using a 50-day SMA crossing above a 200-day SMA."
            ),
            strategy_type="moving_average_crossover",
            asset_universe=["NVDA"],
            date_range="past 2 years",
            entry_rule={
                "type": "moving_average_crossover",
                "fast_indicator": "sma",
                "fast_period": 50,
                "slow_indicator": "sma",
                "slow_period": 200,
                "direction": "bullish",
            },
            exit_logic="Use the opposite crossover as the exit.",
        )

    monkeypatch.setattr(
        llm_interpreter,
        "invoke_openrouter_json_schema",
        fake_direct_schema,
    )
    monkeypatch.setattr(
        llm_interpreter,
        "openrouter_structured_model_candidates",
        lambda: ["primary/model"],
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = interpreter(
        InterpretationRequest(
            current_user_message=(
                "Test Nvidia when the 50-day moving average crosses above the "
                "200-day moving average over the past two years."
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        )
    )

    assert result is not None
    assert seen_schema_names == [
        "LLMInterpretationResponse",
        "FocusedStrategyExtraction",
    ]
    assert result.candidate_strategy_draft.asset_universe == ["NVDA"]
    assert result.candidate_strategy_draft.date_range == "past 2 years"
    assert result.candidate_strategy_draft.entry_rule == {
        "type": "moving_average_crossover",
        "fast_indicator": "sma",
        "fast_period": 50,
        "slow_indicator": "sma",
        "slow_period": 200,
        "direction": "bullish",
    }


def test_default_interpreter_repairs_partial_signal_idea_without_rule_payload(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter

    seen_schema_names: list[str] = []

    async def fake_direct_schema(**kwargs: Any) -> object:
        seen_schema_names.append(kwargs["schema_name"])
        schema_model = kwargs["schema_model"]
        if schema_model is LLMInterpretationResponse:
            return LLMInterpretationResponse(
                intent="backtest_execution",
                task_relation="new_task",
                user_goal_summary="Backtest NVDA with a moving average crossover.",
                semantic_turn_act="new_idea",
                candidate_strategy_draft=LLMStrategyDraft(
                    strategy_type="moving_average_crossover",
                    asset_universe=["NVDA"],
                    date_range="past two years",
                ),
            )
        assert schema_model is FocusedStrategyExtraction
        return FocusedStrategyExtraction(
            is_testable_strategy=True,
            user_goal_summary="Backtest NVDA with a 50/200 SMA bullish crossover.",
            strategy_type="signal_strategy",
            asset_universe=["NVDA"],
            date_range="past 2 years",
            entry_rule={
                "type": "moving_average_crossover",
                "fast_indicator": "sma",
                "fast_period": 50,
                "slow_indicator": "sma",
                "slow_period": 200,
                "direction": "bullish",
            },
        )

    monkeypatch.setattr(
        llm_interpreter,
        "invoke_openrouter_json_schema",
        fake_direct_schema,
    )
    monkeypatch.setattr(
        llm_interpreter,
        "openrouter_structured_model_candidates",
        lambda: ["primary/model"],
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = interpreter(
        InterpretationRequest(
            current_user_message=(
                "Test Nvidia when the 50-day moving average crosses above the "
                "200-day moving average over the past two years."
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        )
    )

    assert result is not None
    assert seen_schema_names == [
        "LLMInterpretationResponse",
        "FocusedStrategyExtraction",
    ]
    assert result.candidate_strategy_draft.entry_rule == {
        "type": "moving_average_crossover",
        "fast_indicator": "sma",
        "fast_period": 50,
        "slow_indicator": "sma",
        "slow_period": 200,
        "direction": "bullish",
    }


def test_default_interpreter_repairs_capability_misroute_for_buy_curiosity(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter

    seen_schema_names: list[str] = []

    async def fake_direct_schema(**kwargs: Any) -> object:
        seen_schema_names.append(kwargs["schema_name"])
        schema_model = kwargs["schema_model"]
        if schema_model is LLMInterpretationResponse:
            return LLMInterpretationResponse(
                intent="conversation_followup",
                task_relation="new_task",
                user_goal_summary="User asks about executable indicators.",
                assistant_response="Executable indicators right now are RSI and SMA.",
                semantic_turn_act="educational_question",
                capability_question_focus="supported_indicators",
            )
        assert schema_model is FocusedStrategyExtraction
        return FocusedStrategyExtraction(
            is_testable_strategy=True,
            user_goal_summary="Test a buy-and-hold Tesla idea.",
            strategy_type="buy_and_hold",
            asset_universe=["TSLA"],
            date_range="past year",
        )

    monkeypatch.setattr(
        llm_interpreter,
        "invoke_openrouter_json_schema",
        fake_direct_schema,
    )
    monkeypatch.setattr(
        llm_interpreter,
        "openrouter_structured_model_candidates",
        lambda: ["primary/model"],
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = interpreter(
        InterpretationRequest(
            current_user_message="what if I bought Tesla when it looked cheap?",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        )
    )

    assert result is not None
    assert seen_schema_names == [
        "LLMInterpretationResponse",
        "FocusedStrategyExtraction",
    ]
    assert result.semantic_turn_act == "new_idea"
    assert result.candidate_strategy_draft.strategy_type == "buy_and_hold"
    assert result.candidate_strategy_draft.asset_universe == ["TSLA"]
    assert result.candidate_strategy_draft.date_range == "past year"


def test_default_interpreter_retries_empty_unsupported_clarification(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter

    calls: list[tuple[str, str]] = []

    async def fake_direct_schema(**kwargs: Any) -> object:
        model_name = str(kwargs["model_name"])
        schema_name = str(kwargs["schema_name"])
        calls.append((model_name, schema_name))
        if model_name == "primary/model" and schema_name == "LLMInterpretationResponse":
            return LLMInterpretationResponse(
                intent="unsupported_or_out_of_scope",
                task_relation="new_task",
                requires_clarification=True,
                user_goal_summary="Buy Tesla after big drops.",
                assistant_response=("Could you clarify what you mean by big drops?"),
            )
        if schema_name == "FocusedStrategyExtraction":
            return FocusedStrategyExtraction(
                is_testable_strategy=True,
                user_goal_summary="Buy Tesla after big drops.",
            )
        return LLMInterpretationResponse(
            intent="strategy_drafting",
            task_relation="new_task",
            requires_clarification=True,
            user_goal_summary="Buy Tesla after big drops.",
            semantic_turn_act="new_idea",
            candidate_strategy_draft=LLMStrategyDraft(
                strategy_type="indicator_threshold",
                strategy_thesis="Buy Tesla after large price declines.",
                asset_universe=["TSLA"],
            ),
            missing_required_fields=["date_range", "entry_threshold", "exit_threshold"],
            assistant_response=(
                "I understand you want to buy Tesla after big drops. "
                "What period and threshold should I use?"
            ),
        )

    monkeypatch.setattr(
        llm_interpreter,
        "invoke_openrouter_json_schema",
        fake_direct_schema,
    )
    monkeypatch.setattr(
        llm_interpreter,
        "openrouter_structured_model_candidates",
        lambda: ["primary/model", "fallback/model"],
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = interpreter(
        InterpretationRequest(
            current_user_message="What if I bought Tesla after big drops?",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        )
    )

    assert result is not None
    assert calls == [
        ("primary/model", "LLMInterpretationResponse"),
        ("primary/model", "FocusedStrategyExtraction"),
        ("fallback/model", "FocusedStrategyExtraction"),
        ("fallback/model", "LLMInterpretationResponse"),
    ]
    assert result.candidate_strategy_draft.asset_universe == ["TSLA"]


def test_default_interpreter_keeps_artifact_context_for_vague_signal_clarification(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter

    seen_schema_names: list[str] = []

    async def fake_direct_schema(**kwargs: Any) -> object:
        seen_schema_names.append(str(kwargs["schema_name"]))
        schema_model = kwargs["schema_model"]
        if schema_model is LLMInterpretationResponse:
            return LLMInterpretationResponse(
                intent="unsupported_or_out_of_scope",
                task_relation="new_task",
                requires_clarification=True,
                user_goal_summary="Test buying SPY when it starts rising.",
                assistant_response=(
                    "I understand the direction, but starts rising needs a concrete "
                    "trigger such as a moving-average crossover or RSI threshold."
                ),
            )
        assert schema_model is FocusedStrategyExtraction
        return FocusedStrategyExtraction(
            is_testable_strategy=True,
            requires_clarification=True,
            user_goal_summary="Test buying SPY when it starts rising.",
            strategy_type="signal_strategy",
            strategy_thesis="Buy SPY when it starts rising.",
            asset_universe=["SPY"],
            entry_logic="Buy SPY when it starts rising.",
            missing_required_fields=["date_range", "entry_rule"],
            assistant_response=("What concrete trigger and date range should I use?"),
        )

    monkeypatch.setattr(
        llm_interpreter,
        "invoke_openrouter_json_schema",
        fake_direct_schema,
    )
    monkeypatch.setattr(
        llm_interpreter,
        "openrouter_structured_model_candidates",
        lambda: ["primary/model"],
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = interpreter(
        InterpretationRequest(
            current_user_message="Test buying SPY when it starts rising.",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        )
    )

    assert result is not None
    assert seen_schema_names == [
        "LLMInterpretationResponse",
        "FocusedStrategyExtraction",
    ]
    assert result.candidate_strategy_draft.asset_universe == ["SPY"]
    assert result.candidate_strategy_draft.entry_logic == (
        "Buy SPY when it starts rising."
    )
    assert result.requires_clarification is True


def test_default_interpreter_retries_empty_refinement_candidate(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter

    calls: list[str] = []

    async def fake_direct_schema(**kwargs: Any) -> LLMInterpretationResponse:
        model_name = str(kwargs["model_name"])
        calls.append(model_name)
        if model_name == "primary/model":
            return LLMInterpretationResponse(
                intent="strategy_drafting",
                task_relation="refine",
                user_goal_summary="Change the date range.",
                semantic_turn_act="refine_current_idea",
                candidate_strategy_draft=LLMStrategyDraft(),
            )
        return LLMInterpretationResponse(
            intent="strategy_drafting",
            task_relation="refine",
            user_goal_summary="Change the date range.",
            semantic_turn_act="refine_current_idea",
            candidate_strategy_draft=LLMStrategyDraft(date_range="last 6 months"),
        )

    monkeypatch.setattr(
        llm_interpreter,
        "invoke_openrouter_json_schema",
        fake_direct_schema,
    )
    monkeypatch.setattr(
        llm_interpreter,
        "openrouter_structured_model_candidates",
        lambda: ["primary/model", "fallback/model"],
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = interpreter(
        InterpretationRequest(
            current_user_message="Use the last 6 months instead.",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    asset_universe=["NVDA"],
                    asset_class="equity",
                    date_range="past year",
                )
            ),
            user=UserState(user_id="u1"),
        )
    )

    assert result is not None
    assert calls == ["primary/model", "primary/model", "fallback/model"]
    assert result.candidate_strategy_draft.date_range == "last 6 months"


def test_default_interpreter_retries_stale_prior_strategy_replay(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter

    calls: list[str] = []

    async def fake_direct_schema(**kwargs: Any) -> LLMInterpretationResponse:
        model_name = str(kwargs["model_name"])
        calls.append(model_name)
        if model_name == "primary/model":
            return LLMInterpretationResponse(
                intent="backtest_execution",
                task_relation="refine",
                user_goal_summary="Change the asset to Nvidia.",
                candidate_strategy_draft=LLMStrategyDraft(
                    raw_user_phrasing="Test buying and holding Apple over the past year.",
                    strategy_type="buy_and_hold",
                    strategy_thesis=("Test buying and holding Apple over the past year."),
                    asset_universe=["AAPL"],
                    date_range="past year",
                ),
            )
        return LLMInterpretationResponse(
            intent="backtest_execution",
            task_relation="refine",
            user_goal_summary="Change the asset to Nvidia.",
            semantic_turn_act="refine_current_idea",
            candidate_strategy_draft=LLMStrategyDraft(asset_universe=["NVDA"]),
        )

    monkeypatch.setattr(
        llm_interpreter,
        "invoke_openrouter_json_schema",
        fake_direct_schema,
    )
    monkeypatch.setattr(
        llm_interpreter,
        "openrouter_structured_model_candidates",
        lambda: ["primary/model", "fallback/model"],
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = interpreter(
        InterpretationRequest(
            current_user_message="Actually make it Nvidia.",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    raw_user_phrasing="Test buying and holding Apple over the past year.",
                    strategy_type="buy_and_hold",
                    strategy_thesis="Test buying and holding Apple over the past year.",
                    asset_universe=["AAPL"],
                    asset_class="equity",
                    date_range="last 1 year",
                )
            ),
            user=UserState(user_id="u1"),
        )
    )

    assert result is not None
    assert calls == ["primary/model", "primary/model", "fallback/model"]
    assert result.candidate_strategy_draft.asset_universe == ["NVDA"]


def test_default_interpreter_plans_stale_artifact_edit_before_fallback(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter

    calls: list[str] = []

    async def fake_direct_schema(**kwargs: Any) -> LLMInterpretationResponse:
        model_name = str(kwargs["model_name"])
        calls.append(model_name)
        wire_text = "\n".join(message["content"] for message in kwargs["messages"])
        if "Focused artifact edit planning" not in wire_text:
            return LLMInterpretationResponse(
                intent="backtest_execution",
                task_relation="refine",
                user_goal_summary="Change the asset to Nvidia.",
                semantic_turn_act="refine_current_idea",
                candidate_strategy_draft=LLMStrategyDraft(
                    raw_user_phrasing="Test buying and holding Apple over the past year.",
                    strategy_type="buy_and_hold",
                    strategy_thesis=("Test buying and holding Apple over the past year."),
                    asset_universe=["AAPL"],
                    date_range="past year",
                ),
            )
        return LLMInterpretationResponse(
            intent="backtest_execution",
            task_relation="refine",
            user_goal_summary="Change the asset to Nvidia.",
            semantic_turn_act="refine_current_idea",
            candidate_strategy_draft=LLMStrategyDraft(asset_universe=["NVDA"]),
        )

    monkeypatch.setattr(
        llm_interpreter,
        "invoke_openrouter_json_schema",
        fake_direct_schema,
    )
    monkeypatch.setattr(
        llm_interpreter,
        "openrouter_structured_model_candidates",
        lambda: ["primary/model", "fallback/model"],
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = interpreter(
        InterpretationRequest(
            current_user_message="Actually make it Nvidia.",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    raw_user_phrasing="Test buying and holding Apple over the past year.",
                    strategy_type="buy_and_hold",
                    strategy_thesis="Test buying and holding Apple over the past year.",
                    asset_universe=["AAPL"],
                    asset_class="equity",
                    date_range="last 1 year",
                )
            ),
            user=UserState(user_id="u1"),
        )
    )

    assert result is not None
    assert calls == ["primary/model", "primary/model"]
    assert interpreter.last_status == "used"
    assert result.candidate_strategy_draft.asset_universe == ["NVDA"]


def test_explicit_model_interpreter_plans_result_refinement_before_accepting_prose(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter

    FakeChatOpenRouter.calls.clear()
    FakeChatOpenRouter.structured_response = LLMInterpretationResponse(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User wants to refine the latest result.",
        assistant_response=(
            "I've updated the strategy to use biweekly recurring buys of $500."
        ),
        semantic_turn_act="educational_question",
    )
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(openrouter, "ChatOpenRouter", FakeChatOpenRouter)

    calls: list[str] = []

    async def fake_direct_schema(**kwargs: Any) -> LLMInterpretationResponse:
        calls.append(str(kwargs["model_name"]))
        wire_text = "\n".join(message["content"] for message in kwargs["messages"])
        assert "Focused artifact edit planning" in wire_text
        return LLMInterpretationResponse(
            intent="strategy_drafting",
            task_relation="refine",
            requires_clarification=False,
            user_goal_summary="Refine AAPL into recurring biweekly buys.",
            semantic_turn_act="refine_current_idea",
            candidate_strategy_draft=LLMStrategyDraft(
                raw_user_phrasing=(
                    "i want to do recurrent biweekly buys of 500 bucks instead"
                ),
                strategy_type="dca_accumulation",
                cadence="biweekly",
                capital_amount=500,
                field_provenance={"capital_amount": "recurring_contribution"},
            ),
        )

    monkeypatch.setattr(
        llm_interpreter,
        "invoke_openrouter_json_schema",
        fake_direct_schema,
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract(),
        model_name="custom/model",
    )
    result = interpreter(
        InterpretationRequest(
            current_user_message=(
                "i want to do recurrent biweekly buys of 500 bucks instead"
            ),
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    raw_user_phrasing="Backtest buy and hold Apple over the past year.",
                    strategy_type="buy_and_hold",
                    strategy_thesis="Buy and hold Apple.",
                    asset_universe=["AAPL"],
                    asset_class="equity",
                    date_range="past year",
                )
            ),
            selected_thread_metadata={
                "requested_field": "refinement",
                "source_result_run_id": "run_123",
            },
            user=UserState(user_id="u1"),
        )
    )

    assert result is not None
    assert interpreter.last_status == "used"
    assert calls == ["custom/model"]
    assert result.assistant_response is None
    assert result.candidate_strategy_draft.strategy_type == "dca_accumulation"
    assert result.candidate_strategy_draft.cadence == "biweekly"
    assert result.candidate_strategy_draft.capital_amount == 500


def test_interpreter_uses_artifact_snapshot_instead_of_raw_history_for_refinements(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter

    seen_messages: list[dict[str, str]] = []

    async def fake_direct_schema(**kwargs: Any) -> LLMInterpretationResponse:
        seen_messages.extend(kwargs["messages"])
        return LLMInterpretationResponse(
            intent="strategy_drafting",
            task_relation="refine",
            user_goal_summary="Change the asset to Nvidia.",
            candidate_strategy_draft=LLMStrategyDraft(
                raw_user_phrasing="Actually make it Nvidia.",
                strategy_type="buy_and_hold",
                asset_universe=["NVDA"],
            ),
        )

    monkeypatch.setattr(
        llm_interpreter,
        "invoke_openrouter_json_schema",
        fake_direct_schema,
    )
    monkeypatch.setattr(
        llm_interpreter,
        "openrouter_structured_model_candidates",
        lambda: ["primary/model"],
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = interpreter(
        InterpretationRequest(
            current_user_message="Actually make it Nvidia.",
            recent_thread_history=[
                ConversationMessage(
                    role="user",
                    content="Test buying and holding Apple over the past year.",
                ),
                ConversationMessage(
                    role="assistant",
                    content=(
                        "I read this as AAPL using a buy and hold approach over "
                        "past year."
                    ),
                ),
            ],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    asset_universe=["AAPL"],
                    asset_class="equity",
                    date_range="last 1 year",
                )
            ),
            user=UserState(user_id="u1"),
        )
    )

    assert result is not None
    wire_text = "\n".join(message["content"] for message in seen_messages)
    assert "Prior strategy JSON" in wire_text
    assert "I read this as AAPL" not in wire_text
    assert "Test buying and holding Apple over the past year." not in wire_text


def test_default_interpreter_rejects_result_explanation_without_latest_result(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter

    calls: list[str] = []

    async def fake_direct_schema(**kwargs: Any) -> LLMInterpretationResponse:
        model_name = str(kwargs["model_name"])
        calls.append(model_name)
        if model_name == "primary/model":
            return LLMInterpretationResponse(
                intent="results_explanation",
                task_relation="new_task",
                user_goal_summary="Claims a run result without a run.",
                semantic_turn_act="answer_pending_need",
                assistant_response="Microsoft beat SPY by 10.2%.",
            )
        return LLMInterpretationResponse(
            intent="backtest_execution",
            task_relation="new_task",
            user_goal_summary="Backtest Microsoft buy and hold.",
            semantic_turn_act="new_idea",
            candidate_strategy_draft=LLMStrategyDraft(
                raw_user_phrasing="Did Microsoft beat SPY last year if I held it?",
                strategy_type="buy_and_hold",
                strategy_thesis="Hold Microsoft for the last year.",
                asset_universe=["MSFT"],
                date_range="last year",
            ),
        )

    monkeypatch.setattr(
        llm_interpreter,
        "invoke_openrouter_json_schema",
        fake_direct_schema,
    )
    monkeypatch.setattr(
        llm_interpreter,
        "openrouter_structured_model_candidates",
        lambda: ["primary/model", "fallback/model"],
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = interpreter(
        InterpretationRequest(
            current_user_message="Did Microsoft beat SPY last year if I held it?",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        )
    )

    assert calls == ["primary/model", "fallback/model"]
    assert result is not None
    assert result.intent == "backtest_execution"
    assert result.candidate_strategy_draft.asset_universe == ["MSFT"]


def test_default_interpreter_coerces_strategy_draft_mislabeled_as_result_context(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter

    async def fake_direct_schema(**_kwargs: Any) -> LLMInterpretationResponse:
        return LLMInterpretationResponse(
            intent="results_explanation",
            task_relation="new_task",
            user_goal_summary="Backtest Microsoft buy and hold.",
            semantic_turn_act="result_followup",
            candidate_strategy_draft=LLMStrategyDraft(
                raw_user_phrasing="Did Microsoft beat SPY last year if I held it?",
                strategy_type="buy_and_hold",
                strategy_thesis="Hold Microsoft for the last year.",
                asset_universe=["MSFT"],
                date_range="last year",
            ),
        )

    monkeypatch.setattr(
        llm_interpreter,
        "invoke_openrouter_json_schema",
        fake_direct_schema,
    )
    monkeypatch.setattr(
        llm_interpreter,
        "openrouter_structured_model_candidates",
        lambda: ["primary/model"],
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = interpreter(
        InterpretationRequest(
            current_user_message="Did Microsoft beat SPY last year if I held it?",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        )
    )

    assert result is not None
    assert result.intent == "strategy_drafting"
    assert result.semantic_turn_act == "new_idea"
    assert "coerced_result_explanation_to_strategy_draft" in result.reason_codes
    assert result.candidate_strategy_draft.asset_universe == ["MSFT"]


def test_interpretation_llm_has_hard_turn_budget(monkeypatch) -> None:
    from argus.agent_runtime import llm_interpreter

    monkeypatch.setenv("AGENT_MODEL", "primary/model")
    monkeypatch.delenv("AGENT_FALLBACK_MODEL", raising=False)
    monkeypatch.setattr(
        llm_interpreter,
        "build_openrouter_model",
        lambda *_args, **_kwargs: SlowStructuredInterpreterModel(),
    )
    monkeypatch.setattr(
        llm_interpreter,
        "openrouter_task_timeout_seconds",
        lambda _task: 0.01,
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract(),
        model_name="primary/model",
    )

    result = interpreter(
        InterpretationRequest(
            current_user_message="what strategies can I test?",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        )
    )

    assert result is None
    assert interpreter.last_status == "failed"


def test_result_breakdown_prompt_asks_for_fact_bank_references(
    monkeypatch,
) -> None:
    from argus.api.chat import breakdown as chat_service

    del monkeypatch
    fake_schema = FakeBreakdownSchemaClient()

    chat_service.llm_result_breakdown_message(
        {
            "title": "AAPL Buy and Hold",
            "symbols": ["AAPL"],
            "benchmark_symbol": "SPY",
            "raw_metrics": {
                "aggregate": {
                    "performance": {
                        "total_return_pct": 39.5,
                        "benchmark_return_pct": 25.6,
                        "delta_vs_benchmark_pct": 13.9,
                        "max_drawdown_pct": -13.8,
                    }
                }
            },
        },
        invoke_json_schema_func=fake_schema,
    )

    messages = fake_schema.calls[0]["messages"]
    system_prompt = messages[0]["content"]
    user_payload = messages[1]["content"]
    assert "non-template" in system_prompt.lower()
    assert "vary the section headings" in system_prompt.lower()
    assert "fact reference" in system_prompt.lower()
    assert "professional markdown" in system_prompt.lower()
    assert "capability truth" in system_prompt.lower()
    assert "profitable trades" in system_prompt.lower()
    assert "alternative benchmarks" in system_prompt.lower()
    assert "stayed in cash" in system_prompt.lower()
    assert "fact_bank" in user_payload
    assert "runnable_next_tests" in user_payload
    assert "draft_only_or_future_tests" in user_payload


def test_result_breakdown_renders_structured_fact_references_from_fact_bank(
    monkeypatch,
) -> None:
    from argus.api.chat import breakdown as chat_service

    del monkeypatch
    fake_schema = FakeBreakdownSchemaClient(
        {
            "sections": [
                {
                    "heading": "Reading this run",
                    "parts": [
                        {"kind": "text", "text": "The tested idea was "},
                        {"kind": "fact", "fact_id": "title"},
                        {"kind": "text", "text": " across "},
                        {"kind": "fact", "fact_id": "date_range"},
                        {"kind": "text", "text": "."},
                    ],
                },
                {
                    "heading": "Return and benchmark",
                    "parts": [
                        {"kind": "fact", "fact_id": "symbols"},
                        {"kind": "text", "text": " finished at "},
                        {"kind": "fact", "fact_id": "total_return"},
                        {"kind": "text", "text": " while "},
                        {"kind": "fact", "fact_id": "benchmark_symbol"},
                        {"kind": "text", "text": " returned "},
                        {"kind": "fact", "fact_id": "benchmark_return"},
                        {"kind": "text", "text": ", leaving "},
                        {"kind": "fact", "fact_id": "benchmark_delta"},
                        {"kind": "text", "text": " of relative performance."},
                    ],
                },
                {
                    "heading": "Risk and caveat",
                    "parts": [
                        {"kind": "text", "text": "The largest drawdown was "},
                        {"kind": "fact", "fact_id": "max_drawdown"},
                        {"kind": "text", "text": ". Assumptions: "},
                        {"kind": "fact", "fact_id": "assumptions"},
                        {"kind": "text", "text": " "},
                        {"kind": "fact", "fact_id": "caveat"},
                    ],
                },
            ]
        }
    )

    text = chat_service.llm_result_breakdown_message(
        {
            "title": "AAPL Buy and Hold",
            "symbols": ["AAPL"],
            "benchmark_symbol": "SPY",
            "date_range": "past year",
            "metrics": [
                {
                    "key": "total_return_pct",
                    "label": "Total Return (%)",
                    "value": "+39.5%",
                },
                {"key": "max_drawdown", "label": "Max Drawdown", "value": "-13.8%"},
                {
                    "key": "benchmark_delta",
                    "label": "Vs benchmark",
                    "value": "+13.9 pts vs SPY",
                },
            ],
            "assumptions": ["Universe: AAPL.", "Benchmark: SPY."],
            "raw_metrics": {
                "aggregate": {
                    "performance": {
                        "total_return_pct": 39.5,
                        "benchmark_return_pct": 25.6,
                        "delta_vs_benchmark_pct": 13.9,
                        "max_drawdown_pct": -13.8,
                    }
                }
            },
        },
        invoke_json_schema_func=fake_schema,
    )

    assert text is not None
    assert "### Reading this run" in text
    assert "AAPL Buy and Hold" in text
    assert "past year" in text
    assert "AAPL" in text
    assert "+39.5%" in text
    assert "SPY" in text
    assert "+25.6%" in text
    assert "+13.9%" in text
    assert "-13.8%" in text
    assert "Universe: AAPL." in text
    assert "not a prediction" in text.lower()


def test_result_breakdown_fact_parts_join_with_professional_spacing(
    monkeypatch,
) -> None:
    from argus.api.chat import breakdown as chat_service

    del monkeypatch
    fake_schema = FakeBreakdownSchemaClient(
        {
            "sections": [
                {
                    "heading": "Reading this run",
                    "parts": [
                        {"kind": "text", "text": "The tested idea was"},
                        {"kind": "fact", "fact_id": "title"},
                        {"kind": "text", "text": "over"},
                        {"kind": "fact", "fact_id": "date_range"},
                        {"kind": "text", "text": "and returned"},
                        {"kind": "fact", "fact_id": "total_return"},
                        {"kind": "text", "text": "."},
                    ],
                },
                {
                    "heading": "Benchmark context",
                    "parts": [
                        {"kind": "fact", "fact_id": "symbols"},
                        {"kind": "text", "text": "was compared with"},
                        {"kind": "fact", "fact_id": "benchmark_symbol"},
                        {"kind": "text", "text": "at"},
                        {"kind": "fact", "fact_id": "benchmark_return"},
                        {"kind": "text", "text": "for a relative spread of"},
                        {"kind": "fact", "fact_id": "benchmark_delta"},
                        {"kind": "text", "text": "."},
                    ],
                },
                {
                    "heading": "Risk, assumptions, and next step",
                    "parts": [
                        {"kind": "text", "text": "The max drawdown was"},
                        {"kind": "fact", "fact_id": "max_drawdown"},
                        {"kind": "text", "text": ". Assumptions:"},
                        {"kind": "fact", "fact_id": "assumptions"},
                        {"kind": "text", "text": "Next runnable checks:"},
                        {"kind": "fact", "fact_id": "runnable_next_tests"},
                        {"kind": "text", "text": "."},
                        {"kind": "fact", "fact_id": "caveat"},
                    ],
                },
            ]
        }
    )

    text = chat_service.llm_result_breakdown_message(
        {
            "title": "BABA Buy and Hold",
            "symbols": ["BABA"],
            "benchmark_symbol": "SPY",
            "date_range": "last month",
            "raw_metrics": {
                "aggregate": {
                    "performance": {
                        "total_return_pct": 1.7,
                        "benchmark_return_pct": 26.6,
                        "delta_vs_benchmark_pct": -24.9,
                        "max_drawdown_pct": -36.8,
                    }
                }
            },
            "assumptions": ["Universe: BABA.", "Benchmark: SPY."],
        },
        invoke_json_schema_func=fake_schema,
    )

    assert text is not None
    assert "**Test:** BABA Buy and Hold, last month." in text
    assert "**Performance:** total return +1.7%." in text
    assert (
        "**Performance:** SPY benchmark return +26.6%; relative performance -24.9%."
        in text
    )
    assert "**Risk marker:** max drawdown -36.8%." in text
    assert "The tested idea was over and returned." not in text
    assert "wasBABA" not in text
    assert "Holdover" not in text
    assert "returned+1.7%" not in text
    assert "BABA Buy and Hold BABA last month" not in text


def test_result_breakdown_falls_back_on_invalid_fact_reference(monkeypatch) -> None:
    from argus.api.chat import breakdown as chat_service

    del monkeypatch
    fake_schema = FakeBreakdownSchemaClient(
        {
            "sections": [
                {
                    "heading": "Invented future",
                    "parts": [
                        {"kind": "text", "text": "The future expectation is "},
                        {"kind": "fact", "fact_id": "future_return"},
                    ],
                }
            ]
        }
    )

    text = chat_service.llm_result_breakdown_message(
        {
            "title": "AAPL Buy and Hold",
            "symbols": ["AAPL"],
            "benchmark_symbol": "SPY",
            "raw_metrics": {
                "aggregate": {
                    "performance": {
                        "total_return_pct": 39.5,
                        "benchmark_return_pct": 25.6,
                        "delta_vs_benchmark_pct": 13.9,
                        "max_drawdown_pct": -13.8,
                    }
                }
            },
            "assumptions": ["Universe: AAPL.", "Benchmark: SPY."],
        },
        invoke_json_schema_func=fake_schema,
    )

    assert text is None


def test_result_breakdown_requires_core_fact_coverage(monkeypatch) -> None:
    from argus.api.chat import breakdown as chat_service

    del monkeypatch
    fake_schema = FakeBreakdownSchemaClient(
        {
            "sections": [
                {
                    "heading": "Too thin",
                    "parts": [
                        {"kind": "text", "text": "The run needs more context. "},
                        {"kind": "fact", "fact_id": "caveat"},
                    ],
                }
            ]
        }
    )

    text = chat_service.llm_result_breakdown_message(
        {
            "title": "AAPL Buy and Hold",
            "symbols": ["AAPL"],
            "benchmark_symbol": "SPY",
            "raw_metrics": {
                "aggregate": {
                    "performance": {
                        "total_return_pct": 39.5,
                        "benchmark_return_pct": 25.6,
                        "delta_vs_benchmark_pct": 13.9,
                        "max_drawdown_pct": -13.8,
                    }
                }
            },
            "assumptions": ["Universe: AAPL.", "Benchmark: SPY."],
        },
        invoke_json_schema_func=fake_schema,
    )

    assert text is None


def test_result_breakdown_path_does_not_use_regex_prose_scanner() -> None:
    from argus.api.chat import breakdown

    source = inspect.getsource(breakdown)

    assert "_unknown_result_breakdown_symbols" not in source
    assert "_unknown_result_breakdown_percentages" not in source
    assert "re.findall" not in source


def test_result_breakdown_fallback_is_structured_educational_and_grounded(
    monkeypatch,
) -> None:
    from argus.api.chat.breakdown import result_breakdown_message
    from argus.api.schemas import BacktestRun
    from argus.domain.store import utcnow

    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    run = BacktestRun(
        id="run-1",
        conversation_id="conversation-1",
        strategy_id=None,
        status="completed",
        asset_class="equity",
        symbols=["AAPL"],
        allocation_method="equal_weight",
        benchmark_symbol="SPY",
        metrics={
            "aggregate": {
                "performance": {
                    "total_return_pct": 39.5,
                    "benchmark_return_pct": 25.6,
                    "delta_vs_benchmark_pct": 13.9,
                    "max_drawdown_pct": -13.8,
                }
            },
            "by_symbol": {},
        },
        config_snapshot={
            "template": "buy_and_hold",
            "symbols": ["AAPL"],
            "timeframe": "1D",
            "benchmark_symbol": "SPY",
        },
        conversation_result_card={
            "title": "AAPL Buy and Hold",
            "rows": [
                {
                    "key": "total_return_pct",
                    "label": "Total Return (%)",
                    "value": "+39.5%",
                },
                {"key": "max_drawdown", "label": "Max Drawdown", "value": "-13.8%"},
            ],
            "assumptions": ["Universe: AAPL.", "Benchmark: SPY."],
        },
        created_at=utcnow(),
        chart=None,
        trades=[],
    )

    text = result_breakdown_message(run)

    assert "### Run Lens" in text
    assert "### Performance Read" in text
    assert "### Risk And Assumptions" in text
    assert "### Discovery Path" in text
    assert "**Total return:** +39.5%." in text
    assert "Entry rule: buy at the start of the period" in text
    assert "AAPL Buy and Hold" in text
    assert "+39.5%" in text
    assert "SPY" in text
    assert "-13.8%" in text
    assert "supported RSI threshold" in text
    assert "compare against buy-and-hold" not in text
    assert "not a prediction" in text.lower()
    assert "trading recommendation" in text.lower()


@pytest.mark.asyncio
async def test_agent_runtime_turn_uses_interpretation_profile_without_legacy_composer(
    monkeypatch,
) -> None:
    FakeChatOpenRouter.calls.clear()
    FakeChatOpenRouter.structured_response = LLMInterpretationResponse(
        intent="conversation_followup",
        task_relation="new_task",
        user_goal_summary="User asked what Argus can do.",
        assistant_response="Argus can help shape and test investing ideas.",
        semantic_turn_act="educational_question",
    )
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(openrouter, "ChatOpenRouter", FakeChatOpenRouter)

    contract = build_default_capability_contract()
    workflow = build_workflow(
        structured_interpreter=OpenRouterStructuredInterpreter(
            contract=contract,
            model_name="custom/model",
        ),
        checkpointer=MemorySaver(),
    )
    result = await run_agent_turn(
        workflow=workflow,
        user=UserState(user_id="u1"),
        thread_id="thread-policy",
        message="what can you do?",
    )

    assert result["assistant_response"] == (
        "Argus can help shape and test investing ideas."
    )
    assert FakeChatOpenRouter.calls == [
        {
            "model_name": "custom/model",
            "temperature": 0,
            "max_tokens": 3200,
            "timeout": 12,
            "max_retries": 1,
            "openrouter_api_key": "test-key",
        }
    ]


def test_openrouter_failure_log_includes_visible_diagnostics(monkeypatch) -> None:
    observed: list[tuple[str, dict[str, object]]] = []

    def warning_stub(message: str, **kwargs: object) -> None:
        observed.append((message, kwargs))

    monkeypatch.setattr("argus.llm.openrouter.logger.warning", warning_stub)

    log_openrouter_failure(
        task="interpretation",
        model_name="test/model",
        exc=RuntimeError("provider rejected request"),
        message="LLM interpretation failed; falling back",
    )

    message, kwargs = observed[0]
    assert "task=interpretation" in message
    assert "model=test/model" in message
    assert "max_tokens=3200" in message
    assert "error_type=RuntimeError" in message
    assert "provider rejected request" not in message
    assert kwargs["error_type"] == "RuntimeError"


def test_direct_json_schema_payload_disables_reasoning_for_artifact_tasks(
    monkeypatch,
) -> None:
    observed_payloads: list[dict[str, Any]] = []
    openrouter.clear_openrouter_route_receipts()

    class FakeAsyncClient:
        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def post(self, _url: str, **kwargs: Any) -> object:
            observed_payloads.append(kwargs["json"])

            class FakeResponse:
                def raise_for_status(self) -> None:
                    return None

                def json(self) -> dict[str, Any]:
                    return {
                        "choices": [
                            {
                                "message": {
                                    "content": '{"intent":"conversation_followup","task_relation":"new_task","requires_clarification":false,"user_goal_summary":"hi","candidate_strategy_draft":{},"missing_required_fields":[],"assistant_response":"Hi.","uses_latest_result_context":false,"confidence":0.8,"reason_codes":[],"ambiguous_fields":[],"unsupported_constraints":[],"response_profile_overrides":{},"semantic_turn_act":"educational_question","result_followup_focus":null}'
                                }
                            }
                        ]
                    }

            return FakeResponse()

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("ARGUS_STRUCTURED_MODEL", "qwen/qwen3.5-9b")
    monkeypatch.setattr(
        openrouter.httpx, "AsyncClient", lambda **_kwargs: FakeAsyncClient()
    )

    result = asyncio.run(
        openrouter.invoke_openrouter_json_schema(
            task="interpretation",
            messages=[{"role": "user", "content": "hello"}],
            schema_model=LLMInterpretationResponse,
            schema_name="LLMInterpretationResponse",
        )
    )

    assert result is not None
    assert observed_payloads[0]["reasoning"] == {"effort": "none"}
    receipts = openrouter.get_openrouter_route_receipts()
    assert len(receipts) == 1
    receipt = receipts[0]
    assert receipt.task == "interpretation"
    assert receipt.tier == "structured"
    assert receipt.model == "qwen/qwen3.5-9b"
    assert receipt.schema_name == "LLMInterpretationResponse"
    assert receipt.outcome == "succeeded"
    assert receipt.failure_mode is None


def test_direct_json_schema_records_missing_key_route_receipt(monkeypatch) -> None:
    openrouter.clear_openrouter_route_receipts()
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("ARGUS_STRUCTURED_MODEL", "structured/primary")
    monkeypatch.setenv("ARGUS_STRUCTURED_FALLBACK_MODEL", "structured/fallback")

    result = asyncio.run(
        openrouter.invoke_openrouter_json_schema(
            task="interpretation",
            messages=[{"role": "user", "content": "hello"}],
            schema_model=LLMInterpretationResponse,
            schema_name="LLMInterpretationResponse",
        )
    )

    assert result is None
    receipts = openrouter.get_openrouter_route_receipts()
    assert len(receipts) == 1
    receipt = receipts[0]
    assert receipt.task == "interpretation"
    assert receipt.tier == "structured"
    assert receipt.model == "structured/primary"
    assert receipt.fallback_model == "structured/fallback"
    assert receipt.outcome == "skipped"
    assert receipt.failure_mode == "missing_api_key"


def test_route_receipt_capture_collects_current_runtime_calls() -> None:
    token = openrouter.begin_openrouter_route_receipt_capture()
    openrouter.record_openrouter_route_receipt(
        task="result_summary",
        model_name="chat/model",
        mode="chat_model",
        schema_name=None,
        latency_ms=42,
        outcome="failed",
        failure_mode="TimeoutError",
    )
    captured = openrouter.end_openrouter_route_receipt_capture(token)

    assert len(captured) == 1
    assert captured[0].task == "result_summary"
    assert captured[0].failure_mode == "TimeoutError"
