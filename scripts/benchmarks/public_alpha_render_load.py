#!/usr/bin/env python
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from math import ceil
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from loguru import logger

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from scripts.benchmarks.render_internet_benchmark import (
        _conversation_id,
        _poll_backtest_job,
        _stream_chat,
        _timed_json_request,
        extract_confirmation_run_action,
        extract_run_reference,
        parse_sse_events,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from render_internet_benchmark import (
        _conversation_id,
        _poll_backtest_job,
        _stream_chat,
        _timed_json_request,
        extract_confirmation_run_action,
        extract_run_reference,
        parse_sse_events,
    )

from argus.api.chat.backtest_jobs import (  # noqa: E402
    RenderTaskRunClient,
    RenderWorkflowDispatcher,
)

from workflows.backtest_job import (  # noqa: E402
    CAPACITY_LOAD_AUTHORITY,
    CAPACITY_LOAD_SOURCE,
    REAL_BACKTEST_JOB_KIND,
    capacity_probe_mode,
)

__all__ = ["capacity_probe_mode"]

SCHEMA_VERSION = "argus_public_alpha_render_load/v1"
CASE_MANIFEST = (
    "idle_one",
    "global_five",
    "same_user_one_running_two_queued",
    "global_five_running_ten_queued",
    "invalid_envelope_retry",
    "upstream_transient_retry",
)
CASE_ADMISSIONS = {
    "idle_one": 1,
    "global_five": 5,
    "same_user_one_running_two_queued": 3,
    "global_five_running_ten_queued": 15,
    "invalid_envelope_retry": 1,
    "upstream_transient_retry": 1,
}
LIMITS = {
    "user_running": 1,
    "user_queued": 2,
    "global_running": 5,
    "global_queued": 10,
}
TERMINAL_JOB_STATUSES = {"succeeded", "failed", "canceled", "expired"}
TERMINAL_TASK_STATUSES = {
    "completed",
    "succeeded",
    "failed",
    "canceled",
    "cancelled",
    "expired",
}
FORBIDDEN_ARTIFACT_FIELDS = {
    "access_token",
    "authorization",
    "conversation_id",
    "email",
    "idempotency_key",
    "job_id",
    "message",
    "password",
    "refresh_token",
    "service_role_key",
    "user_id",
}
ALLOWED_FAILURE_CODES = {
    "backtest_capacity_exceeded",
    "failed_upstream",
    "invalid_job_contract",
    "workflow_task_failed",
    "workflow_task_timeout",
}
DEFAULT_PROMPT = (
    "Test an equal-weight AAPL and MSFT buy-and-hold strategy from "
    "January 1, 2025 through June 5, 2026 with 10,000 dollars"
)


@dataclass(frozen=True)
class LoadIdentity:
    label: str
    email: str
    password: str


@dataclass(frozen=True)
class HarnessConfig:
    repo_root: Path
    output_dir: Path
    api_url: str
    app_url: str
    render_api_key: str
    supabase_url: str
    supabase_service_role_key: str
    candidate_sha: str
    workflow_task: str
    identities: tuple[LoadIdentity, ...]
    timeout_seconds: float
    poll_seconds: float
    prompt: str


@dataclass
class PreparedRun:
    client: httpx.Client
    conversation_id: str
    action: dict[str, Any]


@dataclass(frozen=True)
class SubmittedRun:
    job_id: str
    started_monotonic: float


@dataclass(frozen=True)
class CompletedRun:
    job_id: str
    wall_time_ms: float


def default_output_dir(repo_root: Path) -> Path:
    return repo_root / "temp" / "benchmarks" / "public-alpha-render-load"


def build_case_result(
    *,
    case_id: str,
    started_at: str,
    finished_at: str,
    admitted: int,
    rejected: int,
    wall_times_ms: list[float],
    queue_to_start_ms: list[float],
    start_to_finish_ms: list[float],
    terminal_statuses: list[str],
    task_run_ids: list[str],
    retry_attempts: list[int],
    failure_codes: list[str],
    observed_capacity: dict[str, int],
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "admitted": admitted,
        "rejected": rejected,
        "wall_time_ms": _percentiles(wall_times_ms),
        "queue_to_start_ms": _percentiles(queue_to_start_ms),
        "start_to_finish_ms": _percentiles(start_to_finish_ms),
        "terminal_statuses": dict(sorted(Counter(terminal_statuses).items())),
        "render_task_run_ids": list(task_run_ids),
        "retry_attempts": list(retry_attempts),
        "failure_codes": sorted(set(failure_codes)),
        "observed_capacity": dict(observed_capacity),
    }


def validate_report(report: Mapping[str, Any]) -> None:
    _reject_forbidden_artifact_data(report)
    if report.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected public-alpha load artifact schema")
    if report.get("source") != CAPACITY_LOAD_SOURCE:
        raise ValueError("unexpected public-alpha load artifact source")
    candidate_sha = str(report.get("candidate_sha") or "")
    if re.fullmatch(r"[0-9a-f]{40}", candidate_sha) is None:
        raise ValueError("candidate_sha must be one full lowercase Git SHA")
    _validate_artifact_url(report.get("api_url"), field="api_url")
    _validate_artifact_url(report.get("app_url"), field="app_url")
    workflow = report.get("workflow")
    if not isinstance(workflow, Mapping):
        raise ValueError("workflow contract is required")
    if workflow.get("plan") != "standard" or workflow.get("max_retries") != 1:
        raise ValueError("workflow contract must use standard plan and one retry")
    if report.get("limits") != LIMITS:
        raise ValueError("capacity limits do not match the locked envelope")
    cases = report.get("cases")
    if not isinstance(cases, list):
        raise ValueError("cases must be a list")
    case_ids = tuple(
        str(case.get("case_id")) for case in cases if isinstance(case, Mapping)
    )
    if case_ids != CASE_MANIFEST:
        raise ValueError("artifact must contain the exact locked case manifest")
    for case in cases:
        if not isinstance(case, Mapping):
            raise ValueError("case entries must be objects")
        _validate_case(case)


def write_report(
    *,
    report: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    validate_report(report)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "public-alpha-render-load.json"
    serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
    json_path.write_text(serialized, encoding="utf-8")
    return {"json": json_path}


def run_harness(config: HarnessConfig) -> dict[str, Any]:
    service_client = _service_role_client(config)
    created_user_ids: list[str] = []
    load_clients: list[httpx.Client] = []
    cases: list[dict[str, Any]] = []
    report: dict[str, Any] | None = None
    cleanup_completed = False
    try:
        _create_temporary_identities(
            config=config,
            client=service_client,
            user_ids=created_user_ids,
        )
        runtimes = []
        for identity in config.identities:
            runtime = _login_identity(config=config, identity=identity)
            runtimes.append(runtime)
            load_clients.append(runtime)

        idle_run = _prepare_run(
            config=config,
            client=runtimes[0],
            prompt=config.prompt,
        )
        idle_case, seed_job = _run_public_case(
            config=config,
            service_client=service_client,
            case_id="idle_one",
            prepared=[idle_run],
        )
        cases.append(idle_case)

        global_five = [
            _prepare_run(
                config=config,
                client=runtimes[index],
                prompt=config.prompt,
            )
            for index in range(5)
        ]
        case, _ = _run_public_case(
            config=config,
            service_client=service_client,
            case_id="global_five",
            prepared=global_five,
        )
        cases.append(case)

        same_user = []
        for _ in range(3):
            runtime = _login_identity(
                config=config,
                identity=config.identities[0],
            )
            load_clients.append(runtime)
            same_user.append(
                _prepare_run(
                    config=config,
                    client=runtime,
                    prompt=config.prompt,
                )
            )
        case, _ = _run_public_case(
            config=config,
            service_client=service_client,
            case_id="same_user_one_running_two_queued",
            prepared=same_user,
        )
        cases.append(case)

        global_fifteen = [
            _prepare_run(
                config=config,
                client=runtimes[index],
                prompt=config.prompt,
            )
            for index in range(15)
        ]
        case, _ = _run_public_case(
            config=config,
            service_client=service_client,
            case_id="global_five_running_ten_queued",
            prepared=global_fifteen,
        )
        cases.append(case)

        cases.append(
            _run_probe_case(
                config=config,
                service_client=service_client,
                seed_job=seed_job,
                case_id="invalid_envelope_retry",
                mode="invalid_envelope",
            )
        )
        cases.append(
            _run_probe_case(
                config=config,
                service_client=service_client,
                seed_job=seed_job,
                case_id="upstream_transient_retry",
                mode="upstream_transient_once",
            )
        )
        report = _build_report(
            config=config,
            cases=cases,
            cleanup={"status": "pending", "deleted_identities": 0},
        )
        write_report(report=report, output_dir=config.output_dir)
        deleted_count = _cleanup_temporary_identities(
            config=config,
            client=service_client,
            user_ids=created_user_ids,
        )
        report["cleanup"] = {
            "status": "completed",
            "deleted_identities": deleted_count,
        }
        cleanup_completed = True
        write_report(report=report, output_dir=config.output_dir)
        return report
    finally:
        for client in load_clients:
            client.close()
        service_client.close()
        if not cleanup_completed and created_user_ids:
            _best_effort_cleanup(config=config, user_ids=created_user_ids)


def _run_public_case(
    *,
    config: HarnessConfig,
    service_client: httpx.Client,
    case_id: str,
    prepared: list[PreparedRun],
) -> tuple[dict[str, Any], dict[str, Any]]:
    started_at = _utcnow_iso()
    failures: list[str] = []
    completed: list[CompletedRun] = []
    observed = {"running": 0, "queued": 0}
    max_workers = len(prepared)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        submitted: list[tuple[PreparedRun, SubmittedRun]] = []
        submission_groups = _submission_groups(case_id=case_id, prepared=prepared)
        for group_index, group in enumerate(submission_groups):
            submit_futures = [
                pool.submit(_submit_run, config=config, prepared=item) for item in group
            ]
            for item, future in zip(group, submit_futures, strict=True):
                result = _completed_future_value(future)
                if isinstance(result, SubmittedRun):
                    submitted.append((item, result))
                else:
                    failures.append(result)
            job_ids = {run.job_id for _, run in submitted}
            rows = _fetch_jobs(service_client, job_ids)
            _merge_capacity_peak(observed, rows)
            if group_index < len(submission_groups) - 1:
                target_running = 1 if case_id.startswith("same_user") else 5
                _wait_for_capacity(
                    config=config,
                    client=service_client,
                    job_ids=job_ids,
                    peak=observed,
                    running=target_running,
                    queued=0,
                )
        job_ids = {run.job_id for _, run in submitted}
        if case_id == "same_user_one_running_two_queued":
            _wait_for_capacity(
                config=config,
                client=service_client,
                job_ids=job_ids,
                peak=observed,
                running=1,
                queued=2,
            )
        elif case_id == "global_five_running_ten_queued":
            _wait_for_capacity(
                config=config,
                client=service_client,
                job_ids=job_ids,
                peak=observed,
                running=5,
                queued=10,
            )
        poll_futures = [
            pool.submit(_poll_submitted_run, config=config, prepared=item, run=run)
            for item, run in submitted
        ]
        while not all(future.done() for future in poll_futures):
            rows = _fetch_jobs(service_client, job_ids)
            _merge_capacity_peak(observed, rows)
            time.sleep(config.poll_seconds)
        for future in poll_futures:
            result = _completed_future_value(future)
            if isinstance(result, CompletedRun):
                completed.append(result)
            else:
                failures.append(result)
    if len(completed) != CASE_ADMISSIONS[case_id]:
        raise RuntimeError(f"{case_id} did not admit the locked job count")
    rows = _fetch_jobs(service_client, {item.job_id for item in completed})
    _mark_capacity_jobs(service_client, rows)
    rows = _fetch_jobs(service_client, {item.job_id for item in completed})
    _merge_capacity_peak(observed, rows)
    case = _case_from_rows(
        case_id=case_id,
        started_at=started_at,
        finished_at=_utcnow_iso(),
        rows=rows,
        wall_times_ms=[item.wall_time_ms for item in completed],
        admitted=len(completed),
        rejected=len(failures),
        failure_codes=failures,
        observed_capacity=observed,
    )
    return case, rows[0]


def _submission_groups(
    *,
    case_id: str,
    prepared: list[PreparedRun],
) -> list[list[PreparedRun]]:
    if case_id == "same_user_one_running_two_queued":
        return [prepared[:1], prepared[1:]]
    if case_id == "global_five_running_ten_queued":
        return [prepared[:5], prepared[5:]]
    return [prepared]


def _wait_for_capacity(
    *,
    config: HarnessConfig,
    client: httpx.Client,
    job_ids: set[str],
    peak: dict[str, int],
    running: int,
    queued: int,
) -> None:
    deadline = time.monotonic() + config.timeout_seconds
    while True:
        rows = _fetch_jobs(client, job_ids)
        _merge_capacity_peak(peak, rows)
        counts = Counter(str(row.get("status") or "") for row in rows)
        if counts["running"] >= running and counts["queued"] >= queued:
            return
        if any(str(row.get("status") or "") in TERMINAL_JOB_STATUSES for row in rows):
            raise RuntimeError("capacity phase finished before the locked peak")
        if time.monotonic() >= deadline:
            raise RuntimeError("capacity phase did not reach the locked peak")
        time.sleep(config.poll_seconds)


def _prepare_run(
    *,
    config: HarnessConfig,
    client: httpx.Client,
    prompt: str,
) -> PreparedRun:
    conversation = _timed_json_request(
        client,
        "POST",
        f"{config.api_url}/api/v1/conversations",
        json_body={},
    )
    conversation_id = _conversation_id(conversation.body)
    stream = _stream_chat(
        client=client,
        url=f"{config.api_url}/api/v1/chat/stream",
        body={
            "conversation_id": conversation_id,
            "message": prompt,
            "language": "en",
        },
        timeout_seconds=config.timeout_seconds,
    )
    parsed = parse_sse_events(stream["text"])
    if not parsed.done:
        raise RuntimeError("confirmation stream did not finish")
    action = extract_confirmation_run_action(parsed.events)
    return PreparedRun(
        client=client,
        conversation_id=conversation_id,
        action=action,
    )


def _submit_run(
    *,
    config: HarnessConfig,
    prepared: PreparedRun,
) -> SubmittedRun:
    started = time.perf_counter()
    stream = _stream_chat(
        client=prepared.client,
        url=f"{config.api_url}/api/v1/chat/stream",
        body={
            "conversation_id": prepared.conversation_id,
            "action": prepared.action,
            "language": "en",
        },
        timeout_seconds=config.timeout_seconds,
    )
    parsed = parse_sse_events(stream["text"])
    if not parsed.done:
        raise RuntimeError("run stream did not finish")
    reference = extract_run_reference(parsed.events)
    if reference.kind != "job":
        raise RuntimeError("run stream did not return an async job")
    return SubmittedRun(
        job_id=reference.id,
        started_monotonic=started,
    )


def _poll_submitted_run(
    *,
    config: HarnessConfig,
    prepared: PreparedRun,
    run: SubmittedRun,
) -> CompletedRun:
    _poll_backtest_job(
        client=prepared.client,
        api_url=config.api_url,
        job_id=run.job_id,
        timeout_seconds=config.timeout_seconds,
        poll_sleep_seconds=config.poll_seconds,
    )
    return CompletedRun(
        job_id=run.job_id,
        wall_time_ms=(time.perf_counter() - run.started_monotonic) * 1000.0,
    )


def _run_probe_case(
    *,
    config: HarnessConfig,
    service_client: httpx.Client,
    seed_job: Mapping[str, Any],
    case_id: str,
    mode: str,
) -> dict[str, Any]:
    started_at = _utcnow_iso()
    probe_job = _create_probe_job(
        client=service_client,
        seed_job=seed_job,
        mode=mode,
    )
    job_id = str(probe_job["id"])
    dispatcher = RenderWorkflowDispatcher(
        api_key=config.render_api_key,
        task_id=config.workflow_task,
    )
    task_run = dispatcher.dispatch(job_id=job_id, nonce=uuid4().hex)
    task_run_id = str(task_run.get("id") or "").strip()
    if not task_run_id:
        raise RuntimeError("capacity probe dispatch returned no task run")
    task_client = RenderTaskRunClient(api_key=config.render_api_key)
    deadline = time.monotonic() + config.timeout_seconds
    failure_codes: set[str] = set()
    row = probe_job
    while True:
        rows = _fetch_jobs(service_client, {job_id})
        if rows:
            row = rows[0]
            failure_code = _safe_failure_code(row.get("failure_code"))
            if failure_code:
                failure_codes.add(failure_code)
            metadata = row.get("execution_metadata")
            if isinstance(metadata, Mapping):
                workflow = metadata.get("workflow_backtest")
                if isinstance(workflow, Mapping):
                    category = _safe_failure_code(workflow.get("failure_category"))
                    if category:
                        failure_codes.add(category)
        task_details = task_client.get_task_run(task_run_id)
        task_status = str(task_details.get("status") or "").strip().lower()
        attempts = int(row.get("attempts") or 0)
        job_status = str(row.get("status") or "").strip().lower()
        if (
            task_status in TERMINAL_TASK_STATUSES
            and job_status in TERMINAL_JOB_STATUSES
            and attempts >= 2
        ):
            break
        if time.monotonic() >= deadline:
            raise RuntimeError("capacity probe did not reach its terminal contract")
        time.sleep(config.poll_seconds)
    return _case_from_rows(
        case_id=case_id,
        started_at=started_at,
        finished_at=_utcnow_iso(),
        rows=[row],
        wall_times_ms=[_duration_ms(started_at, _utcnow_iso())],
        admitted=1,
        rejected=0,
        failure_codes=sorted(failure_codes),
        observed_capacity={"running": 1, "queued": 0},
        task_run_ids=[task_run_id],
    )


def _create_probe_job(
    *,
    client: httpx.Client,
    seed_job: Mapping[str, Any],
    mode: str,
) -> dict[str, Any]:
    launch_payload = dict(seed_job.get("launch_payload") or {})
    if mode == "invalid_envelope":
        launch_payload["request"] = "not-an-object"
    if launch_payload.get("kind") != REAL_BACKTEST_JOB_KIND:
        raise RuntimeError("seed job does not use the real backtest task")
    job_id = str(uuid4())
    idempotency_key = str(uuid4())
    identity_hash = _sha256_text(f"{job_id}:identity")
    payload_hash = _sha256_json(launch_payload)
    payload = {
        "id": job_id,
        "user_id": seed_job["user_id"],
        "conversation_id": seed_job["conversation_id"],
        "request_message_id": seed_job.get("request_message_id"),
        "confirmation_message_id": seed_job["confirmation_message_id"],
        "operation_scope": "chat.run_backtest",
        "idempotency_key": idempotency_key,
        "identity_hash": identity_hash,
        "payload_hash": payload_hash,
        "launch_payload": launch_payload,
        "status": "queued",
        "priority": "normal",
        "attempts": 0,
        "max_attempts": 2,
        "queued_at": _utcnow_iso(),
        "execution_metadata": {
            "source": CAPACITY_LOAD_SOURCE,
            "ops_authority": CAPACITY_LOAD_AUTHORITY,
            "openrouter_traffic_class": "registered",
            "capacity_probe": {"mode": mode},
        },
    }
    response = client.post(
        "/rest/v1/backtest_jobs",
        headers={"Prefer": "return=representation"},
        json=payload,
    )
    response.raise_for_status()
    rows = response.json()
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
        raise RuntimeError("service-role capacity probe insert returned no row")
    return dict(rows[0])


def _case_from_rows(
    *,
    case_id: str,
    started_at: str,
    finished_at: str,
    rows: list[dict[str, Any]],
    wall_times_ms: list[float],
    admitted: int,
    rejected: int,
    failure_codes: list[str],
    observed_capacity: dict[str, int],
    task_run_ids: list[str] | None = None,
) -> dict[str, Any]:
    queue_times: list[float] = []
    execution_times: list[float] = []
    statuses: list[str] = []
    retries: list[int] = []
    render_ids = list(task_run_ids or [])
    safe_failures = list(failure_codes)
    for row in rows:
        queue_times.append(_duration_ms(row.get("queued_at"), row.get("started_at")))
        execution_times.append(
            _duration_ms(row.get("started_at"), row.get("finished_at"))
        )
        statuses.append(str(row.get("status") or "unknown"))
        retries.append(max(0, int(row.get("attempts") or 0) - 1))
        failure_code = _safe_failure_code(row.get("failure_code"))
        if failure_code:
            safe_failures.append(failure_code)
        task_run_id = _task_run_id(row)
        if task_run_id and task_run_id not in render_ids:
            render_ids.append(task_run_id)
    return build_case_result(
        case_id=case_id,
        started_at=started_at,
        finished_at=finished_at,
        admitted=admitted,
        rejected=rejected,
        wall_times_ms=wall_times_ms,
        queue_to_start_ms=queue_times,
        start_to_finish_ms=execution_times,
        terminal_statuses=statuses,
        task_run_ids=render_ids,
        retry_attempts=retries,
        failure_codes=safe_failures,
        observed_capacity=observed_capacity,
    )


def _create_temporary_identities(
    *,
    config: HarnessConfig,
    client: httpx.Client,
    user_ids: list[str],
) -> None:
    for identity in config.identities:
        existing = client.get(
            "/rest/v1/private_alpha_allowlist",
            params={"select": "email", "email": f"eq.{identity.email}", "limit": "1"},
        )
        existing.raise_for_status()
        if existing.json():
            raise RuntimeError("dedicated load identity is not temporary and unused")
    for identity in config.identities:
        response = client.post(
            "/auth/v1/admin/users",
            json={
                "email": identity.email,
                "password": identity.password,
                "email_confirm": True,
                "user_metadata": {"source": CAPACITY_LOAD_SOURCE},
            },
        )
        response.raise_for_status()
        body = response.json()
        user_id = str(body.get("id") or "").strip()
        if not user_id:
            raise RuntimeError("temporary identity creation returned no user")
        user_ids.append(user_id)
        allowlist = client.post(
            "/rest/v1/private_alpha_allowlist",
            headers={"Prefer": "return=minimal"},
            json={"email": identity.email, "role": "user"},
        )
        allowlist.raise_for_status()


def _cleanup_temporary_identities(
    *,
    config: HarnessConfig,
    client: httpx.Client,
    user_ids: list[str],
) -> int:
    deleted = 0
    for user_id in user_ids:
        response = client.delete(f"/auth/v1/admin/users/{user_id}")
        response.raise_for_status()
        deleted += 1
    for identity in config.identities:
        response = client.delete(
            "/rest/v1/private_alpha_allowlist",
            params={"email": f"eq.{identity.email}"},
        )
        response.raise_for_status()
    return deleted


def _best_effort_cleanup(*, config: HarnessConfig, user_ids: list[str]) -> None:
    client = _service_role_client(config)
    try:
        _cleanup_temporary_identities(
            config=config,
            client=client,
            user_ids=user_ids,
        )
    except Exception:
        logger.error("Public-alpha load cleanup failed", failure_code="cleanup_failed")
    finally:
        client.close()


def _service_role_client(config: HarnessConfig) -> httpx.Client:
    return httpx.Client(
        base_url=config.supabase_url.rstrip("/"),
        headers={
            "apikey": config.supabase_service_role_key,
            "Authorization": f"Bearer {config.supabase_service_role_key}",
        },
        timeout=httpx.Timeout(config.timeout_seconds, connect=20.0),
    )


def _login_identity(
    *,
    config: HarnessConfig,
    identity: LoadIdentity,
) -> httpx.Client:
    client = httpx.Client(
        follow_redirects=True,
        timeout=httpx.Timeout(config.timeout_seconds, connect=20.0),
    )
    try:
        _timed_json_request(
            client,
            "POST",
            f"{config.api_url}/api/v1/auth/login",
            json_body={"email": identity.email, "password": identity.password},
        )
    except Exception:
        client.close()
        raise
    return client


def _fetch_jobs(
    client: httpx.Client,
    job_ids: set[str],
) -> list[dict[str, Any]]:
    if not job_ids:
        return []
    response = client.get(
        "/rest/v1/backtest_jobs",
        params={
            "select": (
                "id,user_id,conversation_id,request_message_id,"
                "confirmation_message_id,launch_payload,status,attempts,"
                "queued_at,started_at,finished_at,failure_code,"
                "execution_metadata"
            ),
            "id": f"in.({','.join(sorted(job_ids))})",
        },
    )
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, list):
        raise RuntimeError("service-role job lookup returned a non-list response")
    return [dict(row) for row in body if isinstance(row, dict)]


def _mark_capacity_jobs(
    client: httpx.Client,
    rows: list[dict[str, Any]],
) -> None:
    for row in rows:
        metadata = row.get("execution_metadata")
        marked_metadata = dict(metadata) if isinstance(metadata, Mapping) else {}
        marked_metadata["source"] = CAPACITY_LOAD_SOURCE
        response = client.patch(
            "/rest/v1/backtest_jobs",
            params={"id": f"eq.{row['id']}"},
            headers={"Prefer": "return=minimal"},
            json={"execution_metadata": marked_metadata},
        )
        response.raise_for_status()


def _merge_capacity_peak(
    peak: dict[str, int],
    rows: list[dict[str, Any]],
) -> None:
    counts = Counter(str(row.get("status") or "") for row in rows)
    peak["running"] = max(peak["running"], counts["running"])
    peak["queued"] = max(peak["queued"], counts["queued"])


def _completed_future_value(
    future: Future[CompletedRun] | Future[SubmittedRun],
) -> CompletedRun | SubmittedRun | str:
    try:
        return future.result()
    except Exception as exc:
        return _safe_failure_code(type(exc).__name__) or "workflow_task_failed"


def _build_report(
    *,
    config: HarnessConfig,
    cases: list[dict[str, Any]],
    cleanup: dict[str, Any],
) -> dict[str, Any]:
    report = {
        "schema_version": SCHEMA_VERSION,
        "candidate_sha": config.candidate_sha,
        "generated_at": _utcnow_iso(),
        "api_url": config.api_url,
        "app_url": config.app_url,
        "source": CAPACITY_LOAD_SOURCE,
        "workflow": {
            "task": config.workflow_task,
            "plan": "standard",
            "max_retries": 1,
        },
        "limits": dict(LIMITS),
        "cases": cases,
        "cleanup": cleanup,
    }
    validate_report(report)
    return report


def _validate_case(case: Mapping[str, Any]) -> None:
    case_id = str(case.get("case_id") or "")
    required_fields = {
        "started_at",
        "finished_at",
        "admitted",
        "rejected",
        "wall_time_ms",
        "queue_to_start_ms",
        "start_to_finish_ms",
        "terminal_statuses",
        "render_task_run_ids",
        "retry_attempts",
        "failure_codes",
    }
    missing = required_fields.difference(case)
    if missing:
        raise ValueError(f"{case_id} is missing required measured fields")
    if case.get("admitted") != CASE_ADMISSIONS[case_id]:
        raise ValueError(f"{case_id} did not admit the locked job count")
    if case.get("rejected") != 0:
        raise ValueError(f"{case_id} rejected a locked-envelope job")
    retries = case.get("retry_attempts")
    if not isinstance(retries, list):
        raise ValueError(f"{case_id} retry_attempts must be a list")
    expected_retry = 1 if case_id.endswith("_retry") else 0
    if any(value != expected_retry for value in retries):
        raise ValueError(f"{case_id} retry evidence does not match the contract")
    admitted = int(case["admitted"])
    if len(retries) != admitted:
        raise ValueError(f"{case_id} lacks per-job retry evidence")
    task_run_ids = case.get("render_task_run_ids")
    if not isinstance(task_run_ids, list) or len(task_run_ids) != admitted:
        raise ValueError(f"{case_id} lacks per-job Render task-run evidence")
    if any(
        not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value) is None
        for value in task_run_ids
    ):
        raise ValueError(f"{case_id} contains an unsafe Render task-run id")
    terminal_statuses = case.get("terminal_statuses")
    if not isinstance(terminal_statuses, Mapping):
        raise ValueError(f"{case_id} terminal_statuses must be an object")
    if sum(int(value) for value in terminal_statuses.values()) != admitted:
        raise ValueError(f"{case_id} lacks one terminal status per admitted job")
    for field in ("wall_time_ms", "queue_to_start_ms", "start_to_finish_ms"):
        summary = case.get(field)
        if not isinstance(summary, Mapping):
            raise ValueError(f"{case_id} {field} must be an object")
        if not all(
            isinstance(summary.get(percentile), (int, float))
            for percentile in ("p50", "p95")
        ):
            raise ValueError(f"{case_id} {field} lacks measured percentiles")
    failure_codes = case.get("failure_codes")
    if not isinstance(failure_codes, list):
        raise ValueError(f"{case_id} failure_codes must be a list")
    if any(code not in ALLOWED_FAILURE_CODES for code in failure_codes):
        raise ValueError(f"{case_id} contains an unsanitized failure code")
    if case_id == "invalid_envelope_retry":
        if "invalid_job_contract" not in failure_codes:
            raise ValueError("invalid-envelope case lacks its terminal failure code")
    if case_id == "upstream_transient_retry":
        if "failed_upstream" not in failure_codes:
            raise ValueError("transient case lacks its first-attempt failure code")
    observed = case.get("observed_capacity")
    if not isinstance(observed, Mapping):
        raise ValueError(f"{case_id} observed_capacity must be an object")
    if case_id == "same_user_one_running_two_queued":
        if observed.get("running", 0) < 1 or observed.get("queued", 0) < 2:
            raise ValueError("same-user case did not observe one running and two queued")
    if case_id == "global_five_running_ten_queued":
        if observed.get("running", 0) < 5 or observed.get("queued", 0) < 10:
            raise ValueError("global case did not observe five running and ten queued")


def _reject_forbidden_artifact_data(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).strip().lower()
            if normalized in FORBIDDEN_ARTIFACT_FIELDS:
                raise ValueError(f"forbidden artifact field: {normalized}")
            _reject_forbidden_artifact_data(item)
        return
    if isinstance(value, list):
        for item in value:
            _reject_forbidden_artifact_data(item)
        return
    if isinstance(value, str) and "@" in value:
        raise ValueError("forbidden artifact field: raw identity value")


def _validate_artifact_url(value: Any, *, field: str) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an HTTPS URL")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"{field} must not contain credentials or query data")


def _percentiles(values: list[float]) -> dict[str, float | None]:
    cleaned = sorted(max(0.0, float(value)) for value in values)
    if not cleaned:
        return {"p50": None, "p95": None}

    def nearest_rank(percentile: float) -> float:
        index = max(0, ceil(percentile * len(cleaned)) - 1)
        return round(cleaned[index], 3)

    return {"p50": nearest_rank(0.50), "p95": nearest_rank(0.95)}


def _task_run_id(row: Mapping[str, Any]) -> str | None:
    metadata = row.get("execution_metadata")
    if not isinstance(metadata, Mapping):
        return None
    for key in ("workflow_dispatch", "workflow_backtest"):
        section = metadata.get(key)
        if not isinstance(section, Mapping):
            continue
        value = section.get("task_run_id") or section.get("workflow_run_id")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _safe_failure_code(value: Any) -> str | None:
    code = str(value or "").strip().lower()
    return code if code in ALLOWED_FAILURE_CODES else None


def _duration_ms(started_at: Any, finished_at: Any) -> float:
    started = _timestamp(started_at)
    finished = _timestamp(finished_at)
    if started is None or finished is None:
        return 0.0
    return round(max(0.0, (finished - started) * 1000.0), 3)


def _timestamp(value: Any) -> float | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _sha256_json(value: Mapping[str, Any]) -> str:
    serialized = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return _sha256_text(serialized)


def _sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_identities(raw: str) -> tuple[LoadIdentity, ...]:
    try:
        values = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("load identities JSON is invalid") from exc
    if not isinstance(values, list) or len(values) != 15:
        raise ValueError("exactly 15 dedicated temporary load identities are required")
    identities: list[LoadIdentity] = []
    for index, value in enumerate(values):
        if not isinstance(value, Mapping):
            raise ValueError("each load identity must be an object")
        label = str(value.get("label") or "")
        email = str(value.get("email") or "")
        password = str(value.get("password") or "")
        if label != f"public-alpha-load-{index + 1:02d}":
            raise ValueError("load identity labels must use the locked dedicated names")
        if not email or not password or value.get("temporary") is not True:
            raise ValueError("load identities must be explicit temporary credentials")
        identities.append(LoadIdentity(label=label, email=email, password=password))
    return tuple(identities)


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def _repo_root() -> Path:
    return REPO_ROOT


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the locked public-alpha Render capacity envelope."
    )
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=600.0)
    parser.add_argument("--poll-seconds", type=float, default=0.25)
    return parser.parse_args(argv)


def _config_from_env(args: argparse.Namespace) -> HarnessConfig:
    repo_root = _repo_root()
    identities = _parse_identities(
        _required_env("ARGUS_PUBLIC_ALPHA_LOAD_IDENTITIES_JSON")
    )
    return HarnessConfig(
        repo_root=repo_root,
        output_dir=args.output_dir or default_output_dir(repo_root),
        api_url=_required_env("ARGUS_PUBLIC_ALPHA_API_URL").rstrip("/"),
        app_url=_required_env("ARGUS_PUBLIC_ALPHA_APP_URL").rstrip("/"),
        render_api_key=_required_env("RENDER_API_KEY"),
        supabase_url=_required_env("ARGUS_PUBLIC_ALPHA_SUPABASE_URL"),
        supabase_service_role_key=_required_env(
            "ARGUS_PUBLIC_ALPHA_SUPABASE_SERVICE_ROLE_KEY"
        ),
        candidate_sha=_required_env("ARGUS_PUBLIC_ALPHA_CANDIDATE_SHA"),
        workflow_task=os.getenv(
            "ARGUS_BACKTEST_WORKFLOW_TASK",
            "argus-backtests/run_backtest_job",
        ).strip(),
        identities=identities,
        timeout_seconds=max(30.0, float(args.timeout_seconds)),
        poll_seconds=max(0.05, float(args.poll_seconds)),
        prompt=os.getenv("ARGUS_PUBLIC_ALPHA_LOAD_PROMPT", DEFAULT_PROMPT),
    )


def main(argv: list[str] | None = None) -> int:
    repo_root = _repo_root()
    load_dotenv(repo_root / ".env", override=False)
    try:
        config = _config_from_env(_parse_args(argv or sys.argv[1:]))
        report = run_harness(config)
        output = write_report(report=report, output_dir=config.output_dir)
        logger.info(
            "Public-alpha Render capacity artifact written",
            artifact_path=str(output["json"]),
        )
        return 0
    except Exception as exc:
        logger.error(
            "Public-alpha Render capacity harness failed",
            failure_code="capacity_harness_failed",
            failure_type=type(exc).__name__,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
