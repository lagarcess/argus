"""Can Argus actually trade this symbol's history, and how sure are we?

One fact, one owner. Four surfaces used to probe price coverage with four
windows, four budgets and four answers, so the same asset could be refused on
one and offered on the next. They all read this now.

The verdict is deliberately three-valued. "We have no bars for PENGU" is a
true statement about the symbol; "our key expired" is a statement about us,
and voicing the second as the first makes Argus name liquid tickers and
assert they are not tradable. Callers must be able to tell those apart.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from loguru import logger

# One window and one budget for every caller. The window is short because the
# question is "does history exist", not "how far back does it go".
TRADABLE_HISTORY_PROBE_DAYS = 30
TRADABLE_HISTORY_BUDGET_SECONDS = 2.0
_MIN_CLOSES = 2

# A symbol the provider has never heard of does not become tradable while a
# process lives, so a negative is worth keeping; an outage must not be cached
# as a fact about the asset, so `unknown` is never stored.
_CACHE: dict[tuple[str, str], "TradableHistory"] = {}
_CACHE_LOCK = threading.Lock()

Verdict = Literal["tradable", "no_history", "unknown"]


@dataclass(frozen=True)
class TradableHistory:
    """What the price feed will say if a user taps this row."""

    verdict: Verdict
    earliest: date | None = None

    @property
    def is_tradable(self) -> bool:
        return self.verdict == "tradable"

    @property
    def is_our_outage(self) -> bool:
        """True when we could not answer, as opposed to answering no."""
        return self.verdict == "unknown"


def clear_tradable_history_cache() -> None:
    with _CACHE_LOCK:
        _CACHE.clear()


def tradable_history(symbol: str, asset_class: str) -> TradableHistory:
    """Probe once, under a budget, and say which of the three answers it is."""
    key = (str(symbol or "").strip().upper(), str(asset_class or "").strip().lower())
    if not key[0]:
        return TradableHistory("no_history")
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
    if cached is not None:
        return cached
    result = _probe_under_budget(key[0], key[1])
    if result.verdict != "unknown":
        # Only a decided answer is cached; an outage must be re-asked.
        with _CACHE_LOCK:
            _CACHE[key] = result
    return result


def _probe_under_budget(symbol: str, asset_class: str) -> TradableHistory:
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        return executor.submit(_probe, symbol, asset_class).result(
            timeout=TRADABLE_HISTORY_BUDGET_SECONDS
        )
    except Exception as exc:  # noqa: BLE001
        # A slow provider is our problem, never the asset's.
        logger.debug(
            "Tradable-history probe exceeded its budget",
            symbol=symbol,
            asset_class=asset_class,
            error=str(exc),
        )
        return TradableHistory("unknown")
    finally:
        executor.shutdown(wait=False, cancel_futures=False)


def _probe(symbol: str, asset_class: str) -> TradableHistory:
    from argus.domain.market_data.provider import fetch_price_series

    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=TRADABLE_HISTORY_PROBE_DAYS)
    try:
        series = fetch_price_series(symbol, asset_class, start, end, "1d")
    except ValueError as exc:
        # The provider's own taxonomy decides. market_data_empty is the only
        # error that says something true about the symbol.
        if str(exc) == "market_data_empty":
            return TradableHistory("no_history")
        logger.debug(
            "Tradable-history probe could not reach the provider",
            symbol=symbol,
            asset_class=asset_class,
            error=str(exc),
        )
        return TradableHistory("unknown")
    except Exception as exc:  # noqa: BLE001
        logger.debug(
            "Tradable-history probe failed",
            symbol=symbol,
            asset_class=asset_class,
            error=str(exc),
        )
        return TradableHistory("unknown")
    values = series.tolist() if hasattr(series, "tolist") else list(series or [])
    closes = [value for value in values if value is not None]
    if len(closes) < _MIN_CLOSES:
        return TradableHistory("no_history")
    index = getattr(series, "index", None)
    earliest: date | None = None
    if index is not None and len(index):
        try:
            earliest = date.fromisoformat(str(index[0])[:10])
        except ValueError:
            earliest = None
    return TradableHistory("tradable", earliest=earliest)
