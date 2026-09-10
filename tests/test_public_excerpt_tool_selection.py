"""Selected tool answers share one immutable document and revision boundary."""

from __future__ import annotations

import pytest
from argus.api import public_excerpts as service
from argus.api import state as api_state
from argus.domain.public_excerpts import PublicExcerptSourceError
from argus.domain.tool_contracts import ToolResultCard
from argus.domain.tool_declaration import ToolCatalog

from tests import test_public_excerpt_turns as turn_fixtures
from tests.public_excerpt_tool_factories import identity_declaration
from tests.test_public_excerpt_turns import add_pair, create, preview
from tests.test_tool_result_publication import card_document


@pytest.fixture
def owner(monkeypatch):
    return turn_fixtures.owner.__wrapped__(monkeypatch)


@pytest.fixture(autouse=True)
def catalog(monkeypatch):
    from argus.domain import public_excerpt_tool_turns

    declarations = [identity_declaration()]
    monkeypatch.setattr(
        public_excerpt_tool_turns,
        "get_tool_catalog",
        lambda **_: ToolCatalog(tuple(declarations)),
    )
    return declarations


def add_tools(owner, *, index=0, count=2):
    cards = [card_document() for _ in range(count)]
    _, answer = add_pair(
        owner,
        index=index,
        question="What are the provided values?",
        answer="",
        metadata={
            "agent_runtime_turn": {"terminal": True, "status": "completed"},
            "tool_result_cards": cards,
        },
    )
    return answer, cards


def test_sibling_cards_are_ordered_inside_one_selected_turn(owner):
    answer, cards = add_tools(owner)
    result = preview(owner, [answer])
    assert result.kind == "tool_result"
    assert len(result.payload.turns) == 1
    leaf = result.payload.turns[0]
    assert leaf.kind == "tool_result"
    assert [card.presentation for card in leaf.cards] == [
        ToolResultCard.model_validate(card).presentation for card in cards
    ]
    snapshot, created = create(owner, [answer], result)
    assert created and snapshot.payload == result.payload
    assert [str(binding.artifact_id) for binding in snapshot.source_tool_bindings] == [
        card["artifact_id"] for card in cards
    ]
    assert snapshot.source_message_ids == [answer.id]
    assert not snapshot.source_artifact_ids and not snapshot.source_run_ids
    assert not api_state.store.evidence_artifacts and not api_state.store.backtest_runs
    public = service.public_excerpt_reader().read_public_excerpt_view(
        public_id=snapshot.public_id
    )
    encoded = public.model_dump_json()
    for card in cards:
        assert card["artifact_id"] not in encoded and card["call_id"] not in encoded
    assert "arguments" not in encoded


def test_four_messages_with_multiple_calls_remain_four_turns(owner):
    answers = [add_tools(owner, index=index)[0] for index in range(4)]
    result = preview(owner, answers[::-1])
    assert len(result.payload.turns) == 4
    assert all(len(turn.cards) == 2 for turn in result.payload.turns)


@pytest.mark.parametrize(
    "status", ["invalid", "ambiguous", "bounded", "unavailable", "pending"]
)
def test_one_nonanswer_refuses_the_whole_selected_message(owner, status):
    answer, cards = add_tools(owner)
    cards[1]["presentation"]["answer"] = None
    if status != "pending":
        cards[1]["outcome"] = {"status": status, "failure": {"code": "test_failure"}}
    with pytest.raises(PublicExcerptSourceError) as error:
        preview(owner, [answer])
    assert error.value.reason == "not_completed"
    assert not api_state.store.public_excerpt_snapshots


def test_recomputed_revision_gets_new_selection_and_old_snapshot_stays_frozen(owner):
    answer, cards = add_tools(owner)
    before = preview(owner, [answer])
    old, _ = create(owner, [answer], before)
    frozen = old.model_dump_json()
    cards[1]["input_revision"] += 1
    cards[1]["presentation"]["answer"]["value"] = 2
    cards[1]["outcome"]["result"]["value"] = 2
    with pytest.raises(PublicExcerptSourceError) as error:
        create(owner, [answer], before)
    assert error.value.reason == "preview_changed"
    current = preview(owner, [answer])
    new, created = create(owner, [answer], current)
    assert created and new.selection_key != old.selection_key
    assert api_state.store.public_excerpt_snapshots[old.id].model_dump_json() == frozen
    again, created = create(owner, [answer], current)
    assert not created and again.id == new.id


def test_edit_after_projection_is_rejected_at_memory_insert(owner, monkeypatch):
    answer, cards = add_tools(owner)
    document = preview(owner, [answer])
    original = service.MemoryPublicExcerptRepository.create_public_excerpt_snapshot

    def race(self, *, snapshot):
        cards[1]["input_revision"] += 1
        return original(self, snapshot=snapshot)

    monkeypatch.setattr(
        service.MemoryPublicExcerptRepository, "create_public_excerpt_snapshot", race
    )
    with pytest.raises(PublicExcerptSourceError) as error:
        create(owner, [answer], document)
    assert error.value.reason == "preview_changed"
    assert not api_state.store.public_excerpt_snapshots


def test_tool_compatibility_adapter_uses_whole_message_and_exact_revision(owner):
    answer, cards = add_tools(owner)
    user, conversation = owner
    snapshot, _ = service.create_receipt_for_tool_result(
        user=user,
        conversation_id=conversation.id,
        message_id=answer.id,
        artifact_id=cards[0]["artifact_id"],
        input_revision=0,
        owner_note=None,
    )
    assert snapshot.payload.kind == "turns"
    assert len(snapshot.payload.turns[0].cards) == 2
    with pytest.raises(service.EvidenceReceiptSourceChangedError):
        service.create_receipt_for_tool_result(
            user=user,
            conversation_id=conversation.id,
            message_id=answer.id,
            artifact_id=cards[0]["artifact_id"],
            input_revision=1,
            owner_note=None,
        )


@pytest.mark.parametrize("mutation", ["missing", "version", "type", "disabled"])
def test_each_sibling_requires_its_declared_public_binding(owner, catalog, mutation):
    from dataclasses import replace

    answer, cards = add_tools(owner)
    other = replace(identity_declaration(), name="other_identity")
    catalog.append(other)
    cards[1]["tool_name"] = other.name
    if mutation == "missing":
        cards[1]["tool_name"] = "unknown_identity"
    elif mutation == "version":
        cards[1]["card_version"] += 1
    elif mutation == "type":
        cards[1]["card_type"] = "other_card"
    else:
        catalog[-1] = replace(
            other, policy=replace(other.policy, public_receipt="disabled")
        )
    with pytest.raises(PublicExcerptSourceError):
        preview(owner, [answer])
    assert not api_state.store.public_excerpt_snapshots


@pytest.mark.parametrize(
    "problem", [None, "missing_sources", "unlisted_url", "private_text", "invalid_source"]
)
def test_cited_fact_policy_uses_the_shared_source_and_prose_audit(
    owner, catalog, problem
):
    catalog[:] = [identity_declaration(public_receipt="cited_facts")]
    answer, cards = add_tools(owner)
    for card in cards:
        card["presentation"]["sources"] = [
            {"title": "Results", "url": "https://example.test/results"}
        ]
        card["presentation"]["narrative"] = (
            "Read [results](https://example.test/results)."
        )
    if problem == "missing_sources":
        cards[1]["presentation"]["sources"] = []
    elif problem == "unlisted_url":
        cards[1]["presentation"]["narrative"] = "[Other](https://example.test/other)"
    elif problem == "private_text":
        cards[1]["presentation"]["narrative"] = cards[1]["call_id"]
    elif problem == "invalid_source":
        cards[1]["presentation"]["sources"][0]["url"] = (
            "https://user:password@example.test/results"
        )
    if problem is not None:
        with pytest.raises(PublicExcerptSourceError):
            preview(owner, [answer])
    else:
        turn = preview(owner, [answer]).payload.turns[0]
        assert all(card.presentation.narrative is None for card in turn.cards)
        assert all(card.presentation.sources for card in turn.cards)


def test_reordered_or_added_sibling_cannot_publish_an_earlier_preview(owner, monkeypatch):
    answer, cards = add_tools(owner)
    document = preview(owner, [answer])
    original = service.MemoryPublicExcerptRepository.create_public_excerpt_snapshot

    def race(self, *, snapshot):
        cards.reverse()
        return original(self, snapshot=snapshot)

    monkeypatch.setattr(
        service.MemoryPublicExcerptRepository, "create_public_excerpt_snapshot", race
    )
    with pytest.raises(PublicExcerptSourceError) as error:
        create(owner, [answer], document)
    assert error.value.reason == "preview_changed"
    assert not api_state.store.public_excerpt_snapshots


def test_tool_adapter_cannot_publish_an_equal_answer_from_a_new_revision(
    owner, monkeypatch
):
    answer, cards = add_tools(owner)
    user, conversation = owner
    original = service.create_receipt_for_messages

    def recompute_before_shared_create(**kwargs):
        with api_state.store.conversation_message_lock:
            cards[0]["input_revision"] += 1
        return original(**kwargs)

    monkeypatch.setattr(
        service, "create_receipt_for_messages", recompute_before_shared_create
    )
    with pytest.raises(service.EvidenceReceiptSourceChangedError):
        service.create_receipt_for_tool_result(
            user=user,
            conversation_id=conversation.id,
            message_id=answer.id,
            artifact_id=cards[0]["artifact_id"],
            input_revision=0,
            owner_note=None,
        )
    assert not api_state.store.public_excerpt_snapshots
