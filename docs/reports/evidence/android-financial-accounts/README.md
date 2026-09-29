# Android Accounts preserved checkpoint

Saved September 29, 2026 at the founder's shutdown request. Implementation
remains stopped; this checkpoint is not release acceptance.

- Branch: `codex/android-financial-accounts`.
- Implementation commit: `3aed3d2266f8ed5a31c87b8083ef114a33d905cd`.
- Original integration base: `296195e86c972e846c251d256b3cc211975bfd57`.
- Latest observed integration: `de8729843b726a3fd03210cebcedede5e44227c8`;
  not reconciled into this branch.
- Execution manifest: [stopped client recovery table in PR #743](https://github.com/lagarcess/argus/blob/codex/mvee-private-iphone-delivery/docs/specs/argus-execution-board.md).
  That table points to this branch and the implementation commit above.
- Assigned scope and contracts: [Android Accounts spec](../../../superpowers/specs/2026-09-29-android-financial-accounts.md).
- Retained checkout: `/Users/garces/.codex/worktrees/611c/private-alpha-next`.

## Preserved evidence

The 16 PNGs were captured from implementation commit `3aed3d226` using
synthetic identities and records against the isolated local Argus API and
Postgres stack. They show the native create, reopen, correction, known-zero,
unknown and optional half-owned asset flows. They contain no production data.

- `1080x1920/`: English, light theme, font scale 1.3.
- `1440x3120/`: es-419, dark theme, font scale 1.3.

Both sizes used the dedicated API 36 ARM64 emulator, not physical devices.
The capture source predates this preservation-only commit; no new behavioral
verification or final-head acceptance is claimed.

Before shutdown, build/lint and 56 JVM tests passed; both native UI journeys and
the nine default-off foundation device tests passed. Independent scoped review
was clean after create-cancellation and stale-opening reconciliation fixes.
The final core device rerun encountered the local login rate limit. Final API
restart/app restart proof, integration reconciliation, PR publication, CI and
terminal review remain unfinished. Cross-surface synchronization was not proved.

## Recovery and stopped resources

The lane-owned APIs on 59400/59410, emulator 5584 (`Argus_Auth_611c`) and
`android-accounts-611c` Supabase stack were stopped. Supabase confirmed a retained
backup. All local scheduled automations were paused; no lane review watcher or
test process remained at the preservation check. No implementation PR was opened.

Local stack and restricted synthetic-fixture files remain under
`/tmp/argus-android-accounts-611c/`; they are not committed and may expire.
The reusable launcher and test commands are in [Android README](../../../../mobile/android/README.md).
Reinspect resource ownership and the execution manifest before any explicitly
authorized restart. Preserve this worktree; do not replace or delete it.
