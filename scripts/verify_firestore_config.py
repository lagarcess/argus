"""
Script to verify Firestore Configuration Loading.

This script attempts to call `load_config_from_firestore` and prints the result.
It validates that we can connect to Firestore and parse the `dim_strategies` collection.
"""

import os
import sys

from loguru import logger

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "../src"))

from crypto_signals.config import get_settings, load_config_from_firestore
from crypto_signals.secrets_manager import init_secrets

# Configure logging to stdout
logger.remove()
logger.add(sys.stdout, format="{time} - {level} - {message}", level="INFO")


def verify_firestore_config():
    logger.info("Initializing secrets...")
    init_secrets()

    settings = get_settings()
    logger.info(f"Project: {settings.GOOGLE_CLOUD_PROJECT}")

    logger.info("Attempting to load config from Firestore...")
    config = load_config_from_firestore()

    logger.info("=== CONFIGURATION RESULT ===")
    logger.info(f"Crypto Symbols: {config.get('CRYPTO_SYMBOLS', [])}")
    logger.info(f"Equity Symbols: {config.get('EQUITY_SYMBOLS', [])}")

    if not config:
        logger.warning(
            "Config is empty! Check if you have active strategies in 'dim_strategies'."
        )
    else:
        logger.info("SUCCESS: Configuration loaded from Firestore.")


if __name__ == "__main__":
    verify_firestore_config()
