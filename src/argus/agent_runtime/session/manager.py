from __future__ import annotations

from copy import deepcopy

from argus.agent_runtime.state.models import (
    ArtifactReference,
    ConversationMessage,
    TaskSnapshot,
    ThreadState,
)


class InMemorySessionManager:
    def __init__(self) -> None:
        self._threads: dict[str, ThreadState] = {}

    def load_thread(self, *, user_id: str, thread_id: str) -> ThreadState:
        return self._get_or_create_thread(
            user_id=user_id,
            thread_id=thread_id,
        ).model_copy(deep=True)

    def append_message(
        self,
        *,
        user_id: str,
        thread_id: str,
        role: str,
        content: str,
    ) -> None:
        thread = self._get_or_create_thread(user_id=user_id, thread_id=thread_id)
        thread.message_history.append(
            ConversationMessage.model_validate(
                {
                    "role": role,
                    "content": content,
                }
            )
        )

    def save_thread_context(
        self,
        *,
        user_id: str,
        thread_id: str,
        latest_task_snapshot: TaskSnapshot | dict | None = None,
        artifact_references: list[ArtifactReference | dict] | None = None,
        thread_metadata: dict | None = None,
    ) -> None:
        thread = self._get_or_create_thread(user_id=user_id, thread_id=thread_id)
        if latest_task_snapshot is not None:
            thread.latest_task_snapshot = TaskSnapshot.model_validate(
                latest_task_snapshot
            )
        if artifact_references is not None:
            thread.artifact_references = [
                ArtifactReference.model_validate(reference)
                for reference in artifact_references
            ]
        if thread_metadata is not None:
            thread.thread_metadata = deepcopy(thread_metadata)

    def _get_or_create_thread(self, *, user_id: str, thread_id: str) -> ThreadState:
        key = self._thread_key(user_id=user_id, thread_id=thread_id)
        thread = self._threads.get(key)
        if thread is None:
            thread = ThreadState(thread_id=thread_id)
            self._threads[key] = thread
        return thread

    @staticmethod
    def _thread_key(*, user_id: str, thread_id: str) -> str:
        return f"{user_id}:{thread_id}"
