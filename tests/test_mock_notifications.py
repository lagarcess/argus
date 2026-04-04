import os
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
import requests
from crypto_signals.domain.schemas import AssetClass, ExitReason, SignalStatus
from crypto_signals.notifications.discord import DiscordClient
from pydantic import SecretStr

from tests.factories import PositionFactory, SignalFactory


def create_mock_settings(
    test_mode: bool = True,
    test_webhook: str = "https://discord.com/api/webhooks/test",
    crypto_webhook: str | None = None,
    stock_webhook: str | None = None,
    use_forums: bool = False,
):
    """Create a mock Settings object for testing."""
    mock_settings = MagicMock()
    mock_settings.TEST_MODE = test_mode
    mock_settings.TEST_DISCORD_WEBHOOK = SecretStr(test_webhook)
    mock_settings.LIVE_CRYPTO_DISCORD_WEBHOOK_URL = (
        SecretStr(crypto_webhook) if crypto_webhook else None
    )
    mock_settings.LIVE_STOCK_DISCORD_WEBHOOK_URL = (
        SecretStr(stock_webhook) if stock_webhook else None
    )
    mock_settings.DISCORD_USE_FORUMS = use_forums
    return mock_settings


class TestDiscordClient(unittest.TestCase):
    """Test suite for DiscordClient."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_webhook = "https://discord.com/api/webhooks/test"
        self.crypto_webhook = "https://discord.com/api/webhooks/crypto"
        self.stock_webhook = "https://discord.com/api/webhooks/stock"
        self.signal = SignalFactory.build(
            signal_id="test_id",
            ds=date(2025, 1, 1),
            strategy_id="test_strat",
            symbol="BTC/USD",
            asset_class=AssetClass.CRYPTO,
            confluence_factors=["trend_alignment", "volume_spike"],
            entry_price=48000.0,
            pattern_name="BULLISH_ENGULFING",
            status=SignalStatus.WAITING,
            suggested_stop=50000.0,
        )

    # =========================================================================
    # Routing Tests (TEST_MODE behavior)
    # =========================================================================

    def test_routing_test_mode_routes_to_test_webhook(self):
        """In TEST_MODE, all traffic routes to TEST_DISCORD_WEBHOOK regardless of asset_class."""
        settings = create_mock_settings(test_mode=True)
        client = DiscordClient(settings=settings)

        # All asset classes should route to test webhook
        self.assertEqual(client._get_webhook_url(AssetClass.CRYPTO), self.test_webhook)
        self.assertEqual(client._get_webhook_url(AssetClass.EQUITY), self.test_webhook)
        self.assertEqual(
            client._get_webhook_url(None),
            self.test_webhook,  # System messages
        )

    def test_routing_live_mode_crypto(self):
        """In LIVE mode, CRYPTO signals route to LIVE_CRYPTO_DISCORD_WEBHOOK_URL."""
        settings = create_mock_settings(
            test_mode=False,
            crypto_webhook=self.crypto_webhook,
            stock_webhook=self.stock_webhook,
            use_forums=False,
        )
        client = DiscordClient(settings=settings)

        self.assertEqual(client._get_webhook_url(AssetClass.CRYPTO), self.crypto_webhook)

    def test_routing_live_mode_equity(self):
        """In LIVE mode, EQUITY signals route to LIVE_STOCK_DISCORD_WEBHOOK_URL."""
        settings = create_mock_settings(
            test_mode=False,
            crypto_webhook=self.crypto_webhook,
            stock_webhook=self.stock_webhook,
        )
        client = DiscordClient(settings=settings)

        self.assertEqual(client._get_webhook_url(AssetClass.EQUITY), self.stock_webhook)

    def test_routing_live_mode_system_messages_to_test_webhook(self):
        """In LIVE mode, system messages (no asset_class) route to TEST_DISCORD_WEBHOOK."""
        settings = create_mock_settings(
            test_mode=False,
            crypto_webhook=self.crypto_webhook,
            stock_webhook=self.stock_webhook,
        )
        client = DiscordClient(settings=settings)

        # No asset class means system message - routes to test webhook
        self.assertEqual(client._get_webhook_url(None), self.test_webhook)

    def test_routing_live_mode_missing_webhook_returns_none(self):
        """In LIVE mode, missing webhook for asset class returns None."""
        settings = create_mock_settings(
            test_mode=False,
            crypto_webhook=None,  # No crypto webhook configured
            stock_webhook=self.stock_webhook,
        )
        client = DiscordClient(settings=settings)

        # CRYPTO without webhook should return None
        self.assertIsNone(client._get_webhook_url(AssetClass.CRYPTO))

    # =========================================================================
    # send_signal Tests
    # =========================================================================

    @patch("crypto_signals.notifications.discord.requests.post")
    def test_send_signal_success(self, mock_post):
        """Test sending a signal returns thread_id."""
        settings = create_mock_settings(test_mode=True)
        client = DiscordClient(settings=settings)

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"id": "1234567890123456789"}
        mock_post.return_value = mock_response

        thread_id = client.send_signal(self.signal)
        self.assertEqual(thread_id, "1234567890123456789")

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        # Verify ?wait=true is appended to URL
        self.assertEqual(args[0], f"{self.test_webhook}?wait=true")
        self.assertIn("🚀", kwargs["json"]["content"])
        self.assertIn("BTC/USD", kwargs["json"]["content"])

    @patch("crypto_signals.notifications.discord.requests.post")
    def test_send_signal_with_thread_name(self, mock_post):
        """Test sending a signal with a thread name."""
        settings = create_mock_settings(test_mode=True, use_forums=True)
        client = DiscordClient(settings=settings)

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"id": "9876543210987654321"}
        mock_post.return_value = mock_response

        thread_id = client.send_signal(self.signal, thread_name="Test Thread")
        self.assertEqual(thread_id, "9876543210987654321")

        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"]["thread_name"], "Test Thread")

    @patch("crypto_signals.notifications.discord.requests.post")
    def test_send_signal_failure(self, mock_post):
        """Test sending a signal when API fails returns None."""
        settings = create_mock_settings(test_mode=True)
        client = DiscordClient(settings=settings)

        # Simulate network error
        mock_post.side_effect = requests.RequestException("Network Error")

        thread_id = client.send_signal(self.signal)
        self.assertIsNone(thread_id)

    def test_send_signal_no_webhook_returns_none(self):
        """Test sending a signal with no configured webhook returns None."""
        settings = create_mock_settings(
            test_mode=False,
            crypto_webhook=None,  # No webhook for CRYPTO
        )
        client = DiscordClient(settings=settings)

        # Should return None and log critical error
        thread_id = client.send_signal(self.signal)
        self.assertIsNone(thread_id)

    # =========================================================================
    # send_message Tests
    # =========================================================================

    @patch("crypto_signals.notifications.discord.requests.post")
    def test_send_message_success(self, mock_post):
        """Test sending a message successfully."""
        settings = create_mock_settings(test_mode=True, use_forums=False)
        client = DiscordClient(settings=settings)

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        success = client.send_message("Test Message")
        self.assertTrue(success)

    @patch("crypto_signals.notifications.discord.requests.post")
    def test_send_message_with_thread_id(self, mock_post):
        """Test sending a reply to a thread uses ?thread_id query param."""
        settings = create_mock_settings(test_mode=True)
        client = DiscordClient(settings=settings)

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        success = client.send_message("Reply content", thread_id="1234567890")
        self.assertTrue(success)

        mock_post.assert_called_once()
        args, _ = mock_post.call_args
        # Verify ?thread_id is appended to URL
        self.assertEqual(args[0], f"{self.test_webhook}?thread_id=1234567890")

    @patch("crypto_signals.notifications.discord.requests.post")
    def test_send_message_with_asset_class_routing(self, mock_post):
        """Test send_message routes correctly based on asset_class."""
        settings = create_mock_settings(
            test_mode=False,
            crypto_webhook=self.crypto_webhook,
            stock_webhook=self.stock_webhook,
        )
        client = DiscordClient(settings=settings)

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # Send with CRYPTO asset class
        success = client.send_message("Test", asset_class=AssetClass.CRYPTO)
        self.assertTrue(success)

        args, _ = mock_post.call_args
        # Should route to crypto webhook
        self.assertEqual(args[0], self.crypto_webhook)

    @patch("crypto_signals.notifications.discord.requests.post")
    def test_send_message_failure(self, mock_post):
        """Test sending a message when API fails."""
        settings = create_mock_settings(test_mode=True)
        client = DiscordClient(settings=settings)

        # Simulate network error
        mock_post.side_effect = requests.RequestException("Network Error")

        success = client.send_message("Test Message")
        self.assertFalse(success)

    @patch("crypto_signals.notifications.discord.requests.post")
    def test_send_message_thread_reply_failure_does_not_crash(self, mock_post):
        """Test that thread reply failure logs error but doesn't crash."""
        settings = create_mock_settings(test_mode=True)
        client = DiscordClient(settings=settings)

        # Simulate network error on thread reply
        mock_post.side_effect = requests.RequestException("Thread not found")

        # Should return False but not raise exception
        success = client.send_message("Reply content", thread_id="invalid_thread")
        self.assertFalse(success)

    # =========================================================================
    # send_signal with all targets Tests
    # =========================================================================

    @patch("crypto_signals.notifications.discord.requests.post")
    def test_send_signal_with_targets(self, mock_post):
        """Test sending a signal with all targets and invalidation price."""
        settings = create_mock_settings(test_mode=True)
        client = DiscordClient(settings=settings)

        full_signal = SignalFactory.build(
            signal_id="test_id_full",
            ds=date(2025, 1, 1),
            strategy_id="test_strat",
            symbol="ETH/USD",
            asset_class=AssetClass.CRYPTO,
            confluence_factors=["rsi_divergence"],
            entry_price=3050.0,
            pattern_name="BULLISH_ENGULFING",
            status=SignalStatus.WAITING,
            suggested_stop=3000.0,
            invalidation_price=2950.0,
            take_profit_1=3100.0,
            take_profit_2=3200.0,
            take_profit_3=3500.0,
        )

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"id": "thread_123"}
        mock_post.return_value = mock_response

        thread_id = client.send_signal(full_signal)
        self.assertEqual(thread_id, "thread_123")

        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        content = kwargs["json"]["content"]

        self.assertIn("ETH/USD", content)
        self.assertIn("Entry Price:** $3,050.00", content)
        self.assertIn("Stop Loss:** $3,000.00", content)
        self.assertIn("Invalidation Price:** $2,950.00", content)
        self.assertIn("Take Profit 1 (Conservative):** $3,100.00", content)
        self.assertIn("Take Profit 2 (Structural):** $3,200.00", content)
        self.assertIn("Take Profit 3 (Runner):** $3,500.00", content)

    @patch("crypto_signals.notifications.discord.requests.post")
    def test_send_signal_partial_targets(self, mock_post):
        """Test sending a signal with missing targets (conditional rendering)."""
        settings = create_mock_settings(test_mode=True)
        client = DiscordClient(settings=settings)

        # Signal with only TP1 defined, TP2 and TP3 are None
        partial_signal = SignalFactory.build(
            signal_id="test_id_partial",
            ds=date(2025, 1, 1),
            strategy_id="test_strat",
            symbol="XRP/USD",
            asset_class=AssetClass.CRYPTO,
            confluence_factors=["breakout"],
            entry_price=1.50,
            pattern_name="BULLISH_FLAG",
            status=SignalStatus.WAITING,
            suggested_stop=1.40,
            invalidation_price=1.40,  # Same as stop, should not show invalidation line
            take_profit_1=1.60,
            take_profit_2=None,
            take_profit_3=None,
        )

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"id": "partial_thread_123"}
        mock_post.return_value = mock_response

        thread_id = client.send_signal(partial_signal)
        self.assertEqual(thread_id, "partial_thread_123")

        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        content = kwargs["json"]["content"]

        self.assertIn("XRP/USD", content)
        self.assertIn("Take Profit 1 (Conservative):** $1.60", content)
        self.assertNotIn("Take Profit 2", content)
        self.assertNotIn("Take Profit 3", content)
        self.assertNotIn("Invalidation Price", content)

    # =========================================================================
    # send_trade_close Tests
    # =========================================================================

    @patch("crypto_signals.notifications.discord.requests.post")
    def test_send_trade_close_win_uses_money_emoji(self, mock_post):
        """Test that winning trade uses 💰 emoji."""
        from datetime import datetime, timezone

        from crypto_signals.domain.schemas import OrderSide, TradeStatus

        settings = create_mock_settings(test_mode=True, use_forums=True)
        client = DiscordClient(settings=settings)

        # Add discord_thread_id to the signal to simulate an existing thread
        self.signal.discord_thread_id = "thread_win_123"

        position = PositionFactory.build(
            position_id="test-pos-1",
            ds=date(2025, 1, 1),
            account_id="paper",
            symbol="BTC/USD",
            signal_id="test-signal-1",
            status=TradeStatus.CLOSED,
            entry_fill_price=50000.0,
            current_stop_loss=48000.0,
            qty=0.1,
            side=OrderSide.BUY,
            exit_fill_price=55000.0,
            exit_time=datetime.now(timezone.utc),
        )

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = client.send_trade_close(
            signal=self.signal,
            position=position,
            pnl_usd=500.0,
            pnl_pct=10.0,
            duration_str="4h 12m",
            exit_reason="Take Profit 1",
        )

        self.assertTrue(result)
        _, kwargs = mock_post.call_args
        content = kwargs["json"]["content"]

        self.assertIn("💰", content)
        self.assertIn("TRADE CLOSED: BTC/USD", content)
        self.assertIn("+$500.00", content)
        self.assertIn("+10.00%", content)
        self.assertIn("4h 12m", content)

    @patch("crypto_signals.notifications.discord.requests.post")
    def test_send_trade_close_loss_uses_skull_emoji(self, mock_post):
        """Test that losing trade uses 💀 emoji."""
        from datetime import datetime, timezone

        from crypto_signals.domain.schemas import OrderSide, TradeStatus

        settings = create_mock_settings(test_mode=True, use_forums=True)
        client = DiscordClient(settings=settings)

        # Add discord_thread_id to the signal to simulate an existing thread
        self.signal.discord_thread_id = "thread_loss_456"

        position = PositionFactory.build(
            position_id="test-pos-2",
            ds=date(2025, 1, 1),
            account_id="paper",
            symbol="BTC/USD",
            signal_id="test-signal-2",
            status=TradeStatus.CLOSED,
            entry_fill_price=50000.0,
            current_stop_loss=48000.0,
            qty=0.1,
            side=OrderSide.BUY,
            exit_fill_price=48000.0,
            exit_time=datetime.now(timezone.utc),
        )

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = client.send_trade_close(
            signal=self.signal,
            position=position,
            pnl_usd=-200.0,
            pnl_pct=-4.0,
            duration_str="2h 30m",
            exit_reason="Stop Loss",
        )

        self.assertTrue(result)
        _, kwargs = mock_post.call_args
        content = kwargs["json"]["content"]

        self.assertIn("💀", content)
        self.assertIn("TRADE CLOSED: BTC/USD", content)
        self.assertIn("-$200.00", content)
        self.assertIn("-4.00%", content)
        self.assertIn("Stop Loss", content)

    @patch("crypto_signals.notifications.discord.requests.post")
    def test_send_trade_close_with_thread_id(self, mock_post):
        """Test that trade close sends to existing thread."""

        from crypto_signals.domain.schemas import OrderSide, TradeStatus

        settings = create_mock_settings(test_mode=True)
        client = DiscordClient(settings=settings)

        # Signal with thread_id
        signal_with_thread = SignalFactory.build(
            signal_id="test_id",
            ds=date(2025, 1, 1),
            strategy_id="test_strat",
            symbol="ETH/USD",
            asset_class=AssetClass.CRYPTO,
            confluence_factors=["trend"],
            entry_price=3000.0,
            pattern_name="BULLISH_ENGULFING",
            status=SignalStatus.WAITING,
            suggested_stop=2900.0,
            discord_thread_id="thread_123456",
        )

        position = PositionFactory.build(
            position_id="test-pos-3",
            ds=date(2025, 1, 1),
            account_id="paper",
            symbol="ETH/USD",
            signal_id="test_id",
            status=TradeStatus.CLOSED,
            entry_fill_price=3000.0,
            current_stop_loss=2900.0,
            qty=1.0,
            side=OrderSide.BUY,
            exit_fill_price=3300.0,
        )

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = client.send_trade_close(
            signal=signal_with_thread,
            position=position,
            pnl_usd=300.0,
            pnl_pct=10.0,
            duration_str="1h 0m",
            exit_reason="Take Profit 1",
        )

        self.assertTrue(result)
        args, _ = mock_post.call_args
        # Should include thread_id in URL
        self.assertIn("thread_id=thread_123456", args[0])

    # =========================================================================
    # send_signal_update Tests
    # =========================================================================

    @patch("crypto_signals.notifications.discord.requests.post")
    def test_send_signal_update_tp1_hit_includes_action(self, mock_post):
        """Test TP1_HIT includes scaling out action hint."""
        settings = create_mock_settings(test_mode=True)
        client = DiscordClient(settings=settings)

        signal = SignalFactory.build(
            signal_id="test_id",
            ds=date(2025, 1, 1),
            strategy_id="test_strat",
            symbol="BTC/USD",
            asset_class=AssetClass.CRYPTO,
            confluence_factors=["trend"],
            entry_price=50000.0,
            pattern_name="BULLISH_ENGULFING",
            status=SignalStatus.TP1_HIT,
            suggested_stop=48000.0,
            exit_reason=ExitReason.TP1,
            discord_thread_id="thread_123",
        )

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = client.send_signal_update(signal)

        self.assertTrue(result)
        _, kwargs = mock_post.call_args
        content = kwargs["json"]["content"]

        self.assertIn("🎯", content)
        self.assertIn("SIGNAL UPDATE: BTC/USD", content)
        self.assertIn("Scaling Out (50%)", content)
        self.assertIn("Breakeven", content)
        self.assertIn("Bullish Engulfing", content)

    @patch("crypto_signals.notifications.discord.requests.post")
    def test_send_signal_update_invalidated(self, mock_post):
        """Test INVALIDATED signal sends correctly."""
        settings = create_mock_settings(test_mode=True)
        client = DiscordClient(settings=settings)

        signal = SignalFactory.build(
            signal_id="test_id",
            ds=date(2025, 1, 1),
            strategy_id="test_strat",
            symbol="ETH/USD",
            asset_class=AssetClass.CRYPTO,
            confluence_factors=["trend"],
            entry_price=3000.0,
            pattern_name="BEARISH_ENGULFING",
            status=SignalStatus.INVALIDATED,
            suggested_stop=3100.0,
            exit_reason=ExitReason.STRUCTURAL_INVALIDATION,
            discord_thread_id="thread_456",
        )

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = client.send_signal_update(signal)

        self.assertTrue(result)
        _, kwargs = mock_post.call_args
        content = kwargs["json"]["content"]

        self.assertIn("🛑", content)  # EMOJI_STOP
        self.assertIn("INVALIDATED", content)
        self.assertIn("STRUCTURAL_INVALIDATION", content)

    @patch("crypto_signals.notifications.discord.requests.post")
    def test_send_signal_update_expired(self, mock_post):
        """Test EXPIRED signal sends correctly."""
        settings = create_mock_settings(test_mode=True)
        client = DiscordClient(settings=settings)

        signal = SignalFactory.build(
            signal_id="test_id",
            ds=date(2025, 1, 1),
            strategy_id="test_strat",
            symbol="SOL/USD",
            asset_class=AssetClass.CRYPTO,
            confluence_factors=["trend"],
            entry_price=180.0,
            pattern_name="BULLISH_FLAG",
            status=SignalStatus.EXPIRED,
            suggested_stop=170.0,
            exit_reason=ExitReason.EXPIRED,
            discord_thread_id="thread_789",
        )

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = client.send_signal_update(signal)

        self.assertTrue(result)
        _, kwargs = mock_post.call_args
        content = kwargs["json"]["content"]

        self.assertIn("👻", content)  # EMOJI_GHOST
        self.assertIn("EXPIRED", content)
        self.assertIn("EXPIRED", content)

    @patch("crypto_signals.notifications.discord.requests.post")
    def test_send_signal_update_includes_test_label(self, mock_post):
        """Test that [TEST] label appears when TEST_MODE=true."""
        settings = create_mock_settings(test_mode=True)
        client = DiscordClient(settings=settings)

        signal = SignalFactory.build(
            signal_id="test_id",
            ds=date(2025, 1, 1),
            strategy_id="test_strat",
            symbol="BTC/USD",
            asset_class=AssetClass.CRYPTO,
            confluence_factors=["trend"],
            entry_price=50000.0,
            pattern_name="BULLISH_ENGULFING",
            status=SignalStatus.TP1_HIT,
            suggested_stop=48000.0,
            discord_thread_id="thread_123",
        )

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = client.send_signal_update(signal)

        self.assertTrue(result)
        _, kwargs = mock_post.call_args
        content = kwargs["json"]["content"]

        self.assertIn("[TEST]", content)

    @patch("crypto_signals.notifications.discord.requests.post")
    def test_send_signal_update_live_mode_no_label(self, mock_post):
        """Test that [TEST] label is NOT present when TEST_MODE=false."""
        settings = create_mock_settings(
            test_mode=False,
            crypto_webhook="https://discord.com/api/webhooks/crypto",
        )
        client = DiscordClient(settings=settings)

        signal = SignalFactory.build(
            signal_id="test_id",
            ds=date(2025, 1, 1),
            strategy_id="test_strat",
            symbol="BTC/USD",
            asset_class=AssetClass.CRYPTO,
            confluence_factors=["trend"],
            entry_price=50000.0,
            pattern_name="BULLISH_ENGULFING",
            status=SignalStatus.TP1_HIT,
            suggested_stop=48000.0,
            discord_thread_id="thread_123",
        )

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = client.send_signal_update(signal)

        self.assertTrue(result)
        _, kwargs = mock_post.call_args
        content = kwargs["json"]["content"]

        self.assertNotIn("[TEST]", content)


# =============================================================================
# Config Validation Tests
# =============================================================================


class TestConfigValidation(unittest.TestCase):
    """Test configuration validation for webhook routing."""

    def test_config_validation_live_mode_requires_webhooks(self):
        """ValidationError should be raised when TEST_MODE=false without live webhooks."""
        from crypto_signals.config import Settings, get_settings

        # Clear the lru_cache to ensure fresh settings instantiation
        get_settings.cache_clear()

        # Set up minimal env vars for testing config validation
        # Use clear=True to fully isolate environment from .env file influence
        test_env = {
            "ALPACA_API_KEY": "test_key",
            "ALPACA_SECRET_KEY": "test_secret",
            "GOOGLE_CLOUD_PROJECT": "test-project",
            "TEST_DISCORD_WEBHOOK": "https://discord.com/api/webhooks/test",
            "TEST_MODE": "false",
            # Missing LIVE_CRYPTO_DISCORD_WEBHOOK_URL and LIVE_STOCK_DISCORD_WEBHOOK_URL
        }

        try:
            with patch.dict(os.environ, test_env, clear=True):
                with pytest.raises(ValueError) as exc_info:
                    Settings(_env_file=None)

                # Validator checks LIVE_CRYPTO first, so that error is raised
                assert "LIVE_CRYPTO_DISCORD_WEBHOOK_URL" in str(exc_info.value)
        finally:
            # Re-clear cache so other tests get fresh settings
            get_settings.cache_clear()

    def test_config_validation_live_mode_requires_stock_webhook(self):
        """ValidationError for missing LIVE_STOCK when LIVE_CRYPTO is set."""
        from crypto_signals.config import Settings, get_settings

        get_settings.cache_clear()

        # LIVE_CRYPTO is set, but LIVE_STOCK is missing
        test_env = {
            "ALPACA_API_KEY": "test_key",
            "ALPACA_SECRET_KEY": "test_secret",
            "GOOGLE_CLOUD_PROJECT": "test-project",
            "TEST_DISCORD_WEBHOOK": "https://discord.com/api/webhooks/test",
            "TEST_MODE": "false",
            "LIVE_CRYPTO_DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/crypto",
            # Missing LIVE_STOCK_DISCORD_WEBHOOK_URL
        }

        try:
            with patch.dict(os.environ, test_env, clear=True):
                with pytest.raises(ValueError) as exc_info:
                    Settings(_env_file=None)

                assert "LIVE_STOCK_DISCORD_WEBHOOK_URL" in str(exc_info.value)
        finally:
            get_settings.cache_clear()

    def test_config_validation_live_mode_succeeds_with_all_webhooks(self):
        """Settings should load successfully when all required webhooks are configured."""
        from crypto_signals.config import Settings, get_settings

        get_settings.cache_clear()

        # All webhooks configured - should succeed
        test_env = {
            "ALPACA_API_KEY": "test_key",
            "ALPACA_SECRET_KEY": "test_secret",
            "GOOGLE_CLOUD_PROJECT": "test-project",
            "TEST_DISCORD_WEBHOOK": "https://discord.com/api/webhooks/test",
            "TEST_MODE": "false",
            "LIVE_CRYPTO_DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/crypto",
            "LIVE_STOCK_DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/stock",
        }

        try:
            with patch.dict(os.environ, test_env, clear=True):
                # Should not raise - all required webhooks are present
                settings = Settings(_env_file=None)
                assert settings.TEST_MODE is False
                assert settings.LIVE_CRYPTO_DISCORD_WEBHOOK_URL is not None
                assert settings.LIVE_STOCK_DISCORD_WEBHOOK_URL is not None
        finally:
            get_settings.cache_clear()
