### Stability Batch Summary

**A) Dev identity + DB contract alignment**
- Replaced the invalid sentinel `"dev-anon-user"` with the valid UUID `668d486d-558d-4d08-98e0-952cdaf00492` across `auth.py`.
- Added an explicit profile bootstrap path in `auth_required` specifically scoped to dev mock users. It queries the Supabase service-role client to insert the necessary default `profiles` row safely, throwing a `500 Internal Server Error` if it fails rather than degrading silently to a detached mock object.

**B) Stop false-success masking in core endpoints**
- Modified `PersistenceService.list_strategies` and `PersistenceService.get_user_simulations` to explicitly re-raise exceptions encountered during database querying instead of swallowing them and returning empty lists.
- Mapped these downstream to FastAPI 500 error boundaries, ensuring UI requests appropriately catch standard `APIError` payloads instead of treating system failures as empty states.

**C) Save Draft API path completion**
- Verified the Save Draft `onSubmit` branch in the builder (`web/app/(protected)/builder/page.tsx`) was calling `createStrategy`/`updateStrategy` properly.
- Introduced `web/lib/api-errors.ts` to unbox the wrapped SDK responses robustly.
- Wrapped the draft save and backtest execution network calls in `try...catch` blocks. The success toast and redirect sequence are properly halted on exceptions and replaced by actionable error toasts matching the UI guidelines.

**D) SSO redirect hardening**
- Bolstered the `sso_login` endpoint logic. Now enforces that `redirect_to` must not be empty/falsy before running strict allowlist checks via `get_settings().ALLOWED_REDIRECT_URLS`.

**E) Settings getter tests**
- Implemented `tests/test_config.py` verifying standard operations for the singleton config `get_settings()`, including checking environment value mapping and ensuring array deserialization via custom validators executes successfully.

**G) Golden flow persistence verification**
- Embedded explicit behavior-proving unit integration tests into `tests/test_api.py`.
- Checked draft save paths, historical endpoint visibility invariants, and assertions over Supabase table insertion mocks for telemetry.

**Metrics:**
- Backend tests ran: 32 (100% passed).
- Frontend tests ran: 10 (100% passed).
- OpenAPI definition matches UI precisely.
- Minimal MVP confidence scale adjusted significantly. No residual unmapped errors were logged in API routing endpoints during the suite execution.

**Residual Risks:**
- Pydantic models for strategy definitions may require further alignment in edge cases. Specifically observed in testing, partial definitions or empty strategies throw validation limits (e.g. `timeframe` field requiring proper Enum matches `1Hour`). Draft flows passing empty criteria objects will be rejected by the endpoint payload structure rather than the persistence layer.
