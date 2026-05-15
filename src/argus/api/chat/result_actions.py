from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from argus.agent_runtime.stages.artifact_context import (
    latest_run_id_for_action,
    strategy_from_result_reference,
)
from argus.api.chat.artifacts import result_reference_from_run
from argus.api.schemas import BacktestRun, ChatActionPayload

REFINE_STRATEGY_PROMPT = "What would you like to change about this strategy?"
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
    strategy = strategy_from_result_reference(reference)
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
    metadata = {
        "conversation_mode": "setup",
        "agent_runtime_stage_outcome": "await_user_reply",
        "chat_action": action.model_dump(mode="python"),
        "pending_strategy": pending_strategy,
        "source_result_run_id": run.id,
        "source_result_strategy_id": run.strategy_id,
        "source_result_conversation_id": run.conversation_id,
    }
    final_payload = {
        "stage_outcome": "await_user_reply",
        "assistant_response": REFINE_STRATEGY_PROMPT,
        "pending_strategy": pending_strategy,
        "latest_run_id": latest_run_id,
        "source_result_run_id": run.id,
    }
    return ResultActionTurn(
        stage="interpret",
        assistant_text=REFINE_STRATEGY_PROMPT,
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
