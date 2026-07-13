# Issue 194 Shared Backtest Finalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every successful local, direct API, and Render Workflow backtest pass through one typed, idempotent finalizer that atomically publishes the run/evidence tuple and preserves the full Add decision lifecycle.

**Architecture:** Add one domain-level finalization service with typed input/output and a persistence protocol. Memory mode commits through a locked in-memory adapter; Supabase and the Render worker call one transactional PostgreSQL RPC. Callers allocate a stable run id from the owner plus execution identity before finalization, publish only the returned identity, and map finalization failures to the existing retryable failure surfaces.

**Tech Stack:** Python 3.10, Pydantic v2, FastAPI, Supabase/PostgreSQL PL/pgSQL, psycopg 3, pytest, Bun/Vitest.

## Global Constraints

- Target branch is `codex/private-alpha-next`; do not merge to `main` or deploy production.
- Preserve the public job-status enum: `queued`, `running`, `succeeded`, `failed`, `canceled`, `expired`.
- A recoverable persistence failure is `status=failed`, `failure_code=finalization_failed`, `failure_detail=execution_failed`, `retryable=true`, and `result_run_id=null`.
- A completed run is visible only after BacktestRun, Idea, IdeaVersion, EvidenceArtifact, and result-card metadata are committed together.
- The finalizer must be the only writer of this tuple for local, direct API, and Render completion paths.
- Retries reuse the same owner-scoped execution identity and stable run id; duplicate evidence remains blocked by `UNIQUE(user_id, source_run_id)`.
- Keep persistence automatic and commitment explicit; only the existing Add decision action changes lifecycle to `decided`.
- Do not add natural-language routing, localized state, new product surfaces, generic RAG, or a second runtime.
- Preserve context-packet, route-receipt, cost-ledger, and result-readout behavior outside the finalization barrier.

---

### Task 1: Typed finalization boundary and memory atomicity

**Files:**
- Create: `src/argus/domain/backtest_finalization.py`
- Modify: `src/argus/domain/store.py`
- Test: `tests/test_backtest_finalization.py`

**Interfaces:**
- Produces: `stable_backtest_run_id(user_id: str, execution_identity: str) -> str`.
- Produces: frozen `BacktestFinalizationInput` containing owner, execution identity, canonical `BacktestRun`, result card, candidate sidecar ids, and finalization timestamp.
- Produces: frozen `BacktestFinalizedIdentity` containing `run_id`, `idea_id`, `idea_version_id`, and `evidence_artifact_id`.
- Produces: frozen `FinalizedBacktest` containing the canonical run and captured evidence plus `.identity`.
- Produces: `BacktestFinalizationGateway.finalize_backtest_completion(...)` protocol and `MemoryBacktestFinalizationGateway`.
- Produces: `finalize_backtest_completion(gateway, finalization) -> FinalizedBacktest` as the single application boundary.

- [ ] **Step 1: Write failing domain tests**

```python
def test_stable_run_id_is_owner_scoped_and_replay_safe() -> None:
    first = stable_backtest_run_id("user-1", "job:job-1")
    assert first == stable_backtest_run_id("user-1", "job:job-1")
    assert first != stable_backtest_run_id("user-2", "job:job-1")


def test_memory_finalizer_commits_one_complete_tuple_and_reuses_it() -> None:
    store = AlphaStore()
    gateway = MemoryBacktestFinalizationGateway(store)
    first = finalize_backtest_completion(gateway, _input(run_id="run-1"))
    second = finalize_backtest_completion(gateway, _input(run_id="run-1"))
    assert second.identity == first.identity
    assert len(store.backtest_runs) == 1
    assert len(store.ideas) == 1
    assert len(store.idea_versions) == 1
    assert len(store.evidence_artifacts) == 1
    assert store.backtest_runs["run-1"].conversation_result_card[
        "evidence_artifact_id"
    ] == first.identity.evidence_artifact_id
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `poetry run pytest --no-cov tests/test_backtest_finalization.py -q`

Expected: collection/import failure because the typed finalization module does not exist.

- [ ] **Step 3: Implement the minimal typed boundary**

```python
@dataclass(frozen=True)
class BacktestFinalizationInput:
    user_id: str
    execution_identity: str
    run: BacktestRun
    result_card: dict[str, Any]
    idea_id: str
    idea_version_id: str
    evidence_artifact_id: str
    finalized_at: datetime


class BacktestFinalizationGateway(Protocol):
    def finalize_backtest_completion(
        self, *, finalization: BacktestFinalizationInput
    ) -> FinalizedBacktest: ...
```

The application function builds the evidence objects, enriches the run card with stable artifact ids, calls the gateway once, then validates that every returned parent/id relationship is complete and consistent.

- [ ] **Step 4: Implement locked memory commit and replay**

Add an internal `threading.RLock` to `AlphaStore`. Under that lock, return the existing complete tuple for the same owner/run or commit all staged dictionaries without yielding. Reject cross-owner or incomplete existing tuples.

- [ ] **Step 5: Run the domain tests and verify GREEN**

Run: `poetry run pytest --no-cov tests/test_backtest_finalization.py -q`

Expected: all tests pass.

---

### Task 2: Transactional PostgreSQL finalization adapters

**Files:**
- Create: `supabase/migrations/20260713000001_finalize_backtest_completion.sql`
- Modify: `src/argus/domain/supabase_gateway.py`
- Modify: `workflows/backtest_job.py`
- Test: `tests/test_supabase_gateway.py`
- Test: `tests/test_render_workflow_execution.py`
- Test: `tests/test_render_workflow_proof.py`

**Interfaces:**
- Consumes: `BacktestFinalizationInput` and `FinalizedBacktest` from Task 1.
- Produces: service-role-only `public.finalize_backtest_completion(...)` RPC returning run, idea, idea_version, and evidence_artifact JSON.
- Produces: `SupabaseGateway.finalize_backtest_completion(...)`.
- Produces: `PostgresBacktestJobGateway.finalize_backtest_completion(...)`.

- [ ] **Step 1: Write failing migration and adapter tests**

```python
def test_finalization_migration_defines_transactional_service_role_rpc() -> None:
    source = Path(
        "supabase/migrations/20260713000001_finalize_backtest_completion.sql"
    ).read_text()
    assert "function public.finalize_backtest_completion" in source
    assert "grant execute" in source
    assert "to service_role" in source
    assert "revoke all" in source


def test_supabase_finalizer_uses_one_rpc_and_returns_canonical_identity() -> None:
    finalized = gateway.finalize_backtest_completion(finalization=_input())
    assert client.rpc_calls == ["finalize_backtest_completion"]
    assert finalized.identity.evidence_artifact_id == "artifact-1"
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `poetry run pytest --no-cov tests/test_supabase_gateway.py tests/test_render_workflow_proof.py -q -k 'finaliz'`

Expected: failures for missing migration/RPC methods.

- [ ] **Step 3: Add the transactional RPC**

The PL/pgSQL function must:

1. validate non-empty execution identity, completed run status, and owner-owned optional conversation/strategy parents;
2. lock/reuse a run by `id + user_id` and reject an immutable payload collision;
3. lock/reuse an evidence artifact by `user_id + source_run_id` when the tuple already exists;
4. otherwise insert the completed run, Idea with a temporarily null active version, IdeaVersion, active-version link, and EvidenceArtifact inside the function transaction;
5. merge the canonical artifact ids/lifecycle/type into the run result card before returning;
6. return the same canonical tuple on replay, including after an earlier commit whose caller lost the response;
7. revoke public/anon/authenticated access and grant only `service_role`.

- [ ] **Step 4: Implement Supabase and psycopg adapters**

Both adapters serialize the same typed input to the same RPC parameters and validate the four returned models. The Render adapter must call `select * from public.finalize_backtest_completion(...)`; it must not duplicate the insert sequence in worker code.

- [ ] **Step 5: Run adapter tests and verify GREEN**

Run: `poetry run pytest --no-cov tests/test_supabase_gateway.py tests/test_render_workflow_proof.py tests/test_render_workflow_execution.py -q -k 'finaliz or p1_evidence_capture_gateway or postgres_backtest_job_gateway'`

Expected: all selected tests pass.

---

### Task 3: Local chat and direct API callers

**Files:**
- Modify: `src/argus/api/chat/persistence.py`
- Modify: `src/argus/api/chat/evidence.py`
- Modify: `src/argus/api/routers/agent.py`
- Modify: `src/argus/api/routers/backtest.py`
- Modify: `src/argus/api/backtest_service.py`
- Test: `tests/test_p1_evidence_spine.py`
- Test: `tests/test_context_packet_runtime_attachment.py`
- Test: `tests/test_alpha_api.py`
- Test: `tests/test_alpha_api_supabase.py`

**Interfaces:**
- Consumes: shared finalizer and memory/Supabase adapters.
- Changes: `build_runtime_backtest_run(..., run_id: str | None = None)` so the caller can preallocate a stable id.
- Changes: `persist_runtime_backtest_run(..., execution_identity: str)` so chat uses `Idempotency-Key` or request id.
- Changes: `create_run_from_payload(..., run_id: str | None = None, persist_in_memory: bool = False)` so the direct route finalizes instead of publishing early.

- [ ] **Step 1: Write failing local-path tests**

```python
def test_local_runtime_calls_shared_finalizer_before_returning(monkeypatch) -> None:
    observed = []
    monkeypatch.setattr(
        "argus.api.chat.persistence.finalize_backtest_completion",
        lambda gateway, finalization: observed.append(finalization) or _finalized(),
    )
    run = persist_runtime_backtest_run(
        user=_user(),
        conversation=_conversation(),
        result_card=_card(),
        envelope=_envelope(),
        execution_identity="request:req-1",
    )
    assert run is not None
    assert observed[0].run.id == run.id
    assert run.conversation_result_card["evidence_artifact_id"]


def test_direct_backtest_replay_returns_same_finalized_evidence_identity() -> None:
    first = client.post("/api/v1/backtests/run", headers=_headers("key-1"), json=_body())
    second = client.post("/api/v1/backtests/run", headers=_headers("key-1"), json=_body())
    assert second.json()["run"]["id"] == first.json()["run"]["id"]
    assert second.json()["run"]["conversation_result_card"][
        "evidence_artifact_id"
    ] == first.json()["run"]["conversation_result_card"]["evidence_artifact_id"]
```

- [ ] **Step 2: Run the focused local tests and verify RED**

Run: `poetry run pytest --no-cov tests/test_p1_evidence_spine.py tests/test_context_packet_runtime_attachment.py tests/test_alpha_api.py tests/test_alpha_api_supabase.py -q -k 'finaliz or evidence or persist_runtime_backtest_run or backtest_supabase'`

Expected: new finalization assertions fail because callers still persist the run and evidence separately.

- [ ] **Step 3: Route chat persistence through the finalizer**

Build the run and context-packet snapshot before finalization, but do not publish it to memory or Supabase first. Choose the Supabase gateway when configured, otherwise the memory adapter. Cache the returned canonical tuple, persist optional context-packet rows after the barrier, update conversation preview after the barrier, and emit the existing evidence-capture event once.

- [ ] **Step 4: Route direct API persistence through the finalizer**

Derive the owner-scoped stable run id from `/api/v1/backtests/run:{Idempotency-Key}`, build without early memory persistence, finalize once, then cache the returned run in the existing idempotency map. Convert finalization failure to a retryable `503 finalization_failed` problem without returning the computed run.

- [ ] **Step 5: Make chat finalization failure explicit and retryable**

Pass `clean_idempotency_key or request.state.request_id` into chat persistence. Catch the typed finalization error at the existing SSE recovery boundary and emit/persist typed recovery metadata with `failure_code=finalization_failed` while retaining the existing user-safe localized retry message and typed Retry action.

- [ ] **Step 6: Preserve the compatibility wrapper**

Keep `auto_capture_completed_backtest` only as a compatibility wrapper around the shared finalizer for existing tests/callers; it must not retain a second sidecar-write implementation.

- [ ] **Step 7: Run local tests and verify GREEN**

Run: `poetry run pytest --no-cov tests/test_p1_evidence_spine.py tests/test_context_packet_runtime_attachment.py tests/test_alpha_api.py tests/test_alpha_api_supabase.py -q -k 'finaliz or evidence or persist_runtime_backtest_run or backtest_supabase'`

Expected: all selected #194 tests pass; unrelated baseline failures remain separately recorded rather than silently changed.

---

### Task 4: Render Workflow completion and restart semantics

**Files:**
- Modify: `workflows/backtest_job.py`
- Test: `tests/test_render_workflow_execution.py`
- Test: `tests/test_backtest_jobs_async.py`

**Interfaces:**
- Consumes: shared finalizer and Postgres adapter.
- Changes: workflow execution identity is `backtest_job:{job_id}` and its owner-scoped stable run id is recorded in workflow metadata before finalization.
- Changes: finalizer failure maps to the approved retryable job failure shape.
- Changes: replay can recover a previously finalized tuple and link the same result without creating a duplicate artifact.

- [ ] **Step 1: Write failing Render-path tests**

```python
def test_run_backtest_job_finalizes_before_succeeded() -> None:
    result = run_backtest_job(gateway, job_id="job-1", backtest_tool=tool)
    assert gateway.transitions == ["running", "finalized", "succeeded"]
    assert result["result_run_id"] == gateway.finalized.identity.run_id
    assert gateway.created_runs == []


def test_run_backtest_job_marks_finalization_failure_retryable() -> None:
    gateway.finalization_error = RuntimeError("database unavailable")
    result = run_backtest_job(gateway, job_id="job-1", backtest_tool=tool)
    assert result["status"] == "failed"
    assert result["failure_code"] == "finalization_failed"
    assert result["failure_detail"] == "execution_failed"
    assert result["retryable"] is True
    assert result["result_run_id"] is None


def test_worker_replay_reuses_finalized_identity_without_duplicate_evidence() -> None:
    first = run_backtest_job(gateway, job_id="job-1", backtest_tool=tool)
    gateway.prepare_replay()
    second = run_backtest_job(gateway, job_id="job-1", backtest_tool=tool)
    assert second["result_run_id"] == first["result_run_id"]
    assert gateway.finalization_identities == [first["result_run_id"]] * 2
```

- [ ] **Step 2: Run the Render tests and verify RED**

Run: `poetry run pytest --no-cov tests/test_render_workflow_execution.py tests/test_backtest_jobs_async.py -q -k 'finaliz or worker_replay or marks_queued_job_running'`

Expected: tests fail because the workflow still calls `create_backtest_run` directly and maps persistence exceptions to non-retryable `failed_internal`.

- [ ] **Step 3: Replace direct run insertion with shared finalization**

Build the unpersisted run with the stable run id, build a typed finalization input, call `finalize_backtest_completion`, then persist route receipts/cost metadata against the returned run id and finally mark the job succeeded.

- [ ] **Step 4: Add approved failure and replay behavior**

Catch only finalizer-boundary failures as `finalization_failed`/retryable. Preserve existing tool/validation failure policy. Allow a worker retry to reuse an existing running or `finalization_failed` job attempt without changing the public enum; return an already-succeeded canonical result immediately.

- [ ] **Step 5: Run Render tests and verify GREEN**

Run: `poetry run pytest --no-cov tests/test_render_workflow_execution.py tests/test_backtest_jobs_async.py tests/test_backtest_jobs_shadow.py -q -k 'finaliz or worker_replay or run_backtest_job or shadow_backtest_job'`

Expected: all selected tests pass.

---

### Task 5: Evidence-to-decision lifecycle and reader barriers

**Files:**
- Modify: `tests/test_alpha_api_supabase.py`
- Modify: `tests/test_backtest_jobs_async.py`
- Modify: `tests/test_p1_evidence_spine.py`
- Modify only if a proven gap exists: `src/argus/api/routers/backtest.py`
- Modify only if a proven gap exists: `src/argus/domain/supabase_gateway.py`

**Interfaces:**
- Verifies: succeeded job returns a run whose result card contains the full evidence identity.
- Verifies: Add decision persists a note and reload/search return the same artifact/decision identity.
- Verifies: failed finalization returns no run from job polling, reload/history, or search.

- [ ] **Step 1: Write the failing lifecycle test**

```python
def test_real_workflow_result_supports_decision_reload_and_search(mock_gateway) -> None:
    job = _finalized_job_fixture(mock_gateway)
    status = client.get(f"/api/v1/backtest-jobs/{job['id']}", headers=_auth())
    artifact_id = status.json()["run"]["conversation_result_card"][
        "evidence_artifact_id"
    ]
    saved = client.post(
        f"/api/v1/evidence-artifacts/{artifact_id}/decision",
        headers=_auth(),
        json={"decision_state": "promising", "note": "Recheck after earnings."},
    )
    assert saved.status_code == 200
    assert _reload_result_card()["decision_state"] == "promising"
    assert _search_decision()["note"] == "Recheck after earnings."
```

- [ ] **Step 2: Run the lifecycle tests and verify RED**

Run: `poetry run pytest --no-cov tests/test_alpha_api_supabase.py tests/test_backtest_jobs_async.py tests/test_p1_evidence_spine.py -q -k 'workflow_result_supports_decision or partial_finalization'`

Expected: failure demonstrates the missing real-workflow evidence identity before the implementation is complete.

- [ ] **Step 3: Fix only confirmed reader gaps**

Job polling may return a run only when the job is `succeeded`, `result_run_id` is present, the run is completed, and its result card contains all required finalization ids/codes. Existing conversation/history/search queries must continue to filter on completed/finalized identity; add a narrow guard only where the lifecycle test proves a leak.

- [ ] **Step 4: Run the lifecycle tests and verify GREEN**

Run: `poetry run pytest --no-cov tests/test_alpha_api_supabase.py tests/test_backtest_jobs_async.py tests/test_p1_evidence_spine.py -q -k 'workflow_result_supports_decision or partial_finalization'`

Expected: all lifecycle tests pass.

---

### Task 6: Verification, review, publication, and remote follow-up

**Files:**
- Review all files changed from `origin/codex/private-alpha-next`.
- Add no unrelated cleanup.

**Interfaces:**
- Produces: focused and CI-equivalent local verification evidence.
- Produces: two traceable local review passes.
- Produces: draft PR targeting `codex/private-alpha-next`, green CI, ready state, real Render evidence, and resolved Codex review threads.

- [ ] **Step 1: Run focused verification**

Run:

```bash
OPENROUTER_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_ENABLE_EXECUTION_REALISM=false \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest --no-cov \
  tests/test_backtest_finalization.py \
  tests/test_p1_evidence_spine.py \
  tests/test_render_workflow_execution.py \
  tests/test_supabase_gateway.py \
  tests/test_backtest_jobs_async.py \
  tests/test_backtest_jobs_shadow.py \
  tests/test_alpha_api.py \
  tests/test_alpha_api_supabase.py -q
```

Also run touched-file Ruff, migration/release-doc guards, `git diff --check`, and the relevant frontend decision/reload tests.

- [ ] **Step 2: Run `superpowers:requesting-code-review`**

Dispatch one read-only reviewer with the issue, approved contract, exact base SHA, exact head SHA, test evidence, and diff. Validate every reported item against code/tests. Post each confirmed local finding to the PR after it exists for traceability, but fix confirmed Critical/Important findings before publication; record rejected findings with technical evidence.

- [ ] **Step 3: Run `argus-review-contract`**

Review against `origin/codex/private-alpha-next` after rereading canon and the approved integrity contract. Validate and fix only concrete findings. Post confirmed local findings to the PR for traceability once opened.

- [ ] **Step 4: Reverify and publish draft**

Run fresh verification, commit only intended files with a conventional issue-linked message, push `codex/issue-194-backtest-finalization`, and open a draft PR targeting `codex/private-alpha-next` with issue/root-cause/contract/check evidence.

- [ ] **Step 5: Pass CI and mark ready**

Watch all PR checks. Diagnose failures with `github:gh-fix-ci` when needed. Mark ready only after required checks pass, then confirm the PR is open and non-draft.

- [ ] **Step 6: Capture real Render evidence**

Against the branch-deployed private-alpha validation surface for the exact candidate SHA, use a real authenticated browser session to complete a Render Workflow backtest, verify the run/evidence identity, Add decision plus note, reload hydration, and Omnisearch retrieval. Do not deploy production or invite testers.

- [ ] **Step 7: Poll and address Codex review**

Poll thread-aware review state every 5-15 minutes until Codex review lands. For each thread: reproduce/validate first; reply inline with reasoning; apply thumbs-up for a confirmed valid finding or thumbs-down for a demonstrated false positive; fix only confirmed findings; rerun focused checks; reply with evidence; resolve when applicable; push; and rewatch CI.

