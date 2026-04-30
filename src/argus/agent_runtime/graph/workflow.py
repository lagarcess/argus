from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypedDict, cast

from langgraph.graph import END, StateGraph

from argus.agent_runtime.capabilities.contract import (
    CapabilityContract,
    build_default_capability_contract,
)
from argus.agent_runtime.stages.clarify import clarify_stage
from argus.agent_runtime.stages.confirm import confirm_stage
from argus.agent_runtime.stages.execute import execute_stage
from argus.agent_runtime.stages.explain import explain_stage
from argus.agent_runtime.stages.interpret import (
    StageResult,
    StructuredArbitrator,
    interpret_stage,
)
from argus.agent_runtime.stages.next_step import next_step_stage
from argus.agent_runtime.state.models import (
    ArtifactReference,
    RunState,
    TaskSnapshot,
    UserState,
)


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


@dataclass(frozen=True)
class WorkflowTransition:
    outcome: WorkflowStageOutcome
    route: WorkflowRoute


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
    route: WorkflowRoute


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
    structured_arbitrator: StructuredArbitrator | None = None,
):
    active_contract = contract or build_default_capability_contract()
    active_tool = tool or DefaultBacktestTool()

    graph = StateGraph(WorkflowState)
    graph.add_node(
        WorkflowNode.INTERPRET.value,
        lambda state: _interpret_node(
            state,
            structured_arbitrator=structured_arbitrator,
        ),
    )
    graph.add_node(
        WorkflowNode.CLARIFY.value,
        lambda state: _apply_stage_result(
            state,
            clarify_stage(
                state=_run_state(state),
                contract=active_contract,
            ),
        ),
    )
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
    graph.add_node(
        WorkflowNode.EXECUTE.value,
        lambda state: _apply_stage_result(
            state,
            execute_stage(
                state=_run_state(state),
                tool=active_tool,
                max_retries=max_retries,
            ),
        ),
    )
    graph.add_node(
        WorkflowNode.EXPLAIN.value,
        lambda state: _apply_stage_result(
            state,
            explain_stage(state=_run_state(state)),
        ),
    )
    graph.add_node(
        WorkflowNode.NEXT_STEP.value,
        lambda state: _apply_stage_result(
            state,
            next_step_stage(state=_run_state(state)),
        ),
    )

    graph.set_entry_point(WorkflowNode.INTERPRET.value)
    graph.add_conditional_edges(
        WorkflowNode.INTERPRET.value,
        _route_from_state,
        {
            WorkflowRoute.CLARIFY.value: WorkflowNode.CLARIFY.value,
            WorkflowRoute.CONFIRM.value: WorkflowNode.CONFIRM.value,
        },
    )
    graph.add_conditional_edges(
        WorkflowNode.CLARIFY.value,
        _route_from_state,
        {
            WorkflowRoute.CONFIRM.value: WorkflowNode.CONFIRM.value,
            WorkflowRoute.END.value: END,
        },
    )
    graph.add_conditional_edges(
        WorkflowNode.CONFIRM.value,
        _route_from_state,
        {
            WorkflowRoute.CLARIFY.value: WorkflowNode.CLARIFY.value,
            WorkflowRoute.EXECUTE.value: WorkflowNode.EXECUTE.value,
            WorkflowRoute.END.value: END,
        },
    )
    graph.add_conditional_edges(
        WorkflowNode.EXECUTE.value,
        _route_from_state,
        {
            WorkflowRoute.EXPLAIN.value: WorkflowNode.EXPLAIN.value,
            WorkflowRoute.END.value: END,
        },
    )
    graph.add_conditional_edges(
        WorkflowNode.EXPLAIN.value,
        _route_from_state,
        {
            WorkflowRoute.NEXT_STEP.value: WorkflowNode.NEXT_STEP.value,
            WorkflowRoute.END.value: END,
        },
    )
    graph.add_edge(WorkflowNode.NEXT_STEP.value, END)

    return graph.compile()


def _interpret_node(
    state: WorkflowState,
    *,
    structured_arbitrator: StructuredArbitrator | None,
) -> WorkflowState:
    return _apply_stage_result(
        state,
        interpret_stage(
            state=_run_state(state),
            user=_user(state),
            latest_task_snapshot=state.get("latest_task_snapshot"),
            structured_arbitrator=structured_arbitrator,
        ),
    )


def _apply_stage_result(
    state: WorkflowState,
    result: StageResult,
) -> WorkflowState:
    transition = resolve_workflow_transition(result=result)
    run_state = _patched_run_state(
        run_state=_run_state(state),
        patch=result.patch,
    )
    workflow_state: WorkflowState = {
        **state,
        "run_state": run_state,
        "stage_outcome": transition.outcome,
        "route": transition.route,
    }

    for key, value in result.patch.items():
        if key in RUN_STATE_FIELD_NAMES:
            continue
        workflow_state[key] = value

    return workflow_state


def _patched_run_state(*, run_state: RunState, patch: dict[str, Any]) -> RunState:
    payload = run_state.model_dump(mode="python")
    for key, value in patch.items():
        if key in RUN_STATE_FIELD_NAMES:
            payload[key] = value
    return RunState.model_validate(payload)


def resolve_workflow_transition(*, result: StageResult) -> WorkflowTransition:
    outcome = WorkflowStageOutcome(result.outcome)
    failure_classification = result.patch.get("failure_classification")

    if outcome is WorkflowStageOutcome.NEEDS_CLARIFICATION:
        if failure_classification == "unsupported_capability":
            return WorkflowTransition(
                outcome=outcome,
                route=WorkflowRoute.END,
            )
        return WorkflowTransition(
            outcome=outcome,
            route=WorkflowRoute.CLARIFY,
        )
    if outcome is WorkflowStageOutcome.READY_FOR_CONFIRMATION:
        return WorkflowTransition(
            outcome=outcome,
            route=WorkflowRoute.CONFIRM,
        )
    if outcome is WorkflowStageOutcome.APPROVED_FOR_EXECUTION:
        return WorkflowTransition(
            outcome=outcome,
            route=WorkflowRoute.EXECUTE,
        )
    if outcome is WorkflowStageOutcome.EXECUTION_SUCCEEDED:
        return WorkflowTransition(
            outcome=outcome,
            route=WorkflowRoute.EXPLAIN,
        )
    if outcome is WorkflowStageOutcome.READY_TO_RESPOND:
        return WorkflowTransition(
            outcome=outcome,
            route=WorkflowRoute.NEXT_STEP,
        )
    return WorkflowTransition(
        outcome=outcome,
        route=WorkflowRoute.END,
    )


def _route_from_state(state: WorkflowState) -> str:
    return state["route"].value


def _run_state(state: WorkflowState) -> RunState:
    return cast(RunState, state["run_state"])


def _user(state: WorkflowState) -> UserState:
    return cast(UserState, state["user"])
