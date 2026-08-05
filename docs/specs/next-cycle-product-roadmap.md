# Next-Cycle Product Roadmap (DRAFT — founder ranks final)

Feature triage for the cycle after the 2026-08-05 production promotion.
Companion board:
[`next-cycle-stabilization-roadmap.md`](next-cycle-stabilization-roadmap.md).

**One conflict the founder must resolve first:** the 2026-08-01 locked
decision says the 2-4 week guest-canary signal window ranks A1b/A2/A4-class
work by observed usage, not planning order. Prioritizing product memory now
(item 2) overrides that lock. Both positions are the founder's own; the
triage session picks one consciously.

## Proposed order

1. **Mobile readiness decision spike.** The founder will not share the app
   publicly while the PWA layout fails on phones (sidebar, omnisearch
   presentation, oversized pills — real estate the mobile viewport cannot
   afford), yet the product is the public signal engine. That makes mobile
   readiness the gate on the exposure window itself. Timeboxed spike, three
   options with costs: (a) responsive-PWA polish (fastest unlock; the app is
   already beautiful on desktop web), (b) native shell (Capacitor-class)
   reusing the polished PWA, (c) legit native iOS + Android (a different
   product commitment). Deliverable: mobile-layout audit plus an options
   memo; founder picks the lane.
2. **Product memory** — the A1b (linked versions) + A2 (comparison)
   compounding loop, subject to the conflict note above.
3. **Personalization memory** — incubation lane continues
   (`personalization-memory-contract.md` is source of truth; PR #307 is the
   persistence checkpoint). Founder direction today: prioritize within this
   board rather than ignore.
4. **Cost accounting for routine dev/ops work.** Extend the cost-ledger
   discipline to development surfaces: canary runs, warmups, eval sweeps,
   lane live-QA — attributable per key once the three-key routing lane
   (stabilization board, Tier 2) ships. Absorbs the deferred eval-cost /
   open-source eval-harness item.
5. **Sharing** — public evidence excerpts (from Design-Only; scope still to
   be shaped: what a shared result exposes, revocation, privacy posture).
6. **Broker/export handoff** (from Design-Only).

## Brainstorm-first items (recorded, not scheduled)

- **Guided first-run tour** (alpha-user suggested): fluid one-click layer
  that makes Argus aware of where it leads you — not a wizard. Worth-it
  brainstorm before any build.
- **Recency-aware suggestion context**: suggestions must weight the latest
  run (never re-suggest the asset just tested). Macro spans chat context,
  product memory, and personalization memory.
- **Allowance brainstorming session** (founder-led): which capability
  boundaries become tiers/plans once product-market fit appears.
- **Run-action token chip** (#379, closed-parked): localized transcript
  token, no message metering, typed equivalent — founder design discussion
  first.
- **#363 current-data window design** — pending founder lock; recorded
  context: Alpaca/Kraken 1D bars, anchor-start + extend-end retest
  semantics, clamp to earliest available, never dead-end, tier-aware
  policy-owned values.

## Standing Design-Only carryovers

Memory/data controls; voice-to-composer STT; broad Research Lab work
(bounded source-backed freshness only, per the A4 arc); native mobile is now
item 1's decision rather than a parked line.
