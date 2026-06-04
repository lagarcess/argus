from __future__ import annotations

from datetime import datetime, timedelta, timezone

from argus.context.freshness import (
    FreshnessSubject,
    context_packet_freshness,
    freshness_policy_for,
)
from argus.context.packets import ContextPacket


def test_freshness_policy_defines_minimum_launch_ttls() -> None:
    assert freshness_policy_for("ohlcv_historical").ttl_seconds > 24 * 60 * 60
    assert freshness_policy_for("ohlcv_recent").ttl_seconds < 60 * 60
    assert freshness_policy_for("fred_macro").ttl_seconds >= 24 * 60 * 60
    assert freshness_policy_for("alpaca_corporate_actions").ttl_seconds > (
        freshness_policy_for("alpaca_news").ttl_seconds
    )
    assert freshness_policy_for("alpaca_movers").ttl_seconds < (
        freshness_policy_for("alpaca_news").ttl_seconds
    )
    assert freshness_policy_for("route_receipts").ttl_seconds is None
    assert freshness_policy_for("llm_freeform_chat").cacheable is False


def test_context_packet_freshness_uses_packet_type_and_retrieved_at() -> None:
    now = datetime(2026, 5, 20, tzinfo=timezone.utc)
    stale_news = ContextPacket(
        provider="alpaca",
        packet_type="news",
        retrieved_at=now - timedelta(hours=7),
        freshness="fresh",
    )
    fresh_news = ContextPacket(
        provider="alpaca",
        packet_type="news",
        retrieved_at=now - timedelta(minutes=30),
        freshness="fresh",
    )

    assert context_packet_freshness(stale_news, now=now) == "stale"
    assert context_packet_freshness(fresh_news, now=now) == "fresh"


def test_freshness_subjects_cover_launch_stack_without_new_provider_scope() -> None:
    expected: set[FreshnessSubject] = {
        "ohlcv_historical",
        "ohlcv_recent",
        "fred_macro",
        "alpaca_corporate_actions",
        "alpaca_news",
        "alpaca_movers",
        "alpaca_most_actives",
        "context_packets",
        "route_receipts",
        "llm_freeform_chat",
    }

    assert {subject for subject in expected if freshness_policy_for(subject)} == expected
