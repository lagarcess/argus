"""The pending-confirmation artifact's liveness: who may still write it.

A card is pending until a run is admitted for it, or it is cancelled or
superseded. The card row is the single consumption truth every writer here
reads and stamps; nothing in this module composes card content.
"""

from __future__ import annotations

import threading
from typing import Any

from loguru import logger


class DeadConfirmationCardError(ValueError):
    """The card is no longer a live pending confirmation; nothing was written."""


def _card_message_for_state(
    *,
    user_id: str,
    conversation_id: str,
    message_id: str,
    gateway: Any | None,
) -> Any | None:
    if gateway is not None:
        try:
            return gateway.get_message(
                user_id=user_id,
                conversation_id=conversation_id,
                message_id=message_id,
            )
        except Exception:  # noqa: BLE001
            return None
    return _persisted_card_message(
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message_id,
    )


def _stamped_card_metadata(metadata: dict[str, Any], state: str) -> dict[str, Any]:
    """A copy of the card message metadata carrying the liveness state."""
    import copy as _copy

    stamped = _copy.deepcopy(metadata)
    card = stamped.get("confirmation_card")
    if isinstance(card, dict):
        card["confirmation_state"] = state
    reference = stamped.get("active_confirmation_reference")
    if isinstance(reference, dict):
        reference["artifact_status"] = state
    references = stamped.get("artifact_references")
    if isinstance(references, list):
        for item in references:
            if isinstance(item, dict) and item.get("artifact_type") == "confirmation":
                item["artifact_status"] = state
    return stamped


def _write_card_state(
    *,
    user_id: str,
    conversation_id: str,
    message: Any,
    state: str,
    gateway: Any | None,
) -> None:
    from argus.api.message_store import update_message_artifact

    stamped = _stamped_card_metadata(message.metadata, state)
    if gateway is not None:
        gateway.update_message_artifact(
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message.id,
            content=message.content,
            metadata=stamped,
            expected_source_metadata=message.metadata,
            expected_latest_message_id=None,
        )
        return
    update_message_artifact(
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message.id,
        content=message.content,
        metadata=stamped,
        expected_source_metadata=message.metadata,
        expected_latest_message_id=None,
    )


def consume_pending_card_for_run(
    *,
    user_id: str,
    conversation_id: str,
    message_id: str,
    expected_launch_payload_hash: str | None = None,
    gateway: Any | None = None,
) -> str:
    """Stamp the card consumed at run admission; the card row is the truth.

    Pressing Run is a commitment: once a run is admitted for a card, the
    card is no longer pending, whatever the job later does. Returns
    ``consumed`` when this call stamped the card, ``already_consumed`` on a
    replay of an admitted run, ``stale_card`` when the card changed between
    the click and admission (its launch payload hash no longer matches the
    admitted run, or an edit keeps winning the row), in which case the run
    must not dispatch, and ``unstamped`` when the card row cannot be read
    at all, in which case the run proceeds without a stamp and the legacy
    newer-message clause covers liveness once its result lands. The write
    is guarded; a lost race re-reads once and re-decides, so a concurrent
    edit and a consumption can never both win the row.
    """
    from argus.agent_runtime.stages.artifact_context import (
        CONSUMED_CONFIRMATION_STATE,
        confirmation_card_is_dead,
    )
    from argus.domain.supabase_conversation_messages import (
        StaleMessageArtifactError,
    )

    for _ in range(2):
        message = _card_message_for_state(
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            gateway=gateway,
        )
        if message is None or not isinstance(message.metadata, dict):
            return "unstamped"
        if confirmation_card_is_dead(message.metadata):
            return "already_consumed"
        if expected_launch_payload_hash:
            reference = message.metadata.get("active_confirmation_reference")
            reference_metadata = (
                reference.get("metadata") if isinstance(reference, dict) else None
            )
            current_hash = str(
                (reference_metadata or {}).get("launch_payload_hash") or ""
            ).strip()
            if current_hash and current_hash != expected_launch_payload_hash:
                # The click's basis is gone: an edit rewrote the card after
                # the run was requested, so the run refuses as stale rather
                # than executing values the card no longer shows.
                return "stale_card"
        try:
            _write_card_state(
                user_id=user_id,
                conversation_id=conversation_id,
                message=message,
                state=CONSUMED_CONFIRMATION_STATE,
                gateway=gateway,
            )
            return "consumed"
        except StaleMessageArtifactError:
            continue
        except Exception:  # noqa: BLE001
            # The stamp is protective; a store that cannot write it must
            # degrade to the legacy behaviour, never fail the run.
            logger.opt(exception=True).warning(
                "Run consumption stamp could not be written; proceeding "
                "unstamped with legacy liveness",
                conversation_id=conversation_id,
                message_id=message_id,
            )
            return "unstamped"
    return "stale_card"


def restore_pending_card_after_run(
    *,
    user_id: str,
    conversation_id: str,
    message_id: str,
    gateway: Any | None = None,
) -> bool:
    """Restore a consumed card to active when its run died without a result.

    Only a consumed card is restored; a cancelled or superseded card stays
    dead, so a failed run can never resurrect a card the user closed. The
    checkpoint is not written here: recovery derives liveness from the card
    row, and the next turn's metadata fallback carries the restored card.
    """
    from argus.agent_runtime.stages.artifact_context import (
        ACTIVE_CONFIRMATION_STATE,
        CONSUMED_CONFIRMATION_STATE,
    )
    from argus.domain.supabase_conversation_messages import (
        StaleMessageArtifactError,
    )

    for _ in range(2):
        message = _card_message_for_state(
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            gateway=gateway,
        )
        if message is None or not isinstance(message.metadata, dict):
            return False
        card = message.metadata.get("confirmation_card")
        state = str((card or {}).get("confirmation_state") or "").strip().casefold()
        if state == ACTIVE_CONFIRMATION_STATE:
            return True
        if state != CONSUMED_CONFIRMATION_STATE:
            return False
        try:
            _write_card_state(
                user_id=user_id,
                conversation_id=conversation_id,
                message=message,
                state=ACTIVE_CONFIRMATION_STATE,
                gateway=gateway,
            )
            return True
        except StaleMessageArtifactError:
            continue
        except Exception:  # noqa: BLE001
            break
    logger.warning(
        "A failed run could not restore its consumed card to active",
        conversation_id=conversation_id,
        message_id=message_id,
    )
    return False


def consume_confirmation_for_admitted_run(
    *,
    gateway: Any,
    user_id: str,
    conversation_id: str,
    confirmation_message_id: str | None,
    chat_action: dict[str, Any] | None,
    job_id: str,
    utcnow_iso: Any,
) -> dict[str, Any] | None:
    """Stamp the card consumed the moment its run is admitted.

    Pressing Run is a commitment: the card row is the single source of
    consumption truth, so the stamp lands before dispatch for admitted runs
    and idempotently on replays. When the card changed after the click (a
    guarded edit won the row first), the freshly admitted job is marked
    failed and the run refuses as stale instead of executing values the
    card no longer shows.
    """
    from argus.api.chat.backtest_job_envelopes import admission_rejection_envelope
    from argus.domain.edit_contract_config import in_place_card_edits_enabled

    if not in_place_card_edits_enabled():
        # The in-place surface is dark: no non-turn writer exists, so no
        # stamp is needed and the legacy newer-message clause owns liveness.
        return None
    message_id = str(confirmation_message_id or "").strip()
    if not message_id:
        return None
    clicked_hash = None
    if isinstance(chat_action, dict):
        raw_hash = chat_action.get("launch_payload_hash") or (
            chat_action.get("payload") or {}
        ).get("launch_payload_hash")
        if isinstance(raw_hash, str) and raw_hash.strip():
            clicked_hash = raw_hash.strip()
    consumption = consume_pending_card_for_run(
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message_id,
        expected_launch_payload_hash=clicked_hash,
        gateway=gateway,
    )
    if consumption == "unstamped":
        logger.warning(
            "Run admitted without a consumption stamp; the card row could "
            "not be read, so liveness falls back to the legacy clause",
            conversation_id=conversation_id,
            job_id=job_id,
        )
        return None
    if consumption == "stale_card" and job_id:
        try:
            gateway.mark_backtest_job_failed(
                user_id=user_id,
                job_id=job_id,
                failure_code="confirmation_changed",
                failure_detail=(
                    "The confirmation changed before this run could "
                    "start. Nothing ran."
                ),
                retryable=False,
                finished_at=utcnow_iso(),
                execution_metadata={"refused_before_dispatch": True},
            )
        except Exception:  # noqa: BLE001
            logger.warning(
                "Stale-card run refusal could not mark its job failed",
                job_id=job_id,
                conversation_id=conversation_id,
            )
    if consumption == "stale_card":
        return admission_rejection_envelope("confirmation_changed")
    return None


def restore_pending_card_for_failed_job(
    gateway: Any,
    *,
    user_id: str,
    job: dict[str, Any] | None,
) -> None:
    """A chat run that died without a result gives its card back.

    Research and non-chat jobs carry no confirmation card and fall through.
    Restoration is best-effort and fails toward consumed, never toward a
    wrongly editable card; a missed restore leaves the card dead until the
    user starts over, and the loss is logged by the restorer.
    """
    from argus.domain.backtest_job_lifecycle import (
        JOB_DEAD,
        classify_job_for_card,
    )

    if not isinstance(job, dict):
        return
    if (
        classify_job_for_card(status=job.get("status"), retryable=job.get("retryable"))
        != JOB_DEAD
    ):
        # Only a state no future write can turn into a result gives the
        # card back; may-succeed, has-result, and unknown all fail toward
        # consumed. The worker's success write derives its refusal from
        # the same classification, so the two cannot drift apart.
        return
    if job.get("result_run_id"):
        # A run that produced a result consumed its card for good, whatever
        # its row's status claims; never reactivate it.
        return
    message_id = str(job.get("confirmation_message_id") or "").strip()
    conversation_id = str(job.get("conversation_id") or "").strip()
    if not message_id or not conversation_id:
        return
    restore_pending_card_after_run(
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message_id,
        gateway=gateway,
    )


def apply_pending_card_update(
    *,
    user_id: str,
    conversation_id: str,
    source_message: Any,
    expected_source_metadata: dict[str, Any] | None,
    expected_latest_message_id: str | None,
    confirmation_id: str,
    confirmation_payload: dict[str, Any],
    language: str,
    metadata_extra: dict[str, Any] | None = None,
    runtime_workflow: Any | None = None,
):
    """The only write path for a non-turn change to a pending confirmation.

    The edit contract's dividing line is whether a turn was spent, not which
    affordance asked. A turn-based edit mints a new card because the
    conversation records the change; a non-turn change spent nothing, so the
    card it changed is the record, rewritten in place: same confirmation id,
    same message, nothing appended. Every non-turn producer must write
    through here; a key set to None in ``metadata_extra`` is removed so a
    consumed sidecar cannot go stale on the updated card.

    The write is conditional on what the caller read:
    ``expected_source_metadata`` guards the card's own row, and
    ``expected_latest_message_id`` guards conversation activity, because
    every superseding event (a turn, a run result, a cancellation) appends
    a message while a non-turn edit appends nothing, so an interleaved
    append means the caller's active-confirmation check may no longer hold.
    A concurrent writer raises ``StaleMessageArtifactError`` instead of
    being silently rolled back, and callers surface that as a conflict; a
    retry re-reads and re-checks. The rewritten card also carries its
    projections: the conversation's denormalized preview follows the card
    when it is the latest message, and when a runtime checkpoint exists its
    pending strategy, active reference, and confirmation payload are
    rewritten to the edited card. Without the checkpoint sync, a later turn
    whose metadata fallback carries no snapshot reads the pre-edit strategy
    from the checkpoint, and correctness depends on a caller remembering the
    fallback. Returns the updated message, or None when the card cannot be
    assembled.
    """
    from argus.agent_runtime.confirmation_artifacts import (
        confirmation_artifact_reference,
    )
    from argus.agent_runtime.stages.artifact_context import confirmation_card_is_dead

    # Imported here, not at module scope: the card builder re-exports this
    # module, so a top-level import would close the cycle.
    from argus.api.chat.confirmation import runtime_confirmation_card
    from argus.api.message_store import message_preview, update_message_artifact

    # The write-path invariant: no confirmation card is mutated after its
    # run has been admitted (or it was cancelled or superseded). Enforced
    # here so every producer, present or future, inherits it; the guarded
    # write's metadata compare keeps this check honest against races.
    if confirmation_card_is_dead(source_message.metadata) or (
        expected_source_metadata is not None
        and confirmation_card_is_dead(expected_source_metadata)
    ):
        raise DeadConfirmationCardError(
            "The confirmation is no longer pending; nothing was written."
        )

    confirmation_payload["confirmation_id"] = confirmation_id
    confirmation_payload["artifact_id"] = confirmation_id
    card = runtime_confirmation_card(
        {
            "stage_outcome": "await_approval",
            "confirmation_payload": confirmation_payload,
        },
        confirmation_id=confirmation_id,
        conversation_id=conversation_id,
        language=language,
    )
    if card is None:
        return None
    reference = confirmation_artifact_reference(
        confirmation_id=confirmation_id,
        confirmation_payload=confirmation_payload,
        confirmation_card=card,
    )
    metadata: dict[str, Any] = {
        **source_message.metadata,
        "conversation_mode": "confirm",
        "agent_runtime_stage_outcome": "await_approval",
        "confirmation_card": card,
        "confirmation_payload": confirmation_payload,
        "active_confirmation_reference": reference.model_dump(mode="python"),
        "artifact_references": [reference.model_dump(mode="python")],
    }
    for key, value in (metadata_extra or {}).items():
        if value is None:
            metadata.pop(key, None)
        else:
            metadata[key] = value
    content = str(card.get("summary") or "")
    updated = update_message_artifact(
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=source_message.id,
        content=content,
        metadata=metadata,
        expected_source_metadata=expected_source_metadata,
        expected_latest_message_id=expected_latest_message_id,
        preview=message_preview(
            content, role=str(source_message.role), metadata=metadata
        ),
    )
    if runtime_workflow is not None:
        _sync_runtime_checkpoint_with_card(
            workflow=runtime_workflow,
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=source_message.id,
            confirmation_payload=confirmation_payload,
            reference=reference,
        )
    return updated


def _persisted_card_message(
    *,
    user_id: str,
    conversation_id: str,
    message_id: str,
) -> Any | None:
    """Fresh read of the persisted card, for post-sync verification only."""
    from argus.api import state as api_state

    gateway = api_state.supabase_gateway
    if gateway is not None:
        try:
            message = gateway.get_message(
                user_id=user_id,
                conversation_id=conversation_id,
                message_id=message_id,
            )
            if message is not None:
                return message
        except Exception:  # noqa: BLE001
            pass
    with api_state.store.conversation_message_lock:
        for existing in api_state.store.messages.get(conversation_id, []):
            if existing.id == message_id:
                return existing
    return None


# One process-wide lock serializes checkpoint syncs. Edits are rare user
# actions and a sync is a few checkpointer round trips, so cross-conversation
# contention is negligible and a single lock avoids an unbounded per-key map.
_CHECKPOINT_SYNC_LOCK = threading.Lock()


def _sync_runtime_checkpoint_with_card(
    *,
    workflow: Any,
    user_id: str,
    conversation_id: str,
    message_id: str,
    confirmation_payload: dict[str, Any],
    reference: Any,
) -> None:
    """Rewrite the checkpoint's view of the pending card to the edited one.

    Best-effort by design: the persisted message is the durable truth and the
    metadata fallback still corrects a missed sync, so a checkpoint write
    failure degrades to the old conditional behaviour instead of failing the
    edit. The failure is logged loudly because it reintroduces the two-source
    drift this sync exists to close.

    Guarded writes serialize the persisted card, but the checkpoint write
    happens after it, so winners could sync out of order. Syncs for a
    process are serialized by a module lock, and after every checkpoint
    write the sync re-reads the persisted card and repeats until the
    payload it wrote is still the durable one, bounded at three passes. The
    checkpointer offers no compare-and-set, so a cross-process interleave
    inside the final read-to-write window can still stale the checkpoint;
    that residue is detected and logged, and the next turn's metadata
    fallback corrects it.
    """
    import asyncio

    from argus.agent_runtime.state.models import (
        ConfirmationPayload,
        StrategySummary,
        TaskSnapshot,
    )

    async def _write(payload: dict[str, Any], active_reference: Any) -> bool:
        config = {"configurable": {"thread_id": conversation_id}}
        state = await workflow.aget_state(config)
        values = getattr(state, "values", None)
        if not isinstance(values, dict) or not values:
            return False
        strategy = StrategySummary.model_validate(payload["strategy"])
        # The pending card's checkpoint owners are the snapshot and the run
        # state. The workflow-level ``confirmation_payload`` channel is the
        # intra-turn launch hand-off and must not carry a card (#440).
        updates: dict[str, Any] = {}
        snapshot = values.get("latest_task_snapshot")
        if isinstance(snapshot, dict):
            snapshot = TaskSnapshot.model_validate(snapshot)
        if isinstance(snapshot, TaskSnapshot):
            updates["latest_task_snapshot"] = snapshot.model_copy(
                update={
                    "pending_strategy_summary": strategy,
                    "active_confirmation_reference": active_reference,
                }
            )
        run_state = values.get("run_state")
        if run_state is not None:
            updates["run_state"] = run_state.model_copy(
                update={
                    "candidate_strategy_draft": strategy,
                    "confirmation_payload": ConfirmationPayload.model_validate(payload),
                }
            )
        # The write is attributed to the terminal node so a resumed graph
        # never re-enters mid-flight; each turn starts fresh from its input.
        from argus.agent_runtime.graph.workflow import WorkflowNode

        await workflow.aupdate_state(
            config, updates, as_node=WorkflowNode.NEXT_STEP.value
        )
        return True

    def _durable_payload() -> tuple[dict[str, Any], dict[str, Any]] | None:
        persisted = _persisted_card_message(
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
        )
        metadata = getattr(persisted, "metadata", None)
        if not isinstance(metadata, dict):
            return None
        payload = metadata.get("confirmation_payload")
        if not isinstance(payload, dict):
            return None
        return payload, metadata

    async def _sync() -> None:
        wrote = await _write(confirmation_payload, reference)
        if not wrote:
            return
        from argus.agent_runtime.confirmation_artifacts import (
            confirmation_artifact_reference,
        )

        written = confirmation_payload
        for _ in range(3):
            durable = _durable_payload()
            if durable is None or durable[0] == written:
                return
            persisted_payload, metadata = durable
            persisted_reference = confirmation_artifact_reference(
                confirmation_id=str(persisted_payload.get("confirmation_id") or ""),
                confirmation_payload=persisted_payload,
                confirmation_card=(
                    metadata.get("confirmation_card")
                    if isinstance(metadata.get("confirmation_card"), dict)
                    else None
                ),
            )
            await _write(persisted_payload, persisted_reference)
            written = persisted_payload
        durable = _durable_payload()
        if durable is not None and durable[0] != written:
            logger.warning(
                "Checkpoint convergence exhausted its passes; the checkpoint "
                "may trail the persisted card until the next turn's fallback",
                conversation_id=conversation_id,
            )

    try:
        with _CHECKPOINT_SYNC_LOCK:
            asyncio.run(_sync())
    except Exception:
        logger.opt(exception=True).warning(
            "In-place card edit could not sync the runtime checkpoint; a "
            "fallback-less turn may read the pre-edit strategy",
            conversation_id=conversation_id,
        )
