# Remove `archive-v0.1` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the inactive v0.1 application snapshot from the current repository tree, clean stale references, and publish the verified change as a focused PR to `codex/private-alpha-next`.

**Architecture:** The active application remains untouched. Git history at commit `544bf89` retains the old implementation, while the current tree loses the duplicate backend, frontend, migrations, tests, generated clients, locks, and assets. Current documentation is updated only where it would otherwise point at a directory that no longer exists.

**Tech Stack:** Git, Markdown, Poetry/Pytest, Bun/Next.js, GitHub CLI.

## Global Constraints

- Delete `archive-v0.1/**`; do not port any archived code, tests, migrations, UI, or product requirements.
- Preserve normal Git history; do not rewrite repository history.
- Do not modify active runtime code under `src/` or `web/`.
- Do not modify active Supabase migrations/functions, Render configuration, or release workflows.
- Historical documents under `docs/archive/` may retain their original `archive-v0.1` references.
- Run backend verification with provider keys blanked and `ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture`.
- Target the PR to `codex/private-alpha-next`.

---

### Task 1: Delete the Snapshot and Clean Current References

**Files:**
- Delete: `archive-v0.1/**`
- Modify: `README.md`
- Modify: `pyproject.toml`
- Modify: `.gitignore`
- Modify: `docs/specs/private-alpha-next-integration.md`
- Modify: `docs/superpowers/specs/2026-05-13-artifact-centered-runtime-rebuild-scope.md`

**Interfaces:**
- Consumes: the approved removal boundary in `docs/superpowers/specs/2026-07-16-remove-archive-v0-1-design.md`
- Produces: an active repository tree with no package, build, test, migration, or documentation dependency on `archive-v0.1`

- [ ] **Step 1: Confirm the deletion preconditions**

Run:

```bash
test -d archive-v0.1
test "$(git ls-files archive-v0.1 | wc -l | tr -d ' ')" = "161"
git status --short
```

Expected: the directory exists, contains 161 tracked files, and the worktree is clean before deletion.

- [ ] **Step 2: Delete the tracked directory**

Run:

```bash
git rm -r archive-v0.1
```

Expected: Git stages deletion of all 161 archived files.

- [ ] **Step 3: Replace stale current-tree references**

Apply these exact content changes:

`README.md`

```markdown
# Argus

Argus is a chat-first AI investing idea validation platform that turns natural-language ideas into clear, reproducible historical experiments.
```

`pyproject.toml`

```toml
# Active Argus package source lives under src/argus.
package-mode = true
packages = [{include = "argus", from = "src"}]
```

`.gitignore`

```gitignore
# Supabase temp (contains live project ref, org ID, pooler URL — never commit)
supabase/.temp/
```

`docs/specs/private-alpha-next-integration.md`

```markdown
- Dead-code candidate inventories for active-tree code.
```

`docs/superpowers/specs/2026-05-13-artifact-centered-runtime-rebuild-scope.md`

```markdown
- Reviving the legacy v0.1 builder UI from Git history.

## Legacy v0.1 Salvage Policy

Use the legacy v0.1 snapshot from Git history only as reference material
(`544bf89`).
```

and:

```markdown
- Do not copy legacy v0.1 code from Git history wholesale.
```

Expected: current documentation no longer instructs readers to use a live archive directory.

- [ ] **Step 4: Verify the structural diff**

Run:

```bash
test ! -e archive-v0.1
test -z "$(git ls-files archive-v0.1)"
rg -n 'archive-v0\.1|archive-v0|archive_v0' . \
  --hidden \
  -g '!.git/**' \
  -g '!docs/archive/**' \
  -g '!docs/superpowers/specs/2026-07-16-remove-archive-v0-1-design.md' \
  -g '!docs/superpowers/plans/2026-07-16-remove-archive-v0-1.md'
git diff --check
git diff --name-only origin/codex/private-alpha-next...HEAD
git diff --name-only --cached
```

Expected:

- the directory and tracked paths are absent;
- the `rg` command returns no current references;
- `git diff --check` reports no whitespace errors;
- active runtime, frontend, Supabase, Render, and workflow files are absent from the changed-file lists.

- [ ] **Step 5: Commit the removal**

Run:

```bash
git add README.md pyproject.toml .gitignore \
  docs/specs/private-alpha-next-integration.md \
  docs/superpowers/specs/2026-05-13-artifact-centered-runtime-rebuild-scope.md
git commit -m "chore(cleanup): remove legacy v0.1 archive"
```

Expected: one focused cleanup commit containing the directory deletion and stale-reference updates.

---

### Task 2: Verify Active Build and Packaging Paths

**Files:**
- Test: `tests/test_api_import_boundary.py`
- Test: `tests/test_environment_scripts.py`
- Test: `tests/test_render_runtime_compatibility.py`
- Test: `tests/test_private_alpha_release_docs.py`
- Test: `tests/test_modularity_budget.py`
- Test: `web/__tests__/**`

**Interfaces:**
- Consumes: the active repository after Task 1
- Produces: evidence that backend imports, release configuration, frontend tests, and the production frontend build are unchanged

- [ ] **Step 1: Run focused hermetic backend verification**

Run:

```bash
OPENROUTER_API_KEY= \
ALPACA_API_KEY= \
ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest \
  tests/test_api_import_boundary.py \
  tests/test_environment_scripts.py \
  tests/test_render_runtime_compatibility.py \
  tests/test_private_alpha_release_docs.py \
  tests/test_modularity_budget.py \
  -q --no-cov
```

Expected: 67 tests pass.

- [ ] **Step 2: Confirm active package resolution**

Run:

```bash
poetry run python - <<'PY'
from pathlib import Path

import argus
from argus.api.main import app

module_path = Path(argus.__file__).resolve()
assert module_path.as_posix().endswith("/src/argus/__init__.py"), module_path
assert app.title == "Argus Alpha API"
print(module_path)
print(app.title)
PY
```

Expected: `argus` resolves from active `src/argus`, and the API title is `Argus Alpha API`.

- [ ] **Step 3: Run frontend tests**

Run:

```bash
cd web && bun test
```

Expected: 307 tests pass with zero failures.

- [ ] **Step 4: Run the production frontend build**

Run:

```bash
cd web && bun run build
```

Expected: Next.js production build completes successfully.

- [ ] **Step 5: Review the final change set**

Run:

```bash
git status --short --branch
git diff --stat origin/codex/private-alpha-next...HEAD
git diff --name-status origin/codex/private-alpha-next...HEAD
git log --oneline --decorate origin/codex/private-alpha-next..HEAD
```

Expected:

- the branch contains the design, plan, and cleanup commits only;
- no active runtime, frontend, migration, Render, or workflow file changed;
- the worktree is clean.

---

### Task 3: Publish the Pull Request

**Files:**
- No repository files changed.

**Interfaces:**
- Consumes: verified commits from Tasks 1 and 2
- Produces: a GitHub PR targeting `codex/private-alpha-next`

- [ ] **Step 1: Push the branch**

Run:

```bash
git push -u origin codex/remove-archive-v0-1
```

Expected: remote branch `codex/remove-archive-v0-1` is created.

- [ ] **Step 2: Create the PR**

Create a PR with:

```text
Title: chore(cleanup): remove legacy v0.1 archive
Base: codex/private-alpha-next
Head: codex/remove-archive-v0-1
```

PR body:

```markdown
## Summary
- Remove the inactive `archive-v0.1` application snapshot.
- Clean current documentation and ignore rules that referenced the directory.
- Preserve historical recovery through Git commit `544bf89`.

## Changes
- Delete 161 archived backend, frontend, migration, test, generated, lock, and asset files.
- Refresh the root README and package-source comment.
- Point the legacy salvage policy to Git history.

## Motivation
The archived snapshot is not used by runtime, CI, packaging, Render, Supabase, or the active product vision. Keeping it in the current tree adds duplicate manifests, generated clients, and stale product assumptions.

## Impact
- No runtime, API, schema, frontend, or deployment behavior changes.
- Normal Git history remains available for legacy reference.
- Repository working tree is approximately 2.4 MB smaller.

## Testing
- 67 focused hermetic backend tests.
- 307 frontend tests.
- Next.js production build.
- Active `argus` import-path assertion.
- Structural reference and diff checks.

## Risks/Rollback
- Risk is limited to an undiscovered repository-path reference.
- Revert the cleanup commit to restore the current-tree snapshot.
- This PR does not rewrite Git history.

## Checklist
- [x] Test added/updated
- [x] Docs updated
- [x] Backward compatibility considered
```

Expected: PR opens against `codex/private-alpha-next` with the repository's relevant existing maintenance/documentation label if available.

- [ ] **Step 3: Confirm PR state**

Run:

```bash
gh pr view --json number,url,state,isDraft,baseRefName,headRefName,mergeable,statusCheckRollup
```

Expected: the PR is open, targets `codex/private-alpha-next`, and points to `codex/remove-archive-v0-1`.
