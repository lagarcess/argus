"""Maintenance scripts for data cleanup and healing operations.

Usage:
    poetry run python -m crypto_signals.scripts.maintenance.<script_name>

Available scripts:
    cleanup_legacy_gaps  - Mark legacy gaps as resolved (Issue #139)
    fix_reverse_orphans  - Close Alpaca positions for DB-closed records
    migrate_schema       - Migrate Firestore document schemas
    purge_positions      - Delete all positions from Firestore
    purge_signals        - Delete all signals from Firestore
    reset_tables         - Reset BigQuery tables
    resurrect_positions  - Reopen false-closed positions

WARNING: These scripts modify data. Always verify environment before running.
"""
