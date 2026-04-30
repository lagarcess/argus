from argus.agent_runtime.session.manager import InMemorySessionManager
from argus.agent_runtime.state.models import ArtifactReference, TaskSnapshot, UserState


def test_session_manager_isolates_threads_for_same_user() -> None:
    manager = InMemorySessionManager()
    user = UserState(user_id="u1", display_name="Sarah")

    manager.append_message(
        user_id=user.user_id,
        thread_id="thread-a",
        role="user",
        content="Backtest Apple",
    )
    manager.append_message(
        user_id=user.user_id,
        thread_id="thread-b",
        role="user",
        content="Backtest Tesla",
    )

    thread_a = manager.load_thread(user_id=user.user_id, thread_id="thread-a")
    thread_b = manager.load_thread(user_id=user.user_id, thread_id="thread-b")

    assert thread_a.message_history[0].content == "Backtest Apple"
    assert thread_b.message_history[0].content == "Backtest Tesla"


def test_load_thread_returns_copy_and_persists_only_explicit_writes() -> None:
    manager = InMemorySessionManager()
    manager.append_message(
        user_id="u1",
        thread_id="thread-1",
        role="user",
        content="Backtest Tesla",
    )

    loaded = manager.load_thread(user_id="u1", thread_id="thread-1")
    loaded.message_history.append({"role": "assistant", "content": "draft reply"})

    reloaded = manager.load_thread(user_id="u1", thread_id="thread-1")

    assert len(reloaded.message_history) == 1
    assert reloaded.message_history[0].content == "Backtest Tesla"


def test_save_thread_context_updates_durable_snapshot_and_artifacts() -> None:
    manager = InMemorySessionManager()

    manager.save_thread_context(
        user_id="u1",
        thread_id="thread-1",
        latest_task_snapshot=TaskSnapshot(
            latest_task_type="backtest_execution",
            completed=True,
        ),
        artifact_references=[
            ArtifactReference(
                artifact_kind="backtest_result",
                artifact_id="result-1",
            )
        ],
        thread_metadata={"latest_task_type": "backtest_execution"},
    )

    thread = manager.load_thread(user_id="u1", thread_id="thread-1")

    assert thread.latest_task_snapshot is not None
    assert thread.latest_task_snapshot.latest_task_type == "backtest_execution"
    assert thread.latest_task_snapshot.completed is True
    assert thread.artifact_references[0].artifact_id == "result-1"
    assert thread.thread_metadata["latest_task_type"] == "backtest_execution"
