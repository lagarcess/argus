"""Identity-checked receipt trigger transitions on the real migration schema."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

psycopg = pytest.importorskip("psycopg")
DSN = os.getenv("ARGUS_DISPOSABLE_DATABASE_URL", "").strip()
pytestmark = pytest.mark.skipif(not DSN, reason="isolated Postgres URL not configured")
MIGRATIONS = Path(__file__).resolve().parents[1] / "supabase" / "migrations"
BRIDGE = (
    MIGRATIONS / "20260909183500_bridge_public_excerpt_message_trigger.sql"
).read_text()
COMBINED = (
    MIGRATIONS / "20260909233706_combine_selected_tool_receipt_sources.sql"
).read_text()
CLEANUP = COMBINED.split("-- Retire only the compatibility trigger", 1)[1]
CLEANUP = "do $$" + CLEANUP.split("do $$", 1)[1].split("\nrevoke all", 1)[0]
CANONICAL = "revoke_public_excerpts_on_message_delete"
COMPATIBILITY = "revoke_public_excerpts_on_message_delete_registry_compat"
OLD = "public.revoke_public_excerpts_for_deleted_message()"
SHARED = "public.revoke_public_excerpts_for_deleted_source()"


def trigger_function(connection, name):
    row = connection.execute(
        "select tgfoid from pg_trigger where tgrelid='public.messages'::regclass and tgname=%s and not tgisinternal",
        (name,),
    ).fetchone()
    return row[0] if row else None


def function_oid(connection, name):
    return connection.execute("select to_regprocedure(%s)::oid", (name,)).fetchone()[0]


@pytest.mark.parametrize("state", ["absent", "registry", "incoming"])
def test_bridge_is_idempotent_for_each_supported_history(state):
    # DDL stays in this transaction and is rolled back even when the assertion
    # passes; the shared CI database retains its migrated trigger definition.
    connection = psycopg.connect(DSN)
    try:
        if state != "incoming":
            connection.execute(f"drop trigger {CANONICAL} on public.messages")
        if state == "registry":
            connection.execute(
                f"create trigger {CANONICAL} before delete on public.messages for each row execute function {OLD}"
            )
        connection.execute(BRIDGE)
        connection.execute(BRIDGE)
        if state == "registry":
            assert trigger_function(connection, CANONICAL) is None
            assert trigger_function(connection, COMPATIBILITY) == function_oid(
                connection, OLD
            )
        elif state == "incoming":
            assert trigger_function(connection, CANONICAL) == function_oid(
                connection, SHARED
            )
            assert trigger_function(connection, COMPATIBILITY) is None
        else:
            assert trigger_function(connection, CANONICAL) is None
            assert trigger_function(connection, COMPATIBILITY) is None
    finally:
        connection.rollback()
        connection.close()


@pytest.mark.parametrize("target", ["canonical", "compatibility"])
def test_bridge_refuses_a_same_name_trigger_owned_by_another_function(target):
    connection = psycopg.connect(DSN)
    try:
        connection.execute(
            "create function pg_temp.unrelated_receipt_trigger() returns trigger language plpgsql as $$begin return old; end$$"
        )
        if target == "canonical":
            connection.execute(f"drop trigger {CANONICAL} on public.messages")
        name = CANONICAL if target == "canonical" else COMPATIBILITY
        connection.execute(
            f"create trigger {name} before delete on public.messages for each row execute function pg_temp.unrelated_receipt_trigger()"
        )
        with pytest.raises(
            psycopg.errors.RaiseException, match="unexpected public excerpt"
        ):
            connection.execute(BRIDGE)
    finally:
        connection.rollback()
        connection.close()


@pytest.mark.parametrize("identity", ["registry", "unrelated"])
def test_cleanup_only_retires_the_exact_compatibility_function(identity):
    connection = psycopg.connect(DSN)
    try:
        function = OLD
        if identity == "unrelated":
            connection.execute(
                "create function pg_temp.unrelated_receipt_trigger() returns trigger language plpgsql as $$begin return old; end$$"
            )
            function = "pg_temp.unrelated_receipt_trigger()"
        connection.execute(
            f"create trigger {COMPATIBILITY} before delete on public.messages for each row execute function {function}"
        )
        if identity == "unrelated":
            with pytest.raises(
                psycopg.errors.RaiseException,
                match="unexpected public excerpt compatibility",
            ):
                connection.execute(CLEANUP)
        else:
            connection.execute(CLEANUP)
            connection.execute(CLEANUP)
            assert trigger_function(connection, COMPATIBILITY) is None
            assert trigger_function(connection, CANONICAL) == function_oid(
                connection, SHARED
            )
    finally:
        connection.rollback()
        connection.close()
