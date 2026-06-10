# Dead Code Candidate Inventory

| File / Symbol | Candidate Type | Evidence | Confidence | Recommended Next Action | Risk Notes |
| --- | --- | --- | --- | --- | --- |
| `src/argus/api/main.py:_encode_cursor` | unused exported function/component/type | Assigned in `main.py` but never imported or used. The real `encode_cursor` is imported directly in routers. | high | Remove assignment | Low risk |
| `src/argus/api/main.py:_decode_cursor` | unused exported function/component/type | Assigned in `main.py` but never imported or used. The real `decode_cursor` is imported directly in routers. | high | Remove assignment | Low risk |
| `src/argus/api/main.py:_search_type_rank` | unused exported function/component/type | Assigned in `main.py` but never imported or used. The real `search_type_rank` is imported directly in routers. | high | Remove assignment | Low risk |
| `src/argus/api/main.py:_score_search_item` | unused exported function/component/type | Assigned in `main.py` but never imported or used. The real `score_search_item` is imported directly in routers. | high | Remove assignment | Low risk |
| `src/argus/api/main.py:_runtime_confirmation_card` | unused exported function/component/type | Defined in `main.py` but never imported or used. | high | Remove function | Low risk |
| `src/argus/api/main.py:_llm_result_breakdown_message` | unused exported function/component/type | Defined in `main.py` but never imported or used. | high | Remove function | Low risk |
| `src/argus/api/pagination.py:_encode_cursor` | unused exported function/component/type | Assigned to `encode_cursor` but never imported or used. | high | Remove assignment | Low risk |
| `src/argus/api/search_utils.py:_score_search_item` | unused exported function/component/type | Assigned to `score_search_item` but never imported or used. | high | Remove assignment | Low risk |
| `web/components/chat/CollectionPicker.tsx` | deferred product surface | Flagged by knip as unused file. Checked via ripgrep; only referenced in tests. Collections are hidden in private alpha, but remain a documented deferred product object. | medium | Keep until a product owner decides whether Collections are sunset or returning. If sunset, delete with the related API helpers and tests in one focused change. | Do not remove as routine dead code; Collections remain part of the product canon even while disabled. |
| `web/components/views/CollectionsView.tsx` | deferred product surface | Flagged by knip as unused file. Checked via ripgrep; only referenced in tests. Collections are hidden in private alpha, but remain a documented deferred product object. | medium | Keep until a product owner decides whether Collections are sunset or returning. If sunset, delete with the related API helpers and tests in one focused change. | Do not remove as routine dead code; Collections remain part of the product canon even while disabled. |
| `web/components/chat/artifact-history.ts:confirmationActionStatusLabel` | unused exported function/component/type | Flagged by knip as unused export. Only used internally or in tests. | high | Remove export keyword | Low risk |
| `web/components/chat/artifact-history.ts:isSaveActionMetadata` | unused exported function/component/type | Flagged by knip as unused export. | high | Remove export keyword | Low risk |
| `web/components/chat/artifact-history.ts:supersedeOpenConfirmations` | test-only fixture / exported helper | Flagged by knip as unused export but ripgrep shows it's used internally in the same file. | medium | Remove export keyword | Low risk |
| `web/components/chat/card-formatting.ts:periodWithoutParentheses` | unused exported function/component/type | Flagged by knip as unused export. | high | Remove function | Low risk |
| `web/lib/argus-api.ts:normalizeApiLanguage` | unused exported function/component/type | Flagged by knip as unused export. | high | Remove export keyword | Low risk |
| `web/lib/argus-api.ts:getStarterPrompts` | unused exported function/component/type | Flagged by knip as unused export. | high | Remove function | Low risk |
| `web/lib/argus-api.ts:listCollections`, `createCollection`, `patchCollection`, `deleteCollection`, `attachStrategyToCollection` | deferred product surface | Flagged by knip as unused exports. Collections are hidden in private alpha, but remain a documented deferred product object. | medium | Keep until a product owner decides whether Collections are sunset or returning. If sunset, delete with the related UI and tests in one focused change. | Removing these helpers alone would make a future Collections restoration harder and risks drifting from the product canon. |
| `web/lib/chat-action-ownership.ts:isCardScopedAction` | unused exported function/component/type | Flagged by knip as unused export. | high | Remove export keyword | Low risk |
| `web/lib/chat-action-ownership.ts:visibleInputActions` | unused exported function/component/type | Flagged by knip as unused export. | high | Remove export keyword | Low risk |
| `web/lib/chat-backtest-jobs.ts:backtestJobFromMetadata` | unused exported function/component/type | Flagged by knip as unused export. | high | Remove export keyword | Low risk |
| `web/lib/chat-backtest-jobs.ts:isTerminalBacktestJobStatus` | unused exported function/component/type | Flagged by knip as unused export. | high | Remove function | Low risk |
| `web/lib/chat-conversation-routing.ts:actionConversationId` | unused exported function/component/type | Flagged by knip as unused export. | high | Remove export keyword | Low risk |

### Verification Checklist & Risks

* **Files changed:** Created `docs/maintenance/dead-code-candidates.md`
* **Checks run:**
  * Backend: `rg`, `poetry run ruff check`
  * Frontend: `eslint`, `knip`
* **CI Status:** Report-only inventory; rerun CI when converting any candidate into deletion or visibility changes.
* **Risks:**
  * Unused exports may be intended as public SDK API surfaces, though current direction (as of `docs/specs/private-alpha-next-integration.md`) implies a lean API.
  * Internal helpers (`supersedeOpenConfirmations`) might still be needed and modifying visibility can break tests unexpectedly if `isCardScopedAction` or similar is used in an external test suite.
* **Follow-up recommendations:**
  * Review the collections feature flag (`NEXT_PUBLIC_COLLECTIONS_ENABLED=false`). If the feature is permanently sunset, delete `CollectionsView`, `CollectionPicker`, the `web/lib/argus-api.ts` helpers, and related tests together.
  * Strip export keywords from internal helpers to restrict visibility.
