from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg import sql
from psycopg.rows import dict_row

from argus.api.chat.legacy_onboarding_markers import (
    legacy_onboarding_sql_filters,
)
from argus.api.schemas import SearchAssetRollup
from argus.domain.search_sql_text import (
    normalizer_expression,
    symbol_index_expression,
)
from argus.domain.search_text import (
    normalize_search_symbol,
    normalize_search_text,
    search_has_indexable_token,
    search_query_is_indexable,
)

_SEARCH_ACQUIRE_TIMEOUT_SECONDS = 2.0
_CONVERSATION_MATCH_OVERSAMPLE = 10
_MAX_CONVERSATION_MATCHES_PER_SOURCE = 1_010
_DECISION_STATES = ("promising", "watching", "rejected", "revisit_later")
_ROW_GROUP_BY_SOURCE = {
    "conversation": "conversations",
    "chat": "conversations",
    "strategy": "strategies",
    "collection": "collections",
    "run": "runs",
    "idea": "ideas",
    "evidence": "evidence",
    "decision": "decisions",
    "asset_rollup": "asset_rollups",
}
_CONVERSATION_ROW_GROUPS = tuple(
    dict.fromkeys(
        group
        for source, group in _ROW_GROUP_BY_SOURCE.items()
        if source != "asset_rollup"
    )
)


class SearchCursorError(ValueError):
    """Raised when a scoped Search cursor pivot cannot be resolved exactly."""


@dataclass(frozen=True)
class SearchReadResult:
    rows: dict[str, list[dict[str, Any]]]
    ledger_counts: dict[str, int] | None = None
    asset_rollup: SearchAssetRollup | None = None


def _normalized(expression: str) -> sql.Composed:
    return normalizer_expression(sql.SQL(expression))


def _conversation_match_limit(source_limit: int) -> int:
    return min(
        source_limit * _CONVERSATION_MATCH_OVERSAMPLE,
        _MAX_CONVERSATION_MATCHES_PER_SOURCE,
    )


def _symbol_prefix_end(prefix: str | None) -> str | None:
    """Return the exclusive C-collation upper bound for one text prefix."""
    if not prefix:
        return None
    codepoints = [ord(character) for character in prefix]
    for index in range(len(codepoints) - 1, -1, -1):
        codepoint = codepoints[index]
        if codepoint >= 0x10FFFF:
            continue
        successor = codepoint + 1
        if 0xD800 <= successor <= 0xDFFF:
            successor = 0xE000
        return "".join(
            chr(value) for value in (*codepoints[:index], successor)
        )
    return None


def _all_token_recheck(
    normalized_haystack: sql.Composable,
) -> sql.Composed:
    return sql.SQL(
        """
        not exists (
            select 1
            from unnest(%(token_patterns)s::text[]) as required(pattern)
            where not coalesce(
                {normalized_haystack} like required.pattern,
                false
            )
        )
        """
    ).format(normalized_haystack=normalized_haystack)


def _token_match_predicate(
    *,
    normalized_haystack: sql.Composable,
    normalized_index_haystack: sql.Composable | None,
    has_anchor: bool,
) -> sql.Composed:
    predicates: list[sql.Composable] = []
    if has_anchor and normalized_index_haystack is not None:
        predicates.append(
            sql.SQL("{} like %(anchor_pattern)s").format(
                normalized_index_haystack,
            )
        )
    predicates.append(_all_token_recheck(normalized_haystack))
    return sql.SQL(" and ").join(predicates)


_INPUT_CTE = sql.SQL(
    """
    input as (
        select
            %(user_id)s::uuid as user_id,
            %(normalized_query)s::text as normalized_query,
            %(symbol_query)s::text as symbol_query,
            %(symbol_prefix_end)s::text as symbol_prefix_end,
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
    conversation_expression: str
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
    conversation_expression="chat.id",
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
    conversation_expression="strategy.id",
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
    conversation_expression="collection.id",
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
    conversation_expression="run.conversation_id",
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
    conversation_expression="idea.source_conversation_id",
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
_DECISION_INDEX_HAYSTACK = """
    decision.decision_state || ' ' || coalesce(decision.note, '')
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
    conversation_expression="evidence.source_conversation_id",
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
    conversation_expression="decision.source_conversation_id",
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
    has_anchor: bool,
) -> sql.Composable:
    normalized_index_haystack = (
        _normalized(source.candidate_haystack_expression)
        if source.candidate_haystack_expression is not None
        else None
    )
    return _token_match_predicate(
        normalized_haystack=sql.SQL("search_text.normalized_haystack"),
        normalized_index_haystack=normalized_index_haystack,
        has_anchor=has_anchor,
    )


def _late_source_ctes(
    source: _LateSource,
    *,
    has_anchor: bool,
    has_cursor: bool,
) -> tuple[sql.Composed, sql.Composed, sql.Composed, sql.Composed]:
    match_predicate = sql.SQL("(input.normalized_query = '' or ({}))").format(
        _source_token_predicate(
            source,
            has_anchor=has_anchor,
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
                {conversation_expression} as conversation_id,
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
            cross join lateral (
                select {normalized_haystack} as normalized_haystack
            ) as search_text
            where ({filters})
              and ({match_predicate})
        )
        """
    ).format(
        keys_name=keys_name,
        source_type=sql.Literal(source.source_type),
        id_expression=sql.SQL(source.id_expression),
        conversation_expression=sql.SQL(source.conversation_expression),
        activity_expression=sql.SQL(source.activity_expression),
        pinned_rank_expression=sql.SQL(source.pinned_rank_expression),
        normalized_title=_normalized(source.title_expression),
        symbol_rank_expression=sql.SQL(source.symbol_rank_expression),
        type_rank_expression=sql.SQL(source.type_rank_expression),
        matched_expression=sql.SQL(source.matched_expression),
        joins=sql.SQL(source.joins),
        normalized_haystack=_normalized(source.haystack_expression),
        filters=sql.SQL(source.filters),
        match_predicate=match_predicate,
    )
    if has_cursor:
        prefix = sql.SQL(
            """
            {prefix_name} as (
                select *
                from (
                    select
                        grouped_keys.*,
                        row_number() over (
                            partition by grouped_keys.conversation_id
                            order by
                                pinned_rank desc,
                                exact_rank desc,
                                symbol_rank desc,
                                type_rank desc,
                                activity_at desc,
                                id desc
                        ) as conversation_rank
                    from {keys_name} as grouped_keys
                    where grouped_keys.conversation_id is not null
                ) as grouped_conversations
                where conversation_rank = 1
            )
            """
        ).format(prefix_name=prefix_name, keys_name=keys_name)
    else:
        prefix = sql.SQL(
            """
            {prefix_name} as (
                select *
                from (
                    select
                        grouped_keys.*,
                        row_number() over (
                            partition by grouped_keys.conversation_id
                            order by
                                pinned_rank desc,
                                exact_rank desc,
                                symbol_rank desc,
                                type_rank desc,
                                activity_at desc,
                                id desc
                        ) as conversation_rank
                    from {keys_name} as grouped_keys
                    where grouped_keys.conversation_id is not null
                ) as grouped_conversations
                where conversation_rank = 1
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
    has_anchor: bool,
    has_cursor: bool,
) -> sql.Composed:
    ctes: list[sql.Composable] = [
        _INPUT_CTE,
        *_late_source_ctes(
            source,
            has_anchor=has_anchor,
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
) -> sql.Composed:
    match_predicate = _all_token_recheck(
        sql.SQL("search_text.normalized_haystack"),
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
        cross join lateral (
            select {normalized_haystack} as normalized_haystack
        ) as search_text
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
        normalized_haystack=_normalized(source.haystack_expression),
        filters=sql.SQL(source.filters),
        id_expression=sql.SQL(source.id_expression),
        activity_expression=sql.SQL(source.activity_expression),
        match_predicate=match_predicate,
    )


def _direct_pivot_sql() -> sql.Composed:
    return sql.SQL("with {input_cte} {branches}").format(
        input_cte=_INPUT_CTE,
        branches=sql.SQL(" union all ").join(
            _direct_pivot_branch(source) for source in _LATE_SOURCES
        ),
    )


def _idea_browse_from(
    *,
    has_anchor: bool,
    pivot_only: bool,
) -> sql.Composed:
    normalized_haystack = _normalized("idea.title || ' ' || coalesce(idea.summary, '')")
    query_predicate = _token_match_predicate(
        normalized_haystack=sql.SQL("search_text.normalized_haystack"),
        normalized_index_haystack=normalized_haystack,
        has_anchor=has_anchor,
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
        cross join lateral (
            select {normalized_haystack} as normalized_haystack
        ) as search_text
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
        normalized_haystack=normalized_haystack,
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


def _idea_browse_pivot_sql() -> sql.Composed:
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
            has_anchor=False,
            pivot_only=True,
        ),
    )


def _idea_browse_sql(
    *,
    has_anchor: bool,
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
            has_anchor=has_anchor,
            pivot_only=False,
        ),
    )


_DECISION_EVIDENCE_SQL = """
select id, title, digest, payload
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


_CONVERSATION_INPUT_CTE = sql.SQL(
    """
    input as (
        select
            %(user_id)s::uuid as user_id,
            %(normalized_query)s::text as normalized_query,
            %(symbol_query)s::text as symbol_query,
            %(symbol_prefix_end)s::text as symbol_prefix_end,
            %(source_limit)s::integer as source_limit,
            %(match_limit)s::integer as match_limit,
            %(asset_symbol_limit)s::integer as asset_symbol_limit,
            %(text_search_enabled)s::boolean as text_search_enabled,
            %(has_cursor)s::boolean as has_cursor,
            %(cursor_pinned_rank)s::integer as cursor_pinned_rank,
            %(cursor_exact_rank)s::integer as cursor_exact_rank,
            %(cursor_symbol_rank)s::integer as cursor_symbol_rank,
            %(cursor_layer_rank)s::integer as cursor_layer_rank,
            %(cursor_updated_at)s::timestamptz as cursor_updated_at,
            %(cursor_text_rank)s::integer as cursor_text_rank,
            %(cursor_id)s::uuid as cursor_id,
            %(decision_state)s::text as decision_state,
            %(guest_scope)s::boolean as guest_scope,
            %(guest_conversation_id)s::uuid as guest_conversation_id
    )
    """
)


_CONVERSATION_LEDGER_INPUT_CTE = sql.SQL(
    """
    input as (
        select
            %(user_id)s::uuid as user_id,
            %(normalized_query)s::text as normalized_query,
            %(text_search_enabled)s::boolean as text_search_enabled
    )
    """
)


_CONVERSATION_DECISION_FILTER = sql.SQL(
    """
    and (
        input.decision_state is null
        or exists (
            select 1
            from public.decision_notes as source_decision
            where source_decision.user_id = input.user_id
              and source_decision.source_conversation_id = conversation.id
              and source_decision.decision_state = input.decision_state
        )
    )
    """
)


def _conversation_match_ctes(
    *,
    has_anchor: bool,
    has_cursor: bool = False,
) -> sql.Composed:
    chat_title_haystack = _normalized("conversation.title")
    chat_preview_haystack = _normalized("coalesce(conversation.last_message_preview, '')")
    chat_index_haystack = _normalized(
        "conversation.title || ' ' "
        "|| coalesce(conversation.last_message_preview, '')"
    )
    message_haystack = _normalized("message.content")
    run_haystack = _normalized(
        "coalesce(run.conversation_result_card->>'title', '') || ' ' "
        "|| coalesce(array_to_string(run.symbols, ' '), '') || ' ' "
        "|| coalesce(run.config_snapshot->>'template', '') || ' ' "
        "|| coalesce(run.conversation_result_card->>'strategy_label', '')"
    )
    idea_haystack = _normalized("idea.title || ' ' || coalesce(idea.summary, '')")
    evidence_haystack = _normalized(
        "evidence.title || ' ' || coalesce(evidence.digest, '')"
    )
    decision_haystack = _normalized(
        f"""
        {_DECISION_INDEX_HAYSTACK} || ' '
        || evidence.title || ' ' || coalesce(evidence.digest, '')
        """
    )
    decision_all_tokens = _all_token_recheck(decision_haystack)
    conversation_exact_rank = sql.SQL(
        """
        (
            input.normalized_query <> ''
            and input.normalized_query = {normalized_title}
        )::integer
        """
    ).format(normalized_title=_normalized("conversation.title"))
    conversation_symbol_rank = sql.SQL(
        """
        exists (
            select 1
            from public.backtest_runs as symbol_run
            cross join unnest(symbol_run.symbols) as symbol
            where symbol_run.user_id = input.user_id
              and symbol_run.conversation_id = conversation.id
              and symbol_run.status = 'completed'
              and input.symbol_query = lower(symbol)
        )::integer
        """
    )

    def conversation_text_rank(matched_text_sql: sql.Composable) -> sql.Composed:
        return sql.SQL(
            """
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
            )::integer
            """
        ).format(
            normalized_title=_normalized("conversation.title"),
            normalized_matched=normalizer_expression(matched_text_sql),
        )

    def token_predicate(
        haystack: sql.Composable,
        index_haystack: sql.Composable,
    ) -> sql.Composed:
        return _token_match_predicate(
            normalized_haystack=haystack,
            normalized_index_haystack=index_haystack,
            has_anchor=has_anchor,
        )

    def bounded_source_window(
        *,
        source_sql: sql.Composable,
        activity_sql: sql.Composable,
        layer_rank_sql: sql.Composable,
        matched_text_sql: sql.Composable,
        source_tiebreak_sql: sql.Composable,
        cursor_relative: bool,
    ) -> sql.Composed:
        text_rank_sql = conversation_text_rank(matched_text_sql)
        cursor_predicate = (
            sql.SQL(
                """
                and input.has_cursor
                and (
                    conversation.id = input.cursor_id
                    or row(
                        conversation.pinned::integer,
                        {exact_rank_sql},
                        {symbol_rank_sql},
                        {layer_rank_sql},
                        {activity_sql},
                        {text_rank_sql},
                        conversation.id
                    ) <= row(
                        input.cursor_pinned_rank,
                        input.cursor_exact_rank,
                        input.cursor_symbol_rank,
                        input.cursor_layer_rank,
                        input.cursor_updated_at,
                        input.cursor_text_rank,
                        input.cursor_id
                    )
                )
                """
            ).format(
                activity_sql=activity_sql,
                exact_rank_sql=conversation_exact_rank,
                symbol_rank_sql=conversation_symbol_rank,
                layer_rank_sql=layer_rank_sql,
                text_rank_sql=text_rank_sql,
            )
            if cursor_relative
            else sql.SQL("")
        )
        window_order_sql = (
            sql.SQL(
                """
                conversation.pinned::integer desc,
                {exact_rank_sql} desc,
                {symbol_rank_sql} desc,
                {layer_rank_sql} desc,
                {activity_sql} desc,
                {text_rank_sql} desc,
                conversation.id desc,
                {source_tiebreak_sql}
                """
            ).format(
                exact_rank_sql=conversation_exact_rank,
                symbol_rank_sql=conversation_symbol_rank,
                layer_rank_sql=layer_rank_sql,
                activity_sql=activity_sql,
                text_rank_sql=text_rank_sql,
                source_tiebreak_sql=source_tiebreak_sql,
            )
            if cursor_relative
            else sql.SQL("{activity_sql} desc, {source_tiebreak_sql}").format(
                activity_sql=activity_sql,
                source_tiebreak_sql=source_tiebreak_sql,
            )
        )
        return sql.SQL(
            """
            (
            {source_sql}
            {cursor_predicate}
            order by {window_order_sql}
            limit (select match_limit from input)
            )
            """
        ).format(
            source_sql=source_sql,
            cursor_predicate=cursor_predicate,
            window_order_sql=window_order_sql,
        )

    chat_title_predicate = token_predicate(
        chat_title_haystack,
        chat_index_haystack,
    )
    chat_preview_predicate = token_predicate(
        chat_preview_haystack,
        chat_index_haystack,
    )
    message_predicate = token_predicate(message_haystack, message_haystack)
    run_predicate = token_predicate(
        run_haystack,
        _normalized(_RUN_INDEX_HAYSTACK),
    )
    idea_predicate = token_predicate(idea_haystack, idea_haystack)
    evidence_predicate = token_predicate(
        evidence_haystack,
        _normalized(_EVIDENCE_INDEX_HAYSTACK),
    )
    conversation_matched_text = sql.SQL(
        """
        case
            when input.normalized_query = ''
              or ({chat_title_predicate})
                then conversation.title
            when ({chat_preview_predicate})
                then conversation.last_message_preview
        end
        """
    ).format(
        chat_title_predicate=chat_title_predicate,
        chat_preview_predicate=chat_preview_predicate,
    )
    run_matched_text = sql.SQL(
        """
        concat_ws(
            ' ',
            nullif(run.conversation_result_card->>'title', ''),
            nullif(array_to_string(run.symbols, ' '), ''),
            nullif(run.config_snapshot->>'template', ''),
            nullif(run.conversation_result_card->>'strategy_label', '')
        )
        """
    )
    idea_matched_text = sql.SQL(
        "concat_ws(' ', idea.title, nullif(idea.summary, ''))"
    )
    evidence_matched_text = sql.SQL(
        "concat_ws(' ', evidence.title, nullif(evidence.digest, ''))"
    )
    decision_matched_text = sql.SQL(
        """
        concat_ws(
            ' ',
            nullif(decision.note, ''),
            decision.decision_state,
            nullif(evidence.title, ''),
            nullif(evidence.digest, '')
        )
        """
    )

    conversation_source = sql.SQL(
        """
        select
            conversation.id as conversation_id,
            conversation.id as source_id,
            conversation.updated_at as candidate_at,
            {matched_text_sql} as matched_text,
            1::integer as layer_rank,
            'conversation'::text as layer
        from input
        join public.conversations as conversation
          on conversation.user_id = input.user_id
         and conversation.deleted_at is null
         and (
             not input.guest_scope
             or conversation.id = input.guest_conversation_id
         )
         {decision_filter}
        where (
            input.normalized_query = ''
            or (
                input.text_search_enabled
                and (
                    ({chat_title_predicate})
                    or ({chat_preview_predicate})
                )
            )
        )
        """
    ).format(
        matched_text_sql=conversation_matched_text,
        chat_title_predicate=chat_title_predicate,
        chat_preview_predicate=chat_preview_predicate,
        decision_filter=_CONVERSATION_DECISION_FILTER,
    )
    message_source = sql.SQL(
        """
        select
            conversation.id as conversation_id,
            message.id as source_id,
            message.created_at as candidate_at,
            message.content as matched_text,
            2::integer as layer_rank,
            'message'::text as layer
        from input
        join public.messages as message
          on message.user_id = input.user_id
         and message.role = 'user'
         and message.content <> %(legacy_skip_message)s
         and message.content not like %(legacy_goal_pattern)s escape '\\'
        join public.conversations as conversation
          on conversation.id = message.conversation_id
         and conversation.user_id = input.user_id
         and conversation.deleted_at is null
         and (
             not input.guest_scope
             or conversation.id = input.guest_conversation_id
         )
         {decision_filter}
        where input.text_search_enabled
          and input.normalized_query <> ''
          and ({message_predicate})
        """
    ).format(
        message_predicate=message_predicate,
        decision_filter=_CONVERSATION_DECISION_FILTER,
    )
    run_source = sql.SQL(
        """
        select
            conversation.id as conversation_id,
            run.id as source_id,
            coalesce(run.updated_at, run.created_at) as candidate_at,
            {matched_text_sql} as matched_text,
            3::integer as layer_rank,
            'run'::text as layer
        from input
        join public.backtest_runs as run
          on run.user_id = input.user_id
         and run.status = 'completed'
        join public.conversations as conversation
          on conversation.id = run.conversation_id
         and conversation.user_id = input.user_id
         and conversation.deleted_at is null
         and (
             not input.guest_scope
             or conversation.id = input.guest_conversation_id
         )
         {decision_filter}
        where input.text_search_enabled
          and input.normalized_query <> ''
          and ({run_predicate})
        """
    ).format(
        matched_text_sql=run_matched_text,
        run_predicate=run_predicate,
        decision_filter=_CONVERSATION_DECISION_FILTER,
    )
    idea_source = sql.SQL(
        """
        select
            conversation.id as conversation_id,
            idea.id as source_id,
            idea.updated_at as candidate_at,
            {matched_text_sql} as matched_text,
            4::integer as layer_rank,
            'idea'::text as layer
        from input
        join public.ideas as idea
          on idea.user_id = input.user_id
        join public.conversations as conversation
          on conversation.id = idea.source_conversation_id
         and conversation.user_id = input.user_id
         and conversation.deleted_at is null
         and (
             not input.guest_scope
             or conversation.id = input.guest_conversation_id
         )
         {decision_filter}
        where input.text_search_enabled
          and input.normalized_query <> ''
          and ({idea_predicate})
        """
    ).format(
        matched_text_sql=idea_matched_text,
        idea_predicate=idea_predicate,
        decision_filter=_CONVERSATION_DECISION_FILTER,
    )
    evidence_source = sql.SQL(
        """
        select
            conversation.id as conversation_id,
            evidence.id as source_id,
            evidence.updated_at as candidate_at,
            {matched_text_sql} as matched_text,
            5::integer as layer_rank,
            'evidence'::text as layer
        from input
        join public.evidence_artifacts as evidence
          on evidence.user_id = input.user_id
        join public.conversations as conversation
          on conversation.id = evidence.source_conversation_id
         and conversation.user_id = input.user_id
         and conversation.deleted_at is null
         and (
             not input.guest_scope
             or conversation.id = input.guest_conversation_id
         )
         {decision_filter}
        where input.text_search_enabled
          and input.normalized_query <> ''
          and ({evidence_predicate})
        """
    ).format(
        matched_text_sql=evidence_matched_text,
        evidence_predicate=evidence_predicate,
        decision_filter=_CONVERSATION_DECISION_FILTER,
    )
    source_specs: tuple[
        tuple[
            sql.Composable,
            sql.Composable,
            sql.Composable,
            sql.Composable,
            sql.Composable,
        ],
        ...,
    ] = (
        (
            conversation_source,
            sql.SQL("conversation.updated_at"),
            sql.SQL("1::integer"),
            conversation_matched_text,
            sql.SQL("conversation.id desc"),
        ),
        (
            message_source,
            sql.SQL("message.created_at"),
            sql.SQL("2::integer"),
            sql.SQL("message.content"),
            sql.SQL("message.id desc"),
        ),
        (
            run_source,
            sql.SQL("coalesce(run.updated_at, run.created_at)"),
            sql.SQL("3::integer"),
            run_matched_text,
            sql.SQL("run.id desc"),
        ),
        (
            idea_source,
            sql.SQL("idea.updated_at"),
            sql.SQL("4::integer"),
            idea_matched_text,
            sql.SQL("idea.id desc"),
        ),
        (
            evidence_source,
            sql.SQL("evidence.updated_at"),
            sql.SQL("5::integer"),
            evidence_matched_text,
            sql.SQL("evidence.id desc"),
        ),
    )

    def decision_source(indexed_joins: sql.Composable) -> sql.Composed:
        return sql.SQL(
            """
            select
                conversation.id as conversation_id,
                decision.id as source_id,
                decision.updated_at as candidate_at,
                {matched_text_sql} as matched_text,
                6::integer as layer_rank,
                'decision'::text as layer
            from input
            {indexed_joins}
            join public.conversations as conversation
              on conversation.id = decision.source_conversation_id
             and conversation.user_id = input.user_id
             and conversation.deleted_at is null
             and (
                 not input.guest_scope
                 or conversation.id = input.guest_conversation_id
             )
             {decision_filter}
            where input.text_search_enabled
              and input.normalized_query <> ''
              and ({all_tokens})
            """
        ).format(
            indexed_joins=indexed_joins,
            matched_text_sql=decision_matched_text,
            decision_filter=_CONVERSATION_DECISION_FILTER,
            all_tokens=decision_all_tokens,
        )

    if has_anchor:
        decision_sources = (
            decision_source(
                sql.SQL(
                    """
                    join public.decision_notes as decision
                      on decision.user_id = input.user_id
                     and {decision_index} like %(anchor_pattern)s
                    join public.evidence_artifacts as evidence
                      on evidence.id = decision.evidence_artifact_id
                     and evidence.user_id = input.user_id
                     and evidence.source_conversation_id =
                         decision.source_conversation_id
                    """
                ).format(
                    decision_index=_normalized(_DECISION_INDEX_HAYSTACK),
                )
            ),
            decision_source(
                sql.SQL(
                    """
                    join public.evidence_artifacts as evidence
                      on evidence.user_id = input.user_id
                     and {evidence_index} like %(anchor_pattern)s
                    join public.decision_notes as decision
                      on decision.evidence_artifact_id = evidence.id
                     and decision.user_id = input.user_id
                     and decision.source_conversation_id =
                         evidence.source_conversation_id
                    """
                ).format(
                    evidence_index=_normalized(_EVIDENCE_INDEX_HAYSTACK),
                )
            ),
        )
    else:
        decision_sources = (
            decision_source(
                sql.SQL(
                    """
                    join public.decision_notes as decision
                      on decision.user_id = input.user_id
                    join public.evidence_artifacts as evidence
                      on evidence.id = decision.evidence_artifact_id
                     and evidence.user_id = input.user_id
                     and evidence.source_conversation_id =
                         decision.source_conversation_id
                    """
                )
            ),
        )

    def decision_window_ctes(*, cursor_relative: bool) -> sql.Composed:
        candidate_name = sql.SQL(
            "cursor_decision_candidates" if cursor_relative else "decision_candidates"
        )
        match_name = sql.SQL(
            "cursor_decision_matches" if cursor_relative else "decision_matches"
        )
        windows = tuple(
            bounded_source_window(
                source_sql=source,
                activity_sql=sql.SQL("decision.updated_at"),
                layer_rank_sql=sql.SQL("6::integer"),
                matched_text_sql=decision_matched_text,
                source_tiebreak_sql=sql.SQL("decision.id desc"),
                cursor_relative=cursor_relative,
            )
            for source in decision_sources
        )
        if not has_anchor:
            return sql.SQL("{match_name} as ({window})").format(
                match_name=match_name,
                window=windows[0],
            )
        deduplicated_scope = (
            sql.SQL(
                """
                cross join input
                join public.conversations as conversation
                  on conversation.id = deduplicated.conversation_id
                 and conversation.user_id = input.user_id
                 and conversation.deleted_at is null
                """
            )
            if cursor_relative
            else sql.SQL("")
        )
        deduplicated_order = (
            sql.SQL(
                """
                conversation.pinned::integer desc,
                {exact_rank_sql} desc,
                {symbol_rank_sql} desc,
                6::integer desc,
                deduplicated.candidate_at desc,
                {text_rank_sql} desc,
                conversation.id desc,
                deduplicated.source_id desc
                """
            ).format(
                exact_rank_sql=conversation_exact_rank,
                symbol_rank_sql=conversation_symbol_rank,
                text_rank_sql=conversation_text_rank(
                    sql.SQL("deduplicated.matched_text")
                ),
            )
            if cursor_relative
            else sql.SQL(
                """
                deduplicated.candidate_at desc,
                deduplicated.source_id desc
                """
            )
        )
        return sql.SQL(
            """
            {candidate_name} as (
                {candidate_windows}
            ),
            {match_name} as (
                select
                    deduplicated.conversation_id,
                    deduplicated.source_id,
                    deduplicated.candidate_at,
                    deduplicated.matched_text,
                    deduplicated.layer_rank,
                    deduplicated.layer
                from (
                    select distinct on (candidate.source_id)
                        candidate.*
                    from {candidate_name} as candidate
                    order by
                        candidate.source_id,
                        candidate.candidate_at desc
                ) as deduplicated
                {deduplicated_scope}
                order by {deduplicated_order}
                limit (select match_limit from input)
            )
            """
        ).format(
            candidate_name=candidate_name,
            candidate_windows=sql.SQL("\nunion all\n").join(windows),
            deduplicated_scope=deduplicated_scope,
            deduplicated_order=deduplicated_order,
            match_name=match_name,
        )

    def source_windows(*, cursor_relative: bool) -> sql.Composed:
        decision_match_name = sql.SQL(
            "cursor_decision_matches" if cursor_relative else "decision_matches"
        )
        windows = [
            bounded_source_window(
                source_sql=source,
                activity_sql=activity,
                layer_rank_sql=layer_rank,
                matched_text_sql=matched_text,
                source_tiebreak_sql=source_tiebreak,
                cursor_relative=cursor_relative,
            )
            for (
                source,
                activity,
                layer_rank,
                matched_text,
                source_tiebreak,
            ) in source_specs
        ]
        windows.append(
            sql.SQL(
                """
                (
                select
                    decision_match.conversation_id,
                    decision_match.source_id,
                    decision_match.candidate_at,
                    decision_match.matched_text,
                    decision_match.layer_rank,
                    decision_match.layer
                from {decision_match_name} as decision_match
                )
                """
            ).format(decision_match_name=decision_match_name)
        )
        return sql.SQL("\nunion all\n").join(windows)

    base_decision_ctes = decision_window_ctes(cursor_relative=False)
    match_window_ctes = (
        sql.SQL(
            """
            {decision_match_ctes},
            base_matches as (
                {base_matches}
            ),
            cursor_matches as (
                {cursor_matches}
            ),
            matches as (
                select * from base_matches
                union
                select * from cursor_matches
            )
            """
        ).format(
            decision_match_ctes=sql.SQL(",\n").join(
                (
                    base_decision_ctes,
                    decision_window_ctes(cursor_relative=True),
                )
            ),
            base_matches=source_windows(cursor_relative=False),
            cursor_matches=source_windows(cursor_relative=True),
        )
        if has_cursor
        else sql.SQL(
            """
            {decision_match_ctes},
            matches as (
                {base_matches}
            )
            """
        ).format(
            decision_match_ctes=base_decision_ctes,
            base_matches=source_windows(cursor_relative=False),
        )
    )
    return sql.SQL(
        """
        {match_window_ctes},
        winning_matches as (
            select *
            from (
                select
                    matches.*,
                    count(*) over (
                        partition by
                            matches.conversation_id,
                            matches.layer_rank
                    )::integer as match_count,
                    row_number() over (
                        partition by matches.conversation_id
                        order by
                            matches.layer_rank desc,
                            matches.candidate_at desc,
                            matches.matched_text collate "und-x-icu" desc,
                            matches.source_id desc
                    ) as conversation_rank
                from matches
            ) as ranked_matches
            where conversation_rank = 1
        ),
        ranked_conversations as (
            select
                conversation.id as conversation_id,
                conversation.title,
                conversation.last_message_preview,
                conversation.pinned,
                conversation.archived,
                conversation.created_at,
                conversation.updated_at,
                winning.matched_text,
                winning.layer_rank,
                winning.layer,
                winning.match_count,
                case
                    when winning.layer = 'message' then winning.source_id
                    else null
                end as message_id,
                activity.activity_at,
                conversation.pinned::integer as pinned_rank,
                {exact_rank_sql} as exact_rank,
                {symbol_rank_sql} as symbol_rank,
                {text_rank_sql} as text_rank
            from winning_matches as winning
            cross join input
            join public.conversations as conversation
              on conversation.id = winning.conversation_id
             and conversation.user_id = input.user_id
             and conversation.deleted_at is null
            cross join lateral (
                select max(source_activity.activity_at) as activity_at
                from (
                    select conversation.updated_at as activity_at
                    union all
                    select max(coalesce(run.updated_at, run.created_at))
                    from public.backtest_runs as run
                    where run.user_id = input.user_id
                      and run.conversation_id = conversation.id
                    union all
                    select max(message.created_at)
                    from public.messages as message
                    where message.user_id = input.user_id
                      and message.conversation_id = conversation.id
                    union all
                    select max(idea.updated_at)
                    from public.ideas as idea
                    where idea.user_id = input.user_id
                      and idea.source_conversation_id = conversation.id
                    union all
                    select max(evidence.updated_at)
                    from public.evidence_artifacts as evidence
                    where evidence.user_id = input.user_id
                      and evidence.source_conversation_id = conversation.id
                    union all
                    select max(decision.updated_at)
                    from public.decision_notes as decision
                    where decision.user_id = input.user_id
                      and decision.source_conversation_id = conversation.id
                ) as source_activity
            ) as activity
        )
        """
    ).format(
        match_window_ctes=match_window_ctes,
        exact_rank_sql=conversation_exact_rank,
        symbol_rank_sql=conversation_symbol_rank,
        text_rank_sql=conversation_text_rank(sql.SQL("winning.matched_text")),
    )


def _asset_symbol_slot(slot: int) -> sql.Composed:
    return sql.SQL("btrim({})").format(
        symbol_index_expression(
            sql.SQL("run.symbols[{}]").format(sql.Literal(slot))
        )
    )


def _asset_symbol_candidate_branch(slot: int) -> sql.Composed:
    normalized_symbol = _asset_symbol_slot(slot)
    raw_symbol = sql.SQL("run.symbols[{}]").format(sql.Literal(slot))
    return sql.SQL(
        """
        (
            select
                {normalized_symbol} as normalized_symbol,
                (
                    array_agg(
                        {raw_symbol}
                        order by
                            coalesce(run.updated_at, run.created_at) desc,
                            run.id desc
                    )
                )[1] as symbol,
                max(coalesce(run.updated_at, run.created_at)) as last_seen_at
            from input
            join public.backtest_runs as run
              on run.user_id = input.user_id
             and run.status = 'completed'
            join public.conversations as conversation
              on conversation.id = run.conversation_id
             and conversation.user_id = input.user_id
             and conversation.deleted_at is null
             and (
                 not input.guest_scope
                 or conversation.id = input.guest_conversation_id
             )
            where input.symbol_query is not null
              and input.symbol_prefix_end is not null
              and {raw_symbol} is not null
              and {normalized_symbol} collate "C"
                    >= input.symbol_query collate "C"
              and {normalized_symbol} collate "C"
                    < input.symbol_prefix_end collate "C"
            group by {normalized_symbol}
            order by {normalized_symbol} collate "C"
            limit (select asset_symbol_limit from input)
        )
        """
    ).format(
        normalized_symbol=normalized_symbol,
        raw_symbol=raw_symbol,
    )


def _asset_rollup_ctes() -> sql.Composed:
    candidate_branches = sql.SQL("\nunion all\n").join(
        _asset_symbol_candidate_branch(slot) for slot in range(1, 6)
    )
    matching_slot_predicates = sql.SQL("\n or \n").join(
        sql.SQL(
            """
            (
                run.symbols[{slot}] is not null
                and {normalized_symbol} collate "C"
                    = selected.normalized_symbol collate "C"
            )
            """
        ).format(
            slot=sql.Literal(slot),
            normalized_symbol=_asset_symbol_slot(slot),
        )
        for slot in range(1, 6)
    )
    return sql.SQL(
        """
        asset_symbol_candidates as (
            {candidate_branches}
        ),
        asset_symbol_stats as (
            select
                candidate.normalized_symbol,
                (
                    array_agg(
                        candidate.symbol
                        order by
                            candidate.last_seen_at desc,
                            candidate.symbol
                    )
                )[1] as symbol,
                max(candidate.last_seen_at) as last_seen_at
            from asset_symbol_candidates as candidate
            group by candidate.normalized_symbol
        ),
        asset_symbol_resolution as (
            select
                stats.*,
                count(*) over () as matching_symbol_count,
                bool_or(
                    stats.normalized_symbol = input.symbol_query
                ) over () as exact_present
            from asset_symbol_stats as stats
            cross join input
        ),
        asset_selected_symbol as (
            select resolution.*
            from asset_symbol_resolution as resolution
            cross join input
            where resolution.normalized_symbol = input.symbol_query
               or (
                   not resolution.exact_present
                   and resolution.matching_symbol_count = 1
               )
            order by
                (
                    resolution.normalized_symbol = input.symbol_query
                ) desc,
                resolution.last_seen_at desc,
                resolution.symbol
            limit 1
        ),
        asset_matching_runs as materialized (
            select run.*
            from input
            join public.backtest_runs as run
              on run.user_id = input.user_id
             and run.status = 'completed'
            join public.conversations as conversation
              on conversation.id = run.conversation_id
             and conversation.user_id = input.user_id
             and conversation.deleted_at is null
             and (
                 not input.guest_scope
                 or conversation.id = input.guest_conversation_id
             )
            cross join asset_selected_symbol as selected
            where ({matching_slot_predicates})
        ),
        asset_run_lineage as (
            select
                run.id as run_id,
                selected.symbol,
                selected.normalized_symbol,
                coalesce(run.updated_at, run.created_at) as run_touched_at,
                evidence_touch.updated_at as evidence_touched_at,
                latest_decision.decision_state,
                latest_decision.updated_at as decision_touched_at
            from input
            cross join asset_selected_symbol as selected
            cross join asset_matching_runs as run
            left join lateral (
                select max(evidence.updated_at) as updated_at
                from public.evidence_artifacts as evidence
                where evidence.user_id = input.user_id
                  and evidence.source_conversation_id = run.conversation_id
                  and evidence.source_run_id = run.id
            ) as evidence_touch
              on true
            left join lateral (
                select
                    decision.decision_state,
                    decision.updated_at
                from public.evidence_artifacts as evidence
                join public.decision_notes as decision
                  on decision.evidence_artifact_id = evidence.id
                 and decision.user_id = input.user_id
                 and decision.source_conversation_id = run.conversation_id
                where evidence.user_id = input.user_id
                  and evidence.source_conversation_id = run.conversation_id
                  and evidence.source_run_id = run.id
                order by decision.updated_at desc, decision.id desc
                limit 1
            ) as latest_decision
              on true
        ),
        asset_rollup as (
            select
                lineage.normalized_symbol,
                lineage.symbol,
                count(distinct lineage.run_id)::integer as run_count,
                count(distinct lineage.run_id) filter (
                    where lineage.decision_state = 'promising'
                )::integer as promising_count,
                count(distinct lineage.run_id) filter (
                    where lineage.decision_state = 'watching'
                )::integer as watching_count,
                count(distinct lineage.run_id) filter (
                    where lineage.decision_state = 'rejected'
                )::integer as rejected_count,
                count(distinct lineage.run_id) filter (
                    where lineage.decision_state = 'revisit_later'
                )::integer as revisit_later_count,
                max(
                    greatest(
                        lineage.run_touched_at,
                        coalesce(
                            lineage.evidence_touched_at,
                            lineage.run_touched_at
                        ),
                        coalesce(
                            lineage.decision_touched_at,
                            lineage.run_touched_at
                        )
                    )
                ) as last_touched_at
            from asset_run_lineage as lineage
            group by lineage.normalized_symbol, lineage.symbol
        )
        """
    ).format(
        candidate_branches=candidate_branches,
        matching_slot_predicates=matching_slot_predicates,
    )


def _asset_rollup_rows_sql() -> sql.SQL:
    return sql.SQL(
        """
        select
            'asset_rollup'::text as source_type,
            0::integer as pinned_rank,
            0::integer as exact_rank,
            0::integer as symbol_rank,
            0::integer as layer_rank,
            0::integer as text_rank,
            jsonb_build_object(
                'type', 'asset_rollup',
                'symbol', asset.symbol,
                'run_count', asset.run_count,
                'decision_counts', jsonb_build_object(
                    'promising', asset.promising_count,
                    'watching', asset.watching_count,
                    'rejected', asset.rejected_count,
                    'revisit_later', asset.revisit_later_count
                ),
                'last_touched_at', asset.last_touched_at
            ) as payload
        from asset_rollup as asset
        """
    )


def _asset_rollup_search_sql() -> sql.Composed:
    """Build the symbol-only path without transcript/object search relations."""
    return sql.SQL(
        """
        with {input_cte},
        {asset_rollup_ctes}
        {asset_rollup_rows}
        """
    ).format(
        input_cte=_CONVERSATION_INPUT_CTE,
        asset_rollup_ctes=_asset_rollup_ctes(),
        asset_rollup_rows=_asset_rollup_rows_sql(),
    )


def _conversation_search_sql(
    *,
    has_anchor: bool,
    has_cursor: bool = False,
    pivot_only: bool = False,
) -> sql.Composed:
    terminal_predicate = (
        sql.SQL(
            """
            ranked.conversation_id = input.cursor_id
            and ranked.activity_at = input.cursor_updated_at
            """
        )
        if pivot_only
        else sql.SQL(
            """
            not input.has_cursor
            or row(
                ranked.pinned_rank,
                ranked.exact_rank,
                ranked.symbol_rank,
                ranked.layer_rank,
                ranked.activity_at,
                ranked.text_rank,
                ranked.conversation_id
            ) < row(
                input.cursor_pinned_rank,
                input.cursor_exact_rank,
                input.cursor_symbol_rank,
                input.cursor_layer_rank,
                input.cursor_updated_at,
                input.cursor_text_rank,
                input.cursor_id
            )
            """
        )
    )
    conversation_rows = sql.SQL(
        """
        select
            'conversation'::text as source_type,
            ranked.pinned_rank,
            ranked.exact_rank,
            ranked.symbol_rank,
            ranked.layer_rank,
            ranked.text_rank,
            jsonb_build_object(
                'id', ranked.conversation_id,
                'title', ranked.title,
                'last_message_preview', ranked.last_message_preview,
                'pinned', ranked.pinned,
                'archived', ranked.archived,
                'created_at', ranked.created_at,
                'updated_at', ranked.updated_at,
                'deleted_at', null,
                '_recall_match', jsonb_build_object(
                    'matched_text', ranked.matched_text,
                    'layer_rank', ranked.layer_rank,
                    'layer', ranked.layer,
                    'match_count', ranked.match_count,
                    'message_id', ranked.message_id,
                    'symbol_exact_match', ranked.symbol_rank = 1,
                    'activity_at', ranked.activity_at
                )
            ) as payload
        from ranked_conversations as ranked
        cross join input
        where {terminal_predicate}
        order by
            ranked.pinned_rank desc,
            ranked.exact_rank desc,
            ranked.symbol_rank desc,
            ranked.layer_rank desc,
            ranked.activity_at desc,
            ranked.text_rank desc,
            ranked.conversation_id desc
        """
    ).format(
        terminal_predicate=terminal_predicate,
    )
    if pivot_only:
        return sql.SQL(
            """
            with {input_cte},
            {match_ctes}
            {conversation_rows}
            """
        ).format(
            input_cte=_CONVERSATION_INPUT_CTE,
            match_ctes=_conversation_match_ctes(
                has_anchor=has_anchor,
                has_cursor=has_cursor,
            ),
            conversation_rows=conversation_rows,
        )

    return sql.SQL(
        """
        with {input_cte},
        {match_ctes},
        {asset_rollup_ctes},
        conversation_page as (
            {conversation_rows}
            limit (select source_limit from input)
        )
        select
            source_type,
            pinned_rank,
            exact_rank,
            symbol_rank,
            layer_rank,
            text_rank,
            payload
        from conversation_page

        union all

        {asset_rollup_rows}
        """
    ).format(
        input_cte=_CONVERSATION_INPUT_CTE,
        match_ctes=_conversation_match_ctes(
            has_anchor=has_anchor,
            has_cursor=has_cursor,
        ),
        asset_rollup_ctes=_asset_rollup_ctes(),
        asset_rollup_rows=_asset_rollup_rows_sql(),
        conversation_rows=conversation_rows,
    )


def _conversation_ledger_sql(*, has_anchor: bool) -> sql.Composed:
    chat_title_haystack = _normalized("conversation.title")
    chat_preview_haystack = _normalized(
        "coalesce(conversation.last_message_preview, '')"
    )
    chat_index_haystack = _normalized(
        "conversation.title || ' ' "
        "|| coalesce(conversation.last_message_preview, '')"
    )
    message_haystack = _normalized("message.content")
    run_haystack = _normalized(
        "coalesce(run.conversation_result_card->>'title', '') || ' ' "
        "|| coalesce(array_to_string(run.symbols, ' '), '') || ' ' "
        "|| coalesce(run.config_snapshot->>'template', '') || ' ' "
        "|| coalesce(run.conversation_result_card->>'strategy_label', '')"
    )
    idea_haystack = _normalized("idea.title || ' ' || coalesce(idea.summary, '')")
    evidence_haystack = _normalized(
        "evidence.title || ' ' || coalesce(evidence.digest, '')"
    )
    decision_haystack = _normalized(
        f"""
        {_DECISION_INDEX_HAYSTACK} || ' '
        || evidence.title || ' ' || coalesce(evidence.digest, '')
        """
    )

    def token_predicate(
        haystack: sql.Composable,
        index_haystack: sql.Composable,
    ) -> sql.Composed:
        return _token_match_predicate(
            normalized_haystack=haystack,
            normalized_index_haystack=index_haystack,
            has_anchor=has_anchor,
        )

    decision_all_tokens = _all_token_recheck(decision_haystack)
    if has_anchor:
        decision_matches = sql.SQL(
            """
            decision_matching_conversations as (
                (
                select conversation.id as conversation_id
                from input
                join public.decision_notes as decision
                  on decision.user_id = input.user_id
                 and {decision_index} like %(anchor_pattern)s
                join public.evidence_artifacts as evidence
                  on evidence.id = decision.evidence_artifact_id
                 and evidence.user_id = input.user_id
                 and evidence.source_conversation_id =
                     decision.source_conversation_id
                join public.conversations as conversation
                  on conversation.id = decision.source_conversation_id
                 and conversation.user_id = input.user_id
                 and conversation.deleted_at is null
                where input.text_search_enabled
                  and input.normalized_query <> ''
                  and ({all_tokens})
                )

                union

                (
                select conversation.id
                from input
                join public.evidence_artifacts as evidence
                  on evidence.user_id = input.user_id
                 and {evidence_index} like %(anchor_pattern)s
                join public.decision_notes as decision
                  on decision.evidence_artifact_id = evidence.id
                 and decision.user_id = input.user_id
                 and decision.source_conversation_id =
                     evidence.source_conversation_id
                join public.conversations as conversation
                  on conversation.id = decision.source_conversation_id
                 and conversation.user_id = input.user_id
                 and conversation.deleted_at is null
                where input.text_search_enabled
                  and input.normalized_query <> ''
                  and ({all_tokens})
                )
            )
            """
        ).format(
            decision_index=_normalized(_DECISION_INDEX_HAYSTACK),
            evidence_index=_normalized(_EVIDENCE_INDEX_HAYSTACK),
            all_tokens=decision_all_tokens,
        )
    else:
        decision_matches = sql.SQL(
            """
            decision_matching_conversations as (
                select conversation.id as conversation_id
                from input
                join public.decision_notes as decision
                  on decision.user_id = input.user_id
                join public.evidence_artifacts as evidence
                  on evidence.id = decision.evidence_artifact_id
                 and evidence.user_id = input.user_id
                 and evidence.source_conversation_id =
                     decision.source_conversation_id
                join public.conversations as conversation
                  on conversation.id = decision.source_conversation_id
                 and conversation.user_id = input.user_id
                 and conversation.deleted_at is null
                where input.text_search_enabled
                  and input.normalized_query <> ''
                  and ({all_tokens})
            )
            """
        ).format(all_tokens=decision_all_tokens)

    return sql.SQL(
        """
        with {input_cte},
        {decision_matches},
        matching_conversations as (
            select conversation.id as conversation_id
            from input
            join public.conversations as conversation
              on conversation.user_id = input.user_id
             and conversation.deleted_at is null
            where (
                input.normalized_query = ''
                or (
                    input.text_search_enabled
                    and (
                        ({chat_title_predicate})
                        or ({chat_preview_predicate})
                    )
                )
            )

            union

            select conversation.id
            from input
            join public.messages as message
              on message.user_id = input.user_id
             and message.role = 'user'
             and message.content <> %(legacy_skip_message)s
             and message.content not like %(legacy_goal_pattern)s escape '\\'
            join public.conversations as conversation
              on conversation.id = message.conversation_id
             and conversation.user_id = input.user_id
             and conversation.deleted_at is null
            where input.text_search_enabled
              and input.normalized_query <> ''
              and ({message_predicate})

            union

            select conversation.id
            from input
            join public.backtest_runs as run
              on run.user_id = input.user_id
             and run.status = 'completed'
            join public.conversations as conversation
              on conversation.id = run.conversation_id
             and conversation.user_id = input.user_id
             and conversation.deleted_at is null
            where input.text_search_enabled
              and input.normalized_query <> ''
              and ({run_predicate})

            union

            select conversation.id
            from input
            join public.ideas as idea
              on idea.user_id = input.user_id
            join public.conversations as conversation
              on conversation.id = idea.source_conversation_id
             and conversation.user_id = input.user_id
             and conversation.deleted_at is null
            where input.text_search_enabled
              and input.normalized_query <> ''
              and ({idea_predicate})

            union

            select conversation.id
            from input
            join public.evidence_artifacts as evidence
              on evidence.user_id = input.user_id
            join public.conversations as conversation
              on conversation.id = evidence.source_conversation_id
             and conversation.user_id = input.user_id
             and conversation.deleted_at is null
            where input.text_search_enabled
              and input.normalized_query <> ''
              and ({evidence_predicate})

            union

            select conversation_id
            from decision_matching_conversations
        ),
        conversation_states as (
            select distinct
                decision.source_conversation_id as conversation_id,
                decision.decision_state
            from input
            join public.decision_notes as decision
              on decision.user_id = input.user_id
            join matching_conversations as matching
              on matching.conversation_id = decision.source_conversation_id
        )
        select
            decision_state,
            count(distinct conversation_id)::integer as count
        from conversation_states
        group by decision_state
        """
    ).format(
        input_cte=_CONVERSATION_LEDGER_INPUT_CTE,
        decision_matches=decision_matches,
        chat_title_predicate=token_predicate(
            chat_title_haystack,
            chat_index_haystack,
        ),
        chat_preview_predicate=token_predicate(
            chat_preview_haystack,
            chat_index_haystack,
        ),
        message_predicate=token_predicate(message_haystack, message_haystack),
        run_predicate=token_predicate(
            run_haystack,
            _normalized(_RUN_INDEX_HAYSTACK),
        ),
        idea_predicate=token_predicate(idea_haystack, idea_haystack),
        evidence_predicate=token_predicate(
            evidence_haystack,
            _normalized(_EVIDENCE_INDEX_HAYSTACK),
        ),
    )


_CONVERSATION_HYDRATION_SQL = """
select
    jsonb_build_object(
        'id', conversation.id,
        'title', conversation.title,
        'last_message_preview', conversation.last_message_preview,
        'pinned', conversation.pinned,
        'archived', conversation.archived,
        'created_at', conversation.created_at,
        'updated_at', conversation.updated_at,
        'deleted_at', conversation.deleted_at,
        '_recall_summary', jsonb_build_object(
            'run_count', coalesce(run_summary.run_count, 0),
            'symbols', coalesce(run_summary.symbols, array[]::text[]),
            'strategy_families',
                coalesce(run_summary.strategy_families, array[]::text[]),
            'start_date', run_summary.start_date,
            'end_date', run_summary.end_date,
            'decision_states',
                coalesce(decision_summary.decision_states, array[]::text[]),
            'latest_run_decided',
                coalesce(latest_run.latest_run_decided, false),
            'latest_suggestion_untaken',
                coalesce(latest_suggestion.untaken, false),
            'latest_activity', activity.activity_at
        )
    ) as conversation_payload,
    latest_run.payload as latest_run_payload,
    judged_run.payload as judged_run_payload,
    latest_evidence.payload as latest_evidence_payload,
    latest_run_decision.payload as latest_run_decision_payload,
    latest_decision.payload as latest_decision_payload
from public.conversations as conversation
left join lateral (
    select
        count(*)::integer as run_count,
        (
            select (array_agg(symbol order by last_used desc, symbol))[1:5]
            from (
                select symbol, max(coalesce(run.updated_at, run.created_at)) as last_used
                from public.backtest_runs as run
                cross join unnest(run.symbols) as symbol
                where run.user_id = %(user_id)s
                  and run.conversation_id = conversation.id
                  and run.status = 'completed'
                group by symbol
            ) as distinct_symbols
        ) as symbols,
        (
            select (array_agg(family order by last_used desc, family))[1:5]
            from (
                select
                    coalesce(
                        nullif(run.config_snapshot->>'template', ''),
                        nullif(
                            run.conversation_result_card->>'strategy_label',
                            ''
                        )
                    ) as family,
                    max(coalesce(run.updated_at, run.created_at)) as last_used
                from public.backtest_runs as run
                where run.user_id = %(user_id)s
                  and run.conversation_id = conversation.id
                  and run.status = 'completed'
                group by family
            ) as distinct_families
            where family is not null
        ) as strategy_families,
        min(
            case
                when coalesce(
                    run.config_snapshot->>'start_date',
                    run.conversation_result_card#>>'{date_range,start}'
                ) ~ '^\\d{4}-\\d{2}-\\d{2}$'
                    then coalesce(
                        run.config_snapshot->>'start_date',
                        run.conversation_result_card#>>'{date_range,start}'
                    )::date
            end
        ) as start_date,
        max(
            case
                when coalesce(
                    run.config_snapshot->>'end_date',
                    run.conversation_result_card#>>'{date_range,end}'
                ) ~ '^\\d{4}-\\d{2}-\\d{2}$'
                    then coalesce(
                        run.config_snapshot->>'end_date',
                        run.conversation_result_card#>>'{date_range,end}'
                    )::date
            end
        ) as end_date
    from public.backtest_runs as run
    where run.user_id = %(user_id)s
      and run.conversation_id = conversation.id
      and run.status = 'completed'
) as run_summary on true
left join lateral (
    select array_agg(
        states.decision_state
        order by case states.decision_state
            when 'promising' then 1
            when 'watching' then 2
            when 'rejected' then 3
            when 'revisit_later' then 4
            else 5
        end
    ) as decision_states
    from (
        select distinct decision.decision_state
        from public.decision_notes as decision
        where decision.user_id = %(user_id)s
          and decision.source_conversation_id = conversation.id
    ) as states
) as decision_summary on true
left join lateral (
    select
        jsonb_build_object(
            'id', run.id,
            'conversation_id', run.conversation_id,
            'status', run.status,
            'asset_class', run.asset_class,
            'symbols', run.symbols,
            'benchmark_symbol', run.benchmark_symbol,
            'config_snapshot', run.config_snapshot,
            'conversation_result_card', run.conversation_result_card,
            'created_at', run.created_at,
            'updated_at', run.updated_at
        ) as payload,
        run.id,
        exists (
            select 1
            from public.decision_notes as decision
            join public.evidence_artifacts as evidence
              on evidence.id = decision.evidence_artifact_id
             and evidence.user_id = %(user_id)s
            where decision.user_id = %(user_id)s
              and decision.source_conversation_id = conversation.id
              and evidence.source_run_id = run.id
        ) as latest_run_decided
    from public.backtest_runs as run
    where run.user_id = %(user_id)s
      and run.conversation_id = conversation.id
      and run.status = 'completed'
    order by coalesce(run.updated_at, run.created_at) desc, run.id desc
    limit 1
) as latest_run on true
left join lateral (
    select not exists (
        select 1
        from public.messages as later_message
        where later_message.user_id = %(user_id)s
          and later_message.conversation_id = conversation.id
          and later_message.role = 'user'
          and (later_message.created_at, later_message.id)
              > (offer.created_at, offer.id)
    ) as untaken
    from public.messages as offer
    where offer.user_id = %(user_id)s
      and offer.conversation_id = conversation.id
      and offer.role = 'assistant'
      and offer.metadata->>'result_run_id' = latest_run.id::text
      and offer.metadata#>>'{next_experiments,version}'
          = 'argus_next_experiments/v1'
      and jsonb_array_length(
          case
              when jsonb_typeof(offer.metadata#>'{next_experiments,rows}')
                  = 'array'
                  then offer.metadata#>'{next_experiments,rows}'
              else '[]'::jsonb
          end
      ) > 0
    order by offer.created_at desc, offer.id desc
    limit 1
) as latest_suggestion on true
left join lateral (
    select
        jsonb_build_object(
            'id', decision.id,
            'idea_id', decision.idea_id,
            'idea_version_id', decision.idea_version_id,
            'evidence_artifact_id', decision.evidence_artifact_id,
            'source_conversation_id', decision.source_conversation_id,
            'decision_state', decision.decision_state,
            'note', decision.note,
            'created_at', decision.created_at,
            'updated_at', decision.updated_at,
            'source_run_id', evidence.source_run_id,
            'artifact_title', evidence.title,
            'artifact_digest', evidence.digest,
            'artifact_payload', evidence.payload
        ) as payload,
        evidence.source_run_id
    from public.decision_notes as decision
    left join public.evidence_artifacts as evidence
      on evidence.id = decision.evidence_artifact_id
     and evidence.user_id = %(user_id)s
    where decision.user_id = %(user_id)s
      and decision.source_conversation_id = conversation.id
    order by decision.updated_at desc, decision.id desc
    limit 1
) as latest_decision on true
left join lateral (
    select jsonb_build_object(
        'id', run.id,
        'conversation_id', run.conversation_id,
        'status', run.status,
        'asset_class', run.asset_class,
        'symbols', run.symbols,
        'benchmark_symbol', run.benchmark_symbol,
        'config_snapshot', run.config_snapshot,
        'conversation_result_card', run.conversation_result_card,
        'created_at', run.created_at,
        'updated_at', run.updated_at
    ) as payload
    from public.backtest_runs as run
    where run.user_id = %(user_id)s
      and run.conversation_id = conversation.id
      and run.id = latest_decision.source_run_id
    limit 1
) as judged_run on true
left join lateral (
    select jsonb_build_object(
        'id', evidence.id,
        'idea_id', evidence.idea_id,
        'idea_version_id', evidence.idea_version_id,
        'source_conversation_id', evidence.source_conversation_id,
        'source_run_id', evidence.source_run_id,
        'artifact_type', evidence.artifact_type,
        'lifecycle', evidence.lifecycle,
        'title', evidence.title,
        'digest', evidence.digest,
        'payload', evidence.payload,
        'created_at', evidence.created_at,
        'updated_at', evidence.updated_at
    ) as payload
    from public.evidence_artifacts as evidence
    where evidence.user_id = %(user_id)s
      and evidence.source_conversation_id = conversation.id
      and evidence.source_run_id = latest_run.id
    order by evidence.updated_at desc, evidence.id desc
    limit 1
) as latest_evidence on true
left join lateral (
    select jsonb_build_object(
        'id', decision.id,
        'idea_id', decision.idea_id,
        'idea_version_id', decision.idea_version_id,
        'evidence_artifact_id', decision.evidence_artifact_id,
        'source_conversation_id', decision.source_conversation_id,
        'decision_state', decision.decision_state,
        'note', decision.note,
        'created_at', decision.created_at,
        'updated_at', decision.updated_at
    ) as payload
    from public.decision_notes as decision
    where decision.user_id = %(user_id)s
      and decision.source_conversation_id = conversation.id
      and decision.evidence_artifact_id = (
          latest_evidence.payload->>'id'
      )::uuid
    order by decision.updated_at desc, decision.id desc
    limit 1
) as latest_run_decision on true
cross join lateral (
    select max(source_activity.activity_at) as activity_at
    from (
        select conversation.updated_at as activity_at
        union all
        select max(coalesce(run.updated_at, run.created_at))
        from public.backtest_runs as run
        where run.user_id = %(user_id)s
          and run.conversation_id = conversation.id
        union all
        select max(message.created_at)
        from public.messages as message
        where message.user_id = %(user_id)s
          and message.conversation_id = conversation.id
        union all
        select max(idea.updated_at)
        from public.ideas as idea
        where idea.user_id = %(user_id)s
          and idea.source_conversation_id = conversation.id
        union all
        select max(evidence.updated_at)
        from public.evidence_artifacts as evidence
        where evidence.user_id = %(user_id)s
          and evidence.source_conversation_id = conversation.id
        union all
        select max(decision.updated_at)
        from public.decision_notes as decision
        where decision.user_id = %(user_id)s
          and decision.source_conversation_id = conversation.id
    ) as source_activity
) as activity
where conversation.user_id = %(user_id)s
  and conversation.deleted_at is null
  and conversation.id = any(%(conversation_ids)s::uuid[])
order by array_position(%(conversation_ids)s::uuid[], conversation.id)
"""


def _ledger_sql(*, has_anchor: bool) -> sql.Composed:
    normalized_haystack = _normalized("idea.title || ' ' || coalesce(idea.summary, '')")
    token_predicate = _token_match_predicate(
        normalized_haystack=sql.SQL("search_text.normalized_haystack"),
        normalized_index_haystack=normalized_haystack,
        has_anchor=has_anchor,
    )
    return sql.SQL(
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
                or ({token_predicate})
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
        normalized_haystack=normalized_haystack,
        token_predicate=token_predicate,
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
        if cursor_id is not None and str(pivot_id) != cursor_id:
            raise SearchCursorError("Search cursor id is not canonical.")
        try:
            workspace_id = (
                UUID(guest_conversation_id) if guest_conversation_id is not None else None
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("Guest workspace conversation id is invalid.") from exc

        normalized_query = normalize_search_text(query)
        normalized_tokens = tuple(dict.fromkeys(normalized_query.split()))
        symbol_query = normalize_search_symbol(query)
        text_search_enabled = (
            not normalized_query or search_has_indexable_token(query)
        )
        anchor_token = max(
            (token for token in normalized_tokens if len(token) >= 3),
            key=len,
            default=None,
        )
        if query.strip() and not search_query_is_indexable(query):
            if has_cursor:
                raise SearchCursorError(
                    "Deferred short search cannot continue from a cursor."
                )
            return SearchReadResult(
                rows=_group_candidates([], source_limit=source_limit),
                ledger_counts=(
                    {state: 0 for state in _DECISION_STATES}
                    if include_ledger_groups and not guest_scope
                    else None
                ),
            )
        if has_cursor and not text_search_enabled:
            raise SearchCursorError(
                "A symbol-only search cannot continue from a conversation cursor."
            )
        legacy_skip_message, legacy_goal_pattern = legacy_onboarding_sql_filters()
        params: dict[str, Any] = {
            "user_id": owner_id,
            "normalized_query": normalized_query,
            # PostgreSQL text cannot represent NUL. Normalized matching remains
            # exact, while raw symbol equality must be false for such a query
            # because stored Postgres symbols cannot contain NUL either.
            "symbol_query": (symbol_query if "\x00" not in query else None),
            "symbol_prefix_end": (
                _symbol_prefix_end(symbol_query) if "\x00" not in query else None
            ),
            "source_limit": source_limit,
            "match_limit": _conversation_match_limit(source_limit),
            "asset_symbol_limit": 2,
            "text_search_enabled": text_search_enabled,
            "has_cursor": has_cursor,
            "cursor_pinned_rank": 0,
            "cursor_exact_rank": 0,
            "cursor_symbol_rank": 0,
            "cursor_type_rank": 0,
            "cursor_layer_rank": 0,
            "cursor_updated_at": cursor_updated_at,
            "cursor_text_rank": 0,
            "cursor_id": pivot_id,
            "decision_state": decision_state,
            "ledger_browse": include_ledger_groups and not normalized_query,
            "ideas_only": False,
            "guest_scope": guest_scope,
            "guest_conversation_id": workspace_id,
            "token_patterns": [f"%{token}%" for token in normalized_tokens],
            "anchor_pattern": (f"%{anchor_token}%" if anchor_token is not None else None),
            "legacy_skip_message": legacy_skip_message,
            "legacy_goal_pattern": legacy_goal_pattern,
        }
        with self.pool.connection(timeout=_SEARCH_ACQUIRE_TIMEOUT_SECONDS) as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                if has_cursor:
                    cursor.execute(
                        _conversation_search_sql(
                            has_anchor=anchor_token is not None,
                            has_cursor=True,
                            pivot_only=True,
                        ),
                        params,
                    )
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
                        cursor_layer_rank=int(pivot["layer_rank"]),
                        cursor_text_rank=int(pivot["text_rank"]),
                    )

                search_sql = (
                    _conversation_search_sql(
                        has_anchor=anchor_token is not None,
                        has_cursor=has_cursor,
                    )
                    if text_search_enabled
                    else _asset_rollup_search_sql()
                )
                cursor.execute(search_sql, params)
                candidate_rows = cursor.fetchall()
                grouped = _group_candidates(
                    candidate_rows,
                    source_limit=source_limit,
                )
                asset_rows = grouped.pop("asset_rollups", [])
                asset_rollup = (
                    SearchAssetRollup.model_validate(asset_rows[0])
                    if asset_rows
                    else None
                )
                grouped = _hydrate_conversation_recall(
                    cursor=cursor,
                    owner_id=owner_id,
                    grouped=grouped,
                    guest_conversation_id=workspace_id if guest_scope else None,
                )
                ledger_counts = None
                if include_ledger_groups and not guest_scope:
                    ledger_counts = {state: 0 for state in _DECISION_STATES}
                    if text_search_enabled:
                        ledger_params = {
                            **params,
                            "decision_state": None,
                            "has_cursor": False,
                            "cursor_id": None,
                            "cursor_updated_at": None,
                        }
                        cursor.execute(
                            _conversation_ledger_sql(
                                has_anchor=anchor_token is not None
                            ),
                            ledger_params,
                        )
                        for row in cursor.fetchall():
                            state = str(row.get("decision_state") or "")
                            if state in ledger_counts:
                                ledger_counts[state] = int(row.get("count") or 0)

        return SearchReadResult(
            rows=grouped,
            ledger_counts=ledger_counts,
            asset_rollup=asset_rollup,
        )


def _hydrate_conversation_recall(
    *,
    cursor: Any,
    owner_id: UUID,
    grouped: dict[str, list[dict[str, Any]]],
    guest_conversation_id: UUID | None,
) -> dict[str, list[dict[str, Any]]]:
    """Hydrate exact full-lineage aggregates and only selected child facts."""
    candidate_conversations = {
        str(row["id"]): row
        for row in grouped["conversations"]
        if row.get("id") is not None
    }
    unique_ids = list(candidate_conversations)
    if guest_conversation_id is not None:
        unique_ids = [
            value for value in unique_ids if value == str(guest_conversation_id)
        ]
    if not unique_ids:
        return {group: [] for group in _CONVERSATION_ROW_GROUPS}

    params = {"user_id": owner_id, "conversation_ids": unique_ids}
    hydrated: dict[str, list[dict[str, Any]]] = {
        group: [] for group in _CONVERSATION_ROW_GROUPS
    }
    cursor.execute(_CONVERSATION_HYDRATION_SQL, params)
    for row in cursor.fetchall():
        conversation_payload = row.get("conversation_payload")
        if not isinstance(conversation_payload, dict):
            continue
        conversation_id = str(conversation_payload.get("id") or "")
        candidate = candidate_conversations.get(conversation_id, {})
        recall_match = candidate.get("_recall_match")
        if isinstance(recall_match, dict):
            conversation_payload["_recall_match"] = recall_match
        hydrated["conversations"].append(conversation_payload)

        seen_run_ids: set[str] = set()
        for key in ("latest_run_payload", "judged_run_payload"):
            payload = row.get(key)
            if not isinstance(payload, dict):
                continue
            run_id = str(payload.get("id") or "")
            if not run_id or run_id in seen_run_ids:
                continue
            seen_run_ids.add(run_id)
            hydrated["runs"].append(payload)
        latest_evidence = row.get("latest_evidence_payload")
        if isinstance(latest_evidence, dict):
            hydrated["evidence"].append(latest_evidence)
        seen_decision_ids: set[str] = set()
        for key in ("latest_decision_payload", "latest_run_decision_payload"):
            latest_decision = row.get(key)
            if not isinstance(latest_decision, dict):
                continue
            decision_id = str(latest_decision.get("id") or "")
            if not decision_id or decision_id in seen_decision_ids:
                continue
            seen_decision_ids.add(decision_id)
            hydrated["decisions"].append(latest_decision)
    return hydrated


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
        decision["artifact_payload"] = artifact.get("payload")


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
