from __future__ import annotations

import ast
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


def test_usage_counter_resource_constraint_covers_quota_callers() -> None:
    migration_sql = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in sorted((ROOT / "supabase" / "migrations").glob("*.sql"))
    )
    constraint_index = migration_sql.rfind("usage_counters_resource_check")
    assert constraint_index >= 0
    constraint_sql = migration_sql[constraint_index : constraint_index + 500]

    resources = _usage_counter_resources_from_api_code()
    resources.add("backtest_jobs")

    for resource in resources:
        assert f"'{resource}'" in constraint_sql


def _usage_counter_resources_from_api_code() -> set[str]:
    resources: set[str] = set()
    for path in (ROOT / "src" / "argus" / "api").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not _is_check_and_increment_usage_call(node):
                continue
            for keyword in node.keywords:
                if (
                    keyword.arg == "resource"
                    and isinstance(keyword.value, ast.Constant)
                    and isinstance(keyword.value.value, str)
                ):
                    resources.add(keyword.value.value)
    assert resources
    return resources


def _is_check_and_increment_usage_call(node: ast.Call) -> bool:
    if isinstance(node.func, ast.Attribute):
        return node.func.attr == "check_and_increment_usage"
    return isinstance(node.func, ast.Name) and node.func.id == "check_and_increment_usage"
