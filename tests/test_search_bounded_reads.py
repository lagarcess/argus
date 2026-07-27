from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

import pytest


class _RecordingCursor:
    def __init__(self, result_sets: list[list[dict[str, Any]]]) -> None:
        self._result_sets = result_sets
        self.executions: list[tuple[Any, dict[str, Any]]] = []

    def __enter__(self) -> _RecordingCursor:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, query: Any, params: dict[str, Any]) -> None:
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
        from argus.domain.postgres_search_reader import (
            PostgresSearchReader,
            SearchCursorError,
        )
    except ModuleNotFoundError:
        pytest.fail("bounded Postgres Search reader is not implemented")
    return PostgresSearchReader, SearchCursorError


def _candidate(
    source_type: str,
    item_id: str,
    *,
    evidence_artifact_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": item_id,
        "updated_at": "2026-07-27T12:00:00+00:00",
    }
    if source_type == "chat":
        payload.update(
            title="Search chat",
            last_message_preview="Search preview",
            pinned=False,
        )
    elif source_type == "strategy":
        payload.update(
            name="Search strategy",
            symbols=["AAPL"],
            template="buy_hold",
            pinned=False,
        )
    elif source_type == "collection":
        payload.update(name="Search collection", pinned=False)
    elif source_type == "run":
        payload.update(
            conversation_id="00000000-0000-0000-0000-000000000101",
            created_at=payload.pop("updated_at"),
            status="completed",
            benchmark_symbol="SPY",
            conversation_result_card={"title": "Search run"},
        )
    elif source_type == "idea":
        payload.update(
            title="Search idea",
            summary="Search summary",
            lifecycle="decided",
            source_conversation_id="00000000-0000-0000-0000-000000000101",
            decision_state="promising",
        )
    elif source_type == "evidence":
        payload.update(
            title="Search evidence",
            digest="Search digest",
            lifecycle="captured",
            artifact_type="backtest",
            payload={},
            source_conversation_id="00000000-0000-0000-0000-000000000101",
        )
    elif source_type == "decision":
        payload.update(
            idea_id="00000000-0000-0000-0000-000000000201",
            decision_state="promising",
            note="Search decision",
            evidence_artifact_id=evidence_artifact_id,
            source_conversation_id="00000000-0000-0000-0000-000000000101",
        )
    return {"source_type": source_type, "payload": payload}


def test_search_first_page_uses_bounded_candidate_evidence_and_ledger_queries() -> None:
    reader_type, _ = _reader_types()
    artifact_id = "00000000-0000-0000-0000-000000000301"
    candidate_rows = [
        _candidate(
            source,
            f"00000000-0000-0000-0000-00000000010{index}",
            evidence_artifact_id=artifact_id,
        )
        for index, source in enumerate(
            (
                "chat",
                "strategy",
                "collection",
                "run",
                "idea",
                "evidence",
                "decision",
            ),
            start=1,
        )
    ]
    pool = _RecordingPool(
        [
            candidate_rows,
            [
                {
                    "id": artifact_id,
                    "title": "Search evidence",
                    "digest": "Search digest",
                }
            ],
            [
                {"decision_state": "promising", "count": 2},
                {"decision_state": "watching", "count": 1},
            ],
        ]
    )

    result = reader_type(pool).search_rows(
        user_id="00000000-0000-0000-0000-000000000001",
        query="search",
        source_limit=4,
        include_ledger_groups=True,
    )

    assert {source: len(rows) for source, rows in result.rows.items()} == {
        "conversations": 1,
        "strategies": 1,
        "collections": 1,
        "runs": 1,
        "ideas": 1,
        "evidence": 1,
        "decisions": 1,
    }
    assert result.rows["decisions"][0]["artifact_title"] == "Search evidence"
    assert result.rows["decisions"][0]["artifact_digest"] == "Search digest"
    assert result.ledger_counts == {
        "promising": 2,
        "watching": 1,
        "rejected": 0,
        "revisit_later": 0,
    }
    assert len(pool.cursor.executions) == 3
    assert pool.cursor.executions[0][1]["source_limit"] == 4
    assert pool.cursor.executions[1][1]["artifact_ids"] == [artifact_id]
    assert pool.acquisition_timeouts == [2.0]


@pytest.mark.parametrize(
    "pivot_rows",
    [
        [],
        [
            {"source_type": "idea", "score": 50, "type_rank": 5},
            {"source_type": "decision", "score": 50, "type_rank": 5},
        ],
    ],
)
def test_search_cursor_missing_foreign_or_ambiguous_pivot_fails_closed(
    pivot_rows: list[dict[str, Any]],
) -> None:
    reader_type, cursor_error = _reader_types()
    pool = _RecordingPool([pivot_rows])

    with pytest.raises(cursor_error):
        reader_type(pool).search_rows(
            user_id="00000000-0000-0000-0000-000000000001",
            query="search",
            source_limit=4,
            cursor_updated_at=datetime(2026, 7, 27, tzinfo=timezone.utc),
            cursor_id="00000000-0000-0000-0000-000000000101",
        )

    assert len(pool.cursor.executions) == 1


def test_search_naive_cursor_fails_before_database_read() -> None:
    reader_type, cursor_error = _reader_types()
    pool = _RecordingPool([])

    with pytest.raises(cursor_error):
        reader_type(pool).search_rows(
            user_id="00000000-0000-0000-0000-000000000001",
            query="search",
            source_limit=4,
            cursor_updated_at=datetime(2026, 7, 27),
            cursor_id="00000000-0000-0000-0000-000000000101",
        )

    assert pool.cursor.executions == []


def test_search_decision_evidence_batch_is_bounded_and_owner_scoped() -> None:
    reader_type, _ = _reader_types()
    candidates = [
        _candidate(
            "decision",
            f"00000000-0000-0000-0000-0000000001{index:02d}",
            evidence_artifact_id=(f"00000000-0000-0000-0000-0000000002{index:02d}"),
        )
        for index in range(5)
    ]
    pool = _RecordingPool(
        [
            candidates,
            [
                {
                    "id": f"00000000-0000-0000-0000-0000000002{index:02d}",
                    "title": f"Artifact {index}",
                    "digest": f"Digest {index}",
                }
                for index in range(3)
            ],
        ]
    )

    result = reader_type(pool).search_rows(
        user_id="00000000-0000-0000-0000-000000000001",
        query="search",
        source_limit=3,
    )

    assert len(result.rows["decisions"]) == 3
    evidence_params = pool.cursor.executions[1][1]
    assert str(evidence_params["user_id"]) == ("00000000-0000-0000-0000-000000000001")
    assert len(evidence_params["artifact_ids"]) == 3
