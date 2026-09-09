"""Receipt source identity and deletion races under real PostgreSQL locks."""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from uuid import uuid4

import pytest
from faker import Faker

psycopg = pytest.importorskip("psycopg")
DSN = os.getenv("ARGUS_DISPOSABLE_DATABASE_URL", "").strip()
pytestmark = pytest.mark.skipif(not DSN, reason="isolated Postgres URL not configured")
fake = Faker()


@pytest.fixture
def source():
    owner, conversation, message, artifact = [str(uuid4()) for _ in range(4)]
    email = fake.email()
    card = {
        "kind": "tool_result",
        "artifact_id": artifact,
        "input_revision": 0,
        "outcome": {"status": "succeeded"},
    }
    with psycopg.connect(DSN) as connection:
        connection.execute(
            "insert into auth.users(id,email) values (%s,%s)", (owner, email)
        )
        connection.execute(
            "insert into public.profiles(id,email,username) values (%s,%s,%s)",
            (owner, email, owner[:8]),
        )
        connection.execute(
            "insert into public.conversations(id,user_id,title) values (%s,%s,%s)",
            (conversation, owner, fake.sentence()),
        )
        connection.execute(
            "insert into public.messages(id,conversation_id,user_id,role,content,metadata) values (%s,%s,%s,'assistant','',%s::jsonb)",
            (message, conversation, owner, json.dumps({"tool_result_cards": [card]})),
        )
    yield owner, conversation, message, artifact
    with psycopg.connect(DSN) as connection:
        connection.execute("delete from public.profiles where id=%s", (owner,))
        connection.execute("delete from auth.users where id=%s", (owner,))


def insert(connection, source, *, revision=0, owner=None):
    owner_id, conversation, message, artifact = source
    snapshot = str(uuid4())
    connection.execute(
        "insert into public.public_excerpt_snapshots(id,public_id,owner_id,source_conversation_id,source_message_id,source_artifact_id,source_input_revision,title,payload,payload_digest) values (%s,%s,%s,%s,%s,%s,%s,'',%s::jsonb,%s)",
        (
            snapshot,
            uuid4().hex,
            owner or owner_id,
            conversation,
            message,
            artifact,
            revision,
            json.dumps({"schema_version": 2}),
            "a" * 64,
        ),
    )
    return snapshot


def test_concurrent_repeated_source_creates_one_live_receipt(source) -> None:
    barrier = Barrier(2)

    def create() -> str:
        try:
            with psycopg.connect(DSN) as connection:
                barrier.wait(timeout=10)
                insert(connection, source)
            return "created"
        except psycopg.errors.UniqueViolation:
            return "duplicate"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: create(), range(2)))
    assert sorted(results) == ["created", "duplicate"]


@pytest.mark.parametrize(
    "column,value",
    [
        ("source_artifact_id", str(uuid4())),
        ("source_input_revision", 1),
        ("source_message_id", None),
    ],
)
def test_tool_source_identity_is_immutable(source, column, value) -> None:
    with psycopg.connect(DSN) as connection:
        snapshot = insert(connection, source)
    with psycopg.connect(DSN) as connection, pytest.raises(psycopg.errors.CheckViolation):
        connection.execute(
            f"update public.public_excerpt_snapshots set {column}=%s where id=%s",
            (value, snapshot),
        )


def test_changed_card_revision_refuses_snapshot(source) -> None:
    with psycopg.connect(DSN) as connection, pytest.raises(psycopg.errors.CheckViolation):
        insert(connection, source, revision=1)


def test_deleting_message_revokes_receipt_and_keeps_tombstone(source) -> None:
    with psycopg.connect(DSN) as connection:
        snapshot = insert(connection, source)
        connection.execute("delete from public.messages where id=%s", (source[2],))
        row = connection.execute(
            "select source_message_id,revoked_at,revocation_reason from public.public_excerpt_snapshots where id=%s",
            (snapshot,),
        ).fetchone()
        assert row[0] is None and row[1] is not None and row[2] == "source_deleted"


def test_conversation_deleted_before_insert_cannot_create_receipt(source) -> None:
    with psycopg.connect(DSN) as connection:
        connection.execute(
            "update public.conversations set deleted_at=now() where id=%s", (source[1],)
        )
    with psycopg.connect(DSN) as connection, pytest.raises(psycopg.errors.CheckViolation):
        insert(connection, source)


@pytest.mark.parametrize("change", ["edit", "delete_conversation"])
def test_inflight_receipt_waits_for_source_writer_and_refuses_stale_snapshot(
    source, change
) -> None:
    ready = Event()
    reader_pid: list[int] = []

    def create() -> str:
        with psycopg.connect(DSN) as connection:
            reader_pid.append(connection.info.backend_pid)
            ready.set()
            try:
                insert(connection, source)
            except psycopg.errors.CheckViolation as exc:
                return str(exc)
        return "created"

    with psycopg.connect(DSN) as writer, ThreadPoolExecutor(max_workers=1) as pool:
        if change == "edit":
            writer.execute(
                "update public.messages set metadata=jsonb_set(metadata,'{tool_result_cards,0,input_revision}','1'::jsonb) where id=%s",
                (source[2],),
            )
        else:
            writer.execute(
                "update public.conversations set deleted_at=now() where id=%s",
                (source[1],),
            )
        future = pool.submit(create)
        assert ready.wait(timeout=5)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            blocked = writer.execute(
                "select cardinality(pg_blocking_pids(%s)) > 0", (reader_pid[0],)
            ).fetchone()[0]
            if blocked:
                break
            time.sleep(0.01)
        writer.commit()
        assert (
            blocked
        ), "The receipt insert must actually overlap the locked source write."
        refusal = future.result(timeout=5)
        assert (
            "public_excerpt_source_changed" in refusal
            if change == "edit"
            else "public_excerpt_source_deleted" in refusal
        )
    with psycopg.connect(DSN) as connection:
        assert (
            connection.execute(
                "select count(*) from public.public_excerpt_snapshots where owner_id=%s",
                (source[0],),
            ).fetchone()[0]
            == 0
        )
