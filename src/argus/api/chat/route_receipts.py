from __future__ import annotations

from typing import Any

from loguru import logger

from argus.api import state as api_state
from argus.llm.openrouter import OpenRouterRouteReceipt
from argus.observability.cost_ledger import persist_openrouter_cost_ledger_entries


def persist_route_receipts(
    *,
    receipts: list[OpenRouterRouteReceipt],
    user_id: str,
    conversation_id: str,
    run_id: str | None = None,
    message_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    if not receipts or api_state.supabase_gateway is None:
        return
    for receipt in receipts:
        try:
            created = api_state.supabase_gateway.create_route_receipt(
                user_id=user_id,
                conversation_id=conversation_id,
                run_id=run_id,
                message_id=message_id,
                metadata=metadata,
                receipt=receipt.as_dict(),
            )
            request_id = str((metadata or {}).get("request_id") or "").strip() or None
            persist_openrouter_cost_ledger_entries(
                gateway=api_state.supabase_gateway,
                receipts=[receipt],
                source="api_turn",
                feature_area="chat_runtime",
                user_id=user_id,
                conversation_id=conversation_id,
                message_id=message_id,
                backtest_run_id=run_id,
                route_receipt_rows=[created],
                request_id=request_id,
                metadata=metadata,
            )
        except Exception as exc:
            logger.warning(
                "Route receipt persistence failed; using in-memory receipt only",
                error=str(exc),
                user_id=user_id,
                conversation_id=conversation_id,
                llm_task=receipt.task,
            )
