"""The transcript read derives an answer's decision from the rows that own it.

A stored stamp on a message is a transport copy. The read must show the
current decision_notes row for a result card and for a computed answer, drop a
stamp the owner no longer backs, and keep the copy only when the owner cannot
be read at all.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from argus.api.decision_contract import DecisionComputation, DecisionNote
from argus.api.decision_message_reads import repair_message_decisions
from argus.api.schemas import Message
from argus.domain.supabase_gateway import SupabaseGateway
from faker import Faker

fake = Faker()
NOW = datetime(2026, 9, 8, 12, tzinfo=timezone.utc)


def _artifact_decision(
    artifact_id: str, state: str, *, at: datetime = NOW
) -> DecisionNote:
    return DecisionNote(
        id=fake.uuid4(),
        idea_id=fake.uuid4(),
        idea_version_id=fake.uuid4(),
        evidence_artifact_id=artifact_id,
        decision_state=state,  # type: ignore[arg-type]
        created_at=at,
        updated_at=at,
    )


def _answer_decision(message_id: str, state: str, *, at: datetime = NOW) -> DecisionNote:
    return DecisionNote(
        id=fake.uuid4(),
        source_message_id=message_id,
        computation=DecisionComputation(kind="savings_projection", inputs={"months": 9}),
        decision_state=state,  # type: ignore[arg-type]
        created_at=at,
        updated_at=at,
    )


def _message(
    message_id: str, metadata: dict[str, Any], *, role: str = "assistant"
) -> Message:
    return Message(
        id=message_id,
        conversation_id="conversation-1",
        role=role,  # type: ignore[arg-type]
        content=fake.sentence(),
        created_at=NOW,
        metadata=metadata,
    )


def test_result_card_and_computed_answer_take_their_decision_from_the_owner() -> None:
    artifact_id = fake.uuid4()
    card_message = _message(
        "card-1",
        {
            "result_card": {"title": "AAPL", "evidence_artifact_id": artifact_id},
            "result_run_id": fake.uuid4(),
        },
    )
    answer_message = _message(
        "answer-1",
        {"computation": {"kind": "savings_projection", "inputs": {"months": 9}}},
    )
    plain = _message("plain-1", {})
    user_turn = _message(
        "user-1", {"computation": {"kind": "x", "inputs": {}}}, role="user"
    )
    card_decision = _artifact_decision(artifact_id, "promising")
    answer_decision = _answer_decision("answer-1", "watching")
    requested: list[tuple[list[str], list[str]]] = []

    def load(artifact_ids: list[str], message_ids: list[str]) -> dict[str, DecisionNote]:
        requested.append((artifact_ids, message_ids))
        return {artifact_id: card_decision, "answer-1": answer_decision}

    repaired = repair_message_decisions(
        [card_message, answer_message, plain, user_turn], load_decisions=load
    )

    assert requested == [([artifact_id], ["answer-1"])]
    card = repaired[0].metadata
    assert card["decision_note_id"] == card_decision.id
    assert card["decision_state"] == "promising"
    assert card["result_card"]["decision_note_id"] == card_decision.id
    assert card["result_card"]["decision_state"] == "promising"
    assert card["result_card"]["evidence_lifecycle"] == "decided"
    answer = repaired[1].metadata
    assert answer["decision_note_id"] == answer_decision.id
    assert answer["decision_state"] == "watching"
    assert answer["computation"] == answer_message.metadata["computation"]
    assert repaired[2] is plain
    assert repaired[3] is user_turn


def test_a_stamp_the_owner_no_longer_backs_is_dropped_and_a_newer_row_wins() -> None:
    artifact_id = fake.uuid4()
    stale_card = _message(
        "card-1",
        {
            "decision_note_id": "gone",
            "decision_state": "rejected",
            "result_card": {
                "evidence_artifact_id": artifact_id,
                "decision_note_id": "gone",
                "decision_state": "rejected",
                "evidence_lifecycle": "decided",
            },
        },
    )
    stale_answer = _message(
        "answer-1",
        {
            "computation": {"kind": "savings_projection", "inputs": {}},
            "decision_note_id": "older",
            "decision_state": "rejected",
        },
    )
    newer = _answer_decision("answer-1", "promising", at=NOW + timedelta(minutes=1))

    repaired = repair_message_decisions(
        [stale_card, stale_answer],
        load_decisions=lambda _artifacts, _messages: {"answer-1": newer},
    )

    card = repaired[0].metadata
    assert "decision_note_id" not in card and "decision_state" not in card
    assert "decision_note_id" not in card["result_card"]
    assert "decision_state" not in card["result_card"]
    answer = repaired[1].metadata
    assert answer["decision_note_id"] == newer.id
    assert answer["decision_state"] == "promising"


def test_an_unreadable_owner_keeps_the_copy_and_untouched_pages_load_nothing() -> None:
    stamped = _message(
        "answer-1",
        {
            "computation": {"kind": "savings_projection", "inputs": {}},
            "decision_note_id": "kept",
            "decision_state": "watching",
        },
    )
    calls: list[int] = []

    unchanged = repair_message_decisions(
        [stamped], load_decisions=lambda _a, _m: calls.append(1) or None
    )
    untouched = repair_message_decisions(
        [_message("plain-1", {})], load_decisions=lambda _a, _m: calls.append(2) or {}
    )

    assert unchanged == [stamped]
    assert untouched[0].metadata == {}
    assert calls == [1]


class _Table:
    def __init__(self, client: _Client, table_name: str) -> None:
        self.client = client
        self.table_name = table_name
        self.filters: list[tuple[str, str, Any]] = []

    def select(self, *_args: object, **_kwargs: object) -> _Table:
        return self

    def eq(self, key: str, value: object) -> _Table:
        self.filters.append(("eq", key, value))
        return self

    def in_(self, key: str, values: list[object]) -> _Table:
        self.filters.append(("in", key, list(values)))
        return self

    def execute(self) -> SimpleNamespace:
        self.client.queries.append(list(self.filters))
        rows = self.client.rows_by_table.get(self.table_name, [])
        for kind, key, value in self.filters:
            if kind == "eq":
                rows = [row for row in rows if row.get(key) == value]
            else:
                rows = [row for row in rows if row.get(key) in value]
        return SimpleNamespace(data=[dict(row) for row in rows])


class _Client:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows_by_table = {"decision_notes": rows}
        self.queries: list[list[tuple[str, str, Any]]] = []

    def table(self, table_name: str) -> _Table:
        return _Table(self, table_name)


def test_gateway_reads_current_decisions_per_attachment_in_two_bounded_queries() -> None:
    user_id = fake.uuid4()
    artifact_id = fake.uuid4()
    older = _artifact_decision(artifact_id, "watching")
    newer = _artifact_decision(artifact_id, "promising", at=NOW + timedelta(minutes=1))
    answer = _answer_decision("answer-1", "rejected")
    foreign = _answer_decision("answer-1", "watching")
    rows = [
        {**older.model_dump(mode="json"), "user_id": user_id},
        {**newer.model_dump(mode="json"), "user_id": user_id},
        {**answer.model_dump(mode="json"), "user_id": user_id},
        {**foreign.model_dump(mode="json"), "user_id": fake.uuid4()},
    ]
    client = _Client(rows)
    gateway = SupabaseGateway(client=client)  # type: ignore[arg-type]
    gateway._require_owned_conversation = MagicMock()  # type: ignore[method-assign]

    current = gateway.current_decisions_for_attachments(
        user_id=user_id, artifact_ids=[artifact_id], message_ids=["answer-1"]
    )
    nothing = gateway.current_decisions_for_attachments(
        user_id=user_id, artifact_ids=[], message_ids=[]
    )

    assert current[artifact_id].id == newer.id
    assert current["answer-1"].id == answer.id
    assert nothing == {}
    assert client.queries == [
        [("eq", "user_id", user_id), ("in", "evidence_artifact_id", [artifact_id])],
        [("eq", "user_id", user_id), ("in", "source_message_id", ["answer-1"])],
    ]
