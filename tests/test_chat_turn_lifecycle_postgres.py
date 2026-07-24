"""Real-Postgres proof for the ordinary-turn lifecycle contract.

Set ``ARGUS_DISPOSABLE_DATABASE_URL`` to an isolated database with all checked-in
migrations applied. Never point this test at a shared or production database.
"""

from __future__ import annotations

import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Event

import pytest

DSN = os.getenv("ARGUS_DISPOSABLE_DATABASE_URL", "").strip()

pytestmark = pytest.mark.skipif(
    not DSN,
    reason="ARGUS_DISPOSABLE_DATABASE_URL is not configured",
)

psycopg = pytest.importorskip("psycopg")


def _connect():
    return psycopg.connect(DSN, autocommit=True)


def _id() -> str:
    return str(uuid.uuid4())


def _seed_owner(connection) -> dict[str, str]:
    user_id = _id()
    conversation_id = _id()
    email = f"lifecycle-{user_id[:8]}@argus.local"
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
            " values (%s, %s, 'lifecycle proof')",
            (conversation_id, user_id),
        )
    return {"user_id": user_id, "conversation_id": conversation_id}


@pytest.fixture
def owner() -> dict[str, str]:
    with _connect() as connection:
        return _seed_owner(connection)


def _accept(
    connection,
    owner: dict[str, str],
    *,
    turn_id: str | None = None,
    request_id: str | None = None,
    content: str = "Test this idea.",
) -> dict[str, object]:
    turn_id = turn_id or _id()
    if request_id is None:
        request_id = f"request-{turn_id}"
    with connection.cursor() as cursor:
        cursor.execute(
            "select * from public.accept_chat_turn("
            " %s, %s, %s, 'user', %s, '{}'::jsonb, now(), %s, %s)",
            (
                owner["user_id"],
                owner["conversation_id"],
                turn_id,
                content,
                content,
                request_id,
            ),
        )
        row = cursor.fetchone()
    assert row is not None
    return {
        "message": row[0],
        "lifecycle": row[1],
        "replayed": row[2],
    }


def _accept_option(
    connection,
    owner: dict[str, str],
    *,
    source_assistant_id: str,
    expected_source_metadata: dict[str, object],
    option_id: str,
    replacement_values: dict[str, object],
    turn_id: str | None = None,
    message_metadata: dict[str, object] | None = None,
) -> dict[str, object] | None:
    turn_id = turn_id or _id()
    with connection.cursor() as cursor:
        cursor.execute(
            "select * from public.accept_chat_turn("
            " %s, %s, %s, 'user', 'Use daily bars', %s::jsonb,"
            " now(), 'Use daily bars', %s, %s, %s::jsonb, %s, %s::jsonb)",
            (
                owner["user_id"],
                owner["conversation_id"],
                turn_id,
                json.dumps(message_metadata or {}),
                f"request-{turn_id}",
                source_assistant_id,
                json.dumps(expected_source_metadata),
                option_id,
                json.dumps(replacement_values),
            ),
        )
        row = cursor.fetchone()
    if row is None:
        return None
    return {
        "message": row[0],
        "lifecycle": row[1],
        "replayed": row[2],
        "source_message": row[3],
    }


def _accept_option_retry(
    connection,
    owner: dict[str, str],
    *,
    request_message_id: str,
    turn_id: str,
    request_id: str,
) -> dict[str, object] | None:
    metadata = {
        "agent_runtime_turn": {"request_id": request_id},
        "mentions": [{"id": "tampered"}],
        "chat_action": {
            "type": "select_response_option",
            "payload": {
                "request_message_id": request_message_id,
                "source_assistant_id": _id(),
                "option_id": "tampered",
                "replacement_values": {"timeframe": "5m"},
            },
        },
    }
    with connection.cursor() as cursor:
        cursor.execute(
            "select * from public.accept_chat_turn("
            " %s, %s, %s, 'user', 'tampered content', %s::jsonb,"
            " now(), 'tampered preview', %s, %s, %s::jsonb, %s, %s::jsonb,"
            " %s)",
            (
                owner["user_id"],
                owner["conversation_id"],
                turn_id,
                json.dumps(metadata),
                request_id,
                _id(),
                json.dumps({"tampered": True}),
                "tampered",
                json.dumps({"timeframe": "5m"}),
                request_message_id,
            ),
        )
        row = cursor.fetchone()
    if row is None:
        return None
    return {
        "message": row[0],
        "lifecycle": row[1],
        "replayed": row[2],
        "source_message": row[3],
    }


def _append_option_source(
    connection,
    owner: dict[str, str],
) -> tuple[str, dict[str, object]]:
    source_id = _id()
    metadata: dict[str, object] = {
        "clarification": {
            "options": [
                {
                    "id": "daily",
                    "replacement_values": {"timeframe": "1D"},
                }
            ]
        }
    }
    with connection.cursor() as cursor:
        cursor.execute(
            "select * from public.append_conversation_message("
            " %s, %s, %s, 'assistant', 'Choose bars', %s::jsonb,"
            " now(), 'Choose bars', null, null, null, null)",
            (
                owner["user_id"],
                owner["conversation_id"],
                source_id,
                json.dumps(metadata),
            ),
        )
        assert cursor.fetchone() is not None
    return source_id, metadata


def _append_terminal(
    connection,
    owner: dict[str, str],
    *,
    turn_id: str,
    request_id: str,
    status: str,
    message_id: str | None = None,
    failure_code: object = None,
    retryable: object = False,
    include_failure_code: bool = True,
    include_retryable: bool = True,
) -> str:
    message_id = message_id or _id()
    runtime_turn = {
        "turn_id": turn_id,
        "request_id": request_id,
        "terminal": True,
        "status": status,
    }
    if include_failure_code:
        runtime_turn["failure_code"] = failure_code
    if include_retryable:
        runtime_turn["retryable"] = retryable
    metadata = {"agent_runtime_turn": runtime_turn}
    with connection.cursor() as cursor:
        cursor.execute(
            "select * from public.append_conversation_message("
            " %s, %s, %s, 'assistant', 'terminal response', %s::jsonb,"
            " now(), 'terminal response', null, null, null, null)",
            (
                owner["user_id"],
                owner["conversation_id"],
                message_id,
                json.dumps(metadata),
            ),
        )
        assert cursor.fetchone() is not None
    return message_id


def _transition(
    connection,
    *,
    turn_id: str,
    status: str,
    assistant_message_id: str | None = None,
    reconciled_outcome: str | None = None,
    failure_code: str | None = None,
    retryable: bool | None = None,
) -> dict[str, object]:
    with connection.cursor() as cursor:
        cursor.execute(
            "select public.transition_chat_turn(%s, %s, %s, %s, %s, %s)",
            (
                turn_id,
                status,
                assistant_message_id,
                reconciled_outcome,
                failure_code,
                retryable,
            ),
        )
        result = cursor.fetchone()[0]
    assert isinstance(result, dict)
    return result


def _finalize(
    connection,
    owner: dict[str, str],
    *,
    turn_id: str,
    request_id: str,
    message_id: str | None = None,
    status: str = "completed",
    failure_code: str | None = None,
    retryable: bool = False,
    content: str = "terminal response",
    usage_resource: str | None = None,
    usage_limits: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    message_id = message_id or _id()
    runtime_turn: dict[str, object] = {
        "turn_id": turn_id,
        "request_id": request_id,
        "status": status,
        "terminal": True,
    }
    if status == "recoverable_failed":
        runtime_turn.update(
            failure_code=failure_code,
            retryable=retryable,
        )
    with connection.cursor() as cursor:
        cursor.execute(
            "select * from public.finalize_chat_turn("
            " %s, %s, %s, %s, %s, 'assistant', %s,"
            " %s::jsonb, now(), %s, %s, %s, %s, %s, %s::jsonb)",
            (
                owner["user_id"],
                owner["conversation_id"],
                turn_id,
                request_id,
                message_id,
                content,
                json.dumps({"agent_runtime_turn": runtime_turn}),
                content,
                status,
                failure_code,
                retryable,
                usage_resource,
                json.dumps(usage_limits) if usage_limits is not None else None,
            ),
        )
        row = cursor.fetchone()
    assert row is not None
    return {"message": row[0]}


def _age_turn(connection, turn_id: str, *, minutes: int = 30) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "update public.chat_turn_lifecycles"
            " set accepted_at = now() - make_interval(mins => %s),"
            " updated_at = now() - make_interval(mins => %s)"
            " where turn_id = %s",
            (minutes, minutes, turn_id),
        )


def _reconcile(connection, owner: dict[str, str]) -> list[dict[str, object]]:
    with connection.cursor() as cursor:
        cursor.execute(
            "select * from public.reconcile_stale_chat_turns(%s, %s)",
            (owner["conversation_id"], owner["user_id"]),
        )
        return [row[0] for row in cursor.fetchall()]


def test_acceptance_commits_message_and_lifecycle_once(owner) -> None:
    with _connect() as connection:
        turn_id = _id()
        first = _accept(connection, owner, turn_id=turn_id)
        replay = _accept(connection, owner, turn_id=turn_id)

        assert first["replayed"] is False
        assert replay["replayed"] is True
        assert first["message"]["id"] == turn_id
        assert first["lifecycle"]["turn_id"] == turn_id
        assert first["lifecycle"]["status"] == "accepted"
        with connection.cursor() as cursor:
            cursor.execute(
                "select (select count(*) from public.messages where id = %s),"
                " (select count(*) from public.chat_turn_lifecycles"
                " where turn_id = %s)",
                (turn_id, turn_id),
            )
            assert cursor.fetchone() == (1, 1)


def test_response_option_acceptance_is_atomic_and_rejects_replay_or_tampering(
    owner,
) -> None:
    with _connect() as connection:
        source_id, source_metadata = _append_option_source(connection, owner)
        valid = _accept_option(
            connection,
            owner,
            source_assistant_id=source_id,
            expected_source_metadata=source_metadata,
            option_id="daily",
            replacement_values={"timeframe": "1D"},
        )
        assert valid is not None
        assert valid["source_message"]["id"] == source_id
        assert valid["message"]["id"] == valid["lifecycle"]["turn_id"]

        rejected_turn_ids: list[str] = []

        replayed_turn = _id()
        rejected_turn_ids.append(replayed_turn)
        assert (
            _accept_option(
                connection,
                owner,
                source_assistant_id=source_id,
                expected_source_metadata=source_metadata,
                option_id="daily",
                replacement_values={"timeframe": "1D"},
                turn_id=replayed_turn,
            )
            is None
        )

        tampered_source_id, tampered_source_metadata = _append_option_source(
            connection,
            owner,
        )
        tampered_turn = _id()
        rejected_turn_ids.append(tampered_turn)
        assert (
            _accept_option(
                connection,
                owner,
                source_assistant_id=tampered_source_id,
                expected_source_metadata={
                    **tampered_source_metadata,
                    "injected": True,
                },
                option_id="daily",
                replacement_values={"timeframe": "1D"},
                turn_id=tampered_turn,
            )
            is None
        )

        mismatch_source_id, mismatch_source_metadata = _append_option_source(
            connection,
            owner,
        )
        mismatch_turn = _id()
        rejected_turn_ids.append(mismatch_turn)
        assert (
            _accept_option(
                connection,
                owner,
                source_assistant_id=mismatch_source_id,
                expected_source_metadata=mismatch_source_metadata,
                option_id="daily",
                replacement_values={"timeframe": "5m"},
                turn_id=mismatch_turn,
            )
            is None
        )

        stale_source_id, stale_source_metadata = _append_option_source(
            connection,
            owner,
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "select * from public.append_conversation_message("
                " %s, %s, %s, 'assistant', 'Later message', '{}'::jsonb,"
                " now(), 'Later message', null, null, null, null)",
                (owner["user_id"], owner["conversation_id"], _id()),
            )
            assert cursor.fetchone() is not None
        stale_turn = _id()
        rejected_turn_ids.append(stale_turn)
        assert (
            _accept_option(
                connection,
                owner,
                source_assistant_id=stale_source_id,
                expected_source_metadata=stale_source_metadata,
                option_id="daily",
                replacement_values={"timeframe": "1D"},
                turn_id=stale_turn,
            )
            is None
        )

        foreign = _seed_owner(connection)
        foreign_source_id, foreign_metadata = _append_option_source(
            connection,
            foreign,
        )
        injected_turn = _id()
        rejected_turn_ids.append(injected_turn)
        assert (
            _accept_option(
                connection,
                owner,
                source_assistant_id=foreign_source_id,
                expected_source_metadata=foreign_metadata,
                option_id="daily",
                replacement_values={"timeframe": "1D"},
                turn_id=injected_turn,
            )
            is None
        )

        failing_source_id, failing_source_metadata = _append_option_source(
            connection,
            owner,
        )
        failing_turn = _id()
        rejected_turn_ids.append(failing_turn)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                create function pg_temp.reject_option_lifecycle_insert()
                returns trigger
                language plpgsql
                as $$
                begin
                  raise exception 'forced option lifecycle insert failure';
                end;
                $$
                """
            )
            cursor.execute(
                """
                create trigger task5_force_option_lifecycle_insert_failure
                before insert on public.chat_turn_lifecycles
                for each row execute function
                  pg_temp.reject_option_lifecycle_insert()
                """
            )
        try:
            with pytest.raises(
                psycopg.errors.DatabaseError,
                match="forced option lifecycle insert failure",
            ):
                _accept_option(
                    connection,
                    owner,
                    source_assistant_id=failing_source_id,
                    expected_source_metadata=failing_source_metadata,
                    option_id="daily",
                    replacement_values={"timeframe": "1D"},
                    turn_id=failing_turn,
                )
        finally:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    drop trigger if exists
                      task5_force_option_lifecycle_insert_failure
                    on public.chat_turn_lifecycles
                    """
                )

        with connection.cursor() as cursor:
            cursor.execute(
                "select count(*) from public.messages where id = any(%s::uuid[])",
                (rejected_turn_ids,),
            )
            assert cursor.fetchone()[0] == 0
            cursor.execute(
                "select count(*) from public.chat_turn_lifecycles"
                " where turn_id = any(%s::uuid[])",
                (rejected_turn_ids,),
            )
            assert cursor.fetchone()[0] == 0


def test_response_option_retry_is_server_owned_atomic_and_idempotent(owner) -> None:
    with _connect() as connection:
        source_id, source_metadata = _append_option_source(connection, owner)
        original_turn_id = _id()
        canonical_action = {
            "type": "select_response_option",
            "label": "Use daily bars",
            "payload": {
                "option_id": "daily",
                "replacement_values": {"timeframe": "1D"},
            },
            "presentation": None,
        }
        original = _accept_option(
            connection,
            owner,
            source_assistant_id=source_id,
            expected_source_metadata=source_metadata,
            option_id="daily",
            replacement_values={"timeframe": "1D"},
            turn_id=original_turn_id,
            message_metadata={"chat_action": canonical_action},
        )
        assert original is not None
        _finalize(
            connection,
            owner,
            turn_id=original_turn_id,
            request_id=f"request-{original_turn_id}",
            status="recoverable_failed",
            failure_code="runtime_failure",
            retryable=True,
        )

        retry_turn_id = _id()
        accepted = _accept_option_retry(
            connection,
            owner,
            request_message_id=original_turn_id,
            turn_id=retry_turn_id,
            request_id=f"request-{retry_turn_id}",
        )
        assert accepted is not None
        assert accepted["replayed"] is False
        assert accepted["source_message"]["id"] == source_id
        assert accepted["message"]["content"] == "Use daily bars"
        assert accepted["message"]["metadata"] == {
            "agent_runtime_turn": {"request_id": f"request-{retry_turn_id}"},
            "chat_action": canonical_action,
        }
        assert accepted["lifecycle"]["status"] == "accepted"

        replay = _accept_option_retry(
            connection,
            owner,
            request_message_id=original_turn_id,
            turn_id=retry_turn_id,
            request_id=f"request-{retry_turn_id}",
        )
        competing_turn_id = _id()
        competing = _accept_option_retry(
            connection,
            owner,
            request_message_id=original_turn_id,
            turn_id=competing_turn_id,
            request_id=f"request-{competing_turn_id}",
        )
        assert replay is not None
        assert replay["replayed"] is True
        assert replay["message"]["id"] == retry_turn_id
        assert competing is None

        with connection.cursor() as cursor:
            cursor.execute(
                "select status, retryable from public.chat_turn_lifecycles"
                " where turn_id = %s",
                (original_turn_id,),
            )
            assert cursor.fetchone() == ("recoverable_failed", True)
            cursor.execute(
                "select count(*) from public.messages where id = any(%s::uuid[])",
                ([retry_turn_id, competing_turn_id],),
            )
            assert cursor.fetchone()[0] == 1
            cursor.execute(
                "select count(*) from public.chat_turn_lifecycles"
                " where turn_id = any(%s::uuid[])",
                ([retry_turn_id, competing_turn_id],),
            )
            assert cursor.fetchone()[0] == 1


@pytest.mark.parametrize(
    "rejection_case",
    [
        "foreign_owner",
        "foreign_conversation",
        "completed",
        "nonretryable",
        "superseded",
    ],
)
def test_response_option_retry_rejections_are_side_effect_free(
    owner,
    rejection_case: str,
) -> None:
    with _connect() as connection:
        source_id, source_metadata = _append_option_source(connection, owner)
        original_turn_id = _id()
        original = _accept_option(
            connection,
            owner,
            source_assistant_id=source_id,
            expected_source_metadata=source_metadata,
            option_id="daily",
            replacement_values={"timeframe": "1D"},
            turn_id=original_turn_id,
            message_metadata={
                "chat_action": {
                    "type": "select_response_option",
                    "label": "Use daily bars",
                    "payload": {
                        "option_id": "daily",
                        "replacement_values": {"timeframe": "1D"},
                    },
                }
            },
        )
        assert original is not None
        status = (
            "completed" if rejection_case == "completed" else "recoverable_failed"
        )
        _finalize(
            connection,
            owner,
            turn_id=original_turn_id,
            request_id=f"request-{original_turn_id}",
            status=status,
            failure_code=(
                "runtime_failure" if status == "recoverable_failed" else None
            ),
            retryable=rejection_case not in {"completed", "nonretryable"},
        )
        if rejection_case == "superseded":
            _accept(connection, owner)

        retry_owner = owner
        if rejection_case in {"foreign_owner", "foreign_conversation"}:
            foreign = _seed_owner(connection)
            retry_owner = (
                {
                    "user_id": foreign["user_id"],
                    "conversation_id": owner["conversation_id"],
                }
                if rejection_case == "foreign_owner"
                else {
                    "user_id": owner["user_id"],
                    "conversation_id": foreign["conversation_id"],
                }
            )
        retry_turn_id = _id()
        with connection.cursor() as cursor:
            cursor.execute(
                "select count(*) from public.usage_counters"
                " where user_id = %s",
                (retry_owner["user_id"],),
            )
            usage_before = cursor.fetchone()[0]

        rejected = _accept_option_retry(
            connection,
            retry_owner,
            request_message_id=original_turn_id,
            turn_id=retry_turn_id,
            request_id=f"request-{retry_turn_id}",
        )

        assert rejected is None
        with connection.cursor() as cursor:
            cursor.execute(
                "select (select count(*) from public.messages where id = %s),"
                " (select count(*) from public.chat_turn_lifecycles"
                " where turn_id = %s),"
                " (select count(*) from public.usage_counters"
                " where user_id = %s)",
                (retry_turn_id, retry_turn_id, retry_owner["user_id"]),
            )
            assert cursor.fetchone() == (0, 0, usage_before)


def test_terminal_finalization_rolls_back_message_when_transition_fails(
    owner,
) -> None:
    with _connect() as connection:
        accepted = _accept(connection, owner)
        turn_id = str(accepted["message"]["id"])
        request_id = str(accepted["lifecycle"]["request_id"])
        assistant_id = _id()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                create function pg_temp.reject_lifecycle_terminal()
                returns trigger
                language plpgsql
                as $$
                begin
                  raise exception 'forced lifecycle terminal failure';
                end;
                $$
                """
            )
            cursor.execute(
                """
                create trigger task5_force_lifecycle_terminal_failure
                before update on public.chat_turn_lifecycles
                for each row execute function pg_temp.reject_lifecycle_terminal()
                """
            )
        try:
            with pytest.raises(
                psycopg.errors.DatabaseError,
                match="forced lifecycle terminal failure",
            ):
                _finalize(
                    connection,
                    owner,
                    turn_id=turn_id,
                    request_id=request_id,
                    message_id=assistant_id,
                )
        finally:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    drop trigger if exists
                      task5_force_lifecycle_terminal_failure
                    on public.chat_turn_lifecycles
                    """
                )
        with connection.cursor() as cursor:
            cursor.execute(
                "select (select count(*) from public.messages where id = %s),"
                " (select status from public.chat_turn_lifecycles"
                " where turn_id = %s)",
                (assistant_id, turn_id),
            )
            assert cursor.fetchone() == (0, "accepted")


def test_completed_finalization_exact_replay_is_noop_without_duplicate_usage(
    owner,
) -> None:
    with _connect() as connection:
        accepted = _accept(connection, owner)
        turn_id = str(accepted["message"]["id"])
        request_id = str(accepted["lifecycle"]["request_id"])
        assistant_id = _id()
        first = _finalize(
            connection,
            owner,
            turn_id=turn_id,
            request_id=request_id,
            message_id=assistant_id,
            usage_resource="chat_messages",
            usage_limits=[
                {"period": "hour", "limit": 60},
                {"period": "day", "limit": 200},
            ],
        )
        replay = _finalize(
            connection,
            owner,
            turn_id=turn_id,
            request_id=request_id,
            message_id=assistant_id,
            usage_resource="chat_messages",
            usage_limits=[
                {"period": "hour", "limit": 61},
                {"period": "day", "limit": 201},
            ],
        )

        assert replay == first
        with connection.cursor() as cursor:
            cursor.execute(
                "select (select count(*) from public.messages where id = %s),"
                " array_agg((period, used_count)::text order by period)"
                " from public.usage_counters"
                " where user_id = %s and resource = 'chat_messages'",
                (assistant_id, owner["user_id"]),
            )
            message_count, usage = cursor.fetchone()
        assert message_count == 1
        assert usage == ['(day,1)', '(hour,1)']

        with pytest.raises(
            psycopg.errors.DatabaseError,
            match="Chat-turn finalization conflict",
        ):
            _finalize(
                connection,
                owner,
                turn_id=turn_id,
                request_id=request_id,
                message_id=assistant_id,
                content="changed terminal response",
                usage_resource="chat_messages",
                usage_limits=[
                    {"period": "hour", "limit": 60},
                    {"period": "day", "limit": 200},
                ],
            )


def test_recoverable_finalization_exact_replay_is_noop_and_tuple_is_strict(
    owner,
) -> None:
    with _connect() as connection:
        accepted = _accept(connection, owner)
        turn_id = str(accepted["message"]["id"])
        request_id = str(accepted["lifecycle"]["request_id"])
        assistant_id = _id()
        first = _finalize(
            connection,
            owner,
            turn_id=turn_id,
            request_id=request_id,
            message_id=assistant_id,
            status="recoverable_failed",
            failure_code="runtime_failure",
            retryable=True,
        )
        replay = _finalize(
            connection,
            owner,
            turn_id=turn_id,
            request_id=request_id,
            message_id=assistant_id,
            status="recoverable_failed",
            failure_code="runtime_failure",
            retryable=True,
        )

        assert replay == first
        with connection.cursor() as cursor:
            cursor.execute(
                "select (select count(*) from public.messages where id = %s),"
                " (select count(*) from public.usage_counters"
                " where user_id = %s)",
                (assistant_id, owner["user_id"]),
            )
            assert cursor.fetchone() == (1, 0)

        with pytest.raises(
            psycopg.errors.DatabaseError,
            match="Chat-turn terminal payload is invalid",
        ):
            _finalize(
                connection,
                owner,
                turn_id=turn_id,
                request_id=request_id,
                message_id=assistant_id,
                status="recoverable_failed",
                failure_code="runtime_failure",
                retryable=True,
                usage_resource="chat_messages",
                usage_limits=[
                    {"period": "hour", "limit": 60},
                    {"period": "day", "limit": 200},
                ],
            )
        with connection.cursor() as cursor:
            cursor.execute(
                "select count(*) from public.usage_counters"
                " where user_id = %s",
                (owner["user_id"],),
            )
            assert cursor.fetchone()[0] == 0

        with pytest.raises(
            psycopg.errors.DatabaseError,
            match="Chat-turn finalization conflict",
        ):
            _finalize(
                connection,
                owner,
                turn_id=turn_id,
                request_id=request_id,
                message_id=assistant_id,
                status="recoverable_failed",
                failure_code="different_failure",
                retryable=True,
            )


def test_finalizer_lock_wins_over_stale_reconciliation(owner) -> None:
    with _connect() as seed:
        accepted = _accept(seed, owner)
        turn_id = str(accepted["message"]["id"])
        request_id = str(accepted["lifecycle"]["request_id"])
        _age_turn(seed, turn_id)

    with _connect() as finalizer, _connect() as reconciler:
        finalizer.autocommit = False
        with finalizer.cursor() as cursor:
            cursor.execute(
                "select turn_id from public.chat_turn_lifecycles"
                " where turn_id = %s for update",
                (turn_id,),
            )
        assert _reconcile(reconciler, owner) == []
        result = _finalize(
            finalizer,
            owner,
            turn_id=turn_id,
            request_id=request_id,
        )
        finalizer.commit()

    assert result["message"]["id"] is not None
    with _connect() as check:
        with check.cursor() as cursor:
            cursor.execute(
                "select status, assistant_message_id is not null"
                " from public.chat_turn_lifecycles where turn_id = %s",
                (turn_id,),
            )
            assert cursor.fetchone() == ("completed", True)


def test_stale_reconciliation_lock_wins_over_terminal_finalizer(owner) -> None:
    with _connect() as seed:
        accepted = _accept(seed, owner)
        turn_id = str(accepted["message"]["id"])
        request_id = str(accepted["lifecycle"]["request_id"])
        _age_turn(seed, turn_id)

    started = Event()

    def finalize_after_lock() -> str:
        with _connect() as connection:
            started.set()
            with pytest.raises(
                psycopg.errors.DatabaseError,
                match="Chat-turn finalization conflict",
            ):
                _finalize(
                    connection,
                    owner,
                    turn_id=turn_id,
                    request_id=request_id,
                )
        return "conflict"

    with _connect() as reconciler:
        reconciler.autocommit = False
        with reconciler.cursor() as cursor:
            cursor.execute(
                "select turn_id from public.chat_turn_lifecycles"
                " where turn_id = %s for update",
                (turn_id,),
            )
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(finalize_after_lock)
            assert started.wait(1)
            [row] = _reconcile(reconciler, owner)
            assert row["status"] == "abandoned"
            reconciler.commit()
            assert future.result(timeout=5) == "conflict"

    with _connect() as check:
        with check.cursor() as cursor:
            cursor.execute(
                "select status, assistant_message_id,"
                " (select count(*) from public.messages"
                " where metadata #>> '{agent_runtime_turn,turn_id}' = %s)"
                " from public.chat_turn_lifecycles where turn_id = %s",
                (turn_id, turn_id),
            )
            assert cursor.fetchone() == ("abandoned", None, 0)


def test_acceptance_rolls_back_message_when_lifecycle_insert_fails(
    owner,
) -> None:
    with _connect() as connection:
        turn_id = _id()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                create function pg_temp.reject_lifecycle_insert()
                returns trigger
                language plpgsql
                as $$
                begin
                  raise exception 'forced lifecycle insert failure';
                end;
                $$
                """
            )
            cursor.execute(
                """
                create trigger task4_force_lifecycle_insert_failure
                before insert on public.chat_turn_lifecycles
                for each row execute function pg_temp.reject_lifecycle_insert()
                """
            )
        try:
            with pytest.raises(psycopg.errors.DatabaseError):
                _accept(connection, owner, turn_id=turn_id)
        finally:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    drop trigger if exists
                      task4_force_lifecycle_insert_failure
                    on public.chat_turn_lifecycles
                    """
                )
        with connection.cursor() as cursor:
            cursor.execute(
                "select (select count(*) from public.messages where id = %s),"
                " (select count(*) from public.chat_turn_lifecycles"
                " where turn_id = %s)",
                (turn_id, turn_id),
            )
            assert cursor.fetchone() == (0, 0)


def test_acceptance_rejects_a_foreign_conversation_without_writes(
    owner,
) -> None:
    with _connect() as connection:
        foreign = _seed_owner(connection)
        turn_id = _id()
        with pytest.raises(psycopg.errors.DatabaseError):
            _accept(
                connection,
                {
                    "user_id": owner["user_id"],
                    "conversation_id": foreign["conversation_id"],
                },
                turn_id=turn_id,
            )
        with connection.cursor() as cursor:
            cursor.execute(
                "select count(*) from public.messages where id = %s",
                (turn_id,),
            )
            assert cursor.fetchone()[0] == 0


def test_transition_is_null_safe_idempotent_and_terminal(owner) -> None:
    with _connect() as connection:
        accepted = _accept(connection, owner)
        turn_id = str(accepted["message"]["id"])
        request_id = str(accepted["lifecycle"]["request_id"])
        assistant_id = _append_terminal(
            connection,
            owner,
            turn_id=turn_id,
            request_id=request_id,
            status="completed",
        )
        applied = _transition(
            connection,
            turn_id=turn_id,
            status="completed",
            assistant_message_id=assistant_id,
        )
        replay = _transition(
            connection,
            turn_id=turn_id,
            status="completed",
            assistant_message_id=assistant_id,
        )
        other_assistant_id = _append_terminal(
            connection,
            owner,
            turn_id=turn_id,
            request_id=request_id,
            status="completed",
        )
        conflict = _transition(
            connection,
            turn_id=turn_id,
            status="completed",
            assistant_message_id=other_assistant_id,
        )

        assert applied["outcome"] == "applied"
        assert replay["outcome"] == "noop"
        assert conflict["outcome"] == "conflict"
        assert conflict["row"] == applied["row"]


@pytest.mark.parametrize(
    ("status", "reconciled_outcome"),
    [
        ("recoverable_failed", None),
        ("reconciled", "recoverable_failed"),
    ],
)
@pytest.mark.parametrize(
    (
        "include_failure_code",
        "include_retryable",
        "evidence_failure_code",
        "evidence_retryable",
        "caller_failure_code",
        "caller_retryable",
    ),
    [
        (False, True, "runtime_failure", True, "runtime_failure", True),
        (True, False, "runtime_failure", True, "runtime_failure", True),
        (True, True, "durable_failure", True, "caller_failure", True),
        (True, True, "runtime_failure", True, "runtime_failure", False),
        pytest.param(
            True,
            True,
            7,
            True,
            "7",
            True,
            id="numeric-json-failure-code-text-match",
        ),
    ],
)
def test_recoverable_failure_evidence_fields_are_required_and_exact(
    owner,
    status: str,
    reconciled_outcome: str | None,
    include_failure_code: bool,
    include_retryable: bool,
    evidence_failure_code: object,
    evidence_retryable: bool,
    caller_failure_code: str,
    caller_retryable: bool,
) -> None:
    with _connect() as connection:
        accepted = _accept(connection, owner)
        turn_id = str(accepted["message"]["id"])
        request_id = str(accepted["lifecycle"]["request_id"])
        assistant_id = _append_terminal(
            connection,
            owner,
            turn_id=turn_id,
            request_id=request_id,
            status="recoverable_failed",
            failure_code=evidence_failure_code,
            retryable=evidence_retryable,
            include_failure_code=include_failure_code,
            include_retryable=include_retryable,
        )

        result = _transition(
            connection,
            turn_id=turn_id,
            status=status,
            assistant_message_id=assistant_id,
            reconciled_outcome=reconciled_outcome,
            failure_code=caller_failure_code,
            retryable=caller_retryable,
        )

        assert result["outcome"] == "invalid"
        assert result["row"]["status"] == "accepted"
        with connection.cursor() as cursor:
            cursor.execute(
                "select status, assistant_message_id, failure_code, retryable"
                " from public.chat_turn_lifecycles where turn_id = %s",
                (turn_id,),
            )
            assert cursor.fetchone() == ("accepted", None, None, False)


@pytest.mark.parametrize(
    ("status", "reconciled_outcome"),
    [
        ("recoverable_failed", None),
        ("reconciled", "recoverable_failed"),
    ],
)
def test_recoverable_failure_evidence_matches_null_safely(
    owner,
    status: str,
    reconciled_outcome: str | None,
) -> None:
    with _connect() as connection:
        accepted = _accept(connection, owner)
        turn_id = str(accepted["message"]["id"])
        request_id = str(accepted["lifecycle"]["request_id"])
        assistant_id = _append_terminal(
            connection,
            owner,
            turn_id=turn_id,
            request_id=request_id,
            status="recoverable_failed",
            failure_code=None,
            retryable=False,
        )

        result = _transition(
            connection,
            turn_id=turn_id,
            status=status,
            assistant_message_id=assistant_id,
            reconciled_outcome=reconciled_outcome,
            failure_code=None,
            retryable=None,
        )

        assert result["outcome"] == "applied"
        assert result["row"]["failure_code"] is None
        assert result["row"]["retryable"] is False


def test_late_success_cannot_overwrite_terminal_failure(owner) -> None:
    with _connect() as connection:
        accepted = _accept(connection, owner)
        turn_id = str(accepted["message"]["id"])
        request_id = str(accepted["lifecycle"]["request_id"])
        failure_id = _append_terminal(
            connection,
            owner,
            turn_id=turn_id,
            request_id=request_id,
            status="recoverable_failed",
            failure_code="runtime_failure",
            retryable=True,
        )
        failed = _transition(
            connection,
            turn_id=turn_id,
            status="recoverable_failed",
            assistant_message_id=failure_id,
            failure_code="runtime_failure",
            retryable=True,
        )
        success_id = _append_terminal(
            connection,
            owner,
            turn_id=turn_id,
            request_id=request_id,
            status="completed",
        )
        late = _transition(
            connection,
            turn_id=turn_id,
            status="completed",
            assistant_message_id=success_id,
        )

        assert failed["outcome"] == "applied"
        assert late["outcome"] == "conflict"
        assert late["row"]["status"] == "recoverable_failed"
        assert late["row"]["assistant_message_id"] == failure_id


def test_reconciliation_prefers_failure_on_equal_timestamp(owner) -> None:
    with _connect() as connection:
        accepted = _accept(connection, owner)
        turn_id = str(accepted["message"]["id"])
        request_id = str(accepted["lifecycle"]["request_id"])
        _age_turn(connection, turn_id)
        completed_id = _append_terminal(
            connection,
            owner,
            turn_id=turn_id,
            request_id=request_id,
            status="completed",
        )
        failure_id = _append_terminal(
            connection,
            owner,
            turn_id=turn_id,
            request_id=request_id,
            status="recoverable_failed",
            failure_code="runtime_failure",
            retryable=True,
        )
        tied_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        with connection.cursor() as cursor:
            cursor.execute(
                "update public.messages set created_at = %s"
                " where id in (%s, %s)",
                (tied_at, completed_id, failure_id),
            )

        [row] = _reconcile(connection, owner)

        assert row["status"] == "reconciled"
        assert row["reconciled_outcome"] == "recoverable_failed"
        assert row["assistant_message_id"] == failure_id
        assert row["failure_code"] == "runtime_failure"
        assert row["retryable"] is True


def test_reconciliation_skips_malformed_failure_for_later_valid_evidence(
    owner,
) -> None:
    with _connect() as connection:
        accepted = _accept(connection, owner)
        turn_id = str(accepted["message"]["id"])
        request_id = str(accepted["lifecycle"]["request_id"])
        _age_turn(connection, turn_id)
        malformed_id = _append_terminal(
            connection,
            owner,
            turn_id=turn_id,
            request_id=request_id,
            status="recoverable_failed",
            failure_code="malformed_failure",
            retryable=True,
            include_failure_code=False,
        )
        valid_id = _append_terminal(
            connection,
            owner,
            turn_id=turn_id,
            request_id=request_id,
            status="recoverable_failed",
            failure_code="durable_failure",
            retryable=True,
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "update public.messages set created_at = case id"
                " when %s then now() - interval '2 minutes'"
                " when %s then now() - interval '1 minute' end"
                " where id in (%s, %s)",
                (malformed_id, valid_id, malformed_id, valid_id),
            )

        [row] = _reconcile(connection, owner)

        assert row["status"] == "reconciled"
        assert row["assistant_message_id"] == valid_id
        assert row["reconciled_outcome"] == "recoverable_failed"
        assert row["failure_code"] == "durable_failure"
        assert row["retryable"] is True


@pytest.mark.parametrize(
    (
        "failure_code",
        "retryable",
        "include_failure_code",
        "include_retryable",
    ),
    [
        ("runtime_failure", True, False, True),
        ("runtime_failure", True, True, False),
        (7, True, True, True),
        ("runtime_failure", "yes", True, True),
    ],
)
def test_reconciliation_abandons_when_only_failure_evidence_is_malformed(
    owner,
    failure_code: object,
    retryable: object,
    include_failure_code: bool,
    include_retryable: bool,
) -> None:
    with _connect() as connection:
        accepted = _accept(connection, owner)
        turn_id = str(accepted["message"]["id"])
        request_id = str(accepted["lifecycle"]["request_id"])
        _age_turn(connection, turn_id)
        _append_terminal(
            connection,
            owner,
            turn_id=turn_id,
            request_id=request_id,
            status="recoverable_failed",
            failure_code=failure_code,
            retryable=retryable,
            include_failure_code=include_failure_code,
            include_retryable=include_retryable,
        )

        [row] = _reconcile(connection, owner)
        replay = _reconcile(connection, owner)

        assert row["status"] == "abandoned"
        assert row["assistant_message_id"] is None
        assert row["failure_code"] == "turn_abandoned"
        assert row["retryable"] is True
        assert replay == []


def test_foreign_or_mismatched_evidence_cannot_reconcile(owner) -> None:
    with _connect() as connection:
        accepted = _accept(connection, owner)
        turn_id = str(accepted["message"]["id"])
        request_id = str(accepted["lifecycle"]["request_id"])
        _age_turn(connection, turn_id)
        foreign = _seed_owner(connection)
        _append_terminal(
            connection,
            foreign,
            turn_id=turn_id,
            request_id=request_id,
            status="completed",
        )
        _append_terminal(
            connection,
            owner,
            turn_id=turn_id,
            request_id="wrong-request",
            status="completed",
        )

        [row] = _reconcile(connection, owner)

        assert row["status"] == "abandoned"
        assert row["assistant_message_id"] is None
        assert row["failure_code"] == "turn_abandoned"
        assert row["retryable"] is True


def test_reconciliation_processes_only_twenty_in_stale_order(owner) -> None:
    with _connect() as connection:
        turn_ids: list[str] = []
        for index in range(21):
            turn_id = _id()
            _accept(connection, owner, turn_id=turn_id)
            turn_ids.append(turn_id)
            with connection.cursor() as cursor:
                cursor.execute(
                    "update public.chat_turn_lifecycles"
                    " set accepted_at = %s where turn_id = %s",
                    (
                        datetime.now(timezone.utc)
                        - timedelta(minutes=40)
                        + timedelta(seconds=index),
                        turn_id,
                    ),
                )

        rows = _reconcile(connection, owner)

        assert len(rows) == 20
        assert [row["turn_id"] for row in rows] == turn_ids[:20]
        with connection.cursor() as cursor:
            cursor.execute(
                "select status from public.chat_turn_lifecycles"
                " where turn_id = %s",
                (turn_ids[-1],),
            )
            assert cursor.fetchone()[0] == "accepted"


def test_authenticated_role_can_select_only_its_rows_and_cannot_mutate(
    owner,
) -> None:
    with _connect() as connection:
        accepted = _accept(connection, owner)
        turn_id = str(accepted["message"]["id"])
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute("set local role authenticated")
                cursor.execute(
                    "select set_config('request.jwt.claim.sub', %s, true)",
                    (owner["user_id"],),
                )
                cursor.execute(
                    "select count(*) from public.chat_turn_lifecycles"
                    " where turn_id = %s",
                    (turn_id,),
                )
                assert cursor.fetchone()[0] == 1
                cursor.execute(
                    "select set_config('request.jwt.claim.sub', %s, true)",
                    (_id(),),
                )
                cursor.execute(
                    "select count(*) from public.chat_turn_lifecycles"
                    " where turn_id = %s",
                    (turn_id,),
                )
                assert cursor.fetchone()[0] == 0

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute("set local role authenticated")
                    cursor.execute(
                        "update public.chat_turn_lifecycles"
                        " set status = 'running' where turn_id = %s",
                        (turn_id,),
                    )

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute("set local role authenticated")
                    cursor.execute(
                        "select public.transition_chat_turn("
                        " %s, 'running', null, null, null, null)",
                        (turn_id,),
                    )
