from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Mapping
from threading import RLock

from argus.domain.search_text import normalize_search_text

LEDGER_DECISION_STATES = (
    "promising",
    "watching",
    "rejected",
    "revisit_later",
)
MEMORY_LEDGER_CANDIDATE_LIMIT = 20_000

_STATE_ROWS_SQL = """
states(decision_state, position) AS (
    VALUES
        ('promising', 0),
        ('watching', 1),
        ('rejected', 2),
        ('revisit_later', 3)
)
"""

class MemoryLedgerWorkLimitExceeded(RuntimeError):
    """The bounded ledger corpus cannot produce exact counts."""


class MemoryLedgerIndex:
    """Thread-safe, non-durable exact ledger aggregation over SQLite FTS5."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        all_counts: Mapping[str, int],
        work_limit_exceeded: bool,
    ) -> None:
        self._connection = connection
        self._lock = RLock()
        self._all_counts = dict(all_counts)
        self._work_limit_exceeded = work_limit_exceeded

    def counts(
        self,
        *,
        query: str,
        eligible_conversation_id: str | None,
    ) -> dict[str, int]:
        normalized_query = normalize_search_text(query)
        if not normalized_query:
            if eligible_conversation_id is None:
                return dict(self._all_counts)
            return self._guest_counts(eligible_conversation_id)
        tokens = tuple(dict.fromkeys(normalized_query.split()))
        anchored_tokens = tuple(token for token in tokens if len(token) >= 3)
        if not anchored_tokens:
            return _empty_counts()
        if self._work_limit_exceeded:
            raise MemoryLedgerWorkLimitExceeded
        fts_query = " AND ".join(
            _quoted_fts_token(token) for token in anchored_tokens
        )
        with self._lock:
            sql, parameters = _matching_counts_query(
                tokens=tokens,
                fts_query=fts_query,
                eligible_conversation_id=eligible_conversation_id,
            )
            rows = self._connection.execute(sql, parameters).fetchall()
        return {str(state): int(count) for state, count in rows}

    def _guest_counts(self, conversation_id: str) -> dict[str, int]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT decision_state
                FROM decision_membership
                WHERE conversation_id = ?
                """,
                (conversation_id,),
            ).fetchall()
        counts = _empty_counts()
        for (state,) in rows:
            counts[str(state)] = 1
        return counts


def build_memory_ledger_index(
    *,
    candidates: Iterable[tuple[str, str]],
    decision_states_by_conversation: Mapping[str, Iterable[str]],
) -> MemoryLedgerIndex:
    memberships = tuple(
        (conversation_id, decision_state)
        for conversation_id, states in decision_states_by_conversation.items()
        for decision_state in states
        if decision_state in LEDGER_DECISION_STATES
    )
    eligible_conversation_ids = {
        conversation_id for conversation_id, _ in memberships
    }
    all_counts = _empty_counts()
    for _, decision_state in memberships:
        all_counts[decision_state] += 1
    candidate_rows: list[tuple[str, str]] = []
    for conversation_id, text in candidates:
        if conversation_id not in eligible_conversation_ids:
            continue
        normalized_text = normalize_search_text(text)
        if not normalized_text:
            continue
        candidate_rows.append((normalized_text, conversation_id))
        if len(candidate_rows) > MEMORY_LEDGER_CANDIDATE_LIMIT:
            break
    work_limit_exceeded = len(candidate_rows) > MEMORY_LEDGER_CANDIDATE_LIMIT
    if work_limit_exceeded:
        candidate_rows.clear()
    connection = sqlite3.connect(":memory:", check_same_thread=False)
    connection.execute(
        """
        CREATE VIRTUAL TABLE searchable_candidates USING fts5(
            normalized_text,
            conversation_id UNINDEXED,
            tokenize = 'trigram'
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE decision_membership (
            conversation_id TEXT NOT NULL,
            decision_state TEXT NOT NULL,
            PRIMARY KEY (conversation_id, decision_state)
        ) WITHOUT ROWID
        """
    )
    connection.execute(
        """
        CREATE INDEX decision_membership_by_state
        ON decision_membership (decision_state, conversation_id)
        """
    )
    connection.executemany(
        """
        INSERT INTO searchable_candidates (normalized_text, conversation_id)
        VALUES (?, ?)
        """,
        candidate_rows,
    )
    connection.executemany(
        """
        INSERT INTO decision_membership (conversation_id, decision_state)
        VALUES (?, ?)
        """,
        memberships,
    )
    connection.commit()
    return MemoryLedgerIndex(
        connection,
        all_counts=all_counts,
        work_limit_exceeded=work_limit_exceeded,
    )


def _matching_counts_query(
    *,
    tokens: tuple[str, ...],
    fts_query: str,
    eligible_conversation_id: str | None,
) -> tuple[str, tuple[str, ...]]:
    exact_predicates = "\n".join(
        "          AND instr(normalized_text, ?) > 0" for _ in tokens
    )
    eligibility_predicate = (
        "\n          AND conversation_id = ?"
        if eligible_conversation_id is not None
        else ""
    )
    sql = f"""
    WITH
    {_STATE_ROWS_SQL},
    anchored_candidates AS MATERIALIZED (
        SELECT normalized_text, conversation_id
        FROM searchable_candidates
        WHERE searchable_candidates MATCH ?
        LIMIT ?
    ),
    matching_conversations AS MATERIALIZED (
        SELECT DISTINCT conversation_id
        FROM anchored_candidates
        WHERE 1 = 1
{exact_predicates}
{eligibility_predicate}
    ),
    counts AS (
        SELECT membership.decision_state, COUNT(*) AS count
        FROM decision_membership AS membership
        JOIN matching_conversations AS matches USING (conversation_id)
        GROUP BY membership.decision_state
    )
    SELECT states.decision_state, COALESCE(counts.count, 0)
    FROM states
    LEFT JOIN counts USING (decision_state)
    ORDER BY states.position
    """
    parameters = (
        fts_query,
        MEMORY_LEDGER_CANDIDATE_LIMIT,
        *tokens,
        *((eligible_conversation_id,) if eligible_conversation_id is not None else ()),
    )
    return sql, parameters


def _quoted_fts_token(token: str) -> str:
    return f'"{token.replace(chr(34), chr(34) * 2)}"'


def _empty_counts() -> dict[str, int]:
    return {state: 0 for state in LEDGER_DECISION_STATES}
