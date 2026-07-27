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
_TOKEN_PREDICATE_MARKER = "/* argus_search_token_predicates */ true"
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


def _token_predicates(
    normalized_haystack: sql.Composable,
    *,
    token_count: int,
) -> sql.Composable:
    if token_count < 1:
        return sql.SQL("true")
    return sql.SQL(" and ").join(
        sql.SQL("{} like {}").format(
            normalized_haystack,
            sql.Placeholder(f"token_{index}_pattern"),
        )
        for index in range(token_count)
    )


def _bind_token_predicates(
    query: sql.Composable,
    *,
    normalized_haystack: sql.Composable,
    token_count: int,
) -> sql.SQL:
    rendered = query.as_string()
    replacement = _token_predicates(
        normalized_haystack,
        token_count=token_count,
    ).as_string()
    return sql.SQL(rendered.replace(_TOKEN_PREDICATE_MARKER, replacement))


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
            %(ideas_only)s::boolean as ideas_only,
            %(guest_scope)s::boolean as guest_scope,
            %(guest_conversation_id)s::uuid as guest_conversation_id
    )
    """
)


@dataclass(frozen=True)
class _LateSource:
    name: str
    source_type: str
    joins: str
    filters: str
    title_expression: str
    matched_expression: str
    haystack_expression: str
    candidate_haystack_expression: str | None
    symbol_rank_expression: str
    type_rank_expression: str
    pinned_rank_expression: str
    activity_expression: str
    id_expression: str
    payload_joins: str
    payload_expression: str


_LATE_CHAT = _LateSource(
    name="chat",
    source_type="chat",
    joins="""
        join public.conversations as chat
          on chat.user_id = input.user_id
         and chat.deleted_at is null
         and not input.ideas_only
         and (
             not input.guest_scope
             or chat.id = input.guest_conversation_id
         )
    """,
    filters="true",
    title_expression="chat.title",
    matched_expression="coalesce(nullif(chat.last_message_preview, ''), chat.title)",
    haystack_expression="chat.title || ' ' || coalesce(chat.last_message_preview, '')",
    candidate_haystack_expression=(
        "chat.title || ' ' || coalesce(chat.last_message_preview, '')"
    ),
    symbol_rank_expression="false",
    type_rank_expression="4",
    pinned_rank_expression="chat.pinned",
    activity_expression="chat.updated_at",
    id_expression="chat.id",
    payload_joins="""
        join public.conversations as chat
          on chat.id = candidate.id
         and chat.user_id = input.user_id
    """,
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

_STRATEGY_INDEX_HAYSTACK = """
    strategy.name || ' '
    || coalesce(strategy.symbols[array_lower(strategy.symbols, 1)], '') || ' '
    || coalesce(strategy.symbols[array_lower(strategy.symbols, 1) + 1], '') || ' '
    || coalesce(strategy.symbols[array_lower(strategy.symbols, 1) + 2], '') || ' '
    || coalesce(strategy.symbols[array_lower(strategy.symbols, 1) + 3], '') || ' '
    || coalesce(strategy.symbols[array_lower(strategy.symbols, 1) + 4], '') || ' '
    || coalesce(strategy.template, '')
"""
_LATE_STRATEGY = _LateSource(
    name="strategy",
    source_type="strategy",
    joins="""
        join public.strategies as strategy
          on strategy.user_id = input.user_id
         and strategy.deleted_at is null
         and not input.ideas_only
         and not input.guest_scope
    """,
    filters="true",
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
    candidate_haystack_expression=_STRATEGY_INDEX_HAYSTACK,
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
    payload_joins="""
        join public.strategies as strategy
          on strategy.id = candidate.id
         and strategy.user_id = input.user_id
    """,
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

_LATE_COLLECTION = _LateSource(
    name="collection",
    source_type="collection",
    joins="""
        join public.collections as collection
          on collection.user_id = input.user_id
         and collection.deleted_at is null
         and not input.ideas_only
         and not input.guest_scope
    """,
    filters="true",
    title_expression="collection.name",
    matched_expression="collection.name",
    haystack_expression="collection.name",
    candidate_haystack_expression="collection.name",
    symbol_rank_expression="false",
    type_rank_expression="2",
    pinned_rank_expression="collection.pinned",
    activity_expression="collection.updated_at",
    id_expression="collection.id",
    payload_joins="""
        join public.collections as collection
          on collection.id = candidate.id
         and collection.user_id = input.user_id
    """,
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


_RUN_INDEX_HAYSTACK = """
    coalesce(run.conversation_result_card->>'title', '') || ' '
    || coalesce(run.conversation_result_card->'symbols', '[]'::jsonb)::text || ' '
    || coalesce(run.conversation_result_card->>'strategy_label', '') || ' '
    || coalesce(run.benchmark_symbol, '')
"""
_LATE_RUN = _LateSource(
    name="run",
    source_type="run",
    joins="""
        join public.backtest_runs as run
          on run.user_id = input.user_id
         and run.status = 'completed'
         and not input.ideas_only
         and (
             not input.guest_scope
             or run.conversation_id = input.guest_conversation_id
         )
    """,
    filters="true",
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
    candidate_haystack_expression=_RUN_INDEX_HAYSTACK,
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
    payload_joins="""
        join public.backtest_runs as run
          on run.id = candidate.id
         and run.user_id = input.user_id
    """,
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

_LATE_IDEA = _LateSource(
    name="idea",
    source_type="idea",
    joins="""
        join public.ideas as idea
          on idea.user_id = input.user_id
         and (
             not input.guest_scope
             or idea.source_conversation_id = input.guest_conversation_id
         )
    """,
    filters="true",
    title_expression="idea.title",
    matched_expression="coalesce(nullif(idea.summary, ''), idea.title)",
    haystack_expression="idea.title || ' ' || coalesce(idea.summary, '')",
    candidate_haystack_expression="idea.title || ' ' || coalesce(idea.summary, '')",
    symbol_rank_expression="false",
    type_rank_expression="5",
    pinned_rank_expression="false",
    activity_expression="idea.updated_at",
    id_expression="idea.id",
    payload_joins="""
        join public.ideas as idea
          on idea.id = candidate.id
         and idea.user_id = input.user_id
    """,
    payload_expression="""
        jsonb_build_object(
            'id', idea.id,
            'title', idea.title,
            'summary', idea.summary,
            'lifecycle', idea.lifecycle,
            'active_version_id', idea.active_version_id,
            'source_conversation_id', idea.source_conversation_id,
            'updated_at', idea.updated_at,
            'decision_state', null
        )
    """,
)

_EVIDENCE_INDEX_HAYSTACK = """
    evidence.title || ' ' || coalesce(evidence.digest, '') || ' '
    || coalesce(
        evidence.payload#>'{result_card,symbols}',
        '[]'::jsonb
    )::text
"""
_LATE_EVIDENCE = _LateSource(
    name="evidence",
    source_type="evidence",
    joins="""
        join public.evidence_artifacts as evidence
          on evidence.user_id = input.user_id
         and not input.ideas_only
         and (
             not input.guest_scope
             or evidence.source_conversation_id = input.guest_conversation_id
         )
    """,
    filters="true",
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
    candidate_haystack_expression=_EVIDENCE_INDEX_HAYSTACK,
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
    payload_joins="""
        join public.evidence_artifacts as evidence
          on evidence.id = candidate.id
         and evidence.user_id = input.user_id
    """,
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

_LATE_DECISION = _LateSource(
    name="decision",
    source_type="decision",
    joins="""
        join public.decision_notes as decision
          on decision.user_id = input.user_id
         and not input.ideas_only
         and (
             not input.guest_scope
             or decision.source_conversation_id = input.guest_conversation_id
         )
        left join public.evidence_artifacts as decision_evidence
          on decision_evidence.id = decision.evidence_artifact_id
         and decision_evidence.user_id = input.user_id
    """,
    filters="true",
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
    candidate_haystack_expression=None,
    symbol_rank_expression="false",
    type_rank_expression="5",
    pinned_rank_expression="false",
    activity_expression="decision.updated_at",
    id_expression="decision.id",
    payload_joins="""
        join public.decision_notes as decision
          on decision.id = candidate.id
         and decision.user_id = input.user_id
    """,
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

_LATE_SOURCES = (
    _LATE_CHAT,
    _LATE_STRATEGY,
    _LATE_COLLECTION,
    _LATE_RUN,
    _LATE_IDEA,
    _LATE_EVIDENCE,
    _LATE_DECISION,
)


def _source_token_predicate(
    source: _LateSource,
    *,
    normalized_tokens: tuple[str, ...],
) -> sql.Composable:
    predicates: list[sql.Composable] = []
    candidate_is_exact = source.candidate_haystack_expression is not None and " ".join(
        source.candidate_haystack_expression.split()
    ) == " ".join(source.haystack_expression.split())
    if source.candidate_haystack_expression is not None:
        normalized_candidate = _normalized(source.candidate_haystack_expression)
        predicates.extend(
            sql.SQL("{} like {}").format(
                normalized_candidate,
                sql.Placeholder(f"token_{index}_pattern"),
            )
            for index, token in enumerate(normalized_tokens)
            if len(token) >= 3
        )
    exact_indexes = (
        tuple(index for index, token in enumerate(normalized_tokens) if len(token) < 3)
        if candidate_is_exact
        else tuple(range(len(normalized_tokens)))
    )
    if exact_indexes:
        normalized_haystack = _normalized(source.haystack_expression)
        predicates.extend(
            sql.SQL("{} like {}").format(
                normalized_haystack,
                sql.Placeholder(f"token_{index}_pattern"),
            )
            for index in exact_indexes
        )
    return sql.SQL(" and ").join(predicates) if predicates else sql.SQL("true")


def _late_source_ctes(
    source: _LateSource,
    *,
    normalized_tokens: tuple[str, ...],
    has_cursor: bool,
) -> tuple[sql.Composed, sql.Composed, sql.Composed, sql.Composed]:
    match_predicate = sql.SQL("(input.normalized_query <> '' and ({}))").format(
        _source_token_predicate(
            source,
            normalized_tokens=normalized_tokens,
        )
    )
    keys_name = sql.Identifier(f"{source.name}_late_keys")
    prefix_name = sql.Identifier(f"{source.name}_late_prefix")
    ranked_name = sql.Identifier(f"{source.name}_late_ranked")
    payload_name = sql.Identifier(f"{source.name}_late_payload")
    keys = sql.SQL(
        """
        {keys_name} as (
            select
                {source_type}::text as source_type,
                {id_expression} as id,
                {activity_expression} as activity_at,
                ({pinned_rank_expression})::integer as pinned_rank,
                (
                    input.normalized_query = {normalized_title}
                )::integer as exact_rank,
                ({symbol_rank_expression})::integer as symbol_rank,
                ({type_rank_expression})::integer as type_rank,
                {normalized_title} as normalized_title,
                {matched_expression} as matched_text
            from input
            {joins}
            where ({filters})
              and ({match_predicate})
        )
        """
    ).format(
        keys_name=keys_name,
        source_type=sql.Literal(source.source_type),
        id_expression=sql.SQL(source.id_expression),
        activity_expression=sql.SQL(source.activity_expression),
        pinned_rank_expression=sql.SQL(source.pinned_rank_expression),
        normalized_title=_normalized(source.title_expression),
        symbol_rank_expression=sql.SQL(source.symbol_rank_expression),
        type_rank_expression=sql.SQL(source.type_rank_expression),
        matched_expression=sql.SQL(source.matched_expression),
        joins=sql.SQL(source.joins),
        filters=sql.SQL(source.filters),
        match_predicate=match_predicate,
    )
    if has_cursor:
        prefix = sql.SQL(
            """
            {prefix_name} as (
                select *
                from {keys_name}
            )
            """
        ).format(prefix_name=prefix_name, keys_name=keys_name)
    else:
        prefix = sql.SQL(
            """
            {prefix_name} as (
                select *
                from {keys_name}
                order by
                    pinned_rank desc,
                    exact_rank desc,
                    symbol_rank desc,
                    type_rank desc,
                    activity_at desc
                fetch first %(source_limit)s rows with ties
            )
            """
        ).format(prefix_name=prefix_name, keys_name=keys_name)
    ranked = sql.SQL(
        """
        {ranked_name} as (
            select *
            from (
                select
                    prefix.*,
                    (
                        case
                            when input.normalized_query <> ''
                             and strpos(
                                 prefix.normalized_title,
                                 input.normalized_query
                             ) > 0
                                then 100
                            else 0
                        end
                        +
                        case
                            when input.normalized_query <> ''
                             and strpos(
                                 {normalized_matched},
                                 input.normalized_query
                             ) > 0
                                then 50
                            else 0
                        end
                    )::integer as text_rank
                from {prefix_name} as prefix
                cross join input
            ) as eligible
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
        ranked_name=ranked_name,
        prefix_name=prefix_name,
        normalized_matched=_normalized("prefix.matched_text"),
    )
    payload = sql.SQL(
        """
        {payload_name} as (
            select
                candidate.source_type,
                candidate.id,
                candidate.activity_at,
                candidate.pinned_rank,
                candidate.exact_rank,
                candidate.symbol_rank,
                candidate.type_rank,
                candidate.text_rank,
                {payload_expression} as payload
            from {ranked_name} as candidate
            cross join input
            {payload_joins}
        )
        """
    ).format(
        payload_name=payload_name,
        payload_expression=sql.SQL(source.payload_expression),
        ranked_name=ranked_name,
        payload_joins=sql.SQL(source.payload_joins),
    )
    return keys, prefix, ranked, payload


def _late_source_sql(
    source: _LateSource,
    *,
    normalized_tokens: tuple[str, ...],
    has_cursor: bool,
) -> sql.Composed:
    ctes: list[sql.Composable] = [
        _INPUT_CTE,
        *_late_source_ctes(
            source,
            normalized_tokens=normalized_tokens,
            has_cursor=has_cursor,
        ),
    ]
    payload_name = sql.Identifier(f"{source.name}_late_payload")
    return sql.SQL(
        """
        with {ctes}
        select source_type, payload
        from {payload_name}
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
        ctes=sql.SQL(",").join(ctes),
        payload_name=payload_name,
    )


def _direct_pivot_branch(
    source: _LateSource,
    *,
    normalized_tokens: tuple[str, ...],
) -> sql.Composed:
    match_predicate = _token_predicates(
        _normalized(source.haystack_expression),
        token_count=len(normalized_tokens),
    )
    return sql.SQL(
        """
        select
            {source_type}::text as source_type,
            ({pinned_rank_expression})::integer as pinned_rank,
            (
                input.normalized_query = {normalized_title}
            )::integer as exact_rank,
            ({symbol_rank_expression})::integer as symbol_rank,
            ({type_rank_expression})::integer as type_rank,
            (
                case
                    when input.normalized_query <> ''
                     and strpos(
                         {normalized_title},
                         input.normalized_query
                     ) > 0
                        then 100
                    else 0
                end
                +
                case
                    when input.normalized_query <> ''
                     and strpos(
                         {normalized_matched},
                         input.normalized_query
                     ) > 0
                        then 50
                    else 0
                end
            )::integer as text_rank
        from input
        {joins}
        where ({filters})
          and {id_expression} = %(cursor_id)s::uuid
          and {activity_expression} = %(cursor_updated_at)s::timestamptz
          and input.normalized_query <> ''
          and ({match_predicate})
        """
    ).format(
        source_type=sql.Literal(source.source_type),
        pinned_rank_expression=sql.SQL(source.pinned_rank_expression),
        normalized_title=_normalized(source.title_expression),
        symbol_rank_expression=sql.SQL(source.symbol_rank_expression),
        type_rank_expression=sql.SQL(source.type_rank_expression),
        normalized_matched=_normalized(source.matched_expression),
        joins=sql.SQL(source.joins),
        filters=sql.SQL(source.filters),
        id_expression=sql.SQL(source.id_expression),
        activity_expression=sql.SQL(source.activity_expression),
        match_predicate=match_predicate,
    )


def _direct_pivot_sql(
    *,
    normalized_tokens: tuple[str, ...],
) -> sql.Composed:
    return sql.SQL("with {input_cte} {branches}").format(
        input_cte=_INPUT_CTE,
        branches=sql.SQL(" union all ").join(
            _direct_pivot_branch(
                source,
                normalized_tokens=normalized_tokens,
            )
            for source in _LATE_SOURCES
        ),
    )


def _idea_browse_from(
    *,
    normalized_tokens: tuple[str, ...],
    pivot_only: bool,
) -> sql.Composed:
    query_predicate: sql.Composable = sql.SQL("true")
    if normalized_tokens:
        query_predicate = _token_predicates(
            _normalized("idea.title || ' ' || coalesce(idea.summary, '')"),
            token_count=len(normalized_tokens),
        )
    pivot_predicate = (
        sql.SQL(
            """
            and idea.id = %(cursor_id)s::uuid
            and idea.updated_at = %(cursor_updated_at)s::timestamptz
            """
        )
        if pivot_only
        else sql.SQL("")
    )
    return sql.SQL(
        """
        from input
        join public.ideas as idea
          on idea.user_id = input.user_id
         and (
             not input.guest_scope
             or idea.source_conversation_id = input.guest_conversation_id
         )
        left join lateral (
            select decision.decision_state
            from public.decision_notes as decision
            where decision.user_id = input.user_id
              and decision.idea_id = idea.id
            order by decision.updated_at desc, decision.id desc
            limit 1
        ) as latest_decision
          on true
        where (
            input.decision_state is null
            or latest_decision.decision_state = input.decision_state
        )
          and (
              not input.ledger_browse
              or latest_decision.decision_state is not null
          )
          and ({query_predicate})
          {pivot_predicate}
        """
    ).format(
        query_predicate=query_predicate,
        pivot_predicate=pivot_predicate,
    )


_IDEA_BROWSE_INPUT_CTE = sql.SQL(
    """
    input as (
        select
            %(user_id)s::uuid as user_id,
            %(normalized_query)s::text as normalized_query,
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
            %(guest_scope)s::boolean as guest_scope,
            %(guest_conversation_id)s::uuid as guest_conversation_id
    )
    """
)


def _idea_browse_pivot_sql(
    *,
    normalized_tokens: tuple[str, ...],
) -> sql.Composed:
    normalized_title = _normalized("idea.title")
    normalized_matched = _normalized("coalesce(nullif(idea.summary, ''), idea.title)")
    return sql.SQL(
        """
        with {input_cte}
        select
            'idea'::text as source_type,
            0::integer as pinned_rank,
            (
                input.normalized_query = {normalized_title}
            )::integer as exact_rank,
            0::integer as symbol_rank,
            5::integer as type_rank,
            (
                case
                    when input.normalized_query <> ''
                     and strpos(
                         {normalized_title},
                         input.normalized_query
                     ) > 0
                        then 100
                    else 0
                end
                +
                case
                    when input.normalized_query <> ''
                     and strpos(
                         {normalized_matched},
                         input.normalized_query
                     ) > 0
                        then 50
                    else 0
                end
            )::integer as text_rank
        {browse_from}
        """
    ).format(
        input_cte=_IDEA_BROWSE_INPUT_CTE,
        normalized_title=normalized_title,
        normalized_matched=normalized_matched,
        browse_from=_idea_browse_from(
            normalized_tokens=normalized_tokens,
            pivot_only=True,
        ),
    )


def _idea_browse_sql(
    *,
    normalized_tokens: tuple[str, ...],
) -> sql.Composed:
    normalized_title = _normalized("idea.title")
    normalized_matched = _normalized("coalesce(nullif(idea.summary, ''), idea.title)")
    return sql.SQL(
        """
        with {input_cte},
        eligible as (
            select
                idea.id,
                idea.updated_at as activity_at,
                (
                    input.normalized_query = {normalized_title}
                )::integer as exact_rank,
                (
                    case
                        when input.normalized_query <> ''
                         and strpos(
                             {normalized_title},
                             input.normalized_query
                         ) > 0
                            then 100
                        else 0
                    end
                    +
                    case
                        when input.normalized_query <> ''
                         and strpos(
                             {normalized_matched},
                             input.normalized_query
                         ) > 0
                            then 50
                        else 0
                    end
                )::integer as text_rank,
                jsonb_build_object(
                    'id', idea.id,
                    'title', idea.title,
                    'summary', idea.summary,
                    'lifecycle', idea.lifecycle,
                    'active_version_id', idea.active_version_id,
                    'source_conversation_id', idea.source_conversation_id,
                    'updated_at', idea.updated_at,
                    'decision_state', latest_decision.decision_state
                ) as payload
            {browse_from}
        )
        select 'idea'::text as source_type, eligible.payload
        from eligible
        cross join input
        where (
            not input.has_cursor
            or row(
                0,
                eligible.exact_rank,
                0,
                5,
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
            eligible.exact_rank desc,
            eligible.activity_at desc,
            eligible.text_rank desc,
            eligible.id desc
        limit (select source_limit from input)
        """
    ).format(
        input_cte=_IDEA_BROWSE_INPUT_CTE,
        normalized_title=normalized_title,
        normalized_matched=normalized_matched,
        browse_from=_idea_browse_from(
            normalized_tokens=normalized_tokens,
            pivot_only=False,
        ),
    )


_DECISION_EVIDENCE_SQL = """
select id, title, digest
from public.evidence_artifacts
where user_id = %(user_id)s::uuid
  and id = any(%(artifact_ids)s::uuid[])
"""

_IDEA_DECISIONS_SQL = """
select distinct on (idea_id)
    idea_id,
    decision_state
from public.decision_notes
where user_id = %(user_id)s::uuid
  and idea_id = any(%(idea_ids)s::uuid[])
order by idea_id, updated_at desc, id desc
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
            or ({token_predicates})
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
    normalized_haystack=_normalized("idea.title || ' ' || coalesce(idea.summary, '')"),
    token_predicates=sql.SQL(_TOKEN_PREDICATE_MARKER),
)


def _ledger_sql(*, token_count: int) -> sql.SQL:
    return _bind_token_predicates(
        _LEDGER_SQL,
        normalized_haystack=sql.SQL("search_text.normalized_haystack"),
        token_count=token_count,
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
        normalized_tokens = tuple(dict.fromkeys(normalized_query.split()))
        ideas_only = decision_state is not None or (
            include_ledger_groups and not normalized_query
        )
        ordinary_search = decision_state is None and bool(normalized_query)
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
        }
        params.update(
            {
                f"token_{index}_pattern": f"%{token}%"
                for index, token in enumerate(normalized_tokens)
            }
        )
        with self.pool.connection(timeout=_SEARCH_ACQUIRE_TIMEOUT_SECONDS) as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                if has_cursor:
                    if ordinary_search:
                        pivot_query = _direct_pivot_sql(
                            normalized_tokens=normalized_tokens,
                        )
                    else:
                        pivot_query = _idea_browse_pivot_sql(
                            normalized_tokens=normalized_tokens,
                        )
                    cursor.execute(pivot_query, params)
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

                if ordinary_search:
                    candidate_rows = []
                    for source in _LATE_SOURCES:
                        cursor.execute(
                            _late_source_sql(
                                source,
                                normalized_tokens=normalized_tokens,
                                has_cursor=has_cursor,
                            ),
                            params,
                        )
                        candidate_rows.extend(cursor.fetchall())
                else:
                    cursor.execute(
                        _idea_browse_sql(
                            normalized_tokens=normalized_tokens,
                        ),
                        params,
                    )
                    candidate_rows = cursor.fetchall()
                grouped = _group_candidates(
                    candidate_rows,
                    source_limit=source_limit,
                )
                if ordinary_search:
                    _hydrate_idea_decisions(
                        cursor=cursor,
                        owner_id=owner_id,
                        ideas=grouped["ideas"],
                    )
                _hydrate_decision_evidence(
                    cursor=cursor,
                    owner_id=owner_id,
                    decisions=grouped["decisions"],
                )
                ledger_counts = None
                if include_ledger_groups and not guest_scope:
                    cursor.execute(
                        _ledger_sql(token_count=len(normalized_tokens)),
                        {
                            "user_id": owner_id,
                            "normalized_query": normalized_query,
                            **{
                                f"token_{index}_pattern": f"%{token}%"
                                for index, token in enumerate(normalized_tokens)
                            },
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


def _hydrate_idea_decisions(
    *,
    cursor: Any,
    owner_id: UUID,
    ideas: list[dict[str, Any]],
) -> None:
    idea_ids = list(dict.fromkeys(str(row.get("id")) for row in ideas if row.get("id")))
    if not idea_ids:
        return
    cursor.execute(
        _IDEA_DECISIONS_SQL,
        {
            "user_id": owner_id,
            "idea_ids": idea_ids,
        },
    )
    states = {
        str(row.get("idea_id")): row.get("decision_state")
        for row in cursor.fetchall()
        if row.get("idea_id") is not None
    }
    for idea in ideas:
        idea["decision_state"] = states.get(str(idea.get("id")))
