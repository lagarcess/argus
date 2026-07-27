from __future__ import annotations

import atexit
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Any
from uuid import UUID

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

_HISTORY_CONNECT_TIMEOUT_SECONDS = 2
_HISTORY_ACQUIRE_TIMEOUT_SECONDS = 2.0
_HISTORY_STATEMENT_TIMEOUT_MS = 2_000
_HISTORY_POOL_SIZE = 5


class HistoryCursorError(ValueError):
    """Raised when a merged History cursor pivot cannot be resolved exactly."""


_PIVOT_SQL = """
select source_type, pinned, type_rank
from (
    select 'run'::text as source_type, false as pinned, 1 as type_rank
    from public.backtest_runs as run
    where run.user_id = %s
      and run.id = %s

    union all

    select 'chat'::text as source_type, chat.pinned, 4 as type_rank
    from public.conversations as chat
    where chat.user_id = %s
      and chat.id = %s
      and exists (
          select 1
          from public.messages as message
          where message.user_id = %s
            and message.conversation_id = chat.id
      )

    union all

    select 'strategy'::text as source_type, strategy.pinned, 3 as type_rank
    from public.strategies as strategy
    where strategy.user_id = %s
      and strategy.id = %s

    union all

    select 'collection'::text as source_type, collection.pinned, 2 as type_rank
    from public.collections as collection
    where collection.user_id = %s
      and collection.id = %s
) as pivots
"""


_CANDIDATES_SQL = """
with input as (
    select
        %s::uuid as user_id,
        %s::boolean as archived,
        %s::boolean as deleted,
        %s::boolean as has_cursor,
        %s::boolean as cursor_pinned,
        %s::timestamptz as cursor_activity_at,
        %s::integer as cursor_type_rank,
        %s::uuid as cursor_id,
        %s::integer as source_limit
),
run_candidates as (
    select
        'run'::text as source_type,
        false as pinned,
        run.created_at as activity_at,
        1 as type_rank,
        run.id,
        jsonb_build_object(
            'id', run.id,
            'conversation_id', run.conversation_id,
            'conversation_result_card', run.conversation_result_card,
            'created_at', run.created_at
        ) as payload
    from input
    join public.backtest_runs as run
      on run.user_id = input.user_id
    left join public.conversations as parent
      on parent.id = run.conversation_id
     and parent.user_id = input.user_id
    where (
        (
            parent.id is null
            and not input.archived
            and not input.deleted
        )
        or (
            parent.id is not null
            and parent.archived = input.archived
            and (
                (input.deleted and parent.deleted_at is not null)
                or (not input.deleted and parent.deleted_at is null)
            )
        )
    )
      and (
          not input.has_cursor
          or row(false, run.created_at, 1, run.id)
             < row(
                 input.cursor_pinned,
                 input.cursor_activity_at,
                 input.cursor_type_rank,
                 input.cursor_id
             )
      )
    order by run.created_at desc, run.id desc
    limit (select source_limit from input)
),
chat_candidates as (
    select
        'chat'::text as source_type,
        chat.pinned,
        chat.updated_at as activity_at,
        4 as type_rank,
        chat.id,
        jsonb_build_object(
            'id', chat.id,
            'title', chat.title,
            'title_source', chat.title_source,
            'last_message_preview', chat.last_message_preview,
            'pinned', chat.pinned,
            'updated_at', chat.updated_at,
            'deleted_at', chat.deleted_at,
            'archived', chat.archived
        ) as payload
    from input
    join public.conversations as chat
      on chat.user_id = input.user_id
    where chat.archived = input.archived
      and (
          (input.deleted and chat.deleted_at is not null)
          or (not input.deleted and chat.deleted_at is null)
      )
      and exists (
          select 1
          from public.messages as message
          where message.user_id = input.user_id
            and message.conversation_id = chat.id
      )
      and (
          not input.has_cursor
          or row(chat.pinned, chat.updated_at, 4, chat.id)
             < row(
                 input.cursor_pinned,
                 input.cursor_activity_at,
                 input.cursor_type_rank,
                 input.cursor_id
             )
      )
    order by chat.pinned desc, chat.updated_at desc, chat.id desc
    limit (select source_limit from input)
),
strategy_candidates as (
    select
        'strategy'::text as source_type,
        strategy.pinned,
        strategy.updated_at as activity_at,
        3 as type_rank,
        strategy.id,
        jsonb_build_object(
            'id', strategy.id,
            'name', strategy.name,
            'symbols', strategy.symbols,
            'pinned', strategy.pinned,
            'updated_at', strategy.updated_at,
            'deleted_at', strategy.deleted_at
        ) as payload
    from input
    join public.strategies as strategy
      on strategy.user_id = input.user_id
    where (
        (input.deleted and strategy.deleted_at is not null)
        or (not input.deleted and strategy.deleted_at is null)
    )
      and (
          not input.has_cursor
          or row(strategy.pinned, strategy.updated_at, 3, strategy.id)
             < row(
                 input.cursor_pinned,
                 input.cursor_activity_at,
                 input.cursor_type_rank,
                 input.cursor_id
             )
      )
    order by strategy.pinned desc, strategy.updated_at desc, strategy.id desc
    limit (select source_limit from input)
),
collection_candidates as (
    select
        collection.user_id,
        collection.id,
        collection.name,
        collection.pinned,
        collection.deleted_at,
        collection.updated_at
    from input
    join public.collections as collection
      on collection.user_id = input.user_id
    where (
        (input.deleted and collection.deleted_at is not null)
        or (not input.deleted and collection.deleted_at is null)
    )
      and (
          not input.has_cursor
          or row(collection.pinned, collection.updated_at, 2, collection.id)
             < row(
                 input.cursor_pinned,
                 input.cursor_activity_at,
                 input.cursor_type_rank,
                 input.cursor_id
             )
      )
    order by collection.pinned desc, collection.updated_at desc, collection.id desc
    limit (select source_limit from input)
),
collection_rows as (
    select
        'collection'::text as source_type,
        collection.pinned,
        collection.updated_at as activity_at,
        2 as type_rank,
        collection.id,
        jsonb_build_object(
            'id', collection.id,
            'name', collection.name,
            'pinned', collection.pinned,
            'updated_at', collection.updated_at,
            'deleted_at', collection.deleted_at,
            'strategy_count', (
                select count(*)
                from public.collection_strategies as member
                where member.user_id = collection.user_id
                  and member.collection_id = collection.id
            )
        ) as payload
    from collection_candidates as collection
),
candidates as (
    select * from run_candidates
    union all
    select * from chat_candidates
    union all
    select * from strategy_candidates
    union all
    select * from collection_rows
)
select source_type, payload
from candidates
order by pinned desc, activity_at desc, type_rank desc, id desc
"""


@dataclass(frozen=True)
class PostgresHistoryReader:
    pool: Any

    def list_rows(
        self,
        *,
        user_id: str,
        limit: int,
        archived: bool,
        deleted: bool,
        cursor_activity_at: datetime | None = None,
        cursor_id: str | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        if limit < 1:
            raise ValueError("History source limit must be positive.")
        try:
            owner_id = UUID(user_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("History owner id must be a UUID.") from exc

        has_cursor = cursor_activity_at is not None or cursor_id is not None
        if has_cursor and (cursor_activity_at is None or cursor_id is None):
            raise HistoryCursorError("History cursor is incomplete.")
        try:
            pivot_id = UUID(cursor_id) if cursor_id is not None else None
        except (TypeError, ValueError) as exc:
            raise HistoryCursorError("History cursor id is invalid.") from exc

        pivot_pinned = False
        pivot_type_rank = 0
        with self.pool.connection(timeout=_HISTORY_ACQUIRE_TIMEOUT_SECONDS) as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                if has_cursor:
                    pivot_params = (
                        owner_id,
                        pivot_id,
                        owner_id,
                        pivot_id,
                        owner_id,
                        owner_id,
                        pivot_id,
                        owner_id,
                        pivot_id,
                    )
                    cursor.execute(_PIVOT_SQL, pivot_params)
                    pivots = cursor.fetchall()
                    if len(pivots) != 1:
                        raise HistoryCursorError(
                            "History cursor pivot is missing or ambiguous."
                        )
                    pivot_pinned = bool(pivots[0]["pinned"])
                    pivot_type_rank = int(pivots[0]["type_rank"])

                cursor.execute(
                    _CANDIDATES_SQL,
                    (
                        owner_id,
                        archived,
                        deleted,
                        has_cursor,
                        pivot_pinned,
                        cursor_activity_at,
                        pivot_type_rank,
                        pivot_id,
                        limit,
                    ),
                )
                candidates = cursor.fetchall()

        grouped: dict[str, list[dict[str, Any]]] = {
            "runs": [],
            "conversations": [],
            "strategies": [],
            "collections": [],
        }
        target_by_source = {
            "run": "runs",
            "chat": "conversations",
            "strategy": "strategies",
            "collection": "collections",
        }
        for candidate in candidates:
            target = target_by_source.get(str(candidate.get("source_type")))
            payload = candidate.get("payload")
            if target is None or not isinstance(payload, dict):
                continue
            grouped[target].append(payload)
        return grouped


@lru_cache(maxsize=2)
def history_reader_for_database_url(database_url: str) -> PostgresHistoryReader:
    if not database_url:
        raise RuntimeError("Persistent History requires DATABASE_URL.")
    pool = ConnectionPool(
        conninfo=database_url,
        kwargs={
            "autocommit": True,
            "connect_timeout": _HISTORY_CONNECT_TIMEOUT_SECONDS,
            "options": f"-c statement_timeout={_HISTORY_STATEMENT_TIMEOUT_MS}",
        },
        min_size=0,
        max_size=_HISTORY_POOL_SIZE,
        open=True,
        timeout=_HISTORY_ACQUIRE_TIMEOUT_SECONDS,
        name="argus-history",
    )
    atexit.register(pool.close)
    return PostgresHistoryReader(pool)
