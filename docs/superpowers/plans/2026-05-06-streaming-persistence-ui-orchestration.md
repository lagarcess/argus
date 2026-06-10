# Phase 5 Streaming, Persistence, And UI Orchestration Plan

> [!NOTE]
> Historical context. This document is retained as implementation evidence and is not the current execution source of truth.

**Summary**
- Target artifact path for execution: `docs/superpowers/plans/2026-05-06-agent-runtime-phase-5-streaming-persistence.md`.
- Work stays on `fix/argus-runtime-sot`; current checkout is already on that branch.
- Convert production chat from blocking `workflow.invoke()` + `InMemorySessionManager` to `workflow.astream_events(..., config={"configurable": {"thread_id": conversation_id}}, version="v2")`.
- Keep Supabase `messages` and `backtest_runs` as product records, but make LangGraph’s checkpointer the only store for runtime thread state.

**Implementation Changes**
- Add checkpoint dependencies: `langgraph-checkpoint-postgres` and `psycopg[binary,pool]`. LangGraph’s docs state Postgres checkpoint support is a separate install and `AsyncPostgresSaver` is the async production checkpointer: [memory docs](https://docs.langchain.com/oss/python/langgraph/add-memory), [persistence docs](https://docs.langchain.com/oss/python/langgraph/persistence).
- Create an agent runtime resource/lifespan initializer:
  - `MemorySaver` for `ARGUS_PERSISTENCE_MODE != "supabase"`.
  - `AsyncPostgresSaver.from_conn_string(DATABASE_URL)` for Supabase production.
  - Call `await checkpointer.setup()` during Postgres startup so checkpoint tables exist.
  - Compile `build_workflow(..., checkpointer=checkpointer)` inside FastAPI lifespan and store it on `app.state`.
- Retire `InMemorySessionManager`:
  - Remove it from `src/argus/api/main.py`, `src/argus/agent_runtime/runtime.py`, and runtime tests.
  - Move task snapshot construction into graph state updates so checkpoints contain `latest_task_snapshot`, `artifact_references`, and `selected_thread_metadata`.
  - Ensure per-turn graph input is a patch containing the new `run_state` and `user`, without clearing prior checkpoint fields.
- Make graph execution async:
  - Convert `interpret`, `clarify`, `explain`, and `next_step` nodes to `async def`.
  - Use `.ainvoke()` for structured interpretation.
  - Use `.astream()` for user-visible clarification/explanation/next-step text so `astream_events()` can surface token chunks.
  - Wrap synchronous backtest execution with an async boundary, likely `asyncio.to_thread(...)`, so the API event loop is not blocked.
- Move production API to SSE over graph events:
  - Convert `/api/v1/chat/stream` to `async def`.
  - Preflight remains before streaming: auth, quota checks, conversation lookup, user message write.
  - During streaming, translate graph events into `data: {"type": ...}\n\n` payloads:
    - `stage_start`: when a graph node starts.
    - `token`: for chat model chunks from `clarify`, `explain`, and `next_step`.
    - `stage_outcome`: when node output changes outcome.
    - `final`: complete payload with `stage_outcome`, assistant text, confirmation payload, run/result card, next actions, and message id.
    - `data: [DONE]` terminates the stream.
  - Assistant messages and backtest runs are persisted only after the final graph state is assembled.
- Update frontend orchestration:
  - Update `web/lib/argus-api.ts` stream parser to consume data-only SSE events with `type`, while tolerating legacy `event:` frames during migration.
  - Update `ChatInterface.tsx` to drive status from `stage_start`, not local timers or outcome strings.
  - Add locale keys for `interpret`, `clarify`, `confirm`, `execute`, `explain`, and `next_step`.
  - Render tokens progressively from `token.content`; render confirmation/result cards from the `final` payload.
  - Show only a neutral loading state before the first `stage_start`.

**Public Interfaces**
- Keep endpoint path `/api/v1/chat/stream`.
- Canonical SSE frame shape becomes:
  - `{"type":"stage_start","stage":"interpret"}`
  - `{"type":"token","content":"..."}`
  - `{"type":"stage_outcome","outcome":"ready_for_confirmation"}`
  - `{"type":"final","payload":{...}}`
- Runtime config must use `thread_id == conversation_id`; no alternate thread key is allowed.
- New required production env: `DATABASE_URL` when `ARGUS_PERSISTENCE_MODE=supabase`.

**Test And Verification Plan**
- Backend unit tests:
  - Async workflow test proving state resumes on the same `thread_id` with `MemorySaver` and no `InMemorySessionManager`.
  - Async node tests proving LLM callers use `.ainvoke()` or `.astream()`.
  - SSE generator test proving `stage_start` precedes tokens and `final` precedes `[DONE]`.
  - Regression test or static guard that production API code does not call `workflow.invoke()`.
- Frontend tests:
  - Parser handles contract SSE frames and `[DONE]`.
  - Chat status labels update from `stage_start`.
  - Confirmation/result cards render from `final` payload.
- Commands:
  - `poetry run ruff check . --no-cache`
  - `poetry run pytest tests\agent_runtime tests\test_chat_runtime_cutover.py tests\test_alpha_api.py -q --no-cov`
  - `cd web && bun test __tests__`
- Manual gates:
  - Start backend, run `curl.exe -N` against `/api/v1/chat/stream`, and confirm token frames arrive incrementally before `final`.
  - In Supabase mode, send a turn, restart the server, send a follow-up on the same conversation id, and confirm LangGraph restores the pending strategy state instead of restarting the thread.

**Assumptions**
- `DATABASE_URL` points to the Supabase Postgres connection string with permissions to create/checkpoint tables.
- `messages` remain durable conversation history for UI and LLM context; they are not runtime session state.
- Existing onboarding/action shortcut flows can remain outside LangGraph for now, but normal investing-agent turns must use `astream_events()`.
- Existing deterministic confirmation card and backtest persistence helpers stay in place unless a test proves they block streaming or violate the checkpointer rule.
