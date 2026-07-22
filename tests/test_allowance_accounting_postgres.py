"""Real-Postgres proofs for #247 allowance accounting.

Skip-gated on ``ARGUS_DISPOSABLE_DATABASE_URL``: point it at a disposable
Supabase-Postgres database that has every ``supabase/migrations`` file
applied, never at production. These proofs cover the behavior mocks cannot:
same-transaction settlement, barriered admission concurrency, replay and
collision against durable reservations, stale direct-job reconciliation,
owner isolation, and exact UTC window boundaries.
"""

from __future__ import annotations

import json
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

MESSAGE_LIMITS = [{"period": "hour", "limit": 60}, {"period": "day", "limit": 200}]
SIMULATION_LIMITS = [{"period": "hour", "limit": 10}, {"period": "day", "limit": 50}]


def _connect():
    return psycopg.connect(DSN, autocommit=True)


@pytest.fixture
def owner():
    """One disposable auth user + profile + conversation per test."""
    with _connect() as connection:
        yield _seed_owner(connection)


def _seed_owner(connection) -> dict[str, str]:
    user_id = str(uuid.uuid4())
    conversation_id = str(uuid.uuid4())
    email = f"proof-{user_id[:8]}@argus.local"
    with connection.cursor() as cursor:
        cursor.execute(
            "insert into auth.users (id, email) values (%s, %s)",
            (user_id, email),
        )
        cursor.execute(
            "insert into public.profiles (id, email) values (%s, %s)",
            (user_id, email),
        )
        cursor.execute(
            "insert into public.conversations (id, user_id, title)"
            " values (%s, %s, 'proof')",
            (conversation_id, user_id),
        )
    return {"user_id": user_id, "conversation_id": conversation_id}


def _usage_rows(connection, user_id: str, resource: str) -> dict[str, dict]:
    with connection.cursor() as cursor:
        cursor.execute(
            "select period, period_start, period_end, used_count, limit_count"
            " from public.usage_counters"
            " where user_id = %s and resource = %s",
            (user_id, resource),
        )
        return {
            row[0]: {
                "period_start": row[1],
                "period_end": row[2],
                "used_count": row[3],
                "limit_count": row[4],
            }
            for row in cursor.fetchall()
        }


def _settle_message(connection, owner, message_id: str, *, limits=None):
    with connection.cursor() as cursor:
        cursor.execute(
            "select * from public.append_conversation_message_settling_usage("
            " %s, %s, %s, 'assistant', 'terminal product response',"
            " %s::jsonb, now(), 'preview', 'chat_messages', %s::jsonb)",
            (
                owner["user_id"],
                owner["conversation_id"],
                message_id,
                json.dumps(
                    {
                        "agent_runtime_turn": {
                            "status": "succeeded",
                            "terminal": True,
                        }
                    }
                ),
                json.dumps(limits if limits is not None else MESSAGE_LIMITS),
            ),
        )
        return cursor.fetchone()


def _admit(connection, owner, **overrides):
    # Ceilings default high for determinism on a reused disposable database;
    # capacity is proven via the per-user ceiling on a fresh user.
    arguments = {
        "user_id": owner["user_id"],
        "operation_scope": "chat.run_backtest",
        "idempotency_key": overrides.pop("idempotency_key", str(uuid.uuid4())),
        "identity_hash": overrides.pop("identity_hash", f"sha256:{'a' * 64}"),
        "payload_hash": f"sha256:{'b' * 64}",
        "launch_payload": json.dumps({"kind": "proof"}),
        "initial_status": "queued",
        "conversation_id": owner["conversation_id"],
        "user_running_limit": 1000,
        "user_queued_limit": 1000,
        "global_running_limit": 1000000,
        "global_queued_limit": 1000000,
        "allowance_limits": json.dumps(SIMULATION_LIMITS),
    }
    arguments.update(overrides)
    with connection.cursor() as cursor:
        cursor.execute(
            "select public.admit_backtest_job("
            " %(user_id)s, %(operation_scope)s, %(idempotency_key)s,"
            " %(identity_hash)s, %(payload_hash)s, %(launch_payload)s::jsonb,"
            " %(initial_status)s, %(conversation_id)s, null, null,"
            " '{}'::jsonb, %(user_running_limit)s, %(user_queued_limit)s,"
            " %(global_running_limit)s, %(global_queued_limit)s,"
            " %(allowance_limits)s::jsonb)",
            arguments,
        )
        return cursor.fetchone()[0]


def test_settlement_charges_both_windows_once_and_replays_zero(owner):
    with _connect() as connection:
        message_id = str(uuid.uuid4())
        row = _settle_message(connection, owner, message_id)
        assert row[2] is False  # not a replay

        windows = _usage_rows(connection, owner["user_id"], "chat_messages")
        now = datetime.now(timezone.utc)
        hour_start = now.replace(minute=0, second=0, microsecond=0)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        assert windows["hour"]["used_count"] == 1
        assert windows["hour"]["limit_count"] == 60
        assert windows["hour"]["period_start"] == hour_start
        assert windows["hour"]["period_end"] == hour_start + timedelta(hours=1)
        assert windows["day"]["used_count"] == 1
        assert windows["day"]["limit_count"] == 200
        assert windows["day"]["period_start"] == day_start
        assert windows["day"]["period_end"] == day_start + timedelta(days=1)

        replay = _settle_message(connection, owner, message_id)
        assert replay[2] is True
        windows = _usage_rows(connection, owner["user_id"], "chat_messages")
        assert windows["hour"]["used_count"] == 1
        assert windows["day"]["used_count"] == 1


def test_settlement_rolls_back_with_its_message(owner):
    with _connect() as connection:
        message_id = str(uuid.uuid4())
        with pytest.raises(psycopg.errors.DatabaseError):
            _settle_message(
                connection,
                owner,
                message_id,
                limits=[{"period": "week", "limit": 1}],
            )
        with connection.cursor() as cursor:
            cursor.execute(
                "select count(*) from public.messages where id = %s",
                (message_id,),
            )
            assert cursor.fetchone()[0] == 0
        assert _usage_rows(connection, owner["user_id"], "chat_messages") == {}


def test_concurrent_settlements_of_distinct_turns_count_exactly(owner):
    barrier = Barrier(10)

    def settle(_: int) -> None:
        with _connect() as connection:
            barrier.wait(timeout=30)
            _settle_message(connection, owner, str(uuid.uuid4()))

    with ThreadPoolExecutor(max_workers=10) as pool:
        list(pool.map(settle, range(10)))

    with _connect() as connection:
        windows = _usage_rows(connection, owner["user_id"], "chat_messages")
        assert windows["hour"]["used_count"] == 10
        assert windows["day"]["used_count"] == 10


def test_ten_concurrent_same_identity_admissions_charge_once(owner):
    idempotency_key = str(uuid.uuid4())
    identity_hash = f"sha256:{'c' * 64}"
    barrier = Barrier(10)

    def admit(_: int) -> str:
        with _connect() as connection:
            barrier.wait(timeout=30)
            return _admit(
                connection,
                owner,
                idempotency_key=idempotency_key,
                identity_hash=identity_hash,
            )["decision"]

    with ThreadPoolExecutor(max_workers=10) as pool:
        decisions = list(pool.map(admit, range(10)))

    assert sorted(decisions) == ["admitted"] + ["replay"] * 9
    with _connect() as connection:
        windows = _usage_rows(connection, owner["user_id"], "backtest_runs")
        assert windows["hour"]["used_count"] == 1
        assert windows["day"]["used_count"] == 1
        with connection.cursor() as cursor:
            cursor.execute(
                "select count(*) from public.backtest_jobs where user_id = %s",
                (owner["user_id"],),
            )
            assert cursor.fetchone()[0] == 1


def test_concurrent_distinct_identities_respect_capacity_atomically(owner):
    barrier = Barrier(10)

    def admit(_: int) -> str:
        with _connect() as connection:
            barrier.wait(timeout=30)
            return _admit(connection, owner, user_queued_limit=2)["decision"]

    with ThreadPoolExecutor(max_workers=10) as pool:
        decisions = list(pool.map(admit, range(10)))

    assert decisions.count("admitted") == 2  # user_queued_limit=2
    assert decisions.count("per_user_capacity") == 8
    with _connect() as connection:
        windows = _usage_rows(connection, owner["user_id"], "backtest_runs")
        assert windows["hour"]["used_count"] == 2
        assert windows["day"]["used_count"] == 2


def test_same_key_different_identity_conflicts_without_disclosure(owner):
    with _connect() as connection:
        idempotency_key = str(uuid.uuid4())
        first = _admit(connection, owner, idempotency_key=idempotency_key)
        assert first["decision"] == "admitted"
        conflict = _admit(
            connection,
            owner,
            idempotency_key=idempotency_key,
            identity_hash=f"sha256:{'d' * 64}",
        )
        assert conflict == {"decision": "conflict"}
        windows = _usage_rows(connection, owner["user_id"], "backtest_runs")
        assert windows["hour"]["used_count"] == 1


def test_hourly_and_daily_exhaustion_reject_before_any_charge(owner):
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "insert into public.usage_counters"
                " (user_id, resource, period, period_start, period_end,"
                "  used_count, limit_count)"
                " values (%s, 'backtest_runs', 'hour',"
                "  date_trunc('hour', now()),"
                "  date_trunc('hour', now()) + interval '1 hour', 10, 10)",
                (owner["user_id"],),
            )
        outcome = _admit(connection, owner)
        assert outcome == {"decision": "allowance_exhausted"}

        with connection.cursor() as cursor:
            cursor.execute(
                "update public.usage_counters set used_count = 0"
                " where user_id = %s and period = 'hour'",
                (owner["user_id"],),
            )
            cursor.execute(
                "insert into public.usage_counters"
                " (user_id, resource, period, period_start, period_end,"
                "  used_count, limit_count)"
                " values (%s, 'backtest_runs', 'day',"
                "  date_trunc('day', now()),"
                "  date_trunc('day', now()) + interval '1 day', 50, 50)",
                (owner["user_id"],),
            )
        outcome = _admit(connection, owner)
        assert outcome == {"decision": "allowance_exhausted"}
        with connection.cursor() as cursor:
            cursor.execute(
                "select count(*) from public.backtest_jobs where user_id = %s",
                (owner["user_id"],),
            )
            assert cursor.fetchone()[0] == 0


def test_post_admission_failure_keeps_exactly_one_unit(owner):
    with _connect() as connection:
        outcome = _admit(
            connection,
            owner,
            operation_scope="backtests.run",
            initial_status="running",
            conversation_id=None,
        )
        assert outcome["decision"] == "admitted"
        job_id = outcome["job"]["id"]
        with connection.cursor() as cursor:
            cursor.execute(
                "update public.backtest_jobs set status = 'failed',"
                " failure_code = 'execution_failed', retryable = false,"
                " finished_at = now() where id = %s",
                (job_id,),
            )
        windows = _usage_rows(connection, owner["user_id"], "backtest_runs")
        assert windows["hour"]["used_count"] == 1
        assert windows["day"]["used_count"] == 1

        replay = _admit(
            connection,
            owner,
            operation_scope="backtests.run",
            initial_status="running",
            conversation_id=None,
            idempotency_key=outcome["job"]["idempotency_key"],
        )
        assert replay["decision"] == "replay"
        assert replay["job"]["status"] == "failed"
        windows = _usage_rows(connection, owner["user_id"], "backtest_runs")
        assert windows["hour"]["used_count"] == 1


def test_stale_running_direct_job_reconciles_on_new_admission(owner):
    with _connect() as connection:
        stale = _admit(
            connection,
            owner,
            operation_scope="backtests.run",
            initial_status="running",
            conversation_id=None,
        )
        assert stale["decision"] == "admitted"
        with connection.cursor() as cursor:
            cursor.execute(
                "update public.backtest_jobs"
                " set started_at = now() - interval '20 minutes'"
                " where id = %s",
                (stale["job"]["id"],),
            )
        fresh = _admit(
            connection,
            owner,
            operation_scope="backtests.run",
            initial_status="running",
            conversation_id=None,
        )
        assert fresh["decision"] == "admitted"
        with connection.cursor() as cursor:
            cursor.execute(
                "select status, failure_code, retryable"
                " from public.backtest_jobs where id = %s",
                (stale["job"]["id"],),
            )
            status, failure_code, retryable = cursor.fetchone()
        assert status == "failed"
        assert failure_code == "direct_execution_abandoned"
        assert retryable is True


def test_owner_isolation_for_reservations_and_counters(owner):
    with _connect() as connection:
        other = _seed_owner(connection)
        shared_key = str(uuid.uuid4())
        first = _admit(connection, owner, idempotency_key=shared_key)
        second = _admit(connection, other, idempotency_key=shared_key)
        assert first["decision"] == "admitted"
        assert second["decision"] == "admitted"
        assert first["job"]["id"] != second["job"]["id"]
        assert first["job"]["user_id"] == owner["user_id"]
        assert second["job"]["user_id"] == other["user_id"]
        owner_windows = _usage_rows(connection, owner["user_id"], "backtest_runs")
        other_windows = _usage_rows(connection, other["user_id"], "backtest_runs")
        assert owner_windows["day"]["used_count"] == 1
        assert other_windows["day"]["used_count"] == 1


def test_admission_functions_are_service_role_only():
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "select"
                " has_function_privilege('anon',"
                "  'public.admit_backtest_job(uuid,text,text,text,text,jsonb,"
                "text,uuid,uuid,uuid,jsonb,integer,integer,integer,integer,"
                "jsonb)', 'execute'),"
                " has_function_privilege('authenticated',"
                "  'public.admit_backtest_job(uuid,text,text,text,text,jsonb,"
                "text,uuid,uuid,uuid,jsonb,integer,integer,integer,integer,"
                "jsonb)', 'execute'),"
                " has_function_privilege('service_role',"
                "  'public.admit_backtest_job(uuid,text,text,text,text,jsonb,"
                "text,uuid,uuid,uuid,jsonb,integer,integer,integer,integer,"
                "jsonb)', 'execute')"
            )
            anon, authenticated, service_role = cursor.fetchone()
        assert anon is False
        assert authenticated is False
        assert service_role is True
        with connection.cursor() as cursor:
            cursor.execute(
                "select"
                " has_function_privilege('anon',"
                "  'public.finalize_direct_backtest_success(uuid,uuid,text,"
                "jsonb,jsonb,jsonb,jsonb)', 'execute'),"
                " has_function_privilege('authenticated',"
                "  'public.finalize_direct_backtest_success(uuid,uuid,text,"
                "jsonb,jsonb,jsonb,jsonb)', 'execute'),"
                " has_function_privilege('service_role',"
                "  'public.finalize_direct_backtest_success(uuid,uuid,text,"
                "jsonb,jsonb,jsonb,jsonb)', 'execute')"
            )
            anon, authenticated, service_role = cursor.fetchone()
        assert anon is False
        assert authenticated is False
        assert service_role is True


def test_legacy_reservation_replays_on_exact_payload_and_adopts_identity(owner):
    with _connect() as connection:
        key = str(uuid.uuid4())
        legacy_payload_hash = f"sha256:{'1' * 64}"
        with connection.cursor() as cursor:
            cursor.execute(
                "insert into public.backtest_jobs"
                " (user_id, conversation_id, operation_scope, idempotency_key,"
                "  identity_hash, payload_hash, launch_payload, status,"
                "  priority, attempts, max_attempts, queued_at)"
                " values (%s, %s, 'chat.run_backtest', %s, null, %s,"
                "  '{}'::jsonb, 'queued', 'normal', 0, 1, now())"
                " returning id",
                (
                    owner["user_id"],
                    owner["conversation_id"],
                    key,
                    legacy_payload_hash,
                ),
            )
            legacy_job_id = cursor.fetchone()[0]

        canonical_identity = f"sha256:{'2' * 64}"
        replay = _admit(
            connection,
            owner,
            idempotency_key=key,
            identity_hash=canonical_identity,
            payload_hash=legacy_payload_hash,
        )
        assert replay["decision"] == "replay"
        assert str(replay["job"]["id"]) == str(legacy_job_id)
        with connection.cursor() as cursor:
            cursor.execute(
                "select identity_hash from public.backtest_jobs where id = %s",
                (legacy_job_id,),
            )
            assert cursor.fetchone()[0] == canonical_identity

        second = _admit(
            connection,
            owner,
            idempotency_key=key,
            identity_hash=canonical_identity,
            payload_hash=legacy_payload_hash,
        )
        assert second["decision"] == "replay"
        windows = _usage_rows(connection, owner["user_id"], "backtest_runs")
        assert windows == {}  # replays never charge


def test_legacy_reservation_with_different_payload_conflicts(owner):
    with _connect() as connection:
        key = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "insert into public.backtest_jobs"
                " (user_id, conversation_id, operation_scope, idempotency_key,"
                "  identity_hash, payload_hash, launch_payload, status,"
                "  priority, attempts, max_attempts, queued_at)"
                " values (%s, %s, 'chat.run_backtest', %s, null, %s,"
                "  '{}'::jsonb, 'queued', 'normal', 0, 1, now())",
                (
                    owner["user_id"],
                    owner["conversation_id"],
                    key,
                    f"sha256:{'3' * 64}",
                ),
            )
        outcome = _admit(
            connection,
            owner,
            idempotency_key=key,
            payload_hash=f"sha256:{'4' * 64}",
        )
        assert outcome == {"decision": "conflict"}
        assert _usage_rows(connection, owner["user_id"], "backtest_runs") == {}


def _finalize_direct_success(connection, owner, *, job_id: str, run_id: str):
    idea_id = str(uuid.uuid4())
    idea_version_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())
    run = {
        "id": run_id,
        "status": "completed",
        "asset_class": "equity",
        "symbols": ["AAPL"],
        "allocation_method": "equal_weight",
        "benchmark_symbol": "SPY",
        "metrics": {"total_return": 0.1},
        "config_snapshot": {"template": "buy_and_hold"},
        "conversation_result_card": {},
    }
    idea = {"id": idea_id, "title": "Proof idea"}
    idea_version = {
        "id": idea_version_id,
        "idea_id": idea_id,
        "source_run_id": run_id,
        "title": "Proof idea",
    }
    artifact = {
        "id": artifact_id,
        "idea_id": idea_id,
        "idea_version_id": idea_version_id,
        "source_run_id": run_id,
        "title": "Proof evidence",
    }
    with connection.cursor() as cursor:
        cursor.execute(
            "select public.finalize_direct_backtest_success("
            " %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb)",
            (
                owner["user_id"],
                job_id,
                f"direct:{job_id}",
                json.dumps(run),
                json.dumps(idea),
                json.dumps(idea_version),
                json.dumps(artifact),
            ),
        )
        return cursor.fetchone()[0]


def test_direct_success_commits_tuple_and_job_flip_in_one_boundary(owner):
    with _connect() as connection:
        admitted = _admit(
            connection,
            owner,
            operation_scope="backtests.run",
            initial_status="running",
            conversation_id=None,
        )
        job_id = admitted["job"]["id"]
        run_id = str(uuid.uuid4())

        finalized = _finalize_direct_success(
            connection, owner, job_id=job_id, run_id=run_id
        )

        assert finalized is not None
        assert finalized["run"]["id"] == run_id
        with connection.cursor() as cursor:
            cursor.execute(
                "select status, result_run_id from public.backtest_jobs" " where id = %s",
                (job_id,),
            )
            status, result_run_id = cursor.fetchone()
            cursor.execute(
                "select count(*) from public.backtest_runs where id = %s",
                (run_id,),
            )
            run_rows = cursor.fetchone()[0]
        assert status == "succeeded"
        assert str(result_run_id) == run_id
        assert run_rows == 1


def test_reconciled_direct_job_blocks_late_success_without_a_tuple(owner):
    with _connect() as connection:
        admitted = _admit(
            connection,
            owner,
            operation_scope="backtests.run",
            initial_status="running",
            conversation_id=None,
        )
        job_id = admitted["job"]["id"]
        run_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "update public.backtest_jobs set status='failed',"
                " failure_code='direct_execution_abandoned', retryable=true,"
                " finished_at=now() where id = %s",
                (job_id,),
            )

        finalized = _finalize_direct_success(
            connection, owner, job_id=job_id, run_id=run_id
        )

        assert finalized is None
        with connection.cursor() as cursor:
            cursor.execute(
                "select status, failure_code, result_run_id"
                " from public.backtest_jobs where id = %s",
                (job_id,),
            )
            status, failure_code, result_run_id = cursor.fetchone()
            cursor.execute(
                "select count(*) from public.backtest_runs where id = %s",
                (run_id,),
            )
            run_rows = cursor.fetchone()[0]
        assert status == "failed"
        assert failure_code == "direct_execution_abandoned"
        assert result_run_id is None
        assert run_rows == 0
