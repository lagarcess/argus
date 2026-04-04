#!/usr/bin/env python3
"""
Cleanup Script: Resolve Legacy Gaps (Issue #139)

The forensic analysis identified 43 gaps where positions are CLOSED in Firestore,
CLOSED in Alpaca, but missing an `exit_order_id` / sell order verification.

Since these are historical records (not active in Alpaca), we cannot "close" them.
We reconcile them by marking them as LEGACY_GAP_RESOLVED to clear the forensic report.

Safety:
- Double-checks that position is NOT open in Alpaca before touching.
"""

import os

from alpaca.trading.client import TradingClient
from google.cloud import firestore
from rich.console import Console
from rich.prompt import Confirm

from crypto_signals.config import get_settings

# Ensure PROD
os.environ.setdefault("ENVIRONMENT", "PROD")


def cleanup_legacy_gaps():
    console = Console()
    settings = get_settings()

    if settings.ENVIRONMENT != "PROD":
        console.print("[bold red]⚠️  Must run in PROD environment![/bold red]")
        return

    console.print(
        "[bold cyan]🧹 Cleaning Legacy Gaps (Closed DB/Alpaca, Missing Order)[/bold cyan]"
    )

    # Initialize Clients
    db = firestore.Client(project=settings.GOOGLE_CLOUD_PROJECT)
    alpaca = TradingClient(
        api_key=settings.ALPACA_API_KEY,
        secret_key=settings.ALPACA_SECRET_KEY,
        paper=settings.is_paper_trading,
    )

    collection_name = "live_positions"
    console.print(f"Scanning {collection_name} for gaps...")

    # Scan for gaps
    closed_docs = list(
        db.collection(collection_name).where("status", "==", "CLOSED").limit(500).stream()
    )

    tobe_fixed = []

    with console.status("Verifying gaps..."):
        for doc in closed_docs:
            data = doc.to_dict()
            symbol = data.get("symbol")

            # Skip Theoretical
            if data.get("trade_type") == "THEORETICAL":
                continue

            # If already fixed, skip
            if data.get("exit_order_id") == "LEGACY_GAP_RESOLVED":
                continue

            # Identify Gap: No Alpaca Order ID (or no exit order id)
            # The forensic script checks for SELL orders.
            # We used to mark MANUAL_EXIT without recording the ID.

            # If we have a valid alpaca_order_id (entry) but no exit info...
            # And forensic analysis flagged it...
            # We'll just check if it's OPEN in Alpaca.

            try:
                # Check status
                alpaca.get_open_position(symbol)
                # It exists! It's OPEN!
                console.print(f"[red]SKIPPING {symbol}: Position is OPEN locally![/red]")
                continue
            except Exception:
                # 404 - Good, it is closed in Alpaca.
                pass

            # Check if we should fix it
            # We fix if it has NO exit_order_id (or if we assume we need to fill it)
            if not data.get("exit_order_id"):
                tobe_fixed.append(doc)

    console.print(f"Found {len(tobe_fixed)} legacy gaps to resolve.")

    if not Confirm.ask("Mark these as LEGACY_GAP_RESOLVED?"):
        return

    count = 0
    for doc in tobe_fixed:
        try:
            doc.reference.update(
                {
                    "exit_order_id": "LEGACY_GAP_RESOLVED",
                    "exit_reason": "MANUAL_EXIT_LEGACY",  # Preserve context
                }
            )
            count += 1
        except Exception as e:
            console.print(f"Failed to update {doc.id}: {e}")

    console.print(f"[bold green]✅ Resolved {count} legacy gaps.[/bold green]")


if __name__ == "__main__":
    cleanup_legacy_gaps()
