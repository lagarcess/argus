# Modularity Budget Report

Generated for the initial lightweight guardrail baseline.

## Guardrail behavior

- The budget is intentionally narrow and non-refactoring: it watches known large production files only.
- Current line counts are recorded in `.agent/modularity_budget.json`.
- CI fails only when a watched file grows by more than `75` lines beyond its recorded baseline.
- The guard prints the top watched offenders on every run so follow-up refactors can be planned without blocking unrelated work.

## Current top offenders

| Rank | File | Baseline lines | Allowed limit | Recommended follow-up issue |
| ---: | --- | ---: | ---: | --- |
| 1 | `src/argus/agent_runtime/llm_interpreter.py` | 5,279 | 5,354 | Split interpreter prompts, audit helpers, and repair orchestration behind existing `agent_runtime/interpreter/` modules. |
| 2 | `src/argus/agent_runtime/stages/interpret.py` | 3,159 | 3,234 | Extract stage-specific merge, validation, and response-shaping helpers while preserving LangGraph as the single chat brain. |
| 3 | `web/components/chat/ChatInterface.tsx` | 2,523 | 2,598 | Separate rendering shells, artifact lifecycle wiring, and chat-side effects into focused hooks/components without changing UX. |
| 4 | `src/argus/domain/supabase_gateway.py` | 2,036 | 2,111 | Split product persistence gateways by durable artifact type: conversations, messages, runs, feedback, and preferences. |
| 5 | `src/argus/agent_runtime/stages/explain.py` | 1,574 | 1,649 | Separate explanation state collection, deterministic fact formatting, and LLM budget invocation. |
| 6 | `src/argus/api/routers/agent.py` | 1,393 | 1,468 | Keep the router thin by moving request/response assembly and persistence helpers into API service modules. |
| 7 | `src/argus/agent_runtime/stages/interpret_internal/asset_resolution.py` | 1,302 | 1,377 | Split provider-backed lookup, candidate ranking, and user-facing ambiguity shaping. |
| 8 | `src/argus/api/chat/breakdown.py` | 1,242 | 1,317 | Extract deterministic breakdown sections and LLM invocation policy into smaller helpers. |
| 9 | `web/lib/argus-api.ts` | 1,179 | 1,254 | Split API clients by product surface while keeping the documented API contract as source of truth. |
| 10 | `src/argus/agent_runtime/result_followups.py` | 1,138 | 1,213 | Separate supported next-experiment selection from user-facing follow-up copy. |

## Recommended issues

1. **Interpreter decomposition spike** — define safe seams in `llm_interpreter.py` and `stages/interpret.py` that do not introduce regex gates or a second orchestrator.
2. **Chat UI shell split** — move `ChatInterface.tsx` side effects and artifact rendering into focused hooks/components with screenshot-backed QA.
3. **Persistence gateway boundaries** — split `supabase_gateway.py` by entity ownership while preserving RLS expectations and durable artifact semantics.
4. **API thin-router cleanup** — move helper logic out of `agent.py` and keep FastAPI routes limited to auth, validation, transport, persistence, and error shaping.
5. **Result explanation/follow-up modularity** — separate deterministic metrics truth from assistant voice surfaces for explain/breakdown/follow-up modules.
