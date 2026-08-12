"""Real-Postgres proof for service-owned private-alpha access requests."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from faker import Faker

DSN = os.getenv("ARGUS_DISPOSABLE_DATABASE_URL", "").strip()
pytestmark = pytest.mark.skipif(
    not DSN,
    reason="ARGUS_DISPOSABLE_DATABASE_URL is not configured",
)
psycopg = pytest.importorskip("psycopg")
fake = Faker()

WELCOME_CONTENT_VERSION = "private-alpha-access-welcome/v1"
WELCOME_SUBJECT = "Welcome to Argus"
WELCOME_RECEIPT = "resend-email-id-461"


def _random_email() -> str:
    return fake.unique.email(domain="example.com").lower()


def _cleanup_access_rows(email: str) -> None:
    with psycopg.connect(DSN, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                delete from public.private_alpha_access_welcome_deliveries
                where recipient_email = %s
                """,
                (email,),
            )
            cursor.execute(
                "delete from public.private_alpha_allowlist where email = %s",
                (email,),
            )


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


def test_direct_requested_user_activation_without_delivery_is_rejected() -> None:
    email = _random_email()
    try:
        with psycopg.connect(DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    insert into public.private_alpha_allowlist (email, role, language)
                    values (%s, 'requested', 'en')
                    """,
                    (email,),
                )

                cursor.execute("set role service_role")
                with pytest.raises(psycopg.errors.CheckViolation):
                    cursor.execute(
                        """
                        update public.private_alpha_allowlist
                        set role = 'user'
                        where email = %s
                        """,
                        (email,),
                    )
                cursor.execute("reset role")

                cursor.execute(
                    """
                    select role,
                           (
                             select count(*)
                             from public.private_alpha_access_welcome_deliveries
                             where recipient_email = %s
                           )
                    from public.private_alpha_allowlist
                    where email = %s
                    """,
                    (email, email),
                )
                assert cursor.fetchone() == ("requested", 0)
    finally:
        _cleanup_access_rows(email)


def test_completion_records_delivery_and_promotes_atomically() -> None:
    email = _random_email()
    try:
        with psycopg.connect(DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    insert into public.private_alpha_allowlist (email, role, language)
                    values (%s, 'requested', 'en')
                    """,
                    (email,),
                )

                cursor.execute("set role service_role")
                cursor.execute(
                    """
                    select public.complete_private_alpha_access_welcome(
                      %s, 'en', %s, %s, %s
                    )
                    """,
                    (
                        email,
                        WELCOME_CONTENT_VERSION,
                        WELCOME_SUBJECT,
                        WELCOME_RECEIPT,
                    ),
                )
                assert cursor.fetchone() == (True,)
                cursor.execute("reset role")

                cursor.execute(
                    """
                    select role, language, disabled_at
                    from public.private_alpha_allowlist
                    where email = %s
                    """,
                    (email,),
                )
                assert cursor.fetchone() == ("user", "en", None)

                cursor.execute(
                    """
                    select recipient_email, language, content_version, subject,
                           provider_receipt, sent_at is not null, created_at is not null
                    from public.private_alpha_access_welcome_deliveries
                    where recipient_email = %s
                    """,
                    (email,),
                )
                assert cursor.fetchone() == (
                    email,
                    "en",
                    "private-alpha-access-welcome/v1",
                    "Welcome to Argus",
                    "resend-email-id-461",
                    True,
                    True,
                )
    finally:
        _cleanup_access_rows(email)


def test_completion_replay_returns_true_with_one_delivery_row() -> None:
    email = _random_email()
    try:
        with psycopg.connect(DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    insert into public.private_alpha_allowlist (email, role, language)
                    values (%s, 'requested', 'en')
                    """,
                    (email,),
                )
                cursor.execute("set role service_role")

                results = []
                for _ in range(2):
                    cursor.execute(
                        """
                        select public.complete_private_alpha_access_welcome(
                          %s, 'en', %s, %s, %s
                        )
                        """,
                        (
                            email,
                            WELCOME_CONTENT_VERSION,
                            WELCOME_SUBJECT,
                            WELCOME_RECEIPT,
                        ),
                    )
                    results.append(cursor.fetchone())

                assert results == [(True,), (True,)]
                cursor.execute("reset role")
                cursor.execute(
                    """
                    select a.role, count(d.recipient_email)
                    from public.private_alpha_allowlist as a
                    left join public.private_alpha_access_welcome_deliveries as d
                      on d.recipient_email = a.email
                    where a.email = %s
                    group by a.role
                    """,
                    (email,),
                )
                assert cursor.fetchone() == ("user", 1)
    finally:
        _cleanup_access_rows(email)


def test_anon_cannot_insert_requested_row() -> None:
    email = _random_email()
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


def test_concurrent_service_requests_create_exactly_one_requested_row() -> None:
    email = _random_email()
    worker_count = 4
    barrier = Barrier(worker_count)

    def request_access() -> tuple[str, str] | None:
        with psycopg.connect(DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("set role service_role")
                barrier.wait(timeout=10)
                cursor.execute(
                    """
                    insert into public.private_alpha_allowlist (email, role, language)
                    values (%s, 'requested', 'en')
                    on conflict (email) do nothing
                    returning role, language
                    """,
                    (email,),
                )
                return cursor.fetchone()

    try:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            results = list(executor.map(lambda _: request_access(), range(worker_count)))

        assert results.count(("requested", "en")) == 1
        assert results.count(None) == worker_count - 1
        with psycopg.connect(DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select role, language, disabled_at
                    from public.private_alpha_allowlist
                    where email = %s
                    """,
                    (email,),
                )
                assert cursor.fetchall() == [("requested", "en", None)]
    finally:
        with psycopg.connect(DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "delete from public.private_alpha_allowlist where email = %s",
                    (email,),
                )


def test_concurrent_completion_has_one_delivery_and_one_active_row() -> None:
    email = _random_email()
    worker_count = 4
    barrier = Barrier(worker_count)

    with psycopg.connect(DSN, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                insert into public.private_alpha_allowlist (email, role, language)
                values (%s, 'requested', 'es-419')
                """,
                (email,),
            )

    def complete_access_welcome() -> tuple[bool]:
        with psycopg.connect(DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("set role service_role")
                barrier.wait(timeout=10)
                cursor.execute(
                    """
                    select public.complete_private_alpha_access_welcome(
                      %s, 'es-419', %s, 'Bienvenido a Argus', %s
                    )
                    """,
                    (email, WELCOME_CONTENT_VERSION, WELCOME_RECEIPT),
                )
                return cursor.fetchone()

    try:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            results = list(
                executor.map(lambda _: complete_access_welcome(), range(worker_count))
            )

        assert results == [(True,)] * worker_count
        with psycopg.connect(DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select a.role, a.language, a.disabled_at,
                           count(d.recipient_email)
                    from public.private_alpha_allowlist as a
                    left join public.private_alpha_access_welcome_deliveries as d
                      on d.recipient_email = a.email
                    where a.email = %s
                    group by a.role, a.language, a.disabled_at
                    """,
                    (email,),
                )
                assert cursor.fetchall() == [("user", "es-419", None, 1)]
    finally:
        _cleanup_access_rows(email)


def test_browser_roles_cannot_read_or_mutate_delivery_rows() -> None:
    email = _random_email()
    try:
        with psycopg.connect(DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    insert into public.private_alpha_allowlist (email, role, language)
                    values (%s, 'requested', 'en')
                    """,
                    (email,),
                )
                cursor.execute("set role service_role")
                cursor.execute(
                    """
                    select public.complete_private_alpha_access_welcome(
                      %s, 'en', %s, %s, %s
                    )
                    """,
                    (
                        email,
                        WELCOME_CONTENT_VERSION,
                        WELCOME_SUBJECT,
                        WELCOME_RECEIPT,
                    ),
                )
                assert cursor.fetchone() == (True,)
                cursor.execute("reset role")

                cursor.execute(
                    """
                    select
                      has_table_privilege(
                        'anon',
                        'public.private_alpha_access_welcome_deliveries',
                        'select,insert,update,delete'
                      ),
                      has_table_privilege(
                        'authenticated',
                        'public.private_alpha_access_welcome_deliveries',
                        'select,insert,update,delete'
                      ),
                      has_function_privilege(
                        'anon',
                        'public.complete_private_alpha_access_welcome(text,text,text,text,text)',
                        'execute'
                      ),
                      has_function_privilege(
                        'authenticated',
                        'public.complete_private_alpha_access_welcome(text,text,text,text,text)',
                        'execute'
                      ),
                      has_table_privilege(
                        'service_role',
                        'public.private_alpha_access_welcome_deliveries',
                        'select'
                      ),
                      has_table_privilege(
                        'service_role',
                        'public.private_alpha_access_welcome_deliveries',
                        'insert'
                      ),
                      has_table_privilege(
                        'service_role',
                        'public.private_alpha_access_welcome_deliveries',
                        'update'
                      ),
                      has_table_privilege(
                        'service_role',
                        'public.private_alpha_access_welcome_deliveries',
                        'delete'
                      ),
                      has_function_privilege(
                        'service_role',
                        'public.complete_private_alpha_access_welcome(text,text,text,text,text)',
                        'execute'
                      ),
                      has_function_privilege(
                        'service_role',
                        'public.require_private_alpha_access_welcome_delivery()',
                        'execute'
                      ),
                      (
                        select count(*)
                        from pg_policies
                        where schemaname = 'public'
                          and tablename = 'private_alpha_access_welcome_deliveries'
                      )
                    """
                )
                assert cursor.fetchone() == (
                    False,
                    False,
                    False,
                    False,
                    True,
                    True,
                    False,
                    False,
                    True,
                    False,
                    0,
                )

                for role in ("anon", "authenticated"):
                    cursor.execute(f"set role {role}")
                    with pytest.raises(psycopg.errors.InsufficientPrivilege):
                        cursor.execute(
                            """
                            select recipient_email
                            from public.private_alpha_access_welcome_deliveries
                            where recipient_email = %s
                            """,
                            (email,),
                        )
                    with pytest.raises(psycopg.errors.InsufficientPrivilege):
                        cursor.execute(
                            """
                            insert into public.private_alpha_access_welcome_deliveries (
                              recipient_email,
                              language,
                              content_version,
                              subject,
                              provider_receipt
                            )
                            values (%s, 'en', %s, %s, %s)
                            """,
                            (
                                _random_email(),
                                WELCOME_CONTENT_VERSION,
                                WELCOME_SUBJECT,
                                WELCOME_RECEIPT,
                            ),
                        )
                    with pytest.raises(psycopg.errors.InsufficientPrivilege):
                        cursor.execute(
                            """
                            select public.complete_private_alpha_access_welcome(
                              %s, 'en', %s, %s, %s
                            )
                            """,
                            (
                                email,
                                WELCOME_CONTENT_VERSION,
                                WELCOME_SUBJECT,
                                WELCOME_RECEIPT,
                            ),
                        )
                    cursor.execute("reset role")
    finally:
        _cleanup_access_rows(email)
