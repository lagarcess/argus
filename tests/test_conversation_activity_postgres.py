"""Disposable-Postgres proof for durable conversation activity/read truth.

Set ``ARGUS_DISPOSABLE_DATABASE_URL`` only to an isolated Supabase Postgres
database with all checked-in migrations applied.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

DSN = os.getenv("ARGUS_DISPOSABLE_DATABASE_URL", "").strip()
pytestmark = pytest.mark.skipif(
    not DSN,
    reason="ARGUS_DISPOSABLE_DATABASE_URL is not configured",
)
psycopg = pytest.importorskip("psycopg")


def _id() -> str:
    return str(uuid4())


def _connect(*, autocommit: bool = True):
    return psycopg.connect(DSN, autocommit=autocommit)


def _seed_identity(connection, *, anonymous: bool = False) -> str:
    user_id = _id()
    email = None if anonymous else f"activity-{user_id[:8]}@example.test"
    with connection.cursor() as cursor:
        cursor.execute(
            "insert into auth.users (id, email, is_anonymous) values (%s, %s, %s)",
            (user_id, email, anonymous),
        )
        cursor.execute(
            "insert into public.profiles (id, email) values (%s, %s)",
            (user_id, email),
        )
    return user_id


def _seed_conversation(connection, *, user_id: str) -> str:
    conversation_id = _id()
    with connection.cursor() as cursor:
        cursor.execute(
            "insert into public.conversations (id, user_id, title)"
            " values (%s, %s, 'Activity proof')",
            (conversation_id, user_id),
        )
    return conversation_id


def _seed_terminal_turn(
    connection,
    *,
    user_id: str,
    conversation_id: str,
    occurred_at: datetime,
    stage_outcome: str = "ready_to_respond",
    status: str = "completed",
) -> str:
    turn_id = _id()
    assistant_id = _id()
    request_id = f"request-{turn_id}"
    lifecycle_status = status
    reconciled_outcome = None
    failure_code = None
    retryable = False
    if status.startswith("reconciled:"):
        lifecycle_status, reconciled_outcome = status.split(":", 1)
    if status in {"recoverable_failed", "reconciled:recoverable_failed"}:
        failure_code = "runtime_failure"
        retryable = True
    runtime_status = reconciled_outcome or status
    metadata = {
        "agent_runtime_stage_outcome": stage_outcome,
        "agent_runtime_turn": {
            "turn_id": turn_id,
            "request_id": request_id,
            "terminal": True,
            "status": runtime_status,
            "failure_code": failure_code,
            "retryable": retryable,
        },
    }
    with connection.cursor() as cursor:
        cursor.execute(
            "insert into public.messages"
            " (id, conversation_id, user_id, role, content, created_at)"
            " values (%s, %s, %s, 'user', 'Test the idea', %s),"
            "        (%s, %s, %s, 'assistant', 'Typed result', %s)",
            (
                turn_id,
                conversation_id,
                user_id,
                occurred_at - timedelta(microseconds=1),
                assistant_id,
                conversation_id,
                user_id,
                occurred_at,
            ),
        )
        cursor.execute(
            "update public.messages set metadata = %s::jsonb where id = %s",
            (json.dumps(metadata), assistant_id),
        )
        cursor.execute(
            "insert into public.chat_turn_lifecycles"
            " (turn_id, user_id, conversation_id, assistant_message_id,"
            "  request_id, status, reconciled_outcome, failure_code, retryable,"
            "  accepted_at, terminal_at, reconciled_at, created_at, updated_at)"
            " values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                turn_id,
                user_id,
                conversation_id,
                None if lifecycle_status == "abandoned" else assistant_id,
                request_id,
                lifecycle_status,
                reconciled_outcome,
                "turn_abandoned" if lifecycle_status == "abandoned" else failure_code,
                True if lifecycle_status == "abandoned" else retryable,
                occurred_at - timedelta(seconds=1),
                occurred_at,
                occurred_at if lifecycle_status == "reconciled" else None,
                occurred_at - timedelta(seconds=1),
                occurred_at,
            ),
        )
    return turn_id


def _mutate(
    connection,
    *,
    user_id: str,
    conversation_id: str,
    action: str,
    source_kind: str | None = None,
    source_id: str | None = None,
) -> dict[str, object]:
    with connection.cursor() as cursor:
        cursor.execute(
            "select public.mutate_conversation_activity_read_state("
            " %s, %s, %s, %s, %s)",
            (user_id, conversation_id, action, source_kind, source_id),
        )
        row = cursor.fetchone()
    assert row is not None
    assert isinstance(row[0], dict)
    return row[0]


def _read_sources(
    connection,
    *,
    user_id: str,
    conversation_ids: list[str],
) -> list[tuple[object, object, object]]:
    with connection.cursor() as cursor:
        cursor.execute(
            "select * from public.read_conversation_activity_sources(%s, %s)",
            (user_id, conversation_ids),
        )
        return cursor.fetchall()


def _delete_identity(connection, user_id: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute("delete from auth.users where id = %s", (user_id,))


def test_owner_selects_read_state_but_foreign_anon_and_writes_are_denied() -> None:
    with _connect() as connection:
        owner_id = _seed_identity(connection)
        foreign_id = _seed_identity(connection)
        conversation_id = _seed_conversation(connection, user_id=owner_id)
        _mutate(
            connection,
            user_id=owner_id,
            conversation_id=conversation_id,
            action="mark_unread",
        )
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute("set local role authenticated")
                    cursor.execute(
                        "select set_config('request.jwt.claim.sub', %s, true)",
                        (owner_id,),
                    )
                    cursor.execute(
                        "select count(*) from public.conversation_read_states"
                        " where conversation_id = %s",
                        (conversation_id,),
                    )
                    assert cursor.fetchone()[0] == 1
                    cursor.execute(
                        "select set_config('request.jwt.claim.sub', %s, true)",
                        (foreign_id,),
                    )
                    cursor.execute(
                        "select count(*) from public.conversation_read_states"
                        " where conversation_id = %s",
                        (conversation_id,),
                    )
                    assert cursor.fetchone()[0] == 0

            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with connection.transaction():
                    with connection.cursor() as cursor:
                        cursor.execute("set local role authenticated")
                        cursor.execute(
                            "update public.conversation_read_states"
                            " set manual_unread_at = null"
                            " where conversation_id = %s",
                            (conversation_id,),
                        )

            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with connection.transaction():
                    with connection.cursor() as cursor:
                        cursor.execute("set local role anon")
                        cursor.execute(
                            "select * from public.conversation_read_states"
                            " where conversation_id = %s",
                            (conversation_id,),
                        )

            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with connection.transaction():
                    with connection.cursor() as cursor:
                        cursor.execute("set local role authenticated")
                        cursor.execute(
                            "select public.mutate_conversation_activity_read_state("
                            " %s, %s, 'mark_read', null, null)",
                            (owner_id, conversation_id),
                        )
        finally:
            _delete_identity(connection, owner_id)
            _delete_identity(connection, foreign_id)


def test_stale_read_cursor_cannot_consume_a_newer_completion() -> None:
    with _connect() as connection:
        user_id = _seed_identity(connection)
        conversation_id = _seed_conversation(connection, user_id=user_id)
        now = datetime.now(timezone.utc)
        older_id = _seed_terminal_turn(
            connection,
            user_id=user_id,
            conversation_id=conversation_id,
            occurred_at=now,
        )
        newer_id = _seed_terminal_turn(
            connection,
            user_id=user_id,
            conversation_id=conversation_id,
            occurred_at=now + timedelta(seconds=1),
            stage_outcome="await_user_reply",
        )
        try:
            result = _mutate(
                connection,
                user_id=user_id,
                conversation_id=conversation_id,
                action="mark_read",
                source_kind="chat_turn",
                source_id=older_id,
            )
            assert result["outcome"] == "applied"

            rows = _read_sources(
                connection,
                user_id=user_id,
                conversation_ids=[conversation_id],
            )
            assert len(rows) == 1
            sources = rows[0][1]
            read_state = rows[0][2]
            assert sources[-1]["source_id"] == newer_id
            assert sources[-1]["stage_outcome"] == "await_user_reply"
            assert read_state["read_through_source_id"] == older_id
        finally:
            _delete_identity(connection, user_id)


def test_deleted_list_source_read_remains_available_to_owner_batch() -> None:
    with _connect() as connection:
        user_id = _seed_identity(connection)
        conversation_id = _seed_conversation(connection, user_id=user_id)
        terminal_id = _seed_terminal_turn(
            connection,
            user_id=user_id,
            conversation_id=conversation_id,
            occurred_at=datetime.now(timezone.utc),
        )
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "update public.conversations set deleted_at = now() where id = %s",
                    (conversation_id,),
                )

            rows = _read_sources(
                connection,
                user_id=user_id,
                conversation_ids=[conversation_id],
            )

            assert len(rows) == 1
            assert rows[0][1][-1]["source_id"] == terminal_id
            assert (
                _mutate(
                    connection,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    action="mark_unread",
                )["outcome"]
                == "missing"
            )
        finally:
            _delete_identity(connection, user_id)


def test_manual_unread_is_idempotent_and_null_mark_read_preserves_boundary() -> None:
    with _connect() as connection:
        user_id = _seed_identity(connection)
        conversation_id = _seed_conversation(connection, user_id=user_id)
        terminal_id = _seed_terminal_turn(
            connection,
            user_id=user_id,
            conversation_id=conversation_id,
            occurred_at=datetime.now(timezone.utc),
        )
        try:
            _mutate(
                connection,
                user_id=user_id,
                conversation_id=conversation_id,
                action="mark_read",
                source_kind="chat_turn",
                source_id=terminal_id,
            )
            first = _mutate(
                connection,
                user_id=user_id,
                conversation_id=conversation_id,
                action="mark_unread",
            )
            second = _mutate(
                connection,
                user_id=user_id,
                conversation_id=conversation_id,
                action="mark_unread",
            )
            assert first["outcome"] == "applied"
            assert second["outcome"] == "noop"
            assert (
                first["read_state"]["manual_unread_at"]
                == second["read_state"]["manual_unread_at"]
            )

            cleared = _mutate(
                connection,
                user_id=user_id,
                conversation_id=conversation_id,
                action="mark_read",
            )
            assert cleared["read_state"]["manual_unread_at"] is None
            assert cleared["read_state"]["read_through_source_id"] == terminal_id
        finally:
            _delete_identity(connection, user_id)


def test_nonterminal_source_conflicts_without_mutating_read_state() -> None:
    with _connect() as connection:
        user_id = _seed_identity(connection)
        conversation_id = _seed_conversation(connection, user_id=user_id)
        turn_id = _id()
        with connection.cursor() as cursor:
            cursor.execute(
                "insert into public.messages"
                " (id, conversation_id, user_id, role, content)"
                " values (%s, %s, %s, 'user', 'Still working')",
                (turn_id, conversation_id, user_id),
            )
            cursor.execute(
                "insert into public.chat_turn_lifecycles"
                " (turn_id, user_id, conversation_id, request_id, status)"
                " values (%s, %s, %s, %s, 'accepted')",
                (turn_id, user_id, conversation_id, f"request-{turn_id}"),
            )
        try:
            result = _mutate(
                connection,
                user_id=user_id,
                conversation_id=conversation_id,
                action="mark_read",
                source_kind="chat_turn",
                source_id=turn_id,
            )
            assert result == {"outcome": "conflict", "read_state": None}
            with connection.cursor() as cursor:
                cursor.execute(
                    "select count(*) from public.conversation_read_states"
                    " where conversation_id = %s",
                    (conversation_id,),
                )
                assert cursor.fetchone()[0] == 0
        finally:
            _delete_identity(connection, user_id)


def test_conversation_owner_update_and_delete_cascade_read_state() -> None:
    with _connect() as connection:
        source_id = _seed_identity(connection, anonymous=True)
        destination_id = _seed_identity(connection)
        conversation_id = _seed_conversation(connection, user_id=source_id)
        _mutate(
            connection,
            user_id=source_id,
            conversation_id=conversation_id,
            action="mark_unread",
        )
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "update public.conversations set user_id = %s"
                    " where id = %s and user_id = %s",
                    (destination_id, conversation_id, source_id),
                )
                cursor.execute(
                    "select user_id from public.conversation_read_states"
                    " where conversation_id = %s",
                    (conversation_id,),
                )
                assert str(cursor.fetchone()[0]) == destination_id
                cursor.execute(
                    "delete from public.conversations where id = %s",
                    (conversation_id,),
                )
                cursor.execute(
                    "select count(*) from public.conversation_read_states"
                    " where conversation_id = %s",
                    (conversation_id,),
                )
                assert cursor.fetchone()[0] == 0
        finally:
            _delete_identity(connection, source_id)
            _delete_identity(connection, destination_id)


def test_cutoff_baseline_reads_existing_terminal_but_not_later_completion() -> None:
    with _connect() as connection:
        user_id = _seed_identity(connection)
        conversation_id = _seed_conversation(connection, user_id=user_id)
        cutoff = datetime.now(timezone.utc)
        older_id = _seed_terminal_turn(
            connection,
            user_id=user_id,
            conversation_id=conversation_id,
            occurred_at=cutoff - timedelta(seconds=1),
        )
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "select public.baseline_conversation_activity_read_states("
                    " %s, null, 500)",
                    (cutoff,),
                )
                result = cursor.fetchone()[0]
                assert result["processed"] >= 1

            newer_id = _seed_terminal_turn(
                connection,
                user_id=user_id,
                conversation_id=conversation_id,
                occurred_at=cutoff + timedelta(seconds=1),
            )
            with connection.cursor() as cursor:
                cursor.execute(
                    "select public.baseline_conversation_activity_read_states("
                    " %s, null, 500)",
                    (cutoff + timedelta(seconds=2),),
                )
                cursor.fetchone()
                cursor.execute(
                    "select read_through_source_id"
                    " from public.conversation_read_states"
                    " where user_id = %s and conversation_id = %s",
                    (user_id, conversation_id),
                )
                assert str(cursor.fetchone()[0]) == older_id

            rows = _read_sources(
                connection,
                user_id=user_id,
                conversation_ids=[conversation_id],
            )
            assert rows[0][1][-1]["source_id"] == newer_id
        finally:
            _delete_identity(connection, user_id)


def test_batch_read_is_one_call_for_volume_and_rejects_more_than_100_ids() -> None:
    with _connect() as connection:
        user_id = _seed_identity(connection)
        conversation_ids = [
            _seed_conversation(connection, user_id=user_id) for _ in range(100)
        ]
        try:
            rows = _read_sources(
                connection,
                user_id=user_id,
                conversation_ids=conversation_ids,
            )
            assert len(rows) == 100

            with pytest.raises(psycopg.errors.InvalidParameterValue):
                _read_sources(
                    connection,
                    user_id=user_id,
                    conversation_ids=conversation_ids + [_id()],
                )
        finally:
            _delete_identity(connection, user_id)
