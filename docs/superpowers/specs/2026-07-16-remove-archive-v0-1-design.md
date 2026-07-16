# Remove `archive-v0.1` Design

## Decision

Delete `archive-v0.1` from the current repository tree. Do not port code,
tests, migrations, UI, or product requirements from it.

Git history remains the recovery mechanism for the legacy snapshot. This change
does not rewrite repository history.

## Why

The audit found no active runtime, build, deployment, test, database, or
packaging dependency on `archive-v0.1`.

The useful legacy concepts have already been incorporated into current Argus
contracts and implementation:

- typed strategy conditions and indicator comparisons;
- executable capability metadata;
- same-asset, equal-weight multi-symbol backtests;
- explicit fees and slippage;
- evidence, decision, comparison, sharing, and broker-handoff direction.

The remaining unique code is not suitable for direct reuse. It belongs to the
old form-builder product, silently skips unsupported inputs, includes mixed-asset
assumptions, and uses experimental pattern, harmonic, and fidelity calculations
that do not satisfy the current evidence-trust contract.

## Scope

Delete:

- `archive-v0.1/**`

Update current references that would otherwise become stale:

- `README.md`
- `pyproject.toml`
- `.gitignore`
- `docs/specs/private-alpha-next-integration.md`
- `docs/superpowers/specs/2026-05-13-artifact-centered-runtime-rebuild-scope.md`

Historical documents under `docs/archive/` may retain references to
`archive-v0.1` because they describe the repository state at the time they were
written.

## No-Touch Surfaces

Do not change:

- active backend runtime under `src/`;
- active frontend under `web/`;
- active tests except if a focused repository-structure assertion is required;
- Supabase migrations or functions;
- Render configuration or release workflows;
- API, product, architecture, or data-model behavior.

## Historical Recovery

The legacy files remain recoverable from Git:

```bash
git show 544bf89:archive-v0.1/src/argus/engine.py
git show 544bf89^:src/argus/analysis/structural.py
```

The existing rebuild-scope document should point to this history rather than a
live archive directory.

## Verification

After deletion:

1. Confirm no current code, build, test, deployment, or packaging reference
   points to `archive-v0.1`.
2. Confirm the diff contains only the archive deletion and stale-reference
   cleanup.
3. Run focused hermetic backend gates for import boundaries, environment
   scripts, Render runtime compatibility, release docs, and modularity.
4. Run the frontend test suite.
5. Run the production frontend build.
6. Confirm `argus` imports from the active `src/argus` package.

No live deployment or production canary is required because the change does not
alter executable application surfaces.

## Stop Conditions

Stop and reassess if:

- an active import, build, test, migration, or deployment path reaches the
  directory;
- a current source-of-truth document depends on a unique archived concept;
- deletion changes active package resolution or frontend build behavior;
- removal is intended to purge Git history rather than remove the current tree.
