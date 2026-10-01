# Plaid connector evidence (wave 1A)

**Date:** October 1, 2026. **Branch:** `claude/ingestion-plaid`.
**Lane spec:** [financial-ingestion-connectors](../../../specs/lanes/financial-ingestion-connectors.md).
**API:** [Plaid connector routes](../../../API_CONTRACT.md#plaid-connector-default-off).

The connector observes only. It turns Plaid `/transactions/sync` rows into
`ImportCandidate` evidence handed to the hub's `CandidateSink`; it never
creates accounts or activity. Code: `src/argus/domain/ingestion/plaid/`
(config, client, mapping, failures, sync, link, verification, webhooks,
adapter, connector), routes in
`src/argus/api/routers/financial_connections_plaid.py`, wiring in
`src/argus/api/plaid.py`.

## Verification levels

| Claim | Level | Evidence |
| --- | --- | --- |
| Link token creation (new and update mode) | Sandbox | `sandbox-lifecycle.json`: `link_token_created`, `reconnect.update_mode_link_token_created` |
| Public-token exchange, sealed access token, institution label | Sandbox | `exchange.created`, `access_token_sealed`, `label` |
| Exchange retry returns the same connection (no duplicate) | Sandbox | `exchange.retry_created=false`, `retry_same_connection`, `connections=1` (Plaid returned the same Item for the repeated public token) |
| `NOT_READY` handled without claiming freshness | Sandbox | `initial_sync.not_ready_polls=1` |
| Cursor pagination with `has_more` (page size 100) | Sandbox | `initial_sync.pages=4`, `added=331` |
| Re-sync is idempotent | Sandbox | `resync`: 0 added/modified/removed |
| Pending to posted with `pending_transaction_id` | Sandbox | `pending_to_posted`: 17 pending rows before `/transactions/refresh`; 17 posted rows naming an earlier pending row; those 17 pending rows withdrawn as `removed`; 18 new pending |
| `ITEM_LOGIN_REQUIRED` to `needs_reauth`, cursor and freshness kept | Sandbox | `reset_login` (after `/sandbox/item/reset_login`) |
| Reconnect re-check keeps a still-broken Item in `needs_reauth` | Sandbox | `reconnect.status_after_check_without_link_ui` |
| Reconnect returns to `active` after update mode | Mocked provider | `test_reconnected_restores_active_and_keeps_cursor_and_freshness`, API round trip, Postgres test |
| Disconnect revokes at Plaid | Sandbox | `disconnect.provider_revocation=revoked`, `item_get_after_remove=ITEM_NOT_FOUND` |
| Webhook key endpoint reachable, unknown kid refused | Sandbox | `webhook_key_unknown_kid=INVALID_WEBHOOK_VERIFICATION_KEY_ID` |
| Webhook JWT verification (ES256, kid key, iat, body hash) | Mocked provider (local ES256 key) | `test_plaid_verification.py`, `test_plaid_webhook_api.py` |
| Webhook-triggered sync, Item status webhooks, `LOGIN_REPAIRED` | Mocked provider | `test_plaid_webhook_api.py` |
| `PENDING_EXPIRATION`/`PENDING_DISCONNECT` flag `attention_code` on an `active` connection; a successful sync keeps it; update mode (`set_secret` with the existing envelope) clears it | Mocked provider; real Postgres | `test_expiring_consent_flags_attention_that_syncs_keep_and_update_mode_clears`, `test_exchange_sync_and_resync_on_postgres` |
| Mutation during pagination restarts from the starting cursor | Mocked provider; also observed live once | tests below; a first lifecycle run at 19:30Z recorded `initial_sync.restarts=1` while Plaid was still writing the historical pull (that run's JSON was superseded by the committed run) |
| Lease and cursor CAS under concurrency | Mocked provider on real Postgres | `tests/test_ingestion_plaid_postgres.py` |
| Real-institution coverage | Not claimed | `institution-coverage.json` is directory metadata only |

Sandbox runs used `ins_109508` (First Platypus Bank) with the
`user_transactions_dynamic` test user. Plaid's Sandbox cannot drive the Link
update-mode UI from a server, and no Sandbox endpoint clears
`ITEM_LOGIN_REQUIRED` without Link, so the person's update-mode step itself was
not exercised; the server side before and after it was. Plaid cannot reach this
environment, so live webhook delivery was not exercised.

## Commands and results

```bash
# Hermetic (no network)
python -m pytest tests/ingestion/test_plaid_*.py -q --no-cov
# 76 passed (api 8, link 15, mapping 16, sync 11, verification 14, webhook api 12)

# Real Postgres (wave-0 migration)
ARGUS_DISPOSABLE_DATABASE_URL=postgresql://postgres@127.0.0.1:56811/argus_plaid \
  python -m pytest tests/test_ingestion_plaid_postgres.py -q --no-cov
# 2 passed

# Live Sandbox lifecycle: 21 Plaid calls
PLAID_ENV=sandbox PLAID_CREDENTIALS_INJECTED=true \
  python scripts/ingestion/plaid_sandbox_lifecycle.py

# Institution directory coverage: 25 Plaid calls, paced
PLAID_ENV=sandbox PLAID_CREDENTIALS_INJECTED=true \
  python scripts/ingestion/plaid_institution_coverage.py
```

`PLAID_CREDENTIALS_INJECTED=true` is the explicit, sandbox-only opt-in used
here because this session's egress proxy adds the Plaid credential headers. It
is ignored for `PLAID_ENV=production`; deployed services set
`PLAID_CLIENT_ID`/`PLAID_SECRET`. The JSON files hold counts, statuses and Plaid
error codes only; no token, Item id or transaction id.

## Coverage, separately from Sandbox success

`institution-coverage.json` (Sandbox directory, October 1, 2026):

- Plaid's API accepts 20 country codes: US, CA, GB, IE, FR, ES, NL, DE, IT, PL,
  DK, NO, SE, EE, LT, LV, PT, BE, AT, FI.
- `DO` is not one of them: `/institutions/get` and `/institutions/search` with
  `DO` answer `INVALID_FIELD`.
- Searching all supported countries for Banreservas, Banco Popular Dominicano
  and Banco BHD with `transactions` returns 0 matches.
- Institutions reporting `transactions` per country range from 4 (FI) to 9,865
  (US); see the JSON. These are directory counts, not connection proof.

Dominican accounts therefore stay with the Gmail and statement paths; Plaid is
for foreign (non-Dominican) accounts only, as the lane spec says.

## Unsupported or unknown

- Link update-mode UI, OAuth institutions and `redirect_uri` (not configured;
  production OAuth banks need a registered redirect URI and possibly a mobile
  universal link).
- Live webhook delivery to a public URL (`PLAID_WEBHOOK_URL` is empty here).
- Production access, pricing, `/transactions/refresh` add-on billing and real
  institution behavior.
- Accounts without transactions in a sync page get their hint from
  `/accounts/get` (one extra call per sync at most); investment accounts are
  not synced (`/transactions/sync` does not cover them).
- Rows the contract refuses (no `transaction_id`) are skipped and counted in
  `skipped`; the cursor still advances past them.
