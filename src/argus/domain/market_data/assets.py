from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import AssetClass as AlpacaAssetClass
from alpaca.trading.enums import AssetStatus
from alpaca.trading.requests import GetAssetsRequest

AssetClass = Literal["equity", "crypto", "currency_pair"]
AssetProviderMode = Literal[
    "live_provider",
    "recorded_provider_fixture",
    "synthetic_unit_fixture",
]


@dataclass(frozen=True)
class ResolvedAsset:
    canonical_symbol: str
    asset_class: AssetClass
    name: str
    raw_symbol: str


@dataclass(frozen=True)
class AssetUniverseWarmupResult:
    status: Literal["ready", "degraded"]
    provider_mode: AssetProviderMode
    alias_count: int
    required_symbols: tuple[str, ...]
    resolved_symbols: tuple[str, ...]
    missing_symbols: tuple[str, ...]
    duration_ms: int


SYNTHETIC_UNIT_ASSETS: dict[str, tuple[AssetClass, str, str]] = {
    "AAPL": ("equity", "Apple Inc.", "AAPL"),
    "AMZN": ("equity", "Amazon.com Inc.", "AMZN"),
    "BTC": ("crypto", "Bitcoin", "BTC/USD"),
    "ETH": ("crypto", "Ethereum", "ETH/USD"),
    "GOOG": ("equity", "Alphabet Inc. Class C", "GOOG"),
    "GOOGL": ("equity", "Alphabet Inc. Class A", "GOOGL"),
    "META": ("equity", "Meta Platforms Inc.", "META"),
    "MSFT": ("equity", "Microsoft Corporation", "MSFT"),
    "NFLX": ("equity", "Netflix Inc.", "NFLX"),
    "NVDA": ("equity", "NVIDIA Corporation", "NVDA"),
    "SPY": ("equity", "SPDR S&P 500 ETF Trust", "SPY"),
    "TSLA": ("equity", "Tesla Inc.", "TSLA"),
}


_ASSET_ALIAS_MAP: dict[str, ResolvedAsset] | None = None
_ASSET_CACHE_TS: float = 0.0
_ASSET_CACHE_LOCK = threading.Lock()
KRAKEN_PUBLIC_API_BASE = "https://api.kraken.com/0"
FIAT_CODES = {"USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"}
KRAKEN_CRYPTO_ALIASES = {"XBT": "BTC", "XXBT": "BTC", "XETH": "ETH"}


def _cache_ttl_seconds() -> int:
    raw = (os.getenv("MARKET_DATA_CACHE_TTL") or "900").strip()
    try:
        value = int(raw)
    except ValueError:
        value = 900
    return max(value, 60)


def _asset_provider_mode() -> AssetProviderMode:
    raw = (os.getenv("ARGUS_MARKET_DATA_PROVIDER_MODE") or "live_provider").strip()
    if raw in {
        "live_provider",
        "recorded_provider_fixture",
        "synthetic_unit_fixture",
    }:
        return raw  # type: ignore[return-value]
    raise ValueError("invalid_provider_mode")


def _normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper().replace("-", "/")


def _compact_symbol(symbol: str) -> str:
    return _normalize_symbol(symbol).replace("/", "")


def _kraken_public_get(path: str, params: dict[str, object] | None = None) -> dict:
    query = f"?{urlencode(params)}" if params else ""
    request = Request(
        f"{KRAKEN_PUBLIC_API_BASE}{path}{query}",
        headers={"User-Agent": "Argus/1.0"},
    )
    with urlopen(request, timeout=10) as response:  # noqa: S310 - fixed public Kraken API base
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("error"):
        raise ValueError("asset_universe_unavailable")
    return payload


def _canonicalize_crypto_symbol(symbol: str) -> str:
    normalized = _normalize_symbol(symbol).replace("/", "")
    if normalized.endswith("USD") and len(normalized) > 3:
        return normalized[:-3]
    return normalized


def _canonicalize_kraken_asset(asset: str) -> str:
    normalized = _compact_symbol(asset)
    if normalized in KRAKEN_CRYPTO_ALIASES:
        return KRAKEN_CRYPTO_ALIASES[normalized]
    if normalized.startswith("Z") and len(normalized) == 4:
        return normalized[1:]
    if normalized.startswith("X") and len(normalized) == 4:
        return normalized[1:]
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
    if record.asset_class == "currency_pair" and len(canonical) == 6:
        base_aliases.add(f"{canonical[:3]}/{canonical[3:]}")

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


def _load_assets_from_kraken() -> dict[str, ResolvedAsset]:
    payload = _kraken_public_get("/public/AssetPairs")
    pairs = payload.get("result")
    if not isinstance(pairs, dict):
        raise ValueError("asset_universe_unavailable")

    return _load_kraken_asset_pairs(pairs)


def _load_kraken_asset_pairs(pairs: dict[str, object]) -> dict[str, ResolvedAsset]:
    aliases: dict[str, ResolvedAsset] = {}
    for key, row in pairs.items():
        if not isinstance(row, dict) or row.get("status") not in {None, "online"}:
            continue
        altname = str(row.get("altname") or key).upper()
        wsname = str(row.get("wsname") or altname)
        base = _canonicalize_kraken_asset(str(row.get("base") or altname[:3]))
        quote = _canonicalize_kraken_asset(str(row.get("quote") or altname[-3:]))
        if not base or not quote:
            continue

        is_currency_pair = base in FIAT_CODES and quote in FIAT_CODES
        asset_class: AssetClass = "currency_pair" if is_currency_pair else "crypto"
        canonical = f"{base}{quote}" if is_currency_pair else base
        raw_symbol = altname if is_currency_pair else f"{base}/USD"
        name = f"{base}/{quote}" if is_currency_pair else wsname
        if asset_class == "crypto" and quote != "USD":
            continue

        resolved = ResolvedAsset(
            canonical_symbol=canonical,
            asset_class=asset_class,
            name=name,
            raw_symbol=raw_symbol,
        )
        _add_aliases(aliases, resolved, canonical=canonical)
        aliases[_normalize_symbol(altname)] = resolved
        aliases[_compact_symbol(altname)] = resolved
        aliases[wsname.lower().strip()] = resolved
        if is_currency_pair:
            aliases[f"{base.lower()} {quote.lower()}"] = resolved
            aliases[f"{base.lower()}/{quote.lower()}"] = resolved
            if base == "EUR" and quote == "USD":
                aliases["euro dollar"] = resolved

    return aliases


def _load_synthetic_unit_assets() -> dict[str, ResolvedAsset]:
    aliases: dict[str, ResolvedAsset] = {}
    for symbol, (asset_class, name, raw_symbol) in SYNTHETIC_UNIT_ASSETS.items():
        resolved = ResolvedAsset(
            canonical_symbol=symbol,
            asset_class=asset_class,
            name=name,
            raw_symbol=raw_symbol,
        )
        _add_aliases(aliases, resolved, canonical=symbol)
        aliases[name.lower().strip()] = resolved

    return aliases


def _load_recorded_provider_fixture_assets() -> dict[str, ResolvedAsset]:
    raw_path = (os.getenv("ARGUS_ASSET_FIXTURE_PATH") or "").strip()
    if not raw_path:
        raise ValueError("asset_universe_unavailable")
    fixture_path = Path(raw_path).expanduser()
    try:
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError("asset_universe_unavailable") from exc
    if not isinstance(payload, dict):
        raise ValueError("asset_universe_unavailable")

    aliases: dict[str, ResolvedAsset] = {}
    alpaca_assets = payload.get("alpaca_assets") or []
    if isinstance(alpaca_assets, list):
        aliases.update(_load_alpaca_asset_rows(alpaca_assets))

    kraken_pairs = payload.get("kraken_asset_pairs") or payload.get("asset_pairs") or {}
    if isinstance(kraken_pairs, dict):
        aliases.update(_load_kraken_asset_pairs(kraken_pairs))

    if not aliases:
        raise ValueError("asset_universe_unavailable")
    return aliases


def _load_alpaca_asset_rows(rows: list[object]) -> dict[str, ResolvedAsset]:
    aliases: dict[str, ResolvedAsset] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or "active").lower()
        if status != "active":
            continue
        raw_symbol = str(row.get("symbol") or "").upper()
        raw_name = str(row.get("name") or "")
        asset_class = _asset_class_for_row(str(row.get("asset_class") or ""))
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
        name_alias = raw_name.lower().strip()
        if name_alias:
            aliases[name_alias] = resolved

    return aliases


def _load_asset_universe() -> dict[str, ResolvedAsset]:
    mode = _asset_provider_mode()
    if mode == "synthetic_unit_fixture":
        return _load_synthetic_unit_assets()
    if mode == "recorded_provider_fixture":
        return _load_recorded_provider_fixture_assets()

    aliases: dict[str, ResolvedAsset] = {}
    first_error: Exception | None = None
    for loader in (_load_assets_from_alpaca, _load_assets_from_kraken):
        try:
            aliases.update(loader())
        except Exception as exc:
            first_error = first_error or exc

    if not aliases:
        raise ValueError("asset_universe_unavailable") from first_error
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
            _ASSET_ALIAS_MAP = _load_asset_universe()
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

    confident_name_matches = _high_confidence_name_matches(symbol)
    if len(confident_name_matches) == 1:
        return confident_name_matches[0]

    if _is_unresolved_ticker_like_query(symbol):
        raise ValueError("invalid_symbol")

    # 4. Provider-backed name search. This is intentionally sourced from the
    # loaded catalog, so a common name can only resolve when a provider record
    # exists in the active mode.
    matches = search_assets(symbol, limit=2)
    if matches and _name_match_score(lower_candidate, matches[0]) <= 1:
        return matches[0]

    raise ValueError("invalid_symbol")


def warm_asset_universe(
    *,
    required_symbols: tuple[str, ...] = ("AAPL", "MSFT", "SPY"),
    force: bool = False,
) -> AssetUniverseWarmupResult:
    started = time.perf_counter()
    _refresh_asset_cache_if_needed(force=force)
    assert _ASSET_ALIAS_MAP is not None

    resolved: list[str] = []
    missing: list[str] = []
    for symbol in required_symbols:
        try:
            resolved.append(resolve_asset(symbol).canonical_symbol)
        except Exception:
            missing.append(symbol)

    duration_ms = int((time.perf_counter() - started) * 1000)
    return AssetUniverseWarmupResult(
        status="ready" if not missing else "degraded",
        provider_mode=_asset_provider_mode(),
        alias_count=len(_ASSET_ALIAS_MAP),
        required_symbols=required_symbols,
        resolved_symbols=tuple(resolved),
        missing_symbols=tuple(missing),
        duration_ms=duration_ms,
    )


def _is_unresolved_ticker_like_query(query: str) -> bool:
    raw = str(query or "").strip()
    compact = _compact_symbol(raw)
    if not compact.isalpha() or not 2 <= len(compact) <= 5:
        return False
    return "/" not in raw and " " not in raw


def is_ticker_like_query(query: str) -> bool:
    return _is_unresolved_ticker_like_query(query)


def search_assets(query: str, *, limit: int = 12) -> list[ResolvedAsset]:
    _refresh_asset_cache_if_needed()
    assert _ASSET_ALIAS_MAP is not None

    normalized_query = _normalize_symbol(query)
    lowered_query = query.lower().strip()
    if not normalized_query and not lowered_query:
        return []

    scored: dict[str, tuple[int, ResolvedAsset]] = {}
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


def _high_confidence_name_matches(query: str) -> list[ResolvedAsset]:
    lowered_query = query.lower().strip()
    if not lowered_query:
        return []
    assert _ASSET_ALIAS_MAP is not None
    seen: set[str] = set()
    matches: list[tuple[int, ResolvedAsset]] = []
    for record in _ASSET_ALIAS_MAP.values():
        if record.canonical_symbol in seen:
            continue
        seen.add(record.canonical_symbol)
        score = _name_match_score(lowered_query, record)
        if score <= 1:
            matches.append((score, record))
    matches.sort(key=lambda item: (item[0], item[1].asset_class, item[1].canonical_symbol))
    return [record for _, record in matches]


def _name_match_score(query: str, record: ResolvedAsset) -> int:
    name = record.name.lower().strip()
    if query == name:
        return 0
    if name.startswith(query):
        return 1
    if query and query in name:
        return 2
    return 3


def clear_asset_cache() -> None:
    global _ASSET_ALIAS_MAP, _ASSET_CACHE_TS
    with _ASSET_CACHE_LOCK:
        _ASSET_ALIAS_MAP = None
        _ASSET_CACHE_TS = 0.0
