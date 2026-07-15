# Issue #197 Async Result Hydration Implementation Plan

> **For Codex:** Execute test-first and stop after opening a focused PR against `codex/private-alpha-next`; do not deploy the repair before founder merge approval.

**Goal:** Make a completed real-workflow result and its decision hydrate from canonical run evidence after reload, while ensuring failed-canary captures redact embedded artifact identifiers.

**Architecture:** Supabase message reads will reconcile assistant messages that still contain a queued backtest job against the owned durable job and completed run. The response projection will reuse the canonical run card, result fact bank, and workflow readout; decision writes can then persist that projected card through the existing message update path. Canary capture sanitization will move to a small standard-library helper shared by capture generation and replay validation.

**Tech Stack:** Python 3.10, FastAPI/Pydantic models, Supabase gateway, pytest, Bash canary wrapper.

---

### Task 1: Reproduce async reload hydration failure

**Files:**
- Create: `tests/test_backtest_message_projection.py`
- Modify: `tests/test_chat_runtime_reload_guardrails.py`

1. Add a focused unit test where an assistant message contains a stale queued job, the durable job is succeeded, and the canonical run card contains evidence and decision metadata.
2. Require the projection to replace queued content with the workflow readout and attach canonical result metadata without leaking execution metadata.
3. Add a route-level regression proving `/conversations/{id}/messages` invokes the reconciliation path for Supabase-backed history.
4. Run the focused tests and confirm they fail before implementation.

### Task 2: Implement canonical result-message reconciliation

**Files:**
- Create: `src/argus/domain/backtest_message_projection.py`
- Modify: `src/argus/api/chat/artifacts.py`
- Modify: `src/argus/domain/supabase_gateway.py`

1. Add a pure projection helper with cached job/run loaders and a public-field-only job snapshot.
2. Reuse one shared canonical `result_fact_bank` builder for synchronous and asynchronous result metadata.
3. Apply the projection when Supabase lists messages; leave incomplete, failed, foreign, or missing jobs unchanged.
4. Run focused projection, reload, async-job, and API tests.

### Task 3: Reproduce and fix failed-capture privacy leak

**Files:**
- Create: `scripts/ops/canary_capture_sanitizer.py`
- Create: `tests/test_canary_capture_sanitizer.py`
- Modify: `.github/canary-render.sh`

1. Add failing tests for raw UUIDs in `artifact_id`, `confirmation_id`, and UUIDs embedded inside longer strings.
2. Implement recursive standard-library sanitization and validation with stable hashed labels.
3. Import the helper from canary capture generation and self-validate every written capture.
4. Run capture-sanitizer and canary-script tests.

### Task 4: Verify and publish the bounded repair

**Files:**
- Modify only files above.

1. Run formatting/lint/type checks for touched Python and shell surfaces.
2. Run focused backend suites, mocked agent-runtime/eval gates, frontend tests relevant to async job hydration, and `.github/local-smoke.sh`.
3. Perform the required two-layer review and verify the final diff against Argus canon and issue #197 boundaries.
4. Commit with a conventional message, push the issue branch, and open a focused draft PR against `codex/private-alpha-next`.
5. Post only sanitized failure evidence and the PR link to #197; leave #197 open and stop for founder merge approval.
