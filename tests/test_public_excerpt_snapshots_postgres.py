"""Real-Postgres proofs for public evidence receipts.

The two guarantees this table exists to make are enforced by the database, not by
callers, so they have to be proven against a real Postgres:

  1. A snapshot is immutable and revocation cannot be reversed.
  2. Deleting the source revokes the receipt, whichever way the source goes away.

Set ``ARGUS_DISPOSABLE_DATABASE_URL`` only to an isolated Supabase Postgres
database with every checked-in migration applied; never point it at shared or
production data.
"""

from __future__ import annotations

import json
import os
from typing import Any
from uuid import uuid4

import pytest

DSN = os.getenv("ARGUS_DISPOSABLE_DATABASE_URL", "").strip()

pytestmark = pytest.mark.skipif(
    not DSN,
    reason="ARGUS_DISPOSABLE_DATABASE_URL is not configured",
)

psycopg = pytest.importorskip("psycopg")

DIGEST = "a" * 64
PAYLOAD = {
    "schema_version": 1,
    "idea_title": "AAPL buy and hold",
    "symbols": ["AAPL"],
    "assumptions": [],
    "date_range": {
        "start": "2024-01-02",
        "end": "2024-03-01",
        "display": "Jan 2, 2024 to Mar 1, 2024",
    },
    "metrics": [],
    "content_language": "en",
    "framing": "historical_simulation_not_advice",
    "provenance_mark": "tested_with_argus",
}


def _public_id() -> str:
    return uuid4().hex + uuid4().hex[:8]


class _Fixture:
    """One owner with a conversation, run, idea spine, artifact and receipt."""

    def __init__(self, cursor: Any) -> None:
        self.cursor = cursor
        self.owner_id = str(uuid4())
        self.conversation_id = str(uuid4())
        self.strategy_id = str(uuid4())
        self.run_id = str(uuid4())
        self.idea_id = str(uuid4())
        self.idea_version_id = str(uuid4())
        self.artifact_id = str(uuid4())
        self.snapshot_id = str(uuid4())
        self.public_id = _public_id()

    def seed(self) -> None:
        email = f"receipt-{self.owner_id}@example.test"
        self.cursor.execute(
            "insert into auth.users (id, email) values (%s, %s)",
            (self.owner_id, email),
        )
        self.cursor.execute(
            "insert into public.profiles (id, email, username) values (%s, %s, %s)",
            (self.owner_id, email, f"receipt-{self.owner_id[:8]}"),
        )
        self.cursor.execute(
            "insert into public.conversations (id, user_id, title)"
            " values (%s, %s, %s)",
            (self.conversation_id, self.owner_id, "AAPL idea"),
        )
        self.cursor.execute(
            "insert into public.strategies"
            " (id, user_id, name, template, asset_class, symbols, benchmark_symbol)"
            " values (%s, %s, %s, %s, %s, %s, %s)",
            (
                self.strategy_id,
                self.owner_id,
                "Buy and hold",
                "buy_and_hold",
                "equity",
                ["AAPL"],
                "SPY",
            ),
        )
        self.cursor.execute(
            "insert into public.backtest_runs"
            " (id, user_id, conversation_id, strategy_id, status, asset_class,"
            "  symbols, allocation_method, benchmark_symbol, metrics,"
            "  config_snapshot, conversation_result_card)"
            " values (%s, %s, %s, %s, 'completed', 'equity', %s, 'equal_weight',"
            "  'SPY', '{}'::jsonb, '{}'::jsonb, '{}'::jsonb)",
            (
                self.run_id,
                self.owner_id,
                self.conversation_id,
                self.strategy_id,
                ["AAPL"],
            ),
        )
        self.cursor.execute(
            "insert into public.ideas (id, user_id, source_conversation_id, title)"
            " values (%s, %s, %s, %s)",
            (self.idea_id, self.owner_id, self.conversation_id, "AAPL idea"),
        )
        self.cursor.execute(
            "insert into public.idea_versions"
            " (id, user_id, idea_id, source_conversation_id, source_run_id, title)"
            " values (%s, %s, %s, %s, %s, %s)",
            (
                self.idea_version_id,
                self.owner_id,
                self.idea_id,
                self.conversation_id,
                self.run_id,
                "AAPL idea",
            ),
        )
        self.cursor.execute(
            "insert into public.evidence_artifacts"
            " (id, user_id, idea_id, idea_version_id, source_conversation_id,"
            "  source_run_id, title, digest, payload)"
            " values (%s, %s, %s, %s, %s, %s, %s, %s, '{}'::jsonb)",
            (
                self.artifact_id,
                self.owner_id,
                self.idea_id,
                self.idea_version_id,
                self.conversation_id,
                self.run_id,
                "AAPL idea",
                "digest",
            ),
        )
        self.insert_snapshot()

    def insert_snapshot(self, snapshot_id: str | None = None) -> str:
        identifier = snapshot_id or self.snapshot_id
        public_id = self.public_id if snapshot_id is None else _public_id()
        self.cursor.execute(
            "insert into public.public_excerpt_snapshots"
            " (id, public_id, owner_id, evidence_artifact_id,"
            "  source_conversation_id, source_run_id, title, payload, payload_digest)"
            " values (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                identifier,
                public_id,
                self.owner_id,
                self.artifact_id,
                self.conversation_id,
                self.run_id,
                "AAPL buy and hold",
                json.dumps(PAYLOAD),
                DIGEST,
            ),
        )
        return public_id

    def drop_idea_spine(self) -> None:
        """Remove the receipt and the idea spine so a source row can be purged.

        The idea spine blocks a hard delete of its conversation and run, and its
        own removal cascades into the artifact, which revokes the receipt. So the
        receipt is dropped first and reinserted afterwards.
        """
        self.cursor.execute(
            "delete from public.public_excerpt_snapshots where id = %s",
            (self.snapshot_id,),
        )
        self.cursor.execute(
            "delete from public.ideas where id = %s", (self.idea_id,)
        )

    def reinsert_snapshot(
        self, *, conversation_id: str | None = None, run_id: str | None = None
    ) -> None:
        self.cursor.execute(
            "insert into public.public_excerpt_snapshots"
            " (id, public_id, owner_id, source_conversation_id, source_run_id,"
            "  title, payload, payload_digest)"
            " values (%s, %s, %s, %s, %s, %s, %s, %s)",
            (
                self.snapshot_id,
                _public_id(),
                self.owner_id,
                conversation_id,
                run_id,
                "AAPL buy and hold",
                json.dumps(PAYLOAD),
                DIGEST,
            ),
        )

    def revocation(self) -> tuple[Any, Any]:
        self.cursor.execute(
            "select revoked_at, revocation_reason"
            " from public.public_excerpt_snapshots where id = %s",
            (self.snapshot_id,),
        )
        return self.cursor.fetchone()


def _fixture(cursor: Any) -> _Fixture:
    fixture = _Fixture(cursor)
    fixture.seed()
    return fixture


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("payload", json.dumps({**PAYLOAD, "idea_title": "rewritten"})),
        ("public_id", "c" * 32),
        ("payload_digest", "b" * 64),
        ("title", "rewritten"),
        ("owner_id", "00000000-0000-4000-8000-000000000000"),
        ("created_at", "2020-01-01T00:00:00+00:00"),
    ],
)
def test_every_frozen_column_refuses_an_update(column: str, value: str) -> None:
    with psycopg.connect(DSN) as connection:
        try:
            with connection.cursor() as cursor:
                fixture = _fixture(cursor)
                with pytest.raises(psycopg.errors.CheckViolation):
                    cursor.execute(
                        "update public.public_excerpt_snapshots"
                        f" set {column} = %s where id = %s",
                        (value, fixture.snapshot_id),
                    )
        finally:
            connection.rollback()


def test_revocation_cannot_be_reversed() -> None:
    with psycopg.connect(DSN) as connection:
        try:
            with connection.cursor() as cursor:
                fixture = _fixture(cursor)
                cursor.execute(
                    "update public.public_excerpt_snapshots"
                    " set revoked_at = now(), revocation_reason = 'owner_revoked'"
                    " where id = %s",
                    (fixture.snapshot_id,),
                )
                revoked_at, reason = fixture.revocation()
                assert revoked_at is not None
                assert reason == "owner_revoked"

                with pytest.raises(psycopg.errors.CheckViolation):
                    cursor.execute(
                        "update public.public_excerpt_snapshots"
                        " set revoked_at = null, revocation_reason = null"
                        " where id = %s",
                        (fixture.snapshot_id,),
                    )
        finally:
            connection.rollback()


def test_revocation_columns_must_move_together() -> None:
    with psycopg.connect(DSN) as connection:
        try:
            with connection.cursor() as cursor:
                fixture = _fixture(cursor)
                with pytest.raises(psycopg.errors.CheckViolation):
                    cursor.execute(
                        "update public.public_excerpt_snapshots"
                        " set revoked_at = now() where id = %s",
                        (fixture.snapshot_id,),
                    )
        finally:
            connection.rollback()


def test_soft_deleting_the_conversation_revokes_the_receipt() -> None:
    with psycopg.connect(DSN) as connection:
        try:
            with connection.cursor() as cursor:
                fixture = _fixture(cursor)
                cursor.execute(
                    "update public.conversations set deleted_at = now() where id = %s",
                    (fixture.conversation_id,),
                )
                revoked_at, reason = fixture.revocation()
                assert revoked_at is not None
                assert reason == "source_deleted"
        finally:
            connection.rollback()


def test_hard_deleting_a_conversation_is_already_impossible_with_an_idea_spine() -> None:
    """Pre-existing, and it predates receipts entirely.

    ``idea_versions.source_conversation_id`` is ``on delete set null`` while
    ``prevent_idea_version_immutable_update`` forbids changing that column, so a
    captured conversation cannot be hard deleted. Argus only soft deletes, so this
    never surfaces in the product. Recorded here because it is why the purge
    triggers below are a backstop rather than the live path.
    """
    with psycopg.connect(DSN) as connection:
        try:
            with connection.cursor() as cursor:
                fixture = _fixture(cursor)
                with pytest.raises(psycopg.errors.CheckViolation) as failure:
                    cursor.execute(
                        "delete from public.conversations where id = %s",
                        (fixture.conversation_id,),
                    )
                assert "idea_versions immutable fields" in str(failure.value)
        finally:
            connection.rollback()


def test_hard_deleting_a_bare_conversation_revokes_rather_than_orphaning() -> None:
    with psycopg.connect(DSN) as connection:
        try:
            with connection.cursor() as cursor:
                fixture = _fixture(cursor)
                fixture.drop_idea_spine()
                fixture.reinsert_snapshot(
                    conversation_id=fixture.conversation_id,
                    run_id=fixture.run_id,
                )
                cursor.execute(
                    "delete from public.conversations where id = %s",
                    (fixture.conversation_id,),
                )
                revoked_at, reason = fixture.revocation()
                assert revoked_at is not None
                assert reason == "source_deleted"
                # The tombstone survives what it pointed at.
                cursor.execute(
                    "select source_conversation_id"
                    " from public.public_excerpt_snapshots where id = %s",
                    (fixture.snapshot_id,),
                )
                assert cursor.fetchone()[0] is None
        finally:
            connection.rollback()


def test_deleting_the_evidence_artifact_revokes_the_receipt() -> None:
    with psycopg.connect(DSN) as connection:
        try:
            with connection.cursor() as cursor:
                fixture = _fixture(cursor)
                cursor.execute(
                    "delete from public.evidence_artifacts where id = %s",
                    (fixture.artifact_id,),
                )
                revoked_at, reason = fixture.revocation()
                assert revoked_at is not None
                assert reason == "source_deleted"
                cursor.execute(
                    "select evidence_artifact_id"
                    " from public.public_excerpt_snapshots where id = %s",
                    (fixture.snapshot_id,),
                )
                assert cursor.fetchone()[0] is None
        finally:
            connection.rollback()


def test_deleting_the_backtest_run_revokes_the_receipt() -> None:
    with psycopg.connect(DSN) as connection:
        try:
            with connection.cursor() as cursor:
                fixture = _fixture(cursor)
                fixture.drop_idea_spine()
                fixture.reinsert_snapshot(run_id=fixture.run_id)
                cursor.execute(
                    "delete from public.backtest_runs where id = %s",
                    (fixture.run_id,),
                )
                revoked_at, reason = fixture.revocation()
                assert revoked_at is not None
                assert reason == "source_deleted"
                cursor.execute(
                    "select source_run_id from public.public_excerpt_snapshots"
                    " where id = %s",
                    (fixture.snapshot_id,),
                )
                assert cursor.fetchone()[0] is None
        finally:
            connection.rollback()


def test_deleting_the_owner_removes_the_receipt_entirely() -> None:
    with psycopg.connect(DSN) as connection:
        try:
            with connection.cursor() as cursor:
                fixture = _fixture(cursor)
                cursor.execute(
                    "delete from public.profiles where id = %s", (fixture.owner_id,)
                )
                cursor.execute(
                    "select count(*) from public.public_excerpt_snapshots"
                    " where id = %s",
                    (fixture.snapshot_id,),
                )
                assert cursor.fetchone()[0] == 0
        finally:
            connection.rollback()


def test_only_one_live_receipt_per_result_but_resharing_stays_possible() -> None:
    with psycopg.connect(DSN) as connection:
        try:
            with connection.cursor() as cursor:
                fixture = _fixture(cursor)
                second_id = str(uuid4())
                with pytest.raises(psycopg.errors.UniqueViolation):
                    fixture.insert_snapshot(snapshot_id=second_id)
                connection.rollback()

                fixture = _fixture(cursor)
                cursor.execute(
                    "update public.public_excerpt_snapshots"
                    " set revoked_at = now(), revocation_reason = 'owner_revoked'"
                    " where id = %s",
                    (fixture.snapshot_id,),
                )
                fixture.insert_snapshot(snapshot_id=str(uuid4()))
                cursor.execute(
                    "select count(*) from public.public_excerpt_snapshots"
                    " where evidence_artifact_id = %s and revoked_at is null",
                    (fixture.artifact_id,),
                )
                assert cursor.fetchone()[0] == 1
        finally:
            connection.rollback()


def test_anonymous_role_cannot_read_the_table() -> None:
    with psycopg.connect(DSN) as connection:
        try:
            with connection.cursor() as cursor:
                _fixture(cursor)
                cursor.execute("set local role anon")
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    cursor.execute(
                        "select public_id from public.public_excerpt_snapshots"
                    )
        finally:
            connection.rollback()


@pytest.mark.parametrize("role", ["anon", "authenticated"])
def test_no_browser_role_can_reach_the_receipt_table(role: str) -> None:
    """Not even the owner's own session. Both audiences go through the backend.

    This is stronger than an owner-read policy: the owner and source columns are
    not one PostgREST call away from any browser, so the audience split cannot be
    bypassed by crafting a request.
    """
    with psycopg.connect(DSN) as connection:
        try:
            with connection.cursor() as cursor:
                fixture = _fixture(cursor)
                cursor.execute(f"set local role {role}")
                cursor.execute(
                    "select set_config('request.jwt.claims', %s, true)",
                    (
                        json.dumps(
                            {
                                "sub": fixture.owner_id,
                                "role": role,
                                "is_anonymous": role == "anon",
                            }
                        ),
                    ),
                )
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    cursor.execute(
                        "select public_id from public.public_excerpt_snapshots"
                    )
        finally:
            connection.rollback()


def test_a_receipt_cannot_be_inserted_for_a_soft_deleted_conversation() -> None:
    with psycopg.connect(DSN) as connection:
        try:
            with connection.cursor() as cursor:
                fixture = _Fixture(cursor)
                fixture.owner_id = fixture.owner_id
                fixture.seed()
                cursor.execute(
                    "delete from public.public_excerpt_snapshots where id = %s",
                    (fixture.snapshot_id,),
                )
                cursor.execute(
                    "update public.conversations set deleted_at = now() where id = %s",
                    (fixture.conversation_id,),
                )
                with pytest.raises(psycopg.errors.CheckViolation) as failure:
                    fixture.insert_snapshot()
                assert "public_excerpt_source_deleted" in str(failure.value)
        finally:
            connection.rollback()


def test_a_receipt_cannot_be_inserted_for_a_conversation_that_is_gone() -> None:
    with psycopg.connect(DSN) as connection:
        try:
            with connection.cursor() as cursor:
                fixture = _Fixture(cursor)
                fixture.seed()
                fixture.drop_idea_spine()
                cursor.execute(
                    "delete from public.conversations where id = %s",
                    (fixture.conversation_id,),
                )
                # The foreign key refuses first, which is the same outcome: no page.
                with pytest.raises(
                    (
                        psycopg.errors.CheckViolation,
                        psycopg.errors.ForeignKeyViolation,
                    )
                ):
                    fixture.reinsert_snapshot(
                        conversation_id=fixture.conversation_id
                    )
        finally:
            connection.rollback()


def test_a_soft_delete_racing_an_insert_cannot_leave_a_live_receipt() -> None:
    """The race an application check cannot close.

    Two transactions: one inserts a receipt, the other soft deletes its source. The
    insert takes FOR SHARE on the conversation, so whichever order they commit in,
    the receipt does not end up live for a deleted chat.
    """
    with psycopg.connect(DSN) as setup:
        with setup.cursor() as cursor:
            fixture = _Fixture(cursor)
            fixture.seed()
            cursor.execute(
                "delete from public.public_excerpt_snapshots where id = %s",
                (fixture.snapshot_id,),
            )
        setup.commit()
        try:
            deleter = psycopg.connect(DSN)
            inserter = psycopg.connect(DSN)
            try:
                # The delete goes first and holds its row lock uncommitted.
                with deleter.cursor() as delete_cursor:
                    delete_cursor.execute(
                        "update public.conversations set deleted_at = now()"
                        " where id = %s",
                        (fixture.conversation_id,),
                    )
                    # The insert must not slip past while that is in flight.
                    with inserter.cursor() as insert_cursor:
                        insert_cursor.execute("set local lock_timeout = '400ms'")
                        blocked = _Fixture(insert_cursor)
                        blocked.owner_id = fixture.owner_id
                        blocked.conversation_id = fixture.conversation_id
                        blocked.artifact_id = fixture.artifact_id
                        blocked.run_id = fixture.run_id
                        with pytest.raises(
                            (
                                psycopg.errors.LockNotAvailable,
                                psycopg.errors.CheckViolation,
                            )
                        ):
                            blocked.insert_snapshot(snapshot_id=str(uuid4()))
                        inserter.rollback()
                    deleter.commit()

                # After the delete commits, the insert is refused outright.
                with inserter.cursor() as retry_cursor:
                    retry = _Fixture(retry_cursor)
                    retry.owner_id = fixture.owner_id
                    retry.conversation_id = fixture.conversation_id
                    retry.artifact_id = fixture.artifact_id
                    retry.run_id = fixture.run_id
                    with pytest.raises(psycopg.errors.CheckViolation) as failure:
                        retry.insert_snapshot(snapshot_id=str(uuid4()))
                    assert "public_excerpt_source_deleted" in str(failure.value)
                    inserter.rollback()

                with setup.cursor() as check:
                    check.execute(
                        "select count(*) from public.public_excerpt_snapshots"
                        " where source_conversation_id = %s and revoked_at is null",
                        (fixture.conversation_id,),
                    )
                    assert check.fetchone()[0] == 0
            finally:
                deleter.rollback()
                deleter.close()
                inserter.rollback()
                inserter.close()
        finally:
            with psycopg.connect(DSN, autocommit=True) as cleanup:
                with cleanup.cursor() as cursor:
                    cursor.execute(
                        "delete from public.profiles where id = %s",
                        (fixture.owner_id,),
                    )
                    cursor.execute(
                        "delete from auth.users where id = %s", (fixture.owner_id,)
                    )
