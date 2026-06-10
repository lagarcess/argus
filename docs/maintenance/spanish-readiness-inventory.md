# Spanish Readiness Inventory

## Summary

This inventory assesses the Argus application for Spanish localization readiness. It identifies hardcoded English strings and language/locale handling gaps across the frontend UI, backend deterministic copy, and LLM language contracts.

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
| **Frontend Cards** | `web/components/chat/StrategyConfirmationCard.tsx` | Status string matching (e.g., `row.label.toLowerCase() === "assets"`, `"period"`) | High | Product decision | Convert string-based conditional rendering to use programmatic keys (e.g., `row.type === 'asset_list'`). |
| **Frontend Cards** | `web/components/chat/StrategyConfirmationCard.tsx` | Fallback strings: `"Draft canceled"`, `"Ready"`, `"Updated"` | Medium | Jules-safe | Move to proper `t()` keys without relying on explicit fallback parameter defaults. |
| **Artifact Status** | `web/components/chat/artifact-history.ts` | Hardcoded status checks: `"Running"`, `"Run complete"`, `"Editing"`, `"Could not run"` | High | Jules-safe | Refactor to use status ENUMs instead of matching on display strings. |
| **Onboarding** | `web/components/onboarding/OnboardingGate.tsx` | Hardcoded titles: `"Choose your language"`, `"Learn investing basics"` | Medium | Jules-safe | Ensure `t()` handles localization via JSON mapping, standardizing keys. |
| **Backend API Errors** | `src/argus/api/routers/conversations.py` | Hardcoded HTTP exception details: `"Conversation not found."`, `"Strategy not found."` | Medium | Product decision | Implement error code system (e.g., `error_code="CONVERSATION_NOT_FOUND"`) that frontend maps to `t()`. |
| **Backend Results** | `src/argus/domain/benchmark_comparison.py` | User phrases generated in backend: `"Beat by {magnitude}"`, `"In line with benchmark"` | High | Product decision | Return structured data (e.g., `{ type: "beat_benchmark", value: magnitude }`) and localize in frontend. |
| **LLM Prompts** | `src/argus/agent_runtime/stages/interpret.py` | System prompts: `"Supported-strategy facts:"`, `"Available short-lived context packet:"` | High | Codex-owned | Do not change. Treat as Codex-owned runtime contracts.|

## Detailed Inventory

### Static frontend UI copy

| File / Area | Representative examples | Classification | Risk | Owner | Recommendation |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `web/components/chat/StrategyConfirmationCard.tsx` | `row.label.toLowerCase() === "assets"` | UI Logic | High | Product decision | Use structured data types instead of string matching. |
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

### Artifact/result/status labels

| File / Area | Representative examples | Classification | Risk | Owner | Recommendation |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `web/components/chat/artifact-history.ts` | `const IN_PROGRESS_RUN_STATUS_LABELS = new Set(["Running", "Request sent"]);` | Status check | High | Jules-safe | Refactor to use proper status code enums instead of English string matching. |
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
