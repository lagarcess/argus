#!/usr/bin/env python3
"""
Crypto Sentinel - Setup Verification Script.

This script verifies connectivity to all required external services:
- Alpaca Trading API (account status)
- Alpaca Market Data API (latest BTC/USD bar)
- GCP Firestore (write/delete test document)
- GCP BigQuery (dry-run query)
- Discord Webhook (send test message)

Run this script to validate your environment before running the main application.
"""

import sys
from datetime import datetime, timedelta, timezone

from alpaca.data.historical.crypto import CryptoHistoricalDataClient
from alpaca.data.models import BarSet
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from google.cloud import bigquery, firestore


def load_settings():
    """
    Load and validate application settings.

    Returns:
        Settings object if successful, None if validation fails
    """
    try:
        from crypto_signals.config import get_settings

        settings = get_settings()
        print("✅ [Configuration] Loaded successfully")
        return settings
    except Exception as e:
        print(f"❌ [Configuration] Failed: {e}")
        return None


def verify_alpaca_trading(settings) -> bool:
    """
    Verify Alpaca Trading API connectivity.

    Fetches account information to confirm API credentials are valid.

    Returns:
        bool: True if connection successful

    Raises:
        Exception: If connection fails
    """
    client = TradingClient(
        api_key=settings.ALPACA_API_KEY,
        secret_key=settings.ALPACA_SECRET_KEY,
        paper=settings.is_paper_trading,
    )

    account = client.get_account()
    print(f"✅ [Alpaca Trade] Connected (Account Status: {account.status})")
    return True


def verify_alpaca_market_data(settings) -> bool:
    """
    Verify Alpaca Market Data API connectivity.

    Fetches the latest bar for BTC/USD to confirm market data access.

    Returns:
        bool: True if connection successful

    Raises:
        Exception: If connection fails
    """
    client = CryptoHistoricalDataClient(
        api_key=settings.ALPACA_API_KEY,
        secret_key=settings.ALPACA_SECRET_KEY,
    )

    request = CryptoBarsRequest(
        symbol_or_symbols="BTC/USD",
        timeframe=TimeFrame.Minute,
        limit=1,
    )

    bars = client.get_crypto_bars(request)

    if isinstance(bars, BarSet) and bars.data and "BTC/USD" in bars.data:
        latest_bar = bars.data["BTC/USD"][-1]
        print(f"✅ [Alpaca Market] Connected (Latest BTC/USD: ${latest_bar.close:,.2f})")
    else:
        print("✅ [Alpaca Market] Connected (No recent bars available)")

    return True


def verify_firestore(settings) -> bool:
    """
    Verify GCP Firestore connectivity.

    Writes a test document to _healthcheck collection and deletes it.

    Returns:
        bool: True if connection successful

    Raises:
        Exception: If connection fails
    """
    db = firestore.Client(project=settings.GOOGLE_CLOUD_PROJECT)

    # Write test document
    doc_ref = db.collection("_healthcheck").document("connection_test")
    doc_ref.set(
        {
            "test": "connection",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )

    # Delete test document
    doc_ref.delete()

    # Phase 7: Verify write permissions for 'rejected_signals' collection
    # Critical for Shadow Signaling audit trail
    shadow_ref = db.collection("rejected_signals").document("health_check_test")
    shadow_ref.set(
        {
            "test": "write_permission",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "delete_at": datetime.now(timezone.utc) + timedelta(minutes=5),
        }
    )
    shadow_ref.delete()

    print(
        "✅ [GCP Firestore] Connected (Write/Delete Test for _healthcheck & rejected_signals Passed)"
    )
    return True


def verify_bigquery(settings) -> bool:
    """
    Verify GCP BigQuery connectivity.

    Runs a dry-run query (SELECT 1) to confirm BigQuery access.

    Returns:
        bool: True if connection successful

    Raises:
        Exception: If connection fails
    """
    client = bigquery.Client(project=settings.GOOGLE_CLOUD_PROJECT)

    # Configure dry-run job
    job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)

    # Execute dry-run query
    query_job = client.query("SELECT 1", job_config=job_config)

    # Dry-run returns estimated bytes processed
    print(
        f"✅ [GCP BigQuery] Connected (Dry-run bytes: {query_job.total_bytes_processed})"
    )
    return True


def verify_discord(settings) -> bool:
    """
    Verify Discord Webhook connectivity for all configured channels.

    Health check strategy (institutional-grade):
    1. Validate URL format for all configured webhooks
    2. Test actual connectivity to each webhook (GET request - no message sent to live)
    3. Send comprehensive status report ONLY to TEST_DISCORD_WEBHOOK
    4. Never send messages to production/live channels

    This ensures health checks never pollute live/production channels while
    still verifying they are operational.

    Returns:
        bool: True if all configured webhooks are operational

    Raises:
        Exception: If connection fails
    """
    import requests

    from crypto_signals.notifications.discord import DiscordClient

    webhook_status = {}

    # --- Step 1: Validate and test TEST_DISCORD_WEBHOOK ---
    test_webhook_url = settings.TEST_DISCORD_WEBHOOK.get_secret_value()
    try:
        # GET request validates webhook exists without sending a message
        response = requests.get(test_webhook_url, timeout=5.0)
        if response.status_code == 200:
            webhook_status["TEST_DISCORD_WEBHOOK"] = ("✅", "Operational")
        else:
            webhook_status["TEST_DISCORD_WEBHOOK"] = ("⚠️", f"HTTP {response.status_code}")
    except requests.RequestException as e:
        webhook_status["TEST_DISCORD_WEBHOOK"] = ("❌", f"Error: {str(e)[:50]}")

    # --- Step 2: Validate LIVE_CRYPTO_DISCORD_WEBHOOK_URL (if configured) ---
    if settings.LIVE_CRYPTO_DISCORD_WEBHOOK_URL:
        crypto_url = settings.LIVE_CRYPTO_DISCORD_WEBHOOK_URL.get_secret_value()
        try:
            response = requests.get(crypto_url, timeout=5.0)
            if response.status_code == 200:
                webhook_status["LIVE_CRYPTO_WEBHOOK"] = ("✅", "Operational")
            else:
                webhook_status["LIVE_CRYPTO_WEBHOOK"] = (
                    "⚠️",
                    f"HTTP {response.status_code}",
                )
        except requests.RequestException as e:
            webhook_status["LIVE_CRYPTO_WEBHOOK"] = ("❌", f"Error: {str(e)[:50]}")
    else:
        webhook_status["LIVE_CRYPTO_WEBHOOK"] = ("➖", "Not configured")

    # --- Step 3: Validate LIVE_STOCK_DISCORD_WEBHOOK_URL (if configured) ---
    if settings.LIVE_STOCK_DISCORD_WEBHOOK_URL:
        stock_url = settings.LIVE_STOCK_DISCORD_WEBHOOK_URL.get_secret_value()
        try:
            response = requests.get(stock_url, timeout=5.0)
            if response.status_code == 200:
                webhook_status["LIVE_STOCK_WEBHOOK"] = ("✅", "Operational")
            else:
                webhook_status["LIVE_STOCK_WEBHOOK"] = (
                    "⚠️",
                    f"HTTP {response.status_code}",
                )
        except requests.RequestException as e:
            webhook_status["LIVE_STOCK_WEBHOOK"] = ("❌", f"Error: {str(e)[:50]}")
    else:
        webhook_status["LIVE_STOCK_WEBHOOK"] = ("➖", "Not configured")

    # --- Step 4: Validate DISCORD_SHADOW_WEBHOOK_URL (Phase 7) ---
    if settings.DISCORD_SHADOW_WEBHOOK_URL:
        shadow_url = settings.DISCORD_SHADOW_WEBHOOK_URL.get_secret_value()
        try:
            response = requests.get(shadow_url, timeout=5.0)
            if response.status_code == 200:
                webhook_status["SHADOW_WEBHOOK"] = ("✅", "Operational")
            else:
                webhook_status["SHADOW_WEBHOOK"] = (
                    "⚠️",
                    f"HTTP {response.status_code}",
                )
        except requests.RequestException as e:
            webhook_status["SHADOW_WEBHOOK"] = ("❌", f"Error: {str(e)[:50]}")
    else:
        # Warning if not configured in production, acceptable in test
        status_icon = "➖" if settings.TEST_MODE else "⚠️"
        webhook_status["SHADOW_WEBHOOK"] = (
            status_icon,
            "Not configured (Shadow disabled)",
        )

    # --- Step 4.5: Validate DISCORD_DEPLOYS (CI/CD Deployments Webhook) ---
    if settings.DISCORD_DEPLOYS:
        deploys_url = settings.DISCORD_DEPLOYS.get_secret_value()
        try:
            response = requests.get(deploys_url, timeout=5.0)
            if response.status_code == 200:
                webhook_status["DEPLOYS_WEBHOOK"] = ("✅", "Operational")
            else:
                webhook_status["DEPLOYS_WEBHOOK"] = (
                    "⚠️",
                    f"HTTP {response.status_code}",
                )
        except requests.RequestException as e:
            webhook_status["DEPLOYS_WEBHOOK"] = ("❌", f"Error: {str(e)[:50]}")
    else:
        # Not critical - only used in CI/CD, not in application
        webhook_status["DEPLOYS_WEBHOOK"] = ("➖", "Not configured (CI/CD only)")

    # --- Step 5: Build comprehensive status message ---
    mode_str = "TEST" if settings.TEST_MODE else "LIVE"
    status_lines = [
        "✅ **[Health Check]** System is online",
        f"**Mode:** {mode_str}",
        "",
        "**Webhook Status:**",
    ]
    for webhook_name, (emoji, status) in webhook_status.items():
        status_lines.append(f"{emoji} `{webhook_name}`: {status}")

    msg = "\n".join(status_lines)

    # --- Step 6: Send report to TEST_DISCORD_WEBHOOK only ---
    client = DiscordClient(settings=settings)
    success = client.send_message(
        msg,
        thread_name="System Health Check",  # Required for Forum channels
        asset_class=None,  # System message → always routes to TEST_DISCORD_WEBHOOK
    )

    if not success:
        print("❌ [Discord] Failed to send health report to TEST_DISCORD_WEBHOOK")
        return False

    # --- Step 7: Print console status ---
    print("✅ [Discord] Health report sent to TEST_DISCORD_WEBHOOK")
    for webhook_name, (emoji, status) in webhook_status.items():
        print(f"   {emoji} {webhook_name}: {status}")

    # --- Step 8: Validate operational status ---
    # In TEST_MODE: "➖" (not configured) is acceptable for live webhooks
    # In LIVE_MODE: Live webhooks must be "✅" (not "➖" or any error)
    all_operational = True

    for webhook_name, (emoji, _) in webhook_status.items():
        if emoji == "❌" or emoji == "⚠️":
            # Any error is a failure
            all_operational = False
        elif emoji == "➖" and not settings.TEST_MODE:
            # In LIVE mode, unconfigured live webhooks are a failure
            if webhook_name in ("LIVE_CRYPTO_WEBHOOK", "LIVE_STOCK_WEBHOOK"):
                print(f"   ❌ {webhook_name}: Required in LIVE mode but not configured")
                all_operational = False

    return all_operational


def run_all_verifications() -> bool:
    """
    Run all service verifications.

    Returns:
        bool: True if all verifications pass, False otherwise
    """
    print()
    print("🔍 Checking Services...")
    print()

    # Step 1: Load configuration
    settings = load_settings()
    if settings is None:
        print()
        print("❌ Cannot proceed without valid configuration.")
        print("   Please check your .env file and environment variables.")
        return False

    # Step 2: Run individual service checks
    verifications = [
        ("Alpaca Market", verify_alpaca_market_data),
        ("Alpaca Trade", verify_alpaca_trading),
        ("GCP Firestore", verify_firestore),
        ("GCP BigQuery", verify_bigquery),
        ("Discord", verify_discord),
    ]

    all_passed = True

    for service_name, verify_func in verifications:
        try:
            if not verify_func(settings):
                print(f"❌ [{service_name}] Returned False (Check logs)")
                all_passed = False
        except Exception as e:
            print(f"❌ [{service_name}] Failed: {e}")
            all_passed = False

    print()

    if all_passed:
        print("✅ All verifications passed! System ready.")
    else:
        print("⚠️  Some verifications failed. Please check the errors above.")

    return all_passed


if __name__ == "__main__":
    success = run_all_verifications()
    sys.exit(0 if success else 1)
