# Argus Worktree Cleanup

Use `.github/cleanup-worktree.sh` before deleting a disposable Argus worktree
to reclaim dependency, build, and test-cache disk space.

Create disposable Argus worktrees as siblings of the repo, never nested inside
another Argus checkout. Nested worktrees can inherit the parent `.env` through
dotenv upward search, which can silently turn mocked runs into live LLM/provider
calls.

Run `.github/setup.sh` once in each new sibling worktree. Setup automatically
links a missing `.env` and `web/.env.local` from the worktree checked out on
`codex/private-alpha-next`. Existing files and links to other sources are kept
unchanged. If the canonical integration worktree is not available, setup warns
and continues without provisioning secrets, which keeps clean checkouts and CI
safe.

At agent Phase 0, make the topology explicit without reading any values:

```bash
bash .github/setup-worktree-env.sh "$PWD"
bash .github/setup-worktree-env.sh --check "$PWD"
```

The read-only check reports `canonical-linked`, `canonical-source`,
`worktree-local`, `missing`, or `conflicting-link`. Missing and conflicting
topology return a nonzero status; intentional canonical or worktree-local files
remain valid.

When a lane needs its own disposable local-Supabase configuration, run
`scripts/qa/write-local-env.sh`. It atomically replaces that lane's symlinks
with regular worktree-local files; it must never write through a symlink into
the canonical integration environment. Do not use direct shell redirection to
rewrite a linked `.env` or `web/.env.local`.

For local recovery only, `ARGUS_CANONICAL_WORKTREE_ROOT=/absolute/path` can
select the canonical source explicitly. Normal sibling worktrees do not need
this override.

Safe mode removes known generated bloat and keeps local untracked files such as
`.env` and `web/.env.local` intact:

```bash
.github/cleanup-worktree.sh /path/to/worktree
```

For a worktree that is definitely disposable, wipe all ignored and untracked
files too:

```bash
.github/cleanup-worktree.sh /path/to/worktree --wipe-untracked
```

Then remove the worktree:

```bash
git worktree remove /path/to/worktree
git worktree prune
```

Do not use `--wipe-untracked` in a worktree that may contain unsaved source,
notes, screenshots, or local environment files that need to be preserved.
