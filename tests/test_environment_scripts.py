from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_env_example_uses_typed_supabase_postgres_urls() -> None:
    env_example = (ROOT / ".env.example").read_text()

    assert "SUPABASE_POSTGRES_DIRECT_URL=" in env_example
    assert "SUPABASE_POSTGRES_SESSION_POOLER_URL=" in env_example
    assert "SUPABASE_POSTGRES_TRANSACTION_POOLER_URL=" in env_example
    assert "\nDATABASE_URL=" not in env_example
    assert "DATABASE_URL values" not in env_example


def test_qa_script_derives_internal_database_url_from_session_pooler() -> None:
    qa_script = (ROOT / ".github" / "qa.sh").read_text()

    assert 'require_env "SUPABASE_POSTGRES_SESSION_POOLER_URL"' in qa_script
    assert 'require_env "DATABASE_URL"' not in qa_script
    assert 'export DATABASE_URL="$SUPABASE_POSTGRES_SESSION_POOLER_URL"' in qa_script
    assert "SUPABASE_POSTGRES_DIRECT_URL" in qa_script
    assert "Session Pooler -> internal DATABASE_URL" in qa_script


def test_dev_script_ignores_database_urls_even_when_env_contains_them() -> None:
    dev_script = (ROOT / ".github" / "dev.sh").read_text()

    assert "unset DATABASE_URL" in dev_script
    assert "SUPABASE_POSTGRES_SESSION_POOLER_URL" in dev_script
    assert "Database URLs: Ignored" in dev_script
