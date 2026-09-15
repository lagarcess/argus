"""Opt-in measurement HTTP guard; never imported by the product runtime.

One persistent ledger covers all subprocesses and both providers. Reservations
are conditional on providers honoring their generation/context/tool bounds.
Unknown invoices retain the reservation and stop further dispatch.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import math
import time
from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from typing import Any
from unittest.mock import patch

import httpx

MAX_BUDGET_USD = 12.50
MAX_DURATION_SECONDS = 1800
ENDPOINTS = {
    "https://openrouter.ai/api/v1/chat/completions": "openrouter",
    "https://api.perplexity.ai/v1/agent": "perplexity_agent",
}
_LOCK = RLock()


def _encoded(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False).encode()


def _hash(value: Any) -> str:
    return hashlib.sha256(_encoded(value)).hexdigest()


def _number(value: Any, *, positive: bool = False) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(value)
        or value < 0
        or (positive and value == 0)
    ):
        raise ValueError("invalid_bound_or_price")
    return float(value)


def request_models(provider: str, payload: dict[str, Any]) -> list[str]:
    models = payload.get("models") if provider == "perplexity_agent" else None
    if models is None:
        models = [payload.get("model")]
    if (
        not isinstance(models, list)
        or not models
        or not all(isinstance(model, str) and model for model in models)
    ):
        raise ValueError("model_identity_required")
    return models


def request_reservation(provider: str, payload: dict[str, Any], rates: dict) -> float:
    """Reserve the highest complete per-model ceiling, independent of list order."""
    if provider not in {"openrouter", "perplexity_agent"}:
        raise ValueError("unexpected_provider")
    models = request_models(provider, payload)
    ceilings = []
    for model in models:
        rate = rates.get(provider, {}).get(model)
        if rate is None:
            raise ValueError(f"unpriced_model:{model}")
        input_rate = _number(rate.get("input_per_million"))
        output_rate = _number(rate.get("output_per_million"))
        output = _number(
            payload.get(
                "max_tokens" if provider == "openrouter" else "max_output_tokens"
            ),
            positive=True,
        )
        if provider == "openrouter":
            if payload.get("tools") or payload.get("plugins"):
                raise ValueError("unbounded_openrouter_tools")
            # UTF-8 bytes bound input tokens conservatively; add chat framing.
            inputs = len(_encoded(payload)) + 4096
            ceilings.append((inputs * input_rate + output * output_rate) / 1_000_000)
            continue
        if any(
            payload.get(key)
            for key in (
                "preset",
                "profile",
                "background",
                "previous_response_id",
                "skills",
                "stream",
            )
        ):
            raise ValueError("unbounded_agent_work")
        steps = _number(payload.get("max_steps", 1), positive=True) + 1
        context = _number(rate.get("context_window_tokens"), positive=True)
        tools = payload.get("tools", [])
        tool_rates = []
        for tool in tools:
            name = tool.get("type")
            if name not in rates.get("tools", {}):
                raise ValueError(f"unpriced_tool:{name}")
            tool_rates.append(_number(rates["tools"][name]))
        # Without an explicit tool-call limit, reserve every generated token as
        # a possible tool invocation. This deliberately may exceed the cap.
        calls = _number(payload.get("max_tool_calls", steps * output)) if tools else 0
        ceilings.append(
            steps * (context * input_rate + output * output_rate) / 1_000_000
            + calls * max(tool_rates, default=0)
        )
    return max(ceilings)


def initialize_budget(
    path: Path,
    rates: dict,
    *,
    budget_usd: float = MAX_BUDGET_USD,
    duration_seconds: float = MAX_DURATION_SECONDS,
) -> dict:
    budget = _number(budget_usd, positive=True)
    duration = _number(duration_seconds, positive=True)
    if budget > MAX_BUDGET_USD or duration > MAX_DURATION_SECONDS:
        raise ValueError("approved_cap_exceeded")
    started = time.time()
    state = {
        "budget_usd": budget,
        "started_epoch": started,
        "deadline_epoch": started + duration,
        "rates_sha256": _hash(rates),
        "charged_usd": 0,
        "stopped": False,
        "stop_reason": None,
        "requests": [],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(state, stream)
    path.chmod(0o600)
    return state


def read_budget(path: Path) -> dict:
    with _ledger(path) as state:
        return json.loads(json.dumps(state))


@contextmanager
def _ledger(path: Path):
    with _LOCK, path.open("r+") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        state = json.load(stream)
        try:
            yield state
        finally:
            stream.seek(0)
            json.dump(state, stream)
            stream.truncate()
            stream.flush()
            fcntl.flock(stream, fcntl.LOCK_UN)


def _stop(state: dict, reason: str) -> None:
    state.update(stopped=True, stop_reason=reason)


@contextmanager
def guard_http(path: Path, rates: dict, *, live: bool, scope: str):
    """Reserve before the real client's HTTP dispatch; fail closed on any error.

    No headers or exception strings are recorded. Authored requests and provider
    JSON are private measurement traces; sanitize before committing evidence.
    """
    original_sync, original_async = httpx.Client.request, httpx.AsyncClient.request

    def before(client, method, url, kwargs):
        provider = ENDPOINTS.get(str(url))
        if not live:
            raise ValueError("measurement_go_required")
        if provider is None:
            # Native eval market-data checks are read-only and are not LLM work.
            if method.upper() == "GET" and httpx.URL(url).host in {
                "data.alpaca.markets",
                "api.alpaca.markets",
                "paper-api.alpaca.markets",
            }:
                return None
            with _ledger(path) as state:
                _stop(state, "unexpected_measurement_endpoint")
            raise ValueError("unexpected_measurement_endpoint")
        payload = kwargs.get("json", {})
        with _ledger(path) as state:
            try:
                if state["stopped"]:
                    raise ValueError("measurement_stopped")
                if time.time() >= state["deadline_epoch"]:
                    raise ValueError("measurement_deadline")
                if state["rates_sha256"] != _hash(rates):
                    raise ValueError("measurement_rates_changed")
                if method.upper() != "POST":
                    raise ValueError("unexpected_measurement_method")
                if any(row["status"] == "pending" for row in state["requests"]):
                    raise ValueError("parallel_paid_dispatch_forbidden")
                if any(
                    row["scope"] == scope and row["payload_sha256"] == _hash(payload)
                    for row in state["requests"]
                ):
                    raise ValueError("automatic_retry_forbidden")
                reserve = request_reservation(provider, payload, rates)
                if state["charged_usd"] + reserve > state["budget_usd"]:
                    raise ValueError("measurement_budget_exceeded")
            except ValueError as exc:
                if not state["stopped"]:
                    _stop(state, str(exc))
                raise
            row = {
                "request_id": len(state["requests"]) + 1,
                "scope": scope,
                "provider": provider,
                "models": request_models(provider, payload),
                "reservation_usd": reserve,
                "cost_usd": None,
                "status": "pending",
                "payload_sha256": _hash(payload),
                "request": payload,
            }
            state["requests"].append(row)
            state["charged_usd"] += reserve
            # Keep a network wait from crossing the combined wall-clock cap.
            remaining = state["deadline_epoch"] - time.time()
            timeout = kwargs.get("timeout")
            configured = (
                httpx.Timeout(timeout)
                if isinstance(timeout, (httpx.Timeout, int, float))
                else client.timeout
            )
            kwargs["timeout"] = httpx.Timeout(
                **{
                    key: min(value if value is not None else remaining, remaining)
                    for key, value in configured.as_dict().items()
                }
            )
            return row["request_id"]

    def after(request_id, response=None, *, failure=None):
        if request_id is None:
            return response
        with _ledger(path) as state:
            row = state["requests"][request_id - 1]
            row["status"] = "failed" if failure else "completed"
            if failure:
                _stop(state, "provider_request_failed")
                return None
            try:
                body = response.json()
            except ValueError:
                body = {}
            row.update(response=body, http_status=response.status_code)
            usage = body.get("usage", {}) if isinstance(body, dict) else {}
            cost = usage.get("cost") if isinstance(usage, dict) else None
            if row["provider"] == "perplexity_agent":
                cost = (
                    cost.get("total_cost")
                    if isinstance(cost, dict) and cost.get("currency") == "USD"
                    else None
                )
            try:
                cost = _number(cost)
            except ValueError:
                _stop(state, "unknown_provider_cost")
            else:
                row["cost_usd"] = cost
                state["charged_usd"] += cost - row["reservation_usd"]
                if cost > row["reservation_usd"]:
                    _stop(state, "provider_cost_exceeds_reservation")
            if not response.is_success:
                _stop(state, f"provider_http_{response.status_code}")
            if time.time() >= state["deadline_epoch"]:
                _stop(state, "measurement_deadline")
            if state["stopped"]:
                raise ValueError(state["stop_reason"])
        return response

    def sync_request(client, method, url, **kwargs):
        request_id = before(client, method, url, kwargs)
        try:
            response = original_sync(client, method, url, **kwargs)
        except BaseException:
            after(request_id, failure=True)
            raise
        return after(request_id, response)

    async def async_request(client, method, url, **kwargs):
        request_id = before(client, method, url, kwargs)
        try:
            response = await original_async(client, method, url, **kwargs)
        except BaseException:
            after(request_id, failure=True)
            raise
        return after(request_id, response)

    with (
        patch.object(httpx.Client, "request", sync_request),
        patch.object(httpx.AsyncClient, "request", async_request),
    ):
        yield
