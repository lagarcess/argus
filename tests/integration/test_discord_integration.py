"""
Discord Integration Tests.

These tests validate REAL Discord API connectivity and permissions.
They require actual credentials in your environment (.env or env vars).

IMPORTANT: These tests are marked with @pytest.mark.integration and are
SKIPPED by default in CI/CD. Run them locally with:

    poetry run pytest tests/integration/test_discord_integration.py -v

Or run all integration tests:

    poetry run pytest -m integration -v
"""

from unittest.mock import patch

import pytest
from crypto_signals.config import get_settings
from crypto_signals.domain.schemas import AssetClass
from crypto_signals.notifications.discord import DiscordClient

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def discord_client():
    """Create a DiscordClient with real settings."""
    return DiscordClient()


@pytest.fixture
def settings():
    """Get real settings from environment."""
    return get_settings()


# =============================================================================
# INTEGRATION TESTS - Require Real Credentials
# =============================================================================


@pytest.mark.integration
class TestDiscordBotAuthentication:
    """Tests that validate Discord Bot Token is valid and authenticated."""

    def test_bot_token_is_configured(self, settings):
        """Verify DISCORD_BOT_TOKEN is present in settings."""
        assert settings.DISCORD_BOT_TOKEN is not None, (
            "DISCORD_BOT_TOKEN is not configured. "
            "Add it to your .env or environment variables."
        )
        # Token should be a non-empty string
        token_value = settings.DISCORD_BOT_TOKEN.get_secret_value()
        assert len(token_value) > 50, (
            "DISCORD_BOT_TOKEN looks too short. "
            "Discord bot tokens are typically 70+ characters."
        )

    def test_bot_token_authenticates_with_discord_api(self, settings):
        """Verify the bot token can authenticate with Discord's API."""
        import requests

        token = settings.DISCORD_BOT_TOKEN.get_secret_value()
        headers = {
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
        }

        # Use Discord's /users/@me endpoint to verify token validity
        response = requests.get(
            "https://discord.com/api/v10/users/@me",
            headers=headers,
            timeout=10.0,
        )

        assert response.status_code == 200, (
            f"Bot token authentication failed with status {response.status_code}. "
            f"Response: {response.text}"
        )

        # Verify we got bot info back
        bot_info = response.json()
        assert "id" in bot_info, "Response missing 'id' field"
        assert "username" in bot_info, "Response missing 'username' field"
        print(f"\n✅ Authenticated as bot: {bot_info['username']} (ID: {bot_info['id']})")


@pytest.mark.integration
class TestDiscordChannelConfiguration:
    """Tests that validate Discord Channel IDs are correctly configured."""

    def test_crypto_channel_id_is_configured(self, settings):
        """Verify DISCORD_CHANNEL_ID_CRYPTO is present."""
        assert (
            settings.DISCORD_CHANNEL_ID_CRYPTO is not None
        ), "DISCORD_CHANNEL_ID_CRYPTO is not configured."
        # Channel IDs are numeric strings (snowflakes)
        channel_id = settings.DISCORD_CHANNEL_ID_CRYPTO
        assert (
            channel_id.isdigit()
        ), f"DISCORD_CHANNEL_ID_CRYPTO should be a numeric string, got: {channel_id}"
        assert (
            len(channel_id) >= 17
        ), f"DISCORD_CHANNEL_ID_CRYPTO looks too short for a Discord snowflake: {channel_id}"

    def test_stock_channel_id_is_configured(self, settings):
        """Verify DISCORD_CHANNEL_ID_STOCK is present."""
        assert (
            settings.DISCORD_CHANNEL_ID_STOCK is not None
        ), "DISCORD_CHANNEL_ID_STOCK is not configured."
        channel_id = settings.DISCORD_CHANNEL_ID_STOCK
        assert (
            channel_id.isdigit()
        ), f"DISCORD_CHANNEL_ID_STOCK should be a numeric string, got: {channel_id}"
        assert (
            len(channel_id) >= 17
        ), f"DISCORD_CHANNEL_ID_STOCK looks too short for a Discord snowflake: {channel_id}"

    def test_crypto_channel_exists_and_accessible(self, settings):
        """Verify the crypto channel exists and bot can access it."""
        import requests

        token = settings.DISCORD_BOT_TOKEN.get_secret_value()
        channel_id = settings.DISCORD_CHANNEL_ID_CRYPTO

        headers = {
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
        }

        # Use Discord's /channels/{id} endpoint to verify channel exists
        response = requests.get(
            f"https://discord.com/api/v10/channels/{channel_id}",
            headers=headers,
            timeout=10.0,
        )

        assert response.status_code == 200, (
            f"Cannot access crypto channel {channel_id}. "
            f"Status: {response.status_code}, Response: {response.text}"
        )

        channel_info = response.json()
        print(
            f"\n✅ Crypto channel accessible: #{channel_info.get('name', 'unknown')} (ID: {channel_id})"
        )

    def test_stock_channel_exists_and_accessible(self, settings):
        """Verify the stock channel exists and bot can access it."""
        import requests

        token = settings.DISCORD_BOT_TOKEN.get_secret_value()
        channel_id = settings.DISCORD_CHANNEL_ID_STOCK

        headers = {
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
        }

        response = requests.get(
            f"https://discord.com/api/v10/channels/{channel_id}",
            headers=headers,
            timeout=10.0,
        )

        assert response.status_code == 200, (
            f"Cannot access stock channel {channel_id}. "
            f"Status: {response.status_code}, Response: {response.text}"
        )

        channel_info = response.json()
        print(
            f"\n✅ Stock channel accessible: #{channel_info.get('name', 'unknown')} (ID: {channel_id})"
        )


@pytest.mark.integration
class TestDiscordThreadPermissions:
    """Tests that validate bot has permission to read/manage threads."""

    def test_bot_can_list_active_threads_crypto(self, discord_client, settings):
        """Verify bot can list active threads in crypto channel."""
        import requests

        token = settings.DISCORD_BOT_TOKEN.get_secret_value()
        channel_id = settings.DISCORD_CHANNEL_ID_CRYPTO

        headers = {
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
        }

        # First, check the channel type
        channel_response = requests.get(
            f"https://discord.com/api/v10/channels/{channel_id}",
            headers=headers,
            timeout=10.0,
        )
        channel_info = channel_response.json()
        channel_type = channel_info.get("type", 0)

        # Channel type 15 = Forum Channel (uses different API)
        # Channel type 0 = Text Channel (uses /threads/active)
        if channel_type == 15:
            # For Forum channels, use /threads endpoint or guild threads
            guild_id = channel_info.get("guild_id")
            url = f"https://discord.com/api/v10/guilds/{guild_id}/threads/active"
        else:
            url = f"https://discord.com/api/v10/channels/{channel_id}/threads/active"

        response = requests.get(url, headers=headers, timeout=10.0)

        # 403 = Forbidden (missing permissions)
        # 404 = Channel not found or wrong type
        # 200 = Success
        assert response.status_code != 403, (
            "Bot lacks permission to read threads in crypto channel. "
            "Grant 'Read Message History' and 'View Channels' permissions."
        )
        assert response.status_code == 200, (
            f"Failed to list threads. Status: {response.status_code}, "
            f"Response: {response.text}"
        )

        threads_data = response.json()
        thread_count = len(threads_data.get("threads", []))
        channel_type_name = "Forum" if channel_type == 15 else "Text"
        print(
            f"\n✅ Bot can list threads ({channel_type_name} channel). Found {thread_count} active threads."
        )

    def test_bot_can_list_active_threads_stock(self, discord_client, settings):
        """Verify bot can list active threads in stock channel."""
        import requests

        token = settings.DISCORD_BOT_TOKEN.get_secret_value()
        channel_id = settings.DISCORD_CHANNEL_ID_STOCK

        headers = {
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
        }

        # First, check the channel type
        channel_response = requests.get(
            f"https://discord.com/api/v10/channels/{channel_id}",
            headers=headers,
            timeout=10.0,
        )
        channel_info = channel_response.json()
        channel_type = channel_info.get("type", 0)

        # Channel type 15 = Forum Channel (uses different API)
        if channel_type == 15:
            guild_id = channel_info.get("guild_id")
            url = f"https://discord.com/api/v10/guilds/{guild_id}/threads/active"
        else:
            url = f"https://discord.com/api/v10/channels/{channel_id}/threads/active"

        response = requests.get(url, headers=headers, timeout=10.0)

        assert response.status_code != 403, (
            "Bot lacks permission to read threads in stock channel. "
            "Grant 'Read Message History' and 'View Channels' permissions."
        )
        assert response.status_code == 200, (
            f"Failed to list threads. Status: {response.status_code}, "
            f"Response: {response.text}"
        )

        threads_data = response.json()
        thread_count = len(threads_data.get("threads", []))
        channel_type_name = "Forum" if channel_type == 15 else "Text"
        print(
            f"\n✅ Bot can list threads ({channel_type_name} channel). Found {thread_count} active threads."
        )


@pytest.mark.integration
class TestDiscordThreadRecoveryFunction:
    """Tests that validate the actual find_thread_by_signal_id function."""

    def test_find_thread_returns_none_for_nonexistent_signal(self, discord_client):
        """Verify find_thread_by_signal_id returns None for a signal that doesn't exist."""
        # Use a signal_id that definitely doesn't exist
        result = discord_client.find_thread_by_signal_id(
            signal_id="nonexistent-signal-id-12345",
            symbol="TEST/USD",
            asset_class=AssetClass.CRYPTO,
        )

        assert result is None, f"Expected None for nonexistent signal, got: {result}"
        print(
            "\n✅ find_thread_by_signal_id correctly returns None for nonexistent signals"
        )

    def test_find_thread_handles_missing_bot_token_gracefully(self):
        """Verify function handles missing token gracefully (no crash)."""
        # Create client with mocked settings that has no bot token
        with patch.object(get_settings(), "DISCORD_BOT_TOKEN", None):
            client = DiscordClient()
            # Override the settings on the instance
            client.settings = get_settings()
            client.settings.DISCORD_BOT_TOKEN = None

            result = client.find_thread_by_signal_id(
                signal_id="test-signal",
                symbol="BTC/USD",
                asset_class=AssetClass.CRYPTO,
            )

            assert result is None, "Should return None when bot token is missing"
            print("\n✅ find_thread_by_signal_id handles missing token gracefully")


@pytest.mark.integration
class TestDiscordWebhookConfiguration:
    """Tests that validate Discord Webhooks are correctly configured."""

    def test_test_webhook_is_configured(self, settings):
        """Verify TEST_DISCORD_WEBHOOK is present."""
        assert (
            settings.TEST_DISCORD_WEBHOOK is not None
        ), "TEST_DISCORD_WEBHOOK is not configured."
        webhook_url = settings.TEST_DISCORD_WEBHOOK.get_secret_value()
        assert webhook_url.startswith(
            "https://discord.com/api/webhooks/"
        ), f"TEST_DISCORD_WEBHOOK doesn't look like a valid Discord webhook URL: {webhook_url[:50]}..."
        print("\n✅ TEST_DISCORD_WEBHOOK is configured correctly")

    def test_live_crypto_webhook_is_configured(self, settings):
        """Verify LIVE_CRYPTO_DISCORD_WEBHOOK_URL is present."""
        webhook = settings.LIVE_CRYPTO_DISCORD_WEBHOOK_URL
        if webhook is None:
            pytest.skip(
                "LIVE_CRYPTO_DISCORD_WEBHOOK_URL not configured (optional in test mode)"
            )

        webhook_url = webhook.get_secret_value()
        assert webhook_url.startswith(
            "https://discord.com/api/webhooks/"
        ), f"LIVE_CRYPTO_DISCORD_WEBHOOK_URL doesn't look valid: {webhook_url[:50]}..."
        print("\n✅ LIVE_CRYPTO_DISCORD_WEBHOOK_URL is configured correctly")

    def test_live_stock_webhook_is_configured(self, settings):
        """Verify LIVE_STOCK_DISCORD_WEBHOOK_URL is present."""
        webhook = settings.LIVE_STOCK_DISCORD_WEBHOOK_URL
        if webhook is None:
            pytest.skip(
                "LIVE_STOCK_DISCORD_WEBHOOK_URL not configured (optional in test mode)"
            )

        webhook_url = webhook.get_secret_value()
        assert webhook_url.startswith(
            "https://discord.com/api/webhooks/"
        ), f"LIVE_STOCK_DISCORD_WEBHOOK_URL doesn't look valid: {webhook_url[:50]}..."
        print("\n✅ LIVE_STOCK_DISCORD_WEBHOOK_URL is configured correctly")

    def test_shadow_webhook_is_configured(self, settings):
        """Verify DISCORD_SHADOW_WEBHOOK_URL is present."""
        webhook = settings.DISCORD_SHADOW_WEBHOOK_URL
        if webhook is None:
            pytest.skip(
                "DISCORD_SHADOW_WEBHOOK_URL not configured (required for shadow signals)"
            )

        webhook_url = webhook.get_secret_value()
        assert webhook_url.startswith(
            "https://discord.com/api/webhooks/"
        ), f"DISCORD_SHADOW_WEBHOOK_URL doesn't look valid: {webhook_url[:50]}..."
        print("\n✅ DISCORD_SHADOW_WEBHOOK_URL is configured correctly")

    def test_webhook_endpoints_are_reachable(self, settings):
        """Verify all configured webhook URLs are reachable (HTTP 200/204)."""
        import requests

        webhooks_to_test = [
            ("TEST_DISCORD_WEBHOOK", settings.TEST_DISCORD_WEBHOOK),
            ("LIVE_CRYPTO_DISCORD_WEBHOOK_URL", settings.LIVE_CRYPTO_DISCORD_WEBHOOK_URL),
            ("LIVE_STOCK_DISCORD_WEBHOOK_URL", settings.LIVE_STOCK_DISCORD_WEBHOOK_URL),
            ("DISCORD_SHADOW_WEBHOOK_URL", settings.DISCORD_SHADOW_WEBHOOK_URL),
        ]

        for name, webhook in webhooks_to_test:
            if webhook is None:
                print(f"\n⏭️  {name}: Skipped (not configured)")
                continue

            webhook_url = webhook.get_secret_value()

            # Use GET request to test webhook validity without sending a message
            # Discord webhooks return 200 for GET with webhook info
            response = requests.get(webhook_url, timeout=10.0)

            assert response.status_code == 200, (
                f"{name} webhook endpoint unreachable. "
                f"Status: {response.status_code}, Response: {response.text[:200]}"
            )

            webhook_info = response.json()
            webhook_id = webhook_info.get("id", "unknown")
            webhook_name = webhook_info.get("name", "unnamed")
            print(f"\n✅ {name}: Reachable (ID: {webhook_id}, Name: {webhook_name})")
