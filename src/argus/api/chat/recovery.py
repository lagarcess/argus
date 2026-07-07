from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from loguru import logger

from argus.agent_runtime.recovery_messages import (
    RecoveryMessageCode,
    recovery_message,
    recovery_state,
)
from argus.agent_runtime.runtime import build_workflow_input
from argus.agent_runtime.state.models import (
    ArtifactReference,
    StrategySummary,
    TaskSnapshot,
    UserState,
)
from argus.agent_runtime.workflow_contract import WorkflowNode
from argus.api import state as api_state
from argus.api.chat.artifacts import (
    result_reference_from_run,
    saved_strategy_metadata_from_sources,
)
from argus.api.dependencies import dev_memory_fallback_enabled
from argus.api.schemas import BacktestRun, Message

LOST_CONFIRMATION_STATE_MESSAGE = recovery_message("confirmation_state_lost")


@dataclass(frozen=True)
class RuntimeFallbackContext:
    latest_task_snapshot: TaskSnapshot | None = None
    selected_thread_metadata: dict[str, Any] | None = None
    artifact_references: list[ArtifactReference] | None = None
    confirmation_payload: dict[str, Any] | None = None
    confirmation_message_id: str | None = None
    recovery_message: str | None = None
    recovery: dict[str, Any] | None = None


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


async def mark_terminal_runtime_failure_checkpoint(
    *,
    workflow: Any,
    conversation_id: str,
    user: UserState,
    message: str,
    recent_thread_history: list[Any],
    failure_metadata: dict[str, Any],
) -> None:
    from argus.agent_runtime.graph.workflow import WorkflowStageOutcome

    try:
        checkpoint_values = build_workflow_input(
            user=user,
            message=message,
            recent_thread_history=recent_thread_history,
        )
        checkpoint_values.update(
            {
                "stage_outcome": WorkflowStageOutcome.AWAIT_USER_REPLY,
                "assistant_prompt": None,
                "assistant_response": None,
                "confirmation_payload": None,
                "backtest_job": None,
                "latest_task_snapshot": None,
                "artifact_references": [],
                "selected_thread_metadata": {
                    "conversation_mode": "recovery",
                    "agent_runtime_stage_outcome": "agent_runtime_failure",
                    "agent_runtime_turn": failure_metadata.get("agent_runtime_turn"),
                },
            }
        )
        await workflow.aupdate_state(
            {"configurable": {"thread_id": conversation_id}},
            checkpoint_values,
            as_node=WorkflowNode.INTERPRET.value,
        )
    except Exception as exc:
        logger.warning(
            "Agent runtime terminal failure checkpoint write failed",
            error=str(exc),
            conversation_id=conversation_id,
        )


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
    recent_messages: list[Message] | None = None,
    language: str | None = None,
) -> RuntimeFallbackContext | None:
    from argus.agent_runtime.confirmation_artifacts import (
        confirmation_artifact_reference,
        confirmation_id_from_payload,
    )
    from argus.agent_runtime.strategy_contract import strategy_can_be_approved

    messages = (
        recent_messages
        if recent_messages is not None
        else _recent_messages_for_conversation(
            user_id=user_id,
            conversation_id=conversation_id,
            limit=20,
        )
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
            return _confirmation_recovery_context(
                "confirmation_state_lost",
                language=language,
            )
        strategy = payload.get("strategy")
        if not isinstance(strategy, dict):
            return _confirmation_recovery_context(
                "confirmation_state_lost",
                language=language,
            )
        try:
            pending_strategy = StrategySummary.model_validate(strategy)
        except Exception:
            return _confirmation_recovery_context(
                "confirmation_state_lost",
                language=language,
            )
        if not strategy_can_be_approved(pending_strategy):
            return _confirmation_recovery_context(
                "confirmation_state_lost",
                language=language,
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
        # A typed result question during an active confirmation still needs the
        # completed run: without this reference the interpreter loses the
        # latest-result context and coerces the turn away from result_followup.
        result_lookup = _latest_completed_result_reference(
            user_id=user_id,
            conversation_id=conversation_id,
            messages=messages,
        )
        result_reference = result_lookup[0] if result_lookup is not None else None
        references = (
            [result_reference, confirmation_reference]
            if result_reference is not None
            else [confirmation_reference]
        )
        selected_thread_metadata: dict[str, Any] = {
            "latest_task_type": "backtest_execution",
            "last_stage_outcome": "await_approval",
            "fallback_source": "message_metadata",
        }
        if result_reference is not None:
            source_run_id = str(
                result_reference.metadata.get("result_run_id") or ""
            ).strip()
            if source_run_id:
                selected_thread_metadata["source_result_run_id"] = source_run_id
        return RuntimeFallbackContext(
            latest_task_snapshot=TaskSnapshot(
                latest_task_type="backtest_execution",
                completed=False,
                pending_strategy_summary=pending_strategy,
                active_confirmation_reference=confirmation_reference,
                latest_backtest_result_reference=result_reference,
                artifact_references=references,
                last_unresolved_follow_up=(
                    pending_strategy.raw_user_phrasing
                    or pending_strategy.strategy_thesis
                    or pending_strategy.strategy_type
                ),
                resolution_provenance=list(pending_strategy.resolution_provenance),
            ),
            selected_thread_metadata=selected_thread_metadata,
            artifact_references=references,
            confirmation_payload=payload,
            confirmation_message_id=message.id,
        )
    return None


def _confirmation_recovery_context(
    code: RecoveryMessageCode,
    *,
    language: str | None,
) -> RuntimeFallbackContext:
    return RuntimeFallbackContext(
        recovery_message=recovery_message(code, language=language),
        recovery=recovery_state(code, language=language, retryable=False),
    )


def _metadata_invalidates_confirmation(metadata: dict[str, Any]) -> bool:
    if metadata.get("result_card"):
        return True
    if metadata.get("result_run_id") and not _metadata_is_latest_result_fact_reply(
        metadata
    ):
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
    for message_index in range(len(messages) - 1, -1, -1):
        message = messages[message_index]
        if message.role != "assistant":
            continue
        if not isinstance(message.metadata, dict):
            return None
        metadata = message.metadata
        if _metadata_invalidates_pending_strategy(metadata):
            return None
        pending_payload = metadata.get("pending_strategy")
        if (
            not isinstance(pending_payload, dict)
            and _metadata_is_latest_result_fact_reply(metadata)
        ):
            continue
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
        response_intent_facts = (
            response_intent.get("facts") if isinstance(response_intent, dict) else None
        )
        chat_action = metadata.get("chat_action")
        chat_action_payload = (
            chat_action.get("payload") if isinstance(chat_action, dict) else None
        )
        raw_source_run_id = (
            (source_result.get("run_id") if isinstance(source_result, dict) else None)
            or metadata.get("source_result_run_id")
            or (
                response_intent_facts.get("latest_run_id")
                if isinstance(response_intent_facts, dict)
                else None
            )
            or (
                chat_action_payload.get("run_id")
                if isinstance(chat_action_payload, dict)
                else None
            )
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
                source_reference = _result_reference_with_response_metadata(
                    run,
                    message_metadata=metadata,
                )
                selected_thread_metadata["source_result_run_id"] = run.id
                if run.strategy_id is not None:
                    selected_thread_metadata["source_result_strategy_id"] = (
                        run.strategy_id
                    )
        if (
            source_reference is None
            and str(requested_field or "").strip() == "refinement"
        ):
            # Older metadata may lack source_result (e.g. a fact answer sits
            # between the Refine prompt and the edit). Recover the result from
            # messages at or before this prompt — never a newer run or a
            # run-store guess.
            result_lookup = _latest_completed_result_reference(
                user_id=user_id,
                conversation_id=conversation_id,
                messages=messages[: message_index + 1],
                allow_run_store_fallback=False,
            )
            if result_lookup is not None:
                source_reference = result_lookup[0]
                source_run_id = str(
                    source_reference.metadata.get("result_run_id")
                    or source_reference.metadata.get("run_id")
                    or source_reference.artifact_id
                )
                if source_run_id:
                    selected_thread_metadata["source_result_run_id"] = source_run_id
                source_strategy_id = source_reference.metadata.get(
                    "result_strategy_id"
                )
                if isinstance(source_strategy_id, str) and source_strategy_id:
                    selected_thread_metadata["source_result_strategy_id"] = (
                        source_strategy_id
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
    is_latest_result_fact_reply = _metadata_is_latest_result_fact_reply(metadata)
    if metadata.get("result_card"):
        return True
    if metadata.get("result_run_id") and not is_latest_result_fact_reply:
        return True
    action = metadata.get("chat_action")
    if isinstance(action, dict) and action.get("type") == "cancel_confirmation":
        return True
    stage_outcome = str(metadata.get("agent_runtime_stage_outcome") or "")
    if is_latest_result_fact_reply and stage_outcome in {"", "ready_to_respond"}:
        return False
    if stage_outcome == "ready_to_respond" and _metadata_has_pending_response_intent(
        metadata
    ):
        return False
    return stage_outcome in {
        "execution_succeeded",
        "ready_to_respond",
        "end_run",
    }


def _metadata_is_latest_result_fact_reply(metadata: dict[str, Any]) -> bool:
    """Typed latest-result fact replies carry run continuity ids without
    superseding an active confirmation."""

    response_intent = metadata.get("response_intent")
    if not isinstance(response_intent, dict):
        return False
    if response_intent.get("kind") not in {"beginner_guidance", "unsupported_recovery"}:
        return False
    facts = response_intent.get("facts")
    return isinstance(facts, dict) and bool(
        facts.get("fact_key") or facts.get("requested_metric")
    )


def _metadata_has_pending_response_intent(metadata: dict[str, Any]) -> bool:
    pending_strategy = metadata.get("pending_strategy")
    if not isinstance(pending_strategy, dict):
        return False
    response_intent = pending_strategy.get("response_intent")
    if not isinstance(response_intent, dict):
        return False
    needs = response_intent.get("semantic_needs")
    options = response_intent.get("options")
    return bool(
        (isinstance(needs, list) and needs)
        or (isinstance(options, list) and options)
    )


def latest_result_fallback_context(
    *,
    user_id: str,
    conversation_id: str,
) -> RuntimeFallbackContext | None:
    lookup = _latest_completed_result_reference(
        user_id=user_id,
        conversation_id=conversation_id,
    )
    if lookup is None:
        return None
    reference, fallback_source = lookup
    return RuntimeFallbackContext(
        latest_task_snapshot=TaskSnapshot(
            latest_task_type="results_explanation",
            completed=True,
            latest_backtest_result_reference=reference,
        ),
        selected_thread_metadata={
            "latest_task_type": "results_explanation",
            "last_stage_outcome": "ready_to_respond",
            "fallback_source": fallback_source,
        },
        artifact_references=[reference],
    )


def _latest_completed_result_reference(
    *,
    user_id: str,
    conversation_id: str,
    messages: list[Message] | None = None,
    allow_run_store_fallback: bool = True,
) -> tuple[ArtifactReference, str] | None:
    scanned = (
        messages
        if messages is not None
        else _recent_messages_for_conversation(
            user_id=user_id,
            conversation_id=conversation_id,
            limit=20,
        )
    )
    for message in reversed(scanned):
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
        reference = _result_reference_with_response_metadata(
            run,
            message_metadata=metadata,
        )
        return reference, "message_metadata"
    if not allow_run_store_fallback:
        return None
    run = latest_completed_run_for_conversation(
        user_id=user_id,
        conversation_id=conversation_id,
    )
    if run is None:
        return None
    return _result_reference_with_response_metadata(run), "backtest_runs"


def _result_reference_with_response_metadata(
    run: BacktestRun,
    *,
    message_metadata: dict[str, Any] | None = None,
) -> ArtifactReference:
    reference = result_reference_from_run(run)
    reference.metadata.update(
        {
            "result_run_id": run.id,
            "latest_run_id": run.id,
            "result_conversation_id": run.conversation_id,
        }
    )
    if run.strategy_id is not None:
        reference.metadata["result_strategy_id"] = run.strategy_id
    reference.metadata.update(
        saved_strategy_metadata_from_sources(
            run=run,
            message_metadata=message_metadata,
        )
    )
    return reference


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
    if api_state.supabase_gateway is not None:
        try:
            run = api_state.supabase_gateway.get_latest_completed_run_for_conversation(
                user_id=user_id,
                conversation_id=conversation_id,
            )
            if run is not None:
                return run
        except Exception as exc:
            if not dev_memory_fallback_enabled():
                raise
            logger.warning(
                "Supabase latest backtest run read failed; using dev memory fallback",
                error=str(exc),
                conversation_id=conversation_id,
            )
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
