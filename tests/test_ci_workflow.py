from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "deploy.yml"


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


def test_ci_runs_on_main_and_codex_pushes_without_deploying() -> None:
    workflow = _workflow()

    assert workflow["name"] == "CI"
    assert workflow["on"]["push"]["branches"] == ["main", "codex/**"]
    assert workflow["on"]["pull_request"]["branches"] == ["main"]
    assert "deploy" not in workflow["jobs"]


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
