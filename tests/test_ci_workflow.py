from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "ci.yml"
CANARY_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "private-alpha-canary.yml"
SMOKE_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "private-alpha-smoke.yml"
AGENT_RUNTIME_WORKFLOW_PATH = (
    ROOT / ".github" / "workflows" / "agent-runtime-regression.yml"
)
RUNBOOK_PATH = ROOT / "docs" / "PRIVATE_LAUNCH_RUNBOOK.md"


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


def _canary_workflow() -> dict:
    return yaml.safe_load(CANARY_WORKFLOW_PATH.read_text(encoding="utf-8"))


def _smoke_workflow() -> dict:
    return yaml.safe_load(SMOKE_WORKFLOW_PATH.read_text(encoding="utf-8"))


def _agent_runtime_workflow() -> dict:
    return yaml.safe_load(AGENT_RUNTIME_WORKFLOW_PATH.read_text(encoding="utf-8"))


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
    assert "poetry run pytest tests -q --no-cov" in backend_steps


def test_backend_checks_gates_the_suite_by_directory() -> None:
    """New test files must be gated without editing this workflow.

    A curated file list drops new tests silently, so the backend suite step
    runs `tests` as a directory and must never enumerate individual files.
    """
    jobs = _workflow()["jobs"]
    backend_steps = "\n".join(
        str(step.get("run", "")) for step in jobs["backend-checks"]["steps"]
    )

    assert re.search(r"pytest\s+tests\s", backend_steps)
    assert "tests/test_" not in backend_steps
    assert "tests/agent_runtime/" not in backend_steps
    assert "tests/section3/" not in backend_steps

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


def test_ci_runs_guest_release_gates_with_disposable_local_supabase() -> None:
    jobs = _workflow()["jobs"]
    guest_job = jobs["guest-release-gates"]
    joined_steps = "\n".join(str(step.get("run", "")) for step in guest_job["steps"])
    uses_steps = {
        str(step.get("uses", "")): step for step in guest_job["steps"] if step.get("uses")
    }

    assert "supabase/setup-cli@v1" in uses_steps
    assert uses_steps["supabase/setup-cli@v1"]["with"]["version"] == "2.109.0"
    assert "supabase start" in joined_steps
    assert "supabase db reset" in joined_steps
    assert "ARGUS_DISPOSABLE_DATABASE_URL" in joined_steps
    assert "ARGUS_LOCAL_SUPABASE_URL" in joined_steps
    assert "ARGUS_LOCAL_SUPABASE_ANON_KEY" in joined_steps
    assert "ARGUS_LOCAL_SUPABASE_SERVICE_ROLE_KEY" in joined_steps
    assert "tests/evals/test_chat_runtime_trajectory_harness.py" in joined_steps
    # Glob, not a hand-list: a new _postgres proof must be gated without
    # editing the workflow. The hand-list was how uncovered tables shipped.
    assert "tests/test_*_postgres.py" in joined_steps
    assert "tests/test_guest_auth_local_supabase.py" in joined_steps
    assert "scripts/qa/assert_pytest_gate.py" in joined_steps
    assert guest_job["env"]["OPENROUTER_API_KEY"] == ""
    assert guest_job["env"]["ALPACA_API_KEY"] == ""
    assert guest_job["env"]["ALPACA_SECRET_KEY"] == ""
    assert guest_job["env"]["ARGUS_MARKET_DATA_PROVIDER_MODE"] == "synthetic_unit_fixture"
    assert "live_provider" not in joined_steps


def test_ci_aggregator_requires_all_active_quality_jobs() -> None:
    jobs = _workflow()["jobs"]

    assert jobs["ci"]["needs"] == [
        "ownership-gate",
        "backend-checks",
        "frontend-checks",
        "guest-release-gates",
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
    release = workflow["jobs"]["release-coherence"]
    browser = workflow["jobs"]["authenticated-browser-journey"]
    release_steps = "\n".join(str(step.get("run", "")) for step in release["steps"])
    browser_steps = "\n".join(str(step.get("run", "")) for step in browser["steps"])

    assert release["timeout-minutes"] == 30
    assert browser["timeout-minutes"] == 50
    assert "poetry install --with dev,workflows --no-interaction" in release_steps
    assert "poetry install --with dev,workflows --no-interaction" in browser_steps
    assert "cd web && bun install --frozen-lockfile" not in release_steps
    assert "cd web && bun install --frozen-lockfile" in browser_steps
    assert "cli_2.20.0_linux_amd64.zip" in release_steps
    assert "cli_2.20.0_linux_amd64.zip" in browser_steps
    assert (
        '.github/local-smoke.sh --expected-sha "$(git rev-parse HEAD)"' in browser_steps
    )
    assert ".github/canary-render.sh" in release_steps
    assert ".github/canary-render.sh" in browser_steps
    assert "continue-on-error" not in CANARY_WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "ARGUS_WARMUP_EXPECT_MODE: real-workflow" in CANARY_WORKFLOW_PATH.read_text(
        encoding="utf-8"
    )
    assert release["env"]["ARGUS_CANARY_SURFACE"] == "release-coherence"
    assert browser["env"]["ARGUS_CANARY_SURFACE"] == ("authenticated-browser-journey")
    assert "POSTHOG" not in CANARY_WORKFLOW_PATH.read_text(encoding="utf-8")


def test_private_alpha_canary_resolves_the_three_deployed_release_surfaces() -> None:
    workflow = _canary_workflow()
    resolver = (ROOT / ".github" / "canary-resolve-deployed.sh").read_text(
        encoding="utf-8"
    )
    for job in workflow["jobs"].values():
        steps = {step["name"]: step for step in job["steps"]}
        assert steps["Resolve deployed canary release"]["run"] == (
            ".github/canary-resolve-deployed.sh"
        )

    assert '"$SCRIPT_DIR/canary-deployed-sha.py"' in resolver
    assert 'git checkout --detach "$deployed_sha"' in resolver
    assert '"$SCRIPT_DIR/render-env-sync.sh" api-deploy-status' in resolver
    assert '"$SCRIPT_DIR/render-env-sync.sh" web-deploy-status' in resolver
    assert '"$SCRIPT_DIR/render-env-sync.sh" workflow-version-status' in resolver
    assert 'if [ "${GITHUB_EVENT_NAME}" = "schedule" ]; then' in resolver
    assert 'allow_harness_mismatch="true"' in resolver
    assert "cron-deploy-status" not in resolver


def test_private_alpha_canary_workflow_scopes_secrets_to_operational_steps() -> None:
    workflow = _canary_workflow()
    secret_names = {
        "RENDER_API_KEY",
        "ARGUS_OPS_TOKEN",
        "ARGUS_WORKFLOW_DATABASE_URL",
        "ARGUS_CANARY_EMAIL",
        "ARGUS_CANARY_SUPABASE_URL",
        "ARGUS_CANARY_SUPABASE_SERVICE_ROLE_KEY",
    }
    release = workflow["jobs"]["release-coherence"]
    browser = workflow["jobs"]["authenticated-browser-journey"]
    release_secret_names = {
        "RENDER_API_KEY",
        "ARGUS_OPS_TOKEN",
        "ARGUS_WORKFLOW_DATABASE_URL",
        "ARGUS_CANARY_SUPABASE_URL",
        "ARGUS_CANARY_SUPABASE_SERVICE_ROLE_KEY",
    }
    browser_secret_names = {
        "ARGUS_CANARY_EMAIL",
        "ARGUS_CANARY_SUPABASE_URL",
        "ARGUS_CANARY_SUPABASE_SERVICE_ROLE_KEY",
    }

    release_steps = {
        step["name"]: set((step.get("env") or {})) & secret_names
        for step in release["steps"]
    }
    browser_steps = {
        step["name"]: set((step.get("env") or {})) & secret_names
        for step in browser["steps"]
    }
    assert release_steps["Resolve deployed canary release"] == {"RENDER_API_KEY"}
    assert release_steps["Check release-coherence secrets"] == release_secret_names
    assert release_steps["Run direct API signup-denial probe"] == release_secret_names
    assert browser_steps["Resolve deployed canary release"] == {"RENDER_API_KEY"}
    assert browser_steps["Check authenticated-browser secrets"] == browser_secret_names
    assert browser_steps["Run authenticated Spanish browser journey"] == (
        browser_secret_names
    )
    assert browser_steps["Run authenticated Spanish browser journey"].isdisjoint(
        {"RENDER_API_KEY", "ARGUS_OPS_TOKEN", "ARGUS_WORKFLOW_DATABASE_URL"}
    )
    for steps in (release_steps, browser_steps):
        for name, secrets in steps.items():
            if name.startswith("Upload") or name.startswith("Require"):
                assert not secrets


def test_private_alpha_canary_workflow_runs_authoritative_spanish_evidence() -> None:
    workflow = _canary_workflow()
    release = workflow["jobs"]["release-coherence"]
    browser = workflow["jobs"]["authenticated-browser-journey"]
    release_steps = {step["name"]: step for step in release["steps"]}
    browser_steps = {step["name"]: step for step in browser["steps"]}
    release_joined = "\n".join(str(step.get("run", "")) for step in release["steps"])
    browser_joined = "\n".join(str(step.get("run", "")) for step in browser["steps"])

    assert "temp/canary-evidence/release-coherence.json" in release_joined
    assert "temp/canary-evidence/release-coherence.exit" in release_joined
    assert "temp/canary-evidence/authenticated-browser.json" in browser_joined
    assert "temp/canary-evidence/authenticated-browser.exit" in browser_joined
    assert "Run direct API signup-denial probe" in release_steps
    assert "Run direct API signup-denial probe" not in browser_steps
    assert "Run authenticated Spanish browser journey" in browser_steps
    assert "Run authenticated Spanish browser journey" not in release_steps
    assert "Install Chromium for the authenticated browser canary" in browser_steps
    workflow_source = CANARY_WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "private-alpha-release-coherence-evidence" in workflow_source
    assert "private-alpha-authenticated-browser-evidence" in workflow_source
    assert "temp/canary-evidence/*" not in workflow_source
    assert release_steps["Upload release-coherence evidence"]["with"]["path"] == (
        "temp/canary-evidence/release-coherence.json\n"
        "temp/canary-evidence/release-coherence.exit\n"
    )
    assert browser_steps["Upload authenticated-browser evidence"]["with"]["path"] == (
        "temp/canary-evidence/authenticated-browser.json\n"
        "temp/canary-evidence/authenticated-browser.exit\n"
    )
    browser_context = browser_steps["Upload browser canary failure context"]
    assert browser_context["with"]["path"] == "web/temp/playwright-results/**"
    assert browser_context["with"]["if-no-files-found"] == "ignore"
    assert "private-alpha-authenticated-browser-context" in workflow_source
    assert "env" not in browser_context
    redaction_gate = browser_steps["Check browser canary context redaction"]
    assert redaction_gate["id"] == "browser_context"
    assert "web/temp/playwright-results/.redacted" in redaction_gate["run"]
    assert "browser_context_upload=skipped_unredacted" in redaction_gate["run"]
    assert browser_context["if"] == (
        "failure() && steps.browser_context.outputs.ready == 'true'"
    )
    names = [step["name"] for step in browser["steps"]]
    redaction_index = names.index("Check browser canary context redaction")
    gate_index = names.index("Require authenticated browser journey")
    browser_context_index = names.index("Upload browser canary failure context")
    assert gate_index < redaction_index < browser_context_index


def test_runbook_documents_schedule_and_dispatch_harness_ownership() -> None:
    runbook = RUNBOOK_PATH.read_text(encoding="utf-8")

    assert ".github/canary-resolve-deployed.sh" in CANARY_WORKFLOW_PATH.read_text(
        encoding="utf-8"
    )
    assert "A schedule checks out `main`" in runbook
    assert "A `workflow_dispatch` keeps the selected branch checked out" in runbook
    assert "scheduled canary" in runbook
    assert "production promotion reaches `main`" in runbook


def test_private_alpha_canary_schedule_uses_main_as_the_deployment_candidate() -> None:
    workflow = _canary_workflow()
    for job in workflow["jobs"].values():
        steps = {step["name"]: step for step in job["steps"]}
        assert steps["Checkout"]["with"]["ref"] == (
            "${{ github.event_name == 'schedule' && 'main' || github.sha }}"
        )
    resolver = (ROOT / ".github" / "canary-resolve-deployed.sh").read_text(
        encoding="utf-8"
    )
    assert "ARGUS_CANARY_SHA=$deployed_sha" in resolver
    assert "ARGUS_CANARY_HARNESS_SHA=$harness_sha" in resolver


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
    assert '.github/local-smoke.sh --expected-sha "$GITHUB_SHA"' in joined_steps
    assert "RENDER_API_KEY" not in SMOKE_WORKFLOW_PATH.read_text(encoding="utf-8")


def test_agent_runtime_regression_workflow_runs_full_runtime_sweep() -> None:
    workflow = _agent_runtime_workflow()

    assert workflow["name"] == "Agent Runtime Regression"
    assert set(workflow["on"]) == {
        "workflow_dispatch",
        "schedule",
        "push",
        "pull_request",
    }
    assert workflow["on"]["schedule"] == [{"cron": "15 9 * * *"}]
    assert workflow["on"]["push"]["branches"] == ["codex/private-alpha-next"]
    assert workflow["on"]["pull_request"]["branches"] == ["codex/private-alpha-next"]
    assert "src/argus/agent_runtime/**" in workflow["on"]["pull_request"]["paths"]
    assert "tests/agent_runtime/**" in workflow["on"]["pull_request"]["paths"]
    assert "tests/test_spine_guardrails.py" in workflow["on"]["pull_request"]["paths"]
    assert workflow["permissions"] == {"contents": "read"}
    assert "deploy" not in workflow["jobs"]

    job = workflow["jobs"]["agent-runtime"]
    assert job["timeout-minutes"] == 25
    assert job["if"] == (
        "github.event.pull_request.draft == false || "
        "github.event_name != 'pull_request'"
    )
    setup_python_step = next(
        step for step in job["steps"] if step.get("uses") == "actions/setup-python@v5"
    )
    assert setup_python_step["with"]["python-version"] == "3.10"
    checkout_steps = [
        step for step in job["steps"] if step.get("uses") == "actions/checkout@v4"
    ]
    assert checkout_steps == [
        {
            "name": "Checkout workflow ref",
            "if": "github.event_name != 'schedule'",
            "uses": "actions/checkout@v4",
        },
        {
            "name": "Checkout private-alpha-next for nightly schedule",
            "if": "github.event_name == 'schedule'",
            "uses": "actions/checkout@v4",
            "with": {"ref": "codex/private-alpha-next"},
        },
    ]

    joined_steps = "\n".join(str(step.get("run", "")) for step in job["steps"])
    assert "poetry install --with dev --no-interaction" in joined_steps
    assert (
        "poetry run pytest tests/agent_runtime tests/test_spine_guardrails.py -q --no-cov"
        in joined_steps
    )
    sweep_step = next(
        step
        for step in job["steps"]
        if step.get("name") == "Run agent_runtime regression sweep"
    )
    assert sweep_step["env"] == {
        "ARGUS_MARKET_DATA_PROVIDER_MODE": "synthetic_unit_fixture"
    }

    runtime_target = ROOT / "tests" / "agent_runtime"
    hidden_regression_file = (
        ROOT / "tests" / "agent_runtime" / "test_conversational_contract_hardening.py"
    )
    assert hidden_regression_file.exists()
    assert hidden_regression_file.is_relative_to(runtime_target)
    assert str(hidden_regression_file.relative_to(ROOT)) not in joined_steps
