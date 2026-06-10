# Conversation Artifact Continuity Implementation Plan

> [!NOTE]
> Historical context. This document is retained as implementation evidence and is not the current execution source of truth.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make messy post-artifact chat behavior production-ready by anchoring confirmation actions, result follow-ups, retries, and refinement turns to canonical artifact state before applying user edits as typed patches.

**Architecture:** Add a focused artifact-continuity layer under `src/argus/agent_runtime/artifacts/`. Existing runtime stages and API helpers call this layer instead of growing local branches. The layer reconstructs canonical drafts from artifacts, applies deterministic patch semantics, and exposes lifecycle decisions for retry and hydration behavior. LangGraph remains the only runtime brain, Supabase remains durable product persistence, and the frontend renders backend-owned state.

**Tech Stack:** Python, FastAPI, LangGraph runtime state, Pydantic, pytest, Next.js/React, TypeScript, Bun tests, Playwright or in-app browser live QA.

---

## Source Documents

Read these before implementation, in this order:

- `docs/PRODUCT.md`
- `docs/ARCHITECTURE.md`
- `docs/API_CONTRACT.md`
- `docs/DATA_MODEL.md`
- `.agent/designs/argus/DESIGN.md`
- `AGENTS.md`

Relevant intended-contract sections:

- `docs/ARCHITECTURE.md`: Conversation Artifact Continuity
- `docs/API_CONTRACT.md`: Conversation Artifact Continuity Contract
- `docs/DATA_MODEL.md`: messages, backtest runs, strategy artifacts, and retry metadata

## Problem Shape

The live `Review 1` stress test showed a macro failure, not a DCA-specific bug:

- A completed result carried canonical strategy facts.
- Later action chips and free-text edits used incomplete pending state instead of the visible artifact.
- Result follow-up guidance swallowed modification turns and produced generic copy.
- A refine action reconstructed a strategy without durable fields such as amount, cadence, timeframe, and benchmark.
- Retry metadata hydrated after reload in a way that was ambiguous once the conversation had moved on.
- Refresh and backend restart made these state cracks more visible.

This can happen with any supported strategy, asset set, amount, period, timeframe, or benchmark. The fix is a continuity contract around artifacts, not a patch for one prompt.

## Non-Negotiable Boundaries

Do not implement:

- Regex or phrase gates before LLM interpretation.
- Strategy-specific fixes such as preserving cadence only for DCA.
- Hardcoded ticker, benchmark, provider, action-label, date-phrase, or cue-token lists.
- Frontend reconstruction of strategy state from assistant prose.
- A second chat orchestrator outside LangGraph.
- Transcript-only strategy truth.
- Broad branches in `interpret_actions.py`, `artifact_context.py`, `result_actions.py`, or `ChatInterface.tsx` when the behavior has a clearer owner.
- Model upgrade as the fix for deterministic continuity.
- Silent defaults that overwrite user-explicit constraints.

Allowed pattern:

- Normal language reaches the structured LLM interpreter first.
- Deterministic guardrails run after interpretation.
- Continuity logic compares typed strategy fields and artifact metadata.
- Missing, invalid, or stale facts produce clarification or lifecycle state, not invented frontend behavior.

## Ownership Model

Create these focused backend modules:

- `src/argus/agent_runtime/artifacts/__init__.py`
  - Public exports only.
- `src/argus/agent_runtime/artifacts/drafts.py`
  - Reconstruct canonical `StrategySummary` values from confirmation payloads, result metadata, saved strategy references, and failed launch payloads.
- `src/argus/agent_runtime/artifacts/patches.py`
  - Own the typed patch model and merge semantics.
- `src/argus/agent_runtime/artifacts/lifecycle.py`
  - Own retry, supersession, stale action, and action hydratability decisions.
- `src/argus/agent_runtime/artifacts/continuity.py`
  - Resolve the current artifact anchor and coordinate draft, patch, and lifecycle helpers.

Keep these files thin:

- `src/argus/agent_runtime/stages/artifact_context.py`
  - Extraction/adaptation only. Move new policy into `artifacts/*`.
- `src/argus/agent_runtime/stages/interpret_actions.py`
  - Stage routing only. It should call continuity helpers instead of owning artifact state policy.
- `src/argus/api/chat/result_actions.py`
  - API action shaping only. It should seed from canonical result draft reconstruction.
- `src/argus/api/routers/agent.py`
  - Persistence and transport only. It should persist lifecycle metadata returned by runtime logic.

Frontend ownership:

- `web/lib/chat-retry-actions.ts`
  - Interpret backend-owned retry lifecycle metadata for hydration.
- `web/components/chat/artifact-history.ts`
  - Hydrate artifact history without inventing strategy state.
- `web/components/chat/ChatInterface.tsx`
  - Conversation loading and cold-start surface selection.

## Canonical Concepts

Artifact anchor:

- The currently relevant visible artifact for a user action or follow-up.
- Supported anchor kinds: active confirmation, latest result, saved strategy reference, latest failed action.
- Anchor resolution must use structured ids and metadata, not assistant prose.

Canonical draft:

- A `StrategySummary` reconstructed from the anchor.
- It preserves strategy type, asset universe, asset class, dates, amount, cadence, timeframe, benchmark, and supported rule fields when those values are present in durable artifact metadata.
- It does not invent unsupported values to make a run executable.

Typed patch:

- A partial update produced by structured action payloads or post-LLM interpretation.
- Omitted fields are preserved.
- Fields are cleared only through explicit deterministic validation.
- Asset class, symbol resolution, benchmark defaults, date availability, and capability checks remain guardrails after patching.

Lifecycle decision:

- A backend-owned description of whether a retry/action remains active, is superseded, or expired.
- Frontend hydration renders this state; it does not rediscover it from message text.

## Implementation Tasks

### Task 1: Add Backend Artifact Continuity Tests

Files:

- Create `tests/agent_runtime/test_artifact_continuity.py`

Steps:

- [ ] Add failing tests for reconstructing a canonical draft from completed result metadata.
- [ ] Cover at least one DCA result with amount, cadence, timeframe, benchmark, asset class, symbols, and date range.
- [ ] Cover one buy-and-hold result to prove behavior is not strategy-specific.
- [ ] Cover reconstruction from confirmation payload metadata.
- [ ] Cover reconstruction from failed launch payload metadata.
- [ ] Cover a date patch preserving existing amount, cadence, assets, timeframe, and benchmark.
- [ ] Cover an asset patch preserving period, money, timeframe, and benchmark.
- [ ] Cover explicit clear semantics separately from omitted fields.

Verification:

```bash
poetry run pytest tests/agent_runtime/test_artifact_continuity.py -q
```

Expected initial result: tests fail because the new `artifacts/*` layer does not exist.

### Task 2: Implement Canonical Draft Reconstruction

Files:

- Create `src/argus/agent_runtime/artifacts/__init__.py`
- Create `src/argus/agent_runtime/artifacts/drafts.py`
- Update `tests/agent_runtime/test_artifact_continuity.py`

Steps:

- [ ] Implement draft reconstruction from confirmation payloads.
- [ ] Implement draft reconstruction from result metadata and config snapshots.
- [ ] Implement draft reconstruction from failed launch payloads.
- [ ] Reuse existing provider-backed symbol normalization and existing `StrategySummary` validation.
- [ ] Preserve canonical fields without introducing string cue lists or strategy-name branches.
- [ ] Keep `artifact_context.py` as an adapter if existing callers still depend on it.

Verification:

```bash
poetry run pytest tests/agent_runtime/test_artifact_continuity.py -q
```

Commit checkpoint:

```bash
git add src/argus/agent_runtime/artifacts tests/agent_runtime/test_artifact_continuity.py
git commit -m "feat(agent-runtime): add artifact draft reconstruction"
```

### Task 3: Implement Typed Patch Semantics

Files:

- Create `src/argus/agent_runtime/artifacts/patches.py`
- Update `src/argus/agent_runtime/artifacts/__init__.py`
- Update `tests/agent_runtime/test_artifact_continuity.py`

Steps:

- [ ] Define a typed artifact patch model around supported `StrategySummary` fields.
- [ ] Preserve omitted fields from the anchored draft.
- [ ] Normalize typed values using existing codebase helpers where they exist.
- [ ] Add explicit clear semantics only for fields the runtime can safely clear.
- [ ] Record patch source and changed fields in metadata for diagnostics.
- [ ] Do not add pre-interpretation language matching.

Verification:

```bash
poetry run pytest tests/agent_runtime/test_artifact_continuity.py -q
```

Commit checkpoint:

```bash
git add src/argus/agent_runtime/artifacts tests/agent_runtime/test_artifact_continuity.py
git commit -m "feat(agent-runtime): add artifact patch semantics"
```

### Task 4: Implement Artifact Anchor and Lifecycle Policy

Files:

- Create `src/argus/agent_runtime/artifacts/continuity.py`
- Create `src/argus/agent_runtime/artifacts/lifecycle.py`
- Update `tests/agent_runtime/test_artifact_continuity.py`

Steps:

- [ ] Resolve anchors from structured action payload ids and runtime snapshot references.
- [ ] Prefer the visible active confirmation when a confirmation action targets it.
- [ ] Resolve result anchors from durable run ids and result metadata.
- [ ] Resolve failed-action anchors only for active failed actions.
- [ ] Mark retry actions superseded after a newer confirmation, result, cancellation, or successful action supersedes the failed action.
- [ ] Mark retry actions expired when they no longer match the latest failed action reference.
- [ ] Return lifecycle metadata for persistence and frontend hydration.

Verification:

```bash
poetry run pytest tests/agent_runtime/test_artifact_continuity.py -q
```

Commit checkpoint:

```bash
git add src/argus/agent_runtime/artifacts tests/agent_runtime/test_artifact_continuity.py
git commit -m "feat(agent-runtime): add artifact lifecycle policy"
```

### Task 5: Wire Result Refinement Through Continuity

Files:

- Modify `src/argus/api/chat/result_actions.py`
- Update `tests/test_chat_runtime_reload_guardrails.py`
- Update `tests/agent_runtime/test_conversational_contract_hardening.py` if existing contract tests cover refine actions

Steps:

- [ ] Add a failing test where a completed result is refined after reload.
- [ ] Assert the pending strategy keeps assets, asset class, amount, cadence, timeframe, benchmark, and date range.
- [ ] Seed refine actions from `artifacts/drafts.py`, not from partial frontend payloads or assistant prose.
- [ ] Preserve existing result-review behavior for explanation-only actions.
- [ ] Ensure a missing durable run id produces a precise recovery response rather than an invented draft.

Verification:

```bash
poetry run pytest \
  tests/test_chat_runtime_reload_guardrails.py \
  tests/agent_runtime/test_conversational_contract_hardening.py \
  -q
```

Commit checkpoint:

```bash
git add src/argus/api/chat/result_actions.py tests/test_chat_runtime_reload_guardrails.py tests/agent_runtime/test_conversational_contract_hardening.py
git commit -m "fix(chat): preserve result fields during refinement"
```

### Task 6: Wire Confirmation Actions Through Continuity

Files:

- Modify `src/argus/agent_runtime/stages/interpret_actions.py`
- Update `tests/agent_runtime/test_conversational_contract_hardening.py`

Steps:

- [ ] Add failing tests for `change_dates`, `change_asset`, `adjust_assumptions`, `run_backtest`, and `cancel` against a visible confirmation.
- [ ] Assert edit actions preserve unchanged visible fields.
- [ ] Assert `run_backtest` uses the visible executable confirmation payload.
- [ ] Assert `cancel` ends the active confirmation without corrupting historical artifacts.
- [ ] Route structured confirmation actions through artifact anchor resolution.
- [ ] Keep stage routing in `interpret_actions.py`; keep artifact policy in `artifacts/*`.

Verification:

```bash
poetry run pytest tests/agent_runtime/test_conversational_contract_hardening.py -q
```

Commit checkpoint:

```bash
git add src/argus/agent_runtime/stages/interpret_actions.py tests/agent_runtime/test_conversational_contract_hardening.py
git commit -m "fix(agent-runtime): anchor confirmation actions to visible artifacts"
```

### Task 7: Route Post-Artifact Patch Turns Before Open-Ended Guidance

Files:

- Modify `src/argus/agent_runtime/artifacts/continuity.py`
- Modify `src/argus/agent_runtime/stages/interpret_actions.py`
- Update `tests/agent_runtime/test_conversational_contract_hardening.py`

Steps:

- [ ] Add a failing test where the user asks to change dates after a result.
- [ ] Ensure this does not produce generic result-guidance copy.
- [ ] After LLM interpretation, compare the typed candidate draft against the anchored artifact draft.
- [ ] If typed candidate fields changed, let the normal confirmation path handle the patched draft.
- [ ] If no typed patch exists, keep existing result follow-up guidance behavior.
- [ ] Avoid raw phrase matching and cue-token lists.

Verification:

```bash
poetry run pytest tests/agent_runtime/test_conversational_contract_hardening.py -q
```

Commit checkpoint:

```bash
git add src/argus/agent_runtime/artifacts/continuity.py src/argus/agent_runtime/stages/interpret_actions.py tests/agent_runtime/test_conversational_contract_hardening.py
git commit -m "fix(agent-runtime): route artifact patch turns before guidance"
```

### Task 8: Add Review 1 Macro Regression

Files:

- Update `tests/test_chat_runtime_reload_guardrails.py`

Steps:

- [ ] Add an API-level regression that replays the important `Review 1` pattern deterministically.
- [ ] Start from a completed DCA result with AAPL/GOOG, `$200`, monthly cadence, daily timeframe, SPY benchmark, and an original date range.
- [ ] Trigger result explanation/refinement behavior.
- [ ] Send a date-only free-text patch such as October 2019 through October 2025.
- [ ] Simulate at least one runtime failure and retry lifecycle transition.
- [ ] Simulate reload by relying on persisted conversation/checkpoint metadata.
- [ ] Assert the final draft or confirmation preserves canonical fields and normalizes the start of the month to the first day.
- [ ] Assert stale retry metadata is not presented as an active retry after supersession.

Verification:

```bash
poetry run pytest tests/test_chat_runtime_reload_guardrails.py -q
```

Commit checkpoint:

```bash
git add tests/test_chat_runtime_reload_guardrails.py
git commit -m "test(chat): cover messy artifact continuity replay"
```

### Task 9: Harden Frontend Retry Hydration and Conversation Loading

Files:

- Modify `web/lib/chat-retry-actions.ts`
- Modify `web/components/chat/artifact-history.ts`
- Modify `web/components/chat/ChatInterface.tsx`
- Update `web/__tests__/chat-retry-actions.test.ts`
- Update `web/__tests__/chat-artifact-history.test.ts`

Steps:

- [ ] Add tests proving superseded or expired retry metadata does not hydrate as an actionable retry.
- [ ] Add tests proving active retry metadata still hydrates when it points to the current failed action.
- [ ] Use backend lifecycle metadata as the source of truth.
- [ ] Do not infer retry state from visible message text.
- [ ] Ensure direct `/chat?conversation=<id>` loads a conversation-loading state while messages hydrate.
- [ ] Show cold-start starter prompts only when there is no target conversation and no hydrated active conversation.

Verification:

```bash
cd web && bun test __tests__/chat-retry-actions.test.ts __tests__/chat-artifact-history.test.ts
```

Commit checkpoint:

```bash
git add web/lib/chat-retry-actions.ts web/components/chat/artifact-history.ts web/components/chat/ChatInterface.tsx web/__tests__/chat-retry-actions.test.ts web/__tests__/chat-artifact-history.test.ts
git commit -m "fix(chat): hydrate retry actions from lifecycle state"
```

### Task 10: Keep Date and Market Guardrails Separate

Files:

- Modify only the current owner files if tests expose date/data-window failures.

Steps:

- [ ] Confirm continuity code does not own market-hour or provider-date availability policy.
- [ ] If a future-date or market-data-window bug appears, put the guardrail in the existing market-data/date capability owner, not in `interpret_actions.py`.
- [ ] Keep the user-visible confirmation card concise, using the established editable assumption pattern.
- [ ] Preserve the `Through Jun 2` pattern where date availability is already validated by the market-data guardrail.
- [ ] Add tests with a far-future date if the date/data-window owner changes.

Verification when this task touches code:

```bash
poetry run pytest tests/agent_runtime tests/test_chat_runtime_reload_guardrails.py -q
```

Commit checkpoint when this task touches code:

```bash
git add <changed-files>
git commit -m "fix(agent-runtime): validate artifact dates through data guardrails"
```

### Task 11: Focused Verification

Files:

- No code changes expected unless verification finds a bug.

Steps:

- [ ] Run backend artifact and conversation tests.
- [ ] Run frontend retry and hydration tests.
- [ ] Run relevant static checks for edited backend files.
- [ ] Run relevant frontend lint/test checks for edited frontend files.
- [ ] Fix failures in the owning module only.

Verification:

```bash
poetry run pytest \
  tests/agent_runtime/test_artifact_continuity.py \
  tests/agent_runtime/test_conversational_contract_hardening.py \
  tests/test_chat_runtime_reload_guardrails.py \
  -q
```

```bash
poetry run ruff check src/argus/agent_runtime src/argus/api/chat src/argus/api/routers/agent.py tests/agent_runtime tests/test_chat_runtime_reload_guardrails.py
```

```bash
cd web && bun test __tests__/chat-retry-actions.test.ts __tests__/chat-artifact-history.test.ts
```

```bash
cd web && bun run lint
```

Commit checkpoint if cleanup is needed:

```bash
git add <changed-files>
git commit -m "chore(chat): clean up artifact continuity verification"
```

### Task 12: Live Browser QA

Files:

- No code changes expected unless QA finds a bug.

Steps:

- [ ] Stop stale local servers before QA.
- [ ] Start QA backend with `.github/qa.sh`.
- [ ] Start frontend with `cd web && bun run dev`.
- [ ] Open `http://localhost:3000/chat` in the in-app browser.
- [ ] Log in with a QA user.
- [ ] Replay the `Review 1` stress path from the top.
- [ ] Click action chips back and forth, including confirmation actions, result actions, and retry surfaces.
- [ ] Refresh mid-flow.
- [ ] Restart the backend and refresh again.
- [ ] Confirm no cold-start starter surface flashes for a direct conversation URL while the conversation hydrates.
- [ ] Confirm canonical fields remain attached to the artifact after refinement and retry.
- [ ] Confirm generic guidance does not swallow typed modification turns.
- [ ] Confirm stale retry surfaces are hidden or disabled with clear lifecycle behavior.
- [ ] Capture conversation id, browser URL, screenshots, and relevant backend log snippets.

Manual acceptance prompts:

```text
Can you set a strategy where I buy AAPL GOOG at $200 every month for Jan 2021-Jan 2024?
```

```text
Can I do the same strategy but please change the date range from October 2019 to October 2025?
```

```text
do the date range October 2019 to October 2025
```

QA fix ownership:

- Draft field loss: `src/argus/agent_runtime/artifacts/drafts.py`
- Patch merge error: `src/argus/agent_runtime/artifacts/patches.py`
- Wrong anchor: `src/argus/agent_runtime/artifacts/continuity.py`
- Stale retry: `src/argus/agent_runtime/artifacts/lifecycle.py` or `web/lib/chat-retry-actions.ts`
- Hydration flash: `web/components/chat/ChatInterface.tsx`
- Data availability/date guardrail: current market-data/date capability owner

Commit checkpoint if QA fixes are needed:

```bash
git add <changed-files>
git commit -m "fix(chat): harden artifact continuity live qa"
```

## Final Acceptance Checklist

- [ ] Draft reconstruction works from confirmation, result, saved strategy, and failed action artifacts.
- [ ] Typed patch semantics preserve omitted canonical fields.
- [ ] Result refinement preserves result-owned strategy facts.
- [ ] Confirmation actions preserve the visible artifact state.
- [ ] Post-artifact patch turns route to confirmation instead of generic guidance.
- [ ] Retry lifecycle is backend-owned and hydrates safely after reload.
- [ ] Direct conversation URLs do not show cold-start starters while hydrating.
- [ ] Date/data-window guardrails remain in their proper owner.
- [ ] `Review 1` macro replay passes in automated tests.
- [ ] Focused backend tests pass.
- [ ] Focused frontend tests pass.
- [ ] Live browser QA passes after refresh and backend restart.
- [ ] Commits are atomic and conventional.

## Review Questions Before Implementation

- Does every new behavior have a focused owner file?
- Does every patch path start from a visible artifact anchor?
- Does the LLM still interpret language before deterministic guardrails run?
- Does the frontend render lifecycle state instead of inventing it?
- Would the same path work for buy-and-hold, DCA, RSI, moving-average crossover, equity, and crypto within Alpha constraints?
- If the user stress-clicks chips out of order, does the system clarify, preserve, or expire state instead of corrupting it?
