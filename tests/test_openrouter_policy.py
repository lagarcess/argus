from __future__ import annotations

import asyncio
import inspect
import time
from typing import Any

import pytest
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.graph.workflow import build_workflow
from argus.agent_runtime.llm_interpreter import (
    AssetAnswerCandidateAudit,
    AssetGroundingAudit,
    FocusedStrategyExtraction,
    LLMAmbiguousField,
    LLMInterpretationResponse,
    LLMStrategyDraft,
    OpenRouterStructuredInterpreter,
    StatedRunFieldFidelityAudit,
    SupportedStrategyCapabilityConflictAudit,
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
    openrouter_profile_for_task,
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


def test_interpretation_profile_has_bounded_reasoning_for_semantic_repair() -> None:
    profile = openrouter_profile_for_task("interpretation")

    assert profile.temperature == 0
    assert profile.reasoning_effort == "medium"


def test_result_summary_timeout_budget_is_safe_for_render_workflows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeChatOpenRouter.calls.clear()
    FakeChatOpenRouter.structured_response = None
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("ARGUS_CHAT_MODEL", "chat/model")
    monkeypatch.setattr(openrouter, "ChatOpenRouter", FakeChatOpenRouter)

    model = openrouter.build_openrouter_model("result_summary")

    assert model is not None
    assert FakeChatOpenRouter.calls[-1]["timeout"] == 20
    assert openrouter.openrouter_task_timeout_seconds("result_summary") == 20


def test_openrouter_task_timeout_budget_can_be_overridden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeChatOpenRouter.calls.clear()
    FakeChatOpenRouter.structured_response = None
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("ARGUS_CHAT_MODEL", "chat/model")
    monkeypatch.setenv("ARGUS_OPENROUTER_RESULT_SUMMARY_TIMEOUT_SECONDS", "27")
    monkeypatch.setattr(openrouter, "ChatOpenRouter", FakeChatOpenRouter)

    model = openrouter.build_openrouter_model("result_summary")

    assert model is not None
    assert FakeChatOpenRouter.calls[-1]["timeout"] == 27
    assert openrouter.openrouter_task_timeout_seconds("result_summary") == 27


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

    assert openrouter_structured_model_candidates(task="interpretation") == [
        "structured/primary",
        "structured/fallback",
    ]
    assert openrouter_structured_model_candidates(task="result_breakdown") == [
        "context/primary",
        "context/fallback",
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


def test_structured_model_uses_argus_tier_models_unless_explicitly_overridden(
    monkeypatch,
) -> None:
    monkeypatch.delenv("ARGUS_STRUCTURED_MODEL", raising=False)
    monkeypatch.delenv("ARGUS_STRUCTURED_FALLBACK_MODEL", raising=False)

    assert resolve_openrouter_structured_model() == ""
    assert openrouter_structured_model_candidates() == []

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
        {
            "title": "AAPL test",
            "context_packets": [{"id": "packet-1", "provider": "fred"}],
        },
        invoke_json_schema_func=fake_schema,
    )

    assert text is not None
    assert fake_schema.calls[0]["task"] == "result_breakdown"
    assert fake_schema.calls[0]["schema_model"].__name__ == "ResultBreakdownDraft"
    assert fake_schema.calls[0]["schema_name"] == "ResultBreakdownDraft"
    assert fake_schema.calls[0]["context_packet_ids"] == ["packet-1"]


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

    calls: list[dict[str, Any]] = []

    async def fake_direct_schema(**kwargs: Any) -> LLMInterpretationResponse:
        calls.append(kwargs)
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
    assert calls[0]["task"] == "interpretation"
    assert calls[0]["schema_model"] is LLMInterpretationResponse
    assert result.candidate_strategy_draft.asset_universe == ["TSLA"]
    assert result.candidate_strategy_draft.extra_parameters["indicator"] == "rsi"
    assert (
        result.candidate_strategy_draft.extra_parameters["indicator_parameters"][
            "entry_threshold"
        ]
        == 20
    )
    assert calls[0]["model_name"] == "primary/model"


@pytest.mark.parametrize(
    ("answer", "candidate_symbols", "expected_symbol", "primary_turn_act"),
    [
        ("google", ["GOOGL", "GOOG"], "GOOGL", "unsupported_request"),
        ("microsoft", ["MSFT"], "MSFT", "answer_pending_need"),
    ],
)
def test_requested_asset_answer_uses_semantic_candidate_audit_before_provider_validation(
    monkeypatch,
    answer: str,
    candidate_symbols: list[str],
    expected_symbol: str,
    primary_turn_act: str,
) -> None:
    from argus.agent_runtime import llm_interpreter

    calls: list[str] = []

    async def fake_direct_schema(**kwargs: Any):
        schema_model = kwargs["schema_model"]
        calls.append(schema_model.__name__)
        if schema_model is LLMInterpretationResponse:
            return LLMInterpretationResponse(
                intent=(
                    "unsupported_or_out_of_scope"
                    if primary_turn_act == "unsupported_request"
                    else "backtest_execution"
                ),
                task_relation="continue",
                user_goal_summary="User supplied a replacement asset.",
                semantic_turn_act=primary_turn_act,
                candidate_strategy_draft=LLMStrategyDraft(
                    asset_universe=["TSLA"],
                    asset_class="equity",
                ),
            )
        if schema_model is AssetAnswerCandidateAudit:
            return AssetAnswerCandidateAudit(
                candidate_symbols=candidate_symbols,
                confidence=0.86,
            )
        raise AssertionError(f"unexpected schema model {schema_model}")

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

    pending = StrategySummary(
        strategy_type="indicator_threshold",
        strategy_thesis="RSI threshold on TSLA.",
        asset_universe=["TSLA"],
        asset_class="equity",
        date_range={"start": "2025-11-30", "end": "2026-05-31"},
        capital_amount=1000,
        entry_logic="Buy when RSI(14) drops to 30 or below",
        exit_logic="Sell when RSI(14) rises to 55 or above",
    )
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )

    result = interpreter(
        InterpretationRequest(
            current_user_message=answer,
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(pending_strategy_summary=pending),
            selected_thread_metadata={
                "last_stage_outcome": "await_user_reply",
                "requested_field": "asset_universe",
            },
            user=UserState(user_id="u1"),
        )
    )

    assert result is not None
    assert "AssetAnswerCandidateAudit" in calls
    assert result.candidate_strategy_draft.asset_universe == [expected_symbol]
    assert result.candidate_strategy_draft.asset_class == "equity"
    assert "requested_asset_answer_candidate_audit" in result.reason_codes


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


def test_default_interpreter_repairs_underfilled_indicator_threshold_parameters(
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
                    "User wants to test TSLA with RSI below 20 and sell above 60."
                ),
                semantic_turn_act="new_idea",
                candidate_strategy_draft=LLMStrategyDraft(
                    raw_user_phrasing=(
                        "test tsla rsi below 20 and sell above 60 over the last 5 years"
                    ),
                    strategy_type="indicator_threshold",
                    strategy_thesis=(
                        "Buy TSLA when RSI is below 20 and sell when RSI rises above 60."
                    ),
                    asset_universe=["TSLA"],
                    date_range="last 5 years",
                    indicator="rsi",
                ),
            )
        if schema_model is AssetGroundingAudit:
            return AssetGroundingAudit(
                grounded_symbols=["TSLA"],
                confidence=0.9,
            )
        assert schema_model is FocusedStrategyExtraction
        return FocusedStrategyExtraction(
            is_testable_strategy=True,
            user_goal_summary="Backtest TSLA with RSI 20/60 thresholds.",
            strategy_type="indicator_threshold",
            indicator="rsi",
            entry_threshold=20,
            exit_threshold=60,
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
                "test tsla rsi below 20 and sell above 60 over the last 5 years"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        )
    )

    assert result is not None
    assert seen_schema_names[:3] == [
        "LLMInterpretationResponse",
        "AssetGroundingAudit",
        "FocusedStrategyExtraction",
    ]
    parameters = result.candidate_strategy_draft.extra_parameters[
        "indicator_parameters"
    ]
    assert parameters["indicator"] == "rsi"
    assert parameters["entry_threshold"] == 20
    assert parameters["exit_threshold"] == 60
    assert result.candidate_strategy_draft.asset_universe == ["TSLA"]
    assert result.candidate_strategy_draft.date_range == "last 5 years"


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
    assert seen_schema_names[:2] == [
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
    assert seen_schema_names[:2] == [
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
                intent="unsupported_or_out_of_scope",
                task_relation="new_task",
                user_goal_summary="User asks to trade based on Reddit sentiment.",
                candidate_strategy_draft=LLMStrategyDraft(
                    raw_user_phrasing="trade based on Reddit sentiment",
                    strategy_thesis="Trade based on Reddit sentiment.",
                ),
                semantic_turn_act="unsupported_request",
                capability_question_focus="limits",
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
    assert seen_schema_names[:2] == [
        "LLMInterpretationResponse",
        "FocusedStrategyExtraction",
    ]
    assert result.semantic_turn_act == "new_idea"
    assert result.candidate_strategy_draft.strategy_type == "buy_and_hold"
    assert result.candidate_strategy_draft.asset_universe == ["TSLA"]
    assert result.candidate_strategy_draft.date_range == "past year"


def test_default_interpreter_repairs_social_sentiment_trade_misroute(
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
            user_goal_summary="Trade based on Reddit sentiment.",
            strategy_type="reddit_sentiment",
            strategy_thesis="Use Reddit sentiment as the trade signal.",
            entry_logic="Reddit sentiment turns positive",
            assistant_response="Reddit sentiment is not executable yet.",
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
            current_user_message="trade based on Reddit sentiment",
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
    assert result.semantic_turn_act == "unsupported_request"
    assert result.unsupported_constraints[0].category == "unsupported_strategy_logic"
    assert "Reddit sentiment" in result.unsupported_constraints[0].raw_value


def test_default_interpreter_repairs_empty_unsupported_request_into_contract_recovery(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter

    seen_schema_names: list[str] = []

    async def fake_direct_schema(**kwargs: Any) -> object:
        seen_schema_names.append(kwargs["schema_name"])
        schema_model = kwargs["schema_model"]
        if schema_model is LLMInterpretationResponse:
            return LLMInterpretationResponse(
                intent="unsupported_or_out_of_scope",
                task_relation="new_task",
                requires_clarification=True,
                user_goal_summary="Trade based on Reddit sentiment.",
                assistant_response=(
                    "Reddit sentiment is not available as a trading rule."
                ),
                candidate_strategy_draft=LLMStrategyDraft(
                    raw_user_phrasing="trade based on Reddit sentiment",
                    strategy_thesis="Trade based on Reddit sentiment.",
                ),
                semantic_turn_act="unsupported_request",
            )
        assert schema_model is FocusedStrategyExtraction
        return FocusedStrategyExtraction(
            is_testable_strategy=True,
            user_goal_summary="Trade based on Reddit sentiment.",
            strategy_type="reddit_sentiment",
            strategy_thesis="Use Reddit sentiment as the trade signal.",
            entry_logic="Reddit sentiment turns positive",
            assistant_response="Reddit sentiment is not executable yet.",
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
            current_user_message="trade based on Reddit sentiment",
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
    assert result.assistant_response is None
    assert result.semantic_turn_act == "unsupported_request"
    assert result.unsupported_constraints
    assert result.unsupported_constraints[0].category == "unsupported_strategy_logic"
    labels = [
        option.label
        for option in result.unsupported_constraints[0].simplification_options
    ]
    assert labels == [
        "Use a supported RSI threshold rule",
        "Compare with buy and hold",
        "Use a supported moving-average crossover",
    ]


def test_default_interpreter_uses_focused_repair_after_structured_candidate_failures(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter

    seen_schema_names: list[str] = []

    async def fake_direct_schema(**kwargs: Any) -> object:
        seen_schema_names.append(kwargs["schema_name"])
        schema_model = kwargs["schema_model"]
        if schema_model is LLMInterpretationResponse:
            raise ValueError("general schema failed")
        if schema_model is StatedRunFieldFidelityAudit:
            return StatedRunFieldFidelityAudit()
        assert schema_model is FocusedStrategyExtraction
        return FocusedStrategyExtraction(
            is_testable_strategy=True,
            user_goal_summary="Backtest a TSLA 50/200 crossover.",
            strategy_type="signal_strategy",
            strategy_thesis="Backtest TSLA when the 50 SMA crosses the 200 SMA.",
            asset_universe=["TSLA"],
            date_range={"start": "2022-01-01", "end": "today"},
            capital_amount=10000,
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
                "buy when the 50 crosses the 200 for Tesla from January 2022 "
                "to today with 10k"
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
    draft = result.candidate_strategy_draft
    assert draft.strategy_type == "signal_strategy"
    assert draft.asset_universe == ["TSLA"]
    assert "stated_run_field_fidelity_audit" not in result.reason_codes
    assert draft.entry_rule == {
        "type": "moving_average_crossover",
        "fast_indicator": "sma",
        "fast_period": 50,
        "slow_indicator": "sma",
        "slow_period": 200,
        "direction": "bullish",
    }


def test_default_interpreter_audits_stated_fields_after_focused_repair_defaults(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter

    seen_schema_names: list[str] = []

    async def fake_direct_schema(**kwargs: Any) -> object:
        seen_schema_names.append(kwargs["schema_name"])
        schema_model = kwargs["schema_model"]
        if schema_model is LLMInterpretationResponse:
            raise ValueError("general schema failed")
        if schema_model is FocusedStrategyExtraction:
            return FocusedStrategyExtraction(
                is_testable_strategy=True,
                user_goal_summary="Backtest a TSLA 50/200 crossover.",
                strategy_type="signal_strategy",
                strategy_thesis=(
                    "Backtest TSLA when the 50 SMA crosses the 200 SMA from "
                    "January 2022 to today with 10k."
                ),
                asset_universe=["TSLA"],
                date_range="past year",
                entry_rule={
                    "type": "moving_average_crossover",
                    "fast_indicator": "sma",
                    "fast_period": 50,
                    "slow_indicator": "sma",
                    "slow_period": 200,
                    "direction": "bullish",
                },
            )
        assert schema_model is StatedRunFieldFidelityAudit
        return StatedRunFieldFidelityAudit(
            date_range={"start": "2022-01-01", "end": "today"},
            capital_amount=10000,
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
                "buy when the 50 crosses the 200 for Tesla from January 2022 "
                "to today with 10k"
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
        "StatedRunFieldFidelityAudit",
    ]
    draft = result.candidate_strategy_draft
    assert draft.date_range == {"start": "2022-01-01", "end": "today"}
    assert draft.capital_amount == 10000
    assert "stated_run_field_fidelity_audit" in result.reason_codes


def test_default_interpreter_blocks_auto_simplified_buy_hold_for_ambiguous_rule(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter

    async def fake_direct_schema(**kwargs: Any) -> object:
        assert kwargs["schema_model"] is LLMInterpretationResponse
        return LLMInterpretationResponse(
            intent="strategy_drafting",
            task_relation="new_task",
            requires_clarification=False,
            user_goal_summary="Buy and sell when the asset goes up.",
            candidate_strategy_draft=LLMStrategyDraft(
                raw_user_phrasing="buy and sell when it goes up",
                strategy_type="buy_and_hold",
                strategy_thesis=(
                    "Defaulting to buy-and-hold even though the entry and exit "
                    "rules are vague."
                ),
            ),
            ambiguous_fields=[
                LLMAmbiguousField(
                    field_name="entry_logic",
                    raw_value="when it goes up",
                    reason_code="vague_momentum_language",
                ),
                LLMAmbiguousField(
                    field_name="exit_logic",
                    raw_value="when it goes up",
                    reason_code="vague_momentum_language",
                ),
            ],
            semantic_turn_act="new_idea",
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
            current_user_message="buy and sell when it goes up",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        )
    )

    assert result is not None
    assert result.requires_clarification is True
    assert result.candidate_strategy_draft.strategy_type is None
    assert len(result.ambiguous_fields) == 2
    assert (
        "blocked_auto_simplification_for_ambiguous_rule" in result.reason_codes
    )


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
        if schema_name == "FocusedDateWindowExtraction":
            return llm_interpreter.FocusedDateWindowExtraction(
                has_date_window=False,
                confidence=0.35,
                evidence="",
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
    assert calls[:4] == [
        ("primary/model", "LLMInterpretationResponse"),
        ("primary/model", "FocusedStrategyExtraction"),
        ("fallback/model", "FocusedStrategyExtraction"),
        ("fallback/model", "LLMInterpretationResponse"),
    ]
    assert ("fallback/model", "FocusedDateWindowExtraction") in calls
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

    calls: list[tuple[str, str]] = []

    async def fake_direct_schema(**kwargs: Any) -> LLMInterpretationResponse:
        model_name = str(kwargs["model_name"])
        calls.append((model_name, str(kwargs["schema_name"])))
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
    assert calls == [
        ("primary/model", "LLMInterpretationResponse"),
        ("primary/model", "AssetGroundingAudit"),
    ]
    assert result.candidate_strategy_draft.asset_universe == ["NVDA"]


def test_default_interpreter_plans_stale_artifact_edit_before_fallback(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter

    calls: list[tuple[str, str]] = []

    async def fake_direct_schema(**kwargs: Any) -> LLMInterpretationResponse:
        model_name = str(kwargs["model_name"])
        calls.append((model_name, str(kwargs["schema_name"])))
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
    assert calls == [
        ("primary/model", "LLMInterpretationResponse"),
        ("primary/model", "AssetGroundingAudit"),
    ]
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
                field_provenance={
                    "capital_amount": "recurring_contribution",
                    "cadence": "explicit_user",
                },
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


def test_interpreter_sends_pending_field_metadata_with_artifact_context(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter

    seen_messages: list[dict[str, str]] = []

    async def fake_direct_schema(**kwargs: Any) -> LLMInterpretationResponse:
        seen_messages.extend(kwargs["messages"])
        return LLMInterpretationResponse(
            intent="strategy_drafting",
            task_relation="continue",
            user_goal_summary="User answered the pending asset field.",
            candidate_strategy_draft=LLMStrategyDraft(
                raw_user_phrasing="google",
                asset_universe=["GOOGL"],
            ),
            semantic_turn_act="answer_pending_need",
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
            current_user_message="google",
            recent_thread_history=[
                ConversationMessage(
                    role="assistant",
                    content="What asset should I use instead?",
                ),
            ],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="indicator_threshold",
                    asset_universe=["TSLA"],
                    asset_class="equity",
                    date_range={"start": "2025-11-30", "end": "2026-05-31"},
                    entry_logic="Buy when RSI(14) drops to 30 or below",
                    exit_logic="Sell when RSI(14) rises to 55 or above",
                )
            ),
            selected_thread_metadata={
                "last_stage_outcome": "await_user_reply",
                "requested_field": "asset_universe",
            },
            user=UserState(user_id="u1"),
        )
    )

    assert result is not None
    wire_text = "\n".join(message["content"] for message in seen_messages)
    assert "Selected thread metadata JSON" in wire_text
    assert '"requested_field": "asset_universe"' in wire_text
    assert "What asset should I use instead?" not in wire_text


def test_default_interpreter_rejects_result_explanation_without_latest_result(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter

    calls: list[tuple[str, str]] = []

    async def fake_direct_schema(**kwargs: Any) -> LLMInterpretationResponse:
        model_name = str(kwargs["model_name"])
        schema_name = str(kwargs["schema_name"])
        calls.append((model_name, schema_name))
        if schema_name == "StatedRunFieldFidelityAudit":
            return StatedRunFieldFidelityAudit(
                comparison_baseline="SPY",
                date_range="last year",
            )
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

    assert calls == [
        ("primary/model", "LLMInterpretationResponse"),
        ("fallback/model", "LLMInterpretationResponse"),
        ("fallback/model", "StatedRunFieldFidelityAudit"),
    ]
    assert result is not None
    assert result.intent == "backtest_execution"
    assert result.candidate_strategy_draft.asset_universe == ["MSFT"]
    assert result.candidate_strategy_draft.comparison_baseline == "SPY"


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
    assert "plain-english" in system_prompt.lower()
    assert "curiosity-forward" in system_prompt.lower()
    assert "dense financial pdf" in system_prompt.lower()
    assert "capability truth" in system_prompt.lower()
    assert "profitable trades" in system_prompt.lower()
    assert "alternative benchmarks" in system_prompt.lower()
    assert "stayed in cash" in system_prompt.lower()
    assert "provider names" in system_prompt.lower()
    assert "context packet language" in system_prompt.lower()
    assert "market or macro backdrop" in system_prompt.lower()
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
                        {"kind": "fact", "fact_id": "benchmark_comparison"},
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
    assert "Beat by 13.9 percentage points" in text
    assert "-13.8%" in text
    assert "Universe: AAPL." in text
    assert "not a prediction" in text.lower()


def test_result_breakdown_fact_bank_uses_user_safe_benchmark_comparison() -> None:
    from argus.api.chat import breakdown as chat_service

    fact_bank = chat_service.result_breakdown_fact_bank(
        {
            "title": "AAPL Buy and Hold",
            "symbols": ["AAPL"],
            "benchmark_symbol": "QQQ",
            "raw_metrics": {
                "aggregate": {
                    "performance": {
                        "total_return_pct": 15.1,
                        "benchmark_return_pct": 20.4,
                        "delta_vs_benchmark_pct": -5.3,
                        "max_drawdown_pct": -11.3,
                    }
                }
            },
            "assumptions": ["Universe: AAPL.", "Benchmark: QQQ."],
        }
    )

    assert fact_bank["benchmark_comparison"] == "Lagged by 5.3 percentage points"
    assert fact_bank["benchmark_delta_magnitude"] == "5.3 percentage points"
    assert "benchmark_delta" not in fact_bank


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
                        {"kind": "fact", "fact_id": "benchmark_comparison"},
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
        "**Performance:** SPY benchmark return +26.6%; Lagged by 24.9 percentage points."
        in text
    )
    assert "**Risk marker:** max drawdown -36.8%." in text
    assert "The tested idea was over and returned." not in text
    assert "wasBABA" not in text
    assert "Holdover" not in text
    assert "returned+1.7%" not in text
    assert "BABA Buy and Hold BABA last month" not in text


def test_result_breakdown_rejects_malformed_generated_connective_text(
    monkeypatch,
) -> None:
    from argus.api.chat import breakdown as chat_service

    del monkeypatch
    fake_schema = FakeBreakdownSchemaClient(
        {
            "sections": [
                {
                    "heading": "Reading the run",
                    "parts": [
                        {
                            "kind": "text",
                            "text": (
                                "The benchmark return for the same window was "
                            ),
                        },
                        {"kind": "fact", "fact_id": "benchmark_return"},
                        {"kind": "text", "text": " — a spread of "},
                        {"kind": "fact", "fact_id": "benchmark_comparison"},
                        {"kind": "text", "text": "."},
                        {"kind": "fact", "fact_id": "title"},
                        {"kind": "fact", "fact_id": "symbols"},
                        {"kind": "fact", "fact_id": "date_range"},
                        {"kind": "fact", "fact_id": "total_return"},
                        {"kind": "fact", "fact_id": "benchmark_symbol"},
                        {"kind": "fact", "fact_id": "max_drawdown"},
                        {"kind": "fact", "fact_id": "assumptions"},
                        {"kind": "fact", "fact_id": "caveat"},
                    ],
                }
            ]
        }
    )

    text = chat_service.llm_result_breakdown_message(
        {
            "title": "AAPL DCA Accumulation",
            "symbols": ["AAPL"],
            "benchmark_symbol": "SPY",
            "date_range": "March 1, 2024 to October 31, 2024",
            "raw_metrics": {
                "aggregate": {
                    "performance": {
                        "total_return_pct": 12.5,
                        "benchmark_return_pct": 5.5,
                        "delta_vs_benchmark_pct": 7.0,
                        "max_drawdown_pct": -4.5,
                    }
                }
            },
            "assumptions": [
                "Recurring allocation: $200.",
                "Cadence: weekly.",
                "Benchmark: SPY.",
            ],
        },
        invoke_json_schema_func=fake_schema,
    )

    assert text is not None
    assert "was — a spread of" not in text
    assert "**Test:** AAPL DCA Accumulation, March 1, 2024 to October 31, 2024." in text
    assert "SPY benchmark return +5.5%" in text
    assert "Beat by 7.0 percentage points" in text


def test_result_breakdown_rejects_quick_take_headings(monkeypatch) -> None:
    from argus.api.chat import breakdown as chat_service

    del monkeypatch
    fake_schema = FakeBreakdownSchemaClient(
        {
            "sections": [
                {
                    "heading": "Quick Take",
                    "parts": [
                        {"kind": "fact", "fact_id": "title"},
                        {"kind": "fact", "fact_id": "symbols"},
                        {"kind": "fact", "fact_id": "date_range"},
                        {"kind": "fact", "fact_id": "total_return"},
                        {"kind": "fact", "fact_id": "benchmark_symbol"},
                        {"kind": "fact", "fact_id": "benchmark_return"},
                        {"kind": "fact", "fact_id": "benchmark_comparison"},
                        {"kind": "fact", "fact_id": "max_drawdown"},
                        {"kind": "fact", "fact_id": "assumptions"},
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
            "date_range": "past year",
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


def test_result_breakdown_rejects_user_visible_internal_context_terms(
    monkeypatch,
) -> None:
    from argus.api.chat import breakdown as chat_service

    del monkeypatch
    fake_schema = FakeBreakdownSchemaClient(
        {
            "sections": [
                {
                    "heading": "Context and caveats",
                    "parts": [
                        {
                            "kind": "text",
                            "text": (
                                "Macro snapshots from the FRED data packet provide "
                                "background market conditions but do not influence trades."
                            ),
                        },
                        {"kind": "fact", "fact_id": "title"},
                        {"kind": "fact", "fact_id": "symbols"},
                        {"kind": "fact", "fact_id": "date_range"},
                        {"kind": "fact", "fact_id": "total_return"},
                        {"kind": "fact", "fact_id": "benchmark_symbol"},
                        {"kind": "fact", "fact_id": "benchmark_return"},
                        {"kind": "fact", "fact_id": "benchmark_comparison"},
                        {"kind": "fact", "fact_id": "max_drawdown"},
                        {"kind": "fact", "fact_id": "assumptions"},
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
            "date_range": "past year",
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

    assert "### Quick Breakdown" not in text
    assert "deeper read" in text
    assert "**Setup.**" in text
    assert "**How to read it.**" in text
    assert "**Risk and assumptions.**" in text
    assert "**Useful next check.**" in text
    assert "Try next:" not in text
    assert "- Tested:" not in text
    assert "- Result:" not in text
    assert "- Risk:" not in text
    assert "- Next step:" not in text
    assert "**Total return:** +39.5%." in text
    assert "Entry rule: buy at the start of the period" in text
    assert "AAPL Buy and Hold" in text
    assert "+39.5%" in text
    assert "SPY" in text
    assert "-13.8%" in text


def test_result_breakdown_metadata_records_deterministic_fallback(
    monkeypatch,
) -> None:
    from argus.api.chat.breakdown import result_breakdown_message_with_metadata
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
                }
            ],
            "assumptions": ["Universe: AAPL.", "Benchmark: SPY."],
        },
        created_at=utcnow(),
        chart=None,
        trades=[],
    )

    message = result_breakdown_message_with_metadata(run)

    assert message.source == "deterministic_fallback"
    assert message.fallback_used is True
    assert message.failure_mode == "llm_unavailable_or_contract_rejected"
    assert "**Setup.**" in message.text


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


def test_direct_json_schema_payload_uses_interpretation_profile_reasoning(
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
    assert observed_payloads[0]["reasoning"] == {"effort": "medium"}
    receipts = openrouter.get_openrouter_route_receipts()
    assert len(receipts) == 1
    receipt = receipts[0]
    assert receipt.task == "interpretation"
    assert receipt.tier == "structured"
    assert receipt.model == "qwen/qwen3.5-9b"
    assert receipt.schema_name == "LLMInterpretationResponse"
    assert receipt.outcome == "succeeded"
    assert receipt.failure_mode is None


def test_field_fidelity_json_schema_uses_context_route_with_reasoning(
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
                                    "content": '{"capital_amount":100000,"recurring_contribution_amount":null,"cadence":null,"timeframe":null,"date_range":null,"comparison_baseline":null,"confidence":0.95}'
                                }
                            }
                        ]
                    }

            return FakeResponse()

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("ARGUS_CONTEXT_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setattr(
        openrouter.httpx, "AsyncClient", lambda **_kwargs: FakeAsyncClient()
    )

    result = asyncio.run(
        openrouter.invoke_openrouter_json_schema(
            task="field_fidelity",
            messages=[{"role": "user", "content": "con 100000"}],
            schema_model=StatedRunFieldFidelityAudit,
            schema_name="StatedRunFieldFidelityAudit",
        )
    )

    assert result is not None
    assert result.capital_amount == 100000
    assert observed_payloads[0]["model"] == "openai/gpt-oss-120b"
    assert observed_payloads[0]["reasoning"] == {"effort": "high"}
    receipts = openrouter.get_openrouter_route_receipts()
    assert len(receipts) == 1
    receipt = receipts[0]
    assert receipt.task == "field_fidelity"
    assert receipt.tier == "context"
    assert receipt.model == "openai/gpt-oss-120b"
    assert receipt.schema_name == "StatedRunFieldFidelityAudit"
    assert receipt.outcome == "succeeded"


def test_capability_conflict_json_schema_uses_context_route_with_reasoning(
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
                                    "content": '{"drop_unsupported_strategy_logic":true,"keep_unsupported_strategy_logic":false,"confidence":0.94}'
                                }
                            }
                        ]
                    }

            return FakeResponse()

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("ARGUS_CONTEXT_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setattr(
        openrouter.httpx, "AsyncClient", lambda **_kwargs: FakeAsyncClient()
    )

    result = asyncio.run(
        openrouter.invoke_openrouter_json_schema(
            task="capability_conflict",
            messages=[{"role": "user", "content": "Compra y mantén ETH"}],
            schema_model=SupportedStrategyCapabilityConflictAudit,
            schema_name="SupportedStrategyCapabilityConflictAudit",
        )
    )

    assert result is not None
    assert result.drop_unsupported_strategy_logic is True
    assert observed_payloads[0]["model"] == "openai/gpt-oss-120b"
    assert observed_payloads[0]["reasoning"] == {"effort": "medium"}
    receipts = openrouter.get_openrouter_route_receipts()
    assert len(receipts) == 1
    receipt = receipts[0]
    assert receipt.task == "capability_conflict"
    assert receipt.tier == "context"
    assert receipt.model == "openai/gpt-oss-120b"
    assert receipt.schema_name == "SupportedStrategyCapabilityConflictAudit"
    assert receipt.outcome == "succeeded"


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
        token_usage={"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
        context_packet_ids=["packet-1"],
    )
    captured = openrouter.end_openrouter_route_receipt_capture(token)

    assert len(captured) == 1
    assert captured[0].task == "result_summary"
    assert captured[0].failure_mode == "TimeoutError"
    assert captured[0].token_usage == {
        "prompt_tokens": 12,
        "completion_tokens": 8,
        "total_tokens": 20,
    }
    assert captured[0].context_packet_ids == ["packet-1"]
    assert captured[0].as_dict()["context_packet_ids"] == ["packet-1"]


def test_route_receipt_latency_summary_keeps_failure_and_context_evidence() -> None:
    openrouter.clear_openrouter_route_receipts()
    openrouter.record_openrouter_route_receipt(
        task="interpretation",
        model_name="structured/primary",
        mode="json_schema",
        schema_name="LLMInterpretationResponse",
        latency_ms=1200,
        outcome="succeeded",
        token_usage={"prompt_tokens": 50, "completion_tokens": 20},
    )
    openrouter.record_openrouter_route_receipt(
        task="clarification",
        model_name="chat/fallback",
        mode="json_schema",
        schema_name="ClarificationResponse",
        latency_ms=4100,
        outcome="failed",
        failure_mode="TimeoutError",
        token_usage={"total_tokens": 30},
    )
    openrouter.record_openrouter_route_receipt(
        task="result_breakdown",
        model_name="context/primary",
        mode="json_schema",
        schema_name="ResultBreakdown",
        latency_ms=2400,
        outcome="succeeded",
        context_packet_ids=["packet-2", "packet-1"],
    )

    summary = openrouter.summarize_openrouter_route_receipts()

    assert summary["receipt_count"] == 3
    assert summary["total_latency_ms"] == 7700
    assert summary["failure_count"] == 1
    assert summary["slowest_task"] == "clarification"
    assert summary["slowest_latency_ms"] == 4100
    assert summary["context_packet_ids"] == ["packet-2", "packet-1"]
    assert summary["token_usage"] == {
        "prompt_tokens": 50,
        "completion_tokens": 20,
        "total_tokens": 30,
    }
    assert summary["route_waterfall"][1]["failure_mode"] == "TimeoutError"


def test_direct_json_schema_records_openrouter_token_usage(monkeypatch) -> None:
    from argus.agent_runtime.llm_interpreter_types import LLMInterpretationResponse

    openrouter.clear_openrouter_route_receipts()

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "choices": [
                    {
                        "message": {
                            "content": LLMInterpretationResponse(
                                intent="conversation_followup",
                                task_relation="new_task",
                                user_goal_summary="User asked what Argus can do.",
                            ).model_dump_json()
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 44,
                    "completion_tokens": 21,
                    "total_tokens": 65,
                },
            }

    class FakeAsyncClient:
        def __init__(self, **_kwargs: object) -> None:
            return None

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def post(self, *_args: object, **_kwargs: object) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("ARGUS_STRUCTURED_MODEL", "structured/primary")
    monkeypatch.setattr(
        openrouter.httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(**kwargs)
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
    receipt = openrouter.get_openrouter_route_receipts()[0]
    assert receipt.token_usage == {
        "prompt_tokens": 44,
        "completion_tokens": 21,
        "total_tokens": 65,
    }


def test_direct_json_schema_enforces_wall_clock_task_budget(monkeypatch) -> None:
    from argus.agent_runtime.llm_interpreter_types import LLMInterpretationResponse

    openrouter.clear_openrouter_route_receipts()

    class SlowAsyncClient:
        def __init__(self, **_kwargs: object) -> None:
            return None

        async def __aenter__(self) -> "SlowAsyncClient":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def post(self, *_args: object, **_kwargs: object) -> object:
            await asyncio.sleep(10)
            raise AssertionError("the task budget should cancel this request")

    profile = openrouter.OpenRouterProfile(
        "interpretation",
        temperature=0,
        max_tokens=200,
        timeout_seconds=0.01,
    )

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("ARGUS_STRUCTURED_MODEL", "structured/primary")
    monkeypatch.setenv("ARGUS_STRUCTURED_FALLBACK_MODEL", "")
    monkeypatch.setattr(openrouter, "openrouter_profile_for_task", lambda _task: profile)
    monkeypatch.setattr(
        openrouter.httpx, "AsyncClient", lambda **kwargs: SlowAsyncClient(**kwargs)
    )

    with pytest.raises(TimeoutError):
        asyncio.run(
            asyncio.wait_for(
                openrouter.invoke_openrouter_json_schema(
                    task="interpretation",
                    messages=[{"role": "user", "content": "hello"}],
                    schema_model=LLMInterpretationResponse,
                    schema_name="LLMInterpretationResponse",
                ),
                timeout=0.2,
            )
        )

    receipts = openrouter.get_openrouter_route_receipts()
    assert len(receipts) == 1
    receipt = receipts[0]
    assert receipt.task == "interpretation"
    assert receipt.model == "structured/primary"
    assert receipt.outcome == "failed"
    assert receipt.failure_mode == "TimeoutError"
    assert receipt.latency_ms < 200


def test_direct_json_schema_sync_tries_configured_fallback_for_utility_titles(
    monkeypatch,
) -> None:
    from argus.api.naming import NameSuggestion

    openrouter.clear_openrouter_route_receipts()
    attempted_models: list[str] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "choices": [{"message": {"content": '{"name":"Tesla Dip Test"}'}}],
                "usage": {
                    "prompt_tokens": 8,
                    "completion_tokens": 4,
                    "total_tokens": 12,
                },
            }

    class FakeSyncClient:
        def __init__(self, **_kwargs: object) -> None:
            return None

        def __enter__(self) -> "FakeSyncClient":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def post(self, *_args: object, **kwargs: object) -> FakeResponse:
            payload = kwargs["json"]
            assert isinstance(payload, dict)
            model = str(payload["model"])
            attempted_models.append(model)
            if model == "utility/primary":
                raise openrouter.httpx.TimeoutException("slow utility model")
            return FakeResponse()

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("ARGUS_UTILITY_MODEL", "utility/primary")
    monkeypatch.setenv("ARGUS_UTILITY_FALLBACK_MODEL", "utility/fallback")
    monkeypatch.setattr(
        openrouter.httpx, "Client", lambda **kwargs: FakeSyncClient(**kwargs)
    )

    result = openrouter.invoke_openrouter_json_schema_sync(
        task="name_suggestion",
        messages=[{"role": "user", "content": "Tesla dip-buying idea"}],
        schema_model=NameSuggestion,
        schema_name="name_suggestion",
    )

    assert result is not None
    assert result.name == "Tesla Dip Test"
    assert attempted_models == ["utility/primary", "utility/fallback"]
    receipts = openrouter.get_openrouter_route_receipts()
    assert [receipt.outcome for receipt in receipts] == ["failed", "succeeded"]
    assert receipts[0].failure_mode == "TimeoutException"
    assert receipts[1].fallback_used is True
    assert receipts[1].tier == "utility"
    assert receipts[1].token_usage == {
        "prompt_tokens": 8,
        "completion_tokens": 4,
        "total_tokens": 12,
    }


def test_direct_chat_completion_tries_configured_fallback_and_records_usage(
    monkeypatch,
) -> None:
    openrouter.clear_openrouter_route_receipts()
    attempted_models: list[str] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "choices": [{"message": {"content": "Plain-English result summary."}}],
                "usage": {
                    "prompt_tokens": 12,
                    "completion_tokens": 7,
                    "total_tokens": 19,
                },
            }

    class FakeAsyncClient:
        def __init__(self, **_kwargs: object) -> None:
            return None

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def post(self, *_args: object, **kwargs: object) -> FakeResponse:
            payload = kwargs["json"]
            assert isinstance(payload, dict)
            model = str(payload["model"])
            attempted_models.append(model)
            if model == "chat/primary":
                raise openrouter.httpx.TimeoutException("slow primary")
            return FakeResponse()

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("ARGUS_CHAT_MODEL", "chat/primary")
    monkeypatch.setenv("ARGUS_CHAT_FALLBACK_MODEL", "chat/fallback")
    monkeypatch.setattr(
        openrouter.httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(**kwargs)
    )

    result = asyncio.run(
        openrouter.invoke_openrouter_chat_completion(
            task="result_summary",
            messages=[{"role": "user", "content": "summarize"}],
            context_packet_ids=["packet-1"],
        )
    )

    assert result == "Plain-English result summary."
    assert attempted_models == ["chat/primary", "chat/fallback"]
    receipts = openrouter.get_openrouter_route_receipts()
    assert [receipt.outcome for receipt in receipts] == ["failed", "succeeded"]
    assert receipts[0].failure_mode == "TimeoutException"
    assert receipts[1].fallback_used is True
    assert receipts[1].token_usage == {
        "prompt_tokens": 12,
        "completion_tokens": 7,
        "total_tokens": 19,
    }
    assert receipts[1].context_packet_ids == ["packet-1"]
