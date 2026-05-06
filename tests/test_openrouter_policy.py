from __future__ import annotations

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
    structured_response: object | None = None

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.calls.append(kwargs)

    def with_structured_output(self, _schema: object) -> "FakeStructuredModel":
        return FakeStructuredModel()

    def invoke(self, _messages: list[dict[str, str]]) -> object:
        return type(
            "FakeMessage",
            (),
            {
                "content": (
                    "This breakdown explains the stored metrics, benchmark, assumptions, "
                    "and caveats without inventing any missing result data."
                )
            },
        )()


class FakeStructuredModel:
    def invoke(self, _messages: list[dict[str, str]]) -> object:
        if FakeChatOpenRouter.structured_response is not None:
            return FakeChatOpenRouter.structured_response
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
    from argus.api import main as api_main

    FakeChatOpenRouter.calls.clear()
    FakeChatOpenRouter.structured_response = None
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(openrouter, "ChatOpenRouter", FakeChatOpenRouter)

    text = api_main._llm_result_breakdown_message({"title": "AAPL test"})

    assert text is not None
    assert FakeChatOpenRouter.calls[0]["temperature"] == 0.2
    assert FakeChatOpenRouter.calls[0]["max_tokens"] == 2400


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
