from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from argus.agent_runtime.artifacts.drafts import draft_from_result_metadata
from argus.agent_runtime.recovery_messages import resolve_recovery_language
from argus.agent_runtime.stages.artifact_context import latest_run_id_for_action
from argus.api.chat.artifacts import result_reference_from_run
from argus.api.schemas import BacktestRun, ChatActionPayload

MISSING_REFINEMENT_RESULT_MESSAGE = (
    "I could not find the completed backtest to refine. Use Refine strategy from "
    "the latest result card, or run the strategy again."
)
MISSING_REFINEMENT_RESULT_MESSAGE_ES = (
    "No pude encontrar el backtest completado para ajustar la idea. Usa Ajustar "
    "idea desde la tarjeta de resultado más reciente, o ejecuta la estrategia "
    "de nuevo."
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
    language: str = "en",
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
        language=language,
        latest_run_id=latest_run_id,
        pending_strategy=pending_strategy,
        reference=reference,
    )
    assistant_text = _refinement_prompt(
        strategy=pending_strategy["strategy"],
        language=language,
    )
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
    language: str = "en",
) -> ResultActionTurn:
    assistant_text = (
        MISSING_REFINEMENT_RESULT_MESSAGE_ES
        if str(language or "").lower().startswith("es")
        else MISSING_REFINEMENT_RESULT_MESSAGE
    )
    metadata = {
        "conversation_mode": "result_review",
        "agent_runtime_stage_outcome": "ready_to_respond",
        "chat_action": action.model_dump(mode="python"),
    }
    final_payload = {
        "stage_outcome": "ready_to_respond",
        "assistant_response": assistant_text,
    }
    return ResultActionTurn(
        stage="interpret",
        assistant_text=assistant_text,
        metadata=metadata,
        final_payload=final_payload,
    )


def _refinement_response_intent(
    *,
    action: ChatActionPayload,
    language: str,
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
            "language": language,
        },
        "options": [],
    }


def _refinement_prompt(*, strategy: dict[str, Any], language: str) -> str:
    resolved_language = resolve_recovery_language(language)
    assets = strategy.get("asset_universe")
    asset_text = (
        ", ".join(str(asset) for asset in assets if str(asset).strip())
        if isinstance(assets, list)
        else ""
    )
    if resolved_language == "es-419":
        if asset_text:
            return (
                "¿Qué quieres cambiar, comparar o poner a prueba ahora "
                f"para {asset_text}?"
            )
        return "¿Qué quieres cambiar, comparar o poner a prueba ahora?"
    if asset_text:
        return f"What would you like to change, compare, or stress-test next for {asset_text}?"
    return "What would you like to change, compare, or stress-test next?"
