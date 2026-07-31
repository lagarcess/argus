from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

import pytest
from argus.domain.postgres_run_dossier_reader import (
    PostgresRunDossierReader,
    RunDossierCursorError,
)

OWNER_ID = "00000000-0000-0000-0000-000000000001"
CONVERSATION_ID = "00000000-0000-0000-0000-000000000101"
RUN_ID = "00000000-0000-0000-0000-000000000401"
COMPLETED_AT = datetime(2026, 7, 31, 12, tzinfo=timezone.utc)


class _Cursor:
    def __init__(self, result_sets: list[list[dict[str, Any]]]) -> None:
        self.result_sets = result_sets
        self.executions: list[tuple[str, dict[str, Any]]] = []

    def __enter__(self) -> _Cursor:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, query: str, params: dict[str, Any]) -> None:
        self.executions.append((query, params))

    def fetchall(self) -> list[dict[str, Any]]:
        return self.result_sets.pop(0)


class _Connection:
    def __init__(self, cursor: _Cursor) -> None:
        self._cursor = cursor

    def cursor(self, **_kwargs: Any) -> _Cursor:
        return self._cursor


class _Pool:
    def __init__(self, result_sets: list[list[dict[str, Any]]]) -> None:
        self.cursor = _Cursor(result_sets)
        self.timeouts: list[float] = []

    @contextmanager
    def connection(self, *, timeout: float):
        self.timeouts.append(timeout)
        yield _Connection(self.cursor)


def _source_row() -> dict[str, Any]:
    return {
        "run_payload": {
            "id": RUN_ID,
            "conversation_id": CONVERSATION_ID,
            "status": "completed",
            "asset_class": "equity",
            "symbols": ["TSLA"],
            "benchmark_symbol": "SPY",
            "config_snapshot": {"template": "buy_and_hold"},
            "conversation_result_card": {"title": "TSLA run"},
            "created_at": COMPLETED_AT,
            "completed_at": COMPLETED_AT,
        },
        "artifact_payload": {
            "id": "00000000-0000-0000-0000-000000000301",
            "source_conversation_id": CONVERSATION_ID,
            "source_run_id": RUN_ID,
            "title": "TSLA evidence",
            "digest": "TSLA result",
            "payload": {},
            "created_at": COMPLETED_AT,
            "updated_at": COMPLETED_AT,
        },
        "decision_payload": None,
        "result_message_id": "00000000-0000-0000-0000-000000000201",
    }


def test_postgres_reader_uses_scalar_counts_and_one_bounded_page_query() -> None:
    pool = _Pool(
        [
            [{"total_runs": 7, "decided_runs": 5}],
            [_source_row()],
        ]
    )

    page = PostgresRunDossierReader(pool).list_source_rows(
        user_id=OWNER_ID,
        conversation_id=CONVERSATION_ID,
        limit=21,
        cursor_completed_at=None,
        cursor_run_id=None,
    )

    assert page.total_runs == 7
    assert page.decided_runs == 5
    assert [row.run["id"] for row in page.rows] == [RUN_ID]
    assert page.rows[0].result_message_id
    assert len(pool.cursor.executions) == 2
    page_sql, page_params = pool.cursor.executions[-1]
    assert "limit %(limit)s" in page_sql
    assert page_params["limit"] == 21
    assert "order by coalesce(br.updated_at, br.created_at) desc, br.id desc" in page_sql
    assert pool.timeouts == [2.0]


def test_postgres_reader_validates_cursor_pivot_before_counts_or_page() -> None:
    pool = _Pool([[]])

    with pytest.raises(RunDossierCursorError):
        PostgresRunDossierReader(pool).list_source_rows(
            user_id=OWNER_ID,
            conversation_id=CONVERSATION_ID,
            limit=21,
            cursor_completed_at=COMPLETED_AT,
            cursor_run_id=RUN_ID,
        )

    assert len(pool.cursor.executions) == 1


def test_postgres_reader_accepts_only_canonical_uuid_cursor_ids() -> None:
    pool = _Pool([])

    with pytest.raises(RunDossierCursorError):
        PostgresRunDossierReader(pool).list_source_rows(
            user_id=OWNER_ID,
            conversation_id=CONVERSATION_ID,
            limit=21,
            cursor_completed_at=COMPLETED_AT,
            cursor_run_id="not-a-uuid",
        )

    assert pool.cursor.executions == []
