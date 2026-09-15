# #604 delivery stopped after repeated review finding

Historical stop record. Founder authorized resuming once on 2026-09-14.
The original state and findings below are retained; see delivery.md for current
verification and review status.

Branch: `codex/604-conversation-sharing`.
Current commit: `4a3e5a6d9902ae4f6103db9d51167dab98bb6e62` (spec only).
Implementation and these evidence files remain uncommitted in the worktree.
Original integration base: `d788449385ec93e92609b4692aa0fe8c1981ab58`.
Last fetched integration: `8b63b0891922c311e50bffa3c15c60ec6e4b0ff5`.
Reconciliation merge: not performed. The intervening integration change was
roadmap breakpoint documentation, with no shared runtime or contract overlap.

## Review outcome

The initial local Codex review found two distinct issues:

1. The public action bar called plain/mixed answers dated research.
2. Shared links controls were 36px in sheets instead of 44px.

The footer correction added neutral answer copy and four passing plain/mixed
renderer cases, but used `kind === "research"` instead of the actual contract
value `research_answer`. The bounded follow-up Codex review confirmed that real
research receipts consequently fall through to the generic answer footer.
This is a second finding on the same public-renderer provenance mechanism.
Per the founder instruction, no further correction was attempted.
Location: `web/components/receipt/ReceiptBody.tsx:132`; contract:
`web/lib/public-receipt-turns.ts:4`.

The touch-target change uses min-h-11 for all five list controls. The browser
assertion reproduced 36px before the change. Its follow-up matrix did not finish:
a receipt left by the failed test was reused, so the test expected a creation
button where the existing-link state was correctly shown. This test setup issue
has not been corrected after the stop condition.

## Evidence limits

Backend regression red proof and focused green proof are retained here. The
46 receipt Postgres checks passed against a separate schema-only local database
with the new migration applied. No hosted database or provider calls were used.
Earlier browser, frontend tests and build passed before the final footer edit;
they do not establish acceptance for the current worktree. The complete backend
run was interrupted after linked dotenv configuration contaminated unrelated
tests; the planned clean-checkout rerun was not performed.

No exact-head final browser matrix, CI, GitHub Codex review, or terminal readiness
claim exists. No PR was opened, no branch was pushed, and nothing was merged or
deployed. Sharing flags in render.yaml and the release profile remain false.

The pending migration is
`supabase/migrations/20260914120000_share_plain_answer_receipts.sql`.
It widens the existing snapshot kind constraint for plain answers and would need
to run at promotion if delivery resumes.
