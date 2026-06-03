from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from argus.agent_runtime.artifacts.drafts import draft_from_result_metadata
from argus.agent_runtime.stages.artifact_context import latest_run_id_for_action
from argus.agent_runtime.stages.compose import compose_response_intent
from argus.agent_runtime.state.models import ResponseIntent, RunState
from argus.api.chat.artifacts import result_reference_from_run
from argus.api.schemas import BacktestRun, ChatActionPayload

MISSING_REFINEMENT_RESULT_MESSAGE = (
    "I could not find the completed backtest to refine. Use Refine strategy from "
    "the latest result card, or run the strategy again."
)


@dataclass(frozen=True)
class ResultActionTurn:
    stage: str
    assistant_text: str
    metadata: dict[str, Any]
    final_payload: dict[str, Any]


def refine_strategy_action_turn(
    *,
    run: BacktestRun,
    action: ChatActionPayload,
) -> ResultActionTurn:
    reference = result_reference_from_run(run)
    strategy = draft_from_result_metadata(reference.metadata)
    pending_strategy = {
        "strategy": strategy.model_dump(mode="python"),
        "requested_field": "refinement",
        "missing_required_fields": ["refinement"],
        "source_result": {
            "run_id": run.id,
            "strategy_id": run.strategy_id,
            "conversation_id": run.conversation_id,
        },
    }
    latest_run_id = latest_run_id_for_action(
        action_payload=action.payload,
        reference=reference,
    )
    response_intent = _refinement_response_intent(
        action=action,
        latest_run_id=latest_run_id,
        pending_strategy=pending_strategy,
        reference=reference,
    )
    assistant_text = _compose_refinement_prompt(response_intent)
    pending_strategy["response_intent"] = response_intent
    metadata = {
        "conversation_mode": "setup",
        "agent_runtime_stage_outcome": "await_user_reply",
        "chat_action": action.model_dump(mode="python"),
        "pending_strategy": pending_strategy,
        "response_intent": response_intent,
        "source_result_run_id": run.id,
        "source_result_strategy_id": run.strategy_id,
        "source_result_conversation_id": run.conversation_id,
    }
    final_payload = {
        "stage_outcome": "await_user_reply",
        "assistant_response": assistant_text,
        "pending_strategy": pending_strategy,
        "response_intent": response_intent,
        "latest_run_id": latest_run_id,
        "source_result_run_id": run.id,
    }
    return ResultActionTurn(
        stage="interpret",
        assistant_text=assistant_text,
        metadata=metadata,
        final_payload=final_payload,
    )


def missing_refine_strategy_action_turn(
    *,
    action: ChatActionPayload,
) -> ResultActionTurn:
    metadata = {
        "conversation_mode": "result_review",
        "agent_runtime_stage_outcome": "ready_to_respond",
        "chat_action": action.model_dump(mode="python"),
    }
    final_payload = {
        "stage_outcome": "ready_to_respond",
        "assistant_response": MISSING_REFINEMENT_RESULT_MESSAGE,
    }
    return ResultActionTurn(
        stage="interpret",
        assistant_text=MISSING_REFINEMENT_RESULT_MESSAGE,
        metadata=metadata,
        final_payload=final_payload,
    )


def _refinement_response_intent(
    *,
    action: ChatActionPayload,
    latest_run_id: str | None,
    pending_strategy: dict[str, Any],
    reference: Any,
) -> dict[str, Any]:
    return {
        "kind": "clarification",
        "semantic_needs": ["refinement"],
        "requested_fields": ["refinement"],
        "facts": {
            "strategy": pending_strategy["strategy"],
            "structured_action": action.model_dump(mode="python"),
            "latest_run_id": latest_run_id,
            "latest_result_reference": reference.model_dump(mode="python"),
        },
        "options": [],
    }


def _compose_refinement_prompt(response_intent: dict[str, Any]) -> str:
    state = RunState.new(current_user_message="", recent_thread_history=[])
    state.response_intent = ResponseIntent.model_validate(response_intent)
    prompt = compose_response_intent(state)
    if prompt is None:
        raise RuntimeError("Refinement response intent did not compose.")
    return prompt
