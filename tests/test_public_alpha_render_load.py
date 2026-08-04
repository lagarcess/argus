from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
LOAD_SCRIPT = REPO_ROOT / "scripts" / "benchmarks" / "public_alpha_render_load.py"


def _load_module() -> Any:
    assert LOAD_SCRIPT.exists(), "public alpha Render load harness should exist"
    spec = importlib.util.spec_from_file_location(
        "public_alpha_render_load",
        LOAD_SCRIPT,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _case(
    module: Any,
    *,
    case_id: str,
    statuses: list[str],
    retry_attempts: list[int],
) -> dict[str, Any]:
    return module.build_case_result(
        case_id=case_id,
        started_at="2026-07-31T12:00:00+00:00",
        finished_at="2026-07-31T12:01:00+00:00",
        admitted=len(statuses),
        rejected=0,
        wall_times_ms=[1000.0 + index for index, _ in enumerate(statuses)],
        queue_to_start_ms=[100.0 + index for index, _ in enumerate(statuses)],
        start_to_finish_ms=[900.0 for _ in statuses],
        terminal_statuses=statuses,
        task_run_ids=[f"trn-safe-{index}" for index, _ in enumerate(statuses)],
        retry_attempts=retry_attempts,
        failure_codes=[],
        observed_capacity={"running": 0, "queued": 0},
    )


def _valid_cases(module: Any) -> list[dict[str, Any]]:
    cases = []
    for case_id in module.CASE_MANIFEST:
        count = module.CASE_ADMISSIONS[case_id]
        case = _case(
            module,
            case_id=case_id,
            statuses=(
                ["failed"] if case_id == "invalid_envelope_retry" else ["succeeded"]
            )
            * count,
            retry_attempts=([1] * count if case_id.endswith("_retry") else [0] * count),
        )
        case["observed_capacity"] = {
            "idle_one": {"running": 1, "queued": 0},
            "global_five": {"running": 5, "queued": 0},
            "same_user_one_running_two_queued": {"running": 1, "queued": 2},
            "global_five_running_ten_queued": {"running": 5, "queued": 10},
            "invalid_envelope_retry": {"running": 1, "queued": 0},
            "upstream_transient_retry": {"running": 1, "queued": 0},
        }[case_id]
        if case_id == "invalid_envelope_retry":
            case["failure_codes"] = ["invalid_job_contract"]
        elif case_id == "upstream_transient_retry":
            case["failure_codes"] = ["failed_upstream"]
        cases.append(case)
    return cases


def test_default_output_stays_under_temp_capacity_directory() -> None:
    module = _load_module()

    assert module.default_output_dir(REPO_ROOT) == (
        REPO_ROOT / "temp" / "benchmarks" / "public-alpha-render-load"
    )


def test_harness_help_runs_from_the_repository_root() -> None:
    result = subprocess.run(
        ["poetry", "run", "python", str(LOAD_SCRIPT), "--help"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "locked public-alpha Render capacity envelope" in result.stdout
    assert "Traceback" not in result.stderr


def test_exact_locked_capacity_case_manifest_is_stable() -> None:
    module = _load_module()

    assert module.CASE_MANIFEST == (
        "idle_one",
        "global_five",
        "same_user_one_running_two_queued",
        "global_five_running_ten_queued",
        "invalid_envelope_retry",
        "upstream_transient_retry",
    )


def test_case_result_contains_required_measured_fields() -> None:
    module = _load_module()

    case = _case(
        module,
        case_id="global_five",
        statuses=["succeeded"] * 5,
        retry_attempts=[0] * 5,
    )

    assert case == {
        "case_id": "global_five",
        "started_at": "2026-07-31T12:00:00+00:00",
        "finished_at": "2026-07-31T12:01:00+00:00",
        "admitted": 5,
        "rejected": 0,
        "wall_time_ms": {"p50": 1002.0, "p95": 1004.0},
        "queue_to_start_ms": {"p50": 102.0, "p95": 104.0},
        "start_to_finish_ms": {"p50": 900.0, "p95": 900.0},
        "terminal_statuses": {"succeeded": 5},
        "render_task_run_ids": [
            "trn-safe-0",
            "trn-safe-1",
            "trn-safe-2",
            "trn-safe-3",
            "trn-safe-4",
        ],
        "retry_attempts": [0, 0, 0, 0, 0],
        "failure_codes": [],
        "observed_capacity": {"running": 0, "queued": 0},
    }


def test_report_validation_requires_every_locked_case_and_retry_shape() -> None:
    module = _load_module()
    cases = _valid_cases(module)

    report = {
        "schema_version": "argus_public_alpha_render_load/v1",
        "status": "succeeded",
        "completeness": "complete",
        "candidate_sha": "a" * 40,
        "generated_at": "2026-07-31T12:02:00+00:00",
        "api_url": "https://argus.example",
        "app_url": "https://argus-app.example",
        "source": "public_alpha_capacity_load",
        "workflow": {
            "task": "argus-backtests/run_backtest_job",
            "plan": "standard",
            "max_retries": 1,
        },
        "limits": {
            "user_running": 1,
            "user_queued": 2,
            "global_running": 5,
            "global_queued": 10,
        },
        "cases": cases,
        "cleanup": {
            "status": "completed",
            "auth": {
                "targets": 15,
                "deleted": 15,
                "already_absent": 0,
                "failed": 0,
            },
            "allowlist": {"targets": 15, "completed": 15, "failed": 0},
        },
    }

    module.validate_report(report)


def test_report_validation_rejects_raw_identity_and_secret_fields() -> None:
    module = _load_module()
    report = {
        "schema_version": "argus_public_alpha_render_load/v1",
        "status": "succeeded",
        "completeness": "complete",
        "email": "capacity@example.invalid",
        "access_token": "secret-token",
    }

    with pytest.raises(ValueError, match="forbidden artifact field"):
        module.validate_report(report)


def test_write_report_never_serializes_raw_identity_values(tmp_path: Path) -> None:
    module = _load_module()
    report = {
        "schema_version": "argus_public_alpha_render_load/v1",
        "status": "succeeded",
        "completeness": "complete",
        "candidate_sha": "b" * 40,
        "generated_at": "2026-07-31T12:02:00+00:00",
        "api_url": "https://argus.example",
        "app_url": "https://argus-app.example",
        "source": "public_alpha_capacity_load",
        "workflow": {
            "task": "argus-backtests/run_backtest_job",
            "plan": "standard",
            "max_retries": 1,
        },
        "limits": {
            "user_running": 1,
            "user_queued": 2,
            "global_running": 5,
            "global_queued": 10,
        },
        "cases": _valid_cases(module),
        "cleanup": {
            "status": "completed",
            "auth": {
                "targets": 15,
                "deleted": 15,
                "already_absent": 0,
                "failed": 0,
            },
            "allowlist": {"targets": 15, "completed": 15, "failed": 0},
        },
    }

    paths = module.write_report(report=report, output_dir=tmp_path)
    serialized = paths["json"].read_text(encoding="utf-8")

    assert json.loads(serialized)["schema_version"] == (
        "argus_public_alpha_render_load/v1"
    )
    assert "@" not in serialized
    assert "token" not in serialized.lower()
    assert "password" not in serialized.lower()
    assert "conversation_id" not in serialized
    assert "job_id" not in serialized
    assert "user_id" not in serialized


def test_capacity_probe_marker_uses_service_role_metadata_only() -> None:
    module = _load_module()

    assert (
        module.capacity_probe_mode(
            {
                "execution_metadata": {
                    "source": "public_alpha_capacity_load",
                    "ops_authority": "service_role",
                    "capacity_probe": {"mode": "upstream_transient_once"},
                }
            }
        )
        == "upstream_transient_once"
    )
    assert (
        module.capacity_probe_mode(
            {
                "launch_payload": {
                    "source": "public_alpha_capacity_load",
                    "capacity_probe": {"mode": "upstream_transient_once"},
                },
                "execution_metadata": {"source": "api_chat"},
            }
        )
        is None
    )
    assert (
        module.capacity_probe_mode(
            {
                "execution_metadata": {
                    "source": "public_alpha_capacity_load",
                    "capacity_probe": {"mode": "upstream_transient_once"},
                }
            }
        )
        is None
    )
