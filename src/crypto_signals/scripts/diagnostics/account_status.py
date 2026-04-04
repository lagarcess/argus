#!/usr/bin/env python3
"""
Account Status Diagnostic - Alpaca account summary and position check.

Usage:
    poetry run python -m crypto_signals.scripts.diagnostics.account_status

Output:
    Writes report to temp/reports/account_status.txt
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, cast

from alpaca.trading.models import Position, TradeAccount

# Ensure PROD environment for diagnostics
os.environ.setdefault("ENVIRONMENT", "PROD")  # noqa: E402


def get_account_summary() -> Dict[str, Any]:
    """Get Alpaca account summary and return as dict."""
    from alpaca.trading.client import TradingClient

    from crypto_signals.config import get_settings

    settings = get_settings()
    alpaca = TradingClient(
        api_key=settings.ALPACA_API_KEY,
        secret_key=settings.ALPACA_SECRET_KEY,
        paper=settings.is_paper_trading,
    )

    account = cast(TradeAccount, alpaca.get_account())
    positions = alpaca.get_all_positions()

    summary: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "account_status": str(account.status),
        "is_paper": settings.is_paper_trading,
        "cash": float(account.cash or 0.0),
        "portfolio_value": float(account.portfolio_value or 0.0),
        "equity": float(account.equity or 0.0),
        "buying_power": float(account.buying_power or 0.0),
        "last_equity": float(account.last_equity or 0.0),
        "open_positions_count": len(positions),
        "positions": [],
    }

    total_unrealized_pl = 0
    for pos in positions:
        if not isinstance(pos, Position):
            continue
        unrealized_pl = float(pos.unrealized_pl or 0)
        total_unrealized_pl += unrealized_pl
        summary["positions"].append(
            {
                "symbol": getattr(pos, "symbol", "UNKNOWN"),
                "qty": float(pos.qty or 0),
                "avg_entry_price": float(pos.avg_entry_price or 0),
                "current_price": float(pos.current_price or 0),
                "market_value": float(pos.market_value or 0),
                "unrealized_pl": unrealized_pl,
                "unrealized_plpc": float(getattr(pos, "unrealized_plpc", 0) or 0) * 100,
            }
        )

    summary["total_unrealized_pl"] = total_unrealized_pl

    return summary


def write_report(summary: Dict[str, Any], output_path: Path) -> None:
    """Write human-readable report to file."""
    with open(output_path, "w") as f:
        f.write("=" * 70 + "\n")
        f.write("ALPACA ACCOUNT STATUS REPORT\n")
        f.write(f"Generated: {summary['timestamp']}\n")
        f.write("=" * 70 + "\n\n")

        f.write(f"Account Type: {'PAPER' if summary['is_paper'] else 'LIVE'}\n")
        f.write(f"Status: {summary['account_status']}\n\n")

        f.write("--- BALANCE ---\n")
        f.write(f"Cash: ${summary['cash']:,.2f}\n")
        f.write(f"Portfolio Value: ${summary['portfolio_value']:,.2f}\n")
        f.write(f"Equity: ${summary['equity']:,.2f}\n")
        f.write(f"Buying Power: ${summary['buying_power']:,.2f}\n")
        f.write(f"Last Equity: ${summary['last_equity']:,.2f}\n\n")

        f.write("--- POSITIONS ---\n")
        f.write(f"Open Positions: {summary['open_positions_count']}\n")
        f.write(f"Total Unrealized P/L: ${summary['total_unrealized_pl']:,.2f}\n\n")

        if summary["positions"]:
            for pos in summary["positions"]:
                pl_sign = "+" if pos["unrealized_pl"] >= 0 else ""
                f.write(f"{pos['symbol']}\n")
                f.write(f"  Qty: {pos['qty']:.6f}\n")
                f.write(f"  Entry: ${pos['avg_entry_price']:.4f}\n")
                f.write(f"  Current: ${pos['current_price']:.4f}\n")
                f.write(f"  Market Value: ${pos['market_value']:.2f}\n")
                f.write(
                    f"  P/L: {pl_sign}${pos['unrealized_pl']:.2f} ({pl_sign}{pos['unrealized_plpc']:.2f}%)\n\n"
                )
        else:
            f.write("  (No open positions)\n")


def main():
    """Run account status diagnostic."""
    print("Running Account Status Diagnostic...")

    try:
        summary = get_account_summary()

        # Ensure output directory exists
        output_dir = Path("temp/reports")
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / "account_status.txt"
        write_report(summary, output_path)

        print(f"✅ Report written to: {output_path}")
        print(f"   Portfolio Value: ${summary['portfolio_value']:,.2f}")
        print(f"   Open Positions: {summary['open_positions_count']}")
        print(f"   Unrealized P/L: ${summary['total_unrealized_pl']:,.2f}")

        return summary

    except Exception as e:
        print(f"❌ Account status check failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
