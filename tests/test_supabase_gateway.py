from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from argus.domain.supabase_gateway import SupabaseGateway


def test_batched_fetch_helper_exists_for_unbounded_queries():
    gateway = SupabaseGateway(client=MagicMock())
    assert hasattr(gateway, "_fetch_all_rows")


class _RecordingSupabaseClient:
    def __init__(self) -> None:
        self.inserted_message: dict[str, object] | None = None
        self.inserted_by_table: dict[str, dict[str, object]] = {}

    def table(self, table_name: str):
        return _RecordingTable(self, table_name)


class _RecordingTable:
    def __init__(self, client: _RecordingSupabaseClient, table_name: str) -> None:
        self.client = client
        self.table_name = table_name
        self.payload: dict[str, object] = {}

    def insert(self, payload: dict[str, object]):
        if self.table_name == "messages":
            self.client.inserted_message = payload
        self.client.inserted_by_table[self.table_name] = payload
        self.payload = payload
        return self

    def update(self, payload: dict[str, object]):
        self.payload = payload
        return self

    def eq(self, *_args: object):
        return self

    def execute(self):
        if self.table_name == "messages":
            return SimpleNamespace(data=[{"id": "msg-1", **self.payload}])
        return SimpleNamespace(data=[self.payload])


def test_create_message_writes_empty_metadata_object_when_omitted():
    client = _RecordingSupabaseClient()
    gateway = SupabaseGateway(client=client)
    gateway.get_conversation = MagicMock(return_value=object())

    message = gateway.create_message(
        user_id="user-1",
        conversation_id="conversation-1",
        role="user",
        content="Backtest buying and holding Apple over the past year.",
    )

    assert client.inserted_message is not None
    assert client.inserted_message["metadata"] == {}
    assert message.metadata == {}


def test_context_packet_and_route_receipt_persistence_payloads_are_explicit():
    client = _RecordingSupabaseClient()
    gateway = SupabaseGateway(client=client)

    packet_row = gateway.create_context_packet(
        user_id="user-1",
        packet={
            "id": "packet-1",
            "provider": "fred",
            "packet_type": "macro",
            "scope": {"series_id": "FEDFUNDS"},
            "source_ids": ["FEDFUNDS:2024-01-01"],
            "retrieved_at": "2026-05-19T00:00:00+00:00",
            "coverage_start": "2024-01-01",
            "coverage_end": "2024-01-31",
            "freshness": "fresh",
            "facts": [],
            "limitations": ["Context only."],
            "not_for": "simulation_truth",
        },
    )
    attachment_row = gateway.attach_context_packet_to_run(
        user_id="user-1",
        attachment={
            "packet_id": "packet-1",
            "run_id": "run-1",
            "immutable_snapshot": True,
        },
    )
    receipt_row = gateway.create_route_receipt(
        user_id="user-1",
        conversation_id="conversation-1",
        receipt={
            "task": "interpretation",
            "tier": "structured",
            "model": "structured/primary",
            "fallback_model": "structured/fallback",
            "mode": "json_schema",
            "schema_name": "LLMInterpretationResponse",
            "latency_ms": 123,
            "outcome": "succeeded",
            "fallback_used": False,
            "token_usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "context_packet_ids": ["packet-1"],
            "created_at": "2026-05-19T00:00:00+00:00",
        },
    )

    assert packet_row["packet"]["not_for"] == "simulation_truth"
    assert client.inserted_by_table["context_packets"]["user_id"] == "user-1"
    assert attachment_row["context_packet_id"] == "packet-1"
    assert attachment_row["immutable_snapshot"] is True
    assert receipt_row["conversation_id"] == "conversation-1"
    assert receipt_row["latency_ms"] == 123
    assert receipt_row["token_usage"] == {"prompt_tokens": 10, "completion_tokens": 5}
    assert receipt_row["context_packet_ids"] == ["packet-1"]


class _MockAuthAdmin:
    def get_user_by_email(self, _email: str) -> object:
        raise RuntimeError("fall back to profile lookup")

    def list_users(self, **_kwargs: object) -> object:
        raise RuntimeError("fall back to profile lookup")


class _MockAuth:
    admin = _MockAuthAdmin()


class _ExistingProfileClient:
    def __init__(self) -> None:
        self.auth = _MockAuth()
        self.upserted_profile: dict[str, object] | None = None
        self.profile = {
            "id": "user-1",
            "email": "developer@argus.local",
            "username": "mock-developer",
            "display_name": "Mock Developer",
            "language": "en",
            "locale": "en-US",
            "theme": "dark",
            "is_admin": True,
            "onboarding": {
                "completed": True,
                "stage": "completed",
                "language_confirmed": True,
                "primary_goal": "test_stock_idea",
            },
            "created_at": "2026-05-14T00:00:00+00:00",
            "updated_at": "2026-05-14T00:00:00+00:00",
        }

    def table(self, table_name: str):
        assert table_name == "profiles"
        return _ExistingProfileTable(self)


class _ExistingProfileTable:
    def __init__(self, client: _ExistingProfileClient) -> None:
        self.client = client
        self.selected = "*"

    def select(self, selected: str):
        self.selected = selected
        return self

    def eq(self, *_args: object):
        return self

    def limit(self, *_args: object):
        return self

    def single(self):
        return self

    def upsert(self, payload: dict[str, object], **_kwargs: object):
        self.client.upserted_profile = payload
        self.client.profile = {**self.client.profile, **payload}
        return self

    def execute(self):
        if self.selected == "id":
            return SimpleNamespace(data=[{"id": self.client.profile["id"]}])
        return SimpleNamespace(data=[self.client.profile])


def test_mock_user_lookup_preserves_existing_profile_onboarding():
    client = _ExistingProfileClient()
    gateway = SupabaseGateway(
        client=client,
        mock_user_email="developer@argus.local",
        mock_user_password="password",
    )

    user = gateway.get_or_create_mock_user()

    assert client.upserted_profile is None
    assert user.onboarding.completed is True
    assert user.onboarding.primary_goal == "test_stock_idea"


class _HistoryClient:
    def __init__(self) -> None:
        self.rows_by_table: dict[str, list[dict[str, Any]]] = {
            "conversations": [
                {
                    "id": "conv-other",
                    "user_id": "user-1",
                    "title": "Other active idea",
                    "last_message_preview": None,
                    "pinned": False,
                    "archived": False,
                    "deleted_at": None,
                    "updated_at": "2026-05-31T00:00:00+00:00",
                },
                {
                    "id": "conv-active",
                    "user_id": "user-1",
                    "title": "Active idea",
                    "last_message_preview": None,
                    "pinned": False,
                    "archived": False,
                    "deleted_at": None,
                    "updated_at": "2026-05-31T00:00:00+00:00",
                },
                {
                    "id": "conv-archived",
                    "user_id": "user-1",
                    "title": "Archived idea",
                    "last_message_preview": None,
                    "pinned": False,
                    "archived": True,
                    "deleted_at": None,
                    "updated_at": "2026-05-31T00:00:00+00:00",
                },
                {
                    "id": "conv-deleted",
                    "user_id": "user-1",
                    "title": "Deleted idea",
                    "last_message_preview": None,
                    "pinned": False,
                    "archived": False,
                    "deleted_at": "2026-05-31T01:00:00+00:00",
                    "updated_at": "2026-05-31T00:00:00+00:00",
                },
            ],
            "messages": [
                {
                    "id": "msg-active",
                    "user_id": "user-1",
                    "conversation_id": "conv-active",
                },
                {
                    "id": "msg-archived",
                    "user_id": "user-1",
                    "conversation_id": "conv-archived",
                },
                {
                    "id": "msg-deleted",
                    "user_id": "user-1",
                    "conversation_id": "conv-deleted",
                },
                {
                    "id": "msg-other-user",
                    "user_id": "user-2",
                    "conversation_id": "conv-other",
                },
            ],
            "backtest_runs": [
                {
                    "id": "run-active",
                    "user_id": "user-1",
                    "conversation_id": "conv-active",
                    "conversation_result_card": {"title": "AAPL run", "rows": []},
                    "created_at": "2026-05-31T00:00:00+00:00",
                },
                {
                    "id": "run-archived",
                    "user_id": "user-1",
                    "conversation_id": "conv-archived",
                    "conversation_result_card": {"title": "TSLA run", "rows": []},
                    "created_at": "2026-05-31T00:00:00+00:00",
                },
                {
                    "id": "run-deleted",
                    "user_id": "user-1",
                    "conversation_id": "conv-deleted",
                    "conversation_result_card": {"title": "MSFT run", "rows": []},
                    "created_at": "2026-05-31T00:00:00+00:00",
                },
                {
                    "id": "run-orphan",
                    "user_id": "user-1",
                    "conversation_id": None,
                    "conversation_result_card": {"title": "Direct run", "rows": []},
                    "created_at": "2026-05-31T00:00:00+00:00",
                },
            ],
            "strategies": [],
            "collections": [],
        }

    def table(self, table_name: str):
        return _HistoryTable(self.rows_by_table[table_name])


class _HistoryTable:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = list(rows)

    def select(self, *_args: object, **_kwargs: object):
        return self

    def eq(self, key: str, value: object):
        self.rows = [row for row in self.rows if row.get(key) == value]
        return self

    def in_(self, key: str, values: list[object]):
        expected = {str(value) for value in values}
        self.rows = [
            row for row in self.rows if row.get(key) is not None and str(row[key]) in expected
        ]
        return self

    def is_(self, key: str, value: object):
        if value == "null":
            self.rows = [row for row in self.rows if row.get(key) is None]
        return self

    @property
    def not_(self):
        return _HistoryNotFilter(self)

    def order(self, *_args: object, **_kwargs: object):
        return self

    def limit(self, count: int):
        self.rows = self.rows[:count]
        return self

    def range(self, start: int, end: int):
        self.rows = self.rows[start : end + 1]
        return self

    def execute(self):
        return SimpleNamespace(data=list(self.rows))


class _HistoryNotFilter:
    def __init__(self, query: _HistoryTable) -> None:
        self.query = query

    def is_(self, key: str, value: object):
        if value == "null":
            self.query.rows = [
                row for row in self.query.rows if row.get(key) is not None
            ]
        return self.query


def test_gateway_history_filters_runs_by_parent_conversation_state() -> None:
    gateway = SupabaseGateway(client=_HistoryClient())

    default_rows = gateway.list_history_rows(user_id="user-1", limit=100)
    archived_rows = gateway.list_history_rows(
        user_id="user-1",
        limit=100,
        archived=True,
    )
    deleted_rows = gateway.list_history_rows(
        user_id="user-1",
        limit=100,
        deleted=True,
    )

    assert {row["id"] for row in default_rows["runs"]} == {
        "run-active",
        "run-orphan",
    }
    assert {
        row["id"]
        for row in gateway.list_history_rows(user_id="user-1", limit=1)["runs"]
    } == {"run-active"}
    assert {row["id"] for row in archived_rows["runs"]} == {"run-archived"}
    assert {row["id"] for row in deleted_rows["runs"]} == {"run-deleted"}


def test_gateway_history_filters_chats_without_visible_messages() -> None:
    gateway = SupabaseGateway(client=_HistoryClient())

    default_rows = gateway.list_history_rows(user_id="user-1", limit=100)
    archived_rows = gateway.list_history_rows(
        user_id="user-1",
        limit=100,
        archived=True,
    )
    deleted_rows = gateway.list_history_rows(
        user_id="user-1",
        limit=100,
        deleted=True,
    )

    assert {row["id"] for row in default_rows["conversations"]} == {"conv-active"}
    assert {row["id"] for row in archived_rows["conversations"]} == {"conv-archived"}
    assert {row["id"] for row in deleted_rows["conversations"]} == {"conv-deleted"}
