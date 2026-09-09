"""The durable gateway keeps one current decision per owned answer message."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from argus.api.decision_contract import DecisionComputation, DecisionNote
from argus.domain.supabase_gateway import SupabaseGateway
from faker import Faker

fake = Faker()
NOW = datetime(2026, 9, 8, 12, tzinfo=timezone.utc)


class _Table:
    def __init__(self, client: _Client, table_name: str) -> None:
        self.client = client
        self.table_name = table_name
        self.action = "select"
        self.payload: dict[str, Any] = {}
        self.filters: dict[str, Any] = {}

    def select(self, *_args: object, **_kwargs: object) -> _Table:
        self.action = "select"
        return self

    def insert(self, payload: dict[str, Any]) -> _Table:
        self.action = "insert"
        self.payload = dict(payload)
        return self

    def update(self, payload: dict[str, Any]) -> _Table:
        self.action = "update"
        self.payload = dict(payload)
        return self

    def eq(self, key: str, value: object) -> _Table:
        self.filters[key] = value
        return self

    def limit(self, *_args: object) -> _Table:
        return self

    def execute(self) -> SimpleNamespace:
        rows = self.client.rows_by_table.setdefault(self.table_name, [])
        if self.action == "insert":
            self.client.operations.append(("insert", self.table_name, dict(self.payload)))
            if self.client.raise_on_next_insert:
                self.client.raise_on_next_insert = False
                rows.extend(dict(row) for row in self.client.rows_on_insert_error)
                raise RuntimeError("duplicate source_message_id")
            rows.append(dict(self.payload))
            return SimpleNamespace(data=[dict(self.payload)])
        matching = [
            row
            for row in rows
            if all(row.get(key) == value for key, value in self.filters.items())
        ]
        if self.action == "update":
            self.client.operations.append(
                ("update", self.table_name, dict(self.payload), dict(self.filters))
            )
            for row in matching:
                row.update(self.payload)
        return SimpleNamespace(data=[dict(row) for row in matching])


class _Client:
    def __init__(self) -> None:
        self.rows_by_table: dict[str, list[dict[str, Any]]] = {
            "decision_notes": [],
            "messages": [],
        }
        self.operations: list[tuple[Any, ...]] = []
        self.raise_on_next_insert = False
        self.rows_on_insert_error: list[dict[str, Any]] = []

    def table(self, table_name: str) -> _Table:
        return _Table(self, table_name)


def _gateway(client: _Client) -> SupabaseGateway:
    gateway = SupabaseGateway(client=client)  # type: ignore[arg-type]
    gateway._require_owned_conversation = MagicMock()  # type: ignore[method-assign]
    return gateway


def _message_decision(*, user_message_id: str, conversation_id: str) -> DecisionNote:
    return DecisionNote(
        id=fake.uuid4(),
        source_conversation_id=conversation_id,
        source_message_id=user_message_id,
        computation=DecisionComputation(
            kind="savings_projection",
            inputs={"monthly_amount": 5000, "months": 9},
        ),
        decision_state="watching",
        note="Track it.",
        created_at=NOW,
        updated_at=NOW,
    )


def test_first_write_inserts_the_row_with_its_computation_and_no_spine() -> None:
    client = _Client()
    gateway = _gateway(client)
    user_id = fake.uuid4()
    decision = _message_decision(
        user_message_id=fake.uuid4(), conversation_id=fake.uuid4()
    )

    stored = gateway.upsert_message_decision_note(user_id=user_id, decision=decision)

    inserted = next(op for op in client.operations if op[0] == "insert")[2]
    assert inserted["user_id"] == user_id
    assert inserted["source_message_id"] == decision.source_message_id
    assert inserted["computation"] == {
        "kind": "savings_projection",
        "inputs": {"monthly_amount": 5000, "months": 9},
    }
    assert inserted["evidence_artifact_id"] is None
    assert inserted["idea_id"] is None
    assert inserted["idea_version_id"] is None
    assert stored.id == decision.id
    assert stored.computation == decision.computation


def test_repeat_write_updates_the_current_decision_instead_of_adding_one() -> None:
    client = _Client()
    gateway = _gateway(client)
    user_id = fake.uuid4()
    first = _message_decision(user_message_id=fake.uuid4(), conversation_id=fake.uuid4())
    gateway.upsert_message_decision_note(user_id=user_id, decision=first)
    second = first.model_copy(
        update={"id": fake.uuid4(), "decision_state": "promising", "note": "Better."}
    )

    stored = gateway.upsert_message_decision_note(user_id=user_id, decision=second)

    assert stored.id == first.id
    assert stored.decision_state == "promising"
    assert stored.note == "Better."
    assert len(client.rows_by_table["decision_notes"]) == 1
    update = next(op for op in client.operations if op[0] == "update")
    assert update[1] == "decision_notes"
    assert update[3] == {"user_id": user_id, "id": first.id}


def test_a_racing_first_write_converges_on_the_row_that_won() -> None:
    client = _Client()
    gateway = _gateway(client)
    user_id = fake.uuid4()
    decision = _message_decision(
        user_message_id=fake.uuid4(), conversation_id=fake.uuid4()
    )
    winner = decision.model_dump(mode="json")
    winner.update({"id": fake.uuid4(), "user_id": user_id, "decision_state": "rejected"})
    client.raise_on_next_insert = True
    client.rows_on_insert_error = [winner]

    stored = gateway.upsert_message_decision_note(user_id=user_id, decision=decision)

    assert stored.id == winner["id"]
    assert stored.decision_state == decision.decision_state
    assert len(client.rows_by_table["decision_notes"]) == 1


def test_lookups_are_owner_scoped_and_an_insert_failure_without_a_winner_raises() -> None:
    client = _Client()
    gateway = _gateway(client)
    user_id = fake.uuid4()
    decision = _message_decision(
        user_message_id=fake.uuid4(), conversation_id=fake.uuid4()
    )
    gateway.upsert_message_decision_note(user_id=user_id, decision=decision)

    assert gateway.get_decision_note(user_id=user_id, decision_id=decision.id) is not None
    assert (
        gateway.get_decision_note(user_id=fake.uuid4(), decision_id=decision.id) is None
    )
    assert (
        gateway.get_decision_note_by_message(
            user_id=fake.uuid4(), message_id=decision.source_message_id or ""
        )
        is None
    )

    other = _message_decision(user_message_id=fake.uuid4(), conversation_id=fake.uuid4())
    client.raise_on_next_insert = True
    with pytest.raises(RuntimeError):
        gateway.upsert_message_decision_note(user_id=user_id, decision=other)


def test_artifact_decisions_are_refused_by_the_message_writer() -> None:
    gateway = _gateway(_Client())
    artifact_decision = DecisionNote(
        id=fake.uuid4(),
        idea_id=fake.uuid4(),
        idea_version_id=fake.uuid4(),
        evidence_artifact_id=fake.uuid4(),
        decision_state="watching",
        created_at=NOW,
        updated_at=NOW,
    )

    with pytest.raises(ValueError):
        gateway.upsert_message_decision_note(
            user_id=fake.uuid4(), decision=artifact_decision
        )
