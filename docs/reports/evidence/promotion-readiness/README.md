# Promotion-readiness rehearsal

Date: 2026-09-14 America/Chicago (2026-09-15 UTC).
Deliverable: [ordered next-promotion checklist](../../../release-manifests/NEXT-PROMOTION-CHECKLIST.md).
This report proves local preparation, not permission or readiness to promote.
Production reads, paid calls, merges and deployments performed: **zero**.

## Candidate and scope

- Original fetched integration: `edeaffa9f6565e4750fa0685a050f10aefd6d718`.
- Refreshed integration: `a4a183138aadf1cff8268d0ce169e444732116fe`.
- Reconciliation merge / verified code head:
  `75dafb2ddb1d12c4d49f4d218b4409805c089d3f`.
- Branch: `codex/promotion-readiness`; PR base: `codex/private-alpha-next`.
- Intervening integration change: PR #632 sharing, then its board record.
  Semantic overlap: it adds the fourth migration, changes the API/data contract,
  receipt selection/rendering and affected tests. It does not modify the gate
  fix or release profile. The original three-migration result was superseded by
  the four-migration rehearsal; full deterministic checks were rerun on the
  reconciled tree. No prior live evidence was claimed for this candidate.
- Lane edits: checklist, local evidence/diagnostic scripts, five lines in the
  promotion evidence validator and a parametrized regression test. No product,
  migration SQL, `render.yaml` or release-profile edit.
- Final PR head, terminal CI, review and unresolved-thread count belong in the
  PR's terminal audit after the final review returns. This local report does
  not predeclare them.

## Free gates and results

Commands are in the checklist. [verification.txt](verification.txt) retains
compact command output, including the red reproduction. Backend/frontend/smoke
and browser proof use the reconciled code head above. The explicitly focused
release suite ran before reconciliation; the full reconciled suite also includes
those tests. Migration-gate tests ran separately with a real disposable DSN.

| Gate | Result |
| --- | --- |
| Ownership | Pass/no policy: this lane has no branch-specific ownership manifest; tool explicitly skips enforcement. |
| Ruff: src/tests/workflows/scripts | Pass; diagnostic scripts separately linted. |
| Modularity | Pass on the reconciled tree, which already contains current integration. |
| Full backend in dotenv-free sibling | **8,622 passed, 605 skipped**, 5 existing synthetic-JWT warnings. Opt-in live/DB skips are not represented as executed evidence. |
| Mocked eval command from README | **270 passed**, no provider calls. Also covered by the full suite. |
| Focused release docs/identity/configuration/profile/Render/canary/migration contracts | **348 passed, 2 skipped**; the skips were the two real-DB migration checks, run below. Historical manifest compatibility remains green. |
| Migration gate, including real PostgreSQL read-only enforcement | **49 passed**, zero skips. |
| Required real PostgreSQL matrix after fourth migration | **386 passed**, zero skips; `assert_pytest_gate.py` passed. |
| Required anonymous Auth matrix | **12 passed**, zero skips; collection guard passed. |
| Frontend lint, test, build | Lint/build passed; **1,987 tests passed**, zero failures. |
| Browser-storage disclosure | **2 passed** against local mock-auth app. No paid chat turns. |
| Full local smoke | `verification_status=ready`; allowed memory-mode Supabase `gateway_unavailable` degradation only. Workflow dispatch/execution stayed off. |
| Release-profile CLI validation | Pass. Models/flags were read from the committed contract, not changed. |
| Existing artifacts as new-candidate evidence | **Blocked as expected: 0 eligible of 44**. See [evidence-eligibility.json](evidence-eligibility.json). |
| Production migration CLI without production target | **Blocked before database access**, exit 2. [Refusal report](production-cli-refusal.json). This is a refusal check, not a production gate pass. |
| Hosted release audit, warmup, canaries, feature browser walk, live eval/baseline/A/B | **Not run by instruction**. These are production/provider operations, even when their command name sounds like a read-only check. |

The CI backend command is `poetry run pytest tests -q --no-cov`; the standalone
`scripts/ops/tests/test_production_migration_gate.py` is an additional gate, not
silently covered by that directory-level invocation. The final preparation PR
also requires the real GitHub CI results at its final head.

## Failures, causes and dispositions

1. **Gate bug, fixed:** a scorecard could contain a skipped case or an
   infrastructure error, keep correct fixture rows/totals, and pass the promotion
   helper. It checked `unexpected_pass` but never rejected these two missing
   measurement statuses. Both parameterized cases reproduced `DID NOT RAISE`
   before the fix. The shared validator now rejects either status. This aligns
   it with the eval README's rule that unavailable measurements block the gate.
   No native result, expected-failure rule or historical exemption was rewritten.
2. **New-candidate evidence is absent:** all 44 committed native live scorecards
   examined fail new-manifest eligibility. The audit separately records their
   schema/configuration rejection and reachable code changes; the gate's first
   schema error does not hide the identity result. The frozen grounded-math
   scorecard is schema 2 and predates subsequent reachable changes. Historical
   PR #603 artifacts cannot be relabeled as evidence for this candidate.
3. **Baseline/A/B preparation dependency:** the recorded deployed build
   `3d98057c1e722317f0243fb96fb647771ddae484` predates #629 and emits schema 2
   without `release_configuration`. Its old embedding module also lacks
   `resolve_memory_embedding_model`, which today's recorder imports. The
   retained PR #603 ten-pair driver hardcodes old SHAs, paths, fixture counts and
   a $12.50 prior approval. Before the next paid session, prepare and verify an
   external ignored observer/driver that records actual native configuration
   before and after each side, with that side's imports and fresh budget. Do not
   transplant current harness code into the baseline or infer old settings from
   today's contract. No such paid driver was executed here.
4. **Migration gap, expected stop:** local baseline had 75 migrations against
   the new candidate's 79. Exactly the four requested migrations were missing.
   After CLI replay, 79/79 matched with no missing, unexpected, name or content
   drift. Three classify destructive; guest-claim release is contract-replacing.
   This does not say what is currently applied in production.
5. **Local test environment:** the first full backend sweep returned 16
   failures: 14 loopback socket denials, one macOS process-inspection denial and
   one default-off memory test seeing the worktree's enabled dotenv flag. With
   process/loopback access, only the dotenv-sensitive test remained. It also
   failed alone there and passed in the env-free sibling; that full sibling run
   passed. No product fix was made. The pinned installed python-dotenv did not
   implement `PYTHON_DOTENV_DISABLED`, so that variable alone was insufficient.
6. **Local build/browser environment:** Turbopack initially failed to bind a
   subprocess port in the sandbox. Its permitted rerun passed. A dependency
   symlink into another checkout was then refused by Turbopack's filesystem
   root; copying dependencies inside the env-free sibling fixed that setup.
   Concurrent smoke/browser dev servers shared Next's lock and caused two empty
   browser responses. The final browser run used its own `NEXT_DIST_DIR` and
   passed both checks. These were setup failures, not product findings.
7. **Invocation corrections:** the first focused command named a nonexistent
   `test_local_smoke_script.py`; collection stopped with zero tests. The real
   file is `test_local_smoke_contract.py`, included in the full suite and final
   focused check. The shell Supabase wrapper could not write local telemetry in
   the sandbox; the installed v2.109.0 `supabase-go` binary ran the local CLI.

No new product defect was confirmed by this rehearsal. There are still known
product caveats on the active roadmap; this report does not close them or
replace founder browser acceptance.

## Disposable migration proof

- Isolated project: `argus-promotion-readiness-d0a9`, local ports 56331–56334.
  Other developers' Supabase stacks were not reset or stopped.
- Candidate migrations read from the exact fetched integration Git tree;
  Supabase CLI v2.109.0 applied the copied SQL in repository order.
- [Before](four-migrations-before.json): 75 applied, 79 candidate, four missing.
- [After](four-migrations-after.json): 79 applied, 79 candidate, no drift.
- [Object readback](local-objects.json): both widened constraints present;
  claim/release functions are SECURITY DEFINER, executable by service_role,
  and not executable by anon/authenticated. No user rows were read.
- [Rehearsal code](rehearse_migrations.py) uses the production gate's actual
  candidate reader, read-only transaction and comparator. The connection
  adapter only permits IP-literal loopback and labels transport as non-TLS.
  Production target verification, TLS and historical production-ledger
  fingerprints were deliberately not exercised or relaxed in the real gate.
- The owned stack was stopped with `stop --no-backup` after verification.

## Remaining promotion decisions

The founder must select the cut and sharing posture, approve the live-run caps,
approve migration maintenance/compatibility and backup/readback plans, and
authorize production operations. Prepare the baseline configuration observer
before any paid run. The next candidate needs fresh eligible evidence and all
hosted acceptance; this lane stops after its own PR checks and review.
