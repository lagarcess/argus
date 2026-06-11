# Agent Runtime Phase 5 Streaming Persistence Implementation Plan

> [!NOTE]
> Historical context. This document is retained as implementation evidence and is not the current execution source of truth.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Argus chat turns to LangGraph-native checkpoint persistence and SSE event streaming.

**Architecture:** The production chat path invokes the compiled LangGraph workflow through `astream_events()` with `thread_id == conversation_id`. LangGraph checkpointers own runtime state; Supabase product tables continue to own messages and immutable backtest records.

**Tech Stack:** FastAPI, LangGraph `StateGraph`, `MemorySaver`, `AsyncPostgresSaver`, LangChain OpenRouter async model calls, Next.js fetch stream parsing, Bun tests, pytest.

---

### Task 1: Runtime Checkpointer And Async Graph

**Files:**
- Modify: `src/argus/agent_runtime/graph/workflow.py`
- Modify: `src/argus/agent_runtime/runtime.py`
- Modify: `src/argus/agent_runtime/llm_interpreter.py`
- Modify: `src/argus/agent_runtime/llm_clarifier.py`
- Modify: `src/argus/agent_runtime/stages/*.py`
- Test: `tests/agent_runtime/test_workflow.py`

- [x] Add tests for `MemorySaver` thread resume and graph event streaming.
- [x] Compile workflows with a checkpointer.
- [x] Convert graph nodes to async and remove production `.invoke()`.
- [x] Use async LangChain calls in production LLM paths.

### Task 2: API SSE Contract

**Files:**
- Modify: `src/argus/api/main.py`
- Test: `tests/test_chat_runtime_cutover.py`

- [x] Initialize runtime checkpointers during FastAPI lifecycle.
- [x] Use `stream_agent_turn_events()` in `/api/v1/chat/stream`.
- [x] Emit canonical data-only SSE frames and `[DONE]`.
- [x] Persist assistant messages and backtest runs only after final graph output.

### Task 3: Frontend Stream Orchestration

**Files:**
- Modify: `web/lib/argus-api.ts`
- Modify: `web/components/chat/ChatInterface.tsx`
- Modify: `web/public/locales/en/common.json`
- Modify: `web/public/locales/es-419/common.json`
- Test: `web/__tests__/alpha-frontend.test.ts`

- [x] Parse canonical `type` SSE frames while tolerating legacy `event:` frames.
- [x] Drive status labels from `stage_start`.
- [x] Render final confirmation/result payloads from the backend stream.

### Task 4: Verification

- [x] Run `poetry run ruff check . --no-cache`.
  - Result: `All checks passed!`
- [x] Run `poetry run pytest tests\agent_runtime tests\test_chat_runtime_cutover.py tests\test_alpha_api.py -q --no-cov`.
  - Result: `122 passed`.
- [x] Run `cd web && bun test __tests__`.
  - Result: `34 pass`.
- [x] Perform manual streaming check if local services and credentials are available.
  - Result: `curl.exe` was unavailable in this shell, so a streaming HTTP client was used against a temporary local uvicorn server. Verified `stage_start` before `token`, `token` before `final`, and `final` before `[DONE]`.
  - Limitation: the configured OpenRouter provider rejected/rate-limited the live request, so the smoke test produced one fallback token frame instead of multi-token provider streaming.
- [ ] Perform Supabase restart persistence check.
  - Blocked in this workspace: `.env` does not provide `DATABASE_URL`, which is required for `ARGUS_PERSISTENCE_MODE=supabase`.
