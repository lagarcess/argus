# Argus Large-File Modularity Inventory

## Summary

This inventory examines the largest files across the Argus repository (`src/**/*.py`, `web/**/*.ts`, `web/**/*.tsx`) to identify mixed concerns, architectural bottlenecks, and potential extraction seams.

- **Top largest files:** `src/argus/agent_runtime/llm_interpreter.py` (6.8k lines), `src/argus/agent_runtime/stages/interpret.py` (5.2k lines), `web/components/chat/ChatInterface.tsx` (2.3k lines).
- **Highest mixed-concern smell:** `web/components/chat/ChatInterface.tsx` (mixes routing, API parsing, local UI state, result card transformations, and view layout).
- **Safest extraction candidates:** `src/argus/agent_runtime/llm_interpreter.py` (splitting out Audit Pydantic models and pure text-grounding utilities) and `web/lib/argus-api.ts` (splitting out chat stream parsing from standard REST fetchers).
- Avoid touching: The agent_runtime stages (like interpret.py, execute.py, confirm.py, explain.py) handle delicate orchestration logic with specific prompt dependencies. Large-scale refactoring without extensive test coverage carries high risk.

## Inventory

| File | Approx lines | Primary responsibilities | Mixed concerns observed | Suggested extraction seam | Confidence | Risk notes | Recommended next action |
|---|---|---|---|---|---|---|---|
| `src/argus/agent_runtime/llm_interpreter.py` | 6800 | Core LLM JSON extraction, audit model definitions, validation logic. | Combines Pydantic Audit models, symbol grounding utilities, and core interpretation. | Extract `Audit` models to `llm_interpreter_models.py` and text utilities to `asset_text_grounding.py` or similar. | High | Many pure functions, but touches core LLM loop. Direct coverage appears decent but extraction could break import chains. | Extract Pydantic schemas and pure normalizers. |
| `src/argus/agent_runtime/stages/interpret.py` | 5200 | Primary conversation stage logic for strategy parsing. | mixes LLM response profile rendering, timeframe/date math, and state mutation. | Extract date math / endpoint repairs to `argus/agent_runtime/date_resolution.py`. | Medium | Core workflow stage. Modifying orchestration directly is high risk. | Extract isolated date/timeframe pure functions. |
| `web/components/chat/ChatInterface.tsx` | 2300 | Main chat UI container. | Manages active conversation URL state, API request hydration, chat card state modifications, and UI rendering. | Extract state management / routing to a custom hook (e.g., `useChatSession`) and API hydration to separate util. | High | UI regressions, component re-render loops if state isn't memoized correctly. | Extract pure helper functions to `web/lib/chat-utils.ts`. |
| `src/argus/agent_runtime/result_followups.py` | 1400 | Generates follow-up facts and UI answers post-backtest. | Fact bank generation, Markdown drafting, and LLM invocation. | Separate FactBank generation from LLM Markdown rendering/drafting. | Medium | Risk of breaking result card explanatory text. | Acceptable for now, coherent responsibility. |
| `src/argus/domain/supabase_gateway.py` | 1300 | Abstraction for Supabase database access. | Handles queries across users, backtests, and strategies. | Split into domain-specific repositories (e.g., `UserRepo`, `BacktestRepo`). | High | Widespread usage. Database queries are central to the app. | Extract isolated repos if the file grows, otherwise acceptable. |
| `src/argus/agent_runtime/stages/explain.py` | 1180 | Explains backtest outcomes to users. | Computes numerical performance comparisons and renders Quick Take drafts. | Move performance logic (e.g., relative returns, bps math) to `engine_metrics.py`. | Medium | Core conversational logic. | Extract numerical diffing functions. |
| `scripts/benchmarks/backtest_infra_benchmark.py` | 1180 | CLI tool for benchmarking backtest performance. | Combines child process spawning, memory tracking, and Markdown reporting. | Extract Markdown rendering to a shared reporting module if reused. | High | Not production code, safe to modify. | Acceptable for now. |
| `src/argus/api/routers/agent.py` | 1170 | FastAPI endpoints for chat/agent interaction. | API routing, header validation, fallback prompt definitions. | Extract prompt constants to a dedicated module. | Medium | API contract changes. | Acceptable for now. |
| `src/argus/agent_runtime/strategy_contract.py` | 1140 | Pydantic definitions and validation for executable strategies. | Date string parsing and strategy payload normalizations mixed with pure schemas. | Move date/period natural language parsing to a `date_parsers.py` utility. | High | Strategy contracts are critical for engine execution. | Extract pure token parsing utilities. |
| `web/__tests__/alpha-frontend.test.ts` | 1100 | Tests for the alpha frontend UI. | Combines mocking, DOM interactions, and assertions. | Split into targeted test files per component or feature. | Medium | Could break test suite if not careful. | Split tests by module when adding new coverage. |
| `src/argus/agent_runtime/stages/execute.py` | 1080 | Prepares backtest payloads and dispatches execution. | Tool call creation, error classification (e.g., lookback limits), and payload patches. | Move error string classification to `engine_errors.py`. | Medium | Modifying execution dispatch could fail silent. | Extract error classification pure functions. |
| `web/lib/argus-api.ts` | 990 | Frontend API fetchers and SSE parsing. | Mixes standard REST `fetch` calls, SSE parsing logic, and response normalization. | Move SSE parser (`parseChatStreamFrame`) to `web/lib/sse-parser.ts`. | High | Core API client. | Extract SSE parsing and discovery caching logic. |
| `src/argus/llm/openrouter.py` | 960 | Manages OpenRouter LLM requests and token tracking. | API routing, timeout calculations, and usage merging. | Split token usage aggregation from API transport logic. | Medium | Critical path for LLM availability. | Acceptable for now. |
| `src/argus/api/chat/breakdown.py` | 900 | Generates detailed strategy breakdown responses. | LLM invocation, prompt drafting, and text normalization. | Separate text normalization (sentence fragment fixes) from LLM invocation. | Low | Complex string manipulation. | Acceptable for now. |
| `src/argus/agent_runtime/stages/confirm.py` | 820 | Validates strategy capability before execution. | Deals with unsupported constraints, data adjustments, and prompt overrides. | Move data adjustment math and capability checks to `capabilities/contract.py`. | Low | Complicated assumptions logic. | Avoid touching until dedicated milestone. |

## Verification
- **Files changed:** `docs/maintenance/large-file-modularity-inventory.md` created.
- **Checks run:** File line counts and structural sampling executed. `git diff --check` to be verified.
- **CI Status:** Pending push.
- **Risks:** This inventory is report-only and poses zero risk to production behavior.
- **Follow-up recommendations:** Focus initial extraction efforts on pure text/date normalization functions inside the `agent_runtime` files to reduce noise, and consider splitting out the SSE parser from `web/lib/argus-api.ts`.
