"""Real-Postgres proofs for bounded, parity-preserving Omnisearch reads."""

from __future__ import annotations

import os
import random
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from argus.api.search_assembly import scored_supabase_search_items
from argus.api.search_utils import search_rank_key
from argus.domain.search_text import normalize_search_text
from psycopg import sql
from psycopg.types.json import Jsonb

DSN = os.getenv("ARGUS_DISPOSABLE_DATABASE_URL", "").strip()
pytestmark = pytest.mark.skipif(
    not DSN,
    reason="ARGUS_DISPOSABLE_DATABASE_URL is not configured",
)


def _search_components():
    try:
        from argus.domain.postgres_search_reader import (
            PostgresSearchReader,
            SearchCursorError,
        )
        from argus.domain.search_sql_text import normalizer_expression
    except ModuleNotFoundError:
        pytest.fail("bounded Postgres Search reader is not implemented")
    return PostgresSearchReader, SearchCursorError, normalizer_expression


class _TrackingCursor:
    def __init__(self, cursor: Any, tracker: dict[str, Any]) -> None:
        self._cursor = cursor
        self._tracker = tracker

    def __enter__(self) -> _TrackingCursor:
        self._cursor.__enter__()
        return self

    def __exit__(self, *args: object) -> None:
        self._cursor.__exit__(*args)

    def execute(self, query: Any, params: Any = None) -> None:
        self._tracker["query_count"] += 1
        self._cursor.execute(query, params)

    def fetchall(self) -> list[dict[str, Any]]:
        rows = self._cursor.fetchall()
        self._tracker["row_counts"].append(len(rows))
        return rows


class _TrackingConnection:
    def __init__(self, connection: Any, tracker: dict[str, Any]) -> None:
        self._connection = connection
        self._tracker = tracker

    def cursor(self, **kwargs: Any) -> _TrackingCursor:
        return _TrackingCursor(self._connection.cursor(**kwargs), self._tracker)


class _TrackingPool:
    def __init__(self) -> None:
        self.tracker: dict[str, Any] = {"query_count": 0, "row_counts": []}

    @contextmanager
    def connection(self, *, timeout: float):
        assert timeout == 2.0
        with psycopg.connect(DSN, autocommit=True) as connection:
            yield _TrackingConnection(connection, self.tracker)


@pytest.fixture
def search_identities():
    owner_id = uuid4()
    other_id = uuid4()
    with psycopg.connect(DSN, autocommit=True) as connection:
        with connection.cursor() as cursor:
            for user_id, label in ((owner_id, "owner"), (other_id, "other")):
                email = f"search-{label}-{user_id}@argus.local"
                cursor.execute(
                    "insert into auth.users (id, email, is_anonymous)"
                    " values (%s, %s, false)",
                    (user_id, email),
                )
                cursor.execute(
                    "insert into public.profiles (id, email) values (%s, %s)",
                    (user_id, email),
                )
    try:
        yield {"owner": owner_id, "other": other_id}
    finally:
        with psycopg.connect(DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "delete from auth.users where id = any(%s::uuid[])",
                    ([owner_id, other_id],),
                )


def _connect():
    return psycopg.connect(DSN, autocommit=True)


def _reader():
    reader_type, _, _ = _search_components()
    pool = _TrackingPool()
    return reader_type(pool), pool


def _insert_conversation(
    cursor: Any,
    *,
    user_id: UUID,
    timestamp: datetime,
    title: str,
    preview: str = "",
    pinned: bool = False,
    conversation_id: UUID | None = None,
) -> UUID:
    conversation_id = conversation_id or uuid4()
    cursor.execute(
        """
        insert into public.conversations (
            id, user_id, title, title_source, language, pinned, archived,
            last_message_preview, created_at, updated_at
        )
        values (%s, %s, %s, 'ai_generated', 'en', %s, false, %s, %s, %s)
        """,
        (
            conversation_id,
            user_id,
            title,
            pinned,
            preview,
            timestamp,
            timestamp,
        ),
    )
    return conversation_id


def _insert_strategy(
    cursor: Any,
    *,
    user_id: UUID,
    timestamp: datetime,
    name: str,
    symbols: list[str] | None = None,
    pinned: bool = False,
    strategy_id: UUID | None = None,
    conversation_id: UUID | None = None,
) -> UUID:
    strategy_id = strategy_id or uuid4()
    cursor.execute(
        """
        insert into public.strategies (
            id, user_id, conversation_id, name, name_source, template,
            asset_class, symbols, parameters, metrics_preferences,
            benchmark_symbol, pinned, created_at, updated_at
        )
        values (
            %s, %s, %s, %s, 'ai_generated', 'buy_hold', 'equity', %s,
            '{}'::jsonb, array['total_return_pct'], 'SPY', %s, %s, %s
        )
        """,
        (
            strategy_id,
            user_id,
            conversation_id,
            name,
            symbols or ["AAPL"],
            pinned,
            timestamp,
            timestamp,
        ),
    )
    return strategy_id


def _insert_collection(
    cursor: Any,
    *,
    user_id: UUID,
    timestamp: datetime,
    name: str,
    pinned: bool = False,
    collection_id: UUID | None = None,
) -> UUID:
    collection_id = collection_id or uuid4()
    cursor.execute(
        """
        insert into public.collections (
            id, user_id, name, name_source, pinned, created_at, updated_at
        )
        values (%s, %s, %s, 'ai_generated', %s, %s, %s)
        """,
        (collection_id, user_id, name, pinned, timestamp, timestamp),
    )
    return collection_id


def _insert_run(
    cursor: Any,
    *,
    user_id: UUID,
    timestamp: datetime,
    title: str,
    conversation_id: UUID | None = None,
    symbols: list[str] | None = None,
    status: str = "completed",
    run_id: UUID | None = None,
    strategy_label: str | None = None,
) -> UUID:
    run_id = run_id or uuid4()
    run_symbols = symbols or ["AAPL"]
    result_card = {"title": title, "symbols": run_symbols}
    if strategy_label is not None:
        result_card["strategy_label"] = strategy_label
    cursor.execute(
        """
        insert into public.backtest_runs (
            id, user_id, conversation_id, status, asset_class, symbols,
            allocation_method, benchmark_symbol, config_snapshot, metrics,
            conversation_result_card, created_at, updated_at
        )
        values (
            %s, %s, %s, %s, 'equity', %s, 'equal_weight', 'SPY',
            '{}'::jsonb, '{}'::jsonb, %s, %s, %s
        )
        """,
        (
            run_id,
            user_id,
            conversation_id,
            status,
            run_symbols,
            Jsonb(result_card),
            timestamp,
            timestamp,
        ),
    )
    return run_id


def _insert_idea_spine(
    cursor: Any,
    *,
    user_id: UUID,
    timestamp: datetime,
    title: str,
    summary: str,
    conversation_id: UUID | None = None,
    decision_state: str = "promising",
    idea_id: UUID | None = None,
    version_id: UUID | None = None,
    evidence_id: UUID | None = None,
    decision_id: UUID | None = None,
    evidence_symbols: list[str] | None = None,
    evidence_digest: str | None = None,
    evidence_title: str | None = None,
) -> dict[str, UUID]:
    idea_id = idea_id or uuid4()
    version_id = version_id or uuid4()
    evidence_id = evidence_id or uuid4()
    decision_id = decision_id or uuid4()
    cursor.execute(
        """
        insert into public.ideas (
            id, user_id, source_conversation_id, title, summary, lifecycle,
            created_at, updated_at
        )
        values (%s, %s, %s, %s, %s, 'decided', %s, %s)
        """,
        (idea_id, user_id, conversation_id, title, summary, timestamp, timestamp),
    )
    cursor.execute(
        """
        insert into public.idea_versions (
            id, user_id, idea_id, source_conversation_id, version_number,
            canonical_spec, strategy_snapshot, title, summary, lifecycle,
            created_at
        )
        values (
            %s, %s, %s, %s, 1, '{}'::jsonb, '{}'::jsonb, %s, %s,
            'decided', %s
        )
        """,
        (
            version_id,
            user_id,
            idea_id,
            conversation_id,
            title,
            summary,
            timestamp,
        ),
    )
    cursor.execute(
        "update public.ideas set active_version_id = %s where id = %s",
        (version_id, idea_id),
    )
    cursor.execute(
        """
        insert into public.evidence_artifacts (
            id, user_id, idea_id, idea_version_id, source_conversation_id,
            artifact_type, lifecycle, title, digest, payload, created_at,
            updated_at
        )
        values (
            %s, %s, %s, %s, %s, 'backtest', 'decided', %s, %s, %s, %s, %s
        )
        """,
        (
            evidence_id,
            user_id,
            idea_id,
            version_id,
            conversation_id,
            evidence_title if evidence_title is not None else f"{title} evidence",
            evidence_digest if evidence_digest is not None else f"{summary} evidence",
            Jsonb(
                {
                    "result_card": {"symbols": evidence_symbols or ["AAPL"]},
                    "provenance": {
                        "symbols": evidence_symbols or ["AAPL"],
                        "benchmark_symbol": "SPY",
                    },
                }
            ),
            timestamp,
            timestamp,
        ),
    )
    cursor.execute(
        """
        insert into public.decision_notes (
            id, user_id, idea_id, idea_version_id, evidence_artifact_id,
            source_conversation_id, decision_state, note, created_at, updated_at
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            decision_id,
            user_id,
            idea_id,
            version_id,
            evidence_id,
            conversation_id,
            decision_state,
            f"{summary} decision",
            timestamp,
            timestamp,
        ),
    )
    return {
        "idea": idea_id,
        "version": version_id,
        "evidence": evidence_id,
        "decision": decision_id,
    }


def _ranked(raw: dict[str, list[dict[str, Any]]], query: str):
    scored = scored_supabase_search_items(raw=raw, query=query)
    return sorted(
        scored,
        key=lambda pair: search_rank_key(
            score=pair[0],
            kind=pair[1].type,
            updated_at=pair[1].updated_at,
            item_id=pair[1].id,
        ),
        reverse=True,
    )


def _random_text(randomizer: random.Random, length: int) -> str:
    characters: list[str] = []
    while len(characters) < length:
        codepoint = randomizer.randrange(1, sys.maxunicode + 1)
        if 0xD800 <= codepoint <= 0xDFFF:
            continue
        characters.append(chr(codepoint))
    return "".join(characters)


def test_sql_normalizer_matches_python_for_unicode_and_random_text() -> None:
    _, _, normalizer_expression = _search_components()
    randomizer = random.Random(232)
    values = [
        chr(codepoint)
        for codepoint in range(1, sys.maxunicode + 1)
        if not 0xD800 <= codepoint <= 0xDFFF
    ]
    values.extend(
        _random_text(randomizer, randomizer.randrange(1, 16)) for _ in range(2_000)
    )
    with _connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            "create temporary table search_normalizer_probe "
            "(source_text text not null, expected text not null)"
        )
        with cursor.copy(
            "copy search_normalizer_probe (source_text, expected) from stdin"
        ) as copy:
            for value in values:
                copy.write_row((value, normalize_search_text(value)))
        cursor.execute(
            sql.SQL(
                "select count(*) from search_normalizer_probe where {} <> expected"
            ).format(normalizer_expression(sql.Identifier("source_text")))
        )
        assert cursor.fetchone()[0] == 0


def test_search_each_source_returns_at_most_limit_plus_one_candidates(
    search_identities,
) -> None:
    owner_id = search_identities["owner"]
    timestamp = datetime(2026, 7, 27, 12, tzinfo=timezone.utc)
    with _connect() as connection, connection.cursor() as cursor:
        for offset in range(6):
            item_at = timestamp - timedelta(seconds=offset)
            conversation_id = _insert_conversation(
                cursor,
                user_id=owner_id,
                timestamp=item_at,
                title=f"Needle chat {offset}",
                preview="Needle",
            )
            _insert_strategy(
                cursor,
                user_id=owner_id,
                timestamp=item_at,
                name=f"Needle strategy {offset}",
            )
            _insert_collection(
                cursor,
                user_id=owner_id,
                timestamp=item_at,
                name=f"Needle collection {offset}",
            )
            _insert_run(
                cursor,
                user_id=owner_id,
                timestamp=item_at,
                title=f"Needle run {offset}",
                conversation_id=conversation_id,
            )
            _insert_idea_spine(
                cursor,
                user_id=owner_id,
                timestamp=item_at,
                title=f"Needle idea {offset}",
                summary=f"Needle summary {offset}",
                conversation_id=conversation_id,
            )

    reader, pool = _reader()
    public_limit = 3
    result = reader.search_rows(
        user_id=str(owner_id),
        query="needle",
        source_limit=public_limit + 1,
    )

    assert {source: len(rows) for source, rows in result.rows.items()} == {
        "conversations": 4,
        "strategies": 4,
        "collections": 4,
        "runs": 4,
        "ideas": 4,
        "evidence": 4,
        "decisions": 4,
    }
    assert all(len(rows) <= public_limit + 1 for rows in result.rows.values())
    assert pool.tracker["query_count"] == 2
    assert pool.tracker["row_counts"] == [28, 4]


def test_search_preserves_all_token_matching_and_rank_buckets(
    search_identities,
) -> None:
    owner_id = search_identities["owner"]
    now = datetime(2026, 7, 27, 13, tzinfo=timezone.utc)
    with _connect() as connection, connection.cursor() as cursor:
        _insert_conversation(
            cursor,
            user_id=owner_id,
            timestamp=now,
            title="Alpha",
            preview="Beta",
        )
        _insert_collection(
            cursor,
            user_id=owner_id,
            timestamp=now - timedelta(minutes=1),
            name="Alpha Beta",
        )

    reader, _ = _reader()
    result = reader.search_rows(
        user_id=str(owner_id),
        query="alpha beta",
        source_limit=3,
    )
    ranked = _ranked(result.rows, "alpha beta")

    assert [item.type for _, item in ranked] == ["collection", "chat"]


def test_search_score_projection_uses_title_when_optional_preview_text_is_empty(
    search_identities,
) -> None:
    owner_id = search_identities["owner"]
    now = datetime(2026, 7, 27, 13, 30, tzinfo=timezone.utc)
    with _connect() as connection, connection.cursor() as cursor:
        expected = _insert_conversation(
            cursor,
            user_id=owner_id,
            timestamp=now,
            title="Higher id needle thesis",
            preview="",
            conversation_id=UUID("00000000-0000-0000-0000-000000000099"),
        )
        _insert_conversation(
            cursor,
            user_id=owner_id,
            timestamp=now,
            title="Lower id needle thesis",
            preview="needle",
            conversation_id=UUID("00000000-0000-0000-0000-000000000001"),
        )
        _insert_idea_spine(
            cursor,
            user_id=owner_id,
            timestamp=now,
            title="Higher id needle idea",
            summary="",
            idea_id=UUID("00000000-0000-0000-0000-000000000099"),
            evidence_id=UUID("00000000-0000-0000-0000-000000000099"),
            evidence_digest="",
        )
        _insert_idea_spine(
            cursor,
            user_id=owner_id,
            timestamp=now,
            title="Lower id needle idea",
            summary="needle",
            idea_id=UUID("00000000-0000-0000-0000-000000000001"),
            evidence_id=UUID("00000000-0000-0000-0000-000000000001"),
            evidence_digest="needle",
        )
        cursor.execute(
            "update public.ideas set updated_at = %s where id = any(%s::uuid[])",
            (
                now,
                [
                    UUID("00000000-0000-0000-0000-000000000099"),
                    UUID("00000000-0000-0000-0000-000000000001"),
                ],
            ),
        )
        expected_run = _insert_run(
            cursor,
            user_id=owner_id,
            timestamp=now,
            title="",
            strategy_label="Backtest run",
            run_id=UUID("00000000-0000-0000-0000-000000000010"),
        )
        _insert_run(
            cursor,
            user_id=owner_id,
            timestamp=now,
            title="Plain title",
            strategy_label="Backtest run",
            run_id=UUID("00000000-0000-0000-0000-000000000090"),
        )
        expected_decision = _insert_idea_spine(
            cursor,
            user_id=owner_id,
            timestamp=now,
            title="Decision source one",
            summary="",
            evidence_title="",
            evidence_digest="Target",
            decision_id=UUID("00000000-0000-0000-0000-000000000010"),
        )["decision"]
        _insert_idea_spine(
            cursor,
            user_id=owner_id,
            timestamp=now,
            title="Decision source two",
            summary="",
            evidence_title="Plain evidence",
            evidence_digest="Target",
            decision_id=UUID("00000000-0000-0000-0000-000000000090"),
        )

    reader, _ = _reader()
    result = reader.search_rows(
        user_id=str(owner_id),
        query="needle",
        source_limit=1,
    )

    assert [str(row["id"]) for row in result.rows["conversations"]] == [str(expected)]
    assert [str(row["id"]) for row in result.rows["ideas"]] == [str(expected)]
    assert [str(row["id"]) for row in result.rows["evidence"]] == [str(expected)]

    run_result = reader.search_rows(
        user_id=str(owner_id),
        query="backtest run",
        source_limit=1,
    )
    assert [str(row["id"]) for row in run_result.rows["runs"]] == [str(expected_run)]

    decision_result = reader.search_rows(
        user_id=str(owner_id),
        query="target",
        source_limit=1,
    )
    assert [str(row["id"]) for row in decision_result.rows["decisions"]] == [
        str(expected_decision)
    ]


def test_old_pinned_exact_title_and_exact_symbol_beat_newer_plain_matches(
    search_identities,
) -> None:
    owner_id = search_identities["owner"]
    now = datetime(2026, 7, 27, 14, tzinfo=timezone.utc)
    old = now - timedelta(days=30)
    with _connect() as connection, connection.cursor() as cursor:
        _insert_conversation(
            cursor,
            user_id=owner_id,
            timestamp=old,
            title="Pinned AAPL notes",
            preview="AAPL",
            pinned=True,
        )
        _insert_collection(
            cursor,
            user_id=owner_id,
            timestamp=old,
            name="AAPL",
        )
        _insert_strategy(
            cursor,
            user_id=owner_id,
            timestamp=old,
            name="Old symbol strategy",
            symbols=["AAPL"],
        )
        _insert_idea_spine(
            cursor,
            user_id=owner_id,
            timestamp=now,
            title="Newer AAPL evidence idea",
            summary="AAPL plain match",
            evidence_symbols=["MSFT"],
        )

    reader, _ = _reader()
    ranked = _ranked(
        reader.search_rows(
            user_id=str(owner_id),
            query="aapl",
            source_limit=10,
        ).rows,
        "aapl",
    )
    ordered_types = [item.type for _, item in ranked]

    assert ordered_types.index("chat") < ordered_types.index("evidence")
    assert ordered_types.index("collection") < ordered_types.index("evidence")
    assert ordered_types.index("strategy") < ordered_types.index("evidence")


def test_search_first_middle_final_equal_timestamp_and_empty_pages(
    search_identities,
) -> None:
    owner_id = search_identities["owner"]
    timestamp = datetime(2026, 7, 27, 15, tzinfo=timezone.utc)
    inserted: set[str] = set()
    with _connect() as connection, connection.cursor() as cursor:
        for offset in range(7):
            inserted.add(
                str(
                    _insert_strategy(
                        cursor,
                        user_id=owner_id,
                        timestamp=timestamp,
                        name=f"Needle strategy {offset}",
                    )
                )
            )

    reader, _ = _reader()
    seen: list[str] = []
    cursor_at = None
    cursor_id = None
    for expected_count in (3, 3, 1, 0):
        result = reader.search_rows(
            user_id=str(owner_id),
            query="needle",
            source_limit=4,
            cursor_updated_at=cursor_at,
            cursor_id=cursor_id,
        )
        page = _ranked(result.rows, "needle")[:3]
        assert len(page) == expected_count
        seen.extend(item.id for _, item in page)
        if page:
            cursor_at = page[-1][1].updated_at
            cursor_id = page[-1][1].id

    assert len(seen) == len(set(seen))
    assert set(seen) == inserted


def test_search_cursor_pivot_preserves_existing_query_specific_behavior(
    search_identities,
) -> None:
    reader, _ = _reader()
    _, cursor_error, _ = _search_components()
    owner_id = search_identities["owner"]
    other_id = search_identities["other"]
    timestamp = datetime(2026, 7, 27, 16, tzinfo=timezone.utc)
    pivot_id = UUID("f0000000-0000-0000-0000-000000000001")
    foreign_id = UUID("e0000000-0000-0000-0000-000000000001")
    with _connect() as connection, connection.cursor() as cursor:
        _insert_strategy(
            cursor,
            user_id=owner_id,
            timestamp=timestamp,
            name="Alpha pivot",
            strategy_id=pivot_id,
        )
        _insert_strategy(
            cursor,
            user_id=other_id,
            timestamp=timestamp,
            name="Alpha foreign",
            strategy_id=foreign_id,
        )

    for query, item_id in (("beta", pivot_id), ("alpha", foreign_id)):
        with pytest.raises(cursor_error):
            reader.search_rows(
                user_id=str(owner_id),
                query=query,
                source_limit=3,
                cursor_updated_at=timestamp,
                cursor_id=str(item_id),
            )


def test_search_guest_scope_is_applied_before_candidate_limit(
    search_identities,
) -> None:
    owner_id = search_identities["owner"]
    timestamp = datetime(2026, 7, 27, 17, tzinfo=timezone.utc)
    workspace_id = uuid4()
    with _connect() as connection, connection.cursor() as cursor:
        _insert_conversation(
            cursor,
            user_id=owner_id,
            timestamp=timestamp - timedelta(days=1),
            title="Needle workspace",
            conversation_id=workspace_id,
        )
        for offset in range(5):
            other_conversation = _insert_conversation(
                cursor,
                user_id=owner_id,
                timestamp=timestamp + timedelta(minutes=offset),
                title=f"Needle outside {offset}",
            )
            _insert_run(
                cursor,
                user_id=owner_id,
                timestamp=timestamp + timedelta(minutes=offset),
                title=f"Needle outside run {offset}",
                conversation_id=other_conversation,
            )
        expected_run = _insert_run(
            cursor,
            user_id=owner_id,
            timestamp=timestamp - timedelta(days=1),
            title="Needle workspace run",
            conversation_id=workspace_id,
        )

    reader, _ = _reader()
    result = reader.search_rows(
        user_id=str(owner_id),
        query="needle",
        source_limit=1,
        guest_scope=True,
        guest_conversation_id=str(workspace_id),
    )

    assert [str(row["id"]) for row in result.rows["conversations"]] == [str(workspace_id)]
    assert [str(row["id"]) for row in result.rows["runs"]] == [str(expected_run)]
    assert result.rows["strategies"] == []
    assert result.rows["collections"] == []


def test_completed_runs_and_all_artifact_identities_are_preserved(
    search_identities,
) -> None:
    owner_id = search_identities["owner"]
    timestamp = datetime(2026, 7, 27, 18, tzinfo=timezone.utc)
    with _connect() as connection, connection.cursor() as cursor:
        completed_id = _insert_run(
            cursor,
            user_id=owner_id,
            timestamp=timestamp,
            title="Needle completed",
        )
        failed_id = _insert_run(
            cursor,
            user_id=owner_id,
            timestamp=timestamp,
            title="Needle failed",
            status="failed",
        )
        identities = _insert_idea_spine(
            cursor,
            user_id=owner_id,
            timestamp=timestamp,
            title="Needle identity",
            summary="Needle identity summary",
        )

    reader, _ = _reader()
    rows = reader.search_rows(
        user_id=str(owner_id),
        query="needle",
        source_limit=10,
    ).rows

    assert {str(row["id"]) for row in rows["runs"]} == {str(completed_id)}
    assert str(failed_id) not in {str(row["id"]) for row in rows["runs"]}
    assert {str(row["id"]) for row in rows["ideas"]} == {str(identities["idea"])}
    assert {str(row["id"]) for row in rows["evidence"]} == {str(identities["evidence"])}
    assert {str(row["id"]) for row in rows["decisions"]} == {str(identities["decision"])}


def test_latest_decision_equal_timestamp_tie_uses_id_deterministically(
    search_identities,
) -> None:
    owner_id = search_identities["owner"]
    timestamp = datetime(2026, 7, 27, 19, tzinfo=timezone.utc)
    idea_id = uuid4()
    with _connect() as connection, connection.cursor() as cursor:
        first = _insert_idea_spine(
            cursor,
            user_id=owner_id,
            timestamp=timestamp,
            title="Needle tie",
            summary="Needle tie summary",
            decision_state="watching",
            idea_id=idea_id,
            decision_id=UUID("10000000-0000-0000-0000-000000000001"),
        )
        second_version = uuid4()
        second_evidence = uuid4()
        second_decision = UUID("f0000000-0000-0000-0000-000000000001")
        cursor.execute(
            """
            insert into public.idea_versions (
                id, user_id, idea_id, version_number, canonical_spec,
                strategy_snapshot, title, summary, lifecycle, created_at
            )
            values (
                %s, %s, %s, 2, '{}'::jsonb, '{}'::jsonb, 'Needle tie v2',
                'Needle tie v2', 'decided', %s
            )
            """,
            (second_version, owner_id, idea_id, timestamp),
        )
        cursor.execute(
            """
            insert into public.evidence_artifacts (
                id, user_id, idea_id, idea_version_id, title, digest, payload,
                lifecycle, created_at, updated_at
            )
            values (
                %s, %s, %s, %s, 'Needle tie evidence 2',
                'Needle tie digest 2', '{}'::jsonb, 'decided', %s, %s
            )
            """,
            (
                second_evidence,
                owner_id,
                idea_id,
                second_version,
                timestamp,
                timestamp,
            ),
        )
        cursor.execute(
            """
            insert into public.decision_notes (
                id, user_id, idea_id, idea_version_id, evidence_artifact_id,
                decision_state, note, created_at, updated_at
            )
            values (%s, %s, %s, %s, %s, 'rejected', 'higher id', %s, %s)
            """,
            (
                second_decision,
                owner_id,
                idea_id,
                second_version,
                second_evidence,
                timestamp,
                timestamp,
            ),
        )
        assert first["decision"] != second_decision

    reader, _ = _reader()
    result = reader.search_rows(
        user_id=str(owner_id),
        query="needle",
        source_limit=5,
    )

    assert result.rows["ideas"][0]["decision_state"] == "rejected"


def test_ledger_groups_are_exact_and_not_candidate_or_decision_filter_relative(
    search_identities,
) -> None:
    owner_id = search_identities["owner"]
    timestamp = datetime(2026, 7, 27, 20, tzinfo=timezone.utc)
    states = ["promising", "promising", "watching", "rejected", "promising"]
    with _connect() as connection, connection.cursor() as cursor:
        for offset, state in enumerate(states):
            _insert_idea_spine(
                cursor,
                user_id=owner_id,
                timestamp=timestamp - timedelta(seconds=offset),
                title=f"Needle ledger {offset}",
                summary=f"Needle ledger summary {offset}",
                decision_state=state,
            )

    reader, _ = _reader()
    result = reader.search_rows(
        user_id=str(owner_id),
        query="needle",
        source_limit=2,
        decision_state="promising",
        include_ledger_groups=True,
    )

    assert len(result.rows["ideas"]) == 2
    assert all(row["decision_state"] == "promising" for row in result.rows["ideas"])
    assert result.ledger_counts == {
        "promising": 3,
        "watching": 1,
        "rejected": 1,
        "revisit_later": 0,
    }


@pytest.mark.parametrize("initial_volume,larger_volume", [(40, 400)])
def test_search_query_and_row_budget_are_constant_as_volume_grows(
    search_identities,
    initial_volume: int,
    larger_volume: int,
) -> None:
    owner_id = search_identities["owner"]
    timestamp = datetime(2026, 7, 27, 21, tzinfo=timezone.utc)

    def insert_strategies(start: int, stop: int) -> None:
        with _connect() as connection, connection.cursor() as cursor:
            for offset in range(start, stop):
                _insert_strategy(
                    cursor,
                    user_id=owner_id,
                    timestamp=timestamp - timedelta(seconds=offset),
                    name=f"Needle scale {offset}",
                )

    insert_strategies(0, initial_volume)
    first_reader, first_pool = _reader()
    first = first_reader.search_rows(
        user_id=str(owner_id),
        query="needle",
        source_limit=6,
    )
    insert_strategies(initial_volume, larger_volume)
    larger_reader, larger_pool = _reader()
    larger = larger_reader.search_rows(
        user_id=str(owner_id),
        query="needle",
        source_limit=6,
    )

    assert len(first.rows["strategies"]) == len(larger.rows["strategies"]) == 6
    assert first_pool.tracker == {"query_count": 1, "row_counts": [6]}
    assert larger_pool.tracker == {"query_count": 1, "row_counts": [6]}


def test_search_candidate_plan_keeps_a_limit_inside_each_source(
    search_identities,
) -> None:
    from argus.domain.postgres_search_reader import _CANDIDATES_SQL

    owner_id = search_identities["owner"]
    timestamp = datetime(2026, 7, 27, 22, tzinfo=timezone.utc)
    with _connect() as connection, connection.cursor() as cursor:
        for offset in range(40):
            item_at = timestamp - timedelta(seconds=offset)
            conversation_id = _insert_conversation(
                cursor,
                user_id=owner_id,
                timestamp=item_at,
                title=f"Needle conversation {offset}",
            )
            _insert_strategy(
                cursor,
                user_id=owner_id,
                timestamp=item_at,
                name=f"Needle strategy {offset}",
            )
            _insert_collection(
                cursor,
                user_id=owner_id,
                timestamp=item_at,
                name=f"Needle collection {offset}",
            )
            _insert_run(
                cursor,
                user_id=owner_id,
                timestamp=item_at,
                title=f"Needle run {offset}",
                conversation_id=conversation_id,
            )
            _insert_idea_spine(
                cursor,
                user_id=owner_id,
                timestamp=item_at,
                title=f"Needle idea {offset}",
                summary=f"Needle summary {offset}",
                conversation_id=conversation_id,
            )

        cursor.execute(
            sql.SQL("explain (analyze, buffers, format json) {}").format(_CANDIDATES_SQL),
            {
                "user_id": owner_id,
                "normalized_query": "needle",
                "symbol_query": "needle",
                "source_limit": 6,
                "has_cursor": False,
                "cursor_pinned_rank": 0,
                "cursor_exact_rank": 0,
                "cursor_symbol_rank": 0,
                "cursor_type_rank": 0,
                "cursor_updated_at": None,
                "cursor_text_rank": 0,
                "cursor_id": None,
                "decision_state": None,
                "ledger_browse": False,
                "ideas_only": False,
                "guest_scope": False,
                "guest_conversation_id": None,
                "pivot_only": False,
                "pivot_id": None,
            },
        )
        explained = cursor.fetchone()[0][0]

    def plan_nodes(plan: dict[str, Any]):
        yield plan
        for child in plan.get("Plans", []):
            yield from plan_nodes(child)

    plan = explained["Plan"]
    nodes = list(plan_nodes(plan))
    limits = [node for node in nodes if node["Node Type"] == "Limit"]

    assert len(limits) >= 7
    assert all(node["Actual Rows"] <= 6 for node in limits)
    assert plan["Actual Rows"] <= 42
    assert explained["Execution Time"] < 2_000
