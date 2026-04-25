from __future__ import annotations

from datetime import date

import pandas as pd
import pytest
from argus.domain.market_data import assets, provider
from argus.domain.market_data.assets import ResolvedAsset


def test_normalize_df_enforces_utc_sorted_lowercase_ohlcv() -> None:
    frame = pd.DataFrame(
        {
            "Open": [100.0, 101.0],
            "High": [101.0, 102.0],
            "Low": [99.0, 100.0],
            "Close": [100.5, 101.5],
            "Volume": [10.0, 12.0],
        },
        index=pd.to_datetime(["2025-01-02", "2025-01-01"]),
    )
    normalized = provider._normalize_df(frame, symbol="AAPL")
    assert list(normalized.columns) == ["open", "high", "low", "close", "volume"]
    assert str(normalized.index.tz) == "UTC"
    assert normalized.index[0] < normalized.index[1]


@pytest.mark.parametrize(
    ("symbol", "asset_class", "expected"),
    [
        ("aapl", "equity", "AAPL"),
        ("btc", "crypto", "BTC/USD"),
        ("btcusd", "crypto", "BTC/USD"),
        ("eth/usd", "crypto", "ETH/USD"),
    ],
)
def test_to_alpaca_symbol_normalizes_symbol_forms(
    symbol: str, asset_class: provider.AssetClass, expected: str
) -> None:
    assert provider._to_alpaca_symbol(symbol, asset_class) == expected


def test_fetch_ohlcv_passes_ttl_cache_bin(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_cached(**kwargs):  # noqa: ANN003
        captured.update(kwargs)
        return pd.DataFrame(
            {
                "open": [1.0],
                "high": [1.0],
                "low": [1.0],
                "close": [1.0],
                "volume": [1.0],
            },
            index=pd.DatetimeIndex([pd.Timestamp("2025-01-01T00:00:00Z")]),
        )

    monkeypatch.setenv("MARKET_DATA_CACHE_TTL", "900")
    monkeypatch.setattr(provider, "_fetch_bars_cached", fake_cached)
    monkeypatch.setattr(provider.time_module, "time", lambda: 1801)

    provider.fetch_ohlcv(
        symbol="AAPL",
        asset_class="equity",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 2),
        timeframe="1D",
    )

    assert captured["cache_bin"] == 2


def test_fetch_ohlcv_fail_closed_without_synthetic_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_cached(**kwargs):  # noqa: ANN003, ARG001
        raise ValueError("market_data_unavailable")

    monkeypatch.setattr(provider, "_fetch_bars_cached", fake_cached)

    with pytest.raises(ValueError, match="market_data_unavailable"):
        provider.fetch_ohlcv(
            symbol="AAPL",
            asset_class="equity",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 2),
            timeframe="1D",
        )


def test_resolve_asset_aliases_and_caches_universe(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    def fake_load_assets() -> dict[str, ResolvedAsset]:
        calls["count"] += 1
        mapping: dict[str, ResolvedAsset] = {}
        assets._add_aliases(
            mapping,
            ResolvedAsset(
                canonical_symbol="AAPL",
                asset_class="equity",
                name="Apple Inc.",
                raw_symbol="AAPL",
            ),
            canonical="AAPL",
        )
        assets._add_aliases(
            mapping,
            ResolvedAsset(
                canonical_symbol="BTC",
                asset_class="crypto",
                name="Bitcoin",
                raw_symbol="BTC/USD",
            ),
            canonical="BTC",
        )
        return mapping

    assets.clear_asset_cache()
    monkeypatch.setattr(assets, "_load_assets_from_alpaca", fake_load_assets)

    assert assets.resolve_asset("aapl").asset_class == "equity"
    assert assets.resolve_asset("btc/usd").canonical_symbol == "BTC"
    assert assets.resolve_asset("BTCUSD").canonical_symbol == "BTC"
    assert calls["count"] == 1


def test_resolve_asset_rejects_unknown_symbol(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_load_assets() -> dict[str, ResolvedAsset]:
        mapping: dict[str, ResolvedAsset] = {}
        assets._add_aliases(
            mapping,
            ResolvedAsset(
                canonical_symbol="AAPL",
                asset_class="equity",
                name="Apple Inc.",
                raw_symbol="AAPL",
            ),
            canonical="AAPL",
        )
        return mapping

    assets.clear_asset_cache()
    monkeypatch.setattr(assets, "_load_assets_from_alpaca", fake_load_assets)

    with pytest.raises(ValueError, match="invalid_symbol"):
        assets.resolve_asset("NOTREAL")
