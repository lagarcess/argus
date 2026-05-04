from __future__ import annotations

from typing import Any

from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.llm_interpreter import (
    LLMInterpretationResponse,
    OpenRouterStructuredInterpreter,
)
from argus.agent_runtime.stages.interpret import InterpretationRequest
from argus.agent_runtime.state.models import UserState
from argus.domain.orchestrator import ChatTurnIntent, classify_chat_turn_intent
from argus.llm import openrouter


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
        {"model": "test/model", "temperature": 0, "max_tokens": 1200}
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
        "model": "custom/model",
        "temperature": 0,
        "max_tokens": 1200,
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


def test_legacy_chat_composer_uses_bounded_profile(monkeypatch) -> None:
    FakeChatOpenRouter.calls.clear()
    FakeChatOpenRouter.structured_response = ChatTurnIntent(
        intent="guide",
        assistant_response="I can help you shape and test the idea.",
    )
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(openrouter, "ChatOpenRouter", FakeChatOpenRouter)

    result = classify_chat_turn_intent(message="what can you do?", language="en")

    assert result.assistant_response == "I can help you shape and test the idea."
    assert FakeChatOpenRouter.calls[0] == {
        "model": openrouter.resolve_openrouter_model(),
        "temperature": 0.2,
        "max_tokens": 1200,
    }
