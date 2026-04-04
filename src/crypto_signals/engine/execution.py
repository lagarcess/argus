"""
Execution Engine for Alpaca Order Management.

This module bridges Signal objects to live Alpaca trades using Bracket Orders
for atomic Entry, Take-Profit, and Stop-Loss management.

Key Capabilities:
    - execute_signal(): Submit bracket orders with Entry, TP, and SL
    - sync_position_status(): Synchronize position with broker state
    - modify_stop_loss(): Trail stop-loss orders (for Chandelier Exits)
    - close_position_emergency(): Cancel all legs and exit at market
    - get_order_details(): Retrieve order for analytics enrichment
"""

from datetime import date, datetime, timedelta, timezone
from time import sleep
from typing import Any, Dict, List, Optional, cast

from alpaca.common.exceptions import APIError
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
from alpaca.trading.models import Order
from alpaca.trading.requests import (
    MarketOrderRequest,
    StopLossRequest,
    TakeProfitRequest,
)
from crypto_signals.config import get_settings, get_trading_client
from crypto_signals.domain.schemas import (
    AssetClass,
    ExitReason,
    Position,
    Signal,
    TradeStatus,
    TradeType,
)
from crypto_signals.domain.schemas import (
    OrderSide as DomainOrderSide,
)
from crypto_signals.engine.risk import RiskEngine
from crypto_signals.market.data_provider import MarketDataProvider
from crypto_signals.observability import console, get_metrics_collector
from crypto_signals.repository.firestore import PositionRepository
from crypto_signals.utils.symbols import normalize_alpaca_symbol
from loguru import logger
from rich.panel import Panel


class _ActivityWrapper:
    """Helper to wrap raw API dictionaries into object-like structures."""

    def __init__(self, data: Dict[str, Any]):
        self.id = data.get("id")
        self.symbol = data.get("symbol")
        self.qty = data.get("qty")
        self.price = data.get("price")
        self.date = data.get("date")
        self.description = data.get("description")


# Age guard for manual exit verification to prevent race conditions on newly opened positions
_MANUAL_EXIT_VERIFICATION_MIN_AGE_MINUTES = 5

# Statuses indicating an order has been received by Alpaca but not yet filled/canceled
_QUEUED_ORDER_STATUSES = {"accepted", "pending_new", "new"}


class ExecutionEngine:
    """
    Manages the complete order lifecycle from Signal to Alpaca trade.

    Uses Bracket Orders for atomic Entry, Take-Profit, and Stop-Loss.
    Supports position synchronization, stop-loss trailing, and emergency exits.

    Methods:
        execute_signal: Submit bracket order for a Signal
        get_order_details: Retrieve order by ID for enrichment
        sync_position_status: Sync position with Alpaca broker state
        modify_stop_loss: Replace stop-loss order (trailing)
        close_position_emergency: Cancel legs and exit at market
    """

    def __init__(
        self,
        trading_client: Optional[TradingClient] = None,
        repository: Optional[PositionRepository] = None,
        reconciler: Optional[Any] = None,
        market_provider: Optional[MarketDataProvider] = None,
    ):
        """
        Initialize the ExecutionEngine.

        Args:
            trading_client: Optional TradingClient for dependency injection.
            repository: Optional PositionRepository for risk checks.
        """
        settings = get_settings()
        self.alpaca = trading_client if trading_client else get_trading_client()

        # Initialize Repo for Risk Engine
        self.repo = repository if repository else PositionRepository()
        self.reconciler = reconciler
        self.risk_engine = RiskEngine(
            self.alpaca, self.repo, market_provider=market_provider
        )

        # Fetch Account ID for data joins (Issue #182)
        self.account_id = "unknown"
        try:
            self.account_id = str(self.alpaca.get_account().id)
        except APIError as e:
            logger.warning(
                "Failed to fetch Alpaca account ID. Defaulting to 'unknown'.",
                extra={"error": str(e)},
            )
        except Exception as e:
            logger.error(
                "An unexpected error occurred while fetching Alpaca account ID. Defaulting to 'unknown'.",
                extra={"error": str(e)},
            )

        # Environment Logging
        logger.info(
            f"Execution Engine Initialized [Env: {settings.ENVIRONMENT} | Mode: {'PAPER' if settings.is_paper_trading else 'LIVE'} | Account: {self.account_id}]"
        )

    def execute_signal(self, signal: Signal) -> Optional[Position]:
        """
        Execute a trading signal by submitting a Bracket Order to Alpaca.

        Args:
            signal: The Signal object containing entry, TP, and SL levels.

        Returns:
            Position: The created Position object if successful, None otherwise.
        """
        settings = get_settings()

        # === Execution Gating (SAFETY GUARD) ===
        # If explicitly enabled in PROD, execute LIVE.
        # If disabled OR not PROD, execute THEORETICAL (Simulated).
        should_execute_live = (
            settings.ENVIRONMENT == "PROD"
            and getattr(settings, "ENABLE_EXECUTION", False)
            and settings.is_paper_trading  # Always require paper=True for now (safety)
        )

        # Validate required signal fields
        if not self._validate_signal(signal):
            return None

        # === Risk Management (Issue #114) ===
        # Gate 1: Check Risk Constraints (Buying Power, Sector Limits, Drawdown)
        risk_result = self.risk_engine.validate_signal(signal)

        if not risk_result.passed:
            logger.warning(f"RISK BLOCK: {signal.symbol} - {risk_result.reason}")

            # Record Risk Metric
            try:
                # Calculate theoretical position size to estimate protected capital
                qty = self._calculate_qty(signal)
                capital_protected = qty * signal.entry_price
                get_metrics_collector().record_risk_block(
                    gate=risk_result.gate or "unknown",
                    symbol=signal.symbol,
                    amount=capital_protected,
                )
            except Exception:
                logger.opt(exception=True).warning("Failed to record risk metrics")

            # Create "Risk Blocked" Position for Shadow Tracking
            return self._execute_risk_blocked_order(signal, risk_result.reason)

        # Route based on execution mode
        if should_execute_live:
            if signal.asset_class == AssetClass.CRYPTO:
                return self._execute_crypto_signal(signal)
            else:
                return self._execute_bracket_order(signal)
        else:
            # Theoretical execution (Simulated with slippage)
            return self._execute_theoretical_order(signal)

    def _execute_crypto_signal(self, signal: Signal) -> Optional[Position]:
        """
        Execute a crypto signal using a simple market order.

        Alpaca does not support bracket/OTOCO orders for crypto (error 42210000).
        Instead, we submit a simple market order and track SL/TP manually
        via check_exits() in main.py.

        Args:
            signal: The Signal object with entry, TP, and SL levels.

        Returns:
            Position: The created Position object if successful, None otherwise.
        """
        settings = get_settings()

        try:
            qty = self._calculate_qty(signal)
            if qty <= 0:
                logger.error(f"Invalid quantity calculated for {signal.symbol}: {qty}")
                return None

            # === COST BASIS CHECK (Issue #192) ===
            if not self._is_notional_value_sufficient(qty, signal):
                return None

            # Determine order side
            effective_side = signal.side or DomainOrderSide.BUY
            alpaca_side = (
                OrderSide.BUY if effective_side == DomainOrderSide.BUY else OrderSide.SELL
            )

            # Simple market order for crypto (NO order_class, NO take_profit/stop_loss)
            order_request = MarketOrderRequest(
                symbol=signal.symbol,
                qty=qty,
                side=alpaca_side,
                time_in_force=TimeInForce.GTC,  # GTC required for crypto
                client_order_id=signal.signal_id,
            )

            logger.info(
                f"Submitting crypto market order for {signal.symbol}",
                extra={
                    "symbol": signal.symbol,
                    "qty": qty,
                    "side": alpaca_side.value,
                    "client_order_id": signal.signal_id,
                    "note": "Simple order - SL/TP tracked manually",
                },
            )

            order = cast(Order, self.alpaca.submit_order(order_request))

            logger.info(
                f"CRYPTO ORDER SUBMITTED: {signal.symbol}",
                extra={
                    "order_id": str(order.id),
                    "client_order_id": order.client_order_id,
                    "qty": qty,
                    "status": str(order.status),
                },
            )

            # Create Position with SL/TP for manual tracking
            delete_at = datetime.now(timezone.utc) + timedelta(
                days=settings.TTL_DAYS_POSITION
            )

            position = Position(
                position_id=signal.signal_id,
                ds=signal.ds,
                account_id=self.account_id,
                symbol=signal.symbol,
                asset_class=signal.asset_class,
                signal_id=signal.signal_id,
                alpaca_order_id=str(cast(Order, order).id),
                entry_order_id=str(cast(Order, order).id),  # For CFEE attribution
                discord_thread_id=signal.discord_thread_id,
                status=TradeStatus.OPEN,
                entry_fill_price=signal.entry_price,
                current_stop_loss=signal.suggested_stop,
                qty=qty,
                side=effective_side,
                target_entry_price=signal.entry_price,
                tp_order_id=None,  # No TP order - tracked manually
                sl_order_id=None,  # No SL order - tracked manually
                delete_at=delete_at,
            )

            return position

        except Exception as e:
            self._log_execution_failure(signal, e)
            return None

    def _execute_bracket_order(self, signal: Signal) -> Optional[Position]:
        """
        Execute an equity signal using a bracket order.

        Uses OTOCO (One-Triggers-One-Cancels-Other) for atomic TP/SL management.
        Bracket orders are only supported for equities, not crypto.

        Args:
            signal: The Signal object with entry, TP, and SL levels.

        Returns:
            Position: The created Position object if successful, None otherwise.
        """
        settings = get_settings()

        try:
            # Calculate position size
            qty = self._calculate_qty(signal)
            if qty <= 0:
                logger.error(f"Invalid quantity calculated for {signal.symbol}: {qty}")
                return None

            # === COST BASIS CHECK (Issue #192) ===
            if not self._is_notional_value_sufficient(qty, signal):
                return None

            # Determine order side (with None fallback)
            effective_side = signal.side or DomainOrderSide.BUY
            alpaca_side = (
                OrderSide.BUY if effective_side == DomainOrderSide.BUY else OrderSide.SELL
            )

            # Build the Bracket Order request
            order_request = MarketOrderRequest(
                symbol=signal.symbol,  # Alpaca accepts BTC/USD format
                qty=qty,
                side=alpaca_side,
                time_in_force=TimeInForce.GTC,
                order_class=OrderClass.BRACKET,
                take_profit=TakeProfitRequest(limit_price=round(signal.take_profit_1, 2)),
                stop_loss=StopLossRequest(stop_price=round(signal.suggested_stop, 2)),
                client_order_id=signal.signal_id,  # Traceability link
            )

            # Submit the order
            logger.info(
                f"Submitting bracket order for {signal.symbol}",
                extra={
                    "symbol": signal.symbol,
                    "qty": qty,
                    "side": alpaca_side.value,
                    "take_profit": signal.take_profit_1,
                    "stop_loss": signal.suggested_stop,
                    "client_order_id": signal.signal_id,
                },
            )

            order = cast(Order, self.alpaca.submit_order(order_request))

            # Log success
            logger.info(
                f"ORDER SUBMITTED: {signal.symbol}",
                extra={
                    "order_id": str(order.id),
                    "client_order_id": order.client_order_id,
                    "qty": qty,
                    "status": str(order.status),
                },
            )

            # PROD: settings.TTL_DAYS_POSITION (default 90 days)
            delete_at = datetime.now(timezone.utc) + timedelta(
                days=settings.TTL_DAYS_POSITION
            )

            position = Position(
                position_id=signal.signal_id,
                ds=signal.ds,
                account_id=self.account_id,
                symbol=signal.symbol,
                asset_class=signal.asset_class,
                signal_id=signal.signal_id,
                alpaca_order_id=str(cast(Order, order).id),
                entry_order_id=str(cast(Order, order).id),  # For CFEE attribution
                discord_thread_id=signal.discord_thread_id,
                status=TradeStatus.OPEN,
                entry_fill_price=signal.entry_price,
                current_stop_loss=signal.suggested_stop,
                qty=qty,
                side=effective_side,
                target_entry_price=signal.entry_price,
                tp_order_id=None,
                sl_order_id=None,
                delete_at=delete_at,
            )

            return position

        except Exception as e:
            self._log_execution_failure(signal, e)
            return None

    def _execute_theoretical_order(self, signal: Signal) -> Position:
        """
        Create a simulated Position with synthetic slippage.
        """
        settings = get_settings()
        slippage_pct = getattr(settings, "THEORETICAL_SLIPPAGE_PCT", 0.001)

        # Determine order side
        side = signal.side or DomainOrderSide.BUY

        # Calculate synthetic fill price
        # Long: Price spikes UP (slippage against you) -> entry * (1 + slippage)
        # Short: Price drops DOWN (slippage against you) -> entry * (1 - slippage)
        if side == DomainOrderSide.BUY:
            fill_price = signal.entry_price * (1 + slippage_pct)
        else:
            fill_price = signal.entry_price * (1 - slippage_pct)

        fill_price = (
            round(fill_price, 4)
            if signal.asset_class == AssetClass.EQUITY
            else fill_price
        )

        # Calculate quantity (same logic as live)
        qty = self._calculate_qty(signal)

        # Calculate slippage percentage for reporting
        entry_slippage_pct = round(
            (fill_price - signal.entry_price) / signal.entry_price * 100, 4
        )

        logger.info(
            f"SIMULATING {side.value.upper()} for {signal.symbol}",
            extra={
                "signal_id": signal.signal_id,
                "target_entry": signal.entry_price,
                "simulated_fill": fill_price,
                "slippage_pct": entry_slippage_pct,
                "qty": qty,
            },
        )

        # Create Position
        delete_at = datetime.now(timezone.utc) + timedelta(
            days=settings.TTL_DAYS_POSITION
        )

        return Position(
            position_id=signal.signal_id,
            ds=signal.ds,
            account_id="theoretical",
            symbol=signal.symbol,
            asset_class=signal.asset_class,
            signal_id=signal.signal_id,
            alpaca_order_id=f"theo-{signal.signal_id[:8]}",  # Dummy ID
            discord_thread_id=signal.discord_thread_id,
            status=TradeStatus.OPEN,
            entry_fill_price=fill_price,
            current_stop_loss=signal.suggested_stop,
            qty=qty,
            side=side,
            target_entry_price=signal.entry_price,
            # Theoretical trades are self-managed, no broker leg IDs
            tp_order_id=None,
            sl_order_id=None,
            delete_at=delete_at,
            trade_type=TradeType.THEORETICAL.value,
            entry_slippage_pct=entry_slippage_pct,
            filled_at=datetime.now(timezone.utc),
        )

    def _execute_risk_blocked_order(
        self, signal: Signal, reason: str = "Unknown Risk"
    ) -> Position:
        """
        Create a 'Shadow' Position for trades blocked by the Risk Engine.
        Used for theoretical tracking of opportunities missed due to risk limits.
        """
        settings = get_settings()
        qty = self._calculate_qty(signal)

        delete_at = datetime.now(timezone.utc) + timedelta(
            days=settings.TTL_DAYS_POSITION
        )

        return Position(
            position_id=signal.signal_id,
            ds=signal.ds,
            account_id=self.account_id,
            symbol=signal.symbol,
            asset_class=signal.asset_class,
            signal_id=signal.signal_id,
            alpaca_order_id=None,
            discord_thread_id=signal.discord_thread_id,
            status=TradeStatus.CLOSED,  # Immediately closed as it never opened
            entry_fill_price=signal.entry_price,  # Theoretical fill
            current_stop_loss=signal.suggested_stop,
            qty=qty,
            side=signal.side or DomainOrderSide.BUY,
            target_entry_price=signal.entry_price,
            tp_order_id=None,
            sl_order_id=None,
            delete_at=delete_at,
            trade_type=TradeType.RISK_BLOCKED.value,  # Special type
            failed_reason=f"Risk Rejection: {reason}",
            # Optional: Set valid metrics to 0 or None since it didn't run
            filled_at=datetime.now(timezone.utc),
            exit_time=datetime.now(timezone.utc),  # Exit immediately
            exit_reason=ExitReason.CLOSED_EXTERNALLY,  # Closest match or new enum?
        )

    def _validate_signal(self, signal: Signal) -> bool:
        """Validate that signal has required fields for execution."""
        errors = []

        if not signal.take_profit_1:
            errors.append("take_profit_1 is required for bracket order")

        if not signal.suggested_stop or signal.suggested_stop <= 0:
            errors.append("suggested_stop must be positive")

        if not signal.entry_price or signal.entry_price <= 0:
            errors.append("entry_price must be positive")

        if errors:
            logger.error(
                f"Signal validation failed for {signal.symbol}: {', '.join(errors)}"
            )
            return False

        return True

    def _is_notional_value_sufficient(self, qty: float, signal: Signal) -> bool:
        """Check if order notional value meets minimum broker requirements.

        Args:
            qty: Calculated position quantity.
            signal: The Signal object with entry price.

        Returns:
            True if notional value >= MIN_ORDER_NOTIONAL_USD, False otherwise.
        """
        settings = get_settings()
        notional_value = qty * signal.entry_price

        if notional_value < settings.MIN_ORDER_NOTIONAL_USD:
            logger.warning(
                f"Order for {signal.symbol} rejected: "
                f"Notional value ${notional_value:.2f} is below minimum of ${settings.MIN_ORDER_NOTIONAL_USD:.2f}"
            )
            return False
        return True

    def _calculate_qty(self, signal: Signal) -> float:
        """
        Calculate position size based on fixed dollar risk.

        Uses the formula: qty = RISK_PER_TRADE / risk_per_share
        where risk_per_share = |entry_price - stop_loss|

        This ensures that if the stop loss is hit, you lose exactly
        RISK_PER_TRADE dollars (before slippage/fees).

        For crypto, allows fractional quantities (6 decimals).
        For equities, uses 4 decimal precision.
        """
        settings = get_settings()
        risk_per_trade = getattr(settings, "RISK_PER_TRADE", 100.0)

        # Calculate risk per share (distance from entry to stop)
        risk_per_share = abs(signal.entry_price - signal.suggested_stop)

        if risk_per_share <= 0:
            logger.error(
                f"Invalid risk distance for {signal.symbol}: "
                f"entry={signal.entry_price}, stop={signal.suggested_stop}"
            )
            return 0.0

        # Position size = total risk / risk per share
        qty = risk_per_trade / risk_per_share

        # =====================================================================
        # MICRO-CAP SAFEGUARD (Issue #136)
        # When stop-loss is very close to entry (micro-cap scenario with tiny
        # stops), risk_per_share becomes extremely small, causing qty to explode.
        # Example: risk=100, risk_per_share=0.00000001 → qty=10,000,000,000
        #
        # Cap qty at reasonable limit to prevent Alpaca rejections.
        # =====================================================================
        max_qty = (
            settings.MAX_CRYPTO_POSITION_QTY
            if signal.asset_class == AssetClass.CRYPTO
            else settings.MAX_EQUITY_POSITION_QTY
        )

        if qty > max_qty:
            logger.warning(
                f"Position size {qty:.2f} exceeds MAX ({max_qty}) for {signal.symbol}. "
                f"Possible micro-cap edge case (tight stop-loss). Capping at max.",
                extra={
                    "symbol": signal.symbol,
                    "qty": qty,
                    "max_qty": max_qty,
                    "asset_class": signal.asset_class.value,
                    "risk_per_share": risk_per_share,
                    "entry_price": signal.entry_price,
                    "suggested_stop": signal.suggested_stop,
                },
            )
            qty = max_qty

        # Round based on asset class
        if signal.asset_class == AssetClass.CRYPTO:
            # Crypto allows fractional shares (up to 8 decimals for most)
            return round(qty, 6)
        else:
            # Equities: Alpaca supports fractional, round to 4 decimals
            return round(qty, 4)

    def _log_execution_failure(self, signal: Signal, error: Exception) -> None:
        """Display Rich error panel for execution failures."""
        error_content = (
            f"[bold red]Symbol:[/] {signal.symbol}\n"
            f"[bold red]Signal ID:[/] {signal.signal_id}\n"
            f"[bold red]Error:[/] {str(error)}"
        )

        panel = Panel(
            error_content,
            title="[bold white on red] ORDER EXECUTION FAILED [/]",
            border_style="red",
            padding=(1, 2),
        )
        console.print(panel)

        logger.error(
            f"Order execution failed for {signal.symbol}.",
            extra={
                "symbol": signal.symbol,
                "signal_id": signal.signal_id,
                "error": str(error),
            },
        )

    # =========================================================================
    # CFEE RECONCILIATION METHODS (Issue #140 - T+1 Fee Settlement)
    # =========================================================================

    def get_crypto_fees_by_orders(
        self,
        order_ids: List[str],
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """
        Fetch actual CFEE activities from Alpaca for specific order IDs.

        Alpaca posts CFEE records end-of-day (T+1), so this should be called
        24+ hours after trade execution.

        Args:
            order_ids: List of Alpaca order IDs (entry + all exits)
            symbol: Trading symbol (e.g., 'BTC/USD')
            start_date: Start date for CFEE query (trade entry date)
            end_date: End date for CFEE query (trade exit date + 2 days for settlement)

        Returns:
            Dict with:
                - total_fee_usd: Total fees in USD
                - fee_details: List of individual CFEE records
                - fee_tier: Volume tier used
        """
        MAX_RETRIES = 3
        RETRY_DELAY_BASE = 1.0  # seconds

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                # Query CFEE activities via raw REST API (TradingClient v2)
                params = {
                    "activity_types": "CFEE",
                    "date": start_date.isoformat(),
                    "until": end_date.isoformat(),
                    "direction": "asc",
                }

                activities_data = self.alpaca.get("/account/activities", params)

                # Wrap dicts for object compatibility
                activities = (
                    [_ActivityWrapper(a) for a in activities_data]
                    if activities_data
                    else []
                )

                # Filter by symbol and aggregate
                total_fee_usd = 0.0
                fee_details = []
                fee_tier = None

                for activity in activities:
                    # Match by symbol (Alpaca uses 'BTCUSD' format, we use 'BTC/USD')
                    activity_symbol = normalize_alpaca_symbol(str(activity.symbol))
                    query_symbol = normalize_alpaca_symbol(symbol)

                    if activity_symbol != query_symbol:
                        continue

                    # Parse fee amount
                    # CFEE qty is in crypto, price is USD/crypto
                    # Fee USD = abs(qty) * price
                    qty = float(activity.qty) if hasattr(activity, "qty") else 0.0
                    price = float(activity.price) if hasattr(activity, "price") else 0.0

                    # Validate before conversion (skip invalid records)
                    if qty == 0.0 or price == 0.0:
                        logger.warning(
                            f"Invalid CFEE record: qty={qty}, price={price}",
                            extra={
                                "activity_id": activity.id,
                                "symbol": symbol,
                                "qty": qty,
                                "price": price,
                            },
                        )
                        continue  # Skip invalid records

                    fee_usd = abs(qty) * price
                    total_fee_usd += fee_usd

                    fee_details.append(
                        {
                            "activity_id": activity.id,
                            "date": str(activity.date),
                            "qty": qty,
                            "price": price,
                            "fee_usd": fee_usd,
                            "description": activity.description
                            if hasattr(activity, "description")
                            else None,
                        }
                    )

                    # Extract tier from description (e.g., "Tier 0: 0.25%")
                    if hasattr(activity, "description") and not fee_tier:
                        desc = str(activity.description)
                        if "Tier" in desc:
                            fee_tier = desc

                logger.info(
                    f"Fetched CFEE for {symbol}: ${total_fee_usd:.4f} ({len(fee_details)} records)",
                    extra={
                        "symbol": symbol,
                        "total_fee_usd": total_fee_usd,
                        "num_records": len(fee_details),
                        "fee_tier": fee_tier,
                    },
                )

                return {
                    "total_fee_usd": total_fee_usd,
                    "fee_details": fee_details,
                    "fee_tier": fee_tier,
                }

            except Exception as e:
                if attempt < MAX_RETRIES:
                    # Exponential backoff: 1s, 2s, 4s
                    delay = RETRY_DELAY_BASE * (2 ** (attempt - 1))
                    logger.warning(
                        f"CFEE API call failed (attempt {attempt}/{MAX_RETRIES}), retrying.",
                        extra={
                            "symbol": symbol,
                            "attempt": attempt,
                            "max_retries": MAX_RETRIES,
                            "retry_delay": delay,
                            "error": str(e),
                        },
                    )
                    sleep(delay)
                else:
                    # Final attempt failed
                    logger.warning(
                        f"Failed to fetch CFEE for {symbol} after multiple attempts.",
                        extra={
                            "symbol": symbol,
                            "max_retries": MAX_RETRIES,
                            "error": str(e),
                        },
                    )
                    return {
                        "total_fee_usd": 0.0,
                        "fee_details": [],
                        "fee_tier": None,
                    }

    def get_current_fee_tier(self) -> Dict[str, Any]:
        """
        Fetch the account's current volume tier from Alpaca.

        Returns:
            Dict with:
                - tier_name: e.g., "Tier 0"
                - maker_fee_pct: e.g., 0.15
                - taker_fee_pct: e.g., 0.25
        """
        try:
            # Alpaca doesn't expose tier directly in Account API
            # Default to Tier 0 (most conservative)
            # TODO: Parse from account.crypto_tier if available in future API versions

            return {
                "tier_name": "Tier 0",
                "maker_fee_pct": 0.15,
                "taker_fee_pct": 0.25,
            }
        except Exception as e:
            logger.warning(
                "Failed to fetch fee tier.",
                extra={"error": str(e)},
            )
            return {
                "tier_name": "Tier 0 (default)",
                "maker_fee_pct": 0.15,
                "taker_fee_pct": 0.25,
            }

    # =========================================================================
    # ORDER MANAGEMENT METHODS (Managed Trade Model)
    # =========================================================================

    def get_order_details(self, order_id: str) -> Optional[Order]:
        """
        Retrieve order details from Alpaca by order ID.

        Uses GET /v2/orders/{order_id} endpoint.

        Args:
            order_id: The Alpaca order ID (UUID string).

        Returns:
            Order object if found, None if not found or on error.
        """
        try:
            order = cast(Order, self.alpaca.get_order_by_id(order_id))
            logger.debug(
                f"Retrieved order {order_id}: status={order.status}",
                extra={"order_id": order_id, "status": str(order.status)},
            )
            return order
        except Exception as e:
            # Check for 404/not found
            error_str = str(e).lower()
            if "not found" in error_str or "404" in error_str:
                logger.warning(f"Order {order_id} not found in Alpaca")
                return None
            logger.error(
                f"Failed to retrieve order {order_id}.",
                extra={"order_id": order_id, "error": str(e)},
            )
            return None

    def _retry_fill_price_capture(
        self,
        order_id: str,
        position_id: str,
        max_retries: int = 3,
        retry_delay: float = 1.5,
    ) -> Optional[tuple[float, Optional[datetime]]]:
        """
        Retry fill price capture with configurable budget.

        Handles volatile markets where orders sit in "Accepted" or "Partially Filled" state.
        Retries with exponential backoff until fill price is available or budget exhausted.

        Args:
            order_id: Alpaca order ID to check
            position_id: Position ID for logging context
            max_retries: Number of retry attempts (default: 3)
            retry_delay: Delay between retries in seconds (default: 1.5s)

        Returns:
            Tuple of (fill_price, filled_at) if successful, None otherwise
        """
        import time

        for attempt in range(1, max_retries + 1):
            time.sleep(retry_delay)
            try:
                refreshed_order = self.get_order_details(order_id)
                if refreshed_order and refreshed_order.filled_avg_price:
                    fill_price = float(refreshed_order.filled_avg_price)
                    filled_at = refreshed_order.filled_at
                    logger.info(
                        f"[RETRY {attempt}] Captured fill price for {position_id}: ${fill_price}",
                        extra={
                            "position_id": position_id,
                            "order_id": order_id,
                            "attempt": attempt,
                            "fill_price": fill_price,
                        },
                    )
                    return (fill_price, filled_at)
                else:
                    logger.debug(
                        f"[RETRY {attempt}/{max_retries}] Order {order_id} not filled yet "
                        f"(status: {refreshed_order.status if refreshed_order else 'UNKNOWN'})"
                    )
            except Exception as poll_err:
                logger.warning(
                    f"[RETRY {attempt}] Poll failed for {position_id}.",
                    extra={
                        "attempt": attempt,
                        "position_id": position_id,
                        "error": str(poll_err),
                    },
                )

        return None

    def sync_position_status(self, position: Position) -> Position:
        """
        Synchronize position with Alpaca broker state.

        Fetches the parent order and extracts:
        - TP/SL leg order IDs (from order.legs)
        - filled_at timestamp
        - Actual fill price (entry_fill_price)
        - Detects if position was closed externally (TP or SL filled)

        Args:
            position: The Position object to synchronize.

        Returns:
            Updated Position object with latest broker state.
        """
        # ENVIRONMENT GATE: Skip sync in non-PROD environments
        # Theoretical trades are self-managed, so synchronization is a no-op (they are always "synced")
        if position.trade_type == TradeType.THEORETICAL.value:
            return position

        if get_settings().ENVIRONMENT != "PROD":
            return position

        if not position.alpaca_order_id:
            logger.warning(
                f"Cannot sync position {position.position_id}: no alpaca_order_id"
            )
            return position

        # =====================================================================
        # STAFF REVIEW GAP #2: Backfill missing exit_fill_price
        # If position is CLOSED but exit_fill_price is missing, fetch from exit_order_id
        # =====================================================================
        if (
            position.status == TradeStatus.CLOSED
            and position.exit_order_id
            and not position.exit_fill_price
        ):
            try:
                exit_order = self.get_order_details(position.exit_order_id)
                if exit_order and exit_order.filled_avg_price:
                    position.exit_fill_price = float(exit_order.filled_avg_price)
                    if exit_order.filled_at:
                        position.exit_time = exit_order.filled_at
                    logger.info(
                        f"[BACKFILL] Captured missing exit price for {position.position_id}: "
                        f"${position.exit_fill_price}",
                        extra={
                            "position_id": position.position_id,
                            "exit_order_id": position.exit_order_id,
                            "exit_fill_price": position.exit_fill_price,
                        },
                    )
                    # Recalculate PnL with the new exit price
                    pnl_usd, pnl_pct = self._calculate_realized_pnl(position)
                    position.realized_pnl_usd = pnl_usd
                    position.realized_pnl_pct = pnl_pct
                    # Clear awaiting_backfill flag (Issue #141)
                    position.awaiting_backfill = False
            except Exception as e:
                logger.warning(
                    f"Exit price backfill failed for {position.position_id}.",
                    extra={"position_id": position.position_id, "error": str(e)},
                )

        try:
            # Fetch parent order
            order = self.get_order_details(position.alpaca_order_id)
            if not order:
                position.failed_reason = "Parent order not found in Alpaca"
                return position

            # Check order status
            order_status = str(order.status).lower()

            if order_status == "filled":
                # Update fill details
                if order.filled_at:
                    position.filled_at = order.filled_at
                if order.filled_avg_price:
                    position.entry_fill_price = float(order.filled_avg_price)

                # Calculate entry slippage
                if position.target_entry_price and position.target_entry_price > 0:
                    position.entry_slippage_pct = round(
                        (position.entry_fill_price - position.target_entry_price)
                        / position.target_entry_price
                        * 100,
                        4,
                    )

                # Extract commission if available (Alpaca reports fees in 'commission' field)
                # Handle None values (common in paper trading)
                if hasattr(order, "commission"):
                    position.commission = float(order.commission or 0.0)

                # Extract leg IDs from bracket order
                if hasattr(order, "legs") and order.legs:
                    for leg in order.legs:
                        leg_type = str(getattr(leg, "order_type", "")).lower()
                        leg_id = str(leg.id) if leg.id else None

                        if "limit" in leg_type:
                            # Take Profit is a limit order
                            position.tp_order_id = leg_id
                        elif "stop" in leg_type:
                            # Stop Loss is a stop order
                            position.sl_order_id = leg_id

                    logger.info(
                        f"Synced position {position.position_id}: "
                        f"TP={position.tp_order_id}, SL={position.sl_order_id}"
                    )

            elif order_status in ("canceled", "rejected", "expired"):
                position.failed_reason = (
                    f"Order {order_status}: {getattr(order, 'failed_message', 'Unknown')}"
                )
                position.status = TradeStatus.CLOSED

            elif order_status in _QUEUED_ORDER_STATUSES:
                logger.info(
                    f"Position {position.position_id} order still queued "
                    f"(status: {order_status}). Will sync on next cycle after fill.",
                    extra={
                        "symbol": position.symbol,
                        "order_status": order_status,
                        "position_id": position.position_id,
                    },
                )

            # Check if TP or SL was filled (position closed externally)
            # Only check if leg IDs were successfully extracted to avoid unnecessary API calls
            if position.tp_order_id:
                tp_order = self.get_order_details(position.tp_order_id)
                if tp_order and str(tp_order.status).lower() == "filled":
                    position.status = TradeStatus.CLOSED
                    # Capture exit details for PnL calculation
                    if tp_order.filled_avg_price:
                        position.exit_fill_price = float(tp_order.filled_avg_price)
                    if tp_order.filled_at:
                        position.exit_time = tp_order.filled_at
                    position.exit_reason = ExitReason.TP_HIT
                    # ISSUE FIX: Capture exit_order_id for invalidation path backfill
                    position.exit_order_id = str(tp_order.id)
                    logger.info(f"Position {position.position_id} closed via TP")

            if position.sl_order_id and position.status != TradeStatus.CLOSED:
                sl_order = self.get_order_details(position.sl_order_id)
                if sl_order and str(sl_order.status).lower() == "filled":
                    position.status = TradeStatus.CLOSED
                    # Capture exit details for PnL calculation
                    if sl_order.filled_avg_price:
                        position.exit_fill_price = float(sl_order.filled_avg_price)
                    if sl_order.filled_at:
                        position.exit_time = sl_order.filled_at
                    position.exit_reason = ExitReason.STOP_LOSS
                    # ISSUE FIX: Capture exit_order_id for invalidation path backfill
                    position.exit_order_id = str(sl_order.id)
                    logger.info(f"Position {position.position_id} closed via SL")

            # -------------------------------------------------------------------------
            # CALCULATE EXIT METRICS (when position is closed)
            # -------------------------------------------------------------------------
            if position.status == TradeStatus.CLOSED:
                # Calculate trade duration
                if position.filled_at and position.exit_time:
                    duration = position.exit_time - position.filled_at
                    position.trade_duration_seconds = int(duration.total_seconds())

                # Calculate exit slippage (vs target stop or TP level)
                # High-fidelity: compare against expected exit price
                if position.exit_fill_price:
                    target_exit = None
                    if position.exit_reason == ExitReason.STOP_LOSS:
                        # For SL, target is the current stop loss price
                        target_exit = position.current_stop_loss
                    elif position.exit_reason == ExitReason.TP_HIT:
                        # For TP, slippage is typically zero (limit order)
                        # but we still track it for completeness
                        target_exit = position.exit_fill_price
                    else:
                        # Other exits (manual, emergency) - no expected target
                        target_exit = position.exit_fill_price

                    if target_exit and target_exit > 0:
                        position.exit_slippage_pct = round(
                            (position.exit_fill_price - target_exit) / target_exit * 100,
                            4,
                        )

                # Update realized PnL
                pnl_usd, pnl_pct = self._calculate_realized_pnl(position)
                position.realized_pnl_usd = pnl_usd
                position.realized_pnl_pct = pnl_pct

            # -------------------------------------------------------------------------
            # MANUAL / EXTERNAL EXIT DETECTION
            # -------------------------------------------------------------------------
            # If position is still marked OPEN but TP/SL were not triggered,
            # verify if the position corresponds to actual broker state.
            if position.status == TradeStatus.OPEN:
                try:
                    # Check actual open position on Alpaca
                    # get_open_position raises 404 if no position exists
                    alpaca_pos = self.alpaca.get_open_position(
                        normalize_alpaca_symbol(position.symbol)
                    )

                    # Authoritative Reconciliation: Sync current qty and avg entry price
                    # from broker live state to ensure Firestore matches reality.
                    if alpaca_pos:
                        position.qty = float(alpaca_pos.qty)
                        position.entry_fill_price = float(alpaca_pos.avg_entry_price)

                except Exception as e:
                    # 404 means no position -> BEFORE marking CLOSED, verify if a closing order exists
                    if "not found" in str(e).lower() or "404" in str(e):
                        # Race Condition Protection: Skip manual exit verification for young positions
                        # This prevents false closures if sync runs immediately after opening.
                        min_age_minutes = _MANUAL_EXIT_VERIFICATION_MIN_AGE_MINUTES
                        if position.created_at:
                            age = datetime.now(timezone.utc) - position.created_at
                            if age < timedelta(minutes=min_age_minutes):
                                logger.warning(
                                    f"Skipping manual exit verification for young position {position.symbol}",
                                    extra={
                                        "symbol": position.symbol,
                                        "age_seconds": age.total_seconds(),
                                        "min_age_minutes": min_age_minutes,
                                    },
                                )
                                return position

                        if self.reconciler:
                            self.reconciler.handle_manual_exit_verification(position)
                        else:
                            logger.warning(
                                f"Position {position.position_id} missing on Alpaca. "
                                "Verification skipped (no reconciler provided)."
                            )

        except Exception as e:
            logger.error(
                f"Failed to sync position {position.position_id}.",
                extra={"position_id": position.position_id, "error": str(e)},
            )
            position.failed_reason = f"Sync error: {str(e)}"

        return position

    def modify_stop_loss(self, position: Position, new_stop: float) -> bool:
        """
        Update the stop-loss order for an open position.

        For EQUITY positions with bracket orders:
            Uses PATCH /v2/orders/{sl_order_id} to replace the stop_price.

        For CRYPTO positions (no broker SL order):
            Updates position.current_stop_loss for Firestore persistence.
            The manual exit checking in check_exits() will use this value.

        Note: Cannot replace orders in pending states (pending_new,
        pending_cancel, pending_replace).

        Args:
            position: The Position with an active trade.
            new_stop: The new stop-loss price.

        Returns:
            True if modification succeeded, False otherwise.
        """
        # ENVIRONMENT GATE: Skip modification in non-PROD environments,
        # UNLESS it's a theoretical trade (simulated state update).
        is_theoretical = position.trade_type == TradeType.THEORETICAL.value
        if get_settings().ENVIRONMENT != "PROD" and not is_theoretical:
            logger.info(
                f"[THEORETICAL MODE] Stop modification skipped for {position.position_id}"
            )
            return True  # Return True to simulate success in logic flow

        # CRYPTO PATH: No broker SL order - update local tracking
        # Crypto positions have sl_order_id = None (simple market order entry)
        if not position.sl_order_id:
            # Update in-memory for Firestore persistence
            old_stop = position.current_stop_loss
            position.current_stop_loss = new_stop
            logger.info(
                f"CRYPTO STOP UPDATE: {position.position_id}: "
                f"${old_stop} -> ${new_stop} (manual tracking)",
                extra={
                    "position_id": position.position_id,
                    "old_stop": old_stop,
                    "new_stop": new_stop,
                    "note": "Crypto - Firestore only, no broker order",
                },
            )
            return True

        try:
            # Check current SL order status first
            sl_order = self.get_order_details(position.sl_order_id)
            if not sl_order:
                logger.warning(f"SL order {position.sl_order_id} not found")
                return False

            sl_status = str(sl_order.status).lower()
            pending_states = {"pending_new", "pending_cancel", "pending_replace"}

            if sl_status in pending_states:
                logger.warning(f"Cannot replace SL order in {sl_status} state")
                return False

            if sl_status != "new" and sl_status != "accepted":
                logger.warning(f"SL order in non-replaceable state: {sl_status}")
                return False

            # Replace the stop-loss order
            from alpaca.trading.requests import ReplaceOrderRequest

            replace_request = ReplaceOrderRequest(stop_price=round(new_stop, 2))

            replaced_order = self.alpaca.replace_order_by_id(
                order_id=position.sl_order_id, order_data=replace_request
            )

            logger.info(
                f"Modified SL for {position.position_id}: "
                f"{position.current_stop_loss} -> {new_stop}",
                extra={
                    "position_id": position.position_id,
                    "old_stop": position.current_stop_loss,
                    "new_stop": new_stop,
                    "new_order_id": str(replaced_order.id),
                },
            )

            # Update position with new SL order ID (replacement creates new order)
            position.sl_order_id = str(replaced_order.id)
            position.current_stop_loss = new_stop

            return True

        except Exception as e:
            logger.error(
                f"Failed to modify stop for {position.position_id}.",
                extra={"position_id": position.position_id, "error": str(e)},
            )
            return False

    def scale_out_position(self, position: Position, scale_pct: float = 0.5) -> bool:
        """
        Partial close: Sell scale_pct of position at market.

        Used for TP1 automation - scale out 50% when first target is hit.

        1. Calculate scale-out quantity
        2. Submit market order to close portion
        3. Update position.qty with remaining
        4. Record scale-out details for PnL calculations

        Args:
            position: The Position with an active trade
            scale_pct: Percentage to close (default 0.5 = 50%)

        Returns:
            True if scale-out order submitted successfully
        """
        # ENVIRONMENT GATE: Skip scale-out in non-PROD environments
        # UNLESS it's a theoretical trade (simulated state update).
        is_theoretical = position.trade_type == TradeType.THEORETICAL.value
        if get_settings().ENVIRONMENT != "PROD" and not is_theoretical:
            logger.info(
                f"[THEORETICAL MODE] Scale-out skipped for {position.position_id}"
            )
            return True  # Return True to simulate success

        if not position.qty or position.qty <= 0:
            logger.warning(f"Cannot scale out {position.position_id}: no quantity")
            return False

        try:
            # Capture original qty BEFORE any calculations (only on first scale-out)
            if position.original_qty is None:
                position.original_qty = position.qty

            # Calculate scale-out quantity
            scale_qty = position.qty * scale_pct

            # For crypto, qty can be fractional. Round to 8 decimal places.
            scale_qty = round(scale_qty, 8)

            if scale_qty <= 0:
                logger.warning(f"Scale-out qty too small for {position.position_id}")
                return False

            # Determine close side (opposite of entry)
            close_side = (
                OrderSide.SELL if position.side == DomainOrderSide.BUY else OrderSide.BUY
            )

            # Submit market order for partial close
            close_request = MarketOrderRequest(
                symbol=position.symbol,
                qty=scale_qty,
                side=close_side,
                time_in_force=TimeInForce.GTC,
            )

            close_order = cast(Order, self.alpaca.submit_order(close_request))

            # === ISSUE #141: Capture fill price with retry budget ===
            # Track exit order ID for this scale-out
            exit_order_id = str(close_order.id)

            # Capture immediate fill price
            fill_price = None
            if close_order.filled_avg_price:
                fill_price = float(close_order.filled_avg_price)
                logger.info(
                    f"[IMMEDIATE] Captured scale-out fill price for {position.position_id}: "
                    f"${fill_price}"
                )
            else:
                # Use retry budget helper for delayed fills
                result = self._retry_fill_price_capture(
                    order_id=exit_order_id, position_id=position.position_id
                )
                if result:
                    fill_price, _ = result  # We don't need filled_at for scale-outs

            if not fill_price:
                # Mark for backfill but proceed to allow inventory update
                logger.warning(
                    f"[SCALE-OUT] Fill price not available for {position.position_id} "
                    f"after retry budget exhausted. Order ID: {exit_order_id}"
                )

            # === WEIGHTED AVERAGE CALCULATION (Issue #141 - Staff Review Gap #2) ===
            # For multi-stage exits (TP1 @ $100, TP2 @ $110), calculate weighted average
            # Formula: ((New_Qty * New_Price) + Previous_Exit_Value) / Total_Qty_Exited
            if fill_price is not None:
                # Calculate total exit value so far
                previous_exit_value = position.scaled_out_qty * (
                    position.scaled_out_price or 0.0
                )
                new_exit_value = scale_qty * fill_price
                total_exit_value = previous_exit_value + new_exit_value

                # Update scaled-out quantity
                position.scaled_out_qty += scale_qty

                # Calculate weighted average
                if position.scaled_out_qty > 0:
                    position.scaled_out_price = total_exit_value / position.scaled_out_qty
                    logger.info(
                        f"[WEIGHTED AVG] Updated exit price for {position.position_id}: "
                        f"${position.scaled_out_price:.2f} "
                        f"(previous: ${previous_exit_value / (position.scaled_out_qty - scale_qty) if position.scaled_out_qty > scale_qty else 0:.2f}, "
                        f"new: ${fill_price:.2f})"
                    )

                # Track individual scale-out for audit trail
                position.scaled_out_prices.append(
                    {
                        "qty": scale_qty,
                        "price": fill_price,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "order_id": exit_order_id,  # NEW: Track order ID for reconciliation
                    }
                )

                # NEW: Update position.exit_fill_price for final archival
                # This ensures TradeArchivalPipeline gets the correct aggregate value
                position.exit_fill_price = position.scaled_out_price
                position.awaiting_backfill = False
            else:
                # No fill price captured - mark for backfill
                position.awaiting_backfill = True
                logger.warning(
                    f"[SCALE-OUT] Marking {position.position_id} for backfill (no fill price)"
                )

            position.scaled_out_at = datetime.now(timezone.utc)

            # Update remaining quantity
            position.qty = round(position.qty - scale_qty, 8)

            logger.info(
                f"SCALE OUT: {position.position_id} - {scale_pct * 100:.0f}%",
                extra={
                    "position_id": position.position_id,
                    "symbol": position.symbol,
                    "scale_qty": scale_qty,
                    "remaining_qty": position.qty,
                    "fill_price": fill_price,
                    "order_id": str(close_order.id),
                },
            )

            return True

        except Exception as e:
            logger.error(
                f"Scale-out failed for {position.position_id}.",
                extra={"position_id": position.position_id, "error": str(e)},
            )
            position.failed_reason = f"Scale-out failed: {str(e)}"
            return False

    def move_stop_to_breakeven(self, position: Position) -> bool:
        """
        Move stop-loss to entry price (breakeven).

        Used after TP1 scale-out to protect remaining position.

        Args:
            position: The Position with an active stop-loss order

        Returns:
            True if stop moved successfully
        """
        if not position.entry_fill_price:
            logger.warning(
                f"Cannot move to breakeven {position.position_id}: no entry price"
            )
            return False

        # Add small buffer for slippage (0.1% in favorable direction)
        # For longs: breakeven slightly above entry
        # For shorts: breakeven slightly below entry
        buffer_pct = 0.001  # 0.1%
        if position.side == DomainOrderSide.BUY:
            breakeven_price = position.entry_fill_price * (1 + buffer_pct)
        else:
            breakeven_price = position.entry_fill_price * (1 - buffer_pct)

        breakeven_price = round(breakeven_price, 2)

        # Use existing modify_stop_loss method
        success = self.modify_stop_loss(position, breakeven_price)

        if success:
            position.breakeven_applied = True
            logger.info(
                f"BREAKEVEN: {position.position_id} stop -> ${breakeven_price}",
                extra={
                    "position_id": position.position_id,
                    "entry_price": position.entry_fill_price,
                    "breakeven_price": breakeven_price,
                },
            )

        return success

    def _calculate_realized_pnl(self, position: Position) -> tuple[float, float]:
        """
        Calculate aggregate realized PnL including all scale-outs.

        This method computes PnL from:
        1. All scaled-out portions (TP1, TP2 hits)
        2. Final exit of remaining position (if closed)

        Args:
            position: The Position to calculate PnL for.

        Returns:
            Tuple of (pnl_usd, pnl_pct) rounded for display.
        """
        entry = position.entry_fill_price
        exit_price = position.exit_fill_price
        is_long = position.side == DomainOrderSide.BUY

        if entry is None or entry == 0:
            return (0.0, 0.0)

        # PnL from scaled-out portions
        scaled_pnl = 0.0
        for scale in position.scaled_out_prices:
            scale_qty = scale.get("qty", 0)
            scale_price = scale.get("price", entry)
            if is_long:
                scaled_pnl += (scale_price - entry) * scale_qty
            else:
                scaled_pnl += (entry - scale_price) * scale_qty

        # PnL from final exit (if position is closed)
        final_pnl = 0.0
        if exit_price is not None:
            remaining_qty = position.qty
            if is_long:
                final_pnl = (exit_price - entry) * remaining_qty
            else:
                final_pnl = (entry - exit_price) * remaining_qty

        pnl_usd = scaled_pnl + final_pnl

        # Calculate percentage based on total position value
        total_qty = position.original_qty or (position.qty + position.scaled_out_qty)
        if total_qty > 0:
            pnl_pct = (pnl_usd / (entry * total_qty)) * 100
        else:
            pnl_pct = 0.0

        return (round(pnl_usd, 2), round(pnl_pct, 4))

    def close_position_emergency(
        self, position: Position, exit_reason: Optional[ExitReason] = None
    ) -> bool:
        """
        Emergency close: Cancel all open orders and exit at market.

        Sequence:
        1. Cancel TP order if exists (best effort - may already be filled)
        2. Cancel SL order if exists (best effort - may already be filled)
        3. Submit market order to close the position

        Use for: Structural Invalidation, Manual Kill, System Shutdown.

        Args:
            position: The Position to close.
            exit_reason: Optional reason for the exit (e.g., Structural Invalidation).

        Returns:
            True if market order was submitted successfully, False otherwise.
            Note: Cancellation failures are logged but don't affect return value
            since orders may already be filled/canceled.
        """
        # ENVIRONMENT GATE: Skip emergency close in non-PROD environments
        # UNLESS it's a theoretical trade (simulated state update).
        is_theoretical = position.trade_type == TradeType.THEORETICAL.value
        if get_settings().ENVIRONMENT != "PROD" and not is_theoretical:
            logger.info(
                f"[THEORETICAL MODE] Emergency close skipped for {position.position_id}"
            )
            return True

        if is_theoretical:
            position.status = TradeStatus.CLOSED
            position.exit_reason = exit_reason or ExitReason.MANUAL_EXIT
            # ISSUE FIX: Capture dummy exit_order_id for theoretical consistency
            position.exit_order_id = f"theo-exit-{position.position_id[:8]}"
            if not position.exit_fill_price:
                # Estimate exit at current stop if not provided (safe fallback) or handle via caller
                pass
            logger.info(f"THEORETICAL CLOSE: {position.position_id}")
            return True

        # 1. Cancel TP order (best effort - may already be filled/canceled)
        if position.tp_order_id:
            try:
                self.alpaca.cancel_order_by_id(position.tp_order_id)
                logger.info(f"Canceled TP order {position.tp_order_id}")
            except Exception as e:
                # Not an error - order may already be filled or canceled
                logger.debug(
                    f"Could not cancel TP order {position.tp_order_id} (may be filled).",
                    extra={"order_id": position.tp_order_id, "error": str(e)},
                )

        # 2. Cancel SL order (best effort - may already be filled/canceled)
        if position.sl_order_id:
            try:
                self.alpaca.cancel_order_by_id(position.sl_order_id)
                logger.info(f"Canceled SL order {position.sl_order_id}")
            except Exception as e:
                # Not an error - order may already be filled or canceled
                logger.debug(
                    f"Could not cancel SL order {position.sl_order_id} (may be filled).",
                    extra={"order_id": position.sl_order_id, "error": str(e)},
                )

        # 3. Submit market order to close position
        try:
            # Determine close side (opposite of entry)
            close_side = (
                OrderSide.SELL if position.side == DomainOrderSide.BUY else OrderSide.BUY
            )

            # Use position.symbol directly (added to Position model for this purpose)
            close_request = MarketOrderRequest(
                symbol=position.symbol,
                qty=position.qty,
                side=close_side,
                time_in_force=TimeInForce.GTC,
            )

            close_order = cast(Order, self.alpaca.submit_order(close_request))

            # === ISSUE 139 FIX: Capture exit order details ===
            # Store exit order ID for reconciliation and backfill
            position.exit_order_id = str(close_order.id)

            # Capture fill price (market orders typically fill immediately)
            if close_order.filled_avg_price:
                position.exit_fill_price = float(close_order.filled_avg_price)
                if close_order.filled_at:
                    position.exit_time = close_order.filled_at
                logger.info(
                    f"[IMMEDIATE] Captured exit fill price for {position.position_id}: "
                    f"${position.exit_fill_price}"
                )
                position.awaiting_backfill = False
            else:
                # Use retry budget helper for delayed fills
                result = self._retry_fill_price_capture(
                    order_id=position.exit_order_id, position_id=position.position_id
                )

                if result:
                    fill_price, filled_at = result
                    position.exit_fill_price = fill_price
                    position.awaiting_backfill = False
                    if filled_at:
                        position.exit_time = filled_at
                else:
                    # Explicitly handle None (exhausted retries): Mark for deferred backfill
                    position.awaiting_backfill = True
                    logger.warning(
                        f"[BACKFILL PENDING] Exit price for {position.position_id} "
                        f"will be backfilled by sync_position_status()"
                    )

            # Capture fill timestamp
            if close_order.filled_at:
                position.exit_time = close_order.filled_at
            elif not position.exit_time:
                # Fallback to current time if not immediately filled
                position.exit_time = datetime.now(timezone.utc)

            logger.info(
                f"EMERGENCY CLOSE: {position.position_id}",
                extra={
                    "position_id": position.position_id,
                    "symbol": position.symbol,
                    "close_order_id": str(cast(Order, close_order).id),
                    "qty": position.qty,
                    "side": close_side.value,
                    "exit_fill_price": position.exit_fill_price,
                },
            )

            position.status = TradeStatus.CLOSED
            if exit_reason:
                position.exit_reason = exit_reason
            return True

        except Exception as e:
            logger.error(
                f"Emergency close failed for {position.position_id}.",
                extra={"position_id": position.position_id, "error": str(e)},
            )
            position.failed_reason = f"Emergency close failed: {str(e)}"
            return False
