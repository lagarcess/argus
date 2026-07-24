"""Real-Postgres guest cleanup ordering and permanent-account safety proofs."""

from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier

import pytest

DSN = os.getenv("ARGUS_DISPOSABLE_DATABASE_URL", "").strip()
pytestmark = pytest.mark.skipif(
    not DSN,
    reason="ARGUS_DISPOSABLE_DATABASE_URL is not configured",
)
psycopg = pytest.importorskip("psycopg")


def _connect():
    return psycopg.connect(DSN, autocommit=True)


def _seed_expired_guest(connection) -> dict[str, str]:
    user_id = str(uuid.uuid4())
    conversation_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(days=8)
    with connection.cursor() as cursor:
        cursor.execute(
            "insert into auth.users (id, email, is_anonymous)" " values (%s, null, true)",
            (user_id,),
        )
        cursor.execute(
            "insert into public.profiles (id, email) values (%s, null)",
            (user_id,),
        )
        cursor.execute(
            "insert into public.conversations (id, user_id, title)"
            " values (%s, %s, 'expired guest')",
            (conversation_id, user_id),
        )
        cursor.execute(
            "insert into public.messages"
            " (conversation_id, user_id, role, content)"
            " values (%s, %s, 'user', 'private content')",
            (conversation_id, user_id),
        )
        cursor.execute(
            "insert into public.guest_workspaces"
            " (user_id, conversation_id, created_at, expires_at)"
            " values (%s, %s, %s, %s)",
            (
                user_id,
                conversation_id,
                created_at,
                created_at + timedelta(days=7),
            ),
        )
    return {"user_id": user_id, "conversation_id": conversation_id}


def _claim_cleanup(connection, *, dry_run: bool) -> list[tuple[str, str | None]]:
    with connection.cursor() as cursor:
        cursor.execute(
            "select user_id::text, conversation_id::text"
            " from public.claim_expired_guest_workspaces(%s, %s)",
            (25, dry_run),
        )
        return list(cursor.fetchall())


def test_replacing_empty_conversation_preserves_identity_expiry_and_counters() -> None:
    with _connect() as connection:
        user_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).replace(microsecond=0)
        with connection.cursor() as cursor:
            cursor.execute(
                "insert into auth.users (id, email, is_anonymous)"
                " values (%s, null, true)",
                (user_id,),
            )
            cursor.execute(
                "insert into public.profiles (id, email) values (%s, null)",
                (user_id,),
            )
            cursor.execute(
                "insert into public.guest_workspaces"
                " (user_id, created_at, expires_at) values (%s, %s, %s)",
                (user_id, created_at, created_at + timedelta(days=7)),
            )
            cursor.execute(
                "insert into public.conversations (user_id, title)"
                " values (%s, 'first empty chat') returning id::text",
                (user_id,),
            )
            original_conversation_id = cursor.fetchone()[0]
            cursor.execute(
                "insert into public.usage_counters"
                " (user_id, resource, period, period_start, period_end,"
                "  used_count, limit_count)"
                " values (%s, 'chat_messages', 'guest_session', %s, %s, 3, 10)",
                (user_id, created_at, created_at + timedelta(days=7)),
            )
            cursor.execute(
                "select id::text from public.replace_empty_guest_conversation("
                "%s, 'replacement chat', 'system_default', 'en')",
                (user_id,),
            )
            replacement_conversation_id = cursor.fetchone()[0]
            cursor.execute(
                "select user_id::text, conversation_id::text, created_at, expires_at"
                " from public.guest_workspaces where user_id = %s",
                (user_id,),
            )
            workspace = cursor.fetchone()
            cursor.execute(
                "select used_count from public.usage_counters"
                " where user_id = %s and resource = 'chat_messages'"
                " and period = 'guest_session'",
                (user_id,),
            )
            used_count = cursor.fetchone()[0]
            cursor.execute(
                "select count(*) from public.conversations where user_id = %s",
                (user_id,),
            )
            conversation_count = cursor.fetchone()[0]

        assert replacement_conversation_id != original_conversation_id
        assert workspace == (
            user_id,
            replacement_conversation_id,
            created_at,
            created_at + timedelta(days=7),
        )
        assert used_count == 3
        assert conversation_count == 1
        with connection.cursor() as cursor:
            cursor.execute("delete from auth.users where id = %s", (user_id,))


def test_start_over_replaces_complete_graph_but_preserves_guest_policy() -> None:
    with _connect() as connection:
        user_id = str(uuid.uuid4())
        conversation_id = str(uuid.uuid4())
        run_id = str(uuid.uuid4())
        idea_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())
        evidence_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).replace(microsecond=0)
        expires_at = created_at + timedelta(days=7)
        with connection.cursor() as cursor:
            cursor.execute(
                "insert into auth.users (id, email, is_anonymous)"
                " values (%s, null, true)",
                (user_id,),
            )
            cursor.execute(
                "insert into public.profiles (id, email) values (%s, null)",
                (user_id,),
            )
            cursor.execute(
                "insert into public.guest_workspaces"
                " (user_id, created_at, expires_at) values (%s, %s, %s)",
                (user_id, created_at, expires_at),
            )
            cursor.execute(
                "insert into public.conversations (id,user_id,title)"
                " values (%s,%s,'temporary result')",
                (conversation_id, user_id),
            )
            cursor.execute(
                "insert into public.messages (conversation_id,user_id,role,content)"
                " values (%s,%s,'user','test BTC')",
                (conversation_id, user_id),
            )
            cursor.execute(
                "insert into public.backtest_runs"
                " (id,user_id,conversation_id,status,asset_class,symbols,"
                "  benchmark_symbol,config_snapshot,conversation_result_card)"
                " values (%s,%s,%s,'completed','crypto',array['BTC'],'BTC',"
                " '{}'::jsonb,'{}'::jsonb)",
                (run_id, user_id, conversation_id),
            )
            cursor.execute(
                "insert into public.ideas"
                " (id,user_id,source_conversation_id,title)"
                " values (%s,%s,%s,'BTC idea')",
                (idea_id, user_id, conversation_id),
            )
            cursor.execute(
                "insert into public.idea_versions"
                " (id,user_id,idea_id,source_conversation_id,source_run_id,"
                "  title,canonical_spec,strategy_snapshot)"
                " values (%s,%s,%s,%s,%s,'BTC idea','{}'::jsonb,'{}'::jsonb)",
                (version_id, user_id, idea_id, conversation_id, run_id),
            )
            cursor.execute(
                "update public.ideas set active_version_id=%s where id=%s",
                (version_id, idea_id),
            )
            cursor.execute(
                "insert into public.evidence_artifacts"
                " (id,user_id,idea_id,idea_version_id,source_conversation_id,"
                "  source_run_id,title)"
                " values (%s,%s,%s,%s,%s,%s,'BTC result')",
                (
                    evidence_id,
                    user_id,
                    idea_id,
                    version_id,
                    conversation_id,
                    run_id,
                ),
            )
            cursor.execute(
                "insert into public.decision_notes"
                " (user_id,idea_id,idea_version_id,evidence_artifact_id,"
                "  source_conversation_id,decision_state)"
                " values (%s,%s,%s,%s,%s,'watching')",
                (user_id, idea_id, version_id, evidence_id, conversation_id),
            )
            cursor.execute(
                "insert into public.usage_counters"
                " (user_id,resource,period,period_start,period_end,"
                "  used_count,limit_count)"
                " values (%s,'chat_messages','guest_session',%s,%s,4,10)",
                (user_id, created_at, expires_at),
            )
            cursor.execute(
                "insert into public.checkpoints"
                " (thread_id,checkpoint_ns,checkpoint_id,checkpoint)"
                " values (%s,'','checkpoint-start-over','{}'::jsonb)",
                (conversation_id,),
            )

            cursor.execute(
                "select id::text from public.replace_guest_conversation("
                "%s,'New idea','system_default','en')",
                (user_id,),
            )
            replacement_id = cursor.fetchone()[0]
            cursor.execute(
                "select conversation_id::text,created_at,expires_at"
                " from public.guest_workspaces where user_id=%s",
                (user_id,),
            )
            workspace = cursor.fetchone()
            cursor.execute(
                "select used_count from public.usage_counters"
                " where user_id=%s and resource='chat_messages'"
                " and period='guest_session'",
                (user_id,),
            )
            used_count = cursor.fetchone()[0]
            counts = {}
            for table in (
                "messages",
                "backtest_runs",
                "ideas",
                "idea_versions",
                "evidence_artifacts",
                "decision_notes",
            ):
                cursor.execute(
                    f"select count(*) from public.{table} where user_id=%s",
                    (user_id,),
                )
                counts[table] = cursor.fetchone()[0]
            cursor.execute(
                "select count(*) from public.checkpoints where thread_id=%s",
                (conversation_id,),
            )
            checkpoint_count = cursor.fetchone()[0]
            cursor.execute(
                "select count(*) from public.conversations where user_id=%s",
                (user_id,),
            )
            conversation_count = cursor.fetchone()[0]
            cursor.execute(
                "select is_anonymous from auth.users where id=%s",
                (user_id,),
            )
            is_anonymous = cursor.fetchone()[0]

        assert replacement_id != conversation_id
        assert workspace == (replacement_id, created_at, expires_at)
        assert used_count == 4
        assert counts == {
            "messages": 0,
            "backtest_runs": 0,
            "ideas": 0,
            "idea_versions": 0,
            "evidence_artifacts": 0,
            "decision_notes": 0,
        }
        assert checkpoint_count == 0
        assert conversation_count == 1
        assert is_anonymous is True
        with connection.cursor() as cursor:
            cursor.execute("delete from auth.users where id=%s", (user_id,))


def test_cleanup_dry_run_is_bounded_and_changes_nothing() -> None:
    with _connect() as connection:
        guest = _seed_expired_guest(connection)
        rows = _claim_cleanup(connection, dry_run=True)
        assert (guest["user_id"], guest["conversation_id"]) in rows
        with connection.cursor() as cursor:
            cursor.execute(
                "select status, conversation_id from public.guest_workspaces"
                " where user_id = %s",
                (guest["user_id"],),
            )
            status, conversation_id = cursor.fetchone()
            assert status == "active"
            assert str(conversation_id) == guest["conversation_id"]
            cursor.execute("delete from auth.users where id = %s", (guest["user_id"],))


def test_cleanup_dry_run_and_real_run_share_transition_grace_predicate() -> None:
    with psycopg.connect(DSN, autocommit=False) as connection:
        active = _seed_expired_guest(connection)
        stale_expired = _seed_expired_guest(connection)
        recent_expired = _seed_expired_guest(connection)
        permanent = _seed_expired_guest(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                "update public.guest_workspaces"
                " set status = 'expired', updated_at = now() - interval '10 minutes'"
                " where user_id = %s",
                (stale_expired["user_id"],),
            )
            cursor.execute(
                "update public.guest_workspaces"
                " set status = 'expired', updated_at = now() - interval '1 minute'"
                " where user_id = %s",
                (recent_expired["user_id"],),
            )
            cursor.execute(
                "update auth.users" " set is_anonymous = false, email = %s where id = %s",
                (
                    f"permanent-{permanent['user_id'][:8]}@example.com",
                    permanent["user_id"],
                ),
            )
            cursor.execute(
                "update public.profiles set email = %s where id = %s",
                (
                    f"permanent-{permanent['user_id'][:8]}@example.com",
                    permanent["user_id"],
                ),
            )
            fixture_ids = [
                active["user_id"],
                stale_expired["user_id"],
                recent_expired["user_id"],
                permanent["user_id"],
            ]
            cursor.execute(
                "select user_id::text, status, conversation_id::text"
                " from public.guest_workspaces"
                " where user_id = any(%s::uuid[]) order by user_id",
                (fixture_ids,),
            )
            before = cursor.fetchall()
            cursor.execute(
                "select user_id::text, conversation_id::text"
                " from public.claim_expired_guest_workspaces(100, true)",
            )
            dry_ids = {row[0] for row in cursor.fetchall() if row[0] in set(fixture_ids)}
            cursor.execute(
                "select user_id::text, status, conversation_id::text"
                " from public.guest_workspaces"
                " where user_id = any(%s::uuid[]) order by user_id",
                (fixture_ids,),
            )
            assert cursor.fetchall() == before
            cursor.execute(
                "select user_id::text, conversation_id::text"
                " from public.claim_expired_guest_workspaces(100, false)",
            )
            real_ids = {row[0] for row in cursor.fetchall() if row[0] in set(fixture_ids)}

        assert (
            dry_ids
            == real_ids
            == {
                active["user_id"],
                stale_expired["user_id"],
            }
        )
        connection.rollback()


def test_cleanup_marks_expired_before_removing_conversation_graph() -> None:
    with _connect() as connection:
        guest = _seed_expired_guest(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                "insert into public.feedback (user_id, type, message)"
                " values (%s, 'general', 'private guest feedback')",
                (guest["user_id"],),
            )
        rows = _claim_cleanup(connection, dry_run=False)
        assert rows == [(guest["user_id"], guest["conversation_id"])]
        with connection.cursor() as cursor:
            cursor.execute(
                "select status, conversation_id from public.guest_workspaces"
                " where user_id = %s",
                (guest["user_id"],),
            )
            status, conversation_id = cursor.fetchone()
            assert status == "expired"
            assert conversation_id is None
            cursor.execute(
                "select count(*) from public.conversations where id = %s",
                (guest["conversation_id"],),
            )
            assert cursor.fetchone()[0] == 0
            cursor.execute(
                "select count(*) from public.messages where user_id = %s",
                (guest["user_id"],),
            )
            assert cursor.fetchone()[0] == 0
            cursor.execute(
                "select count(*) from public.feedback where user_id = %s",
                (guest["user_id"],),
            )
            assert cursor.fetchone()[0] == 0
            cursor.execute("delete from auth.users where id = %s", (guest["user_id"],))


def test_cleanup_removes_conversation_checkpoint_graph() -> None:
    with _connect() as connection:
        guest = _seed_expired_guest(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                "insert into public.checkpoints"
                " (thread_id, checkpoint_ns, checkpoint_id, checkpoint)"
                " values (%s, '', 'checkpoint-1', '{}'::jsonb)",
                (guest["conversation_id"],),
            )
            cursor.execute(
                "insert into public.checkpoint_blobs"
                " (thread_id, checkpoint_ns, channel, version, type, blob)"
                " values (%s, '', 'messages', '1', 'msgpack', null)",
                (guest["conversation_id"],),
            )
            cursor.execute(
                "insert into public.checkpoint_writes"
                " (thread_id, checkpoint_ns, checkpoint_id, task_id,"
                "  idx, channel, type, blob)"
                " values (%s, '', 'checkpoint-1', 'task-1', 0,"
                "  'messages', 'msgpack', %s)",
                (guest["conversation_id"], b"checkpoint"),
            )

        rows = _claim_cleanup(connection, dry_run=False)
        assert rows == [(guest["user_id"], guest["conversation_id"])]
        with connection.cursor() as cursor:
            for table in ("checkpoints", "checkpoint_blobs", "checkpoint_writes"):
                cursor.execute(
                    f"select count(*) from public.{table} where thread_id = %s",
                    (guest["conversation_id"],),
                )
                assert cursor.fetchone()[0] == 0
            cursor.execute("delete from auth.users where id = %s", (guest["user_id"],))


def test_cleanup_cannot_select_a_converted_or_permanent_account() -> None:
    with _connect() as connection:
        guest = _seed_expired_guest(connection)
        verified_email = f"converted-{guest['user_id'][:8]}@example.com"
        with connection.cursor() as cursor:
            cursor.execute(
                "update auth.users set is_anonymous = false, email = %s" " where id = %s",
                (verified_email, guest["user_id"]),
            )
            cursor.execute(
                "update public.profiles set email = %s where id = %s",
                (verified_email, guest["user_id"]),
            )

        rows = _claim_cleanup(connection, dry_run=False)
        assert all(row[0] != guest["user_id"] for row in rows)
        with connection.cursor() as cursor:
            cursor.execute(
                "select count(*) from auth.users where id = %s",
                (guest["user_id"],),
            )
            assert cursor.fetchone()[0] == 1
            cursor.execute(
                "select status, conversation_id from public.guest_workspaces"
                " where user_id = %s",
                (guest["user_id"],),
            )
            status, conversation_id = cursor.fetchone()
            assert status == "active"
            assert str(conversation_id) == guest["conversation_id"]
            cursor.execute("delete from auth.users where id = %s", (guest["user_id"],))


def test_concurrent_cleanup_claims_each_guest_at_most_once() -> None:
    with _connect() as connection:
        guests = [_seed_expired_guest(connection), _seed_expired_guest(connection)]
    barrier = Barrier(2)

    def claim() -> list[tuple[str, str | None]]:
        with _connect() as connection:
            barrier.wait(timeout=10)
            return _claim_cleanup(connection, dry_run=False)

    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(lambda _: claim(), range(2)))

    claimed_ids = [user_id for rows in claims for user_id, _ in rows]
    expected_ids = {guest["user_id"] for guest in guests}
    assert set(claimed_ids) == expected_ids
    assert len(claimed_ids) == len(set(claimed_ids))
    with _connect() as connection:
        assert _claim_cleanup(connection, dry_run=False) == []
        with connection.cursor() as cursor:
            cursor.execute(
                "delete from auth.users where id = any(%s::uuid[])",
                ([guest["user_id"] for guest in guests],),
            )


def test_guest_privileged_functions_are_service_role_only() -> None:
    signatures = (
        "public.bind_guest_conversation(uuid,uuid)",
        "public.replace_empty_guest_conversation(uuid,text,text,text)",
        "public.claim_expired_guest_workspaces(integer,boolean)",
        (
            "public.create_feedback_settling_usage("
            "uuid,uuid,text,text,jsonb,text,jsonb)"
        ),
    )
    with _connect() as connection:
        with connection.cursor() as cursor:
            for signature in signatures:
                cursor.execute(
                    "select"
                    " has_function_privilege('anon', %s, 'execute'),"
                    " has_function_privilege('authenticated', %s, 'execute'),"
                    " has_function_privilege('service_role', %s, 'execute')",
                    (signature, signature, signature),
                )
                anon, authenticated, service_role = cursor.fetchone()
                assert anon is False
                assert authenticated is False
                assert service_role is True
