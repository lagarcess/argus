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
            *[[candidate] for candidate in candidate_rows],
            [
                {
                    "idea_id": candidate_rows[4]["payload"]["id"],
                    "decision_state": "promising",
                }
            ],
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
    assert len(pool.cursor.executions) == 10
    assert all(params["source_limit"] == 4 for _, params in pool.cursor.executions[:7])
    assert pool.cursor.executions[8][1]["artifact_ids"] == [artifact_id]
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


def test_search_nul_query_keeps_normalized_text_but_never_binds_raw_nul() -> None:
    reader_type, _ = _reader_types()
    pool = _RecordingPool([[] for _ in range(7)])

    reader_type(pool).search_rows(
        user_id="00000000-0000-0000-0000-000000000001",
        query="nee\x00dle",
        source_limit=4,
    )

    params = pool.cursor.executions[0][1]
    assert params["normalized_query"] == "nee dle"
    assert params["symbol_query"] is None


def test_search_uses_parameterized_token_likes_without_row_token_splitting() -> None:
    reader_type, _ = _reader_types()
    pool = _RecordingPool([[] for _ in range(7)])

    reader_type(pool).search_rows(
        user_id="00000000-0000-0000-0000-000000000001",
        query="Alpha x beta alpha",
        source_limit=4,
    )

    query, params = pool.cursor.executions[0]
    rendered = query.as_string()

    assert "regexp_split_to_table" not in rendered
    assert params["token_0_pattern"] == "%alpha%"
    assert params["token_1_pattern"] == "%x%"
    assert params["token_2_pattern"] == "%beta%"
    assert "token_0_pattern" in rendered
    assert "token_1_pattern" in rendered
    assert "token_2_pattern" in rendered
    assert "alpha" not in rendered
    assert "beta" not in rendered


def test_search_exact_index_predicate_keeps_mixed_short_token_recheck() -> None:
    from argus.domain.postgres_search_reader import (
        _LATE_CHAT,
        _source_token_predicate,
    )

    rendered = _source_token_predicate(
        _LATE_CHAT,
        normalized_tokens=("alpha", "x"),
    ).as_string()

    assert "token_0_pattern" in rendered
    assert "token_1_pattern" in rendered


def test_search_executes_one_bounded_candidate_query_per_source() -> None:
    reader_type, _ = _reader_types()
    pool = _RecordingPool([[] for _ in range(7)])

    reader_type(pool).search_rows(
        user_id="00000000-0000-0000-0000-000000000001",
        query="alpha",
        source_limit=4,
    )

    candidate_queries = pool.cursor.executions[:7]
    assert len(candidate_queries) == 7
    assert all("fetch first" in query.as_string() for query, _ in candidate_queries)
    assert all(params["source_limit"] == 4 for _, params in candidate_queries)


def test_search_cursor_uses_direct_source_primary_key_probes() -> None:
    reader_type, _ = _reader_types()
    pool = _RecordingPool(
        [
            [
                {
                    "source_type": "strategy",
                    "pinned_rank": 0,
                    "exact_rank": 0,
                    "symbol_rank": 0,
                    "type_rank": 3,
                    "text_rank": 0,
                }
            ],
            *([[]] * 7),
        ]
    )

    reader_type(pool).search_rows(
        user_id="00000000-0000-0000-0000-000000000001",
        query="Alpha x",
        source_limit=4,
        cursor_updated_at=datetime(2026, 7, 27, tzinfo=timezone.utc),
        cursor_id="00000000-0000-0000-0000-000000000101",
    )

    pivot_query = pool.cursor.executions[0][0].as_string()
    assert "pivot_only" not in pivot_query
    assert "chat.id = %(cursor_id)s::uuid" in pivot_query
    assert "strategy.id = %(cursor_id)s::uuid" in pivot_query
    assert "collection.id = %(cursor_id)s::uuid" in pivot_query
    assert "run.id = %(cursor_id)s::uuid" in pivot_query
    assert "idea.id = %(cursor_id)s::uuid" in pivot_query
    assert "evidence.id = %(cursor_id)s::uuid" in pivot_query
    assert "decision.id = %(cursor_id)s::uuid" in pivot_query


def test_search_hydrates_returned_idea_decisions_in_one_bounded_batch() -> None:
    reader_type, _ = _reader_types()
    idea_id = "00000000-0000-0000-0000-000000000201"
    idea = _candidate("idea", idea_id)
    idea["payload"]["decision_state"] = None
    pool = _RecordingPool(
        [
            [],
            [],
            [],
            [],
            [idea],
            [],
            [],
            [{"idea_id": idea_id, "decision_state": "watching"}],
        ]
    )

    result = reader_type(pool).search_rows(
        user_id="00000000-0000-0000-0000-000000000001",
        query="search",
        source_limit=4,
    )

    assert result.rows["ideas"][0]["decision_state"] == "watching"
    assert len(pool.cursor.executions) == 8
    assert all(
        "join lateral" not in query.as_string() for query, _ in pool.cursor.executions[:7]
    )
    query, params = pool.cursor.executions[7]
    assert "distinct on (idea_id)" in query
    assert params["idea_ids"] == [idea_id]
    assert str(params["user_id"]) == "00000000-0000-0000-0000-000000000001"


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
            [],
            [],
            [],
            [],
            [],
            [],
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
    evidence_params = pool.cursor.executions[7][1]
    assert str(evidence_params["user_id"]) == ("00000000-0000-0000-0000-000000000001")
    assert len(evidence_params["artifact_ids"]) == 3
