"""
Asset Validation Service.

This module provides pre-flight validation of portfolio symbols against Alpaca's
live asset status, filtering out inactive or non-tradable symbols before processing.
"""

import logging
from typing import List

from alpaca.common.exceptions import APIError
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import AssetClass as AlpacaAssetClass
from alpaca.trading.enums import AssetStatus
from alpaca.trading.models import Asset
from alpaca.trading.requests import GetAssetsRequest
from crypto_signals.domain.schemas import AssetClass
from crypto_signals.observability import log_critical_situation
from loguru import logger
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


class AssetValidationService:
    """
    Pre-flight validator for portfolio symbols against Alpaca's asset API.

    Fetches all assets of a given class once, then filters locally to avoid
    hitting the 200 requests/minute API limit.
    """

    def __init__(self, trading_client: TradingClient):
        """
        Initialize with an authenticated TradingClient.

        Args:
            trading_client: Alpaca TradingClient for asset queries
        """
        self._client = trading_client

    def _normalize_symbol(self, symbol: str) -> str:
        """
        Normalize symbol for comparison with Alpaca's format.

        Alpaca uses BTCUSD format, while config may use BTC/USD.

        Args:
            symbol: Symbol from configuration (e.g., "BTC/USD")

        Returns:
            Normalized uppercase symbol without slashes (e.g., "BTCUSD")
        """
        return symbol.upper().replace("/", "")

    def _map_asset_class(self, asset_class: AssetClass) -> AlpacaAssetClass:
        """
        Map internal AssetClass enum to Alpaca's AssetClass enum.

        Args:
            asset_class: Internal asset class enum

        Returns:
            Corresponding Alpaca AssetClass enum value
        """
        if asset_class == AssetClass.CRYPTO:
            return AlpacaAssetClass.CRYPTO
        elif asset_class == AssetClass.EQUITY:
            return AlpacaAssetClass.US_EQUITY
        else:
            raise ValueError(f"Unsupported asset class: {asset_class}")

    @retry(
        retry=retry_if_exception_type((ConnectionError, TimeoutError, APIError)),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def get_valid_portfolio(
        self,
        symbols: List[str],
        asset_class: AssetClass,
    ) -> List[str]:
        """
        Filter symbols to only those active and tradable on Alpaca.

        Efficiency: Fetches all assets of the class ONCE using get_all_assets(),
        then filters locally. This avoids per-symbol API calls which would hit
        the 200 requests/minute rate limit.

        Symbol Mapping: Returns Alpaca's preferred symbol format (e.g., "BTCUSD")
        instead of the config format (e.g., "BTC/USD") to ensure subsequent
        Data API calls use the broker's expected format.

        Args:
            symbols: List of symbols from configuration (e.g., ["BTC/USD", "ETH/USD"])
            asset_class: Asset class (CRYPTO or EQUITY)

        Returns:
            List of valid Alpaca symbols that exist, are active, and are tradable
        """
        if not symbols:
            return []

        try:
            # Fetch all assets of this class in one API call
            alpaca_class = self._map_asset_class(asset_class)
            request = GetAssetsRequest(asset_class=alpaca_class)
            all_assets = self._client.get_all_assets(request)

            # Build normalized_symbol -> original_alpaca_symbol map for valid assets
            # Key: Normalized (uppercase, no slashes), Value: Alpaca's original symbol
            valid_asset_map = {}
            for asset in all_assets:
                if not isinstance(asset, Asset):
                    continue
                if asset.status == AssetStatus.ACTIVE and asset.tradable:
                    normalized = self._normalize_symbol(asset.symbol)
                    if normalized in valid_asset_map:
                        logger.warning(
                            f"Duplicate normalized symbol detected: {normalized} "
                            f"(existing: {valid_asset_map[normalized]}, new: {asset.symbol}). "
                            "Using first encountered."
                        )
                    else:
                        valid_asset_map[normalized] = asset.symbol

            # Also build a map for lookup of all assets (for error reporting)
            # Filter first to ensure type safety (Asset | str issue)
            all_asset_lookup = {
                self._normalize_symbol(a.symbol): a
                for a in all_assets
                if isinstance(a, Asset)
            }

            logger.debug(
                f"Fetched {len(all_assets)} {asset_class.value} assets, "
                f"{len(valid_asset_map)} are active and tradable"
            )

            # Filter input symbols and return Alpaca's preferred format
            valid_symbols = []
            for symbol in symbols:
                normalized = self._normalize_symbol(symbol)

                if normalized in valid_asset_map:
                    # Return Alpaca's original symbol format for API compatibility
                    alpaca_symbol = valid_asset_map[normalized]
                    valid_symbols.append(alpaca_symbol)
                    if alpaca_symbol != symbol:
                        logger.debug(f"Symbol mapped: {symbol} -> {alpaca_symbol}")
                else:
                    # Determine reason for filtering
                    matching_asset = all_asset_lookup.get(normalized)

                    if matching_asset is None:
                        reason = "Symbol not found in Alpaca's asset registry"
                    elif matching_asset.status != AssetStatus.ACTIVE:
                        reason = (
                            f"Asset status is {matching_asset.status.value} (not ACTIVE)"
                        )
                    elif not matching_asset.tradable:
                        reason = "Asset is marked as non-tradable"
                    else:
                        reason = "Unknown validation failure"

                    # Log with Rich red panel
                    log_critical_situation(
                        situation="INACTIVE ASSET SKIPPED",
                        details=f"Symbol: {symbol}\nAsset Class: {asset_class.value}\nReason: {reason}",
                        suggestion="Remove from portfolio or check Alpaca asset availability",
                    )

            logger.info(
                f"Asset validation: {len(valid_symbols)}/{len(symbols)} "
                f"{asset_class.value} symbols are valid"
            )

            return valid_symbols

        except Exception as e:
            logger.error(f"Asset validation failed for {asset_class.value}: {e}")
            # Fail-open: Return original symbols if validation fails
            # This ensures the bot can still run, and individual symbol errors
            # will be caught during data fetching
            logger.warning(
                "Proceeding with unvalidated portfolio due to validation failure"
            )
            return list(symbols)
