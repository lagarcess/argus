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

**Interpreter schema update:** `codex/private-alpha-readiness` now asks the LLM
to accept any user language while returning canonical Argus machine values, plus
`language`, `date_range_raw_text`, and `evidence_spans` metadata. Runtime date
repair can resolve bounded date spans through `argus.nlp.natural_time` before
falling back to whole-message parsing. This reduces hardcoded multilingual token
growth in core runtime contracts, but it still requires Spanish transcript QA
and live canary evidence before enabling Spanish in production-like environments.

**Domain slot normalization update:** LLM-returned DCA cadence values now pass
through the existing strategy capability registry after interpretation. Known
localized aliases such as `semanal` become canonical engine values such as
`weekly`; unknown cadence text is preserved as `raw_cadence` metadata and
cleared from the executable cadence field so deterministic guardrails can ask a
follow-up instead of leaking localized prose into the engine contract.

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
| **LLM Interpreter Metadata** | `src/argus/agent_runtime/llm_interpreter.py`, `src/argus/agent_runtime/llm_interpreter_types.py`, `src/argus/nlp/natural_time.py` | Structured interpretation now carries `language`, `date_range_raw_text`, and `evidence_spans`; bounded date evidence is resolved through natural-time parsing before whole-message fallback. | Partially resolved | Codex-owned | Keep the bounded-span tests; add Spanish transcript/live QA before enabling Spanish. |
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
| `src/argus/agent_runtime/llm_interpreter.py`, `src/argus/agent_runtime/llm_interpreter_types.py` | LLM interpreter schema and prompt now require canonical internal values, detected language, bounded date raw text, and evidence spans; conversion stores that metadata in `StrategySummary.extra_parameters`. | Interpreter contract | Partially resolved | Codex-owned | Do not make metadata executable by itself; keep deterministic validation and add Spanish runtime transcript coverage. |
| `src/argus/agent_runtime/llm_interpreter.py`, `src/argus/domain/slot_normalizer.py`, `src/argus/domain/strategy_capabilities.py` | Post-LLM DCA cadence values are normalized through registry aliases, so Spanish cadence text can reach the runtime without expanding core parser token tables. | Domain slot normalization | Partially resolved | Codex-owned | Extend this registry-backed pattern to other Argus-domain slots before adding more languages. |
| `src/argus/nlp/natural_time.py` | Bounded date evidence can be resolved with `dateparser` through the Argus natural-time wrapper instead of expanding month/date token tables inside runtime contracts. | Natural time parsing | Partially resolved | Codex-owned | Feed only bounded spans or strong candidates; avoid whole-chat false positives. |
| `src/argus/api/routers/agent.py` | Runtime failure recovery writes English text directly into the assistant transcript. | Recovery copy | High | Codex-owned | Keep recovery behavior structured and language-aware; do not make English prose the durable failure contract. |
| `tests/agent_runtime/*` | Existing tests now include Spanish DCA, direct buy-and-hold/date repair, mixed-asset guardrail, approval, and latest-result follow-up transcripts that exercise the real structured interpreter conversion and runtime validation. | Coverage gap | Medium | Codex-owned | Add full browser QA with live provider/auth before enabling Spanish in Render. |

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
