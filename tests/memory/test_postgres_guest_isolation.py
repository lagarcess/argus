"""Real-Postgres proof for registered-only personalization-memory storage."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

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


def _connect(*, autocommit: bool = True):
    return psycopg.connect(DSN, autocommit=autocommit)


def _seed_identity(
    connection,
    *,
    anonymous: bool,
    email: str | None = None,
) -> str:
    user_id = str(uuid.uuid4())
    verified_email = None if anonymous else (email or f"user-{user_id[:8]}@example.com")
    with connection.cursor() as cursor:
        cursor.execute(
            "insert into auth.users (id, email, is_anonymous) values (%s, %s, %s)",
            (user_id, verified_email, anonymous),
        )
        cursor.execute(
            "insert into public.profiles (id, email) values (%s, %s)",
            (user_id, verified_email),
        )
    return user_id


def _create_workspace(connection, owner_id: str) -> None:
    created_at = datetime.now(timezone.utc).replace(microsecond=0)
    with connection.cursor() as cursor:
        cursor.execute(
            "insert into public.guest_workspaces"
            " (user_id, created_at, expires_at) values (%s, %s, %s)",
            (owner_id, created_at, created_at + timedelta(days=7)),
        )


@pytest.fixture
def owners() -> Iterator[dict[str, str]]:
    with _connect() as connection:
        registered = _seed_identity(connection, anonymous=False)
        other_registered = _seed_identity(connection, anonymous=False)
        guest = _seed_identity(connection, anonymous=True)
        _create_workspace(connection, guest)
    try:
        yield {
            "registered": registered,
            "other_registered": other_registered,
            "guest": guest,
        }
    finally:
        with _connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "delete from auth.users where id = any(%s::uuid[])",
                    ([registered, other_registered, guest],),
                )


def _insert_settings(connection, owner_id: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "insert into public.memory_settings (owner_id, category)"
            " values (%s, 'workflow_preference')",
            (owner_id,),
        )


def _insert_candidate(
    connection,
    owner_id: str,
    *,
    candidate_id: str | None = None,
) -> str:
    candidate_id = candidate_id or f"candidate-{uuid.uuid4()}"
    with connection.cursor() as cursor:
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
            (candidate_id, owner_id, f"sha256:{'1' * 64}"),
        )
    return candidate_id


def _insert_confirmation_receipt(
    connection,
    owner_id: str,
    candidate_id: str,
    *,
    receipt_id: str | None = None,
) -> str:
    receipt_id = receipt_id or f"receipt-{uuid.uuid4()}"
    with connection.cursor() as cursor:
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
    return receipt_id


def _insert_record(
    connection,
    owner_id: str,
    candidate_id: str,
    receipt_id: str,
    *,
    record_id: str | None = None,
) -> str:
    record_id = record_id or f"record-{uuid.uuid4()}"
    with connection.cursor() as cursor:
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
    return record_id


@contextmanager
def _replica_trigger_setup(connection) -> Iterator[None]:
    """Inject impossible corruption only into the disposable test database."""

    with connection.cursor() as cursor:
        cursor.execute("set session_replication_role = replica")
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute("set session_replication_role = origin")


def _inject_guest_memory_state(connection, table: str, owner_id: str) -> None:
    suffix = uuid.uuid4().hex
    statements: dict[str, tuple[str, tuple[Any, ...]]] = {
        "memory_settings": (
            "insert into public.memory_settings (owner_id,category)"
            " values (%s,'workflow_preference')",
            (owner_id,),
        ),
        "memory_candidates": (
            """
            insert into public.memory_candidates (
              id,owner_id,category,source_label,source_value,future_benefit,
              trigger,proposed_context,opt_in_scope,sensitivity_status,
              sensitivity_flags,sensitivity_policy_version,
              sensitivity_content_digest
            )
            values (
              %s,%s,'workflow_preference','Injected label','Injected value',
              'Injected future benefit','explicit_request','ordinary',
              array['workflow_preference'],'clear','{}'::text[],
              'argus.memory-sensitivity/v1',%s
            )
            """,
            (f"candidate-{suffix}", owner_id, f"sha256:{'2' * 64}"),
        ),
        "memory_consent_actions": (
            """
            insert into public.memory_consent_actions (
              id,owner_id,action,candidate_id,requested_scope,granted_scope,
              effective_scope,idempotency_key
            )
            values (
              %s,%s,'direct_enable',null,array['workflow_preference'],
              array['workflow_preference'],array['workflow_preference'],%s
            )
            """,
            (f"receipt-{suffix}", owner_id, f"enable-{suffix}"),
        ),
        "memory_records": (
            """
            insert into public.memory_records (
              id,owner_id,candidate_id,consent_action_id,category,label,value
            )
            values (
              %s,%s,%s,%s,'workflow_preference','Injected label',
              'Injected value'
            )
            """,
            (
                f"record-{suffix}",
                owner_id,
                f"candidate-{suffix}",
                f"receipt-{suffix}",
            ),
        ),
        "memory_provenance": (
            """
            insert into public.memory_provenance (
              owner_id,candidate_id,record_id,ordinal,source_kind,source_id,
              source_version
            )
            values (
              %s,%s,null,0,'decision_note',%s,'2026-07-29T22:00:00Z'
            )
            """,
            (owner_id, f"candidate-{suffix}", f"decision-{suffix}"),
        ),
        "memory_prompt_history": (
            """
            insert into public.memory_prompt_history (
              owner_id,category,last_proactive_prompt_at
            )
            values (%s,'workflow_preference',now())
            """,
            (owner_id,),
        ),
        "memory_reconciliations": (
            """
            insert into public.memory_reconciliations (
              owner_id,record_id,generation,operation,status
            )
            values (%s,%s,1,'create','pending')
            """,
            (owner_id, f"record-{suffix}"),
        ),
        "memory_provider_projections": (
            """
            insert into public.memory_provider_projections (
              owner_id,record_id,provider_ref,generation
            )
            values (%s,%s,%s,1)
            """,
            (owner_id, f"record-{suffix}", f"provider-{suffix}"),
        ),
        "memory_provider_cleanup": (
            """
            insert into public.memory_provider_cleanup (
              owner_id,record_id,provider_ref,generation,status
            )
            values (%s,%s,%s,1,'pending')
            """,
            (owner_id, f"record-{suffix}", f"provider-{suffix}"),
        ),
    }
    assert table in statements
    sql, parameters = statements[table]
    with _replica_trigger_setup(connection):
        with connection.cursor() as cursor:
            cursor.execute(sql, parameters)


def _seed_handoff(connection) -> dict[str, str]:
    source = _seed_identity(connection, anonymous=True)
    destination = _seed_identity(connection, anonymous=False)
    _create_workspace(connection, source)
    conversation_id = str(uuid.uuid4())
    handoff_id = str(uuid.uuid4())
    secret_hash = hashlib.sha256(f"secret-{uuid.uuid4()}".encode()).hexdigest()
    with connection.cursor() as cursor:
        cursor.execute(
            "insert into public.conversations (id,user_id,title)"
            " values (%s,%s,'Temporary memory proof')",
            (conversation_id, source),
        )
        cursor.execute(
            "select email from auth.users where id = %s",
            (destination,),
        )
        destination_email = str(cursor.fetchone()[0]).strip().lower()
        destination_email_hash = hashlib.sha256(destination_email.encode()).hexdigest()
        cursor.execute(
            """
            insert into public.guest_workspace_handoffs (
              id,
              secret_hash,
              source_user_id,
              destination_email_hash,
              destination_user_id,
              source_conversation_id,
              created_at,
              expires_at
            )
            values (%s,%s,%s,%s,%s,%s,now(),now() + interval '10 minutes')
            """,
            (
                handoff_id,
                secret_hash,
                source,
                destination_email_hash,
                destination,
                conversation_id,
            ),
        )
    return {
        "source": source,
        "destination": destination,
        "conversation": conversation_id,
        "handoff": handoff_id,
        "secret_hash": secret_hash,
    }


def _claim_handoff(connection, handoff: dict[str, str]) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            select *
              from public.claim_guest_workspace_handoff_by_email(%s,%s,%s,false)
            """,
            (
                handoff["handoff"],
                handoff["secret_hash"],
                handoff["destination"],
            ),
        )
        cursor.fetchone()


def test_private_memory_schema_has_forced_rls_denied_grants_and_guards() -> None:
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select table_name,
                       to_regclass('public.' || table_name)::text
                  from unnest(%s::text[]) as table_name
                 order by table_name
                """,
                (list(MEMORY_TABLES),),
            )
            assert cursor.fetchall() == [
                (table, table) for table in sorted(MEMORY_TABLES)
            ]

            cursor.execute(
                """
                select c.relname, c.relrowsecurity, c.relforcerowsecurity
                  from pg_catalog.pg_class as c
                  join pg_catalog.pg_namespace as n on n.oid = c.relnamespace
                 where n.nspname = 'public'
                   and c.relname = any(%s::text[])
                 order by c.relname
                """,
                (list(MEMORY_TABLES),),
            )
            assert cursor.fetchall() == [
                (table, True, True) for table in sorted(MEMORY_TABLES)
            ]

            cursor.execute(
                """
                select role_name, table_name, privilege_name,
                       has_table_privilege(
                         role_name,
                         format('public.%%I', table_name),
                         privilege_name
                       )
                  from unnest(
                         array['anon', 'authenticated', 'service_role']
                       ) as role_name
                 cross join unnest(%s::text[]) as table_name
                 cross join unnest(
                   array['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE',
                         'REFERENCES', 'TRIGGER']
                 ) as privilege_name
                 order by role_name, table_name, privilege_name
                """,
                (list(MEMORY_TABLES),),
            )
            assert all(not row[3] for row in cursor.fetchall())

            cursor.execute(
                """
                select c.relname,
                       exists (
                         select 1
                           from pg_catalog.aclexplode(
                             coalesce(
                               c.relacl,
                               pg_catalog.acldefault('r', c.relowner)
                             )
                           ) as acl
                          where acl.grantee = 0
                       ) as public_has_privilege
                  from pg_catalog.pg_class as c
                  join pg_catalog.pg_namespace as n on n.oid = c.relnamespace
                 where n.nspname = 'public'
                   and c.relname = any(%s::text[])
                 order by c.relname
                """,
                (list(MEMORY_TABLES),),
            )
            assert cursor.fetchall() == [
                (table, False) for table in sorted(MEMORY_TABLES)
            ]

            cursor.execute(
                """
                select sequence.relname
                  from pg_catalog.pg_class as sequence
                  join pg_catalog.pg_namespace as n
                    on n.oid = sequence.relnamespace
                  join pg_catalog.pg_depend as dependency
                    on dependency.objid = sequence.oid
                   and dependency.deptype in ('a', 'i')
                  join pg_catalog.pg_class as memory_table
                    on memory_table.oid = dependency.refobjid
                 where sequence.relkind = 'S'
                   and n.nspname = 'public'
                   and memory_table.relname = any(%s::text[])
                """,
                (list(MEMORY_TABLES),),
            )
            assert cursor.fetchall() == []
            cursor.execute(
                """
                select pg_get_indexdef(index_relation.oid)
                  from pg_catalog.pg_class as index_relation
                  join pg_catalog.pg_namespace as n
                    on n.oid = index_relation.relnamespace
                 where n.nspname = 'public'
                   and index_relation.relname =
                     'memory_records_consent_action_idx'
                """
            )
            assert cursor.fetchone() == (
                "CREATE INDEX memory_records_consent_action_idx ON "
                "public.memory_records USING btree "
                "(owner_id, consent_action_id, candidate_id)",
            )

            cursor.execute(
                """
                select p.prosecdef, p.proconfig
                  from pg_catalog.pg_proc as p
                  join pg_catalog.pg_namespace as n on n.oid = p.pronamespace
                 where n.nspname = 'argus_private'
                   and p.proname = 'is_registered_memory_owner'
                """
            )
            assert cursor.fetchone() == (True, ['search_path=""'])
            for role_name in ("anon", "authenticated", "service_role"):
                cursor.execute(
                    """
                    select has_function_privilege(
                      %s,
                      'argus_private.is_registered_memory_owner(uuid)',
                      'execute'
                    )
                    """,
                    (role_name,),
                )
                assert cursor.fetchone() == (False,)

            cursor.execute(
                """
                select c.relname, t.tgname
                  from pg_catalog.pg_trigger as t
                  join pg_catalog.pg_class as c on c.oid = t.tgrelid
                  join pg_catalog.pg_namespace as n on n.oid = c.relnamespace
                 where not t.tgisinternal
                   and n.nspname = 'public'
                   and (
                     (
                       c.relname = any(%s::text[])
                       and t.tgname = 'enforce_registered_memory_owner'
                     )
                     or (
                       c.relname = 'guest_workspaces'
                       and t.tgname = 'guard_guest_memory_zero_state'
                     )
                   )
                 order by c.relname, t.tgname
                """,
                (list(MEMORY_TABLES),),
            )
            assert cursor.fetchall() == sorted(
                [
                    *(
                        (table, "enforce_registered_memory_owner")
                        for table in MEMORY_TABLES
                    ),
                    ("guest_workspaces", "guard_guest_memory_zero_state"),
                ]
            )


def test_postgres_registered_writes_succeed_but_guest_truth_wins(
    owners: dict[str, str],
) -> None:
    with _connect() as connection:
        _insert_settings(connection, owners["registered"])
        with connection.cursor() as cursor:
            cursor.execute(
                "select category from public.memory_settings where owner_id = %s",
                (owners["registered"],),
            )
            assert cursor.fetchone() == ("workflow_preference",)

        with pytest.raises(psycopg.errors.CheckViolation, match="registered"):
            _insert_settings(connection, owners["guest"])

        with pytest.raises(psycopg.errors.CheckViolation, match="registered"):
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "select set_config('request.jwt.claims', %s, true)",
                        (
                            json.dumps(
                                {
                                    "sub": owners["registered"],
                                    "role": "authenticated",
                                    "is_anonymous": False,
                                }
                            ),
                        ),
                    )
                    cursor.execute(
                        "insert into public.memory_settings (owner_id,category)"
                        " values (%s,'personalization_preference')",
                        (owners["guest"],),
                    )


@pytest.mark.parametrize(
    ("role_name", "is_anonymous"),
    (
        ("anon", None),
        ("authenticated", False),
        ("authenticated", True),
        ("service_role", False),
    ),
)
def test_data_api_roles_have_no_direct_memory_access(
    owners: dict[str, str],
    role_name: str,
    is_anonymous: bool | None,
) -> None:
    with _connect(autocommit=False) as connection:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with connection.cursor() as cursor:
                cursor.execute(f"set local role {role_name}")
                if is_anonymous is not None:
                    claim_owner = (
                        owners["guest"] if is_anonymous else owners["registered"]
                    )
                    cursor.execute(
                        "select set_config('request.jwt.claims', %s, true)",
                        (
                            json.dumps(
                                {
                                    "sub": claim_owner,
                                    "role": role_name,
                                    "is_anonymous": is_anonymous,
                                }
                            ),
                        ),
                    )
                cursor.execute("select * from public.memory_settings")


@pytest.mark.parametrize("workspace_status", ("active", "claiming"))
def test_linked_identity_remains_ineligible_while_guest_workspace_is_active_or_claiming(
    workspace_status: str,
) -> None:
    with _connect() as connection:
        owner_id = _seed_identity(connection, anonymous=True)
        _create_workspace(connection, owner_id)
        email = f"linked-{owner_id[:8]}@example.com"
        try:
            if workspace_status == "claiming":
                with connection.cursor() as cursor:
                    cursor.execute(
                        "update public.guest_workspaces"
                        " set status='claiming' where user_id=%s",
                        (owner_id,),
                    )
            with _replica_trigger_setup(connection):
                with connection.cursor() as cursor:
                    cursor.execute(
                        "update auth.users set is_anonymous=false,email=%s where id=%s",
                        (email, owner_id),
                    )
                    cursor.execute(
                        "update public.profiles set email=%s where id=%s",
                        (email, owner_id),
                    )

            with pytest.raises(psycopg.errors.CheckViolation, match="registered"):
                _insert_settings(connection, owner_id)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("delete from auth.users where id = %s", (owner_id,))


def test_composite_owner_foreign_keys_reject_cross_owner_linkage(
    owners: dict[str, str],
) -> None:
    with _connect() as connection:
        candidate_id = _insert_candidate(connection, owners["other_registered"])
        receipt_id = _insert_confirmation_receipt(
            connection,
            owners["other_registered"],
            candidate_id,
        )
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            _insert_record(
                connection,
                owners["registered"],
                candidate_id,
                receipt_id,
            )

        own_candidate = _insert_candidate(connection, owners["registered"])
        own_receipt = _insert_confirmation_receipt(
            connection,
            owners["registered"],
            own_candidate,
        )
        own_record = _insert_record(
            connection,
            owners["registered"],
            own_candidate,
            own_receipt,
        )
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    insert into public.memory_provenance (
                      owner_id,candidate_id,record_id,ordinal,source_kind,
                      source_id,source_version
                    )
                    values (
                      %s,null,%s,0,'decision_note','decision-cross-owner','v1'
                    )
                    """,
                    (owners["other_registered"], own_record),
                )


def test_candidate_confirmation_requires_existing_same_owner_candidate(
    owners: dict[str, str],
) -> None:
    with _connect() as connection:
        candidate_id = _insert_candidate(
            connection,
            owners["other_registered"],
        )
        with pytest.raises(
            psycopg.errors.CheckViolation,
            match="existing same-owner candidate",
        ):
            _insert_confirmation_receipt(
                connection,
                owners["registered"],
                candidate_id,
            )


def test_record_rejects_consent_scope_unrelated_to_candidate_and_rolls_back(
    owners: dict[str, str],
) -> None:
    with _connect() as connection:
        candidate_id = _insert_candidate(connection, owners["registered"])
        receipt_id = f"receipt-{uuid.uuid4()}"
        invalid_receipt_sql = """
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
              array['personalization_preference'],
              array['personalization_preference'],
              array['personalization_preference', 'workflow_preference'],
              %s
            )
        """

        with pytest.raises(
            psycopg.errors.CheckViolation,
            match="candidate category must be in requested scope",
        ):
            with connection.cursor() as cursor:
                cursor.execute(
                    invalid_receipt_sql,
                    (
                        receipt_id,
                        owners["registered"],
                        candidate_id,
                        candidate_id,
                    ),
                )

        transaction_candidate_id = f"candidate-{uuid.uuid4()}"
        transaction_receipt_id = f"receipt-{uuid.uuid4()}"
        transaction_record_id = f"record-{uuid.uuid4()}"
        with pytest.raises(
            psycopg.errors.CheckViolation,
            match="requested consent scope",
        ):
            with connection.transaction():
                _insert_candidate(
                    connection,
                    owners["registered"],
                    candidate_id=transaction_candidate_id,
                )
                with _replica_trigger_setup(connection):
                    with connection.cursor() as cursor:
                        cursor.execute(
                            invalid_receipt_sql,
                            (
                                transaction_receipt_id,
                                owners["registered"],
                                transaction_candidate_id,
                                transaction_candidate_id,
                            ),
                        )
                _insert_record(
                    connection,
                    owners["registered"],
                    transaction_candidate_id,
                    transaction_receipt_id,
                    record_id=transaction_record_id,
                )

        with connection.cursor() as cursor:
            for table, row_id in (
                ("memory_candidates", transaction_candidate_id),
                ("memory_consent_actions", transaction_receipt_id),
                ("memory_records", transaction_record_id),
            ):
                query = (
                    f"select count(*) from public.{table}" " where owner_id=%s and id=%s"
                )
                cursor.execute(
                    query,
                    (owners["registered"], row_id),
                )
                assert cursor.fetchone() == (0,)


def test_direct_enable_requires_nonempty_granted_scope(
    owners: dict[str, str],
) -> None:
    with _connect() as connection:
        with pytest.raises(psycopg.errors.CheckViolation):
            with connection.cursor() as cursor:
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
                      'direct_enable',
                      null,
                      array['workflow_preference'],
                      '{}'::text[],
                      array['workflow_preference'],
                      %s
                    )
                    """,
                    (
                        f"receipt-{uuid.uuid4()}",
                        owners["registered"],
                        f"enable-{uuid.uuid4()}",
                    ),
                )


def test_constraints_and_immutable_identity_are_database_enforced(
    owners: dict[str, str],
) -> None:
    with _connect() as connection:
        with pytest.raises(psycopg.errors.CheckViolation):
            with connection.cursor() as cursor:
                cursor.execute(
                    "insert into public.memory_settings (owner_id,category)"
                    " values (%s,'unreviewed_category')",
                    (owners["registered"],),
                )

        candidate_id = _insert_candidate(connection, owners["registered"])
        receipt_id = _insert_confirmation_receipt(
            connection,
            owners["registered"],
            candidate_id,
        )
        record_id = _insert_record(
            connection,
            owners["registered"],
            candidate_id,
            receipt_id,
        )

        with pytest.raises(psycopg.errors.CheckViolation):
            with connection.cursor() as cursor:
                cursor.execute(
                    "update public.memory_records set owner_id=%s where id=%s",
                    (owners["other_registered"], record_id),
                )
        with pytest.raises(psycopg.errors.CheckViolation):
            with connection.cursor() as cursor:
                cursor.execute(
                    "update public.memory_records"
                    " set category='personalization_preference',"
                    "     revision=revision+1,"
                    "     updated_at=now()+interval '1 second'"
                    " where id=%s",
                    (record_id,),
                )
        with pytest.raises(psycopg.errors.CheckViolation):
            with connection.cursor() as cursor:
                cursor.execute(
                    "update public.memory_consent_actions"
                    " set policy_version='argus.memory-policy/v2'"
                    " where id=%s",
                    (receipt_id,),
                )
        with pytest.raises(psycopg.errors.CheckViolation):
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    insert into public.memory_reconciliations (
                      owner_id,record_id,generation,operation,status
                    )
                    values (%s,%s,-1,'update','pending')
                    """,
                    (owners["registered"], record_id),
                )

        with connection.cursor() as cursor:
            cursor.execute(
                "update public.memory_records"
                " set label='Updated label',"
                "     revision=revision+1,"
                "     updated_at=now()+interval '1 second'"
                " where id=%s returning label,revision",
                (record_id,),
            )
            assert cursor.fetchone() == ("Updated label", 2)


def test_same_identity_link_succeeds_only_from_complete_memory_zero_state() -> None:
    with _connect() as connection:
        owner_id = _seed_identity(connection, anonymous=True)
        _create_workspace(connection, owner_id)
        email = f"converted-{owner_id[:8]}@example.com"
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "update auth.users set is_anonymous=false,email=%s where id=%s",
                    (email, owner_id),
                )
                cursor.execute(
                    "select status,claimed_by::text"
                    " from public.guest_workspaces where user_id=%s",
                    (owner_id,),
                )
                assert cursor.fetchone() == ("claimed", owner_id)
            _insert_settings(connection, owner_id)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("delete from auth.users where id = %s", (owner_id,))


@pytest.mark.parametrize("memory_table", MEMORY_TABLES)
def test_same_identity_link_rejects_corruption_from_every_memory_table(
    memory_table: str,
) -> None:
    with _connect() as connection:
        owner_id = _seed_identity(connection, anonymous=True)
        _create_workspace(connection, owner_id)
        _inject_guest_memory_state(connection, memory_table, owner_id)
        email = f"blocked-{owner_id[:8]}@example.com"
        try:
            with pytest.raises(
                psycopg.errors.CheckViolation,
                match="memory state must be zero",
            ):
                with connection.cursor() as cursor:
                    cursor.execute(
                        "update auth.users"
                        " set is_anonymous=false,email=%s where id=%s",
                        (email, owner_id),
                    )
            with connection.cursor() as cursor:
                cursor.execute(
                    "select is_anonymous,email from auth.users where id=%s",
                    (owner_id,),
                )
                assert cursor.fetchone() == (True, None)
                cursor.execute(
                    "select status from public.guest_workspaces where user_id=%s",
                    (owner_id,),
                )
                assert cursor.fetchone() == ("active",)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("delete from auth.users where id = %s", (owner_id,))


def test_existing_account_handoff_succeeds_from_complete_memory_zero_state() -> None:
    with _connect() as connection:
        handoff = _seed_handoff(connection)
        try:
            _claim_handoff(connection, handoff)
            with connection.cursor() as cursor:
                cursor.execute(
                    "select user_id::text from public.conversations where id=%s",
                    (handoff["conversation"],),
                )
                assert cursor.fetchone() == (handoff["destination"],)
                cursor.execute(
                    "select status from public.guest_workspaces where user_id=%s",
                    (handoff["source"],),
                )
                assert cursor.fetchone() == ("claimed",)
        finally:
            with connection.cursor() as cursor:
                cursor.execute(
                    "delete from auth.users where id = any(%s::uuid[])",
                    ([handoff["source"], handoff["destination"]],),
                )


@pytest.mark.parametrize("memory_table", MEMORY_TABLES)
def test_existing_account_handoff_rejects_corruption_from_every_memory_table(
    memory_table: str,
) -> None:
    with _connect() as connection:
        handoff = _seed_handoff(connection)
        _inject_guest_memory_state(connection, memory_table, handoff["source"])
        try:
            with pytest.raises(
                psycopg.errors.CheckViolation,
                match="memory state must be zero",
            ):
                _claim_handoff(connection, handoff)
            with connection.cursor() as cursor:
                cursor.execute(
                    "select user_id::text from public.conversations where id=%s",
                    (handoff["conversation"],),
                )
                assert cursor.fetchone() == (handoff["source"],)
                cursor.execute(
                    "select status from public.guest_workspace_handoffs where id=%s",
                    (handoff["handoff"],),
                )
                assert cursor.fetchone() == ("pending",)
        finally:
            with connection.cursor() as cursor:
                cursor.execute(
                    "delete from auth.users where id = any(%s::uuid[])",
                    ([handoff["source"], handoff["destination"]],),
                )
