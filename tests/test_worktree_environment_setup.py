from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / ".github" / "setup-worktree-env.sh"
SETUP = ROOT / ".github" / "setup.sh"
CODEX_ENVIRONMENT = ROOT / ".codex" / "environments" / "environment.toml"
BACKEND_SECRET = "backend-secret-value"
FRONTEND_SECRET = "frontend-secret-value"


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )


def _create_worktrees(tmp_path: Path) -> tuple[Path, Path]:
    repository = tmp_path / "repository"
    repository.mkdir()
    _git(repository, "init", "-b", "main")
    _git(repository, "config", "user.email", "argus-tests@example.com")
    _git(repository, "config", "user.name", "Argus Tests")

    (repository / ".gitignore").write_text(
        ".env\nweb/.env.local\n",
        encoding="utf-8",
    )
    (repository / "tracked.txt").write_text("seed\n", encoding="utf-8")
    _git(repository, "add", ".gitignore", "tracked.txt")
    _git(repository, "commit", "-m", "test: seed repository")
    _git(repository, "branch", "codex/private-alpha-next")

    canonical = tmp_path / "canonical integration"
    worker = tmp_path / "issue 194 worker"
    _git(
        repository,
        "worktree",
        "add",
        str(canonical),
        "codex/private-alpha-next",
    )
    _git(
        repository,
        "worktree",
        "add",
        "-b",
        "codex/issue-194",
        str(worker),
        "main",
    )
    return canonical, worker


def _write_canonical_env(canonical: Path) -> None:
    (canonical / ".env").write_text(
        f"OPENROUTER_API_KEY={BACKEND_SECRET}\n",
        encoding="utf-8",
    )
    (canonical / "web").mkdir(exist_ok=True)
    (canonical / "web" / ".env.local").write_text(
        f"NEXT_PUBLIC_SUPABASE_ANON_KEY={FRONTEND_SECRET}\n",
        encoding="utf-8",
    )


def _run_helper(
    target: Path,
    *,
    canonical_override: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("ARGUS_CANONICAL_WORKTREE_ROOT", None)
    if canonical_override is not None:
        env["ARGUS_CANONICAL_WORKTREE_ROOT"] = str(canonical_override)

    return subprocess.run(
        ["bash", str(HELPER), str(target)],
        cwd=target,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return result.stdout + result.stderr


def test_setup_calls_worktree_env_helper_before_dependency_setup() -> None:
    source = SETUP.read_text(encoding="utf-8")

    assert 'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"' in source
    assert 'REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"' in source
    invocation = '"$SCRIPT_DIR/setup-worktree-env.sh" "$REPO_ROOT"'
    assert invocation in source
    assert source.index(invocation) < source.index("PINNED_PYTHON=")
    assert "git ls-files -- .env web/.env.local" in source


def test_codex_environment_delegates_to_tracked_setup_and_cleanup() -> None:
    source = CODEX_ENVIRONMENT.read_text(encoding="utf-8")

    assert "exec .github/setup.sh" in source
    assert 'exec .github/cleanup-worktree.sh "${1:-$PWD}" "${2:-safe}"' in source
    assert "poetry install" not in source
    assert "bun install" not in source
    assert "ALPACA_API_KEY" not in source


def test_links_missing_environment_files_from_integration_worktree(
    tmp_path: Path,
) -> None:
    canonical, worker = _create_worktrees(tmp_path)
    _write_canonical_env(canonical)

    result = _run_helper(worker)

    assert result.returncode == 0, _combined_output(result)
    assert HELPER.stat().st_mode & stat.S_IXUSR
    assert (worker / ".env").is_symlink()
    assert (worker / "web" / ".env.local").is_symlink()
    assert (worker / ".env").resolve() == canonical / ".env"
    assert (worker / "web" / ".env.local").resolve() == (
        canonical / "web" / ".env.local"
    )
    assert BACKEND_SECRET not in _combined_output(result)
    assert FRONTEND_SECRET not in _combined_output(result)


def test_rerun_keeps_existing_canonical_links(tmp_path: Path) -> None:
    canonical, worker = _create_worktrees(tmp_path)
    _write_canonical_env(canonical)

    first = _run_helper(worker)
    backend_link = os.readlink(worker / ".env") if first.returncode == 0 else ""
    frontend_link = (
        os.readlink(worker / "web" / ".env.local") if first.returncode == 0 else ""
    )
    second = _run_helper(worker)

    assert first.returncode == 0, _combined_output(first)
    assert second.returncode == 0, _combined_output(second)
    assert os.readlink(worker / ".env") == backend_link
    assert os.readlink(worker / "web" / ".env.local") == frontend_link
    assert BACKEND_SECRET not in _combined_output(second)
    assert FRONTEND_SECRET not in _combined_output(second)


def test_preserves_existing_file_and_conflicting_symlink(tmp_path: Path) -> None:
    canonical, worker = _create_worktrees(tmp_path)
    _write_canonical_env(canonical)
    (worker / ".env").write_text("worker-owned\n", encoding="utf-8")
    (worker / "web").mkdir(exist_ok=True)
    alternate_frontend_env = tmp_path / "alternate-frontend.env"
    alternate_frontend_env.write_text("alternate-owned\n", encoding="utf-8")
    (worker / "web" / ".env.local").symlink_to(alternate_frontend_env)

    result = _run_helper(worker)

    assert result.returncode == 0, _combined_output(result)
    assert not (worker / ".env").is_symlink()
    assert (worker / ".env").read_text(encoding="utf-8") == "worker-owned\n"
    assert (worker / "web" / ".env.local").resolve() == alternate_frontend_env
    assert BACKEND_SECRET not in _combined_output(result)
    assert FRONTEND_SECRET not in _combined_output(result)


def test_canonical_worktree_keeps_regular_environment_files(tmp_path: Path) -> None:
    canonical, _worker = _create_worktrees(tmp_path)
    _write_canonical_env(canonical)

    result = _run_helper(canonical)

    assert result.returncode == 0, _combined_output(result)
    assert not (canonical / ".env").is_symlink()
    assert not (canonical / "web" / ".env.local").is_symlink()
    assert BACKEND_SECRET not in _combined_output(result)
    assert FRONTEND_SECRET not in _combined_output(result)


def test_missing_integration_worktree_warns_and_continues(tmp_path: Path) -> None:
    repository = tmp_path / "clean-checkout"
    repository.mkdir()
    _git(repository, "init", "-b", "main")

    result = _run_helper(repository)

    assert result.returncode == 0, _combined_output(result)
    assert not (repository / ".env").exists()
    assert not (repository / "web" / ".env.local").exists()
    assert "canonical integration worktree was not found" in result.stdout


def test_explicit_canonical_override_supports_local_recovery(tmp_path: Path) -> None:
    repository = tmp_path / "worker"
    repository.mkdir()
    _git(repository, "init", "-b", "codex/issue-195")
    canonical = tmp_path / "manual canonical"
    canonical.mkdir()
    _write_canonical_env(canonical)

    result = _run_helper(repository, canonical_override=canonical)

    assert result.returncode == 0, _combined_output(result)
    assert (repository / ".env").resolve() == canonical / ".env"
    assert (repository / "web" / ".env.local").resolve() == (
        canonical / "web" / ".env.local"
    )
    assert BACKEND_SECRET not in _combined_output(result)
    assert FRONTEND_SECRET not in _combined_output(result)
