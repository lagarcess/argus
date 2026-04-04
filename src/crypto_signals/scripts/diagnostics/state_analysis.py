#!/usr/bin/env python3
"""
State Analysis Diagnostic - Firestore state analysis before/after runs.

Usage:
    poetry run python -m crypto_signals.scripts.diagnostics.state_analysis

Output:
    Writes report to temp/reports/state_analysis.txt
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

# Ensure PROD environment for diagnostics
os.environ.setdefault("ENVIRONMENT", "PROD")  # noqa: E402


def analyze_firestore_state() -> Dict[str, Any]:
    """Analyze current Firestore state and return summary."""
    from google.cloud import firestore

    from crypto_signals.config import get_settings

    settings = get_settings()
    db = firestore.Client(project=settings.GOOGLE_CLOUD_PROJECT)

    # Determine collections based on environment
    signals_coll = "live_signals" if settings.ENVIRONMENT == "PROD" else "test_signals"
    positions_coll = (
        "live_positions" if settings.ENVIRONMENT == "PROD" else "test_positions"
    )

    summary: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": settings.ENVIRONMENT,
        "signals_collection": signals_coll,
        "positions_collection": positions_coll,
        "positions": {
            "OPEN": 0,
            "CLOSED": 0,
        },
        "signals": {
            "WAITING": 0,
            "TP1_HIT": 0,
            "TP2_HIT": 0,
            "TP3_HIT": 0,
            "INVALIDATED": 0,
            "EXPIRED": 0,
        },
        "active_signals": [],
        "open_positions": [],
    }

    # Count positions
    for status in ["OPEN", "CLOSED"]:
        docs = list(db.collection(positions_coll).where("status", "==", status).stream())
        summary["positions"][status] = len(docs)

        if status == "OPEN":
            for doc in docs:
                data = doc.to_dict()
                summary["open_positions"].append(
                    {
                        "position_id": data.get("position_id", "")[:12],
                        "symbol": data.get("symbol"),
                        "side": data.get("side"),
                        "qty": data.get("qty"),
                    }
                )

    # Count signals
    for status in summary["signals"].keys():
        docs = list(db.collection(signals_coll).where("status", "==", status).stream())
        summary["signals"][status] = len(docs)

        if status in ["WAITING", "TP1_HIT", "TP2_HIT"]:
            for doc in docs:
                data = doc.to_dict()
                summary["active_signals"].append(
                    {
                        "signal_id": data.get("signal_id", "")[:12],
                        "symbol": data.get("symbol"),
                        "status": data.get("status"),
                        "pattern": data.get("pattern_name"),
                    }
                )

    return summary


def write_report(summary: Dict[str, Any], output_path: Path) -> None:
    """Write human-readable report to file."""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("FIRESTORE STATE ANALYSIS REPORT\n")
        f.write(f"Generated: {summary['timestamp']}\n")
        f.write("=" * 70 + "\n\n")

        f.write(f"Environment: {summary['environment']}\n")
        f.write(f"Signals Collection: {summary['signals_collection']}\n")
        f.write(f"Positions Collection: {summary['positions_collection']}\n\n")

        f.write("--- POSITIONS ---\n")
        for status, count in summary["positions"].items():
            f.write(f"  {status}: {count}\n")
        f.write("\n")

        if summary["open_positions"]:
            f.write("Open positions to sync:\n")
            for pos in summary["open_positions"]:
                f.write(
                    f"  {pos['symbol']}: {pos['side']} x{pos['qty']} ({pos['position_id']}...)\n"
                )
            f.write("\n")

        f.write("--- SIGNALS ---\n")
        for status, count in summary["signals"].items():
            f.write(f"  {status}: {count}\n")
        f.write("\n")

        active_count = len(summary["active_signals"])
        f.write(f"--- ACTIVE SIGNALS ({active_count}) ---\n")
        f.write("(These will be checked for exits on next run)\n\n")

        if summary["active_signals"]:
            for sig in summary["active_signals"]:
                f.write(f"  {sig['symbol']}: {sig['status']} - {sig['pattern']}\n")
        else:
            f.write("  (No active signals)\n")

        f.write("\n" + "=" * 70 + "\n")
        f.write("WHAT HAPPENS ON NEXT RUN\n")
        f.write("=" * 70 + "\n\n")

        open_pos = summary["positions"]["OPEN"]
        active_sigs = len(summary["active_signals"])

        if open_pos > 0:
            f.write(
                f"1. Position Sync: {open_pos} OPEN positions will be synced with Alpaca\n"
            )
            f.write("   - If position not found on Alpaca -> marked MANUAL_EXIT\n")
            f.write("   - If position still open -> status stays OPEN\n\n")
        else:
            f.write("1. Position Sync: No OPEN positions to sync\n\n")

        if active_sigs > 0:
            f.write(f"2. Exit Checks: {active_sigs} active signals will be evaluated\n")
            f.write("   - check_exits() runs on each WAITING/TP1/TP2 signal\n")
            f.write("   - If TP/SL conditions met -> status updates\n")
            f.write("   - [!] Exit order bug (Issue #139) still applies!\n\n")
        else:
            f.write("2. Exit Checks: No active signals to evaluate\n\n")

        f.write("3. New Signal Generation: Pattern detection runs normally\n")


def main():
    """Run state analysis diagnostic."""
    print("Running Firestore State Analysis...")

    try:
        summary = analyze_firestore_state()

        # Ensure output directory exists
        output_dir = Path("temp/reports")
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / "state_analysis.txt"
        write_report(summary, output_path)

        print(f"✅ Report written to: {output_path}")
        print(f"   Environment: {summary['environment']}")
        print(f"   OPEN Positions: {summary['positions']['OPEN']}")
        print(f"   Active Signals: {len(summary['active_signals'])}")

        return summary

    except Exception as e:
        print(f"❌ State analysis failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
