"""Recorded smoke conversations put back into the evidence API's memory store.

The evidence API keeps conversations in memory, so a restart loses every one the
browser walk opens. Each record in the folder is restored as it was stored: the
conversation under its recorded id, each question as the user's message, and
each reply with its recorded id, text and metadata. Nothing is regenerated and
no model is called.
"""

from __future__ import annotations

import json
from pathlib import Path


def restore_recorded_turns(folder: Path, *, owner: str) -> dict[str, str]:
    """Restore every record under ``folder`` for ``owner``; returns label to id."""
    from argus.api import state as api_state
    from argus.api.message_store import create_message
    from argus.api.schemas import Conversation
    from argus.domain.store import utcnow

    restored: dict[str, str] = {}
    for path in sorted(folder.glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        conversation_id = record.get("conversation_id")
        turns = record.get("turns") or []
        if not conversation_id or not turns:
            continue
        if conversation_id in api_state.store.conversations:
            continue
        now = utcnow()
        api_state.store.conversations[conversation_id] = Conversation(
            id=conversation_id,
            title=str(turns[0].get("message") or path.stem)[:60],
            title_source="user_renamed",
            language=record.get("language"),
            created_at=now,
            updated_at=now,
        )
        api_state.store.conversation_owners[conversation_id] = owner
        api_state.store.messages[conversation_id] = []
        for turn in turns:
            create_message(
                user_id=owner,
                conversation_id=conversation_id,
                role="user",
                content=str(turn.get("message") or ""),
            )
            create_message(
                user_id=owner,
                conversation_id=conversation_id,
                role="assistant",
                content=str((turn.get("summary") or {}).get("content") or ""),
                metadata=turn.get("metadata") or {},
                message_id=turn.get("message_id"),
            )
        restored[path.stem] = conversation_id
    return restored
