from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import httpx

from argus.domain.research.search.contracts import (
    MAX_RESULTS,
    SearchResult,
    SearchResultPacket,
    SearchUnavailableError,
    sanitize_search_result,
)
from argus.domain.research.search.http_post import post_json

PERPLEXITY_SEARCH_URL = "https://api.perplexity.ai/search"

# Documented fixed per-request Search fee; no LLM token charges on this path.
DOCUMENTED_PERPLEXITY_SEARCH_COST_USD = 0.005


class PerplexityDirectProvider:
    """Thin single-attempt adapter for the Perplexity Search API.

    Response shape confirmed against the official quickstart on 2026-07-26:
    POST {query, max_results} -> {"results": [{title, url, snippet,
    date|null, last_updated}]}.
    """

    def __init__(
        self,
        *,
        api_key: str,
        transport: httpx.BaseTransport | None = None,
        endpoint: str = PERPLEXITY_SEARCH_URL,
    ) -> None:
        self._api_key = api_key.strip()
        self._transport = transport
        self._endpoint = endpoint

    def search(
        self, query: str, *, max_results: int, timeout_seconds: float
    ) -> SearchResultPacket:
        self.require_configured()
        bounded_results = max(1, min(int(max_results), MAX_RESULTS))
        started = time.monotonic()
        payload = post_json(
            endpoint=self._endpoint,
            transport=self._transport,
            timeout_seconds=timeout_seconds,
            headers={"Authorization": f"Bearer {self._api_key}"},
            body={"query": query, "max_results": bounded_results},
        )
        latency_ms = int((time.monotonic() - started) * 1000)
        return SearchResultPacket(
            results=_sanitized_results(payload),
            retrieved_at=datetime.now(timezone.utc),
            latency_ms=latency_ms,
            provider_id="perplexity_direct",
            cost_usd=DOCUMENTED_PERPLEXITY_SEARCH_COST_USD,
        )

    def require_configured(self) -> None:
        """Fail before admission when this adapter cannot make a request."""
        if not self._api_key:
            raise SearchUnavailableError(reason="not_configured")


def _sanitized_results(payload: Any) -> list[SearchResult]:
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise SearchUnavailableError(reason="malformed_response")
    sanitized: list[SearchResult] = []
    for raw in payload["results"]:
        if not isinstance(raw, dict):
            continue
        result = sanitize_search_result(
            title=str(raw.get("title") or ""),
            url=str(raw.get("url") or ""),
            snippet=str(raw.get("snippet") or ""),
            source_date=_source_date(raw),
        )
        if result is not None:
            sanitized.append(result)
    return sanitized


def _source_date(raw: dict[str, Any]) -> str | None:
    value = raw.get("last_updated") or raw.get("date")
    return None if value is None else str(value)
