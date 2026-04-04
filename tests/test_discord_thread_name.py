"""Test that send_signal includes thread_name in payload for Forum channels."""

from datetime import date
from unittest.mock import MagicMock, patch

from crypto_signals.domain.schemas import AssetClass


def test_send_signal_includes_thread_name_for_forum_channels():
    """
    Regression test for Discord Forum channel thread_name bug.

    Verifies that send_signal() includes thread_name in the Discord API
    payload to prevent 220001 error (Forum channels require thread_name).
    """

    from crypto_signals.domain.schemas import (
        SignalStatus,
        get_deterministic_id,
    )
    from crypto_signals.notifications.discord import DiscordClient

    from tests.factories import SignalFactory

    # Create a mock settings object
    with patch("crypto_signals.notifications.discord.get_settings") as mock_settings:
        settings_instance = MagicMock()
        settings_instance.TEST_MODE = False
        settings_instance.DISCORD_USE_FORUMS = True
        settings_instance.LIVE_CRYPTO_DISCORD_WEBHOOK_URL = MagicMock()
        settings_instance.LIVE_CRYPTO_DISCORD_WEBHOOK_URL.get_secret_value.return_value = "https://discord.com/api/webhooks/test/webhook"
        mock_settings.return_value = settings_instance

        # Create Discord client
        client = DiscordClient(settings=settings_instance)

        test_ds = date(2025, 1, 15)
        test_strategy = "test-strategy"
        test_symbol = "BTC/USD"
        test_id = get_deterministic_id(f"{test_ds}|{test_strategy}|{test_symbol}")

        # Create a test signal
        signal = SignalFactory.build(
            signal_id=test_id,
            ds=test_ds,
            strategy_id=test_strategy,
            symbol=test_symbol,
            asset_class=AssetClass.CRYPTO,
            pattern_name="inverse_head_shoulders",
            entry_price=50000.0,
            suggested_stop=48000.0,
            take_profit_1=52000.0,
            status=SignalStatus.WAITING,
        )

        # Mock the requests.post call to capture the payload
        with patch("crypto_signals.notifications.discord.requests.post") as mock_post:
            # Mock successful response
            mock_response = MagicMock()
            mock_response.json.return_value = {"id": "thread_12345"}
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            # Call send_signal
            thread_id = client.send_signal(signal)

            # Verify thread_id was returned
            assert thread_id == "thread_12345"

            # Verify requests.post was called
            assert mock_post.called

            # Extract the JSON payload from the call
            call_args = mock_post.call_args
            json_payload = call_args.kwargs.get("json")

            # CRITICAL ASSERTION: thread_name MUST be present in payload
            assert "thread_name" in json_payload, (
                "send_signal() must include 'thread_name' in payload for Forum channels. "
                "Missing thread_name causes Discord API error 220001."
            )

            # Verify thread_name format is correct
            thread_name = json_payload["thread_name"]
            assert "BTC/USD" in thread_name
            assert "Inverse Head Shoulders" in thread_name

            # Verify it contains an emoji (either rocket or building)
            assert any(emoji in thread_name for emoji in ["🚀", "🏛️", "📊"])


def test_send_signal_without_forum_mode_omits_thread_name():
    """
    Verifies that send_signal() does NOT include thread_name in the payload
    when DISCORD_USE_FORUMS=False.
    """

    from crypto_signals.domain.schemas import SignalStatus
    from crypto_signals.notifications.discord import DiscordClient

    from tests.factories import SignalFactory

    with patch("crypto_signals.notifications.discord.get_settings") as mock_settings:
        settings_instance = MagicMock()
        settings_instance.DISCORD_USE_FORUMS = False  # Forum mode OFF
        settings_instance.TEST_MODE = False  # Ensure TEST_MODE is also off
        settings_instance.TEST_DISCORD_WEBHOOK = MagicMock()
        settings_instance.TEST_DISCORD_WEBHOOK.get_secret_value.return_value = (
            "https://discord.com/api/webhooks/test/webhook"
        )
        mock_settings.return_value = settings_instance

        client = DiscordClient(settings=settings_instance)

        signal = SignalFactory.build(
            signal_id="test-signal-456",
            ds=date(2025, 1, 16),
            strategy_id="test-strategy",
            symbol="ETH/USD",
            asset_class=AssetClass.CRYPTO,
            pattern_name="bullish_engulfing",
            entry_price=3000.0,
            suggested_stop=2900.0,
            status=SignalStatus.WAITING,
        )

        with patch("crypto_signals.notifications.discord.requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {"id": "message_67890"}
            mock_post.return_value = mock_response

            client.send_signal(signal)

            payload = mock_post.call_args.kwargs.get("json")
            assert (
                "thread_name" not in payload
            ), "thread_name should be omitted when DISCORD_USE_FORUMS is False"


def test_send_message_fails_in_forum_mode_without_thread_name():
    """
    Verifies send_message() returns False if DISCORD_USE_FORUMS=True
    and a new thread is attempted without a thread_name.
    """
    from crypto_signals.notifications.discord import DiscordClient

    with patch("crypto_signals.notifications.discord.get_settings") as mock_settings:
        settings_instance = MagicMock()
        settings_instance.DISCORD_USE_FORUMS = True  # Forum mode ON
        settings_instance.TEST_DISCORD_WEBHOOK = MagicMock()
        settings_instance.TEST_DISCORD_WEBHOOK.get_secret_value.return_value = (
            "https://discord.com/api/webhooks/test/webhook"
        )
        mock_settings.return_value = settings_instance

        client = DiscordClient(settings=settings_instance)

        with patch("crypto_signals.notifications.discord.requests.post") as mock_post:
            # Attempt to send a message to a new thread without a thread_name
            result = client.send_message(content="This should fail")

            # CRITICAL ASSERTION: Must return False and not attempt to post
            assert (
                result is False
            ), "send_message should return False in forum mode without a thread_name"
            assert not mock_post.called, "requests.post should not be called when thread_name is missing in forum mode"


def test_send_message_succeeds_in_forum_mode_with_thread_name():
    """
    Verifies send_message() succeeds with a thread_name when
    DISCORD_USE_FORUMS=True.
    """
    from crypto_signals.notifications.discord import DiscordClient

    with patch("crypto_signals.notifications.discord.get_settings") as mock_settings:
        settings_instance = MagicMock()
        settings_instance.DISCORD_USE_FORUMS = True  # Forum mode ON
        settings_instance.TEST_DISCORD_WEBHOOK = MagicMock()
        settings_instance.TEST_DISCORD_WEBHOOK.get_secret_value.return_value = (
            "https://discord.com/api/webhooks/test/webhook"
        )
        mock_settings.return_value = settings_instance

        client = DiscordClient(settings=settings_instance)

        with patch("crypto_signals.notifications.discord.requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            result = client.send_message(
                content="This is a new thread", thread_name="My New Thread"
            )

            assert result is True
            assert mock_post.called

            # Check that 'thread_name' is in the payload
            payload = mock_post.call_args.kwargs.get("json")
            assert "thread_name" in payload
            assert payload["thread_name"] == "My New Thread"


def test_send_message_succeeds_in_text_channel_mode_without_thread_name():
    """
    Verifies send_message() works as normal for standard text channels
    (DISCORD_USE_FORUMS=False) without a thread_name.
    """
    from crypto_signals.notifications.discord import DiscordClient

    with patch("crypto_signals.notifications.discord.get_settings") as mock_settings:
        settings_instance = MagicMock()
        settings_instance.DISCORD_USE_FORUMS = False  # Forum mode OFF
        settings_instance.TEST_DISCORD_WEBHOOK = MagicMock()
        settings_instance.TEST_DISCORD_WEBHOOK.get_secret_value.return_value = (
            "https://discord.com/api/webhooks/test/webhook"
        )
        mock_settings.return_value = settings_instance

        client = DiscordClient(settings=settings_instance)

        with patch("crypto_signals.notifications.discord.requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            result = client.send_message(content="Standard message")

            assert result is True
            assert mock_post.called

            # Check that 'thread_name' is NOT in the payload
            payload = mock_post.call_args.kwargs.get("json")
            assert "thread_name" not in payload


def test_send_shadow_signal_includes_thread_name_in_forum_mode():
    """
    Verifies send_shadow_signal() includes a thread_name in the payload
    when DISCORD_SHADOW_USE_FORUMS=True.
    """
    from crypto_signals.domain.schemas import SignalStatus
    from crypto_signals.notifications.discord import DiscordClient

    from tests.factories import SignalFactory

    with patch("crypto_signals.notifications.discord.get_settings") as mock_settings:
        settings_instance = MagicMock()
        settings_instance.TEST_MODE = False
        settings_instance.DISCORD_SHADOW_USE_FORUMS = True  # Forum mode ON
        settings_instance.DISCORD_SHADOW_WEBHOOK_URL = MagicMock()
        settings_instance.DISCORD_SHADOW_WEBHOOK_URL.get_secret_value.return_value = (
            "https://discord.com/api/webhooks/shadow/webhook"
        )
        mock_settings.return_value = settings_instance

        client = DiscordClient(settings=settings_instance)

        shadow_signal = SignalFactory.build(
            signal_id="shadow-signal-1",
            symbol="DOGE/USD",
            status=SignalStatus.REJECTED_BY_FILTER,
            rejection_reason="LOW_VOLUME",
        )

        with patch("crypto_signals.notifications.discord.requests.post") as mock_post:
            mock_response = MagicMock()
            mock_post.return_value = mock_response

            client.send_shadow_signal(shadow_signal)

            payload = mock_post.call_args.kwargs.get("json")
            assert "thread_name" in payload
            assert "DOGE/USD" in payload["thread_name"]
            assert "Rejected: Low Volume" in payload["thread_name"]


def test_send_shadow_signal_omits_thread_name_in_standard_mode():
    """
    Verifies send_shadow_signal() does NOT include a thread_name
    when DISCORD_SHADOW_USE_FORUMS=False.
    """
    from crypto_signals.domain.schemas import SignalStatus
    from crypto_signals.notifications.discord import DiscordClient

    from tests.factories import SignalFactory

    with patch("crypto_signals.notifications.discord.get_settings") as mock_settings:
        settings_instance = MagicMock()
        settings_instance.TEST_MODE = False
        settings_instance.DISCORD_SHADOW_USE_FORUMS = False  # Forum mode OFF
        settings_instance.DISCORD_SHADOW_WEBHOOK_URL = MagicMock()
        settings_instance.DISCORD_SHADOW_WEBHOOK_URL.get_secret_value.return_value = (
            "https://discord.com/api/webhooks/shadow/webhook"
        )
        mock_settings.return_value = settings_instance

        client = DiscordClient(settings=settings_instance)

        shadow_signal = SignalFactory.build(
            signal_id="shadow-signal-2",
            symbol="SHIB/USD",
            status=SignalStatus.REJECTED_BY_FILTER,
            rejection_reason="HIGH_RISK",
        )

        with patch("crypto_signals.notifications.discord.requests.post") as mock_post:
            mock_response = MagicMock()
            mock_post.return_value = mock_response

            client.send_shadow_signal(shadow_signal)

            payload = mock_post.call_args.kwargs.get("json")
            assert "thread_name" not in payload
