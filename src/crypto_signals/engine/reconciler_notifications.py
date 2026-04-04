from crypto_signals.notifications.discord import DiscordClient
from loguru import logger


class ReconcilerNotificationService:
    """Handles formatted notifications for StateReconciler events."""

    def __init__(self, discord_client: DiscordClient):
        self.discord = discord_client

    def notify_manual_exit(self, symbol: str, order_id: str) -> None:
        """Alerts that a manual exit was detected and verified."""
        try:
            self.discord.send_message(
                f"☝️  **MANUAL EXIT DETECTED**: {symbol}\n"
                f"Position was found closed on Alpaca but open in DB.\n"
                f"Verified via manually placed order: `{order_id}`."
            )
        except Exception as e:
            logger.warning(f"Failed to notify manual exit for {symbol}: {e}")

    def notify_critical_sync_failure(self, symbol: str) -> None:
        """Alerts when a zombie position cannot be verified via order history."""
        try:
            self.discord.send_message(
                f"🛑 **CRITICAL SYNC FAILURE**: {symbol}\n"
                f"Position is missing from Alpaca but **NO EXIT ORDER FOUND**.\n"
                f"System will NOT close it automatically.\n"
                f"**Action Required**: Investigate immediately."
            )
        except Exception as e:
            logger.warning(f"Failed to send sync failure alert for {symbol}: {e}")

    def notify_orphan(self, symbol: str) -> None:
        """Alerts when a position exists on Alpaca but not in Firestore."""
        try:
            self.discord.send_message(
                f"⚠️  **CRITICAL ORPHAN**: {symbol}\n"
                f"Position is open in Alpaca but has no Firestore record.\n"
                f"**Action Required**: Manual investigation and position management."
            )
        except Exception as e:
            logger.warning(f"Failed to send orphan alert for {symbol}: {e}")

    def notify_reverse_orphan(self, symbol: str, position_id: str) -> None:
        """Alerts when a position is closed in Firestore but still open on Alpaca."""
        try:
            self.discord.send_message(
                f"🚨 **CRITICAL REVERSE ORPHAN**: {symbol}\n"
                f"Position is CLOSED in Firestore but STILL OPEN in Alpaca!\n"
                f"**Position ID**: {position_id}\n"
                f"**Action Required**: Manual close in Alpaca dashboard."
            )
        except Exception as e:
            logger.warning(f"Failed to send reverse orphan alert for {symbol}: {e}")
