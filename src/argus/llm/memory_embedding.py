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


# The API accepts up to 512 inputs per request, so a bulk projection costs one
# round trip instead of one per record.
MAX_EMBEDDING_BATCH = 512


class MemoryEmbedder(Protocol):
    """Turns memory text into vectors; never stores anything."""

    @property
    def dimensions(self) -> int: ...

    def embed(self, text: str) -> list[float]: ...

    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...

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
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Vectorize many texts in as few round trips as the API allows."""

        if not self._api_key:
            raise MemoryEmbeddingUnavailable("not_configured")
        contents = [text.strip() for text in texts]
        if not contents or any(not content for content in contents):
            raise MemoryEmbeddingUnavailable("empty_input")
        vectors: list[list[float]] = []
        for start in range(0, len(contents), MAX_EMBEDDING_BATCH):
            batch = contents[start : start + MAX_EMBEDDING_BATCH]
            vectors.extend(self._embed_one_request(batch))
        return vectors

    def _embed_one_request(self, batch: list[str]) -> list[list[float]]:
        payload = self._post(
            {
                "model": self._model,
                "input": batch,
                "dimensions": self._dimensions,
                "encoding_format": EMBEDDING_ENCODING_FORMAT,
            }
        )
        vectors = _vectors_in_order(payload, expected=len(batch))
        for vector in vectors:
            if len(vector) != self._dimensions:
                raise MemoryEmbeddingUnavailable(
                    "malformed_response",
                    detail=f"expected {self._dimensions} dimensions, got {len(vector)}",
                )
        self._last_usage = _usage_from(payload)
        return vectors

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


def _vectors_in_order(payload: Any, *, expected: int) -> list[list[float]]:
    """Decode every embedding, restored to request order by its index."""

    if not isinstance(payload, dict):
        raise MemoryEmbeddingUnavailable("malformed_response", detail="not_an_object")
    data = payload.get("data")
    if not isinstance(data, list) or len(data) != expected:
        raise MemoryEmbeddingUnavailable("malformed_response", detail="no_data")
    ordered: list[list[float] | None] = [None] * expected
    for position, entry in enumerate(data):
        if not isinstance(entry, dict):
            raise MemoryEmbeddingUnavailable(
                "malformed_response",
                detail="no_embedding",
            )
        index = entry.get("index")
        slot = (
            index if isinstance(index, int) and not isinstance(index, bool) else position
        )
        if not 0 <= slot < expected or ordered[slot] is not None:
            raise MemoryEmbeddingUnavailable(
                "malformed_response",
                detail="unusable_index",
            )
        ordered[slot] = _decode_embedding(entry.get("embedding"))
    if any(vector is None for vector in ordered):
        raise MemoryEmbeddingUnavailable("malformed_response", detail="no_data")
    return [vector for vector in ordered if vector is not None]


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
