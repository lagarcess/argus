from __future__ import annotations

import inspect
from typing import Any

import pytest
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.graph.workflow import build_workflow
from argus.agent_runtime.llm_interpreter import (
    LLMInterpretationResponse,
    OpenRouterStructuredInterpreter,
)
from argus.agent_runtime.runtime import run_agent_turn
from argus.agent_runtime.stages.interpret import InterpretationRequest
from argus.agent_runtime.state.models import UserState
from argus.llm import openrouter
from argus.llm.openrouter import log_openrouter_failure
from langgraph.checkpoint.memory import MemorySaver


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


def test_openrouter_factory_applies_task_token_budget(
    monkeypatch,
) -> None:
    FakeChatOpenRouter.calls.clear()
    FakeChatOpenRouter.structured_response = None
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("AGENT_MODEL", "test/model")
    monkeypatch.setattr(openrouter, "ChatOpenRouter", FakeChatOpenRouter)

    model = openrouter.build_openrouter_model("interpretation")

    assert model is not None
    assert FakeChatOpenRouter.calls == [
        {
            "model_name": "test/model",
            "temperature": 0,
            "max_tokens": 1200,
            "openrouter_api_key": "test-key",
        }
    ]


def test_openrouter_factory_returns_none_without_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    assert openrouter.build_openrouter_model("result_breakdown") is None


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
        "max_tokens": 1200,
        "openrouter_api_key": "test-key",
    }


def test_result_breakdown_uses_bounded_profile(monkeypatch) -> None:
    from argus.api import chat_service

    FakeChatOpenRouter.calls.clear()
    FakeChatOpenRouter.invoked_messages.clear()
    FakeChatOpenRouter.structured_invoked_messages.clear()
    FakeChatOpenRouter.structured_response = None
    FakeChatOpenRouter.invoke_content = None
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(openrouter, "ChatOpenRouter", FakeChatOpenRouter)

    text = chat_service.llm_result_breakdown_message({"title": "AAPL test"})

    assert text is not None
    assert FakeChatOpenRouter.calls[0]["temperature"] == 0.2
    assert FakeChatOpenRouter.calls[0]["max_tokens"] == 2400


def test_result_breakdown_prompt_asks_for_fact_bank_references(
    monkeypatch,
) -> None:
    from argus.api import chat_service

    FakeChatOpenRouter.calls.clear()
    FakeChatOpenRouter.invoked_messages.clear()
    FakeChatOpenRouter.structured_invoked_messages.clear()
    FakeChatOpenRouter.structured_response = None
    FakeChatOpenRouter.invoke_content = None
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(openrouter, "ChatOpenRouter", FakeChatOpenRouter)

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
        }
    )

    system_prompt = FakeChatOpenRouter.structured_invoked_messages[0][0]["content"]
    user_payload = FakeChatOpenRouter.structured_invoked_messages[0][1]["content"]
    assert "non-template" in system_prompt.lower()
    assert "vary the section headings" in system_prompt.lower()
    assert "fact reference" in system_prompt.lower()
    assert "professional markdown" in system_prompt.lower()
    assert "capability truth" in system_prompt.lower()
    assert "fact_bank" in user_payload
    assert "runnable_next_tests" in user_payload
    assert "draft_only_or_future_tests" in user_payload


def test_result_breakdown_renders_structured_fact_references_from_fact_bank(
    monkeypatch,
) -> None:
    from argus.api import chat_service

    FakeChatOpenRouter.calls.clear()
    FakeChatOpenRouter.invoked_messages.clear()
    FakeChatOpenRouter.structured_invoked_messages.clear()
    FakeChatOpenRouter.structured_response = {
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
    FakeChatOpenRouter.invoke_content = None
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(openrouter, "ChatOpenRouter", FakeChatOpenRouter)

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
        }
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
    from argus.api import chat_service

    FakeChatOpenRouter.calls.clear()
    FakeChatOpenRouter.invoked_messages.clear()
    FakeChatOpenRouter.structured_invoked_messages.clear()
    FakeChatOpenRouter.structured_response = {
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
    FakeChatOpenRouter.invoke_content = None
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(openrouter, "ChatOpenRouter", FakeChatOpenRouter)

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
        }
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
    from argus.api import chat_service

    FakeChatOpenRouter.calls.clear()
    FakeChatOpenRouter.invoked_messages.clear()
    FakeChatOpenRouter.structured_invoked_messages.clear()
    FakeChatOpenRouter.structured_response = {
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
    FakeChatOpenRouter.invoke_content = None
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(openrouter, "ChatOpenRouter", FakeChatOpenRouter)

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
        }
    )

    assert text is None


def test_result_breakdown_requires_core_fact_coverage(monkeypatch) -> None:
    from argus.api import chat_service

    FakeChatOpenRouter.calls.clear()
    FakeChatOpenRouter.invoked_messages.clear()
    FakeChatOpenRouter.structured_invoked_messages.clear()
    FakeChatOpenRouter.structured_response = {
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
    FakeChatOpenRouter.invoke_content = None
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(openrouter, "ChatOpenRouter", FakeChatOpenRouter)

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
        }
    )

    assert text is None


def test_result_breakdown_path_does_not_use_regex_prose_scanner() -> None:
    from argus.api import chat_service

    source = inspect.getsource(chat_service)

    assert "_unknown_result_breakdown_symbols" not in source
    assert "_unknown_result_breakdown_percentages" not in source
    assert "re.findall" not in source


def test_result_breakdown_fallback_is_structured_educational_and_grounded(
    monkeypatch,
) -> None:
    from argus.api.chat_service import result_breakdown_message
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

    assert "### What Was Tested" in text
    assert "### What Happened" in text
    assert "### Benchmark Context" in text
    assert "### Risk Read" in text
    assert "### Assumptions" in text
    assert "### What To Try Next" in text
    assert "**Total return:** +39.5%." in text
    assert "AAPL Buy and Hold" in text
    assert "+39.5%" in text
    assert "SPY" in text
    assert "-13.8%" in text
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
            "max_tokens": 1200,
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
    assert "max_tokens=1200" in message
    assert "error_type=RuntimeError" in message
    assert "provider rejected request" not in message
    assert kwargs["error_type"] == "RuntimeError"
