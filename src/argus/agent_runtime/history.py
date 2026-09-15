"""One history window: bounded shared context plus recent receiver turns."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from argus.agent_runtime.state.models import ConversationMessage
from argus.domain.public_excerpt_forks import FORK_TEXT_BYTES


def select_thread_history(
    messages: Iterable[ConversationMessage | dict[str, Any]],
    *,
    recent_limit: int = 6,
) -> list[ConversationMessage]:
    history = [
        message
        if isinstance(message, ConversationMessage)
        else ConversationMessage.model_validate(message)
        for message in messages
    ]
    shared_bytes = sum(
        len(message.content.encode("utf-8"))
        for message in history
        if message.shared_context
    )
    if shared_bytes > FORK_TEXT_BYTES:
        raise ValueError("shared history exceeds its import bound")
    ordinary_indices = [
        index for index, message in enumerate(history) if not message.shared_context
    ]
    recent = set(ordinary_indices[-recent_limit:]) if recent_limit > 0 else set()
    return [
        message
        for index, message in enumerate(history)
        if message.shared_context or index in recent
    ]
