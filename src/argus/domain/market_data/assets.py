from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Literal

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import AssetClass as AlpacaAssetClass
from alpaca.trading.enums import AssetStatus
from alpaca.trading.requests import GetAssetsRequest

AssetClass = Literal["equity", "crypto"]


@dataclass(frozen=True)
class ResolvedAsset:
    canonical_symbol: str
    asset_class: AssetClass
    name: str
    raw_symbol: str


ASSET_SEARCH_ALIASES = {
    "alphabet": ("GOOG", "GOOGL"),
    "amazon": ("AMZN",),
    "apple": ("AAPL",),
    "bitcoin": ("BTC", "BTCUSD"),
    "btc": ("BTC", "BTCUSD"),
    "ethereum": ("ETH", "ETHUSD"),
    "ether": ("ETH", "ETHUSD"),
    "facebook": ("META",),
    "google": ("GOOG", "GOOGL"),
    "meta": ("META",),
    "microsoft": ("MSFT",),
    "netflix": ("NFLX",),
    "nvidia": ("NVDA",),
    "tesla": ("TSLA",),
}


_ASSET_ALIAS_MAP: dict[str, ResolvedAsset] | None = None
_ASSET_CACHE_TS: float = 0.0
_ASSET_CACHE_LOCK = threading.Lock()


def _cache_ttl_seconds() -> int:
    raw = (os.getenv("MARKET_DATA_CACHE_TTL") or "900").strip()
    try:
        value = int(raw)
    except ValueError:
        value = 900
    return max(value, 60)


def _normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper().replace("-", "/")


def _canonicalize_crypto_symbol(symbol: str) -> str:
    normalized = _normalize_symbol(symbol).replace("/", "")
    if normalized.endswith("USD") and len(normalized) > 3:
        return normalized[:-3]
    return normalized


def _asset_class_for_row(asset_class: str) -> AssetClass | None:
    lowered = asset_class.lower()
    if lowered == "us_equity":
        return "equity"
    if lowered == "crypto":
        return "crypto"
    return None


def _add_aliases(
    aliases: dict[str, ResolvedAsset], record: ResolvedAsset, *, canonical: str
) -> None:
    base_aliases = {
        _normalize_symbol(record.raw_symbol),
        _normalize_symbol(record.raw_symbol).replace("/", ""),
        canonical,
    }
    if record.asset_class == "crypto":
        base_aliases.add(f"{canonical}/USD")
        base_aliases.add(f"{canonical}USD")

    for alias in base_aliases:
        aliases[alias] = record


def _load_assets_from_alpaca() -> dict[str, ResolvedAsset]:
    key = (os.getenv("ALPACA_API_KEY") or "").strip()
    secret = (os.getenv("ALPACA_SECRET_KEY") or "").strip()
    if not key or not secret:
        raise ValueError("asset_universe_unavailable")

    paper = (os.getenv("ALPACA_PAPER_TRADING") or "true").strip().lower() != "false"
    client = TradingClient(api_key=key, secret_key=secret, paper=paper)

    active_assets: list[object] = []
    for cls in (AlpacaAssetClass.US_EQUITY, AlpacaAssetClass.CRYPTO):
        request = GetAssetsRequest(status=AssetStatus.ACTIVE, asset_class=cls)
        active_assets.extend(client.get_all_assets(request))

    aliases: dict[str, ResolvedAsset] = {}
    for asset in active_assets:
        raw_symbol = str(getattr(asset, "symbol", "") or "").upper()
        raw_name = str(getattr(asset, "name", "") or "")
        raw_asset_class = getattr(asset, "asset_class", "") or ""
        row_class = str(getattr(raw_asset_class, "value", raw_asset_class) or "")
        asset_class = _asset_class_for_row(row_class)
        if not raw_symbol or asset_class is None:
            continue

        canonical = (
            _canonicalize_crypto_symbol(raw_symbol)
            if asset_class == "crypto"
            else _normalize_symbol(raw_symbol)
        )
        if not canonical:
            continue

        resolved = ResolvedAsset(
            canonical_symbol=canonical,
            asset_class=asset_class,
            name=raw_name,
            raw_symbol=raw_symbol,
        )
        _add_aliases(aliases, resolved, canonical=canonical)

        # Add name alias (lower-case, stripped)
        name_alias = raw_name.lower().strip()
        if name_alias and name_alias not in aliases:
            aliases[name_alias] = resolved

    if not aliases:
        raise ValueError("asset_universe_unavailable")

    return aliases


def _refresh_asset_cache_if_needed(*, force: bool = False) -> None:
    global _ASSET_ALIAS_MAP, _ASSET_CACHE_TS

    now = time.time()
    ttl = _cache_ttl_seconds()
    expired = (now - _ASSET_CACHE_TS) >= ttl
    if not (force or _ASSET_ALIAS_MAP is None or expired):
        return
    with _ASSET_CACHE_LOCK:
        now = time.time()
        expired = (now - _ASSET_CACHE_TS) >= ttl
        if force or _ASSET_ALIAS_MAP is None or expired:
            _ASSET_ALIAS_MAP = _load_assets_from_alpaca()
            _ASSET_CACHE_TS = now


def resolve_asset(symbol: str) -> ResolvedAsset:
    _refresh_asset_cache_if_needed()
    assert _ASSET_ALIAS_MAP is not None

    candidate = _normalize_symbol(symbol)
    # 1. Direct ticker match
    direct = _ASSET_ALIAS_MAP.get(candidate) or _ASSET_ALIAS_MAP.get(
        candidate.replace("/", "")
    )
    if direct:
        return direct

    # 2. Case-insensitive ticker or name match
    lower_candidate = symbol.lower().strip()
    named = _ASSET_ALIAS_MAP.get(lower_candidate)
    if named:
        return named

    # 3. Crypto USD suffix handling
    if candidate.endswith("/USD"):
        without_quote = candidate[:-4]
        alt = _ASSET_ALIAS_MAP.get(without_quote)
        if alt:
            return alt

    raise ValueError("invalid_symbol")


def search_assets(query: str, *, limit: int = 12) -> list[ResolvedAsset]:
    _refresh_asset_cache_if_needed()
    assert _ASSET_ALIAS_MAP is not None

    normalized_query = _normalize_symbol(query)
    lowered_query = query.lower().strip()
    if not normalized_query and not lowered_query:
        return []

    scored: dict[str, tuple[int, ResolvedAsset]] = {}
    for alias in ASSET_SEARCH_ALIASES.get(lowered_query, ()):
        record = _ASSET_ALIAS_MAP.get(_normalize_symbol(alias)) or _ASSET_ALIAS_MAP.get(
            alias.lower()
        )
        if record is not None:
            scored[record.canonical_symbol] = (0, record)

    for alias, record in _ASSET_ALIAS_MAP.items():
        alias_upper = _normalize_symbol(alias)
        name_lower = record.name.lower().strip()
        score: int | None = None
        if alias_upper == normalized_query or record.canonical_symbol == normalized_query:
            score = 1
        elif alias_upper.startswith(normalized_query):
            score = 2
        elif name_lower.startswith(lowered_query):
            score = 3
        elif normalized_query in alias_upper:
            score = 4
        elif lowered_query and lowered_query in name_lower:
            score = 5
        if score is None:
            continue
        existing = scored.get(record.canonical_symbol)
        if existing is None or score < existing[0]:
            scored[record.canonical_symbol] = (score, record)

    ranked = sorted(
        scored.values(),
        key=lambda item: (item[0], item[1].asset_class, item[1].canonical_symbol),
    )
    return [record for _, record in ranked[: max(1, min(limit, 25))]]


def clear_asset_cache() -> None:
    global _ASSET_ALIAS_MAP, _ASSET_CACHE_TS
    with _ASSET_CACHE_LOCK:
        _ASSET_ALIAS_MAP = None
        _ASSET_CACHE_TS = 0.0
