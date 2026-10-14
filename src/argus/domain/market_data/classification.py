"""Shared symbol classification for price readers and historical metadata."""

from __future__ import annotations

from dataclasses import dataclass

from argus.domain.market_data.assets import AssetClass, resolve_asset


@dataclass(frozen=True)
class SymbolAsset:
    symbol: str
    asset_class: AssetClass


def classify_symbol(symbol: str, *, resolve_asset_func=resolve_asset) -> SymbolAsset:
    resolved = resolve_asset_func(symbol)
    return SymbolAsset(symbol=resolved.canonical_symbol, asset_class=resolved.asset_class)
