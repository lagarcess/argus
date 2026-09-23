# Local guest and display currency contract

This is the local SQLite experience. It does not create a provider account, email
address, bank connection, or record acceptance of terms. Guest profile labels are
`Local guest` / `Local guest workspace`; `preferred_name` and country are unknown.
Locale comes only from the submitted choice, and the initial timezone is UTC.

`POST /api/platform/session/guest` requires JSON
`{"locale":"en"|"es-419","mode":"demo"|"empty"}`. Success is `200` with the
normal session snapshot below. Each fresh entry gets a server-generated user and
household, owner membership, hashed session token, and HttpOnly / SameSite=Strict
cookie. Empty mode creates no financial records. Demo mode calls the registered
ledger seed owner within the same transaction to create a small independent
synthetic dataset; it never copies the shared demo identity or existing records.
Creation and any seed failure roll back together.

A valid existing guest cookie returns the same workspace/session, mode, locale
and expiry; it does not seed again or extend time. A signed-in local account gets
`409 already_signed_in`. An expired or revoked cookie cannot recover the old
workspace; explicit new entry creates a separate one. No request automatically
enters a workspace after logout.

The guest lifetime is fixed at 24 hours after creation, stored on the server.
Expired guest authentication or claim returns `401 authentication_required`.
The shared `active_context` authority also checks guest expiry inside persistence
transactions: a request captured before expiry cannot save private data after it.
There is a local lifetime creation cap of 1,000 guest workspace records, enforced
inside the write transaction (`429 guest_capacity_reached`). Expired records are
retained locally and still count; there is no automatic purge job in this slice.
The shared HTTP runtime additionally applies request/body/concurrency admission.
Foreign-origin writes are `403 cross_origin_write`, malformed commands are `422`,
and demo mode without a registered seed owner is `503 guest_demo_unavailable`.

`POST /api/platform/session/claim` requires the active guest cookie and JSON
`{"display_name":"My local profile","password":"chosen local password"}`.
Display name is trimmed, 1–80 characters; password is 10–128 characters. A `200`
response preserves the user ID, household ID, and every financial/artifact record,
saves a scrypt password hash, marks the guest as claimed, revokes prior sessions,
and issues a normal seven-day local session. There is no email or username field.
The UI must show/copy the returned `user.id`: subsequent login uses
`POST /session/login {"user_id":...,"password":...}`. A claimed account cannot be
claimed again (`409 guest_required`). Captured role/generation checks apply before
claim, so reset or role changes cannot be bypassed by a paused request.

Every session/login/guest/claim/household-switch snapshot adds these fields:

```typescript
data_generation: number; // Canonical household lifecycle generation.
guest: {
  is_guest: boolean;
  expires_at: string | null; // Fixed ISO UTC guest expiry; null after claim.
  mode: "demo" | "empty" | null; // null for permanent local accounts.
  can_claim: boolean;
  local_only: true;
};
currency_context: {
  currency: string | null;
  source: "explicit_override" | "selected_account" | "default_account"
        | "household_default" | "unknown";
  account_id: string | null;
};
```

Private browser draft keys must include `user.id`, `household.id` and
`data_generation`. Reset advances this generation; guest claim preserves it.
The snapshot reads it through the existing lifecycle authority in the same read
transaction as the rest of the snapshot, including after household switches.

`GET /settings` preserves the same `guest` and `currency_context` fields from the
identity snapshot. `PATCH /household {"country":null}` explicitly clears a saved
country for both guest and registered local accounts: storage uses the empty
string for the existing non-null column and responses serialize `country:null`.
Omitting `country` leaves it unchanged. Clearing it does not clear an explicit
currency override or account currency; with neither, display currency is unknown.

`GET /api/platform/session?account_id=<id>` selects a current-household active
ledger account for this response only. An unavailable, deleted or foreign account
returns `404 account_not_found`, even if an explicit currency override exists.
Without selection, the oldest active account by `recorded_at,id` supplies a stable
default; balances do not influence selection. Nothing persists a second account
currency or converts ledger amounts.

The precedence is explicit household currency override, selected/default active
account currency, then existing household country default. With none available,
`currency:null, source:"unknown", account_id:null`. Empty guests also expose
`household.country:null` and `household.effective_currency:null`. The compatibility
household currency field retains its country/override meaning; clients should use
`currency_context` for the account-aware display choice. Currency options still
derive from `supported_currencies`; JPY and KWD use their ledger-owned precision.
The UI must visibly identify explicit overrides and avoid rendering an unknown
currency as USD. Transaction, balance, import and chat action amounts always use
their canonical ledger account/transaction currency.

Integration: call `Identity.register_guest_seed(callback)` once during composition.
The callback receives `(sqlite_connection, authenticated_context)` in the guest
creation transaction. It owns only its domain records and should not acquire a
second write transaction. The seed is invoked only for a fresh demo entry; reset,
claim, re-entry, initialization and restart never invoke it.
Reset also restores unknown country/currency for a guest-origin household while
preserving its original guest expiry, including after that local account is saved.
