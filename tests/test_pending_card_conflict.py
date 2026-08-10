"""A non-turn rewrite is conditional on what its caller read.

Two writers that both read the same card must not silently roll each other
back: the first write wins, the second surfaces as a conflict, and the
stored card keeps the winner's values. The rewrite also owns its
projections: the conversation's denormalized preview follows the rewritten
card while that card is the latest message, and a non-turn change never
reorders recents.
"""

from __future__ import annotations

import copy

import pytest
from argus.api import state as api_state
from argus.api.message_store import (
    create_message,
    message_preview,
    update_message_artifact,
)
from argus.domain.supabase_conversation_messages import StaleMessageArtifactError

from tests.test_confirmation_direct_edit import (
    CONFIRMATION_ID,
    _conversation,
    _direct_edit,
    _plant_confirmation,
)


def _client():
    from argus.api.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    client.post("/api/v1/dev/reset")
    return client


def _card_message(conversation_id: str):
    with api_state.store.conversation_message_lock:
        for message in api_state.store.messages.get(conversation_id, []):
            card = (message.metadata or {}).get("confirmation_card")
            if isinstance(card, dict) and card.get("confirmation_id") == (
                CONFIRMATION_ID
            ):
                return message
    raise AssertionError("planted confirmation card not found")


def test_stale_writer_conflicts_and_rolls_nothing_back() -> None:
    """A writer whose read predates another writer's edit must conflict;
    the winner's values survive untouched."""
    client = _client()
    conversation = _conversation(client)
    _plant_confirmation(client, conversation["id"])
    stale_read = copy.deepcopy(_card_message(conversation["id"]).metadata)
    owner = api_state.store.conversation_owners[conversation["id"]]

    response = _direct_edit(
        client, conversation["id"], CONFIRMATION_ID, {"capital": 25000}
    )
    assert response.status_code == 200, response.text
    winner = _card_message(conversation["id"])

    with pytest.raises(StaleMessageArtifactError):
        update_message_artifact(
            user_id=owner,
            conversation_id=conversation["id"],
            message_id=winner.id,
            content="stale rewrite",
            metadata={"conversation_mode": "confirm"},
            expected_source_metadata=stale_read,
            expected_latest_message_id=winner.id,
        )

    stored = _card_message(conversation["id"])
    assert stored.content == winner.content
    payload = stored.metadata["confirmation_payload"]
    assert (
        payload["strategy"]["capital_amount"] == 25000
    ), "the losing writer must not roll back the winning edit"


def test_an_append_between_read_and_write_conflicts() -> None:
    """Every superseding event appends a message; a write whose activity
    expectation predates an append must conflict, because the caller's
    active-confirmation check may no longer hold."""
    client = _client()
    conversation = _conversation(client)
    _plant_confirmation(client, conversation["id"])
    owner = api_state.store.conversation_owners[conversation["id"]]
    card = _card_message(conversation["id"])
    stale_view = copy.deepcopy(card.metadata)
    stale_latest = card.id

    create_message(
        user_id=owner,
        conversation_id=conversation["id"],
        role="assistant",
        content="a superseding turn landed here",
    )

    with pytest.raises(StaleMessageArtifactError):
        update_message_artifact(
            user_id=owner,
            conversation_id=conversation["id"],
            message_id=card.id,
            content="rewrite past a superseding append",
            metadata={"conversation_mode": "confirm"},
            expected_source_metadata=stale_view,
            expected_latest_message_id=stale_latest,
        )

    stored = _card_message(conversation["id"])
    assert (
        stored.content == card.content
    ), "an edit that lost to an append must leave the card untouched"


def test_edit_carries_the_preview_while_the_card_is_latest() -> None:
    client = _client()
    conversation = _conversation(client)
    _plant_confirmation(client, conversation["id"])
    before = api_state.store.conversations[conversation["id"]]

    response = _direct_edit(
        client, conversation["id"], CONFIRMATION_ID, {"capital": 25000}
    )
    assert response.status_code == 200, response.text
    updated = _card_message(conversation["id"])

    record = api_state.store.conversations[conversation["id"]]
    assert record.last_message_preview == message_preview(
        updated.content, role=updated.role, metadata=updated.metadata
    ), "recents must describe the edited card, not the pre-edit one"
    assert (
        record.updated_at == before.updated_at
    ), "a non-turn change spends nothing and must not reorder recents"


def test_edit_of_a_non_latest_card_leaves_the_preview_alone() -> None:
    """A card behind later messages is still editable through the route,
    because the route's expectations come from its own fresh read: the
    activity guard rejects interleaved appends, never standing history.
    The preview stays with the true latest message."""
    client = _client()
    conversation = _conversation(client)
    _plant_confirmation(client, conversation["id"])
    owner = api_state.store.conversation_owners[conversation["id"]]
    create_message(
        user_id=owner,
        conversation_id=conversation["id"],
        role="user",
        content="How risky is this idea?",
    )
    latest_preview = api_state.store.conversations[
        conversation["id"]
    ].last_message_preview

    response = _direct_edit(
        client, conversation["id"], CONFIRMATION_ID, {"capital": 25000}
    )
    assert response.status_code == 200, response.text

    record = api_state.store.conversations[conversation["id"]]
    assert (
        record.last_message_preview == latest_preview
    ), "editing an older card must not overwrite the newer message's preview"
