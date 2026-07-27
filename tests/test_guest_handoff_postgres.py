"""Real-Postgres proof for single-use guest workspace handoff and transfer."""

from __future__ import annotations

import hashlib
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from typing import Any

import pytest

DSN = os.getenv("ARGUS_DISPOSABLE_DATABASE_URL", "").strip()
pytestmark = pytest.mark.skipif(
    not DSN,
    reason="ARGUS_DISPOSABLE_DATABASE_URL is not configured",
)
psycopg = pytest.importorskip("psycopg")


def _connect(*, autocommit: bool = True):
    return psycopg.connect(DSN, autocommit=autocommit)


def _seed_identity(
    connection,
    *,
    anonymous: bool,
    email: str | None = None,
) -> str:
    user_id = str(uuid.uuid4())
    verified_email = None if anonymous else (email or f"member-{user_id[:8]}@example.com")
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


def _seed_complete_graph(connection) -> dict[str, Any]:
    source = _seed_identity(connection, anonymous=True)
    destination = _seed_identity(connection, anonymous=False)
    other_destination = _seed_identity(connection, anonymous=False)
    created_at = datetime.now(timezone.utc).replace(microsecond=0)
    ids = {
        name: str(uuid.uuid4())
        for name in (
            "conversation",
            "user_message",
            "assistant_message",
            "lifecycle",
            "strategy",
            "run",
            "job",
            "idea",
            "version",
            "evidence",
            "decision",
            "context_packet",
            "run_context_packet",
            "handoff",
        )
    }
    opaque_secret = f"secret-{uuid.uuid4()}"
    secret_hash = hashlib.sha256(opaque_secret.encode("utf-8")).hexdigest()
    with connection.cursor() as cursor:
        cursor.execute("select email from auth.users where id = %s", (destination,))
        destination_email = cursor.fetchone()[0]
        destination_email_hash = hashlib.sha256(
            str(destination_email).strip().lower().encode("utf-8")
        ).hexdigest()
        cursor.execute(
            "insert into public.guest_workspaces"
            " (user_id, created_at, expires_at) values (%s, %s, %s)",
            (source, created_at, created_at + timedelta(days=7)),
        )
        cursor.execute(
            "insert into public.conversations"
            " (id, user_id, title, last_message_preview)"
            " values (%s, %s, 'Guest NVDA idea', 'A truthful preview')",
            (ids["conversation"], source),
        )
        cursor.execute(
            "insert into public.messages (id, conversation_id, user_id, role, content)"
            " values (%s, %s, %s, 'user', 'Test NVDA after a pullback'),"
            "        (%s, %s, %s, 'assistant', 'Here is the result')",
            (
                ids["user_message"],
                ids["conversation"],
                source,
                ids["assistant_message"],
                ids["conversation"],
                source,
            ),
        )
        cursor.execute(
            "insert into public.chat_turn_lifecycles"
            " (turn_id,user_id,conversation_id,assistant_message_id,request_id,"
            "  status,accepted_at,terminal_at,created_at,updated_at)"
            " values (%s,%s,%s,%s,'request-guest-handoff','completed',"
            "  %s,%s,%s,%s)",
            (
                ids["user_message"],
                source,
                ids["conversation"],
                ids["assistant_message"],
                created_at,
                created_at,
                created_at,
                created_at,
            ),
        )
        cursor.execute(
            "insert into public.strategies"
            " (id,user_id,conversation_id,name,template,asset_class,symbols,"
            "  benchmark_symbol)"
            " values (%s,%s,%s,'NVDA pullback','buy_and_hold','equity',"
            " array['NVDA'],'SPY')",
            (ids["strategy"], source, ids["conversation"]),
        )
        cursor.execute(
            "insert into public.backtest_runs"
            " (id,user_id,conversation_id,strategy_id,status,asset_class,symbols,"
            "  benchmark_symbol,config_snapshot,conversation_result_card)"
            " values (%s,%s,%s,%s,'completed','equity',array['NVDA'],'SPY',"
            ' \'{}\'::jsonb,\'{"title":"NVDA pullback","rows":[]}\'::jsonb)',
            (
                ids["run"],
                source,
                ids["conversation"],
                ids["strategy"],
            ),
        )
        cursor.execute(
            "insert into public.backtest_jobs"
            " (id,user_id,conversation_id,request_message_id,"
            "  confirmation_message_id,idempotency_key,payload_hash,"
            "  launch_payload,status,result_run_id)"
            " values (%s,%s,%s,%s,%s,'run-action-1','payload-1',"
            " '{}'::jsonb,'succeeded',%s)",
            (
                ids["job"],
                source,
                ids["conversation"],
                ids["user_message"],
                ids["assistant_message"],
                ids["run"],
            ),
        )
        cursor.execute(
            "insert into public.ideas"
            " (id,user_id,source_conversation_id,title,summary,lifecycle)"
            " values (%s,%s,%s,'NVDA pullback','Captured idea','decided')",
            (ids["idea"], source, ids["conversation"]),
        )
        cursor.execute(
            "insert into public.idea_versions"
            " (id,user_id,idea_id,source_conversation_id,source_run_id,"
            "  canonical_spec,strategy_snapshot,title,summary,lifecycle)"
            " values (%s,%s,%s,%s,%s,'{}'::jsonb,'{}'::jsonb,"
            " 'NVDA pullback','Version one','decided')",
            (
                ids["version"],
                source,
                ids["idea"],
                ids["conversation"],
                ids["run"],
            ),
        )
        cursor.execute(
            "update public.ideas set active_version_id = %s where id = %s",
            (ids["version"], ids["idea"]),
        )
        cursor.execute(
            "insert into public.evidence_artifacts"
            " (id,user_id,idea_id,idea_version_id,source_conversation_id,"
            "  source_run_id,lifecycle,title,digest,payload)"
            " values (%s,%s,%s,%s,%s,%s,'decided','NVDA result',"
            " 'Immutable digest','{}'::jsonb)",
            (
                ids["evidence"],
                source,
                ids["idea"],
                ids["version"],
                ids["conversation"],
                ids["run"],
            ),
        )
        cursor.execute(
            "insert into public.decision_notes"
            " (id,user_id,idea_id,idea_version_id,evidence_artifact_id,"
            "  source_conversation_id,decision_state,note)"
            " values (%s,%s,%s,%s,%s,%s,'watching','Keep watching')",
            (
                ids["decision"],
                source,
                ids["idea"],
                ids["version"],
                ids["evidence"],
                ids["conversation"],
            ),
        )
        cursor.execute(
            "insert into public.context_packets"
            " (id,user_id,provider,packet_type,retrieved_at)"
            " values (%s,%s,'alpaca','news',%s)",
            (ids["context_packet"], source, created_at),
        )
        cursor.execute(
            "insert into public.run_context_packets"
            " (id,user_id,run_id,context_packet_id)"
            " values (%s,%s,%s,%s)",
            (
                ids["run_context_packet"],
                source,
                ids["run"],
                ids["context_packet"],
            ),
        )
        cursor.execute(
            "insert into public.usage_counters"
            " (user_id,resource,period,period_start,period_end,used_count,limit_count)"
            " values (%s,'chat_messages','guest_session',%s,%s,4,10)",
            (source, created_at, created_at + timedelta(days=7)),
        )
        cursor.execute(
            "insert into public.feedback (user_id,type,message)"
            " values (%s,'general','Source-owned feedback')",
            (source,),
        )
        cursor.execute(
            "insert into public.checkpoints"
            " (thread_id,checkpoint_ns,checkpoint_id,checkpoint)"
            " values (%s,'','checkpoint-1','{}'::jsonb)",
            (ids["conversation"],),
        )
        cursor.execute(
            "insert into public.guest_workspace_handoffs"
            " (id,secret_hash,source_user_id,destination_user_id,"
            "  destination_email_hash,"
            "  source_conversation_id,pending_action,created_at,expires_at)"
            " values (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)",
            (
                ids["handoff"],
                secret_hash,
                source,
                destination,
                destination_email_hash,
                ids["conversation"],
                (
                    '{"reason":"save_decision",'
                    f'"conversation_id":"{ids["conversation"]}",'
                    '"action_id":"decision-action-1",'
                    f'"artifact_id":"{ids["evidence"]}"'
                    "}"
                ),
                created_at,
                created_at + timedelta(minutes=10),
            ),
        )
    return {
        **ids,
        "source": source,
        "destination": destination,
        "other_destination": other_destination,
        "opaque_secret": opaque_secret,
        "secret_hash": secret_hash,
    }


def _claim(connection, graph: dict[str, Any], *, destination: str | None = None):
    return _claim_by_email(connection, graph, destination=destination)


def _claim_by_email(
    connection,
    graph: dict[str, Any],
    *,
    destination: str | None = None,
    allow_replay: bool = False,
):
    with connection.cursor() as cursor:
        cursor.execute(
            "select source_user_id::text,destination_user_id::text,"
            " conversation_id::text,pending_action"
            " from public.claim_guest_workspace_handoff_by_email(%s,%s,%s,%s)",
            (
                graph["handoff"],
                graph["secret_hash"],
                destination or graph["destination"],
                allow_replay,
            ),
        )
        return cursor.fetchone()


def _delete_fixture_identities(connection, graph: dict[str, Any]) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "delete from public.guest_workspace_handoffs"
            " where id = %s or source_user_id = %s",
            (graph["handoff"], graph["source"]),
        )
        cursor.execute(
            "delete from auth.users where id = any(%s::uuid[])",
            (
                [
                    graph["source"],
                    graph["destination"],
                    graph["other_destination"],
                ],
            ),
        )


def test_handoff_storage_and_privileged_claim_contract_exist() -> None:
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("select to_regclass('public.guest_workspace_handoffs')::text")
            assert cursor.fetchone()[0] == "guest_workspace_handoffs"
            cursor.execute(
                """
                select
                  to_regprocedure(
                    'argus_private.claim_guest_workspace_handoff(uuid,text,uuid)'
                  )::text,
                  to_regprocedure(
                    'public.claim_guest_workspace_handoff(uuid,text,uuid)'
                  )::text
                """
            )
            private_function, service_wrapper = cursor.fetchone()

    assert private_function is not None
    assert service_wrapper is not None


def test_email_bound_claim_resolves_only_after_verified_login_and_reconciles_once() -> (
    None
):
    with _connect() as connection:
        graph = _seed_complete_graph(connection)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "update public.guest_workspace_handoffs"
                    " set destination_user_id = null where id = %s",
                    (graph["handoff"],),
                )
            with pytest.raises(psycopg.Error, match="wrong_destination"):
                _claim_by_email(
                    connection,
                    graph,
                    destination=graph["other_destination"],
                )

            first = _claim_by_email(connection, graph)
            replay = _claim_by_email(connection, graph, allow_replay=True)
            assert first == replay
            assert first[:3] == (
                graph["source"],
                graph["destination"],
                graph["conversation"],
            )
            with pytest.raises(psycopg.Error, match="guest_handoff_consumed"):
                _claim_by_email(connection, graph)
        finally:
            _delete_fixture_identities(connection, graph)


def test_handoff_table_and_claim_wrapper_are_not_client_executable() -> None:
    with _connect(autocommit=False) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select
                  has_table_privilege('anon', 'public.guest_workspace_handoffs', 'select'),
                  has_table_privilege(
                    'authenticated',
                    'public.guest_workspace_handoffs',
                    'select'
                  ),
                  has_function_privilege(
                    'anon',
                    'public.claim_guest_workspace_handoff(uuid,text,uuid)',
                    'execute'
                  ),
                  has_function_privilege(
                    'authenticated',
                    'public.claim_guest_workspace_handoff(uuid,text,uuid)',
                    'execute'
                  ),
                  has_function_privilege(
                    'service_role',
                    'public.claim_guest_workspace_handoff(uuid,text,uuid)',
                    'execute'
                  ),
                  has_function_privilege(
                    'anon',
                    'public.claim_guest_workspace_handoff_by_email(uuid,text,uuid,boolean)',
                    'execute'
                  ),
                  has_function_privilege(
                    'authenticated',
                    'public.claim_guest_workspace_handoff_by_email(uuid,text,uuid,boolean)',
                    'execute'
                  ),
                  has_function_privilege(
                    'service_role',
                    'public.claim_guest_workspace_handoff_by_email(uuid,text,uuid,boolean)',
                    'execute'
                  )
                """
            )
            privileges = cursor.fetchone()

    assert privileges == (False, False, False, False, True, False, False, True)


def test_complete_graph_claim_preserves_ids_and_moves_each_owner_once() -> None:
    with _connect() as connection:
        graph = _seed_complete_graph(connection)
        try:
            claimed = _claim(connection, graph)
            assert claimed[:3] == (
                graph["source"],
                graph["destination"],
                graph["conversation"],
            )
            assert claimed[3]["action_id"] == "decision-action-1"

            with connection.cursor() as cursor:
                for table, expected_count in (
                    ("conversations", 1),
                    ("messages", 2),
                    ("chat_turn_lifecycles", 1),
                    ("strategies", 1),
                    ("backtest_runs", 1),
                    ("backtest_jobs", 1),
                    ("ideas", 1),
                    ("idea_versions", 1),
                    ("evidence_artifacts", 1),
                    ("decision_notes", 1),
                    ("context_packets", 1),
                    ("run_context_packets", 1),
                ):
                    cursor.execute(
                        f"select count(*) from public.{table} where user_id = %s",
                        (graph["destination"],),
                    )
                    assert cursor.fetchone()[0] == expected_count
                    cursor.execute(
                        f"select count(*) from public.{table} where user_id = %s",
                        (graph["source"],),
                    )
                    assert cursor.fetchone()[0] == 0
                cursor.execute(
                    "select status,claimed_by::text,conversation_id::text"
                    " from public.guest_workspaces where user_id = %s",
                    (graph["source"],),
                )
                assert cursor.fetchone() == (
                    "claimed",
                    graph["destination"],
                    graph["conversation"],
                )
                cursor.execute(
                    "select used_count from public.usage_counters"
                    " where user_id = %s and resource = 'chat_messages'",
                    (graph["source"],),
                )
                assert cursor.fetchone()[0] == 4
                cursor.execute(
                    "select count(*) from public.usage_counters where user_id = %s",
                    (graph["destination"],),
                )
                assert cursor.fetchone()[0] == 0
                cursor.execute(
                    "select count(*) from public.checkpoints where thread_id = %s",
                    (graph["conversation"],),
                )
                assert cursor.fetchone()[0] == 1
                cursor.execute(
                    "select count(*) from public.conversations where id = %s",
                    (graph["conversation"],),
                )
                assert cursor.fetchone()[0] == 1
                cursor.execute(
                    "select count(*) from public.chat_turn_lifecycles"
                    " where turn_id = %s and user_id = %s",
                    (graph["user_message"], graph["destination"]),
                )
                assert cursor.fetchone()[0] == 1

            with pytest.raises(psycopg.Error, match="guest_handoff_consumed"):
                _claim(connection, graph)

            with connection.cursor() as cursor:
                cursor.execute(
                    "delete from auth.users where id = %s",
                    (graph["source"],),
                )
                cursor.execute(
                    "select count(*) from public.conversations where id = %s",
                    (graph["conversation"],),
                )
                assert cursor.fetchone()[0] == 1
                cursor.execute(
                    "select count(*) from public.checkpoints where thread_id = %s",
                    (graph["conversation"],),
                )
                assert cursor.fetchone()[0] == 1
                cursor.execute(
                    "select count(*) from public.chat_turn_lifecycles"
                    " where turn_id = %s and user_id = %s",
                    (graph["user_message"], graph["destination"]),
                )
                assert cursor.fetchone()[0] == 1
        finally:
            _delete_fixture_identities(connection, graph)


def test_wrong_destination_and_tampered_secret_change_zero_owners() -> None:
    with _connect() as connection:
        graph = _seed_complete_graph(connection)
        try:
            with pytest.raises(psycopg.Error, match="wrong_destination"):
                _claim(
                    connection,
                    graph,
                    destination=graph["other_destination"],
                )
            tampered = dict(graph)
            tampered["secret_hash"] = hashlib.sha256(b"tampered").hexdigest()
            with pytest.raises(psycopg.Error, match="guest_handoff_invalid"):
                _claim(connection, tampered)
            with connection.cursor() as cursor:
                for table in (
                    "conversations",
                    "messages",
                    "backtest_runs",
                    "backtest_jobs",
                    "ideas",
                    "evidence_artifacts",
                    "decision_notes",
                ):
                    cursor.execute(
                        f"select count(*) from public.{table} where user_id = %s",
                        (graph["destination"],),
                    )
                    assert cursor.fetchone()[0] == 0
                cursor.execute(
                    "select status from public.guest_workspace_handoffs where id = %s",
                    (graph["handoff"],),
                )
                assert cursor.fetchone()[0] == "pending"
        finally:
            _delete_fixture_identities(connection, graph)


def test_expired_and_consumed_handoffs_fail_without_transfer() -> None:
    for terminal_state in ("expired", "consumed"):
        with _connect() as connection:
            graph = _seed_complete_graph(connection)
            try:
                with connection.cursor() as cursor:
                    if terminal_state == "expired":
                        created_at = datetime.now(timezone.utc) - timedelta(minutes=11)
                        cursor.execute(
                            "update public.guest_workspace_handoffs"
                            " set created_at=%s,expires_at=%s where id=%s",
                            (
                                created_at,
                                created_at + timedelta(minutes=10),
                                graph["handoff"],
                            ),
                        )
                    else:
                        cursor.execute(
                            "update public.guest_workspace_handoffs"
                            " set status='consumed',consumed_at=now() where id=%s",
                            (graph["handoff"],),
                        )
                with pytest.raises(
                    psycopg.Error, match=f"guest_handoff_{terminal_state}"
                ):
                    _claim(connection, graph)
                with connection.cursor() as cursor:
                    cursor.execute(
                        "select user_id::text from public.conversations where id = %s",
                        (graph["conversation"],),
                    )
                    assert cursor.fetchone()[0] == graph["source"]
            finally:
                _delete_fixture_identities(connection, graph)


def test_foreign_row_injection_fails_closed() -> None:
    with _connect() as connection:
        graph = _seed_complete_graph(connection)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "insert into public.strategies"
                    " (user_id,conversation_id,name,template,asset_class,symbols,"
                    "  benchmark_symbol)"
                    " values (%s,%s,'Injected','buy_and_hold','equity',"
                    " array['AAPL'],'SPY')",
                    (graph["other_destination"], graph["conversation"]),
                )
            with pytest.raises(psycopg.Error, match="unsafe_product_graph"):
                _claim(connection, graph)
            with connection.cursor() as cursor:
                cursor.execute(
                    "select user_id::text from public.conversations where id=%s",
                    (graph["conversation"],),
                )
                assert cursor.fetchone()[0] == graph["source"]
        finally:
            _delete_fixture_identities(connection, graph)


def test_lifecycle_foreign_row_injection_fails_closed() -> None:
    with _connect() as connection:
        graph = _seed_complete_graph(connection)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "update public.chat_turn_lifecycles set user_id = %s"
                    " where turn_id = %s",
                    (graph["other_destination"], graph["user_message"]),
                )
            with pytest.raises(psycopg.Error, match="unsafe_product_graph"):
                _claim(connection, graph)
            with connection.cursor() as cursor:
                cursor.execute(
                    "select user_id::text from public.conversations where id=%s",
                    (graph["conversation"],),
                )
                assert cursor.fetchone()[0] == graph["source"]
                cursor.execute(
                    "select user_id::text from public.chat_turn_lifecycles"
                    " where turn_id=%s",
                    (graph["user_message"],),
                )
                assert cursor.fetchone()[0] == graph["other_destination"]
        finally:
            _delete_fixture_identities(connection, graph)


@pytest.mark.parametrize(
    ("table", "trigger_column"),
    (
        ("conversations", "user_id"),
        ("chat_turn_lifecycles", "user_id"),
        ("backtest_jobs", "user_id"),
        ("evidence_artifacts", "user_id"),
        ("context_packets", "user_id"),
        ("guest_workspaces", "status"),
    ),
)
def test_failure_at_each_transfer_group_rolls_back_every_owner(
    table: str,
    trigger_column: str,
) -> None:
    with _connect(autocommit=False) as connection:
        graph = _seed_complete_graph(connection)
        trigger_name = f"abort_{table}_{uuid.uuid4().hex}"
        with connection.cursor() as cursor:
            cursor.execute(
                """
                create function pg_temp.abort_guest_claim()
                returns trigger
                language plpgsql
                as $$
                begin
                  raise exception 'test_abort_guest_claim';
                end;
                $$
                """
            )
            cursor.execute(
                f"create trigger {trigger_name}"
                f" before update of {trigger_column} on public.{table}"
                " for each row execute function pg_temp.abort_guest_claim()"
            )
            cursor.execute("savepoint before_claim")
            with pytest.raises(psycopg.Error, match="test_abort_guest_claim"):
                _claim(connection, graph)
            cursor.execute("rollback to savepoint before_claim")

            for owner_table in (
                "conversations",
                "messages",
                "chat_turn_lifecycles",
                "strategies",
                "backtest_runs",
                "backtest_jobs",
                "ideas",
                "idea_versions",
                "evidence_artifacts",
                "decision_notes",
                "context_packets",
                "run_context_packets",
            ):
                cursor.execute(
                    f"select count(*) from public.{owner_table}" " where user_id = %s",
                    (graph["destination"],),
                )
                assert cursor.fetchone()[0] == 0
            cursor.execute(
                "select status from public.guest_workspace_handoffs where id = %s",
                (graph["handoff"],),
            )
            assert cursor.fetchone()[0] == "pending"
            cursor.execute(
                "select user_id::text from public.conversations where id = %s",
                (graph["conversation"],),
            )
            assert cursor.fetchone()[0] == graph["source"]


def test_two_concurrent_claims_produce_one_success() -> None:
    with _connect() as connection:
        graph = _seed_complete_graph(connection)
    barrier = Barrier(2)

    def claim_once(_: int) -> str:
        with _connect() as connection:
            barrier.wait(timeout=10)
            try:
                _claim(connection, graph)
                return "success"
            except psycopg.Error as exc:
                return str(exc)

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(claim_once, range(2)))
        assert results.count("success") == 1
        assert sum("guest_handoff_consumed" in result for result in results) == 1
        with _connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "select count(*) from public.conversations where id=%s"
                    " and user_id=%s",
                    (graph["conversation"], graph["destination"]),
                )
                assert cursor.fetchone()[0] == 1
    finally:
        with _connect() as connection:
            _delete_fixture_identities(connection, graph)
