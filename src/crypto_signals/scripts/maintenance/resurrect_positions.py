#!/usr/bin/env python3
"""
Healing Script: Resurrect False-Closed Positions (Issue #139)

Detects positions that are:
1. CLOSED in Firestore (status=CLOSED)
2. OPEN in Alpaca (qty > 0)
   (Handling Symbol format mismatch: DB 'ETH/USD' vs Alpaca 'ETHUSD')

Action:
- Updates Firestore status to OPEN.
- Clears exit fields (`exit_reason`, `exit_time`, `exit_fill_price`, `exit_order_id`).
- This allows the system to resume managing them.
"""

import os

from alpaca.trading.client import TradingClient
from google.cloud import firestore
from rich.console import Console
from rich.prompt import Confirm
from rich.table import Table

from crypto_signals.config import get_settings

# Ensure PROD
os.environ.setdefault("ENVIRONMENT", "PROD")


def resurrect_positions():
    console = Console()
    settings = get_settings()

    if settings.ENVIRONMENT != "PROD":
        console.print("[bold red]⚠️  Must run in PROD environment![/bold red]")
        return

    console.print("[bold cyan]🔥 Resurrecting False-Closed Positions[/bold cyan]")

    # Initialize Clients
    db = firestore.Client(project=settings.GOOGLE_CLOUD_PROJECT)
    alpaca = TradingClient(
        api_key=settings.ALPACA_API_KEY,
        secret_key=settings.ALPACA_SECRET_KEY,
        paper=settings.is_paper_trading,
    )

    collection_name = "live_positions"
    console.print(f"Scanning {collection_name} for resurrection candidates...")

    # Get all Alpaca Positions first (Source of Truth for 'OPEN')
    try:
        from alpaca.trading.models import Position

        alpaca_positions = alpaca.get_all_positions()
        alpaca_map: dict[str, Position] = {
            p.symbol: p for p in alpaca_positions if isinstance(p, Position)
        }
    except Exception as e:
        console.print(f"[bold red]Failed to fetch Alpaca positions: {e}[/bold red]")
        return

    if not alpaca_map:
        console.print("No open positions in Alpaca to match.")
        return

    # Scan DB Closed positions
    # We look for DB records matching Alpaca symbols
    candidates = []

    for symbol, alpaca_pos in alpaca_map.items():
        # Normalized lookup: Alpaca 'ETHUSD' -> DB 'ETH/USD'
        db_symbol = symbol
        if "USD" in symbol and "/" not in symbol:
            db_symbol = symbol.replace("USD", "/USD")

        # Find latest doc
        docs = list(
            db.collection(collection_name)
            .where("symbol", "==", db_symbol)
            .limit(5)
            .stream()
        )

        target_doc = None
        for d in docs:
            data = d.to_dict()
            # We want the one that is CLOSED
            if data.get("status") == "CLOSED":
                target_doc = d
                break
            elif data.get("status") == "OPEN":
                # Already open, no need to resurrect
                target_doc = None
                break

        if target_doc:
            candidates.append(
                {
                    "doc_id": target_doc.id,
                    "symbol": db_symbol,
                    "alpaca_qty": alpaca_pos.qty,
                    "db_reason": target_doc.to_dict().get("exit_reason"),
                }
            )

    if not candidates:
        console.print(
            "[bold green]✅ No resurrection candidates found (All Alpaca positions match Open DB records).[/bold green]"
        )
        return

    # Display Candidates
    table = Table(title="Resurrection Candidates")
    table.add_column("Symbol", style="cyan")
    table.add_column("DB Reason", style="red")
    table.add_column("Alpaca Qty", style="yellow")
    table.add_column("Doc ID", style="dim")

    for c in candidates:
        table.add_row(c["symbol"], str(c["db_reason"]), str(c["alpaca_qty"]), c["doc_id"])

    console.print(table)

    if not Confirm.ask("Resurrect these positions (Set OPEN in DB)?"):
        return

    # Execute Resurrection
    count = 0
    for c in candidates:
        try:
            db.collection(collection_name).document(c["doc_id"]).update(
                {
                    "status": "OPEN",
                    "exit_reason": firestore.DELETE_FIELD,
                    "exit_time": firestore.DELETE_FIELD,
                    "exit_fill_price": firestore.DELETE_FIELD,
                    "exit_order_id": firestore.DELETE_FIELD,
                    "failed_reason": firestore.DELETE_FIELD,  # Clear past errors
                }
            )
            count += 1
            console.print(f" -> Resurrected {c['symbol']}")
        except Exception as e:
            console.print(f"[bold red]Failed to update {c['symbol']}: {e}[/bold red]")

    console.print(f"[bold green]✅ Resurrected {count} positions.[/bold green]")


if __name__ == "__main__":
    resurrect_positions()
