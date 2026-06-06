# Render Workflow Proof Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate the Render Workflow execution boundary with a tiny durable proof job before moving real backtests out of the API.

**Architecture:** Add the future `backtest_jobs` durable boundary now, then run a proof-only Render Workflow task that transitions one proof job from `queued` to `running` to `succeeded`. Keep workflow dependencies isolated in the optional Poetry `workflows` group so the API import graph and chat/runtime behavior remain unchanged.

**Tech Stack:** Python 3.10, Render Workflows Python SDK, psycopg, Supabase Postgres, pytest.

---

### Task 1: Durable Job Boundary

**Files:**
- Create: `supabase/migrations/20260606000001_add_backtest_jobs.sql`
- Test: `tests/test_render_workflow_proof.py`

- [x] Add `public.backtest_jobs` with future production fields, strict status checks, idempotency indexes, owner-select RLS, and service-role privileges.
- [x] Verify the migration is discoverable and matches `docs/DATA_MODEL.md` / `docs/API_CONTRACT.md` job shape.

### Task 2: Proof Workflow

**Files:**
- Create: `workflows/__init__.py`
- Create: `workflows/proof.py`
- Create: `workflows/main.py`
- Modify: `pyproject.toml`
- Modify: `poetry.lock`
- Test: `tests/test_render_workflow_proof.py`

- [x] Implement a pure `run_workflow_proof()` function that accepts a gateway, validates `launch_payload.kind == "render_workflow_proof"`, writes `running`, writes `succeeded`, reads back the row, and returns a JSON-safe result.
- [x] Implement a `PostgresProofJobGateway` backed by workflow-scoped `ARGUS_WORKFLOW_DATABASE_URL`, with `DATABASE_URL` accepted only as a local/backward-compatible fallback.
- [x] Register `workflow_proof(job_id, nonce)` in `workflows/main.py` using Render Workflows.
- [x] Manage Render Workflow runtime dependencies through Poetry by installing the root package with `main,workflows`; do not maintain a separate `workflows/requirements.txt`.

### Task 3: Validation Entry Points

**Files:**
- Create: `workflows/trigger_proof.py`
- Create: `.github/workflow-proof.sh`
- Modify: `.env.example`
- Modify: `.github/argus-env.sh`
- Test: `tests/test_environment_scripts.py`

- [x] Add a CLI that can seed a proof row, trigger local/remote Render task execution, and verify the row.
- [x] Allow proof seeding to create a disposable preview/local auth profile when no `--user-id` is supplied.
- [x] Add a shell wrapper with explicit `seed`, `local`, `remote`, `verify`, and `direct` commands.
- [x] Document required secret and non-secret environment variables.

### Task 4: Verification

**Commands:**
- `poetry run pytest tests/test_render_workflow_proof.py tests/test_environment_scripts.py tests/test_alpha_artifacts.py tests/test_render_runtime_compatibility.py -q --no-cov`
- `git status --short --branch`

- [x] Confirm focused tests pass.
- [x] Report external blockers separately: Render CLI, Supabase CLI/local project config, Render Dashboard service creation, and sandbox Supabase credentials.

### Task 5: API Shadow Job Creation

**Files:**
- Create: `src/argus/api/chat/backtest_jobs.py`
- Modify: `src/argus/api/state.py`
- Modify: `src/argus/api/routers/agent.py`
- Modify: `src/argus/domain/supabase_gateway.py`
- Test: `tests/test_backtest_jobs_shadow.py`
- Test: `tests/test_supabase_gateway.py`

- [x] Add `ARGUS_BACKTEST_JOBS_SHADOW_ENABLED`, default-off in docs and Render Blueprint defaults.
- [x] Wrap the existing in-process backtest tool so the API can create a durable `backtest_jobs` row before the current user-facing execution path.
- [x] Preserve the current in-process result path as the response shown to the user.
- [x] Link successful in-process `backtest_runs` back to the shadow job through `result_run_id`.
- [x] Fail open in dev/memory fallback mode and fail closed in strict QA mode.

### Task 6: Proof Dispatch And Backpressure

**Files:**
- Modify: `src/argus/api/chat/backtest_jobs.py`
- Modify: `src/argus/domain/supabase_gateway.py`
- Modify: `.github/render-env-sync.sh`
- Modify: `.github/argus-env.sh`
- Modify: `render.yaml`
- Test: `tests/test_backtest_jobs_shadow.py`
- Test: `tests/test_environment_scripts.py`

- [x] Add `ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED`, default-off in docs and Render Blueprint defaults.
- [x] Dispatch the Render Workflow proof task when both shadow and dispatch flags are enabled.
- [x] Persist Render task-run metadata under `execution_metadata.workflow_dispatch`.
- [x] Keep the current API in-process result path as the user-facing result while proof dispatch runs out-of-process.
- [x] Add per-user and global running/queued limits for shadow job creation.
- [x] Add `.github/render-env-sync.sh` commands to inspect redacted API dispatch env, enable dispatch intentionally, disable dispatch, and sync workflow proof env.

### Task 7: Current Boundary And Remaining Scope

This branch now proves the control-plane boundary through a real Render Workflow
task run. A follow-on slice now adds a separate default-off `run_backtest_job`
task for real execution while keeping this proof task available for smoke checks.

- [x] Durable job table exists locally and in live Supabase.
- [x] API can create shadow jobs and link the current in-process run result.
- [x] API can start the Render Workflow proof task when explicitly enabled.
- [x] Backpressure knobs exist for user/global queued and running job limits.
- [x] Render Blueprint defaults keep shadow and dispatch disabled.
- [x] Future slice: move the real backtest engine and heavy dependencies into the Render Workflow execution plane behind `ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED=false` by default.
- [ ] Future slice: add frontend async job-state rendering through Supabase Realtime or API polling.
