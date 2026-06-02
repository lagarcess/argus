from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from argus.agent_runtime.asset_text_grounding import (
    ResolveAssetCandidate,
    provider_ticker_mentions_from_text,
)


def current_message_has_extra_provider_asset_for_benchmark(
    draft: Any,
    *,
    current_message: str,
    resolved_asset_mentions: Iterable[Any],
    resolve_candidate: ResolveAssetCandidate,
) -> bool:
    """Detect omitted benchmark assets from provider-grounded current-turn facts."""

    draft_symbols = _normalized_symbols(getattr(draft, "asset_universe", []))
    if not draft_symbols:
        return False

    draft_asset_class = str(getattr(draft, "asset_class", "") or "").strip()
    current_assets = [
        *resolved_asset_mentions,
        *provider_ticker_assets_from_text(
            current_message,
            resolve_candidate=resolve_candidate,
        ),
    ]
    seen_symbols: set[str] = set()
    for asset in current_assets:
        symbol = str(getattr(asset, "canonical_symbol", "") or "").strip().upper()
        if not symbol or symbol in seen_symbols or symbol in draft_symbols:
            continue
        seen_symbols.add(symbol)
        asset_class = str(getattr(asset, "asset_class", "") or "").strip()
        if draft_asset_class and asset_class and asset_class != draft_asset_class:
            continue
        return True
    return False


def provider_ticker_assets_from_text(
    text: str,
    *,
    resolve_candidate: ResolveAssetCandidate,
    limit: int = 5,
) -> list[Any]:
    return [
        mention.asset
        for mention in provider_ticker_mentions_from_text(
            text,
            resolve_candidate=resolve_candidate,
            limit=limit,
        )
    ]


def _normalized_symbols(values: Iterable[Any]) -> set[str]:
    return {
        str(value or "").strip().upper()
        for value in values
        if str(value or "").strip()
    }
