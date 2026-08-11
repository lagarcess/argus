"""The in-place surface ships dark by default.

Three review rounds found real defects in the run-consumption guard, so
the surface is behind ARGUS_IN_PLACE_CARD_EDITS_ENABLED, default off,
until the guard finishes as its own lane. Dark means dark everywhere at
once: the routes answer 404, cards advertise no direct edits so the
frontend renders no pills, and run admission stamps nothing, leaving the
legacy newer-message clause as the only liveness mechanism, exactly as
before the lane.
"""

from __future__ import annotations

from argus.api import state as api_state
from argus.api.chat.confirmation import consume_confirmation_for_admitted_run

from tests.test_confirmation_direct_edit import (
    CONFIRMATION_ID,
    _conversation,
    _direct_edit,
    _plant_confirmation,
)
from tests.test_pending_card_conflict import _card_message, _client


def test_dark_surface_is_dark_everywhere_at_once(monkeypatch) -> None:
    monkeypatch.delenv("ARGUS_IN_PLACE_CARD_EDITS_ENABLED", raising=False)
    client = _client()
    conversation = _conversation(client)
    metadata = _plant_confirmation(client, conversation["id"])

    assert "direct_edits" not in (
        metadata["confirmation_card"].get("capabilities") or {}
    ), "a dark surface must not advertise edit affordances"

    response = _direct_edit(
        client, conversation["id"], CONFIRMATION_ID, {"capital": 25000}
    )
    assert response.status_code == 404, response.text
    assert response.json()["code"] == "not_found"

    peers = client.post(
        f"/api/v1/conversations/{conversation['id']}/confirmations/"
        f"{CONFIRMATION_ID}/peer-assets",
        json={"symbols": ["MSFT"]},
    )
    assert peers.status_code == 404, peers.text

    owner = api_state.store.conversation_owners[conversation["id"]]
    card = _card_message(conversation["id"])
    refusal = consume_confirmation_for_admitted_run(
        gateway=None,
        user_id=owner,
        conversation_id=conversation["id"],
        confirmation_message_id=card.id,
        chat_action=None,
        job_id="job-1",
        utcnow_iso=lambda: "2026-08-11T00:00:00Z",
    )
    assert refusal is None
    stored = _card_message(conversation["id"])
    assert (
        stored.metadata["confirmation_card"]["confirmation_state"] == "active"
    ), "a dark surface stamps nothing; legacy liveness owns the lifecycle"


def test_enabled_surface_advertises_and_serves(monkeypatch) -> None:
    monkeypatch.setenv("ARGUS_IN_PLACE_CARD_EDITS_ENABLED", "true")
    client = _client()
    conversation = _conversation(client)
    metadata = _plant_confirmation(client, conversation["id"])
    capabilities = metadata["confirmation_card"]["capabilities"]
    assert "dates" in capabilities["direct_edits"]
    assert "edit_constraints" in capabilities

    response = _direct_edit(
        client, conversation["id"], CONFIRMATION_ID, {"capital": 25000}
    )
    assert response.status_code == 200, response.text
