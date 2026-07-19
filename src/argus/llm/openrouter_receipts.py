"""Passive OpenRouter route-receipt store: capture, retrieval, and summary.

The active recorder (which resolves models and tiers) stays beside the
routing logic in ``argus.llm.openrouter``; this module owns the receipt
record itself, the process-wide store, the per-request capture window, and
the diagnostic summary over receipts.
"""

from __future__ import annotations

from collections.abc import Iterable
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from threading import Lock
from typing import TYPE_CHECKING, Literal

from argus.llm.openrouter_usage import merge_openrouter_token_usage

if TYPE_CHECKING:
    from argus.llm.openrouter import OpenRouterModelTier, OpenRouterTask


@dataclass(frozen=True)
class OpenRouterRouteReceipt:
    task: OpenRouterTask
    tier: OpenRouterModelTier
    model: str
    fallback_model: str
    mode: Literal["json_schema", "chat_model"]
    schema_name: str | None
    latency_ms: int
    outcome: Literal["succeeded", "failed", "skipped"]
    failure_mode: str | None = None
    fallback_used: bool = False
    token_usage: dict[str, int] | None = None
    usage_cost_usd: float | None = None
    context_packet_ids: list[str] = field(default_factory=list)
    created_at: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "task": self.task,
            "tier": self.tier,
            "model": self.model,
            "fallback_model": self.fallback_model,
            "mode": self.mode,
            "schema_name": self.schema_name,
            "latency_ms": self.latency_ms,
            "outcome": self.outcome,
            "failure_mode": self.failure_mode,
            "fallback_used": self.fallback_used,
            "token_usage": self.token_usage,
            "usage_cost_usd": self.usage_cost_usd,
            "context_packet_ids": list(self.context_packet_ids),
            "created_at": self.created_at,
        }


_ROUTE_RECEIPTS: list[OpenRouterRouteReceipt] = []
_ROUTE_RECEIPTS_LOCK = Lock()
_ROUTE_RECEIPT_CAPTURE: ContextVar[list[OpenRouterRouteReceipt] | None] = ContextVar(
    "openrouter_route_receipt_capture",
    default=None,
)


def append_openrouter_route_receipt(receipt: OpenRouterRouteReceipt) -> None:
    with _ROUTE_RECEIPTS_LOCK:
        _ROUTE_RECEIPTS.append(receipt)
    capture = _ROUTE_RECEIPT_CAPTURE.get()
    if capture is not None:
        capture.append(receipt)


def get_openrouter_route_receipts() -> list[OpenRouterRouteReceipt]:
    with _ROUTE_RECEIPTS_LOCK:
        return list(_ROUTE_RECEIPTS)


def clear_openrouter_route_receipts() -> None:
    with _ROUTE_RECEIPTS_LOCK:
        _ROUTE_RECEIPTS.clear()


def begin_openrouter_route_receipt_capture() -> Token[list[OpenRouterRouteReceipt] | None]:
    return _ROUTE_RECEIPT_CAPTURE.set([])


def end_openrouter_route_receipt_capture(
    token: Token[list[OpenRouterRouteReceipt] | None],
) -> list[OpenRouterRouteReceipt]:
    receipts = list(_ROUTE_RECEIPT_CAPTURE.get() or [])
    _ROUTE_RECEIPT_CAPTURE.reset(token)
    return receipts


def summarize_openrouter_route_receipts(
    receipts: Iterable[OpenRouterRouteReceipt] | None = None,
) -> dict[str, object]:
    """
    Builds a small internal latency/failure waterfall from existing receipts.

    This is diagnostic only. It must not bypass semantic arbitration,
    capability validation, context replayability, or fallback observability.
    """

    active_receipts = list(receipts) if receipts is not None else get_openrouter_route_receipts()
    route_waterfall = [
        {
            "task": receipt.task,
            "tier": receipt.tier,
            "model": receipt.model,
            "fallback_model": receipt.fallback_model,
            "latency_ms": receipt.latency_ms,
            "outcome": receipt.outcome,
            "failure_mode": receipt.failure_mode,
            "fallback_used": receipt.fallback_used,
            "context_packet_ids": list(receipt.context_packet_ids),
        }
        for receipt in active_receipts
    ]
    slowest = max(active_receipts, key=lambda receipt: receipt.latency_ms, default=None)
    return {
        "receipt_count": len(active_receipts),
        "total_latency_ms": sum(receipt.latency_ms for receipt in active_receipts),
        "failure_count": sum(1 for receipt in active_receipts if receipt.outcome == "failed"),
        "fallback_count": sum(1 for receipt in active_receipts if receipt.fallback_used),
        "slowest_task": slowest.task if slowest is not None else None,
        "slowest_latency_ms": slowest.latency_ms if slowest is not None else 0,
        "context_packet_ids": _unique_context_packet_ids(active_receipts),
        "token_usage": _merged_receipt_token_usage(active_receipts),
        "route_waterfall": route_waterfall,
    }


def _unique_context_packet_ids(receipts: Iterable[OpenRouterRouteReceipt]) -> list[str]:
    normalized: list[str] = []
    for receipt in receipts:
        for packet_id in receipt.context_packet_ids:
            if packet_id and packet_id not in normalized:
                normalized.append(packet_id)
    return normalized


def _merged_receipt_token_usage(
    receipts: Iterable[OpenRouterRouteReceipt],
) -> dict[str, int] | None:
    merged: dict[str, int] | None = None
    for receipt in receipts:
        merged = merge_openrouter_token_usage(merged, receipt.token_usage)
    return merged
