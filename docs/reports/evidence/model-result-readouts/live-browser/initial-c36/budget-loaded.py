"""QA-only all-attempt dollar guard. No application source is changed."""
from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

# Captain verified public endpoint maxima on 2026-09-10, USD per million.
# Double input envelopes reserve cache-write premiums and framing uncertainty.
RATES = {
    "x-ai/grok-4.3": ("2.50", "5.00"),
    "anthropic/claude-haiku-4.5": ("1.10", "5.50"),
    "google/gemini-2.5-flash-lite": ("0.18", "0.72"),
    "deepseek/deepseek-v4-flash": ("0.21", "0.56"),
    "qwen/qwen3.5-9b": ("0.17", "0.25"),
    "openai/gpt-oss-120b": ("0.35", "0.95"),
}


class Budget:
    def __init__(self, output: Path, cap: str = "1.00") -> None:
        self.output = output
        self.cap = Decimal(cap)
        self.lock = threading.Lock()
        self.attempts: list[dict[str, Any]] = []
        self.halted: str | None = None
        self.case = "startup"

    def _flush(self) -> None:
        self.output.write_text(json.dumps(self.summary(), indent=2) + "\n")

    def summary(self) -> dict[str, Any]:
        priced = sum((Decimal(row["cost_usd"]) for row in self.attempts if row.get("cost_usd") is not None), Decimal(0))
        unresolved = sum((Decimal(row["reservation_usd"]) for row in self.attempts if row.get("cost_usd") is None), Decimal(0))
        return {"cap_usd": str(self.cap), "reported_cost_usd": str(priced), "unreconciled_reservation_usd": str(unresolved), "remaining_usd": str(self.cap - priced - unresolved), "halted": self.halted, "attempt_count": len(self.attempts), "attempts": self.attempts}

    def reserve(self, payload: dict[str, Any]) -> int:
        with self.lock:
            if self.halted:
                raise RuntimeError(f"Live browser budget halted: {self.halted}")
            model = payload.get("model")
            output = payload.get("max_tokens") or payload.get("max_completion_tokens")
            raw = json.dumps(payload, ensure_ascii=True).encode()
            tokens = len(raw) + 2048
            if model not in RATES or not isinstance(output, int) or output <= 0 or payload.get("stream") or payload.get("plugins") or tokens + output >= 200_000:
                self.halted = "unpriced_or_unbounded_request"
                self._flush()
                raise RuntimeError(self.halted)
            input_rate, output_rate = (Decimal(value) for value in RATES[model])
            reservation = (Decimal(tokens) * input_rate * 2 + Decimal(output) * output_rate) / Decimal(1_000_000)
            if reservation > Decimal(self.summary()["remaining_usd"]):
                self.halted = "insufficient_remaining_reservation"
                self._flush()
                raise RuntimeError(self.halted)
            index = len(self.attempts)
            self.attempts.append({"attempt": index + 1, "case": self.case, "started_at": datetime.now(timezone.utc).isoformat(), "model": model, "schema": ((payload.get("response_format") or {}).get("json_schema") or {}).get("name"), "request_sha256": hashlib.sha256(raw).hexdigest(), "input_token_upper_bound": tokens, "max_output_tokens": output, "reservation_usd": str(reservation), "cost_usd": None, "outcome": "in_flight"})
            self._flush()
            return index

    def finish(self, index: int, data: dict[str, Any] | None, status: int | None, error: str | None = None) -> None:
        with self.lock:
            row = self.attempts[index]
            usage = (data or {}).get("usage") or {}
            raw_cost = usage.get("cost")
            try:
                cost = Decimal(str(raw_cost))
                if not cost.is_finite() or cost < 0:
                    raise ValueError
            except Exception:
                cost = None
                self.halted = "unpriced_completed_attempt"
            row.update(finished_at=datetime.now(timezone.utc).isoformat(), status=status, generation_id=(data or {}).get("id"), served_model=(data or {}).get("model"), usage=usage, cost_usd=str(cost) if cost is not None else None, error_class=error, outcome="response" if data is not None else "transport_error")
            if row.get("schema") in {"QuickTakeDraft", "ResultBreakdownDraft"}:
                choices = (data or {}).get("choices") or []
                row["readout_raw_completion"] = (choices[0].get("message") or {}).get("content") if choices else None
            if cost is not None and cost > Decimal(row["reservation_usd"]):
                self.halted = "provider_cost_exceeded_reservation"
            self._flush()


def install_http_budget(budget: Budget, provider_requests: list[dict[str, Any]]) -> None:
    import httpx
    import requests

    def allowed(method: str, host: str, path: str) -> bool:
        if host in {"127.0.0.1", "localhost", "::1"}:
            return False
        if host == "openrouter.ai" and method == "POST" and path == "/api/v1/chat/completions":
            return True
        if host in {"data.alpaca.markets", "paper-api.alpaca.markets", "api.alpaca.markets"} and method == "GET":
            provider_requests.append({"host": host, "path": path, "method": method})
            return False
        raise RuntimeError("Live browser harness blocked an unapproved external request")

    original_sync = httpx.Client.send
    original_async = httpx.AsyncClient.send

    def sync_send(client: Any, request: Any, **kwargs: Any) -> Any:
        if not allowed(request.method, request.url.host, request.url.path):
            return original_sync(client, request, **kwargs)
        index = budget.reserve(json.loads(request.content))
        try:
            response = original_sync(client, request, **kwargs)
            response.read()
            try:
                data = response.json()
            except Exception:
                data = None
            budget.finish(index, data, response.status_code)
            return response
        except Exception as exc:
            if budget.attempts[index]["outcome"] == "in_flight":
                budget.finish(index, None, None, type(exc).__name__)
            raise

    async def async_send(client: Any, request: Any, **kwargs: Any) -> Any:
        if not allowed(request.method, request.url.host, request.url.path):
            return await original_async(client, request, **kwargs)
        index = budget.reserve(json.loads(request.content))
        try:
            response = await original_async(client, request, **kwargs)
            await response.aread()
            try:
                data = response.json()
            except Exception:
                data = None
            budget.finish(index, data, response.status_code)
            return response
        except Exception as exc:
            if budget.attempts[index]["outcome"] == "in_flight":
                budget.finish(index, None, None, type(exc).__name__)
            raise

    original_requests = requests.Session.request

    def requests_send(session: Any, method: str, url: str, **kwargs: Any) -> Any:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if allowed(method.upper(), parsed.hostname or "", parsed.path):
            raise RuntimeError("Unexpected completion transport")
        return original_requests(session, method, url, **kwargs)

    httpx.Client.send = sync_send
    httpx.AsyncClient.send = async_send
    requests.Session.request = requests_send
