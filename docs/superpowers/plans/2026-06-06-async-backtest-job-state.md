# Async Backtest Job State Implementation Plan

> [!NOTE]
> Historical context. This document is retained as implementation evidence and is not the current execution source of truth.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move chat-confirmed `Run backtest` actions onto durable real Render Workflow jobs and hydrate queued/running/succeeded/failed state in chat without holding the API SSE stream open for the backtest duration.

**Architecture:** Keep LangGraph as the only chat runtime. In real workflow mode, the existing backtest tool wrapper creates or reuses a `backtest_jobs` row, dispatches `argus-backtests/run_backtest_job`, and returns an accepted job artifact instead of invoking the in-process engine. The frontend renders a job card from backend-provided job metadata, polls a small REST fallback endpoint for durable job state, and replaces a succeeded job with the canonical `backtest_runs` result card.

**Tech Stack:** FastAPI, Pydantic, Supabase-backed persistence gateway, Render Workflows, LangGraph stage results, Next.js/React, Bun/Vitest-style unit tests, pytest.

---

### Task 1: Contract And Schema Surface

**Files:**
- Modify: `docs/API_CONTRACT.md`
- Modify: `docs/api/openapi.yaml`
- Modify: `src/argus/api/schemas.py`

- [x] **Step 1: Add API contract text for job hydration**

  Add a formal polling fallback below `POST /backtests/run`:

  ```markdown
  ## `GET /backtest-jobs/{id}`

  Returns the durable lifecycle state for one user-owned async backtest job.
  This endpoint is a recovery/polling fallback for browsers that missed
  Supabase Realtime updates; the durable job row remains the source of truth.

  **Response:**
  ```json
  {
    "job": {
      "id": "uuid",
      "conversation_id": "uuid",
      "status": "queued",
      "result_run_id": null,
      "failure_code": null,
      "failure_detail": null,
      "retryable": false
    },
    "run": null
  }
  ```
  ```

- [x] **Step 2: Add Pydantic models**

  Add `BacktestJobStatus`, `BacktestJob`, and `BacktestJobResponse`:

  ```python
  BacktestJobStatus = Literal[
      "queued", "running", "succeeded", "failed", "canceled", "expired"
  ]

  class BacktestJob(BaseModel):
      id: str
      conversation_id: str
      request_message_id: str | None = None
      confirmation_message_id: str | None = None
      status: BacktestJobStatus
      result_run_id: str | None = None
      failure_code: str | None = None
      failure_detail: str | None = None
      retryable: bool = False
      queued_at: datetime | None = None
      started_at: datetime | None = None
      finished_at: datetime | None = None
      created_at: datetime | None = None
      updated_at: datetime | None = None

  class BacktestJobResponse(BaseModel):
      job: BacktestJob
      run: BacktestRun | None = None
  ```

- [x] **Step 3: Run a schema import check**

  Run:

  ```bash
  poetry run python - <<'PY'
  from argus.api.schemas import BacktestJob, BacktestJobResponse
  print(BacktestJob.__name__, BacktestJobResponse.__name__)
  PY
  ```

  Expected: prints `BacktestJob BacktestJobResponse`.

### Task 2: Backend Async Job Acceptance

**Files:**
- Modify: `src/argus/api/chat/backtest_jobs.py`
- Modify: `src/argus/agent_runtime/stages/execute.py`
- Modify: `src/argus/api/routers/agent.py`
- Modify: `src/argus/api/routers/backtest.py`
- Modify: `src/argus/domain/supabase_gateway.py`
- Test: `tests/test_backtest_jobs_async.py`
- Test: `tests/test_backtest_jobs_shadow.py`

- [x] **Step 1: Write red tests for accepted job execution**

  Add tests that assert real workflow mode creates a `run_backtest_job` launch payload, dispatches `argus-backtests/run_backtest_job`, returns an async job envelope, and does not call the delegate:

  ```python
  def test_real_workflow_mode_returns_async_job_without_delegate(monkeypatch):
      monkeypatch.setenv("ARGUS_BACKTEST_JOBS_SHADOW_ENABLED", "true")
      monkeypatch.setenv("ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED", "true")
      monkeypatch.setenv("ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED", "true")
      result = tool.run(_payload())
      assert result["success"] is True
      assert result["payload"]["backtest_job"]["status"] == "queued"
      assert delegate.calls == []
  ```

- [x] **Step 2: Verify the red tests fail**

  Run:

  ```bash
  poetry run pytest tests/test_backtest_jobs_async.py -q --no-cov
  ```

  Expected: failures show the delegate is still called or no async job payload exists.

- [x] **Step 3: Return async job envelopes in real workflow mode**

  Change `ShadowBacktestJobTool.run()` so real workflow execution with dispatch enabled returns:

  ```python
  {
      "success": True,
      "payload": {
          "backtest_job": public_backtest_job_payload(job),
      },
      "error_type": None,
      "error_message": None,
      "retryable": False,
      "capability_context": {"execution_status": "queued"},
  }
  ```

  Only skip the delegate when a durable real job exists and dispatch was started or restored from idempotent metadata.

- [x] **Step 4: Teach execute stage to end with a job artifact**

  In `execute_stage()`, detect `payload.backtest_job` and return `ready_to_respond` with:

  ```python
  StageResult(
      outcome="ready_to_respond",
      stage_patch={
          "tool_call_records": records,
          "failure_classification": None,
          "assistant_response": async_backtest_job_message(job),
          "final_response_payload": {"backtest_job": job},
          "artifact_references": [
              ArtifactReference(
                  artifact_kind="backtest_job",
                  artifact_id=job["id"],
                  artifact_status=job["status"],
                  metadata=job,
              ).model_dump(mode="python")
          ],
      },
  )
  ```

- [x] **Step 5: Persist job artifact metadata from chat stream**

  In `agent.py`, when final payload contains `backtest_job`, persist:

  ```python
  metadata["backtest_job"] = job
  metadata["backtest_job_id"] = job["id"]
  runtime_result["backtest_job"] = job
  ```

- [x] **Step 6: Add job status endpoint**

  Add `GET /api/v1/backtest-jobs/{job_id}` to `backtest.py`. It reads `api_state.supabase_gateway.get_backtest_job()`, fetches `result_run_id` when present, returns `BacktestJobResponse`, and returns 404 for missing or unowned jobs.

- [x] **Step 7: Verify backend green**

  Run:

  ```bash
  poetry run pytest tests/test_backtest_jobs_async.py tests/test_backtest_jobs_shadow.py tests/test_render_workflow_execution.py -q --no-cov
  ```

  Expected: all selected tests pass.

### Task 3: Frontend Job Types, Hydration, And Polling Fallback

**Files:**
- Modify: `web/lib/argus-api.ts`
- Create: `web/lib/chat-backtest-jobs.ts`
- Modify: `web/components/chat/types.ts`
- Create: `web/components/chat/BacktestJobCard.tsx`
- Modify: `web/components/chat/ChatMessage.tsx`
- Modify: `web/components/chat/ChatInterface.tsx`
- Modify: `web/public/locales/en/common.json`
- Modify: `web/public/locales/es-419/common.json`
- Test: `web/__tests__/chat-backtest-jobs.test.ts`
- Test: `web/__tests__/chat-artifact-history.test.ts`

- [x] **Step 1: Write red frontend tests**

  Add tests that assert job metadata hydrates to a `backtest_job` message, failed jobs remain failed, and a succeeded job with a run becomes a strategy result:

  ```ts
  test("applies a failed durable job update without leaving Running visible", () => {
    const messages = applyBacktestJobUpdate([queuedJobMessage()], {
      job: failedJob(),
      run: null,
    });
    expect(messages[0].kind).toBe("backtest_job");
    expect(messages[0].backtestJob?.status).toBe("failed");
  });
  ```

- [x] **Step 2: Verify frontend red**

  Run:

  ```bash
  cd web && bun test __tests__/chat-backtest-jobs.test.ts
  ```

  Expected: module or helper functions are missing.

- [x] **Step 3: Add API types and fetcher**

  Add `BacktestJobStatus`, `BacktestJob`, `BacktestJobResponse`, and:

  ```ts
  export async function getBacktestJob(jobId: string) {
    return apiFetch<BacktestJobResponse>(`/backtest-jobs/${jobId}`);
  }
  ```

- [x] **Step 4: Add pure job-state helpers**

  Implement `jobMessageFromMetadata()`, `applyBacktestJobUpdate()`, and `pendingBacktestJobIds()` in `web/lib/chat-backtest-jobs.ts`. These helpers must use backend `job` and `run` objects only.

- [x] **Step 5: Render the job card**

  Add `BacktestJobCard` with calm status copy for `queued`, `running`, `failed`, `canceled`, and `expired`. For `succeeded` without a run, display a brief loading/recovery state until polling fetches the canonical run.

- [x] **Step 6: Poll visible jobs after stream and reload**

  In `ChatInterface`, when final payload includes `backtest_job`, render a job card and schedule polling. Add an effect that polls visible queued/running job messages and replaces succeeded jobs with result cards from `run`.

- [x] **Step 7: Verify frontend green**

  Run:

  ```bash
  cd web && bun test __tests__/chat-backtest-jobs.test.ts __tests__/chat-artifact-history.test.ts
  ```

  Expected: all selected frontend tests pass.

### Task 4: Focused And Operational Verification

**Files:**
- Verify working tree and touched docs/code only.

- [x] **Step 1: Run focused backend tests**

  Run:

  ```bash
  poetry run pytest tests/test_backtest_jobs_async.py tests/test_backtest_jobs_shadow.py tests/test_render_workflow_execution.py tests/test_chat_stream_contract.py -q --no-cov
  ```

- [x] **Step 2: Run focused frontend tests**

  Run:

  ```bash
  cd web && bun test __tests__/chat-backtest-jobs.test.ts __tests__/chat-artifact-history.test.ts __tests__/chat-message-hydration.test.ts
  ```

- [x] **Step 3: Run lint and build**

  Run:

  ```bash
  poetry run ruff check .
  cd web && bun test
  cd web && bun run build
  ```

- [x] **Step 4: Keep live config safe**

  Run:

  ```bash
  .github/warmup-render.sh --expect-mode safe-off
  ```

  Expected: live API remains safe/off. Do not sync `api-real-workflow-on` unless explicitly validating one internet smoke.

- [x] **Step 5: Commit and push**

  Run:

  ```bash
  git status --short
  git add docs/API_CONTRACT.md docs/api/openapi.yaml src/argus web tests
  git commit -m "feat(backtests): render async workflow job state"
  git push
  ```

  Expected: branch is clean and pushed to `origin/codex/render-workflow-proof`.

### Self-Review

- Spec coverage: the plan covers real job creation/dispatch, proof task separation, API quick return, frontend queued/running/succeeded/failed rendering, reload hydration through durable job polling, and safe/off operational verification.
- Placeholder scan: no implementation step relies on an undefined endpoint or undocumented payload shape.
- Type consistency: backend `BacktestJobResponse` maps to frontend `BacktestJobResponse`; job status values match `docs/API_CONTRACT.md` and `docs/DATA_MODEL.md`.
