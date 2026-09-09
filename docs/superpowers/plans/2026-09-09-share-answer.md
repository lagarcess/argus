# Share the answer Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development to execute
> the bounded tasks below with focused review between tasks.

**Goal:** Share up to four eligible answers from one conversation through the
existing immutable receipt pipeline.

**Architecture:** One backend eligibility and creation boundary owns every entry
point. A versioned closed payload feeds one public receipt body, with a v1
compatibility projection and new content derived from the card's typed facts.

**Tech Stack:** FastAPI/Pydantic, Supabase Postgres, Next.js/React, Poetry and Bun.

**Spec:** `docs/specs/conversation-sharing.md` sections 4/4.5/9 and
`docs/superpowers/specs/2026-09-09-share-answer-delivery.md`.

## Global constraints

- Maximum four turns from one owned conversation, in conversation order.
- Research payload fields exactly match section 4.2; `extra="forbid"` on every
  public model; no source ids, raw card payloads, or private runtime metadata.
- One refusal refuses the whole publication. Creation rechecks eligibility.
- Existing v1 payload/rendering and live-link identity remain compatible.
- Flags remain off. No merge/deploy, provider/prompt change, guest share, fork,
  prefill, history copy, refresh, or rerun.
- Local tests use `poetry run` (verified Python 3.10.20) and Bun. Never edit the
  canonical-linked `.env`. Browser evidence is durable and bilingual.

## Task 1: Closed snapshots and one owner service

**Own:** `src/argus/api/public_excerpt_schemas.py`,
`src/argus/api/public_excerpts.py`, receipt routers,
`src/argus/domain/public_excerpts.py`, `supabase_public_excerpts.py`, focused
receipt helper modules, the additive receipt migration and backend receipt tests.

**Interfaces:** Retain the artifact POST as an adapter. Add owner-scoped candidate,
preview and creation endpoints under the conversation; requests name one to four
assistant message ids and an optional owner note. Candidate results contain a
typed reason and field, never backend-localized prose. Preview returns the exact
closed payload and its digest; creation recomputes and checks that digest before
publishing. Publish the exact TypeScript-facing shapes to the web task before it
starts. Public reads continue selecting only snapshot columns.

- [ ] Add adversarial tests first, including this invariant using the shared
  receipt fixtures and the real service:

  ```python
  with pytest.raises(PublicExcerptSourceError):
      preview_receipt_for_messages(
          user=owner, conversation_id=conversation.id,
          message_ids=[eligible.id, ineligible.id], owner_note=None,
      )
  assert not store.public_excerpt_snapshots
  ```

- [ ] Run the new tests and retain the expected missing-behavior failure.
- [ ] Implement the closed research payload, version-aware parser and shared
  field audit. Preserve the concrete v1 type and raw serialized v1 payload.
- [ ] Implement candidate/preview/create through one owner service, backtest
  compatibility adapter, selection identity and insert-race recovery. Resolve
  research job questions and terminal state from the existing typed job owner.
- [ ] Extend the existing snapshot storage and guards; test owner/delete races,
  single-versus-wrapper identity, cascade/revoke, 1..4 bounds and atomic refusal.
- [ ] Run `poetry run pytest tests/test_public_excerpt*.py -q --no-cov`, separating
  disposable-Postgres proof from unit tests so skips cannot count as acceptance.
- [ ] Run focused lint and a bounded implementation review, then commit.

## Task 2: Selection, exact preview and one receipt body

**Own:** `web/lib/public-receipt-contract.ts`, `evidence-receipts.ts`, receipt
presentation helpers, receipt components and `/r/[receiptId]` routes,
`ShareReceiptAction.tsx`, `ChatHeaderMenu.tsx`, the narrow ChatMessage/result-card
and ChatInterface mounts, SharedReceiptsView and focused frontend tests.

**Interfaces:** Consume Task 1's candidate reasons and preview/create contract.
The header is the sole sharing entry point and opens selection. No message
overflow item, assistant-bubble pill or visible result-card share control remains.
Sharing one answer means selecting one turn there. The panel renders Task 1's
closed preview through `ReceiptBody` with
analytics/action bar disabled until a real public page is rendered. Legacy v1
formatting is adapted into the same internal presentation and DOM.

- [ ] Write interaction tests for disabled candidate reasons, four-turn bound,
  eligible-only select all, preview before creation and singleton selection:

  ```tsx
  expect(screen.getByRole("checkbox", { name: /not grounded/i })).toBeDisabled();
  expect(screen.getByText(/typed sources/i)).toBeVisible();
  expect(createReceipt).not.toHaveBeenCalled();
  ```

- [ ] Run the tests red, then generalize the existing panel and share control.
- [ ] Preserve one ReceiptBody and its ruled-row/stamp geometry. Project new
  backtest content using the existing result fact and display owners; render
  research prose with the supported markdown subset, dated sources and framing.
- [ ] Extend the same SSR preview card, metadata and Settings list. Public CTA
  uses bare `/`; funnel stages carry kind and count one page view.
- [ ] Add both locale bundles together; no em dash and no prose-derived eligibility.
- [ ] Run focused Bun tests, TypeScript and lint. Review the actual diff for
  accidental parallel sharing systems before committing.

## Task 3: Durable browser proof and finishing bar

**Own:** contract docs, OpenAPI generation, lane-local QA drivers and
`docs/reports/evidence/share-answer/`, final integration/PR coordination.

- [ ] Use the existing receipt seed server and frozen v1 JSON to establish and
  compare rendering; never edit historical evidence. Use one real research turn
  per author language and freeze its sanitized proof for repeated rendering.
- [ ] Capture research at 390/1280 in en/es-419 signed out, disabled reasons in
  both languages, sole header entry, singleton selection, owner preview, Settings
  revoke/tombstone and bare-entry CTA. Inspect screenshots, not only assertions.
- [ ] Run disposable Postgres tests with zero skips and update canonical docs and
  OpenAPI. Commit durable screenshots and a truthful evidence manifest.
- [ ] Fetch integration, merge one-way if needed, audit overlap, run modularity
  budget against the combined tree, and rerun only invalidated acceptance.
- [ ] Publish the PR with enhancement/web/api/core labels. Mark it ready for
  review before the final gates; confirm CI/runtime and a cleared Codex round
  naming the exact head, with zero unresolved threads.
- [ ] Write terminal audit after review completes. Stop at the non-draft PR for
  the founder's merge decision; only mark the Goal complete when all gates pass.
