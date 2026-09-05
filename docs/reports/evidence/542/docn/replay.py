"""Local PostgreSQL/PostgREST replay of the DOCN refusal, without providers.

Run from the repository root with PYTHONPATH=.:src, ARGUS_DISPOSABLE_DATABASE_URL
and ARGUS_REPLAY_POSTGREST_URL pointing at a disposable migrated local database.
Pass --expect-receipt when testing PR #543; omit it for production 7d8ace45.
"""

from __future__ import annotations

import argparse
import json
import os
from urllib.parse import urlparse
from uuid import uuid4

from argus.agent_runtime.stages.execute import execute_stage
from argus.agent_runtime.state.models import RunState
from argus.api.chat.backtest_jobs import (
    BacktestJobShadowContext,
    ShadowBacktestJobTool,
    backtest_job_shadow_context,
)
from argus.domain.supabase_gateway import SupabaseGateway
from argus.domain.usage_limits import (
    GUEST_SIMULATION_ALLOWANCE,
    SIMULATION_USAGE_RESOURCE,
)
from postgrest import SyncPostgrestClient

from tests.test_allowance_accounting_postgres import (
    _admit,
    _connect,
    _guest_limits,
    _seed_guest_owner,
    _usage_rows,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expect-receipt", action="store_true")
    args = parser.parse_args()
    rest_url = os.environ["ARGUS_REPLAY_POSTGREST_URL"]
    for value in (rest_url, os.environ["ARGUS_DISPOSABLE_DATABASE_URL"]):
        if urlparse(value).hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise RuntimeError(
                "This replay is restricted to disposable loopback services"
            )

    with _connect() as db, SyncPostgrestClient(rest_url) as client:
        owner = _seed_guest_owner(db)
        try:
            windows = _guest_limits(owner, GUEST_SIMULATION_ALLOWANCE)
            for _ in range(GUEST_SIMULATION_ALLOWANCE):
                admitted = _admit(db, owner, allowance_limits=json.dumps(windows))
                assert admitted["decision"] == "admitted"
                db.execute(
                    "update public.backtest_jobs set status='failed',"
                    " finished_at=now(),failure_code='test_fixture' where id=%s",
                    (admitted["job"]["id"],),
                )
            owner["conversation_id"] = db.execute(
                "select id::text from public.replace_guest_conversation("
                "%s,'New idea','system_default','en')",
                (owner["user_id"],),
            ).fetchone()[0]
            before = _usage_rows(db, owner["user_id"], SIMULATION_USAGE_RESOURCE)
            assert before["guest_session"]["used_count"] == GUEST_SIMULATION_ALLOWANCE
            assert (
                db.execute(
                    "select count(*) from public.backtest_jobs where user_id=%s",
                    (owner["user_id"],),
                ).fetchone()[0]
                == 0
            )
            confirmation_message_id = str(uuid4())
            request_message_id = str(uuid4())
            for message_id, role in (
                (confirmation_message_id, "assistant"),
                (request_message_id, "user"),
            ):
                db.execute(
                    "insert into public.messages(id,user_id,conversation_id,role,content)"
                    " values(%s,%s,%s,%s,'Local DOCN admission proof')",
                    (message_id, owner["user_id"], owner["conversation_id"], role),
                )
            key = f"confirmation-{uuid4()}"
            context = BacktestJobShadowContext(
                user_id=owner["user_id"],
                conversation_id=owner["conversation_id"],
                account_kind="guest",
                request_message_id=request_message_id,
                confirmation_message_id=confirmation_message_id,
                idempotency_key=key,
                request_id=str(uuid4()),
                chat_action={"type": "run_backtest", "confirmation_id": key},
                allowance_limits=windows,
                visitor_key=f"visitor:local-replay-{uuid4()}",
            )
            gateway = SupabaseGateway(client=client)  # type: ignore[arg-type]
            tool = ShadowBacktestJobTool(
                delegate=None,
                gateway_getter=lambda: gateway,
                dev_memory_fallback_getter=lambda: False,
            )
            state = RunState.new(
                current_user_message="Run backtest", recent_thread_history=[]
            )
            state.confirmation_payload = {
                "strategy_type": "buy_and_hold",
                "symbol": "DOCN",
                "symbols": ["DOCN"],
                "asset_class": "equity",
                "timeframe": "1D",
                "date_range": {"start": "2023-09-05", "end": "2026-09-03"},
                "capital_amount": 1000,
                "sizing_mode": "capital_amount",
                "benchmark_symbol": "SPY",
                "language": "en",
            }
            with backtest_job_shadow_context(context):
                result = execute_stage(state=state, tool=tool, max_retries=1)
            jobs = db.execute(
                "select status,failure_code,failure_detail,idempotency_key,"
                " execution_metadata->>'admission_decision' from public.backtest_jobs"
                " where user_id=%s",
                (owner["user_id"],),
            ).fetchall()
            assert _usage_rows(db, owner["user_id"], SIMULATION_USAGE_RESOURCE) == before
            assert context.workflow_dispatch_started is False
            if args.expect_receipt:
                [job] = jobs
                assert job[:3] == (
                    "failed",
                    "account_conversion_required",
                    "guest_simulation_allowance_exhausted",
                )
                assert job[3].startswith("rejection:") and job[3] != key
                assert job[4] == "conversion_required"
                assert result.patch["final_response_payload"]["code"] == job[1]
                assert "used its simulation allowance" in result.patch["assistant_prompt"]
                with backtest_job_shadow_context(context):
                    replay = execute_stage(state=state, tool=tool, max_retries=1)
                assert (
                    replay.patch["backtest_job"]["id"]
                    == result.patch["backtest_job"]["id"]
                )
                assert db.execute(
                    "select count(*) from public.backtest_jobs where user_id=%s",
                    (owner["user_id"],),
                ).fetchone()[0] == 1
                assert _usage_rows(db, owner["user_id"], SIMULATION_USAGE_RESOURCE) == before
            else:
                assert jobs == []
                assert "could not complete" in result.patch["assistant_prompt"]
            print(
                json.dumps(
                    {
                        "postgres": db.execute("show server_version").fetchone()[0],
                        "definition_md5": dict(
                            db.execute(
                                "select proname,md5(pg_get_functiondef(oid)) from pg_proc"
                                " where pronamespace in ('public'::regnamespace,'argus_private'::regnamespace)"
                                " and proname in ('admit_backtest_job','validated_usage_windows',"
                                " 'replace_guest_conversation')"
                            ).fetchall()
                        ),
                        "jobs_before": 0,
                        "used_before": before["guest_session"]["used_count"],
                        "jobs_after": len(jobs),
                        "workflow_dispatched": context.workflow_dispatch_started,
                        "outcome": result.outcome,
                        "assistant_prompt": result.patch["assistant_prompt"],
                        "public_code": result.patch.get("final_response_payload", {}).get(
                            "code"
                        ),
                        "failure_code": jobs[0][1] if jobs else None,
                        "receipt_replay_verified": args.expect_receipt,
                        "allowance_unchanged": True,
                    },
                    indent=2,
                )
            )
        finally:
            db.execute("delete from auth.users where id=%s", (owner["user_id"],))


if __name__ == "__main__":
    main()
