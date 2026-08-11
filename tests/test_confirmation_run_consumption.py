"""Pressing Run is a commitment: the card row records it, everyone derives.

The invariant lives at the write path: no confirmation card may be mutated
after its run has been admitted, so every producer, present or future,
inherits the refusal. Consumption is stamped on the card's own row at run
admission, every liveness reader derives from the one oracle, and a run
that dies without a result restores the card through the same guarded
writer, so the user who cancels a queued run edits and runs again, losing
nothing.
"""

from __future__ import annotations

import copy

import pytest
from argus.api import state as api_state
from argus.api.chat.actions import (
    latest_active_confirmation_id,
    pending_confirmation_exists,
)
from argus.api.chat.confirmation import (
    DeadConfirmationCardError,
    apply_pending_card_update,
    consume_pending_card_for_run,
    restore_pending_card_after_run,
    restore_pending_card_for_failed_job,
)
from argus.api.chat.recovery import confirmation_metadata_fallback_context

from tests.test_confirmation_direct_edit import (
    CONFIRMATION_ID,
    _conversation,
    _direct_edit,
    _plant_confirmation,
)
from tests.test_pending_card_conflict import _card_message, _client


def _consume(conversation_id: str, owner: str, **kwargs) -> str:
    card = _card_message(conversation_id)
    return consume_pending_card_for_run(
        user_id=owner,
        conversation_id=conversation_id,
        message_id=card.id,
        **kwargs,
    )


def test_no_card_mutation_after_its_run_was_admitted() -> None:
    """The write-path invariant: even a producer holding a fresh, matching
    read of the consumed card is refused; the guard is the writer's, not
    the route's."""
    client = _client()
    conversation = _conversation(client)
    _plant_confirmation(client, conversation["id"])
    owner = api_state.store.conversation_owners[conversation["id"]]
    assert _consume(conversation["id"], owner) == "consumed"

    card = _card_message(conversation["id"])
    fresh_read = copy.deepcopy(card.metadata)
    payload = copy.deepcopy(card.metadata["confirmation_payload"])
    payload["strategy"]["capital_amount"] = 25000
    with pytest.raises(DeadConfirmationCardError):
        apply_pending_card_update(
            user_id=owner,
            conversation_id=conversation["id"],
            source_message=card,
            expected_source_metadata=fresh_read,
            expected_latest_message_id=card.id,
            confirmation_id=CONFIRMATION_ID,
            confirmation_payload=payload,
            language="en",
        )
    stored = _card_message(conversation["id"])
    assert (
        stored.metadata["confirmation_payload"]["strategy"]["capital_amount"] == 10000
    ), "a consumed card keeps the values its run was admitted with"


def test_the_no_race_sequence_cannot_split_card_and_result() -> None:
    """Admit a run, try to edit in place, let the worker finish: the edit
    is refused with no race required, so the conversation can never show a
    result computed from pre-edit values under a card claiming post-edit
    ones."""
    client = _client()
    conversation = _conversation(client)
    _plant_confirmation(client, conversation["id"])
    owner = api_state.store.conversation_owners[conversation["id"]]
    before = _card_message(conversation["id"])
    count_before = len(api_state.store.messages[conversation["id"]])

    assert _consume(conversation["id"], owner) == "consumed"
    response = _direct_edit(
        client, conversation["id"], CONFIRMATION_ID, {"capital": 25000}
    )
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "artifact_action_invalid_state"

    # The background worker then finalizes without appending anything: the
    # card still carries the admitted values, and the transcript grew by
    # nothing, so the projected result and the card describe one strategy.
    after = _card_message(conversation["id"])
    assert (
        after.metadata["confirmation_payload"] == before.metadata["confirmation_payload"]
    )
    assert len(api_state.store.messages[conversation["id"]]) == count_before


def test_every_liveness_reader_derives_from_the_stamp() -> None:
    client = _client()
    conversation = _conversation(client)
    _plant_confirmation(client, conversation["id"])
    owner = api_state.store.conversation_owners[conversation["id"]]
    assert (
        latest_active_confirmation_id(user_id=owner, conversation_id=conversation["id"])
        == CONFIRMATION_ID
    )

    assert _consume(conversation["id"], owner) == "consumed"

    assert (
        latest_active_confirmation_id(user_id=owner, conversation_id=conversation["id"])
        is None
    ), "the action walk derives from the card row"
    assert not pending_confirmation_exists(
        user_id=owner, conversation_id=conversation["id"]
    ), "the pending-existence probe derives from the card row"
    assert (
        confirmation_metadata_fallback_context(
            user_id=owner, conversation_id=conversation["id"]
        )
        is None
    ), "recovery must never resurrect a consumed card as fallback context"


def test_replaying_an_admitted_run_is_idempotent() -> None:
    client = _client()
    conversation = _conversation(client)
    _plant_confirmation(client, conversation["id"])
    owner = api_state.store.conversation_owners[conversation["id"]]
    assert _consume(conversation["id"], owner) == "consumed"
    assert _consume(conversation["id"], owner) == "already_consumed"


def test_a_click_whose_card_changed_refuses_to_consume() -> None:
    """The run's basis is the card as clicked: when the card's launch hash
    no longer matches the admitted run, consumption refuses and the card
    stays live for the edit that won."""
    client = _client()
    conversation = _conversation(client)
    _plant_confirmation(client, conversation["id"])
    owner = api_state.store.conversation_owners[conversation["id"]]
    # Materialize the reference (an in-place edit writes it to the row).
    response = _direct_edit(
        client, conversation["id"], CONFIRMATION_ID, {"capital": 20000}
    )
    assert response.status_code == 200, response.text

    outcome = _consume(
        conversation["id"], owner, expected_launch_payload_hash="not-the-hash"
    )
    assert outcome == "stale_card"
    card = _card_message(conversation["id"])
    assert (
        card.metadata["confirmation_card"]["confirmation_state"] == "active"
    ), "a refused consumption must not stamp the card"


def test_a_run_that_dies_without_a_result_gives_the_card_back() -> None:
    """Cancel the queued run, edit, run again, lose nothing: the terminal
    without-result path restores the card to active, and the edit that was
    refused while consumed now applies."""
    client = _client()
    conversation = _conversation(client)
    _plant_confirmation(client, conversation["id"])
    owner = api_state.store.conversation_owners[conversation["id"]]
    card = _card_message(conversation["id"])
    assert _consume(conversation["id"], owner) == "consumed"
    refused = _direct_edit(
        client, conversation["id"], CONFIRMATION_ID, {"capital": 25000}
    )
    assert refused.status_code == 409

    restore_pending_card_for_failed_job(
        None,
        user_id=owner,
        job={
            "status": "canceled",
            "confirmation_message_id": card.id,
            "conversation_id": conversation["id"],
        },
    )

    assert (
        latest_active_confirmation_id(user_id=owner, conversation_id=conversation["id"])
        == CONFIRMATION_ID
    )
    retried = _direct_edit(
        client, conversation["id"], CONFIRMATION_ID, {"capital": 25000}
    )
    assert retried.status_code == 200, retried.text
    stored = _card_message(conversation["id"])
    assert stored.metadata["confirmation_payload"]["strategy"]["capital_amount"] == 25000


def test_a_failed_run_never_resurrects_a_cancelled_card() -> None:
    client = _client()
    conversation = _conversation(client)
    _plant_confirmation(client, conversation["id"])
    owner = api_state.store.conversation_owners[conversation["id"]]
    card = _card_message(conversation["id"])
    with api_state.store.conversation_message_lock:
        cancelled = copy.deepcopy(card.metadata)
        cancelled["confirmation_card"]["confirmation_state"] = "cancelled"
        messages = api_state.store.messages[conversation["id"]]
        for index, existing in enumerate(messages):
            if existing.id == card.id:
                messages[index] = existing.model_copy(update={"metadata": cancelled})

    assert not restore_pending_card_after_run(
        user_id=owner,
        conversation_id=conversation["id"],
        message_id=card.id,
    )
    stored = _card_message(conversation["id"])
    assert stored.metadata["confirmation_card"]["confirmation_state"] == (
        "cancelled"
    ), "only a consumed card is restorable; user-closed cards stay closed"


def test_a_legacy_transcript_still_reads_dead_after_its_result() -> None:
    """Durable transcripts from before the stamp carry consumption only as
    a later result message; the compatibility clause keeps them dead."""
    from argus.api.message_store import create_message

    client = _client()
    conversation = _conversation(client)
    _plant_confirmation(client, conversation["id"])
    owner = api_state.store.conversation_owners[conversation["id"]]
    create_message(
        user_id=owner,
        conversation_id=conversation["id"],
        role="assistant",
        content="Here is the result.",
        metadata={"result_card": {"run_id": "legacy-run"}},
    )
    assert (
        latest_active_confirmation_id(user_id=owner, conversation_id=conversation["id"])
        is None
    )


def test_restoration_requires_terminal_without_result() -> None:
    """Only a run that died without a result gives the card back: a
    succeeded job, or a failed-looking row that carries a result, must
    never reactivate its consumed card, whichever reconciler lost the
    race."""
    client = _client()
    conversation = _conversation(client)
    _plant_confirmation(client, conversation["id"])
    owner = api_state.store.conversation_owners[conversation["id"]]
    card = _card_message(conversation["id"])
    assert _consume(conversation["id"], owner) == "consumed"

    for job in (
        {"status": "succeeded"},
        {"status": "failed", "result_run_id": "run-1"},
        {},
    ):
        restore_pending_card_for_failed_job(
            None,
            user_id=owner,
            job={
                **job,
                "confirmation_message_id": card.id,
                "conversation_id": conversation["id"],
            },
        )
        stored = _card_message(conversation["id"])
        assert stored.metadata["confirmation_card"]["confirmation_state"] == (
            "consumed"
        ), f"job shape {job} must not reactivate the card"
