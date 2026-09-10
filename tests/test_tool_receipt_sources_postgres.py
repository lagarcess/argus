"""Receipt source identity and deletion races under real PostgreSQL locks."""

from __future__ import annotations

import hashlib
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
    from argus.domain.tool_contracts import ToolCall, ToolOutcome

    from tests.public_excerpt_tool_factories import identity_declaration

    owner, conversation, message, artifact = [str(uuid4()) for _ in range(4)]
    email = fake.email()
    card = (
        identity_declaration()
        .result_card(
            call=ToolCall(
                tool_name="identity_value",
                call_id=str(uuid4()),
                arguments={"known": 0, "unknown": None},
            ),
            outcome=ToolOutcome(status="succeeded", result={"value": 0}),
            artifact_id=artifact,
        )
        .model_dump(mode="json")
    )
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


def insert(connection, source, *, revision=0, owner=None, selected=False, bindings=None):
    owner_id, conversation, message, artifact = source
    snapshot = str(uuid4())
    if selected:
        bindings = (
            bindings
            if bindings is not None
            else [
                {
                    "message_id": message,
                    "artifact_id": artifact,
                    "input_revision": revision,
                }
            ]
        )
        key = hashlib.sha256(json.dumps(bindings, sort_keys=True).encode()).hexdigest()
        connection.execute(
            "insert into public.public_excerpt_snapshots(id,public_id,owner_id,source_conversation_id,source_message_ids,source_tool_bindings,selection_key,kind,title,payload,payload_digest) values (%s,%s,%s,%s,%s,%s::jsonb,%s,'tool_result','',%s::jsonb,%s)",
            (
                snapshot,
                uuid4().hex,
                owner or owner_id,
                conversation,
                [message],
                json.dumps(bindings),
                key,
                json.dumps({"schema_version": 2, "kind": "turns"}),
                "a" * 64,
            ),
        )
        return snapshot
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
@pytest.mark.parametrize("selected", [False, True])
def test_inflight_receipt_waits_for_source_writer_and_refuses_stale_snapshot(
    source, change, selected
) -> None:
    ready = Event()
    reader_pid: list[int] = []

    def create() -> str:
        with psycopg.connect(DSN) as connection:
            reader_pid.append(connection.info.backend_pid)
            ready.set()
            try:
                insert(connection, source, selected=selected)
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


def test_selected_tool_bindings_remain_private_immutable_provenance(source):
    with psycopg.connect(DSN) as connection:
        snapshot = insert(connection, source, selected=True)
    with psycopg.connect(DSN) as connection, pytest.raises(psycopg.errors.CheckViolation):
        connection.execute(
            "update public.public_excerpt_snapshots set source_tool_bindings='[]'::jsonb where id=%s",
            (snapshot,),
        )
    with psycopg.connect(DSN) as connection:
        connection.execute("delete from public.messages where id=%s", (source[2],))
        row = connection.execute(
            "select source_message_ids,source_tool_bindings,revoked_at,revocation_reason,source_artifact_ids,source_run_ids from public.public_excerpt_snapshots where id=%s",
            (snapshot,),
        ).fetchone()
        assert list(map(str, row[0])) == [source[2]]
        assert row[1] == [
            {"message_id": source[2], "artifact_id": source[3], "input_revision": 0}
        ]
        assert row[2] is not None and row[3] == "source_deleted"
        assert row[4] == [] and row[5] == []


@pytest.mark.parametrize(
    "mutation", ["missing", "reordered", "duplicate", "wrong_message", "pending"]
)
def test_selected_snapshot_requires_every_sibling_in_exact_order(source, mutation):
    from copy import deepcopy

    with psycopg.connect(DSN) as connection:
        metadata = connection.execute(
            "select metadata from public.messages where id=%s", (source[2],)
        ).fetchone()[0]
        cards = metadata["tool_result_cards"]
        sibling = deepcopy(cards[0])
        sibling.update(artifact_id=str(uuid4()), call_id=str(uuid4()))
        cards.append(sibling)
        bindings = [
            {
                "message_id": source[2],
                "artifact_id": card["artifact_id"],
                "input_revision": 0,
            }
            for card in cards
        ]
        if mutation == "missing":
            bindings.pop()
        elif mutation == "reordered":
            bindings.reverse()
        elif mutation == "duplicate":
            bindings[1] = bindings[0]
        elif mutation == "wrong_message":
            bindings[1]["message_id"] = str(uuid4())
        else:
            sibling["presentation"]["answer"] = None
        connection.execute(
            "update public.messages set metadata=%s::jsonb where id=%s",
            (json.dumps(metadata), source[2]),
        )
    with psycopg.connect(DSN) as connection, pytest.raises(psycopg.errors.CheckViolation):
        insert(connection, source, selected=True, bindings=bindings)
    with psycopg.connect(DSN) as connection:
        assert (
            connection.execute(
                "select count(*) from public.public_excerpt_snapshots where owner_id=%s",
                (source[0],),
            ).fetchone()[0]
            == 0
        )
