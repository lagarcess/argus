"""The result-attach guard against real Postgres, in every encoding.

The round-7 interleaving: in the proof-shadow configuration the link
write carries ``mark_succeeded=False``, and before this lane it bypassed
the lifecycle statement entirely, so a job whose card had already been
restored could still gain ``result_run_id`` and a published result.
These proofs run the real writers, worker SQL, API PostgREST, and the
proof task's status transitions, against the disposable local stack and
assert the interleaving is impossible rather than unlikely, while the
legitimate proof-shadow success path still links.

Set ``ARGUS_DISPOSABLE_DATABASE_URL`` plus ``ARGUS_LOCAL_SUPABASE_URL``
and ``ARGUS_LOCAL_SUPABASE_SERVICE_ROLE_KEY`` to run locally.
"""

from __future__ import annotations

import itertools
import json as _json
import os
import uuid

import pytest


@pytest.fixture(autouse=True)
def _in_place_surface_enabled(monkeypatch):
    """The card consume/restore legs exercise the in-place surface, which
    ships default-off behind ARGUS_IN_PLACE_CARD_EDITS_ENABLED until this
    guard lane closes. The link-write predicates themselves are unflagged
    correctness."""
    monkeypatch.setenv("ARGUS_IN_PLACE_CARD_EDITS_ENABLED", "true")


DSN = os.getenv("ARGUS_DISPOSABLE_DATABASE_URL", "").strip()
LOCAL_URL = os.getenv("ARGUS_LOCAL_SUPABASE_URL", "").strip()
LOCAL_SERVICE_KEY = os.getenv("ARGUS_LOCAL_SUPABASE_SERVICE_ROLE_KEY", "").strip()

pytestmark = pytest.mark.skipif(
    not (DSN and LOCAL_URL and LOCAL_SERVICE_KEY),
    reason="disposable local Supabase is not configured",
)
psycopg = pytest.importorskip("psycopg")


def _connect():
    return psycopg.connect(DSN, autocommit=True)


def _seed_owner(connection) -> dict[str, str]:
    user_id = str(uuid.uuid4())
    conversation_id = str(uuid.uuid4())
    email = f"job-link-{user_id[:8]}@argus.local"
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
            " values (%s, %s, 'job link proof')",
            (conversation_id, user_id),
        )
    return {"user_id": user_id, "conversation_id": conversation_id}


def _seed_job(
    connection,
    owner,
    *,
    status: str,
    retryable: bool,
    confirmation_message_id: str | None = None,
    kind: str = "render_workflow_proof",
) -> str:
    job_id = str(uuid.uuid4())
    with connection.cursor() as cursor:
        cursor.execute(
            """
            insert into public.backtest_jobs
              (id, user_id, operation_scope, idempotency_key, identity_hash,
               payload_hash, launch_payload, status, retryable,
               conversation_id, confirmation_message_id)
            values (%s, %s, 'chat.run_backtest', %s, 'identity', 'payload',
                    %s::jsonb, %s, %s, %s, %s)
            """,
            (
                job_id,
                owner["user_id"],
                f"key-{job_id[:8]}",
                _json.dumps({"kind": kind}),
                status,
                retryable,
                owner["conversation_id"],
                confirmation_message_id,
            ),
        )
    return job_id


def _seed_run(connection, owner) -> str:
    run_id = str(uuid.uuid4())
    with connection.cursor() as cursor:
        cursor.execute(
            """
            insert into public.backtest_runs
              (id, user_id, conversation_id, status, asset_class, symbols,
               benchmark_symbol, config_snapshot)
            values (%s, %s, %s, 'completed', 'equity', %s, 'SPY', %s::jsonb)
            """,
            (
                run_id,
                owner["user_id"],
                owner["conversation_id"],
                ["NFLX"],
                _json.dumps({"kind": "test"}),
            ),
        )
    return run_id


def _job_row(connection, job_id):
    with connection.cursor() as cursor:
        cursor.execute(
            "select status, result_run_id, retryable"
            " from public.backtest_jobs where id = %s",
            (job_id,),
        )
        return cursor.fetchone()


def _supabase_gateway():
    from argus.domain.supabase_gateway import SupabaseGateway

    from supabase import create_client

    return SupabaseGateway(client=create_client(LOCAL_URL, LOCAL_SERVICE_KEY))


def _worker_gateway():
    from workflows.backtest_job import PostgresBacktestJobGateway

    return PostgresBacktestJobGateway(DSN)


def _proof_gateway():
    from workflows.proof import PostgresProofJobGateway

    return PostgresProofJobGateway(DSN)


def _consumed_card(gateway, owner) -> str:
    from argus.api.chat.confirmation import consume_pending_card_for_run

    card = gateway.create_message(
        user_id=owner["user_id"],
        conversation_id=owner["conversation_id"],
        role="assistant",
        content="Buy and hold NFLX",
        metadata={
            "conversation_mode": "confirm",
            "confirmation_card": {
                "confirmation_id": f"conf-{uuid.uuid4().hex[:8]}",
                "confirmation_state": "active",
            },
            "confirmation_payload": {"strategy": {"capital_amount": 10000}},
        },
    )
    assert (
        consume_pending_card_for_run(
            user_id=owner["user_id"],
            conversation_id=owner["conversation_id"],
            message_id=card.id,
            gateway=gateway,
        )
        == "consumed"
    )
    return card.id


def _card_state(gateway, owner, message_id: str) -> str:
    stored = gateway.get_message(
        user_id=owner["user_id"],
        conversation_id=owner["conversation_id"],
        message_id=message_id,
    )
    assert stored is not None
    return stored.metadata["confirmation_card"]["confirmation_state"]


def test_the_attach_predicate_agrees_with_the_classifier_on_postgres() -> None:
    """Walk every state the database allows and assert the generated
    attach fragment and the Python classification never disagree."""
    from argus.domain.backtest_job_lifecycle import (
        JOB_HAS_RESULT,
        JOB_MAY_SUCCEED,
        classify_job_for_card,
        job_result_attach_sql_predicate,
    )

    with _connect() as connection:
        owner = _seed_owner(connection)
        for status, retryable in itertools.product(
            ("queued", "running", "succeeded", "failed", "canceled", "expired"),
            (True, False),
        ):
            job_id = _seed_job(connection, owner, status=status, retryable=retryable)
            with connection.cursor() as cursor:
                cursor.execute(
                    "select "
                    + job_result_attach_sql_predicate()
                    + " from public.backtest_jobs where id = %s",
                    (job_id,),
                )
                sql_allows = bool(cursor.fetchone()[0])
            python_allows = classify_job_for_card(
                status=status, retryable=retryable
            ) in (JOB_MAY_SUCCEED, JOB_HAS_RESULT)
            assert sql_allows == python_allows, (status, retryable)


def test_restored_card_cannot_gain_a_result_through_the_worker_link() -> None:
    """The round-7 interleaving on the worker SQL writer: the reconciler
    cancels the job and restores the card, then the in-process link
    arrives with mark_succeeded=False. The attach is refused, the row is
    unchanged, and the card stays active."""
    from argus.api.chat.confirmation import restore_pending_card_for_failed_job

    with _connect() as connection:
        owner = _seed_owner(connection)
        gateway = _supabase_gateway()
        card_id = _consumed_card(gateway, owner)
        job_id = _seed_job(
            connection,
            owner,
            status="failed",
            retryable=False,
            confirmation_message_id=card_id,
        )
        restore_pending_card_for_failed_job(
            gateway,
            user_id=owner["user_id"],
            job={
                "status": "failed",
                "retryable": False,
                "confirmation_message_id": card_id,
                "conversation_id": owner["conversation_id"],
            },
        )
        assert _card_state(gateway, owner, card_id) == "active"

        run_id = _seed_run(connection, owner)
        standing = _worker_gateway().link_backtest_job_result(
            user_id=owner["user_id"],
            job_id=job_id,
            result_run_id=run_id,
            execution_metadata={"api_in_process_result": {"result_run_id": run_id}},
            mark_succeeded=False,
        )
        assert str(standing.get("status")) == "failed"
        assert standing.get("result_run_id") is None
        status, result_run_id, _ = _job_row(connection, job_id)
        assert status == "failed" and result_run_id is None
        assert _card_state(gateway, owner, card_id) == "active"


def test_restored_card_cannot_gain_a_result_through_the_api_link() -> None:
    """The same interleaving through the API gateway's PostgREST encoding
    of the attach guard."""
    from argus.api.chat.confirmation import restore_pending_card_for_failed_job

    with _connect() as connection:
        owner = _seed_owner(connection)
        gateway = _supabase_gateway()
        card_id = _consumed_card(gateway, owner)
        job_id = _seed_job(
            connection,
            owner,
            status="canceled",
            retryable=False,
            confirmation_message_id=card_id,
        )
        restore_pending_card_for_failed_job(
            gateway,
            user_id=owner["user_id"],
            job={
                "status": "canceled",
                "retryable": False,
                "confirmation_message_id": card_id,
                "conversation_id": owner["conversation_id"],
            },
        )
        assert _card_state(gateway, owner, card_id) == "active"

        run_id = _seed_run(connection, owner)
        standing = gateway.link_backtest_job_result(
            user_id=owner["user_id"],
            job_id=job_id,
            result_run_id=run_id,
            execution_metadata={"api_in_process_result": {"result_run_id": run_id}},
            mark_succeeded=False,
        )
        assert str(standing.get("status")) == "canceled"
        assert standing.get("result_run_id") is None
        status, result_run_id, _ = _job_row(connection, job_id)
        assert status == "canceled" and result_run_id is None
        assert _card_state(gateway, owner, card_id) == "active"


def test_proof_transitions_cannot_revive_a_dead_job() -> None:
    """The proof task's status writes pass the same statement: a canceled
    job accepts neither running nor succeeded, so the proof machinery can
    never re-open the attach window after a restore."""
    with _connect() as connection:
        owner = _seed_owner(connection)
        job_id = _seed_job(connection, owner, status="canceled", retryable=False)
        proof = _proof_gateway()

        for requested in ("running", "succeeded"):
            standing = proof.update_job_status(
                job_id=job_id,
                status=requested,
                execution_metadata={"workflow_proof": {"kind": "render_workflow_proof"}},
            )
            assert str(standing.get("status")) == "canceled", requested
        status, result_run_id, _ = _job_row(connection, job_id)
        assert status == "canceled" and result_run_id is None


def test_proof_shadow_success_path_still_links_the_result() -> None:
    """The legitimate flow is unchanged: the proof task walks the job
    queued to running to succeeded, then the in-process link with
    mark_succeeded=False attaches the result, and the consumed card stays
    consumed."""
    with _connect() as connection:
        owner = _seed_owner(connection)
        gateway = _supabase_gateway()
        card_id = _consumed_card(gateway, owner)
        job_id = _seed_job(
            connection,
            owner,
            status="queued",
            retryable=False,
            confirmation_message_id=card_id,
        )
        proof = _proof_gateway()
        running = proof.update_job_status(
            job_id=job_id,
            status="running",
            execution_metadata={"workflow_proof": {"kind": "render_workflow_proof"}},
        )
        assert str(running.get("status")) == "running"
        succeeded = proof.update_job_status(
            job_id=job_id,
            status="succeeded",
            execution_metadata={"workflow_proof": {"kind": "render_workflow_proof"}},
        )
        assert str(succeeded.get("status")) == "succeeded"

        run_id = _seed_run(connection, owner)
        linked = gateway.link_backtest_job_result(
            user_id=owner["user_id"],
            job_id=job_id,
            result_run_id=run_id,
            execution_metadata={"api_in_process_result": {"result_run_id": run_id}},
            mark_succeeded=False,
        )
        assert str(linked.get("result_run_id")) == run_id
        status, result_run_id, _ = _job_row(connection, job_id)
        assert status == "succeeded" and str(result_run_id) == run_id
        assert _card_state(gateway, owner, card_id) == "consumed"


def _seed_finalized_tuple(connection, owner, run_id: str, *, idea_id: str | None = None):
    """The finalization tuple a withheld run must take with it: idea (or a
    version added to an existing idea), version, evidence artifact."""
    version_id = str(uuid.uuid4())
    evidence_id = str(uuid.uuid4())
    created_idea = idea_id is None
    idea_id = idea_id or str(uuid.uuid4())
    with connection.cursor() as cursor:
        if created_idea:
            cursor.execute(
                """
                insert into public.ideas (id, user_id, title)
                values (%s, %s, 'NFLX buy and hold')
                """,
                (idea_id, owner["user_id"]),
            )
        cursor.execute(
            """
            insert into public.idea_versions
              (id, user_id, idea_id, source_run_id, version_number, title)
            values (%s, %s, %s, %s,
                    (select coalesce(max(version_number), 0) + 1
                     from public.idea_versions where idea_id = %s),
                    'NFLX buy and hold')
            """,
            (version_id, owner["user_id"], idea_id, run_id, idea_id),
        )
        cursor.execute(
            "update public.ideas set active_version_id = %s where id = %s",
            (version_id, idea_id),
        )
        cursor.execute(
            """
            insert into public.evidence_artifacts
              (id, user_id, idea_id, idea_version_id, source_run_id,
               title, digest)
            values (%s, %s, %s, %s, %s, 'NFLX evidence', 'Total return +12.5%%')
            """,
            (evidence_id, owner["user_id"], idea_id, version_id, run_id),
        )
    return {"idea_id": idea_id, "version_id": version_id, "evidence_id": evidence_id}


def _count(connection, sql: str, *params) -> int:
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        return int(cursor.fetchone()[0])


def test_withheld_results_leave_every_product_readable_table() -> None:
    """After a refused link, the caller removes the full finalized tuple:
    run, minted version, evidence (Omnisearch indexes it with no link
    check), and an idea left versionless. Deletion is owner-scoped, and an
    idea with earlier published versions survives, repointed to its
    latest remaining version."""
    with _connect() as connection:
        owner = _seed_owner(connection)
        other = _seed_owner(connection)

        # API gateway: a fresh idea minted by the withheld run disappears.
        api_run = _seed_run(connection, owner)
        api_tuple = _seed_finalized_tuple(connection, owner, api_run)
        assert not _supabase_gateway().delete_withheld_backtest_result(
            user_id=other["user_id"], run_id=api_run
        )
        assert _supabase_gateway().delete_withheld_backtest_result(
            user_id=owner["user_id"], run_id=api_run
        )
        for table, row_id in (
            ("backtest_runs", api_run),
            ("idea_versions", api_tuple["version_id"]),
            ("evidence_artifacts", api_tuple["evidence_id"]),
            ("ideas", api_tuple["idea_id"]),
        ):
            assert (
                _count(
                    connection,
                    f"select count(*) from public.{table} where id = %s",  # noqa: S608
                    row_id,
                )
                == 0
            ), table

        # Worker gateway: an idea with an earlier published version keeps
        # it and repoints its active version.
        published_run = _seed_run(connection, owner)
        published = _seed_finalized_tuple(connection, owner, published_run)
        worker_run = _seed_run(connection, owner)
        withheld = _seed_finalized_tuple(
            connection, owner, worker_run, idea_id=published["idea_id"]
        )
        assert _worker_gateway().delete_withheld_backtest_result(
            user_id=owner["user_id"], run_id=worker_run
        )
        assert (
            _count(
                connection,
                "select count(*) from public.idea_versions where id = %s",
                withheld["version_id"],
            )
            == 0
        )
        assert (
            _count(
                connection,
                "select count(*) from public.evidence_artifacts where id = %s",
                withheld["evidence_id"],
            )
            == 0
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "select active_version_id from public.ideas where id = %s",
                (published["idea_id"],),
            )
            assert str(cursor.fetchone()[0]) == published["version_id"]
        assert (
            _count(
                connection,
                "select count(*) from public.backtest_runs where id = %s",
                worker_run,
            )
            == 0
        )


def test_worker_success_link_still_lands_from_running() -> None:
    """The real-workflow success write is unchanged by the attach guard:
    a running job converts to succeeded with its result in one write."""
    with _connect() as connection:
        owner = _seed_owner(connection)
        job_id = _seed_job(
            connection,
            owner,
            status="running",
            retryable=False,
            kind="run_backtest_job",
        )
        run_id = _seed_run(connection, owner)
        succeeded = _worker_gateway().link_backtest_job_result(
            user_id=owner["user_id"],
            job_id=job_id,
            result_run_id=run_id,
            execution_metadata={"kind": "run_backtest_job"},
            mark_succeeded=True,
        )
        assert str(succeeded.get("status")) == "succeeded"
        assert str(succeeded.get("result_run_id")) == run_id
