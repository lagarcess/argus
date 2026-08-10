"""The runtime checkpoint and the persisted card are one fact, kept together.

After an in-place edit the persisted message is the durable truth, but the
LangGraph checkpoint still holds the pre-edit strategy, and a turn whose
metadata fallback carries no snapshot (recovery contexts legitimately have
``latest_task_snapshot=None``; ``build_workflow_input`` only overrides the
channel when a fallback snapshot exists, ``runtime.py:84``) reads the
checkpoint as-is. Two sources of truth with one going stale is the design
defect; the write path, ``apply_pending_card_update``, must keep both
consistent so no later turn can depend on a caller remembering the fallback.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from argus.agent_runtime.confirmation_artifacts import confirmation_artifact_reference
from argus.agent_runtime.state.models import (
    RunState,
    StrategySummary,
    TaskSnapshot,
)
from argus.api import state as api_state_module
from argus.api.main import app
from fastapi.testclient import TestClient

from tests.test_confirmation_direct_edit import (
    CONFIRMATION_ID,
    _confirmation_payload,
    _conversation,
    _direct_edit,
    _plant_confirmation,
)


def _client() -> TestClient:
    client = TestClient(app)
    client.post("/api/v1/dev/reset")
    return client


def _seed_checkpoint(
    workflow: Any, conversation_id: str, payload: dict[str, Any]
) -> None:
    """Mimic the checkpoint a real confirmation turn leaves behind."""
    strategy = StrategySummary.model_validate(payload["strategy"])
    reference = confirmation_artifact_reference(
        confirmation_id=CONFIRMATION_ID,
        confirmation_payload=payload,
    )
    snapshot = TaskSnapshot(
        latest_task_type="backtest_execution",
        completed=False,
        pending_strategy_summary=strategy,
        active_confirmation_reference=reference,
        artifact_references=[reference],
    )
    run_state = RunState.new(
        current_user_message="Buy and hold NFLX with $10,000 through 2023",
        recent_thread_history=[],
    )
    asyncio.run(
        workflow.aupdate_state(
            {"configurable": {"thread_id": conversation_id}},
            {
                "latest_task_snapshot": snapshot,
                "confirmation_payload": dict(payload),
                "run_state": run_state,
            },
        )
    )


def _checkpoint_values(workflow: Any, conversation_id: str) -> dict[str, Any]:
    state = asyncio.run(
        workflow.aget_state({"configurable": {"thread_id": conversation_id}})
    )
    values = getattr(state, "values", None)
    return values if isinstance(values, dict) else {}


def test_conversational_turn_after_direct_edit_reads_edited_values() -> None:
    """A fallback-less turn reads the checkpoint verbatim, so the in-place
    write path must have updated it: the pending strategy, the active
    reference's embedded payload, and the confirmation payload channel all
    carry the edited values, never the pre-edit ones."""
    client = _client()
    conversation = _conversation(client)
    payload = _confirmation_payload()
    _plant_confirmation(client, conversation["id"], payload)
    workflow = api_state_module.get_agent_runtime_workflow(SimpleNamespace(app=app))
    _seed_checkpoint(workflow, conversation["id"], payload)

    response = _direct_edit(
        client, conversation["id"], CONFIRMATION_ID, {"capital": 25000}
    )
    assert response.status_code == 200, response.text

    values = _checkpoint_values(workflow, conversation["id"])
    snapshot = values.get("latest_task_snapshot")
    assert isinstance(snapshot, TaskSnapshot)
    assert snapshot.pending_strategy_summary is not None
    assert snapshot.pending_strategy_summary.capital_amount == 25000, (
        "the checkpoint's pending strategy must carry the edited capital; a "
        "turn without a fallback snapshot reads exactly this value"
    )
    reference = snapshot.active_confirmation_reference
    assert reference is not None
    embedded = reference.metadata.get("confirmation_payload")
    assert isinstance(embedded, dict)
    assert embedded["strategy"]["capital_amount"] == 25000, (
        "the reference's embedded payload is what the interpreter treats as "
        "the effective strategy; it must not describe the pre-edit card"
    )
    channel_payload = values.get("confirmation_payload")
    assert isinstance(channel_payload, dict)
    assert channel_payload["strategy"]["capital_amount"] == 25000
    run_state = values.get("run_state")
    assert run_state is not None
    assert run_state.confirmation_payload is not None
    assert run_state.confirmation_payload.strategy.capital_amount == 25000


def test_late_sync_converges_to_the_persisted_card() -> None:
    """A checkpoint sync that lost the write race re-reads the persisted
    card and converges on it: whatever order syncs land in, the checkpoint
    ends describing the durable record."""
    client = _client()
    conversation = _conversation(client)
    payload = _confirmation_payload()
    _plant_confirmation(client, conversation["id"], payload)
    workflow = api_state_module.get_agent_runtime_workflow(SimpleNamespace(app=app))
    _seed_checkpoint(workflow, conversation["id"], payload)

    response = _direct_edit(
        client, conversation["id"], CONFIRMATION_ID, {"capital": 25000}
    )
    assert response.status_code == 200, response.text
    message_id = response.json()["message"]["id"]

    # Replay the pre-edit sync as if it had been delayed past the edit's own.
    from argus.api.chat.confirmation import _sync_runtime_checkpoint_with_card

    stale_payload = _confirmation_payload()
    stale_payload["confirmation_id"] = CONFIRMATION_ID
    stale_payload["artifact_id"] = CONFIRMATION_ID
    stale_reference = confirmation_artifact_reference(
        confirmation_id=CONFIRMATION_ID,
        confirmation_payload=stale_payload,
    )
    owner = api_state_module.store.conversation_owners[conversation["id"]]
    _sync_runtime_checkpoint_with_card(
        workflow=workflow,
        user_id=owner,
        conversation_id=conversation["id"],
        message_id=message_id,
        confirmation_payload=stale_payload,
        reference=stale_reference,
    )

    values = _checkpoint_values(workflow, conversation["id"])
    snapshot = values.get("latest_task_snapshot")
    assert isinstance(snapshot, TaskSnapshot)
    assert snapshot.pending_strategy_summary is not None
    assert snapshot.pending_strategy_summary.capital_amount == 25000, (
        "a delayed stale sync must converge to the persisted card, not "
        "clobber the newer edit"
    )
    channel_payload = values.get("confirmation_payload")
    assert isinstance(channel_payload, dict)
    assert channel_payload["strategy"]["capital_amount"] == 25000


def test_edit_without_a_checkpoint_still_succeeds() -> None:
    """A card planted outside the runtime (no checkpoint) edits normally;
    the sync is a consistency obligation, not a precondition."""
    client = _client()
    conversation = _conversation(client)
    _plant_confirmation(client, conversation["id"])

    response = _direct_edit(
        client, conversation["id"], CONFIRMATION_ID, {"capital": 25000}
    )
    assert response.status_code == 200, response.text
    payload = response.json()["message"]["metadata"]["confirmation_payload"]
    assert payload["strategy"]["capital_amount"] == 25000
