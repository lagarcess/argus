#!/usr/bin/env python3
"""
Script to purge recent signals from live_signals (cleanup accidental test runs).
"""

import sys
from datetime import datetime, timedelta, timezone

import typer
from crypto_signals.config import get_settings
from crypto_signals.secrets_manager import init_secrets
from google.cloud import firestore
from loguru import logger
from rich.console import Console
from rich.prompt import Confirm
from rich.table import Table

console = Console()
app = typer.Typer()


@app.command()
def main(
    hours: int = typer.Option(24, help="Lookback hours to find recent signals"),
    force: bool = typer.Option(
        False, "--force", "-f", help="Force deletion without confirmation"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Only list signals, do not delete"
    ),
):
    """Purge recent signals from live_signals collection."""
    if not init_secrets():
        logger.error("Failed to load secrets")
        sys.exit(1)

    settings = get_settings()
    # Force connection to live_signals regardless of current env settings
    # (Since we are cleaning up PROD from a local env)
    db = firestore.Client(project=settings.GOOGLE_CLOUD_PROJECT)
    collection_name = "live_signals"

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    console.print(
        f"[bold cyan]Scanning '{collection_name}' for signals created after {cutoff.isoformat()}...[/bold cyan]"
    )

    # Primary query: created_at
    query = db.collection(collection_name).where(
        filter=firestore.FieldFilter("created_at", ">=", cutoff)
    )
    docs = list(query.stream())

    # Fallback: Query by 'ds' string (today and yesterday)
    # This catches signals where created_at might be missing or date-based logic differs
    if not docs:
        console.print(
            "[yellow]No signals found by 'created_at'. Checking 'ds' field...[/yellow]"
        )
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

        # Check today
        query_ds = db.collection(collection_name).where(
            filter=firestore.FieldFilter("ds", "in", [today, yesterday])
        )
        docs = list(query_ds.stream())

    # Fallback: If created_at is missing (legacy), validation might fail, or we check 'ds'
    # But checking 'ds' via query string comparison is risky.
    # Let's verify results.

    if not docs:
        console.print("[green]No recent signals found.[/green]")
        return

    table = Table(title=f"Recent Signals (Last {hours}h)")
    table.add_column("ID", style="cyan")
    table.add_column("Symbol", style="yellow")
    table.add_column("Created At", style="green")

    for doc in docs:
        data = doc.to_dict()
        table.add_row(doc.id, data.get("symbol"), str(data.get("created_at")))

    console.print(table)

    if dry_run:
        console.print("[yellow]Dry run complete. No data deleted.[/yellow]")
        return

    if not force:
        if not Confirm.ask(f"Delete these {len(docs)} signals from PROD?"):
            console.print("[red]Aborted.[/red]")
            return

    with console.status(f"[bold red]Deleting {len(docs)} signals...[/bold red]"):
        batch = db.batch()
        count = 0
        batch_size = 0
        for doc in docs:
            batch.delete(doc.reference)
            count += 1
            batch_size += 1
            if batch_size >= 400:
                batch.commit()
                batch = db.batch()
                batch_size = 0

        if batch_size > 0:
            batch.commit()

    console.print(f"[bold green]Successfully deleted {count} documents.[/bold green]")


if __name__ == "__main__":
    app()
