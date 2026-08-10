"""Shared research-rail fixtures: hermetic provider shapes, no live calls."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest


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
    model: str = "openai/gpt-5.6-sol",
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
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "tool_calls_details": tool_calls_details,
        },
    }
    if status is not None:
        document["status"] = status
    return document


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
