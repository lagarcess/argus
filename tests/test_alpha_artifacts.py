from __future__ import annotations

import ast
from pathlib import Path

import yaml

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


def test_backtests_run_openapi_requires_idempotency_key() -> None:
    openapi = ROOT / "docs" / "api" / "openapi.yaml"

    text = openapi.read_text(encoding="utf-8")
    start = text.index("  /api/v1/backtests/run:")
    end = text.index("  /api/v1/backtest-jobs/{id}:")
    backtest_run_contract = text[start:end]

    assert "name: Idempotency-Key" in backtest_run_contract
    assert "in: header" in backtest_run_contract
    assert "required: true" in backtest_run_contract


def test_logout_openapi_declares_browser_origin_rejection() -> None:
    openapi = ROOT / "docs" / "api" / "openapi.yaml"

    text = openapi.read_text(encoding="utf-8")
    start = text.index("  /api/v1/auth/logout:")
    end = text.index("  /api/v1/auth/session:")
    logout_contract = text[start:end]

    assert '"403":' in logout_contract
    assert "untrusted browser origin" in logout_contract.lower()


def test_authenticated_openapi_declares_session_verification_unavailable() -> None:
    openapi = ROOT / "docs" / "api" / "openapi.yaml"

    text = openapi.read_text(encoding="utf-8")
    assert "AuthSessionVerificationUnavailable" in text
    assert "auth_session_verification_unavailable" in text
    contract = yaml.safe_load(text)
    unauthenticated_paths = {
        "/api/v1/auth/signup",
        "/api/v1/auth/login",
        "/api/v1/auth/logout",
    }
    for path, path_contract in contract["paths"].items():
        if path in unauthenticated_paths:
            continue
        for method in ("get", "post", "patch", "put", "delete"):
            operation = path_contract.get(method)
            if operation is None:
                continue
            assert operation["responses"]["503"] == {
                "$ref": "#/components/responses/AuthSessionVerificationUnavailable"
            }


def test_api_contract_documents_recovery_transport_rejections() -> None:
    contract = (ROOT / "docs" / "API_CONTRACT.md").read_text(encoding="utf-8")
    start = contract.index("**Account recovery:**")
    end = contract.index("**Password and session controls:**")
    recovery_contract = contract[start:end]

    assert "`413 Payload Too Large`" in recovery_contract
    assert "4,096 bytes" in recovery_contract
    assert "`415 Unsupported Media Type`" in recovery_contract
    assert "`application/json`" in recovery_contract


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


def test_p1_evidence_spine_migration_freezes_immutable_fields_only() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in sorted((ROOT / "supabase" / "migrations").glob("*.sql"))
    )

    assert (
        "create or replace function public.prevent_idea_version_immutable_update" in text
    )
    assert "create trigger prevent_idea_versions_immutable_update" in text
    assert "before update on public.idea_versions" in text
    assert (
        "create or replace function public.prevent_evidence_artifact_immutable_update"
        in text
    )
    assert "create trigger prevent_evidence_artifacts_immutable_update" in text
    assert "before update on public.evidence_artifacts" in text

    for column in (
        "id",
        "user_id",
        "idea_id",
        "source_conversation_id",
        "source_run_id",
        "version_number",
        "canonical_spec",
        "strategy_snapshot",
        "title",
        "summary",
        "created_at",
    ):
        assert f"new.{column} is distinct from old.{column}" in text

    for column in (
        "id",
        "user_id",
        "idea_id",
        "idea_version_id",
        "source_conversation_id",
        "source_run_id",
        "artifact_type",
        "title",
        "digest",
        "payload",
        "created_at",
    ):
        assert f"new.{column} is distinct from old.{column}" in text

    assert "new.lifecycle is distinct from old.lifecycle" not in text
    assert "new.updated_at is distinct from old.updated_at" not in text


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
    names = {"check_and_increment_usage", "check_and_increment_usage_limits"}
    if isinstance(node.func, ast.Attribute):
        return node.func.attr in names
    return isinstance(node.func, ast.Name) and node.func.id in names
