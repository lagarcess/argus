from __future__ import annotations

import time

import pytest
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


def test_lowercase_language_token_does_not_use_exact_ticker_lookup(
    monkeypatch,
) -> None:
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    assets.clear_asset_cache()
    deere = ResolvedAsset(
        canonical_symbol="DE",
        asset_class="equity",
        name="Deere & Company",
        raw_symbol="DE",
        provider="alpaca",
    )

    def forbidden_exact_lookup(symbol: str) -> ResolvedAsset:
        raise AssertionError(f"lowercase language token used exact lookup: {symbol}")

    monkeypatch.setattr(
        assets,
        "_load_asset_from_alpaca_symbol",
        forbidden_exact_lookup,
    )
    monkeypatch.setattr(
        assets,
        "_load_asset_universe",
        lambda: {"DE": deere, "deere & company": deere},
    )

    with pytest.raises(ValueError, match="invalid_symbol"):
        assets.resolve_asset("de")

    assets.clear_asset_cache()


def test_lowercase_crypto_symbol_can_still_resolve_by_provider_name(
    monkeypatch,
) -> None:
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    assets.clear_asset_cache()
    ethereum = ResolvedAsset(
        canonical_symbol="ETH",
        asset_class="crypto",
        name="Ethereum / USD",
        raw_symbol="ETH/USD",
        provider="kraken",
    )

    monkeypatch.setattr(
        assets,
        "_load_asset_from_alpaca_symbol",
        lambda symbol: (_ for _ in ()).throw(AssertionError(symbol)),
    )
    monkeypatch.setattr(
        assets,
        "_load_asset_universe",
        lambda: {"ETH": ethereum, "ethereum / usd": ethereum},
    )

    resolved = assets.resolve_asset("eth")

    assert resolved.canonical_symbol == "ETH"

    assets.clear_asset_cache()


def test_live_ticker_resolution_caches_exact_provider_lookup(
    monkeypatch,
) -> None:
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    assets.clear_asset_cache()
    calls = 0

    def exact_alpaca_lookup(symbol: str) -> ResolvedAsset:
        nonlocal calls
        calls += 1
        assert symbol == "MSFT"
        return ResolvedAsset(
            canonical_symbol="MSFT",
            asset_class="equity",
            name="Microsoft Corporation",
            raw_symbol="MSFT",
            provider="alpaca",
        )

    monkeypatch.setattr(
        assets,
        "_load_asset_from_alpaca_symbol",
        exact_alpaca_lookup,
    )

    first = assets.resolve_asset("MSFT")
    second = assets.resolve_asset("MSFT")

    assert first.canonical_symbol == "MSFT"
    assert second.canonical_symbol == "MSFT"
    assert calls == 1

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
