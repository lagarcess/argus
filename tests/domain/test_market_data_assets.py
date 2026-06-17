from __future__ import annotations

import time

from argus.domain.market_data import assets
from argus.domain.market_data.assets import ResolvedAsset


def test_live_ticker_resolution_uses_exact_lookup_before_universe(
    monkeypatch,
) -> None:
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    assets.clear_asset_cache()
    def forbidden_universe_loader() -> dict[str, ResolvedAsset]:
        raise AssertionError("ticker resolution should not load the full universe")

    def exact_alpaca_lookup(symbol: str) -> ResolvedAsset:
        assert symbol == "AAPL"
        return ResolvedAsset(
            canonical_symbol="AAPL",
            asset_class="equity",
            name="Apple Inc.",
            raw_symbol="AAPL",
            provider="alpaca",
        )

    monkeypatch.setattr(assets, "_load_asset_universe", forbidden_universe_loader)
    monkeypatch.setattr(
        assets,
        "_load_asset_from_alpaca_symbol",
        exact_alpaca_lookup,
    )

    resolved = assets.resolve_asset("AAPL")

    assert resolved.canonical_symbol == "AAPL"
    assert resolved.provider == "alpaca"

    assets.clear_asset_cache()


def test_live_asset_universe_loader_times_out_slow_provider_and_uses_fallback(
    monkeypatch,
) -> None:
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    monkeypatch.setenv("ARGUS_ASSET_UNIVERSE_LOADER_TIMEOUT_SECONDS", "0.01")
    assets.clear_asset_cache()

    def slow_alpaca_loader() -> dict[str, ResolvedAsset]:
        time.sleep(0.12)
        return {
            "AAPL": ResolvedAsset(
                canonical_symbol="AAPL",
                asset_class="equity",
                name="Apple Inc.",
                raw_symbol="AAPL",
                provider="alpaca",
            )
        }

    def kraken_loader() -> dict[str, ResolvedAsset]:
        return {
            "BTC": ResolvedAsset(
                canonical_symbol="BTC",
                asset_class="crypto",
                name="Bitcoin / USD",
                raw_symbol="BTC/USD",
                provider="kraken",
            )
        }

    monkeypatch.setattr(assets, "_load_assets_from_alpaca", slow_alpaca_loader)
    monkeypatch.setattr(assets, "_load_assets_from_kraken", kraken_loader)

    started = time.perf_counter()
    resolved = assets.resolve_asset("BTC")
    duration = time.perf_counter() - started

    assert resolved.canonical_symbol == "BTC"
    assert duration < 0.08

    assets.clear_asset_cache()
