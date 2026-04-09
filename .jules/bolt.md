
## 2026-04-09 - [Align Profile Schema to V1 API Contract]
**Learning:** During the automated API typescript generation, using the `openapi-ts` CLI from root directly overwrote the entire manually maintained `/web/lib/` folder, breaking mock and local configs.
**Action:** Introduced an `openapi-ts.config.ts` configuration to target `lib/generated` to protect manual source files, resolving wiping issues, and then manually re-exported the generated typescript interfaces in `lib/api.ts`.

## 2026-04-09 - [PR #25 Regression Fixes - OpenAPI BacktestResponse & Single Symbol Constraints]
**Learning:** OpenAPI generator didn't export `BacktestResponse` properly out-of-the-box in its barrel file because it wasn't strictly defined in the `schema.py` or because of a naming conflict. A manual interface was overriding it.
**Action:** Re-added the export to `web/lib/api.ts`, removed the manual `BacktestResponse`, patched `mockApi.ts` to construct the object cleanly matching the expected schema map (with `id`, `config_snapshot`, and `results`), and fixed builder regressions ensuring exactly 1 symbol is sent and mapping correctly to `indicators_config`.
