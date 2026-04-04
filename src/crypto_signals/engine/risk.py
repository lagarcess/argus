from typing import NamedTuple, Optional

import pandas as pd
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import AssetClass as AlpacaAssetClass
from alpaca.trading.enums import OrderSide, QueryOrderStatus
from alpaca.trading.models import TradeAccount
from alpaca.trading.requests import GetOrdersRequest
from crypto_signals.config import get_settings
from crypto_signals.domain.schemas import AssetClass, Signal
from crypto_signals.market.data_provider import MarketDataProvider
from crypto_signals.repository.firestore import PositionRepository
from loguru import logger


class RiskCheckResult(NamedTuple):
    passed: bool
    reason: Optional[str] = None
    gate: Optional[str] = None

    def __bool__(self) -> bool:
        return self.passed


class RiskEngine:
    """
    Capital Preservation Layer.

    Enforces pre-trade risk checks:
    1. Buying Power Checks (Reg-T vs Cash)
    2. Sector Exposure Limits (Max Positions)
    3. Daily Account Drawdown Limits
    """

    def __init__(
        self,
        trading_client: TradingClient,
        repository: PositionRepository,
        market_provider: Optional[MarketDataProvider] = None,
    ):
        self.alpaca = trading_client
        self.repo = repository
        self.market_provider = market_provider
        self.settings = get_settings()

    ASSET_CLASS_MAP = {
        AssetClass.CRYPTO: AlpacaAssetClass.CRYPTO,
        AssetClass.EQUITY: AlpacaAssetClass.US_EQUITY,
    }

    def validate_signal(self, signal: Signal) -> RiskCheckResult:
        """
        Orchestrate all risk checks for a signal.
        order matters: Fail fast on cheapest checks first.
        """
        # 1. Daily Drawdown
        drawdown_check = self.check_daily_drawdown()
        if not drawdown_check.passed:
            return drawdown_check

        # 2. Duplicate Symbol Check
        duplicate_check = self.check_duplicate_symbol(signal)
        if not duplicate_check.passed:
            return duplicate_check

        # 3. Sector Limits
        sector_check = self.check_sector_limit(signal.asset_class)
        if not sector_check.passed:
            return sector_check

        # 4. Correlation Risk
        correlation_check = self.check_correlation(signal)
        if not correlation_check.passed:
            return correlation_check

        # 5. Buying Power
        # Note: Using RISK_PER_TRADE as cost estimate since qty not yet calculated.
        bp_check = self.check_buying_power(
            signal.asset_class, self.settings.MIN_ASSET_BP_USD
        )
        if not bp_check.passed:
            return bp_check

        return RiskCheckResult(passed=True)

    def check_daily_drawdown(self) -> RiskCheckResult:
        """
        Gate: Daily Account Drawdown.
        Formula: (Equity - LastEquity) / LastEquity
        """
        try:
            account = self.alpaca.get_account()
            if not isinstance(account, TradeAccount):
                logger.warning(
                    "Could not verify drawdown - account object is not a TradeAccount."
                )
                return RiskCheckResult(passed=True)  # Fail open if account fetch fails
            equity = float(account.equity)
            last_equity = float(account.last_equity)

            # Avoid div by zero
            if last_equity == 0:
                return RiskCheckResult(passed=True)

            drawdown_pct = (equity - last_equity) / last_equity

            # Drawdown is negative value. e.g. -0.05 is 5% loss.
            # Limit is positive float e.g. 0.02 (2%)
            # If current drawdown is -0.05, and limit is 0.02 (-0.02 threshold)

            threshold = -abs(self.settings.MAX_DAILY_DRAWDOWN_PCT)
            if drawdown_pct < threshold:
                reason = f"Daily Drawdown Limit Hit: {drawdown_pct:.2%} < {threshold:.2%}"
                logger.warning(reason)
                return RiskCheckResult(passed=False, reason=reason, gate="drawdown")

            return RiskCheckResult(passed=True)

        except Exception as e:
            logger.error("Risk Check Failed (Drawdown).", extra={"error": str(e)})
            # Fail safe: If we can't verify risk, we block.
            return RiskCheckResult(
                passed=False, reason=f"Error checking drawdown: {e}", gate="drawdown"
            )

    def check_duplicate_symbol(self, signal: Signal) -> RiskCheckResult:
        """
        Gate: Prevent multiple positions for same symbol (Pyramiding).
        """
        try:
            open_positions = self.repo.get_open_positions()
            for pos in open_positions:
                if pos.symbol == signal.symbol:
                    reason = f"Duplicate Position: {signal.symbol} is already open ({pos.position_id})"
                    logger.warning(reason)
                    return RiskCheckResult(passed=False, reason=reason, gate="duplicate")

            return RiskCheckResult(passed=True)

        except Exception as e:
            logger.error("Risk Check Failed (Duplicate).", extra={"error": str(e)})
            return RiskCheckResult(
                passed=False, reason=f"Error checking duplicate: {e}", gate="duplicate"
            )

    def check_sector_limit(self, asset_class: AssetClass) -> RiskCheckResult:
        """
        Gate: Max Open Positions by Asset Class.
        Uses Alpaca API as source of truth to avoid stale Firestore data bypass.
        Counts both filled positions AND pending buy orders to prevent race conditions.
        """
        try:
            limit = (
                self.settings.MAX_CRYPTO_POSITIONS
                if asset_class == AssetClass.CRYPTO
                else self.settings.MAX_EQUITY_POSITIONS
            )

            # Map domain AssetClass to Alpaca Enum explicitly
            if asset_class not in self.ASSET_CLASS_MAP:
                logger.error(f"Unknown Asset Class in Sector Check: {asset_class}")
                return RiskCheckResult(
                    passed=False,
                    reason=f"Unknown Asset Class: {asset_class}",
                    gate="sector_cap",
                )

            target_alpaca_class = self.ASSET_CLASS_MAP[asset_class]

            # 1. Fetch Authoritative State (Filled Positions)
            alpaca_positions = self.alpaca.get_all_positions()
            filled_count = sum(
                1 for p in alpaca_positions if p.asset_class == target_alpaca_class
            )

            # 2. Fetch Pending Orders (Race Condition Protection)
            # If we have 4 positions and 2 pending buys, effectively we have 6.
            # Only counting BUY side.
            orders_req = GetOrdersRequest(status=QueryOrderStatus.OPEN)
            open_orders = self.alpaca.get_orders(filter=orders_req)

            pending_buys = sum(
                1
                for o in open_orders
                if o.asset_class == target_alpaca_class and o.side == OrderSide.BUY
            )

            total_exposure = filled_count + pending_buys

            if total_exposure >= limit:
                reason = (
                    f"Max {asset_class.value} positions reached: "
                    f"{total_exposure}/{limit} "
                    f"({filled_count} filled + {pending_buys} pending)"
                )
                logger.warning(reason)
                return RiskCheckResult(passed=False, reason=reason, gate="sector_cap")

            return RiskCheckResult(passed=True)

        except Exception as e:
            logger.error("Risk Check Failed (Sector Cap).", extra={"error": str(e)})
            return RiskCheckResult(
                passed=False, reason=f"Error checking sector cap: {e}", gate="sector_cap"
            )

    def check_correlation(self, signal: Signal) -> RiskCheckResult:
        """
        Gate: Correlation Risk.
        Rejects trade if highly correlated (>0.8) with any open position.
        Optimized to fetch market data in batches per asset class.
        """
        if not self.market_provider:
            return RiskCheckResult(passed=True, reason="Skipped: No Market Provider")

        try:
            open_positions = self.repo.get_open_positions()
            if not open_positions:
                return RiskCheckResult(passed=True)

            # Group symbols by Asset Class to batch requests
            # We want to check correlation against ALL open positions.
            # We also need the candidate signal's data.

            # Map: AssetClass -> set(symbols)
            symbols_by_class = {AssetClass.CRYPTO: set(), AssetClass.EQUITY: set()}

            # Add candidate
            symbols_by_class[signal.asset_class].add(signal.symbol)

            # Add open positions (excluding self if somehow in list)
            filtered_positions = [p for p in open_positions if p.symbol != signal.symbol]
            if not filtered_positions:
                # If only open position is self (re-entry?), no correlation check needed against others
                return RiskCheckResult(passed=True)

            for pos in filtered_positions:
                symbols_by_class[pos.asset_class].add(pos.symbol)

            # Fetch Data Batches
            # Map: symbol -> pd.Series (Close prices)
            price_series_map = {}

            for asset_class, symbols in symbols_by_class.items():
                if not symbols:
                    continue

                symbol_list = list(symbols)
                try:
                    # Batch fetch
                    bars_df = self.market_provider.get_daily_bars(
                        symbol_list, asset_class, lookback_days=90
                    )

                    # Process response
                    # If single symbol passed (list of length 1), it might return single-index DF depending on impl details,
                    # but our updating logic says: "If list of symbols: MultiIndex DataFrame".
                    # However, if we pass a list of length 1, let's be robust.

                    if isinstance(bars_df.index, pd.MultiIndex):
                        # MultiIndex: (symbol, timestamp)
                        # We want to extract close price for each symbol
                        # Efficient way: loop through unique symbols in index
                        # distinct_symbols = bars_df.index.get_level_values(0).unique()
                        # But better to just iterate over what we requested

                        for sym in symbol_list:
                            try:
                                # xs is robust for selecting from MultiIndex
                                # Check if symbol exists in index first to avoid KeyError
                                if sym in bars_df.index.get_level_values(0):
                                    sym_data = bars_df.xs(sym, level=0)
                                    if "close" in sym_data.columns:
                                        price_series_map[sym] = sym_data["close"]
                            except KeyError:
                                continue
                    else:
                        # Single index (timestamp) - implies only one symbol was returned/requested
                        # OR the provider stripped the index.
                        # Since we modified provider to keep MultiIndex if list is passed, this shouldn't happen
                        # unless we passed a list of 1 and logic was ambiguous?
                        # Actually, my change says: `if isinstance(symbol, str)`.
                        # So if we pass `["BTC/USD"]`, it is NOT a str, so it should keep MultiIndex.
                        # EXCEPT if the API returns a single-level DF naturally for some reason (which it usually doesn't for bars).
                        # But let's handle the case if it somehow is single index:
                        if len(symbol_list) == 1:
                            if "close" in bars_df.columns:
                                price_series_map[symbol_list[0]] = bars_df["close"]

                except Exception as e:
                    logger.warning(
                        f"Failed to fetch batch data for {asset_class.value}.",
                        extra={"asset_class": asset_class.value, "error": str(e)},
                    )
                    # If we fail to get data for the CANDIDATE, we must fail.
                    # If we fail to get data for a position, we normally block access.
                    # Let's inspect what's missing later.

            # Check if we have candidate data
            if signal.symbol not in price_series_map:
                return RiskCheckResult(
                    passed=False,
                    reason=f"Market data missing for candidate {signal.symbol}",
                    gate="correlation",
                )

            candidate_series = price_series_map[signal.symbol]

            # Compare against all open positions
            for pos in filtered_positions:
                if pos.symbol not in price_series_map:
                    logger.warning(
                        f"Market data for existing position {pos.symbol} is missing. Blocking trade precautiously."
                    )
                    return RiskCheckResult(
                        passed=False,
                        reason=f"Could not verify correlation due to missing data for {pos.symbol}",
                        gate="correlation",
                    )

                pos_series = price_series_map[pos.symbol]

                try:
                    # Pandas corr handles alignment via index (dates)
                    correlation = candidate_series.corr(pos_series)

                    if correlation is not None and correlation > 0.8:
                        reason = (
                            f"Correlation Risk: {signal.symbol} is {correlation:.2f} "
                            f"correlated with existing position {pos.symbol}"
                        )
                        logger.warning(reason)
                        return RiskCheckResult(
                            passed=False, reason=reason, gate="correlation"
                        )
                except Exception as e:
                    logger.warning(
                        f"Correlation calc error for {pos.symbol}.",
                        extra={"symbol": pos.symbol, "error": str(e)},
                    )
                    return RiskCheckResult(
                        passed=False,
                        reason=f"Error calculating correlation with {pos.symbol}: {e}",
                        gate="correlation",
                    )

            return RiskCheckResult(passed=True)

        except Exception as e:
            logger.error("Risk Check Failed (Correlation).", extra={"error": str(e)})
            return RiskCheckResult(
                passed=False,
                reason=f"Error checking correlation: {e}",
                gate="correlation",
            )

    def check_buying_power(
        self, asset_class: AssetClass, required_amount: float
    ) -> RiskCheckResult:
        """
        Gate: Buying Power.
        Crypto -> non_marginable_buying_power (Cash)
        Equity -> regt_buying_power (Overnight hold safety)
        """
        try:
            account = self.alpaca.get_account()

            if not isinstance(account, TradeAccount):
                logger.warning(
                    "Could not verify buying power - account object is not a TradeAccount."
                )
                return RiskCheckResult(passed=True)
            if asset_class == AssetClass.CRYPTO:
                available = float(account.non_marginable_buying_power)
                bp_type = "Cash (Crypto)"
            else:
                # Use Reg-T for safety against PDT/Overnight holds
                available = float(account.regt_buying_power)
                bp_type = "Reg-T Margin (Equity)"

            if available < required_amount:
                reason = (
                    f"Insufficient Buying Power ({bp_type}): "
                    f"${available:.2f} < ${required_amount:.2f} (Min Req)"
                )
                logger.warning(reason)
                return RiskCheckResult(passed=False, reason=reason, gate="buying_power")

            return RiskCheckResult(passed=True)

        except Exception as e:
            logger.error("Risk Check Failed (Buying Power).", extra={"error": str(e)})
            return RiskCheckResult(
                passed=False,
                reason=f"Error checking buying power: {e}",
                gate="buying_power",
            )
