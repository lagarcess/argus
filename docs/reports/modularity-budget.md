# Modularity Budget Report

Generated for the lightweight, forward-only guardrail baseline.

## Guardrail behavior

- The budget is intentionally forward-only and non-refactoring: only explicitly watched large files can fail CI.
- Current watched-file line counts are recorded in `.agent/modularity_budget.json`.
- CI fails only when a watched file grows by more than `75` lines beyond its recorded baseline.
- The script scans `src`, `tests`, and `web` and prints the top current large files so newly large files are visible without becoming surprise blockers.
- Every currently scanned Python, frontend-unit, and E2E test file at or above the configured `baseline_capture_minimum_lines` value (currently 1,000) has a current line-count baseline. Those files may grow by at most `75` lines before CI fails; no existing test needs an immediate rewrite.
- Frontend tests and E2E tests are deliberately included. The only exclusions are dependencies, build output, and the frontend lockfile.
- If a separately delivered change deletes a watched file, the checker skips that missing baseline. Deletion cannot block an unrelated change, and the stale entry can be removed during the normal follow-up.

## Current top offenders

| Rank | File | Baseline lines | Allowed limit | Recommended follow-up issue |
| ---: | --- | ---: | ---: | --- |
| 1 | `tests/agent_runtime/test_interpret_stage.py` | 11,010 | 11,085 | Split cases by interpreter capability while preserving the shared harness. |
| 2 | `tests/agent_runtime/test_conversational_contract_hardening.py` | 7,285 | 7,360 | Separate independent contract families into focused modules. |
| 3 | `tests/test_chat_runtime_reload_guardrails.py` | 6,280 | 6,355 | Group reload scenarios by durable artifact ownership. |
| 4 | `tests/agent_runtime/test_llm_interpreter_artifact_capability_repairs.py` | 5,738 | 5,813 | Extract capability-repair scenarios by supported strategy shape. |
| 5 | `tests/agent_runtime/test_llm_interpreter_semantic_contracts.py` | 5,292 | 5,367 | Split semantic contract assertions by owned field family. |
| 6 | `tests/agent_runtime/test_llm_interpreter_date_window_repairs.py` | 4,693 | 4,768 | Separate date-window cases by repair path. |
| 7 | `tests/agent_runtime/test_llm_interpreter_grounding_and_signal_rules.py` | 4,562 | 4,637 | Separate grounding and signal-rule scenarios. |
| 8 | `tests/test_alpha_api_supabase.py` | 4,489 | 4,564 | Divide API coverage by durable artifact endpoint. |
| 9 | `tests/test_alpha_api.py` | 4,335 | 4,410 | Divide API coverage by endpoint family. |
| 10 | `tests/test_openrouter_policy.py` | 4,038 | 4,113 | Separate provider-key and request-policy scenarios. |

## Recommended issues

1. **Interpreter test decomposition** — split the largest interpreter suites by capability or strategy shape while preserving shared fixtures and parametrization.
2. **Chat-runtime test decomposition** — group reload and lifecycle scenarios by durable artifact ownership.
3. **API test decomposition** — divide the large API suites by endpoint/artifact family without weakening contract coverage.
