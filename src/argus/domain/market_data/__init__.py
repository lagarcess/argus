from .assets import (
    AssetUniverseWarmupResult,
    ResolvedAsset,
    clear_asset_cache,
    is_ticker_like_query,
    resolve_asset,
    search_assets,
    warm_asset_universe,
)


def clear_market_data_cache() -> None:
    from .provider import clear_market_data_cache as _clear_market_data_cache

    return _clear_market_data_cache()


def fetch_ohlcv(*args, **kwargs):
    from .provider import fetch_ohlcv as _fetch_ohlcv

    return _fetch_ohlcv(*args, **kwargs)


def fetch_price_series(*args, **kwargs):
    from .provider import fetch_price_series as _fetch_price_series

    return _fetch_price_series(*args, **kwargs)

__all__ = [
    "ResolvedAsset",
    "AssetUniverseWarmupResult",
    "clear_asset_cache",
    "clear_market_data_cache",
    "fetch_ohlcv",
    "fetch_price_series",
    "is_ticker_like_query",
    "resolve_asset",
    "search_assets",
    "warm_asset_universe",
]
