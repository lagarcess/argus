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
        "ARGUS_DEV_MEMORY_FALLBACK",
        "ARGUS_MARKET_DATA_PROVIDER_MODE",
        "ARGUS_RUNTIME_EVENT_TIMEOUT_SECONDS",
        "ARGUS_RUNTIME_EVENT_KEEPALIVE_SECONDS",
        "ARGUS_CHECKPOINTER_MODE",
        "ARGUS_MOCK_AUTH",
        "ARGUS_CORS_ALLOW_ORIGINS",
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
    assert "ARGUS_WORKFLOW_PROOF_PLAN=" in env_example
    assert "ARGUS_RENDER_WORKFLOW_PROOF_ENV=(" in env_contract
    assert "ARGUS_RENDER_WORKFLOW_PROOF_TASK" in env_contract
    assert "ARGUS_WORKFLOW_PROOF_PLAN" in env_contract
    assert "DATABASE_URL" in env_contract
    assert all(service["type"] != "workflow" for service in render_config["services"])


def test_workflow_proof_seed_usage_allows_disposable_preview_user() -> None:
    proof_script = _source(".github/workflow-proof.sh")

    assert ".github/workflow-proof.sh seed [--user-id <uuid>]" in proof_script
    assert "Seed creates a disposable proof auth/profile row" in proof_script
    assert "local or preview Supabase database" in proof_script


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

    assert "https://argus-app-suz5.onrender.com" in warmup
    assert "https://argus-ohr5.onrender.com" in warmup
    assert "/health" in warmup
    assert "Argus product path is ready for testers" in warmup


def test_warmup_script_checks_product_readiness_endpoint() -> None:
    warmup = _source(".github/warmup-render.sh")

    assert "/internal/readiness" in warmup
    assert "ARGUS_OPS_TOKEN" in warmup
    assert "Authorization: Bearer ${OPS_TOKEN}" in warmup
