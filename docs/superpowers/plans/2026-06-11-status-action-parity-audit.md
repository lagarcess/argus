# Status Action Parity Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden private-alpha chat artifact status/action ownership so confirmation, job, result, retry, feedback, and more-menu surfaces behave consistently across stream, polling, reload, local QA, and live QA.

**Architecture:** Keep Supabase/API job rows and backend result readouts as the durable source of truth. Add small frontend helpers only for presentation ownership and feedback context; do not add runtime orchestration, retry endpoints, schemas, or feature-surface enablement. Use focused tests as the audit harness, then patch narrow mismatches.

**Tech Stack:** Next.js/React, TypeScript, Bun tests, FastAPI/Python, pytest, Supabase-backed QA mode, Codex browser QA.

---

## Reference Inputs

- Spec: `docs/specs/private-alpha-status-action-parity-audit.md`
- Branch source of truth: `docs/specs/private-alpha-next-integration.md`
- Prior milestone context: `docs/specs/private-alpha-conversation-trust.md`
- Frontend lifecycle helpers:
  - `web/lib/chat-backtest-jobs.ts`
  - `web/lib/backtest-job-card-copy.ts`
  - `web/lib/chat-action-ownership.ts`
  - `web/lib/chat-retry-actions.ts`
  - `web/components/chat/artifact-history.ts`
- Frontend surfaces:
  - `web/components/chat/ChatMessage.tsx`
  - `web/components/chat/ChatInterface.tsx`
  - `web/components/chat/BacktestJobCard.tsx`
  - `web/components/chat/StrategyConfirmationCard.tsx`
  - `web/components/chat/StrategyResultCard.tsx`
- Backend job contract:
  - `src/argus/api/chat/backtest_jobs.py`
  - `src/argus/api/schemas.py`
  - `docs/API_CONTRACT.md`
  - `docs/DATA_MODEL.md`

## Guardrails

- Do not add direct async-job retry.
- Do not infer retry behavior from prose or from `backtest_job.retryable` alone.
- Do not enable hidden Strategies or Collections product surfaces.
- Save can remain functional when result action metadata exists; do not broaden the save product scope.
- Hide `Copy ID` from the assistant more menu.
- Include both local verification and live QA.
- Ignore the Jules intake branch until a safe Jules dispatch is needed.

## Planned File Structure

- Create `web/lib/chat-message-feedback-context.ts`
  - Builds exact feedback/report context for message and artifact turns.
- Create `web/__tests__/chat-message-feedback-context.test.ts`
  - Unit-tests message/artifact feedback context.
- Modify `web/components/chat/ChatMessage.tsx`
  - Uses the feedback context helper and removes `Copy ID` from the more menu.
- Modify `web/lib/chat-action-ownership.ts`
  - Ensures presentation-scoped card actions stay out of composer/footer helpers.
- Modify `web/components/chat/ChatInterface.tsx`
  - Reuses shared ownership filtering for latest input actions.
- Modify `web/__tests__/chat-turn-artifact-ux.test.ts`
  - Adds ownership tests for presentation-only card actions and hidden `Copy ID`.
- Modify `web/__tests__/chat-backtest-jobs.test.ts`
  - Adds terminal job status and polling matrix coverage.
- Modify `tests/test_backtest_jobs_async.py`
  - Adds missing backend status/reconciliation parity coverage if frontend audit exposes a backend gap.

---

### Task 1: Add Feedback Artifact Context And Hide Copy ID

**Files:**
- Create: `web/lib/chat-message-feedback-context.ts`
- Create: `web/__tests__/chat-message-feedback-context.test.ts`
- Modify: `web/components/chat/ChatMessage.tsx`

- [ ] **Step 1: Write failing feedback context tests**

Add `web/__tests__/chat-message-feedback-context.test.ts`:

```ts
import { describe, expect, test } from "bun:test";

import { feedbackContextForMessage } from "../lib/chat-message-feedback-context";
import type { Message } from "../components/chat/types";

describe("chat message feedback context", () => {
  test("includes result artifact identifiers for result-card feedback", () => {
    const message: Message = {
      id: "assistant-result-1",
      role: "ai",
      kind: "strategy_result",
      content: "**Quick take**",
      artifactId: "run-1",
      artifactType: "backtest_run",
      artifactStatus: "completed",
      result: {
        strategyName: "AAPL buy and hold",
        period: "June 1, 2025 to June 1, 2026",
        metrics: [],
        runId: "run-1",
        strategyId: "strategy-1",
        savedStrategyId: "strategy-1",
        artifactId: "run-1",
        artifactType: "backtest_run",
        artifactStatus: "completed",
      },
    };

    expect(feedbackContextForMessage(message, "conversation-1", { rating: "positive" })).toEqual({
      message_id: "assistant-result-1",
      conversation_id: "conversation-1",
      message_kind: "strategy_result",
      artifact_id: "run-1",
      artifact_type: "backtest_run",
      artifact_status: "completed",
      result_run_id: "run-1",
      strategy_id: "strategy-1",
      saved_strategy_id: "strategy-1",
      rating: "positive",
    });
  });

  test("includes job status identifiers for async job feedback", () => {
    const message: Message = {
      id: "assistant-job-1",
      role: "ai",
      kind: "backtest_job",
      artifactId: "job-1",
      artifactType: "backtest_job",
      artifactStatus: "failed",
      backtestJob: {
        id: "job-1",
        conversation_id: "conversation-1",
        request_message_id: "request-message-1",
        confirmation_message_id: "confirmation-message-1",
        status: "failed",
        result_run_id: null,
        failure_code: "market_data_unavailable",
        failure_detail: "market_data_issue",
        retryable: true,
        queued_at: "2026-06-06T12:00:00Z",
        started_at: "2026-06-06T12:00:01Z",
        finished_at: "2026-06-06T12:00:04Z",
        created_at: "2026-06-06T12:00:00Z",
        updated_at: "2026-06-06T12:00:04Z",
      },
    };

    expect(feedbackContextForMessage(message, "conversation-1")).toEqual({
      message_id: "assistant-job-1",
      conversation_id: "conversation-1",
      message_kind: "backtest_job",
      artifact_id: "job-1",
      artifact_type: "backtest_job",
      artifact_status: "failed",
      backtest_job_id: "job-1",
      backtest_job_status: "failed",
      failure_code: "market_data_unavailable",
      retryable: true,
    });
  });

  test("includes confirmation identifiers for confirmation-card feedback", () => {
    const message: Message = {
      id: "assistant-confirmation-1",
      role: "ai",
      kind: "strategy_confirmation",
      artifactId: "confirmation-1",
      artifactType: "confirmation",
      artifactStatus: "active",
      confirmation: {
        confirmation_id: "confirmation-1",
        confirmation_state: "active",
        title: "AAPL buy and hold",
        status: "ready_to_run",
        statusLabel: "Ready to run",
        summary: "Ready to test AAPL.",
        rows: [],
        actions: [],
      },
    };

    expect(feedbackContextForMessage(message, "conversation-1")).toEqual({
      message_id: "assistant-confirmation-1",
      conversation_id: "conversation-1",
      message_kind: "strategy_confirmation",
      artifact_id: "confirmation-1",
      artifact_type: "confirmation",
      artifact_status: "active",
      confirmation_id: "confirmation-1",
      confirmation_state: "active",
      confirmation_status: "ready_to_run",
    });
  });

  test("omits empty optional values", () => {
    const message: Message = {
      id: "assistant-text-1",
      role: "ai",
      kind: "text",
      content: "I can help.",
    };

    expect(feedbackContextForMessage(message, null)).toEqual({
      message_id: "assistant-text-1",
      message_kind: "text",
    });
  });
});
```

- [ ] **Step 2: Run the failing feedback context tests**

Run:

```bash
cd web && bun test __tests__/chat-message-feedback-context.test.ts
```

Expected: fail because `web/lib/chat-message-feedback-context.ts` does not exist.

- [ ] **Step 3: Implement the feedback context helper**

Create `web/lib/chat-message-feedback-context.ts`:

```ts
import type { Message } from "@/components/chat/types";

type FeedbackContextValue = string | number | boolean | null | undefined;

function compactContext(context: Record<string, FeedbackContextValue>) {
  return Object.fromEntries(
    Object.entries(context).filter(([, value]) => value !== null && value !== undefined && value !== ""),
  );
}

export function feedbackContextForMessage(
  message: Message,
  conversationId: string | null | undefined,
  extra: Record<string, FeedbackContextValue> = {},
): Record<string, string | number | boolean> {
  const result = message.result;
  const confirmation = message.confirmation;
  const job = message.backtestJob;
  const artifactId =
    message.artifactId ??
    result?.artifactId ??
    result?.runId ??
    confirmation?.artifactId ??
    confirmation?.confirmation_id ??
    job?.id;
  const artifactType =
    message.artifactType ??
    result?.artifactType ??
    confirmation?.artifactType ??
    (job ? "backtest_job" : undefined);
  const artifactStatus =
    message.artifactStatus ??
    result?.artifactStatus ??
    confirmation?.artifactStatus ??
    job?.status;

  return compactContext({
    message_id: message.id,
    conversation_id: conversationId,
    message_kind: message.kind ?? "text",
    artifact_id: artifactId,
    artifact_type: artifactType,
    artifact_status: artifactStatus,
    result_run_id: result?.runId,
    strategy_id: result?.strategyId,
    saved_strategy_id: message.savedStrategyId ?? result?.savedStrategyId,
    confirmation_id: confirmation?.confirmation_id,
    confirmation_state: confirmation?.confirmation_state,
    confirmation_status: confirmation?.status,
    backtest_job_id: job?.id,
    backtest_job_status: job?.status,
    failure_code: job?.failure_code,
    retryable: job?.retryable,
    ...extra,
  }) as Record<string, string | number | boolean>;
}
```

- [ ] **Step 4: Use the helper in `ChatMessage` and remove Copy ID**

Modify `web/components/chat/ChatMessage.tsx`:

```ts
import { feedbackContextForMessage } from "@/lib/chat-message-feedback-context";
```

Inside `ChatMessage`, before `handleRating`, add:

```ts
  const feedbackContext = (extra: Record<string, string | number | boolean> = {}) =>
    feedbackContextForMessage(message, conversationId, extra);
```

Replace the current rating context calls with:

```ts
      postFeedback({
        type: "general",
        message: newRating === "positive" ? "Thumbs Up" : "Thumbs Down",
        context: feedbackContext({ rating: newRating })
      });
      onFeedback?.("rating", feedbackContext(), newRating);
```

Replace the report issue button handler with:

```ts
                      onClick={() => { setShowOptions(false); onFeedback?.("bug", feedbackContext()); }}
```

Delete this `Copy ID` menu item from the more menu:

```tsx
                    <button
                      className="w-full flex items-center gap-4 px-5 py-3 hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-left text-black dark:text-white text-[15px] font-medium"
                      role="menuitem"
                      onClick={() => { void handleCopy(message.id); setShowOptions(false); }}
                    >
                      <Copy className="w-4 h-4 text-black/60 dark:text-white/60" />
                      {t('chat.copy_id')}
                    </button>
```

- [ ] **Step 5: Run feedback context tests**

Run:

```bash
cd web && bun test __tests__/chat-message-feedback-context.test.ts
```

Expected: pass.

- [ ] **Step 6: Commit Task 1**

Run:

```bash
git add web/lib/chat-message-feedback-context.ts web/__tests__/chat-message-feedback-context.test.ts web/components/chat/ChatMessage.tsx
git commit -m "fix(chat): attach feedback to artifact context"
```

Expected: commit succeeds.

---

### Task 2: Tighten Shared Action Ownership Filtering

**Files:**
- Modify: `web/lib/chat-action-ownership.ts`
- Modify: `web/components/chat/ChatInterface.tsx`
- Modify: `web/__tests__/chat-turn-artifact-ux.test.ts`

- [ ] **Step 1: Add failing ownership coverage**

Update `web/__tests__/chat-turn-artifact-ux.test.ts` in the first test so the action list includes presentation-only card actions:

```ts
      { id: "presentation-confirmation", label: "Presentation confirmation", presentation: "confirmation" },
      { id: "presentation-result", label: "Presentation result", presentation: "result" },
```

Then update the expectations:

```ts
    expect(actions.filter(actionHasCardScopedOwnership).map((action) => action.label)).toEqual([
      "Run backtest",
      "Explain result",
      "Save",
      "Presentation confirmation",
      "Presentation result",
    ]);
    expect(visibleComposerActions(actions).map((action) => action.label)).toEqual([
      "Try again",
      "Ask follow-up",
    ]);
```

Add a source guard to the assistant-turn controls test:

```ts
    const chat = readFileSync(
      join(root, "components/chat/ChatInterface.tsx"),
      "utf-8",
    );

    expect(chat).toContain("visibleComposerActions(latestAi?.actions ?? [])");
```

- [ ] **Step 2: Run the failing ownership tests**

Run:

```bash
cd web && bun test __tests__/chat-turn-artifact-ux.test.ts
```

Expected: fail because `visibleComposerActions` filters by `isCardScopedAction` instead of `actionHasCardScopedOwnership`, and `latestInputActions` still has custom filtering.

- [ ] **Step 3: Patch shared ownership filtering**

Modify `web/lib/chat-action-ownership.ts`:

```ts
export function visibleComposerActions(actions: ChatActionOption[]) {
  return visibleInputActions(actions).filter(
    (action) => !actionHasCardScopedOwnership(action),
  );
}
```

Modify `latestInputActions` in `web/components/chat/ChatInterface.tsx`:

```ts
  return visibleComposerActions(latestAi?.actions ?? []).filter(
    (action) => action.artifactType !== "failed_action",
  );
```

- [ ] **Step 4: Run ownership tests**

Run:

```bash
cd web && bun test __tests__/chat-turn-artifact-ux.test.ts
```

Expected: pass.

- [ ] **Step 5: Commit Task 2**

Run:

```bash
git add web/lib/chat-action-ownership.ts web/components/chat/ChatInterface.tsx web/__tests__/chat-turn-artifact-ux.test.ts
git commit -m "fix(chat): keep card actions on artifact surfaces"
```

Expected: commit succeeds.

---

### Task 3: Add Job Lifecycle Matrix Coverage

**Files:**
- Modify: `web/__tests__/chat-backtest-jobs.test.ts`

- [ ] **Step 1: Add terminal and pollable status tests**

Add these tests inside `describe("chat backtest jobs", () => { ... })`:

```ts
  test("pending job ids keep queued running and succeeded-without-run pollable", () => {
    const messages: Message[] = [
      { ...queuedJobMessage(), id: "queued", backtestJob: job({ id: "queued", status: "queued" }) },
      { ...queuedJobMessage(), id: "running", backtestJob: job({ id: "running", status: "running" }) },
      { ...queuedJobMessage(), id: "succeeded", backtestJob: job({ id: "succeeded", status: "succeeded" }) },
      { ...queuedJobMessage(), id: "failed", backtestJob: job({ id: "failed", status: "failed" }) },
      { ...queuedJobMessage(), id: "canceled", backtestJob: job({ id: "canceled", status: "canceled" }) },
      { ...queuedJobMessage(), id: "expired", backtestJob: job({ id: "expired", status: "expired" }) },
    ];

    expect(pendingBacktestJobIds(messages)).toEqual(["queued", "running", "succeeded"]);
  });

  test("canceled durable job settles request-sent confirmation status", () => {
    const confirmationMessage: Message = supersedePriorConfirmations(
      {
        id: "confirmation-message-1",
        role: "ai",
        kind: "strategy_confirmation",
        confirmation: {
          confirmation_id: "confirmation-1",
          confirmation_state: "active",
          title: "AAPL buy and hold",
          statusLabel: "Ready to run",
          summary: "Ready to test AAPL.",
          rows: [],
          actions: [],
        },
        actions: [],
      },
      "Running",
    );
    const queuedMessages = applyBacktestJobUpdate(
      [confirmationMessage, queuedJobMessage()],
      {
        job: job({ status: "running" }),
        run: null,
      },
    );
    const [settledConfirmation, canceledJob] = applyBacktestJobUpdate(
      queuedMessages,
      {
        job: job({
          status: "canceled",
          finished_at: "2026-06-06T12:00:04Z",
        }),
        run: null,
      },
    );

    expect(settledConfirmation.confirmation?.statusLabel).toBe("Not completed");
    expect(settledConfirmation.confirmation?.status).toBe("not_completed");
    expect(canceledJob.kind).toBe("backtest_job");
    expect(canceledJob.backtestJob?.status).toBe("canceled");
    expect(pendingBacktestJobIds([canceledJob])).toEqual([]);
  });
```

- [ ] **Step 2: Run lifecycle matrix tests**

Run:

```bash
cd web && bun test __tests__/chat-backtest-jobs.test.ts
```

Expected: pass if current behavior already matches the matrix; fail if the audit finds a mismatch.

- [ ] **Step 3: Patch only if the tests fail**

If `pendingBacktestJobIds` fails, keep this intended status set in `web/lib/chat-backtest-jobs.ts`:

```ts
const ACTIVE_JOB_STATUSES = new Set<BacktestJobStatus>([
  "queued",
  "running",
  "succeeded",
]);
```

If canceled confirmation settlement fails, keep this intended terminal mapping in `confirmationStatusForJob`:

```ts
  if (status === "canceled" || status === "expired") {
    return "not_completed";
  }
```

- [ ] **Step 4: Rerun lifecycle matrix tests**

Run:

```bash
cd web && bun test __tests__/chat-backtest-jobs.test.ts
```

Expected: pass.

- [ ] **Step 5: Commit Task 3**

Run:

```bash
git add web/lib/chat-backtest-jobs.ts web/__tests__/chat-backtest-jobs.test.ts
git commit -m "test(chat): cover async job lifecycle parity"
```

Expected: commit succeeds. If no production file changed, stage only the test file and keep the same commit message.

---

### Task 4: Add Backend Job Status Parity Coverage

**Files:**
- Modify: `tests/test_backtest_jobs_async.py`

- [ ] **Step 1: Add terminal workflow reconciliation tests**

Add these tests near `test_terminal_render_task_timeout_reconciles_running_job`:

```py
def test_terminal_render_task_cancellation_reconciles_as_non_retryable() -> None:
    from argus.api.chat.backtest_jobs import reconcile_terminal_render_task_run

    gateway = _TimedOutJobGateway()
    task_client = _FakeTerminalTaskRunClient(
        {
            "id": "trn-timeout-1",
            "status": "canceled",
            "error": "canceled by operator",
            "completedAt": "2026-06-06T12:01:10Z",
        }
    )

    reconciled = reconcile_terminal_render_task_run(
        gateway=gateway,
        user_id="user-1",
        job=gateway.get_backtest_job(user_id="user-1", job_id="job-timeout-1"),
        task_run_client=task_client,
    )

    assert reconciled["status"] == "failed"
    assert reconciled["failure_code"] == "workflow_task_canceled"
    assert reconciled["retryable"] is False
    assert gateway.failed_updates[0]["failure_detail"] == (
        "Backtest execution was canceled before finishing."
    )


def test_terminal_render_task_expiration_reconciles_as_retryable() -> None:
    from argus.api.chat.backtest_jobs import reconcile_terminal_render_task_run

    gateway = _TimedOutJobGateway()
    task_client = _FakeTerminalTaskRunClient(
        {
            "id": "trn-timeout-1",
            "status": "expired",
            "error": "task expired",
            "completedAt": "2026-06-06T12:01:10Z",
        }
    )

    reconciled = reconcile_terminal_render_task_run(
        gateway=gateway,
        user_id="user-1",
        job=gateway.get_backtest_job(user_id="user-1", job_id="job-timeout-1"),
        task_run_client=task_client,
    )

    assert reconciled["status"] == "failed"
    assert reconciled["failure_code"] == "workflow_task_expired"
    assert reconciled["retryable"] is True
    assert gateway.failed_updates[0]["failure_detail"] == (
        "Backtest execution expired before finishing."
    )
```

- [ ] **Step 2: Run backend parity tests**

Run:

```bash
poetry run pytest tests/test_backtest_jobs_async.py::test_terminal_render_task_cancellation_reconciles_as_non_retryable tests/test_backtest_jobs_async.py::test_terminal_render_task_expiration_reconciles_as_retryable -q
```

Expected: pass if backend reconciliation already matches the intended taxonomy; fail if the audit finds a mismatch.

- [ ] **Step 3: Patch only if tests fail**

If cancellation/expiration mapping fails, patch `_workflow_task_failure` in `src/argus/api/chat/backtest_jobs.py` so it keeps this behavior:

```py
    if status in {"canceled", "cancelled"}:
        return (
            "workflow_task_canceled",
            "Backtest execution was canceled before finishing.",
            False,
        )
    if status == "expired":
        return (
            "workflow_task_expired",
            "Backtest execution expired before finishing.",
            True,
        )
```

- [ ] **Step 4: Rerun backend parity tests**

Run:

```bash
poetry run pytest tests/test_backtest_jobs_async.py::test_terminal_render_task_cancellation_reconciles_as_non_retryable tests/test_backtest_jobs_async.py::test_terminal_render_task_expiration_reconciles_as_retryable -q
```

Expected: pass.

- [ ] **Step 5: Commit Task 4**

Run:

```bash
git add tests/test_backtest_jobs_async.py src/argus/api/chat/backtest_jobs.py
git commit -m "test(api): cover terminal workflow job parity"
```

Expected: commit succeeds. If no production file changed, stage only the test file and keep the same commit message.

---

### Task 5: Verify Copy ID Removal And Retry Ownership

**Files:**
- Modify: `web/__tests__/chat-turn-artifact-ux.test.ts`
- Modify: `web/__tests__/backtest-job-card-copy.test.ts`

- [ ] **Step 1: Add UI guard for hidden Copy ID**

Add this test to `web/__tests__/chat-turn-artifact-ux.test.ts`:

```ts
  test("assistant more menu hides internal message ids", () => {
    const message = readFileSync(
      join(root, "components/chat/ChatMessage.tsx"),
      "utf-8",
    );

    expect(message).toContain("chat.copy_plaintext");
    expect(message).toContain("chat.report_issue");
    expect(message).not.toContain("chat.copy_id");
    expect(message).not.toContain("handleCopy(message.id)");
  });
```

- [ ] **Step 2: Add retry-copy matrix coverage**

Update `web/__tests__/backtest-job-card-copy.test.ts` with:

```ts
  test("never uses retry copy for canceled or expired jobs", () => {
    expect(backtestJobCardCopy(job({ status: "canceled", retryable: true }), {
      canRetry: true,
    }).bodyKey).toBe("chat.backtest_job.expired_body");

    expect(backtestJobCardCopy(job({ status: "expired", retryable: true }), {
      canRetry: true,
    }).bodyKey).toBe("chat.backtest_job.expired_body");
  });
```

- [ ] **Step 3: Run UI ownership tests**

Run:

```bash
cd web && bun test __tests__/chat-turn-artifact-ux.test.ts __tests__/backtest-job-card-copy.test.ts
```

Expected: pass after Task 1 removes `Copy ID`; fail if any internal-id UI remains.

- [ ] **Step 4: Patch only if tests fail**

If `chat.copy_id` still appears in `ChatMessage.tsx`, remove the remaining menu item. Keep locale keys in `common.json` untouched unless they are unused by broader UI cleanup, because this slice hides the action rather than performing a locale inventory.

- [ ] **Step 5: Commit Task 5**

Run:

```bash
git add web/components/chat/ChatMessage.tsx web/__tests__/chat-turn-artifact-ux.test.ts web/__tests__/backtest-job-card-copy.test.ts
git commit -m "fix(chat): hide internal message id action"
```

Expected: commit succeeds. If Task 1 already committed the production removal, this commit may contain only tests.

---

### Task 6: Local Verification

**Files:**
- No planned file changes.

- [ ] **Step 1: Run focused frontend lifecycle tests**

Run:

```bash
cd web && bun test __tests__/chat-backtest-jobs.test.ts __tests__/backtest-job-card-copy.test.ts __tests__/chat-turn-artifact-ux.test.ts __tests__/chat-retry-actions.test.ts __tests__/chat-artifact-history.test.ts __tests__/chat-message-feedback-context.test.ts
```

Expected: all tests pass.

- [ ] **Step 2: Run focused backend lifecycle tests**

Run:

```bash
poetry run pytest tests/test_backtest_jobs_async.py::test_backtest_job_status_endpoint_returns_job_and_result tests/test_backtest_jobs_async.py::test_backtest_job_status_endpoint_reconciles_terminal_workflow_run tests/test_backtest_jobs_async.py::test_terminal_render_task_cancellation_reconciles_as_non_retryable tests/test_backtest_jobs_async.py::test_terminal_render_task_expiration_reconciles_as_retryable tests/test_chat_stream_contract.py::test_chat_stream_runtime_failure_persists_retry_last_turn_metadata -q
```

Expected: all tests pass.

- [ ] **Step 3: Run frontend build**

Run:

```bash
cd web && bun run build
```

Expected: build exits successfully.

- [ ] **Step 4: Run diff hygiene**

Run:

```bash
git diff --check
```

Expected: no whitespace errors.

- [ ] **Step 5: Commit verification-only doc update if needed**

If verification evidence is added to `docs/specs/private-alpha-status-action-parity-audit.md`, run:

```bash
git add docs/specs/private-alpha-status-action-parity-audit.md
git commit -m "docs(chat): record status action parity verification"
```

Expected: commit succeeds. Skip this step if no verification evidence is written to docs.

---

### Task 7: Live QA And Browser Smoke

**Files:**
- No planned file changes unless QA evidence is intentionally appended to the spec.

- [ ] **Step 1: Start backend QA mode**

Run in a terminal session:

```bash
.github/qa.sh
```

Expected:
- Backend starts on `http://127.0.0.1:8000`.
- QA mode uses Supabase persistence, live provider asset resolution, Postgres checkpointer, and real backend auth validation.

- [ ] **Step 2: Start frontend with real auth QA settings**

Ensure `web/.env.local` contains:

```bash
NEXT_PUBLIC_MOCK_AUTH=false
NEXT_PUBLIC_ARGUS_API_URL=http://127.0.0.1:8000/api/v1
NEXT_PUBLIC_STRATEGIES_ENABLED=false
NEXT_PUBLIC_COLLECTIONS_ENABLED=false
NEXT_PUBLIC_CHAT_EXPLORATORY_SUGGESTIONS_ENABLED=false
```

Then run:

```bash
cd web && bun run dev
```

Expected: frontend starts on `http://localhost:3000`.

- [ ] **Step 3: Run browser QA for the happy path**

Use Codex browser QA against `http://localhost:3000`.

Flow:
1. Sign in with private-alpha credentials.
2. Start or open a chat.
3. Ask: `Backtest AAPL from 2024 to 2025.`
4. Confirm the confirmation card owns the run/edit/cancel actions.
5. Click `Run backtest`.
6. Observe queued/running job card state.
7. Wait for result card hydration.
8. Confirm the historical confirmation settles to complete and no longer has run actions.
9. Click `Explain result` and confirm the action is card-owned.
10. Open the assistant more menu and confirm `Copy ID` is not visible.
11. Submit positive or negative feedback and confirm no UI error appears.

Expected: flow completes without console errors, duplicate action surfaces, stale running labels, or hidden id menu items.

- [ ] **Step 4: Run browser QA for failed or not-completed path**

Use the lowest-risk available path:
- If a known unsupported/invalid executable request reliably produces a failed job, use it.
- If no safe live failure path is available, use QA/local API controls or a focused seeded job row only if the existing QA environment already supports that without schema or production-data changes.

Expected:
- failed/canceled/expired job card does not promise retry unless a structured retry action is present;
- confirmation history settles to `Could not run` or `Not completed`;
- no frontend-prose retry inference appears.

- [ ] **Step 5: Capture QA evidence**

Record in the final report:
- backend/frontend commands used;
- browser target URL;
- happy-path status sequence observed;
- failed/not-completed status sequence observed or the reason a live terminal path could not be safely induced;
- console errors, if any;
- screenshots if useful.

- [ ] **Step 6: Final commit if QA evidence is documented**

If QA evidence is appended to the spec, run:

```bash
git add docs/specs/private-alpha-status-action-parity-audit.md
git commit -m "docs(chat): capture status action parity QA"
```

Expected: commit succeeds. Skip this step if evidence stays only in the final report.

---

## Final Verification Checklist

- [ ] `cd web && bun test __tests__/chat-backtest-jobs.test.ts __tests__/backtest-job-card-copy.test.ts __tests__/chat-turn-artifact-ux.test.ts __tests__/chat-retry-actions.test.ts __tests__/chat-artifact-history.test.ts __tests__/chat-message-feedback-context.test.ts`
- [ ] `poetry run pytest tests/test_backtest_jobs_async.py::test_backtest_job_status_endpoint_returns_job_and_result tests/test_backtest_jobs_async.py::test_backtest_job_status_endpoint_reconciles_terminal_workflow_run tests/test_backtest_jobs_async.py::test_terminal_render_task_cancellation_reconciles_as_non_retryable tests/test_backtest_jobs_async.py::test_terminal_render_task_expiration_reconciles_as_retryable tests/test_chat_stream_contract.py::test_chat_stream_runtime_failure_persists_retry_last_turn_metadata -q`
- [ ] `cd web && bun run build`
- [ ] `git diff --check`
- [ ] Browser QA happy path completed.
- [ ] Browser QA failed/not-completed path completed or explicitly documented as unsafe to induce.
- [ ] No direct async-job retry added.
- [ ] Save remains functional when metadata exists, with no hidden surface enabled.
- [ ] `Copy ID` hidden from the assistant more menu.
- [ ] Final branch has coherent conventional commits.

## Self-Review Notes

- Spec coverage: the plan maps every spec requirement to Task 1 through Task 7.
- Placeholder scan: no open-ended implementation placeholders are intentionally left; conditional patch steps include exact target behavior.
- Type consistency: helper names, action names, status names, and file paths match the current codebase.
