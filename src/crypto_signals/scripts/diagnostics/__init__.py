"""Diagnostic scripts for system health and forensic analysis.

Usage:
    poetry run python -m crypto_signals.scripts.diagnostics.<script_name>

Available scripts:
    account_status       - Alpaca account balance and positions
    book_balancing       - Compare Alpaca vs Firestore positions
    check_alpaca_positions - Quick check of Alpaca vs DB sync
    data_integrity_check - Audit Firestore field presence/NULLs
    forensic_analysis    - Deep dive into exit gaps and orphans
    forensic_details     - Quick forensic details dump
    health_check         - Full system health verification
    schema_audit         - Analyze Pydantic model definitions
    state_analysis       - Firestore collection state summary
    verify_order         - Verify specific order execution
"""

from crypto_signals.scripts.diagnostics.account_status import get_account_summary
from crypto_signals.scripts.diagnostics.forensic_analysis import analyze_exit_gap
from crypto_signals.scripts.diagnostics.health_check import run_all_verifications
from crypto_signals.scripts.diagnostics.state_analysis import analyze_firestore_state

__all__ = [
    "analyze_exit_gap",
    "get_account_summary",
    "analyze_firestore_state",
    "run_all_verifications",
]
