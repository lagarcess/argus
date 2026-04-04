from enum import Enum


class ReconciliationErrors(str, Enum):
    """Enumeration of critical reconciliation error message templates."""

    ZOMBIE_EXIT_GAP = (
        "CRITICAL SYNC ISSUE: {symbol} is OPEN in DB but MISSING in Alpaca. "
        "No matching exit order found."
    )
    ORPHAN_POSITION = "ORPHAN: {symbol}"
    REVERSE_ORPHAN = "REVERSE_ORPHAN: {symbol}"
