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


CONVERSATION_ID = "00000000-0000-0000-0000-000000000101"
OWNER_ID = "00000000-0000-0000-0000-000000000001"
ACTIVITY_AT = "2026-07-27T12:00:00+00:00"


def _conversation_candidate() -> dict[str, Any]:
    return {
        "source_type": "conversation",
        "pinned_rank": 0,
        "exact_rank": 0,
        "symbol_rank": 0,
        "layer_rank": 6,
        "text_rank": 50,
        "payload": {
            "id": CONVERSATION_ID,
            "title": "Search chat",
            "last_message_preview": "Search preview",
            "updated_at": "2026-07-26T12:00:00+00:00",
            "pinned": False,
            "deleted_at": None,
            "_recall_match": {
                "matched_text": "Search decision evidence",
                "layer_rank": 6,
                "layer": "decision",
                "match_count": 1,
                "message_id": None,
                "symbol_exact_match": False,
                "activity_at": ACTIVITY_AT,
            },
        },
    }


def _hydration_row() -> dict[str, Any]:
    return {
        "conversation_payload": {
            "id": CONVERSATION_ID,
            "title": "Search chat",
            "last_message_preview": "Search preview",
            "updated_at": "2026-07-26T12:00:00+00:00",
            "pinned": False,
            "deleted_at": None,
            "_recall_summary": {
                "run_count": 7,
                "symbols": ["AAPL", "MSFT"],
                "strategy_families": ["buy_and_hold"],
                "start_date": "2019-01-01",
                "end_date": "2026-07-27",
                "decision_states": ["promising", "watching"],
                "latest_run_decided": False,
                "latest_suggestion_untaken": False,
                "latest_activity": ACTIVITY_AT,
            },
        },
        "latest_run_payload": {
            "id": "00000000-0000-0000-0000-000000000401",
            "conversation_id": CONVERSATION_ID,
            "status": "completed",
            "symbols": ["AAPL"],
            "benchmark_symbol": "SPY",
            "config_snapshot": {"template": "buy_and_hold"},
            "conversation_result_card": {"title": "Latest run"},
            "created_at": ACTIVITY_AT,
            "updated_at": ACTIVITY_AT,
        },
        "judged_run_payload": {
            "id": "00000000-0000-0000-0000-000000000402",
            "conversation_id": CONVERSATION_ID,
            "status": "completed",
            "symbols": ["MSFT"],
            "benchmark_symbol": "SPY",
            "config_snapshot": {"template": "buy_and_hold"},
            "conversation_result_card": {"title": "Judged older run"},
            "created_at": "2025-01-01T12:00:00+00:00",
            "updated_at": "2025-01-01T12:00:00+00:00",
        },
        "latest_evidence_payload": {
            "id": "00000000-0000-0000-0000-000000000301",
            "source_conversation_id": CONVERSATION_ID,
            "source_run_id": "00000000-0000-0000-0000-000000000401",
            "title": "Latest evidence",
            "digest": "Latest quick take",
            "payload": {},
            "updated_at": ACTIVITY_AT,
        },
        "latest_decision_payload": {
            "id": "00000000-0000-0000-0000-000000000501",
            "source_conversation_id": CONVERSATION_ID,
            "evidence_artifact_id": "00000000-0000-0000-0000-000000000302",
            "source_run_id": "00000000-0000-0000-0000-000000000402",
            "decision_state": "promising",
            "note": "Search decision.",
            "artifact_title": "Older evidence",
            "artifact_digest": "Older quick take",
            "artifact_payload": {},
            "updated_at": ACTIVITY_AT,
        },
    }


def test_search_first_page_is_one_candidate_one_hydration_and_one_ledger_read() -> None:
    reader_type, _ = _reader_types()
    pool = _RecordingPool(
        [
            [_conversation_candidate()],
            [_hydration_row()],
            [
                {"decision_state": "promising", "count": 1},
                {"decision_state": "watching", "count": 1},
            ],
        ]
    )

    result = reader_type(pool).search_rows(
        user_id=OWNER_ID,
        query="search",
        source_limit=4,
        include_ledger_groups=True,
    )

    assert {source: len(rows) for source, rows in result.rows.items()} == {
        "conversations": 1,
        "strategies": 0,
        "collections": 0,
        "runs": 2,
        "ideas": 0,
        "evidence": 1,
        "decisions": 1,
    }
    assert result.rows["conversations"][0]["_recall_match"] == {
        "matched_text": "Search decision evidence",
        "layer_rank": 6,
        "layer": "decision",
        "match_count": 1,
        "message_id": None,
        "symbol_exact_match": False,
        "activity_at": ACTIVITY_AT,
    }
    assert result.rows["conversations"][0]["_recall_summary"]["run_count"] == 7
    assert result.ledger_counts == {
        "promising": 1,
        "watching": 1,
        "rejected": 0,
        "revisit_later": 0,
    }
    assert len(pool.cursor.executions) == 3
    assert pool.cursor.executions[0][1]["source_limit"] == 4
    assert pool.acquisition_timeouts == [2.0]


def test_search_rejects_nonpositive_bound_before_database_read() -> None:
    reader_type, _ = _reader_types()
    pool = _RecordingPool([])

    with pytest.raises(ValueError, match="positive"):
        reader_type(pool).search_rows(
            user_id=OWNER_ID,
            query="search",
            source_limit=0,
        )

    assert pool.cursor.executions == []


@pytest.mark.parametrize("query", ["a", "GL", "__"])
def test_search_defers_nonempty_queries_without_an_indexable_token(
    query: str,
) -> None:
    reader_type, _ = _reader_types()
    pool = _RecordingPool([])

    result = reader_type(pool).search_rows(
        user_id=OWNER_ID,
        query=query,
        source_limit=4,
        include_ledger_groups=True,
    )

    assert all(not rows for rows in result.rows.values())
    assert result.asset_rollup is None
    assert result.ledger_counts == {
        "promising": 0,
        "watching": 0,
        "rejected": 0,
        "revisit_later": 0,
    }
    assert pool.cursor.executions == []
    assert pool.acquisition_timeouts == []


@pytest.mark.parametrize("pivot_rows", [[], [_conversation_candidate()] * 2])
def test_search_cursor_missing_foreign_or_ambiguous_pivot_fails_closed(
    pivot_rows: list[dict[str, Any]],
) -> None:
    reader_type, cursor_error = _reader_types()
    pool = _RecordingPool([pivot_rows])

    with pytest.raises(cursor_error):
        reader_type(pool).search_rows(
            user_id=OWNER_ID,
            query="search",
            source_limit=4,
            cursor_updated_at=datetime(2026, 7, 27, 12, tzinfo=timezone.utc),
            cursor_id=CONVERSATION_ID,
        )

    assert len(pool.cursor.executions) == 1


def test_search_naive_cursor_fails_before_database_read() -> None:
    reader_type, cursor_error = _reader_types()
    pool = _RecordingPool([])

    with pytest.raises(cursor_error):
        reader_type(pool).search_rows(
            user_id=OWNER_ID,
            query="search",
            source_limit=4,
            cursor_updated_at=datetime(2026, 7, 27),
            cursor_id=CONVERSATION_ID,
        )

    assert pool.cursor.executions == []


@pytest.mark.parametrize(
    "cursor_id",
    ["{aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa}", "AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA"],
)
def test_search_noncanonical_cursor_uuid_fails_before_database_read(
    cursor_id: str,
) -> None:
    reader_type, cursor_error = _reader_types()
    pool = _RecordingPool([])

    with pytest.raises(cursor_error):
        reader_type(pool).search_rows(
            user_id=OWNER_ID,
            query="search",
            source_limit=4,
            cursor_updated_at=datetime(2026, 7, 27, tzinfo=timezone.utc),
            cursor_id=cursor_id,
        )

    assert pool.cursor.executions == []


def test_search_nul_query_keeps_normalized_text_but_never_binds_raw_nul() -> None:
    reader_type, _ = _reader_types()
    pool = _RecordingPool([[]])

    reader_type(pool).search_rows(
        user_id=OWNER_ID,
        query="nee\x00dle",
        source_limit=4,
    )

    params = pool.cursor.executions[0][1]
    assert params["normalized_query"] == "nee dle"
    assert params["symbol_query"] is None
    assert "\x00" not in str(params)


def test_search_uses_bound_token_array_without_row_token_splitting() -> None:
    reader_type, _ = _reader_types()
    pool = _RecordingPool([[]])

    reader_type(pool).search_rows(
        user_id=OWNER_ID,
        query="Alpha x beta alpha",
        source_limit=4,
    )

    query, params = pool.cursor.executions[0]
    rendered = query.as_string()

    assert "regexp_split_to_table" not in rendered
    assert params["token_patterns"] == ["%alpha%", "%x%", "%beta%"]
    assert params["anchor_pattern"] == "%alpha%"
    assert "unnest(%(token_patterns)s::text[])" in rendered
    assert "%(anchor_pattern)s" in rendered
    assert "token_0_pattern" not in rendered


def test_search_sql_shape_is_constant_as_token_count_grows() -> None:
    reader_type, _ = _reader_types()

    def rendered_sql_shape(query: str) -> tuple[int, int]:
        pool = _RecordingPool([[]])
        reader_type(pool).search_rows(
            user_id=OWNER_ID,
            query=query,
            source_limit=4,
        )
        rendered = pool.cursor.executions[0][0].as_string()
        return len(rendered), rendered.count('collate "und-x-icu"')

    assert rendered_sql_shape(
        " ".join(f"needle{index:03d}" for index in range(400))
    ) == rendered_sql_shape("needle000")


def test_search_groups_all_matching_layers_before_conversation_limit() -> None:
    reader_type, _ = _reader_types()
    pool = _RecordingPool([[]])

    reader_type(pool).search_rows(
        user_id=OWNER_ID,
        query="alpha",
        source_limit=4,
    )

    assert len(pool.cursor.executions) == 1
    rendered = pool.cursor.executions[0][0].as_string()
    for source_table in (
        "public.conversations",
        "public.messages",
        "public.backtest_runs",
        "public.ideas",
        "public.evidence_artifacts",
        "public.decision_notes",
    ):
        assert source_table in rendered
    assert "message.role = 'user'" in rendered
    assert "row_number() over" in rendered
    assert "partition by matches.conversation_id" in rendered
    assert rendered.rfind("limit") > rendered.rfind("partition by")
    # Each child layer joins its canonical active conversation before grouping.
    assert rendered.count("conversation.deleted_at is null") >= 7


def test_search_guest_workspace_scope_is_inside_every_match_layer_before_limit() -> None:
    reader_type, _ = _reader_types()
    pool = _RecordingPool([[]])

    reader_type(pool).search_rows(
        user_id=OWNER_ID,
        query="alpha",
        source_limit=1,
        guest_scope=True,
        guest_conversation_id=CONVERSATION_ID,
    )

    rendered, params = pool.cursor.executions[0]
    sql_text = rendered.as_string()
    assert sql_text.count("conversation.id = input.guest_conversation_id") >= 6
    assert sql_text.rfind("conversation.id = input.guest_conversation_id") < (
        sql_text.rfind("row_number() over")
    )
    assert str(params["guest_conversation_id"]) == CONVERSATION_ID
    assert params["source_limit"] == 1


def test_search_decision_filter_and_ledger_match_all_conversation_layers() -> None:
    reader_type, _ = _reader_types()
    pool = _RecordingPool([[], []])

    reader_type(pool).search_rows(
        user_id=OWNER_ID,
        query="alpha",
        source_limit=4,
        decision_state="watching",
        include_ledger_groups=True,
    )

    candidate_sql = pool.cursor.executions[0][0].as_string()
    ledger_sql = pool.cursor.executions[1][0].as_string()
    for source_table in (
        "public.conversations",
        "public.backtest_runs",
        "public.ideas",
        "public.evidence_artifacts",
        "public.decision_notes",
    ):
        assert source_table in candidate_sql
        assert source_table in ledger_sql
    assert "count(distinct conversation_id)" in ledger_sql
    assert pool.cursor.executions[1][1]["decision_state"] is None


def test_search_cursor_pivots_on_conversation_projection_and_canonical_activity() -> None:
    reader_type, _ = _reader_types()
    pool = _RecordingPool([[_conversation_candidate()], []])

    reader_type(pool).search_rows(
        user_id=OWNER_ID,
        query="Alpha x",
        source_limit=4,
        cursor_updated_at=datetime(2026, 7, 27, 12, tzinfo=timezone.utc),
        cursor_id=CONVERSATION_ID,
    )

    pivot_query, pivot_params = pool.cursor.executions[0]
    rendered = pivot_query.as_string()
    assert "ranked.conversation_id = input.cursor_id" in rendered
    assert "ranked.activity_at = input.cursor_updated_at" in rendered
    assert "run.id = %(cursor_id)s::uuid" not in rendered
    assert "decision.id = %(cursor_id)s::uuid" not in rendered
    page_params = pool.cursor.executions[1][1]
    assert page_params["cursor_layer_rank"] == 6
    assert pivot_params["cursor_id"] == page_params["cursor_id"]


def test_search_hydration_is_one_owner_scoped_full_aggregate_without_child_cap() -> None:
    reader_type, _ = _reader_types()
    pool = _RecordingPool([[_conversation_candidate()], [_hydration_row()]])

    result = reader_type(pool).search_rows(
        user_id=OWNER_ID,
        query="search",
        source_limit=4,
    )

    assert result.rows["conversations"][0]["_recall_summary"] == {
        "run_count": 7,
        "symbols": ["AAPL", "MSFT"],
        "strategy_families": ["buy_and_hold"],
        "start_date": "2019-01-01",
        "end_date": "2026-07-27",
        "decision_states": ["promising", "watching"],
        "latest_run_decided": False,
        "latest_suggestion_untaken": False,
        "latest_activity": ACTIVITY_AT,
    }
    assert [row["conversation_id"] for row in result.rows["runs"]] == [
        CONVERSATION_ID,
        CONVERSATION_ID,
    ]
    assert len(pool.cursor.executions) == 2
    hydration_sql, params = pool.cursor.executions[1]
    rendered = str(hydration_sql)
    assert "recall_rank <= 5" not in rendered
    assert "count(*)::integer as run_count" in rendered
    assert "select distinct decision.decision_state" in rendered
    assert "min(" in rendered and "max(" in rendered
    assert "limit 1" in rendered
    assert params["conversation_ids"] == [CONVERSATION_ID]
    assert str(params["user_id"]) == OWNER_ID


def test_search_hydration_projects_only_a_bounded_untaken_suggestion_bit() -> None:
    reader_type, _ = _reader_types()
    pool = _RecordingPool([[_conversation_candidate()], [_hydration_row()]])

    reader_type(pool).search_rows(
        user_id=OWNER_ID,
        query="search",
        source_limit=4,
    )

    hydration_sql = " ".join(str(pool.cursor.executions[1][0]).split())
    assert "'latest_suggestion_untaken'" in hydration_sql
    assert "offer.metadata->>'result_run_id' = latest_run.id::text" in hydration_sql
    assert "argus_next_experiments/v1" in hydration_sql
    assert "not exists" in hydration_sql
    assert "later_message.role = 'user'" in hydration_sql
    assert "latest_suggestion.untaken" in hydration_sql
    assert "'content', offer.content" not in hydration_sql
    assert "'metadata', offer.metadata" not in hydration_sql


def test_search_hydration_activity_mirrors_ranked_message_activity_scope() -> None:
    reader_type, _ = _reader_types()
    pool = _RecordingPool([[_conversation_candidate()], [_hydration_row()]])

    reader_type(pool).search_rows(
        user_id=OWNER_ID,
        query="search",
        source_limit=4,
    )

    ranking_sql = " ".join(pool.cursor.executions[0][0].as_string().split())
    hydration_sql = " ".join(str(pool.cursor.executions[1][0]).split())
    assert (
        "select max(message.created_at) "
        "from public.messages as message "
        "where message.user_id = input.user_id "
        "and message.conversation_id = conversation.id"
    ) in ranking_sql
    assert (
        "select max(message.created_at) "
        "from public.messages as message "
        "where message.user_id = %(user_id)s "
        "and message.conversation_id = conversation.id"
    ) in hydration_sql


def test_search_full_aggregate_projects_exact_dossier_without_hydrating_all_children() -> (
    None
):
    from argus.api.search_assembly import scored_supabase_search_items

    reader_type, _ = _reader_types()
    pool = _RecordingPool([[_conversation_candidate()], [_hydration_row()]])
    result = reader_type(pool).search_rows(
        user_id=OWNER_ID,
        query="search",
        source_limit=4,
    )

    scored = scored_supabase_search_items(raw=result.rows, query="search")

    assert len(scored) == 1
    _, item = scored[0]
    assert item.id == CONVERSATION_ID
    assert item.matched_text == "Search decision evidence"
    assert item.updated_at.isoformat() == ACTIVITY_AT
    assert item.decision_states == ("promising", "watching")
    assert item.dossier.tested.run_count == 7
    assert item.dossier.tested.symbols == ["AAPL", "MSFT"]
    assert item.dossier.tested.start_date.isoformat() == "2019-01-01"
    assert item.dossier.decision is not None
    assert item.dossier.decision.run_label == "Judged older run"
    assert item.dossier.outcome is not None
    assert item.dossier.outcome.run_label == "Latest run"


def test_persistent_title_match_never_trusts_an_unrelated_preview_hint() -> None:
    from argus.api.search_assembly import scored_supabase_search_items

    candidate = _conversation_candidate()
    candidate["payload"].update(
        {
            "title": "Gold allocation",
            "last_message_preview": "Review again later",
            "_recall_match": {
                "matched_text": "Review again later",
                "layer_rank": 1,
                "symbol_exact_match": False,
                "activity_at": ACTIVITY_AT,
            },
        }
    )
    hydration = _hydration_row()
    hydration["conversation_payload"].update(
        {
            "title": "Gold allocation",
            "last_message_preview": "Review again later",
        }
    )
    reader_type, _ = _reader_types()
    result = reader_type(_RecordingPool([[candidate], [hydration]])).search_rows(
        user_id=OWNER_ID,
        query="gold",
        source_limit=4,
    )

    scored = scored_supabase_search_items(raw=result.rows, query="gold")

    assert len(scored) == 1
    _, item = scored[0]
    assert item.matched_text == "Gold allocation"


def test_persistent_preview_match_returns_preview_with_unrelated_title() -> None:
    from argus.api.search_assembly import scored_supabase_search_items

    candidate = _conversation_candidate()
    candidate["payload"].update(
        {
            "title": "Review again later",
            "last_message_preview": "Gold allocation",
            "_recall_match": {
                "matched_text": "Gold allocation",
                "layer_rank": 1,
                "symbol_exact_match": False,
                "activity_at": ACTIVITY_AT,
            },
        }
    )
    hydration = _hydration_row()
    hydration["conversation_payload"].update(
        {
            "title": "Review again later",
            "last_message_preview": "Gold allocation",
        }
    )
    reader_type, _ = _reader_types()
    result = reader_type(_RecordingPool([[candidate], [hydration]])).search_rows(
        user_id=OWNER_ID,
        query="gold",
        source_limit=4,
    )

    scored = scored_supabase_search_items(raw=result.rows, query="gold")

    assert len(scored) == 1
    _, item = scored[0]
    assert item.matched_text == "Gold allocation"


def test_conversation_recall_anchor_predicates_match_the_shipped_indexes() -> None:
    from argus.domain.postgres_search_reader import (
        _DECISION_INDEX_HAYSTACK,
        _EVIDENCE_INDEX_HAYSTACK,
        _RUN_INDEX_HAYSTACK,
        _conversation_match_ctes,
        _normalized,
    )

    rendered = " ".join(
        _conversation_match_ctes(has_anchor=True).as_string().split()
    )
    indexed_haystacks = (
        (
            "conversation.title || ' ' "
            "|| coalesce(conversation.last_message_preview, '')"
        ),
        "message.content",
        _RUN_INDEX_HAYSTACK,
        "idea.title || ' ' || coalesce(idea.summary, '')",
        _EVIDENCE_INDEX_HAYSTACK,
        _DECISION_INDEX_HAYSTACK,
    )

    for haystack in indexed_haystacks:
        normalized = " ".join(_normalized(haystack).as_string().split())
        assert f"{normalized} like %(anchor_pattern)s" in rendered


def test_conversation_recall_caps_every_source_before_window_ranking() -> None:
    reader_type, _ = _reader_types()
    pool = _RecordingPool([[]])

    reader_type(pool).search_rows(
        user_id=OWNER_ID,
        query="the",
        source_limit=30,
    )

    rendered, params = pool.cursor.executions[0]
    sql_text = rendered.as_string()
    assert "%(match_limit)s::integer as match_limit" in sql_text
    bounded_matches = sql_text[
        sql_text.index("matches as (") : sql_text.index("winning_matches as (")
    ]
    assert bounded_matches.count(
        "limit (select match_limit from input)"
    ) == 6
    assert bounded_matches.rfind(
        "limit (select match_limit from input)"
    ) < sql_text.index("count(*) over")
    assert params["match_limit"] == 300


def test_conversation_recall_match_cap_has_an_absolute_ceiling() -> None:
    from argus.domain.postgres_search_reader import _conversation_match_limit

    assert _conversation_match_limit(1) == 10
    assert _conversation_match_limit(101) == 1_010
    assert _conversation_match_limit(1_000) == 1_010
