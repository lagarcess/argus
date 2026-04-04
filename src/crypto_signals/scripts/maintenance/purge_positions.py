#!/usr/bin/env python3
"""
Purge Positions Collection - Delete all positions from Firestore.

This script is a destructive operation that deletes all documents
from the positions collection. Use with caution!

Safety:
- Respects ENVIRONMENT setting (PROD uses live_positions, DEV uses test_positions)
- Confirms count before deletion
- Deletes in batches to avoid timeouts

Usage:
    poetry run python -m crypto_signals.scripts.maintenance.purge_positions
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


def purge_positions(dry_run: bool = False) -> int:
    """
    Delete all positions from the positions collection.

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

    collection_name = "test_positions"

    console.print(f"[bold cyan]=== PURGE {collection_name.upper()} ===[/bold cyan]")
    console.print(f"Environment: {settings.ENVIRONMENT}")
    console.print(f"Project: {settings.GOOGLE_CLOUD_PROJECT}")

    # Count documents
    positions = list(db.collection(collection_name).stream())
    count = len(positions)

    console.print(f"\nFound [bold]{count}[/bold] positions to delete")

    if count == 0:
        console.print("[green]✅ Collection is already empty[/green]")
        return 0

    if dry_run:
        console.print("[yellow]DRY RUN - No documents deleted[/yellow]")
        return count

    if not Confirm.ask(f"Delete all {count} positions from {collection_name}?"):
        console.print("Cancelled.")
        return 0

    # Delete in batches
    batch_size = 100
    deleted = 0
    batch = db.batch()

    for i, doc in enumerate(positions):
        batch.delete(doc.reference)
        deleted += 1

        if (i + 1) % batch_size == 0:
            batch.commit()
            console.print(f"Deleted {deleted}/{count}...")
            batch = db.batch()

    # Commit remaining
    if deleted % batch_size != 0:
        batch.commit()

    console.print(f"\n[bold green]✅ Deleted {deleted} positions[/bold green]")
    return deleted


def main():
    purge_positions(dry_run=False)


if __name__ == "__main__":
    main()
