"""Real-Postgres proof for reconciliation-safe memory deletion."""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest

DSN = os.getenv("ARGUS_DISPOSABLE_DATABASE_URL", "").strip()
pytestmark = pytest.mark.skipif(
    not DSN,
    reason="ARGUS_DISPOSABLE_DATABASE_URL is not configured",
)
psycopg = pytest.importorskip("psycopg")

MEMORY_TABLES = (
    "memory_settings",
    "memory_candidates",
    "memory_consent_actions",
    "memory_records",
    "memory_provenance",
    "memory_prompt_history",
    "memory_reconciliations",
    "memory_provider_projections",
    "memory_provider_cleanup",
)
RECONCILIATION_STATUSES = ("pending", "running", "succeeded", "failed")
UNFINISHED_STATUSES = {"pending", "running"}


def _connect():
    return psycopg.connect(DSN, autocommit=True)


def _seed_registered_owner(connection) -> str:
    owner_id = str(uuid.uuid4())
    email = f"memory-delete-{owner_id[:8]}@example.com"
    with connection.cursor() as cursor:
        cursor.execute(
            "insert into auth.users (id,email,is_anonymous)" " values (%s,%s,false)",
            (owner_id, email),
        )
        cursor.execute(
            "insert into public.profiles (id,email) values (%s,%s)",
            (owner_id, email),
        )
    return owner_id


def _seed_guest_owner(connection) -> str:
    owner_id = str(uuid.uuid4())
    with connection.cursor() as cursor:
        cursor.execute(
            "insert into auth.users (id,email,is_anonymous)" " values (%s,null,true)",
            (owner_id,),
        )
        cursor.execute(
            "insert into public.profiles (id,email) values (%s,null)",
            (owner_id,),
        )
        cursor.execute(
            """
            insert into public.guest_workspaces (
              user_id,
              created_at,
              expires_at
            )
            values (%s,now(),now() + interval '7 days')
            """,
            (owner_id,),
        )
    return owner_id


@contextmanager
def _replica_trigger_setup(connection) -> Iterator[None]:
    with connection.cursor() as cursor:
        cursor.execute("set session_replication_role = replica")
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute("set session_replication_role = origin")


def _seed_complete_memory_state(
    connection,
    owner_id: str,
    reconciliation_status: str,
    reconciliation_operation: str = "create",
) -> dict[str, str]:
    suffix = uuid.uuid4().hex
    candidate_id = f"candidate-{suffix}"
    receipt_id = f"receipt-{suffix}"
    record_id = f"record-{suffix}"
    provider_ref = f"provider-{suffix}"
    completed_at = (
        None
        if reconciliation_status in UNFINISHED_STATUSES
        else datetime.now(timezone.utc)
    )
    error_code = "provider_failed" if reconciliation_status == "failed" else None

    with connection.cursor() as cursor:
        cursor.execute(
            """
            insert into public.memory_settings (owner_id,category)
            values (%s,'workflow_preference')
            """,
            (owner_id,),
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
            (candidate_id, owner_id, f"sha256:{'4' * 64}"),
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
            (receipt_id, owner_id, candidate_id, candidate_id),
        )
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
            (record_id, owner_id, candidate_id, receipt_id),
        )
        cursor.execute(
            """
            insert into public.memory_provenance (
              owner_id,
              record_id,
              ordinal,
              source_kind,
              source_id,
              source_version
            )
            values (%s,%s,0,'decision_note',%s,'v1')
            """,
            (owner_id, record_id, f"decision-{suffix}"),
        )
        cursor.execute(
            """
            insert into public.memory_prompt_history (
              owner_id,
              category,
              last_proactive_prompt_at,
              updated_at
            )
            values (%s,'workflow_preference',now(),now())
            """,
            (owner_id,),
        )
        cursor.execute(
            """
            insert into public.memory_reconciliations (
              owner_id,
              record_id,
              generation,
              operation,
              status,
              error_code,
              completed_at
            )
            values (
              %s,
              %s,
              1,
              %s,
              %s,
              %s,
              %s
            )
            """,
            (
                owner_id,
                record_id,
                reconciliation_operation,
                reconciliation_status,
                error_code,
                completed_at,
            ),
        )
        cursor.execute(
            """
            insert into public.memory_provider_projections (
              owner_id,
              record_id,
              provider_ref,
              generation
            )
            values (%s,%s,%s,1)
            """,
            (owner_id, record_id, provider_ref),
        )
        cursor.execute(
            """
            insert into public.memory_provider_cleanup (
              owner_id,
              record_id,
              provider_ref,
              generation
            )
            values (%s,%s,%s,1)
            """,
            (owner_id, record_id, f"{provider_ref}-cleanup"),
        )
    return {
        "candidate_id": candidate_id,
        "receipt_id": receipt_id,
        "record_id": record_id,
        "provider_ref": provider_ref,
    }


def _insert_reconciliation(
    connection,
    *,
    owner_id: str,
    record_id: str,
    generation: int,
    operation: str,
    status: str,
) -> None:
    completed_at = None if status in UNFINISHED_STATUSES else datetime.now(timezone.utc)
    error_code = "provider_failed" if status == "failed" else None
    with connection.cursor() as cursor:
        cursor.execute(
            """
            insert into public.memory_reconciliations (
              owner_id,
              record_id,
              generation,
              operation,
              status,
              error_code,
              completed_at
            )
            values (%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                owner_id,
                record_id,
                generation,
                operation,
                status,
                error_code,
                completed_at,
            ),
        )


@pytest.fixture
def seeded_memory(
    request: pytest.FixtureRequest,
) -> Iterator[dict[str, str]]:
    status = str(request.param)
    with _connect() as connection:
        owner_id = _seed_registered_owner(connection)
        memory_ids = _seed_complete_memory_state(
            connection,
            owner_id,
            status,
        )
    try:
        yield {
            "owner_id": owner_id,
            "status": status,
            **memory_ids,
        }
    finally:
        with _connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "delete from public.memory_reconciliations" " where owner_id = %s",
                    (owner_id,),
                )
                cursor.execute(
                    "delete from auth.users where id = %s",
                    (owner_id,),
                )


def _row_count(
    connection,
    table: str,
    owner_id: str,
    *,
    id_column: str | None = None,
    row_id: str | None = None,
) -> int:
    query = f"select count(*) from public.{table} where owner_id=%s"
    parameters: list[str] = [owner_id]
    if id_column is not None:
        query += f" and {id_column}=%s"
        assert row_id is not None
        parameters.append(row_id)
    with connection.cursor() as cursor:
        cursor.execute(query, parameters)
        return int(cursor.fetchone()[0])


@pytest.mark.parametrize(
    "seeded_memory",
    RECONCILIATION_STATUSES,
    indirect=True,
)
def test_direct_record_delete_waits_only_for_unfinished_reconciliation(
    seeded_memory: dict[str, str],
) -> None:
    with _connect() as connection:
        if seeded_memory["status"] in UNFINISHED_STATUSES:
            with pytest.raises(
                psycopg.errors.CheckViolation,
                match="unfinished provider reconciliation",
            ):
                with connection.cursor() as cursor:
                    cursor.execute(
                        "delete from public.memory_records"
                        " where owner_id=%s and id=%s",
                        (
                            seeded_memory["owner_id"],
                            seeded_memory["record_id"],
                        ),
                    )
            assert (
                _row_count(
                    connection,
                    "memory_records",
                    seeded_memory["owner_id"],
                    id_column="id",
                    row_id=seeded_memory["record_id"],
                )
                == 1
            )
            assert (
                _row_count(
                    connection,
                    "memory_reconciliations",
                    seeded_memory["owner_id"],
                    id_column="record_id",
                    row_id=seeded_memory["record_id"],
                )
                == 1
            )
        else:
            with connection.cursor() as cursor:
                cursor.execute(
                    "delete from public.memory_records" " where owner_id=%s and id=%s",
                    (
                        seeded_memory["owner_id"],
                        seeded_memory["record_id"],
                    ),
                )
            assert (
                _row_count(
                    connection,
                    "memory_records",
                    seeded_memory["owner_id"],
                    id_column="id",
                    row_id=seeded_memory["record_id"],
                )
                == 0
            )
            assert (
                _row_count(
                    connection,
                    "memory_reconciliations",
                    seeded_memory["owner_id"],
                    id_column="record_id",
                    row_id=seeded_memory["record_id"],
                )
                == 1
            )

        assert (
            _row_count(
                connection,
                "memory_consent_actions",
                seeded_memory["owner_id"],
                id_column="id",
                row_id=seeded_memory["receipt_id"],
            )
            == 1
        )
        assert (
            _row_count(
                connection,
                "memory_provider_cleanup",
                seeded_memory["owner_id"],
                id_column="record_id",
                row_id=seeded_memory["record_id"],
            )
            == 1
        )


@pytest.mark.parametrize("seeded_memory", ("succeeded",), indirect=True)
def test_delete_generation_starts_after_record_absence_and_finishes_later(
    seeded_memory: dict[str, str],
) -> None:
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "delete from public.memory_records" " where owner_id=%s and id=%s",
                (seeded_memory["owner_id"], seeded_memory["record_id"]),
            )
        _insert_reconciliation(
            connection,
            owner_id=seeded_memory["owner_id"],
            record_id=seeded_memory["record_id"],
            generation=2,
            operation="delete",
            status="pending",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """
                update public.memory_reconciliations
                   set status='succeeded',
                       completed_at=now()
                 where owner_id=%s
                   and record_id=%s
                   and generation=2
             returning operation,status
                """,
                (seeded_memory["owner_id"], seeded_memory["record_id"]),
            )
            assert cursor.fetchone() == ("delete", "succeeded")
            cursor.execute(
                """
                select generation,operation,status
                  from public.memory_reconciliations
                 where owner_id=%s
                   and record_id=%s
                 order by generation
                """,
                (seeded_memory["owner_id"], seeded_memory["record_id"]),
            )
            assert cursor.fetchall() == [
                (1, "create", "succeeded"),
                (2, "delete", "succeeded"),
            ]


@pytest.mark.parametrize("seeded_memory", ("succeeded",), indirect=True)
def test_delete_generation_rejects_a_live_record(
    seeded_memory: dict[str, str],
) -> None:
    with _connect() as connection:
        with pytest.raises(
            psycopg.errors.CheckViolation,
            match="delete reconciliation requires record absence",
        ):
            _insert_reconciliation(
                connection,
                owner_id=seeded_memory["owner_id"],
                record_id=seeded_memory["record_id"],
                generation=2,
                operation="delete",
                status="pending",
            )


@pytest.mark.parametrize("operation", ("create", "update"))
def test_terminal_create_and_update_generations_survive_record_delete(
    operation: str,
) -> None:
    with _connect() as connection:
        owner_id = _seed_registered_owner(connection)
        memory_ids = _seed_complete_memory_state(
            connection,
            owner_id,
            "succeeded",
            reconciliation_operation=operation,
        )
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "delete from public.memory_records" " where owner_id=%s and id=%s",
                    (owner_id, memory_ids["record_id"]),
                )
                cursor.execute(
                    """
                    select operation,status
                      from public.memory_reconciliations
                     where owner_id=%s
                       and record_id=%s
                       and generation=1
                    """,
                    (owner_id, memory_ids["record_id"]),
                )
                assert cursor.fetchone() == (operation, "succeeded")
        finally:
            with connection.cursor() as cursor:
                cursor.execute(
                    "delete from public.memory_reconciliations" " where owner_id=%s",
                    (owner_id,),
                )
                cursor.execute(
                    "delete from auth.users where id=%s",
                    (owner_id,),
                )


@pytest.mark.parametrize("operation", ("create", "update"))
def test_create_and_update_reconciliation_require_a_live_same_owner_record(
    operation: str,
) -> None:
    with _connect() as connection:
        owner_id = _seed_registered_owner(connection)
        try:
            with pytest.raises(
                psycopg.errors.CheckViolation,
                match="requires a live same-owner record",
            ):
                _insert_reconciliation(
                    connection,
                    owner_id=owner_id,
                    record_id=f"record-{uuid.uuid4()}",
                    generation=1,
                    operation=operation,
                    status="pending",
                )
        finally:
            with connection.cursor() as cursor:
                cursor.execute(
                    "delete from auth.users where id=%s",
                    (owner_id,),
                )


@pytest.mark.parametrize("status", RECONCILIATION_STATUSES)
@pytest.mark.parametrize("deletion_root", ("profile", "auth"))
def test_account_delete_cascades_orphan_delete_reconciliation(
    status: str,
    deletion_root: str,
) -> None:
    with _connect() as connection:
        owner_id = _seed_registered_owner(connection)
        memory_ids = _seed_complete_memory_state(
            connection,
            owner_id,
            "succeeded",
        )
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "delete from public.memory_records" " where owner_id=%s and id=%s",
                    (owner_id, memory_ids["record_id"]),
                )
            _insert_reconciliation(
                connection,
                owner_id=owner_id,
                record_id=memory_ids["record_id"],
                generation=2,
                operation="delete",
                status=status,
            )
            with connection.cursor() as cursor:
                if deletion_root == "profile":
                    cursor.execute(
                        "delete from public.profiles where id=%s",
                        (owner_id,),
                    )
                else:
                    cursor.execute(
                        "delete from auth.users where id=%s",
                        (owner_id,),
                    )
            assert all(
                _row_count(connection, table, owner_id) == 0 for table in MEMORY_TABLES
            )
        finally:
            with connection.cursor() as cursor:
                cursor.execute(
                    "delete from public.memory_reconciliations" " where owner_id=%s",
                    (owner_id,),
                )
                cursor.execute(
                    "delete from auth.users where id=%s",
                    (owner_id,),
                )


def test_orphan_delete_reconciliation_keeps_guest_conversion_nonzero() -> None:
    with _connect() as connection:
        owner_id = _seed_guest_owner(connection)
        record_id = f"record-{uuid.uuid4()}"
        try:
            with _replica_trigger_setup(connection):
                _insert_reconciliation(
                    connection,
                    owner_id=owner_id,
                    record_id=record_id,
                    generation=1,
                    operation="delete",
                    status="pending",
                )
            with pytest.raises(
                psycopg.errors.CheckViolation,
                match="memory state must be zero",
            ):
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        update auth.users
                           set is_anonymous=false,
                               email=%s
                         where id=%s
                        """,
                        (f"converted-{owner_id[:8]}@example.com", owner_id),
                    )
            with connection.cursor() as cursor:
                cursor.execute(
                    "select is_anonymous from auth.users where id=%s",
                    (owner_id,),
                )
                assert cursor.fetchone() == (True,)
                cursor.execute(
                    "select status from public.guest_workspaces where user_id=%s",
                    (owner_id,),
                )
                assert cursor.fetchone() == ("active",)
        finally:
            with connection.cursor() as cursor:
                cursor.execute(
                    "delete from public.memory_reconciliations" " where owner_id=%s",
                    (owner_id,),
                )
                cursor.execute(
                    "delete from auth.users where id=%s",
                    (owner_id,),
                )


@pytest.mark.parametrize(
    "seeded_memory",
    RECONCILIATION_STATUSES,
    indirect=True,
)
def test_profile_delete_cascades_all_memory_regardless_of_reconciliation(
    seeded_memory: dict[str, str],
) -> None:
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "delete from public.profiles where id=%s",
                (seeded_memory["owner_id"],),
            )
        assert all(
            _row_count(connection, table, seeded_memory["owner_id"]) == 0
            for table in MEMORY_TABLES
        )


@pytest.mark.parametrize(
    "seeded_memory",
    RECONCILIATION_STATUSES,
    indirect=True,
)
def test_auth_root_delete_cascades_all_memory_regardless_of_reconciliation(
    seeded_memory: dict[str, str],
) -> None:
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "delete from auth.users where id=%s",
                (seeded_memory["owner_id"],),
            )
        assert all(
            _row_count(connection, table, seeded_memory["owner_id"]) == 0
            for table in MEMORY_TABLES
        )


def test_record_delete_guard_is_fixed_path_private_and_fail_closed() -> None:
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select p.prosecdef,p.proconfig
                  from pg_catalog.pg_proc as p
                  join pg_catalog.pg_namespace as n on n.oid=p.pronamespace
                 where n.nspname='argus_private'
                   and p.proname='guard_memory_record_delete'
                """
            )
            assert cursor.fetchone() == (True, ['search_path=""'])
            for role_name in ("anon", "authenticated", "service_role"):
                cursor.execute(
                    """
                    select has_function_privilege(
                      %s,
                      'argus_private.guard_memory_record_delete()',
                      'execute'
                    )
                    """,
                    (role_name,),
                )
                assert cursor.fetchone() == (False,)

            cursor.execute(
                """
                create temporary table unexpected_record_delete (
                  owner_id uuid not null,
                  id text not null
                )
                """
            )
            cursor.execute(
                """
                create trigger guard_unexpected_record_delete
                before delete on unexpected_record_delete
                for each row execute function
                  argus_private.guard_memory_record_delete()
                """
            )
            cursor.execute(
                "insert into unexpected_record_delete (owner_id,id)"
                " values (%s,'unexpected')",
                (str(uuid.uuid4()),),
            )
            with pytest.raises(
                psycopg.errors.CheckViolation,
                match="unsupported memory record delete target",
            ):
                cursor.execute("delete from unexpected_record_delete")


def test_reconciliation_lifecycle_guard_is_private_and_fail_closed() -> None:
    with _connect() as connection:
        owner_id = _seed_registered_owner(connection)
        memory_ids = _seed_complete_memory_state(
            connection,
            owner_id,
            "succeeded",
        )
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select p.prosecdef,p.proconfig
                      from pg_catalog.pg_proc as p
                      join pg_catalog.pg_namespace as n
                        on n.oid=p.pronamespace
                     where n.nspname='argus_private'
                       and p.proname='validate_memory_reconciliation_lifecycle'
                    """
                )
                assert cursor.fetchone() == (True, ['search_path=""'])
                for role_name in ("anon", "authenticated", "service_role"):
                    cursor.execute(
                        """
                        select has_function_privilege(
                          %s,
                          'argus_private.validate_memory_reconciliation_lifecycle()',
                          'execute'
                        )
                        """,
                        (role_name,),
                    )
                    assert cursor.fetchone() == (False,)

                with pytest.raises(
                    psycopg.errors.CheckViolation,
                    match="unsupported reconciliation operation",
                ):
                    cursor.execute(
                        """
                        insert into public.memory_reconciliations (
                          owner_id,record_id,generation,operation,status
                        )
                        values (%s,%s,2,'unknown','pending')
                        """,
                        (owner_id, memory_ids["record_id"]),
                    )
                with pytest.raises(
                    psycopg.errors.CheckViolation,
                    match="unsupported reconciliation status",
                ):
                    cursor.execute(
                        """
                        insert into public.memory_reconciliations (
                          owner_id,record_id,generation,operation,status
                        )
                        values (%s,%s,2,'update','unknown')
                        """,
                        (owner_id, memory_ids["record_id"]),
                    )
                with pytest.raises(
                    psycopg.errors.CheckViolation,
                    match="invalid reconciliation state",
                ):
                    cursor.execute(
                        """
                        insert into public.memory_reconciliations (
                          owner_id,record_id,generation,operation,status,
                          completed_at
                        )
                        values (%s,%s,2,'update','pending',now())
                        """,
                        (owner_id, memory_ids["record_id"]),
                    )
                with pytest.raises(
                    psycopg.errors.CheckViolation,
                    match="operation is immutable",
                ):
                    cursor.execute(
                        """
                        update public.memory_reconciliations
                           set operation='update'
                         where owner_id=%s
                           and record_id=%s
                           and generation=1
                        """,
                        (owner_id, memory_ids["record_id"]),
                    )

                cursor.execute(
                    """
                    create temporary table unexpected_reconciliation (
                      owner_id uuid not null
                    )
                    """
                )
                cursor.execute(
                    """
                    create trigger validate_unexpected_reconciliation
                    before insert on unexpected_reconciliation
                    for each row execute function
                      argus_private.validate_memory_reconciliation_lifecycle()
                    """
                )
                with pytest.raises(
                    psycopg.errors.CheckViolation,
                    match="unsupported reconciliation lifecycle target",
                ):
                    cursor.execute(
                        "insert into unexpected_reconciliation (owner_id)" " values (%s)",
                        (owner_id,),
                    )
        finally:
            with connection.cursor() as cursor:
                cursor.execute(
                    "delete from public.memory_reconciliations" " where owner_id=%s",
                    (owner_id,),
                )
                cursor.execute(
                    "delete from auth.users where id=%s",
                    (owner_id,),
                )
