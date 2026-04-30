from fastapi.testclient import TestClient

from argus.api import main as api_main
from argus.agent_runtime.graph.workflow import (
    WorkflowRoute,
    WorkflowStageOutcome,
    build_workflow,
    resolve_workflow_transition,
)
from argus.agent_runtime.runtime import build_workflow_input, run_agent_turn
from argus.agent_runtime.session.manager import InMemorySessionManager
from argus.agent_runtime.stages.execute import execute_stage
from argus.agent_runtime.state.models import (
    ArtifactReference,
    TaskSnapshot,
    UserState,
)
from argus.agent_runtime.tools.backtest_stub import StubBacktestTool


class FakeWorkflow:
    def __init__(self, response: dict) -> None:
        self._response = response

    def invoke(self, initial_state: dict) -> dict:
        return {
            **initial_state,
            **self._response,
        }


def test_workflow_requires_confirmation_before_execute() -> None:
    workflow = build_workflow()
    manager = InMemorySessionManager()
    user = UserState(user_id="u1", expertise_level="advanced")

    result = run_agent_turn(
        workflow=workflow,
        session_manager=manager,
        user=user,
        thread_id="thread-1",
        message=(
            "Backtest Tesla when RSI drops below 30 and exit above 55 "
            "over the last year"
        ),
    )

    assert result["stage_outcome"] == "await_approval"
    assert "Please confirm this backtest" in result["assistant_prompt"]


def test_runtime_keeps_thread_history_but_not_unapproved_confirmation_state() -> None:
    workflow = build_workflow()
    manager = InMemorySessionManager()
    user = UserState(user_id="u1", expertise_level="advanced")

    run_agent_turn(
        workflow=workflow,
        session_manager=manager,
        user=user,
        thread_id="thread-1",
        message=(
            "Backtest Tesla when RSI drops below 30 and exit above 55 "
            "over the last year"
        ),
    )

    thread = manager.load_thread(user_id=user.user_id, thread_id="thread-1")

    assert len(thread.message_history) == 2
    assert thread.message_history[0].role == "user"
    assert thread.message_history[1].role == "assistant"
    assert thread.latest_task_snapshot is not None
    assert thread.latest_task_snapshot.completed is False
    assert thread.latest_task_snapshot.confirmed_strategy_summary is None
    assert "confirmation_payload" not in thread.thread_metadata


def test_workflow_routes_under_specified_backtest_into_clarification() -> None:
    workflow = build_workflow()
    manager = InMemorySessionManager()
    user = UserState(user_id="u1", expertise_level="advanced")

    result = run_agent_turn(
        workflow=workflow,
        session_manager=manager,
        user=user,
        thread_id="thread-clarify",
        message="Backtest Tesla",
    )

    assert result["stage_outcome"] == "await_user_reply"
    assert result["requested_field"] == "entry_logic"
    assert "entry logic" in result["assistant_prompt"].lower()


def test_workflow_transition_ends_for_unsupported_capability_failure() -> None:
    tool = StubBacktestTool(
        responses=[
            {
                "success": False,
                "error_type": "unsupported_capability",
                "error_message": "Options backtests are not supported.",
                "retryable": False,
                "payload": None,
                "capability_context": {},
            }
        ]
    )
    state = build_workflow_input(
        session_manager=InMemorySessionManager(),
        user=UserState(user_id="u1", expertise_level="advanced"),
        thread_id="thread-unsupported",
        message="Run it",
    )
    state["run_state"].confirmation_payload = {"strategy": {"asset_universe": ["TSLA"]}}

    result = execute_stage(state=state["run_state"], tool=tool, max_retries=2)
    transition = resolve_workflow_transition(result=result)

    assert transition.outcome is WorkflowStageOutcome.NEEDS_CLARIFICATION
    assert transition.route is WorkflowRoute.END
    assert "supported backtest" in result.patch["assistant_prompt"]


def test_build_workflow_input_seeds_selected_context_and_keeps_run_state_fresh() -> None:
    manager = InMemorySessionManager()
    manager.append_message(
        user_id="u1",
        thread_id="thread-seeded",
        role="user",
        content="Previous question",
    )
    manager.save_thread_context(
        user_id="u1",
        thread_id="thread-seeded",
        latest_task_snapshot=TaskSnapshot(
            latest_task_type="results_explanation",
            completed=True,
        ),
        artifact_references=[
            ArtifactReference(
                artifact_kind="backtest_result",
                artifact_id="result-1",
            )
        ],
        thread_metadata={
            "latest_task_type": "results_explanation",
            "last_stage_outcome": "ready_to_respond",
            "ignored_key": "should_not_be_seeded",
        },
    )

    first_input = build_workflow_input(
        session_manager=manager,
        user=UserState(user_id="u1", expertise_level="advanced"),
        thread_id="thread-seeded",
        message="Explain the result",
    )
    first_input["run_state"].tool_call_records.append({"tool_name": "scratch"})
    first_input["run_state"].confirmation_payload = {"strategy": {"asset_universe": ["TSLA"]}}

    second_input = build_workflow_input(
        session_manager=manager,
        user=UserState(user_id="u1", expertise_level="advanced"),
        thread_id="thread-seeded",
        message="Explain the result again",
    )

    assert second_input["run_state"].tool_call_records == []
    assert second_input["run_state"].confirmation_payload is None
    assert second_input["selected_thread_metadata"] == {
        "latest_task_type": "results_explanation",
        "last_stage_outcome": "ready_to_respond",
    }
    assert len(second_input["artifact_references"]) == 1
    assert second_input["artifact_references"][0].artifact_id == "result-1"


def test_workflow_preserves_seeded_thread_metadata_and_artifacts() -> None:
    workflow = build_workflow()
    manager = InMemorySessionManager()
    manager.save_thread_context(
        user_id="u1",
        thread_id="thread-preserved",
        latest_task_snapshot=TaskSnapshot(
            latest_task_type="results_explanation",
            completed=True,
        ),
        artifact_references=[
            ArtifactReference(
                artifact_kind="backtest_result",
                artifact_id="result-2",
            )
        ],
        thread_metadata={
            "latest_task_type": "results_explanation",
            "last_stage_outcome": "ready_to_respond",
        },
    )

    seeded = build_workflow_input(
        session_manager=manager,
        user=UserState(user_id="u1", expertise_level="advanced"),
        thread_id="thread-preserved",
        message="Why did it do that?",
    )
    result = workflow.invoke(seeded)

    assert result["selected_thread_metadata"]["latest_task_type"] == "results_explanation"
    assert result["artifact_references"][0].artifact_id == "result-2"


def test_run_agent_turn_persists_artifact_references_on_write_back() -> None:
    manager = InMemorySessionManager()
    workflow = FakeWorkflow(
        {
            "stage_outcome": "ready_to_respond",
            "artifact_references": [
                ArtifactReference(
                    artifact_kind="backtest_result",
                    artifact_id="result-new",
                )
            ],
            "assistant_response": "Done.",
        }
    )

    run_agent_turn(
        workflow=workflow,
        session_manager=manager,
        user=UserState(user_id="u1", expertise_level="advanced"),
        thread_id="thread-artifacts",
        message="Explain the result",
    )

    thread = manager.load_thread(user_id="u1", thread_id="thread-artifacts")

    assert len(thread.artifact_references) == 1
    assert thread.artifact_references[0].artifact_id == "result-new"


def test_run_agent_turn_populates_and_preserves_snapshot_references() -> None:
    manager = InMemorySessionManager()
    manager.save_thread_context(
        user_id="u1",
        thread_id="thread-snapshot",
        latest_task_snapshot=TaskSnapshot(
            latest_task_type="backtest_execution",
            completed=True,
            latest_backtest_result_reference=ArtifactReference(
                artifact_kind="backtest_result",
                artifact_id="result-old",
            ),
        ),
        artifact_references=[
            ArtifactReference(
                artifact_kind="backtest_result",
                artifact_id="result-old",
            )
        ],
    )

    workflow_with_new_refs = FakeWorkflow(
        {
            "stage_outcome": "ready_to_respond",
            "artifact_references": [
                ArtifactReference(
                    artifact_kind="backtest_result",
                    artifact_id="result-new",
                ),
                ArtifactReference(
                    artifact_kind="collection_action",
                    artifact_id="collection-1",
                ),
            ],
            "assistant_response": "Saved.",
        }
    )
    run_agent_turn(
        workflow=workflow_with_new_refs,
        session_manager=manager,
        user=UserState(user_id="u1", expertise_level="advanced"),
        thread_id="thread-snapshot",
        message="Save that",
    )

    updated_thread = manager.load_thread(user_id="u1", thread_id="thread-snapshot")
    assert updated_thread.latest_task_snapshot is not None
    assert (
        updated_thread.latest_task_snapshot.latest_backtest_result_reference.artifact_id
        == "result-new"
    )
    assert (
        updated_thread.latest_task_snapshot.latest_collection_action_reference.artifact_id
        == "collection-1"
    )

    workflow_without_new_refs = FakeWorkflow(
        {
            "stage_outcome": "await_user_reply",
            "assistant_prompt": "Can you clarify that?",
        }
    )
    run_agent_turn(
        workflow=workflow_without_new_refs,
        session_manager=manager,
        user=UserState(user_id="u1", expertise_level="advanced"),
        thread_id="thread-snapshot",
        message="What next?",
    )

    preserved_thread = manager.load_thread(user_id="u1", thread_id="thread-snapshot")
    assert preserved_thread.latest_task_snapshot is not None
    assert (
        preserved_thread.latest_task_snapshot.latest_backtest_result_reference.artifact_id
        == "result-new"
    )
    assert (
        preserved_thread.latest_task_snapshot.latest_collection_action_reference.artifact_id
        == "collection-1"
    )


def test_run_agent_turn_marks_ready_to_respond_turn_as_completed() -> None:
    manager = InMemorySessionManager()
    workflow = FakeWorkflow(
        {
            "stage_outcome": "ready_to_respond",
            "assistant_response": "Here is what happened.",
        }
    )

    run_agent_turn(
        workflow=workflow,
        session_manager=manager,
        user=UserState(user_id="u1", expertise_level="advanced"),
        thread_id="thread-completed",
        message="Explain the result",
    )

    thread = manager.load_thread(user_id="u1", thread_id="thread-completed")
    assert thread.latest_task_snapshot is not None
    assert thread.latest_task_snapshot.completed is True


def test_run_agent_turn_clears_resolved_unresolved_follow_up() -> None:
    manager = InMemorySessionManager()
    manager.save_thread_context(
        user_id="u1",
        thread_id="thread-follow-up",
        latest_task_snapshot=TaskSnapshot(
            latest_task_type="conversation_followup",
            completed=False,
            last_unresolved_follow_up="Can you clarify whether this is a new idea?",
        ),
    )
    workflow = FakeWorkflow(
        {
            "stage_outcome": "ready_to_respond",
            "assistant_response": "That clarifies it.",
        }
    )

    run_agent_turn(
        workflow=workflow,
        session_manager=manager,
        user=UserState(user_id="u1", expertise_level="advanced"),
        thread_id="thread-follow-up",
        message="Continue with the current idea.",
    )

    thread = manager.load_thread(user_id="u1", thread_id="thread-follow-up")
    assert thread.latest_task_snapshot is not None
    assert thread.latest_task_snapshot.last_unresolved_follow_up is None


def test_build_workflow_input_bounds_recent_thread_history() -> None:
    manager = InMemorySessionManager()
    for index in range(8):
        manager.append_message(
            user_id="u1",
            thread_id="thread-history",
            role="user",
            content=f"message-{index}",
        )

    seeded = build_workflow_input(
        session_manager=manager,
        user=UserState(user_id="u1", expertise_level="advanced"),
        thread_id="thread-history",
        message="Latest request",
    )

    recent_history = seeded["run_state"].recent_thread_history
    assert len(recent_history) == 6
    assert [message.content for message in recent_history] == [
        "message-2",
        "message-3",
        "message-4",
        "message-5",
        "message-6",
        "message-7",
    ]


def test_internal_agent_runtime_turn_endpoint_returns_confirmation_ready_result(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        api_main,
        "agent_runtime_session_manager",
        InMemorySessionManager(),
    )
    monkeypatch.setattr(
        api_main,
        "agent_runtime_workflow",
        build_workflow(),
    )
    client = TestClient(api_main.app)

    response = client.post(
        "/internal/agent-runtime/turn",
        json={
            "user_id": "u1",
            "thread_id": "thread-internal",
            "message": (
                "Backtest Tesla over the last 2 years when RSI drops below 30 "
                "and exit above 55"
            ),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["stage_outcome"] == "await_approval"
    assert "confirmation_payload" in payload
    assert (
        payload["confirmation_payload"]["strategy"]["asset_universe"]
        == ["TSLA"]
    )
