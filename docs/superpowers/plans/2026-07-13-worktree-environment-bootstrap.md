# Worktree Environment Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `.github/setup.sh` automatically and safely link canonical Argus environment files into sibling worker worktrees.

**Architecture:** A focused Bash helper discovers the checked-out `codex/private-alpha-next` worktree through Git's porcelain worktree inventory and provisions only missing symlinks. The existing setup script calls the helper once and remains the sole user-facing entrypoint.

**Tech Stack:** Bash, Git worktrees, pytest, Python subprocess fixtures

## Global Constraints

- Never print, copy, source, or commit secret values.
- Never overwrite an existing file or conflicting symlink.
- Missing canonical sources warn and continue so CI and clean checkouts remain valid.
- Do not change Argus product runtime, deployment, or issue 194-196 surfaces.

---

### Task 1: Specify the provisioning contract with failing tests

**Files:**
- Create: `tests/test_worktree_environment_setup.py`

**Interfaces:**
- Consumes: Git's `worktree list --porcelain` output and the future `.github/setup-worktree-env.sh` command.
- Produces: executable contract tests for setup delegation and environment-file provisioning.

- [ ] **Step 1: Write tests that create temporary canonical and worker Git worktrees**

```python
def test_links_missing_environment_files_from_integration_worktree(tmp_path: Path) -> None:
    canonical, worker = _create_worktrees(tmp_path)
    _write_canonical_env(canonical)
    result = _run_helper(worker)
    assert result.returncode == 0
    assert (worker / ".env").resolve() == canonical / ".env"
    assert (worker / "web/.env.local").resolve() == canonical / "web/.env.local"
```

- [ ] **Step 2: Add cases for reruns, conflicts, missing canonical worktrees, explicit overrides, and output redaction**

```python
assert "backend-secret-value" not in result.stdout + result.stderr
assert existing_file.read_text() == "worker-owned\n"
assert missing_source_result.returncode == 0
```

- [ ] **Step 3: Run the focused tests and verify RED**

Run: `poetry run pytest tests/test_worktree_environment_setup.py -q --no-cov`

Expected: FAIL because `.github/setup-worktree-env.sh` and the setup delegation do not exist.

### Task 2: Implement minimal idempotent provisioning

**Files:**
- Create: `.github/setup-worktree-env.sh`
- Modify: `.github/setup.sh`
- Modify: `.github/WORKTREE_CLEANUP.md`

**Interfaces:**
- Consumes: optional `ARGUS_CANONICAL_WORKTREE_ROOT`, otherwise the local Git worktree inventory.
- Produces: missing `.env` and `web/.env.local` symlinks in the target worktree without exposing values.

- [ ] **Step 1: Add canonical worktree discovery**

```bash
canonical_root="${ARGUS_CANONICAL_WORKTREE_ROOT:-}"
if [ -z "$canonical_root" ]; then
    canonical_root="$(find_integration_worktree || true)"
fi
```

- [ ] **Step 2: Add safe link creation**

```bash
if [ -e "$destination" ] || [ -L "$destination" ]; then
    preserve_existing_destination
elif [ -f "$source" ]; then
    ln -s "$source" "$destination"
fi
```

- [ ] **Step 3: Invoke the helper from `.github/setup.sh` before dependency installation**

```bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
"$SCRIPT_DIR/setup-worktree-env.sh" "$REPO_ROOT"
```

- [ ] **Step 4: Document that setup is automatic and cleanup removes only worktree-local links**

- [ ] **Step 5: Run the focused tests and verify GREEN**

Run: `poetry run pytest tests/test_worktree_environment_setup.py -q --no-cov`

Expected: all focused tests pass.

### Task 3: Verify integration safety

**Files:**
- Verify only: all changed files

**Interfaces:**
- Consumes: completed implementation and tests.
- Produces: evidence that environment contracts and shell syntax remain valid.

- [ ] **Step 1: Check Bash syntax**

Run: `bash -n .github/setup.sh .github/setup-worktree-env.sh`

Expected: exit 0 with no output.

- [ ] **Step 2: Run environment-script regression tests**

Run: `poetry run pytest tests/test_worktree_environment_setup.py tests/test_environment_scripts.py -q --no-cov`

Expected: all selected tests pass.

- [ ] **Step 3: Review the exact diff and verify no environment files are tracked**

Run: `git diff --check && git diff -- . ':!poetry.lock' && git ls-files --error-unmatch .env web/.env.local`

Expected: diff check passes; the final command fails because the secret files remain untracked.

- [ ] **Step 4: Commit the isolated patch**

```bash
git add .github/setup.sh .github/setup-worktree-env.sh .github/WORKTREE_CLEANUP.md tests/test_worktree_environment_setup.py docs/superpowers/specs/2026-07-13-worktree-environment-bootstrap-design.md docs/superpowers/plans/2026-07-13-worktree-environment-bootstrap.md
git commit -m "chore(dev): provision worktree environment links"
```

