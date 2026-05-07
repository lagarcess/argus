from __future__ import annotations

import pytest
from argus.agent_runtime.graph.workflow import build_workflow
from argus.agent_runtime.runtime import run_agent_turn
from argus.agent_runtime.stages.interpret import (
    InterpretationRequest,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import UserState
from langgraph.checkpoint.memory import MemorySaver


def _workflow_with_interpretation(response: StructuredInterpretation):
    class Interpreter:
        async def ainvoke(
            self, _request: InterpretationRequest
        ) -> StructuredInterpretation:
            return response

    return build_workflow(
        structured_interpreter=Interpreter(),
        checkpointer=MemorySaver(),
    )


@pytest.mark.asyncio
async def test_conversational_ux_response_comes_from_runtime_interpreter() -> None:
    workflow = _workflow_with_interpretation(
        StructuredInterpretation(
            intent="conversation_followup",
            task_relation="new_task",
            user_goal_summary="User asks what Argus can do.",
            assistant_response=(
                "Argus can help you shape an investing idea, check what details "
                "are missing, and run a historical simulation when it is ready."
            ),
            confidence=0.92,
            semantic_turn_act="educational_question",
        )
    )

    result = await run_agent_turn(
        workflow=workflow,
        user=UserState(user_id="u1", language_preference="en"),
        thread_id="thread-ux",
        message="help",
    )

    assert result["stage_outcome"] == "ready_to_respond"
    assert "shape an investing idea" in result["assistant_response"]


@pytest.mark.asyncio
async def test_conversational_ux_low_confidence_runtime_response_is_preserved() -> None:
    workflow = _workflow_with_interpretation(
        StructuredInterpretation(
            intent="conversation_followup",
            task_relation="new_task",
            user_goal_summary="User asks for guidance.",
            assistant_response=(
                "I can start by explaining the idea in plain language, then we "
                "can turn it into a supported backtest."
            ),
            confidence=0.1,
            semantic_turn_act="educational_question",
        )
    )

    result = await run_agent_turn(
        workflow=workflow,
        user=UserState(user_id="u1", language_preference="en"),
        thread_id="thread-ux-low-confidence",
        message="help",
    )

    assert result["stage_outcome"] == "ready_to_respond"
    assert "supported backtest" in result["assistant_response"]


def test_legacy_template_fallback_is_not_available() -> None:
    import importlib.util

    assert importlib.util.find_spec("argus.domain.orchestrator") is None
