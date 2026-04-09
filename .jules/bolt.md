
## 2026-04-09 - [Align Profile Schema to V1 API Contract]
**Learning:** During the automated API typescript generation, using the `openapi-ts` CLI from root directly overwrote the entire manually maintained `/web/lib/` folder, breaking mock and local configs.
**Action:** Introduced an `openapi-ts.config.ts` configuration to target `lib/generated` to protect manual source files, resolving wiping issues, and then manually re-exported the generated typescript interfaces in `lib/api.ts`.
