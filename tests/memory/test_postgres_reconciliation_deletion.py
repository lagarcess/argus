"""Real-Postgres proof for reconciliation-safe memory deletion."""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
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


def _seed_complete_memory_state(
    connection,
    owner_id: str,
    reconciliation_status: str,
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
              'delete',
              %s,
              %s,
              %s
            )
            """,
            (
                owner_id,
                record_id,
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
                == 0
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
