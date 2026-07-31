"""Real-Postgres proof for service-owned private-alpha access requests."""

from __future__ import annotations

import os
import uuid

import pytest

DSN = os.getenv("ARGUS_DISPOSABLE_DATABASE_URL", "").strip()
pytestmark = pytest.mark.skipif(
    not DSN,
    reason="ARGUS_DISPOSABLE_DATABASE_URL is not configured",
)
psycopg = pytest.importorskip("psycopg")


def test_access_request_constraints_and_rls_are_service_role_only() -> None:
    with psycopg.connect(DSN, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select relrowsecurity
                from pg_class
                where oid = 'public.private_alpha_allowlist'::regclass
                """
            )
            assert cursor.fetchone() == (True,)

            cursor.execute(
                """
                select
                  has_table_privilege(
                    'anon',
                    'public.private_alpha_allowlist',
                    'select,insert,update,delete'
                  ),
                  has_table_privilege(
                    'authenticated',
                    'public.private_alpha_allowlist',
                    'select,insert,update,delete'
                  ),
                  has_table_privilege(
                    'service_role',
                    'public.private_alpha_allowlist',
                    'select,insert,update,delete'
                  ),
                  (
                    select count(*)
                    from pg_policies
                    where schemaname = 'public'
                      and tablename = 'private_alpha_allowlist'
                  )
                """
            )
            assert cursor.fetchone() == (False, False, True, 0)

            cursor.execute(
                """
                select pg_get_constraintdef(oid)
                from pg_constraint
                where conrelid = 'public.private_alpha_allowlist'::regclass
                  and conname in (
                    'private_alpha_allowlist_role_check',
                    'private_alpha_allowlist_language_check'
                  )
                order by conname
                """
            )
            constraints = " ".join(row[0] for row in cursor.fetchall())

    assert "'requested'::text" in constraints
    assert "'es-419'::text" in constraints


def test_service_role_can_insert_and_promote_requested_row() -> None:
    email = f"access-{uuid.uuid4()}@example.com"
    with psycopg.connect(DSN, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("set role service_role")
            try:
                cursor.execute(
                    """
                    insert into public.private_alpha_allowlist (email, role, language)
                    values (%s, 'requested', 'es-419')
                    returning role, language
                    """,
                    (email,),
                )
                assert cursor.fetchone() == ("requested", "es-419")
                cursor.execute(
                    """
                    update public.private_alpha_allowlist
                    set role = 'user'
                    where email = %s
                      and role = 'requested'
                      and disabled_at is null
                    returning role
                    """,
                    (email,),
                )
                assert cursor.fetchone() == ("user",)
                cursor.execute(
                    "delete from public.private_alpha_allowlist where email = %s",
                    (email,),
                )
            finally:
                cursor.execute("reset role")


def test_anon_cannot_insert_requested_row() -> None:
    email = f"access-{uuid.uuid4()}@example.com"
    with psycopg.connect(DSN, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("set role anon")
            try:
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    cursor.execute(
                        """
                        insert into public.private_alpha_allowlist
                          (email, role, language)
                        values (%s, 'requested', 'en')
                        """,
                        (email,),
                    )
            finally:
                cursor.execute("reset role")
