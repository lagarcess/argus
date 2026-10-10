# PR927 accepted-design refresh

The founder authorized refreshing the existing website-only promotion PR927 and obtaining green CI. This is preparation, not permission to merge, deploy, publish pages, activate forms or send email.

## Publication gates

Both gates remain open: the privacy policy needed by Meta must name the actual responsible operator in Spanish and English, and the founder must separately confirm LLC clearance. No operator name was supplied or invented. “LLC pending” is not acceptable published operator wording. No pages may ship until both gates are settled.

The accepted #939 design stays locked. Pages-first is not selected or implemented. Any later pages-first proposal must explicitly withhold both forms; missing provider keys and visible unavailable forms do not meet that condition.

## Candidate and scope

- Existing branch: `codex/cuadrao-marketing-main-promotion-prep`, PR927 targeting `main`.
- Existing worktree: `/Users/garces/Documents/projects/repos/argus-worktrees/cuadrao-marketing-main-prep`.
- Previous promotion head: `2d44044e405a4eae37d1c22567a5c3137ff53b7f`.
- Original and refreshed main base: `a9286b21886eb03df7a21f2f4b7d5e79af570679`. No base drift, merge, rebase or force-push.
- Accepted design source: PR939 at `a706ed2284ad67f959d334baa2d4e0305217ac93`; its runtime source is `0455fa4c2a7795064ea85b75879c83b09eec52e6`.
- Current integration observed at refresh: `cd14c9883f180876d27c121f0787b25a73529492`. Integration runtime is not imported into this main-based promotion. #939 remains unchanged.

Every Marketing runtime, asset, test, configuration and lockfile comes from the accepted source unchanged. The only package documentation difference is `marketing/README.md`: preserve #929's main-specific rollback paragraph and use a pinned design-guide link because that integration-only guide is intentionally excluded. [Scope manifest](scope.json) proves package identity and lists the bounded promotion paths.

The existing #927 main-tailored CI, workflow tests, signup migration and database test are preserved. No change to `web/`, `src/`, `ios/`, `render.yaml`, migration-applier tooling or any other migration reaches main. No Business or Consumer product worktree or service was changed.

The #929 launch evidence, including its corrected contact/privacy captures, is preserved byte-for-byte. It is historical evidence, not a screenshot of the updated design. Accepted #939 touch-up evidence and the old-layout archive are included. Six historical build logs received trailing-whitespace cleanup only; images and recorded results are unchanged. The runbook keeps the corrected main rollback explanation, incorporates the already-approved independent signup-migration ordering clarification, and records the stronger publication gates.

## Verification

Fresh production build, lint and typecheck passed. Unit/demo tests passed 178 tests; the focused main workflow-contract suite passed 16. Modularity passed on this tree, which already contains the unchanged main base. The complete browser confirmation passed 199 tests with one intentional touch-pointer skip. The first run timed out in both no-JavaScript contact navigations; both isolated checks passed, then the complete suite passed without code changes. Both runs are retained. Local Bun was 1.4.2; CI uses the pinned 1.3.14 toolchain. The publication-head CI result belongs to PR927 checks, not #939's earlier green run.

The accepted visual evidence is explicitly retained by exact package-runtime identity. A fresh build and the Marketing browser suite verify its behavior on the main-based candidate. No redesign or provider activation is part of this refresh. The demo and previews on4511,4512,4513 remain untouched. Browser tests use isolated local mock providers on4580,4581,4582.

The final independent Codex review returned clean after checking the staged refresh, package identity, preserved evidence, main exclusions and publication gates. No runtime edits or review dismissals were needed. The reviewer is stopped. Fresh logs are committed beside this record. The terminal exact-head CI result is recorded in [PR927 checks and the completion comment](https://github.com/lagarcess/argus/pull/927); this pre-push record does not claim that CI has finished.

## Continuation

Before an eventual merge, land the source/evidence through the normal integration path (#939 and the carried #929 corrections), re-read the main candidate and CI, and obtain founder merge approval. Do not merge all integration changes into main for this website release.

After both publication gates are settled, deployment, database applies, provider configuration, cost, hosted acceptance, domain cutover and public-form activation still need their named approvals in the [launch runbook](../../../runbooks/cuadrao-marketing-launch.md). None occurred in this task. Original comparison and archived source remain available.
