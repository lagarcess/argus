# Cross-platform chart validation prototype

Founder-assigned September 28, 2026. Rendering and interaction proof only.

## 1. Why

PRODUCT section 4 and MVEE section 2 require understandable phone experiences,
visible assumptions and separate currencies. Validate the chart direction in
open PR #727 before it spreads: Swift Charts, Vico candidate, Lightweight Charts.

Original fetched integration: `codex/private-alpha-next` at
`4b84e054a0d8079b21f38784335ad3241809b4cd`.
Worker: `codex/chart-validation-prototype`, isolated worktree `2825`.
Inspected open, unmerged references: #727 `802b82306cc29373d7e4dce44c17d33adb243e30`,
#729 `b422d986bcf068b56e07283481de373ba8e30dc0`,
#730 `edc43cb7961b68e7ca699a4101510a79667d1a7f`.

## 2. Locked decisions

1. Own only `prototypes/chart-validation/`, this spec and
   `docs/reports/evidence/chart-validation/` plus the bounded report.
2. Standalone iPhone Swift Charts, Android Compose Vico and browser Lightweight
   Charts projects. Inspect official documentation and actual toolchains before
   pinning versions. Reuse foundation setup as reference, never merge those PRs.
3. One committed language-neutral JSON fixture bundle. Reuse the canonical
   backtest `chart.series` `{time: YYYY-MM-DD, value: number}` and currency
   semantics. The envelope for projected series and explicit gaps is proposed,
   not a new production contract. No client computes financial facts.
4. Fixture dates are civil Gregorian dates, displayed in UTC without shifting
   the date with device timezone. Currency amounts are major units, two display
   decimals; USD and DOP remain separate. Null values explicitly mean missing.
5. Draw separate actual and projected series, with text legends and distinct
   stroke styles. Break paths at missing points; linear segments, no smoothing.
6. One card in a vertically scrollable page, controls for scenario, language and
   Light/Dark/System, a stable date/value readout and previous/next/reset controls.
   No precision drag is required to inspect any point, including missing points.
7. Horizontal gestures select nearest dated sample (ties choose earlier).
   Vertical gestures scroll the page. Release retains the last selection;
   cancellation restores the selection before dragging; reset clears it. Changing
   scenario clears selection. Empty/single-point cases are first-class.
8. Synthetic fixtures cover flat/jump/gap/negative, empty, singleton, long series,
   fixed-capital and recurring-contribution shapes. Dated contribution facts are
   authored in the fixture, not inferred from a change in chart value.
9. Measure local rendering/interaction performance; identify simulator/emulator
   evidence explicitly. No physical-device or minimum-OS certification by inference.

## 3. Reserved / parked scope

Production screens, account/chat/forecast logic, navigation/shell files, shared
build configuration, APIs, persistence, native auth, providers, live data,
financial calculations and backtest execution are excluded. No Docker restart,
keys, paid calls, hosted writes, merge or deployment. Dedicated devices where
practical; coordinate reservations with native-auth verification.

## 4. Contract gates

No production API/data contract changes. The proposed fixture contract lives at
`prototypes/chart-validation/CONTRACT.md`. Foundation toolchain provenance and
official sources belong in platform READMEs and the evidence report. A concrete
incompatibility is reported rather than changing the approved library direction.

## 5. Execution contract

One labeled prototype PR targeting `codex/private-alpha-next`. This spec is its
first commit. Bounded platform workers own only their implementation/test/evidence
subtrees; release captain owns fixtures, integration and final review.

Proof: fixture invariants, platform build/tests, bilingual/theme screenshots,
scrub/endpoints/gaps, scroll coexistence, accessible controls, release/cancel/reset,
and measured performance on local iPhone/Android/browser. Commit runnable commands
and durable artifacts with exact source identity. Evidence-only commits require
explicit source-tree revalidation. Report each platform adopt/change/reject with
remaining limitations; incomplete proof cannot be called READY.

Fetch integration again, assess semantic overlap by owner/contract/state/tests,
merge one way if advanced, revalidate affected evidence and merged-tree modularity.
Apply argus-review-exhaust: validate findings, fix in scope, reply/react/resolve,
finish on clean latest-delta review, zero unresolved threads and applicable green
CI. No unchanged-head review repeats. Founder owns merge/deployment.

## 6. Stop conditions

Report inability to compile the approved library against actual toolchains, missing
local device runtimes, or a need to alter another lane's shared build/shell. Do not
substitute libraries, claim unrun device evidence, or expand into financial logic.
Continue independent authorized platform work while an environmental gate is blocked.

## Sources

Argus: AGENTS.md; PRODUCT.md; DOCUMENTATION_AUTHORITY.md; MVEE;
ARCHITECTURE.md and #727 chart direction; API_CONTRACT.md result chart and display
date sections; DATA_MODEL.md backtest_runs; DESIGN.md; #729 and #730 setup.

Official library documentation must be recorded per platform during verification.
The standalone envelope and selection lifecycle above are prototype choices,
not claims about an existing production contract.
