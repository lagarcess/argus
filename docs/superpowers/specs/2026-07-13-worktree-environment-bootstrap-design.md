# Worktree Environment Bootstrap Design

**Status:** Approved for implementation on 2026-07-13

## Goal

Keep `.github/setup.sh` as the only Argus worktree setup command while making
the existing canonical backend and frontend environment files available in
every sibling worker worktree automatically.

## Design

The tracked Codex local-environment configuration delegates setup and cleanup to
the existing repository scripts instead of embedding copies. `.github/setup.sh`
invokes one small helper before dependency installation. The helper finds the
worktree currently checked out on
`codex/private-alpha-next`, then creates absolute symlinks for a missing `.env`
and `web/.env.local` from that canonical worktree.

The helper is an implementation detail, not a second user workflow. Running
`.github/setup.sh` remains the only required action.

## Safety Contract

- Never copy, source, or print secret values.
- Never commit environment files.
- Never replace an existing regular file or a symlink to a different source.
- Treat a link already pointing to the canonical file as an idempotent no-op.
- If the canonical integration worktree or either source file is unavailable,
  warn and continue with the current setup behavior.
- In the canonical integration worktree itself, existing files remain regular
  files and setup is a no-op.
- Clean checkouts and CI continue without environment provisioning when no
  canonical integration worktree exists.
- An explicit `ARGUS_CANONICAL_WORKTREE_ROOT` may override discovery for local
  recovery, but normal worktrees require no per-worktree configuration.

## Scope

Allowed:

- `.github/setup.sh`
- `.github/setup-worktree-env.sh`
- `.codex/environments/environment.toml`
- focused setup tests
- worktree setup documentation

Forbidden:

- product runtime, frontend, API, database, or deploy behavior
- environment values or credentials in Git
- changes to `.github/dev.sh`, `.github/qa.sh`, or release profiles
- issue 194, 195, or 196 implementation surfaces

## Verification

Automated tests prove first-run linking, idempotent reruns, preservation of
existing files and conflicting links, clean-checkout fallback, override
behavior, setup delegation, and absence of secret values in command output.
