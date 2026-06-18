from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "ci.yml"
CANARY_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "private-alpha-canary.yml"
SMOKE_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "private-alpha-smoke.yml"


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


def _canary_workflow() -> dict:
    return yaml.safe_load(CANARY_WORKFLOW_PATH.read_text(encoding="utf-8"))


def _smoke_workflow() -> dict:
    return yaml.safe_load(SMOKE_WORKFLOW_PATH.read_text(encoding="utf-8"))


def test_ci_runs_on_main_codex_and_jules_without_deploying() -> None:
    workflow = _workflow()

    assert not (ROOT / ".github" / "workflows" / "deploy.yml").exists()
    assert workflow["name"] == "CI"
    assert workflow["on"]["push"]["branches"] == ["main", "codex/**", "jules/**"]
    assert workflow["on"]["pull_request"]["branches"] == [
        "main",
        "codex/private-alpha-next",
        "codex/private-alpha-next-jules-intake",
    ]
    assert "deploy" not in workflow["jobs"]


def test_ci_queues_integration_branch_runs_without_canceling_evidence() -> None:
    concurrency = _workflow()["concurrency"]

    assert concurrency["group"] == "${{ github.workflow }}-${{ github.ref }}"
    assert concurrency["cancel-in-progress"] == (
        "${{ github.ref != 'refs/heads/codex/private-alpha-next' && "
        "github.ref != 'refs/heads/codex/private-alpha-next-jules-intake' }}"
    )


def test_ci_has_active_backend_and_frontend_quality_jobs() -> None:
    jobs = _workflow()["jobs"]

    assert {"ownership-gate", "backend-checks", "frontend-checks", "ci"} <= set(jobs)
    assert "mock-demo phase" not in WORKFLOW_PATH.read_text(encoding="utf-8")

    backend_steps = "\n".join(
        str(step.get("run", "")) for step in jobs["backend-checks"]["steps"]
    )
    assert "poetry run ruff check src tests workflows scripts" in backend_steps
    assert "tests/test_environment_scripts.py" in backend_steps
    assert "tests/test_api_import_boundary.py" in backend_steps
    assert "tests/test_render_canary_script.py" in backend_steps
    assert "tests/test_legacy_orchestrator_retirement.py" in backend_steps
    assert "tests/test_chat_backtest_state_machine.py" in backend_steps
    assert "tests/test_openrouter_policy.py" in backend_steps
    assert "tests/agent_runtime/test_execute_recovery.py" in backend_steps
    assert "tests/section3/test_market_data_provider.py" in backend_steps
    assert "--no-cov" in backend_steps

    frontend_steps = "\n".join(
        str(step.get("run", "")) for step in jobs["frontend-checks"]["steps"]
    )
    setup_bun_step = next(
        step
        for step in jobs["frontend-checks"]["steps"]
        if step.get("uses") == "oven-sh/setup-bun@v2"
    )
    assert setup_bun_step["with"]["bun-version"] == "1.3.14"
    assert "bun test" in frontend_steps
    assert "bun run build" in frontend_steps


def test_ci_aggregator_requires_all_active_quality_jobs() -> None:
    jobs = _workflow()["jobs"]

    assert jobs["ci"]["needs"] == [
        "ownership-gate",
        "backend-checks",
        "frontend-checks",
    ]


def test_private_alpha_canary_workflow_is_manual_and_scheduled_only() -> None:
    workflow = _canary_workflow()

    assert workflow["name"] == "Private Alpha Canary"
    assert set(workflow["on"]) == {"workflow_dispatch", "schedule"}
    assert workflow["on"]["schedule"] == [{"cron": "30 14 * * *"}]
    assert workflow["permissions"] == {"contents": "read"}
    assert "deploy" not in workflow["jobs"]


def test_private_alpha_canary_workflow_runs_real_workflow_gate() -> None:
    workflow = _canary_workflow()
    job = workflow["jobs"]["canary"]

    assert job["timeout-minutes"] == 25
    joined_steps = "\n".join(str(step.get("run", "")) for step in job["steps"])
    assert "poetry install --with dev,workflows --no-interaction" in joined_steps
    assert "cd web && bun install --frozen-lockfile" in joined_steps
    assert ".github/local-smoke.sh --expected-sha \"$GITHUB_SHA\"" in joined_steps
    assert joined_steps.index(".github/local-smoke.sh") < joined_steps.index(
        ".github/warmup-render.sh"
    )
    assert ".github/warmup-render.sh --expect-mode real-workflow" in joined_steps
    assert ".github/canary-render.sh" in joined_steps
    assert "ARGUS_WARMUP_EXPECT_MODE: real-workflow" in CANARY_WORKFLOW_PATH.read_text(
        encoding="utf-8"
    )
    assert "POSTHOG" not in CANARY_WORKFLOW_PATH.read_text(encoding="utf-8")


def test_private_alpha_smoke_workflow_runs_local_predeploy_gate() -> None:
    workflow = _smoke_workflow()

    assert workflow["name"] == "Private Alpha Local Smoke"
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["on"]["push"]["branches"] == ["codex/private-alpha-next"]
    assert workflow["on"]["pull_request"]["branches"] == [
        "codex/private-alpha-next",
        "codex/private-alpha-next-jules-intake",
    ]
    assert "deploy" not in workflow["jobs"]

    job = workflow["jobs"]["local-smoke"]
    assert job["timeout-minutes"] == 10
    joined_steps = "\n".join(str(step.get("run", "")) for step in job["steps"])
    assert "poetry install --with dev,workflows --no-interaction" in joined_steps
    assert "cd web && bun install --frozen-lockfile" in joined_steps
    assert ".github/local-smoke.sh --expected-sha \"$GITHUB_SHA\"" in joined_steps
    assert "RENDER_API_KEY" not in SMOKE_WORKFLOW_PATH.read_text(encoding="utf-8")
