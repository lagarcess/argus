#!/usr/bin/env python3
"""
Schema Audit - Analyze Pydantic Model Field Definitions.

This script inspects Signal and Position Pydantic models to show:
1. All field names and their types
2. Which fields are required vs optional
3. Default values for optional fields
4. Guidance on when NULL is acceptable

Usage:
    poetry run python -m crypto_signals.scripts.diagnostics.schema_audit
"""

import os

os.environ.setdefault("ENVIRONMENT", "PROD")


from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

from crypto_signals.domain.schemas import Position, Signal  # noqa: E402

console = Console()


def audit_model(model_class, model_name: str) -> None:
    """Audit a Pydantic model's field definitions."""
    console.print(f"\n[bold cyan]=== {model_name} MODEL FIELDS ===")

    table = Table(title=f"{model_name} Schema")
    table.add_column("Field", style="cyan")
    table.add_column("Required?", style="bold")
    table.add_column("Default", style="dim")
    table.add_column("Description", style="dim", max_width=40)

    for field_name, field_info in model_class.model_fields.items():
        is_required = field_info.is_required()
        default = field_info.default
        description = field_info.description or "-"

        if is_required:
            status = "[red]REQUIRED[/red]"
            default_str = "-"
        else:
            status = "[green]optional[/green]"
            default_str = str(default)[:20] if default is not None else "None"

        # Truncate description
        if len(description) > 40:
            description = description[:37] + "..."

        table.add_row(field_name, status, default_str, description)

    console.print(table)


def print_null_guidance():
    """Print guidance on when NULL is acceptable."""
    console.print("\n[bold yellow]=== NULL FIELD GUIDANCE ===")

    console.print("""
[green]Signal Fields - NULL is OK:[/green]
  • take_profit_1/2/3      - Not all patterns define TPs
  • invalidation_price     - Only some patterns use this
  • exit_reason            - NULL until signal exits
  • discord_thread_id      - NULL until Discord notification
  • delete_at              - TTL is optional
  • pattern_duration_days  - NULL for patterns without tracking
  • structural_anchors     - NULL for non-structural patterns

[red]Signal Fields - NULL is a BUG:[/red]
  • entry_price            - NEVER NULL (required)
  • suggested_stop         - NEVER NULL (required)
  • signal_id, symbol      - NEVER NULL (required)
  • pattern_name, ds       - NEVER NULL (required)

[green]Position Fields - NULL is OK:[/green]
  • exit_* fields          - NULL until position closes
  • tp_order_id/sl_order_id - NULL until bracket fills
  • failed_reason          - NULL unless order failed
  • trailing_stop_final    - NULL until TP3 exit

[red]Position Fields - NULL is a BUG:[/red]
  • entry_fill_price       - Must have fill price
  • qty, side, status      - Core trading data
  • signal_id              - Must link to origin signal
""")


def main():
    console.print("[bold]=" * 70)
    console.print("[bold cyan]PYDANTIC SCHEMA AUDIT")
    console.print("[bold]=" * 70)

    audit_model(Signal, "Signal")
    audit_model(Position, "Position")
    print_null_guidance()

    console.print("\n[bold green]=== AUDIT COMPLETE ===[/bold green]\n")


if __name__ == "__main__":
    main()
