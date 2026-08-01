from __future__ import annotations

import json
import re
from collections import Counter
from math import ceil
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

from workflows.backtest_job import CAPACITY_LOAD_SOURCE

SCHEMA_VERSION = "argus_public_alpha_render_load/v1"
LOCKED_WORKFLOW_TASK = "argus-backtests/run_backtest_job"
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
ALLOWED_FAILURE_CODES = {
    "backtest_capacity_exceeded",
    "failed_upstream",
    "invalid_job_contract",
    "workflow_task_failed",
    "workflow_task_timeout",
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
    if report.get("status") != "succeeded":
        raise ValueError("successful artifact status must be succeeded")
    if report.get("completeness") != "complete":
        raise ValueError("successful artifact completeness must be complete")
    _validate_complete_measurements(report)
    validate_cleanup(report.get("cleanup"), require_completed=True)


def validate_measured_report(report: Mapping[str, Any]) -> None:
    _reject_forbidden_artifact_data(report)
    if report.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected public-alpha load artifact schema")
    if report.get("status") != "measured":
        raise ValueError("pre-cleanup artifact status must be measured")
    if report.get("completeness") != "complete_measurements_pending_cleanup":
        raise ValueError("pre-cleanup artifact must remain non-final")
    _validate_complete_measurements(report)
    cleanup = report.get("cleanup")
    validate_cleanup(cleanup, require_completed=False)
    if not isinstance(cleanup, Mapping) or cleanup.get("status") != "pending":
        raise ValueError("pre-cleanup artifact requires pending cleanup")
    auth = cleanup["auth"]
    allowlist = cleanup["allowlist"]
    if (
        auth["targets"] != 15
        or auth["deleted"] != 0
        or auth["already_absent"] != 0
        or auth["failed"] != 0
        or allowlist["targets"] != 15
        or allowlist["completed"] != 0
        or allowlist["failed"] != 0
    ):
        raise ValueError("pre-cleanup artifact must precede all cleanup attempts")


def _validate_complete_measurements(report: Mapping[str, Any]) -> None:
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
    _validate_workflow_contract(workflow)
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


def write_measured_report(
    *,
    report: Mapping[str, Any],
    output_dir: Path,
) -> Path:
    validate_measured_report(report)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "public-alpha-render-load.pending.json"
    output_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def write_partial_report(report: Mapping[str, Any], output_path: Path) -> None:
    validate_partial_report(report)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def validate_partial_report(report: Mapping[str, Any]) -> None:
    _reject_forbidden_artifact_data(report)
    if report.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected public-alpha load artifact schema")
    if report.get("status") != "failed" or report.get("completeness") != "partial":
        raise ValueError("partial artifact must be marked failed and partial")
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
    _validate_workflow_contract(workflow)
    if report.get("limits") != LIMITS:
        raise ValueError("capacity limits do not match the locked envelope")
    completed = report.get("completed_cases")
    if not isinstance(completed, list):
        raise ValueError("partial artifact completed_cases must be a list")
    completed_ids: list[str] = []
    for case in completed:
        if not isinstance(case, Mapping):
            raise ValueError("partial artifact completed case must be an object")
        _validate_case(case)
        completed_ids.append(str(case.get("case_id") or ""))
    if tuple(completed_ids) != CASE_MANIFEST[: len(completed_ids)]:
        raise ValueError("partial artifact cases must be a manifest prefix")
    failing = report.get("failing_case")
    if not isinstance(failing, Mapping) or failing.get("status") != "failed":
        raise ValueError("partial artifact requires one failing case")
    failing_case_id = str(failing.get("case_id") or "")
    if failing_case_id not in {"identity_setup", "cleanup", *CASE_MANIFEST}:
        raise ValueError("partial artifact has an unknown failing case")
    stop_reason = str(failing.get("stop_reason") or "")
    if re.fullmatch(r"[a-z][a-z0-9_]{2,63}", stop_reason) is None:
        raise ValueError("partial artifact stop reason must be stable")
    observed = failing.get("observed_capacity")
    if not isinstance(observed, Mapping):
        raise ValueError("partial artifact requires observed capacity")
    if any(not isinstance(value, int) or value < 0 for value in observed.values()):
        raise ValueError("partial artifact capacity values must be non-negative")
    validate_cleanup(report.get("cleanup"), require_completed=False)


def _validate_workflow_contract(workflow: Mapping[str, Any]) -> None:
    if workflow.get("task") != LOCKED_WORKFLOW_TASK:
        raise ValueError("workflow task must use the locked real backtest task")
    if workflow.get("plan") != "standard" or workflow.get("max_retries") != 1:
        raise ValueError("workflow contract must use standard plan and one retry")


def validate_cleanup(value: Any, *, require_completed: bool) -> None:
    if not isinstance(value, Mapping):
        raise ValueError("cleanup evidence must be an object")
    if require_completed and value.get("status") != "completed":
        raise ValueError("successful artifact requires completed cleanup")
    if value.get("status") not in {"pending", "completed", "incomplete"}:
        raise ValueError("cleanup status is invalid")
    auth = value.get("auth")
    allowlist = value.get("allowlist")
    if not isinstance(auth, Mapping) or not isinstance(allowlist, Mapping):
        raise ValueError("cleanup evidence requires auth and allowlist counts")
    for field in ("targets", "deleted", "already_absent", "failed"):
        if not isinstance(auth.get(field), int) or int(auth[field]) < 0:
            raise ValueError("cleanup auth counts must be non-negative integers")
    for field in ("targets", "completed", "failed"):
        if not isinstance(allowlist.get(field), int) or int(allowlist[field]) < 0:
            raise ValueError("cleanup allowlist counts must be non-negative integers")
    if value.get("status") != "pending":
        if (
            auth["deleted"] + auth["already_absent"] + auth["failed"]
            != auth["targets"]
        ):
            raise ValueError("cleanup auth counts do not reconcile")
        if allowlist["completed"] + allowlist["failed"] != allowlist["targets"]:
            raise ValueError("cleanup allowlist counts do not reconcile")
    if require_completed and (auth["failed"] or allowlist["failed"]):
        raise ValueError("successful artifact cannot contain incomplete cleanup")
    if require_completed and (auth["targets"] != 15 or allowlist["targets"] != 15):
        raise ValueError("successful artifact requires all 15 cleanup targets")


def _validate_case(case: Mapping[str, Any]) -> None:
    case_id = str(case.get("case_id") or "")
    if case_id not in CASE_ADMISSIONS:
        raise ValueError("case evidence has an unknown case id")
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
    if required_fields.difference(case):
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
    if (
        case_id == "invalid_envelope_retry"
        and "invalid_job_contract" not in failure_codes
    ):
        raise ValueError("invalid-envelope case lacks its terminal failure code")
    if case_id == "upstream_transient_retry" and "failed_upstream" not in failure_codes:
        raise ValueError("transient case lacks its first-attempt failure code")
    observed = case.get("observed_capacity")
    if not isinstance(observed, Mapping):
        raise ValueError(f"{case_id} observed_capacity must be an object")
    expected_capacity = {
        "idle_one": {"running": 1, "queued": 0},
        "global_five": {"running": 5, "queued": 0},
        "same_user_one_running_two_queued": {"running": 1, "queued": 2},
        "global_five_running_ten_queued": {"running": 5, "queued": 10},
        "invalid_envelope_retry": {"running": 1, "queued": 0},
        "upstream_transient_retry": {"running": 1, "queued": 0},
    }[case_id]
    if {
        "running": observed.get("running"),
        "queued": observed.get("queued"),
    } != expected_capacity:
        raise ValueError(f"{case_id} capacity evidence must match one exact sample")


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
