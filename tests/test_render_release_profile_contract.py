from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import yaml

from tests.test_environment_scripts import (
    _real_workflow_api_env_payload,
    _render_env_payload,
    _run_render_release_audit,
    _workflow_env_payload,
)

ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_render_config_audit_uses_the_checked_in_release_profile() -> None:
    source = _source(".github/render-env-sync.sh")

    assert "private-alpha-release-profile.py" in source
    assert "env-pairs" in source
    assert "required-present" in source
    assert "release_profile_hash=" in source
    assert "release_profile_status=ready" in source


def test_warmup_passes_through_release_profile_proof() -> None:
    source = _source(".github/warmup-render.sh")

    assert "release_profile_hash" in source
    assert "release_profile_status=ready" in source


def test_shared_maintenance_is_a_first_class_render_release_surface() -> None:
    render_config = yaml.safe_load(_source("render.yaml"))
    env_contract = _source(".github/argus-env.sh")
    env_sync = _source(".github/render-env-sync.sh")
    cron = next(
        service
        for service in render_config["services"]
        if service["name"] == "argus-maintenance"
    )

    assert cron["type"] == "cron"
    assert cron["schedule"] == "*/15 * * * *"
    assert cron["startCommand"] == (
        "poetry run python scripts/ops/scheduled_maintenance.py"
    )
    assert "ARGUS_RENDER_CRON_ENV" in env_contract
    assert "ARGUS_RENDER_MAINTENANCE_SERVICE_NAME" in env_contract
    assert "cron-deploy-status" in env_sync
    assert (ROOT / "scripts" / "ops" / "scheduled_maintenance.py").is_file()


def test_release_docs_name_all_four_live_surfaces_and_the_shared_entry_point() -> None:
    runbook = _source("docs/PRIVATE_LAUNCH_RUNBOOK.md")
    architecture = _source("docs/ARCHITECTURE.md")
    data_model = _source("docs/DATA_MODEL.md")
    release_contract = _source("docs/specs/private-alpha-ci-cd-sota.md")
    integrity_contract = _source(
        "docs/specs/private-alpha-release-integrity-contract.md"
    )
    manifest = _source("docs/release-manifests/TEMPLATE.md")

    for service in (
        "argus-api",
        "argus-app",
        "argus-backtests",
        "argus-maintenance",
    ):
        assert service in runbook
        assert service in release_contract
        assert service in manifest
    for source in (
        runbook,
        architecture,
        data_model,
        release_contract,
        integrity_contract,
        manifest,
    ):
        assert "argus-maintenance" in source
    assert "scripts/ops/scheduled_maintenance.py" in runbook
    assert "cron-deploy-status" in runbook
    assert "checked-in cron declaration is not hosted proof" in runbook
    assert "Hosted enforcement starts only after release" in data_model


def test_release_contract_enables_checks_passing_autodeploy_for_all_four() -> None:
    profile = json.loads(_source(".github/private-alpha-release-profile.json"))
    render_config = yaml.safe_load(_source("render.yaml"))
    render_by_name = {service["name"]: service for service in render_config["services"]}
    runbook = _source("docs/PRIVATE_LAUNCH_RUNBOOK.md")

    for surface in ("api", "web", "workflow", "cron"):
        assert profile["services"][surface]["auto_deploy_trigger"] == "checksPass"
    assert render_by_name["argus-api"]["autoDeployTrigger"] == "checksPass"
    assert render_by_name["argus-app"]["autoDeployTrigger"] == "checksPass"
    assert render_by_name["argus-maintenance"]["autoDeployTrigger"] == "checksPass"
    assert "argus-backtests" not in render_by_name
    assert "checksPass" in runbook
    assert "argus-api" in runbook
    assert "argus-app" in runbook
    assert "argus-backtests" in runbook


def test_workflow_version_status_derives_proof_from_ready_version(
    tmp_path: Path,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_render = bin_dir / "render"
    fake_render.write_text(
        "#!/bin/bash\n"
        "printf '%s' '[{\"createdAt\":\"2026-08-12T15:00:00Z\","
        "\"id\":\"wfv-current\",\"name\":\"d67cef9\","
        "\"status\":\"ready\",\"workflowId\":\"wfl-test\"}]'\n",
        encoding="utf-8",
    )
    fake_render.chmod(0o755)
    fake_curl = bin_dir / "curl"
    fake_curl.write_text(
        "#!/bin/bash\n"
        "printf '%s' '[{\"envVar\":{\"key\":"
        "\"ARGUS_RENDER_WORKFLOW_RELEASE_COMMIT\",\"value\":\"stale000\"}},"
        "{\"envVar\":{\"key\":\"ARGUS_RENDER_WORKFLOW_RELEASE_VERSION_ID\","
        "\"value\":\"wfv-stale\"}}]'\n",
        encoding="utf-8",
    )
    fake_curl.chmod(0o755)
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "RENDER_API_KEY": "fake-render-token",
            "ARGUS_RENDER_WORKFLOW_SERVICE_ID": "wfl-test",
        }
    )

    result = subprocess.run(
        [str(ROOT / ".github" / "render-env-sync.sh"), "workflow-version-status"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "workflow_version_id=wfv-current" in result.stdout
    assert "status=ready" in result.stdout
    assert "commit=d67cef9" in result.stdout
    assert "stale000" not in result.stdout
    assert "expected_workflow_version_id" not in result.stdout


def test_render_env_sync_audit_fails_when_one_autodeploy_surface_is_off(
    tmp_path: Path,
) -> None:
    result = _run_render_release_audit(
        tmp_path,
        expect_mode="real-workflow",
        api_env_json=_real_workflow_api_env_payload(),
        web_env_json=_render_env_payload("argus-app"),
        workflow_env_json=_workflow_env_payload(),
        workflow_service_json=json.dumps({"autoDeployTrigger": "off"}),
    )

    assert result.returncode == 1
    assert (
        "drift argus-backtests:autoDeployTrigger "
        "expected=checksPass actual=off" in result.stdout
    )
    assert "autodeploy_status=drift" in result.stdout
    assert "status=drift" in result.stdout


def test_render_env_sync_audit_compares_the_transition_cors_allowlist(
    tmp_path: Path,
) -> None:
    result = _run_render_release_audit(
        tmp_path,
        expect_mode="real-workflow",
        api_env_json=_render_env_payload(
            "argus-api",
            overrides={
                "ARGUS_BACKTEST_JOBS_SHADOW_ENABLED": "true",
                "ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED": "true",
                "ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED": "true",
                "RENDER_API_KEY": "fake-render-token",
                "ARGUS_CORS_ALLOW_ORIGINS": "https://argus-app-suz5.onrender.com",
            },
        ),
        web_env_json=_render_env_payload("argus-app"),
        workflow_env_json=_workflow_env_payload(),
    )

    assert result.returncode == 1
    assert "drift argus-api:ARGUS_CORS_ALLOW_ORIGINS" in result.stdout
    assert "status=drift" in result.stdout
