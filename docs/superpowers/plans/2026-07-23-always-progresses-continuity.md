# Argus Always Progresses Continuity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every accepted Argus conversation operation advance, clarify,
redirect, recover, or finish intentionally across message, confirmation, Run,
result, retry, and reload without semantic loops, lost facts, duplicate work, or
transport-derived failure.

**Architecture:** Add one small internal progress contract around the existing
LangGraph runtime, then close continuity at the existing artifact, ordinary-turn
lifecycle, backtest-job, message-persistence, and frontend projection owners.
No new orchestrator is introduced: LangGraph still owns meaning,
`chat_turn_lifecycles` owns durable ordinary-turn terminal truth,
`backtest_jobs` owns admitted Run truth, and the frontend renders those facts.

**Tech Stack:** Python 3.10, FastAPI, LangGraph, Pydantic, Supabase/Postgres
PL/pgSQL, React 19, Next.js 16, TypeScript, pytest, Bun test, Playwright, SSE.

## Global Constraints

- Start from the clean local `codex/private-alpha-next` integration commit that
  contains this plan and
  `docs/superpowers/specs/2026-07-23-always-progresses-continuity-design.md`.
- Compare the worker branch to `codex/private-alpha-next`, never to `main`.
- Read `AGENTS.md`, `docs/PRODUCT.md`, `docs/ARCHITECTURE.md`,
  `docs/API_CONTRACT.md`, `docs/DATA_MODEL.md`,
  `.agent/designs/argus/DESIGN.md`,
  `docs/specs/private-alpha-next-decision-memo.md`,
  `docs/specs/private-alpha-interim-roadmap.md`, the locked design, this plan,
  and `tests/evals/README.md` before changing code.
- Treat issues #230, #231, #233, #237, #238, #239, #240, #242, and #243 as
  supporting evidence, not automatic completion units.
- Treat `claude/argus-alpha-audit-c2d919` as read-only code leverage and
  anti-pattern evidence. Do not merge it, broadly cherry-pick it, or reuse its
  old acceptance claims.
- Use one shared progress vocabulary through existing owners. Do not add a
  second chat brain, central progress orchestrator, ordinary-turn queue, or new
  intent taxonomy.
- Normal user language reaches the LLM interpreter first. Do not add regex,
  prose similarity, phrase tables, display-label parsing, or language-specific
  routing.
- The progress fingerprint contains only typed material state. Prose, raw user
  wording, evidence spans, localization, provider/model names, receipt order,
  and presentation timestamps never prove progress.
- One accepted runtime attempt has one monotonic deadline, one shared
  provider-call allowance, and one first-wins internal terminal owner. Nested
  repairs and fallbacks cannot reset them.
- At most one pending conversational artifact retains executable authority.
  Completed confirmations and results remain immutable.
- Preserve compatible assets, capital, dates, benchmark, strategy/rules,
  cadence/timeframe, costs, and stable artifact/action/job/result identities
  through clarification, edit, retry, replacement, and reload.
- Reuse the approved ordinary-turn states exactly: `accepted`, `running`,
  `completed`, `recoverable_failed`, `abandoned`, and `reconciled`.
- `no_progress` is a successful actionable assistant outcome, not an
  infrastructure failure and not a new public lifecycle state.
- `confirmation_id` remains the Run action identity and its
  `Idempotency-Key`. One intentional Run creates at most one job, run, and
  result.
- Transport ambiguity is not business failure. The client checks durable job
  truth before showing `could_not_run`.
- Retry is typed, durable, owner-scoped, and bound to persisted content and
  artifact identity. It cannot duplicate message usage, confirmation, job,
  run, or result.
- Do not implement `IdeaVersion`, comparison, freshness, Search, discovery,
  Omnisearch, a new capability, RAG, result-card redesign, or unrelated polish.
- Use TDD and conventional atomic commits. One implementation worker owns the
  protected runtime spine at a time.
- Every worker is operating in a shared checkout. Give it exact file ownership,
  tell it other agents may have committed adjacent work, and forbid reverting
  or overwriting changes outside its assigned task.
- Every task gets a fresh implementation worker and a fresh task review using
  `superpowers:requesting-code-review`; Critical and Important findings are
  fixed and re-reviewed before the next task.
- Apply review proportionality: validate reachability and materiality, choose
  the smallest safe fix, and remove unjustified machinery after each fix.
- The integrated candidate then gets one independent
  `argus-review-contract` review **or** the founder's `/code-review` Claude
  review, not both automatically.
- Codex Cloud review is founder-triggered only after the Draft PR, exact-head
  local QA, and the independent contract review are clear.
- Run the mocked eval harness for every relevant change. If interpreter-facing
  behavior changes, run one sanctioned exact-head live eval before review; do
  not loop paid evals.
- Completion requires exact-head production-parity local browser QA with real
  interpretation and persistence. Submit each prescribed prompt once except
  when Retry is the behavior under test; execute at most one real backtest.
- Do not mark the PR Ready, merge, deploy, expose testers, close issues, or
  change production/hosted Supabase without explicit founder direction.

---

## File Structure

Phase 0 decides whether every listed production file actually needs a diff.
Already-correct behavior stays unchanged and receives evidence only.

### Semantic progress

- Create `src/argus/agent_runtime/turn_progress.py`: typed snapshot projection,
  transition classification, and privacy-safe hashes.
- Create `src/argus/agent_runtime/turn_execution.py`: context-local deadline,
  call allowance, provider permits, and first-wins terminal evidence.
- Modify `src/argus/llm/openrouter.py`: reserve before each real primary or
  fallback provider attempt and record skipped receipts when exhausted.
- Modify `src/argus/agent_runtime/runtime.py`: capture entry/exit snapshots and
  return typed progress evidence.
- Modify `src/argus/api/routers/agent.py`: own the accepted-turn execution
  scope, absolute turn wall, terminal claims, and persisted progress metadata.
- Modify `src/argus/api/chat/title_finalization.py`: detach after-stream work
  from the visible turn context.
- Create `tests/agent_runtime/test_turn_progress.py`.
- Create `tests/agent_runtime/test_turn_execution.py`.
- Modify `tests/test_chat_stream_contract.py` and
  `tests/test_chat_runtime_cutover.py`.

### Artifact continuity

- Modify `src/argus/agent_runtime/artifacts/continuity.py`: one canonical active
  anchor/authority decision.
- Modify only the reproduced corridors among
  `src/argus/agent_runtime/stages/interpret_actions.py`,
  `src/argus/agent_runtime/interpreter/artifact_assumption_edit.py`, and
  `src/argus/agent_runtime/stages/interpret_internal/confirmation_artifact_edits.py`.
- Modify `src/argus/api/chat/actions.py`: reject stale/missing identities before
  provider or compute work.
- Modify `tests/agent_runtime/test_artifact_continuity.py`,
  `tests/agent_runtime/test_artifact_edit_operations.py`,
  `tests/agent_runtime/test_post_result_edit_routing.py`, and
  `tests/test_chat_runtime_reload_guardrails.py`.

### Durable ordinary-turn lifecycle

- Create `src/argus/domain/chat_turn_lifecycle.py`: memory twin of the approved
  lifecycle and reconciliation predicate.
- Create `src/argus/domain/chat_turn_lifecycle_gateway.py`: focused Supabase
  gateway mixin.
- Modify `src/argus/domain/store.py` and
  `src/argus/domain/supabase_gateway.py`: compose the new focused owner.
- Create
  `supabase/migrations/20260723000001_add_chat_turn_lifecycles.sql`.
- Create
  `supabase/migrations/20260723000002_chat_turn_acceptance_and_reconciliation.sql`.
- Modify `src/argus/api/chat/request_admission.py` and
  `src/argus/api/message_store.py`: atomically accept a user message and its
  lifecycle identity.
- Create `src/argus/api/chat/turn_lifecycle_hooks.py`: thin route hooks.
- Create `src/argus/api/chat/turn_lifecycle_projection.py`: read-time overlay
  for reconciled/abandoned turns.
- Modify `src/argus/api/routers/agent.py` and the conversation-message GET
  route discovered in Phase 0.
- Create `tests/test_chat_turn_lifecycle.py`,
  `tests/test_chat_turn_lifecycle_gateway.py`,
  `tests/test_chat_turn_lifecycle_migration.py`, and
  `tests/test_chat_turn_lifecycle_postgres.py`.
- Create
  `tests/test_chat_turn_route_matrix.py`.
- Modify `tests/test_chat_request_admission.py`.

### Retry and frontend lifecycle projection

- Modify `src/argus/api/chat/retry.py`: bind Retry to persisted request message
  and structured action identity.
- Modify `web/lib/chat-retry-actions.ts`,
  `web/lib/chat-message-hydration.ts`,
  `web/lib/chat-recovery-display.ts`, and
  `web/components/chat/ChatInterface.tsx`: use durable projection and persisted
  content.
- Modify `web/components/chat/ChatMessage.tsx`: keep recovery adjacent to its
  owning user/action row.
- Modify focused retry, hydration, lifecycle, and recovery tests.

### Run ambiguity

- Modify only the reproduced server lookup/replay gap among
  `src/argus/api/chat/backtest_admission_flow.py`,
  `src/argus/api/chat/backtest_jobs.py`, and the backtest GET route.
- Modify `web/lib/chat-backtest-jobs.ts`,
  `web/components/chat/artifact-history.ts`,
  `web/components/chat/ChatInterface.tsx`, and focused tests so transport
  ambiguity becomes checking/reconciliation before failure.

### Session proof

- Create `tests/evals/chat_runtime_trajectory_adapters.py`: concrete adapters
  behind the existing `TrajectoryAdapters` contract.
- Modify `tests/evals/test_chat_runtime_trajectory_harness.py` and
  `tests/evals/alpha_session_trajectories.json` only where exact-head product
  truth requires it.
- Create `web/e2e/always-progresses.spec.ts`: deterministic browser harness for
  presentation and fault-injection mechanics.
- Create `docs/reports/always-progresses-closure-evidence.md`: exact-candidate
  evidence ledger; it must not declare completion before all gates pass.

---

### Task 0: Exact-Head Gap Audit And Work Ledger

**Files:**
- Create scratch only:
  `.superpowers/sdd/always-progresses-phase0.md`
- Read-only compare:
  `claude/argus-alpha-audit-c2d919`

**Interfaces:**
- Consumes: exact worker HEAD, locked design, current issues, current source and
  tests.
- Produces: one evidence table with `requirement`, `current proof`,
  `reproduced gap`, `owner`, `smallest delta`, and `test command`.

- [ ] **Step 1: Fail closed on the prepared worktree**

Run:

```bash
ROOT="$(git rev-parse --show-toplevel)"
test "$(git branch --show-current)" = "codex/always-progresses-continuity"
test -z "$(git status --porcelain)"
test -z "$(git rev-parse --show-superproject-working-tree)"
git merge-base --is-ancestor codex/private-alpha-next HEAD
test -f docs/superpowers/specs/2026-07-23-always-progresses-continuity-design.md
test -f docs/superpowers/plans/2026-07-23-always-progresses-continuity.md
```

Expected: every command exits zero. If any command fails, stop without changing
files, branches, services, GitHub, or external state.

- [ ] **Step 2: Create the durable SDD ledger**

Run:

```bash
mkdir -p .superpowers/sdd
test -f .superpowers/sdd/progress.md || : > .superpowers/sdd/progress.md
printf '%s\n' \
  "base_sha=$(git rev-parse HEAD)" \
  "parent_sha=$(git rev-parse codex/private-alpha-next)" \
  > .superpowers/sdd/always-progresses-phase0.md
```

Expected: both scratch files exist and remain untracked/ignored.

- [ ] **Step 3: Dispatch the read-only Phase 0 team**

Dispatch these configured agents in parallel, each with the locked design path,
the current HEAD, a bounded output file under `.superpowers/sdd/`, and an
explicit no-mutation stop:

```text
argus-code-scout
  -> current implementation/test/gap map; compare donor branch narrowly
argus-runtime-guardian
  -> semantic progress, interpreter, recovery, and artifact-spine invariants
argus-domain-modeler
  -> approved lifecycle ownership, invariants, RLS, and migration boundary
argus-verification-qa
  -> deterministic, Postgres, trajectory, and browser acceptance matrix
```

The release-captain session, not a subagent, reconciles contradictions. Do not
start implementation while an ownership or contract contradiction remains.

- [ ] **Step 4: Reproduce the claimed gaps at exact HEAD**

Run the current free baseline first:

```bash
OPENROUTER_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest \
  tests/agent_runtime \
  tests/test_spine_guardrails.py \
  tests/test_chat_request_admission.py \
  tests/test_chat_runtime_reload_guardrails.py \
  tests/test_backtest_jobs_async.py \
  tests/evals/test_measurement_eval_harness.py \
  tests/evals/test_chat_runtime_eval_manifest.py \
  tests/evals/test_chat_runtime_trajectory_harness.py \
  -q --no-cov
```

Expected: record the exact baseline, including pre-existing failures. Do not
change code to make the baseline look cleaner.

For each design requirement, add or identify one red that proves a current
product gap. If current code already proves the behavior, mark it
`already_green` and remove that implementation delta from later tasks.

- [ ] **Step 5: Lock the synthesized gap ledger**

Append the synthesized table to
`.superpowers/sdd/always-progresses-phase0.md`. The table must explicitly
classify:

```text
already_green
missing_implementation
stale_issue_claim
evidence_only_gap
blocked_requires_founder
```

Stop for the founder only if the smallest safe implementation requires a new
public lifecycle state, a second runtime owner, `IdeaVersion`, a new provider,
or a public contract outside the approved design.

---

### Task 1: Typed Progress Snapshot

**Files:**
- Create: `src/argus/agent_runtime/turn_progress.py`
- Create: `tests/agent_runtime/test_turn_progress.py`
- Modify: `tests/agent_runtime/test_runtime_semantic_boundaries.py`

**Interfaces:**
- Produces:
  `semantic_progress_snapshot(state: Any) -> ProgressSnapshot | None`,
  `semantic_progress_fingerprint(state: Any) -> str | None`, and
  `assess_progress(before: ProgressSnapshot | None,
  after: ProgressSnapshot | None, terminal: ProgressOutcome | None)
  -> ProgressAssessment`.
- Consumes only Pydantic models or serialized runtime dictionaries.

- [ ] **Step 1: Write the red snapshot contract**

Use these public internal types and assertions:

```python
from argus.agent_runtime.turn_progress import (
    ProgressAssessment,
    ProgressSnapshot,
    assess_progress,
    semantic_progress_fingerprint,
    semantic_progress_snapshot,
)
from argus.agent_runtime.state.models import (
    ArtifactReference,
    ResponseIntent,
    RunState,
    StrategySummary,
    TaskSnapshot,
)


def _strategy() -> StrategySummary:
    return StrategySummary(
        strategy_type="buy_and_hold",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range={"start": "2022-01-01", "end": "2025-01-01"},
        capital_amount=10_000,
    )


def production_shaped_checkpoint() -> dict[str, object]:
    strategy = _strategy()
    intent = ResponseIntent(
        kind="clarification",
        semantic_needs=["period"],
        requested_fields=["date_range"],
    )
    return {
        "stage_outcome": "await_user_reply",
        "run_state": RunState(
            current_user_message="test AAPL",
            candidate_strategy_draft=strategy,
            missing_required_fields=["date_range"],
            response_intent=intent,
        ),
        "latest_task_snapshot": TaskSnapshot(
            pending_strategy_summary=strategy,
            pending_needs=["period"],
            active_draft_reference=ArtifactReference(
                artifact_kind="draft",
                artifact_id="draft-1",
                artifact_status="active",
            ),
        ),
    }


def equivalent_public_payload() -> dict[str, object]:
    strategy = _strategy()
    return {
        "stage_outcome": "await_user_reply",
        "pending_strategy": {
            "strategy": strategy.model_dump(mode="python"),
            "missing_required_fields": ["date_range"],
        },
        "response_intent": {
            "kind": "clarification",
            "semantic_needs": ["period"],
            "requested_fields": ["date_range"],
        },
        "artifact_references": [
            {
                "artifact_kind": "draft",
                "artifact_id": "draft-1",
                "artifact_status": "active",
                "metadata": {},
            }
        ],
    }


def semantic_state(
    *,
    pending_needs: list[str] | None = None,
    artifact_id: str = "draft-1",
    assistant_response: str | None = None,
    evidence_spans: list[dict[str, str]] | None = None,
    language: str | None = None,
) -> dict[str, object]:
    payload = equivalent_public_payload()
    intent = dict(payload["response_intent"])
    intent["semantic_needs"] = list(pending_needs or ["period"])
    payload["response_intent"] = intent
    payload["artifact_references"] = [
        {
            "artifact_kind": "draft",
            "artifact_id": artifact_id,
            "artifact_status": "active",
            "metadata": {},
        }
    ]
    payload["assistant_response"] = assistant_response
    payload["evidence_spans"] = list(evidence_spans or [])
    payload["language"] = language
    return payload


def test_model_and_public_dict_normalize_to_same_snapshot() -> None:
    checkpoint = production_shaped_checkpoint()
    public = equivalent_public_payload()
    assert semantic_progress_snapshot(checkpoint) == semantic_progress_snapshot(public)


def test_prose_and_provenance_do_not_change_fingerprint() -> None:
    left = semantic_state(
        assistant_response="Test AAPL.",
        evidence_spans=[{"text": "AAPL"}],
        language="en",
    )
    right = semantic_state(
        assistant_response="Probemos AAPL.",
        evidence_spans=[{"text": "Apple"}],
        language="es-419",
    )
    assert semantic_progress_fingerprint(left) == semantic_progress_fingerprint(right)


def test_pending_need_and_artifact_identity_are_material() -> None:
    period = semantic_state(pending_needs=["period"], artifact_id="draft-1")
    asset = semantic_state(pending_needs=["asset_target"], artifact_id="draft-1")
    replacement = semantic_state(pending_needs=["period"], artifact_id="draft-2")
    assert semantic_progress_fingerprint(period) != semantic_progress_fingerprint(asset)
    assert semantic_progress_fingerprint(period) != semantic_progress_fingerprint(
        replacement
    )


def test_equivalent_state_with_actionable_terminal_is_no_progress() -> None:
    snapshot = semantic_progress_snapshot(semantic_state(pending_needs=["period"]))
    assert assess_progress(snapshot, snapshot, terminal="no_progress") == (
        ProgressAssessment(outcome="no_progress", changed_fields=())
    )
```

Also pin that unknown `extra_parameters`, raw date wording, labels, evidence,
provider context, and timestamps do not participate, while known executable
fields, `rule_spec`, confirmation status, job status, and result identity do.

- [ ] **Step 2: Verify the reds**

Run:

```bash
poetry run pytest tests/agent_runtime/test_turn_progress.py -q --no-cov
```

Expected: import failure because `turn_progress.py` does not exist.

- [ ] **Step 3: Implement the explicit projection**

Use these exact internal shapes:

```python
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Literal

ProgressOutcome = Literal[
    "advanced",
    "clarification",
    "redirected",
    "finished",
    "no_progress",
    "recoverable_failed",
    "terminal_failed",
]


@dataclass(frozen=True)
class ProgressSnapshot:
    projection: dict[str, Any]


@dataclass(frozen=True)
class ProgressAssessment:
    outcome: ProgressOutcome
    changed_fields: tuple[str, ...]


def semantic_progress_fingerprint(state: Any) -> str | None:
    snapshot = semantic_progress_snapshot(state)
    if snapshot is None:
        return None
    encoded = json.dumps(
        snapshot.projection,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
```

Build `semantic_progress_snapshot` with explicit allowlists for the typed fields
named by the design. Normalize models with `model_dump(mode="python")`; sort
string sets and artifact identities; omit empty values. Do not use a generic
recursive allowlist or a denylist of prose keys.

Implement `assess_progress` so `no_progress`, `recoverable_failed`,
`terminal_failed`, `clarification`, `redirected`, and `finished` are explicit
typed terminals; otherwise return `advanced` only when material keys changed.

- [ ] **Step 4: Run focused and spine checks**

Run:

```bash
poetry run pytest \
  tests/agent_runtime/test_turn_progress.py \
  tests/agent_runtime/test_state_models.py \
  tests/agent_runtime/test_runtime_semantic_boundaries.py \
  -q --no-cov
poetry run ruff check \
  src/argus/agent_runtime/turn_progress.py \
  tests/agent_runtime/test_turn_progress.py
```

Expected: all selected tests pass and Ruff is clean.

- [ ] **Step 5: Commit and request task review**

```bash
git add \
  src/argus/agent_runtime/turn_progress.py \
  tests/agent_runtime/test_turn_progress.py \
  tests/agent_runtime/test_runtime_semantic_boundaries.py
git commit -m "feat(runtime): define typed conversation progress"
```

Record the pre-task and post-task SHAs, generate the review package, and run a
fresh `superpowers:requesting-code-review` task review. Fix and re-review every
Critical or Important finding before Task 2.

---

### Task 2: Turn-Wide Deadline, Call Allowance, And Terminal Owner

**Files:**
- Create: `src/argus/agent_runtime/turn_execution.py`
- Modify: `src/argus/llm/openrouter.py`
- Modify: `src/argus/agent_runtime/runtime.py`
- Modify: `src/argus/api/routers/agent.py`
- Modify: `src/argus/api/chat/title_finalization.py`
- Create: `tests/agent_runtime/test_turn_execution.py`
- Modify: `tests/test_chat_stream_contract.py`
- Modify: `tests/test_chat_runtime_cutover.py`

**Interfaces:**
- Consumes:
  `semantic_progress_fingerprint`.
- Produces:
  `turn_execution_scope(*, entry_state: Any)
  -> Iterator[TurnExecutionContext]`,
  `reserve_provider_call(task: OpenRouterTask,
  task_timeout_seconds: float | None) -> ProviderCallPermit | None`,
  `record_exit_progress(state: Any,
  terminal: ProgressOutcome | None) -> ProgressAssessment`,
  `claim_turn_terminal(outcome: ProgressOutcome,
  reason: str | None) -> bool`, and
  `turn_execution_summary(receipts: Iterable[OpenRouterRouteReceipt])
  -> dict[str, Any]`.

- [ ] **Step 1: Write the red controller matrix**

Pin all of these before implementation:

```text
events_cannot_reset_the_absolute_turn_deadline
  Fake clock starts at 0, forty events arrive 0.03 seconds apart, absolute
  deadline is 0.25 seconds, and the stream ends with turn_deadline_exhausted.
primary_and_fallback_share_one_call_allowance
  Allowance 1 permits the primary candidate and blocks the fallback.
exhausted_reservation_records_skipped_receipt_without_provider_call
  HTTP spy count stays zero and one skipped receipt names the budget reason.
first_terminal_claim_wins
  First claim returns true, second false, and the first outcome/reason remain.
same_typed_state_becomes_no_progress
  Equal entry/exit fingerprints produce typed no_progress.
background_title_work_has_no_parent_turn_context
  Scheduled naming sees active_turn_execution() is None.
inline_and_threaded_streams_use_one_scope
  Both runtime-worker settings create one scope and one terminal.
turn_deadline_diagnostic_uses_total_turn_elapsed
  Diagnostic reports configured turn duration and total turn elapsed rather
  than the per-event limit.
```

Use a fake monotonic clock and provider spies. The deadline test must advance
through many individually timely events beyond the absolute deadline; it must
fail if the implementation resets a per-event timer.

- [ ] **Step 2: Verify the reds**

Run:

```bash
poetry run pytest \
  tests/agent_runtime/test_turn_execution.py \
  tests/test_chat_stream_contract.py \
  tests/test_chat_runtime_cutover.py \
  -q --no-cov
```

Expected: new controller imports or behavioral assertions fail at the Task 1
head.

- [ ] **Step 3: Implement the context-local controller**

Use a `ContextVar[TurnExecutionContext | None]` and one monotonic clock:

```python
@dataclass
class TurnExecutionContext:
    started_monotonic: float
    deadline_monotonic: float
    deadline_seconds: float
    call_allowance: int
    entry_fingerprint: str | None
    calls_reserved: int = 0
    terminal: str | None = None
    terminal_reason: str | None = None
    exit_fingerprint: str | None = None
    progress_outcome: str | None = None
    blocked_tasks: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ProviderCallPermit:
    task: str
    timeout_seconds: float
```

`turn_execution_scope` creates and releases exactly one context. Its `finally`
block claims a recoverable severed terminal only if no owner already claimed a
terminal. `reserve_provider_call` returns `None` before any provider access when
the deadline or allowance is exhausted. Without an active visible-turn context,
after-stream/background work keeps its existing task-local behavior.

The default absolute deadline is the existing
`ARGUS_RUNTIME_EVENT_TIMEOUT_SECONDS` value. Derive the default call allowance
by recording the exact maximal legitimate current route in the Phase 0 ledger;
do not invent a larger arbitrary ceiling.

- [ ] **Step 4: Reserve at every actual OpenRouter attempt**

In all three OpenRouter invocation corridors—async structured, async chat, and
sync structured—reserve inside the candidate loop immediately before the HTTP
client is created:

```python
permit = reserve_provider_call(
    task,
    task_timeout_seconds=float(profile.timeout_seconds),
)
if permit is None:
    record_openrouter_route_receipt(
        task=task,
        model_name=candidate_model,
        mode=mode,
        schema_name=schema_name,
        latency_ms=0,
        outcome="skipped",
        failure_mode=turn_budget_block_reason(),
        context_packet_ids=context_packet_ids,
    )
    return None
```

Use `permit.timeout_seconds` for both the HTTP client and `asyncio.wait_for`.
Do not reserve for missing-key or missing-model paths because they make no
provider attempt.

- [ ] **Step 5: Wrap both runtime stream modes once**

The accepted ordinary-turn event generator owns the scope outside the
inline/threaded branch. Capture the input fingerprint from the actual workflow
input/fallback state, not raw text. When the runtime final arrives, capture the
exit snapshot and persist the typed progress outcome in internal metadata.
Persist only input/output hashes, typed outcome/reason, calls reserved,
allowance, elapsed time, and exhaustion flags; never persist the raw snapshot.

The absolute wall wraps the whole event sequence; keep the existing per-event
stall guard as the tighter local bound. Deadline failure diagnostics contain
the configured turn duration and total turn elapsed, while the existing
per-event diagnostic stays unchanged.

Onboarding, cancellation, normal final, deterministic recovery, and
post-admission initialization failure each claim one typed internal terminal.
`title_finalization` detaches at task entry.

- [ ] **Step 6: Run focused, hermetic, mocked-eval, and modularity gates**

```bash
OPENROUTER_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest \
  tests/agent_runtime/test_turn_execution.py \
  tests/test_chat_stream_contract.py \
  tests/test_chat_runtime_cutover.py \
  tests/agent_runtime \
  tests/test_spine_guardrails.py \
  tests/evals/test_measurement_eval_harness.py \
  tests/evals/test_chat_runtime_eval_manifest.py \
  tests/evals/test_chat_runtime_trajectory_harness.py \
  -q --no-cov
poetry run python scripts/check_agent_runtime_modularity.py
poetry run ruff check src/argus tests/agent_runtime/test_turn_execution.py
git diff --check
```

Expected: all selected gates pass, no live provider call occurs, and modularity
has no violation.

- [ ] **Step 7: Commit and review**

```bash
git add \
  src/argus/agent_runtime/turn_execution.py \
  src/argus/llm/openrouter.py \
  src/argus/agent_runtime/runtime.py \
  src/argus/api/routers/agent.py \
  src/argus/api/chat/title_finalization.py \
  tests/agent_runtime/test_turn_execution.py \
  tests/test_chat_stream_contract.py \
  tests/test_chat_runtime_cutover.py
git commit -m "feat(runtime): bound accepted turn execution"
```

Run the fresh task review and an `argus-runtime-guardian` read-only review of
this task range. Resolve only confirmed, reachable, material findings; then
re-run the covering tests and re-review.

---

### Task 3: No-Progress Clarification And Artifact Authority

**Files:**
- Modify only reproduced gaps in:
  `src/argus/agent_runtime/artifacts/continuity.py`,
  `src/argus/agent_runtime/stages/interpret.py`,
  `src/argus/agent_runtime/stages/interpret_actions.py`,
  `src/argus/agent_runtime/interpreter/artifact_assumption_edit.py`,
  `src/argus/agent_runtime/stages/interpret_internal/confirmation_artifact_edits.py`,
  and `src/argus/api/chat/actions.py`
- Modify focused artifact and interpret tests listed in File Structure.

**Interfaces:**
- Consumes: `ProgressAssessment` and current `ArtifactAnchor`.
- Produces: one typed `no_progress` response and one active executable
  artifact authority.

- [ ] **Step 1: Write red journey-level tests**

Pin these named behaviors in the existing fixture style:

```text
equivalent_pending_need_stops_with_no_progress_options
answered_fields_survive_no_progress_stop
new_confirmation_supersedes_old_executable_authority
stale_run_action_reaches_zero_provider_and_compute_work
empty_or_inapplicable_edit_never_becomes_executable
result_refinement_anchors_completed_result_without_mutating_it
```

The no-progress response must carry typed concrete options: supply the missing
value, choose a supported alternative when available, keep unchanged, or
cancel. The normal prompt is LLM-owned; deterministic localized copy is only
the degraded fallback.

- [ ] **Step 2: Verify the reds**

Run:

```bash
poetry run pytest \
  tests/agent_runtime/test_artifact_continuity.py \
  tests/agent_runtime/test_artifact_edit_operations.py \
  tests/agent_runtime/test_interpret_stage.py \
  tests/agent_runtime/test_post_result_edit_routing.py \
  tests/test_chat_runtime_reload_guardrails.py \
  -q --no-cov
```

Expected: only the newly added gap assertions fail.

- [ ] **Step 3: Apply the existing anchor and patch once**

Resolve authority in this order:

```text
explicit structured action identity
matching active confirmation
explicit or latest completed result
retryable failed-action identity
no anchor
```

All corridors must consume the same resolved anchor and typed patch result.
Delete reproduced duplicate flat-plan/application branches rather than adding a
fourth compatibility corridor. An edit creates a new pending artifact and
invalidates the prior confirmation's executable authority. A completed result
is read-only input to new work.

When `record_exit_progress` reports equivalent material state and no other
approved terminal exists, emit one typed `no_progress` response. Do not compare
assistant text.

- [ ] **Step 4: Prove artifact and capability regressions**

```bash
OPENROUTER_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest \
  tests/agent_runtime/test_artifact_continuity.py \
  tests/agent_runtime/test_artifact_edit_operations.py \
  tests/agent_runtime/test_interpret_stage.py \
  tests/agent_runtime/test_post_result_edit_routing.py \
  tests/agent_runtime/test_options_semantic_admission.py \
  tests/agent_runtime/test_future_performance_admission.py \
  tests/test_chat_runtime_reload_guardrails.py \
  -q --no-cov
poetry run python scripts/check_agent_runtime_modularity.py
poetry run ruff check src/argus/agent_runtime src/argus/api/chat/actions.py
git diff --check
```

Expected: all selected tests pass with no runtime-spine or modularity violation.

- [ ] **Step 5: Commit and review**

```bash
git add \
  src/argus/agent_runtime/artifacts/continuity.py \
  src/argus/agent_runtime/stages/interpret.py \
  src/argus/agent_runtime/stages/interpret_actions.py \
  src/argus/agent_runtime/interpreter/artifact_assumption_edit.py \
  src/argus/agent_runtime/stages/interpret_internal/confirmation_artifact_edits.py \
  src/argus/api/chat/actions.py \
  tests/agent_runtime/test_artifact_continuity.py \
  tests/agent_runtime/test_artifact_edit_operations.py \
  tests/agent_runtime/test_interpret_stage.py \
  tests/agent_runtime/test_post_result_edit_routing.py \
  tests/test_chat_runtime_reload_guardrails.py
git commit -m "fix(chat): stop semantic loops and stale authority"
```

Stage only files owned by this task. Run the fresh task code review and a
runtime-guardian review before proceeding.

---

### Task 4: Durable Ordinary-Turn Lifecycle Core

**Files:**
- Create the domain, gateway, migration, and focused tests listed under
  Durable ordinary-turn lifecycle.
- Modify `src/argus/domain/store.py` and
  `src/argus/domain/supabase_gateway.py`.

**Interfaces:**
- Produces:
  `accept_chat_turn(*, user_id: str, conversation_id: str,
  request_id: str, message: Message) -> Message`,
  `transition_chat_turn(*, turn_id: str, to_status: TurnStatus,
  assistant_message_id: str | None, reconciled_outcome: str | None,
  failure_code: str | None, retryable: bool | None) -> TransitionResult`,
  `reconcile_stale_chat_turns(*, conversation_id: str, user_id: str)
  -> list[dict[str, Any]]`, and
  `list_projectable_chat_turns(*, conversation_id: str, user_id: str,
  message_ids: list[str]) -> list[dict[str, Any]]`.
- Owns recovery truth only; it is not semantic memory or a queue.

- [ ] **Step 1: Write the red memory and gateway contract**

The state machine tests must pin:

```python
ALLOWED = {
    "accepted": {"running", "completed", "recoverable_failed", "abandoned", "reconciled"},
    "running": {"completed", "recoverable_failed", "abandoned", "reconciled"},
}
TERMINAL = {"completed", "recoverable_failed", "abandoned", "reconciled"}
```

Also prove exact null-safe replay truth, late-success conflict, missing-row
failure, owner scoping, deterministic stale ordering, failure-before-success
evidence precedence, and no-proof `abandoned` with
`failure_code="turn_abandoned"` and `retryable=True`.

- [ ] **Step 2: Write the red migration contract**

Parse the real schema and assert:

- owner-scoped RLS `SELECT` and service-role-only mutation;
- `turn_id` references the accepted user message;
- the acceptance RPC composes `append_conversation_message`;
- acceptance and lifecycle insert occur in one transaction;
- transition is compare-and-set and null-safe;
- reconciliation uses database time, locks rows, rechecks staleness, processes
  at most 20 rows, and validates user/conversation/request/turn evidence;
- foreign messages cannot reconcile a row;
- terminal rows cannot be overwritten.

- [ ] **Step 3: Implement the memory twin and focused gateway mixin**

Use a frozen `TransitionResult`:

```python
@dataclass(frozen=True)
class TransitionResult:
    outcome: Literal["applied", "noop", "conflict", "missing", "invalid"]
    row: dict[str, Any] | None = None
```

The memory twin and SQL return the same outcomes. Compose
`ChatTurnLifecycleGatewayMixin` into `SupabaseGateway` rather than growing new
methods directly in the gateway mega-file.

- [ ] **Step 4: Implement forward-only migrations**

The first migration creates the approved table, constraints, indexes, grants,
RLS, and transition function. The second creates:

```sql
public.accept_chat_turn(
  p_user_id uuid,
  p_conversation_id uuid,
  p_message_id uuid,
  p_role text,
  p_content text,
  p_metadata jsonb,
  p_created_at timestamptz,
  p_preview text,
  p_request_id text
)
```

and:

```sql
public.reconcile_stale_chat_turns(
  p_conversation_id uuid,
  p_user_id uuid
)
```

`accept_chat_turn` must call the existing serialized append behavior rather
than writing a second hand-rolled `messages` insert. Use forward repair for
migration mistakes; never edit already-published migration history.

- [ ] **Step 5: Run memory, schema, and disposable-Postgres proof**

```bash
poetry run pytest \
  tests/test_chat_turn_lifecycle.py \
  tests/test_chat_turn_lifecycle_gateway.py \
  tests/test_chat_turn_lifecycle_migration.py \
  tests/test_chat_request_admission.py \
  -q --no-cov
poetry run pytest tests/test_chat_turn_lifecycle_postgres.py -q --no-cov
poetry run ruff check \
  src/argus/domain/chat_turn_lifecycle.py \
  src/argus/domain/chat_turn_lifecycle_gateway.py \
  tests/test_chat_turn_lifecycle.py \
  tests/test_chat_turn_lifecycle_gateway.py
git diff --check
```

Expected: unit/schema tests pass. The real-Postgres proof must pass against an
isolated disposable database; if Docker/Postgres is unavailable, report the
gate blocked rather than claiming completion.

- [ ] **Step 6: Commit and review**

```bash
git add \
  src/argus/domain/chat_turn_lifecycle.py \
  src/argus/domain/chat_turn_lifecycle_gateway.py \
  src/argus/domain/store.py \
  src/argus/domain/supabase_gateway.py \
  supabase/migrations/20260723000001_add_chat_turn_lifecycles.sql \
  supabase/migrations/20260723000002_chat_turn_acceptance_and_reconciliation.sql \
  tests/test_chat_turn_lifecycle.py \
  tests/test_chat_turn_lifecycle_gateway.py \
  tests/test_chat_turn_lifecycle_migration.py \
  tests/test_chat_turn_lifecycle_postgres.py
git commit -m "feat(chat): add durable ordinary-turn lifecycle"
```

Run the task code review plus `argus-domain-modeler` and
`argus-security-release-reviewer` read-only reviews. Fix only confirmed
contract, ownership, RLS, or durable-state findings and repeat the Postgres
proof.

---

### Task 5: Route Hooks, Reconciliation Projection, And Durable Retry

**Files:**
- Create/modify the route, request admission, message store, lifecycle hook,
  projection, retry, and frontend files listed above.
- Create `tests/test_chat_turn_route_matrix.py`.
- Modify focused frontend lifecycle/retry tests.

**Interfaces:**
- Consumes Task 4 lifecycle gateway.
- Produces atomic acceptance, `running`, durable terminal transitions, stale
  reconciliation on next POST/read, and one persisted-content Retry action.

- [ ] **Step 1: Write the red route matrix**

Pin these routes:

```text
ordinary message -> accepted -> running -> completed
ordinary runtime failure -> accepted/running -> recoverable_failed
process loss with success evidence -> reconciled(completed)
process loss with failure evidence -> reconciled(recoverable_failed)
process loss without evidence -> abandoned + retry_last_turn
onboarding/control turn -> terminal completed
cancel turn -> terminal completed
run_backtest action -> no chat_turn_lifecycle row
unauthorized conversation -> no reconciliation mutation
disconnect only -> no failure transition
```

Every assistant terminal metadata envelope includes the accepted `turn_id` and
request id. Assistant persistence must succeed before `completed` is reported.

- [ ] **Step 2: Write frontend retry/hydration reds**

Prove:

- abandoned recovery stays adjacent to the owning text or action message;
- `request_message_id == owning message id == lifecycle turn_id`;
- tampered payload text is ignored in favor of persisted content;
- wrong-role or mismatched ids produce no replay action;
- later user/artifact work supersedes the actionable Retry while preserving
  historical recovery;
- reload and live rendering match in English and Spanish.

- [ ] **Step 3: Implement atomic acceptance and thin hooks**

`ChatRequestAdmission.persist()` calls the Task 4 acceptance owner for ordinary
turns and reuses the returned persisted message. Give admission an explicit
internal mode:

```python
AdmissionOwner = Literal["ordinary_turn", "message_only"]
```

Normal conversation turns, onboarding controls, response-option selections,
cancel actions, and non-Run structured actions use `ordinary_turn`. A
`run_backtest` action uses `message_only` because `backtest_jobs` owns its
lifecycle; its user-message append still uses the canonical serialized writer.
Thin hooks transition `running` at runtime start and terminal only after the
owning assistant message is durable.

Reconciliation runs after ownership succeeds:

```text
before the next accepted POST for that conversation
before returning an owner-scoped conversation message page
```

Project lifecycle truth onto response copies. Do not mutate historical message
rows or insert a synthetic assistant row for `abandoned`.

- [ ] **Step 4: Bind Retry to durable identity**

The backend emits:

```json
{
  "retry_last_turn": {
    "request_message_id": "<accepted user message id>",
    "message": "<persisted user content>",
    "action": {"type": "<typed action>", "payload": {}}
  }
}
```

Include `action` only when the owning persisted user message had a structured
action. The frontend resolver checks all three identities and replays persisted
content. A visible Retry creates a new accepted attempt but does not charge the
failed attempt; the existing Usage settlement remains the owner of successful
message counting.

- [ ] **Step 5: Run route, lifecycle, usage, frontend, and reload gates**

```bash
poetry run pytest \
  tests/test_chat_turn_route_matrix.py \
  tests/test_chat_request_admission.py \
  tests/test_chat_runtime_reload_guardrails.py \
  tests/test_allowance_accounting.py \
  -q --no-cov
cd web && bun test \
  __tests__/chat-message-hydration.test.ts \
  __tests__/chat-recovery-display.test.ts \
  __tests__/chat-retry-actions.test.ts \
  __tests__/chat-retry-action-history.test.ts \
  __tests__/chat-lifecycle-source.test.ts
cd ..
poetry run ruff check src/argus tests/test_chat_turn_route_matrix.py
cd web && bun run lint && bun run build
cd ..
git diff --check
```

Expected: all selected tests, lint, and production build pass.

- [ ] **Step 6: Commit and review**

```bash
git add \
  src/argus/api/chat/request_admission.py \
  src/argus/api/chat/turn_lifecycle_hooks.py \
  src/argus/api/chat/turn_lifecycle_projection.py \
  src/argus/api/chat/retry.py \
  src/argus/api/message_store.py \
  src/argus/api/routers/agent.py \
  src/argus/api/routers/conversations.py \
  web/lib/chat-retry-actions.ts \
  web/lib/chat-message-hydration.ts \
  web/lib/chat-recovery-display.ts \
  web/components/chat/ChatInterface.tsx \
  web/components/chat/ChatMessage.tsx \
  web/__tests__/chat-message-hydration.test.ts \
  web/__tests__/chat-recovery-display.test.ts \
  web/__tests__/chat-retry-actions.test.ts \
  web/__tests__/chat-retry-action-history.test.ts \
  web/__tests__/chat-lifecycle-source.test.ts \
  tests/test_chat_turn_route_matrix.py \
  tests/test_chat_request_admission.py \
  tests/test_chat_runtime_reload_guardrails.py \
  tests/test_allowance_accounting.py
git commit -m "feat(chat): make turn recovery durable"
```

Stage only files changed by this task. Run fresh task review,
`argus-runtime-guardian`, `argus-verification-qa`, and
`argus-security-release-reviewer` against this task range.

---

### Task 6: Run Transport Ambiguity Reconciliation

**Files:**
- Modify only reproduced gaps in server job lookup/replay and frontend checking
  files listed under Run ambiguity.
- Modify `tests/test_backtest_jobs_async.py`,
  `tests/test_chat_backtest_state_machine.py`,
  `web/__tests__/chat-backtest-jobs.test.ts`, and
  `web/__tests__/chat-artifact-history.test.ts`.

**Interfaces:**
- Consumes existing atomic admission and owner-scoped job lookup.
- Produces one checking/reconciliation path keyed by `confirmation_id`.

- [ ] **Step 1: Write red ambiguity cases**

Pin:

```text
response lost after admission -> lookup same identity -> queued/running
response lost after success -> lookup -> one canonical result
lookup 404 before proof -> one exact same-key replay only
identity collision -> 409 without disclosure
durable failed/canceled/expired -> terminal failure
transport exception alone -> never could_not_run
reload queued/running -> continue checking same job
```

Use provider, delegate, and compute spies to prove one execution.

- [ ] **Step 2: Verify the reds**

```bash
poetry run pytest \
  tests/test_backtest_jobs_async.py \
  tests/test_chat_backtest_state_machine.py \
  -q --no-cov
cd web && bun test \
  __tests__/chat-backtest-jobs.test.ts \
  __tests__/chat-artifact-history.test.ts
cd ..
```

Expected: only the new ambiguity assertions fail.

- [ ] **Step 3: Reuse durable job truth**

On transport ambiguity:

```text
set presentation-only checking
GET owner-scoped job by action identity
render queued/running without terminal failure
hydrate linked result on succeeded
render typed failure only on durable failed/canceled/expired
allow one same-key replay only under the approved 404 contract
```

Do not add a new polling subsystem or make Render/control-plane reconciliation a
browser dependency.

- [ ] **Step 4: Prove exact-once and regressions**

```bash
poetry run pytest \
  tests/test_backtest_jobs_async.py \
  tests/test_chat_backtest_state_machine.py \
  tests/test_chat_runtime_reload_guardrails.py \
  tests/test_allowance_accounting_postgres.py \
  -q --no-cov
cd web && bun test \
  __tests__/chat-backtest-jobs.test.ts \
  __tests__/chat-artifact-history.test.ts \
  __tests__/chat-turn-artifact-ux.test.ts
cd ..
git diff --check
```

Expected: one job/run/result per action identity and no transport-only terminal
failure.

- [ ] **Step 5: Commit and review**

```bash
git add \
  src/argus/api/chat/backtest_admission_flow.py \
  src/argus/api/chat/backtest_jobs.py \
  src/argus/api/routers/backtest.py \
  web/lib/chat-backtest-jobs.ts \
  web/components/chat/artifact-history.ts \
  web/components/chat/ChatInterface.tsx \
  tests/test_backtest_jobs_async.py \
  tests/test_chat_backtest_state_machine.py \
  tests/test_chat_runtime_reload_guardrails.py \
  tests/test_allowance_accounting_postgres.py \
  web/__tests__/chat-backtest-jobs.test.ts \
  web/__tests__/chat-artifact-history.test.ts \
  web/__tests__/chat-turn-artifact-ux.test.ts
git commit -m "fix(backtest): reconcile ambiguous run responses"
```

Stage only Task 6 files. Run fresh task review plus runtime and security/release
reviews.

---

### Task 7: Concrete Session Trajectory Adapters

**Files:**
- Create: `tests/evals/chat_runtime_trajectory_adapters.py`
- Modify: `tests/evals/test_chat_runtime_trajectory_harness.py`
- Modify only justified expectations:
  `tests/evals/alpha_session_trajectories.json`

**Interfaces:**
- Implements the existing `TrajectoryAdapters` operations:
  `stream`, `action`, `disconnect`, `reload`, `retry`, and `persistence`.
- Observes product behavior only; it never repairs state.

- [ ] **Step 1: Write adapter contract reds**

Each adapter must return the existing `StepObservation` with canonical SSE,
visible category, stage outcome, artifact/action identity, lifecycle, reload,
recovery, route receipts, terminal fingerprint, stale execution count, and
orphan count where applicable.

Pin that a disconnect owns a submission before client terminal, not a second
operation after a visible terminal.

- [ ] **Step 2: Implement concrete adapters**

Use the real FastAPI application, memory/Supabase test owners, canonical SSE
parser, actual message reload projection, and structured actions. Fault
injection may sever transport or runtime at named boundaries; it must not
write product state directly.

Do not place secrets, prompts, raw transcripts, conversation ids, or payloads
in scorecards.

- [ ] **Step 3: Remove masks only with integrated proof**

For each `expected_fail`, run its trajectory against the integrated candidate.
Remove the mask only when every hard check passes. A remaining failure keeps
its exact issue and narrow allowed-failure prefix; it cannot be described as
pillar completion.

- [ ] **Step 4: Run the free session gate**

```bash
OPENROUTER_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest \
  tests/evals/test_measurement_eval_harness.py \
  tests/evals/test_chat_runtime_eval_manifest.py \
  tests/evals/test_chat_runtime_trajectory_harness.py \
  -q --no-cov
```

Expected: all applicable trajectories pass with no hidden expected-fail
success.

- [ ] **Step 5: Commit and review**

```bash
git add tests/evals
git commit -m "test(runtime): exercise concrete continuity journeys"
```

Run a fresh task review and `argus-verification-qa`.

---

### Task 8: Integrated Deterministic And Browser Acceptance

**Files:**
- Create: `web/e2e/always-progresses.spec.ts`
- Create/update:
  `docs/reports/always-progresses-closure-evidence.md`
- Modify product code only if a founder-visible failure is reproduced,
  diagnosed, and approved as in-scope.

**Interfaces:**
- Consumes the exact integrated candidate from Tasks 1–7.
- Produces deterministic, real-Postgres, exact-head browser, and optional live
  interpreter evidence.

- [ ] **Step 1: Run the integrated deterministic gates**

```bash
OPENROUTER_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest \
  tests/agent_runtime \
  tests/test_spine_guardrails.py \
  tests/test_chat_request_admission.py \
  tests/test_chat_turn_lifecycle.py \
  tests/test_chat_turn_route_matrix.py \
  tests/test_chat_runtime_reload_guardrails.py \
  tests/test_backtest_jobs_async.py \
  tests/test_chat_backtest_state_machine.py \
  tests/evals/test_measurement_eval_harness.py \
  tests/evals/test_chat_runtime_eval_manifest.py \
  tests/evals/test_chat_runtime_trajectory_harness.py \
  -q --no-cov
poetry run pytest tests/test_chat_turn_lifecycle_postgres.py -q --no-cov
poetry run python scripts/check_agent_runtime_modularity.py
poetry run ruff check src/argus tests
cd web && bun test && bun run lint && bun run build
cd ..
git diff --check
```

Also run focused regression journeys for chart ranges, Security, Usage, and
capability truth. Record exact commands and counts in the closure ledger.

- [ ] **Step 2: Run one sanctioned exact-head live eval when required**

If any task changed interpreter-facing runtime behavior, run exactly once:

```bash
test -n "${ARGUS_EVAL_ENV_FILE:-}"
ARGUS_RUN_LIVE_EVALS=1 \
poetry run pytest tests/evals/test_measurement_eval_live.py -q
```

Record SHA, one-attempt integrity, scorecard path, pass/fail totals, cost,
latency, and any provider incident. Do not rerun or edit fixtures without
founder authorization. If no interpreter-facing behavior changed, record why
the gate is not applicable.

- [ ] **Step 3: Start exact-head production-parity local QA**

Use `.github/qa.sh` and real-auth frontend configuration from this worktree.
Use the established normal non-admin QA identity through the existing
credential automation; never ask the founder to type credentials, and never
print, read into chat, screenshot, or persist a secret.

Before submitting a prompt, prove:

```text
backend and frontend serve the exact candidate SHA
real interpreter credential is available
real persistence is active
normal user is authenticated and not admin
baseline usage and database truth are recorded safely
browser console and network recording are active
```

An environment failure is `BLOCKED`, not a product failure. Repair only local
environment wiring; do not mutate hosted Supabase or production.

- [ ] **Step 4: Run the six founder-visible journeys**

Run each prescribed journey once in a fresh or explicitly continued
conversation as the design requires:

```text
1. supported clarification -> answer -> edit -> latest confirmation
   -> one real Run whose client terminal is intentionally hidden
   -> checking/reconciliation -> result/Quick take -> reload
2. ambiguous pending answer -> no_progress with facts preserved and no Run
3. accepted ordinary turn interrupted -> reload -> durable Retry
   -> one successful completion without double charge
4. inspect the same Journey 1 Run identity and prove one job/run/result
5. old Run after replacement -> stale rejection before compute
6. explicit result refinement -> new confirmation, old result immutable,
   no IdeaVersion claim
```

At least one journey is Spanish. Across the complete set, inspect:

```text
visible response and controls
typed API/message metadata
durable lifecycle/job/run rows
usage counters
reload identity
browser console and network
provider/delegate/compute counts where fault injection is involved
```

Only Journey 1 executes a real backtest. Journey 4 is the durable
identity/database/reload proof for that same admitted execution and cannot
create a second one.

Stop on the first real product failure. Diagnose root cause and smallest safe
fix; do not continue the matrix, run a paid scorecard, or begin a review loop.
After a bounded correction, rerun only the failed journey and any directly
affected prior preservation guard before completing the remaining journeys.

- [ ] **Step 5: Commit browser harness and honest evidence**

```bash
git add \
  web/e2e/always-progresses.spec.ts \
  docs/reports/always-progresses-closure-evidence.md
git commit -m "test(chat): prove always-progresses journeys"
```

The evidence document may say `candidate ready for independent review` only
when all required gates pass at the exact HEAD. It must list every unrun,
blocked, or external gate.

- [ ] **Step 6: Run final whole-branch internal review**

Generate one review package from the branch merge base to HEAD and run
`superpowers:requesting-code-review` with the locked design and this plan.
Use the most capable configured reviewer. Send the complete findings list to one
fix worker, not one worker per finding. Re-review only the changed delta plus
the material invariants it affects.

---

### Task 9: Independent Contract Review, Draft PR, And Founder Handoff

**Files:**
- Update only review-driven code/tests and
  `docs/reports/always-progresses-closure-evidence.md`.
- Create no issue and close no issue.

**Interfaces:**
- Produces one clean candidate branch and Draft PR with exact-head evidence.

- [ ] **Step 1: Run exactly one independent review layer**

Ask the founder which independent layer owns this pass:

```text
Option A: run argus-review-contract in a fresh independent session/subagent
Option B: stop and hand the exact SHA/evidence package to the founder's
          /code-review Claude session
```

Do not automatically run both. The reviewer reads the named parent branch,
canon, locked design, implementation plan, full branch diff, deterministic
evidence, browser evidence, and any live-eval evidence.

For every finding:

```text
confirm reachability on the exact head
classify materiality and lane relevance
fix the smallest safe boundary when confirmed
reassess complexity against severity and likelihood
reject speculative/disproportionate scope with evidence
rerun the covering tests and affected browser journey
request one delta-only re-review
```

Do not turn unchanged surfaces into new requirements merely to continue the
loop.

- [ ] **Step 2: Publish only after the independent layer is clear**

Verify clean state, exact parent, and all evidence. Push with a normal
fast-forward and create/update a Draft PR targeting `codex/private-alpha-next`.
The PR body contains Summary, Changes, Motivation, Impact, Testing,
Risks/Rollback, remaining gates, and a checklist marking only proven items.

Do not mark Ready for review.

- [ ] **Step 3: Wait for CI to reach terminal state**

Track required checks at the exact PR head. Fix only candidate-caused failures.
Do not treat a skipped Supabase Preview as real migration proof; preserve the
disposable-Postgres evidence.

- [ ] **Step 4: Stop for founder-triggered Codex Cloud review**

Report:

```text
PR URL
base and head SHAs
commit list
clean/remote parity
subagent task and review ledger
deterministic and Postgres gates
browser journey table and evidence paths
live-eval disposition
CI state
independent-review disposition
remaining external/tester-exposure gates
```

The founder decides when to mark the Draft Ready and trigger Codex Cloud
review. After Cloud findings arrive, validate and fix only confirmed in-scope
material issues, reply to each thread with reasoning, react appropriately,
resolve handled threads, and run one delta-only review. Stop when no unresolved
material blocker remains; do not request another Cloud review without founder
authorization.

Never merge, deploy, close issues, or declare the pillar complete from this
implementation session.

---

## Completion Mapping

The release-captain session must be able to point from every locked acceptance
criterion to exact evidence:

| Design acceptance | Owning task |
| --- | --- |
| Typed progress and repeated-state stop | 1–3 |
| One deadline/call allowance/terminal | 2 |
| Fact preservation and one active authority | 3 |
| Durable ordinary-turn owner and Retry | 4–5 |
| Exact-once Run and ambiguity recovery | 6 |
| Concrete session adapters | 7 |
| Deterministic, Postgres, live, browser proof | 8 |
| Independent review, Draft PR, CI, Cloud handoff | 9 |
| IdeaVersion/discovery/Omnisearch untouched | Global constraints and every review |

The unit of completion is the integrated user-visible pillar. A green
subsystem, a merged partial commit, or a checked issue box is not completion.
