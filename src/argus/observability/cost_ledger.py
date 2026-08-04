from __future__ import annotations

from typing import Any, Literal, Protocol

from loguru import logger

from argus.llm.openrouter import OpenRouterRouteReceipt

CostLedgerSource = Literal[
    "api_turn",
    "render_workflow",
    "eval_harness",
    "manual_reconciliation",
    "runtime_compute",
    "storage",
    "market_data",
    "stt",
    "research",
]


class CostLedgerGateway(Protocol):
    def create_cost_ledger_entry(self, *, entry: dict[str, Any]) -> dict[str, Any]:
        """Append one operational cost ledger row."""


def openrouter_cost_ledger_entry_from_receipt(
    *,
    receipt: OpenRouterRouteReceipt,
    source: CostLedgerSource,
    correlation_id: str,
    feature_area: str,
    user_id: str | None = None,
    conversation_id: str | None = None,
    message_id: str | None = None,
    backtest_run_id: str | None = None,
    backtest_job_id: str | None = None,
    route_receipt_id: str | None = None,
    request_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    token_usage = dict(receipt.token_usage or {})
    input_tokens = _first_int(token_usage, "prompt_tokens", "input_tokens")
    output_tokens = _first_int(token_usage, "completion_tokens", "output_tokens")
    total_tokens = _first_int(token_usage, "total_tokens")
    if total_tokens is None and (input_tokens is not None or output_tokens is not None):
        total_tokens = int(input_tokens or 0) + int(output_tokens or 0)

    usage_metadata: dict[str, Any] = dict(token_usage)
    if receipt.usage_cost_usd is not None:
        usage_metadata["usage_cost_usd"] = receipt.usage_cost_usd

    billable_quantity = total_tokens
    cost_amount = receipt.usage_cost_usd
    return {
        "source": source,
        "service": "openrouter",
        "provider": "openrouter",
        "model": receipt.model,
        "feature_area": feature_area,
        "task": receipt.task,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "message_id": message_id,
        "backtest_run_id": backtest_run_id,
        "backtest_job_id": backtest_job_id,
        "route_receipt_id": route_receipt_id,
        "request_id": request_id,
        "correlation_id": correlation_id,
        "provider_request_id": None,
        "upstream_id": None,
        "usage_metadata": usage_metadata,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "billable_unit": "token",
        "billable_quantity": billable_quantity,
        "cost_amount": cost_amount,
        "cost_currency": "USD",
        "cost_source": (
            "provider_reported" if cost_amount is not None else "unavailable"
        ),
        "latency_ms": receipt.latency_ms,
        "status": receipt.outcome,
        "metadata": _ledger_metadata(receipt=receipt, metadata=metadata),
        "occurred_at": receipt.created_at or None,
    }


def persist_openrouter_cost_ledger_entries(
    *,
    gateway: CostLedgerGateway,
    receipts: list[OpenRouterRouteReceipt],
    source: CostLedgerSource,
    feature_area: str,
    user_id: str | None = None,
    conversation_id: str | None = None,
    message_id: str | None = None,
    backtest_run_id: str | None = None,
    backtest_job_id: str | None = None,
    request_id: str | None = None,
    correlation_id: str | None = None,
    route_receipt_rows: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    if not receipts:
        return

    receipt_rows = route_receipt_rows or []
    for index, receipt in enumerate(receipts):
        route_receipt_id = _route_receipt_id(receipt_rows, index)
        resolved_correlation_id = correlation_id or _default_correlation_id(
            source=source,
            request_id=request_id,
            conversation_id=conversation_id,
            message_id=message_id,
            backtest_job_id=backtest_job_id,
            backtest_run_id=backtest_run_id,
            route_receipt_id=route_receipt_id,
        )
        entry = openrouter_cost_ledger_entry_from_receipt(
            receipt=receipt,
            source=source,
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            backtest_run_id=backtest_run_id,
            backtest_job_id=backtest_job_id,
            route_receipt_id=route_receipt_id,
            request_id=request_id,
            correlation_id=resolved_correlation_id,
            feature_area=feature_area,
            metadata=metadata,
        )
        try:
            gateway.create_cost_ledger_entry(entry=entry)
        except Exception as exc:
            logger.warning(
                "Cost ledger persistence failed; continuing without spend row",
                error=str(exc),
                source=source,
                feature_area=feature_area,
                llm_task=receipt.task,
                correlation_id=resolved_correlation_id,
                failure_classification="telemetry_only",
            )


def normalize_cost_ledger_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Apply canonical column defaults for one cost ledger row before insert.

    Both persistence backends (the Supabase client gateway and the psycopg
    workflow gateway) call this so the default values live in one place and the
    two write paths cannot drift. ``occurred_at`` is left untouched here; each
    backend fills it with its own timestamp helper when the value is absent.
    """
    return {
        "source": entry["source"],
        "service": entry["service"],
        "provider": entry["provider"],
        "model": entry.get("model"),
        "feature_area": entry["feature_area"],
        "task": entry.get("task"),
        "user_id": entry.get("user_id"),
        "conversation_id": entry.get("conversation_id"),
        "message_id": entry.get("message_id"),
        "backtest_run_id": entry.get("backtest_run_id"),
        "backtest_job_id": entry.get("backtest_job_id"),
        "route_receipt_id": entry.get("route_receipt_id"),
        "request_id": entry.get("request_id"),
        "correlation_id": entry["correlation_id"],
        "provider_request_id": entry.get("provider_request_id"),
        "upstream_id": entry.get("upstream_id"),
        "usage_metadata": entry.get("usage_metadata") or {},
        "input_tokens": entry.get("input_tokens"),
        "output_tokens": entry.get("output_tokens"),
        "total_tokens": entry.get("total_tokens"),
        "billable_unit": entry.get("billable_unit") or "unknown",
        "billable_quantity": entry.get("billable_quantity"),
        "cost_amount": entry.get("cost_amount"),
        "cost_currency": entry.get("cost_currency") or "USD",
        "cost_source": entry.get("cost_source") or "unavailable",
        "latency_ms": entry.get("latency_ms"),
        "status": entry.get("status") or "succeeded",
        "metadata": entry.get("metadata") or {},
        "occurred_at": entry.get("occurred_at"),
    }


def _first_int(values: dict[str, int], *keys: str) -> int | None:
    for key in keys:
        value = values.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
    return None


def _route_receipt_id(rows: list[dict[str, Any]], index: int) -> str | None:
    if index >= len(rows):
        return None
    value = rows[index].get("id")
    text = str(value or "").strip()
    return text or None


def _default_correlation_id(
    *,
    source: CostLedgerSource,
    request_id: str | None,
    conversation_id: str | None,
    message_id: str | None,
    backtest_job_id: str | None,
    backtest_run_id: str | None,
    route_receipt_id: str | None,
) -> str:
    if request_id and conversation_id and message_id:
        return f"{request_id}:{conversation_id}:{message_id}"
    if source == "render_workflow" and backtest_job_id and backtest_run_id:
        return f"workflow:{backtest_job_id}:{backtest_run_id}"
    parts = [
        source,
        request_id,
        conversation_id,
        message_id,
        backtest_job_id,
        backtest_run_id,
        route_receipt_id,
    ]
    return ":".join(part for part in parts if part) or source


def _ledger_metadata(
    *,
    receipt: OpenRouterRouteReceipt,
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    result = dict(metadata or {})
    result.update(
        {
            "tier": receipt.tier,
            "mode": receipt.mode,
            "schema_name": receipt.schema_name,
            "fallback_model": receipt.fallback_model,
            "fallback_used": receipt.fallback_used,
            "failure_mode": receipt.failure_mode,
            "context_packet_count": len(receipt.context_packet_ids),
        }
    )
    return result
