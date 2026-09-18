"""An answer that weighs options carries one calculation card per option, and the
answer stays the unit: one marker over every card, one decision that re-runs
every option, one Search dossier, and a comparison only between answers of one
calculation."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from argus.agent_runtime.answer_calculation import (
    ANSWER_ASSUMPTIONS_KEY,
    ANSWER_TEMPLATE_KEY,
    figure_text,
    unstated_assumptions,
)
from argus.api import guest_access
from argus.api import public_excerpts as receipts
from argus.api import state as api_state
from argus.api.chat.computed_answers import OwnedAnswer, _calculation_names, _looked_up
from argus.api.decision_contract import DecisionComputation, DecisionNote
from argus.api.main import app
from argus.api.message_store import create_message
from argus.api.schemas import Message
from argus.domain.answer_dossiers import computed_answer_cards, project_answer_dossier
from argus.domain.computation_marker import computation_from_tool_cards
from argus.domain.public_excerpts import PublicExcerptSourceError
from argus.domain.research.contracts import ResearchPacket
from argus.domain.tool_contracts import ToolResultCard
from faker import Faker
from fastapi.testclient import TestClient

from tests.domain.calculations import WORKED_ARGUMENTS
from tests.domain.calculations.support import run_calculation
from tests.public_excerpt_factories import build_conversation, utc

fake = Faker()

LOAN = {
    "direction": "borrow",
    "currency": "USD",
    "present_value": 200_000,
    "payment": None,
    "future_value": 0,
    "annual_rate_pct": 6,
    "periods": 360,
}
TEMPLATE = (
    "The first loan costs {{first.payment}} a month and the second {{second.payment}}."
)


def _card(kind: str, arguments: dict) -> ToolResultCard:
    """A computed card as an answer publishes it: its own call and artifact."""
    return run_calculation(kind, arguments).model_copy(
        update={"artifact_id": fake.uuid4(), "call_id": f"answer-{uuid4()}"}
    )


def _cards() -> list[ToolResultCard]:
    return [_card("time_value", {**LOAN, "annual_rate_pct": rate}) for rate in (6, 5)]


def _prose(cards: list[ToolResultCard]) -> str:
    return (
        f"The first loan costs {figure_text(cards[0].presentation.answer)} a month "
        f"and the second {figure_text(cards[1].presentation.answer)}."
    )


def _seed(client: TestClient, conversation_id: str, cards: list[ToolResultCard]):
    owner = client.get("/api/v1/me").json()["user"]["id"]
    computation = computation_from_tool_cards(cards)
    assert computation is not None
    return create_message(
        user_id=owner,
        conversation_id=conversation_id,
        role="assistant",
        content=_prose(cards),
        metadata={
            "tool_result_cards": [card.model_dump(mode="json") for card in cards],
            "computation": computation.model_dump(mode="json"),
            ANSWER_TEMPLATE_KEY: {
                "cards": {"first": cards[0].artifact_id, "second": cards[1].artifact_id},
                "text": TEMPLATE,
                "language": "en",
            },
        },
    )


@pytest.fixture
def answer():
    client = TestClient(app)
    client.post("/api/v1/dev/reset")
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]
    cards = _cards()
    return client, conversation["id"], _seed(client, conversation["id"], cards), cards


def test_the_marker_holds_every_calculation_card_in_order() -> None:
    cards = _cards()
    computation = computation_from_tool_cards(cards)
    assert computation is not None
    assert computation.kinds == ["time_value", "time_value"]
    assert [item.inputs for item in computation.calculations] == [
        card.arguments for card in cards
    ]
    stored = computation.model_dump(mode="json")
    assert set(stored) == {"calculations"}
    assert DecisionComputation.model_validate(stored) == computation
    single = computation_from_tool_cards(cards[:1])
    assert single is not None
    assert set(single.model_dump(mode="json")) == {
        "kind",
        "inputs",
    }, "one calculation keeps the shape every stored marker has"


def test_recomputing_one_option_rederives_the_marker_and_prose_from_every_card(
    answer,
) -> None:
    client, conversation_id, message, cards = answer
    response = client.post(
        f"/api/v1/conversations/{conversation_id}/tool-results/{cards[1].artifact_id}/recompute",
        json={
            "message_id": message.id,
            "input_revision": 0,
            "arguments": {"annual_rate_pct": 4},
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()["message"]
    stored = [
        ToolResultCard.model_validate(card)
        for card in body["metadata"]["tool_result_cards"]
    ]
    assert stored[0].arguments == cards[0].arguments
    assert stored[1].arguments["annual_rate_pct"] == 4
    marker = DecisionComputation.model_validate(body["metadata"]["computation"])
    assert [item.inputs for item in marker.calculations] == [
        card.arguments for card in stored
    ]
    assert body["content"] == _prose(stored)


def test_one_decision_stores_every_option_and_reopening_re_runs_each(answer) -> None:
    client, conversation_id, message, cards = answer
    route = f"/api/v1/conversations/{conversation_id}/messages/{message.id}/decision"
    decided = client.post(route, json={"decision_state": "watching"})
    assert decided.status_code == 200, decided.text
    decision = decided.json()["decision"]
    stored = DecisionComputation.model_validate(decision["computation"])
    assert [item.inputs for item in stored.calculations] == [
        card.arguments for card in cards
    ]
    again = client.post(route, json={"decision_state": "promising"})
    assert (
        again.json()["decision"]["id"] == decision["id"]
    ), "the answer holds one decision"

    opened = client.get(f"/api/v1/decisions/{decision['id']}")
    assert opened.status_code == 200, opened.text
    reruns = opened.json()["reruns"]
    assert [rerun["status"] for rerun in reruns] == ["computed", "computed"]
    payments = [rerun["result"]["presentation"]["answer"]["value"] for rerun in reruns]
    assert payments == [pytest.approx(card.presentation.answer.value) for card in cards]

    edited = client.post(
        f"/api/v1/decisions/{decision['id']}/rerun",
        json={"inputs": {"annual_rate_pct": 4}, "calculation": 1},
    )
    assert edited.status_code == 200, edited.text
    first, second = edited.json()["reruns"]
    assert first["result"]["presentation"]["answer"]["value"] == pytest.approx(
        payments[0]
    )
    assert second["inputs"]["annual_rate_pct"] == 4
    assert second["result"]["presentation"]["answer"]["value"] < payments[1]
    nowhere = client.post(
        f"/api/v1/decisions/{decision['id']}/rerun",
        json={"inputs": {"annual_rate_pct": 4}, "calculation": 3},
    )
    assert nowhere.status_code == 422


def test_search_re_runs_every_option_beside_the_untouched_answer(answer) -> None:
    client, conversation_id, message, cards = answer
    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages/{message.id}/computation/rerun",
        json={"inputs": {"periods": 240}, "calculation": 0},
    )
    assert response.status_code == 200, response.text
    first, second = response.json()["reruns"]
    assert first["inputs"]["periods"] == 240
    assert second["inputs"] == cards[1].arguments
    kept = api_state.store.messages[conversation_id][-1]
    assert kept.metadata["tool_result_cards"][0]["arguments"] == cards[0].arguments


def test_a_decision_stored_in_the_one_calculation_shape_still_opens(answer) -> None:
    client, conversation_id, message, cards = answer
    owner = client.get("/api/v1/me").json()["user"]["id"]
    now = datetime.now(timezone.utc)
    legacy = DecisionNote.model_validate(
        {
            "id": fake.uuid4(),
            "source_conversation_id": conversation_id,
            "source_message_id": message.id,
            "computation": {"kind": "time_value", "inputs": cards[0].arguments},
            "decision_state": "watching",
            "created_at": now,
            "updated_at": now,
        }
    )
    api_state.store.decision_notes[legacy.id] = legacy
    api_state.store.decision_note_owners[legacy.id] = owner
    opened = client.get(f"/api/v1/decisions/{legacy.id}")
    assert opened.status_code == 200, opened.text
    body = opened.json()
    assert body["computation"]["kind"] == "time_value"
    assert [rerun["status"] for rerun in body["reruns"]] == ["computed"]


def test_the_dossier_carries_every_card_the_marker_names(answer) -> None:
    _, _, message, cards = answer
    row = message.model_dump(mode="python")
    found = computed_answer_cards(row)
    assert found is not None
    assert [card.artifact_id for card in found] == [card.artifact_id for card in cards]
    dossier = project_answer_dossier(
        message=row,
        cards=found,
        asked="Which loan costs less each month?",
        decision=None,
        decision_action_availability="available",
    )
    assert [card["artifact_id"] for card in dossier.cards] == [
        card.artifact_id for card in cards
    ]
    missing = {
        **row,
        "metadata": {
            **row["metadata"],
            "tool_result_cards": row["metadata"]["tool_result_cards"][:1],
        },
    }
    assert computed_answer_cards(missing) is None


def test_compare_refuses_an_answer_weighing_options_and_continue_carries_every_card(
    answer,
) -> None:
    client, conversation_id, message, cards = answer
    other = client.post("/api/v1/conversations", json={}).json()["conversation"]
    second = _seed(client, other["id"], _cards())
    compared = client.post(
        "/api/v1/computations/compare",
        json={
            "left": {"conversation_id": conversation_id, "message_id": message.id},
            "right": {"conversation_id": other["id"], "message_id": second.id},
        },
    )
    assert compared.status_code == 422, compared.text

    continued = client.post(
        f"/api/v1/conversations/{conversation_id}/messages/{message.id}/continue"
    )
    assert continued.status_code == 200, continued.text
    new_id = continued.json()["conversation"]["id"]
    carried = api_state.store.messages[new_id][-1].metadata
    copies = [
        ToolResultCard.model_validate(card) for card in carried["tool_result_cards"]
    ]
    assert [card.arguments for card in copies] == [card.arguments for card in cards]
    assert not {card.artifact_id for card in copies} & {
        card.artifact_id for card in cards
    }
    marker = DecisionComputation.model_validate(carried["computation"])
    assert marker.kinds == ["time_value", "time_value"]


def test_refresh_matches_each_looked_up_calculation_to_its_card_by_name(answer) -> None:
    _, _, message, cards = answer
    owned = OwnedAnswer(
        message=message,
        cards=cards,
        computation=computation_from_tool_cards(cards),
        asked=None,
    )
    assert _calculation_names(owned) == ["first", "second"]
    packet = ResearchPacket(
        answer_markdown="Looked up again.",
        calculations=(
            {"name": "Second", "kind": "time_value", "inputs": []},
            {"name": "first", "kind": "time_value", "inputs": []},
        ),
    )
    assert _looked_up(packet, name="first", kind="time_value", single=False)["name"] == (
        "first"
    )
    assert _looked_up(packet, name="second", kind="time_value", single=False)["name"] == (
        "Second"
    )
    assert _looked_up(packet, name="third", kind="time_value", single=False) is None
    assert _looked_up(packet, name="any", kind="bond_value", single=True) is None


CITED_PRICE = {
    "currency": "USD",
    "symbol": "AAPL",
    "price": 150,
    "per_share": 6.25,
    "multiple": None,
    "sources": {
        "price": {
            "kind": "page",
            "title": "Apple quote",
            "url": "https://www.nasdaq.com/market-activity/stocks/aapl",
            "date": "2026-09-10",
        }
    },
}


@pytest.fixture
def sharer(monkeypatch):
    # The owner shares from a clean request context, whatever an earlier test left.
    token = guest_access._current_account_context.set(None)
    monkeypatch.setattr(api_state, "supabase_gateway", None)
    api_state.store.reset()
    user = api_state.store.get_or_create_dev_user()
    conversation = build_conversation()
    api_state.store.conversations[conversation.id] = conversation
    api_state.store.conversation_owners[conversation.id] = user.id
    yield user, conversation
    guest_access._current_account_context.reset(token)


def _shared(sharer, cards: list[ToolResultCard], *, index: int) -> Message:
    _, conversation = sharer
    computation = computation_from_tool_cards(cards)
    assert computation is not None
    question = Message(
        id=str(uuid4()),
        role="user",
        content="Which multiple is lower?",
        created_at=utc(index * 2),
        conversation_id=conversation.id,
    )
    answer = Message(
        id=str(uuid4()),
        role="assistant",
        content="Here are both multiples.",
        created_at=utc(index * 2 + 1),
        conversation_id=conversation.id,
        metadata={
            "agent_runtime_turn": {"terminal": True, "status": "completed"},
            "tool_result_cards": [card.model_dump(mode="json") for card in cards],
            "computation": computation.model_dump(mode="json"),
        },
    )
    api_state.store.messages.setdefault(conversation.id, []).extend([question, answer])
    return answer


def test_receipt_freezes_user_inputs_but_unknown_private_card_inputs_refuse(
    sharer,
) -> None:
    user, conversation = sharer
    cards = [
        _card("price_multiple", CITED_PRICE),
        _card("price_multiple", {**CITED_PRICE, "price": 180}),
    ]
    answer = _shared(sharer, cards, index=0)
    preview = receipts.preview_receipt_for_messages(
        user=user,
        conversation_id=conversation.id,
        message_ids=[answer.id],
        owner_note=None,
    )
    leaf = preview.payload.turns[0]
    assert [item.answer.value for item in leaf.calculations] == [
        card.presentation.answer.value for card in cards
    ]
    frozen = leaf.model_dump(mode="json")
    assert "title" not in frozen and len(frozen["calculations"]) == 2
    assert "6.25" in str(frozen), "the exact preview includes the input the owner wrote"

    mixed = _shared(
        sharer,
        [
            _card("price_multiple", CITED_PRICE),
            _card("ranked_comparison", WORKED_ARGUMENTS["ranked_comparison"]),
        ],
        index=1,
    )
    selected = dict(
        user=user,
        conversation_id=conversation.id,
        message_ids=[mixed.id],
        owner_note=None,
    )
    accepted = receipts.preview_receipt_for_messages(**selected)
    assert len(accepted.payload.turns[0].calculations) == 2
    # The known user-written inputs qualify without page citations. If their
    # provenance is absent, ranking rows must not publish private stored facts.
    for fact in mixed.metadata["tool_result_cards"][1]["presentation"]["inputs"]:
        fact["source"] = None
        fact["visibility"] = "private"
    with pytest.raises(PublicExcerptSourceError) as refused:
        receipts.preview_receipt_for_messages(**selected)
    assert refused.value.reason == "private_inputs"


def test_recomputing_an_assumed_input_the_prose_never_names_drops_it_from_the_line() -> (
    None
):
    client = TestClient(app)
    client.post("/api/v1/dev/reset")
    owner = client.get("/api/v1/me").json()["user"]["id"]
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]
    card = _card(
        "time_value",
        {
            **LOAN,
            "periods_per_year": 12,
            "payment_timing": "end",
            "sources": {"periods": {"kind": "assumption"}},
        },
    )
    template = "The loan costs {{payment}} a month."
    listed = unstated_assumptions(template, {"loan": card})
    assert listed == [{"artifact_id": card.artifact_id, "name": "periods"}]
    computation = computation_from_tool_cards([card])
    assert computation is not None
    message = create_message(
        user_id=owner,
        conversation_id=conversation["id"],
        role="assistant",
        content=f"The loan costs {figure_text(card.presentation.answer)} a month.",
        metadata={
            "tool_result_cards": [card.model_dump(mode="json")],
            "computation": computation.model_dump(mode="json"),
            ANSWER_TEMPLATE_KEY: {
                "cards": {"loan": card.artifact_id},
                "text": template,
                "language": "en",
            },
            ANSWER_ASSUMPTIONS_KEY: listed,
        },
    )
    response = client.post(
        f"/api/v1/conversations/{conversation['id']}/tool-results/{card.artifact_id}/recompute",
        json={
            "message_id": message.id,
            "input_revision": 0,
            "arguments": {"periods": 240},
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()["message"]
    assert (
        body["metadata"][ANSWER_ASSUMPTIONS_KEY] == []
    ), "an edited input is the reader's own"
    revised = ToolResultCard.model_validate(body["metadata"]["tool_result_cards"][0])
    assert (
        body["content"]
        == f"The loan costs {figure_text(revised.presentation.answer)} a month."
    )


def test_two_recomputes_keep_every_other_fact_of_the_answer_and_its_prose_current(
    answer,
) -> None:
    client, _, _, _ = answer
    conversation_id = client.post("/api/v1/conversations", json={}).json()[
        "conversation"
    ]["id"]
    cards = _cards()
    seeded = _seed(client, conversation_id, cards)
    extras = {
        "research": {
            "shape": "balanced",
            "sources": [{"url": "https://example.com/rates", "title": "Rates"}],
        },
        "next_steps": {
            "version": "argus_next_steps/v1",
            "items": [{"type": "question", "text": "How do the totals compare?"}],
        },
        "agent_runtime_turn": {
            "turn_id": "turn-1",
            "status": "completed",
            "terminal": True,
        },
    }
    api_state.store.messages[conversation_id][-1] = seeded.model_copy(
        update={"metadata": {**seeded.metadata, **extras}}
    )
    url = (
        f"/api/v1/conversations/{conversation_id}/tool-results/"
        f"{cards[1].artifact_id}/recompute"
    )
    for revision, rate in ((0, 4), (1, 3)):
        response = client.post(
            url,
            json={
                "message_id": seeded.id,
                "input_revision": revision,
                "arguments": {"annual_rate_pct": rate},
            },
        )
        assert response.status_code == 200, response.text
    body = response.json()["message"]
    for key, value in extras.items():
        assert body["metadata"][key] == value
    assert body["metadata"][ANSWER_TEMPLATE_KEY] == seeded.metadata[ANSWER_TEMPLATE_KEY]
    stored = [
        ToolResultCard.model_validate(card)
        for card in body["metadata"]["tool_result_cards"]
    ]
    assert stored[1].arguments["annual_rate_pct"] == 3
    assert body["content"] == _prose(stored)


def test_continuing_an_answer_points_its_prose_at_the_copied_cards(answer) -> None:
    client, conversation_id, message, _ = answer
    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages/{message.id}/continue"
    )
    assert response.status_code == 200, response.text
    new_id = response.json()["conversation"]["id"]
    continued = client.get(f"/api/v1/conversations/{new_id}/messages").json()["items"][0]
    copies = [
        ToolResultCard.model_validate(card)
        for card in continued["metadata"]["tool_result_cards"]
    ]
    template = continued["metadata"][ANSWER_TEMPLATE_KEY]
    assert template["cards"] == {
        "first": copies[0].artifact_id,
        "second": copies[1].artifact_id,
    }
    assert template["text"] == TEMPLATE
    recomputed = client.post(
        f"/api/v1/conversations/{new_id}/tool-results/{copies[1].artifact_id}/recompute",
        json={
            "message_id": continued["id"],
            "input_revision": 0,
            "arguments": {"annual_rate_pct": 4},
        },
    )
    assert recomputed.status_code == 200, recomputed.text
    body = recomputed.json()["message"]
    stored = [
        ToolResultCard.model_validate(card)
        for card in body["metadata"]["tool_result_cards"]
    ]
    assert body["content"] == _prose(stored)
    assert body["content"] != continued["content"]


def test_recomputing_the_latest_answer_refreshes_the_conversation_preview() -> None:
    client = TestClient(app)
    client.post("/api/v1/dev/reset")
    owner = client.get("/api/v1/me").json()["user"]["id"]
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]
    card = _card("time_value", {**LOAN, "periods_per_year": 12, "payment_timing": "end"})
    template = "The loan costs {{payment}} a month."
    computation = computation_from_tool_cards([card])
    assert computation is not None
    message = create_message(
        user_id=owner,
        conversation_id=conversation["id"],
        role="assistant",
        content=f"The loan costs {figure_text(card.presentation.answer)} a month.",
        metadata={
            "tool_result_cards": [card.model_dump(mode="json")],
            "computation": computation.model_dump(mode="json"),
            ANSWER_TEMPLATE_KEY: {
                "cards": {"loan": card.artifact_id},
                "text": template,
                "language": "en",
            },
        },
    )
    response = client.post(
        f"/api/v1/conversations/{conversation['id']}/tool-results/{card.artifact_id}/recompute",
        json={
            "message_id": message.id,
            "input_revision": 0,
            "arguments": {"periods": 240},
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()["message"]
    revised = ToolResultCard.model_validate(body["metadata"]["tool_result_cards"][0])
    assert body["content"] != message.content
    preview = api_state.store.conversations[conversation["id"]].last_message_preview
    assert preview is not None
    assert figure_text(revised.presentation.answer) in preview
