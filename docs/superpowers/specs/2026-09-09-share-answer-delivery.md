# Share the answer delivery contract

Implement the existing sharing system's extension approved in
[`conversation-sharing.md`](../../specs/conversation-sharing.md), sections 4 and
4.5, including the founder's four-turn wrapper decision at `743dfda3`.
That specification owns product decisions and the research field list; this
document records delivery and verification, rather than another sharing design.

## Why

The grounded-finance board's **Share the answer** item makes an eligible grounded
answer distributable through the same immutable receipt as a backtest. This
supports PRODUCT.md's checkable answers and the decision memo's sanitized
artifact distribution loop.

## Locked boundaries

- One `public_excerpt_snapshots` pipeline, public `/r/<id>`, Settings list,
  revocation and source deletion lifecycle. This is the storage table behind the
  existing `evidence_receipts` module.
- A closed outer `turns` wrapper holds one through four independently eligible
  per-turn receipts from one conversation in conversation order. No public source
  identifiers. One failed check refuses the whole selection.
- Preserve the v1 model and its frozen rendering. New backtest facts derive from
  the card's existing typed fact owners; research fields are exactly section 4.2.
- One `ReceiptBody` renders receipt form from a presentation projection. Legacy
  formatting is a compatibility adapter, not another public body.
- One backend eligibility/projection service serves candidate reasons, exact
  preview, final creation, and the artifact compatibility endpoint. Final creation
  checks the facts again, including every question, answer and owner note.
- The header link glyph sits left of MoreVertical and opens selection. Ineligible
  turns remain visible and disabled with localized reasons. Select all means all
  eligible; when more than four exist it cannot silently select an arbitrary four.
- The header glyph is the only entry point. No assistant-bubble share pill,
  message-overflow share item or visible StrategyResultCard share control remains.
  The existing creation logic serves the selection screen. One checked turn means
  a single-answer receipt, through the same ownership and eligibility checks.
- The public action says Continue with Argus and lands at bare guest entry.
- All content freezes; cross-turn inference remains the explicitly accepted risk
  documented in section 4.5. Preview displays the entire selected publication.

## Reserved scope

No guest creation, cross-conversation composition, fork, prefilled prompt,
copy-into-history, live refresh, receipt rerun, new sharing flags, or flag enablement.
Interpreter/model-facing text and research provider behavior are outside this lane.

## Contract gates

Update API_CONTRACT.md, DATA_MODEL.md section 12.1.3, the generated OpenAPI,
and the original receipt spec's research exclusion. Use an additive migration on
the existing receipt storage and preserve RLS, immutability and deletion guards.

## Execution contract

One worker PR targets `codex/private-alpha-next`, starting at
`743dfda3da9b467d32023ac32e900dad5a392500`. The previous read-only baseline at
`9e8b59b2` passed 268 backend receipt tests and 89 frontend receipt tests; only the
binding spec changed between those commits.

Focused new tests must cover closed variants, all refusal classes and named fields,
four-turn bounds, owner/conversation boundaries, race/idempotency, preview/create
agreement, v1 compatibility, flag-off identity and lifecycle behavior in Postgres.
Browser proof covers research shared and opened signed out at 390 and 1280 in both
languages; readable disabled selector reasons in both languages;
revoke/tombstone; one header entry point, singleton and four-turn selection; and an
unchanged v1 fixture. Preserve screenshots and
sanitized evidence in the PR. Real research provenance is captured once; browser
rendering reuses the frozen answer without further retrieval.

The finishing bar is exact-head green CI including the non-draft runtime sweep,
a completed and cleared Codex review at that head, and zero unresolved threads.
Labels: enhancement, web, api, core. Reconcile one-way from integration, audit
semantic overlap and run the modularity budget against the merged tree before a
ready claim. The founder retains merge, migration application and deployment.

## Stop conditions

Stop and report if a second receipt body is necessary, the closed research fields
or privacy checks must be weakened, v1 content must be rewritten, or satisfying a
confirmed durable-state requirement requires scope beyond this contract.
