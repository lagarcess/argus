#!/usr/bin/env python3
"""
Diagnostic: Check Alpaca Positions vs Firestore
"""

import os

from alpaca.trading.client import TradingClient
from google.cloud import firestore
from rich.console import Console
from rich.table import Table

from crypto_signals.config import get_settings

# Ensure PROD
os.environ.setdefault("ENVIRONMENT", "PROD")


def check_alpaca_vs_db():
    console = Console()
    settings = get_settings()

    console.print(
        f"[bold cyan]🔍 Checking Alpaca Positions vs Firestore ({settings.ENVIRONMENT})[/bold cyan]"
    )

    # Init Clients
    alpaca = TradingClient(
        api_key=settings.ALPACA_API_KEY,
        secret_key=settings.ALPACA_SECRET_KEY,
        paper=settings.is_paper_trading,
    )
    db = firestore.Client(project=settings.GOOGLE_CLOUD_PROJECT)
    collection = "live_positions" if settings.ENVIRONMENT == "PROD" else "test_positions"

    # 1. Get Alpaca Positions
    try:
        alpaca_positions = alpaca.get_all_positions()
        console.print(f"Found {len(alpaca_positions)} open positions in Alpaca.")
    except Exception as e:
        console.print(f"[bold red]Failed to fetch Alpaca positions: {e}[/bold red]")
        return

    if not alpaca_positions:
        console.print("No open positions in Alpaca.")
        return

    # 2. Check DB
    table = Table(title="Alpaca vs Firestore")
    table.add_column("Symbol", style="cyan")
    table.add_column("Qty", style="yellow")
    table.add_column("DB Status", style="magenta")
    table.add_column("DB Doc ID", style="dim")
    table.add_column("Match?", style="bold")

    orphans = []
    from alpaca.trading.models import Position

    for pos in alpaca_positions:
        if not isinstance(pos, Position):
            continue
        symbol = pos.symbol
        qty = pos.qty

        # Normalize Symbol (Alpaca 'AAVEUSD' -> DB 'AAVE/USD')
        # DB uses 'BTC/USD' format for crypto.
        potential_symbols = [symbol]
        if "USD" in symbol and "/" not in symbol:
            potential_symbols.append(symbol.replace("USD", "/USD"))

        docs = []
        for s in potential_symbols:
            d = list(db.collection(collection).where("symbol", "==", s).limit(5).stream())
            if d:
                docs = d
                break

        db_status = "MISSING"
        doc_id = "-"
        match = "[red]ORPHAN[/red]"

        # Sort manually if needed, or rely on simple check
        # Ideally we look for OPEN positions first
        found_open = False
        latest_doc = None

        for d in docs:
            data = d.to_dict()
            if data.get("status") == "OPEN":
                db_status = "OPEN"
                doc_id = d.id
                match = "[green]OK[/green]"
                found_open = True
                break
            latest_doc = d

        if not found_open and latest_doc:
            # If we found records but none OPEN
            data = latest_doc.to_dict()
            db_status = f"{data.get('status')} (Closed)"
            doc_id = latest_doc.id
            match = "[yellow]MISMATCH[/yellow]"

        table.add_row(symbol, str(qty), db_status, doc_id, match)

        if db_status == "MISSING":
            orphans.append(symbol)

    console.print(table)
    console.print(
        f"\nSummary: {len(orphans)} Orphans (Missing in DB), {len(alpaca_positions) - len(orphans)} Matched/Mismatch"
    )


if __name__ == "__main__":
    check_alpaca_vs_db()
