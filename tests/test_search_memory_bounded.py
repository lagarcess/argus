from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from typing import Any

import pytest
from argus.api import memory_search_candidates, search_assembly
from argus.api import state as api_state
from argus.api.schemas import Conversation, DecisionNote


@pytest.fixture(autouse=True)
def _reset_memory_store() -> None:
    api_state.store.reset()


class _LockAwareMessage:
    role = "user"

    def __init__(
        self,
        *,
        conversation_id: str,
        message_id: str,
        content: str,
        lock: Lock,
    ) -> None:
        self.conversation_id = conversation_id
        self.id = message_id
        self.content = content
        self.created_at = datetime.now(timezone.utc)
        self._lock = lock

    def model_dump(self) -> dict[str, Any]:
        acquired = self._lock.acquire(blocking=False)
        assert acquired, "memory search copied a message under the finalization lock"
        self._lock.release()
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at,
            "metadata": None,
        }


def _owned_conversation(*, conversation_id: str, title: str) -> None:
    now = datetime.now(timezone.utc)
    user = api_state.store.get_or_create_dev_user()
    api_state.store.conversations[conversation_id] = Conversation(
        id=conversation_id,
        title=title,
        created_at=now,
        updated_at=now,
        language="en",
    )
    api_state.store.conversation_owners[conversation_id] = user.id


def test_memory_search_bounds_message_candidates_and_copies_outside_finalization_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = api_state.store.get_or_create_dev_user()
    finalization_lock = Lock()
    monkeypatch.setattr(
        api_state.store,
        "backtest_finalization_lock",
        finalization_lock,
    )
    captured_messages: list[dict[str, Any]] = []
    index_builds = 0

    for conversation_index in range(40):
        conversation_id = f"conversation-{conversation_index}"
        _owned_conversation(
            conversation_id=conversation_id,
            title=f"Unrelated memory {conversation_index}",
        )
        api_state.store.messages[conversation_id] = [
            _LockAwareMessage(
                conversation_id=conversation_id,
                message_id=f"message-{conversation_index}-{message_index}",
                content=(
                    "needle in the transcript"
                    if conversation_index == 39 and message_index == 9
                    else f"ordinary transcript text {message_index}"
                ),
                lock=finalization_lock,
            )
            for message_index in range(10)
        ]

    def _capture_rows(**kwargs: Any) -> list[search_assembly.ScoredSearchItem]:
        captured_messages.extend(kwargs["messages"])
        return []

    monkeypatch.setattr(search_assembly, "_project_rows", _capture_rows)
    monkeypatch.setattr(search_assembly, "project_asset_rollup", lambda **_: None)
    original_builder = memory_search_candidates._build_memory_search_index

    def _counted_builder(**kwargs: Any) -> Any:
        nonlocal index_builds
        index_builds += 1
        return original_builder(**kwargs)

    monkeypatch.setattr(
        memory_search_candidates,
        "_build_memory_search_index",
        _counted_builder,
    )

    search_assembly.memory_search_read(
        user=user,
        query="needle",
        source_limit=2,
    )
    search_assembly.memory_search_read(
        user=user,
        query="transcript",
        source_limit=2,
    )

    assert index_builds == 1
    assert captured_messages[0]["id"] == "message-39-9"
    assert len(captured_messages) <= 21


def test_memory_ledger_counts_all_distinct_matches_beyond_presentation_cap() -> None:
    user = api_state.store.get_or_create_dev_user()
    now = datetime.now(timezone.utc)

    for index in range(600):
        conversation_id = f"conversation-ledger-{index:04d}"
        decision_note_id = f"decision-ledger-{index:04d}"
        api_state.store.conversations[conversation_id] = Conversation(
            id=conversation_id,
            title=f"Needle title {index}",
            last_message_preview=f"Needle preview {index}",
            created_at=now,
            updated_at=now,
            language="en",
        )
        api_state.store.conversation_owners[conversation_id] = user.id
        api_state.store.decision_notes[decision_note_id] = DecisionNote(
            id=decision_note_id,
            idea_id=f"idea-{index}",
            idea_version_id=f"version-{index}",
            evidence_artifact_id=f"artifact-{index}",
            source_conversation_id=conversation_id,
            decision_state="watching",
            note="Separate judgment.",
            created_at=now,
            updated_at=now,
        )
        api_state.store.decision_note_owners[decision_note_id] = user.id

    snapshot = memory_search_candidates.bounded_memory_search_snapshot(
        store=api_state.store,
        user=user,
        query="needle",
        source_limit=1,
        include_conversation_rows=True,
        include_ledger_groups=True,
    )

    assert snapshot.ledger_counts == {
        "promising": 0,
        "watching": 600,
        "rejected": 0,
        "revisit_later": 0,
    }
    assert len(snapshot.conversations) <= 10
