from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from loguru import logger

from argus.api.dependencies import current_user
from argus.api.schemas import DiscoveryItem, DiscoveryResponse, User
from argus.domain.indicators import search_indicators
from argus.domain.market_data import search_assets

router = APIRouter(prefix="/api/v1", tags=["discovery"])

_INDICATOR_SUPPORT_STATUS = {
    "executable": "supported",
    "supported": "supported",
    "draftable": "draft_only",
    "draft_only": "draft_only",
    "searchable": "draft_only",
    "searchable_only": "draft_only",
    "unavailable": "unavailable",
}


def display_asset_class(asset_class: str) -> str:
    labels = {
        "equity": "Stock",
        "crypto": "Crypto",
        "currency_pair": "Currency Pair",
    }
    return labels.get(asset_class, asset_class.replace("_", " ").title())


def discovery_asset_provider(asset_class: str, provider: str | None = None) -> str:
    normalized_provider = (provider or "").strip().lower()
    if normalized_provider and normalized_provider != "unknown":
        return normalized_provider
    if asset_class == "currency_pair":
        return "kraken"
    return "alpaca"


def discovery_support_status(status: str | None) -> str:
    return _INDICATOR_SUPPORT_STATUS.get((status or "").strip().lower(), "draft_only")


@router.get("/discovery/assets", response_model=DiscoveryResponse)
def discovery_assets(
    q: str = Query("", max_length=80),
    limit: int = Query(12, ge=1, le=25),
    user: User = Depends(current_user),  # noqa: B008
) -> DiscoveryResponse:
    del user
    query = q.strip()
    if not query:
        return DiscoveryResponse(items=[])
    try:
        assets = search_assets(query, limit=limit)
    except Exception as exc:
        logger.warning("Asset discovery unavailable", error=str(exc))
        return DiscoveryResponse(items=[])
    return DiscoveryResponse(
        items=[
            DiscoveryItem(
                id=f"asset:{asset.asset_class}:{asset.canonical_symbol}",
                type="asset",
                label=(
                    f"{asset.canonical_symbol} \u00b7 {asset.name}"
                    if asset.name
                    else asset.canonical_symbol
                ),
                symbol=asset.canonical_symbol,
                asset_class=asset.asset_class,
                description=display_asset_class(asset.asset_class),
                insert_text=asset.canonical_symbol,
                provider=discovery_asset_provider(asset.asset_class, asset.provider),
                support_status="supported",
            )
            for asset in assets
        ]
    )


@router.get("/discovery/indicators", response_model=DiscoveryResponse)
def discovery_indicators(
    q: str = Query("", max_length=80),
    limit: int = Query(12, ge=1, le=25),
    user: User = Depends(current_user),  # noqa: B008
) -> DiscoveryResponse:
    del user
    query = q.strip()
    if not query:
        return DiscoveryResponse(items=[])
    indicators = [
        indicator
        for indicator in search_indicators(query, limit=limit)
        if discovery_support_status(indicator.support_status) == "supported"
    ]
    # Deferred(private-alpha-discovery): unsupported indicator mentions belong to
    # the future Research Lab/draft flow, not this launch discovery surface.
    return DiscoveryResponse(
        items=[
            DiscoveryItem(
                id=f"indicator:{indicator.key}",
                type="indicator",
                label=indicator.label,
                symbol=indicator.key,
                description=indicator.description,
                insert_text=indicator.key.upper(),
                provider="pandas-ta-classic",
                support_status=discovery_support_status(indicator.support_status),
            )
            for indicator in indicators
        ]
    )


_display_asset_class = display_asset_class
_discovery_asset_provider = discovery_asset_provider
_discovery_support_status = discovery_support_status
