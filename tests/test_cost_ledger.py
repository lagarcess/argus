from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from argus.api.chat.route_receipts import persist_route_receipts
from argus.llm.openrouter import OpenRouterRouteReceipt
from argus.observability import cost_ledger as cost_ledger_module
from argus.observability.cost_ledger import (
    openrouter_cost_ledger_entry_from_receipt,
    persist_openrouter_cost_ledger_entries,
)

ROOT = Path(__file__).resolve().parents[1]


class _FakeCostLedgerGateway:
    def __init__(self) -> None:
        self.route_receipts: list[dict[str, Any]] = []
        self.cost_ledger_entries: list[dict[str, Any]] = []

    def create_route_receipt(
        self,
        *,
        user_id: str | None,
        receipt: dict[str, Any],
        conversation_id: str | None = None,
        run_id: str | None = None,
        message_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        row = {
            "id": f"receipt-{len(self.route_receipts) + 1}",
            "user_id": user_id,
            "conversation_id": conversation_id,
            "run_id": run_id,
            "message_id": message_id,
            "metadata": metadata or {},
            **receipt,
        }
        self.route_receipts.append(row)
        return row

    def create_cost_ledger_entry(self, *, entry: dict[str, Any]) -> dict[str, Any]:
        row = {"id": f"ledger-{len(self.cost_ledger_entries) + 1}", **entry}
        self.cost_ledger_entries.append(row)
        return row


class _UnavailableCostLedgerGateway(_FakeCostLedgerGateway):
    def create_cost_ledger_entry(self, *, entry: dict[str, Any]) -> dict[str, Any]:
        del entry
        raise RuntimeError("PGRST205: cost_ledger_entries is unavailable")


class _WarningCapture:
    def __init__(self) -> None:
        self.records: list[tuple[str, dict[str, Any]]] = []

    def warning(self, message: str, **context: Any) -> None:
        self.records.append((message, context))


def _receipt(**overrides: Any) -> OpenRouterRouteReceipt:
    values: dict[str, Any] = {
        "task": "interpretation",
        "tier": "structured",
        "model": "openai/gpt-4.1-mini",
        "fallback_model": "openai/gpt-4.1-nano",
        "mode": "json_schema",
        "schema_name": "LLMInterpretationResponse",
        "latency_ms": 321,
        "outcome": "succeeded",
        "token_usage": {
            "prompt_tokens": 100,
            "completion_tokens": 40,
            "total_tokens": 140,
        },
        "usage_cost_usd": 0.00042,
        "context_packet_ids": ["packet-1"],
        "created_at": "2026-07-02T12:00:00+00:00",
    }
    values.update(overrides)
    return OpenRouterRouteReceipt(**values)


def test_openrouter_receipt_builds_provider_cost_ledger_entry() -> None:
    entry = openrouter_cost_ledger_entry_from_receipt(
        receipt=_receipt(),
        source="api_turn",
        user_id="user-1",
        conversation_id="conversation-1",
        message_id="message-1",
        route_receipt_id="receipt-1",
        request_id="req-1",
        correlation_id="req-1:conversation-1:message-1",
        feature_area="chat_runtime",
        metadata={"surface": "chat"},
    )

    assert entry["source"] == "api_turn"
    assert entry["service"] == "openrouter"
    assert entry["provider"] == "openrouter"
    assert entry["model"] == "openai/gpt-4.1-mini"
    assert entry["task"] == "interpretation"
    assert entry["user_id"] == "user-1"
    assert entry["conversation_id"] == "conversation-1"
    assert entry["message_id"] == "message-1"
    assert entry["route_receipt_id"] == "receipt-1"
    assert entry["request_id"] == "req-1"
    assert entry["correlation_id"] == "req-1:conversation-1:message-1"
    assert entry["input_tokens"] == 100
    assert entry["output_tokens"] == 40
    assert entry["total_tokens"] == 140
    assert entry["billable_unit"] == "token"
    assert entry["billable_quantity"] == 140
    assert entry["cost_amount"] == 0.00042
    assert entry["cost_currency"] == "USD"
    assert entry["cost_source"] == "provider_reported"
    assert entry["latency_ms"] == 321
    assert entry["usage_metadata"] == {
        "prompt_tokens": 100,
        "completion_tokens": 40,
        "total_tokens": 140,
        "usage_cost_usd": 0.00042,
    }
    assert entry["metadata"]["surface"] == "chat"
    assert entry["metadata"]["fallback_model"] == "openai/gpt-4.1-nano"
    assert entry["metadata"]["context_packet_count"] == 1


def test_persist_route_receipts_also_appends_cost_ledger_entries(monkeypatch) -> None:
    gateway = _FakeCostLedgerGateway()
    monkeypatch.setattr("argus.api.chat.route_receipts.api_state.supabase_gateway", gateway)

    persist_route_receipts(
        receipts=[_receipt()],
        user_id="user-1",
        conversation_id="conversation-1",
        message_id="message-1",
        metadata={"request_id": "req-1", "source": "api_turn"},
    )

    assert len(gateway.route_receipts) == 1
    assert len(gateway.cost_ledger_entries) == 1
    entry = gateway.cost_ledger_entries[0]
    assert entry["source"] == "api_turn"
    assert entry["conversation_id"] == "conversation-1"
    assert entry["message_id"] == "message-1"
    assert entry["route_receipt_id"] == "receipt-1"
    assert entry["request_id"] == "req-1"
    assert entry["correlation_id"] == "req-1:conversation-1:message-1"
    assert entry["cost_amount"] == 0.00042


def test_chat_route_receipt_survives_telemetry_only_cost_ledger_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = _UnavailableCostLedgerGateway()
    warning_capture = _WarningCapture()
    monkeypatch.setattr(cost_ledger_module, "logger", warning_capture)
    monkeypatch.setattr(
        "argus.api.chat.route_receipts.api_state.supabase_gateway",
        gateway,
    )

    persist_route_receipts(
        receipts=[_receipt()],
        user_id="user-1",
        conversation_id="conversation-1",
        message_id="message-1",
        metadata={"request_id": "req-1"},
    )

    assert len(gateway.route_receipts) == 1
    assert gateway.cost_ledger_entries == []
    assert len(warning_capture.records) == 1
    message, context = warning_capture.records[0]
    assert message == "Cost ledger persistence failed; continuing without spend row"
    assert context["failure_classification"] == "telemetry_only"
    assert context["correlation_id"] == "req-1:conversation-1:message-1"


def test_eval_harness_receipts_can_append_cost_ledger_entries() -> None:
    gateway = _FakeCostLedgerGateway()

    persist_openrouter_cost_ledger_entries(
        gateway=gateway,
        receipts=[_receipt(task="capability_conflict", tier="context")],
        source="eval_harness",
        correlation_id="eval:private-alpha-next:case-1",
        feature_area="eval_readiness",
        metadata={
            "eval_suite_id": "private-alpha-next",
            "eval_case_id": "case-1",
        },
    )

    assert len(gateway.cost_ledger_entries) == 1
    entry = gateway.cost_ledger_entries[0]
    assert entry["source"] == "eval_harness"
    assert entry["user_id"] is None
    assert entry["conversation_id"] is None
    assert entry["correlation_id"] == "eval:private-alpha-next:case-1"
    assert entry["feature_area"] == "eval_readiness"
    assert entry["metadata"]["eval_case_id"] == "case-1"


def test_cost_ledger_migration_is_append_only_and_revertible() -> None:
    migration_sql = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in sorted((ROOT / "supabase" / "migrations").glob("*.sql"))
    )

    assert "create table if not exists public.cost_ledger_entries" in migration_sql
    assert "source text not null" in migration_sql
    assert "service text not null" in migration_sql
    assert "provider text not null" in migration_sql
    assert "model text" in migration_sql
    assert "input_tokens integer" in migration_sql
    assert "output_tokens integer" in migration_sql
    assert "total_tokens integer" in migration_sql
    assert "cost_amount numeric(18, 8)" in migration_sql
    assert "correlation_id text not null" in migration_sql
    assert (
        "alter table public.cost_ledger_entries enable row level security"
        in migration_sql
    )
    assert (
        "grant insert, select on table public.cost_ledger_entries to service_role"
        in migration_sql
    )
    assert (
        "revoke all on table public.cost_ledger_entries "
        "from anon, authenticated, service_role" in migration_sql
    )
    assert "grant update on table public.cost_ledger_entries" not in migration_sql
    assert "grant delete on table public.cost_ledger_entries" not in migration_sql
    assert "grant all privileges on table public.cost_ledger_entries" not in migration_sql
    assert "rollback: drop table if exists public.cost_ledger_entries" in migration_sql


def test_cost_ledger_product_code_has_no_update_or_delete_path() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for root in ("src/argus", "workflows", "tests/evals")
        for path in (ROOT / root).rglob("*.py")
    )

    assert '.table("cost_ledger_entries").insert' in source
    assert '.table("cost_ledger_entries").update' not in source
    assert '.table("cost_ledger_entries").upsert' not in source
    assert '.table("cost_ledger_entries").delete' not in source
