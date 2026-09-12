"""The durable reader hands Search the newest computed answer per conversation."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from argus.domain.supabase_computed_answers import SupabaseComputedAnswerReadMixin
from faker import Faker

fake = Faker()


class _Table:
    def __init__(self, client: _Client, table_name: str) -> None:
        self.client = client
        self.table_name = table_name
        self.filters: list[tuple[str, str, Any]] = []
        self.orders: list[tuple[str, bool]] = []
        self.limit_value: int | None = None
        self.negate = False

    def select(self, *_args: object) -> _Table:
        return self

    @property
    def not_(self) -> _Table:
        self.negate = True
        return self

    def eq(self, key: str, value: object) -> _Table:
        self.filters.append(("eq", key, value))
        return self

    def lte(self, key: str, value: object) -> _Table:
        self.filters.append(("lte", key, value))
        return self

    def in_(self, key: str, values: list[Any]) -> _Table:
        self.filters.append(("in", key, list(values)))
        return self

    def is_(self, key: str, value: object) -> _Table:
        self.filters.append(("not_is" if self.negate else "is", key, value))
        self.negate = False
        return self

    def order(self, key: str, desc: bool = False) -> _Table:
        self.orders.append((key, desc))
        return self

    def limit(self, value: int) -> _Table:
        self.limit_value = value
        return self

    def execute(self) -> SimpleNamespace:
        self.client.queries.append(self)
        rows = [row for row in self.client.rows if self._matches(row)]
        for key, desc in reversed(self.orders):
            rows.sort(key=lambda row: str(row.get(key)), reverse=desc)
        if self.limit_value is not None:
            rows = rows[: self.limit_value]
        return SimpleNamespace(data=[dict(row) for row in rows])

    def _matches(self, row: dict[str, Any]) -> bool:
        for kind, key, value in self.filters:
            if kind == "eq" and row.get(key) != value:
                return False
            if kind == "lte" and not str(row.get(key)) <= str(value):
                return False
            if kind == "in" and row.get(key) not in value:
                return False
            if kind == "not_is":
                current: Any = row
                for part in key.split("->"):
                    current = current.get(part) if isinstance(current, dict) else None
                if current is None:
                    return False
        return True


class _Client:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.queries: list[_Table] = []

    def table(self, table_name: str) -> _Table:
        return _Table(self, table_name)


class _Reader(SupabaseComputedAnswerReadMixin):
    def __init__(self, client: _Client) -> None:
        self.client = client  # type: ignore[assignment]


def _message(
    conversation_id: str, role: str, created_at: str, **metadata: Any
) -> dict[str, Any]:
    return {
        "id": fake.uuid4(),
        "conversation_id": conversation_id,
        "role": role,
        "content": fake.sentence(),
        "metadata": metadata,
        "created_at": created_at,
        "user_id": "owner",
    }


def test_latest_computed_answer_per_conversation_with_its_question() -> None:
    first, second = fake.uuid4(), fake.uuid4()
    rows = [
        _message(first, "user", "2026-09-10T10:00:00+00:00"),
        _message(
            first,
            "assistant",
            "2026-09-10T10:01:00+00:00",
            computation={"kind": "time_value", "inputs": {}},
        ),
        _message(first, "user", "2026-09-10T11:00:00+00:00"),
        _message(
            first,
            "assistant",
            "2026-09-10T11:01:00+00:00",
            computation={"kind": "time_value", "inputs": {"payment": 1}},
        ),
        _message(second, "assistant", "2026-09-10T09:00:00+00:00"),
    ]
    reader = _Reader(_Client(rows))

    latest = reader.latest_computed_answers(
        user_id="owner", conversation_ids=[first, second]
    )

    assert set(latest) == {first}
    assert latest[first]["metadata"]["computation"]["inputs"] == {"payment": 1}
    question = reader.question_before_message(
        user_id="owner", conversation_id=first, created_at=latest[first]["created_at"]
    )
    assert question is not None and question["created_at"] == "2026-09-10T11:00:00+00:00"
    query = reader.client.queries[0]
    assert ("eq", "user_id", "owner") in query.filters
    assert ("not_is", "metadata->computation", "null") in query.filters
    assert reader.latest_computed_answers(user_id="owner", conversation_ids=[]) == {}


def test_symbol_rows_are_owner_scoped_and_optionally_one_conversation() -> None:
    mine, other = fake.uuid4(), fake.uuid4()
    rows = [
        _message(
            mine,
            "assistant",
            "2026-09-10T10:00:00+00:00",
            computation={"kind": "price_multiple", "inputs": {}, "symbols": ["AAPL"]},
        ),
        _message(
            other,
            "assistant",
            "2026-09-10T10:00:00+00:00",
            computation={"kind": "price_multiple", "inputs": {}, "symbols": ["MSFT"]},
        ),
        _message(
            other,
            "assistant",
            "2026-09-10T10:00:00+00:00",
            computation={"kind": "time_value", "inputs": {}},
        ),
    ]
    reader = _Reader(_Client(rows))
    assert len(reader.computed_answer_rows_for_symbols(user_id="owner")) == 2
    scoped = reader.computed_answer_rows_for_symbols(
        user_id="owner", conversation_id=mine
    )
    assert [row["conversation_id"] for row in scoped] == [mine]
