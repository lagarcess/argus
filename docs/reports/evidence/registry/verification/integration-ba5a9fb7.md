# Registry reconciliation with Share the answer

This is an in-progress reconciliation record, not a terminal readiness audit.

## Lineage and overlap

- Original registry integration base: `9e8b59b23f29d432ec7603c42f7362137b1ee21f`.
- Previous reconciled integration: `377190bd2911959e14ad9d92f2f4dba3edeb8453`.
- Fetched current integration: `ba5a9fb71a2696cc7155d6c8241d20dc79bea4c7`.
- Worker before this normal merge: `34683041`.
- Reconciliation merge commit: pending conflict resolution and verification.

PR #574 adds selected-turn sharing, source arrays and validation, header-only
selection/preview, and canonical DCA readouts. These overlap the registry's
generic tool receipt, public parser/renderer, publication guards, and source
revision identity. The fifteen textual conflicts do not describe the full
overlap: automatically merged chat, locale, result projection, list and copy
owners also require inspection. No interpreter prompt, financial repair or
tool-declaration owner changed in incoming integration.

## One shared receipt boundary

New receipts use incoming selected-turn version 2. A generic turn contains
ordered sibling card presentations from one assistant message; sibling calls
do not consume additional positions in the four-turn selection cap. Generic
cards use the existing declaration-bound presentation after public sanitization.
The existing artifact and tool-result routes adapt to the same selection
service. A refused sibling refuses that selected turn and the entire selection.

The generic leaf is `kind: tool_result`, with `question`, ordered `cards`,
`owner_note`, `content_language`, computed framing and provenance. Each card
contains only its `card_type`, `card_version`, and public `presentation`.
List and funnel kinds add `tool_result`; distinct selected kinds produce `mixed`.
Runtime bounds derive from the existing turn and call limits.

Selection identity includes each selected tool card's message, artifact and input
revision. Private `source_tool_bindings` keep those identities separate from
genuine EvidenceArtifact and run source arrays. Public payloads carry none of
these identities. Recomputation can create a new selection while old links stay
frozen. Existing bare version 2 tool documents retain strict read compatibility;
neither their payloads nor their digests are rewritten.

The incoming header is the sole share entry. Its selection, preview and guest
rules remain, while obsolete per-card share controls are removed. One public
body renders the existing card presentations. The incoming DCA fact owner and
its zero-preserving behavior remain alongside registry progress and plural-job
continuity.

Public receipt eligibility is also declaration-owned. A fail-closed
`public_receipt` policy distinguishes `disabled`, `typed_facts`, and
`cited_facts`. Backtests opt into typed facts; the three existing cited research
operations require cited facts. The quote and discovery operations remain
disabled, preserving incoming fast/find exclusions even when plural calls
remove the singular research sidecar. A new local tool opts in through its own
declaration. Receipt consumers check each sibling's admitted declaration and
versioned card binding, retained citations where required, and shared privacy
and failure gates; they do not map tool names to eligibility. This policy
extends generated catalog metadata and belongs in the next measured surface.

The combined `ChatInterface.tsx` is 2,600 lines: two over the former 2,598 limit.
Moving the share panel into its existing experience-surface owner removes the
duplicated placement, but the required conversation id and sharing callback
still add two header props. Independent review rejected formatting compression;
normal formatting was restored. The release captain permits exactly two extra
growth lines for this merged wiring: the captured baseline remains 2,523 and
this file's allowance becomes 77. Other budgets stay unchanged. This explicit
heuristic-budget adjustment avoids adding an otherwise unnecessary state layer;
the full merged-tree budget gate and functional/browser checks still apply.

## Migration reconciliation

The landed `20260909183646_share_answer_receipt_selections.sql` remains
byte-identical to integration. Its SHA-256 is
`151b8238f8c35c6c070d0f57778ed415379e366c1aefd60288f534a8fcff6b17`.

The registry's unlanded older migration stops creating the colliding message
trigger. An ordered bridge checks the trigger's exact function identity and
preserves an already-applied registry deletion trigger under a compatibility
name. Unknown identities fail closed. A later combined migration supplies one
source validator and deletion revoker for selected arrays, plural tool bindings
and legacy singular tool sources, then removes only the verified compatibility
trigger. Both previously applied migration orders and a fresh reset of all 74
migrations passed locally. The two receipt suites plus trigger-identity checks
passed 62 tests; the full PostgreSQL matrix passed 384 tests in 82.77 seconds,
with zero skips, failures or errors. Their pytest gates passed. No hosted
database cleanup or payload rewrite is part of this work.

## Reconciliation checks and review

The focused backend/API/recompute suite passed 425 tests, and the generated
OpenAPI compatibility check passed 23. The frontend's focused suite passed 220;
its app typecheck and changed-file ESLint passed. The development fixture browser
matrix passed all 20 cases, including header focus and bilingual selected-turn
preview/public receipts at mobile and desktop widths. These development captures
do not replace the final committed-candidate capture.

Independent UI review passed 160 tests and retained the existing v1 snapshots.
Independent backend review passed 203 tests, then 38 on its reported revision
race fix. That race could publish a recomputed revision with identical public
facts after the compatibility route had checked the older revision. The route
now passes its private expected source into the shared creator, which checks its
own projection before the existing locked insert. The reproduced race is closed.
The reviewer also inspected both upgrade histories, fresh reset, and focused
PostgreSQL evidence and found no remaining issue in the changed scope.

## Evidence disposition

The earlier failed full measurements and the 28 interleaved probes remain
unchanged, failed historical evidence. Deterministic repair reports explain
their bounded follow-ups; they do not regrade those observations.

Incoming receipt/API/header/DCA changes invalidate acceptance claims for those
affected surfaces. Reconciliation requires the shared receipt backend tests,
real PostgreSQL migration/ownership/revision/deletion checks, and affected
bilingual preview/public browser evidence. Existing research and interpreter
observations remain useful provenance, but no prior scorecard accepts the new
catalog fingerprint. The reconciled candidate still owes a clean full live
measurement and exact-head CI and GitHub Codex review.

Serializer-pinned `src/argus/api/state.py` remains unchanged from the original
integration base. The Lane C import probes and merged-tree modularity gate will
be rerun after reconciliation. No paid provider calls were made to plan or
resolve this integration overlap.
