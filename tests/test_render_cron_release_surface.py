"""The cron is a release surface, so every release gate must see all four."""

from __future__ import annotations

from pathlib import Path

from tests.test_environment_scripts import (
    _render_env_payload,
    _run_render_release_audit,
    _source,
)

ROOT = Path(__file__).resolve().parents[1]
ENV_CONTRACT = ROOT / ".github" / "argus-env.sh"


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


def _cron_service_block(source: str) -> str:
    return source.split("cron_service_id() {", maxsplit=1)[1].split("\n}", maxsplit=1)[0]


def test_every_release_gate_enumerates_the_cron_alongside_the_other_three() -> None:
    env_sync = _source(".github/render-env-sync.sh")
    canary = _source(".github/canary-render.sh")
    canary_workflow = _source(".github/workflows/private-alpha-canary.yml")
    runbook = _source("docs/PRIVATE_LAUNCH_RUNBOOK.md")
    integrity = _source("docs/specs/private-alpha-release-integrity-contract.md")
    manifest = _source("docs/release-manifests/TEMPLATE.md")

    assert ".github/render-env-sync.sh cron-deploy-status" in env_sync
    assert "print_cron_deploy_status()" in env_sync
    assert "cron-deploy-status)" in env_sync
    assert "cron_env_status=" in env_sync
    assert "cron_env_fingerprint=" in env_sync
    assert "release_profile_allowed_keys cron" in env_sync
    assert 'release_profile_expected_pairs cron "$expected_mode"' in env_sync

    assert '"$SCRIPT_DIR/render-env-sync.sh" cron-deploy-status' in canary
    assert 'fail_canary "deploy_status" "api_cron_deploy_sha_mismatch"' in canary
    assert 'fail_canary "deploy_status" "cron_deploy_not_live"' in canary
    assert ".github/render-env-sync.sh cron-deploy-status" in canary_workflow
    assert "cron_status_unavailable" in canary_workflow
    assert "cron_deploy_not_live" in canary_workflow
    assert "cron_deploy_sha_mismatch" in canary_workflow

    assert ".github/render-env-sync.sh cron-deploy-status" in runbook
    assert "argus-maintenance" in runbook
    assert "All four deployed surfaces" in integrity
    assert "Cron deployed SHA:" in manifest
    assert "cron_env_status:" in manifest

    # The release-discipline reference is an operator-facing topology list, so a
    # stale three-service claim there contradicts every gate fixed above.
    topology = _source("docs/specs/private-alpha-ci-cd-sota.md")
    assert "The stable target topology is four surfaces:" in topology
    assert "`argus-maintenance`: scheduled retention" in topology
    assert "Argus does not need more services at this stage." not in topology


def test_current_promotion_keeps_the_unapplied_cron_absent() -> None:
    runbook = _source("docs/PRIVATE_LAUNCH_RUNBOOK.md")
    promotion = runbook.split("## Before Tester Sessions", maxsplit=1)[1].split(
        "## Signup And Login Verification", maxsplit=1
    )[0]
    maintenance = runbook.split("## Scheduled Maintenance", maxsplit=1)[1].split(
        "## Runtime Tuning Flags", maxsplit=1
    )[0]
    promotion = " ".join(promotion.split())
    maintenance = " ".join(maintenance.split())

    assert "deploy `argus-api`, then `argus-app`" in promotion
    assert "Do not create or deploy `argus-maintenance`" in promotion
    assert "`cron-deploy-status` must report `status=absent`" in promotion
    assert "then `argus-maintenance`" not in promotion

    assert "deliberately absent and is not deployed" in maintenance
    assert "`cron_env_status` must be `absent`" in maintenance
    assert "Promotion deploys it with" not in maintenance


def test_a_failed_cron_lookup_is_never_reported_as_absent() -> None:
    env_sync = _source(".github/render-env-sync.sh")
    canary = _source(".github/canary-render.sh")
    canary_workflow = _source(".github/workflows/private-alpha-canary.yml")

    # `|| true` here would turn any 401 or timeout into the absence exemption.
    assert "|| true" not in _cron_service_block(env_sync)
    assert "CRON_SERVICE_LOOKUP_FAILED=true" in env_sync
    assert "cron_env_status=lookup_failed" in env_sync
    assert "service_lookup_failed" in env_sync
    assert 'fail_canary "deploy_status" "cron_status_unavailable"' in canary
    assert "cron_status_unavailable" in canary_workflow


def test_the_cron_service_id_is_resolved_from_render_not_hardcoded() -> None:
    env_sync = _source(".github/render-env-sync.sh")
    env_contract = ENV_CONTRACT.read_text()

    # An id someone has to remember to paste would make "absent" unfalsifiable.
    assert 'ARGUS_RENDER_MAINTENANCE_SERVICE_NAME="argus-maintenance"' in env_contract
    assert "cron_service_id()" in env_sync
    assert "type=cron_job" in env_sync
    assert "srv-" not in _cron_service_block(env_sync)


def test_a_deployed_cron_is_audited_like_every_other_surface(tmp_path: Path) -> None:
    result = _run_render_release_audit(
        tmp_path,
        api_env_json=_safe_off_api_env(),
        web_env_json=_render_env_payload("argus-app"),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "cron_env_status=ready" in result.stdout
    assert "ok argus-maintenance:ARGUS_PERSISTENCE_MODE=supabase" in result.stdout


def test_a_cron_with_a_missing_secret_fails_the_release_config_audit(
    tmp_path: Path,
) -> None:
    result = _run_render_release_audit(
        tmp_path,
        api_env_json=_safe_off_api_env(),
        web_env_json=_render_env_payload("argus-app"),
        cron_env_json=_render_env_payload(
            "argus-maintenance", omit={"SUPABASE_SERVICE_ROLE_KEY"}
        ),
    )

    assert result.returncode == 1
    assert "cron_env_status=drift" in result.stdout
    assert "status=drift" in result.stdout


def test_a_drifted_cron_value_fails_the_release_config_audit(tmp_path: Path) -> None:
    result = _run_render_release_audit(
        tmp_path,
        api_env_json=_safe_off_api_env(),
        web_env_json=_render_env_payload("argus-app"),
        cron_env_json=_render_env_payload(
            "argus-maintenance", overrides={"ARGUS_PERSISTENCE_MODE": "memory"}
        ),
    )

    assert result.returncode == 1
    assert "cron_env_status=drift" in result.stdout


def test_an_unexpected_cron_key_fails_the_release_config_audit(tmp_path: Path) -> None:
    result = _run_render_release_audit(
        tmp_path,
        api_env_json=_safe_off_api_env(),
        web_env_json=_render_env_payload("argus-app"),
        cron_env_json=_render_env_payload(
            "argus-maintenance", extra={"ARGUS_OPS_TOKEN": "smuggled"}
        ),
    )

    assert result.returncode == 1
    assert "cron_env_status=drift" in result.stdout


def test_an_absent_cron_is_reported_as_absent_not_silently_skipped(
    tmp_path: Path,
) -> None:
    result = _run_render_release_audit(
        tmp_path,
        api_env_json=_safe_off_api_env(),
        web_env_json=_render_env_payload("argus-app"),
        cron_service_id=None,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "cron_env_status=absent" in result.stdout
    assert "cron_env_fingerprint=<absent>" in result.stdout
    assert "cron_env_status=ready" not in result.stdout


def test_a_failed_cron_lookup_fails_the_audit_instead_of_reading_as_absent(
    tmp_path: Path,
) -> None:
    """A 401 or timeout must not buy the absence exemption a stale cron needs."""
    result = _run_render_release_audit(
        tmp_path,
        api_env_json=_safe_off_api_env(),
        web_env_json=_render_env_payload("argus-app"),
        cron_lookup_fails=True,
    )

    assert result.returncode == 1
    assert "cron_env_status=lookup_failed" in result.stdout
    assert "cron_env_fingerprint=<unknown>" in result.stdout
    assert "status=drift" in result.stdout
    assert "cron_env_status=absent" not in result.stdout
    assert "cron_env_status=ready" not in result.stdout
