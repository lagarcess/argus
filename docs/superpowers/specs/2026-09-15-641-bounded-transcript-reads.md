# Bounded saved-transcript reads for #641

Founder-locked 2026-09-15 after PR #635 landed.

## Why

Long conversations must stay responsive when open on another device. PRODUCT.md's
Speed Matters and Continuity standards require reply checks to avoid rereading
unchanged history. Issue #641 identifies the full-pagination cost in #635.

## Locked decisions

1. Pending-reply checks use the existing owner-scoped messages API with the last saved message as an
   inclusive anchor. Follow cursors only through the new suffix, never old pages.
   Ordinary activity refreshes retain full-history reconciliation.
2. Keep the raw API snapshot alongside its derived display projection. Merge a
   returned suffix into that snapshot and use the canonical projection, preserving
   effects on earlier cards. Unchanged checks perform no projection or UI apply.
3. Retain unchanged display message objects when projecting a changed snapshot.
4. Preserve the existing timeout, cancellation, anchors, scroll, and sender guards.

## Reserved scope

#640 remains deferred. No pre-admission freshness redesign, paid runs, model text,
DB/migration, render.yaml, or release-contract changes. No new API fields.

## Contract gates

No API or data model shape changes. Document usage of the existing inclusive
anchor in the evidence report; existing owner scoping and cursor ordering apply.

## Execution contract

One branch from integration 538aec3a9947caf8eb290a1f87551a2212496d44 and one PR
against codex/private-alpha-next. Prove request counts on a 1,000-message fixture,
no apply when unchanged, suffix pagination, full-context projection, and timeout
cancellation. Run the existing 19 accepted provider-free browser cases in both
languages plus long-history cases. Commit red/green evidence and revalidate at
head. Run frontend checks, mocked evals, and merged-tree modularity.

Open and keep the PR ready. Follow the founder's latest review loop: inspect each
finding at head, fix confirmed ones with tests, decline wrong ones with reasons,
reply/resolve, push, wait for green CI, and request Codex again until clean at head
with zero unresolved threads. Stop there. Founder owns merging.

## Stop conditions

Escalate if existing API ordering/anchors cannot safely support suffix reads or
if a required correctness fix needs a forbidden backend/contract change. Never
stash or weaken acceptance checks.

## Sources

- docs/PRODUCT.md: Speed Matters and Continuity
- docs/API_CONTRACT.md: GET /conversations/{id}/messages
- docs/specs/argus-grounded-finance-roadmap.md: second-tab replies
- Issues #598, #641 and PR #635; #640 explicitly deferred
