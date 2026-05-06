from __future__ import annotations

from copy import deepcopy
from enum import Enum
from typing import Any, TypedDict, cast

from argus.agent_runtime.capabilities.contract import (
    CapabilityContract,
    build_default_capability_contract,
)
from argus.agent_runtime.stages.clarify import (
    StructuredClarificationGenerator,
    clarify_stage_async,
)
from argus.agent_runtime.stages.confirm import confirm_stage
from argus.agent_runtime.stages.execute import execute_stage_async
from argus.agent_runtime.stages.explain import explain_stage_async
from argus.agent_runtime.stages.interpret import (
    StageResult,
    StructuredInterpreter,
    interpret_stage_async,
)
from argus.agent_runtime.stages.next_step import next_step_stage_async
from argus.agent_runtime.state.models import (
    ArtifactReference,
    RunState,
    TaskSnapshot,
    UserState,
)
from langgraph.graph import END, StateGraph


class WorkflowNode(str, Enum):
    INTERPRET = "interpret"
    CLARIFY = "clarify"
    CONFIRM = "confirm"
    EXECUTE = "execute"
    EXPLAIN = "explain"
    NEXT_STEP = "next_step"


class WorkflowRoute(str, Enum):
    CLARIFY = "clarify"
    CONFIRM = "confirm"
    EXECUTE = "execute"
    EXPLAIN = "explain"
    NEXT_STEP = "next_step"
    END = "end"


class WorkflowStageOutcome(str, Enum):
    NEEDS_CLARIFICATION = "needs_clarification"
    READY_FOR_CONFIRMATION = "ready_for_confirmation"
    AWAIT_USER_REPLY = "await_user_reply"
    AWAIT_APPROVAL = "await_approval"
    APPROVED_FOR_EXECUTION = "approved_for_execution"
    EXECUTION_SUCCEEDED = "execution_succeeded"
    EXECUTION_FAILED_RECOVERABLY = "execution_failed_recoverably"
    EXECUTION_FAILED_TERMINALLY = "execution_failed_terminally"
    READY_TO_RESPOND = "ready_to_respond"
    END_RUN = "end_run"


class WorkflowState(TypedDict, total=False):
    run_state: RunState
    user: UserState
    latest_task_snapshot: TaskSnapshot | None
    selected_thread_metadata: dict[str, Any]
    artifact_references: list[ArtifactReference]
    stage_outcome: WorkflowStageOutcome
    assistant_prompt: str | None
    assistant_response: str | None
    requested_field: str | None
    optional_parameter_choices: list[str]
    confirmation_payload: dict[str, Any]
    failure_classification: str | None
    final_response_payload: dict[str, Any]
    next_actions: list[str]


RUN_STATE_FIELD_NAMES = frozenset(RunState.model_fields)


class DefaultBacktestTool:
    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        del payload
        return deepcopy(
            {
                "success": True,
                "payload": {
                    "total_return": 0.14,
                    "benchmark_return": 0.09,
                },
                "error_type": None,
                "error_message": None,
                "retryable": False,
                "capability_context": {},
            }
        )


def build_workflow(
    *,
    contract: CapabilityContract | None = None,
    tool: Any | None = None,
    max_retries: int = 2,
    structured_interpreter: StructuredInterpreter | None = None,
    clarification_generator: StructuredClarificationGenerator | None = None,
    checkpointer: Any | None = None,
):
    active_contract = contract or build_default_capability_contract()
    active_tool = tool or DefaultBacktestTool()

    async def interpret_node(state: WorkflowState) -> WorkflowState:
        return await _interpret_node_async(
            state,
            structured_interpreter=structured_interpreter,
        )

    async def clarify_node(state: WorkflowState) -> WorkflowState:
        return await _clarify_node_async(
            state,
            contract=active_contract,
            clarification_generator=clarification_generator,
        )

    async def execute_node(state: WorkflowState) -> WorkflowState:
        return await _execute_node_async(
            state,
            tool=active_tool,
            max_retries=max_retries,
        )

    graph = StateGraph(WorkflowState)
    graph.add_node(WorkflowNode.INTERPRET.value, interpret_node)
    graph.add_node(WorkflowNode.CLARIFY.value, clarify_node)
    graph.add_node(
        WorkflowNode.CONFIRM.value,
        lambda state: _apply_stage_result(
            state,
            confirm_stage(
                state=_run_state(state),
                contract=active_contract,
            ),
        ),
    )
    graph.add_node(WorkflowNode.EXECUTE.value, execute_node)
    graph.add_node(WorkflowNode.EXPLAIN.value, _explain_node_async)
    graph.add_node(WorkflowNode.NEXT_STEP.value, _next_step_node_async)

    graph.set_entry_point(WorkflowNode.INTERPRET.value)
    graph.add_conditional_edges(
        WorkflowNode.INTERPRET.value,
        _route_from_stage_outcome,
        {
            WorkflowRoute.CLARIFY.value: WorkflowNode.CLARIFY.value,
            WorkflowRoute.CONFIRM.value: WorkflowNode.CONFIRM.value,
            WorkflowRoute.EXECUTE.value: WorkflowNode.EXECUTE.value,
            WorkflowRoute.END.value: END,
        },
    )
    graph.add_conditional_edges(
        WorkflowNode.CLARIFY.value,
        _route_from_stage_outcome,
        {
            WorkflowRoute.CONFIRM.value: WorkflowNode.CONFIRM.value,
            WorkflowRoute.END.value: END,
        },
    )
    graph.add_conditional_edges(
        WorkflowNode.CONFIRM.value,
        _route_from_stage_outcome,
        {
            WorkflowRoute.CLARIFY.value: WorkflowNode.CLARIFY.value,
            WorkflowRoute.EXECUTE.value: WorkflowNode.EXECUTE.value,
            WorkflowRoute.END.value: END,
        },
    )
    graph.add_conditional_edges(
        WorkflowNode.EXECUTE.value,
        _route_from_stage_outcome,
        {
            WorkflowRoute.EXPLAIN.value: WorkflowNode.EXPLAIN.value,
            WorkflowRoute.END.value: END,
        },
    )
    graph.add_conditional_edges(
        WorkflowNode.EXPLAIN.value,
        _route_from_explain_outcome,
        {
            WorkflowRoute.NEXT_STEP.value: WorkflowNode.NEXT_STEP.value,
            WorkflowRoute.END.value: END,
        },
    )
    graph.add_edge(WorkflowNode.NEXT_STEP.value, END)

    return graph.compile(checkpointer=checkpointer)


async def _interpret_node_async(
    state: WorkflowState,
    *,
    structured_interpreter: StructuredInterpreter | None,
) -> WorkflowState:
    return _apply_stage_result(
        state,
        await interpret_stage_async(
            state=_run_state(state),
            user=_user(state),
            latest_task_snapshot=state.get("latest_task_snapshot"),
            structured_interpreter=structured_interpreter,
        ),
    )


async def _clarify_node_async(
    state: WorkflowState,
    *,
    contract: CapabilityContract,
    clarification_generator: StructuredClarificationGenerator | None,
) -> WorkflowState:
    return _apply_stage_result(
        state,
        await clarify_stage_async(
            state=_run_state(state),
            contract=contract,
            clarification_generator=clarification_generator,
            language=_user(state).language_preference,
        ),
    )


async def _execute_node_async(
    state: WorkflowState,
    *,
    tool: Any,
    max_retries: int,
) -> WorkflowState:
    return _apply_stage_result(
        state,
        await execute_stage_async(
            state=_run_state(state),
            tool=tool,
            max_retries=max_retries,
        ),
    )


async def _explain_node_async(state: WorkflowState) -> WorkflowState:
    return _apply_stage_result(
        state,
        await explain_stage_async(state=_run_state(state)),
    )


async def _next_step_node_async(state: WorkflowState) -> WorkflowState:
    return _apply_stage_result(
        state,
        await next_step_stage_async(state=_run_state(state)),
    )


def _apply_stage_result(
    state: WorkflowState,
    result: StageResult,
) -> WorkflowState:
    outcome = WorkflowStageOutcome(result.outcome)
    run_state = _patched_run_state(
        run_state=_run_state(state),
        patch=result.patch,
    )
    workflow_state: WorkflowState = {
        **state,
        "run_state": run_state,
        "stage_outcome": outcome,
    }

    for key, value in result.patch.items():
        if key in RUN_STATE_FIELD_NAMES:
            continue
        workflow_state[key] = value

    artifact_references = _resolve_artifact_references(workflow_state)
    workflow_state["artifact_references"] = artifact_references
    workflow_state["latest_task_snapshot"] = _build_task_snapshot(
        run_state=run_state,
        stage_outcome=outcome,
        prior_task_snapshot=state.get("latest_task_snapshot"),
        artifact_references=artifact_references,
    )
    workflow_state["selected_thread_metadata"] = _build_thread_metadata(
        run_state=run_state,
        stage_outcome=outcome,
    )

    return workflow_state


def _patched_run_state(*, run_state: RunState, patch: dict[str, Any]) -> RunState:
    payload = run_state.model_dump(mode="python")
    for key, value in patch.items():
        if key in RUN_STATE_FIELD_NAMES:
            payload[key] = value
    return RunState.model_validate(payload)


def _route_from_stage_outcome(state: WorkflowState) -> str:
    outcome = WorkflowStageOutcome(state["stage_outcome"])
    failure_classification = state.get("failure_classification")

    if outcome is WorkflowStageOutcome.NEEDS_CLARIFICATION:
        if failure_classification == "unsupported_capability":
            return WorkflowRoute.END.value
        return WorkflowRoute.CLARIFY.value
    if outcome is WorkflowStageOutcome.READY_FOR_CONFIRMATION:
        return WorkflowRoute.CONFIRM.value
    if outcome is WorkflowStageOutcome.APPROVED_FOR_EXECUTION:
        return WorkflowRoute.EXECUTE.value
    if outcome is WorkflowStageOutcome.EXECUTION_SUCCEEDED:
        return WorkflowRoute.EXPLAIN.value
    return WorkflowRoute.END.value


def _route_from_explain_outcome(state: WorkflowState) -> str:
    outcome = WorkflowStageOutcome(state["stage_outcome"])
    if outcome is WorkflowStageOutcome.READY_TO_RESPOND:
        return WorkflowRoute.NEXT_STEP.value
    return WorkflowRoute.END.value


def _run_state(state: WorkflowState) -> RunState:
    return cast(RunState, state["run_state"])


def _user(state: WorkflowState) -> UserState:
    return cast(UserState, state["user"])


def _build_task_snapshot(
    *,
    run_state: RunState,
    stage_outcome: Any,
    prior_task_snapshot: TaskSnapshot | None,
    artifact_references: list[ArtifactReference],
) -> TaskSnapshot:
    stage_outcome_value = getattr(stage_outcome, "value", stage_outcome)
    completed_outcomes = {"execution_succeeded", "ready_to_respond", "end_run"}
    latest_backtest_reference = _latest_artifact_reference(
        artifact_references=artifact_references,
        artifact_kind="backtest_result",
    )
    latest_collection_reference = _latest_artifact_reference(
        artifact_references=artifact_references,
        artifact_kind="collection_action",
    )
    pending_strategy_summary = (
        run_state.candidate_strategy_draft
        if stage_outcome_value in {"await_user_reply", "await_approval"}
        else (
            prior_task_snapshot.pending_strategy_summary
            if prior_task_snapshot is not None
            and stage_outcome_value not in completed_outcomes
            else None
        )
    )
    return TaskSnapshot(
        latest_task_type=run_state.intent,
        completed=stage_outcome_value in completed_outcomes,
        pending_strategy_summary=pending_strategy_summary,
        confirmed_strategy_summary=(
            run_state.candidate_strategy_draft
            if stage_outcome_value in completed_outcomes
            else (
                prior_task_snapshot.confirmed_strategy_summary
                if prior_task_snapshot is not None
                else None
            )
        ),
        latest_backtest_result_reference=(
            latest_backtest_reference
            or (
                prior_task_snapshot.latest_backtest_result_reference
                if prior_task_snapshot is not None
                else None
            )
        ),
        latest_collection_action_reference=(
            latest_collection_reference
            or (
                prior_task_snapshot.latest_collection_action_reference
                if prior_task_snapshot is not None
                else None
            )
        ),
        last_unresolved_follow_up=(
            run_state.user_goal_summary
            if stage_outcome_value in {"await_user_reply", "await_approval"}
            else None
        ),
    )


def _build_thread_metadata(
    *,
    run_state: RunState,
    stage_outcome: Any,
) -> dict[str, Any]:
    stage_outcome_value = getattr(stage_outcome, "value", stage_outcome)
    return {
        "latest_task_type": run_state.intent,
        "last_stage_outcome": stage_outcome_value,
    }


def _resolve_artifact_references(state: WorkflowState) -> list[ArtifactReference]:
    raw_references = state.get("artifact_references", [])
    references: list[ArtifactReference] = []
    for reference in raw_references:
        references.append(ArtifactReference.model_validate(reference))
    return references


def _latest_artifact_reference(
    *,
    artifact_references: list[ArtifactReference],
    artifact_kind: str,
) -> ArtifactReference | None:
    for reference in reversed(artifact_references):
        if reference.artifact_kind == artifact_kind:
            return reference.model_copy(deep=True)
    return None
