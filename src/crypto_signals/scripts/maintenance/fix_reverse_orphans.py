#!/usr/bin/env python3
"""
Healing Script: Fix Reverse Orphans (Issue #139)

Detects positions that are:
1. CLOSED in Firestore (status=CLOSED)
2. OPEN in Alpaca (qty > 0)

Action:
- Submits market SELL order to Alpaca to close the position.
- Updates Firestore with the new exit_order_id.
"""

import os

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.models import Order, Position
from alpaca.trading.requests import MarketOrderRequest
from google.cloud import firestore
from rich.console import Console
from rich.prompt import Confirm
from rich.table import Table

from crypto_signals.config import get_settings
from crypto_signals.utils.symbols import normalize_alpaca_symbol


def heal_reverse_orphans():
    # Ensure PROD
    os.environ.setdefault("ENVIRONMENT", "PROD")
    console = Console()
    settings = get_settings()

    if settings.ENVIRONMENT != "PROD":
        console.print("[bold red]⚠️  Must run in PROD environment![/bold red]")
        return

    console.print(
        "[bold cyan]🩹 Healing Reverse Orphans (Closed in DB, Open in Alpaca)[/bold cyan]"
    )

    # Initialize Clients
    db = firestore.Client(project=settings.GOOGLE_CLOUD_PROJECT)
    alpaca = TradingClient(
        api_key=settings.ALPACA_API_KEY,
        secret_key=settings.ALPACA_SECRET_KEY,
        paper=settings.is_paper_trading,
    )

    collection_name = "live_positions"
    console.print(f"Scanning {collection_name}...")

    # 1. Get all CLOSED positions from DB
    # (In a real scenario with thousands of records, we'd limit or paginate.
    # For now, we fetch recent ones or rely on the user's "14" hint)
    # Optimization: Only check positions updated recently or iterate all closed?
    # Let's iterate closed positions from the last 30 days or simply all (if feasible).
    # Given the context, we'll scan the last 200 closed positions.

    closed_ref = db.collection(collection_name).where("status", "==", "CLOSED").limit(200)
    closed_docs = list(closed_ref.stream())

    console.print(f"Fetched {len(closed_docs)} closed positions from DB.")

    orphans = []

    with console.status("Checking Alpaca status..."):
        for doc in closed_docs:
            data = doc.to_dict()
            symbol = data.get("symbol")

            # Skip Theoretical
            if data.get("trade_type") == "THEORETICAL":
                continue

            try:
                # Check Alpaca
                pos = alpaca.get_open_position(normalize_alpaca_symbol(symbol))

                # If we get here, it's OPEN in Alpaca
                if isinstance(pos, Position):
                    qty = float(pos.qty) if pos.qty is not None else 0.0
                    market_value = (
                        float(pos.market_value) if pos.market_value is not None else 0.0
                    )
                    orphans.append(
                        {
                            "doc_id": doc.id,
                            "symbol": symbol,
                            "db_qty": data.get("qty"),
                            "alpaca_qty": qty,
                            "alpaca_val": market_value,
                            "exit_reason": data.get("exit_reason"),
                        }
                    )
            except Exception:
                # 404 - Position is actually closed in Alpaca (Good)
                pass

    if not orphans:
        console.print(
            "[bold green]✅ No Reverse Orphans found! (DB Closed = Alpaca Closed)[/bold green]"
        )
        return

    # Display Orphans
    table = Table(title="Reverse Orphans Detected")
    table.add_column("Symbol", style="cyan")
    table.add_column("DB Status", style="green")
    table.add_column("Alpaca Qty", style="red")
    table.add_column("Market Value", style="yellow")
    table.add_column("DB Doc ID", style="dim")

    for o in orphans:
        table.add_row(
            o["symbol"],
            "CLOSED",
            str(o["alpaca_qty"]),
            f"${o['alpaca_val']:.2f}",
            o["doc_id"],
        )

    console.print(table)

    if not Confirm.ask("Do you want to CLOSE these positions in Alpaca and update DB?"):
        console.print("Cancelled.")
        return

    # Execute Healing
    for o in orphans:
        symbol = o["symbol"]
        qty = o["alpaca_qty"]
        doc_id = o["doc_id"]

        console.print(f"Closing {symbol} (Qty: {qty})...")

        try:
            # Determine side (always sell for long exit, assuming long only for now)
            # Todo: Check position side if we support shorts.
            # Assuming Long Exits for safety (selling).

            req = MarketOrderRequest(
                symbol=normalize_alpaca_symbol(symbol),
                qty=qty,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.GTC,
            )

            order = alpaca.submit_order(req)
            if isinstance(order, Order):
                console.print(f" -> Order Submitted: {order.id}")

                # Update DB with new exit info
                # We won't wait for fill here (async), just record the order ID
                # The Sync Loop will pick up the fill details later (or manual check)

                db.collection(collection_name).document(doc_id).update(
                    {
                        "exit_order_id": str(order.id),
                        "exit_reason": "MANUAL_FIX_139",  # Tag it
                        "awaiting_backfill": True,
                    }
                )
            console.print(" -> DB Updated")

        except Exception as e:
            console.print(f"[bold red]FAILED to close {symbol}: {e}[/bold red]")

    console.print("[bold green]Healing Complete.[/bold green]")


if __name__ == "__main__":
    heal_reverse_orphans()
