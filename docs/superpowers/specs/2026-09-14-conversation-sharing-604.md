# Sharing selected answers in the conversation

Founder-locked 2026-09-14, adapting the existing receipt feature after #604.

## 1. Why

Argus PRODUCT.md makes conversation the primary workspace. The grounded-finance
roadmap's Sharing lane makes a useful answer something its owner can send.
The promotion walk found that ordinary completed answers could not be selected.

## 2. Locked decisions

1. Select question plus final answer inside the conversation. Backtests,
   research, calculations and plain answers qualify; confirmations and
   clarifications do not. Keep Select all, owner note and exact preview.
2. Owner selection and the exact preview are the privacy boundary. Remove
   credential-shape scanning, question/answer caps, source requirements and
   link/source matching, and memory/degraded-answer refusals. Retain exact
   matching against private Argus user, conversation, message, job and artifact
   identifiers and closed projections that add no account data or other turns.
3. Diagnose and fix the completed backtest judgment using canonical completion
   truth. Do not merely bypass it.
4. Keep frozen snapshots, registered owners, /r/<id>, Settings Shared links,
   revoke, tombstones, delete cascade, noindex and rate limits. Preserve sources
   and dates where present. Reuse existing receipt records and table.
5. Use shared responsive primitives. Sheets belong below 720px; 1024px is for
   the run dossier. AdaptivePanel still uses 1024px at the integration base;
   report that dependency and leave the shared component untouched in this lane.
6. Sharing flags remain false in render.yaml and the release profile. Enable
   only in local fixtures. Prefer no migration; report any widened kind check.

## 3. Reserved scope

No provider/model/runtime redesign, memory subsystem changes, new sharing
service, public fork or continuation state, hosted migration, merge or deploy.
No shared AdaptivePanel change. No live answer without an approved spend cap.

## 4. Contract gates

Update docs/specs/conversation-sharing.md, supersede section 7.5 of the original
receipt spec, update API_CONTRACT.md and DATA_MODEL.md, and regenerate OpenAPI
if schemas change. Backend and web share a closed versioned payload contract.

## 5. Execution contract

One PR targeting codex/private-alpha-next, closing #604. Original fetched base:
`d788449385ec93e92609b4692aa0fe8c1981ab58`.

Scripted regression tests must fail on that base and pass on the final code for
all #604 cases. Verify retained private-ID, exact-preview, ownership, revocation
and deletion behavior. Use seeded or recorded conversations for EN/es-419
browser evidence at 390, 719, 720, 1023, 1024 and 1280px, and signed-out pages
at 390/1280px. Commit durable evidence. Record the AdaptivePanel discrepancy
honestly rather than claiming those intermediate widths meet the contract.

Reconcile current integration one-way, audit semantic overlap, run the merged
modularity budget and deterministic gates. Get CI green and a clean Codex
review on the final head, with zero unresolved review threads. Stop and report;
the founder merges and enables flags at promotion.

## 6. Stop conditions

- A second Codex finding on the same preview/privacy mechanism: stop and report
  instead of fixing that mechanism again.
- Shared component changes required for the responsive contract: report, leave
  AdaptivePanel untouched, and do not claim that acceptance gate passed.
- Any live provider answer needs a proposed spend cap and founder approval.
- Scope requires account data, hidden turns or live public source reads: stop.

## Sources

Founder instructions 2026-09-14; issue #604 and its recorded promotion evidence;
docs/PRODUCT.md; docs/specs/argus-grounded-finance-roadmap.md Sharing lane;
docs/specs/private-alpha-next-decision-memo.md sections 5.8 and 10.7.
