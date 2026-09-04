"""Persist disputed research invoices without claiming a reconciled charge."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from loguru import logger

from argus.api import state as api_state
from argus.domain.research.billing import UnpricedResearchSpend


class ResearchPricingRecorder:
    """A bounded API-owned writer; a database round-trip never gates the answer."""

    MAX_PENDING = 16

    def __init__(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._executor = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="research-invoices"
        )
        self._pending: dict[asyncio.Task[None], UnpricedResearchSpend] = {}
        self._closed = False

    def __call__(self, spend: UnpricedResearchSpend) -> None:
        # Provider callbacks run in asyncio.to_thread, outside the API loop.
        self._loop.call_soon_threadsafe(self._submit, spend)

    def _submit(self, spend: UnpricedResearchSpend) -> None:
        if self._closed or len(self._pending) >= self.MAX_PENDING:
            logger.error(
                "research_cost_unrecorded recorder=closed_or_full {}",
                spend.model_dump_json(),
            )
            return
        task = self._loop.create_task(self._persist(spend))
        self._pending[task] = spend
        task.add_done_callback(lambda completed: self._pending.pop(completed, None))

    async def _persist(self, spend: UnpricedResearchSpend) -> None:
        try:
            await self._loop.run_in_executor(
                self._executor, record_unpriced_research_spend, spend
            )
        except Exception:  # noqa: BLE001
            logger.error(
                "research_cost_unrecorded recorder=failed {}", spend.model_dump_json()
            )

    async def close(self) -> None:
        self._closed = True
        if self._pending:
            _, pending = await asyncio.wait(self._pending, timeout=2)
            for task in pending:
                logger.error(
                    "research_cost_persistence_pending_at_shutdown {}",
                    self._pending[task].model_dump_json(),
                )
        self._executor.shutdown(wait=False, cancel_futures=True)


def record_unpriced_research_spend(spend: UnpricedResearchSpend) -> None:
    gateway = api_state.supabase_gateway
    if gateway is None:
        raise RuntimeError("research cost ledger unavailable")
    report = spend.model_dump(mode="json")
    gateway.create_cost_ledger_entry(
        entry={
            "source": "research",
            "service": "perplexity_agent",
            "provider": "perplexity_agent",
            "model": spend.usage.model,
            "feature_area": "research_rail",
            "task": "invoice_reconciliation",
            "correlation_id": f"research:invoice:{spend.provider_response_id or uuid4()}",
            "provider_request_id": spend.provider_response_id,
            "input_tokens": spend.usage.input_tokens,
            "output_tokens": spend.usage.output_tokens,
            "billable_unit": "request",
            "billable_quantity": None,
            "cost_amount": None,
            "cost_currency": "USD",
            "cost_source": "unavailable",
            "latency_ms": spend.usage.latency_ms,
            "status": "succeeded",
            "usage_metadata": {"pricing_status": "unpriced", **report},
        }
    )
