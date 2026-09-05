"""Run the production preview reader against an isolated synthetic Postgres.

Requires the explicitly named local proof container documented in
preview-sql-proof.md. The fixed loopback DSN cannot select a hosted database or
the shared local Supabase database. Run once per fresh proof container.
"""

import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import psycopg
from argus.api.chat.legacy_onboarding_markers import (
    _LEGACY_GOAL_PREFIX,
    _LEGACY_SKIP_MARKER,
)
from argus.domain.conversation_previews import project_conversation_preview
from argus.domain.postgres_keyset_reader import PostgresKeysetReader
from psycopg.types.json import Jsonb

DSN = "postgresql://postgres@127.0.0.1:55431/argus_531_preview_proof"
OWNER = UUID(int=1)
OTHER_OWNER = UUID(int=2)
CHATS = {
    name: UUID(int=index)
    for index, name in enumerate(
        ("tie", "empty", "markers", "tool", "system", "foreign", "unrequested"),
        start=101,
    )
}
NOW = datetime(2026, 8, 31, 10, tzinfo=timezone.utc)


class ObservedCursor:
    def __init__(self, cursor: Any, executions: list[Any]):
        self.cursor = cursor
        self.executions = executions

    def __enter__(self):
        self.cursor.__enter__()
        return self

    def __exit__(self, *args):
        return self.cursor.__exit__(*args)

    def execute(self, query, params):
        self.executions.append((query, params))
        return self.cursor.execute(query, params)

    def fetchall(self):
        return self.cursor.fetchall()


class ObservedConnection:
    def __init__(self, connection: Any, executions: list[Any]):
        self.connection = connection
        self.executions = executions

    def cursor(self, **kwargs):
        return ObservedCursor(self.connection.cursor(**kwargs), self.executions)


class ObservedPool:
    def __init__(self):
        self.executions = []
        self.acquisitions = 0

    @contextmanager
    def connection(self, *, timeout: float):
        assert timeout == 2.0
        self.acquisitions += 1
        with psycopg.connect(DSN, autocommit=True) as connection:
            yield ObservedConnection(connection, self.executions)


def walk_plan(plan):
    yield plan
    for child in plan.get("Plans", []):
        yield from walk_plan(child)


def main():
    with psycopg.connect(DSN, autocommit=True) as connection:
        # Empty-proof schema creation fails if this is not a fresh isolated DB.
        connection.execute(
            "create table public.conversations (id uuid primary key, user_id uuid not null)"
        )
        connection.execute("""create table public.messages (
            id uuid primary key, user_id uuid not null,
            conversation_id uuid not null references public.conversations(id),
            role text not null, content text not null,
            metadata jsonb not null default '{}', created_at timestamptz not null
        )""")
        # Exact production index from 20260424000001_alpha_core.sql:138.
        connection.execute(
            "create index idx_messages_conversation_created on public.messages(conversation_id, created_at desc)"
        )
        with connection.cursor() as cursor:
            cursor.executemany(
                "insert into public.conversations values (%s, %s)",
                [
                    (chat, OTHER_OWNER if name == "foreign" else OWNER)
                    for name, chat in CHATS.items()
                ],
            )
        for name in ("tie", "foreign"):
            connection.execute(
                """insert into public.messages
                select md5(%s || n::text)::uuid, %s, %s, 'user', 'synthetic old message',
                       '{}'::jsonb, %s::timestamptz - n * interval '1 minute'
                from generate_series(1, 12000) n""",
                (name, OTHER_OWNER if name == "foreign" else OWNER, CHATS[name], NOW),
            )
        rows = [
            (
                1,
                "tie",
                OWNER,
                "assistant",
                "older tied result",
                {"result_card": {"symbols": ["SPY"]}},
                NOW,
            ),
            (
                2,
                "tie",
                OWNER,
                "assistant",
                "winning tied result",
                {"result_card": {"symbols": ["NVDA"]}},
                NOW,
            ),
            (
                3,
                "tie",
                OTHER_OWNER,
                "assistant",
                "FOREIGN MESSAGE MUST NOT LEAK",
                {},
                NOW + timedelta(minutes=3),
            ),
            (4, "markers", OWNER, "user", "visible owner message", {}, NOW),
            (
                5,
                "markers",
                OWNER,
                "user",
                _LEGACY_SKIP_MARKER,
                {},
                NOW + timedelta(minutes=1),
            ),
            (
                6,
                "markers",
                OWNER,
                "user",
                _LEGACY_GOAL_PREFIX + "synthetic",
                {},
                NOW + timedelta(minutes=2),
            ),
            (7, "tool", OWNER, "tool", "INTERNAL TOOL CONTENT", {}, NOW),
            (8, "system", OWNER, "system", "INTERNAL SYSTEM CONTENT", {}, NOW),
            (
                9,
                "foreign",
                OTHER_OWNER,
                "assistant",
                "FOREIGN CONVERSATION MUST NOT LEAK",
                {},
                NOW,
            ),
            (10, "unrequested", OWNER, "user", "UNREQUESTED CONVERSATION", {}, NOW),
        ]
        with connection.cursor() as cursor:
            cursor.executemany(
                "insert into public.messages values (%s, %s, %s, %s, %s, %s, %s)",
                [
                    (
                        UUID(int=number),
                        owner,
                        CHATS[chat],
                        role,
                        content,
                        Jsonb(metadata),
                        at,
                    )
                    for number, chat, owner, role, content, metadata, at in rows
                ],
            )
        connection.execute("analyze public.conversations")
        connection.execute("analyze public.messages")
        total_messages = connection.execute(
            "select count(*) from public.messages"
        ).fetchone()[0]

    pool = ObservedPool()
    requested = [str(chat) for name, chat in CHATS.items() if name != "unrequested"]
    result = PostgresKeysetReader(pool).read_conversation_preview_messages(
        user_id=str(OWNER), conversation_ids=requested + [requested[0]]
    )
    assert pool.acquisitions == 1 and len(pool.executions) == 1
    indexed = {row["conversation_id"]: row for row in result}
    assert len(indexed) == 5
    assert str(CHATS["foreign"]) not in indexed
    assert str(CHATS["unrequested"]) not in indexed
    assert indexed[str(CHATS["tie"])]["content"] == "winning tied result"
    assert indexed[str(CHATS["empty"])]["role"] is None
    assert indexed[str(CHATS["markers"])]["content"] == "visible owner message"
    projected = {
        name: project_conversation_preview(indexed[str(chat)])
        for name, chat in CHATS.items()
        if str(chat) in indexed
    }
    assert projected["tie"].kind == "result" and projected["tie"].symbols == ["NVDA"]
    assert projected["empty"].kind == "empty"
    assert projected["tool"].kind == projected["system"].kind == "unavailable"
    assert "INTERNAL" not in " ".join(
        value.model_dump_json() for value in projected.values()
    )

    query, params = pool.executions[0]
    with psycopg.connect(DSN, autocommit=True) as connection:
        measured = connection.execute(
            "explain (analyze, buffers, format json) " + query, params
        ).fetchone()[0][0]
        version = connection.execute("show server_version").fetchone()[0]
    nodes = list(walk_plan(measured["Plan"]))
    message_scans = [node for node in nodes if node.get("Relation Name") == "messages"]
    assert message_scans
    assert all(
        node["Node Type"] in {"Index Scan", "Index Only Scan"} for node in message_scans
    )
    assert {node.get("Index Name") for node in message_scans} == {
        "idx_messages_conversation_created"
    }
    assert sum(node["Actual Rows"] * node["Actual Loops"] for node in message_scans) <= 30
    print(
        json.dumps(
            {
                "status": "passed",
                "postgres": version,
                "synthetic_conversations": len(CHATS),
                "synthetic_messages": total_messages,
                "requested_conversations": len(requested),
                "returned_owned_conversations": len(result),
                "reader_queries": len(pool.executions),
                "reader_pool_acquisitions": pool.acquisitions,
                "checks": [
                    "latest timestamp and id tie ordering",
                    "owner scoped conversations",
                    "cross-owner message excluded",
                    "unrequested conversation excluded",
                    "empty chat",
                    "legacy skip and goal markers excluded",
                    "system and tool previews unavailable",
                    "one deduplicated batch",
                ],
                "plan": [
                    {
                        key: node[key]
                        for key in (
                            "Node Type",
                            "Index Name",
                            "Relation Name",
                            "Actual Rows",
                            "Actual Loops",
                            "Rows Removed by Filter",
                        )
                        if key in node
                    }
                    for node in nodes
                ],
                "execution_ms": measured["Execution Time"],
                "shared_hit_blocks": measured["Plan"].get("Shared Hit Blocks", 0),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
