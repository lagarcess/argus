# #604 conversation sharing delivery

Verification in progress after founder-authorized resume. This is not a readiness claim.

Original integration base: `d788449385ec93e92609b4692aa0fe8c1981ab58`.
The footer regression failed in English and Spanish, then all eight renderer
cases passed after correcting `research_answer`. The isolated browser fixture
now resets its memory store and receipt creation limiter before every case;
the requested five-cell matrix passed twice in one API process (10 tests).
See the retained red/green logs in this directory. These runs precede integration
reconciliation; final evidence will be captured after merging current integration.

The new migration `20260914120000_share_plain_answer_receipts.sql` widens the
existing snapshot kind check for plain answers. It has been tested only in a
separate disposable local database; the founder applies it at promotion.
Sharing flags remain false in render.yaml and the release profile.

Latest integration includes result-card profit and settings/modal ownership
changes. They overlap the rendered result and Shared links entry flow, so those
browser acceptance surfaces must be rerun after reconciliation. Eval evidence
configuration changes affect the full deterministic suite, which will run from
a clean checkout without a linked .env. No interpreter prompt or provider turn
has changed in this lane; no paid evaluation is required or authorized.

The final GitHub Codex review is pending. If it raises renderer provenance
again, stop and report under the founder's latest instruction. No merge/deploy.

## Reconciled browser and frontend evidence

Integration merged: `fc3d1414ed8eb4c81fa3f5aedf7e68254f65df5f`.
Reconciliation commit / captured product head:
`f553962d51809179dc4bbc06ce9806a83b4c19fc`.

`browser/` contains selection, note, exact preview, created link, Shared links,
signed-out 390/1024 pages and revoked pages for EN dark 390/720/1024/1280
and ES light 390. All five real receipt-service cases passed. Product UI and
receipt API code are unchanged since this capture; follow-up test-only changes
align the calculation expectations with visible owner inputs and import the
canonical job-scope constant in the fixture. Revalidation at the final pushed
head will be recorded on the PR, together with terminal CI and Codex review.

The API fixture uses the production receipt routes with a synthetic memory
store, registered mock-auth owner, no linked dotenv, and no provider calls.
Unrelated browser shell endpoints are stubbed. The Next.js browser server uses
sharing and Spanish flags locally; deployment configuration remains unchanged.
The public payload equals the preview payload and contains none of the seeded
owner/conversation/message IDs. Confirmation cards are not selectable. Shared
links controls measure at least 44px. Public pages declare noindex, preserve the
publisher link, fit both public widths, and show the tombstone after UI revoke.

Frontend: 1,984 tests pass; lint has zero errors and eight existing warnings;
production build passes. Merged-tree modularity and Ruff pass.

The first complete clean-checkout backend attempt found 15 sandbox permission
failures (loopback servers and process inspection) and one fixture scope literal.
The fixture now imports CHAT_RUN_SCOPE. A full unsandboxed local-only rerun is
required; no application guard or test expectation was weakened for permissions.
