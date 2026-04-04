import os
import sys

from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from alpaca.common.exceptions import APIError
from crypto_signals.config import get_trading_client


def validate_assets():
    load_dotenv()
    trading_client = get_trading_client()

    raw_symbols = [
        "AAVE",
        "AVAX",
        "BAT",
        "BCH",
        "BTC",
        "CRV",
        "DOGE",
        "DOT",
        "ETH",
        "GRT",
        "LINK",
        "LTC",
        "PEPE",
        "SHIB",
        "SOL",
        "SUSHI",
        "UNI",
        "USDC",
        "USDT",
        "XRP",
        "XTZ",
        "YFI",
    ]

    valid_symbols = []

    print(f"Validating {len(raw_symbols)} assets against Alpaca API...")

    for symbol in raw_symbols:
        # Try both raw format and /USD format
        formats_to_try = [f"{symbol}/USD", symbol]

        found = False
        for fmt in formats_to_try:
            try:
                asset = trading_client.get_asset(fmt)
                if asset.tradable:
                    valid_symbols.append(fmt)
                    print(f"✅ {fmt}: Valid and Tradable")
                    found = True
                    break
                else:
                    print(f"⚠️ {fmt}: Found but NOT tradable")
            except APIError:
                continue
            except Exception as e:
                print(f"❌ {fmt}: Error - {str(e)}")

        if not found:
            print(f"❌ {symbol}: Not found or not tradable")

    print("\n" + "=" * 50)
    print("VALID SYMBOLS FOR .env:")
    print("=" * 50)
    result = ",".join(valid_symbols)
    print(result)

    with open("valid_assets.txt", "w") as f:
        f.write(result)


if __name__ == "__main__":
    validate_assets()
