from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import httpx

from argus.domain.discovery_search.contracts import (
    MAX_RESULTS,
    SearchResult,
    SearchResultPacket,
    SearchUnavailableError,
    sanitize_search_result,
)
from argus.domain.discovery_search.http_post import post_json

OPENROUTER_CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterWebSearchProvider:
    """Thin single-attempt adapter for OpenRouter's web plugin.

    Shape confirmed against the official plugin docs on 2026-07-26:
    `plugins: [{"id": "web", "max_results": N}]` on chat completions; citations
    arrive as `choices[0].message.annotations[].url_citation{url, title,
    content}` with no source-date guarantee. This supersedes the eval
    scaffold's beta `openrouter:web_search` server-tool assumption.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        transport: httpx.BaseTransport | None = None,
        endpoint: str = OPENROUTER_CHAT_COMPLETIONS_URL,
    ) -> None:
        self._api_key = api_key.strip()
        self._model = model.strip()
        self._transport = transport
        self._endpoint = endpoint

    def search(
        self, query: str, *, max_results: int, timeout_seconds: float
    ) -> SearchResultPacket:
        if not self._api_key or not self._model:
            raise SearchUnavailableError(reason="not_configured")
        bounded_results = max(1, min(int(max_results), MAX_RESULTS))
        started = time.monotonic()
        payload = post_json(
            endpoint=self._endpoint,
            transport=self._transport,
            timeout_seconds=timeout_seconds,
            headers={"Authorization": f"Bearer {self._api_key}"},
            body={
                "model": self._model,
                "messages": [{"role": "user", "content": query}],
                "plugins": [{"id": "web", "max_results": bounded_results}],
            },
        )
        latency_ms = int((time.monotonic() - started) * 1000)
        return SearchResultPacket(
            results=_sanitized_citations(payload),
            retrieved_at=datetime.now(timezone.utc),
            latency_ms=latency_ms,
            provider_id="openrouter_web_search",
            cost_usd=_reported_cost(payload),
        )


def _message(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        choices = payload.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            message = choices[0].get("message")
            if isinstance(message, dict):
                return message
    raise SearchUnavailableError(reason="malformed_response")


def _sanitized_citations(payload: Any) -> list[SearchResult]:
    message = _message(payload)
    annotations = message.get("annotations")
    if not isinstance(annotations, list):
        annotations = []
    message_content = message.get("content")
    if not isinstance(message_content, str):
        message_content = ""
    sanitized: list[SearchResult] = []
    for annotation in annotations:
        if not isinstance(annotation, dict):
            continue
        citation = annotation.get("url_citation", annotation)
        if not isinstance(citation, dict):
            continue
        result = sanitize_search_result(
            title=str(citation.get("title") or ""),
            url=str(citation.get("url") or ""),
            snippet=str(citation.get("content") or "")
            or _cited_message_context(message_content, citation),
            source_date=None,
        )
        if result is not None:
            sanitized.append(result)
    return sanitized


def _cited_message_context(content: str, citation: dict[str, Any]) -> str:
    """Recover bounded evidence when OpenRouter omits citation content."""
    start = citation.get("start_index")
    end = citation.get("end_index")
    if (
        isinstance(start, bool)
        or isinstance(end, bool)
        or not isinstance(start, int)
        or not isinstance(end, int)
        or start < 0
        or end < start
        or end > len(content)
    ):
        return ""
    return content[start:end]


def _reported_cost(payload: Any) -> float | None:
    if not isinstance(payload, dict):
        return None
    usage = payload.get("usage")
    if not isinstance(usage, dict) or usage.get("cost") is None:
        return None
    try:
        cost = float(usage["cost"])
    except (TypeError, ValueError):
        return None
    return cost if cost >= 0 else None
