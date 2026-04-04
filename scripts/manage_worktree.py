"""
Worktree Management Script for Parallel Development.
Usage: python scripts/manage_worktree.py [create|remove|sync|list]
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.prompt import Confirm

app = typer.Typer()
console = Console()


def run_command(
    args: list[str], cwd: Optional[Path] = None, capture: bool = False
) -> subprocess.CompletedProcess:
    """Run a shell command."""
    try:
        return subprocess.run(
            args, cwd=cwd, check=True, capture_output=capture, text=True, encoding="utf-8"
        )
    except subprocess.CalledProcessError as e:
        if capture:
            console.print(f"[bold red]Command failed:[/bold red] {' '.join(args)}")
            console.print(e.stderr)
        raise


def get_repo_root() -> Path:
    """Get the absolute path to the git repository root."""
    res = run_command(["git", "rev-parse", "--show-toplevel"], capture=True)
    return Path(res.stdout.strip())


def slugify(text: str) -> str:
    """Turn a branch name into a folder-safe slug."""
    return text.replace("/", "-").replace("\\", "-").lower()


@app.command()
def list_worktrees():
    """List all active worktrees."""
    run_command(["git", "worktree", "list"])


@app.command()
def create(
    branch: Annotated[
        str, typer.Argument(help="Branch name to create or checkout (e.g. feat/new-ui)")
    ],
    base: Annotated[
        str, typer.Option(help="Base branch to fork from if creating new")
    ] = "main",
):
    """
    Create a new parallel worktree for a branch.
    Auto-fetches origin, sets up tracking if remote exists, copies .env, and installs deps.
    """
    root = get_repo_root()
    folder_name = f"{root.name}-{slugify(branch)}"
    target_path = root.parent / folder_name

    if target_path.exists():
        console.print(
            f"[bold red]Error: Target directory {target_path} already exists.[/bold red]"
        )
        sys.exit(1)

    console.print("[blue]Fetching origin to check for existing branch...[/blue]")
    run_command(["git", "fetch", "origin"])

    # Determine Git Strategy
    # Check if branch exists remotely
    remote_exists = False
    try:
        run_command(["git", "rev-parse", "--verify", f"origin/{branch}"], capture=True)
        remote_exists = True
    except subprocess.CalledProcessError:
        pass

    # Check if branch exists locally
    local_exists = False
    try:
        run_command(["git", "rev-parse", "--verify", branch], capture=True)
        local_exists = True
    except subprocess.CalledProcessError:
        pass

    cmd = ["git", "worktree", "add"]

    if local_exists:
        console.print(f"[green]Found local branch '{branch}'. Checking out...[/green]")
        cmd.extend([str(target_path), branch])
    elif remote_exists:
        console.print(
            f"[green]Found remote branch 'origin/{branch}'. Creating tracking branch...[/green]"
        )
        cmd.extend(["-b", branch, str(target_path), f"origin/{branch}"])
    else:
        console.print(
            f"[yellow]Branch '{branch}' not found. Creating new from '{base}'...[/yellow]"
        )
        cmd.extend(["-b", branch, str(target_path), base])

    # Execute Worktree Creation
    run_command(cmd)

    # Post-Creation Setup
    console.print("[blue]Setting up environment...[/blue]")

    # 1. Copy .env
    src_env = root / ".env"
    dst_env = target_path / ".env"
    if src_env.exists():
        shutil.copy(src_env, dst_env)
        console.print("✅ Copied .env")
    else:
        console.print("[yellow]Warning: No .env found in root to copy.[/yellow]")

    # 2. Install Dependencies
    console.print("[blue]Installing dependencies with Poetry...[/blue]")
    try:
        run_command(["poetry", "install"], cwd=target_path)
        console.print("✅ Dependencies installed")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Failed to install dependencies: {e}[/red]")
        console.print("You may need to run 'poetry install' manually in the new folder.")

    console.print(f"\n[bold green]Success! Worktree ready at:[/bold green] {target_path}")
    console.print(f"To verify: [bold]cd {target_path} && poetry run pytest[/bold]")


@app.command()
def remove(
    branch_slug: Annotated[
        str, typer.Argument(help="Folder slug or branch name to remove")
    ],
):
    """Remove a worktree and prune git metadata."""
    root = get_repo_root()
    # Handle both "feat/foo" (branch) and "crypto-signals-feat-foo" (folder) inputs
    if "/" in branch_slug:
        folder_name = f"{root.name}-{slugify(branch_slug)}"
    elif branch_slug.startswith(root.name):
        folder_name = branch_slug
    else:
        # Assume it's a suffix
        folder_name = f"{root.name}-{branch_slug}"

    target_path = root.parent / folder_name

    if not target_path.exists():
        console.print(f"[red]Directory {target_path} does not exist.[/red]")
        sys.exit(1)

    if not Confirm.ask(f"Are you sure you want to delete {target_path}?"):
        sys.exit(0)

    # Git Worktree Remove
    try:
        run_command(["git", "worktree", "remove", str(target_path)])
        # Also clean up the directory if git didn't (sometimes happens with untracked files)
        if target_path.exists():
            shutil.rmtree(target_path)
        console.print(f"[green]Removed worktree {folder_name}[/green]")

        # Prune to be safe
        run_command(["git", "worktree", "prune"])

    except Exception as e:
        console.print(f"[red]Error removing worktree: {e}[/red]")
        console.print("Try manually deleting the folder and running 'git worktree prune'")


@app.command()
def sync(
    force: Annotated[
        bool, typer.Option("--force", help="Bypass CI/CD guardrails")
    ] = False,
):
    """
    Sync current branch with main via Rebase.
    Includes CI/CD Guardrail to prevent syncing if main is broken.
    """
    # 1. CI/CD Guardrail
    console.print("[blue]Checking CI/CD status of 'main'...[/blue]")
    try:
        # Check last run of deploy.yml on main
        res = run_command(
            [
                "gh",
                "run",
                "list",
                "--workflow",
                "deploy.yml",
                "--branch",
                "main",
                "--limit",
                "1",
                "--json",
                "conclusion,url,displayTitle",
            ],
            capture=True,
        )

        data = json.loads(res.stdout)
        if data:
            run = data[0]
            status = run.get("conclusion")
            url = run.get("url")
            title = run.get("displayTitle")

            if status != "success" and not force:
                console.print("\n[bold red]⛔ GUARDRAIL ACTIVATED[/bold red]")
                console.print(f"Main build is currently: [bold]{status}[/bold]")
                console.print(f"Commit: {title}")
                console.print(f"URL: {url}")
                console.print(
                    "\n[yellow]Preventing rebase to protect your branch from broken code.[/yellow]"
                )
                console.print(
                    "Use [bold]--force[/bold] if you absolutely need to sync now."
                )
                sys.exit(1)
            elif status == "success":
                console.print("[green]✅ Main is healthy. Proceeding.[/green]")
        else:
            console.print(
                "[yellow]No CI/CD history found for 'main'. Proceeding with caution.[/yellow]"
            )

    except subprocess.CalledProcessError as e:
        console.print(
            f"[yellow]Warning: Could not check CI/CD status ({e}). Proceeding...[/yellow]"
        )

    # 2. Fetch
    console.print("[blue]Fetching origin...[/blue]")
    run_command(["git", "fetch", "origin"])

    # 3. Rebase
    console.print("[blue]Rebasing on origin/main...[/blue]")
    try:
        run_command(["git", "rebase", "origin/main"])
        console.print("[bold green]Successfully synced with main![/bold green]")
    except subprocess.CalledProcessError:
        console.print("[bold red]Conflict detected during rebase![/bold red]")
        console.print(
            "Please resolve conflicts manually, then run 'git rebase --continue'."
        )
        sys.exit(1)


if __name__ == "__main__":
    app()
