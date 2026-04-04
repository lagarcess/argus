#!/usr/bin/env python3
"""
Purge Signal Collection - Delete all signals from Firestore.

This script is a destructive operation that deletes all documents
from the signals collection. Use with caution!

Safety:
- Respects ENVIRONMENT setting (PROD uses live_signals, DEV uses test_signals)
- Confirms count before deletion
- Deletes in batches to avoid timeouts

Usage:
    poetry run python -m crypto_signals.scripts.maintenance.purge_signals
"""

import os

os.environ.setdefault("ENVIRONMENT", "PROD")

from google.cloud import firestore  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.prompt import Confirm  # noqa: E402

from crypto_signals.config import get_settings  # noqa: E402

console = Console()
settings = get_settings()
db = firestore.Client(project=settings.GOOGLE_CLOUD_PROJECT)


def purge_signals(dry_run: bool = False) -> int:
    """
    Delete all signals from the signals collection.

    Args:
        dry_run: If True, only count documents without deleting.

    Returns:
        Number of documents deleted (or would be deleted in dry_run).
    """
    if settings.ENVIRONMENT == "PROD":
        console.print(
            "[bold red]❌ Purge scripts are disabled in PROD environment for safety.[/bold red]"
        )
        return 0

    collection_name = "test_signals"

    console.print(f"[bold cyan]=== PURGE {collection_name.upper()} ===[/bold cyan]")
    console.print(f"Environment: {settings.ENVIRONMENT}")
    console.print(f"Project: {settings.GOOGLE_CLOUD_PROJECT}")

    # Count documents
    signals = list(db.collection(collection_name).stream())
    count = len(signals)

    console.print(f"\nFound [bold]{count}[/bold] signals to delete")

    if count == 0:
        console.print("[green]✅ Collection is already empty[/green]")
        return 0

    if dry_run:
        console.print("[yellow]DRY RUN - No documents deleted[/yellow]")
        return count

    if not Confirm.ask(f"Delete all {count} signals from {collection_name}?"):
        console.print("Cancelled.")
        return 0

    # Delete in batches
    batch_size = 100
    deleted = 0
    batch = db.batch()

    for i, doc in enumerate(signals):
        batch.delete(doc.reference)
        deleted += 1

        if (i + 1) % batch_size == 0:
            batch.commit()
            console.print(f"Deleted {deleted}/{count}...")
            batch = db.batch()

    # Commit remaining
    if deleted % batch_size != 0:
        batch.commit()

    console.print(f"\n[bold green]✅ Deleted {deleted} signals[/bold green]")
    return deleted


def main():
    purge_signals(dry_run=False)


if __name__ == "__main__":
    main()
