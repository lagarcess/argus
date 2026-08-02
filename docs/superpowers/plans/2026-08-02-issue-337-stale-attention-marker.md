# Issue #337 Stale Attention Marker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove a rail needs-attention tick when its typed clarification recovers to an active confirmation, without changing independent failures or other tick types.

**Architecture:** The rail remains a render-time projection of `Message[]`. A private predicate will suppress only a `RecoveryDisplay.kind === "clarification"` tick when a later active `strategy_confirmation` is present; failed jobs and all other recovery kinds stay unchanged.

**Tech Stack:** TypeScript, React/Next.js, Bun, existing rail test harness, Playwright.

## Founder acceptance correction — 2026-08-02

The first browser fixture used a registered account and two completed runs.
That did not represent the locked G-01/G-02 Guest session, and it masked the
rail visibility failure that occurs when a Guest's single allowed completed
run is the only legitimate tick left after clarification recovery.

The corrected acceptance path is:

- identify the deterministic EN/es-419 fixture as Guest;
- keep exactly one completed result in the recovered transcript;
- prove red while the `>=2` tick visibility gate hides the rail;
- lower only the tick-count gate to one while retaining the 12-message and
  desktop thresholds;
- replay the same shape through disposable local Supabase Guest Auth and
  durable messages/runs, including reload, with zero provider or hosted writes.

This addendum expands the allowed test surfaces to
`web/e2e/conversation-activity-ui.spec.ts`,
`web/e2e/guest-experience.preflight.spec.ts`, and
`web/e2e/support/guest-qa.ts`. Backend product behavior and API/data contracts
remain unchanged.

## Review correction — typed continuity required — 2026-08-02

The original positional predicate in Task 1 was insufficient: any later active
confirmation could clear every earlier clarification, including a recovery for
an unrelated idea. The locked spec requires transcript evidence that the
confirmation continues the clarification.

The corrected implementation projects existing backend-owned
`pending_strategy` and `confirmation_payload.strategy` metadata onto hydrated
messages. A clarification clears only when the requested field is present in a
later active confirmation and typed strategy facts prove the same path. Missing
or conflicting relationship evidence fails closed, so the marker stays
visible. This expands the frontend behavior surface to the existing stream and
reload hydration helpers and their focused tests; it does not add or change a
backend, API, data, localization, provider, or LLM contract.

## Global Constraints

- Keep behavior frontend-only: rail derivation plus projection of existing
  persisted/streamed typed metadata. Do not create a new backend relationship.
- No backend/API/data/localization/provider/LLM changes.
- Active confirmation means `confirmation_state` is `"active"` or omitted; cancelled/superseded confirmations never resolve.
- Preserve result, decision-saved, failed-job, retryable, coverage, unsupported, and artifact-action ticks.
- Capture deterministic EN and es-419 browser evidence.

---

### Task 1: Test and implement resolved-clarification filtering

**Files:**

- Modify: `web/__tests__/conversation-activity-rail.test.ts`
- Modify: `web/lib/conversation-rail.ts`

**Interfaces:**

- Consumes: `deriveConversationRailTicks(messages: Message[]): ConversationRailTick[]`.
- Produces: the same public function with resolved clarification ticks omitted.

- [ ] **Step 1: Write a failing G-01/G-02 regression test**

Add a `confirmationMessage` fixture with `role: "ai"`, `kind: "strategy_confirmation"`, an active confirmation, and required title/statusLabel/summary/rows. Add the exact transcript:

```ts
[
  textMessage("user-idea", "user"),
  textMessage("asset-question", "ai", {
    recoveryDisplay: {
      kind: "clarification",
      requestedField: "asset_universe",
      semanticNeeds: ["asset_target"],
    },
  }),
  textMessage("user-asset", "user"),
  textMessage("date-question", "ai", {
    recoveryDisplay: {
      kind: "clarification",
      requestedField: "date_range",
      semanticNeeds: ["period"],
    },
  }),
  textMessage("user-dates", "user"),
  confirmationMessage("recovered-confirmation"),
  jobMessage("independent-failed-job", "failed"),
]
```

Name the test `clears clarification attention after the same transcript reaches an active confirmation`. Assert the ticks are exactly `[["independent-failed-job", "error_recovery"]]`. The production change that must make it fail is removing the resolution filter.

- [ ] **Step 2: Prove red**

Run:

```bash
cd web && bun test __tests__/conversation-activity-rail.test.ts --test-name-pattern "clears clarification attention"
```

Expected: fail because both clarification messages are currently emitted as `error_recovery`.

- [ ] **Step 3: Add boundary tests**

Test that cancelled and superseded confirmation states leave the clarification tick visible. Test that a `coverage_recovery` after an active confirmation remains an `error_recovery` tick. These catch the two invalid implementations: treating every confirmation as resolution and suppressing unrelated recovery classes.

- [ ] **Step 4: Implement the smallest proven-link predicate**

Project existing `pending_strategy` and `confirmation_payload.strategy`
metadata through both reload and streamed-final message paths. When deriving a
`recoveryDisplay` tick, skip it only if its kind is `clarification`, the later
confirmation is active, its strategy supplies the requested field, and the
typed strategy path or source-result artifact proves continuity. Missing or
conflicting relationship evidence must keep the tick. Do not change the
failed-job, assistant-recovery-code, superseded-runtime-failure, coverage,
unsupported, or artifact-action branches.

- [ ] **Step 5: Prove green and commit**

Run:

```bash
cd web && bun test __tests__/conversation-activity-rail.test.ts
```

Then commit only the test and derivation:

```bash
git add web/lib/conversation-rail.ts web/__tests__/conversation-activity-rail.test.ts
git commit -m "fix(chat): clear resolved rail attention"
```

### Task 2: Capture deterministic browser evidence

**Files:**

- Create: `output/playwright/issue-337-en.png`
- Create: `output/playwright/issue-337-es-419.png`

- [ ] **Step 1:** Inspect `web/e2e/conversation-activity-ui.spec.ts` and reuse its deterministic rail fixture or test route. Do not use a live provider or submit a real turn.

- [ ] **Step 2:** Start the supported deterministic local web surface. Use Playwright snapshots before interactions, then save the EN screenshot. Verify the recovered clarification marker is absent and a failed-job tick remains.

- [ ] **Step 3:** Change the existing UI language control to es-419, re-snapshot, save the second screenshot, and verify the same behavior. No locale-specific runtime branch may be added.

- [ ] **Step 4:** Run the focused existing rail E2E owner test and record the exit status.

### Task 3: Review, reconcile, and publish

**Files:**

- Review: `web/lib/conversation-rail.ts`, `web/__tests__/conversation-activity-rail.test.ts`, and `origin/codex/private-alpha-next...HEAD`.

- [ ] **Step 1:** Run the focused Bun test and the repository’s documented lint/type command; inspect full output and exit codes.

- [ ] **Step 2:** Independently review the actual diff: only the rail/test contract changed; result/decision/independent failures remain; no API/data/i18n move; tests prove each locked decision. Fix only validated findings.

- [ ] **Step 3:** Fetch integration. Record original base `6533377c1a08539136a622a7d53eee20d0efd845`, current remote SHA, and semantic-overlap disposition. If it advanced with overlap, merge normally (never rebase) and rerun affected checks.

- [ ] **Step 4:** Push and open a Draft PR against `codex/private-alpha-next`, linking `Closes #337`. Use the required TL;DR, Summary, Changes, Motivation, Impact, Testing, Risks/Rollback, and Checklist sections. Do not merge or deploy.

- [ ] **Step 5:** Inspect exact-head GitHub CI to its terminal state. Report the original/current integration SHAs, reconciliation merge if any, evidence retained/invalidated, PR head, and CI state.
