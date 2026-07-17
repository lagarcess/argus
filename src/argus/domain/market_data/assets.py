from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeVar
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from loguru import logger

T = TypeVar("T")

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
    provider: str = "unknown"
    exchange: str | None = None


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
    "AMD": ("equity", "Advanced Micro Devices Inc.", "AMD"),
    "AMZN": ("equity", "Amazon.com Inc.", "AMZN"),
    "BTC": ("crypto", "Bitcoin", "BTC/USD"),
    "ETH": ("crypto", "Ethereum", "ETH/USD"),
    "EURUSD": ("currency_pair", "EUR/USD", "EURUSD"),
    "GOOG": ("equity", "Alphabet Inc. Class C", "GOOG"),
    "GOOGL": ("equity", "Alphabet Inc. Class A", "GOOGL"),
    "INTC": ("equity", "Intel Corporation", "INTC"),
    "META": ("equity", "Meta Platforms Inc.", "META"),
    "MSFT": ("equity", "Microsoft Corporation", "MSFT"),
    "NFLX": ("equity", "Netflix Inc.", "NFLX"),
    "NVDA": ("equity", "NVIDIA Corporation", "NVDA"),
    "QQQ": ("equity", "Invesco QQQ Trust", "QQQ"),
    "SPY": ("equity", "SPDR S&P 500 ETF Trust", "SPY"),
    "TSLA": ("equity", "Tesla Inc.", "TSLA"),
}


_ASSET_ALIAS_MAP: dict[str, ResolvedAsset] | None = None
_ASSET_CACHE_TS: float = 0.0
_ASSET_CACHE_MODE: AssetProviderMode | None = None
_ASSET_EXACT_LOOKUP_CACHE: dict[str, ResolvedAsset] = {}
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


def _asset_universe_loader_timeout_seconds() -> float:
    raw = (os.getenv("ARGUS_ASSET_UNIVERSE_LOADER_TIMEOUT_SECONDS") or "20").strip()
    try:
        value = float(raw)
    except ValueError:
        return 20.0
    return max(value, 0.01)


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
        base_name = record.name.lower().strip() if record.name else None
        base_aliases.add(f"{canonical}/USD")
        base_aliases.add(f"{canonical}USD")
        base_aliases.add(f"{canonical} USD")
        base_aliases.add(f"{canonical} dollar")
        if base_name:
            base_aliases.update(
                _crypto_base_name_aliases(base_name, raw_symbol=record.raw_symbol)
            )
            base_aliases.add(f"{base_name} usd")
            base_aliases.add(f"{base_name}/usd")
            base_aliases.add(f"{base_name} dollar")
    if record.asset_class == "currency_pair" and len(canonical) == 6:
        base_aliases.add(f"{canonical[:3]}/{canonical[3:]}")

    for alias in base_aliases:
        aliases[alias] = record


def _crypto_base_name_aliases(name: str | None, *, raw_symbol: str) -> set[str]:
    if not name:
        return set()
    normalized = name.lower().strip()
    if not normalized:
        return set()
    aliases: set[str] = {normalized}
    # Provider crypto names are often pair-shaped, for example "Bitcoin / USD".
    # Only the primary USD quote owns the bare base alias; quote-specific pairs
    # keep quote-specific aliases so "Bitcoin" does not resolve to BTC/USDC.
    if "/" in normalized and _crypto_quote_symbol(raw_symbol) == "USD":
        base, *_ = [part.strip() for part in normalized.split("/") if part.strip()]
        if base:
            aliases.add(base)
    return aliases


def _crypto_quote_symbol(raw_symbol: str) -> str | None:
    normalized = _normalize_symbol(raw_symbol)
    if "/" not in normalized:
        return None
    *_, quote = [part.strip().upper() for part in normalized.split("/") if part.strip()]
    return quote or None


def _load_assets_from_alpaca() -> dict[str, ResolvedAsset]:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.enums import AssetClass as AlpacaAssetClass
    from alpaca.trading.enums import AssetStatus
    from alpaca.trading.requests import GetAssetsRequest

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
        parsed = _resolved_asset_from_alpaca_asset(asset)
        if parsed is None:
            continue
        canonical, resolved = parsed
        _add_aliases(aliases, resolved, canonical=canonical)

        # Add name alias (lower-case, stripped)
        name_alias = resolved.name.lower().strip()
        if name_alias and name_alias not in aliases:
            aliases[name_alias] = resolved

    if not aliases:
        raise ValueError("asset_universe_unavailable")

    return aliases


def _load_asset_from_alpaca_symbol(symbol: str) -> ResolvedAsset:
    from alpaca.trading.client import TradingClient

    key = (os.getenv("ALPACA_API_KEY") or "").strip()
    secret = (os.getenv("ALPACA_SECRET_KEY") or "").strip()
    if not key or not secret:
        raise ValueError("asset_universe_unavailable")

    paper = (os.getenv("ALPACA_PAPER_TRADING") or "true").strip().lower() != "false"
    client = TradingClient(api_key=key, secret_key=secret, paper=paper)
    parsed = _resolved_asset_from_alpaca_asset(client.get_asset(symbol))
    if parsed is None:
        raise ValueError("invalid_symbol")
    _, resolved = parsed
    return resolved


def _resolved_asset_from_alpaca_asset(
    asset: object,
) -> tuple[str, ResolvedAsset] | None:
    raw_status = getattr(asset, "status", None) or "active"
    status = str(getattr(raw_status, "value", raw_status) or "").lower()
    if status and status != "active":
        return None

    raw_symbol = str(getattr(asset, "symbol", "") or "").upper()
    raw_name = str(getattr(asset, "name", "") or "")
    raw_asset_class = getattr(asset, "asset_class", "") or ""
    row_class = str(getattr(raw_asset_class, "value", raw_asset_class) or "")
    asset_class = _asset_class_for_row(row_class)
    if not raw_symbol or asset_class is None:
        return None

    canonical = (
        _canonicalize_crypto_symbol(raw_symbol)
        if asset_class == "crypto"
        else _normalize_symbol(raw_symbol)
    )
    if not canonical:
        return None

    resolved = ResolvedAsset(
        canonical_symbol=canonical,
        asset_class=asset_class,
        name=raw_name,
        raw_symbol=raw_symbol,
        provider="alpaca",
        exchange=str(getattr(asset, "exchange", "") or "") or None,
    )
    return canonical, resolved


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
            provider="kraken",
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
            provider="synthetic_unit_fixture",
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
            provider=str(row.get("provider") or "recorded_provider_fixture"),
            exchange=str(row.get("exchange") or "") or None,
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
    for provider, loader in (
        ("alpaca", _load_assets_from_alpaca),
        ("kraken", _load_assets_from_kraken),
    ):
        try:
            aliases.update(_load_live_provider_assets(loader, provider=provider))
        except Exception as exc:
            first_error = first_error or exc

    if not aliases:
        raise ValueError("asset_universe_unavailable") from first_error
    return aliases


def _load_live_provider_assets(
    loader: Callable[[], dict[str, ResolvedAsset]],
    *,
    provider: str,
) -> dict[str, ResolvedAsset]:
    return _run_live_provider_call(
        loader,
        provider=provider,
        operation="asset_universe",
    )


def _run_live_provider_call(
    loader: Callable[[], T],
    *,
    provider: str,
    operation: str,
) -> T:
    timeout_seconds = _asset_universe_loader_timeout_seconds()
    executor = ThreadPoolExecutor(
        max_workers=1,
        thread_name_prefix=f"argus-assets-{provider}",
    )
    future = executor.submit(loader)
    try:
        logger.debug(
            "Asset provider call started "
            f"provider={provider} operation={operation} "
            f"timeout_seconds={timeout_seconds}",
            provider=provider,
            operation=operation,
            timeout_seconds=timeout_seconds,
        )
        result = future.result(timeout=timeout_seconds)
        logger.debug(
            "Asset provider call completed "
            f"provider={provider} operation={operation} "
            f"result_type={type(result).__name__}",
            provider=provider,
            operation=operation,
            result_type=type(result).__name__,
            result_size=len(result) if hasattr(result, "__len__") else None,
        )
        return result
    except TimeoutError as exc:
        future.cancel()
        logger.warning(
            "Asset provider call timed out "
            f"provider={provider} operation={operation} "
            f"timeout_seconds={timeout_seconds}",
            provider=provider,
            operation=operation,
            timeout_seconds=timeout_seconds,
        )
        raise ValueError("asset_universe_unavailable") from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _refresh_asset_cache_if_needed(*, force: bool = False) -> None:
    global _ASSET_ALIAS_MAP, _ASSET_CACHE_MODE, _ASSET_CACHE_TS

    now = time.time()
    ttl = _cache_ttl_seconds()
    expired = (now - _ASSET_CACHE_TS) >= ttl
    provider_mode = _asset_provider_mode()
    mode_changed = _ASSET_CACHE_MODE != provider_mode
    if not (force or _ASSET_ALIAS_MAP is None or expired or mode_changed):
        return
    with _ASSET_CACHE_LOCK:
        now = time.time()
        expired = (now - _ASSET_CACHE_TS) >= ttl
        provider_mode = _asset_provider_mode()
        mode_changed = _ASSET_CACHE_MODE != provider_mode
        if force or _ASSET_ALIAS_MAP is None or expired or mode_changed:
            _ASSET_ALIAS_MAP = _load_asset_universe()
            _ASSET_CACHE_TS = now
            _ASSET_CACHE_MODE = provider_mode


def resolve_asset(symbol: str) -> ResolvedAsset:
    candidate = _normalize_symbol(symbol)
    explicit_ticker_query = _is_explicit_ticker_query(symbol)
    if explicit_ticker_query and _is_unresolved_ticker_like_query(symbol):
        live_asset = _resolve_live_provider_ticker(candidate)
        if live_asset is not None:
            return live_asset

    _refresh_asset_cache_if_needed()
    assert _ASSET_ALIAS_MAP is not None

    # 1. Exact catalog alias match, case-insensitive for ticker-like aliases.
    direct = _ASSET_ALIAS_MAP.get(candidate) or _ASSET_ALIAS_MAP.get(
        candidate.replace("/", "")
    )
    if direct is not None and _accepts_exact_catalog_alias(symbol, direct):
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
        asset = confident_name_matches[0]
        if _accepts_high_confidence_name_match(symbol, asset):
            return asset

    if _is_unresolved_ticker_like_query(symbol):
        raise ValueError("invalid_symbol")

    # 4. Provider-backed name search. This is intentionally sourced from the
    # loaded catalog, so a common name can only resolve when a provider record
    # exists in the active mode.
    matches = search_assets(symbol, limit=2)
    if matches and _name_match_score(lower_candidate, matches[0]) <= 1:
        return matches[0]

    raise ValueError("invalid_symbol")


def _resolve_live_provider_ticker(symbol: str) -> ResolvedAsset | None:
    if _asset_provider_mode() != "live_provider":
        return None
    with _ASSET_CACHE_LOCK:
        cached = _ASSET_EXACT_LOOKUP_CACHE.get(symbol)
    if cached is not None:
        logger.debug("Asset provider exact lookup cache hit symbol={}", symbol)
        return cached
    try:
        asset = _run_live_provider_call(
            lambda: _load_asset_from_alpaca_symbol(symbol),
            provider="alpaca",
            operation=f"symbol_lookup:{symbol}",
        )
        with _ASSET_CACHE_LOCK:
            _ASSET_EXACT_LOOKUP_CACHE[symbol] = asset
        return asset
    except Exception:
        return None


def _accepts_exact_catalog_alias(query: str, asset: ResolvedAsset) -> bool:
    raw = str(query or "").strip()
    if _is_explicit_ticker_query(raw):
        return True
    if "/" in raw or "-" in raw:
        return True
    compact = _compact_symbol(raw)
    if asset.asset_class == "crypto":
        return True
    if compact and raw != raw.lower():
        return True
    return len(compact) >= 4


def warm_asset_universe(
    *,
    required_symbols: tuple[str, ...] = ("AAPL", "MSFT", "SPY"),
    force: bool = False,
) -> AssetUniverseWarmupResult:
    started = time.perf_counter()
    _refresh_asset_cache_if_needed(force=force)
    if _ASSET_ALIAS_MAP is None:
        raise ValueError("asset_universe_unavailable")

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


def _is_explicit_ticker_query(query: str) -> bool:
    raw = str(query or "").strip()
    if not raw or " " in raw:
        return False
    if "/" in raw or "-" in raw:
        return True
    compact = raw.replace("/", "").replace("-", "")
    return bool(compact and compact.isalpha() and compact == compact.upper())


def _accepts_high_confidence_name_match(query: str, asset: ResolvedAsset) -> bool:
    raw = str(query or "").strip()
    compact = raw.replace("/", "").replace("-", "")
    if (
        compact.isalpha()
        and 2 <= len(compact) <= 3
        and compact == compact.lower()
        and "/" not in raw
        and " " not in raw
    ):
        return asset.asset_class == "crypto"
    return True


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
    global _ASSET_ALIAS_MAP, _ASSET_CACHE_MODE, _ASSET_CACHE_TS
    global _ASSET_EXACT_LOOKUP_CACHE
    with _ASSET_CACHE_LOCK:
        _ASSET_ALIAS_MAP = None
        _ASSET_CACHE_TS = 0.0
        _ASSET_CACHE_MODE = None
        _ASSET_EXACT_LOOKUP_CACHE = {}
