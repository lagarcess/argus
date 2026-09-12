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
from collections.abc import Callable, Hashable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, timedelta
from functools import partial
from typing import Any, Literal, TypeVar

from loguru import logger

from argus.domain.market_data.new_york_clock import new_york_today

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

# Every budgeted probe runs on one bounded pool. A probe past its budget keeps
# running under its key, so asking again waits on that request instead of
# starting another, and beyond this many unfinished probes nothing new starts.
_PROBE_WORKERS = 4
_MAX_PENDING_PROBES = 16
_PROBE_POOL = ThreadPoolExecutor(
    max_workers=_PROBE_WORKERS, thread_name_prefix="market-data-probe"
)
_PENDING_PROBES: dict[Hashable, Future[Any]] = {}

Verdict = Literal["tradable", "no_history", "unknown"]
_Answer = TypeVar("_Answer")


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
        _HISTORY_START_CACHE.clear()
        _PENDING_PROBES.clear()


# How far back an equity's history can begin is the provider's floor; an asset
# listed later begins on its own first bar, which only the feed knows.
ASSET_HISTORY_START_BUDGET_SECONDS = 3.0
# US equity markets have never closed for two weeks, so a longer silence in the
# feed marks where its continuous daily history begins.
_CONTINUOUS_HISTORY_GAP = timedelta(days=14)
_HISTORY_START_CACHE: dict[tuple[str, date], date] = {}


def asset_history_start(symbol: str, asset_class: str) -> date | None:
    """The first day of the price feed's continuous daily history for this asset.

    None when that cannot be established inside the budget, and for crypto and
    currency pairs, whose feeds can fall back to a recent rolling window; a
    caller holding None states no start date. A decided answer is cached for
    the New York day.
    """
    key_symbol = str(symbol or "").strip().upper()
    if not key_symbol or str(asset_class or "").strip().lower() != "equity":
        return None
    key = (key_symbol, new_york_today())
    try:
        return _run_budgeted(
            ("history_start", *key),
            partial(_first_equity_bar_date, *key),
            budget=ASSET_HISTORY_START_BUDGET_SECONDS,
            lookup=partial(_HISTORY_START_CACHE.get, key),
            keep=partial(_keep_history_start, key),
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug(
            "Asset history start could not be established",
            symbol=key_symbol,
            error=str(exc),
        )
        return None


def _keep_history_start(key: tuple[str, date], start: date | None) -> None:
    if start is not None:
        _HISTORY_START_CACHE[key] = start


def shared_history_start(symbols: list[str], asset_class: str) -> date | None:
    """The first day every asset of a run has history, or None if any is unknown."""
    starts = [asset_history_start(symbol, asset_class) for symbol in symbols]
    if not starts or any(start is None for start in starts):
        return None
    return max(start for start in starts if start is not None)


def _first_equity_bar_date(symbol: str, today: date) -> date | None:
    from argus.domain.market_data.capabilities import ALPACA_EQUITY_HISTORY_START
    from argus.domain.market_data.provider import fetch_price_series

    series = fetch_price_series(
        symbol, "equity", ALPACA_EQUITY_HISTORY_START, today, "1d"
    )
    index = getattr(series, "index", None)
    if index is None or len(index) == 0:
        return None
    days = [date.fromisoformat(str(stamp)[:10]) for stamp in index]
    start = days[0]
    for previous, current in zip(days, days[1:], strict=False):
        if current - previous > _CONTINUOUS_HISTORY_GAP:
            start = current
    return start


def tradable_history(symbol: str, asset_class: str) -> TradableHistory:
    """Probe once, under a budget, and say which of the three answers it is."""
    key = (str(symbol or "").strip().upper(), str(asset_class or "").strip().lower())
    if not key[0]:
        return TradableHistory("no_history")
    try:
        return _run_budgeted(
            ("tradable", *key),
            partial(_probe, *key),
            budget=TRADABLE_HISTORY_BUDGET_SECONDS,
            lookup=partial(_CACHE.get, key),
            keep=partial(_keep_tradable_history, key),
        )
    except Exception as exc:  # noqa: BLE001
        # A slow provider is our problem, never the asset's.
        logger.debug(
            "Tradable-history probe exceeded its budget",
            symbol=key[0],
            asset_class=key[1],
            error=str(exc),
        )
        return TradableHistory("unknown")


def _keep_tradable_history(key: tuple[str, str], result: TradableHistory) -> None:
    # Only a decided answer is cached; an outage must be re-asked.
    if result.verdict != "unknown":
        _CACHE[key] = result


def _run_budgeted(
    key: Hashable,
    work: Callable[[], _Answer],
    *,
    budget: float,
    lookup: Callable[[], _Answer | None],
    keep: Callable[[_Answer], None],
) -> _Answer:
    """The cached answer, else wait up to ``budget`` on this key's one probe."""
    with _CACHE_LOCK:
        cached = lookup()
        if cached is not None:
            return cached
        future = _PENDING_PROBES.get(key)
        if future is not None and future.done() and future.exception() is not None:
            future = None
        started = future is None
        if future is None:
            if len(_PENDING_PROBES) >= _MAX_PENDING_PROBES:
                raise RuntimeError("market data probes are at capacity")
            future = _PROBE_POOL.submit(work)
            _PENDING_PROBES[key] = future
    if started:
        future.add_done_callback(partial(_settle_probe, key, keep))
    return future.result(timeout=budget)


def _settle_probe(
    key: Hashable, keep: Callable[[Any], None], future: Future[Any]
) -> None:
    """Forget a finished probe and keep its answer, even when no caller waited."""
    with _CACHE_LOCK:
        if _PENDING_PROBES.get(key) is future:
            del _PENDING_PROBES[key]
        if not future.cancelled() and future.exception() is None:
            keep(future.result())


def _probe(symbol: str, asset_class: str) -> TradableHistory:
    from argus.domain.market_data.provider import fetch_price_series

    end = new_york_today()
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
