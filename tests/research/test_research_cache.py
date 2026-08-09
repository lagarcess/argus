"""Shared cache locks: cross-user hits, per-data-class TTL, no user identity."""

from __future__ import annotations

import inspect
import time

from argus.domain.research import cache as research_cache
from argus.domain.research.cache import (
    DATA_CLASS_TTL_SECONDS,
    cache_get,
    cache_put,
    cache_stats,
    data_class_for,
    research_cache_key,
    ttl_for_packet,
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
    cache_put(
        key_user_a,
        packet,
        ttl_seconds=ttl_for_packet(question_kind="live_quote"),
    )
    served = cache_get(key_user_b)
    assert served is not None
    assert served.answer_markdown == "AAPL at $312.41"
    stats = cache_stats()
    assert stats["hits"] == 1 and stats["misses"] == 1


def test_the_seven_data_classes_match_the_section_7_table() -> None:
    """One row per spec table row; the ladder orders tolerance exactly."""
    assert DATA_CLASS_TTL_SECONDS["quotes"] == 120.0
    assert DATA_CLASS_TTL_SECONDS["movers"] == 300.0
    assert DATA_CLASS_TTL_SECONDS["analyst_estimates"] == 259_200.0
    assert DATA_CLASS_TTL_SECONDS["peers_constituents"] == 5_184_000.0
    assert DATA_CLASS_TTL_SECONDS["fundamentals"] == 7_776_000.0
    assert DATA_CLASS_TTL_SECONDS["closed_ohlcv"] == 7_776_000.0
    assert DATA_CLASS_TTL_SECONDS["filings_transcripts"] == 7_776_000.0
    assert len(DATA_CLASS_TTL_SECONDS) == 7
    assert (
        DATA_CLASS_TTL_SECONDS["quotes"]
        < DATA_CLASS_TTL_SECONDS["movers"]
        < DATA_CLASS_TTL_SECONDS["analyst_estimates"]
        < DATA_CLASS_TTL_SECONDS["peers_constituents"]
        <= DATA_CLASS_TTL_SECONDS["fundamentals"]
    )


def test_question_kinds_map_to_their_dominant_data_class() -> None:
    assert data_class_for(question_kind="live_quote") == "quotes"
    assert data_class_for(question_kind="screening") == "movers"
    assert data_class_for(question_kind="find_assets") == "movers"
    assert data_class_for(question_kind="etf_constituents") == "peers_constituents"
    assert data_class_for(question_kind="company_lookup") == "fundamentals"
    assert data_class_for(question_kind="cross_company") == "analyst_estimates"
    # Unknown kinds stay conservative, never long-lived.
    assert data_class_for(question_kind="something_new") == "movers"


def test_uniform_packet_categories_decide_the_class_over_the_kind() -> None:
    """A holdings-only pull is constituents data whatever the question was;
    an estimates-only pull is estimates data. Mixed packets keep the
    question's dominant need, so a genuinely current ask stays fresh."""
    assert (
        data_class_for(question_kind="company_lookup", categories=("etf_holdings",))
        == "peers_constituents"
    )
    assert (
        data_class_for(question_kind="company_lookup", categories=("analyst_estimates",))
        == "analyst_estimates"
    )
    assert (
        data_class_for(
            question_kind="company_lookup", categories=("earnings_transcript",)
        )
        == "filings_transcripts"
    )
    # A fast answer mixing a quote with its verification table stays a quote.
    assert (
        data_class_for(question_kind="live_quote", categories=("quote", "tickers_lookup"))
        == "quotes"
    )
    # price_target is an estimate before it is a price.
    assert (
        data_class_for(question_kind="live_quote", categories=("price_target",))
        == "analyst_estimates"
    )


def test_closed_period_rule_wins_over_everything() -> None:
    for kind in ("live_quote", "company_lookup", "cross_company", "screening"):
        assert data_class_for(question_kind=kind, closed_period=True) == "closed_ohlcv"
    assert (
        data_class_for(
            question_kind="live_quote",
            categories=("quote",),
            closed_period=True,
        )
        == "closed_ohlcv"
    )
    assert (
        ttl_for_packet(question_kind="live_quote", closed_period=True)
        == DATA_CLASS_TTL_SECONDS["closed_ohlcv"]
    )


def test_expired_entries_fall_out(monkeypatch) -> None:
    key = _key_for_user("expiring")
    cache_put(key, ResearchPacket(answer_markdown="old"), ttl_seconds=120.0)
    real_monotonic = time.monotonic
    monkeypatch.setattr(
        research_cache.time, "monotonic", lambda: real_monotonic() + 121.0
    )
    assert cache_get(key) is None
