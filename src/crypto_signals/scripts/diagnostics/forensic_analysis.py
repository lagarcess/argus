#!/usr/bin/env python3
"""
Forensic Analysis Script - Exit Order Gap Detection.

This script investigates whether exits in Firestore correspond to actual
sell orders in Alpaca. It identifies:
1. Positions/Signals that hit TP or were invalidated
2. Cross-references with Alpaca orders to find sell orders
3. Reports any gaps where Firestore shows exit but Alpaca has no sell

Usage:
    python -m crypto_signals.scripts.forensic_analysis
"""

# Ensure PROD environment for diagnostics
import os
import sys
from typing import Optional

os.environ.setdefault("ENVIRONMENT", "PROD")  # noqa: E402

from alpaca.trading.client import TradingClient  # noqa: E402
from alpaca.trading.enums import OrderSide, QueryOrderStatus  # noqa: E402
from alpaca.trading.models import Order  # noqa: E402
from alpaca.trading.requests import GetOrdersRequest  # noqa: E402
from google.cloud import firestore  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402


def load_settings():
    """Load application settings."""
    try:
        from crypto_signals.config import get_settings

        return get_settings()
    except Exception as e:
        print(f"❌ Failed to load settings: {e}")
        return None


def get_closed_signals(db, collection_name: str, limit: int = 50):
    """Get signals with exit statuses (TP_HIT, INVALIDATED, EXPIRED)."""
    exit_statuses = ["TP1_HIT", "TP2_HIT", "TP3_HIT", "INVALIDATED", "EXPIRED"]

    # Query signals that hit exits
    signals = []

    for status in exit_statuses:
        query = db.collection(collection_name).where("status", "==", status).limit(limit)

        for doc in query.stream():
            data = doc.to_dict()
            data["doc_id"] = doc.id
            signals.append(data)

    return signals


def get_closed_positions(db, collection_name: str, limit: int = 50):
    """Get positions with CLOSED status."""
    query = db.collection(collection_name).where("status", "==", "CLOSED").limit(limit)

    positions = []
    for doc in query.stream():
        data = doc.to_dict()
        data["doc_id"] = doc.id
        positions.append(data)

    return positions


def get_all_positions(db, collection_name: str, limit: int = 100):
    """Get all positions (for debugging)."""
    query = db.collection(collection_name).limit(limit)

    positions = []
    for doc in query.stream():
        data = doc.to_dict()
        data["doc_id"] = doc.id
        positions.append(data)

    return positions


def get_alpaca_orders(
    alpaca: TradingClient, symbol: Optional[str] = None, limit: int = 100
):
    """Get filled orders from Alpaca."""
    try:
        request = GetOrdersRequest(
            status=QueryOrderStatus.ALL,
            limit=limit,
        )
        orders = alpaca.get_orders(filter=request)

        # Filter to ensure Order objects (narrowing Union)
        orders = [o for o in orders if isinstance(o, Order)]

        # Filter to symbol if provided
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]

        return orders
    except Exception as e:
        print(f"❌ Failed to fetch Alpaca orders: {e}")
        return []


def analyze_exit_gap(console: Console, settings):
    """Main analysis function."""
    console.print(
        "\n[bold cyan]🔍 FORENSIC ANALYSIS: Exit Order Gap Detection[/bold cyan]\n"
    )

    # Initialize clients
    db = firestore.Client(project=settings.GOOGLE_CLOUD_PROJECT)
    alpaca = TradingClient(
        api_key=settings.ALPACA_API_KEY,
        secret_key=settings.ALPACA_SECRET_KEY,
        paper=settings.is_paper_trading,
    )

    # Determine collections based on environment
    signals_collection = (
        "live_signals" if settings.ENVIRONMENT == "PROD" else "test_signals"
    )
    positions_collection = (
        "live_positions" if settings.ENVIRONMENT == "PROD" else "test_positions"
    )

    console.print(f"[dim]Environment: {settings.ENVIRONMENT}[/dim]")
    console.print(f"[dim]Signals Collection: {signals_collection}[/dim]")
    console.print(f"[dim]Positions Collection: {positions_collection}[/dim]\n")

    # ======================================================================
    # SECTION 1: Firestore Signals with Exit Status
    # ======================================================================
    console.print(
        "[bold yellow]📊 Section 1: Firestore Signals with Exit Status[/bold yellow]"
    )

    exited_signals = get_closed_signals(db, signals_collection)
    console.print(f"Found {len(exited_signals)} exited signals\n")

    if exited_signals:
        table = Table(title="Exited Signals", show_lines=True)
        table.add_column("Signal ID", style="cyan", max_width=20)
        table.add_column("Symbol", style="green")
        table.add_column("Status", style="yellow")
        table.add_column("Exit Reason", style="magenta")
        table.add_column("Pattern", style="blue")

        for sig in exited_signals[:20]:  # Limit display
            table.add_row(
                sig.get("signal_id", "N/A")[:20],
                sig.get("symbol", "N/A"),
                sig.get("status", "N/A"),
                str(sig.get("exit_reason", "N/A")),
                sig.get("pattern_name", "N/A"),
            )

        console.print(table)
        console.print()

    # ======================================================================
    # SECTION 2: Firestore Positions (All)
    # ======================================================================
    console.print("[bold yellow]📊 Section 2: Firestore Positions[/bold yellow]")

    all_positions = get_all_positions(db, positions_collection)
    console.print(f"Found {len(all_positions)} total positions\n")

    closed_positions = [p for p in all_positions if p.get("status") == "CLOSED"]
    open_positions = [p for p in all_positions if p.get("status") == "OPEN"]

    console.print(f"  - OPEN: {len(open_positions)}")
    console.print(f"  - CLOSED: {len(closed_positions)}\n")

    if all_positions:
        table = Table(title="All Positions", show_lines=True)
        table.add_column("Position ID", style="cyan", max_width=20)
        table.add_column("Symbol", style="green")
        table.add_column("Status", style="yellow")
        table.add_column("Exit Reason", style="magenta")
        table.add_column("Side", style="blue")
        table.add_column("Trade Type", style="dim")
        table.add_column("Alpaca Order ID", style="dim", max_width=15)

        for pos in all_positions:
            table.add_row(
                pos.get("position_id", "N/A")[:20],
                pos.get("symbol", "N/A"),
                pos.get("status", "N/A"),
                str(pos.get("exit_reason", "-")),
                pos.get("side", "N/A"),
                pos.get("trade_type", "LIVE"),
                str(pos.get("alpaca_order_id", "N/A"))[:15]
                if pos.get("alpaca_order_id")
                else "-",
            )

        console.print(table)
        console.print()

    # ======================================================================
    # SECTION 3: Alpaca Orders Analysis
    # ======================================================================
    console.print("[bold yellow]📊 Section 3: Alpaca Orders[/bold yellow]")

    # Get unique symbols from positions
    symbols = set(p.get("symbol") for p in all_positions if p.get("symbol"))
    console.print(f"Analyzing {len(symbols)} symbols: {list(symbols)}\n")

    all_alpaca_orders = get_alpaca_orders(alpaca, limit=500)
    console.print(f"Total Alpaca orders retrieved: {len(all_alpaca_orders)}\n")

    # Categorize orders by side
    buy_orders = [o for o in all_alpaca_orders if o.side == OrderSide.BUY]
    sell_orders = [o for o in all_alpaca_orders if o.side == OrderSide.SELL]

    console.print(f"  - BUY orders: {len(buy_orders)}")
    console.print(f"  - SELL orders: {len(sell_orders)}\n")

    if all_alpaca_orders:
        table = Table(title="Alpaca Orders (Last 50)", show_lines=True)
        table.add_column("Order ID", style="cyan", max_width=15)
        table.add_column("Symbol", style="green")
        table.add_column("Side", style="yellow")
        table.add_column("Status", style="magenta")
        table.add_column("Type", style="blue")
        table.add_column("Qty", style="dim")
        table.add_column("Client Order ID", style="dim", max_width=20)

        for order in all_alpaca_orders[:50]:
            side_style = "[green]" if order.side == OrderSide.BUY else "[red]"
            table.add_row(
                str(order.id)[:15],
                order.symbol,
                f"{side_style}{order.side.value}[/]",
                str(order.status),
                str(order.order_type),
                str(order.qty or order.filled_qty),
                str(order.client_order_id or "-")[:20],
            )

        console.print(table)
        console.print()

    # ======================================================================
    # SECTION 4: Gap Detection
    # ======================================================================
    console.print("[bold yellow]🚨 Section 4: Gap Detection[/bold yellow]\n")

    # Build set of Alpaca sell order symbols
    set(o.symbol for o in sell_orders)

    # Check for positions that show CLOSED but no sell order exists
    gaps_detected = []

    for pos in closed_positions:
        symbol = pos.get("symbol")
        trade_type = pos.get("trade_type", "LIVE")

        # Skip theoretical trades - they don't hit Alpaca
        if trade_type in ("THEORETICAL", "RISK_BLOCKED"):
            continue

        # Skip resolved legacy gaps
        if pos.get("exit_order_id") == "LEGACY_GAP_RESOLVED":
            continue

        # Check if any sell order exists for this symbol
        matching_sells = [
            o
            for o in sell_orders
            if o.symbol == symbol and str(o.status).lower() == "filled"
        ]

        if not matching_sells:
            gaps_detected.append(
                {
                    "position_id": pos.get("position_id"),
                    "symbol": symbol,
                    "status": pos.get("status"),
                    "exit_reason": pos.get("exit_reason"),
                    "alpaca_order_id": pos.get("alpaca_order_id"),
                    "trade_type": trade_type,
                }
            )

    if gaps_detected:
        console.print(
            f"[bold red]⚠️  GAPS DETECTED: {len(gaps_detected)} positions closed in Firestore but NO SELL ORDER in Alpaca[/bold red]\n"
        )

        gap_table = Table(title="Exit Order Gaps", show_lines=True, border_style="red")
        gap_table.add_column("Position ID", style="cyan", max_width=20)
        gap_table.add_column("Symbol", style="green")
        gap_table.add_column("Exit Reason", style="magenta")
        gap_table.add_column("Trade Type", style="blue")
        gap_table.add_column("Alpaca Order ID", style="dim")

        for gap in gaps_detected:
            gap_table.add_row(
                gap["position_id"][:20] if gap["position_id"] else "N/A",
                gap["symbol"],
                str(gap["exit_reason"]),
                gap["trade_type"],
                str(gap["alpaca_order_id"])[:20] if gap["alpaca_order_id"] else "N/A",
            )

        console.print(gap_table)
    else:
        console.print(
            "[bold green]✅ No gaps detected (all closed positions have corresponding sell orders)[/bold green]"
        )

        # But warn if there are no sell orders at all
        if len(sell_orders) == 0 and len(closed_positions) > 0:
            console.print(
                "\n[bold yellow]⚠️  WARNING: Zero sell orders found in Alpaca but closed positions exist![/bold yellow]"
            )
            console.print("[dim]This could indicate:")
            console.print("  1. All exits were THEORETICAL trades (expected)")
            console.print("  2. Exit orders are not being submitted (BUG)")
            console.print("  3. Orders were placed on a different account[/dim]")

    # ======================================================================
    # SECTION 5: Summary
    # ======================================================================
    console.print("\n[bold cyan]📋 Summary[/bold cyan]")
    console.print(f"  - Exited Signals: {len(exited_signals)}")
    console.print(f"  - Total Positions: {len(all_positions)}")
    console.print(f"  - Closed Positions: {len(closed_positions)}")
    console.print(f"  - Alpaca BUY Orders: {len(buy_orders)}")
    console.print(f"  - Alpaca SELL Orders: {len(sell_orders)}")
    console.print(f"  - Exit Gaps Found: {len(gaps_detected)}")

    return {
        "exited_signals": len(exited_signals),
        "closed_positions": len(closed_positions),
        "buy_orders": len(buy_orders),
        "sell_orders": len(sell_orders),
        "gaps": len(gaps_detected),
        "gap_details": gaps_detected,
    }


def main():
    """Main entry point."""
    console = Console()

    settings = load_settings()
    if settings is None:
        sys.exit(1)

    try:
        results = analyze_exit_gap(console, settings)
        print("\n")

        # Return non-zero if gaps found
        if results["gaps"] > 0:
            sys.exit(1)
        sys.exit(0)

    except Exception as e:
        console.print(f"\n[bold red]❌ Analysis failed: {e}[/bold red]")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
