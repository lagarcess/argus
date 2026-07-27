from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg import sql
from psycopg.rows import dict_row

from argus.domain.search_sql_text import normalizer_expression
from argus.domain.search_text import normalize_search_text

_SEARCH_ACQUIRE_TIMEOUT_SECONDS = 2.0
_DECISION_STATES = ("promising", "watching", "rejected", "revisit_later")
_ROW_GROUP_BY_SOURCE = {
    "chat": "conversations",
    "strategy": "strategies",
    "collection": "collections",
    "run": "runs",
    "idea": "ideas",
    "evidence": "evidence",
    "decision": "decisions",
}


class SearchCursorError(ValueError):
    """Raised when a scoped Search cursor pivot cannot be resolved exactly."""


@dataclass(frozen=True)
class SearchReadResult:
    rows: dict[str, list[dict[str, Any]]]
    ledger_counts: dict[str, int] | None = None


def _normalized(expression: str) -> sql.Composed:
    return normalizer_expression(sql.SQL(expression))


def _base_cte(
    *,
    name: str,
    source_type: str,
    source_sql: str,
    title_expression: str,
    matched_expression: str,
    haystack_expression: str,
    symbol_rank_expression: str,
    type_rank_expression: str,
    pinned_rank_expression: str,
    activity_expression: str,
    id_expression: str,
    payload_expression: str,
    allow_empty_query: bool = False,
) -> sql.Composed:
    match_predicate: sql.Composable = sql.SQL(
        """
        (
            input.normalized_query <> ''
            and (
                strpos(base.normalized_haystack, input.normalized_query) > 0
                or not exists (
                    select 1
                    from regexp_split_to_table(
                        input.normalized_query,
                        ' +'
                    ) as query_token
                    where strpos(
                        base.normalized_haystack,
                        query_token
                    ) = 0
                )
            )
        )
        """
    )
    if allow_empty_query:
        match_predicate = sql.SQL("(input.normalized_query = '' or {})").format(
            match_predicate
        )
    return sql.SQL(
        """
        {base_name} as (
            select
                {source_type}::text as source_type,
                {id_expression} as id,
                {activity_expression} as activity_at,
                ({pinned_rank_expression})::integer as pinned_rank,
                ({type_rank_expression})::integer as type_rank,
                {normalized_title} as normalized_title,
                {normalized_matched} as normalized_matched,
                {normalized_haystack} as normalized_haystack,
                ({symbol_rank_expression})::integer as symbol_rank,
                {payload_expression} as payload
            from input
            {source_sql}
        ),
        {eligible_name} as (
            select
                base.source_type,
                base.id,
                base.activity_at,
                base.pinned_rank,
                (
                    input.normalized_query = base.normalized_title
                )::integer as exact_rank,
                base.symbol_rank,
                base.type_rank,
                (
                    case
                        when input.normalized_query <> ''
                         and strpos(
                             base.normalized_title,
                             input.normalized_query
                         ) > 0
                            then 100
                        else 0
                    end
                    +
                    case
                        when input.normalized_query <> ''
                         and strpos(
                             base.normalized_matched,
                             input.normalized_query
                         ) > 0
                            then 50
                        else 0
                    end
                )::integer as text_rank,
                base.payload
            from {base_name} as base
            cross join input
            where {match_predicate}
        )
        """
    ).format(
        base_name=sql.Identifier(f"{name}_base"),
        eligible_name=sql.Identifier(f"{name}_eligible"),
        source_type=sql.Literal(source_type),
        id_expression=sql.SQL(id_expression),
        activity_expression=sql.SQL(activity_expression),
        pinned_rank_expression=sql.SQL(pinned_rank_expression),
        type_rank_expression=sql.SQL(type_rank_expression),
        normalized_title=_normalized(title_expression),
        normalized_matched=_normalized(matched_expression),
        normalized_haystack=_normalized(haystack_expression),
        symbol_rank_expression=sql.SQL(symbol_rank_expression),
        payload_expression=sql.SQL(payload_expression),
        source_sql=sql.SQL(source_sql),
        match_predicate=match_predicate,
    )


_INPUT_CTE = sql.SQL(
    """
    input as (
        select
            %(user_id)s::uuid as user_id,
            %(normalized_query)s::text as normalized_query,
            %(symbol_query)s::text as symbol_query,
            %(source_limit)s::integer as source_limit,
            %(has_cursor)s::boolean as has_cursor,
            %(cursor_pinned_rank)s::integer as cursor_pinned_rank,
            %(cursor_exact_rank)s::integer as cursor_exact_rank,
            %(cursor_symbol_rank)s::integer as cursor_symbol_rank,
            %(cursor_type_rank)s::integer as cursor_type_rank,
            %(cursor_updated_at)s::timestamptz as cursor_updated_at,
            %(cursor_text_rank)s::integer as cursor_text_rank,
            %(cursor_id)s::uuid as cursor_id,
            %(decision_state)s::text as decision_state,
            %(ledger_browse)s::boolean as ledger_browse,
            %(ideas_only)s::boolean as ideas_only,
            %(guest_scope)s::boolean as guest_scope,
            %(guest_conversation_id)s::uuid as guest_conversation_id,
            %(pivot_only)s::boolean as pivot_only,
            %(pivot_id)s::uuid as pivot_id
    )
    """
)

_CHAT_CTE = _base_cte(
    name="chat",
    source_type="chat",
    source_sql="""
        join public.conversations as chat
          on chat.user_id = input.user_id
         and chat.deleted_at is null
         and not input.ideas_only
         and (
             not input.guest_scope
             or chat.id = input.guest_conversation_id
         )
         and (not input.pivot_only or chat.id = input.pivot_id)
    """,
    title_expression="chat.title",
    matched_expression=("coalesce(nullif(chat.last_message_preview, ''), chat.title)"),
    haystack_expression=("chat.title || ' ' || coalesce(chat.last_message_preview, '')"),
    symbol_rank_expression="false",
    type_rank_expression="4",
    pinned_rank_expression="chat.pinned",
    activity_expression="chat.updated_at",
    id_expression="chat.id",
    payload_expression="""
        jsonb_build_object(
            'id', chat.id,
            'title', chat.title,
            'last_message_preview', chat.last_message_preview,
            'updated_at', chat.updated_at,
            'deleted_at', chat.deleted_at,
            'pinned', chat.pinned
        )
    """,
)

_STRATEGY_CTE = _base_cte(
    name="strategy",
    source_type="strategy",
    source_sql="""
        join public.strategies as strategy
          on strategy.user_id = input.user_id
         and strategy.deleted_at is null
         and not input.ideas_only
         and not input.guest_scope
         and (not input.pivot_only or strategy.id = input.pivot_id)
    """,
    title_expression="strategy.name",
    matched_expression="""
        case
            when cardinality(strategy.symbols) > 0
                then array_to_string(strategy.symbols, ', ')
            else strategy.name
        end
    """,
    haystack_expression="""
        strategy.name || ' '
        || array_to_string(strategy.symbols, ' ') || ' '
        || coalesce(strategy.template, '')
    """,
    symbol_rank_expression="""
        exists (
            select 1
            from unnest(strategy.symbols) as symbol
            where input.symbol_query = lower(symbol)
        )
    """,
    type_rank_expression="3",
    pinned_rank_expression="strategy.pinned",
    activity_expression="strategy.updated_at",
    id_expression="strategy.id",
    payload_expression="""
        jsonb_build_object(
            'id', strategy.id,
            'name', strategy.name,
            'symbols', strategy.symbols,
            'template', strategy.template,
            'updated_at', strategy.updated_at,
            'deleted_at', strategy.deleted_at,
            'pinned', strategy.pinned
        )
    """,
)

_COLLECTION_CTE = _base_cte(
    name="collection",
    source_type="collection",
    source_sql="""
        join public.collections as collection
          on collection.user_id = input.user_id
         and collection.deleted_at is null
         and not input.ideas_only
         and not input.guest_scope
         and (not input.pivot_only or collection.id = input.pivot_id)
    """,
    title_expression="collection.name",
    matched_expression="collection.name",
    haystack_expression="collection.name",
    symbol_rank_expression="false",
    type_rank_expression="2",
    pinned_rank_expression="collection.pinned",
    activity_expression="collection.updated_at",
    id_expression="collection.id",
    payload_expression="""
        jsonb_build_object(
            'id', collection.id,
            'name', collection.name,
            'updated_at', collection.updated_at,
            'deleted_at', collection.deleted_at,
            'pinned', collection.pinned
        )
    """,
)

_RUN_CTE = _base_cte(
    name="run",
    source_type="run",
    source_sql="""
        join public.backtest_runs as run
          on run.user_id = input.user_id
         and run.status = 'completed'
         and not input.ideas_only
         and (
             not input.guest_scope
             or run.conversation_id = input.guest_conversation_id
         )
         and (not input.pivot_only or run.id = input.pivot_id)
    """,
    title_expression=(
        "coalesce(nullif(run.conversation_result_card->>'title', ''), 'Backtest run')"
    ),
    matched_expression=(
        "coalesce(nullif(run.conversation_result_card->>'title', ''), 'Backtest run')"
    ),
    haystack_expression="""
        coalesce(run.conversation_result_card->>'title', '') || ' '
        || coalesce(
            (
                select string_agg(symbol, ' ')
                from jsonb_array_elements_text(
                    coalesce(
                        run.conversation_result_card->'symbols',
                        '[]'::jsonb
                    )
                ) as symbol
            ),
            ''
        ) || ' '
        || coalesce(run.conversation_result_card->>'strategy_label', '') || ' '
        || coalesce(run.benchmark_symbol, '')
    """,
    symbol_rank_expression="""
        exists (
            select 1
            from jsonb_array_elements_text(
                coalesce(
                    run.conversation_result_card->'symbols',
                    '[]'::jsonb
                )
            ) as symbol
            where input.symbol_query = lower(symbol)
        )
    """,
    type_rank_expression="""
        case
            when run.conversation_result_card->>'artifact_type' = 'backtest'
              or run.conversation_result_card ? 'evidence_artifact_id'
                then 5
            else 1
        end
    """,
    pinned_rank_expression="false",
    activity_expression="run.created_at",
    id_expression="run.id",
    payload_expression="""
        jsonb_build_object(
            'id', run.id,
            'conversation_id', run.conversation_id,
            'conversation_result_card', run.conversation_result_card,
            'created_at', run.created_at,
            'status', run.status,
            'asset_class', run.asset_class,
            'benchmark_symbol', run.benchmark_symbol
        )
    """,
)

_IDEA_CTE = _base_cte(
    name="idea",
    source_type="idea",
    source_sql="""
        join public.ideas as idea
          on idea.user_id = input.user_id
         and (
             not input.guest_scope
             or idea.source_conversation_id = input.guest_conversation_id
         )
         and (not input.pivot_only or idea.id = input.pivot_id)
        left join lateral (
            select decision.decision_state
            from public.decision_notes as decision
            where decision.user_id = input.user_id
              and decision.idea_id = idea.id
            order by decision.updated_at desc, decision.id desc
            limit 1
        ) as latest_decision on true
        where (
            input.decision_state is null
            or latest_decision.decision_state = input.decision_state
        )
          and (
              not input.ledger_browse
              or latest_decision.decision_state is not null
          )
    """,
    title_expression="idea.title",
    matched_expression="coalesce(nullif(idea.summary, ''), idea.title)",
    haystack_expression="idea.title || ' ' || coalesce(idea.summary, '')",
    symbol_rank_expression="false",
    type_rank_expression="5",
    pinned_rank_expression="false",
    activity_expression="idea.updated_at",
    id_expression="idea.id",
    payload_expression="""
        jsonb_build_object(
            'id', idea.id,
            'title', idea.title,
            'summary', idea.summary,
            'lifecycle', idea.lifecycle,
            'active_version_id', idea.active_version_id,
            'source_conversation_id', idea.source_conversation_id,
            'updated_at', idea.updated_at,
            'decision_state', latest_decision.decision_state
        )
    """,
    allow_empty_query=True,
)

_EVIDENCE_CTE = _base_cte(
    name="evidence",
    source_type="evidence",
    source_sql="""
        join public.evidence_artifacts as evidence
          on evidence.user_id = input.user_id
         and not input.ideas_only
         and (
             not input.guest_scope
             or evidence.source_conversation_id = input.guest_conversation_id
         )
         and (not input.pivot_only or evidence.id = input.pivot_id)
    """,
    title_expression="evidence.title",
    matched_expression="coalesce(nullif(evidence.digest, ''), evidence.title)",
    haystack_expression="""
        evidence.title || ' ' || coalesce(evidence.digest, '') || ' '
        || coalesce(
            (
                select string_agg(symbol, ' ')
                from jsonb_array_elements_text(
                    coalesce(
                        evidence.payload#>'{result_card,symbols}',
                        '[]'::jsonb
                    )
                ) as symbol
            ),
            ''
        )
    """,
    symbol_rank_expression="""
        exists (
            select 1
            from jsonb_array_elements_text(
                coalesce(
                    evidence.payload#>'{provenance,symbols}',
                    evidence.payload#>'{result_card,symbols}',
                    '[]'::jsonb
                )
            ) as symbol
            where input.symbol_query = lower(symbol)
        )
    """,
    type_rank_expression="5",
    pinned_rank_expression="false",
    activity_expression="evidence.updated_at",
    id_expression="evidence.id",
    payload_expression="""
        jsonb_build_object(
            'id', evidence.id,
            'title', evidence.title,
            'digest', evidence.digest,
            'lifecycle', evidence.lifecycle,
            'artifact_type', evidence.artifact_type,
            'payload', evidence.payload,
            'source_run_id', evidence.source_run_id,
            'source_conversation_id', evidence.source_conversation_id,
            'updated_at', evidence.updated_at
        )
    """,
)

_DECISION_CTE = _base_cte(
    name="decision",
    source_type="decision",
    source_sql="""
        join public.decision_notes as decision
          on decision.user_id = input.user_id
         and not input.ideas_only
         and (
             not input.guest_scope
             or decision.source_conversation_id = input.guest_conversation_id
         )
         and (not input.pivot_only or decision.id = input.pivot_id)
        left join public.evidence_artifacts as decision_evidence
          on decision_evidence.id = decision.evidence_artifact_id
         and decision_evidence.user_id = input.user_id
    """,
    title_expression="""
        coalesce(
            nullif(decision_evidence.title, ''),
            nullif(decision_evidence.digest, ''),
            decision.id::text
        )
    """,
    matched_expression="""
        concat_ws(
            ' ',
            decision.decision_state,
            decision.note,
            decision_evidence.digest
        )
    """,
    haystack_expression="""
        concat_ws(
            ' ',
            decision.decision_state,
            decision.note,
            decision_evidence.title,
            decision_evidence.digest
        )
    """,
    symbol_rank_expression="false",
    type_rank_expression="5",
    pinned_rank_expression="false",
    activity_expression="decision.updated_at",
    id_expression="decision.id",
    payload_expression="""
        jsonb_build_object(
            'id', decision.id,
            'idea_id', decision.idea_id,
            'decision_state', decision.decision_state,
            'note', decision.note,
            'evidence_artifact_id', decision.evidence_artifact_id,
            'source_conversation_id', decision.source_conversation_id,
            'updated_at', decision.updated_at
        )
    """,
)

_SOURCE_CTES = (
    _CHAT_CTE,
    _STRATEGY_CTE,
    _COLLECTION_CTE,
    _RUN_CTE,
    _IDEA_CTE,
    _EVIDENCE_CTE,
    _DECISION_CTE,
)
_ELIGIBLE_NAMES = (
    "chat_eligible",
    "strategy_eligible",
    "collection_eligible",
    "run_eligible",
    "idea_eligible",
    "evidence_eligible",
    "decision_eligible",
)


def _with_sources(body: sql.Composable) -> sql.Composed:
    ctes: list[sql.Composable] = [_INPUT_CTE, *_SOURCE_CTES]
    return sql.SQL("with {} {}").format(sql.SQL(",").join(ctes), body)


_PIVOT_SQL = _with_sources(
    sql.SQL(
        """
        select
            eligible.source_type,
            eligible.pinned_rank,
            eligible.exact_rank,
            eligible.symbol_rank,
            eligible.type_rank,
            eligible.text_rank
        from (
            {eligible_union}
        ) as eligible
        cross join input
        where eligible.id = input.cursor_id
          and eligible.activity_at = input.cursor_updated_at
        """
    ).format(
        eligible_union=sql.SQL(" union all ").join(
            sql.SQL("select * from {}").format(sql.Identifier(name))
            for name in _ELIGIBLE_NAMES
        )
    )
)


def _candidate_cte(name: str) -> sql.Composed:
    eligible_name = f"{name}_eligible"
    candidate_name = f"{name}_candidates"
    return sql.SQL(
        """
        {candidate_name} as (
            select eligible.*
            from {eligible_name} as eligible
            cross join input
            where (
                not input.has_cursor
                or row(
                    eligible.pinned_rank,
                    eligible.exact_rank,
                    eligible.symbol_rank,
                    eligible.type_rank,
                    eligible.activity_at,
                    eligible.text_rank,
                    eligible.id
                ) < row(
                    input.cursor_pinned_rank,
                    input.cursor_exact_rank,
                    input.cursor_symbol_rank,
                    input.cursor_type_rank,
                    input.cursor_updated_at,
                    input.cursor_text_rank,
                    input.cursor_id
                )
            )
            order by
                eligible.pinned_rank desc,
                eligible.exact_rank desc,
                eligible.symbol_rank desc,
                eligible.type_rank desc,
                eligible.activity_at desc,
                eligible.text_rank desc,
                eligible.id desc
            limit (select source_limit from input)
        )
        """
    ).format(
        candidate_name=sql.Identifier(candidate_name),
        eligible_name=sql.Identifier(eligible_name),
    )


_CANDIDATE_NAMES = tuple(
    f"{name.removesuffix('_eligible')}_candidates" for name in _ELIGIBLE_NAMES
)
_CANDIDATES_SQL = _with_sources(
    sql.SQL(
        """
        , {candidate_ctes}
        select source_type, payload
        from (
            {candidate_union}
        ) as candidates
        order by
            pinned_rank desc,
            exact_rank desc,
            symbol_rank desc,
            type_rank desc,
            activity_at desc,
            text_rank desc,
            id desc
        """
    ).format(
        candidate_ctes=sql.SQL(",").join(
            _candidate_cte(name.removesuffix("_eligible")) for name in _ELIGIBLE_NAMES
        ),
        candidate_union=sql.SQL(" union all ").join(
            sql.SQL("select * from {}").format(sql.Identifier(name))
            for name in _CANDIDATE_NAMES
        ),
    )
)

_DECISION_EVIDENCE_SQL = """
select id, title, digest
from public.evidence_artifacts
where user_id = %(user_id)s::uuid
  and id = any(%(artifact_ids)s::uuid[])
"""

_LEDGER_SQL = sql.SQL(
    """
    with input as (
        select
            %(user_id)s::uuid as user_id,
            %(normalized_query)s::text as normalized_query
    ),
    matching_ideas as (
        select idea.id
        from input
        join public.ideas as idea
          on idea.user_id = input.user_id
        cross join lateral (
            select
                {normalized_haystack} as normalized_haystack
        ) as search_text
        where (
            input.normalized_query = ''
            or (
                strpos(
                    search_text.normalized_haystack,
                    input.normalized_query
                ) > 0
                or not exists (
                    select 1
                    from regexp_split_to_table(
                        input.normalized_query,
                        ' +'
                    ) as query_token
                    where strpos(
                        search_text.normalized_haystack,
                        query_token
                    ) = 0
                )
            )
        )
    ),
    latest_decisions as (
        select distinct on (decision.idea_id)
            decision.idea_id,
            decision.decision_state
        from input
        join public.decision_notes as decision
          on decision.user_id = input.user_id
        join matching_ideas
          on matching_ideas.id = decision.idea_id
        order by
            decision.idea_id,
            decision.updated_at desc,
            decision.id desc
    )
    select decision_state, count(*)::integer as count
    from latest_decisions
    group by decision_state
    """
).format(
    normalized_haystack=_normalized("idea.title || ' ' || coalesce(idea.summary, '')")
)


@dataclass(frozen=True)
class PostgresSearchReader:
    pool: Any

    def search_rows(
        self,
        *,
        user_id: str,
        query: str,
        source_limit: int,
        cursor_updated_at: datetime | None = None,
        cursor_id: str | None = None,
        decision_state: str | None = None,
        include_ledger_groups: bool = False,
        guest_scope: bool = False,
        guest_conversation_id: str | None = None,
    ) -> SearchReadResult:
        if source_limit < 1:
            raise ValueError("Search source limit must be positive.")
        try:
            owner_id = UUID(user_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("Search owner id must be a UUID.") from exc

        has_cursor = cursor_updated_at is not None or cursor_id is not None
        if has_cursor and (cursor_updated_at is None or cursor_id is None):
            raise SearchCursorError("Search cursor is incomplete.")
        if cursor_updated_at is not None and (
            cursor_updated_at.tzinfo is None or cursor_updated_at.utcoffset() is None
        ):
            raise SearchCursorError("Search cursor timestamp must include a timezone.")
        try:
            pivot_id = UUID(cursor_id) if cursor_id is not None else None
        except (TypeError, ValueError) as exc:
            raise SearchCursorError("Search cursor id is invalid.") from exc
        try:
            workspace_id = (
                UUID(guest_conversation_id) if guest_conversation_id is not None else None
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("Guest workspace conversation id is invalid.") from exc

        normalized_query = normalize_search_text(query)
        ideas_only = decision_state is not None or (
            include_ledger_groups and not normalized_query
        )
        params: dict[str, Any] = {
            "user_id": owner_id,
            "normalized_query": normalized_query,
            # PostgreSQL text cannot represent NUL. Normalized matching remains
            # exact, while raw symbol equality must be false for such a query
            # because stored Postgres symbols cannot contain NUL either.
            "symbol_query": None if "\x00" in query else query,
            "source_limit": source_limit,
            "has_cursor": has_cursor,
            "cursor_pinned_rank": 0,
            "cursor_exact_rank": 0,
            "cursor_symbol_rank": 0,
            "cursor_type_rank": 0,
            "cursor_updated_at": cursor_updated_at,
            "cursor_text_rank": 0,
            "cursor_id": pivot_id,
            "decision_state": decision_state,
            "ledger_browse": include_ledger_groups and not normalized_query,
            "ideas_only": ideas_only,
            "guest_scope": guest_scope,
            "guest_conversation_id": workspace_id,
            "pivot_only": False,
            "pivot_id": pivot_id,
        }
        with self.pool.connection(timeout=_SEARCH_ACQUIRE_TIMEOUT_SECONDS) as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                if has_cursor:
                    pivot_params = {
                        **params,
                        "pivot_only": True,
                    }
                    cursor.execute(_PIVOT_SQL, pivot_params)
                    pivots = cursor.fetchall()
                    if len(pivots) != 1:
                        raise SearchCursorError(
                            "Search cursor pivot is missing or ambiguous."
                        )
                    pivot = pivots[0]
                    params.update(
                        cursor_pinned_rank=int(pivot["pinned_rank"]),
                        cursor_exact_rank=int(pivot["exact_rank"]),
                        cursor_symbol_rank=int(pivot["symbol_rank"]),
                        cursor_type_rank=int(pivot["type_rank"]),
                        cursor_text_rank=int(pivot["text_rank"]),
                    )

                cursor.execute(_CANDIDATES_SQL, params)
                candidate_rows = cursor.fetchall()
                grouped = _group_candidates(
                    candidate_rows,
                    source_limit=source_limit,
                )
                _hydrate_decision_evidence(
                    cursor=cursor,
                    owner_id=owner_id,
                    decisions=grouped["decisions"],
                )
                ledger_counts = None
                if include_ledger_groups and not guest_scope:
                    cursor.execute(
                        _LEDGER_SQL,
                        {
                            "user_id": owner_id,
                            "normalized_query": normalized_query,
                        },
                    )
                    ledger_counts = {state: 0 for state in _DECISION_STATES}
                    for row in cursor.fetchall():
                        state = str(row.get("decision_state") or "")
                        if state in ledger_counts:
                            ledger_counts[state] = int(row.get("count") or 0)

        return SearchReadResult(rows=grouped, ledger_counts=ledger_counts)


def _group_candidates(
    candidates: list[dict[str, Any]],
    *,
    source_limit: int,
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {
        group: [] for group in _ROW_GROUP_BY_SOURCE.values()
    }
    for candidate in candidates:
        group = _ROW_GROUP_BY_SOURCE.get(str(candidate.get("source_type")))
        payload = candidate.get("payload")
        if group is None or not isinstance(payload, dict):
            continue
        if len(grouped[group]) < source_limit:
            grouped[group].append(payload)
    return grouped


def _hydrate_decision_evidence(
    *,
    cursor: Any,
    owner_id: UUID,
    decisions: list[dict[str, Any]],
) -> None:
    artifact_ids = list(
        dict.fromkeys(
            str(row.get("evidence_artifact_id"))
            for row in decisions
            if row.get("evidence_artifact_id")
        )
    )
    if not artifact_ids:
        return
    cursor.execute(
        _DECISION_EVIDENCE_SQL,
        {
            "user_id": owner_id,
            "artifact_ids": artifact_ids,
        },
    )
    artifacts = {
        str(row.get("id")): row for row in cursor.fetchall() if row.get("id") is not None
    }
    for decision in decisions:
        artifact = artifacts.get(str(decision.get("evidence_artifact_id"))) or {}
        decision["artifact_title"] = artifact.get("title")
        decision["artifact_digest"] = artifact.get("digest")
