# Issue 542 Durable Backtest Failures Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent a completed launch's confirmation identity from being reused and make every later admission refusal a durable, user-visible failed job with a recorded reason.

**Architecture:** Treat the existing job reservation as the single source of truth for whether a confirmation identity is spent. Rotate a spent identity before publishing a new confirmation card. When admission still refuses a launch, insert a separate terminal job receipt without overwriting the earlier reservation, then derive the assistant response from that job's `failure_code`.

**Tech Stack:** Python 3.10, FastAPI, Pydantic, Supabase/PostgREST, pytest.

**Spec:** GitHub issue #542 and its production evidence for conversation `91931579-0cc8-4fa0-bedd-726abb0afa9c`.

## Global Constraints

- Start from `codex/private-alpha-next` commit `5d408acf6b1ed9608dfe8b757ff41372f9b9daeb`.
- Do not edit the issue's named no-touch files or sharing surfaces.
- Preserve the earlier successful reservation and completed run.
- Do not merge or deploy; return a reviewed PR to the founder.

---

### Task 1: Lock the production reproduction into failing tests

**Files:**
- Create: `tests/test_issue_542_durable_backtest_failures.py`
- Reference: `src/argus/api/chat/artifacts.py`
- Reference: `src/argus/api/chat/backtest_jobs.py`
- Reference: `src/argus/agent_runtime/stages/execute.py`

- [x] Add a test with the earlier three-symbol reservation and a new five-symbol, `$100,000`, buy-and-hold confirmation ending on the current day; assert the spent confirmation ID is replaced before the card is published.
- [x] Add an admission-conflict reproduction using the same five-symbol payload; assert a new failed job exists with both `failure_code` and `failure_detail` while the earlier successful job remains unchanged.
- [x] Assert the assistant response names the recorded reason and does not use the generic “could not complete” string.
- [x] Run the focused test file and confirm it fails for the expected missing invariants.

### Task 2: Enforce single-use confirmation identities

**Files:**
- Modify: `src/argus/api/chat/artifacts.py`
- Modify: `src/argus/api/routers/agent.py`
- Test: `tests/test_issue_542_durable_backtest_failures.py`

- [x] Add one artifact-boundary helper that reads the durable chat-run reservation for the proposed confirmation ID.
- [x] If the reservation exists, mint a fresh ID and update the confirmation payload's identity fields before building the card and artifact reference.
- [x] Leave unused identities unchanged and preserve request replay behavior.
- [x] Run the identity reproduction test and confirm it passes.

### Task 3: Persist rejected launches as failed job receipts

**Files:**
- Modify: `src/argus/api/chat/backtest_job_envelopes.py`
- Modify: `src/argus/api/chat/backtest_admission_flow.py`
- Modify: `src/argus/api/chat/backtest_jobs.py`
- Modify: `src/argus/domain/backtest_admission_gateway.py`
- Modify: `src/argus/domain/supabase_gateway.py`
- Test: `tests/test_issue_542_durable_backtest_failures.py`
- Test: `tests/test_backtest_jobs_shadow.py`

- [x] Define one canonical mapping from admission decision to failure code, detail, and retryability.
- [x] Insert an atomic terminal `backtest_jobs` receipt for admission rejections, with a stable derived receipt key so transport replay cannot duplicate the failure and the earlier successful reservation is never mutated.
- [x] Return the stored job through the runtime so assistant-message metadata links to the durable failure.
- [x] Update existing admission-rejection tests to require a failed job rather than no row.
- [x] Run the focused admission and issue tests.

### Task 4: Derive failure copy from the stored job reason

**Files:**
- Modify: `src/argus/agent_runtime/stages/execute.py`
- Modify: `src/argus/domain/engine_launch/results.py`
- Test: `tests/test_issue_542_durable_backtest_failures.py`
- Test: `tests/agent_runtime/test_capacity_refusal_copy.py`

- [x] Handle terminal async jobs as execution failures while retaining the job artifact in the stage result.
- [x] Select user-safe copy from the job's recorded `failure_code`; keep capacity recovery retryable and preserve account-conversion signaling.
- [x] Add safe copy for admission conflict and other pre-start rejection codes.
- [x] Run the focused execution-copy tests.

### Task 5: Update contracts and verify the repaired slice

**Files:**
- Modify: `docs/API_CONTRACT.md`
- Modify: `docs/DATA_MODEL.md`
- Modify: `docs/reports/evidence/542/README.md`
- Test: focused backend suites from Tasks 1-4

- [x] Document that confirmation identities become spent once reserved and that admission refusals persist as terminal job receipts without consuming allowance.
- [x] Record the production trigger, why the current-day coverage-hash regression is not the trigger on this base, the focused commands, and results in durable evidence.
- [x] Run formatting, type/static checks required by the touched surfaces, the focused pytest matrix, and the modularity-budget check.
- [x] Confirm no forbidden file changed and inspect the final diff for proportionality.

### Task 6: Reconcile, publish, and report without merging

**Files:**
- Modify only if reconciliation requires it: files already in scope

- [x] Fetch `origin/codex/private-alpha-next`, record its current SHA, and compare semantic overlap with the original base.
- [x] If integration advanced, merge it one way into this worker branch and rerun only invalidated evidence plus exact-head deterministic gates. (Not needed: integration remained at the original base.)
- [x] Commit with a conventional message, push the branch, and open a Draft PR targeting `codex/private-alpha-next` with `Closes #542` and the required structured sections.
- [x] Add existing relevant labels, request review, inspect unresolved threads, and report exact-head CI state.
- [ ] Stop with the PR open; do not merge or deploy.
