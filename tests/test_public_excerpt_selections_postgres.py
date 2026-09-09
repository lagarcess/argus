"""Real database selection identity, all-source locks and revocation proofs."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest

from tests.test_public_excerpt_snapshots_postgres import _Fixture, _public_id

DSN = os.getenv("ARGUS_DISPOSABLE_DATABASE_URL", "").strip()
pytestmark = pytest.mark.skipif(
    not DSN, reason="ARGUS_DISPOSABLE_DATABASE_URL is not configured"
)
psycopg = pytest.importorskip("psycopg")


def seed(connection):
    cursor = connection.cursor()
    fixture = _Fixture(cursor)
    fixture.seed()
    ids = [uuid4(), uuid4()]
    for message_id in ids:
        cursor.execute(
            "insert into messages(id,user_id,conversation_id,role,content) values (%s,%s,%s,'assistant','A grounded answer')",
            (message_id, fixture.owner_id, fixture.conversation_id),
        )
    return fixture, ids


def insert(cursor, fixture, ids, *, key=None, runs=(), artifacts=()):
    public_id = _public_id()
    cursor.execute(
        "insert into public_excerpt_snapshots(public_id,owner_id,source_conversation_id,source_message_ids,source_run_ids,source_artifact_ids,selection_key,kind,title,payload,payload_digest) values (%s,%s,%s,%s,%s,%s,%s,'research_answer','Question','{}','"
        + "a" * 64
        + "') returning id",
        (
            public_id,
            fixture.owner_id,
            fixture.conversation_id,
            ids,
            list(runs),
            list(artifacts),
            key or "b" * 64,
        ),
    )
    return cursor.fetchone()[0]


def test_new_selection_locks_sources_and_each_message_delete_revokes():
    with psycopg.connect(DSN) as connection:
        fixture, ids = seed(connection)
        snapshot = insert(connection.cursor(), fixture, ids)
        connection.execute("delete from messages where id=%s", (ids[-1],))
        assert (
            connection.execute(
                "select revocation_reason from public_excerpt_snapshots where id=%s",
                (snapshot,),
            ).fetchone()[0]
            == "source_deleted"
        )
        connection.rollback()


@pytest.mark.parametrize("source", ["message", "run", "artifact"])
def test_missing_or_foreign_selected_source_refuses(source):
    with psycopg.connect(DSN) as connection:
        fixture, ids = seed(connection)
        bad = uuid4()
        with pytest.raises(psycopg.errors.CheckViolation):
            insert(
                connection.cursor(),
                fixture,
                [bad] if source == "message" else ids,
                runs=[bad] if source == "run" else [],
                artifacts=[bad] if source == "artifact" else [],
            )
        connection.rollback()


@pytest.mark.parametrize(
    "column",
    [
        "source_message_ids",
        "source_run_ids",
        "source_artifact_ids",
        "selection_key",
        "kind",
    ],
)
def test_selection_lineage_is_immutable(column):
    from psycopg import sql

    with psycopg.connect(DSN) as connection:
        fixture, ids = seed(connection)
        snapshot = insert(connection.cursor(), fixture, ids)
        value = (
            "c" * 64
            if column == "selection_key"
            else "mixed"
            if column == "kind"
            else [uuid4()]
        )
        with pytest.raises(psycopg.errors.CheckViolation):
            connection.execute(
                sql.SQL("update public_excerpt_snapshots set {}=%s where id=%s").format(
                    sql.Identifier(column)
                ),
                (value, snapshot),
            )
        connection.rollback()


def test_selection_unique_constraint_resolves_concurrent_creates():
    with psycopg.connect(DSN) as setup:
        fixture, ids = seed(setup)
        setup.commit()
    try:
        started = Event()
        backend_pids = []

        def second():
            with psycopg.connect(DSN) as connection:
                backend_pids.append(connection.info.backend_pid)
                started.set()
                try:
                    insert(connection.cursor(), fixture, ids)
                    connection.commit()
                    return "created"
                except psycopg.errors.UniqueViolation:
                    return "existing"

        with psycopg.connect(DSN) as first, ThreadPoolExecutor(max_workers=1) as pool:
            insert(first.cursor(), fixture, ids)
            future = pool.submit(second)
            assert started.wait(5)
            from time import monotonic, sleep

            with psycopg.connect(DSN, autocommit=True) as observer:
                deadline = monotonic() + 5
                while monotonic() < deadline:
                    if observer.execute(
                        "select cardinality(pg_blocking_pids(%s))", (backend_pids[0],)
                    ).fetchone()[0]:
                        break
                    sleep(0.01)
                else:
                    pytest.fail(
                        "Concurrent insert never waited on the winner's transaction"
                    )
            first.commit()
            assert future.result(timeout=10) == "existing"
        with psycopg.connect(DSN) as check:
            assert (
                check.execute(
                    "select count(*) from public_excerpt_snapshots where owner_id=%s and selection_key=%s",
                    (fixture.owner_id, "b" * 64),
                ).fetchone()[0]
                == 1
            )
    finally:
        with psycopg.connect(DSN) as cleanup:
            cleanup.execute("delete from auth.users where id=%s", (fixture.owner_id,))


def test_moderation_revocation_reason_is_retained_without_a_new_public_surface():
    with psycopg.connect(DSN) as connection:
        fixture, ids = seed(connection)
        snapshot = insert(connection.cursor(), fixture, ids)
        connection.execute(
            "update public_excerpt_snapshots set revoked_at=now(),revocation_reason='removed_by_argus' where id=%s",
            (snapshot,),
        )
        assert (
            connection.execute(
                "select revocation_reason from public_excerpt_snapshots where id=%s",
                (snapshot,),
            ).fetchone()[0]
            == "removed_by_argus"
        )
        connection.rollback()


@pytest.mark.parametrize(
    "source_table", ["messages", "backtest_runs", "evidence_artifacts"]
)
def test_selected_source_delete_blocks_creation_until_it_can_refuse(source_table):
    """Real row-lock contention, followed by a committed-delete refusal."""
    from psycopg import sql

    with psycopg.connect(DSN) as setup:
        fixture, ids = seed(setup)
        if source_table == "backtest_runs":
            fixture.drop_idea_spine()
        setup.commit()
    source_id = (
        ids[-1]
        if source_table == "messages"
        else fixture.run_id
        if source_table == "backtest_runs"
        else fixture.artifact_id
    )
    try:
        with psycopg.connect(DSN) as deleter, psycopg.connect(DSN) as inserter:
            deleter.execute(
                sql.SQL("delete from {} where id=%s").format(
                    sql.Identifier(source_table)
                ),
                (source_id,),
            )
            inserter.execute("set local lock_timeout = '300ms'")
            with pytest.raises(psycopg.errors.LockNotAvailable):
                insert(
                    inserter.cursor(),
                    fixture,
                    ids,
                    runs=[fixture.run_id] if source_table == "backtest_runs" else [],
                    artifacts=[fixture.artifact_id]
                    if source_table == "evidence_artifacts"
                    else [],
                )
            inserter.rollback()
            deleter.commit()
            with pytest.raises(psycopg.errors.CheckViolation):
                insert(
                    inserter.cursor(),
                    fixture,
                    ids,
                    runs=[fixture.run_id] if source_table == "backtest_runs" else [],
                    artifacts=[fixture.artifact_id]
                    if source_table == "evidence_artifacts"
                    else [],
                )
            inserter.rollback()
    finally:
        with psycopg.connect(DSN) as cleanup:
            cleanup.execute("delete from auth.users where id=%s", (fixture.owner_id,))


@pytest.mark.parametrize(
    "action,allowed", [("share_result", True), ("keep_history", False)]
)
def test_guest_conversion_sql_accepts_only_message_bound_share_actions(action, allowed):
    from psycopg.types.json import Jsonb

    conversation_id = uuid4()
    pending = {
        "reason": action,
        "conversation_id": str(conversation_id),
        "action_id": str(uuid4()),
        "message_id": str(uuid4()),
    }
    with psycopg.connect(DSN) as connection:
        result = connection.execute(
            "select argus_private.valid_guest_pending_action(%s,%s)",
            (Jsonb(pending), conversation_id),
        ).fetchone()[0]
        assert result is allowed
