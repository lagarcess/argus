from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _markdown_section(text: str, anchor: str, next_anchor: str) -> str:
    start = text.index(f'<a id="{anchor}"></a>')
    end = text.index(f'<a id="{next_anchor}"></a>', start)
    return text[start:end]


def test_reliability_contract_locks_admission_and_run_reconciliation() -> None:
    contract = (ROOT / "docs" / "API_CONTRACT.md").read_text(encoding="utf-8")

    admission = _markdown_section(
        contract,
        "contract-idempotency-admission",
        "contract-request-boundaries",
    )
    for exact_rule in (
        "`(user_id, operation_scope, Idempotency-Key)`",
        "`chat.run_backtest`",
        "`backtests.run`",
        "`409 idempotency_conflict`",
        "`429` | `backtest_capacity_exceeded` | `15` seconds",
        "`503` | `backtest_capacity_exceeded` | `15` seconds",
        "`409 idempotency_in_progress`",
        "`Retry-After: 1`",
    ):
        assert exact_rule in admission

    reconciliation = _markdown_section(
        contract,
        "contract-run-action-reconciliation",
        "contract-chat-turn-lifecycle",
    )
    for exact_rule in (
        "`confirmation_id` is the Run action identity",
        "`Idempotency-Key` must equal `confirmation_id`",
        "`GET /api/v1/backtest-jobs/by-action/{confirmation_id}`",
        "`queued` or `running`",
        "`failed`, `canceled`, or `expired`",
    ):
        assert exact_rule in reconciliation


def test_reliability_contract_locks_chat_request_boundaries() -> None:
    contract = (ROOT / "docs" / "API_CONTRACT.md").read_text(encoding="utf-8")
    bounds = _markdown_section(
        contract,
        "contract-request-boundaries",
        "contract-openapi-authority",
    )

    for exact_rule in (
        "| Entire request body | `65,536` UTF-8 bytes |",
        "| `conversation_id` | `128` Unicode code points |",
        "| `message` | `16,000` Unicode code points |",
        "| `mentions` | `10` items |",
        "| `mention.id` | `128` Unicode code points |",
        "| `mention.label` | `120` Unicode code points |",
        "| `mention.symbol` | `32` Unicode code points |",
        "| `mention.description` | `256` Unicode code points |",
        "| `mention.insert_text` | `64` Unicode code points |",
        "| `mention.provider` | `64` Unicode code points |",
        "| `action.label` | `120` Unicode code points |",
        "| `action.labelKey` | `160` Unicode code points |",
        "| `action.payload` serialized size | `16,384` UTF-8 bytes |",
        "| `action.payload` container depth | `6` |",
        "| Any `action.payload` object | `50` keys |",
        "| Any `action.payload` array | `50` items |",
        "| Any `action.payload` string | `4,096` Unicode code points |",
        "`413 request_body_too_large`",
        "`422 validation_error`",
    ):
        assert exact_rule in bounds


def test_reliability_contract_locks_openapi_authority_and_exclusions() -> None:
    contract = (ROOT / "docs" / "API_CONTRACT.md").read_text(encoding="utf-8")
    authority = _markdown_section(
        contract,
        "contract-openapi-authority",
        "contract-run-action-reconciliation",
    )

    for exact_rule in (
        "FastAPI `app.openapi()` is the canonical machine-readable source",
        "`docs/api/openapi.yaml` is the checked compatibility artifact",
        "`GET /health`",
        "`GET /internal/readiness`",
        "`POST /api/v1/dev/reset`",
        "`POST /api/v1/chat/stream` 200 `text/event-stream` response body",
        "`/api/v1` appears exactly once",
    ):
        assert exact_rule in authority


def test_reliability_contract_locks_durable_turn_lifecycle() -> None:
    contract = (ROOT / "docs" / "API_CONTRACT.md").read_text(encoding="utf-8")
    architecture = (ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    data_model = (ROOT / "docs" / "DATA_MODEL.md").read_text(encoding="utf-8")

    lifecycle_start = contract.index('<a id="contract-chat-turn-lifecycle"></a>')
    lifecycle_end = contract.index("\n## Admin Bypass", lifecycle_start)
    lifecycle = contract[lifecycle_start:lifecycle_end]
    for state in (
        "`accepted`",
        "`running`",
        "`completed`",
        "`recoverable_failed`",
        "`abandoned`",
        "`reconciled`",
    ):
        assert state in lifecycle
    for exact_rule in (
        "`15 minutes`",
        "`20` stale rows",
        "`completed | recoverable_failed | abandoned`",
        "`turn_abandoned`",
    ):
        assert exact_rule in lifecycle

    assert (
        "Supabase owns the current durable lifecycle of every accepted chat turn"
        in architecture
    )
    assert "## 8.1 chat_turn_lifecycles" in data_model
    assert "`UNIQUE(user_id, operation_scope, idempotency_key)`" in data_model


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
