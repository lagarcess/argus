from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ENV_CONTRACT = ROOT / ".github" / "argus-env.sh"


def _source(path: str) -> str:
    return (ROOT / path).read_text()


def _render_env(service_name: str) -> dict[str, dict[str, str | bool]]:
    render_config = yaml.safe_load(_source("render.yaml"))

    for service in render_config["services"]:
        if service["name"] == service_name:
            return {env["key"]: env for env in service["envVars"]}

    raise AssertionError(f"{service_name} service missing from render.yaml")


def _contract_array(name: str) -> list[str]:
    result = subprocess.run(
        [
            "bash",
            "-c",
            f'source .github/argus-env.sh; printf "%s\\n" "${{{name}[@]}}"',
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.splitlines()


def test_env_example_uses_typed_supabase_postgres_urls() -> None:
    env_example = (ROOT / ".env.example").read_text()

    assert "SUPABASE_POSTGRES_DIRECT_URL=" in env_example
    assert "SUPABASE_POSTGRES_SESSION_POOLER_URL=" in env_example
    assert "SUPABASE_POSTGRES_TRANSACTION_POOLER_URL=" in env_example
    assert "\nDATABASE_URL=" not in env_example
    assert "DATABASE_URL values" not in env_example


def test_qa_script_derives_internal_database_url_from_session_pooler() -> None:
    qa_script = _source(".github/qa.sh")
    env_contract = ENV_CONTRACT.read_text()
    combined = qa_script + "\n" + env_contract

    assert "SUPABASE_POSTGRES_SESSION_POOLER_URL" in env_contract
    assert 'argus_require_env "$name"' in env_contract
    assert 'require_env "DATABASE_URL"' not in combined
    assert 'export DATABASE_URL="$SUPABASE_POSTGRES_SESSION_POOLER_URL"' in env_contract
    assert "SUPABASE_POSTGRES_DIRECT_URL" in combined
    assert "Session Pooler -> internal DATABASE_URL" in qa_script


def test_dev_script_ignores_database_urls_even_when_env_contains_them() -> None:
    dev_script = _source(".github/dev.sh")
    env_contract = ENV_CONTRACT.read_text()
    combined = dev_script + "\n" + env_contract

    assert "unset DATABASE_URL" in env_contract
    assert "SUPABASE_POSTGRES_SESSION_POOLER_URL" in combined
    assert "Database URLs: Ignored" in dev_script


def test_dev_script_disables_disk_market_data_cache_for_stable_memory_qa() -> None:
    dev_script = _source(".github/dev.sh")
    env_contract = ENV_CONTRACT.read_text()

    assert "Synthetic fixtures (no API calls)" in dev_script
    assert "Disk market-data cache: Disabled" in dev_script
    assert "export ENABLE_MARKET_DATA_CACHE=false" in env_contract


def test_dev_and_qa_scripts_source_shared_env_contract() -> None:
    assert ENV_CONTRACT.exists()
    assert 'source "$SCRIPT_DIR/argus-env.sh"' in _source(".github/dev.sh")
    assert 'source "$SCRIPT_DIR/argus-env.sh"' in _source(".github/qa.sh")


def test_shared_env_contract_requires_unset_indirect_env_under_nounset() -> None:
    result = subprocess.run(
        [
            "bash",
            "-c",
            "set -euo pipefail; "
            "source .github/argus-env.sh; "
            "unset OPENROUTER_API_KEY; "
            "argus_require_env OPENROUTER_API_KEY",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "OPENROUTER_API_KEY is required" in result.stdout
    assert "bad substitution" not in result.stderr
    assert "unbound variable" not in result.stderr


def test_render_blueprint_uses_current_env_contract_names_only() -> None:
    render_yaml = _source("render.yaml")
    contract = ENV_CONTRACT.read_text()

    for key in (
        "ARGUS_PERSISTENCE_MODE",
        "POETRY_VERSION",
        "ARGUS_DEV_MEMORY_FALLBACK",
        "ARGUS_MARKET_DATA_PROVIDER_MODE",
        "ARGUS_RUNTIME_EVENT_TIMEOUT_SECONDS",
        "ARGUS_RUNTIME_EVENT_KEEPALIVE_SECONDS",
        "ARGUS_CHECKPOINTER_MODE",
        "ARGUS_MOCK_AUTH",
        "ARGUS_CORS_ALLOW_ORIGINS",
        "ARGUS_BACKTEST_JOBS_SHADOW_ENABLED",
        "ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED",
        "ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED",
        "ARGUS_BACKTEST_WORKFLOW_TASK",
        "ARGUS_BACKTEST_REAL_WORKFLOW_TASK",
        "ARGUS_BACKTEST_JOBS_USER_RUNNING_LIMIT",
        "ARGUS_BACKTEST_JOBS_USER_QUEUED_LIMIT",
        "ARGUS_BACKTEST_JOBS_GLOBAL_RUNNING_LIMIT",
        "ARGUS_BACKTEST_JOBS_GLOBAL_QUEUED_LIMIT",
        "NEXT_PUBLIC_ARGUS_API_URL",
        "NEXT_PUBLIC_MOCK_AUTH",
    ):
        assert key in contract
        assert key in render_yaml

    for legacy_key in (
        "NEXT_PUBLIC_API_URL",
        "NEXT_PUBLIC_MOCK_API",
        "AGENT_MODEL",
        "AGENT_FALLBACK_MODEL",
    ):
        assert legacy_key not in render_yaml


def test_render_workflow_task_slug_is_single_current_default() -> None:
    env_example = _source(".env.example")
    env_contract = ENV_CONTRACT.read_text()
    trigger_proof = _source("workflows/trigger_proof.py")

    assert (
        'ARGUS_BACKTEST_WORKFLOW_TASK_DEFAULT="argus-backtests/workflow_proof"'
        in env_contract
    )
    assert (
        'ARGUS_BACKTEST_REAL_WORKFLOW_TASK_DEFAULT="argus-backtests/run_backtest_job"'
        in env_contract
    )
    assert "ARGUS_BACKTEST_WORKFLOW_TASK=argus-backtests/workflow_proof" in env_example
    assert (
        "ARGUS_BACKTEST_REAL_WORKFLOW_TASK=argus-backtests/run_backtest_job"
        in env_example
    )
    assert (
        "ARGUS_RENDER_WORKFLOW_PROOF_TASK=argus-backtests/workflow_proof" in env_example
    )
    assert 'or "argus-backtests/workflow_proof"' in trigger_proof
    assert "argus-render-workflow-proof" not in env_example
    assert "argus-render-workflow-proof" not in trigger_proof


def test_render_python_builds_use_managed_poetry() -> None:
    render_yaml = _source("render.yaml")
    env_contract = ENV_CONTRACT.read_text()
    env_example = _source(".env.example")

    assert 'ARGUS_RENDER_POETRY_VERSION="2.1.3"' in env_contract
    assert "POETRY_VERSION=2.1.3" in env_example
    assert "pip install poetry" not in render_yaml
    assert "pip install poetry" not in env_contract
    assert (
        'ARGUS_RENDER_API_BUILD_COMMAND="poetry config virtualenvs.create false '
        "&& poetry install --only main --no-interaction\""
    ) in env_contract
    assert (
        'ARGUS_RENDER_API_START_COMMAND="poetry run uvicorn argus.api.main:app '
        "--host 0.0.0.0 --port \\$PORT\""
    ) in env_contract
    assert (
        'ARGUS_RENDER_WORKFLOW_BUILD_COMMAND="poetry config virtualenvs.create false '
        "&& poetry install --only main,workflows --no-interaction\""
    ) in env_contract


def test_env_example_declares_render_api_key_once() -> None:
    env_example = _source(".env.example")

    assert env_example.count("\nRENDER_API_KEY=") == 1
    assert "Reuse the RENDER_API_KEY declared" in env_example


def test_render_blueprint_declares_shared_render_env_contract_vars() -> None:
    assert set(_contract_array("ARGUS_RENDER_API_ENV")) == set(_render_env("argus-api"))
    assert set(_contract_array("ARGUS_RENDER_WEB_ENV")) == set(_render_env("argus-app"))


def test_render_blueprint_syncs_public_supabase_coordinates() -> None:
    api_env = _render_env("argus-api")
    web_env = _render_env("argus-app")

    for env, public_keys in (
        (api_env, ("SUPABASE_URL", "SUPABASE_ANON_KEY")),
        (web_env, ("NEXT_PUBLIC_SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_ANON_KEY")),
    ):
        for key in public_keys:
            assert "value" in env[key]
            assert env[key].get("sync") is not False
            assert "YOUR_" not in str(env[key]["value"])
            assert "your_" not in str(env[key]["value"])


def test_render_blueprint_syncs_non_secret_model_routing() -> None:
    api_env = _render_env("argus-api")

    for key in (
        "ARGUS_UTILITY_MODEL",
        "ARGUS_UTILITY_FALLBACK_MODEL",
        "ARGUS_CHAT_MODEL",
        "ARGUS_CHAT_FALLBACK_MODEL",
        "ARGUS_STRUCTURED_MODEL",
        "ARGUS_STRUCTURED_FALLBACK_MODEL",
        "ARGUS_CONTEXT_MODEL",
        "ARGUS_CONTEXT_FALLBACK_MODEL",
    ):
        assert "value" in api_env[key]
        assert api_env[key].get("sync") is not False
        assert "YOUR_" not in str(api_env[key]["value"])
        assert "your_" not in str(api_env[key]["value"])


def test_render_blueprint_keeps_true_secrets_manual() -> None:
    api_env = _render_env("argus-api")

    for key in (
        "DATABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_JWT_SECRET",
        "RENDER_API_KEY",
        "OPENROUTER_API_KEY",
        "ALPACA_API_KEY",
        "ALPACA_SECRET_KEY",
        "ARGUS_OPS_TOKEN",
    ):
        assert api_env[key] == {"key": key, "sync": False}


def test_workflow_proof_env_contract_is_documented_but_not_blueprinted() -> None:
    env_example = _source(".env.example")
    env_contract = ENV_CONTRACT.read_text()
    render_config = yaml.safe_load(_source("render.yaml"))

    assert "ARGUS_RENDER_WORKFLOW_PROOF_TASK=" in env_example
    assert (
        "ARGUS_WORKFLOW_DATABASE_URL=${SUPABASE_POSTGRES_TRANSACTION_POOLER_URL}"
        in env_example
    )
    assert "ARGUS_WORKFLOW_PROOF_PLAN=" in env_example
    assert "POETRY_VERSION=2.1.3" in env_example
    assert "ARGUS_BACKTEST_WORKFLOW_TIMEOUT_SECONDS=300" in env_example
    assert "ARGUS_OPENROUTER_RESULT_SUMMARY_TIMEOUT_SECONDS=20" in env_example
    assert "ARGUS_RENDER_WORKFLOW_PROOF_ENV=(" in env_contract
    assert "ARGUS_WORKFLOW_DATABASE_URL" in env_contract
    assert "ARGUS_RENDER_WORKFLOW_PROOF_TASK" in env_contract
    assert "ARGUS_WORKFLOW_PROOF_PLAN" in env_contract
    assert "POETRY_VERSION" in env_contract
    assert "ARGUS_BACKTEST_WORKFLOW_TIMEOUT_SECONDS" in env_contract
    assert "ARGUS_MARKET_DATA_PROVIDER_MODE" in env_contract
    assert "ENABLE_MARKET_DATA_CACHE" in env_contract
    assert "ALPACA_API_KEY" in env_contract
    assert "ALPACA_SECRET_KEY" in env_contract
    assert "ALPACA_PAPER_TRADING" in env_contract
    assert "OPENROUTER_API_KEY" in env_contract
    assert "ARGUS_UTILITY_MODEL" in env_contract
    assert "ARGUS_UTILITY_FALLBACK_MODEL" in env_contract
    assert "ARGUS_CHAT_MODEL" in env_contract
    assert "ARGUS_CHAT_FALLBACK_MODEL" in env_contract
    assert "ARGUS_OPENROUTER_RESULT_SUMMARY_TIMEOUT_SECONDS" in env_contract
    assert "ARGUS_STRUCTURED_MODEL" in env_contract
    assert "ARGUS_STRUCTURED_FALLBACK_MODEL" in env_contract
    assert "ARGUS_CONTEXT_MODEL" in env_contract
    assert "ARGUS_CONTEXT_FALLBACK_MODEL" in env_contract
    assert (
        "ARGUS_BACKTEST_WORKFLOW_TIMEOUT_SECONDS "
        '"${ARGUS_BACKTEST_WORKFLOW_TIMEOUT_SECONDS:-300}"'
    ) in _source(".github/render-env-sync.sh")
    assert all(service["type"] != "workflow" for service in render_config["services"])


def test_workflow_proof_seed_usage_allows_disposable_preview_user() -> None:
    proof_script = _source(".github/workflow-proof.sh")

    assert ".github/workflow-proof.sh seed [--user-id <uuid>]" in proof_script
    assert "Seed creates a disposable proof auth/profile row" in proof_script
    assert "local or preview Supabase database" in proof_script


def test_render_env_sync_uses_shared_contract_and_single_var_updates() -> None:
    source = _source(".github/render-env-sync.sh")
    env_contract = ENV_CONTRACT.read_text()

    assert 'source "$SCRIPT_DIR/argus-env.sh"' in source
    assert "ARGUS_BACKTEST_WORKFLOW_TASK_DEFAULT" in source
    assert "ARGUS_RENDER_WORKFLOW_BUILD_COMMAND" in env_contract
    assert "ARGUS_RENDER_API_BUILD_COMMAND" in env_contract
    assert "ARGUS_RENDER_API_START_COMMAND" in env_contract
    assert "ARGUS_RENDER_WORKFLOW_START_COMMAND" in env_contract
    assert "/v1/services/${service_id}/env-vars/${key}" in source
    assert "ARGUS_BACKTEST_JOBS_SHADOW_ENABLED true" in source
    assert "ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED true" in source
    assert "ARGUS_BACKTEST_JOBS_USER_RUNNING_LIMIT" in source
    assert "ARGUS_BACKTEST_JOBS_GLOBAL_QUEUED_LIMIT" in source


def test_render_env_sync_pushes_workflow_llm_readout_env() -> None:
    source = _source(".github/render-env-sync.sh")
    workflow_block = source.split("sync_workflow_proof() {", maxsplit=1)[1].split(
        "\n}",
        maxsplit=1,
    )[0]

    for key in (
        "OPENROUTER_API_KEY",
        "ARGUS_UTILITY_MODEL",
        "ARGUS_UTILITY_FALLBACK_MODEL",
        "ARGUS_CHAT_MODEL",
        "ARGUS_CHAT_FALLBACK_MODEL",
        "ARGUS_STRUCTURED_MODEL",
        "ARGUS_STRUCTURED_FALLBACK_MODEL",
        "ARGUS_CONTEXT_MODEL",
        "ARGUS_CONTEXT_FALLBACK_MODEL",
    ):
        assert f"require_local_env {key}" in workflow_block
        assert f'put_render_env "$WORKFLOW_SERVICE_ID" {key} "${key}"' in workflow_block
    assert (
        'put_render_env "$WORKFLOW_SERVICE_ID" '
        'ARGUS_OPENROUTER_RESULT_SUMMARY_TIMEOUT_SECONDS '
        '"${ARGUS_OPENROUTER_RESULT_SUMMARY_TIMEOUT_SECONDS:-20}"'
    ) in workflow_block
    assert "ARGUS_WORKFLOW_DATABASE_URL" in source
    assert "require_local_env ALPACA_API_KEY" in source
    assert "require_local_env ALPACA_SECRET_KEY" in source


def test_render_env_sync_can_release_workflow_after_env_updates() -> None:
    source = _source(".github/render-env-sync.sh")

    assert ".github/render-env-sync.sh workflow-release [commit]" in source
    assert "sync_workflow_release()" in source
    assert 'render workflows versions release "$WORKFLOW_SERVICE_ID"' in source
    assert "--wait" in source
    assert "--confirm" in source
    assert 'put_render_env "$WORKFLOW_SERVICE_ID" ALPACA_API_KEY' in source
    assert 'put_render_env "$WORKFLOW_SERVICE_ID" ALPACA_SECRET_KEY' in source
    assert (
        'put_render_env "$WORKFLOW_SERVICE_ID" ARGUS_MARKET_DATA_PROVIDER_MODE' in source
    )
    assert 'put_render_env "$WORKFLOW_SERVICE_ID" ENABLE_MARKET_DATA_CACHE' in source
    assert 'put_render_env "$WORKFLOW_SERVICE_ID" ALPACA_PAPER_TRADING' in source
    assert 'put_render_env "$WORKFLOW_SERVICE_ID" POETRY_VERSION' in source
    assert "workflow-runtime" in source
    assert "https://api.render.com/v1/workflows/${WORKFLOW_SERVICE_ID}" in source
    assert "render_workflow_json" in source


def test_render_env_sync_prints_api_deploy_status_without_mutation() -> None:
    source = _source(".github/render-env-sync.sh")

    assert ".github/render-env-sync.sh api-deploy-status" in source
    assert "print_api_deploy_status()" in source
    assert "/v1/services/${service_id}/deploys?limit=1" in source
    assert 'print_deploy_status "$API_SERVICE_ID" "argus-api"' in source
    assert "commit_short" in source
    assert "deploy_id" in source

    deploy_status_block = source.split(
        "print_api_deploy_status() {",
        maxsplit=1,
    )[1].split("\n}", maxsplit=1)[0]

    assert "put_render_env" not in deploy_status_block
    assert "delete_render_env" not in deploy_status_block


def test_render_env_sync_prints_web_deploy_status_without_mutation() -> None:
    env_contract = ENV_CONTRACT.read_text()
    source = _source(".github/render-env-sync.sh")

    assert 'ARGUS_PRIVATE_LAUNCH_WEB_SERVICE_ID="srv-d7ap6bmslomc73eqp8m0"' in (
        env_contract
    )
    assert ".github/render-env-sync.sh web-deploy-status" in source
    assert "WEB_SERVICE_ID" in source
    assert "print_web_deploy_status()" in source
    assert "/v1/services/${service_id}/deploys?limit=1" in source
    assert 'print_deploy_status "$WEB_SERVICE_ID" "argus-app"' in source

    deploy_status_block = source.split(
        "print_web_deploy_status() {",
        maxsplit=1,
    )[1].split("\n}", maxsplit=1)[0]

    assert "put_render_env" not in deploy_status_block
    assert "delete_render_env" not in deploy_status_block


def test_render_env_sync_can_sync_api_runtime_config() -> None:
    source = _source(".github/render-env-sync.sh")

    assert ".github/render-env-sync.sh api-runtime" in source
    api_runtime_block = source.split("sync_api_runtime() {", maxsplit=1)[1].split(
        "sync_workflow_proof() {", maxsplit=1
    )[0]
    assert "https://api.render.com/v1/services/${API_SERVICE_ID}" in api_runtime_block
    assert "envSpecificDetails" in api_runtime_block
    assert "buildCommand: $build_command" in api_runtime_block
    assert "startCommand: $start_command" in api_runtime_block
    assert 'put_render_env "$API_SERVICE_ID" POETRY_VERSION' in api_runtime_block
    assert ".buildConfig + {buildCommand: $build_command}" in source
    assert "ARGUS_RENDER_WORKFLOW_BUILD_COMMAND" in source
    assert "ARGUS_RENDER_WORKFLOW_START_COMMAND" in source
    assert "set -x" not in source


def test_env_example_separates_shadow_jobs_from_workflow_dispatch() -> None:
    env_example = _source(".env.example")
    shadow_block = env_example.split("# Backtest jobs shadow mode", maxsplit=1)[1].split(
        "# Backtest jobs workflow dispatch",
        maxsplit=1,
    )[0]
    dispatch_block = env_example.split(
        "# Backtest jobs workflow dispatch",
        maxsplit=1,
    )[1].split("# Collections", maxsplit=1)[0]

    assert "workflow dispatch" not in shadow_block.lower()
    assert "durable" in shadow_block
    assert "ARGUS_BACKTEST_JOBS_SHADOW_ENABLED=false" in shadow_block
    assert "ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED=false" in dispatch_block
    assert "ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED=false" in dispatch_block
    assert "ARGUS_BACKTEST_WORKFLOW_TASK=argus-backtests/workflow_proof" in dispatch_block
    assert (
        "ARGUS_BACKTEST_REAL_WORKFLOW_TASK=argus-backtests/run_backtest_job"
        in dispatch_block
    )
    assert "still returns the current in-process result" in dispatch_block


def test_render_env_sync_can_inspect_and_safely_disable_dispatch() -> None:
    source = _source(".github/render-env-sync.sh")
    dispatch_off_block = source.split("sync_api_safe_off() {", maxsplit=1)[1].split(
        "\n}",
        maxsplit=1,
    )[0]

    assert ".github/render-env-sync.sh api-status" in source
    assert ".github/render-env-sync.sh api-safe-off" in source
    assert ".github/render-env-sync.sh api-proof-shadow-on" in source
    assert ".github/render-env-sync.sh api-real-workflow-on" in source
    assert "print_api_status()" in source
    assert "<redacted-present>" in source
    assert "<missing-or-empty>" in source
    assert 'if [ "$status" = "404" ]' in source
    assert "already absent ${service_id}:${key}" in source
    assert "ARGUS_BACKTEST_JOBS_SHADOW_ENABLED false" in dispatch_off_block
    assert "ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED false" in dispatch_off_block
    assert "ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED false" in dispatch_off_block
    assert "ARGUS_BACKTEST_WORKFLOW_TASK" in dispatch_off_block
    assert "ARGUS_BACKTEST_REAL_WORKFLOW_TASK" in dispatch_off_block
    assert 'delete_render_env "$API_SERVICE_ID" RENDER_API_KEY' in dispatch_off_block


def test_render_env_sync_separates_proof_and_real_api_modes() -> None:
    source = _source(".github/render-env-sync.sh")
    proof_block = source.split("sync_api_proof_shadow_on() {", maxsplit=1)[1].split(
        "\n}",
        maxsplit=1,
    )[0]
    real_block = source.split("sync_api_real_workflow_on() {", maxsplit=1)[1].split(
        "\n}",
        maxsplit=1,
    )[0]

    assert "ARGUS_BACKTEST_JOBS_SHADOW_ENABLED true" in proof_block
    assert "ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED true" in proof_block
    assert "ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED false" in proof_block
    assert (
        'ARGUS_BACKTEST_WORKFLOW_TASK "$ARGUS_BACKTEST_WORKFLOW_TASK_DEFAULT"'
        in proof_block
    )
    assert (
        'ARGUS_BACKTEST_REAL_WORKFLOW_TASK "$ARGUS_BACKTEST_REAL_WORKFLOW_TASK_DEFAULT"'
        in proof_block
    )
    assert (
        'put_render_env "$API_SERVICE_ID" RENDER_API_KEY "$RENDER_API_KEY"' in proof_block
    )

    assert "ARGUS_BACKTEST_JOBS_SHADOW_ENABLED true" in real_block
    assert "ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED true" in real_block
    assert "ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED true" in real_block
    assert (
        'ARGUS_BACKTEST_WORKFLOW_TASK "$ARGUS_BACKTEST_WORKFLOW_TASK_DEFAULT"'
        in real_block
    )
    assert (
        'ARGUS_BACKTEST_REAL_WORKFLOW_TASK "$ARGUS_BACKTEST_REAL_WORKFLOW_TASK_DEFAULT"'
        in real_block
    )
    assert (
        'put_render_env "$API_SERVICE_ID" RENDER_API_KEY "$RENDER_API_KEY"' in real_block
    )


def test_render_blueprint_preserves_optional_posthog_key() -> None:
    env_contract = ENV_CONTRACT.read_text()
    web_env = _render_env("argus-app")

    assert "NEXT_PUBLIC_POSTHOG_KEY" in env_contract
    assert web_env["NEXT_PUBLIC_POSTHOG_KEY"] == {
        "key": "NEXT_PUBLIC_POSTHOG_KEY",
        "sync": False,
    }


def test_warmup_script_defaults_to_private_launch_render_urls() -> None:
    warmup = _source(".github/warmup-render.sh")
    env_contract = ENV_CONTRACT.read_text()

    assert "https://argus-app-suz5.onrender.com" in env_contract
    assert "https://argus-ohr5.onrender.com" in env_contract
    assert "ARGUS_PRIVATE_LAUNCH_APP_URL" in warmup
    assert "ARGUS_PRIVATE_LAUNCH_API_URL" in warmup
    assert "/health" in warmup
    assert "Argus product path is ready for testers" in warmup


def test_warmup_script_checks_product_readiness_endpoint() -> None:
    warmup = _source(".github/warmup-render.sh")

    assert 'source "$SCRIPT_DIR/argus-env.sh"' in warmup
    assert "argus_load_root_env" in warmup
    assert "/internal/readiness" in warmup
    assert "ARGUS_OPS_TOKEN" in warmup
    assert "Authorization: Bearer ${OPS_TOKEN}" in warmup


def test_warmup_script_can_assert_expected_api_mode_without_mutating_render() -> None:
    warmup = _source(".github/warmup-render.sh")

    assert "--expect-mode <safe-off|proof-shadow|real-workflow>" in warmup
    assert "assert_api_mode()" in warmup
    assert '"$SCRIPT_DIR/render-env-sync.sh" api-status' in warmup
    assert "ARGUS_BACKTEST_JOBS_SHADOW_ENABLED=false" in warmup
    assert "ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED=true" in warmup
    assert "ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED=true" in warmup
    assert "ARGUS_BACKTEST_WORKFLOW_TASK=argus-backtests/workflow_proof" in warmup
    assert "ARGUS_BACKTEST_REAL_WORKFLOW_TASK=argus-backtests/run_backtest_job" in warmup
    assert "put_render_env" not in warmup
    assert "delete_render_env" not in warmup


def test_warmup_script_runs_stale_job_scan_when_supabase_verifier_env_exists() -> None:
    warmup = _source(".github/warmup-render.sh")

    assert ".github/stale-backtest-jobs.sh" in warmup
    assert "ARGUS_STALE_JOBS_SUPABASE_URL" in warmup
    assert "ARGUS_STALE_JOBS_SUPABASE_SERVICE_ROLE_KEY" in warmup
    assert "Skipping stale backtest job scan" in warmup
    assert "set -x" not in warmup


def test_private_launch_runbook_uses_real_workflow_readiness_gate() -> None:
    runbook = _source("docs/PRIVATE_LAUNCH_RUNBOOK.md")
    before_sessions = runbook.split("## Before Tester Sessions", maxsplit=1)[
        1
    ].split("## Backtest Workflow Modes", maxsplit=1)[0]
    normalized_before_sessions = " ".join(before_sessions.split())

    assert ".github/render-env-sync.sh api-real-workflow-on" in before_sessions
    assert ".github/render-env-sync.sh api-deploy-status" in before_sessions
    assert ".github/render-env-sync.sh web-deploy-status" in before_sessions
    assert ".github/warmup-render.sh --expect-mode real-workflow" in before_sessions
    assert ".github/canary-render.sh" in before_sessions
    assert (
        "API deploy-status, app deploy-status, warmup, English canary, and Spanish canary"
        in normalized_before_sessions
    )
    assert "both scripts pass" not in before_sessions
    assert ".github/stale-backtest-jobs.sh" in runbook
    assert "api-safe-off` is the default private-alpha tester mode" not in runbook
    assert "NEXT_PUBLIC_POSTHOG_KEY" in runbook


def test_private_launch_runbook_smoke_covers_final_readiness_path() -> None:
    runbook = _source("docs/PRIVATE_LAUNCH_RUNBOOK.md")
    smoke_test = runbook.split("## Smoke Test", maxsplit=1)[1].split(
        "## Supabase Persistence Check",
        maxsplit=1,
    )[0]

    for expected in (
        "Cold-start starter chips are visible",
        "do not reference 2024",
        "Spanish prompt",
        "Run backtest",
        "Change dates",
        "Change asset",
        "Adjust assumptions",
        "Cancel",
        "Quick take",
        "Explain result",
        "Retry",
        "Reloading the page preserves the conversation, job state, and result",
        "Feedback can be submitted",
    ):
        assert expected in smoke_test
