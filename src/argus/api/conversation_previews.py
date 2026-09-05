"""One bounded, owner-scoped read supplies every conversation preview surface."""

from collections.abc import Sequence

from loguru import logger

from argus.api import state as api_state
from argus.api.chat.legacy_onboarding_markers import is_legacy_onboarding_marker
from argus.api.schemas import ConversationPreview
from argus.domain.conversation_previews import (
    MAX_CONVERSATION_PREVIEWS,
    project_conversation_preview,
)


def conversation_previews(
    *, user_id: str, conversation_ids: Sequence[str]
) -> dict[str, ConversationPreview]:
    requested = list(dict.fromkeys(conversation_ids))
    if len(requested) > MAX_CONVERSATION_PREVIEWS:
        raise ValueError("At most 100 conversation previews may be read at once.")
    if not requested:
        return {}
    gateway = api_state.supabase_gateway
    if gateway is not None:
        read = getattr(gateway, "read_conversation_preview_messages", None)
        if read is None:
            return {key: ConversationPreview(kind="unavailable") for key in requested}
        try:
            rows = read(user_id=user_id, conversation_ids=requested)
        except Exception as exc:
            logger.warning(
                "Conversation preview batch unavailable",
                error_type=type(exc).__name__,
                conversation_count=len(requested),
            )
            return {key: ConversationPreview(kind="unavailable") for key in requested}
        indexed = {str(row["conversation_id"]): row for row in rows}
        return {
            key: project_conversation_preview(indexed[key])
            if key in indexed
            else ConversationPreview(kind="unavailable")
            for key in requested
        }
    store = api_state.store
    result = {}
    for key in requested:
        if store.conversation_owners.get(key) != user_id:
            result[key] = ConversationPreview(kind="unavailable")
            continue
        messages = [
            message
            for message in store.messages.get(key, [])
            if not (
                message.role == "user" and is_legacy_onboarding_marker(message.content)
            )
        ]
        latest = max(
            messages, key=lambda message: (message.created_at, message.id), default=None
        )
        result[key] = project_conversation_preview(
            latest.model_dump() if latest else None
        )
    return result
