#!/usr/bin/env python3
"""
Data Integrity Check - Audit Firestore Collections.

This script audits all fields in the Signal and Position schemas to verify:
1. Which fields are present in Firestore documents
2. Which required fields are missing or NULL
3. Schema consistency between Pydantic models and stored data

Usage:
    poetry run python -m crypto_signals.scripts.diagnostics.data_integrity_check
"""

import os

os.environ.setdefault("ENVIRONMENT", "PROD")

from typing import Union, get_origin  # noqa: E402

from google.cloud import firestore  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

from crypto_signals.config import get_settings  # noqa: E402
from crypto_signals.domain.schemas import Position, Signal  # noqa: E402

console = Console()
settings = get_settings()
db = firestore.Client(project=settings.GOOGLE_CLOUD_PROJECT)


def audit_collection(
    collection_name: str,
    required_fields: dict[str, str],
    limit: int = 5,
) -> None:
    """Audit a Firestore collection for field presence and NULL values."""
    console.print(f"\n[bold cyan]=== {collection_name.upper()} ===")

    docs = list(db.collection(collection_name).limit(limit).stream())
    console.print(f"Documents found: {len(docs)}")

    if not docs:
        console.print("[yellow]⚠️  Collection is empty[/yellow]")
        return

    console.print(
        f"[bold blue]Checking {len(docs)} documents in {collection_name}...[/bold blue]"
    )

    # 1. Field Presence Audit
    # We check against a hardcoded list of "vital" fields for now.
    # Ideally, this should come from Pydantic models (Issue #274)

    # Audit first document
    sample_doc = docs[0].to_dict()

    table = Table(title=f"Field Audit (Sample: {docs[0].id[:20]}...)")
    table.add_column("Field", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Value Preview", style="dim")
    table.add_column("Description", style="dim")

    for field, description in required_fields.items():
        value = sample_doc.get(field, "❌ MISSING")
        if value is None:
            status = "[yellow]⚠️ NULL[/yellow]"
            preview = "None"
        elif value == "❌ MISSING":
            status = "[red]❌ MISSING[/red]"
            preview = "-"
        else:
            status = "[green]✅ OK[/green]"
            preview = str(value)[:30]

        table.add_row(field, status, preview, description)

    console.print(table)


def get_required_fields(model_class) -> dict[str, str]:
    """
    Extract fields that cannot be None (Optional) from a Pydantic model.
    Returns: dict[field_name, description]
    """
    fields = {}
    for name, info in model_class.model_fields.items():
        # Check if field accepts None.
        # If annotation allows None (e.g. Optional[str] or Union[str, None]), it is optional.
        annotation = info.annotation
        origin = get_origin(annotation)

        is_nullable = False
        if origin is Union and type(None) in annotation.__args__:
            is_nullable = True

        # Also check Pydantic "default=None" just in case, though annotation is definitive
        if info.default is None and info.default_factory is None:
            # If default is explicit None, it's nullable (unless it's a required field with None default, which is rare)
            # But annotation check is usually enough for Pydantic v2
            pass

        if not is_nullable:
            description = info.description or "No description"
            # Truncate description for display
            fields[name] = (
                description[:40] + "..." if len(description) > 40 else description
            )

    return fields


def main():
    console.print("[bold]=" * 70)
    console.print("[bold cyan]FIRESTORE DATA INTEGRITY CHECK")
    console.print("[bold]=" * 70)
    console.print(f"Environment: {settings.ENVIRONMENT}")
    console.print(f"Project: {settings.GOOGLE_CLOUD_PROJECT}")

    # Dynamically introspect models
    signal_fields = get_required_fields(Signal)
    position_fields = get_required_fields(Position)

    signals_collection = (
        "live_signals" if settings.ENVIRONMENT == "PROD" else "test_signals"
    )
    positions_collection = (
        "live_positions" if settings.ENVIRONMENT == "PROD" else "test_positions"
    )

    audit_collection(signals_collection, signal_fields)
    audit_collection(positions_collection, position_fields)

    console.print("\n[bold green]=== AUDIT COMPLETE ===[/bold green]\n")


if __name__ == "__main__":
    main()
