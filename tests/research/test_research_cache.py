"""Shared cache locks: cross-user hits, per-class TTL, no user identity."""

from __future__ import annotations

import inspect
import time

from argus.domain.research import cache as research_cache
from argus.domain.research.cache import (
    CLOSED_PERIOD_TTL_SECONDS,
    cache_get,
    cache_put,
    cache_stats,
    research_cache_key,
    ttl_for,
)
from argus.domain.research.contracts import ResearchPacket


def _key_for_user(question: str) -> str:
    # Deliberately built from public request identity only; two users asking
    # the same question must produce the same key.
    return research_cache_key(
        capability_class="fast_quote",
        shape="fast",
        symbols=("AAPL",),
        period_key="current",
        question_fingerprint=" ".join(question.lower().split()),
        language="en",
    )


def test_cache_key_has_no_user_parameter() -> None:
    parameters = inspect.signature(research_cache_key).parameters
    assert not any(
        "user" in name or "guest" in name or "visitor" in name or "session" in name
        for name in parameters
    ), "the shared cache key must never accept user-scoped identity"


def test_cross_user_hit_shares_one_provider_answer() -> None:
    key_user_a = _key_for_user("What is Apple trading at?")
    key_user_b = _key_for_user("what is apple trading at?")
    assert key_user_a == key_user_b

    packet = ResearchPacket(answer_markdown="AAPL at $312.41")
    assert cache_get(key_user_a) is None
    cache_put(key_user_a, packet, ttl_seconds=ttl_for("fast_quote", closed_period=False))
    served = cache_get(key_user_b)
    assert served is not None
    assert served.answer_markdown == "AAPL at $312.41"
    stats = cache_stats()
    assert stats["hits"] == 1 and stats["misses"] == 1


def test_per_class_ttls_match_the_spec_tolerances() -> None:
    assert ttl_for("fast_quote", closed_period=False) == 120.0
    assert ttl_for("screening", closed_period=False) == 300.0
    assert ttl_for("balanced_lookup", closed_period=False) == 900.0
    assert ttl_for("thorough_research", closed_period=False) == 21_600.0
    # A closed historical window is effectively immutable.
    for capability_class in ("fast_quote", "balanced_lookup", "thorough_research"):
        assert ttl_for(capability_class, closed_period=True) == CLOSED_PERIOD_TTL_SECONDS
    # The ladder orders freshness tolerance exactly as the spec table does.
    assert (
        ttl_for("fast_quote", closed_period=False)
        < ttl_for("screening", closed_period=False)
        < ttl_for("balanced_lookup", closed_period=False)
        < ttl_for("thorough_research", closed_period=False)
        < CLOSED_PERIOD_TTL_SECONDS
    )


def test_expired_entries_fall_out(monkeypatch) -> None:
    key = _key_for_user("expiring")
    cache_put(key, ResearchPacket(answer_markdown="old"), ttl_seconds=120.0)
    real_monotonic = time.monotonic
    monkeypatch.setattr(
        research_cache.time, "monotonic", lambda: real_monotonic() + 121.0
    )
    assert cache_get(key) is None
