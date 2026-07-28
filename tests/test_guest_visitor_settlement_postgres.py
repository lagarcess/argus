"""Real-Postgres proofs for visitor-keyed guest message settlement.

Skip-gated on ``ARGUS_DISPOSABLE_DATABASE_URL``. finalize_chat_turn gained
p_visitor_key: when present, the settled unit lands in
visitor_usage_counters inside the terminal transaction, and replays never
double-charge. Metering claims are only proven against the real schema.
"""

from __future__ import annotations

import json
import os
import secrets
import uuid

import pytest

DSN = os.getenv("ARGUS_DISPOSABLE_DATABASE_URL", "").strip()

pytestmark = pytest.mark.skipif(
    not DSN,
    reason="ARGUS_DISPOSABLE_DATABASE_URL is not configured",
)

psycopg = pytest.importorskip("psycopg")

DAY_LIMITS = [{"period": "day", "limit": 10}]


def _connect():
    return psycopg.connect(DSN, autocommit=True)


@pytest.fixture
def owner():
    with _connect() as connection:
        user_id = str(uuid.uuid4())
        conversation_id = str(uuid.uuid4())
        email = f"visitor-settle-{user_id[:8]}@argus.local"
        with connection.cursor() as cursor:
            cursor.execute(
                "insert into auth.users (id, email) values (%s, %s)",
                (user_id, email),
            )
            cursor.execute(
                "insert into public.profiles (id, email) values (%s, %s)",
                (user_id, email),
            )
            cursor.execute(
                "insert into public.conversations (id, user_id, title)"
                " values (%s, %s, 'Visitor settlement proof')",
                (conversation_id, user_id),
            )
        try:
            yield {"user_id": user_id, "conversation_id": conversation_id}
        finally:
            with connection.cursor() as cursor:
                cursor.execute(
                    "delete from auth.users where id = %s", (user_id,)
                )


def _accept(connection, owner, *, turn_id: str, request_id: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "select * from public.accept_chat_turn("
            " %s, %s, %s, 'user', 'One guest message',"
            " '{}'::jsonb, now(), 'One guest message', %s)",
            (
                owner["user_id"],
                owner["conversation_id"],
                turn_id,
                request_id,
            ),
        )
        assert cursor.fetchone() is not None


def _finalize(
    connection,
    owner,
    *,
    turn_id: str,
    request_id: str,
    message_id: str,
    visitor_key: str | None,
) -> None:
    runtime_turn = {
        "turn_id": turn_id,
        "request_id": request_id,
        "status": "completed",
        "terminal": True,
    }
    with connection.cursor() as cursor:
        cursor.execute(
            "select * from public.finalize_chat_turn("
            " %s, %s, %s, %s, %s, 'assistant', 'reply',"
            " %s::jsonb, now(), 'reply', 'completed', null, false,"
            " 'chat_messages', %s::jsonb, %s)",
            (
                owner["user_id"],
                owner["conversation_id"],
                turn_id,
                request_id,
                message_id,
                json.dumps({"agent_runtime_turn": runtime_turn}),
                json.dumps(DAY_LIMITS),
                visitor_key,
            ),
        )
        assert cursor.fetchone() is not None


def _visitor_used(cursor, visitor_key: str) -> int | None:
    cursor.execute(
        "select used_count from public.visitor_usage_counters"
        " where visitor_key = %s and resource = 'chat_messages'"
        " and period = 'day'",
        (visitor_key,),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def _account_used(cursor, user_id: str) -> int | None:
    cursor.execute(
        "select used_count from public.usage_counters"
        " where user_id = %s and resource = 'chat_messages'"
        " and period = 'day'",
        (user_id,),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def test_visitor_key_routes_settlement_to_the_visitor_table(owner) -> None:
    visitor_key = f"visitor:{secrets.token_hex(16)}"
    turn_id, request_id, message_id = (
        str(uuid.uuid4()),
        f"req-{secrets.token_hex(6)}",
        str(uuid.uuid4()),
    )
    with _connect() as connection:
        _accept(connection, owner, turn_id=turn_id, request_id=request_id)
        _finalize(
            connection,
            owner,
            turn_id=turn_id,
            request_id=request_id,
            message_id=message_id,
            visitor_key=visitor_key,
        )
        with connection.cursor() as cursor:
            assert _visitor_used(cursor, visitor_key) == 1
            # The account table stays untouched: one unit, one owner.
            assert _account_used(cursor, owner["user_id"]) is None


def test_replayed_finalization_never_double_charges_the_visitor(owner) -> None:
    visitor_key = f"visitor:{secrets.token_hex(16)}"
    turn_id, request_id, message_id = (
        str(uuid.uuid4()),
        f"req-{secrets.token_hex(6)}",
        str(uuid.uuid4()),
    )
    with _connect() as connection:
        _accept(connection, owner, turn_id=turn_id, request_id=request_id)
        for _ in range(3):
            _finalize(
                connection,
                owner,
                turn_id=turn_id,
                request_id=request_id,
                message_id=message_id,
                visitor_key=visitor_key,
            )
        with connection.cursor() as cursor:
            assert _visitor_used(cursor, visitor_key) == 1


def test_account_settlement_without_visitor_key_is_unchanged(owner) -> None:
    turn_id, request_id, message_id = (
        str(uuid.uuid4()),
        f"req-{secrets.token_hex(6)}",
        str(uuid.uuid4()),
    )
    with _connect() as connection:
        _accept(connection, owner, turn_id=turn_id, request_id=request_id)
        _finalize(
            connection,
            owner,
            turn_id=turn_id,
            request_id=request_id,
            message_id=message_id,
            visitor_key=None,
        )
        with connection.cursor() as cursor:
            assert _account_used(cursor, owner["user_id"]) == 1
