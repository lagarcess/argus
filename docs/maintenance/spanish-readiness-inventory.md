# Spanish Readiness Inventory

## Summary

This inventory assesses the Argus application for Spanish localization readiness. It identifies hardcoded English strings and language/locale handling gaps across the frontend UI, backend deterministic copy, and LLM language contracts.

**Decision:** Spanish is not release-ready for private alpha yet. This branch is
allowed to land Spanish scaffolding behind `NEXT_PUBLIC_ENABLE_SPANISH`, but
Spanish must remain disabled in production-like Render environments until a
Codex-owned runtime readiness gate passes. The current work stabilizes
translation keys, static UI coverage, and confirmation-card state handling; it
does not prove the LangGraph chat/backtest spine is language agnostic.

**Runtime-state normalization update:** `codex/private-alpha-readiness` adds a
shared `resolution_provenance` normalizer for workflow snapshots, public runtime
payloads, interpreter patches, and LLM interpreter capability validation. This
addresses the known dict-shaped provenance crash class, but Spanish must remain
disabled in production-like environments until the broader Spanish runtime QA
matrix and live canary pass.

The findings are grouped by category:
*   **Static frontend UI copy**: ~100+ strings wrapped in `t()` with hardcoded English fallbacks.
*   **Backend deterministic user-facing copy**: ~20+ strings in API exceptions and artifact labels.
*   **LLM prompt / instruction language contracts**: ~15+ strings in system prompts and context packets.
*   **Artifact/result/status labels**: ~10+ strings defining statuses and outcomes.
*   **Test fixtures/snapshots**: ~10+ strings in validation tests.
*   **Internal logs/debug-only strings**: ~50+ log messages using English.

## Highest Priority Findings

| Area | File(s) | Finding | Risk | Owner | Recommendation |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Frontend Cards** | `web/components/chat/StrategyConfirmationCard.tsx`, `web/components/chat/confirmation-display.ts`, `src/argus/api/chat/confirmation.py` | Confirmation cards now emit/use stable `status`, `rows[].key`, and i18n label keys instead of using translated labels for behavior. | Resolved | Codex-owned | Keep the `spanish-ui-smoke` guard that rejects `row.label.toLowerCase()` and English status sets in card state logic. |
| **Artifact Status** | `web/components/chat/artifact-history.ts`, `web/lib/chat-backtest-jobs.ts` | Confirmation lifecycle updates now store stable status codes while preserving legacy English fallback labels for old persisted cards. | Resolved | Codex-owned | Continue using `confirmation-display.ts` helpers for new confirmation status behavior. |
| **Onboarding** | `web/components/onboarding/OnboardingGate.tsx` | Hardcoded titles: `"Choose your language"`, `"Learn investing basics"` | Medium | Jules-safe | Ensure `t()` handles localization via JSON mapping, standardizing keys. |
| **Backend API Errors** | `src/argus/api/routers/conversations.py` | Hardcoded HTTP exception details: `"Conversation not found."`, `"Strategy not found."` | Medium | Product decision | Implement error code system (e.g., `error_code="CONVERSATION_NOT_FOUND"`) that frontend maps to `t()`. |
| **Backend Results** | `src/argus/domain/benchmark_comparison.py` | User phrases generated in backend: `"Beat by {magnitude}"`, `"In line with benchmark"` | High | Product decision | Return structured data (e.g., `{ type: "beat_benchmark", value: magnitude }`) and localize in frontend. |
| **LLM Prompts** | `src/argus/agent_runtime/stages/interpret.py` | System prompts: `"Supported-strategy facts:"`, `"Available short-lived context packet:"` | High | Codex-owned | Do not change. Treat as Codex-owned runtime contracts.|
| **Runtime State Hydration** | `src/argus/agent_runtime/state/models.py`, `src/argus/agent_runtime/runtime.py`, `src/argus/agent_runtime/graph/workflow.py`, `src/argus/agent_runtime/stages/interpret.py`, `src/argus/agent_runtime/stages/interpret_types.py`, `src/argus/agent_runtime/llm_interpreter.py` | Dict-shaped `resolution_provenance` entries are normalized/deduped before durable snapshot carry-forward, public payload serialization, interpreter patches, and LLM interpreter capability validation. | Partially resolved | Codex-owned | Keep the regression tests; still run the full Spanish continuation QA matrix before enabling Spanish in Render. |
| **Recovery Copy** | `src/argus/api/routers/agent.py` | Generic runtime failure recovery currently persists English copy. | High | Codex-owned | Define structured error/recovery codes and language-aware presentation so Spanish users do not see English fallback copy on runtime failure. |

## Detailed Inventory

### Static frontend UI copy

| File / Area | Representative examples | Classification | Risk | Owner | Recommendation |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `web/components/chat/StrategyConfirmationCard.tsx` | Confirmation row behavior now uses `rows[].key` with legacy fallback mapping in `confirmation-display.ts`. | UI Logic | Resolved | Codex-owned | Preserve stable row keys for future languages. |
| `web/components/chat/ChatInput.tsx` | `t("chat.message_empty", "Message is empty")` | Fallback | Low | Jules-safe | Rely on localization JSON files instead of hardcoded fallbacks. |
| `web/components/chat/ChatInterface.tsx` | `t("onboarding.goals.learn_basics.title", "Learn investing basics")` | Fallback | Low | Jules-safe | Rely on localization JSON files. |
| `web/components/chat/StrategyResultCard.tsx` | `t("chat.result_card.ending_value", "Ending value")` | Fallback | Low | Jules-safe | Rely on localization JSON files. |
| `web/components/sidebar/ProfileMenu.tsx` | `t("settings.profile.delete_account", "Delete account")` | Fallback | Low | Jules-safe | Rely on localization JSON files. |

### Backend deterministic user-facing copy

| File / Area | Representative examples | Classification | Risk | Owner | Recommendation |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `src/argus/api/routers/*.py` | `raise HTTPException(status_code=404, detail="Conversation not found.")` | Error msg | Medium | Product decision | Send error codes instead of strings to allow frontend localization. |
| `src/argus/api/dependencies.py` | `detail="Supabase persistence is required for non-mock authentication."` | Error msg | Medium | Product decision | Send error codes. |
| `src/argus/domain/benchmark_comparison.py` | `user_phrase=f"Beat by {magnitude}"` | Data label | High | Product decision | Move string generation to the frontend, send structured values. |

### LLM prompt / instruction language contracts

| File / Area | Representative examples | Classification | Risk | Owner | Recommendation |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `src/argus/agent_runtime/stages/interpret.py` | `{"role": "system", "content": f"Supported-strategy facts: {fact_packet}"}` | Prompt | High | Codex-owned | No action needed. Treat as Codex-owned. |
| `src/argus/agent_runtime/artifact_edit_planner.py` | `{"role": "system", "content": ...}` | Prompt | High | Codex-owned | No action needed. Treat as Codex-owned. |
| `src/argus/agent_runtime/result_followups.py` | `{"role": "system", "content": ...}` | Prompt | High | Codex-owned | No action needed. Treat as Codex-owned. |
| `src/argus/agent_runtime/stages/explain.py` | `{"role": "system", "content": ...}` | Prompt | High | Codex-owned | No action needed. Treat as Codex-owned. |

### Runtime language-agnostic spine

| File / Area | Representative examples | Classification | Risk | Owner | Recommendation |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `src/argus/agent_runtime/state/models.py`, `src/argus/agent_runtime/runtime.py`, `src/argus/agent_runtime/graph/workflow.py`, `src/argus/agent_runtime/stages/interpret.py`, `src/argus/agent_runtime/stages/interpret_types.py`, `src/argus/agent_runtime/llm_interpreter.py` | Shared provenance normalization protects persisted snapshot carry-forward, public runtime payloads, interpreter patches, and LLM capability validation from dict/model drift. | State normalization | Partially resolved | Codex-owned | Broaden Spanish continuation/live QA before enabling the Spanish feature flag. |
| `src/argus/api/routers/agent.py` | Runtime failure recovery writes English text directly into the assistant transcript. | Recovery copy | High | Codex-owned | Keep recovery behavior structured and language-aware; do not make English prose the durable failure contract. |
| `tests/agent_runtime/*` | Existing tests cover many English runtime paths but do not yet cover Spanish multi-turn continuation into confirmation/result. | Coverage gap | High | Codex-owned | Add a compact Spanish runtime transcript set before enabling Spanish in Render. |

### Artifact/result/status labels

| File / Area | Representative examples | Classification | Risk | Owner | Recommendation |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `web/components/chat/artifact-history.ts` | Confirmation lifecycle now uses stable confirmation status codes and legacy label fallback mapping. | Status check | Resolved | Codex-owned | Do not reintroduce English display-label state checks. |
| `web/lib/backtest-job-card-copy.ts` | `statusLabelFallback: "Queued"`, `"Running"`, `"Result ready"`, `"Could not run"`, `"Not completed"` | Fallback | Low | Jules-safe | Rely on localization JSON files. |

### Test fixtures/snapshots

| File / Area | Representative examples | Classification | Risk | Owner | Recommendation |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `tests/test_slot_normalizer.py` | `normalize_parameter_value("dca_accumulation", "dca_cadence", "semanal") == "weekly"` | Test data | Low | Jules-safe | Already localized conceptually, maintain aliases. |

### Internal logs/debug-only strings

| File / Area | Representative examples | Classification | Risk | Owner | Recommendation |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `src/argus/llm/openrouter.py` | `logger.warning("OpenRouter unavailable; missing API key", llm_task=task)` | Log | Low | Jules-safe | No action needed. Logs can remain in English. |
| `src/argus/api/chat/recovery.py` | `logger.warning(...)` | Log | Low | Jules-safe | No action needed. |

### Already localized / no action needed

| File / Area | Finding | Reason |
| :--- | :--- | :--- |
| `web/components/ThemeProvider.tsx` | N/A | No user-visible strings. |
| `src/argus/domain/cadences.py` | English keys `["daily", "weekly"]` | Backend keys, mapped using normalizer alias mechanism. |
