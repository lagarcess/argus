from __future__ import annotations

from argus.llm.openrouter import invoke_openrouter_chat_completion


async def compose_active_confirmation_interpreter_recovery(
    *,
    current_user_message: str,
    setup_phrase: str,
    assumptions_response: str | None,
    action_guidance: str,
) -> str | None:
    """Compose a user-facing recovery near an active confirmation artifact.

    The structured interpreter owns semantic routing. This helper is only used
    when that interpreter is unavailable and a visible confirmation is still
    present, so the fallback can answer the user's turn without pretending every
    follow-up is an assumption question.
    """

    message = current_user_message.strip()
    if not message:
        return None
    facts = [
        f"Current setup: {setup_phrase}.",
        f"Visible-card guidance: {action_guidance}",
    ]
    if assumptions_response:
        facts.append(f"Visible-card assumptions: {assumptions_response}")
    messages = [
        {
            "role": "system",
            "content": (
                "You are Argus, a chat-first investing experimentation assistant. "
                "The structured interpreter is unavailable for this turn, but a "
                "confirmation card is visible and still ready. Answer the user's "
                "message directly in warm, plain English. If they ask about the "
                "visible card, use only the supplied card facts. If they ask a "
                "general educational or side question, answer that question and "
                "mention the confirmation only briefly when useful. Do not expose "
                "runtime internals, do not claim a hidden artifact exists, do not "
                "invent execution facts, and do not give investment advice."
            ),
        },
        {"role": "system", "content": "\n".join(facts)},
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
