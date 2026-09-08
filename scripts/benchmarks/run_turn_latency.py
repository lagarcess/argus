"""Bounded real HTTP cohort for #462. No runtime/configuration mutations.

Uses an existing QA login, creates ordinary test conversations, follows only
server-issued Run actions, and reads receipts via a read-only SQL connection.
Raw responses and credentials stay in memory; local correlation ids stay in temp/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import httpx
import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

from scripts.benchmarks.public_alpha_render_load_auth import (
    LoadIdentity,
    create_service_role_session_client,
)
from scripts.benchmarks.render_internet_benchmark import (
    _conversation_id,
    _run_action_headers,
    extract_confirmation_run_action,
)
from scripts.benchmarks.turn_latency import poll_job, stream_turn, typed_outcome


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def receipts_for(connection, request_id):
    with connection.transaction():
        return connection.execute(
            """SELECT task, tier, model, mode, schema_name, latency_ms, outcome,
                      fallback_used, failure_mode,
                      metadata->'turn_execution' AS turn_execution
               FROM public.route_receipts
               WHERE metadata->>'request_id' = %s
               ORDER BY created_at, id""",
            (request_id,),
        ).fetchall()


def observe(client, db, body, *, category, sample_id, case_id, headers=None):
    started_at = utc_now()
    observation, request_id, started = stream_turn(client, body, headers=headers)
    final = observation.final
    outcome = typed_outcome(final)
    job = final.get("backtest_job")
    if not job:
        job = (final.get("final_response_payload") or {}).get("backtest_job")
    record = {
        "sample_id": sample_id,
        "case_id": case_id,
        "requested_category": category,
        "language": body["language"],
        "started_at": started_at,
        "timings": observation.timings,
        "events": observation.events,
        "visible_kind": observation.visible_kind,
        "outcome": outcome,
        "completion_ms": observation.timings.get("done_ms")
        if "final_ms" in observation.timings and not observation.error_kind
        else None,
        "status": "stream_complete"
        if "done_ms" in observation.timings and "final_ms" in observation.timings
        else "incomplete_stream",
    }
    if observation.error_kind:
        record["status"] = "stream_error"
        record["error_kind"] = observation.error_kind
        record["error_code"] = observation.error_code
    if job:
        record["job"] = poll_job(client, job["id"], started)
        record["job"].setdefault("operation_scope", job.get("operation_scope"))
        record["completion_ms"] = record["job"]["completion_ms"]
        record["status"] = record["job"]["status"]
    try:
        record["receipts"] = receipts_for(db, request_id) if request_id else []
        record["receipt_status"] = "read" if request_id else "missing_request_id"
    except psycopg.Error as exc:
        record["receipts"] = []
        record["receipt_status"] = "unavailable"
        record["receipt_error_kind"] = type(exc).__name__
    correlation = {
        "sample_id": sample_id,
        "request_id": request_id,
        "conversation_id": body["conversation_id"],
        "message_id": final.get("message_id"),
        "job_id": job.get("id") if job else None,
    }
    return record, correlation, final


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-live", action="store_true", required=True)
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args()
    load_dotenv(args.env_file, override=False)
    manifest = json.loads(args.manifest.read_text())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if (args.output_dir / "observations.jsonl").exists():
        parser.error(
            "output directory already has observations; choose a fresh directory"
        )
    provenance = {
        "schema_version": "argus_turn_latency/v1",
        "started_at": utc_now(),
        "api_url": args.api_url,
        "source_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "script_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [Path(__file__), Path(__file__).with_name("turn_latency.py")]
        },
        "sample_start": args.start,
        "sample_limit": args.limit,
        "concurrency": 1,
        "clock": "time.perf_counter",
        "quantiles": "nearest_rank",
        "warmup": "health and authenticated login only; no measured turn discarded",
    }
    (args.output_dir / "provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n"
    )
    # Existing repository QA session mechanism. Require an existing profile:
    # generate_link can create users, which this measurement must never do.
    supabase_url = os.environ["SUPABASE_PROJECT_URL"].rstrip("/")
    service_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    email = os.environ["MOCK_USER_EMAIL"]
    with httpx.Client(
        base_url=supabase_url,
        timeout=30,
        headers={
            "apikey": service_key,
            "Authorization": "Bearer " + service_key,
        },
    ) as service_client:
        existing = service_client.get(
            "/rest/v1/profiles",
            params={
                "select": "id",
                "email": "eq." + email,
                "limit": "1",
            },
        )
        existing.raise_for_status()
        if len(existing.json()) != 1:
            raise RuntimeError("configured QA profile is absent; no identity created")
        client = create_service_role_session_client(
            SimpleNamespace(api_url=args.api_url, timeout_seconds=180),
            service_client,
            LoadIdentity(label="issue-462-qa", email=email),
        )
    provenance["authentication"] = (
        "existing_QA_profile_admin_generated_link_no_email_sent"
    )
    with (
        client,
        psycopg.connect(
            os.environ["SUPABASE_POSTGRES_SESSION_POOLER_URL"],
            connect_timeout=20,
            options="-c default_transaction_read_only=on -c statement_timeout=15000",
            row_factory=dict_row,
        ) as db,
    ):
        client.get("/health").raise_for_status()
        client.get("/api/v1/me").raise_for_status()
        with (
            (args.output_dir / "observations.jsonl").open("w") as output,
            (args.output_dir / "private-correlations.jsonl").open("w") as correlations,
        ):
            for iteration in range(args.start, args.start + args.limit):
                for group in manifest["categories"]:
                    case = group["cases"][iteration % len(group["cases"])]
                    response = client.post("/api/v1/conversations", json={})
                    response.raise_for_status()
                    body = {
                        "conversation_id": _conversation_id(response.json()),
                        "message": case["message"],
                        "language": case["language"],
                        "memory_opt_out": True,
                    }
                    sample_id = f"{group['category']}-{iteration + 1:02d}"
                    record, correlation, final = observe(
                        client,
                        db,
                        body,
                        category=group["category"],
                        sample_id=sample_id,
                        case_id=case["id"],
                    )
                    save(output, correlations, record, correlation)
                    if group.get("run_backtest") and record["outcome"]["confirmation"]:
                        action = extract_confirmation_run_action(
                            [{"type": "final", "payload": final}]
                        )
                        run_body = {k: v for k, v in body.items() if k != "message"}
                        run_body["action"] = action
                        record, correlation, _ = observe(
                            client,
                            db,
                            run_body,
                            category="backtest_run",
                            sample_id=f"backtest_run-{iteration + 1:02d}",
                            case_id=case["id"],
                            headers=_run_action_headers(action),
                        )
                        save(output, correlations, record, correlation)
    provenance["finished_at"] = utc_now()
    (args.output_dir / "provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n"
    )


def save(output, correlations, record, correlation):
    output.write(json.dumps(record, default=str) + "\n")
    output.flush()
    correlations.write(json.dumps(correlation) + "\n")
    correlations.flush()
    print(
        json.dumps(
            {
                "sample": record["sample_id"],
                "outcome": record["outcome"],
                "ttft_ms": record["timings"].get("first_token_ms"),
                "completion_ms": record["completion_ms"],
                "status": record["status"],
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
