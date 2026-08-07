"""Transit-only vectorization for confirmed memory text.

Memory text transits Perplexity for vectorization and nothing more: no memory
is stored with the vendor, and both the vectors and the memories live only in
the Argus Supabase database. Every failure is typed so retrieval degrades to
the canonical fallback instead of breaking a turn.
"""

from __future__ import annotations

import base64
import os
import struct
from decimal import Decimal
from typing import Any, Protocol

import httpx

PERPLEXITY_EMBEDDINGS_URL = "https://api.perplexity.ai/v1/embeddings"

# Contract confirmed against the official embeddings API reference on
# 2026-08-07: POST {input, model, dimensions?, encoding_format?} ->
# {"data": [{"embedding": <base64>}], "usage": {...}}.
DEFAULT_EMBEDDING_MODEL = "pplx-embed-v1-0.6b"
DEFAULT_EMBEDDING_DIMENSIONS = 1024
DEFAULT_EMBEDDING_TIMEOUT_SECONDS = 8.0

# int8 keeps the payload small and preserves cosine ordering; the vector store
# normalizes, so quantized components rank the same as full-precision ones.
EMBEDDING_ENCODING_FORMAT = "base64_int8"

# Documented list price for pplx-embed-v1-0.6b on 2026-08-07.
DOCUMENTED_EMBEDDING_COST_USD_PER_MILLION_TOKENS = Decimal("0.004")


class MemoryEmbeddingUnavailable(RuntimeError):
    """Vectorization failed; the caller degrades to canonical retrieval."""

    def __init__(self, reason: str, detail: str | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


class EmbeddingUsage:
    """Token and cost counters reported by one embedding call."""

    __slots__ = ("total_tokens", "reported_cost_usd")

    def __init__(
        self,
        *,
        total_tokens: int | None = None,
        reported_cost_usd: Decimal | None = None,
    ) -> None:
        self.total_tokens = total_tokens
        self.reported_cost_usd = reported_cost_usd


class MemoryEmbedder(Protocol):
    """Turns one memory text into one vector; never stores anything."""

    @property
    def dimensions(self) -> int: ...

    def embed(self, text: str) -> list[float]: ...

    def last_usage(self) -> EmbeddingUsage: ...


class PerplexityMemoryEmbedder:
    """Single-attempt adapter for the Perplexity embeddings API."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_EMBEDDING_MODEL,
        dimensions: int = DEFAULT_EMBEDDING_DIMENSIONS,
        timeout_seconds: float = DEFAULT_EMBEDDING_TIMEOUT_SECONDS,
        transport: httpx.BaseTransport | None = None,
        endpoint: str = PERPLEXITY_EMBEDDINGS_URL,
    ) -> None:
        self._api_key = api_key.strip()
        self._model = model
        self._dimensions = dimensions
        self._timeout_seconds = timeout_seconds
        self._transport = transport
        self._endpoint = endpoint
        self._last_usage = EmbeddingUsage()

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def last_usage(self) -> EmbeddingUsage:
        return self._last_usage

    def embed(self, text: str) -> list[float]:
        if not self._api_key:
            raise MemoryEmbeddingUnavailable("not_configured")
        content = text.strip()
        if not content:
            raise MemoryEmbeddingUnavailable("empty_input")
        payload = self._post(
            {
                "model": self._model,
                "input": [content],
                "dimensions": self._dimensions,
                "encoding_format": EMBEDDING_ENCODING_FORMAT,
            }
        )
        vector = _first_vector(payload)
        if len(vector) != self._dimensions:
            raise MemoryEmbeddingUnavailable(
                "malformed_response",
                detail=f"expected {self._dimensions} dimensions, got {len(vector)}",
            )
        self._last_usage = _usage_from(payload)
        return vector

    def _post(self, body: dict[str, Any]) -> Any:
        try:
            with httpx.Client(
                timeout=self._timeout_seconds,
                transport=self._transport,
            ) as client:
                response = client.post(
                    self._endpoint,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException as exc:
            raise MemoryEmbeddingUnavailable("timeout", detail=str(exc)) from exc
        except httpx.HTTPStatusError as exc:
            reason = (
                "authentication_failed"
                if exc.response.status_code in (401, 403)
                else "http_error"
            )
            raise MemoryEmbeddingUnavailable(
                reason,
                detail=f"status={exc.response.status_code}",
            ) from exc
        except httpx.HTTPError as exc:
            raise MemoryEmbeddingUnavailable("http_error", detail=str(exc)) from exc
        except ValueError as exc:
            raise MemoryEmbeddingUnavailable(
                "malformed_response",
                detail="invalid_json",
            ) from exc


def _first_vector(payload: Any) -> list[float]:
    if not isinstance(payload, dict):
        raise MemoryEmbeddingUnavailable("malformed_response", detail="not_an_object")
    data = payload.get("data")
    if not isinstance(data, list) or not data:
        raise MemoryEmbeddingUnavailable("malformed_response", detail="no_data")
    first = data[0]
    if not isinstance(first, dict):
        raise MemoryEmbeddingUnavailable("malformed_response", detail="no_embedding")
    return _decode_embedding(first.get("embedding"))


def _decode_embedding(raw: Any) -> list[float]:
    """Decode the documented base64 int8 payload, or a plain numeric vector."""

    if isinstance(raw, list):
        try:
            return [float(component) for component in raw]
        except (TypeError, ValueError) as exc:
            raise MemoryEmbeddingUnavailable(
                "malformed_response",
                detail="non_numeric_vector",
            ) from exc
    if not isinstance(raw, str) or not raw:
        raise MemoryEmbeddingUnavailable("malformed_response", detail="no_embedding")
    try:
        decoded = base64.b64decode(raw, validate=True)
    except (ValueError, TypeError) as exc:
        raise MemoryEmbeddingUnavailable(
            "malformed_response",
            detail="invalid_base64",
        ) from exc
    if not decoded:
        raise MemoryEmbeddingUnavailable("malformed_response", detail="empty_vector")
    return [float(value) for value in struct.unpack(f"{len(decoded)}b", decoded)]


def _usage_from(payload: Any) -> EmbeddingUsage:
    usage = payload.get("usage") if isinstance(payload, dict) else None
    if not isinstance(usage, dict):
        return EmbeddingUsage()
    total_tokens = usage.get("total_tokens")
    cost = usage.get("cost")
    reported = cost.get("total_cost") if isinstance(cost, dict) else None
    return EmbeddingUsage(
        total_tokens=total_tokens if isinstance(total_tokens, int) else None,
        reported_cost_usd=_as_decimal(reported),
    )


def _as_decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        parsed = Decimal(str(value))
    except (ArithmeticError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def perplexity_embedder_from_env(
    *,
    transport: httpx.BaseTransport | None = None,
) -> PerplexityMemoryEmbedder | None:
    """Build the embedder from the existing Perplexity key, or None."""

    api_key = os.getenv("PERPLEXITY_API_KEY", "").strip()
    if not api_key:
        return None
    return PerplexityMemoryEmbedder(
        api_key=api_key,
        model=os.getenv(
            "ARGUS_MEMORY_EMBEDDING_MODEL",
            DEFAULT_EMBEDDING_MODEL,
        ).strip()
        or DEFAULT_EMBEDDING_MODEL,
        dimensions=_env_int(
            "ARGUS_MEMORY_EMBEDDING_DIMENSIONS",
            DEFAULT_EMBEDDING_DIMENSIONS,
        ),
        timeout_seconds=_env_float(
            "ARGUS_MEMORY_EMBEDDING_TIMEOUT_SECONDS",
            DEFAULT_EMBEDDING_TIMEOUT_SECONDS,
        ),
        transport=transport,
    )


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default
