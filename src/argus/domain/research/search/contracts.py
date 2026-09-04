from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

MAX_TITLE_CHARS = 200
MAX_SNIPPET_CHARS = 1000
MAX_URL_CHARS = 512
MAX_RESULTS = 5

SearchUnavailableReason = Literal[
    "not_configured",
    "authentication_failed",
    "timeout",
    "http_error",
    "malformed_response",
]

_ALLOWED_UNAVAILABLE_REASONS: frozenset[str] = frozenset(
    (
        "not_configured",
        "authentication_failed",
        "timeout",
        "http_error",
        "malformed_response",
    )
)


class SearchUnavailableError(Exception):
    """Typed single-attempt Search failure; the composer maps it to recovery."""

    def __init__(self, *, reason: str, detail: str | None = None) -> None:
        if reason not in _ALLOWED_UNAVAILABLE_REASONS:
            raise ValueError(f"unknown search unavailable reason: {reason}")
        super().__init__(reason if detail is None else f"{reason}: {detail}")
        self.reason: SearchUnavailableReason = reason  # type: ignore[assignment]
        self.detail = detail


class SearchResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str = Field(min_length=1, max_length=MAX_TITLE_CHARS)
    url: str = Field(min_length=len("https://x"), max_length=MAX_URL_CHARS)
    snippet: str = Field(max_length=MAX_SNIPPET_CHARS)
    source_date: str | None = None


class SearchResultPacket(BaseModel):
    model_config = ConfigDict(frozen=True)

    results: tuple[SearchResult, ...] = ()
    retrieved_at: datetime
    latency_ms: int = Field(ge=0)
    provider_id: str
    cost_usd: float | None = Field(default=None, ge=0.0)

    def __init__(self, **data: object) -> None:
        results = data.get("results")
        if isinstance(results, (list, tuple)):
            data["results"] = tuple(results)[:MAX_RESULTS]
        super().__init__(**data)


@runtime_checkable
class SearchProvider(Protocol):
    def require_configured(self) -> None: ...

    def search(
        self, query: str, *, max_results: int, timeout_seconds: float
    ) -> SearchResultPacket: ...


def _strip_control_characters(value: str) -> str:
    return "".join(char for char in value if char >= " " and char != "\x7f")


def _normalized_source_date(raw: str | None) -> str | None:
    if raw is None:
        return None
    candidate = raw.strip()
    if not candidate:
        return None
    try:
        return date.fromisoformat(candidate[:10]).isoformat()
    except ValueError:
        return None


def sanitize_search_result(
    *,
    title: str,
    url: str,
    snippet: str,
    source_date: str | None = None,
) -> SearchResult | None:
    """Bound one untrusted provider result; None means drop it entirely."""
    cleaned_url = _strip_control_characters(url or "").strip()
    if not cleaned_url.startswith("https://") or len(cleaned_url) > MAX_URL_CHARS:
        return None
    cleaned_title = _strip_control_characters(title or "").strip()[:MAX_TITLE_CHARS]
    cleaned_snippet = _strip_control_characters(snippet or "").strip()[:MAX_SNIPPET_CHARS]
    if not cleaned_title:
        return None
    return SearchResult(
        title=cleaned_title,
        url=cleaned_url,
        snippet=cleaned_snippet,
        source_date=_normalized_source_date(source_date),
    )
