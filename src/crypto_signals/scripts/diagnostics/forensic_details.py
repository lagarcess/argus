#!/usr/bin/env python3
"""Quick forensic details script."""

import os

os.environ.setdefault("ENVIRONMENT", "PROD")  # noqa: E402


from google.cloud import firestore  # noqa: E402

from crypto_signals.config import get_settings  # noqa: E402

settings = get_settings()
db = firestore.Client(project=settings.GOOGLE_CLOUD_PROJECT)

# Get closed positions
positions = db.collection("live_positions").where("status", "==", "CLOSED").stream()

print("=== CLOSED POSITIONS IN FIRESTORE ===\n")
for doc in positions:
    data = doc.to_dict()
    print(f"Symbol: {data.get('symbol')}")
    print(f"  Position ID: {data.get('position_id')}")
    print(f"  Exit Reason: {data.get('exit_reason')}")
    print(f"  Trade Type: {data.get('trade_type', 'LIVE')}")
    print(f"  Entry Fill: ${data.get('entry_fill_price', 0):.2f}")
    exit_price = data.get("exit_fill_price") or 0
    print(f"  Exit Fill: ${exit_price:.2f}")
    print(f"  Side: {data.get('side')}")
    print(f"  Alpaca Order ID: {data.get('alpaca_order_id')}")
    print("---")

# Also check signals
print("\n\n=== EXITED SIGNALS IN FIRESTORE ===\n")
exit_statuses = ["TP1_HIT", "TP2_HIT", "TP3_HIT", "INVALIDATED"]
for status in exit_statuses:
    signals = (
        db.collection("live_signals").where("status", "==", status).limit(10).stream()
    )
    for doc in signals:
        data = doc.to_dict()
        print(f"Symbol: {data.get('symbol')}")
        print(f"  Signal ID: {data.get('signal_id')}")
        print(f"  Status: {data.get('status')}")
        print(f"  Exit Reason: {data.get('exit_reason')}")
        print(f"  Pattern: {data.get('pattern_name')}")
        print("---")
