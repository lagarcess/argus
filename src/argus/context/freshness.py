from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from argus.context.packets import ContextFreshness, ContextPacket, ContextPacketType

FreshnessSubject = Literal[
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
]


@dataclass(frozen=True)
class FreshnessPolicy:
    subject: FreshnessSubject
    ttl_seconds: int | None
    cacheable: bool = True
    durable: bool = False


_DAY = 24 * 60 * 60

_POLICIES: dict[FreshnessSubject, FreshnessPolicy] = {
    "ohlcv_historical": FreshnessPolicy("ohlcv_historical", 30 * _DAY),
    "ohlcv_recent": FreshnessPolicy("ohlcv_recent", 15 * 60),
    "fred_macro": FreshnessPolicy("fred_macro", _DAY),
    "alpaca_corporate_actions": FreshnessPolicy(
        "alpaca_corporate_actions", 7 * _DAY
    ),
    "alpaca_news": FreshnessPolicy("alpaca_news", 2 * 60 * 60),
    "alpaca_movers": FreshnessPolicy("alpaca_movers", 5 * 60),
    "alpaca_most_actives": FreshnessPolicy("alpaca_most_actives", 5 * 60),
    "context_packets": FreshnessPolicy("context_packets", None, durable=True),
    "route_receipts": FreshnessPolicy("route_receipts", None, durable=True),
    "llm_freeform_chat": FreshnessPolicy(
        "llm_freeform_chat",
        None,
        cacheable=False,
    ),
}

_PACKET_SUBJECTS: dict[ContextPacketType, FreshnessSubject] = {
    "macro": "fred_macro",
    "news": "alpaca_news",
    "corporate_actions": "alpaca_corporate_actions",
    "market_movers": "alpaca_movers",
    "most_actives": "alpaca_most_actives",
}


def freshness_policy_for(subject: FreshnessSubject) -> FreshnessPolicy:
    return _POLICIES[subject]


def context_packet_freshness(
    packet: ContextPacket,
    *,
    now: datetime | None = None,
) -> ContextFreshness:
    if packet.freshness == "unknown":
        return "unknown"
    subject = _PACKET_SUBJECTS.get(packet.packet_type)
    if subject is None:
        return packet.freshness
    ttl_seconds = freshness_policy_for(subject).ttl_seconds
    if ttl_seconds is None:
        return packet.freshness
    reference_now = now or datetime.now(timezone.utc)
    retrieved_at = packet.retrieved_at
    if retrieved_at.tzinfo is None:
        retrieved_at = retrieved_at.replace(tzinfo=timezone.utc)
    age_seconds = (reference_now - retrieved_at).total_seconds()
    return "stale" if age_seconds > ttl_seconds else "fresh"
