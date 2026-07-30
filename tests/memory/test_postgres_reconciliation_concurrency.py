"""Real-Postgres proof for serialized memory-record reconciliation state."""

from __future__ import annotations

import os
import threading
import uuid
from collections.abc import Iterator
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
from typing import Any

import pytest

DSN = os.getenv("ARGUS_DISPOSABLE_DATABASE_URL", "").strip()
pytestmark = pytest.mark.skipif(
    not DSN,
    reason="ARGUS_DISPOSABLE_DATABASE_URL is not configured",
)
psycopg = pytest.importorskip("psycopg")


def _connect(*, autocommit: bool = True):
    return psycopg.connect(DSN, autocommit=autocommit)


@dataclass(frozen=True)
class _LifecycleState:
    owner_id: str
    candidate_id: str
    receipt_id: str
    record_id: str


def _seed_lifecycle_state(connection) -> _LifecycleState:
    suffix = uuid.uuid4().hex
    state = _LifecycleState(
        owner_id=str(uuid.uuid4()),
        candidate_id=f"candidate-{suffix}",
        receipt_id=f"receipt-{suffix}",
        record_id=f"record-{suffix}",
    )
    email = f"memory-race-{suffix[:8]}@example.com"
    with connection.cursor() as cursor:
        cursor.execute(
            "insert into auth.users (id,email,is_anonymous) values (%s,%s,false)",
            (state.owner_id, email),
        )
        cursor.execute(
            "insert into public.profiles (id,email) values (%s,%s)",
            (state.owner_id, email),
        )
        cursor.execute(
            """
            insert into public.memory_candidates (
              id,
              owner_id,
              category,
              source_label,
              source_value,
              future_benefit,
              trigger,
              proposed_context,
              opt_in_scope,
              sensitivity_status,
              sensitivity_flags,
              sensitivity_policy_version,
              sensitivity_content_digest
            )
            values (
              %s,
              %s,
              'workflow_preference',
              'Show assumptions first',
              'Show assumptions before every result explanation.',
              'Keeps future result reviews consistent.',
              'explicit_request',
              'ordinary',
              array['workflow_preference'],
              'clear',
              '{}'::text[],
              'argus.memory-sensitivity/v1',
              %s
            )
            """,
            (state.candidate_id, state.owner_id, f"sha256:{'7' * 64}"),
        )
        cursor.execute(
            """
            insert into public.memory_consent_actions (
              id,
              owner_id,
              action,
              candidate_id,
              requested_scope,
              granted_scope,
              effective_scope,
              idempotency_key
            )
            values (
              %s,
              %s,
              'candidate_confirmation',
              %s,
              array['workflow_preference'],
              array['workflow_preference'],
              array['workflow_preference'],
              %s
            )
            """,
            (
                state.receipt_id,
                state.owner_id,
                state.candidate_id,
                state.candidate_id,
            ),
        )
        _insert_record(cursor, state)
        cursor.execute(
            """
            insert into public.memory_reconciliations (
              owner_id,
              record_id,
              generation,
              operation,
              status,
              completed_at
            )
            values (%s,%s,1,'create','succeeded',now())
            """,
            (state.owner_id, state.record_id),
        )
    return state


def _insert_record(cursor, state: _LifecycleState) -> None:
    cursor.execute(
        """
        insert into public.memory_records (
          id,
          owner_id,
          candidate_id,
          consent_action_id,
          category,
          label,
          value
        )
        values (
          %s,
          %s,
          %s,
          %s,
          'workflow_preference',
          'Show assumptions first',
          'Show assumptions before every result explanation.'
        )
        """,
        (
            state.record_id,
            state.owner_id,
            state.candidate_id,
            state.receipt_id,
        ),
    )


@pytest.fixture
def lifecycle_state() -> Iterator[_LifecycleState]:
    with _connect() as connection:
        state = _seed_lifecycle_state(connection)
    try:
        yield state
    finally:
        with _connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "delete from public.memory_reconciliations where owner_id=%s",
                    (state.owner_id,),
                )
                cursor.execute(
                    "delete from auth.users where id=%s",
                    (state.owner_id,),
                )


def _run_concurrent_statement(
    query: str,
    parameters: tuple[Any, ...],
    started: threading.Event,
) -> tuple[str, str] | None:
    try:
        with _connect(autocommit=False) as connection:
            with connection.cursor() as cursor:
                cursor.execute("set local statement_timeout='5s'")
                started.set()
                cursor.execute(query, parameters)
            connection.commit()
    except psycopg.Error as error:
        return error.sqlstate or "", str(error)
    return None


def _assert_statement_waits(
    future: Future[tuple[str, str] | None],
) -> None:
    with pytest.raises(TimeoutError):
        future.result(timeout=0.3)


def _count_rows(
    connection,
    table: str,
    state: _LifecycleState,
    *,
    operation: str | None = None,
) -> int:
    query = f"select count(*) from public.{table} where owner_id=%s"
    parameters: list[str] = [state.owner_id]
    if table == "memory_records":
        query += " and id=%s"
        parameters.append(state.record_id)
    else:
        query += " and record_id=%s"
        parameters.append(state.record_id)
    if operation is not None:
        query += " and operation=%s"
        parameters.append(operation)
    with connection.cursor() as cursor:
        cursor.execute(query, parameters)
        return int(cursor.fetchone()[0])


@pytest.mark.parametrize("operation", ("create", "update"))
def test_open_record_delete_serializes_new_live_record_reconciliation(
    lifecycle_state: _LifecycleState,
    operation: str,
) -> None:
    started = threading.Event()
    with _connect(autocommit=False) as deleting:
        with deleting.cursor() as cursor:
            cursor.execute(
                "delete from public.memory_records where owner_id=%s and id=%s",
                (lifecycle_state.owner_id, lifecycle_state.record_id),
            )
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                _run_concurrent_statement,
                """
                insert into public.memory_reconciliations (
                  owner_id,record_id,generation,operation,status
                )
                values (%s,%s,2,%s,'pending')
                """,
                (
                    lifecycle_state.owner_id,
                    lifecycle_state.record_id,
                    operation,
                ),
                started,
            )
            assert started.wait(timeout=2)
            try:
                _assert_statement_waits(future)
            finally:
                deleting.commit()
            error = future.result(timeout=5)

    assert error is not None
    assert error[0] == "23514"
    assert "requires a live same-owner record" in error[1]
    with _connect() as connection:
        assert _count_rows(connection, "memory_records", lifecycle_state) == 0
        assert _count_rows(
            connection,
            "memory_reconciliations",
            lifecycle_state,
            operation=operation,
        ) == (1 if operation == "create" else 0)


def test_open_delete_reconciliation_serializes_record_resurrection(
    lifecycle_state: _LifecycleState,
) -> None:
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "delete from public.memory_records where owner_id=%s and id=%s",
                (lifecycle_state.owner_id, lifecycle_state.record_id),
            )

    started = threading.Event()
    with _connect(autocommit=False) as reconciling:
        with reconciling.cursor() as cursor:
            cursor.execute(
                """
                insert into public.memory_reconciliations (
                  owner_id,record_id,generation,operation,status
                )
                values (%s,%s,2,'delete','pending')
                """,
                (lifecycle_state.owner_id, lifecycle_state.record_id),
            )
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                _run_concurrent_statement,
                """
                insert into public.memory_records (
                  id,
                  owner_id,
                  candidate_id,
                  consent_action_id,
                  category,
                  label,
                  value
                )
                values (
                  %s,
                  %s,
                  %s,
                  %s,
                  'workflow_preference',
                  'Show assumptions first',
                  'Show assumptions before every result explanation.'
                )
                """,
                (
                    lifecycle_state.record_id,
                    lifecycle_state.owner_id,
                    lifecycle_state.candidate_id,
                    lifecycle_state.receipt_id,
                ),
                started,
            )
            assert started.wait(timeout=2)
            try:
                _assert_statement_waits(future)
            finally:
                reconciling.commit()
            error = future.result(timeout=5)

    assert error is not None
    assert error[0] == "23514"
    assert "existing delete reconciliation" in error[1]
    with _connect() as connection:
        assert _count_rows(connection, "memory_records", lifecycle_state) == 0
        assert (
            _count_rows(
                connection,
                "memory_reconciliations",
                lifecycle_state,
                operation="delete",
            )
            == 1
        )


@pytest.mark.parametrize("operation", ("create", "update"))
def test_open_live_record_reconciliation_serializes_record_delete(
    lifecycle_state: _LifecycleState,
    operation: str,
) -> None:
    started = threading.Event()
    with _connect(autocommit=False) as reconciling:
        with reconciling.cursor() as cursor:
            cursor.execute(
                """
                insert into public.memory_reconciliations (
                  owner_id,record_id,generation,operation,status
                )
                values (%s,%s,2,%s,'pending')
                """,
                (
                    lifecycle_state.owner_id,
                    lifecycle_state.record_id,
                    operation,
                ),
            )
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                _run_concurrent_statement,
                "delete from public.memory_records where owner_id=%s and id=%s",
                (lifecycle_state.owner_id, lifecycle_state.record_id),
                started,
            )
            assert started.wait(timeout=2)
            try:
                _assert_statement_waits(future)
            finally:
                reconciling.commit()
            error = future.result(timeout=5)

    assert error is not None
    assert error[0] == "23514"
    assert "unfinished provider reconciliation" in error[1]
    with _connect() as connection:
        assert _count_rows(connection, "memory_records", lifecycle_state) == 1
        assert _count_rows(
            connection,
            "memory_reconciliations",
            lifecycle_state,
            operation=operation,
        ) == (2 if operation == "create" else 1)


def test_open_record_insert_serializes_delete_reconciliation(
    lifecycle_state: _LifecycleState,
) -> None:
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "delete from public.memory_records where owner_id=%s and id=%s",
                (lifecycle_state.owner_id, lifecycle_state.record_id),
            )

    started = threading.Event()
    with _connect(autocommit=False) as creating:
        with creating.cursor() as cursor:
            _insert_record(cursor, lifecycle_state)
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                _run_concurrent_statement,
                """
                insert into public.memory_reconciliations (
                  owner_id,record_id,generation,operation,status
                )
                values (%s,%s,2,'delete','pending')
                """,
                (lifecycle_state.owner_id, lifecycle_state.record_id),
                started,
            )
            assert started.wait(timeout=2)
            try:
                _assert_statement_waits(future)
            finally:
                creating.commit()
            error = future.result(timeout=5)

    assert error is not None
    assert error[0] == "23514"
    assert "delete reconciliation requires record absence" in error[1]
    with _connect() as connection:
        assert _count_rows(connection, "memory_records", lifecycle_state) == 1
        assert (
            _count_rows(
                connection,
                "memory_reconciliations",
                lifecycle_state,
                operation="delete",
            )
            == 0
        )


def test_lifecycle_lock_releases_when_record_delete_rolls_back(
    lifecycle_state: _LifecycleState,
) -> None:
    started = threading.Event()
    with _connect(autocommit=False) as deleting:
        with deleting.cursor() as cursor:
            cursor.execute(
                "delete from public.memory_records where owner_id=%s and id=%s",
                (lifecycle_state.owner_id, lifecycle_state.record_id),
            )
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                _run_concurrent_statement,
                """
                insert into public.memory_reconciliations (
                  owner_id,record_id,generation,operation,status
                )
                values (%s,%s,2,'update','pending')
                """,
                (lifecycle_state.owner_id, lifecycle_state.record_id),
                started,
            )
            assert started.wait(timeout=2)
            try:
                _assert_statement_waits(future)
            finally:
                deleting.rollback()
            assert future.result(timeout=5) is None

    with _connect() as connection:
        assert _count_rows(connection, "memory_records", lifecycle_state) == 1
        assert (
            _count_rows(
                connection,
                "memory_reconciliations",
                lifecycle_state,
                operation="update",
            )
            == 1
        )


def test_reconciliation_update_serializes_against_open_record_delete(
    lifecycle_state: _LifecycleState,
) -> None:
    started = threading.Event()
    with _connect(autocommit=False) as deleting:
        with deleting.cursor() as cursor:
            cursor.execute(
                "delete from public.memory_records where owner_id=%s and id=%s",
                (lifecycle_state.owner_id, lifecycle_state.record_id),
            )
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                _run_concurrent_statement,
                """
                update public.memory_reconciliations
                   set status='failed',
                       error_code='projection_failed',
                       completed_at=now()
                 where owner_id=%s
                   and record_id=%s
                   and generation=1
                """,
                (lifecycle_state.owner_id, lifecycle_state.record_id),
                started,
            )
            assert started.wait(timeout=2)
            try:
                _assert_statement_waits(future)
            finally:
                deleting.commit()
            error = future.result(timeout=5)

    assert error is not None
    assert error[0] == "23514"
    assert "requires a live same-owner record" in error[1]
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select operation,status
                  from public.memory_reconciliations
                 where owner_id=%s
                   and record_id=%s
                   and generation=1
                """,
                (lifecycle_state.owner_id, lifecycle_state.record_id),
            )
            assert cursor.fetchone() == ("create", "succeeded")


@pytest.mark.parametrize("deletion_root", ("profile", "auth"))
def test_account_delete_skips_record_lock_and_cannot_deadlock_reconciliation(
    lifecycle_state: _LifecycleState,
    deletion_root: str,
) -> None:
    key = (
        f"argus:memory-record:{lifecycle_state.owner_id}:" f"{lifecycle_state.record_id}"
    )
    started = threading.Event()
    with _connect(autocommit=False) as deleting:
        with deleting.cursor() as cursor:
            if deletion_root == "profile":
                cursor.execute(
                    "delete from public.profiles where id=%s",
                    (lifecycle_state.owner_id,),
                )
            else:
                cursor.execute(
                    "delete from auth.users where id=%s",
                    (lifecycle_state.owner_id,),
                )

        with _connect() as probing:
            with probing.cursor() as cursor:
                cursor.execute(
                    """
                    select pg_catalog.pg_try_advisory_xact_lock(
                      pg_catalog.hashtextextended(%s,0)
                    )
                    """,
                    (key,),
                )
                assert cursor.fetchone() == (True,)

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                _run_concurrent_statement,
                """
                insert into public.memory_reconciliations (
                  owner_id,record_id,generation,operation,status
                )
                values (%s,%s,2,'update','pending')
                """,
                (lifecycle_state.owner_id, lifecycle_state.record_id),
                started,
            )
            assert started.wait(timeout=2)
            try:
                _assert_statement_waits(future)
            finally:
                deleting.commit()
            error = future.result(timeout=5)

    assert error is not None
    assert error[0] != "40P01"
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select count(*)
                  from public.memory_reconciliations
                 where owner_id=%s
                """,
                (lifecycle_state.owner_id,),
            )
            assert cursor.fetchone() == (0,)


def test_lifecycle_lock_is_private_fixed_path_and_fail_closed() -> None:
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select p.prosecdef,p.proconfig
                  from pg_catalog.pg_proc as p
                  join pg_catalog.pg_namespace as n on n.oid=p.pronamespace
                 where n.nspname='argus_private'
                   and p.proname='lock_memory_record_lifecycle'
                """
            )
            assert cursor.fetchone() == (True, ['search_path=""'])
            for role_name in ("anon", "authenticated", "service_role"):
                cursor.execute(
                    """
                    select has_function_privilege(
                      %s,
                      'argus_private.lock_memory_record_lifecycle()',
                      'execute'
                    )
                    """,
                    (role_name,),
                )
                assert cursor.fetchone() == (False,)

            cursor.execute(
                """
                create temporary table unexpected_memory_lifecycle (
                  owner_id uuid not null,
                  id text not null
                )
                """
            )
            cursor.execute(
                """
                create trigger lock_unexpected_memory_lifecycle
                before insert on unexpected_memory_lifecycle
                for each row execute function
                  argus_private.lock_memory_record_lifecycle()
                """
            )
            with pytest.raises(
                psycopg.errors.CheckViolation,
                match="unsupported memory record lifecycle target",
            ):
                cursor.execute(
                    """
                    insert into unexpected_memory_lifecycle (owner_id,id)
                    values (%s,'unexpected')
                    """,
                    (str(uuid.uuid4()),),
                )
