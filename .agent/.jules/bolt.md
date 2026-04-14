## 2026-04-14 - Agentic Reason Engine

**Learning:** LangChain `with_structured_output` mapping to Pydantic objects creates a highly resilient JSON-schema response from OpenRouter/DeepSeek. Quota exhaustion triggers Postgres `P0001` exceptions via `execute()` in the Supabase client when mapped via SECURITY DEFINER, which requires careful string matching. Mocking dependencies with `Depends` in FastAPI requires targeting the exact module where the dependency is injected, or using `app.dependency_overrides`.

**Action:** Implemented the logic and established retry loops via custom `@retry_with_backoff` decorator in `agent.py`. Used Langchain to power `draft_strategy` using the `_StrategyDraftOutput` internal model.
