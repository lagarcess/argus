"""Shared research-rail fixtures: hermetic provider shapes, no live calls."""

from __future__ import annotations

import json
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import httpx
import pytest
from argus.domain.research.pricing import (
    MODEL_RATE_TABLE_USD_PER_MILLION,
    TOOL_RATE_TABLE_USD_PER_INVOCATION,
)

_MILLION = Decimal(1_000_000)
_PROVIDER_COST_PRECISION = Decimal("0.00001")


@pytest.fixture(autouse=True)
def research_rail_on(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "true")
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "synthetic_unit_fixture")
    from argus.domain.research.cache import cache_clear

    cache_clear()
    yield
    cache_clear()


def agent_response(
    *,
    text: str = "Apple closed at $312.41 on 2026-08-06.",
    tickers: list[str] | None = None,
    lookup_rows: list[tuple[str, str, str]] | None = None,
    sources: list[str] | None = None,
    invocations: int = 1,
    web_search_invocations: int = 0,
    fetch_url_invocations: int = 0,
    input_tokens: int = 1_000,
    output_tokens: int = 500,
    cache_creation_input_tokens: int = 0,
    cache_read_input_tokens: int = 0,
    model: str = "openai/gpt-5.6-sol",
    cost_overrides: dict[str, Any] | None = None,
    response_id: str = "resp_test",
    status: str | None = None,
) -> dict[str, Any]:
    """A Perplexity Agent API response in the documented output shape."""
    results: list[dict[str, Any]] = [
        {
            "category": "quote",
            "content": "## Quote\n| symbol | price |\n| --- | --- |\n| AAPL | 312.41 |",
            "sources": list(sources or []),
            "tickers": list(tickers or ["AAPL"]),
        }
    ]
    if lookup_rows:
        table = "Ticker matches:\n| query | ticker | name |\n| --- | --- | --- |\n"
        table += "\n".join(
            f"| {query} | {ticker} | {name} |" for query, ticker, name in lookup_rows
        )
        results.append({"category": "tickers_lookup", "content": table, "sources": []})
    tool_calls_details: dict[str, dict[str, int]] = {
        "finance_search": {"invocation": invocations}
    }
    if web_search_invocations:
        # The request tool is web_search; Agent API usage currently reports
        # the provider-owned response key as search_web.
        tool_calls_details["search_web"] = {"invocation": web_search_invocations}
    if fetch_url_invocations:
        tool_calls_details["fetch_url"] = {"invocation": fetch_url_invocations}
    cost = _agent_cost(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_input_tokens=cache_creation_input_tokens,
        cache_read_input_tokens=cache_read_input_tokens,
        finance_search_invocations=invocations,
        web_search_invocations=web_search_invocations,
        fetch_url_invocations=fetch_url_invocations,
    )
    if cost_overrides:
        cost.update(cost_overrides)
    document: dict[str, Any] = {
        "id": response_id,
        "model": model,
        "output": [
            {"type": "skill_loaded", "name": "finance"},
            {
                "type": "finance_results",
                "categories": [item["category"] for item in results],
                "tickers": list(tickers or ["AAPL"]),
                "results": results,
            },
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text}],
            },
        ],
        "usage": {
            "cost": cost,
            "input_tokens": input_tokens,
            "input_tokens_details": {
                "cache_creation_input_tokens": cache_creation_input_tokens,
                "cache_read_input_tokens": cache_read_input_tokens,
                "cached_tokens": cache_read_input_tokens,
            },
            "output_tokens": output_tokens,
            "output_tokens_details": {"reasoning_tokens": 0},
            "total_tokens": input_tokens + output_tokens,
            "tool_calls_details": tool_calls_details,
        },
    }
    if status is not None:
        document["status"] = status
    return document


def _agent_cost(
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_creation_input_tokens: int,
    cache_read_input_tokens: int,
    finance_search_invocations: int,
    web_search_invocations: int,
    fetch_url_invocations: int,
) -> dict[str, Any]:
    tiers = MODEL_RATE_TABLE_USD_PER_MILLION.get(
        model, MODEL_RATE_TABLE_USD_PER_MILLION["openai/gpt-5.6-sol"]
    )
    rate = next(
        tier
        for tier in tiers
        if tier.max_input_tokens is None or input_tokens <= tier.max_input_tokens
    )
    uncached_input_tokens = max(
        0, input_tokens - cache_creation_input_tokens - cache_read_input_tokens
    )
    input_cost = _token_cost(uncached_input_tokens, rate.input_usd_per_million)
    output_cost = _token_cost(output_tokens, rate.output_usd_per_million)
    cache_creation_cost = _token_cost(
        cache_creation_input_tokens, rate.cache_creation_input_usd_per_million
    )
    cache_read_cost = _token_cost(
        cache_read_input_tokens, rate.cache_read_input_usd_per_million
    )
    tool_cost_details = {
        "finance_search": Decimal(finance_search_invocations)
        * TOOL_RATE_TABLE_USD_PER_INVOCATION["finance_search"],
        "search_web": Decimal(web_search_invocations)
        * TOOL_RATE_TABLE_USD_PER_INVOCATION["web_search"],
        "fetch_url": Decimal(fetch_url_invocations)
        * TOOL_RATE_TABLE_USD_PER_INVOCATION["fetch_url"],
    }
    tool_calls_cost = sum(tool_cost_details.values(), start=Decimal(0))
    total_cost = sum(
        (
            input_cost,
            output_cost,
            cache_creation_cost,
            cache_read_cost,
            tool_calls_cost,
        ),
        start=Decimal(0),
    ).quantize(_PROVIDER_COST_PRECISION, rounding=ROUND_HALF_UP)
    cost: dict[str, Any] = {
        "currency": "USD",
        "input_cost": float(input_cost),
        "output_cost": float(output_cost),
        "cache_creation_cost": float(cache_creation_cost),
        "cache_read_cost": float(cache_read_cost),
        "total_cost": float(total_cost),
    }
    if tool_calls_cost:
        cost["tool_calls_cost"] = float(tool_calls_cost)
        cost["tool_calls_cost_details"] = {
            tool: float(value) for tool, value in tool_cost_details.items() if value
        }
    return cost


def _token_cost(tokens: int, rate: Decimal) -> Decimal:
    return (Decimal(tokens) * rate / _MILLION).quantize(
        _PROVIDER_COST_PRECISION, rounding=ROUND_HALF_UP
    )


class RecordingTransport(httpx.BaseTransport):
    """Serves canned agent documents and records every request."""

    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self.documents = list(documents)
        self.requests: list[httpx.Request] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if not self.documents:
            return httpx.Response(500, json={"error": "exhausted"})
        document = self.documents.pop(0)
        return httpx.Response(200, json=document)


def request_body(request: httpx.Request) -> dict[str, Any]:
    return json.loads(request.content.decode())


def set_research_query(monkeypatch, namespace, **fields):
    """Supply the primary interpretation at the router test boundary."""
    from argus.agent_runtime.research_query import ResearchQueryExtraction

    original = namespace["_interpretation"]
    query = ResearchQueryExtraction(**fields)

    def interpreted(*args, **kwargs):
        return original(*args, **kwargs).model_copy(update={"research_query": query})

    monkeypatch.setitem(namespace, "_interpretation", interpreted)
