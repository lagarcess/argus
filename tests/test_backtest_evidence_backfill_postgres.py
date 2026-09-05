"""The evidence backfill against the real finalizer on the disposable stack.

A June-shaped job: succeeded, linked to a completed run in its conversation,
no idea / idea version / evidence artifact, card without identity. The owner
predicate rejects it, the activity projection reads ``checking``. The backfill
selects it with the owner predicate, finalizes it through
``public.finalize_backtest_completion`` via the Supabase gateway, and the same
predicate then accepts it. A second pass finds nothing.

Set ``ARGUS_DISPOSABLE_DATABASE_URL`` plus ``ARGUS_LOCAL_SUPABASE_URL`` and
``ARGUS_LOCAL_SUPABASE_SERVICE_ROLE_KEY`` to run locally.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

DSN = os.getenv("ARGUS_DISPOSABLE_DATABASE_URL", "").strip()
LOCAL_URL = os.getenv("ARGUS_LOCAL_SUPABASE_URL", "").strip()
LOCAL_SERVICE_KEY = os.getenv("ARGUS_LOCAL_SUPABASE_SERVICE_ROLE_KEY", "").strip()

pytestmark = pytest.mark.skipif(
    not (DSN and LOCAL_URL and LOCAL_SERVICE_KEY),
    reason="disposable local Supabase is not configured",
)
psycopg = pytest.importorskip("psycopg")

OPS_DIR = Path(__file__).resolve().parents[1] / "scripts" / "ops"


def _module():
    sys.path.insert(0, str(OPS_DIR))
    try:
        import backfill_backtest_evidence as module
    finally:
        sys.path.pop(0)
    return module


def _connect():
    return psycopg.connect(DSN, autocommit=True)


def _supabase_gateway():
    from argus.domain.supabase_gateway import SupabaseGateway

    from supabase import create_client

    return SupabaseGateway(client=create_client(LOCAL_URL, LOCAL_SERVICE_KEY))


def _seed_owner(connection) -> dict[str, str]:
    user_id = str(uuid4())
    conversation_id = str(uuid4())
    email = f"backfill-{user_id[:8]}@argus.local"
    with connection.cursor() as cursor:
        cursor.execute(
            "insert into auth.users (id, email) values (%s, %s)", (user_id, email)
        )
        cursor.execute(
            "insert into public.profiles (id, email) values (%s, %s)", (user_id, email)
        )
        cursor.execute(
            "insert into public.conversations (id, user_id, title)"
            " values (%s, %s, 'June backtest')",
            (conversation_id, user_id),
        )
    return {"user_id": user_id, "conversation_id": conversation_id}


def _seed_june_shaped_job(connection, owner) -> tuple[str, str]:
    """The worker's pre-#201 output: run persisted, card without identity,
    job linked and succeeded, no evidence tuple."""
    run_id = str(uuid4())
    job_id = str(uuid4())
    card = {
        "title": "AAPL, MSFT buy and hold",
        "symbols": ["AAPL", "MSFT"],
        "strategy_label": "Buy and hold",
        "date_range": "Jan 1, 2025 to Jun 5, 2026",
        "status_label": "Completed",
        "rows": [{"label": "Total return", "value": "+12.8%"}],
        "benchmark_note": "SPY returned +26.1%",
        "assumptions": ["No fees"],
        "actions": [{"type": "show_breakdown", "payload": {}}],
        "chart": {"kind": "equity_curve"},
    }
    finished = datetime(2026, 6, 10, 14, 18, tzinfo=timezone.utc)
    with connection.cursor() as cursor:
        cursor.execute(
            """
            insert into public.backtest_runs
              (id, user_id, conversation_id, status, asset_class, symbols,
               allocation_method, benchmark_symbol, metrics, config_snapshot,
               conversation_result_card, chart, trades, created_at)
            values (%s, %s, %s, 'completed', 'equity', %s, 'equal_weight', 'SPY',
                    %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s)
            """,
            (
                run_id,
                owner["user_id"],
                owner["conversation_id"],
                ["AAPL", "MSFT"],
                json.dumps({"aggregate": {"performance": {"total_return_pct": 12.8}}}),
                json.dumps({"template": "buy_and_hold", "start_date": "2025-01-01"}),
                json.dumps(card),
                json.dumps(
                    {
                        "kind": "equity_curve",
                        "currency": "USD",
                        "base_value": 10000,
                        "series": [{"date": "2025-01-02", "value": 10000.5}],
                        "markers": [],
                        "attribution": {"provider": "test"},
                    }
                ),
                json.dumps([{"symbol": "AAPL", "side": "buy", "qty": 1.25}]),
                finished,
            ),
        )
        cursor.execute(
            """
            insert into public.backtest_jobs
              (id, user_id, conversation_id, operation_scope, idempotency_key,
               identity_hash, payload_hash, launch_payload, status, result_run_id,
               queued_at, started_at, finished_at, execution_metadata)
            values (%s, %s, %s, 'chat.run_backtest', %s, 'sha256:identity',
                    'sha256:payload', %s::jsonb, 'succeeded', %s, %s, %s, %s, %s::jsonb)
            """,
            (
                job_id,
                owner["user_id"],
                owner["conversation_id"],
                f"conf-{job_id[:8]}",
                json.dumps({"kind": "run_backtest_job", "request": {}}),
                run_id,
                finished,
                finished,
                finished,
                json.dumps(
                    {
                        "shadow_mode": "true",
                        "workflow_backtest": {
                            "kind": "run_backtest_job",
                            "result_run_id": run_id,
                        },
                    }
                ),
            ),
        )
    return job_id, run_id


def _settled(connection, job_id: str) -> bool:
    with connection.cursor() as cursor:
        cursor.execute(
            "select argus_private.backtest_job_result_hydrateable(j)"
            " from public.backtest_jobs as j where j.id = %s",
            (job_id,),
        )
        return bool(cursor.fetchone()[0])


def _job_source(connection, owner) -> dict:
    with connection.cursor() as cursor:
        cursor.execute(
            "select sources from public.read_conversation_activity_sources(%s, %s)",
            (owner["user_id"], [owner["conversation_id"]]),
        )
        sources = cursor.fetchone()[0]
    jobs = [source for source in sources if source["source_kind"] == "backtest_job"]
    assert len(jobs) == 1
    return jobs[0]


def _delete_identity(connection, user_id: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute("delete from auth.users where id = %s", (user_id,))


def test_backfill_finalizes_a_june_shaped_job_until_the_owner_predicate_accepts_it() -> (
    None
):
    module = _module()
    with _connect() as connection:
        owner = _seed_owner(connection)
        try:
            job_id, run_id = _seed_june_shaped_job(connection, owner)
            assert not _settled(connection, job_id)
            assert _job_source(connection, owner)["result_hydrateable"] is False

            candidates = module.select_candidates(connection, limit=100)
            ours = [candidate for candidate in candidates if candidate.job_id == job_id]
            assert len(ours) == 1
            assert ours[0].result_run_id == run_id

            gateway = _supabase_gateway()
            dry = module.run_backfill(
                ours,
                gateway=gateway,
                apply=False,
                settled=lambda _job_id: pytest.fail("dry run must not verify"),
            )
            assert dry["jobs"][0]["outcome"] == "candidate"
            assert not _settled(connection, job_id)

            report = module.run_backfill(
                ours,
                gateway=gateway,
                apply=True,
                settled=lambda candidate_job_id: module.job_is_settled(
                    connection, job_id=candidate_job_id
                ),
            )
            assert report["status"] == "ready", report
            assert report["jobs"][0]["outcome"] == "finalized"
            identity = report["jobs"][0]["identity"]

            assert _settled(connection, job_id)
            assert _job_source(connection, owner)["result_hydrateable"] is True
            with connection.cursor() as cursor:
                cursor.execute(
                    "select e.id::text, e.idea_id::text, e.idea_version_id::text,"
                    " e.source_conversation_id::text, r.conversation_result_card"
                    " from public.evidence_artifacts as e"
                    " join public.backtest_runs as r on r.id = e.source_run_id"
                    " where e.source_run_id = %s",
                    (run_id,),
                )
                artifact_id, idea_id, version_id, source_conversation, card = (
                    cursor.fetchone()
                )
            assert artifact_id == identity["evidence_artifact_id"]
            assert idea_id == identity["idea_id"]
            assert version_id == identity["idea_version_id"]
            assert source_conversation == owner["conversation_id"]
            assert card["evidence_artifact_id"] == artifact_id
            assert card["idea_id"] == idea_id
            assert card["idea_version_id"] == version_id
            assert card["title"] == "AAPL, MSFT buy and hold"
            assert card["rows"] == [{"label": "Total return", "value": "+12.8%"}]

            # A second pass has nothing left to do.
            remaining = [
                candidate
                for candidate in module.select_candidates(connection, limit=100)
                if candidate.job_id == job_id
            ]
            assert remaining == []
        finally:
            _delete_identity(connection, owner["user_id"])
