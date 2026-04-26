from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from fnmatch import fnmatch
from pathlib import Path
from typing import Any


def _run_git(repo_root: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout.strip()


def _run_git_optional(repo_root: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _normalize_path(path: str) -> str:
    cleaned = path.strip().replace("\\", "/")
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    return cleaned


def _matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch(path, pattern) for pattern in patterns)


def _resolve_branch(repo_root: Path, explicit_branch: str | None) -> str:
    if explicit_branch:
        return explicit_branch

    github_head_ref = os.getenv("GITHUB_HEAD_REF")
    if github_head_ref:
        return github_head_ref

    github_ref_name = os.getenv("GITHUB_REF_NAME")
    if github_ref_name:
        return github_ref_name

    return _run_git(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"])


def _resolve_base_ref(repo_root: Path, requested_ref: str) -> str:
    candidates = [requested_ref, f"origin/{requested_ref}"]
    for candidate in candidates:
        probe = _run_git_optional(repo_root, ["rev-parse", "--verify", candidate])
        if probe:
            return candidate
    raise RuntimeError(f"Unable to resolve base ref '{requested_ref}'")


def _collect_git_changed_files(repo_root: Path, base_ref: str) -> list[str]:
    merge_base = _run_git(repo_root, ["merge-base", base_ref, "HEAD"])
    committed = _run_git_optional(
        repo_root,
        ["diff", "--name-only", "--diff-filter=ACDMRTUXB", f"{merge_base}...HEAD"],
    )
    staged = _run_git_optional(
        repo_root, ["diff", "--name-only", "--cached", "--diff-filter=ACDMRTUXB"]
    )
    unstaged = _run_git_optional(
        repo_root, ["diff", "--name-only", "--diff-filter=ACDMRTUXB"]
    )
    untracked = _run_git_optional(
        repo_root, ["ls-files", "--others", "--exclude-standard"]
    )

    combined: set[str] = set()
    for block in (committed, staged, unstaged, untracked):
        for line in block.splitlines():
            normalized = _normalize_path(line)
            if normalized:
                combined.add(normalized)

    return sorted(combined)


def _load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify branch file ownership against allow/deny policies."
    )
    parser.add_argument(
        "--manifest",
        default=".agent/ownership/branch_ownership.json",
        help="Path to ownership manifest JSON (repo-relative or absolute).",
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Repository root path. Defaults to script-derived repository root.",
    )
    parser.add_argument(
        "--branch",
        default=None,
        help="Branch name override. Defaults to current branch or CI metadata.",
    )
    parser.add_argument(
        "--base-ref",
        default=None,
        help="Base branch override for diff collection.",
    )
    parser.add_argument(
        "--files",
        nargs="*",
        default=None,
        help="Optional explicit changed files list (bypasses git diff collection).",
    )
    args = parser.parse_args()

    repo_root = (
        Path(args.repo_root).resolve()
        if args.repo_root
        else Path(__file__).resolve().parents[3]
    )
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = (repo_root / manifest_path).resolve()

    if not manifest_path.exists():
        print(f"ERROR: Ownership manifest not found: {manifest_path}")
        return 2

    manifest = _load_manifest(manifest_path)
    branches: dict[str, dict[str, Any]] = manifest.get("branches", {})
    branch_name = _resolve_branch(repo_root, args.branch)

    if branch_name not in branches:
        print(f"Branch '{branch_name}' has no ownership policy. Skipping enforcement.")
        return 0

    policy = branches[branch_name]
    allow: list[str] = policy.get("allow", [])
    deny: list[str] = policy.get("deny", [])
    if not allow:
        print(f"ERROR: Branch '{branch_name}' policy has no allowlist entries.")
        return 2

    if args.files:
        changed_files = sorted({_normalize_path(path) for path in args.files if path})
        base_ref = (
            args.base_ref or policy.get("base_ref") or manifest.get("default_base_ref")
        )
    else:
        requested_base = (
            args.base_ref or policy.get("base_ref") or manifest.get("default_base_ref")
        )
        if not requested_base:
            print(
                f"ERROR: Branch '{branch_name}' has no base ref and no default_base_ref."
            )
            return 2
        base_ref = _resolve_base_ref(repo_root, requested_base)
        changed_files = _collect_git_changed_files(repo_root, base_ref)

    if not changed_files:
        print(f"Ownership gate passed: no changed files detected for '{branch_name}'.")
        return 0

    denied_hits: list[str] = []
    outside_allowlist: list[str] = []
    for path in changed_files:
        if _matches_any(path, deny):
            denied_hits.append(path)
            continue
        if not _matches_any(path, allow):
            outside_allowlist.append(path)

    if denied_hits or outside_allowlist:
        print("Ownership gate failed.")
        print(f"Branch: {branch_name}")
        if base_ref:
            print(f"Base ref: {base_ref}")
        print("Changed files:")
        for file_path in changed_files:
            print(f"  - {file_path}")
        if denied_hits:
            print("Denied files (explicitly prohibited):")
            for file_path in denied_hits:
                print(f"  - {file_path}")
        if outside_allowlist:
            print("Out-of-scope files (not in allowlist):")
            for file_path in outside_allowlist:
                print(f"  - {file_path}")
        return 1

    print(f"Ownership gate passed for '{branch_name}'.")
    print(f"Checked {len(changed_files)} changed file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
