# Ask for feedback: evidence

Roadmap item "Ask for feedback" in `docs/specs/argus-grounded-finance-roadmap.md`
(added at `ff98fec7`). Integration base `ff98fec7`. Code head `044b9713`.

## Browser proof, both languages

Run from `web/` against a real local API: this worktree, memory persistence,
mock auth, no `.env`, and the SMTP credential blank on purpose.

```bash
FEEDBACK_ASK_LIVE_API=1 FEEDBACK_ASK_EVIDENCE_DIR=../docs/reports/evidence/ask-for-feedback PLAYWRIGHT_PORT=3100 bunx playwright test e2e/feedback-ask.spec.ts --workers=1
```

Result: 4 passed. The transcript, one user turn and one result card, is a route
fixture in the same shape as `e2e/issue-509-card-copy-language.spec.ts`. With
`FEEDBACK_ASK_LIVE_API=1` the tap goes to the real endpoint; without it the save
is stubbed and the spec also passes.

| Screenshot | What it shows |
| --- | --- |
| `en-1-ask-after-result.png`, `es-419-1-ask-after-result.png` | The ask under a result: three one-tap answers and a dismiss button |
| `en-2-tap-saved.png`, `es-419-2-tap-saved.png` | After a tap: thanks and "Tell us more" |
| `en-3-tell-us-more-dialog.png`, `es-419-3-tell-us-more-dialog.png` | The existing feedback dialog, opened from the ask |
| `en-4-dismissed-after-reload.png`, `es-419-4-dismissed-after-reload.png` | No ask after a dismissal and a reload |

The quick take on the fixture card says its saved facts are not sufficient
because the fixture carries no readout facts. That text is not part of this
change.

The spec also asserts, per language:

- the tap's request is `type: "general"` with context exactly
  `{source: "feedback_ask", surface: "chat", rating: "positive", tags: [], hasAttachments: false, attachmentCount: 0}`,
  and the conversation id appears nowhere in the body;
- the endpoint answered 200;
- the dialog's "include approved context from this conversation" checkbox is
  present and unchecked;
- the ask stays gone after a reload, both after a tap and after a dismissal.

API log for the two real taps, one per language:

```text
INFO     | argus.api.routers.feedback:feedback:116 - Feedback submitted
"POST /api/v1/feedback HTTP/1.1" 200 OK
WARNING  | argus.api.feedback_notification:notify_feedback_submitted:93 - Feedback notification failed
INFO     | argus.api.routers.feedback:feedback:116 - Feedback submitted
"POST /api/v1/feedback HTTP/1.1" 200 OK
WARNING  | argus.api.feedback_notification:notify_feedback_submitted:93 - Feedback notification failed
```

Because the credential was blank, both taps also show a failed email that still
saved the feedback.

## Test email

One email, marked as a test, sent on 2026-09-11 from a local run of the real app
at code head `044b9713`. One `POST /api/v1/feedback` went through FastAPI's
`TestClient` with memory persistence and the message:

> [TEST] Ask for feedback lane, local run on 2026-09-11. Please ignore: this
> only checks that feedback reaches support@get-argus.com.

The route returned 200 and saved one row. The notification task logged
`Feedback notification sent` with Resend receipt
`0e15b6d0-e9e1-4553-830e-1820002c2947`. Resend accepted the message for
support@get-argus.com. The send-only key cannot read delivery status, so the
founder confirms arrival in the inbox.

The test run read the credential from the integration `.env` into its own
process and never printed it. In that file
`ARGUS_APPROVAL_EMAIL_SMTP_PASSWORD=${RESEND_API_KEY}` sits above the
`RESEND_API_KEY` line, so a loader that reads in order, such as python-dotenv or
`source .env`, sees the password as empty. The run resolved that one reference
itself; no `.env` was edited. Hosted services set the password directly.

## Checks at code head `044b9713`

| Check | Result |
| --- | --- |
| `poetry run pytest tests -q --no-cov` | 7249 passed, 585 skipped |
| `tests/test_interpreter_prompt_freeze.py` | 3 passed, no model-facing text changed |
| `cd web && bun test` | 1713 pass, 0 fail |
| `cd web && bun run lint` on changed files | clean |
| `bunx playwright test e2e/browser-storage-disclosure.spec.ts` | 2 passed |
| `scripts/check_modularity_budget.py` | no violations; `ChatInterface.tsx` 2584 to 2581 lines |

No live measurement: no model-facing text or routing changed.
