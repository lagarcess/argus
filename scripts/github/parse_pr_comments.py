"""
Parse and display GitHub PR comments from JSON dump.
Usage: python scripts/parse_pr_comments.py <json_file> [--output <output_file>]
"""

import json
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

app = typer.Typer()
console = Console()


def load_json(path: Path) -> list:
    """Load JSON handling encoding issues."""
    encodings = ["utf-8", "utf-16", "latin-1"]
    for encoding in encodings:
        try:
            with open(path, "r", encoding=encoding) as f:
                return json.load(f)
        except (UnicodeError, json.JSONDecodeError):
            continue
    console.print(f"[bold red]Failed to load JSON from {path}[/bold red]")
    sys.exit(1)


@app.command()
def main(
    input_file: Annotated[
        Path,
        typer.Argument(help="Path to the JSON file containing comments"),
    ],
    output_dir: Annotated[
        Path,
        typer.Option(
            help="Directory to save the readable output (default: temp/pr_comments)"
        ),
    ] = Path("temp/pr_comments"),
    unresolved_only: Annotated[
        bool,
        typer.Option(help="Show only unresolved conversations (if supported by dump)"),
    ] = False,
):
    """
    Parse GitHub API comment JSON dump and display/save readable report.
    """
    import re

    if not input_file.exists():
        console.print(f"[bold red]Input file not found: {input_file}[/bold red]")
        sys.exit(1)

    comments = load_json(input_file)

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{input_file.stem}_readable.txt"

    console.print(
        f"[bold blue]Parsing {len(comments)} comments from {input_file.name}...[/bold blue]"
    )

    report_lines = []

    # improved table layout
    table = Table(
        title=f"PR Comments: {input_file.name}",
        show_header=True,
        header_style="bold magenta",
        padding=(0, 1),
    )
    table.add_column("Prio", style="bold", width=8)
    table.add_column("File", style="cyan", overflow="fold", ratio=2)
    table.add_column("Lines", style="yellow", justify="right", width=12)
    table.add_column("User", style="green", width=15)
    table.add_column("Comment", style="white", ratio=3)

    for i, c in enumerate(comments):
        # Path & User
        path = c.get("path", "General")
        user = c.get("user", {}).get("login", "Unknown")
        url = c.get("html_url", "")

        # Line Range Logic
        # GitHub API usually gives 'line' (end) and 'start_line'. If start_line is null, it's a single line.
        end_line = c.get("line") or c.get("original_line") or "N/A"
        start_line = c.get("start_line") or c.get("original_start_line") or end_line

        if start_line == end_line or start_line == "N/A":
            line_str = f"{end_line}"
        else:
            line_str = f"{start_line}-{end_line}"

        # Body Cleaning & Priority Extraction
        raw_body = c.get("body", "")

        # Regex to find ![priority](.../high-priority.svg)
        # Matches content like ![high](...high-priority.svg) or ![medium](...)
        prio_match = re.search(
            r"!\[.*?\]\(.*?([a-z]+)-priority\.svg\)", raw_body, re.IGNORECASE
        )

        priority = "Normal"
        prio_color = "white"
        clean_body = raw_body

        if prio_match:
            prio_slug = prio_match.group(1).lower()
            if "high" in prio_slug:
                priority = "HIGH"
                prio_color = "red"
            elif "medium" in prio_slug:
                priority = "MED"
                prio_color = "yellow"
            elif "low" in prio_slug:
                priority = "LOW"
                prio_color = "blue"

            # Remove the image markdown from the body
            # We remove the whole match
            clean_body = raw_body.replace(prio_match.group(0), "").strip()

        # Add to Rich Table
        # Fold long paths, truncate very long comments for display
        short_body = clean_body.split("\n")[0][:80] + (
            "..." if len(clean_body) > 80 else ""
        )

        table.add_row(Text(priority, style=prio_color), path, line_str, user, short_body)

        # Add to Report File (Full Detail)
        report_lines.append("-" * 80)
        report_lines.append(f"Comment #{i+1} [{priority}]")
        report_lines.append(f"File:     {path}")
        report_lines.append(f"Lines:    {line_str}")
        report_lines.append(f"User:     {user}")
        report_lines.append(f"URL:      {url}")
        report_lines.append(f"Content:\n{clean_body}\n")

    # Display Table
    console.print(table)

    # Save Report
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    console.print(f"\n[bold green]Report saved to: {output_file}[/bold green]")

    # Summary for Agent
    console.print(
        Panel(
            f"Agents: Check {output_file} for full details.\n"
            f"Address HIGH priority items immediately.",
            title="Agent Instruction",
            border_style="yellow",
        )
    )


if __name__ == "__main__":
    app()
