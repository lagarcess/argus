"""Behavioral release-audit coverage for the shared maintenance cron."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from tests.render_release_test_support import (
    _cron_service_payload,
    _render_env_payload,
    _run_render_release_audit,
)

ROOT = Path(__file__).resolve().parents[1]


def _safe_off_api_env() -> str:
    return _render_env_payload(
        "argus-api",
        overrides={
            "RENDER_API_KEY": "",
            "ARGUS_BACKTEST_JOBS_SHADOW_ENABLED": "false",
            "ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED": "false",
            "ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED": "false",
        },
    )


def _audit(tmp_path: Path, **kwargs):
    return _run_render_release_audit(
        tmp_path,
        api_env_json=_safe_off_api_env(),
        web_env_json=_render_env_payload("argus-app"),
        **kwargs,
    )


def _cron_deploy_status(
    tmp_path: Path,
    *,
    service_present: bool = True,
    service_count: int = 1,
    lookup_fails: bool = False,
) -> subprocess.CompletedProcess[str]:
    github_dir = tmp_path / ".github"
    github_dir.mkdir(parents=True)
    for name in (
        "render-env-sync.sh",
        "argus-env.sh",
        "private-alpha-release-profile.py",
        "private-alpha-release-profile.json",
    ):
        copied = github_dir / name
        shutil.copy(ROOT / ".github" / name, copied)
        copied.chmod(0o755)

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_curl = bin_dir / "curl"
    fake_curl.write_text(
        """#!/bin/bash
case "$*" in
  *type=cron_job*)
    [ -n "$FAKE_CRON_LOOKUP_FAIL" ] && exit 22
    printf "%s" "$FAKE_CRON_LOOKUP_JSON"
    ;;
  *"/services/crn-fake-maintenance/deploys"*)
    printf "%s" "$FAKE_CRON_DEPLOY_JSON"
    ;;
  *) exit 9 ;;
esac
""",
        encoding="utf-8",
    )
    fake_curl.chmod(0o755)

    service_rows = [
        {
            "service": {
                "id": "crn-fake-maintenance" if index == 0 else f"crn-duplicate-{index}",
                "name": "argus-maintenance",
            }
        }
        for index in range(service_count if service_present else 0)
    ]
    deploy_rows = [
        {
            "deploy": {
                "id": "dep-maintenance",
                "status": "live",
                "commit": {"id": "a" * 40},
            }
        }
    ]
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "RENDER_API_KEY": "fake-render-token",
            "FAKE_CRON_LOOKUP_FAIL": "1" if lookup_fails else "",
            "FAKE_CRON_LOOKUP_JSON": json.dumps(service_rows),
            "FAKE_CRON_DEPLOY_JSON": json.dumps(deploy_rows),
        }
    )
    return subprocess.run(
        [str(github_dir / "render-env-sync.sh"), "cron-deploy-status"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_deployed_cron_is_audited_like_every_other_surface(tmp_path: Path) -> None:
    result = _audit(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "cron_config_status=ready" in result.stdout
    assert "ok argus-maintenance:ARGUS_PERSISTENCE_MODE=supabase" in result.stdout
    assert "ok argus-maintenance:autoDeployTrigger=checksPass" in result.stdout
    assert "ok argus-maintenance:runtime=python" in result.stdout
    assert "ok argus-maintenance:schedule=*/15 * * * *" in result.stdout
    assert "ok argus-maintenance:notificationsToSend=failure" in result.stdout
    assert (
        "ok argus-maintenance:startCommand="
        "poetry run python scripts/ops/scheduled_maintenance.py" in result.stdout
    )


def test_cron_deploy_status_reads_the_latest_live_commit(tmp_path: Path) -> None:
    result = _cron_deploy_status(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "service=argus-maintenance" in result.stdout
    assert "status=live" in result.stdout
    assert f"commit={'a' * 40}" in result.stdout


def test_cron_deploy_status_distinguishes_absence_from_lookup_failure(
    tmp_path: Path,
) -> None:
    absent = _cron_deploy_status(tmp_path / "absent", service_present=False)
    failed = _cron_deploy_status(tmp_path / "failed", lookup_fails=True)

    assert absent.returncode == 0
    assert "status=absent" in absent.stdout
    assert failed.returncode == 1
    assert "status=lookup_failed" in failed.stdout


def test_cron_deploy_status_rejects_ambiguous_service_matches(tmp_path: Path) -> None:
    result = _cron_deploy_status(tmp_path, service_count=2)

    assert result.returncode == 1
    assert "status=lookup_failed" in result.stdout
    assert "matched 2 exact services" in result.stderr


def test_cron_missing_a_required_secret_fails_the_audit(tmp_path: Path) -> None:
    result = _audit(
        tmp_path,
        cron_env_json=_render_env_payload(
            "argus-maintenance", omit={"SUPABASE_SERVICE_ROLE_KEY"}
        ),
    )

    assert result.returncode == 1
    assert "cron_config_status=drift" in result.stdout
    assert "status=drift" in result.stdout


def test_cron_value_drift_fails_the_audit(tmp_path: Path) -> None:
    result = _audit(
        tmp_path,
        cron_env_json=_render_env_payload(
            "argus-maintenance", overrides={"ARGUS_PERSISTENCE_MODE": "memory"}
        ),
    )

    assert result.returncode == 1
    assert "cron_config_status=drift" in result.stdout


def test_cron_rejects_an_unexpected_environment_key(tmp_path: Path) -> None:
    result = _audit(
        tmp_path,
        cron_env_json=_render_env_payload(
            "argus-maintenance", extra={"ARGUS_OPS_TOKEN": "unexpected"}
        ),
    )

    assert result.returncode == 1
    assert "cron_config_status=drift" in result.stdout


def test_absent_cron_is_reported_explicitly_before_blueprint_creation(
    tmp_path: Path,
) -> None:
    result = _audit(tmp_path, cron_service_id=None)

    assert result.returncode == 1
    assert "cron_config_status=absent" in result.stdout
    assert "cron_config_fingerprint=<absent>" in result.stdout
    assert "cron_config_status=ready" not in result.stdout
    assert "drift argus-maintenance:service_absent" in result.stdout
    assert "status=drift" in result.stdout


def test_failed_cron_lookup_is_not_misreported_as_absence(tmp_path: Path) -> None:
    result = _audit(tmp_path, cron_lookup_fails=True)

    assert result.returncode == 1
    assert "cron_config_status=lookup_failed" in result.stdout
    assert "cron_config_fingerprint=<unknown>" in result.stdout
    assert "cron_config_status=absent" not in result.stdout
    assert "status=drift" in result.stdout


def test_cron_schedule_drift_fails_the_audit(tmp_path: Path) -> None:
    result = _audit(
        tmp_path,
        cron_service_json=_cron_service_payload(schedule="0 * * * *"),
    )

    assert result.returncode == 1
    assert (
        "drift argus-maintenance:schedule "
        "expected=*/15 * * * * actual=0 * * * *" in result.stdout
    )
    assert "cron_config_status=drift" in result.stdout


def test_cron_entry_point_drift_fails_the_audit(tmp_path: Path) -> None:
    result = _audit(
        tmp_path,
        cron_service_json=_cron_service_payload(
            start_command="poetry run python scripts/ops/research_cleanup.py"
        ),
    )

    assert result.returncode == 1
    assert "drift argus-maintenance:startCommand" in result.stdout
    assert "scripts/ops/scheduled_maintenance.py" in result.stdout
    assert "cron_config_status=drift" in result.stdout


def test_cron_autodeploy_drift_fails_the_audit(tmp_path: Path) -> None:
    result = _audit(
        tmp_path,
        cron_service_json=_cron_service_payload(auto_deploy_trigger="off"),
    )

    assert result.returncode == 1
    assert (
        "drift argus-maintenance:autoDeployTrigger "
        "expected=checksPass actual=off" in result.stdout
    )
    assert "autodeploy_status=drift" in result.stdout


def test_cron_failure_notification_drift_fails_the_audit(tmp_path: Path) -> None:
    result = _audit(
        tmp_path,
        cron_notification_json=json.dumps(
            {
                "serviceId": "crn-fake-maintenance",
                "notificationsToSend": "none",
                "previewNotificationsEnabled": "default",
            }
        ),
    )

    assert result.returncode == 1
    assert (
        "drift argus-maintenance:notificationsToSend "
        "expected=failure actual=none" in result.stdout
    )
    assert "cron_config_status=drift" in result.stdout


def test_cron_notification_lookup_failure_fails_the_audit(tmp_path: Path) -> None:
    result = _audit(tmp_path, cron_notification_lookup_fails=True)

    assert result.returncode == 1
    assert "drift argus-maintenance:notification_lookup_failed" in result.stdout
    assert "cron_config_status=drift" in result.stdout
    assert "status=drift" in result.stdout
