"""State Reconciler Module (Issue #113).

Detects and resolves synchronization gaps between Alpaca broker state
and Firestore database state.

Example:
    >>> from crypto_signals.engine.reconciler import StateReconciler
    >>> from crypto_signals.market.data_provider import get_trading_client
    >>> from crypto_signals.repository.firestore import PositionRepository
    >>> from crypto_signals.notifications.discord import DiscordClient
    >>> from crypto_signals.engine.reconciler_notifications import ReconcilerNotificationService
    >>>
    >>> reconciler = StateReconciler(
    ...     get_trading_client(),
    ...     PositionRepository(),
    ...     ReconcilerNotificationService(DiscordClient())
    ... )
    >>> report = reconciler.reconcile()
    >>> if report.critical_issues:
    ...     print(f"Issues detected: {report.critical_issues}")
"""

import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from alpaca.trading.client import TradingClient
from alpaca.trading.models import Position as AlpacaPosition
from alpaca.trading.requests import GetOrdersRequest
from crypto_signals.config import Settings, get_settings
from crypto_signals.domain.enums import ReconciliationErrors
from crypto_signals.domain.schemas import (
    ExitReason,
    Position,
    ReconciliationReport,
    SignalStatus,
    TradeStatus,
    TradeType,
)
from crypto_signals.engine.reconciler_notifications import ReconcilerNotificationService
from crypto_signals.repository.firestore import PositionRepository, SignalRepository
from crypto_signals.utils.symbols import normalize_alpaca_symbol
from loguru import logger


class StateReconciler:
    """
    Detects and resolves synchronization gaps between Alpaca and Firestore.
    Handles Zombie Positions (Firestore OPEN, Alpaca CLOSED) and Orphans (Alpaca OPEN, Firestore MISSING).
    """

    def __init__(
        self,
        alpaca_client: TradingClient,
        position_repo: PositionRepository,
        notification_service: ReconcilerNotificationService,
        settings: Optional[Settings] = None,
        signal_repo: Optional[SignalRepository] = None,
    ):
        """
        Initialize the StateReconciler.

        Args:
            alpaca_client: TradingClient for fetching broker positions.
            position_repo: PositionRepository for database operations.
            notification_service: ReconcilerNotificationService for alerts.
            settings: Settings object (defaults to get_settings()).
            signal_repo: SignalRepository for database operations (optional).
        """
        self.alpaca = alpaca_client
        self.position_repo = position_repo
        self.notifications = notification_service
        self.settings: Settings = settings or get_settings()
        self.signal_repo = signal_repo or SignalRepository()

        logger.info(
            "StateReconciler initialized",
            extra={
                "environment": self.settings.ENVIRONMENT,
                "mode": "ENABLED" if self.settings.ENVIRONMENT == "PROD" else "DISABLED",
            },
        )

    def reconcile(self, min_age_minutes: int = 5) -> ReconciliationReport:
        """
        Execute full reconciliation between Alpaca and Firestore.

        Process:
        1. Fetch open positions from Alpaca and Firestore.
        2. Detect discrepancies (Zombies and Orphans).
        3. Heal zombies (verify exit then close in DB).
        4. Alert on orphans.

        Args:
            min_age_minutes: Min age to consider for zombie healing (race condition guard).

        Returns:
            ReconciliationReport: Summary of reconciliation results
        """
        start_time = time.time()

        # ENVIRONMENT GATE: Skip execution in non-PROD
        if self.settings.ENVIRONMENT != "PROD":
            logger.warning(
                f"Reconciliation skipped: ENVIRONMENT is {self.settings.ENVIRONMENT}, not PROD"
            )
            return ReconciliationReport(
                critical_issues=[
                    f"Reconciliation disabled in {self.settings.ENVIRONMENT}"
                ]
            )

        critical_issues: list[str] = []
        reconciled_count: int = 0
        zombies: list[str] = []
        orphans: list[str] = []

        try:
            # 1. Fetch State
            alpaca_pos, firestore_pos, fetch_errors = self._fetch_provider_state()
            critical_issues.extend(fetch_errors)

            # 2. Detect Discrepancies
            zombie_candidates, orphan_candidates = self._detect_discrepancies(
                alpaca_pos, firestore_pos
            )

            # 3. Heal Zombies
            zombies, healed_count, zombie_errors = self._heal_zombies(
                zombie_candidates, firestore_pos, min_age_minutes
            )
            reconciled_count += healed_count
            critical_issues.extend(zombie_errors)

            # 4. Handle Orphans
            orphans, orphan_errors = self._handle_orphans(orphan_candidates)
            critical_issues.extend(orphan_errors)

            # 5. Check Reverse Orphans
            reverse_orphan_errors = self._check_reverse_orphans()
            critical_issues.extend(reverse_orphan_errors)

            # 6. TIER 2: Signal Status Healing (Auto-Healing)
            # Close the circuit between positions and signals
            signal_healing_count, signal_healing_errors = self._heal_signal_statuses(
                firestore_pos
            )
            reconciled_count += signal_healing_count
            critical_issues.extend(signal_healing_errors)

        except Exception as e:
            error_msg = f"Reconciliation execution failed: {e}"
            logger.error(error_msg)
            critical_issues.append(error_msg)

        # 6. Build report
        duration_seconds = time.time() - start_time

        report = ReconciliationReport(
            zombies=zombies,
            orphans=orphans,
            reconciled_count=reconciled_count,
            duration_seconds=duration_seconds,
            critical_issues=critical_issues,
        )

        self._log_report_summary(report)
        return report

    def handle_manual_exit_verification(self, position: Position) -> Optional[Position]:
        """
        Verify if a position that is missing from Alpaca has a corresponding manual exit order.
        If verified, it returns the updated Position object. If not, returns None.

        This logic is centralized here to unify state reconciliation strategies.
        """
        logger.warning(
            f"Position {position.position_id} ({position.symbol}) not found on Alpaca. "
            "Verifying manual exit via order history..."
        )

        try:
            # 1. Determine the expected exit side
            # Using specific check for Alpaca OrderSide enum to avoid domain mismatch
            from alpaca.trading.enums import OrderSide as AlpacaOrderSide
            from crypto_signals.domain.schemas import OrderSide as DomainOrderSide

            close_side = (
                AlpacaOrderSide.SELL
                if position.side == DomainOrderSide.BUY
                else AlpacaOrderSide.BUY
            )

            # 2. Search recent filled orders for this symbol

            from alpaca.trading.enums import QueryOrderStatus

            request = GetOrdersRequest(
                status=QueryOrderStatus.CLOSED,
                symbols=[position.symbol],
                limit=500,
                side=close_side,
            )
            from alpaca.trading.models import Order

            recent_orders_result = self.alpaca.get_orders(filter=request)
            recent_orders = (
                recent_orders_result if isinstance(recent_orders_result, list) else []
            )

            # 3. Find the most recent fill that is NOT our known TP or SL legs
            closing_order = None
            ignored_ids = {
                position.tp_order_id,
                position.sl_order_id,
                position.alpaca_order_id,
                position.position_id,  # Used as client_order_id for entry
            }

            for o in recent_orders:
                if isinstance(o, Order):
                    # Check both Alpaca UUID and Client Order ID to prevent false MANUAL_EXIT
                    order_id = str(o.id)
                    client_id = getattr(o, "client_order_id", None)
                    if client_id:
                        client_id = str(client_id)

                    if order_id in ignored_ids or (
                        client_id and client_id in ignored_ids
                    ):
                        continue

                    closing_order = o
                    break

            # 4. If closing order found, heal the position state
            if closing_order:
                # The position object is updated in-place. The caller is responsible for persisting this change.
                position.status = TradeStatus.CLOSED
                position.exit_reason = ExitReason.MANUAL_EXIT
                if closing_order.filled_avg_price:
                    position.exit_fill_price = float(closing_order.filled_avg_price)
                if closing_order.filled_at:
                    position.exit_time = closing_order.filled_at
                position.exit_order_id = str(closing_order.id)

                logger.info(
                    f"✅ MANUAL EXIT VERIFIED: {position.symbol} via Order {closing_order.id}",
                    extra={
                        "symbol": position.symbol,
                        "order_id": closing_order.id,
                        "price": position.exit_fill_price,
                    },
                )

                # Notify Discord of the manual exit detected during sync
                self.notifications.notify_manual_exit(
                    position.symbol, str(closing_order.id)
                )

                return position

            # 5. If NO closing order found, it's a critical sync issue (don't close yet)
            logger.error(
                f"🛑 EXIT VERIFICATION FAILED: {position.symbol} missing from Alpaca "
                "but NO matching closing order found. Keeping open in DB to prevent gap."
            )
            return None

        except Exception as e:
            logger.error(
                f"Error during manual exit verification for {position.symbol}: {e}"
            )
            return None

    def _fetch_provider_state(
        self,
    ) -> tuple[list[AlpacaPosition], list[Position], list[str]]:
        """Fetch current state from Alpaca and Firestore."""
        alpaca_positions_list: list[AlpacaPosition] = []
        firestore_positions: list[Position] = []
        errors: list[str] = []

        # 1. Fetch Alpaca
        logger.info("Fetching positions from Alpaca...")
        try:
            raw_alpaca_positions = self.alpaca.get_all_positions()
            alpaca_positions_list = (
                raw_alpaca_positions if isinstance(raw_alpaca_positions, list) else []
            )

            # Log state
            alpaca_symbols = {
                normalize_alpaca_symbol(p.symbol) for p in alpaca_positions_list
            }
            logger.info(
                f"Alpaca state: {len(alpaca_symbols)} open positions",
                extra={"symbols": sorted(list(alpaca_symbols))},
            )
        except Exception as e:
            error_msg = f"Failed to fetch Alpaca positions: {e}"
            logger.error(error_msg)
            errors.append(error_msg)

        # 2. Fetch Firestore
        logger.info("Fetching positions from Firestore...")
        try:
            all_firestore_positions = self.position_repo.get_open_positions()

            # Filter out THEORETICAL trades (simulated state)
            firestore_positions = [
                p
                for p in all_firestore_positions
                if p.trade_type != TradeType.THEORETICAL.value
            ]

            # Log state
            firestore_symbols = {
                normalize_alpaca_symbol(p.symbol) for p in firestore_positions
            }
            logger.info(
                f"Firestore state: {len(firestore_positions)} open positions",
                extra={"symbols": sorted(list(firestore_symbols))},
            )
        except Exception as e:
            error_msg = f"Failed to fetch Firestore positions: {e}"
            logger.error(error_msg)
            errors.append(error_msg)

        return alpaca_positions_list, firestore_positions, errors

    def _detect_discrepancies(
        self,
        alpaca_positions: list[AlpacaPosition],
        firestore_positions: list[Position],
    ) -> tuple[list[str], list[str]]:
        """Identify zombie and orphan candidates based on position sets."""

        # Normalize keys
        alpaca_symbols = {normalize_alpaca_symbol(p.symbol) for p in alpaca_positions}
        firestore_symbols_norm = {
            normalize_alpaca_symbol(p.symbol) for p in firestore_positions
        }

        # Mapping for denormalization
        norm_to_original = {
            normalize_alpaca_symbol(p.symbol): p.symbol for p in firestore_positions
        }

        # Logic
        zombie_symbols_norm = firestore_symbols_norm - alpaca_symbols
        orphan_symbols_norm = alpaca_symbols - firestore_symbols_norm

        # Map back to originals
        zombies = [norm_to_original[s] for s in zombie_symbols_norm]
        orphans = list(orphan_symbols_norm)  # Keep normalized, will be formatted later

        logger.info(
            "Reconciliation analysis complete",
            extra={
                "zombies_detected": len(zombies),
                "orphans_detected": len(orphans),
            },
        )
        return zombies, orphans

    def _heal_zombies(
        self,
        zombies: list[str],
        firestore_positions: list[Position],
        min_age_minutes: int,
    ) -> tuple[list[str], int, list[str]]:
        """Attempt to heal zombie positions by checking for valid exits."""
        healed_count = 0
        final_zombies = []
        errors = []

        # Fast lookup
        symbol_to_position = {p.symbol: p for p in firestore_positions}

        for symbol in zombies:
            try:
                pos = symbol_to_position.get(symbol)
                if not pos:
                    continue

                # Race Condition Protection
                if pos.created_at:
                    age = datetime.now(timezone.utc) - pos.created_at
                    if age < timedelta(minutes=min_age_minutes):
                        logger.warning(
                            f"Skipping young zombie candidate {symbol}",
                            extra={
                                "symbol": symbol,
                                "age_seconds": age.total_seconds(),
                                "min_age_minutes": min_age_minutes,
                            },
                        )
                        # Ensure it's still reported as a zombie, just not acted upon yet
                        final_zombies.append(symbol)
                        continue

                # Heal
                updated_pos = self.handle_manual_exit_verification(pos)
                if updated_pos:
                    self.position_repo.update_position(updated_pos)
                    healed_count += 1
                    logger.warning(
                        f"Zombie healed: {symbol}",
                        extra={
                            "symbol": symbol,
                            "position_id": updated_pos.position_id,
                            "status": updated_pos.status,
                        },
                    )
                else:
                    # Verification failed
                    final_zombies.append(symbol)
                    error_msg = ReconciliationErrors.ZOMBIE_EXIT_GAP.format(symbol=symbol)
                    logger.critical(
                        error_msg,
                        extra={
                            "symbol": symbol,
                            "position_id": pos.position_id,
                        },
                    )
                    errors.append(error_msg)
                    self.notifications.notify_critical_sync_failure(symbol)

            except Exception as e:
                error_msg = f"Failed to heal zombie {symbol}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
                final_zombies.append(symbol)

        return final_zombies, healed_count, errors

    def _handle_orphans(
        self, orphan_candidates: list[str]
    ) -> tuple[list[str], list[str]]:
        """Format and alert on orphan positions."""
        crypto_config = self.settings.CRYPTO_SYMBOLS or []
        config_map = {normalize_alpaca_symbol(s): s for s in crypto_config}

        orphans = []
        errors = []

        for s_norm in orphan_candidates:
            # Denormalize
            symbol = config_map.get(s_norm, s_norm)
            orphans.append(symbol)

            # Alert
            logger.critical(
                f"ORPHAN POSITION DETECTED: {symbol}",
                extra={
                    "symbol": symbol,
                    "impact": "Position open in Alpaca but missing from DB",
                },
            )
            self.notifications.notify_orphan(symbol)
            errors.append(ReconciliationErrors.ORPHAN_POSITION.format(symbol=symbol))

        return orphans, errors

    def _heal_signal_statuses(
        self, firestore_positions: list[Position]
    ) -> tuple[int, list[str]]:
        """
        Heal WAITING signals to ACTIVE if an OPEN position exists.
        Protects against crashes during the 'Gap of Silence' between execution and persistence.
        """
        healed_count = 0
        errors = []

        logger.info(f"Checking {len(firestore_positions)} signals for status healing...")

        for pos in firestore_positions:
            if pos.status != TradeStatus.OPEN:
                continue

            try:
                sig = self.signal_repo.get_by_id(pos.signal_id)
                if sig and sig.status == SignalStatus.WAITING:
                    logger.warning(
                        f"TIER 2 HEAL: Signal {sig.signal_id} ({sig.symbol}) is WAITING "
                        "but an OPEN position exists. Healing to ACTIVE.",
                        extra={
                            "symbol": sig.symbol,
                            "signal_id": sig.signal_id,
                            "position_id": pos.position_id,
                        },
                    )
                    success = self.signal_repo.update_signal_atomic(
                        sig.signal_id, {"status": SignalStatus.ACTIVE.value}
                    )
                    if success:
                        healed_count += 1
                    else:
                        errors.append(
                            f"Failed atomic heal for signal {sig.signal_id} ({sig.symbol})"
                        )
            except Exception as e:
                error_msg = f"Error healing signal status for {pos.symbol}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)

        return healed_count, errors

    def _check_reverse_orphans(self) -> list[str]:
        """Check if recently closed positions in DB are still open in Alpaca."""
        logger.info("Checking for reverse orphans (CLOSED in DB, OPEN in Alpaca)...")
        errors = []

        try:
            closed_positions = self.position_repo.get_closed_positions(limit=50)
            reverse_orphans = []

            for closed_pos in closed_positions:
                try:
                    alpaca_pos = self.alpaca.get_open_position(
                        normalize_alpaca_symbol(closed_pos.symbol)
                    )
                    if alpaca_pos:
                        reverse_orphans.append(closed_pos.symbol)
                        logger.critical(
                            f"REVERSE ORPHAN DETECTED: {closed_pos.symbol}",
                            extra={
                                "symbol": closed_pos.symbol,
                                "position_id": closed_pos.position_id,
                                "impact": "Position closed in DB but STILL OPEN in Alpaca!",
                            },
                        )

                        self.notifications.notify_reverse_orphan(
                            closed_pos.symbol, closed_pos.position_id
                        )

                        errors.append(
                            ReconciliationErrors.REVERSE_ORPHAN.format(
                                symbol=closed_pos.symbol
                            )
                        )

                except Exception as e:
                    # 404/not found means correctly closed
                    if "not found" not in str(e).lower() and "404" not in str(e):
                        logger.warning(
                            f"Error checking closed position {closed_pos.symbol}: {e}"
                        )

            if reverse_orphans:
                logger.warning(
                    f"Found {len(reverse_orphans)} reverse orphans",
                    extra={"symbols": reverse_orphans},
                )

        except Exception as e:
            logger.warning("Reverse orphan detection failed.", extra={"error": str(e)})

        return errors

    def _log_report_summary(self, report: ReconciliationReport) -> None:
        """Log the final reconciliation summary."""
        logger.info(
            "Reconciliation complete",
            extra={
                "zombies": len(report.zombies),
                "orphans": len(report.orphans),
                "reconciled": report.reconciled_count,
                "duration_seconds": round(report.duration_seconds, 3),
                "critical_issues": len(report.critical_issues),
            },
        )
