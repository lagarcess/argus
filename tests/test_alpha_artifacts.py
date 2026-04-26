from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_active_openapi_uses_alpha_contract_names() -> None:
    openapi = ROOT / "docs" / "api" / "openapi.yaml"

    text = openapi.read_text(encoding="utf-8")

    for path in (
        "/api/v1/me",
        "/api/v1/conversations",
        "/api/v1/chat/stream",
        "/api/v1/backtests/run",
        "/api/v1/collections",
        "/api/v1/history",
    ):
        assert path in text
    assert "conversation_result_card" in text
    assert "backtest_runs" in text
    assert "portfolios" not in text.lower()
    assert "simulations" not in text.lower()
    assert "summary:" not in text.lower()


def test_supabase_migration_matches_alpha_data_model() -> None:
    migration = ROOT / "supabase" / "migrations" / "20260424000001_alpha_core.sql"

    text = migration.read_text(encoding="utf-8").lower()

    for table in (
        "profiles",
        "conversations",
        "messages",
        "strategies",
        "collections",
        "collection_strategies",
        "backtest_runs",
        "feedback",
        "usage_counters",
    ):
        assert f"create table if not exists public.{table}" in text
        assert f"alter table public.{table} enable row level security" in text

    assert "using gin(symbols)" in text
    assert "unique(user_id, resource, period, period_start)" in text
    assert "simulations" not in text
    assert "portfolios" not in text
