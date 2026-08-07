"""Transit-only vectorization: correct decoding, typed failures, no leakage."""

from __future__ import annotations

import base64
import json
import struct
from decimal import Decimal

import httpx
import pytest
from argus.llm.memory_embedding import (
    DEFAULT_EMBEDDING_MODEL,
    EMBEDDING_ENCODING_FORMAT,
    MAX_EMBEDDING_BATCH,
    PERPLEXITY_EMBEDDINGS_URL,
    MemoryEmbeddingUnavailable,
    PerplexityMemoryEmbedder,
    perplexity_embedder_from_env,
)

API_KEY = "pplx-test-key"


def _encoded(components: list[int]) -> str:
    return base64.b64encode(struct.pack(f"{len(components)}b", *components)).decode()


def _transport(handler) -> httpx.MockTransport:  # noqa: ANN001
    return httpx.MockTransport(handler)


def _ok_payload(components: list[int], *, cost: float = 0.000004) -> dict:
    return {
        "object": "list",
        "data": [{"object": "embedding", "index": 0, "embedding": _encoded(components)}],
        "model": DEFAULT_EMBEDDING_MODEL,
        "usage": {
            "prompt_tokens": 12,
            "total_tokens": 12,
            "cost": {"input_cost": cost, "total_cost": cost, "currency": "USD"},
        },
    }


def _embedder(handler, **kwargs) -> PerplexityMemoryEmbedder:  # noqa: ANN001
    return PerplexityMemoryEmbedder(
        api_key=API_KEY,
        dimensions=kwargs.pop("dimensions", 4),
        transport=_transport(handler),
        **kwargs,
    )


def test_decodes_the_documented_base64_int8_vector() -> None:
    """Catches the quantized vector payload being misread as raw bytes."""
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("Authorization")
        captured["body"] = request.read().decode()
        return httpx.Response(200, json=_ok_payload([12, -7, 0, 127]))

    vector = _embedder(handler).embed("keep the lower drawdown choice")

    assert vector == [12.0, -7.0, 0.0, 127.0]
    assert captured["url"] == PERPLEXITY_EMBEDDINGS_URL
    assert captured["auth"] == f"Bearer {API_KEY}"
    assert EMBEDDING_ENCODING_FORMAT in captured["body"]


def test_reports_usage_and_cost_from_the_vendor_response() -> None:
    """Catches embedding spend going unmeasured."""

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, json=_ok_payload([1, 2, 3, 4], cost=0.000012))

    embedder = _embedder(handler)
    usage = embedder.embed_batch_with_usage(["anything"]).usage

    assert usage.total_tokens == 12
    assert usage.reported_cost_usd == Decimal("0.000012")


def test_a_vector_of_the_wrong_width_is_rejected() -> None:
    """Catches a model or dimension mismatch silently corrupting the index."""

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, json=_ok_payload([1, 2, 3]))

    with pytest.raises(MemoryEmbeddingUnavailable) as failure:
        _embedder(handler, dimensions=4).embed("anything")

    assert failure.value.reason == "malformed_response"


@pytest.mark.parametrize(
    ("status", "expected"),
    (
        (401, "authentication_failed"),
        (403, "authentication_failed"),
        (500, "http_error"),
        (429, "http_error"),
    ),
)
def test_http_failures_map_to_typed_reasons(status: int, expected: str) -> None:
    """Catches a vendor outage escaping as an untyped error."""

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(status, json={"error": "nope"})

    with pytest.raises(MemoryEmbeddingUnavailable) as failure:
        _embedder(handler).embed("anything")

    assert failure.value.reason == expected


def test_timeouts_map_to_a_typed_reason() -> None:
    """Catches a slow vendor hanging a turn instead of degrading recall."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("too slow", request=request)

    with pytest.raises(MemoryEmbeddingUnavailable) as failure:
        _embedder(handler).embed("anything")

    assert failure.value.reason == "timeout"


@pytest.mark.parametrize(
    "payload",
    (
        {"data": []},
        {"data": [{}]},
        {"data": [{"embedding": ""}]},
        {"data": [{"embedding": "not base64!!"}]},
        {"nope": True},
        [],
    ),
)
def test_malformed_responses_are_rejected_rather_than_guessed(payload: object) -> None:
    """Catches a malformed vendor response producing a bogus vector."""

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, json=payload)

    with pytest.raises(MemoryEmbeddingUnavailable):
        _embedder(handler).embed("anything")


def test_a_missing_key_fails_before_any_request_is_made() -> None:
    """Catches an unconfigured deployment attempting vendor calls."""
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json=_ok_payload([1, 2, 3, 4]))

    embedder = PerplexityMemoryEmbedder(
        api_key="  ",
        dimensions=4,
        transport=_transport(handler),
    )

    with pytest.raises(MemoryEmbeddingUnavailable) as failure:
        embedder.embed("anything")

    assert failure.value.reason == "not_configured"
    assert called is False


def test_empty_text_is_never_sent_to_the_vendor() -> None:
    """Catches blank memory text producing a pointless billed call."""
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json=_ok_payload([1, 2, 3, 4]))

    with pytest.raises(MemoryEmbeddingUnavailable) as failure:
        _embedder(handler).embed("   ")

    assert failure.value.reason == "empty_input"
    assert called is False


def test_env_factory_stays_off_without_the_existing_perplexity_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catches semantic recall trying to start without a configured key."""
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)

    assert perplexity_embedder_from_env() is None


def test_env_factory_uses_the_existing_perplexity_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catches the lane inventing a second vendor credential."""
    monkeypatch.setenv("PERPLEXITY_API_KEY", API_KEY)
    monkeypatch.delenv("ARGUS_MEMORY_EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("ARGUS_MEMORY_EMBEDDING_DIMENSIONS", raising=False)

    embedder = perplexity_embedder_from_env()

    assert embedder is not None
    assert embedder.dimensions == 1024


def test_a_batch_is_one_request_not_one_per_text() -> None:
    """Catches a bulk projection fanning out into a request per record."""
    requests: list[list[str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.read())
        requests.append(body["input"])
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": position, "embedding": _encoded([position, 1, 2, 3])}
                    for position in range(len(body["input"]))
                ],
                "usage": {"total_tokens": 9},
            },
        )

    vectors = _embedder(handler).embed_batch(["one", "two", "three"])

    assert len(requests) == 1
    assert requests[0] == ["one", "two", "three"]
    assert [vector[0] for vector in vectors] == [0.0, 1.0, 2.0]


def test_batches_split_at_the_documented_ceiling() -> None:
    """Catches exceeding the 512-input limit in a single request."""
    sizes: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.read())
        sizes.append(len(body["input"]))
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": position, "embedding": _encoded([1, 2, 3, 4])}
                    for position in range(len(body["input"]))
                ]
            },
        )

    _embedder(handler).embed_batch([f"text-{index}" for index in range(700)])

    assert sizes == [MAX_EMBEDDING_BATCH, 700 - MAX_EMBEDDING_BATCH]


def test_vectors_come_back_in_request_order() -> None:
    """Catches an out-of-order response silently mismatching text to vector."""

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": _encoded([9, 9, 9, 9])},
                    {"index": 0, "embedding": _encoded([1, 1, 1, 1])},
                ]
            },
        )

    vectors = _embedder(handler).embed_batch(["first", "second"])

    assert vectors[0][0] == 1.0
    assert vectors[1][0] == 9.0


def test_a_short_response_is_rejected_rather_than_misaligned() -> None:
    """Catches a dropped embedding shifting every later text onto a wrong vector."""

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            json={"data": [{"index": 0, "embedding": _encoded([1, 2, 3, 4])}]},
        )

    with pytest.raises(MemoryEmbeddingUnavailable):
        _embedder(handler).embed_batch(["one", "two"])


def test_single_embed_still_returns_one_vector() -> None:
    """Catches the batch refactor changing the single-text contract."""

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, json=_ok_payload([5, 6, 7, 8]))

    assert _embedder(handler).embed("anything") == [5.0, 6.0, 7.0, 8.0]


def test_a_batched_response_missing_indices_is_rejected() -> None:
    """Catches the exact silent corruption: missing index and reordered."""

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            json={
                "data": [
                    {"embedding": _encoded([9, 9, 9, 9])},
                    {"embedding": _encoded([1, 1, 1, 1])},
                ]
            },
        )

    with pytest.raises(MemoryEmbeddingUnavailable) as failure:
        _embedder(handler).embed_batch(["first", "second"])

    assert failure.value.detail == "missing_index"


def test_a_single_input_may_still_rely_on_position() -> None:
    """Catches over-tightening: one input makes order unambiguous."""

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, json={"data": [{"embedding": _encoded([2, 3, 4, 5])}]})

    assert _embedder(handler).embed("only") == [2.0, 3.0, 4.0, 5.0]


def test_batched_usage_sums_across_requests() -> None:
    """Catches a multi-request batch reporting only its last chunk's usage."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.read())
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": position, "embedding": _encoded([1, 2, 3, 4])}
                    for position in range(len(body["input"]))
                ],
                "usage": {
                    "total_tokens": 10,
                    "cost": {"total_cost": 0.000002, "currency": "USD"},
                },
            },
        )

    result = _embedder(handler).embed_batch_with_usage(
        [f"text-{index}" for index in range(700)]
    )

    assert len(result.vectors) == 700
    # Two requests at 10 tokens each, not one request's worth.
    assert result.usage.total_tokens == 20
    assert result.usage.reported_cost_usd == Decimal("0.000004")
