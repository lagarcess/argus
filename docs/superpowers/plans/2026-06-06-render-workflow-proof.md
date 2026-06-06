# Render Workflow Proof Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate the Render Workflow execution boundary with a tiny durable proof job before moving real backtests out of the API.

**Architecture:** Add the future `backtest_jobs` durable boundary now, then run a proof-only Render Workflow task that transitions one proof job from `queued` to `running` to `succeeded`. Keep workflow dependencies isolated under `workflows/` so the API import graph and chat/runtime behavior remain unchanged.

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
- Create: `workflows/requirements.txt`
- Test: `tests/test_render_workflow_proof.py`

- [x] Implement a pure `run_workflow_proof()` function that accepts a gateway, validates `launch_payload.kind == "render_workflow_proof"`, writes `running`, writes `succeeded`, reads back the row, and returns a JSON-safe result.
- [x] Implement a `PostgresProofJobGateway` backed by `DATABASE_URL`.
- [x] Register `workflow_proof(job_id, nonce)` in `workflows/main.py` using Render Workflows.

### Task 3: Validation Entry Points

**Files:**
- Create: `workflows/trigger_proof.py`
- Create: `.github/workflow-proof.sh`
- Modify: `.env.example`
- Modify: `.github/argus-env.sh`
- Test: `tests/test_environment_scripts.py`

- [x] Add a CLI that can seed a proof row, trigger local/remote Render task execution, and verify the row.
- [x] Add a shell wrapper with explicit `seed`, `local`, `remote`, `verify`, and `direct` commands.
- [x] Document required secret and non-secret environment variables.

### Task 4: Verification

**Commands:**
- `poetry run pytest tests/test_render_workflow_proof.py tests/test_environment_scripts.py tests/test_alpha_artifacts.py tests/test_render_runtime_compatibility.py -q --no-cov`
- `git status --short --branch`

- [x] Confirm focused tests pass.
- [ ] Report external blockers separately: Render CLI, Supabase CLI/local project config, Render Dashboard service creation, and sandbox Supabase credentials.
