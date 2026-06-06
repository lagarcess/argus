from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from loguru import logger

from argus.agent_runtime.confirmation_artifacts import (
    confirmation_artifact_reference,
    confirmation_id_from_payload,
)
from argus.agent_runtime.state.models import (
    ArtifactReference,
    StrategySummary,
    TaskSnapshot,
)
from argus.agent_runtime.strategy_contract import strategy_can_be_approved
from argus.api import state as api_state
from argus.api.chat.artifacts import (
    result_reference_from_run,
    saved_strategy_metadata_from_sources,
)
from argus.api.dependencies import dev_memory_fallback_enabled
from argus.api.schemas import BacktestRun, Message

LOST_CONFIRMATION_STATE_MESSAGE = (
    "I lost the active confirmation state, but your conversation is saved. "
    "I can restate the strategy so you can confirm it again."
)


@dataclass(frozen=True)
class RuntimeFallbackContext:
    latest_task_snapshot: TaskSnapshot | None = None
    selected_thread_metadata: dict[str, Any] | None = None
    artifact_references: list[ArtifactReference] | None = None
    confirmation_payload: dict[str, Any] | None = None
    confirmation_message_id: str | None = None
    recovery_message: str | None = None


def _recent_messages_for_conversation(
    *,
    user_id: str,
    conversation_id: str,
    limit: int,
) -> list[Message]:
    messages: list[Message] = []
    if api_state.supabase_gateway is not None:
        try:
            messages = api_state.supabase_gateway.list_messages(
                user_id=user_id,
                conversation_id=conversation_id,
                limit=limit,
            )
        except Exception as exc:
            if not dev_memory_fallback_enabled():
                raise
            logger.warning(
                "Supabase confirmation state read failed; using dev memory fallback",
                error=str(exc),
                conversation_id=conversation_id,
            )
    if not messages:
        messages = list(api_state.store.messages.get(conversation_id, []))[-limit:]
    return messages


async def runtime_checkpoint_values(
    *,
    workflow: Any,
    conversation_id: str,
) -> dict[str, Any]:
    try:
        state_snapshot = await workflow.aget_state(
            {"configurable": {"thread_id": conversation_id}}
        )
    except Exception as exc:
        logger.warning(
            "Agent runtime checkpoint read failed; considering metadata fallback",
            error=str(exc),
            conversation_id=conversation_id,
        )
        return {}
    values = getattr(state_snapshot, "values", None)
    return values if isinstance(values, dict) else {}


def checkpoint_has_pending_confirmation(values: dict[str, Any]) -> bool:
    stage_outcome = values.get("stage_outcome")
    stage_outcome_value = str(getattr(stage_outcome, "value", stage_outcome or ""))
    if stage_outcome_value != "await_approval":
        return False
    snapshot = _task_snapshot_from_value(values.get("latest_task_snapshot"))
    if snapshot is not None and snapshot.pending_strategy_summary is not None:
        return True
    run_state = values.get("run_state")
    return getattr(run_state, "confirmation_payload", None) is not None


def checkpoint_has_latest_result(values: dict[str, Any]) -> bool:
    snapshot = _task_snapshot_from_value(values.get("latest_task_snapshot"))
    return snapshot is not None and snapshot.latest_backtest_result_reference is not None


def checkpoint_latest_result_has_context_packets(values: dict[str, Any]) -> bool:
    snapshot = _task_snapshot_from_value(values.get("latest_task_snapshot"))
    if snapshot is None:
        return False
    return result_reference_has_context_packets(snapshot.latest_backtest_result_reference)


def result_reference_has_context_packets(reference: ArtifactReference | None) -> bool:
    if reference is None:
        return False
    metadata = reference.metadata
    packets = metadata.get("context_packets")
    if isinstance(packets, list) and packets:
        return True
    result_card = metadata.get("result_card")
    if isinstance(result_card, dict):
        card_packets = result_card.get("context_packets")
        return isinstance(card_packets, list) and bool(card_packets)
    return False


def checkpoint_has_pending_strategy(values: dict[str, Any]) -> bool:
    snapshot = _task_snapshot_from_value(values.get("latest_task_snapshot"))
    return snapshot is not None and snapshot.pending_strategy_summary is not None


def confirmation_metadata_fallback_context(
    *,
    user_id: str,
    conversation_id: str,
) -> RuntimeFallbackContext | None:
    messages = _recent_messages_for_conversation(
        user_id=user_id,
        conversation_id=conversation_id,
        limit=20,
    )
    for message in reversed(messages):
        if message.role != "assistant" or not isinstance(message.metadata, dict):
            continue
        metadata = message.metadata
        if _metadata_invalidates_confirmation(metadata):
            return None
        if not metadata.get("confirmation_card"):
            continue
        payload = metadata.get("confirmation_payload")
        if not isinstance(payload, dict):
            return RuntimeFallbackContext(
                recovery_message=LOST_CONFIRMATION_STATE_MESSAGE
            )
        strategy = payload.get("strategy")
        if not isinstance(strategy, dict):
            return RuntimeFallbackContext(
                recovery_message=LOST_CONFIRMATION_STATE_MESSAGE
            )
        try:
            pending_strategy = StrategySummary.model_validate(strategy)
        except Exception:
            return RuntimeFallbackContext(
                recovery_message=LOST_CONFIRMATION_STATE_MESSAGE
            )
        if not strategy_can_be_approved(pending_strategy):
            return RuntimeFallbackContext(
                recovery_message=LOST_CONFIRMATION_STATE_MESSAGE
            )
        card = metadata.get("confirmation_card")
        confirmation_id = confirmation_id_from_payload(
            payload,
            fallback=(
                str(card.get("confirmation_id"))
                if isinstance(card, dict) and card.get("confirmation_id")
                else None
            ),
        )
        confirmation_reference = confirmation_artifact_reference(
            confirmation_id=confirmation_id,
            confirmation_payload=payload,
            confirmation_card=card if isinstance(card, dict) else None,
        )
        return RuntimeFallbackContext(
            latest_task_snapshot=TaskSnapshot(
                latest_task_type="backtest_execution",
                completed=False,
                pending_strategy_summary=pending_strategy,
                active_confirmation_reference=confirmation_reference,
                artifact_references=[confirmation_reference],
                last_unresolved_follow_up=(
                    pending_strategy.raw_user_phrasing
                    or pending_strategy.strategy_thesis
                    or pending_strategy.strategy_type
                ),
                resolution_provenance=list(pending_strategy.resolution_provenance),
            ),
            selected_thread_metadata={
                "latest_task_type": "backtest_execution",
                "last_stage_outcome": "await_approval",
                "fallback_source": "message_metadata",
            },
            artifact_references=[confirmation_reference],
            confirmation_payload=payload,
            confirmation_message_id=message.id,
        )
    return None


def _metadata_invalidates_confirmation(metadata: dict[str, Any]) -> bool:
    if metadata.get("result_card") or metadata.get("result_run_id"):
        return True
    action = metadata.get("chat_action")
    if isinstance(action, dict) and action.get("type") == "cancel_confirmation":
        return True
    pending_strategy = metadata.get("pending_strategy")
    if not isinstance(pending_strategy, dict):
        return False
    requested_field = pending_strategy.get("requested_field")
    stage_outcome = str(metadata.get("agent_runtime_stage_outcome") or "")
    return (
        isinstance(requested_field, str)
        and bool(requested_field.strip())
        and stage_outcome in {"await_user_reply", "needs_clarification"}
    )


def pending_strategy_metadata_fallback_context(
    *,
    user_id: str,
    conversation_id: str,
) -> RuntimeFallbackContext | None:
    messages = _recent_messages_for_conversation(
        user_id=user_id,
        conversation_id=conversation_id,
        limit=20,
    )
    for message in reversed(messages):
        if message.role != "assistant":
            continue
        if not isinstance(message.metadata, dict):
            return None
        metadata = message.metadata
        if _metadata_invalidates_pending_strategy(metadata):
            return None
        pending_payload = metadata.get("pending_strategy")
        if not isinstance(pending_payload, dict):
            return None
        strategy_payload = pending_payload.get("strategy")
        if not isinstance(strategy_payload, dict):
            continue
        try:
            pending_strategy = StrategySummary.model_validate(strategy_payload)
        except Exception:
            continue
        requested_field = pending_payload.get("requested_field")
        stage_outcome = str(
            metadata.get("agent_runtime_stage_outcome") or "await_user_reply"
        )
        selected_thread_metadata: dict[str, Any] = {
            "latest_task_type": "backtest_execution",
            "last_stage_outcome": stage_outcome,
            "fallback_source": "pending_strategy_metadata",
        }
        if isinstance(requested_field, str) and requested_field:
            selected_thread_metadata["requested_field"] = requested_field
        pending_resolution = pending_payload.get("pending_resolution")
        if isinstance(pending_resolution, dict):
            selected_thread_metadata["pending_resolution"] = dict(pending_resolution)
        response_intent = pending_payload.get("response_intent")
        if isinstance(response_intent, dict):
            selected_thread_metadata["response_intent"] = dict(response_intent)
        source_reference: ArtifactReference | None = None
        source_result = pending_payload.get("source_result")
        raw_source_run_id = (
            source_result.get("run_id")
            if isinstance(source_result, dict)
            else metadata.get("source_result_run_id")
        )
        if raw_source_run_id is not None:
            run = _run_by_id_for_user(
                user_id=user_id,
                run_id=str(raw_source_run_id),
            )
            if (
                run is not None
                and run.conversation_id == conversation_id
                and run.status == "completed"
            ):
                source_reference = result_reference_from_run(run)
                source_reference.metadata.update(
                    saved_strategy_metadata_from_sources(
                        run=run,
                        message_metadata=metadata,
                    )
                )
                selected_thread_metadata["source_result_run_id"] = run.id
                if run.strategy_id is not None:
                    selected_thread_metadata["source_result_strategy_id"] = (
                        run.strategy_id
                    )
        return RuntimeFallbackContext(
            latest_task_snapshot=TaskSnapshot(
                latest_task_type="backtest_execution",
                completed=False,
                pending_strategy_summary=pending_strategy,
                latest_backtest_result_reference=source_reference,
                last_unresolved_follow_up=(
                    pending_strategy.raw_user_phrasing
                    or pending_strategy.strategy_thesis
                    or pending_strategy.strategy_type
                ),
                resolution_provenance=list(pending_strategy.resolution_provenance),
                artifact_references=(
                    [source_reference] if source_reference is not None else []
                ),
            ),
            selected_thread_metadata=selected_thread_metadata,
            artifact_references=(
                [source_reference] if source_reference is not None else []
            ),
            confirmation_payload=(
                metadata.get("confirmation_payload")
                if isinstance(metadata.get("confirmation_payload"), dict)
                else None
            ),
        )
    return None


def _metadata_invalidates_pending_strategy(metadata: dict[str, Any]) -> bool:
    if metadata.get("result_card") or metadata.get("result_run_id"):
        return True
    action = metadata.get("chat_action")
    if isinstance(action, dict) and action.get("type") == "cancel_confirmation":
        return True
    stage_outcome = str(metadata.get("agent_runtime_stage_outcome") or "")
    return stage_outcome in {
        "execution_succeeded",
        "ready_to_respond",
        "end_run",
    }


def latest_result_fallback_context(
    *,
    user_id: str,
    conversation_id: str,
) -> RuntimeFallbackContext | None:
    messages = _recent_messages_for_conversation(
        user_id=user_id,
        conversation_id=conversation_id,
        limit=20,
    )
    for message in reversed(messages):
        if message.role != "assistant" or not isinstance(message.metadata, dict):
            continue
        metadata = message.metadata
        raw_run_id = metadata.get("result_run_id") or metadata.get("latest_run_id")
        if raw_run_id is None:
            continue
        run = _run_by_id_for_user(user_id=user_id, run_id=str(raw_run_id))
        if run is None or run.conversation_id != conversation_id:
            continue
        if run.status != "completed":
            continue
        reference = result_reference_from_run(run)
        reference.metadata.update(
            saved_strategy_metadata_from_sources(
                run=run,
                message_metadata=metadata,
            )
        )
        return RuntimeFallbackContext(
            latest_task_snapshot=TaskSnapshot(
                latest_task_type="results_explanation",
                completed=True,
                latest_backtest_result_reference=reference,
            ),
            selected_thread_metadata={
                "latest_task_type": "results_explanation",
                "last_stage_outcome": "ready_to_respond",
                "fallback_source": "message_metadata",
            },
            artifact_references=[reference],
        )
    return None


def failed_action_metadata_fallback_context(
    *,
    user_id: str,
    conversation_id: str,
) -> RuntimeFallbackContext | None:
    messages = _recent_messages_for_conversation(
        user_id=user_id,
        conversation_id=conversation_id,
        limit=20,
    )
    for message in reversed(messages):
        if message.role != "assistant" or not isinstance(message.metadata, dict):
            continue
        if _metadata_supersedes_failed_action(message.metadata):
            return None
        reference = _failed_action_reference_from_metadata(
            metadata=message.metadata,
            fallback_id=f"failed-action-{message.id}",
        )
        if reference is None:
            continue
        return RuntimeFallbackContext(
            latest_task_snapshot=TaskSnapshot(
                latest_task_type="backtest_execution",
                completed=False,
                latest_failed_action_reference=reference,
                artifact_references=[reference],
            ),
            selected_thread_metadata={
                "latest_task_type": "backtest_execution",
                "last_stage_outcome": "execution_failed_recoverably",
                "fallback_source": "failed_action_metadata",
            },
            artifact_references=[reference],
        )
    return None


def _metadata_supersedes_failed_action(metadata: dict[str, Any]) -> bool:
    return bool(
        metadata.get("result_card")
        or metadata.get("result_run_id")
        or metadata.get("latest_run_id")
        or metadata.get("confirmation_card")
        or metadata.get("pending_strategy")
    )


def _failed_action_reference_from_metadata(
    *,
    metadata: dict[str, Any],
    fallback_id: str,
) -> ArtifactReference | None:
    raw_reference = metadata.get("latest_failed_action_reference")
    if isinstance(raw_reference, dict):
        try:
            return ArtifactReference.model_validate(raw_reference)
        except Exception:
            return None
    failed_action = metadata.get("failed_action")
    if not isinstance(failed_action, dict):
        return None
    launch_payload = failed_action.get("launch_payload")
    if not isinstance(launch_payload, dict):
        return None
    return ArtifactReference(
        artifact_kind="failed_action",
        artifact_id=str(failed_action.get("artifact_id") or fallback_id),
        artifact_status=str(failed_action.get("artifact_status") or "failed"),
        metadata=dict(failed_action),
    )


def _task_snapshot_from_value(value: Any) -> TaskSnapshot | None:
    if value is None:
        return None
    if isinstance(value, TaskSnapshot):
        return value
    try:
        return TaskSnapshot.model_validate(value)
    except Exception:
        return None


def _run_by_id_for_user(*, user_id: str, run_id: str) -> BacktestRun | None:
    run = None
    if api_state.supabase_gateway is not None:
        try:
            run = api_state.supabase_gateway.get_backtest_run(
                user_id=user_id,
                run_id=run_id,
            )
        except Exception as exc:
            if not dev_memory_fallback_enabled():
                raise
            logger.warning(
                "Supabase backtest run read failed; using dev memory fallback",
                error=str(exc),
                run_id=run_id,
            )
    if run is None:
        run = api_state.store.backtest_runs.get(run_id)
    if run is None:
        return None
    if api_state.store.backtest_run_owners.get(run.id, user_id) != user_id:
        return None
    return run


def latest_completed_run_for_conversation(
    *,
    user_id: str,
    conversation_id: str,
) -> BacktestRun | None:
    candidates = [
        run
        for run_id, run in api_state.store.backtest_runs.items()
        if api_state.store.backtest_run_owners.get(run_id) == user_id
        and run.conversation_id == conversation_id
        and run.status == "completed"
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda run: run.created_at)
