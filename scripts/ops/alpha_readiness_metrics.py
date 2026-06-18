from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from math import floor, isfinite
from typing import Any, Sequence

import httpx
from dotenv import load_dotenv

TERMINAL_FAILURE_STATUSES = {"failed", "canceled", "expired"}


def _copy_first_env(target: str, candidates: Sequence[str]) -> None:
    if os.getenv(target):
        return
    for candidate in candidates:
        value = os.getenv(candidate)
        if value:
            os.environ[target] = value
            return


def _prepare_supabase_env() -> None:
    _copy_first_env(
        "ARGUS_ALPHA_METRICS_SUPABASE_URL",
        (
            "ARGUS_CANARY_SUPABASE_URL",
            "ARGUS_STALE_JOBS_SUPABASE_URL",
            "SUPABASE_URL",
            "SUPABASE_PROJECT_URL",
        ),
    )
    _copy_first_env(
        "ARGUS_ALPHA_METRICS_SUPABASE_SERVICE_ROLE_KEY",
        (
            "ARGUS_CANARY_SUPABASE_SERVICE_ROLE_KEY",
            "ARGUS_STALE_JOBS_SUPABASE_SERVICE_ROLE_KEY",
            "SUPABASE_SERVICE_ROLE_KEY",
        ),
    )


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _elapsed_ms(start: Any, finish: Any) -> float | None:
    start_dt = _parse_timestamp(start)
    finish_dt = _parse_timestamp(finish)
    if start_dt is None or finish_dt is None:
        return None
    return round(max(0.0, (finish_dt - start_dt).total_seconds() * 1000.0), 3)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        raise ValueError("percentile requires at least one value")
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 3)
    rank = (len(ordered) - 1) * percentile
    lower_index = floor(rank)
    upper_index = min(lower_index + 1, len(ordered) - 1)
    weight = rank - lower_index
    interpolated = ordered[lower_index] * (1 - weight) + ordered[upper_index] * weight
    return round(interpolated, 3)


def _timing_summary(values: list[float]) -> dict[str, float | int]:
    clean = [float(value) for value in values if isfinite(float(value))]
    if not clean:
        return {}
    return {
        "count": len(clean),
        "p50": _percentile(clean, 0.50),
        "p95": _percentile(clean, 0.95),
        "max": round(max(clean), 3),
    }


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _workflow_timings(metadata: dict[str, Any]) -> dict[str, float]:
    workflow = _dict_or_empty(metadata.get("workflow_backtest"))
    raw = _dict_or_empty(workflow.get("timings_ms"))
    timings: dict[str, float] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or isinstance(value, bool):
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if isfinite(numeric) and numeric >= 0.0:
            timings[key] = round(numeric, 3)
    return timings


def summarize_backtest_jobs(
    jobs: Sequence[dict[str, Any]],
    *,
    window_hours: int,
    generated_at: str,
) -> dict[str, Any]:
    status_counts: Counter[str] = Counter()
    failure_code_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    job_timings: dict[str, list[float]] = defaultdict(list)
    workflow_timings: dict[str, list[float]] = defaultdict(list)
    llm_explain_stage_count = 0
    fallback_count = 0
    missing_workflow_metadata_count = 0
    terminal_failures = 0
    active_jobs = 0

    for job in jobs:
        status = str(job.get("status") or "unknown")
        status_counts[status] += 1
        if status in {"queued", "running"}:
            active_jobs += 1
        if status in TERMINAL_FAILURE_STATUSES:
            terminal_failures += 1
            failure_code = str(job.get("failure_code") or "unknown")
            failure_code_counts[failure_code] += 1

        queued_to_started = _elapsed_ms(job.get("queued_at"), job.get("started_at"))
        started_to_finished = _elapsed_ms(job.get("started_at"), job.get("finished_at"))
        queued_to_finished = _elapsed_ms(job.get("queued_at"), job.get("finished_at"))
        for key, value in (
            ("queued_to_started", queued_to_started),
            ("started_to_finished", started_to_finished),
            ("queued_to_finished", queued_to_finished),
        ):
            if value is not None:
                job_timings[key].append(value)

        metadata = _dict_or_empty(job.get("execution_metadata"))
        workflow = _dict_or_empty(metadata.get("workflow_backtest"))
        if not workflow:
            missing_workflow_metadata_count += 1
        else:
            source = str(workflow.get("result_readout_source") or "unknown")
            source_counts[source] += 1
            fallback_used = workflow.get("result_readout_fallback_used")
            if source == "llm_explain_stage" and fallback_used is False:
                llm_explain_stage_count += 1
            if source == "deterministic_fallback" or fallback_used is True:
                fallback_count += 1

        for key, value in _workflow_timings(metadata).items():
            workflow_timings[key].append(value)

    return {
        "generated_at": generated_at,
        "window_hours": window_hours,
        "job_count": len(jobs),
        "status_counts": dict(sorted(status_counts.items())),
        "failure_code_counts": dict(sorted(failure_code_counts.items())),
        "readout": {
            "llm_explain_stage_count": llm_explain_stage_count,
            "fallback_count": fallback_count,
            "missing_workflow_metadata_count": missing_workflow_metadata_count,
            "source_counts": dict(sorted(source_counts.items())),
        },
        "job_timing_ms": {
            key: summary
            for key, values in sorted(job_timings.items())
            if (summary := _timing_summary(values))
        },
        "workflow_timing_ms": {
            key: summary
            for key, values in sorted(workflow_timings.items())
            if (summary := _timing_summary(values))
        },
        "gate_signals": {
            "active_jobs": active_jobs,
            "terminal_failures": terminal_failures,
            "deterministic_readout_fallbacks": fallback_count,
            "missing_workflow_metadata": missing_workflow_metadata_count,
        },
    }


def _fetch_recent_backtest_jobs(
    *,
    base_url: str,
    service_role_key: str,
    since: datetime,
    limit: int,
) -> list[dict[str, Any]]:
    params = httpx.QueryParams(
        {
            "select": (
                "status,queued_at,started_at,finished_at,created_at,updated_at,"
                "result_run_id,failure_code,execution_metadata"
            ),
            "created_at": f"gte.{since.isoformat()}",
            "order": "created_at.desc",
            "limit": str(max(1, limit)),
        }
    )
    headers = {
        "apikey": service_role_key,
        "Authorization": f"Bearer {service_role_key}",
        "Accept": "application/json",
    }
    with httpx.Client(timeout=30.0) as client:
        response = client.get(f"{base_url.rstrip('/')}/rest/v1/backtest_jobs", params=params, headers=headers)
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, list):
        raise RuntimeError("Supabase REST response was not a list.")
    return [dict(row) for row in payload if isinstance(row, dict)]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize private-alpha backtest job health from existing Supabase "
            "execution metadata without emitting user, conversation, or prompt data."
        ),
    )
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument(
        "--fail-on-degraded",
        action="store_true",
        help="Exit non-zero when fallback readouts, terminal failures, or missing metadata are present.",
    )
    return parser


def _print_text(summary: dict[str, Any]) -> None:
    print(
        "alpha readiness metrics: "
        f"window={summary['window_hours']}h "
        f"jobs={summary['job_count']} "
        f"statuses={summary['status_counts']}"
    )
    readout = summary["readout"]
    print(
        "readout: "
        f"llm={readout['llm_explain_stage_count']} "
        f"fallback={readout['fallback_count']} "
        f"missing_workflow_metadata={readout['missing_workflow_metadata_count']} "
        f"sources={readout['source_counts']}"
    )
    for label, timings in (
        ("job_timing_ms", summary["job_timing_ms"]),
        ("workflow_timing_ms", summary["workflow_timing_ms"]),
    ):
        if timings:
            print(f"{label}: {timings}")
    print(f"gate_signals: {summary['gate_signals']}")


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv()
    args = _build_parser().parse_args(argv)
    _prepare_supabase_env()

    base_url = os.getenv("ARGUS_ALPHA_METRICS_SUPABASE_URL")
    service_role_key = os.getenv("ARGUS_ALPHA_METRICS_SUPABASE_SERVICE_ROLE_KEY")
    if not base_url or not service_role_key:
        raise RuntimeError(
            "ARGUS_ALPHA_METRICS_SUPABASE_URL and "
            "ARGUS_ALPHA_METRICS_SUPABASE_SERVICE_ROLE_KEY are required."
        )

    generated_at_dt = datetime.now(timezone.utc)
    since = generated_at_dt - timedelta(hours=max(1, args.hours))
    jobs = _fetch_recent_backtest_jobs(
        base_url=base_url,
        service_role_key=service_role_key,
        since=since,
        limit=args.limit,
    )
    summary = summarize_backtest_jobs(
        jobs,
        window_hours=max(1, args.hours),
        generated_at=generated_at_dt.isoformat(),
    )

    if args.json:
        print(json.dumps(summary, sort_keys=True))
    else:
        _print_text(summary)

    degraded = any(
        summary["gate_signals"][key] > 0
        for key in (
            "terminal_failures",
            "deterministic_readout_fallbacks",
            "missing_workflow_metadata",
        )
    )
    return 1 if args.fail_on_degraded and degraded else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
