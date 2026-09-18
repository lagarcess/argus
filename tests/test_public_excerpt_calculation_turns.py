"""Step 14: a computed answer is a receipt kind of its own under schema v2.

The receipt freezes the card's typed facts: title, answer, rows, notes, and
only the inputs a public page stated. Inputs the user typed, and the card's
arguments, never reach the public payload; a frozen receipt never changes when
the answer is recomputed. Version 1 and the other kinds are unchanged.
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from argus.api import public_excerpts as service
from argus.api import state as api_state
from argus.api.schemas import Message
from argus.domain.computation_marker import computation_from_tool_card
from argus.domain.public_excerpt_kinds import document_kind

from tests.domain.calculations import WORKED_ARGUMENTS
from tests.domain.calculations.support import run_calculation
from tests.public_excerpt_factories import build_conversation, utc

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
def owner(monkeypatch):
    monkeypatch.setattr(api_state, "supabase_gateway", None)
    api_state.store.reset()
    user = api_state.store.get_or_create_dev_user()
    conversation = build_conversation()
    api_state.store.conversations[conversation.id] = conversation
    api_state.store.conversation_owners[conversation.id] = user.id
    return user, conversation


def add_calculation(
    owner,
    *,
    index=0,
    kind="price_multiple",
    arguments=CITED_PRICE,
    question="Is Apple expensive at this P/E?",
    metadata_update=None,
    with_question=True,
):
    _, conversation = owner
    card = run_calculation(kind, arguments).model_copy(
        update={"artifact_id": str(uuid4())}
    )
    metadata = {
        "agent_runtime_turn": {"terminal": True, "status": "completed"},
        "tool_result_cards": [card.model_dump(mode="json")],
        "computation": computation_from_tool_card(card).model_dump(mode="json"),
    }
    metadata.update(metadata_update or {})
    messages = []
    if with_question:
        messages.append(
            Message(
                id=str(uuid4()),
                role="user",
                content=question,
                created_at=utc(index * 2),
                conversation_id=conversation.id,
            )
        )
    answer = Message(
        id=str(uuid4()),
        role="assistant",
        content="Here is that multiple.",
        created_at=utc(index * 2 + 1),
        conversation_id=conversation.id,
        metadata=metadata,
    )
    messages.append(answer)
    api_state.store.messages.setdefault(conversation.id, []).extend(messages)
    return answer, card


def preview(owner, messages, note=None):
    user, conversation = owner
    return service.preview_receipt_for_messages(
        user=user,
        conversation_id=conversation.id,
        message_ids=[message.id for message in messages],
        owner_note=note,
    )


def test_a_computed_answer_previews_visible_user_inputs_and_public_sources(owner):
    answer, card = add_calculation(owner)
    result = preview(owner, [answer])
    assert result.payload.schema_version == 2
    assert document_kind(result.payload) == "calculation"
    leaf = result.payload.turns[0]
    assert leaf.kind == "calculation"
    assert leaf.question == "Is Apple expensive at this P/E?"
    (calculation,) = leaf.calculations
    assert calculation.title.locale_key == card.presentation.title.locale_key
    assert calculation.answer.value == card.presentation.answer.value
    assert [fact.value for fact in calculation.inputs] == [
        fact.value for fact in card.presentation.inputs if fact.value is not None
    ]
    cited = next(fact for fact in calculation.inputs if fact.source is not None)
    assert cited.source.url == CITED_PRICE["sources"]["price"]["url"]
    assert cited.source.date == CITED_PRICE["sources"]["price"]["date"]
    assert leaf.framing == "calculation_not_advice"
    document = json.dumps(result.payload.model_dump(mode="json"))
    assert "6.25" in document, "the owner can preview the input they wrote"
    assert "arguments" not in document
    assert '"AAPL"' in document
    assert not api_state.store.public_excerpt_snapshots


def test_ranked_receipt_omits_the_comparison_only_leader_gap(owner):
    arguments = WORKED_ARGUMENTS["ranked_comparison"]
    answer, card = add_calculation(
        owner,
        kind="ranked_comparison",
        arguments={
            **arguments,
            "sources": {
                name: CITED_PRICE["sources"]["price"]
                for name in ("key_label", "prefer")
            },
        },
    )
    (calculation,) = preview(owner, [answer]).payload.turns[0].calculations
    leader_gap = next(fact for fact in card.presentation.rows if fact.name == "gap_0")
    assert all(
        fact.label.interpolation_args != leader_gap.label.interpolation_args
        for fact in calculation.rows
    )
    assert len(calculation.rows) == len(card.presentation.rows) - 1


def test_candidates_name_the_calculation_kind_and_readable_refusals(owner):
    eligible, _ = add_calculation(owner)
    failed, _ = add_calculation(
        owner, index=1, arguments={**CITED_PRICE, "per_share": 0}, question="And at zero?"
    )
    ranked, _ = add_calculation(
        owner,
        index=2,
        kind="ranked_comparison",
        arguments=WORKED_ARGUMENTS["ranked_comparison"],
        question="Which card is cheapest?",
    )
    items = service.receipt_candidates(user=owner[0], conversation_id=owner[1].id).items
    by_id = {item.message_id: item for item in items}
    assert by_id[eligible.id].eligible and by_id[eligible.id].kind == "calculation"
    assert by_id[failed.id].reason == "not_completed"
    assert by_id[ranked.id].eligible
    assert len(preview(owner, [eligible, ranked]).payload.turns) == 2


def test_a_calculation_and_a_research_answer_share_as_a_mixed_receipt(owner):
    from tests.test_public_excerpt_turns import add_pair

    _, research = add_pair(owner, index=5)
    answer, _ = add_calculation(owner)
    result = preview(owner, [answer, research])
    assert document_kind(result.payload) == "mixed"
    assert {turn.kind for turn in result.payload.turns} == {
        "calculation",
        "research_answer",
    }


def test_the_created_receipt_is_frozen_when_the_answer_is_recomputed(owner):
    answer, card = add_calculation(owner)
    document = preview(owner, [answer])
    user, conversation = owner
    service.create_receipt_for_messages(
        user=user,
        conversation_id=conversation.id,
        message_ids=[answer.id],
        owner_note=None,
        expected_digest=document.payload_digest,
    )
    snapshots = api_state.store.public_excerpt_snapshots
    snapshot = (
        next(iter(snapshots.values())) if isinstance(snapshots, dict) else snapshots[0]
    )
    frozen = snapshot.payload.model_dump(mode="json")
    answer.metadata["tool_result_cards"][0]["presentation"]["answer"]["value"] = 999
    assert snapshot.payload.model_dump(mode="json") == frozen
    assert (
        snapshot.payload.turns[0].calculations[0].answer.value
        == card.presentation.answer.value
    )


def test_a_continued_result_names_its_missing_question_not_an_unfinished_turn(owner):
    continued, _ = add_calculation(
        owner,
        with_question=False,
        metadata_update={
            "agent_runtime_turn": None,
            "continued_from": {
                "conversation_id": str(uuid4()),
                "message_id": str(uuid4()),
            },
        },
    )
    items = service.receipt_candidates(user=owner[0], conversation_id=owner[1].id).items
    assert [(item.message_id, item.reason) for item in items] == [
        (continued.id, "missing_question")
    ]


def test_the_owner_link_list_titles_a_calculation_by_its_question(owner):
    from argus.domain.public_excerpts import snapshot_list_item

    answer, _ = add_calculation(owner)
    document = preview(owner, [answer])
    user, conversation = owner
    service.create_receipt_for_messages(
        user=user,
        conversation_id=conversation.id,
        message_ids=[answer.id],
        owner_note=None,
        expected_digest=document.payload_digest,
    )
    snapshots = api_state.store.public_excerpt_snapshots
    snapshot = (
        next(iter(snapshots.values())) if isinstance(snapshots, dict) else snapshots[0]
    )
    item = snapshot_list_item(snapshot)
    assert item.title == "Is Apple expensive at this P/E?"
    assert item.kind == "calculation"
    assert item.symbols == []
    assert item.date_range is None
