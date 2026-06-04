from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_CONTRACT = ROOT / ".github" / "argus-env.sh"


def _source(path: str) -> str:
    return (ROOT / path).read_text()


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


def test_render_blueprint_uses_current_env_contract_names_only() -> None:
    render_yaml = _source("render.yaml")
    contract = ENV_CONTRACT.read_text()

    for key in (
        "ARGUS_PERSISTENCE_MODE",
        "ARGUS_DEV_MEMORY_FALLBACK",
        "ARGUS_MARKET_DATA_PROVIDER_MODE",
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


def test_warmup_script_defaults_to_private_launch_render_urls() -> None:
    warmup = _source(".github/warmup-render.sh")

    assert "https://argus-app-suz5.onrender.com" in warmup
    assert "https://argus-ohr5.onrender.com" in warmup
    assert "/health" in warmup
    assert "Argus is warm and ready for testers" in warmup
