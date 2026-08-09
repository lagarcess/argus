"""Shared research cache with per-data-class TTL.

SHARED ACROSS USERS BY DESIGN. finance_search returns public market data, so
one user's answer may serve another user's identical question, and that is the
cost lever. The hard rule at this seam: THIS CACHE MUST NEVER BE REUSED FOR
ANYTHING USER-SCOPED. Keys must never include a user, guest, visitor, session,
or conversation identity, and values must only ever be provider packets about
public markets. Memory, preferences, drafts, and any personalized content are
forbidden here, whatever the TTL.

TTL is per data class, the seven rows of the spec section 7 table:

- ``quotes``               120s  (quotes, pre and after hours: seconds to minutes)
- ``movers``               300s  (top gainers, losers, most active: minutes)
- ``analyst_estimates``    3d    (analyst estimates: days)
- ``peers_constituents``   60d   (peers, ETF constituents and weights: months)
- ``fundamentals``         90d   (fundamentals and statements: quarterly)
- ``closed_ohlcv``         90d   (closed historical OHLCV: effectively immutable)
- ``filings_transcripts``  90d   (earnings transcripts, SEC filings: immutable
                                  once published)

The two immutable rows share the 90-day value because this cache lives in
process memory: immutability is real, retention is bounded. The class of an
entry comes from what the packet actually contains when its result categories
are uniform (a holdings-only pull is constituents data whatever the question
was), and from the question's dominant data need otherwise; the most volatile
ingredient of a genuinely current ask (a live quote) keeps its short
tolerance because the question kind carries it there.

The closed-period rule stands: a question about an entirely closed window is
``closed_ohlcv`` regardless of anything else. The cache key includes the
period of interest, so a specific past close is a different entry from a
trailing window.
"""

from __future__ import annotations

import hashlib
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from argus.domain.research.contracts import CapabilityClass, ResearchPacket

DataClass = Literal[
    "quotes",
    "movers",
    "analyst_estimates",
    "fundamentals",
    "peers_constituents",
    "closed_ohlcv",
    "filings_transcripts",
]

DATA_CLASS_TTL_SECONDS: dict[DataClass, float] = {
    "quotes": 120.0,
    "movers": 300.0,
    "analyst_estimates": 259_200.0,
    "peers_constituents": 5_184_000.0,
    "fundamentals": 7_776_000.0,
    "closed_ohlcv": 7_776_000.0,
    "filings_transcripts": 7_776_000.0,
}

# Ordered: the first family a category matches decides it, so
# "earnings_transcript" is a filing before it is fundamentals and
# "price_target" is an estimate before it is a quote.
_CATEGORY_FAMILIES: tuple[tuple[DataClass, tuple[str, ...]], ...] = (
    ("filings_transcripts", ("transcript", "filing", "sec_")),
    ("peers_constituents", ("holding", "peer", "constituent", "tickers_lookup")),
    ("analyst_estimates", ("estimate", "price_target", "recommendation", "rating")),
    ("movers", ("gainer", "loser", "most_active", "mover", "screen")),
    (
        "fundamentals",
        ("financial", "income", "balance", "cash", "statement", "ratio", "profile"),
    ),
    ("quotes", ("quote", "price", "market_cap")),
)

# The question's dominant data need, used when the packet mixes families.
# Comparisons lean on estimates and statements (days); lookups lean on
# statements (quarterly); current-facts finds and screens are movers-fresh.
_KIND_DATA_CLASS: dict[str, DataClass] = {
    "live_quote": "quotes",
    "screening": "movers",
    "find_assets": "movers",
    "etf_constituents": "peers_constituents",
    "company_lookup": "fundamentals",
    "cross_company": "analyst_estimates",
}

_MAX_ENTRIES = 512


def _family_for_category(category: str) -> DataClass | None:
    lowered = category.strip().lower()
    for family, needles in _CATEGORY_FAMILIES:
        if any(needle in lowered for needle in needles):
            return family
    return None


def data_class_for(
    *,
    question_kind: str | None,
    categories: Sequence[str] = (),
    closed_period: bool = False,
) -> DataClass:
    """The section 7 data class governing one cache entry."""
    if closed_period:
        return "closed_ohlcv"
    families = {
        family
        for family in (_family_for_category(category) for category in categories)
        if family is not None
    }
    if len(families) == 1:
        return next(iter(families))
    return _KIND_DATA_CLASS.get(str(question_kind or ""), "movers")


def ttl_for_packet(
    *,
    question_kind: str | None,
    categories: Sequence[str] = (),
    closed_period: bool = False,
) -> float:
    return DATA_CLASS_TTL_SECONDS[
        data_class_for(
            question_kind=question_kind,
            categories=categories,
            closed_period=closed_period,
        )
    ]


@dataclass
class _Entry:
    packet: ResearchPacket
    stored_at: float
    ttl_seconds: float


_CACHE: dict[str, _Entry] = {}
_LOCK = threading.Lock()
_HITS = 0
_MISSES = 0


def research_cache_key(
    *,
    capability_class: CapabilityClass,
    shape: str,
    symbols: tuple[str, ...],
    period_key: str,
    question_fingerprint: str,
    language: str,
) -> str:
    """Public-market request identity only. No user identity may enter here."""
    material = "|".join(
        (
            capability_class,
            shape,
            ",".join(sorted(symbol.upper() for symbol in symbols)),
            period_key,
            question_fingerprint,
            language,
        )
    )
    return hashlib.sha256(material.encode()).hexdigest()


def cache_get(key: str) -> ResearchPacket | None:
    global _HITS, _MISSES
    now = time.monotonic()
    with _LOCK:
        entry = _CACHE.get(key)
        if entry is None:
            _MISSES += 1
            return None
        if now - entry.stored_at > entry.ttl_seconds:
            del _CACHE[key]
            _MISSES += 1
            return None
        _HITS += 1
        return entry.packet


def cache_put(key: str, packet: ResearchPacket, *, ttl_seconds: float) -> None:
    if ttl_seconds <= 0:
        return
    with _LOCK:
        if len(_CACHE) >= _MAX_ENTRIES:
            oldest = min(_CACHE.items(), key=lambda item: item[1].stored_at)[0]
            del _CACHE[oldest]
        _CACHE[key] = _Entry(
            packet=packet, stored_at=time.monotonic(), ttl_seconds=ttl_seconds
        )


def cache_stats() -> dict[str, int]:
    with _LOCK:
        return {"entries": len(_CACHE), "hits": _HITS, "misses": _MISSES}


def cache_clear() -> None:
    """Test seam."""
    global _HITS, _MISSES
    with _LOCK:
        _CACHE.clear()
        _HITS = 0
        _MISSES = 0
