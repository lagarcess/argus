"""
Synchronization script for documentation and DBML.
"""

import re
import sys
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Type, Union, get_args, get_origin

import typer
from pydantic import BaseModel
from rich.console import Console

from crypto_signals.domain.schemas import (
    AccountSnapshot,
    FactRejectedSignal,
    Position,
    Signal,
    StrategyConfig,
    TradeExecution,
)

app = typer.Typer()
console = Console()

# =============================================================================
# CONFIGURATION
# =============================================================================


class TableConfig(BaseModel):
    model: Type[BaseModel]
    table_name: str
    header_color: str
    pk_fields: List[str]
    refs: Dict[
        str, str
    ] = {}  # field_name -> ref definition (e.g. "> dim_strategies.strategy_id")
    table_note: str = ""


CONFIG_MAP = {
    "dim_strategies": TableConfig(
        model=StrategyConfig,
        table_name="dim_strategies",
        header_color="#ff9900",
        pk_fields=["strategy_id"],
        table_note="Config table. Defines trading rules.",
    ),
    "live_signals": TableConfig(
        model=Signal,
        table_name="live_signals",
        header_color="#e06666",
        pk_fields=["signal_id"],
        refs={
            "strategy_id": "> dim_strategies.strategy_id",
        },
        table_note="Ephemeral opportunities.",
    ),
    "live_positions": TableConfig(
        model=Position,
        table_name="live_positions",
        header_color="#e06666",
        pk_fields=["position_id"],
        refs={
            "signal_id": "- live_signals.signal_id",
        },
        table_note="Active Trades (Operational State).",
    ),
    "fact_trades": TableConfig(
        model=TradeExecution,
        table_name="fact_trades",
        header_color="#6d9eeb",
        pk_fields=["ds", "trade_id"],
        refs={
            "strategy_id": "> dim_strategies.strategy_id",
        },
        table_note="Immutable Ledger of all CLOSED trades.",
    ),
    "snapshot_accounts": TableConfig(
        model=AccountSnapshot,
        table_name="snapshot_accounts",
        header_color="#6d9eeb",
        pk_fields=["ds", "account_id"],
        table_note="Daily Account state snapshots.",
    ),
    "fact_rejected_signals": TableConfig(
        model=FactRejectedSignal,
        table_name="fact_rejected_signals",
        header_color="#6d9eeb",
        pk_fields=["ds", "signal_id"],
        table_note="Analytical archival of rejected opportunities.",
    ),
}

# Mapping for Markdown generation (Model -> Block Name in MD)
MD_MAPPING = {
    "AccountSnapshot": AccountSnapshot,
    "TradeExecution": TradeExecution,
    "Signal": Signal,
}

# =============================================================================
# GENERATORS
# =============================================================================


class MarkdownGenerator:
    def generate_table(self, model: Type[BaseModel]) -> str:
        lines = ["| Field | Type | Description |", "| :--- | :--- | :--- |"]

        for name, field in model.model_fields.items():
            type_str = self._format_type(field.annotation)
            desc = field.description or ""
            # Escape pipes in description
            desc = desc.replace("|", "\\|").replace("\n", " ")
            lines.append(f"| `{name}` | `{type_str}` | {desc} |")

        return "\n".join(lines)

    def _format_type(self, type_: Any) -> str:
        # Simple type formatting
        if type_ is None:
            return "None"

        origin = get_origin(type_)
        args = get_args(type_)

        if origin is Union:
            # Handle Optional (Union[T, None])
            non_none = [t for t in args if t is not type(None)]
            if len(non_none) == 1:
                return self._format_type(non_none[0])
            return " | ".join(self._format_type(t) for t in non_none)

        if origin is list or origin is List:
            return f"List[{self._format_type(args[0])}]"

        if origin is dict or origin is Dict:
            return "Dict"

        if isinstance(type_, type):
            if issubclass(type_, Enum):
                return "str"  # Enums are strings in this system
            if type_ is datetime:
                return "datetime"
            if type_ is date:
                return "date"
            if type_ is str:
                return "str"
            if type_ is int:
                return "int"
            if type_ is float:
                return "float"
            if type_ is bool:
                return "bool"
            return type_.__name__

        return str(type_)


class DBMLGenerator:
    def generate_table_block(self, config: TableConfig) -> str:
        lines = []
        # Header
        lines.append(f"Table {config.table_name} [headercolor: {config.header_color}] {{")

        # Fields
        for name, field in config.model.model_fields.items():
            dbml_type = self._map_to_dbml_type(field.annotation)
            metadata = []

            if name in config.pk_fields:
                metadata.append("pk")

            if name in config.refs:
                metadata.append(f"ref: {config.refs[name]}")

            note = field.description
            if note:
                # Clean up note for DBML single line string
                note = note.replace("'", "").replace("\n", " ")
                if len(note) > 50:
                    note = note[:47] + "..."
                metadata.append(f"note: '{note}'")

            meta_str = ""
            if metadata:
                meta_str = f" [{', '.join(metadata)}]"

            lines.append(f"  {name} {dbml_type}{meta_str}")

        # Table Note
        if config.table_note:
            lines.append(f"  Note: '{config.table_note}'")

        lines.append("}")
        return "\n".join(lines)

    def _map_to_dbml_type(self, type_: Any) -> str:
        origin = get_origin(type_)
        args = get_args(type_)

        if origin is Union:
            non_none = [t for t in args if t is not type(None)]
            if len(non_none) == 1:
                return self._map_to_dbml_type(non_none[0])
            return "varchar"  # Fallback

        if origin is list or origin is List:
            return "list"

        if origin is dict or origin is Dict:
            return "json"

        if isinstance(type_, type):
            if issubclass(type_, Enum):
                return "enum"
            if type_ is datetime:
                return "timestamp"
            if type_ is date:
                return "date"
            if type_ is str:
                return "varchar"
            if type_ is int:
                return "int"
            if type_ is float:
                return "float"
            if type_ is bool:
                return "boolean"
            if type_.__name__ == "UUID":
                return "uuid"

        # Basic type name fallback
        type_name = str(type_).lower()
        if "uuid" in type_name:
            return "uuid"
        return "varchar"


# =============================================================================
# MAIN APP
# =============================================================================


@app.command()
def sync_docs(
    check: bool = typer.Option(
        False,
        "--check",
        help="Check if documentation is up-to-date without modifying files. Returns exit code 1 if changes are needed.",
    ),
):
    """
    Synchronize documentation and DBML with Pydantic schemas.
    """
    root_dir = Path.cwd()
    docs_dir = root_dir / "docs"

    any_changes = False

    # 1. Update Handbook (Markdown)
    handbook_path = docs_dir / "data" / "00_data_handbook.md"
    if handbook_path.exists():
        if not check:
            console.print(f"Updating {handbook_path}...")
        else:
            console.print(f"Checking {handbook_path}...")

        changed = _update_file_with_markers(
            handbook_path,
            MD_MAPPING,
            MarkdownGenerator(),
            marker_fmt="<!-- GENERATED: {} -->",
            end_marker="<!-- END_GENERATED -->",
            check_only=check,
        )
        if changed:
            any_changes = True
    else:
        console.print(f"[red]Handbook not found at {handbook_path}[/red]")
        sys.exit(1)

    # 2. Update DBML
    dbml_path = docs_dir / "architecture" / "current-schema.dbml"
    if dbml_path.exists():
        if not check:
            console.print(f"Updating {dbml_path}...")
        else:
            console.print(f"Checking {dbml_path}...")

        # For DBML, key is table name in CONFIG_MAP
        # We need a generator that takes the key and looks up config
        dbml_gen = DBMLGenerator()

        # Helper adapter to match signature
        class DBMLAdapter:
            def generate_table(self, key):
                if key in CONFIG_MAP:
                    return dbml_gen.generate_table_block(CONFIG_MAP[key])
                return ""

        changed = _update_file_with_markers(
            dbml_path,
            {k: k for k in CONFIG_MAP.keys()},  # Identity map, key passed to generator
            DBMLAdapter(),
            marker_fmt="// GENERATED: {}",
            end_marker="// END_GENERATED",
            check_only=check,
        )
        if changed:
            any_changes = True
    else:
        console.print(f"[red]DBML not found at {dbml_path}[/red]")
        sys.exit(1)

    if check:
        if any_changes:
            console.print(
                "[red]Documentation is out of sync. Please run 'poetry run sync-docs' to update.[/red]"
            )
            sys.exit(1)
        else:
            console.print("[green]Documentation is up-to-date.[/green]")
    else:
        console.print("[green]Documentation synchronization complete![/green]")


def _update_file_with_markers(
    filepath: Path,
    mapping: Dict[str, Any],
    generator: Any,
    marker_fmt: str,
    end_marker: str,
    check_only: bool = False,
) -> bool:
    content = filepath.read_text(encoding="utf-8")
    original_content = content

    for key, model_or_config_key in mapping.items():
        start_marker = marker_fmt.format(key)

        pattern = re.compile(
            re.escape(start_marker) + r"(.*?)" + re.escape(end_marker), re.DOTALL
        )

        if start_marker not in content:
            console.print(
                f"[yellow]Marker {start_marker} not found in {filepath.name}[/yellow]"
            )
            continue

        new_block_content = generator.generate_table(model_or_config_key)
        replacement = f"{start_marker}\n{new_block_content}\n{end_marker}"

        content = pattern.sub(replacement, content)

    if content != original_content:
        if check_only:
            return True
        filepath.write_text(content, encoding="utf-8")
        return True

    return False


if __name__ == "__main__":
    app()
