"""Unit tests for equities feature flag configuration."""

from unittest.mock import patch

import pytest


class TestEquitiesFeatureFlag:
    """Tests for the ENABLE_EQUITIES configuration setting."""

    @pytest.fixture(autouse=True)
    def clear_settings_cache(self):
        """Clear the lru_cache before each test."""
        from crypto_signals.config import get_settings

        get_settings.cache_clear()
        yield
        get_settings.cache_clear()

    def test_equities_disabled_by_default(self):
        """
        Test that equities are disabled by default (ENABLE_EQUITIES=false).

        When ENABLE_EQUITIES is false (default), EQUITY_SYMBOLS should be
        forced to an empty list regardless of what's configured in .env.
        """
        with patch.dict(
            "os.environ",
            {
                "ALPACA_API_KEY": "test_key",
                "ALPACA_SECRET_KEY": "test_secret",
                "GOOGLE_CLOUD_PROJECT": "test-project",
                "TEST_DISCORD_WEBHOOK": "https://discord.com/api/webhooks/test",
                "EQUITY_SYMBOLS": "AAPL,TSLA,NVDA",  # Configured but should be ignored
                "ENABLE_EQUITIES": "false",
            },
            clear=True,
        ):
            from crypto_signals.config import get_settings

            settings = get_settings()

            # EQUITY_SYMBOLS should be empty even though configured
            assert settings.EQUITY_SYMBOLS == []
            assert settings.ENABLE_EQUITIES is False

    def test_equities_enabled_preserves_symbols(self):
        """
        Test that equities are preserved when ENABLE_EQUITIES=true.

        When ENABLE_EQUITIES is true, EQUITY_SYMBOLS should be preserved
        from the configuration.
        """
        with patch.dict(
            "os.environ",
            {
                "ALPACA_API_KEY": "test_key",
                "ALPACA_SECRET_KEY": "test_secret",
                "GOOGLE_CLOUD_PROJECT": "test-project",
                "TEST_DISCORD_WEBHOOK": "https://discord.com/api/webhooks/test",
                "EQUITY_SYMBOLS": "AAPL,TSLA,NVDA",
                "ENABLE_EQUITIES": "true",
            },
            clear=True,
        ):
            from crypto_signals.config import get_settings

            settings = get_settings()

            # EQUITY_SYMBOLS should be preserved
            assert settings.EQUITY_SYMBOLS == ["AAPL", "TSLA", "NVDA"]
            assert settings.ENABLE_EQUITIES is True

    def test_equities_disabled_empty_symbols_stays_empty(self):
        """
        Test that empty EQUITY_SYMBOLS stays empty when disabled.

        Edge case: if no equities configured and flag is false,
        should still result in empty list (no errors).
        """
        with patch.dict(
            "os.environ",
            {
                "ALPACA_API_KEY": "test_key",
                "ALPACA_SECRET_KEY": "test_secret",
                "GOOGLE_CLOUD_PROJECT": "test-project",
                "TEST_DISCORD_WEBHOOK": "https://discord.com/api/webhooks/test",
                # EQUITY_SYMBOLS not set (uses default empty list)
                "ENABLE_EQUITIES": "false",
            },
            clear=True,
        ):
            from crypto_signals.config import get_settings

            settings = get_settings()

            assert settings.EQUITY_SYMBOLS == []
