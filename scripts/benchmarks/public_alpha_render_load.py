#!/usr/bin/env python
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from collections import Counter
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
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

try:
    from scripts.benchmarks.public_alpha_render_load_auth import (
        LoadIdentity,
    )
    from scripts.benchmarks.public_alpha_render_load_auth import (
        cleanup_temporary_identities as _cleanup_temporary_identities,
    )
    from scripts.benchmarks.public_alpha_render_load_auth import (
        create_service_role_session_client as _create_service_role_session_client,
    )
    from scripts.benchmarks.public_alpha_render_load_auth import (
        create_temporary_identities as _create_temporary_identities_impl,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from public_alpha_render_load_auth import (
        LoadIdentity,
    )
    from public_alpha_render_load_auth import (
        cleanup_temporary_identities as _cleanup_temporary_identities,
    )
    from public_alpha_render_load_auth import (
        create_service_role_session_client as _create_service_role_session_client,
    )
    from public_alpha_render_load_auth import (
        create_temporary_identities as _create_temporary_identities_impl,
    )

try:
    from scripts.benchmarks.public_alpha_render_load_evidence import (
        ALLOWED_FAILURE_CODES,
        CASE_ADMISSIONS,
        CASE_MANIFEST,
        LIMITS,
        SCHEMA_VERSION,
        build_case_result,
        validate_report,
        write_report,
    )
    from scripts.benchmarks.public_alpha_render_load_evidence import (
        validate_partial_report as _validate_partial_report,
    )
    from scripts.benchmarks.public_alpha_render_load_evidence import (
        write_measured_report as _write_measured_report,
    )
    from scripts.benchmarks.public_alpha_render_load_evidence import (
        write_partial_report as _write_partial_report,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from public_alpha_render_load_evidence import (
        ALLOWED_FAILURE_CODES,
        CASE_ADMISSIONS,
        CASE_MANIFEST,
        LIMITS,
        SCHEMA_VERSION,
        build_case_result,
        validate_report,
        write_report,
    )
    from public_alpha_render_load_evidence import (
        validate_partial_report as _validate_partial_report,
    )
    from public_alpha_render_load_evidence import (
        write_measured_report as _write_measured_report,
    )
    from public_alpha_render_load_evidence import (
        write_partial_report as _write_partial_report,
    )

__all__ = ["CASE_MANIFEST", "capacity_probe_mode"]

TERMINAL_JOB_STATUSES = {"succeeded", "failed", "canceled", "expired"}
TERMINAL_TASK_STATUSES = {
    "completed",
    "succeeded",
    "failed",
    "canceled",
    "cancelled",
    "expired",
}
DEFAULT_PROMPT = (
    "Test an equal-weight AAPL and MSFT buy-and-hold strategy from "
    "January 1, 2025 through June 5, 2026 with 10,000 dollars"
)


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


class CapacityEnvelopeStop(RuntimeError):
    def __init__(
        self,
        *,
        case_id: str,
        reason: str,
        observed_capacity: dict[str, int],
    ) -> None:
        super().__init__(reason)
        self.case_id = case_id
        self.reason = reason
        self.observed_capacity = dict(observed_capacity)


def default_output_dir(repo_root: Path) -> Path:
    return repo_root / "temp" / "benchmarks" / "public-alpha-render-load"


def run_harness(config: HarnessConfig) -> dict[str, Any]:
    service_client = _service_role_client(config)
    created_user_ids: list[str] = []
    load_clients: list[httpx.Client] = []
    cases: list[dict[str, Any]] = []
    active_case = "identity_setup"
    failing_case: dict[str, Any] | None = None
    partial_report: dict[str, Any] | None = None
    partial_write_error: Exception | None = None
    measured_path: Path | None = None
    try:
        _create_temporary_identities(
            config=config,
            client=service_client,
            user_ids=created_user_ids,
        )
        runtimes: list[httpx.Client] = []
        for identity in config.identities:
            runtime = _create_service_role_session_client(
                config,
                service_client,
                identity,
            )
            runtimes.append(runtime)
            load_clients.append(runtime)

        active_case = "idle_one"
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

        active_case = "global_five"
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

        active_case = "same_user_one_running_two_queued"
        same_user = []
        for _ in range(3):
            runtime = _create_service_role_session_client(
                config,
                service_client,
                config.identities[0],
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

        active_case = "global_five_running_ten_queued"
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

        active_case = "invalid_envelope_retry"
        cases.append(
            _run_probe_case(
                config=config,
                service_client=service_client,
                seed_job=seed_job,
                case_id="invalid_envelope_retry",
                mode="invalid_envelope",
            )
        )
        active_case = "upstream_transient_retry"
        cases.append(
            _run_probe_case(
                config=config,
                service_client=service_client,
                seed_job=seed_job,
                case_id="upstream_transient_retry",
                mode="upstream_transient_once",
            )
        )
        measured_path = _write_measured_report(
            report=_build_measured_report(
                config=config,
                cases=cases,
                cleanup=_pending_cleanup(config, created_user_ids),
            ),
            output_dir=config.output_dir,
        )
    except CapacityEnvelopeStop as exc:
        failing_case = {
            "case_id": exc.case_id,
            "status": "failed",
            "observed_capacity": exc.observed_capacity,
            "stop_reason": exc.reason,
        }
    except Exception as exc:
        failing_case = {
            "case_id": active_case,
            "status": "failed",
            "observed_capacity": {},
            "stop_reason": _stable_stop_reason(exc),
        }
    finally:
        if failing_case is not None:
            partial_report = _build_partial_report(
                config,
                completed_cases=cases,
                failing_case=failing_case,
                cleanup=_pending_cleanup(config, created_user_ids),
            )
            try:
                _write_partial_report(
                    partial_report,
                    config.output_dir / "public-alpha-render-load.partial.json",
                )
            except Exception as exc:
                partial_write_error = exc
        for client in load_clients:
            try:
                client.close()
            except Exception:
                logger.error(
                    "Public-alpha load session close failed",
                    failure_code="session_close_failed",
                )
        cleanup = (
            _cleanup_temporary_identities(
                config=config,
                client=service_client,
                user_ids=created_user_ids,
            )
            if created_user_ids
            else _empty_cleanup()
        )
        service_client.close()
        if partial_write_error is not None:
            raise partial_write_error

    if partial_report is not None:
        partial_report["cleanup"] = cleanup
        _write_partial_report(
            partial_report,
            config.output_dir / "public-alpha-render-load.partial.json",
        )
        return partial_report

    if cleanup.get("status") != "completed":
        partial_report = _build_partial_report(
            config,
            completed_cases=cases,
            failing_case={
                "case_id": "cleanup",
                "status": "failed",
                "observed_capacity": {},
                "stop_reason": "cleanup_incomplete",
            },
            cleanup=cleanup,
        )
        _write_partial_report(
            partial_report,
            config.output_dir / "public-alpha-render-load.partial.json",
        )
        return partial_report

    report = _build_report(config=config, cases=cases, cleanup=cleanup)
    write_report(report=report, output_dir=config.output_dir)
    if measured_path is not None:
        try:
            measured_path.unlink(missing_ok=True)
        except OSError:
            logger.warning(
                "Public-alpha pre-cleanup checkpoint retained",
                failure_code="checkpoint_cleanup_failed",
            )
    return report


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
            _observe_capacity_sample(case_id, observed, rows)
            if group_index < len(submission_groups) - 1:
                target_running = 1 if case_id.startswith("same_user") else 5
                _wait_for_capacity(
                    config=config,
                    client=service_client,
                    case_id=case_id,
                    job_ids=job_ids,
                    observed=observed,
                    running=target_running,
                    queued=0,
                )
        job_ids = {run.job_id for _, run in submitted}
        if case_id == "idle_one":
            target = (1, 0)
        elif case_id == "global_five":
            target = (5, 0)
        elif case_id == "same_user_one_running_two_queued":
            target = (1, 2)
        elif case_id == "global_five_running_ten_queued":
            target = (5, 10)
        else:
            target = None
        if target is not None:
            if (
                observed.get("running"),
                observed.get("queued"),
            ) != target:
                _wait_for_capacity(
                    config=config,
                    client=service_client,
                    case_id=case_id,
                    job_ids=job_ids,
                    observed=observed,
                    running=target[0],
                    queued=target[1],
                )
        poll_futures = [
            pool.submit(_poll_submitted_run, config=config, prepared=item, run=run)
            for item, run in submitted
        ]
        while not all(future.done() for future in poll_futures):
            rows = _fetch_jobs(service_client, job_ids)
            _observe_capacity_sample(case_id, observed, rows)
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
    _observe_capacity_sample(case_id, observed, rows)
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
    case_id: str,
    job_ids: set[str],
    observed: dict[str, int],
    running: int,
    queued: int,
) -> None:
    deadline = time.monotonic() + config.timeout_seconds
    best_sample = _normalized_capacity_sample(observed)
    while True:
        rows = _fetch_jobs(client, job_ids)
        sample = _capacity_sample(rows)
        _enforce_capacity_bounds(case_id, sample)
        if _capacity_rank(sample) > _capacity_rank(best_sample):
            best_sample = sample
        if sample["running"] == running and sample["queued"] == queued:
            observed.clear()
            observed.update({"running": running, "queued": queued})
            return
        if any(str(row.get("status") or "") in TERMINAL_JOB_STATUSES for row in rows):
            raise CapacityEnvelopeStop(
                case_id=case_id,
                reason="capacity_peak_not_reached",
                observed_capacity=best_sample,
            )
        if time.monotonic() >= deadline:
            raise CapacityEnvelopeStop(
                case_id=case_id,
                reason="capacity_peak_timeout",
                observed_capacity=best_sample,
            )
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
    _create_temporary_identities_impl(
        config=config,
        client=client,
        user_ids=user_ids,
        source=CAPACITY_LOAD_SOURCE,
    )


def _service_role_client(config: HarnessConfig) -> httpx.Client:
    return httpx.Client(
        base_url=config.supabase_url.rstrip("/"),
        headers={
            "apikey": config.supabase_service_role_key,
            "Authorization": f"Bearer {config.supabase_service_role_key}",
        },
        timeout=httpx.Timeout(config.timeout_seconds, connect=20.0),
    )


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


def _capacity_sample(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(row.get("status") or "") for row in rows)
    user_counts: dict[str, Counter[str]] = {}
    for row in rows:
        user_ref = str(row.get("user_id") or "")
        per_user = user_counts.setdefault(user_ref, Counter())
        per_user[str(row.get("status") or "")] += 1
    return {
        "running": counts["running"],
        "queued": counts["queued"],
        "max_user_running": max(
            (counts["running"] for counts in user_counts.values()),
            default=0,
        ),
        "max_user_queued": max(
            (counts["queued"] for counts in user_counts.values()),
            default=0,
        ),
    }


def _observe_capacity_sample(
    case_id: str,
    observed: dict[str, int],
    rows: list[dict[str, Any]],
) -> dict[str, int]:
    sample = _capacity_sample(rows)
    _enforce_capacity_bounds(case_id, sample)
    expected = {
        "idle_one": (1, 0),
        "global_five": (5, 0),
        "same_user_one_running_two_queued": (1, 2),
        "global_five_running_ten_queued": (5, 10),
    }.get(case_id)
    if expected == (sample["running"], sample["queued"]):
        observed.clear()
        observed.update({"running": expected[0], "queued": expected[1]})
    elif _capacity_rank(sample) > _capacity_rank(observed):
        observed.clear()
        observed.update(sample)
    return sample


def _normalized_capacity_sample(sample: Mapping[str, int]) -> dict[str, int]:
    return {
        "running": int(sample.get("running", 0)),
        "queued": int(sample.get("queued", 0)),
        "max_user_running": int(sample.get("max_user_running", 0)),
        "max_user_queued": int(sample.get("max_user_queued", 0)),
    }


def _capacity_rank(sample: Mapping[str, int]) -> tuple[int, int, int]:
    running = int(sample.get("running", 0))
    queued = int(sample.get("queued", 0))
    return running + queued, running, queued


def _enforce_capacity_bounds(
    case_id: str,
    sample: dict[str, int],
) -> None:
    checks = (
        ("global_running_exceeded", "running", LIMITS["global_running"]),
        ("global_queued_exceeded", "queued", LIMITS["global_queued"]),
        ("same_user_running_exceeded", "max_user_running", LIMITS["user_running"]),
        ("same_user_queued_exceeded", "max_user_queued", LIMITS["user_queued"]),
    )
    for reason, field, limit in checks:
        if sample[field] > limit:
            raise CapacityEnvelopeStop(
                case_id=case_id,
                reason=reason,
                observed_capacity=sample,
            )


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
        "status": "succeeded",
        "completeness": "complete",
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


def _build_measured_report(
    *,
    config: HarnessConfig,
    cases: list[dict[str, Any]],
    cleanup: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "measured",
        "completeness": "complete_measurements_pending_cleanup",
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


def _build_partial_report(
    config: HarnessConfig,
    *,
    completed_cases: list[dict[str, Any]],
    failing_case: dict[str, Any],
    cleanup: dict[str, Any],
) -> dict[str, Any]:
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "failed",
        "completeness": "partial",
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
        "completed_cases": list(completed_cases),
        "failing_case": dict(failing_case),
        "cleanup": cleanup,
    }
    _validate_partial_report(report)
    return report


def _pending_cleanup(
    config: HarnessConfig,
    user_ids: list[str],
) -> dict[str, Any]:
    return {
        "status": "pending",
        "auth": {
            "targets": len(user_ids),
            "deleted": 0,
            "already_absent": 0,
            "failed": 0,
        },
        "allowlist": {
            "targets": len(config.identities) if user_ids else 0,
            "completed": 0,
            "failed": 0,
        },
    }


def _empty_cleanup() -> dict[str, Any]:
    return {
        "status": "completed",
        "auth": {
            "targets": 0,
            "deleted": 0,
            "already_absent": 0,
            "failed": 0,
        },
        "allowlist": {"targets": 0, "completed": 0, "failed": 0},
    }


def _stable_stop_reason(exc: Exception) -> str:
    if isinstance(exc, ValueError) and "timestamp" in str(exc).lower():
        return "measurement_timestamp_invalid"
    return "harness_case_failed"


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
        raise ValueError("required measurement timestamp is missing or malformed")
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
        if label != f"public-alpha-load-{index + 1:02d}":
            raise ValueError("load identity labels must use the locked dedicated names")
        if not email or value.get("temporary") is not True:
            raise ValueError("load identities must be explicit temporary users")
        identities.append(LoadIdentity(label=label, email=email))
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
        config = _config_from_env(
            _parse_args(argv if argv is not None else sys.argv[1:])
        )
        report = run_harness(config)
        if report.get("status") != "succeeded":
            logger.error(
                "Public-alpha Render capacity harness stopped",
                failure_code=str(
                    report.get("failing_case", {}).get("stop_reason")
                    or "capacity_harness_failed"
                ),
            )
            return 1
        output = {"json": config.output_dir / "public-alpha-render-load.json"}
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
