# Next-Cycle Product Roadmap

Feature triage for the cycle after the 2026-08-05 production promotion.
Founder-ranked 2026-08-06. Companion board:
[`next-cycle-stabilization-roadmap.md`](next-cycle-stabilization-roadmap.md).

## Conflict resolved

The 2026-08-01 lock said the 2-4 week guest-canary signal window should rank
A1b/A2/A4-class work by observed usage rather than planning order. The founder
resolved this in practice on 2026-08-06 by driving personalization memory to
completion ahead of that window. Signal-first still governs the A1b/A2
product-memory arc below; it no longer governs personalization memory.

## Ranked

1. **Personalization memory — built, gated, in review (PR #386).** The complete
   loop now exists behind a default-off flag, exposed only to `admin` and
   `developer` roles on the private alpha allowlist, never the public. Argus
   proposes a memory, the user confirms, and confirmed memories reach
   post-interpretation surfaces only. Users can inspect, see why something was
   stored, edit, delete, disable, reset, export, and run temporary chats where
   nothing is remembered. Guests are denied before any side effect, including
   through conversion.

   Locked during this cycle:
   - **Mem0 is the retrieval provider**, sitting behind the existing
     `MemoryProvider` protocol. Not wired yet: recall is token matching until it
     lands, which is a quality upgrade rather than a missing feature. Two open
     questions before wiring: cloud versus self-hosted (a privacy decision, the
     decision memo leans self-hosted on Argus-owned Postgres), and disabling
     Mem0's automatic fact extraction, which conflicts with section 12.3's
     assisted-not-automatic rule and the never-store rule for raw conversation.
   - **Sensitivity is backend-owned.** Clients cannot supply a claim; the API
     rejects one at the contract. Broker credentials and raw conversation are
     categorically never stored regardless of user confirmation.
   - **First opt-in scope stays "remember saved decisions"** per section 15.3.
     The other three categories exist in code and stay closed.

   Gating this: PR #307 carries the same persistence tranche that #386
   fresh-ported, so #307's open alignment question governs both. Public
   exposure additionally needs the roadmap milestone opened and real legal
   review of terms and privacy per Risk 6.

2. **Mobile readiness decision spike.** Still the gate on the public exposure
   window: the founder will not share Argus publicly while the PWA layout fails
   on phones, yet the product is the public signal engine. Timeboxed spike,
   three options with costs: responsive-PWA polish (fastest unlock, the app is
   already strong on desktop), a native shell reusing the polished PWA, or real
   native iOS and Android. Deliverable is a mobile-layout audit plus an options
   memo.

3. **Product memory** — the A1b (linked versions) and A2 (comparison)
   compounding loop. Distinct from personalization memory and not a dependency
   of it: product memory is canonical Idea/IdeaVersion/EvidenceArtifact/
   DecisionNote truth, personalization memory is an opt-in sidecar that may
   reference it but never becomes an alternate source of truth. Still ranked by
   the signal-first lock.

4. **Cost accounting for routine dev/ops work.** Extend cost-ledger discipline
   to canary runs, warmups, eval sweeps, and lane live-QA, attributable per key
   once the three-key routing lane ships (stabilization board, Tier 2).

5. **Sharing** — public evidence excerpts. Scope still to be shaped: what a
   shared result exposes, revocation, privacy posture.

6. **Broker/export handoff.**

## Brainstorm-first (recorded, not scheduled)

- **Recency-aware suggestion context** — suggestions must weight the latest run
  and never re-suggest the asset just tested. Now partly reachable:
  personalization memory is the mechanism that makes Try-next and discovery
  rows personal rather than generic, and it is the same macro that connects to
  the #384 peer-recommender lane. Worth scoping once #386 is in.
- **Guided first-run tour** — a fluid one-click layer, not a wizard.
- **Allowance brainstorming** — which capability boundaries become tiers once
  product-market fit appears.
- **Run-action token chip** (#379) — localized transcript token, no message
  metering, typed equivalent.
- **#363 current-data window** — the remaining design questions beyond what PR
  #363 ships: clamp-to-earliest on the start edge, disposition-aware Retest,
  and tier-aware policy-owned values.

## Standing Design-Only carryovers

Memory and data controls beyond what #386 ships; voice-to-composer STT; broad
Research Lab work bounded to source-backed freshness; native mobile now lives
in item 2's decision rather than as a parked line.
