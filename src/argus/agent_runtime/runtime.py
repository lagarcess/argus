from __future__ import annotations

from collections.abc import AsyncIterator, Iterable
from typing import Any

from argus.agent_runtime.graph.workflow import WorkflowNode, WorkflowState
from argus.agent_runtime.stages.compose import compose_response_intent
from argus.agent_runtime.state.models import (
    ArtifactReference,
    ConversationMessage,
    RunState,
    UserState,
)

MAX_RECENT_THREAD_HISTORY = 6
TOKEN_STREAM_NODES = {
    WorkflowNode.CLARIFY.value,
    WorkflowNode.EXPLAIN.value,
    WorkflowNode.NEXT_STEP.value,
}
WORKFLOW_NODE_NAMES = {node.value for node in WorkflowNode}


def build_workflow_input(
    *,
    user: UserState,
    message: str,
    recent_thread_history: Iterable[ConversationMessage | dict[str, Any]] | None = None,
) -> WorkflowState:
    normalized_message = " ".join(message.strip().split())
    return {
        "run_state": RunState.new(
            current_user_message=normalized_message,
            recent_thread_history=_bounded_recent_thread_history(
                list(recent_thread_history or [])
            ),
        ),
        "user": user,
    }


async def stream_agent_turn_events(
    *,
    workflow: Any,
    user: UserState,
    thread_id: str,
    message: str,
    recent_thread_history: Iterable[ConversationMessage | dict[str, Any]] | None = None,
) -> AsyncIterator[dict[str, Any]]:
    initial_state = build_workflow_input(
        user=user,
        message=message,
        recent_thread_history=recent_thread_history,
    )
    config = {"configurable": {"thread_id": thread_id}}
    seen_stage_starts: set[str] = set()
    seen_stage_outcomes: set[str] = set()

    async for event in workflow.astream_events(
        initial_state,
        config=config,
        version="v2",
    ):
        kind = event.get("event")
        node_name = _event_node_name(event)
        if kind == "on_chain_start" and node_name in WORKFLOW_NODE_NAMES:
            if node_name not in seen_stage_starts:
                seen_stage_starts.add(node_name)
                yield {"type": "stage_start", "stage": node_name}
            continue
        if kind == "on_chat_model_stream" and node_name in TOKEN_STREAM_NODES:
            content = _chunk_content(event.get("data", {}).get("chunk"))
            if content:
                yield {"type": "token", "content": content}
            continue
        if kind == "on_chain_end" and node_name in WORKFLOW_NODE_NAMES:
            outcome = _stage_outcome_from_event(event)
            if outcome is not None and outcome not in seen_stage_outcomes:
                seen_stage_outcomes.add(outcome)
                yield {"type": "stage_outcome", "outcome": outcome}

    final_state = await _final_workflow_state(workflow=workflow, config=config)
    yield {"type": "final", "payload": _public_result(final_state)}


async def run_agent_turn(
    *,
    workflow: Any,
    user: UserState,
    thread_id: str,
    message: str,
    recent_thread_history: Iterable[ConversationMessage | dict[str, Any]] | None = None,
) -> dict[str, Any]:
    final_payload: dict[str, Any] | None = None
    async for event in stream_agent_turn_events(
        workflow=workflow,
        user=user,
        thread_id=thread_id,
        message=message,
        recent_thread_history=recent_thread_history,
    ):
        if event.get("type") == "final":
            payload = event.get("payload")
            if isinstance(payload, dict):
                final_payload = payload
    return final_payload or {}


async def _final_workflow_state(*, workflow: Any, config: dict[str, Any]) -> dict[str, Any]:
    state_snapshot = await workflow.aget_state(config)
    values = getattr(state_snapshot, "values", None)
    if not isinstance(values, dict):
        return {}
    return _compose_runtime_response(values)


def _event_node_name(event: dict[str, Any]) -> str | None:
    metadata = event.get("metadata")
    if isinstance(metadata, dict):
        node_name = metadata.get("langgraph_node")
        if isinstance(node_name, str) and node_name in WORKFLOW_NODE_NAMES:
            return node_name
    name = event.get("name")
    if isinstance(name, str) and name in WORKFLOW_NODE_NAMES:
        return name
    return None


def _stage_outcome_from_event(event: dict[str, Any]) -> str | None:
    data = event.get("data")
    if not isinstance(data, dict):
        return None
    output = data.get("output")
    if not isinstance(output, dict):
        return None
    outcome = output.get("stage_outcome")
    if outcome is None:
        return None
    return str(getattr(outcome, "value", outcome))


def _chunk_content(chunk: Any) -> str:
    content = getattr(chunk, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)
    return ""


def _compose_runtime_response(result: dict[str, Any]) -> dict[str, Any]:
    run_state = result.get("run_state")
    if not isinstance(run_state, RunState):
        return result
    composed = compose_response_intent(run_state)
    if composed is None:
        return result
    patched = dict(result)
    patched["assistant_prompt"] = composed
    return patched


def _public_result(result: dict[str, Any]) -> dict[str, Any]:
    allowed_keys = {
        "stage_outcome",
        "assistant_prompt",
        "assistant_response",
        "requested_field",
        "optional_parameter_choices",
        "confirmation_payload",
        "next_actions",
        "failure_classification",
        "final_response_payload",
    }
    serialized = {
        key: _serialize_public_value(key, value)
        for key, value in result.items()
        if key in allowed_keys and value is not None
    }
    run_state = result.get("run_state")
    if run_state is not None:
        if (
            "confirmation_payload" not in serialized
            and getattr(run_state, "confirmation_payload", None) is not None
        ):
            serialized["confirmation_payload"] = _serialize_public_value(
                "confirmation_payload",
                run_state.confirmation_payload,
            )
        if (
            "final_response_payload" not in serialized
            and getattr(run_state, "final_response_payload", None) is not None
        ):
            serialized["final_response_payload"] = _serialize_public_value(
                "final_response_payload",
                run_state.final_response_payload,
            )
        if (
            "failure_classification" not in serialized
            and getattr(run_state, "failure_classification", None) is not None
        ):
            serialized["failure_classification"] = run_state.failure_classification
    stage_outcome = result.get("stage_outcome")
    if stage_outcome is not None:
        serialized["stage_outcome"] = getattr(stage_outcome, "value", stage_outcome)
    return serialized


def _serialize_public_value(key: str, value: Any) -> Any:
    if key in {"confirmation_payload", "final_response_payload"} and hasattr(
        value,
        "model_dump",
    ):
        return value.model_dump(mode="python")
    return value


def _bounded_recent_thread_history(
    message_history: list[ConversationMessage | dict[str, Any]],
) -> list[ConversationMessage]:
    bounded: list[ConversationMessage] = []
    for message in message_history[-MAX_RECENT_THREAD_HISTORY:]:
        if isinstance(message, ConversationMessage):
            bounded.append(message.model_copy(deep=True))
        else:
            bounded.append(ConversationMessage.model_validate(message))
    return bounded


def resolve_persisted_artifact_references(
    raw_references: Iterable[ArtifactReference | dict[str, Any]],
) -> list[ArtifactReference]:
    return [
        ArtifactReference.model_validate(reference)
        for reference in raw_references
    ]
