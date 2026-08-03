# Private Alpha Next Integration

Status: Active integration staging/process context
Date: 2026-06-10
Last reconciled: 2026-08-02
Branch: `codex/private-alpha-next`
Audience: Founder, Codex, external async agents, reviewers

Latest product change: PR #356 at `48de2f3f`, which standardizes menu-row
hover/selected highlights as rounded inset pills across Settings, Profile,
Recents overflow, and chat-header menus (issue #343). It follows PR #357 at
`9f97f1dc` (guest dossier conversion gating, issue #340), PR #353 at
`7e4c58f8` (proven-continuity rail attention clearing, issue #337), PR #355
at `c01d5730` (opening-turn asset/capital preservation, issue #336), PR #362
at `b2e8975c` (live-eval environment repair, issue #361), and PR #348 at
`38874bae` (self-hosted canonical fonts).
Later commits may reconcile documentation and issue state without changing
product behavior. New work must branch from the current remote
`codex/private-alpha-next` head rather than pinning either product SHA. The
accepted post-promotion
vertical slices are graph range switching (PR #264), account recovery/session
controls (PR #261), truthful Usage allowances/accounting (PR #259), and
executable capability truth (PR #266), the Always Progresses continuity
baseline (PR #268), calendar-materiality classification (PR #267), chat-header
title/owner-menu correction (PR #274), explicit onboarding removal (PR #275),
truthful stale Run settlement (PR #277), and supported strategy-transition
preservation (PR #278), plus the default-on grounded-discovery baseline
(PR #276), modeled-cost preservation (PR #280), and the Guest experience
(PR #279), followed by chat next-move presentation (PR #281). Provider-free
backend test isolation landed through PR #282, and PR #286 made the complete
`tests/` directory the backend CI gate. PR #287 then delivered resolver-owned
discovery selection identity and candidate/entity corroboration. PR #285 then
bounded Conversations, Messages, History, and Omnisearch/Idea Ledger reads at
the Postgres boundary while preserving cursor, ranking, ownership, and artifact
contracts. This is an integration checkpoint, not a deployed or
tester-exposed SHA. PR #288 then completed canonical fact-preserving recovery
after stale or failed actions without changing public artifact contracts.
Later slices culminated in PR #298's visitor/day Guest settlement, honest
discovery progress, and per-candidate source ownership, followed by PR #299's
instant and race-safe browser-session conversation switching. PR #300 then
completed comparison name grounding, unsupported-target disclosure, and
discovery-act preservation through pending confirmations. PR #302 completed
bounded progressive Recents disclosure, and PR #303 reconciled catalog-valid
benchmarks with explicit zero price bars before confirmation. PR #304 then
completed distinct Quick take, Explain result, typed Try next, and recoverable
failure ownership across live turns, durable jobs, reload, English, and
Spanish. PR #305 then completed issue #253's deterministic decision-first
recall projection and panel as `88ab906d`. PR #306 completed the Full
Omnisearch memory-inspector journey as `b71f1eaf`: one ranked conversation row,
bounded object-first transcript recall, jump-to-match, deterministic dossiers
and asset rollups, exact decision filtering and mutation refresh, and
provider-free **Run it fresh** composition. The accepted implementation keeps
the #232 pagination/cursor boundary and #252 navigation-race guarantees, adds
no RAG/embeddings or durable recall model, and closes the Omnisearch product
lane without claiming deployment or tester exposure.
PR #316 subsequently completed issue #309's bounded run-dossier history and
effective-decision browser as `9aa209d4`. PR #318 made accepted-turn downstream
failures remain assistant-owned across reload and Retry as `f6d0981e`, followed
by the test-isolation checkpoint `1ed8d4f0`; issue #313 is closed. PR #315 added
the current-conversation activity rail as `6e20328c`. PR #317 then added one
central keyboard-shortcut registry, localized help overlay, and shared Recents
and Settings quick-jump behavior as `2ff6f3c6`, without changing Cmd/Ctrl+K
Omnisearch or the existing F2 rename binding. PR #324 aligned Recents hints with
that registry as `812c8fef`, and PR #311 then completed the typed, provider-free
current-data retest action as `51984a42`; issue #310 is closed.

The next integrated group adds bounded product and release-readiness work:
registered-only avatar themes through PR #312 (`40eba1f6`); public-alpha
capacity, capped-key, requested-access, approval-email, and hosted-proof
mechanics through PR #319 (`1c3775aa`); one shared frontend failure vocabulary
through PR #320 (`53c36d40`); auth copy, localized errors, and consistent card
containment through PRs #323, #325, and #328 (`c1a13949`, `05fbef06`, and
`403ea114`); and removal of the unavailable Release Notes row through PR #327
(`22bec7da`). Public account access remains explicitly disabled and founder
controlled despite the completed technical-readiness proof.

PR #329 added the durable backend/data conversation-activity and read-state
foundation as `8a5d621b`; PR #331 completed its chat/Recents frontend consumer
as `ec3a0a52`. The #329 migration is not claimed as hosted by these integration
merges. PR #326 closed issue #321 as `8e2a6217` with bounded
invisible/interactive CAPTCHA deadlines and an accessible localized challenge
dialog. PR #330 then completed deferred Guest bootstrap as `94476226`, keeping
anonymous identity and CAPTCHA acquisition behind the first submission while
preserving #331 activity ownership. Issue #314 remains a separate API evidence
gap discovered during typed-retest delivery, not unfinished #310 work.
PR #348 then self-hosted the canonical Inter and Space Grotesk variable fonts
as `38874bae`, removing the Google Fonts network dependency from build,
runtime, and provider-free browser QA. It added no environment variable,
deployment, API, schema, or migration requirement. The separate low-priority
fallback-order alignment remains issue #350.
PR #362 then repaired the sanctioned live-eval harness as `b2e8975c`, closing
issue #361: the explicit `ARGUS_EVAL_ENV_FILE` environment now preloads before
Argus imports, so calendar-aware live cases exercise real market sessions and
report `calendar_alignment` truthfully instead of failing 17 of 39 cases under
the leaked synthetic fixture calendar. The change is confined to
`tests/evals/` and added no environment variable, deployment, API, schema, or
migration requirement.
PR #355 then closed issue #336 as `c01d5730`: provider-resolved assets and
capital supplied in a terse opening turn survive into clarification and the
confirmation card, with post-LLM provider-context reconciliation removing only
stale asset blockers once every extracted traded-asset mention is accounted
for. Mixed, ambiguous, underfilled, overflow, and cross-class contexts stay
blocked. Accepted evidence includes the exact-head live-eval gate and a
founder-witnessed browser reproduction of the original G-01 transcript. It
added no environment variable, deployment, API, schema, or migration
requirement.
PR #353 then closed issue #337 as `7e4c58f8`: a rail needs-attention tick for
a clarification clears only when a later active confirmation is proven, via
backend-owned typed metadata (`strategy_path_id`, `source_result_run_id`, and
provenance-checked user values), to continue the same strategy path; unproven
or unrelated confirmations fail closed. The Guest rail keeps its single
legitimate completed-run tick visible. The first exact-head verification
failed and was repaired (e2e seed omitted real workflow metadata) before
acceptance; the final head passed the real local-Supabase Guest replay
independently. It added no environment variable, deployment, API, schema, or
migration requirement.
PR #357 then closed issue #340 as `9f97f1dc`: guest Omnisearch dossiers keep
Add/Edit decision actions visible and conversion-gate activation through a
typed `available | account_conversion_required` availability contract across
Python, OpenAPI, and TypeScript, then resume the exact run, decision state,
and note after conversion. The server remains authoritative and no guest
write path exists; the gated presentation activates only for clients
declaring the additive `dossier_decision_conversion_v1` capability header, so
legacy clients keep the prior stripped behavior. `docs/API_CONTRACT.md` and
`docs/api/openapi.yaml` changed in-PR with compatibility tests; it added no
environment variable, deployment, schema, or migration requirement. Issue
#341 is now unblocked for dispatch from the post-#357 integration head.
PR #356 then closed issue #343 as `48de2f3f`: menu-row hover/selected
highlights use one rounded inset-pill geometry across Settings, Profile,
Recents overflow, and chat-header menus, with destructive-red and neutral
action colors unchanged. Class-only change; hover evidence is committed
in-repo under `docs/reports/evidence/issue-343/`. The founder explicitly
overruled the absent on-PR Codex review after personal visual checks. It
added no environment variable, deployment, API, schema, or migration
requirement.

Current note: while the interim pivot is active, use
`docs/specs/private-alpha-interim-roadmap.md` as the founder-outcome and live-QA
slate, `docs/specs/private-alpha-next-roadmap.md` as the parent execution board,
and `docs/specs/private-alpha-next-decision-memo.md` as the strategic north
star. This document remains staging and branch-process context for
`codex/private-alpha-next`.
For release-gate and canary decisions, the decision memo is later-context only;
use the CI/CD SOTA spec, launch runbook, and release manifest template instead.

For smoke, canary, manifest, and deployment discipline, use
`docs/specs/private-alpha-ci-cd-sota.md`, `docs/PRIVATE_LAUNCH_RUNBOOK.md`, and
`docs/release-manifests/TEMPLATE.md`.

## Purpose

This document is the working source of truth for the next integration branch
after the private-alpha conversation trust checkpoint. It exists so every agent
starts from the current `main` reality, not from stale milestone debt.

The integration branch is a staging lane. It is allowed to collect reviewed work
before a future PR, but it is not a release branch and must not be merged or
deployed automatically.

## Current Release Gate Reference

The private-alpha promotion path still uses the CI/CD SOTA gate in
`docs/specs/private-alpha-ci-cd-sota.md` plus the operator instructions in
`docs/PRIVATE_LAUNCH_RUNBOOK.md`.

Before testers are invited, the release captain must prove:

- local smoke passed for the candidate SHA;
- `argus-api` and `argus-app` latest Render deploys are `live` at the candidate
  SHA;
- Render release config audit produced the expected `env_fingerprint`,
  `workflow_env_fingerprint`, `workflow_env_status=ready`, `workflow_task`, and
  `real_workflow_task`;
- warmup ran `workflow_proof` against the deployed `argus-backtests` workflow
  and emitted `workflow_runtime_provider_mode=live_provider` plus
  `workflow_runtime_proof=ready`;
- the `Private Alpha Canary` workflow or equivalent manual commands passed both
  English, Spanish, and provider-path canaries;
- the canary evidence artifact is retained as `private-alpha-canary-evidence`;
- a release manifest exists from `docs/release-manifests/TEMPLATE.md` and names
  SHA, env fingerprints, workflow env status, canary evidence, rollback target,
  approver, and backtest service mode.

Production deploys remain manual and founder-directed. No production deploy
happens from this branch unless the founder explicitly asks for a deploy check.

## Branch Model

Use this flow:

```text
main
  -> codex/private-alpha-next
       -> codex/<focused-high-leverage-slice>
       -> codex/<focused-low-risk-debt-slice>
```

Rules:

- `main` remains the clean release checkpoint.
- `codex/private-alpha-next` is the only integration staging branch.
- Codex worker branches start from `codex/private-alpha-next`.
- Create worker worktrees as siblings of the repo, never nested inside another
  Argus checkout. Nested worktrees can inherit a parent `.env` through dotenv
  upward search, which can silently turn mocked runs into live LLM/provider
  calls.
- Workers do not push directly to `main`.
- Jules work is decommissioned for the near term. Do not create or maintain
  `jules/**` branches, `codex/private-alpha-next-jules-intake`, or Jules intake
  PRs unless the founder explicitly reactivates that workflow.
- External async agents, if reintroduced later, must use a fresh
  founder-approved delegation model and must not push directly to
  `codex/private-alpha-next`.
- Codex reviews worker diffs before they are merged or cherry-picked into the
  integration branch.
- High-leverage work lands in `codex/private-alpha-next` first.
- Every slice ends with tests run, browser QA notes when relevant, known
  caveats, and a conventional commit.
- No production deploy happens from this branch unless the founder explicitly
  asks for a deploy check.

## Claude Review Workflow

Claude review is a bounded review aid, not an always-on push hook.

- During active development, run Claude Code CLI reviews on demand from the
  terminal against a bounded local diff before commit or before internal review.
- For promotion candidates, run Claude review as an explicit gate through a
  manual GitHub workflow, PR label, or review command after the lane is stable.
- Do not run Claude review automatically on every push. WIP branches should not
  accumulate noisy automated review comments before a lane is ready.
- Claude reviews must use the root `CLAUDE.md`, `AGENTS.md`, the canon docs,
  the active roadmap or lane spec, and the correct parent branch for the diff.
- Promotion-gate review focus is defined by the root `CLAUDE.md`. The
  integration workflow especially depends on regression detection,
  language-agnostic runtime-spine protection, modularity, API contract drift,
  frontend truth ownership, tests/browser-QA gaps, and release-gate discipline.

## Quarantine Reference Branches

These branches are intentionally preserved as reference material, not as merge
sources:

- `codex/private-alpha-next-quarantine-fc231e8`: preserves the broader P2
  direction and UI/product ideas, but its backend/runtime/data scope
  destabilized Argus. Use it only for product direction, UI salvage candidates,
  tests, and anti-pattern evidence.
- `codex/private-alpha-next-p2.1-quarantine`: preserves a narrower P2.1 slicing
  attempt around capabilities and indicator truth, but it again drifted against
  Argus runtime principles. Use it only for cautionary evidence, possible test
  cases, and scope lessons.

Do not broad cherry-pick or merge from either branch. Any salvage must be
rebuilt from current `codex/private-alpha-next` after a bounded roadmap slice is
approved.

## Current Closed Items

Do not reopen these as debt unless a new bug is reproduced:

- Fast GitHub CI baseline exists.
- Manual CD remains manual.
- Post-merge `argus-app` deploy smoke passed on `2fc4773`.
- Empty composer send tooltip exists.
- Composer caret, placeholder, and `@` button alignment were polished for the
  known empty/focused/clicked states.
- Restored archived/recently-deleted chats refresh without the original stale
  list smell.
- The old static `@` preview was replaced with provider-backed discovery plus
  the supported indicator catalog.
- Asset discovery quality is closed for this batch: provider and indicator
  search results rank exact ticker/alias matches first, common crypto/currency
  aliases replace the full typed phrase, repeated browser-session discovery
  queries use the local cache, and stale visible results cannot be selected
  while a newer query is loading.
- The misleading "share conversation id" pseudo-action was removed.
- Status/action parity is closed for this batch: confirmation, queued/running,
  terminal job, result-card, feedback, retry, and more-menu surfaces now follow
  one artifact lifecycle, internal Copy ID is hidden, and terminal job actions
  remain scoped to the durable artifact instead of transcript prose.
- Result voice cleanup is closed for this batch: Quick take and Explain result
  remain distinct, Explain result uses the deeper fact-grounded breakdown
  surface, and the old duplicate result-card Try next action remains removed.
  PR #304 adds the successor surface: capped typed rows under one localized Try
  next owner, with ordinary conversational turns still handled by the LLM chat
  brain.
- Local live QA proof was captured on 2026-06-11 in QA mode with real Supabase
  auth and API persistence: a GOOG buy-and-hold conversation rendered the
  confirmation card, completed result card, Quick take, and Explain result;
  no visible Try next, Quick Breakdown, Copy ID, or console/API regression was
  observed.
- Pre-merge internet readiness passed on 2026-06-11 for commit `dd65bf6`:
  Render `argus-api` deploy `dep-d8lj6ureo5us73fanrcg` and `argus-app` deploy
  `dep-d8lj8cjtqb8s738jf28g` both reached `live`; warmup passed in
  `real-workflow` mode; the authenticated canary conversation
  `d2fba747-bb93-45be-a48d-0fc944982423` completed durable job
  `93c89ccf-fb88-4ae2-ba93-4e0ab7b821c6` with run
  `e654ed96-efc0-44d6-86fe-033383c2d625`; and a deployed browser shell smoke
  rendered the unauthenticated front door without new console errors after
  reload.
- Post-merge main deploy passed on 2026-06-12 UTC for commit `f335d78`:
  Render `argus-api` deploy `dep-d8lkvl48aovs73dmc1dg` and `argus-app` deploy
  `dep-d8lkvnm7r5hc73d968k0` both reached `live`; warmup passed in
  `real-workflow` mode; the authenticated developer canary conversation
  `4ac80db0-5eb2-40cc-9a5b-a232c73ace01` completed durable job
  `2d65a145-94b8-404e-a949-2f0e0907d51a` with run
  `f17c8578-78b0-4bd6-82a2-24aaf17feff9`; and the canary confirmed the
  confirmation card, `run_backtest` action, async job/run result, LLM readout
  voice, and persisted messages.
- `docs/archive/LAUNCH_GATE_FINAL_CLOSURE_PLAN.md` is archived historical context.
- Adaptive result-chart range switching is complete at PR #264: viewport-only
  presets and Custom/Reset preserve canonical result truth and passed live
  EN/ES desktop/mobile QA.
- Account recovery and session controls are complete at PR #261: Settings ->
  Security is reachable and recovery, password change, and current/other/all
  session actions passed real-auth QA.
- Usage allowance truth is complete at PR #259: Settings -> Usage is reachable,
  hourly/daily message and simulation truth is backend-owned, accounting is
  durable and replay-safe, and exact-head real-auth/local-persistence QA passed.
- Executable capability truth is complete at PR #266 / issue #241: supported
  golden cross reaches the ordinary runnable path; recognized non-executable
  momentum breakout, news-sentiment rules, and future-performance requests stay
  non-runnable; compatible facts survive recovery; and only an explicit
  supported alternative plus a historical period creates a new confirmation.
  Final candidate `e10bdd2` passed founder-visible browser QA and landed as
  `bbd1d2b`.
- The Always Progresses continuity baseline is complete at PR #268: ordinary
  and action retries are durable, Run admission/reconciliation is exact-once,
  completed results remain immutable, and the bounded EN/ES browser matrix
  passed. It landed as `847c413b` and remains a standing quality bar rather
  than an open-ended repair program.
- Calendar-materiality classification is complete at PR #267: routine
  exchange-calendar alignment stays quiet while provider-coverage truncation
  receives one typed, reload-stable notice. It landed as `d6d1134`.
- The bounded chat-header and onboarding cleanup is complete through PRs #274
  and #275: owner controls follow the active chat, and the explicit
  private-alpha onboarding product has been removed. They landed as
  `291b58f7` and `88ae8c77`.
- Stale Run settlement is complete at PR #277 / issue #273: stale actions
  create no compute, settle to typed Updated truth, preserve the latest
  actionable confirmation, and remain stable after reload. It landed as
  `2d5a2b52`.
- Supported strategy-transition preservation is complete at PR #278 / issue
  #270: buy-and-hold can transition to a typed 50/200 SMA crossover while
  preserving assets, capital, dates, daily timeframe, benchmark, and modeled
  costs through confirmation, launch projection, and reload. It landed as
  `b80d95a2`.
- Modeled-cost preservation is integrated from PR #280 at `d16f7496`: asset,
  date, capital, and strategy edits preserve explicitly owned fee/slippage
  assumptions; card and natural-language edits share the canonical evidence
  boundary; explicit zero clears costs; and confirmation, launch, and reload
  agree. Issue #271 is complete; PR #280's bounded same-chat integration
  journey is the closure evidence. Any later repetition belongs to promotion
  qualification, not issue acceptance.
- Grounded Discovery Search v1 is integrated from PR #276 at `c212107a`.
  Explicit peer/category discovery has one typed route, bounded source-backed
  Search, resolver-validated candidates for equity, crypto, and currency-pair
  assets, persisted EN/ES rendering, honest kill-switch recovery, and
  operational cost evidence. Search is part of the normal Argus shape and
  defaults on; explicit `false` is the emergency kill switch. Issue #244 stays
  open because one comparison phrasing missed the typed route in the sanctioned
  eval; that gap, Render configuration, and an exact-SHA canary are required
  before tester exposure.
- Chat next-move presentation is integrated from PR #281 at `8fde4ac1`, with
  resolver-owned discovery selection identity added by PR #287 at `ea2b3f35`.
  Clarify options, supported follow-ups, and discovery candidates render as
  stacked rows under their owning message; verified candidate reasons remain
  visible; and persisted discovery evidence opens in a source-safe panel
  without another provider call. The shared in-flight lock protects the
  composer and rows in one tab. A selected candidate now carries the identity
  the resolver already verified as a normal asset mention, including across
  durable Retry, without becoming a prepared execution action. Remaining work
  is backend concurrent-turn admission, honest live progress, guest discovery
  allowance, and any general assumption carry-forward beyond selected identity.
- Candidate/entity corroboration is integrated from PR #287. A source-named
  entity must agree with the resolved candidate, preventing unrelated
  cross-class ticker collisions such as a gold miner for a Tron request.
  Crypto-exposure vehicles are currently filtered with true collisions; #244
  owns the deliberate product design needed to surface them safely.
- Guest access is integrated from PR #279 at `53e812e9`: verified anonymous
  identity, one temporary owner-scoped workspace, fixed lifetime allowances,
  exact-once settlement, one simulation, conversion/claim, cleanup, Guest
  shell, capability gates, and privacy-safe funnel evidence. Guest defaults on
  with explicit-off rollback; public-account access remains separately off.
  Issue #293 is closed with no-defect evidence after one real guest session
  crossed the one-hour JWT boundary without losing its conversation or
  workspace. Hosted configuration, canary, and public traffic remain later
  release gates.
- Backend verification is provider-free by default after PR #282 at
  `059f8e82`: root test fixtures force synthetic market data and keep provider
  credentials explicitly empty so dotenv cannot silently restore them. Both
  alpha API suites are part of `backend-checks`.
- Backend CI is directory-complete after PR #286 at `75e87206`: the gate runs
  the full `tests/` tree, the stale pure-approval fixture is corrected, and a
  guard test prevents the workflow from returning to a curated file list.
  Issues #283 and #284 are closed. This changes verification coverage, not
  runtime behavior.
- Bounded database pagination and search are complete at PR #285 / issue #232:
  Conversations and Messages use stable keyset reads, completed-result
  projection uses bounded batches, and History and Omnisearch/Idea Ledger
  bound their source candidates while preserving public cursor compatibility,
  ordering, ownership, ranking, exact ledger groups, and canonical artifacts.
  It landed as `7b7920bb`. The founder-accepted sparse/deep/final History Run
  scan exception remains documented: returned candidates and normal measured
  distributions are bounded, while a maintained History read model is deferred
  scale architecture.
- Browser-session transcript reuse and navigation race safety are complete at
  PR #299 / issue #252. Fresh and stale conversations render immediately from
  the bounded user-and-conversation cache; true cold misses replace the prior
  transcript with a delayed truthful retrieval state; retired loads cannot
  commit over the latest destination; and destination-owned failure/Retry,
  scroll restoration, auth clearing, EN/es-419, keyboard, and reduced-motion
  behavior passed exact-head browser QA. It landed as `f368febb`. Profiling did
  not justify prefetch or virtualization, so neither was added.
- Comparison grounding and discovery-act continuity are complete at PR #300 /
  issues #292 and #296. Company names reach the provider-backed resolver,
  unsupported named comparison targets reconcile to the class default with a
  localized pinned disclosure, and a pending confirmation cannot capture a
  typed discovery ask. It landed as `c21f842f`.
- Progressive Recents disclosure is complete at PR #302 / issue #245. Recents
  uses the bounded chat-only conversation endpoint, caps each loaded unpinned
  time group at five until explicitly expanded, and loads older pages only
  after an accessible single-flight action. It landed as `928dcdbb` while
  preserving PR #299 switching, race, selection, attention, and reload truth.
- Benchmark price-coverage reconciliation is complete at PR #303 / issue #301.
  An explicit provider zero-bars response for a catalog-valid benchmark
  reconciles to the class default at card time with the existing localized
  disclosure; transport failures remain owned by the run path. It landed as
  `da9f8500`.
- Result and recovery surface ownership is complete at PR #304 / issue #249.
  Quick take owns the glance readout, Explain result owns grounded
  comprehension, stacked typed rows own Try next, and retryable composition
  failures render distinctly and resolve in place. Durable job projection,
  reload, non-repetition, accessibility, and English/Spanish parity were
  included in the accepted lane evidence. It landed as `59a274c3`.
- Fact-preserving recovery is complete at PR #288 / issue #272: stale or
  failed actions restore the latest usable canonical confirmation or result
  anchor, preserve assets, capital, requested/effective dates, daily timeframe,
  benchmark, rules, and modeled costs, and ask only for genuinely missing
  fields. Prior results remain immutable, later explicit edits supersede
  recovery state, and recovery creates no duplicate job, Run, or usage.
- Requested/effective period truth is complete and issue #251 is closed. PR
  #262 established the shared coverage contract, PR #267 classified quiet
  calendar alignment versus material provider truncation, and PR #268
  preserved the resulting artifact through continued conversation and reload.
  PR #297 completed the trajectory-ledger reconciliation as `09044231`,
  removing stale #241/#251 masks while preserving #239's exact current
  failures. Issue #243 is closed; promotion evidence remains solely with #233.
- Hosted cost-ledger visibility is repaired and issue #246 is closed. The
  existing `20260702000001_add_cost_ledger_entries` migration was applied
  directly to the hosted Argus Supabase project with matching migration
  history. RLS and service-role-only append/read privileges were verified; no
  application commit, deploy, or PR was required. See
  `docs/reports/issue-246-cost-ledger-closure-evidence.md`.
- Structural OpenAPI compatibility is complete and issue #234 is closed. PR
  #289 landed as `8a66f0ba`: generated FastAPI structure remains authoritative,
  the checked artifact is reproducibly generated, and CI enforces normalized
  public path/method, parameter, request/response schema, required-field, enum,
  exclusion, and server-prefix compatibility. Both PR and post-merge CI passed.
  PR #290 then landed the compatible request-size and correlated RFC 9457
  failure boundary as `b073b1a0`; issue #235 is closed.
- Chat request and correlated-failure ownership is complete at PR #290 /
  `b073b1a0`. Declared and chunked bodies enforce the same early ingress
  ceiling; typed field/list/depth/serialized-size limits fail before expensive
  work; unexpected exceptions preserve CORS and return sanitized RFC 9457 JSON
  with one header/body/log request id. Rejection isolation, exact-boundary
  acceptance, canonical SSE stability, OpenAPI regeneration, and structural
  compatibility are directly tested. PR and post-merge CI passed.
- Guest grounded-discovery metering is integrated from PR #291 at `f1e65dde`.
  Guests receive two searches per visitor per day, renewing a temporary
  workspace does not reset the allowance, and a configurable global daily
  ceiling bounds total attempted Search spend. The additive
  `visitor_usage_counters` migration is integrated but still requires
  application to each hosted target during promotion. Issue #244 remains open
  for the broader discovery activation and accepted follow-up register.
- Discovery continuity PR #295 is integrated at `8f17a45e`. Resolver-verified
  candidate rows are now the default path; paid Search is reserved for
  explicit requests or current-fact needs. Typed retry and fair charging,
  async provider offload, incomplete-rule copy, and EN/es-419 J1/J2 continuity
  are proven.
- Discovery and Guest continuity PR #298 is integrated at `ba0aa2f6`.
  Search and verification emit truthful live progress, each discovery row owns
  its citation action, and Guest message/simulation limits settle against a
  privacy-safe visitor/day identity across temporary-session renewal. This
  completes the planned second pass, not promotion: hosted migrations,
  configuration, and exact-SHA canary gates remain open.

## P0 Reintegration Checkpoint

The clean reintegration strategy is now part of the process model:

- `codex/private-alpha-next` remained the clean integration gate.
- contaminated autonomous work was preserved under
  `codex/private-alpha-next-quarantine-fc231e8` for read-only reference.
- P0 continuity was rebuilt as a focused clean slice at `bbd9f10`.
- quarantine commits may be inspected for ideas, tests, and failure evidence,
  but runtime code should not be broadly cherry-picked.

## Remaining High-Leverage Work

Codex should own or closely supervise this:

1. **Finish the remaining interim product outcome and activation gates**
   - Grounded discovery now includes the PR #295 continuity pass at
     `8f17a45e`, PR #298's second pass at `ba0aa2f6`, PR #300's comparison
     grounding and discovery-act continuity at `c21f842f`, and PR #303's
     benchmark coverage reconciliation at `da9f8500`. Do not rebuild the cheap
     verified rows, Search-exception policy, live progress, citation ownership,
     visitor/day Guest settlement, or comparison corridor. Keep #244 open only
     for the accepted exposure-vehicle product decision and the hosted
     migrations, Render configuration, and exact-SHA canary.
   - Full Omnisearch may now build against the accepted grounded-discovery
     contract. Its owner must reconcile onto this checkpoint and must not
     invent discovery truth or implicitly activate Search.
   - Always Progresses is delivered and now acts as the quality bar for these
     slices; it is not the next broad pillar to redispatch.

2. **Advance bounded continuity follow-ups by owner**
   - #269 landed through Guest PR #279 at `53e812e9` and is closed. Do not open
     a second runtime lane.
   - #271 landed through PR #280 at `d16f7496` and is closed. #272 landed
     through PR #288 at `9f3453a3` and is closed; do not open another modeled
     cost or canonical recovery lane without a new reproduction.
   - #273 is closed at `2d5a2b52`. #249 is closed through PR #304 at
     `59a274c3`; Quick take, Explain result, typed Try next rows, and
     recoverable failure now have distinct owners while preserving Guest
     hydration, discovery rows, conversation switching, and bounded Recents.
     No artifact-presentation follow-up remains without a new reproduction.
   - The exact handoff table lives in
     `docs/specs/private-alpha-interim-roadmap.md`.

3. **Evidence-aware idea loop source thesis**
   - Perplexity, citations, research-to-testable-hypothesis loops, inbox briefs,
     saved research, and monitoring remain design/reference material until the
     active roadmap starts a bounded slice.
   - `docs/specs/evidence-aware-idea-loop.md` is preserved in `docs/specs/` as
     the source thesis that informed
     `docs/specs/private-alpha-next-decision-memo.md`. It is not the active
     sequencing document.
   - Use the decision memo for current strategy and
     `docs/specs/private-alpha-next-roadmap.md` for current execution. This
     branch may refine the source thesis, but it must not implement the
     evidence-aware idea loop without explicit approval.

## Integrated Guest Checkpoint And Later Promotion Gates

PR #279 landed on `codex/private-alpha-next` as `53e812e9`. The section below
preserves its migration, ownership, rollback, and later promotion contract; it
is not an active worker-branch instruction.

Migration order is fixed:

1. `20260724101324_add_guest_workspaces.sql`
2. `20260724102309_add_guest_session_allowances.sql`
3. `20260724102645_guest_conversation_and_cleanup.sql`
4. `20260724110000_restore_settle_only_usage.sql`
5. `20260724110100_serialize_guest_feedback.sql`
6. `20260724110200_align_guest_cleanup_candidates.sql`
7. `20260724211312_guest_workspace_handoffs.sql`
8. `20260724223000_replace_guest_conversation.sql`
9. `20260724230000_harden_guest_public_boundaries.sql`
10. `20260725220148_fix_expired_guest_complete_graph_cleanup.sql`
11. `20260726001954_isolate_guest_cleanup_candidates.sql`
12. `20260726001955_enforce_guest_terminal_message_limit.sql`
13. `20260726002158_respect_permanent_conversation_ownership.sql`
14. `20260726014754_isolate_poisoned_guest_orphans.sql`
15. `20260726185021_harden_guest_lifecycle_ownership.sql`
16. `20260727230000_add_visitor_usage_counters.sql`
17. `20260728120000_visitor_keyed_guest_settlement.sql`

The earlier message-settlement and atomic-backtest-admission migrations remain
prerequisites and must retain their existing order. Integration must reset a
fresh local database and rerun the zero-skip guest Postgres/Auth matrix before
promotion. Migration 16 adds an opaque, visitor-owned daily discovery counter
and global attempted-search bucket. Migration 17 re-keys Guest message and
simulation settlement to the same privacy-safe visitor/day boundary. Both must
be present before Guest grounded discovery is exposed.

The conversion contract has two owners:

- provider-native anonymous-to-permanent linking keeps the same Auth UUID;
- an existing registered account claims the complete guest graph through the
  short-lived, email-hash-bound, single-use server handoff. Login completes
  the claim before returning its session and can reconcile one ambiguous
  same-destination response without repeating transfer.

Neither path copies visible prose in the browser or merges guest lifetime
counters into registered hour/day counters. Guest server/bootstrap and
presentation flags default on as emergency kill switches. Rollback is flags
first: explicitly disable the frontend guest presentation, then server guest
bootstrap; keep public-account access false. Do not roll back by deleting guest
rows or reverting already-applied migrations.
The server guest flag is the creation gate: disabling it stops new anonymous
sessions while existing verified guests drain to conversion, fixed expiry, or
transactional cleanup.

Always Progresses, Grounded Discovery, modeled-cost preservation, Guest, and
visitor-owned Guest discovery metering are reconciled at the integration
checkpoint. Before promotion to `main` or public traffic, apply migrations
through `20260728120000`, configure
`ARGUS_DISCOVERY_GLOBAL_DAILY_CEILING`, and complete
`docs/GUEST_PUBLIC_LAUNCH_SAFETY.md`: branch-deployed exact-SHA canary, hosted
anonymous Auth and server-validated Turnstile, trusted-origin/rate-limit
verification, hard provider budget, scheduled cleanup ownership, first-traffic
monitoring, release manifest, and founder traffic/cost approval.

## Historical Evidence Retention

Completed specs, plans, and browser reports remain in place when GitHub issues,
PR descriptions, or closure ledgers link to their paths. Their status banners
mark them as completed execution records or superseded observations. Moving
those files into `docs/archive/` would break evidence lineage without reducing
active ambiguity.

The active command sources are only the interim roadmap, the parent roadmap,
the decision memo, and this integration-process document. Completed
Always Progresses plans and dated reports are regression evidence, not active
dispatch instructions.

## Known Non-Blocking Debt

Track these as future validation slices, not blockers for the current main
deploy:

1. **Composer paste and long copied-result handling**
   - Live observation on 2026-06-11: `Copy Plain Text` can copy a non-empty
     result breakdown into the Codex browser tab clipboard and show `Copied`,
     but pasting back into `ChatInput` can fail when the browser does not
     support or allow the current `document.execCommand("insertText")` paste
     path after the paste handler calls `preventDefault`.
   - Product concern: long copied result text can overwhelm the persistent
     composer if pasted inline. Frontier chat products often promote long
     copied content into file-like attachments, but Argus should not fake
     `.txt` attachments while the current OpenRouter-backed chat path does not
     support text-file inputs.
   - Future validation should confirm normal-browser versus Codex-browser
     behavior, define an Argus-scale long-text paste treatment such as capped
     inline paste, paste preview, or explicit large-text handling, then replace
     the `execCommand` paste path with a modern contenteditable or state
     insertion path and add Bun plus browser QA.
   - This is not ready for delegated implementation until the product behavior
     is scoped. A future scout may later run a read-only validation inventory or
     help draft a GitHub task prompt if external-agent work is reactivated.

## Deferred External-Agent Scout Candidates

External async-agent work is decommissioned for the near term. If the founder
reactivates it later, these are the only categories that should be considered
for bounded scout or janitor work:

- Docs classification proposals: canon, active plan, historical evidence,
  archive candidate.
- Dead-code candidate inventories for active-tree code.
- Large-file inventory with proposed extraction seams, without performing broad
  refactors.
- Small test coverage additions around already-stable behavior.
- i18n/key consistency reports and narrow copy fixes.

External agents must not touch:

- Supabase migrations, RLS, auth, or service-role behavior.
- Render config, deploy scripts, workflow env sync, or production env names.
- `src/argus/agent_runtime/stages/interpret.py` or runtime routing without
  explicit approval.
- LLM provider plumbing, OpenRouter profiles, Perplexity integrations, or model
  fallback chains.
- Backtest engine execution semantics.
- Frontend state that invents backend facts.

## Documentation Hygiene

Use these classes:

- **Canon**: `docs/PRODUCT.md`, `docs/ARCHITECTURE.md`,
  `docs/API_CONTRACT.md`, `docs/DATA_MODEL.md`,
  `.agent/designs/argus/DESIGN.md`, and `AGENTS.md`.
- **Active specs**: current milestone docs, including this file and approved
  future specs.
- **Historical evidence**: completed launch/milestone closure reports and
  browser/canary evidence.
- **Archive**: stale plans superseded by merged implementation or newer specs.

The former interim issue dependency map and Wave 0 plan are archived at
`docs/archive/private-alpha-interim-issue-roadmap-2026-07-21.md`. The active
interim roadmap now contains only founder outcomes, retained decisions,
delivery discipline, and current completion truth.

Do not delete historical docs casually. Prefer adding a short status banner that
points to the active source of truth, then archive only after review.

## Verification Expectations

For docs-only changes:

- `git diff --check`
- link/path sanity check for referenced docs

For frontend changes:

- focused `bun test` suites for touched behavior
- `cd web && bun run build`
- browser QA in the Codex browser for visible behavior

For backend/runtime changes:

- focused pytest suite for touched behavior
- `poetry run ruff check src tests workflows scripts`
- local or live smoke only when the change affects runtime/deploy behavior

## Stop Conditions

Stop and ask before proceeding if a task:

- requires new Supabase schema, RLS, or production data writes;
- changes runtime routing or result readout provenance;
- changes Render service topology, env var names, or deploy behavior;
- starts implementing Perplexity Research Lab features;
- needs a product decision about public sharing, privacy, or revocation.
