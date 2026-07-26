from __future__ import annotations

from argus.agent_runtime.recovery_messages import recovery_message
from argus.agent_runtime.response_language import response_language_instruction
from argus.agent_runtime.stages.interpret_types import (
    InterpretDecision,
    StageResult,
)
from argus.llm.openrouter import invoke_openrouter_chat_completion


async def discovery_stage_result_if_applicable(
    *,
    decision: InterpretDecision,
    current_user_message: str,
    language: str,
) -> StageResult | None:
    """Own every asset_discovery turn; other turns pass through untouched.

    The typed act is the single routing condition. Search execution stays
    behind the grounded-discovery flag; without it this composer answers with
    honest typed recovery and never constructs a provider.
    """

    if decision.semantic_turn_act != "asset_discovery":
        return None
    return await _unavailable_result(
        decision=decision,
        current_user_message=current_user_message,
        language=language,
    )


async def _unavailable_result(
    *,
    decision: InterpretDecision,
    current_user_message: str,
    language: str,
) -> StageResult:
    voiced = await _voiced_discovery_unavailable(
        current_user_message=current_user_message,
        language=language,
    )
    assistant_response = voiced or recovery_message(
        "discovery_unavailable", retryable=False
    )
    return StageResult(
        outcome="ready_to_respond",
        decision=decision,
        stage_patch={
            "assistant_response": assistant_response,
            "recovery": {"code": "discovery_unavailable", "retryable": False},
        },
    )


async def _voiced_discovery_unavailable(
    *,
    current_user_message: str,
    language: str,
) -> str | None:
    message = current_user_message.strip()
    if not message:
        return None
    language_instruction = response_language_instruction(language)
    messages = [
        {
            "role": "system",
            "content": (
                "You are Argus, a chat-first investing experimentation "
                "assistant. The user asked you to find or discover assets, but "
                "grounded source-backed discovery is not available right now. "
                f"{language_instruction} "
                "In two or three warm plain sentences: say honestly that you "
                "cannot look up current source-backed candidates yet, that you "
                "will not guess names from memory, and invite them to name a "
                "symbol or company they already have in mind so you can test "
                "it. Their conversation and any current setup are unchanged. "
                "Do not list any asset names, do not mention providers or "
                "internal tools, and do not give investment advice."
            ),
        },
        {"role": "user", "content": message},
    ]
    try:
        response = await invoke_openrouter_chat_completion(
            task="chat_composer",
            messages=messages,
        )
    except Exception:
        return None
    cleaned = str(response or "").strip()
    return cleaned or None
