"""The durable reader lists an owner's computed answers of one kind in live conversations."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from argus.domain.supabase_computed_answers import SupabaseComputedAnswerReadMixin


class _Query:
    def __init__(self, client: _Client, table: str) -> None:
        self.client, self.table = client, table
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def __getattr__(self, name: str):
        def record(*args: Any, **kwargs: Any) -> _Query:
            self.calls.append((name, args + tuple(sorted(kwargs.items()))))
            return self

        return record

    def execute(self) -> SimpleNamespace:
        self.client.queries.append(self)
        return SimpleNamespace(data=self.client.data[self.table])


class _Client:
    def __init__(self, data: dict[str, list[dict[str, Any]]]) -> None:
        self.data = data
        self.queries: list[_Query] = []

    def table(self, name: str) -> _Query:
        return _Query(self, name)


class _Reader(SupabaseComputedAnswerReadMixin):
    def __init__(self, client: _Client) -> None:
        self.client = client  # type: ignore[assignment]


def test_the_kind_filter_reads_the_marker_and_drops_deleted_conversations() -> None:
    client = _Client(
        {
            "messages": [
                {"id": "m1", "conversation_id": "live", "role": "assistant"},
                {"id": "m2", "conversation_id": "deleted", "role": "assistant"},
            ],
            "conversations": [{"id": "live"}],
        }
    )
    rows = _Reader(client).computed_answers_of_kind(
        user_id="owner", kind="price_multiple", limit=11
    )
    assert [row["id"] for row in rows] == ["m1"]
    messages, conversations = client.queries
    assert ("eq", ("metadata->computation->>kind", "price_multiple")) in messages.calls
    assert ("eq", ("user_id", "owner")) in messages.calls
    assert ("limit", (11,)) in messages.calls
    assert ("is_", ("deleted_at", "null")) in conversations.calls
    assert ("in_", ("id", ["live", "deleted"])) in conversations.calls


def test_no_matching_message_skips_the_conversation_read() -> None:
    client = _Client({"messages": [], "conversations": []})
    assert _Reader(client).computed_answers_of_kind(user_id="o", kind="k", limit=3) == []
    assert len(client.queries) == 1
