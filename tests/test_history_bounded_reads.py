from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest


class _RecordingCursor:
    def __init__(self, result_sets: list[list[dict[str, Any]]]) -> None:
        self._result_sets = result_sets
        self.executions: list[tuple[str, tuple[Any, ...]]] = []

    def __enter__(self) -> _RecordingCursor:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, query: str, params: tuple[Any, ...]) -> None:
        self.executions.append((query, params))

    def fetchall(self) -> list[dict[str, Any]]:
        return self._result_sets.pop(0)


class _RecordingConnection:
    def __init__(self, cursor: _RecordingCursor) -> None:
        self._cursor = cursor

    def cursor(self, **_kwargs: Any) -> _RecordingCursor:
        return self._cursor


class _RecordingPool:
    def __init__(self, result_sets: list[list[dict[str, Any]]]) -> None:
        self.cursor = _RecordingCursor(result_sets)
        self.acquisition_timeouts: list[float] = []

    @contextmanager
    def connection(self, *, timeout: float):
        self.acquisition_timeouts.append(timeout)
        yield _RecordingConnection(self.cursor)


def _reader_types():
    try:
        from argus.domain.postgres_history_reader import (
            HistoryCursorError,
            PostgresHistoryReader,
        )
    except ModuleNotFoundError:
        pytest.fail("bounded Postgres History reader is not implemented")
    return HistoryCursorError, PostgresHistoryReader


def test_history_first_page_uses_one_bounded_query_and_preserves_raw_groups() -> None:
    _, reader_type = _reader_types()
    pool = _RecordingPool(
        [
            [
                {
                    "source_type": "chat",
                    "payload": {
                        "id": "11111111-1111-1111-1111-111111111111",
                        "title": "AAPL idea",
                        "title_source": "ai_generated",
                        "last_message_preview": "Test AAPL",
                        "pinned": True,
                        "updated_at": "2026-07-01T00:00:00+00:00",
                    },
                },
                {
                    "source_type": "collection",
                    "payload": {
                        "id": "22222222-2222-2222-2222-222222222222",
                        "name": "Watch next",
                        "pinned": False,
                        "strategy_count": 3,
                        "updated_at": "2026-06-30T00:00:00+00:00",
                    },
                },
            ]
        ]
    )

    rows = reader_type(pool).list_rows(
        user_id="00000000-0000-0000-0000-000000000001",
        limit=3,
        archived=False,
        deleted=False,
    )

    assert rows == {
        "runs": [],
        "conversations": [
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "title": "AAPL idea",
                "title_source": "ai_generated",
                "last_message_preview": "Test AAPL",
                "pinned": True,
                "updated_at": "2026-07-01T00:00:00+00:00",
            }
        ],
        "strategies": [],
        "collections": [
            {
                "id": "22222222-2222-2222-2222-222222222222",
                "name": "Watch next",
                "pinned": False,
                "strategy_count": 3,
                "updated_at": "2026-06-30T00:00:00+00:00",
            }
        ],
    }
    assert len(pool.cursor.executions) == 1
    assert pool.acquisition_timeouts == [2.0]


def test_history_cursor_uses_one_pivot_query_and_one_candidate_query() -> None:
    _, reader_type = _reader_types()
    cursor_at = datetime(2026, 7, 1, tzinfo=timezone.utc)
    pool = _RecordingPool(
        [
            [{"source_type": "strategy", "pinned": True, "type_rank": 3}],
            [],
        ]
    )

    rows = reader_type(pool).list_rows(
        user_id="00000000-0000-0000-0000-000000000001",
        limit=4,
        archived=False,
        deleted=False,
        cursor_activity_at=cursor_at,
        cursor_id="11111111-1111-1111-1111-111111111111",
    )

    assert rows == {
        "runs": [],
        "conversations": [],
        "strategies": [],
        "collections": [],
    }
    assert len(pool.cursor.executions) == 2
    candidate_params = pool.cursor.executions[1][1]
    assert cursor_at in candidate_params
    assert True in candidate_params
    assert 3 in candidate_params


@pytest.mark.parametrize(
    "pivot_rows",
    [
        [],
        [
            {"source_type": "strategy", "pinned": False, "type_rank": 3},
            {"source_type": "collection", "pinned": False, "type_rank": 2},
        ],
    ],
)
def test_history_cursor_missing_or_ambiguous_pivot_fails_closed(
    pivot_rows: list[dict[str, Any]],
) -> None:
    cursor_error, reader_type = _reader_types()
    pool = _RecordingPool([pivot_rows])

    with pytest.raises(cursor_error):
        reader_type(pool).list_rows(
            user_id="00000000-0000-0000-0000-000000000001",
            limit=4,
            archived=False,
            deleted=False,
            cursor_activity_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
            cursor_id="11111111-1111-1111-1111-111111111111",
        )

    assert len(pool.cursor.executions) == 1


def test_history_pool_bounds_connections_and_statement_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try:
        from argus.domain import postgres_history_reader
    except ImportError:
        pytest.fail("bounded Postgres History reader is not implemented")
    captured: dict[str, Any] = {}

    class _Pool:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

        def close(self) -> None:
            return None

    postgres_history_reader.history_reader_for_database_url.cache_clear()
    monkeypatch.setattr(postgres_history_reader, "ConnectionPool", _Pool)

    postgres_history_reader.history_reader_for_database_url(
        "postgresql://history-pool/argus"
    )

    assert captured["min_size"] == 0
    assert captured["max_size"] == 5
    assert (
        f"statement_timeout={postgres_history_reader._HISTORY_STATEMENT_TIMEOUT_MS}"
        in captured["kwargs"]["options"]
    )
    postgres_history_reader.history_reader_for_database_url.cache_clear()


def test_supabase_persistence_requires_and_injects_history_database_reader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.domain import supabase_gateway

    monkeypatch.setenv("SUPABASE_URL", "https://argus.local")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        supabase_gateway.SupabaseGateway.from_env()

    reader = MagicMock()
    monkeypatch.setenv("DATABASE_URL", "postgresql://history-pool/argus")
    monkeypatch.setattr(supabase_gateway, "create_client", MagicMock())
    reader_factory = MagicMock(return_value=reader)
    monkeypatch.setattr(
        supabase_gateway,
        "history_reader_for_database_url",
        reader_factory,
    )
    search_reader = MagicMock()
    search_reader_factory = MagicMock(return_value=search_reader)
    monkeypatch.setattr(
        supabase_gateway,
        "PostgresSearchReader",
        search_reader_factory,
    )

    gateway = supabase_gateway.SupabaseGateway.from_env()

    assert gateway.history_reader is reader
    assert gateway.search_reader is search_reader
    reader_factory.assert_called_once_with("postgresql://history-pool/argus")
    search_reader_factory.assert_called_once_with(reader.pool)
