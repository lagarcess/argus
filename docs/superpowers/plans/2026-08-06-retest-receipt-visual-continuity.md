# Retest Receipt Visual Continuity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the Retest user receipt visually stable from optimistic submission through backend-owned receipt hydration and terminal recovery.

**Architecture:** Add one non-persisted presentation flag to optimistic Retest messages. Render pending and ready states through the same `RetestReceipt` component, and settle the flag through the existing stream final, error, done, and HTTP rejection paths. Backend receipt metadata remains the sole source of symbols, strategy, dates, and duration.

**Tech Stack:** React 19, Next.js 16, TypeScript, Bun test, React server rendering, Playwright Chromium.

## Global Constraints

- Do not change Retest admission, payloads, provider preflight, confirmation, usage accounting, or backtest job polling.
- Do not derive canonical receipt facts in the client.
- Do not add a timer, polling loop, backend field, request lifecycle, or persisted UI state.
- Reuse existing recovery projections for terminal failure.
- Preserve English and es-419 behavior without adding new product copy.
- PR #363 remains founder-gated and must not be merged by the implementation agent.

---

### Task 1: Prove the unstable optimistic receipt

**Files:**
- Create: `web/__tests__/chat-retest-receipt.test.tsx`
- Modify: `web/__tests__/chat-retest.test.ts`

**Interfaces:**
- Consumes: `Message`, `ChatMessage`, `RetestReceipt`, `applyRetestReceipt`, and `retestActionOption`.
- Produces: failing behavioral coverage for a stable pending shell and terminal settlement.

- [ ] **Step 1: Add a component-level failing test**

Render a real `ChatMessage` for an optimistic Retest message carrying
`retestReceiptPending: true` and no receipt. Assert that it renders
`data-retest-receipt-state="pending"` and the same
`data-retest-receipt-context-row` used by a ready message. Render the ready
fixture with literal backend receipt facts and assert
`data-retest-receipt-state="ready"` plus the literal context text.

- [ ] **Step 2: Add a projection-level failing test**

Use a literal optimistic Retest `Message` with the typed action and pending
flag. Call:

```ts
applyRetestReceipt(messages, "user-retest-1", null)
```

Assert that the matched Retest message clears `retestReceiptPending` without
inventing `retestReceipt`. Then pass a literal receipt and assert that it clears
pending and stores that receipt. A non-Retest action must remain unchanged.

- [ ] **Step 3: Verify RED**

Run:

```bash
cd web
bun test __tests__/chat-retest-receipt.test.tsx __tests__/chat-retest.test.ts
```

Expected: FAIL because the optimistic message still renders the generic action
pill and `applyRetestReceipt(..., null)` does not settle pending presentation.

---

### Task 2: Render and settle one stable receipt shell

**Files:**
- Modify: `web/components/chat/types.ts`
- Modify: `web/lib/chat-retest.ts`
- Modify: `web/components/chat/RetestReceipt.tsx`
- Modify: `web/components/chat/ChatMessage.tsx`
- Modify: `web/components/chat/ChatInterface.tsx`
- Test: `web/__tests__/chat-retest-receipt.test.tsx`
- Test: `web/__tests__/chat-retest.test.ts`

**Interfaces:**
- Produces: `Message.retestReceiptPending?: boolean` and a
  `RetestReceipt` presentation accepting `receipt: RetestReceiptPayload | null`
  plus `pending: boolean`.
- Preserves: `applyRetestReceipt(messages, userMessageId, receipt)` as the one
  settlement helper used by stream terminal paths.

- [ ] **Step 1: Add the ephemeral message field**

Add this field beside `retestReceipt`:

```ts
/** Ephemeral optimistic presentation; never hydrated or persisted. */
retestReceiptPending?: boolean;
```

Set it to `true` only when `handleSend` constructs an optimistic
`retest_run` user message.

- [ ] **Step 2: Make settlement total and Retest-scoped**

Change `applyRetestReceipt` so it only touches the matched user Retest action,
always sets `retestReceiptPending: false`, stores a supplied receipt, preserves
an existing receipt when called later with `null`, and leaves non-Retest
messages byte-for-byte unchanged.

- [ ] **Step 3: Render pending and ready through one component**

Allow `RetestReceipt` to receive a null receipt in pending mode. Keep one outer
container with `data-retest-receipt-state="pending|ready"`. Render the same
second-row element in both states. Pending uses an `aria-hidden` pulse placeholder;
ready renders the backend-derived context line. No client facts or new copy are
created.

- [ ] **Step 4: Use the stable component for optimistic Retest only**

In `ChatMessage`, route a Retest action to `RetestReceipt` when either a receipt
exists or `retestReceiptPending` is true. Legacy/incomplete settled action
messages without either value retain the current generic one-line action pill.

- [ ] **Step 5: Settle every existing terminal transport path**

Reuse `applyRetestReceipt` on:

- final payload, with `retestReceiptFromFinalPayload(finalPayload)`;
- SSE error, with `null` before durable-id replacement;
- done, with `null` while preserving any ready receipt;
- HTTP rejection, with `null` before assistant recovery projection.

Ambiguity resolution continues replacing the optimistic transcript with its
canonical hydrated view, which never projects pending state.

- [ ] **Step 6: Verify GREEN**

Run:

```bash
cd web
bun test __tests__/chat-retest-receipt.test.tsx __tests__/chat-retest.test.ts __tests__/chat-recovery-display.test.ts __tests__/chat-backtest-jobs.test.ts
```

Expected: all tests pass with no React or i18n warnings.

- [ ] **Step 7: Commit the implementation**

```bash
git add web/components/chat/types.ts web/lib/chat-retest.ts \
  web/components/chat/RetestReceipt.tsx web/components/chat/ChatMessage.tsx \
  web/components/chat/ChatInterface.tsx \
  web/__tests__/chat-retest-receipt.test.tsx web/__tests__/chat-retest.test.ts
git commit -m "fix(retest): keep receipt stable while loading"
```

---

### Task 3: Visual and release evidence

**Files:**
- Modify: `docs/evidence/363-retest-button-states/README.md`
- Create: `docs/evidence/363-retest-button-states/en-retest-receipt-pending.png`
- Create: `docs/evidence/363-retest-button-states/en-retest-receipt-ready.png`
- Create: `docs/evidence/363-retest-button-states/es-419-retest-receipt-pending.png`
- Create: `docs/evidence/363-retest-button-states/es-419-retest-receipt-ready.png`
- Temporary only: a focused Playwright capture fixture removed before commit.

**Interfaces:**
- Consumes: the real chat message renderer and deterministic delayed stream
  response.
- Produces: exact-head bilingual evidence for the only visually changed surface.

- [ ] **Step 1: Run the focused frontend matrix**

```bash
cd web
bun test __tests__/chat-retest-receipt.test.tsx __tests__/chat-retest.test.ts \
  __tests__/chat-recovery-display.test.ts __tests__/chat-backtest-jobs.test.ts \
  __tests__/run-dossier-view.test.tsx
```

- [ ] **Step 2: Capture a delayed optimistic-to-ready transition**

Use deterministic owner-scoped fixtures and a delayed Retest response. Capture
pending and ready frames in English and es-419. Assert the same receipt shell
remains mounted, its context row remains present, and its height does not change
between frames. Do not call providers, an LLM, or a simulation.

- [ ] **Step 3: Refresh the evidence README and remove capture-only code**

Record the exact candidate SHA, the delayed-response method, locale matrix, and
the stable-shell/height assertions. Delete temporary test routes and capture
fixtures before staging.

- [ ] **Step 4: Run exact-head verification**

```bash
cd web && bun test && bun run build
cd ..
poetry run ruff check src tests workflows scripts
poetry run python scripts/check_modularity_budget.py
git diff --check
```

Run the backend Retest suites only if the final diff crosses a backend surface;
otherwise retain the accepted exact-head backend evidence and state why.

- [ ] **Step 5: Commit evidence and push**

```bash
git add docs/evidence/363-retest-button-states
git commit -m "docs(retest): prove stable receipt transition"
git push origin codex/issue-333-retest-current-data
```

- [ ] **Step 6: Request and close final review**

Request `@codex review` once at the pushed exact head. Wait for the response,
inspect unresolved threads, address only confirmed findings caused by this
delta, and leave PR #363 open for the founder.
