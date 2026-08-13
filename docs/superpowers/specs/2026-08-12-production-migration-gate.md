# Production Migration Gate Design

**Issue:** #449

**Integration base:** `f9acfa61311786803721268854685fd94f3f1899`

**Owner:** promotion path and private-launch runbook

**Scope:** read-only release control; no hosted mutation

## Why this lane exists

The 2026-08-11 production promotion deployed code while nine checked-in
migrations were absent from production. Service health, SHA coherence, and
configuration checks all passed, but the research path could not use the schema
it required.

The promotion path therefore needs an executable schema-parity gate before any
service deploy. A runbook reminder alone is not sufficient.

## Locked behavior

1. The operator supplies an exact 40-character candidate commit SHA. Checkout
   `HEAD` and the tracked working tree must match that candidate.
2. The gate reads `supabase/migrations` from that Git commit, not from the
   mutable working tree.
3. For a production promotion, that candidate is the exact immutable commit
   intended to land on `main`. If landing changes the SHA, the earlier report is
   invalid and the landed commit must be gated before any deploy-capable action.
   The final gate uses `--verify-landed-ref origin/main`, fetches that branch
   inside the executable boundary, requires it to equal the candidate, and then
   repeats production schema parity.
4. The database connection is supplied explicitly through
   `ARGUS_PRODUCTION_DATABASE_URL`. Dotenv discovery is forbidden.
5. The exact candidate's existing `render.yaml` `argus-api` `SUPABASE_URL` owns
   the production Supabase project ref. The gate derives that ref and verifies
   it against the connection host or pooler username before connecting. It
   never prints credentials or creates a second target config.
6. The database session is read-only. The only product query reads
   `supabase_migrations.schema_migrations` in version order.
7. The JSON report records the exact candidate SHA, sanitized database target,
   every candidate migration, every applied migration, the latest applied
   version, missing migrations, unexpected applied migrations, and name drift.
8. Each missing migration receives a conservative safety classification:
   `additive`, `contract-replacing`, or `destructive`, plus the corresponding
   live-database requirement. Unknown SQL is never called additive.
9. Any missing, unexpected, mismatched, unreadable, malformed, or duplicate
   migration blocks promotion. Exact parity is the only passing state.
10. The gate never applies SQL. A human reviews and applies approved migrations
   out of band, in repository order, then reruns the gate for readback proof.
11. The report is written as durable release evidence before service deploy.

Classification is advisory about *how* a human may apply a pending migration;
it never weakens the parity stop. Additive migrations still block service deploy
until production records them as applied.

## Safety classification

The classifier strips comments, quoted values, and dollar-quoted function
bodies before examining top-level statements. It uses a strict additive
allowlist. Data deletion, truncation, or object removal is destructive.
Replacement, permission removal, data rewrites, and other non-additive or
unrecognized statements are contract-replacing. This biases ambiguous SQL
toward a safer operator review.

The report maps classifications to requirements:

- `additive`: may be reviewed for live application, with normal rollback proof.
- `contract-replacing`: requires an expand/contract compatibility plan or a
  maintenance window.
- `destructive`: requires a maintenance window, backup/readback plan, and
  founder approval.

## Promotion-path contract

The order is fixed:

1. Resolve the exact immutable commit that will land and deploy, plus the
   promotion target.
2. Run the production migration gate and save its JSON report.
3. If the report is blocked, stop. A human may apply approved migrations and
   rerun step 2.
4. Land the gated candidate without rewriting it and prove `origin/main`
   resolves to the gated SHA with `--verify-landed-ref origin/main`. The gate
   must fetch the ref itself; stale or unavailable remote state blocks. If the
   SHA differs, invalidate the report and rerun the gate against the landed SHA
   while autodeploy remains manual.
5. Only a passing parity report for the landed candidate allows deployment of
   `argus-api`, `argus-app`, and `argus-backtests`.
6. Continue with exact-SHA deploy, warmup, canary, and manifest evidence.

Structural tests must pin the executable gate before all three service deploys
in both `docs/specs/private-alpha-ci-cd-sota.md` and
`docs/PRIVATE_LAUNCH_RUNBOOK.md`.

## Owned files

- `scripts/ops/production_migration_gate.py`
- `scripts/ops/tests/test_production_migration_gate.py`
- `tests/test_private_alpha_release_docs.py`
- `docs/specs/private-alpha-ci-cd-sota.md`
- `docs/PRIVATE_LAUNCH_RUNBOOK.md`
- `docs/release-manifests/TEMPLATE.md`

## No-touch and stop conditions

- Do not change `render.yaml` or `.github/private-alpha-release-profile.json`.
- Do not add a pre-deploy or release command that applies migrations.
- Do not change application runtime, API, data model, RLS, or migration SQL.
- Do not connect to production during implementation verification.
- Stop if the gate cannot prove the target, read the ledger, or produce exact
  parity.
- Stop after the issue PR has a clean review verdict and zero unresolved review
  threads. The founder owns merge and deployment.

## Verification

- Red-first unit tests cover exact candidate enumeration, sanitized target
  validation, read-only ledger access, parity, missing/unexpected/name-drift
  stops, and all three safety classes.
- Structural documentation tests prove the gate precedes service deployment.
- Focused pytest, Ruff, `git diff --check`, scope audit, and the repository
  modularity guard run at the final PR head.
- The PR targets `codex/private-alpha-next` and reports its exact head.

## Source evidence

- `docs/release-manifests/2026-08-12-main-production-promotion.md` records the
  manual ledger census, one approved apply, and post-apply object readback.
- `docs/release-manifests/2026-08-12-main-production-promotion-716221f.md`
  records the no-gap path from an empty candidate migration diff.
- PR #470, merged as the lane base, owns the three-service release contract and
  remains unchanged by this lane.
