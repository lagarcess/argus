"""
Post review comments to a GitHub PR.
Usage: python scripts/post_review.py <pr_number> <comments_json> [--approve/--request-changes]
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Annotated, Any, Dict, List

import typer
from rich.console import Console

app = typer.Typer()
console = Console()


def run_gh_command(args: List[str]) -> Dict[str, Any]:
    """Run a gh CLI command and return JSON output if available."""
    try:
        result = subprocess.run(
            ["gh"] + args,
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",  # Force UTF-8 for gh output
        )
        if result.stdout.strip():
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                return {"text": result.stdout}
        return {}
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]Error running gh command: {e.stderr}[/bold red]")
        sys.exit(1)


@app.command()
def main(
    pr_number: Annotated[int, typer.Argument(help="PR Number to review")],
    review_file: Annotated[
        Path, typer.Argument(help="JSON file containing review data (body, comments)")
    ],
    event: Annotated[
        str, typer.Option(help="Review event: APPROVE, REQUEST_CHANGES, or COMMENT")
    ] = "COMMENT",
):
    """
    Post a structured review to a PR using 'gh api'.

    Expected JSON Format:
    {
        "body": "General review summary...",
        "comments": [
            {
                "path": "src/file.py",
                "line": 10,
                "body": "Fix this..."
            }
        ]
    }
    """
    if not review_file.exists():
        console.print(f"[bold red]Review file not found: {review_file}[/bold red]")
        sys.exit(1)

    try:
        with open(review_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        console.print(f"[bold red]Failed to parse review JSON: {e}[/bold red]")
        sys.exit(1)
    except FileNotFoundError:
        console.print(f"[bold red]Review file not found: {review_file}[/bold red]")
        sys.exit(1)

    # Validate Data
    body = data.get("body", "Automated Review by Antigravity")
    comments = data.get("comments", [])

    # 1. Fetch PR details to get HEAD SHA (required for inline comments)
    console.print(f"[blue]Fetching details for PR #{pr_number}...[/blue]")
    pr_details = run_gh_command(["pr", "view", str(pr_number), "--json", "headRefOid"])
    commit_oid = pr_details.get("headRefOid")

    if not commit_oid and comments:
        console.print(
            "[bold red]Could not determine HEAD SHA. Cannot post inline comments.[/bold red]"
        )
        sys.exit(1)

    # 2. Construct Payload
    # https://docs.github.com/en/rest/pulls/reviews?apiVersion=2022-11-28#create-a-review-for-a-pull-request
    payload = {"event": event, "body": body, "comments": []}

    for c in comments:
        payload["comments"].append(
            {"path": c["path"], "line": int(c["line"]), "body": c["body"]}
        )

    # Save payload to temp file for gh input
    temp_payload = Path("temp/gh_review_payload.json")
    temp_payload.parent.mkdir(exist_ok=True, parents=True)
    with open(temp_payload, "w", encoding="utf-8") as f:
        json.dump(payload, f)

    # 3. Submit Review
    console.print(
        f"[yellow]Posting review with {len(comments)} inline comments...[/yellow]"
    )

    # We use 'gh api' directly with input from file
    cmd = [
        "api",
        f"repos/:owner/:repo/pulls/{pr_number}/reviews",
        "--input",
        str(temp_payload),
    ]

    # 'gh api' automatically handles :owner/:repo context if run in a repo directory
    run_gh_command(cmd)

    console.print(
        f"[bold green]Successfully posted review to PR #{pr_number}[/bold green]"
    )
    temp_payload.unlink()


if __name__ == "__main__":
    app()
