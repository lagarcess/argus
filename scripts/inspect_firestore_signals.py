#!/usr/bin/env python3
"""
Firestore Signals Inspection Script.

This script inspects the live_signals collection in Firestore to identify
legacy documents that may be missing required fields (asset_class, entry_price).
Use this to diagnose "poison" records before enabling cleanup-on-failure.
"""

import sys
from collections import Counter

import typer
from crypto_signals.config import get_settings
from crypto_signals.observability import configure_logging, console
from crypto_signals.secrets_manager import init_secrets
from google.cloud import firestore
from loguru import logger
from rich.panel import Panel
from rich.table import Table

# Initialize Typer app
app = typer.Typer(help="Inspect and optionally purge invalid Firestore signals")

# Required fields for Signal model validation
REQUIRED_FIELDS = {
    "signal_id",
    "ds",
    "strategy_id",
    "symbol",
    "asset_class",
    "entry_price",
    "pattern_name",
    "suggested_stop",
    "created_at",
}


@app.command()
def main(
    purge: bool = typer.Option(
        False, "--purge", help="Purge poison signals found during inspection"
    ),
):
    """Inspect all documents in live_signals collection."""
    # Configure colorful logging
    configure_logging(level="INFO")

    logger.info("Starting Firestore signals inspection...")

    # Initialize secrets
    if not init_secrets():
        logger.critical("Failed to load required secrets. Exiting.")
        sys.exit(1)

    try:
        # Initialize Firestore client
        settings = get_settings()
        db = firestore.Client(project=settings.GOOGLE_CLOUD_PROJECT)
        collection_name = "live_signals"

        with console.status(f"[bold cyan]Fetching documents from '{collection_name}'..."):
            docs = list(db.collection(collection_name).stream())

        total_count = len(docs)

        if total_count == 0:
            console.print(
                Panel(
                    "[yellow]Collection is empty. No documents to inspect.[/yellow]",
                    title="Inspection Result",
                )
            )
            sys.exit(0)

        # Analyze documents
        missing_fields_counter = Counter()
        poison_docs = []

        with console.status("[bold cyan]Analyzing documents..."):
            for doc in docs:
                data = doc.to_dict()
                doc_fields = set(data.keys())
                missing = REQUIRED_FIELDS - doc_fields

                if missing:
                    poison_docs.append({"id": doc.id, "missing": missing})
                    for field in missing:
                        missing_fields_counter[field] += 1

        # Calculate statistics
        valid_count = total_count - len(poison_docs)

        # Display Summary Table
        summary_table = Table(
            title="📊 INSPECTION SUMMARY",
            title_style="bold cyan",
            show_header=True,
            header_style="bold magenta",
        )
        summary_table.add_column("Metric", style="cyan", width=30)
        summary_table.add_column("Value", justify="right", style="green", width=15)

        summary_table.add_row("Total Documents", str(total_count))
        summary_table.add_row("Valid Documents", f"[green]{valid_count}[/green]")
        summary_table.add_row(
            "Poison Documents",
            f"[red]{len(poison_docs)}[/red]" if poison_docs else "[green]0[/green]",
        )

        console.print("\n")
        console.print(summary_table)

        # Display Missing Fields Breakdown
        if missing_fields_counter:
            field_table = Table(title="📉 Missing Fields Breakdown", style="yellow")
            field_table.add_column("Field Name", style="yellow")
            field_table.add_column("Count", justify="right", style="white")

            for field, count in missing_fields_counter.most_common():
                field_table.add_row(field, str(count))

            console.print("\n")
            console.print(field_table)

        # Display Report
        if poison_docs:
            poison_table = Table(
                title="⚠️ POISON DOCUMENTS DETECTED",
                title_style="bold red",
                border_style="red",
            )
            poison_table.add_column("Document ID", style="cyan", width=40)
            poison_table.add_column("Missing Fields", style="red")

            for doc_info in poison_docs:
                poison_table.add_row(
                    doc_info["id"], str(sorted(list(doc_info["missing"])))
                )

            console.print("\n")
            console.print(poison_table)

            if purge:
                console.print("\n")
                with console.status("[bold red]Purging poison signals..."):
                    batch = db.batch()
                    count = 0
                    for doc_info in poison_docs:
                        doc_ref = db.collection(collection_name).document(doc_info["id"])
                        batch.delete(doc_ref)
                        count += 1
                        if count % 400 == 0:
                            batch.commit()
                            batch = db.batch()
                    if count % 400 != 0:
                        batch.commit()

                console.print(
                    Panel(
                        f"[bold green]Successfully purged {count} poison signals.[/bold green]\n"
                        "The database is now hardened and healthy.",
                        title="✅ PURGE COMPLETE",
                        border_style="green",
                    )
                )
                sys.exit(0)
            else:
                console.print("\n")
                console.print(
                    Panel(
                        f"[bold red]{len(poison_docs)} Critical Validation Errors Detected[/bold red]\n\n"
                        "These documents will cause runtime failures.\n"
                        "To fix this, run with [bold white]--purge[/bold white] to auto-delete these records.\n"
                        "Alternatively, ensure [bold white]CLEANUP_ON_FAILURE=True[/bold white] in config.",
                        title="❌ ACTION REQUIRED",
                        border_style="red",
                    )
                )
                sys.exit(1)
        else:
            console.print("\n")
            console.print(
                Panel(
                    "[bold green]All documents are valid.[/bold green]\n"
                    "No cleanup required.",
                    title="✅ INSPECTION PASSED",
                    border_style="green",
                )
            )
            sys.exit(0)

    except Exception as e:
        logger.critical(f"Inspection failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    app()
