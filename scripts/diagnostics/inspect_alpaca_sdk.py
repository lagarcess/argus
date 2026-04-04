"""
Diagnostic script to inspect Alpaca SDK capabilities and available methods.
Useful for verifying API surface area across different SDK versions.
"""

import sys
from pprint import pprint

try:
    from alpaca.trading import requests
    from alpaca.trading.client import TradingClient
except ImportError:
    print("Error: alpaca-py not installed.")
    sys.exit(1)


def inspect_sdk():
    print("=== Alpaca SDK Inspection ===\n")

    # Inspect TradingClient attributes
    print("--- TradingClient Attributes ---")
    client_attrs = [a for a in dir(TradingClient) if not a.startswith("_")]
    pprint(client_attrs)

    # Check for specific methods of interest
    target_methods = ["get_account_activities", "get_account", "get"]
    print("\n--- Method Availability Check ---")
    for method in target_methods:
        exists = hasattr(TradingClient, method)
        print(f"TradingClient.{method}: {'AVAILABLE' if exists else 'MISSING'}")

    # Inspect requests module
    print("\n--- alpaca.trading.requests Classes ---")
    req_classes = [a for a in dir(requests) if not a.startswith("_")]
    pprint(req_classes)


if __name__ == "__main__":
    inspect_sdk()
