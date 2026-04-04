"""
Trade Archival Pipeline.

This pipeline moves CLOSED positions from Firestore (Operational)
to BigQuery (Analytical). It enriches the data by fetching exact execution
details (fees, fill times) from the Alpaca API.

Pattern: "Enrich-Extract-Load"
1. Extract: Get CLOSED positions from Firestore.
2. Transform: Call Alpaca API for each position to get truth data (fees, times).
3. Load: Push to BigQuery via BasePipeline (Truncate->Staging->Merge).
"""

import time
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, List

import pandas as pd
from alpaca.common.exceptions import APIError
from google.cloud import firestore
from google.cloud.firestore import FieldFilter
from loguru import logger
from pydantic import BaseModel

from crypto_signals.config import (
    get_crypto_data_client,
    get_stock_data_client,
    get_trading_client,
)
from crypto_signals.domain.schemas import ExitReason, OrderSide, TradeExecution
from crypto_signals.market.data_provider import MarketDataProvider
from crypto_signals.pipelines.base import BigQueryPipelineBase


class TradeArchivalPipeline(BigQueryPipelineBase):
    """
    Pipeline to archive closed trades from Firestore to BigQuery.

    Enriches Firestore data with precise execution details from Alpaca.
    """

    def __init__(self, execution_engine: Any | None = None):
        """Initialize the pipeline with specific configuration."""
        # settings is available via self.settings after super().__init__
        super().__init__(
            job_name="trade_archival",
            staging_table_id=None,
            fact_table_id="",  # Placeholder
            id_column="trade_id",
            partition_column="ds",
            schema_model=TradeExecution,
        )

        env_suffix = "" if self.settings.ENVIRONMENT == "PROD" else "_test"
        self.fact_table_id = f"{self.settings.GOOGLE_CLOUD_PROJECT}.crypto_analytics.fact_trades{env_suffix}"

        # Initialize Source Clients
        # Note: We use the project from settings, same as BQ
        self.firestore_client = firestore.Client(
            project=self.settings.GOOGLE_CLOUD_PROJECT
        )

        # Environment-aware collection routing
        self.source_collection = (
            "live_positions" if self.settings.ENVIRONMENT == "PROD" else "test_positions"
        )

        self.alpaca = get_trading_client()

        # Initialize MarketDataProvider with required clients
        stock_client = get_stock_data_client()
        crypto_client = get_crypto_data_client()
        self.market_provider = MarketDataProvider(stock_client, crypto_client)

        # Initialize ExecutionEngine for fee tier queries (Issue #140)
        # Use injected instance if available, else create new (backward compatibility)
        if execution_engine:
            self.execution_engine = execution_engine
        else:
            from crypto_signals.engine.execution import ExecutionEngine

            self.execution_engine = ExecutionEngine()

    def _get_actual_fees(
        self, alpaca_order_id: str | None, symbol: str, side: str
    ) -> float | None:
        """
        Fetch actual fees (CFEE) from Alpaca Activities API.

        Args:
            alpaca_order_id: The Alpaca Order ID (UUID).
            symbol: Trading pair symbol (e.g., "BTC/USD").
            side: Order side ("buy" or "sell").

        Returns:
            float: Total fees in USD, or None if no activities found.
        """
        if not alpaca_order_id:
            return None

        try:
            # Fetch recent account activities (CFEE = Crypto Fee)
            # Filter by date/type/direction via API parameters to optimize?
            # alpaca-py `get_account_activities` supports `activity_types`.
            # Note: We can't filter by order_id in the API call, must filter in client.
            # Fetching last 100 CFEE activities should cover recent trades.

            # Fetch recent account activities (CFEE = Crypto Fee)
            # Use public .get() method which handles params correctly in most SDK versions
            activities = self.alpaca.get(
                "/account/activities", {"activity_types": "CSD,CFEE"}
            )

            # Filter for this specific order
            # CFEE activities link to order_id (sometimes in 'id' or separate field depending on SDK version)
            # Inspecting common pattern: activity.order_id should match.
            related_activities = [
                a
                for a in activities
                if isinstance(a, dict) and str(a.get("order_id")) == alpaca_order_id
            ]

            if not related_activities:
                return None

            total_fee_usd = 0.0

            for activity in related_activities:
                # activity['qty'] is the fee amount
                # activity['price'] is the fill price (exchange rate) at that moment
                # activity['symbol'] is the asset

                qty_val = activity.get("qty")
                fee_qty = float(qty_val) if qty_val else 0.0

                # Determine currency of the fee
                # Note: 'price' in Activity might be None for some types.
                price_val = activity.get("price")
                price = float(price_val) if price_val else 0.0

                # Buy orders: Fee is in Asset (e.g., BTC). Conver to USD.
                # Sell orders: Fee is in USD (deducted from proceeds).
                if side.lower() == "buy":
                    # Fee is in Asset. Convert to USD.
                    # Assumption: price is the USD price of the asset at execution.
                    fee_value = fee_qty * price
                else:
                    # Fee is in USD (deducted from proceeds).
                    fee_value = fee_qty

                total_fee_usd += fee_value

            return total_fee_usd

        except Exception as e:
            logger.warning(
                f"Failed to fetch actual fees for order {alpaca_order_id}: {e}"
            )
            return None

    def extract(self) -> List[Any]:
        """
        Extract CLOSED positions from Firestore.

        Returns:
            List[dict]: List of raw position dictionaries.
        """
        logger.info(f"[{self.job_name}] extracting CLOSED positions from Firestore...")

        # Query CLOSED positions (deleted after successful merge via cleanup)
        docs = (
            self.firestore_client.collection(self.source_collection)
            .where(filter=FieldFilter("status", "==", "CLOSED"))
            .stream()
        )

        raw_data = []
        for doc in docs:
            data = doc.to_dict()
            if data:
                raw_data.append(data)

        logger.info(f"[{self.job_name}] extracted {len(raw_data)} closed positions.")
        return raw_data

    def transform(self, raw_data: List[Any]) -> List[dict]:
        """
        Enrich raw Firestore positions with Alpaca execution details.

        Args:
            raw_data: List of position dictionaries from Firestore.

        Returns:
            List[dict]: Enriched data matching TradeExecution schema (as dicts).
        """
        logger.info(
            f"[{self.job_name}] Enriching {len(raw_data)} trades with Alpaca data..."
        )

        transformed = []

        # Symbol-based cache to prevent redundant API calls
        # Key: f"{symbol}_{asset_class}", Value: DataFrame of daily bars
        symbol_bars_cache: dict = {}

        for idx, pos in enumerate(raw_data):
            # Rate Limit Safety: Sleep 100ms between requests
            # (skip before first request)
            if idx > 0:
                time.sleep(0.1)

            try:
                # 1. Fetch Order Details from Alpaca to get Fees and Exact Times
                # The position_id in Firestore IS the Client Order ID from Alpaca
                # (idempotency key)
                client_order_id = pos.get("position_id")

                try:
                    # Fetch order by client_order_id to ensure we get the specific trade
                    order = self.alpaca.get_order_by_client_id(client_order_id)
                except APIError as e:
                    # Specific handling for 404/Not Found
                    # In Alpaca, the HTTP status code may live on the nested
                    # http_error object.
                    status_code = getattr(
                        getattr(e, "http_error", None), "status_code", None
                    )
                    if status_code == 404 or "not found" in str(e).lower():
                        logger.warning(
                            f"[{self.job_name}] Order {client_order_id} not found in Alpaca. "
                            "Assuming Theoretical/Paper trade. Falling back to Firestore data."
                        )
                        # Create synthetic order from Firestore data
                        # Robustness: Ensure qty is handled if missing
                        qty_fallback = pos.get("qty", 0.0) or 0.0
                        order = SimpleNamespace(
                            id=None,
                            filled_avg_price=pos.get("entry_fill_price") or 0.0,
                            filled_qty=qty_fallback,
                            side=pos.get("side", "buy").lower(),
                        )
                    else:
                        raise e

                # Cast order to Any to avoid MyPy 'dict' inference errors (Issue #114)
                from typing import Any, cast

                order = cast(Any, order)

                # 2. Calculate Derived Metrics
                # Note: Alpaca 'filled_avg_price' is the source of truth
                # for execution price
                if isinstance(order, SimpleNamespace):
                    entry_price_val = float(order.filled_avg_price or 0.0)
                    qty = float(order.filled_qty or 0.0)
                else:
                    entry_price_val = (
                        float(order.filled_avg_price) if order.filled_avg_price else 0.0
                    )
                    qty = float(order.filled_qty) if order.filled_qty else 0.0

                # Target price from original Signal (stored in Firestore position)
                # This is the price we *intended* to enter at
                # Use target_entry_price if available, fallback to entry_fill_price for legacy
                target_price = float(
                    pos.get("target_entry_price")
                    if pos.get("target_entry_price") is not None
                    else (pos.get("entry_fill_price") or 0.0)
                )

                # Source of Truth: Alpaca Order Side (Entry Order)
                # Cast to string to handle Enum or str types robustly
                # Cast order to Any to avoid MyPy 'dict' inference error
                from typing import cast

                order_any = cast(Any, order)

                alpaca_order_id = (
                    str(order_any.id) if tuple([order_any.id]) and order_any.id else None
                )

                order_side_str = str(order_any.side).lower()

                # Get exit price from Firestore document, default to 0.0 if missing
                exit_price_val = float(pos.get("exit_fill_price", 0.0))

                # exit_price_val initially comes from final close
                # exit_price_val initially comes from final close
                # Weighted average will be calculated by the TradeExecution model validator
                exit_price_val = float(pos.get("exit_fill_price") or 0.0)

                # Timestamps retrieval
                entry_time_str = pos.get("entry_time")
                exit_time_str = pos.get("exit_time")

                # Extract Alpaca timestamp for fallback (filled_at or submitted_at)
                # Handle both SimpleNamespace (paper/fallback) and real Order objects
                alpaca_time = getattr(order, "filled_at", None)
                if not alpaca_time:
                    alpaca_time = getattr(order, "submitted_at", None)

                # Parse or default
                position_id = pos.get("position_id")

                def parse_dt(val, fallback_val=None, pid=position_id):
                    if isinstance(val, datetime):
                        return val

                    if val:
                        try:
                            # Parse ISO string
                            return datetime.fromisoformat(str(val))
                        except (ValueError, TypeError) as exc:
                            logger.warning(
                                f"Failed to parse datetime value '{val}'; Error: {exc}"
                            )

                    # Fallback logic
                    if fallback_val:
                        # Log debug to track this correction
                        # logger.debug(f"Using fallback time {fallback_val} for missing doc time.")
                        return fallback_val

                    # Final resort: now()
                    # Only warn if we really have no data
                    logger.warning(
                        f"Missing timestamps and no fallback available for {pid}. Defaulting to NOW."
                    )
                    return datetime.now(timezone.utc)

                entry_time = parse_dt(entry_time_str, fallback_val=alpaca_time)
                # For exit, use the same alpaca_time (usually close enough for daily resolution)
                # or updated_at if available?
                # If it's a closed position, exit time is crucial.
                # Usually filled_at of the order IS the entry time.
                # But for exit_time, we might differ.
                # However, defaulting to 'entry' time is better than 'now' for historical trades.
                # Ideally we'd fetch the EXIT order too, but we only fetched one order (entry usually).
                # Re-using alpaca_time (entry) is safer for "which day" than now().
                exit_fallback = (
                    getattr(order, "filled_at", None)
                    or getattr(order, "updated_at", None)
                    or alpaca_time
                )
                exit_time = parse_dt(exit_time_str, fallback_val=exit_fallback)

                # CALCULATIONS
                # Fees: Try to fetch ACTUAL fees from Alpaca Activities (CFEE)
                fees_usd = 0.0
                fee_calculation_type = "ESTIMATED"
                fee_tier = None
                actual_fee_usd = None

                is_crypto = pos.get("asset_class") == "CRYPTO"

                if is_crypto:
                    # 1. Try Actual CFEE Lookup
                    actual_fee_usd = self._get_actual_fees(
                        alpaca_order_id, pos.get("symbol"), order_side_str
                    )

                    if actual_fee_usd is not None:
                        fees_usd = actual_fee_usd
                        fee_calculation_type = "ACTUAL_CFEE"
                        logger.debug(
                            f"Using ACTUAL fees for {pos.get('symbol')}: ${fees_usd:.2f}"
                        )
                    else:
                        # 2. Fallback to Estimation
                        # Get current fee tier for accurate estimate
                        tier_info = self.execution_engine.get_current_fee_tier()

                        # Use taker fee (conservative, most trades are takers)
                        taker_fee_pct = tier_info["taker_fee_pct"]
                        fee_tier = tier_info["tier_name"]

                        # Fee = (Entry Value + Exit Value) * taker_fee_pct / 100
                        entry_val = entry_price_val * qty
                        exit_val = exit_price_val * qty
                        fees_usd = (entry_val + exit_val) * (taker_fee_pct / 100.0)

                        logger.debug(
                            f"Using ESTIMATED fees for {pos.get('symbol')}: ${fees_usd:.2f} ({fee_tier})"
                        )

                # PnL Calculation using ALPACA entry price (Truth) vs
                # Firestore Exit Price
                pnl_gross = (exit_price_val - entry_price_val) * qty

                if order_side_str == OrderSide.SELL.value:  # Short
                    pnl_gross = (entry_price_val - exit_price_val) * qty

                # --- MFE Calculation ---
                max_favorable_excursion = None
                try:
                    # Build cache key from symbol and asset class
                    symbol = pos.get("symbol")
                    asset_class = pos.get("asset_class", "CRYPTO")
                    cache_key = f"{symbol}_{asset_class}"

                    # Check cache before fetching
                    if cache_key in symbol_bars_cache:
                        bars_df = symbol_bars_cache[cache_key]
                    else:
                        # Fetch bars and store in cache
                        bars_df = self.market_provider.get_daily_bars(
                            symbol=symbol,
                            asset_class=asset_class,
                            lookback_days=None,
                        )
                        symbol_bars_cache[cache_key] = bars_df

                    if not bars_df.empty:
                        # Filter for trade window
                        trade_window = bars_df[
                            (bars_df.index >= pd.Timestamp(entry_time).floor("D"))
                            & (bars_df.index <= pd.Timestamp(exit_time).ceil("D"))
                        ]

                        if not trade_window.empty:
                            if order_side_str == OrderSide.BUY.value:
                                highest_price = trade_window["high"].max()
                                max_favorable_excursion = highest_price - entry_price_val
                            else:  # Short
                                lowest_price = trade_window["low"].min()
                                mfe = entry_price_val - lowest_price
                                max_favorable_excursion = mfe

                except Exception as e:
                    logger.warning(
                        f"Failed to calculate MFE for {pos.get('position_id')}: {e}"
                    )

                pnl_usd = pnl_gross - fees_usd

                # PnL % should be a percentage value (e.g. 5.0 for 5%), not a ratio
                cost_basis = entry_price_val * qty
                pnl_pct = (pnl_usd / cost_basis * 100.0) if cost_basis else 0.0

                # Slippage Calculation (Direction-Aware)
                # For LONG: positive slippage = filled higher (unfavorable)
                # For SHORT: positive slippage = filled lower (unfavorable)
                if target_price:
                    if order_side_str == OrderSide.BUY.value:  # Long
                        # Long: filled higher than target = positive slippage (bad)
                        slippage_pct = round(
                            ((entry_price_val - target_price) / target_price * 100.0), 4
                        )
                    else:  # Short
                        # Short: filled lower than target = positive slippage (bad)
                        # Inverted formula: (target - actual) / target
                        slippage_pct = round(
                            ((target_price - entry_price_val) / target_price * 100.0), 4
                        )
                else:
                    slippage_pct = 0.0

                duration = int((exit_time - entry_time).total_seconds())

                # Construct Model
                trade = TradeExecution(
                    ds=entry_time.date(),
                    trade_id=pos.get("position_id"),
                    account_id=pos.get("account_id"),
                    strategy_id=pos.get("strategy_id") or "UNKNOWN",
                    asset_class=pos.get("asset_class", "CRYPTO"),
                    symbol=pos.get("symbol"),
                    side=pos.get("side"),
                    qty=qty,  # Authenticated from Alpaca
                    entry_price=entry_price_val,  # Authenticated from Alpaca
                    exit_price=exit_price_val,  # Will be weighted-averaged by model!
                    entry_time=entry_time,
                    exit_time=exit_time,
                    pnl_usd=round(pnl_usd, 2),
                    pnl_pct=round(pnl_pct, 4),
                    fees_usd=round(fees_usd, 2),
                    slippage_pct=slippage_pct,
                    trade_duration=duration,
                    exit_reason=ExitReason(pos.get("exit_reason", ExitReason.TP1.value)),
                    max_favorable_excursion=max_favorable_excursion,
                    # Propagate Discord thread_id for social context analytics
                    discord_thread_id=pos.get("discord_thread_id"),
                    # Propagate final trailing stop for Runner (TP3) exit analysis
                    trailing_stop_final=pos.get("trailing_stop_final"),
                    # New fields for slippage analysis and broker auditability
                    target_entry_price=target_price,
                    alpaca_order_id=alpaca_order_id,
                    # Exit order ID for reconciliation and fill tracking
                    exit_order_id=pos.get("exit_order_id"),
                    # CFEE Reconciliation Fields (Issue #140)
                    fee_finalized=(
                        fee_calculation_type == "ACTUAL_CFEE"
                    ),  # Finalized if we got actuals
                    actual_fee_usd=actual_fee_usd,  # Populated if found
                    fee_calculation_type=fee_calculation_type,
                    fee_tier=fee_tier,  # e.g., "Tier 0"
                    entry_order_id=pos.get("entry_order_id"),  # For CFEE attribution
                    fee_reconciled_at=(
                        datetime.now(timezone.utc)
                        if fee_calculation_type == "ACTUAL_CFEE"
                        else None
                    ),
                    # PASS THROUGH FIELDS FOR MODEL LOGIC
                    scaled_out_prices=pos.get("scaled_out_prices", []),
                    original_qty=pos.get("original_qty"),
                )

                # Validate and Dump to JSON (BasePipeline expects dicts)
                transformed.append(trade.model_dump(mode="json"))

            except Exception as e:
                # Log error but don't stop the whole batch?
                # For now, log and skip specific bad records to avoid blocking
                # the pipeline.
                logger.error(
                    f"[{self.job_name}] Failed to transform position "
                    f"{pos.get('position_id')}: {e}"
                )
                continue

        return transformed

    def cleanup(self, data: List[BaseModel]) -> None:
        """
        Delete processed positions from Firestore.

        Args:
            data: List of successfully loaded TradeExecution models.
        """
        if not data:
            return

        logger.info(
            f"[{self.job_name}] Cleaning up {len(data)} records from Firestore..."
        )

        # Batch delete
        batch = self.firestore_client.batch()
        count = 0

        for item in data:
            if isinstance(item, TradeExecution):
                # item is now a TradeExecution Pydantic model
                # We need the Original ID used in Firestore.
                # In transform, we mapped trade_id -> position_id.
                doc_id = item.trade_id

                # Assumption: Firestore Doc ID == position_id
            # (which is usually true in this design)
            # If Doc ID was random, we'd need to have passed it through.
            # Let's assume Doc ID KEY strategy is used or we query ID.
            # Usually: collection('live_positions').document(position_id)
            ref = self.firestore_client.collection(self.source_collection).document(
                doc_id
            )
            batch.delete(ref)
            count += 1

            if count >= 400:  # Firestore batch limit is 500
                batch.commit()
                batch = self.firestore_client.batch()
                count = 0

        if count > 0:
            batch.commit()

        logger.info(f"[{self.job_name}] Cleanup complete.")
