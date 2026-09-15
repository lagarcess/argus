"""Measurement-only transport admission and durable, content-free spend ledger.

Reservations are admission estimates, never provider-enforced invoice ceilings.
The fatal stop deliberately bypasses production ``except Exception`` fallbacks.
"""

from __future__ import annotations

import json
import os
import re
import threading
from collections import Counter
from contextlib import contextmanager
from contextvars import ContextVar
from decimal import Decimal
from pathlib import Path
from typing import Iterator

import httpx
from argus.domain.research.perplexity_agent import (
    PerplexityAgentClient,
    _usage_from_response,
)
from argus.domain.research.pricing import MODEL_RATE_TABLE_USD_PER_MILLION
from argus.domain.research.search.perplexity_direct import (
    DOCUMENTED_PERPLEXITY_SEARCH_COST_USD,
)
from argus.llm.openrouter_usage import openrouter_usage_cost_from_payload

PROPOSAL = Path(__file__).resolve().parents[2] / (
    "docs/reports/evidence/calculation-followups/measurement-budget-proposal.md"
)
LIMITS = {"agent": Decimal("8"), "openrouter": Decimal("4"), "search": Decimal("3")}
RESERVATIONS = {
    "agent": Decimal("1.50"),
    "openrouter": Decimal("0.10"),
    "search": Decimal(str(DOCUMENTED_PERPLEXITY_SEARCH_COST_USD)),
}
TOTAL_LIMIT = sum(LIMITS.values())


class MeasurementBudgetStop(BaseException):
    """The entire paid run must stop, retaining partial evidence."""


class MeasurementBudget:
    def __init__(self, path: Path, case_ids: set[str]) -> None:
        case_ids = set(case_ids)
        blocks = re.findall(r"```text\n(.*?)\n```", PROPOSAL.read_text(), re.DOTALL)
        if len(blocks) != 3:
            raise ValueError("approved measurement scope must contain three allowlists")
        self.agent_cases, self.search_cases, self.no_research_cases = (
            frozenset(block.splitlines()) for block in blocks
        )
        if tuple(
            map(len, (self.agent_cases, self.search_cases, self.no_research_cases))
        ) != (16, 9, 14):
            raise ValueError("approved measurement scope changed")
        if (
            not (self.agent_cases | self.search_cases | self.no_research_cases)
            <= case_ids
        ):
            raise ValueError("approved scope missing from fixture cases")
        if self.no_research_cases & (self.agent_cases | self.search_cases):
            raise ValueError("conflicting research allowances")
        self.case_ids = frozenset(case_ids)
        self._case: ContextVar[str | None] = ContextVar(
            "measurement_budget_case", default=None
        )
        self._lock = threading.RLock()
        self._stopped: str | None = None
        self._settled = dict.fromkeys(LIMITS, Decimal(0))
        self._pending: dict[int, tuple[str, str, Decimal]] = {}
        self._sends: Counter[tuple[str, str]] = Counter()
        self._attempts: Counter[tuple[str, str]] = Counter()
        self._sequence = 0
        self._agent_applications: Counter[str] = Counter()
        path.parent.mkdir(parents=True, exist_ok=True)
        # Never silently append a new run to another run's admission ledger.
        self._file = path.open("x", encoding="utf-8")
        self._event("started", total_limit_usd=str(TOTAL_LIMIT))

    @contextmanager
    def case(self, case_id: str) -> Iterator[None]:
        if case_id not in self.case_ids:
            raise ValueError("unknown measurement case")
        token = self._case.set(case_id)
        try:
            self.check()
            yield
            self.check()
            with self._lock:
                if self._pending:
                    self._stop("outstanding_invoice_at_case_end")
        finally:
            self._case.reset(token)

    def _event(self, event: str, **data: object) -> None:
        self._file.write(json.dumps({"event": event, **data}, sort_keys=True) + "\n")
        self._file.flush()
        os.fsync(self._file.fileno())

    def _stop(self, reason: str) -> None:
        if self._stopped is None:
            self._stopped = reason
            self._event("stopped", reason=reason, **self.snapshot())
        raise MeasurementBudgetStop(self._stopped)

    def check(self) -> None:
        with self._lock:
            if self._stopped:
                raise MeasurementBudgetStop(self._stopped)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "stop_reason": self._stopped,
                "settled_usd": {k: str(v) for k, v in self._settled.items()},
                "total_settled_usd": str(sum(self._settled.values())),
                "outstanding_sends": len(self._pending),
                "sends": [
                    {"case_id": case, "provider": pool, "count": count}
                    for (case, pool), count in sorted(self._sends.items())
                ],
                "attempts": [
                    {"case_id": case, "provider": pool, "count": count}
                    for (case, pool), count in sorted(self._attempts.items())
                ],
            }

    def agent_application(self) -> None:
        with self._lock:
            self.check()
            case = self._case.get()
            if case is None:
                self._stop("paid_send_outside_case")
            self._agent_applications[case] += 1
            self._event(
                "agent_application", case_id=case, count=self._agent_applications[case]
            )
            if self._agent_applications[case] > 1:
                self._stop("agent_application_retry_denied")

    def agent_reservation(self, body: dict) -> Decimal:
        """Estimate every fallback at its highest rate; retain the approved floor.

        Four bytes per token estimates the initial request, repeated per step.
        Retrieved context and internal tool work are not bounded by that estimate.
        The response invoice, never this reservation, owns actual spend.
        """
        models = body.get("models")
        if not isinstance(models, list) or not models:
            self._stop("invalid_agent_request_models")
        if any(
            not isinstance(model, str) or model not in MODEL_RATE_TABLE_USD_PER_MILLION
            for model in models
        ):
            self._stop("unpriced_agent_request_model")
        steps, output = body.get("max_steps"), body.get("max_output_tokens")
        if any(
            not isinstance(value, int) or isinstance(value, bool) or value <= 0
            for value in (steps, output)
        ):
            self._stop("invalid_agent_request_limits")
        input_tokens = Decimal(len(json.dumps(body).encode("utf-8"))) / 4
        estimates = [
            Decimal(steps)
            * (
                input_tokens
                * max(
                    rate.input_usd_per_million, rate.cache_creation_input_usd_per_million
                )
                + Decimal(output) * rate.output_usd_per_million
            )
            / 1_000_000
            for model in models
            for rate in MODEL_RATE_TABLE_USD_PER_MILLION[model]
        ]
        return max(RESERVATIONS["agent"], *estimates)

    def admit(self, pool: str, request: httpx.Request | None = None) -> int:
        with self._lock:
            self.check()
            case = self._case.get()
            if case is None:
                self._stop("paid_send_outside_case")
            assert case is not None
            self._attempts[case, pool] += 1
            self._event("attempt", case_id=case, provider=pool)
            if pool in ("agent", "search") and case in self.no_research_cases:
                self._stop("no_new_facts_research_attempt")
            if pool == "agent":
                if case not in self.agent_cases:
                    self._stop("agent_case_not_allowed")
                if self._sends[case, pool]:
                    self._stop("agent_retry_denied")
                if sum(n for (_, p), n in self._sends.items() if p == pool) >= 16:
                    self._stop("agent_send_limit")
                if any(p == pool for _, p, _ in self._pending.values()):
                    self._stop("agent_request_still_outstanding")
            if pool == "search" and case not in self.search_cases:
                self._stop("search_case_not_allowed")
            if any(p == "agent" for _, p, _ in self._pending.values()):
                self._stop("agent_request_still_outstanding")
            reserved = sum(v for _, p, v in self._pending.values() if p == pool)
            reservation = RESERVATIONS[pool]
            if pool == "agent" and request is not None:
                try:
                    body = json.loads(request.content)
                except (ValueError, UnicodeError):
                    self._stop("invalid_agent_request_body")
                if not isinstance(body, dict):
                    self._stop("invalid_agent_request_body")
                reservation = self.agent_reservation(body)
            if self._settled[pool] + reserved + reservation > LIMITS[pool]:
                self._stop("provider_admission_budget")
            total = sum(self._settled.values()) + sum(
                v for _, _, v in self._pending.values()
            )
            if total + reservation > TOTAL_LIMIT:
                self._stop("total_admission_budget")
            self._sequence += 1
            self._pending[self._sequence] = (case, pool, reservation)
            self._sends[case, pool] += 1
            self._event(
                "send",
                send_id=self._sequence,
                case_id=case,
                provider=pool,
                reservation_usd=str(reservation),
            )
            return self._sequence

    def uncertain(self, send_id: int) -> None:
        with self._lock:
            self._event("unresolved_invoice", send_id=send_id)
            self._stop("unresolved_invoice")

    def settle(self, send_id: int, cost: object) -> None:
        with self._lock:
            if send_id not in self._pending:
                self._stop("duplicate_or_unknown_settlement")
            try:
                amount = Decimal(str(cost))
            except Exception:
                self.uncertain(send_id)
            if not amount.is_finite() or amount < 0 or isinstance(cost, bool):
                self.uncertain(send_id)
            case, pool, reservation = self._pending.pop(send_id)
            self._settled[pool] += amount
            self._event(
                "invoice",
                send_id=send_id,
                case_id=case,
                provider=pool,
                cost_usd=str(amount),
            )
            if pool == "agent" and amount > RESERVATIONS["agent"]:
                self._stop("agent_invoice_exceeds_reservation")
            if (
                self._settled[pool] >= LIMITS[pool]
                or sum(self._settled.values()) >= TOTAL_LIMIT
            ):
                self._stop("settled_budget_exhausted")
            self.check()

    def assert_complete(self) -> None:
        with self._lock:
            self.check()
            if self._pending:
                self._stop("outstanding_invoice_at_completion")
            self._event("complete", **self.snapshot())

    def close(self) -> None:
        with self._lock:
            self._file.close()

    def _pool(self, request: httpx.Request) -> str | None:
        host, path = request.url.host, request.url.path.rstrip("/")
        if host not in ("api.perplexity.ai", "openrouter.ai"):
            return None
        if request.method == "POST":
            if host == "api.perplexity.ai" and path == "/v1/agent":
                return "agent"
            if host == "api.perplexity.ai" and path == "/search":
                return "search"
            if host == "openrouter.ai" and path == "/api/v1/chat/completions":
                return "openrouter"
        with self._lock:
            self._stop("unbudgeted_provider_endpoint")
        return None

    def _invoice(self, send_id: int, pool: str, response: httpx.Response) -> None:
        if pool == "search":
            # Search has a documented fixed request fee, not a token invoice.
            self.settle(send_id, DOCUMENTED_PERPLEXITY_SEARCH_COST_USD)
            if response.status_code >= 400:
                with self._lock:
                    self._stop("search_http_error")
            return
        try:
            if "text/event-stream" in response.headers.get("content-type", ""):
                documents = [
                    json.loads(line[5:].strip())
                    for line in response.text.splitlines()
                    if line.startswith("data:") and line[5:].strip() not in ("", "[DONE]")
                ]
                invoices = [
                    item
                    for item in documents
                    if isinstance(item, dict) and item.get("usage")
                ]
                if len(invoices) != 1:
                    self.uncertain(send_id)
                document = invoices[0]
            else:
                document = response.json()
            if not isinstance(document, dict):
                self.uncertain(send_id)
            if pool == "agent":
                cost = _usage_from_response(
                    document, latency_ms=0, on_unpriced=lambda _: None
                ).cost_usd
            else:
                cost = openrouter_usage_cost_from_payload(document)
        except Exception:
            self.uncertain(send_id)
        self.settle(send_id, cost)
        if response.status_code >= 400:
            with self._lock:
                self._stop("provider_http_error")

    def install(self, monkeypatch: object) -> None:
        """Patch the actual HTTPX transport boundary, below retry/fallback owners."""
        sync_send = httpx.Client._send_single_request
        async_send = httpx.AsyncClient._send_single_request
        budget = self
        agent_post = PerplexityAgentClient._post

        def post(
            client: PerplexityAgentClient, payload: dict, *, timeout_seconds: float
        ) -> dict:
            budget.agent_application()
            return agent_post(client, payload, timeout_seconds=timeout_seconds)

        monkeypatch.setattr(PerplexityAgentClient, "_post", post)

        def send(client: httpx.Client, request: httpx.Request) -> httpx.Response:
            pool = budget._pool(request)
            if pool is None:
                return sync_send(client, request)
            send_id = budget.admit(pool, request)
            try:
                response = sync_send(client, request)
                response.read()
            except BaseException:
                budget.uncertain(send_id)
                raise
            budget._invoice(send_id, pool, response)
            return response

        async def asend(
            client: httpx.AsyncClient, request: httpx.Request
        ) -> httpx.Response:
            pool = budget._pool(request)
            if pool is None:
                return await async_send(client, request)
            send_id = budget.admit(pool, request)
            try:
                response = await async_send(client, request)
                await response.aread()
            except BaseException:
                budget.uncertain(send_id)
                raise
            budget._invoice(send_id, pool, response)
            return response

        monkeypatch.setattr(httpx.Client, "_send_single_request", send)
        monkeypatch.setattr(httpx.AsyncClient, "_send_single_request", asend)
