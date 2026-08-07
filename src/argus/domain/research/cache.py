"""Shared research cache with per-class TTL.

SHARED ACROSS USERS BY DESIGN. finance_search returns public market data, so
one user's answer may serve another user's identical question, and that is the
cost lever. The hard rule at this seam: THIS CACHE MUST NEVER BE REUSED FOR
ANYTHING USER-SCOPED. Keys must never include a user, guest, visitor, session,
or conversation identity, and values must only ever be provider packets about
public markets. Memory, preferences, drafts, and any personalized content are
forbidden here, whatever the TTL.

TTL is per capability class, mapped from the spec section 7 tolerance table:

- ``fast_quote``        120s   (quotes, pre/after hours: seconds to minutes)
- ``screening``         300s   (gainers, losers, most active: minutes)
- ``balanced_lookup``   900s   (mixes statements with current figures; bounded
                                by the freshest ingredient, matching the
                                ``ohlcv_recent`` freshness policy)
- ``thorough_research`` 6h     (fundamentals and multi-year work; kept well
                                under the quarterly tolerance because thorough
                                answers may still quote current levels)
- closed historical periods    30d (effectively immutable once closed)

The cache key includes the period of interest, so a specific past close is a
different entry from a trailing window.
"""

from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass

from argus.domain.research.contracts import CapabilityClass, ResearchPacket

_BASE_TTL_SECONDS: dict[str, float] = {
    "fast_quote": 120.0,
    "screening": 300.0,
    "balanced_lookup": 900.0,
    "thorough_research": 21_600.0,
}
CLOSED_PERIOD_TTL_SECONDS = 2_592_000.0  # 30 days
_MAX_ENTRIES = 512


@dataclass
class _Entry:
    packet: ResearchPacket
    stored_at: float
    ttl_seconds: float


_CACHE: dict[str, _Entry] = {}
_LOCK = threading.Lock()
_HITS = 0
_MISSES = 0


def ttl_for(capability_class: CapabilityClass, *, closed_period: bool) -> float:
    if closed_period:
        return CLOSED_PERIOD_TTL_SECONDS
    return _BASE_TTL_SECONDS.get(capability_class, 900.0)


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
