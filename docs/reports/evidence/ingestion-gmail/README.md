# Gmail connector evidence (wave 1B)

**Date:** October 1, 2026. **Branch:** `claude/ingestion-gmail`.
**Lane spec:** [financial-ingestion-connectors](../../../specs/lanes/financial-ingestion-connectors.md).
**API:** [Gmail connector routes](../../../API_CONTRACT.md#gmail-connector-default-off).
**Data:** [Gmail sender allowlist](../../../DATA_MODEL.md#gmail-sender-allowlist).

**Verification level: mocked provider only.** No Google Cloud OAuth client or
test inbox exists yet, so no request in this lane reached Google. Every Google
response used in the tests comes from an in-process fake
(`tests/ingestion/gmail_fakes.py`) with synthetic, clearly labeled mailboxes
(`tests/ingestion/gmail_mailbox.py`: fictional banks on `.test` domains, no real
people or email content).

The connector observes only. It turns allowlisted, sender-authenticated Gmail
messages into `ImportCandidate` drafts handed to the hub's `CandidateSink`; it
never creates accounts or activity. Code: `src/argus/domain/ingestion/gmail/`
(config, client, state, oauth, senders, senders_postgres, mime, html_text,
attachments, authenticity, extract, messages, failures, sync, suggestions,
adapter, connector), routes in
`src/argus/api/routers/financial_connections_gmail.py`, wiring in
`src/argus/api/gmail.py`, table in
`supabase/migrations/20261001160000_financial_source_gmail_senders.sql`.
Forwarding mail to Cuadrao is not offered as a substitute for this connection.

## Scope and why

Exactly one scope: `https://www.googleapis.com/auth/gmail.readonly`.

- It is the narrowest Gmail scope that can read message bodies and
  attachments, which bank alerts and statement notices need. Google classifies
  it as **restricted** ([Gmail API scopes][gmail-scopes], [restricted
  scopes][restricted]).
- `gmail.metadata` cannot read bodies or attachments and is restricted too
  ([Gmail API scopes][gmail-scopes]), so it would not reduce the verification
  burden. (Its inability to use the `q` search parameter is from memory of the
  Gmail reference and was not re-verified here.)
- No `openid` or `email`: `users.getProfile` returns the mailbox address under
  `gmail.readonly`, so no identity scope is requested.
- `access_type=offline` and `prompt=consent` obtain a refresh token on every
  authorization; `include_granted_scopes=true` makes an earlier
  `gmail.readonly` grant visible in the token response, so a token response
  without it means the person unticked it under granular consent, which Google
  expects apps to check ([granular permissions][granular]).

## What the founder must create

1. A Google Cloud project for Cuadrao (separate from any personal project).
2. Enable the Gmail API in that project.
3. Google Auth Platform / OAuth consent screen: user type **External**, app
   name "Cuadrao", support email, app logo optional, app domain and links to
   the privacy policy and terms (see Privacy below), authorized domain of the
   web app, developer contact. Add the scope `.../auth/gmail.readonly` under
   Data Access. Keep publishing status **Testing** and add each test user's
   Google account under Audience.
4. Credentials: an OAuth client of type **Web application**. Authorized
   redirect URI = the web app page that receives `code` and `state` (for
   example `https://<app-domain>/settings/connections/gmail`; an
   `http://localhost` URI is allowed for local development). That page posts
   both to `POST /api/v1/financial-connections/gmail/callback` with the
   person's session. The web page itself is not part of this lane.
5. A dedicated test inbox (a Gmail account created for testing, receiving
   only mail the founder authorizes for this purpose), added as a test user.
6. Store `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` and
   `GOOGLE_OAUTH_REDIRECT_URI` as server-side environment variables of the API
   service only (Render dashboard; `render.yaml` declares them `sync: false`,
   nothing is committed), with `ARGUS_INGESTION_SECRET_KEY` already set. Never
   put the client secret in the web app, a `NEXT_PUBLIC_*` variable, a
   transcript or a ticket. Enabling also needs `ARGUS_INGESTION_ENABLED=true`
   and `ARGUS_FINANCIAL_ACCOUNTS_ENABLED=true`, both still default-off.
7. Before any external user: Google verification of the restricted scope and
   the security assessment (below), and the privacy statements.

## Testing-mode limits (sourced)

| Limit | Source | How it was checked |
| --- | --- | --- |
| A project in **Testing** status is limited to 100 test users listed on the consent screen | [Manage App Audience][audience]; [Unverified apps][unverified] | WebSearch result summaries of Google Cloud Help; direct fetch of `support.google.com` was blocked by this environment's egress proxy |
| Refresh tokens issued to an External app in **Testing** expire after 7 days unless only name/email/profile scopes are requested | [Using OAuth 2.0 to Access Google APIs][oauth2] | WebSearch summary; `developers.google.com` fetch blocked here |
| Unverified apps requesting restricted scopes show the unverified-app screen and are capped at 100 new users over the project's lifetime | [Unverified apps][unverified] | WebSearch summary |

Consequence for testing: a test connection will hit `invalid_grant` about a
week after each authorization. The connector records `needs_reauth` with
`gmail_token_revoked`, keeps `last_success_at` and the cursor, and the person
re-runs authorize; the callback replaces the credential on the same connection.

## Restricted-scope verification and security assessment (sourced)

- Apps that request restricted scopes must pass a security assessment that
  verifies they handle data securely and delete user data on request; Google
  uses the App Defense Alliance **CASA** framework, and the assessor issues a
  Letter of Validation ([Security Assessment][casa]).
- The assessment is repeated every 12 months from the previous Letter of
  Validation date ([Annual Recertification][recert]).
- Google's API Services User Data Policy, including its **Limited Use**
  requirements, applies to data from these scopes ([User Data Policy][policy]).
- Not verified here: assessor cost and timeline (only third-party blog
  figures were found, not Google sources), and the exact CASA tier Google will
  assign; Google assigns it during review.

Until verification passes, Gmail stays limited to manually added test users.

## Privacy statements needed before external users

- A privacy policy section stating which Gmail data is accessed (messages from
  senders the person chooses, their headers, visible text and allowed
  attachments), why (proposing reviewed financial drafts), what is kept
  (below), that nothing is shared with a household or third party by
  connecting, and how to disconnect and delete.
- The Limited Use affirmative disclosure Google requires, for example: "Use
  of information received from Google APIs will adhere to the Google API
  Services User Data Policy, including the Limited Use requirements."
- In-app disclosure before consent: only chosen senders are read; drafts need
  review; sender suggestions read headers of recent mail on request.

## Data retention for email content

| Data | Kept? |
| --- | --- |
| Refresh token | Sealed (AES-256-GCM, bound to `gmail:<connection id>`) in `financial_source_connections`; deleted on disconnect |
| Access token | Memory only, minted per sync or suggestion request, never stored or logged |
| Mailbox address | Not stored: a keyed HMAC digest (`external_ref`) and a masked label only |
| Sender allowlist | `financial_source_gmail_senders`; deleted on disconnect |
| Message body, HTML, headers | Not stored; parsed in memory during a sync |
| Excerpt | Subject and visible text, inert and capped at 280 characters, inside the candidate (reconciliation decides its retention) |
| Attachments | Bytes fetched only for allowed types under 10 MiB, hashed and dropped; the candidate keeps `<message id>:<part id>`, media type, size, SHA-256 and inert file name |
| Sender suggestions | Computed per request from headers, never stored or logged |

Reading statement files (PDF/CSV) belongs to a document-import path that does
not exist yet; this wave hands off only the attachment reference.

## Content extraction is a separate, authorized step

No model and no keyword or regex rule reads what an email says. The shipped
`UnreviewedEmailExtractor` asserts only the sender domain; amount, currency,
dates, direction and account stay unresolved for review. A content extractor
plugs in through the `EmailExtractor` protocol (`extract.py`) and needs founder
authorization: a paid model and a committed scorecard (AGENTS.md
Never-Violate 12).

## Verification levels

| Claim | Level | Evidence |
| --- | --- | --- |
| Consent URL: `gmail.readonly` only, offline, `prompt=consent`, incremental, PKCE S256 | Mocked provider | `test_authorize_url_asks_only_for_gmail_readonly_with_pkce_and_offline_access` |
| State bound to the person, single-use, expiring, tamper-proof; PKCE verifier checked by the token endpoint | Mocked provider | `test_state_is_*`, `test_forged_or_altered_state_is_refused` (4), `test_a_code_issued_for_another_pkce_challenge_is_refused_by_google`, RFC 7636 vector |
| Partial consent refused and released; missing refresh token stores nothing | Mocked provider | `test_partial_consent_*`, `test_missing_refresh_token_*`, API 422 |
| Connection: digest ref, masked label, sealed refresh token | Mocked provider | `test_callback_creates_a_connection_*` |
| Reconnect updates the same connection; insert race resolves; other person's mailbox refused | Mocked provider; Postgres | `test_reconnect_*`, `test_concurrent_callback_race_*`, `test_mailbox_connected_by_someone_else_*`, `tests/test_ingestion_gmail_postgres.py` |
| Allowlist only; query built from it; strict local match (lookalike domain rejected) | Mocked provider | `test_initial_sync_imports_allowlisted_authenticated_messages_only`, `test_matching_*`, `test_senders_that_could_inject_query_operators_are_refused` (12) |
| Forged `From` skipped using Gmail's topmost `Authentication-Results` | Mocked provider (synthetic headers) | `test_gmail_authentication_results_decide_sender_authenticity`, spoofed fixture |
| MIME limits, charset handling, HTML to inert text, nothing fetched | Mocked provider | `test_hostile_html_*`, `test_hidden_markup_is_dropped` (6), `test_part_tree_is_bounded`, `fake.unexpected == []` |
| Attachment media types, size cap (30 MiB part never downloaded), signatures | Mocked provider | `test_attachment_policy_*`, `test_candidates_claim_only_machine_certain_facts` |
| Pagination (search and history), bounded with resume | Mocked provider | `test_scan_paginates_and_reports_truncation`, `test_history_pagination_is_bounded_and_resumes` |
| Incremental history, spam rescue, duplicates are one observation | Mocked provider | `test_incremental_*`, `test_message_rescued_from_spam_*`, `test_same_message_from_scan_and_history_*`, `test_a_retried_sync_*` |
| Concurrent syncs advance the cursor once; stale lease cannot advance | Mocked provider; Postgres | `test_concurrent_syncs_*` (memory and Postgres), `test_a_sync_that_outlives_its_lease_*` |
| History 404 recovery, window bounded | Mocked provider | `test_history_too_old_*`, `test_recovery_window_never_exceeds_the_lookback` |
| Revoked grant, 401, 403 scope, 403 other: `needs_reauth`, freshness kept | Mocked provider; Postgres | `test_revoked_refresh_token_*`, `test_refused_access_needs_reauth` (3) |
| 429/5xx bounded backoff then `gmail_unavailable`, cursor kept | Mocked provider | `test_outages_*` (3), `test_a_transient_outage_*` |
| Disconnect revokes; failure still deletes credential; allowlist deleted | Mocked provider; Postgres | `test_connect_choose_senders_sync_and_disconnect`, `test_failed_revocation_still_deletes_credential` |
| Flag/config off is 404; other person's connection is 404; no token in responses or logs | Mocked provider | `test_flag_off_*`, `test_missing_configuration_*` (4), `test_another_persons_connection_looks_absent`, loguru capture in the round-trip test |
| Allowlist table RLS, owner-only writes through a live connection | Real Postgres 16 (Supabase shim) | `test_clients_read_their_own_senders_and_never_write`, `test_senders_attach_only_*` |
| Real Google OAuth, consent screen, Gmail API behavior and quotas | **Not verified** | Needs the founder's OAuth client and test inbox |

## Commands and results

```bash
# Hermetic (no network)
python -m pytest tests/ingestion/test_gmail_*.py -q --no-cov
# 94 passed (oauth 16, parsing 34, sync 12, sync failures 13, api 19)

# Real Postgres (wave-0 and Gmail senders migrations)
ARGUS_DISPOSABLE_DATABASE_URL=postgresql://postgres@127.0.0.1:56811/argus_gmail \
  python -m pytest tests/test_ingestion_gmail_postgres.py \
  tests/test_ingestion_connections_postgres.py -q --no-cov
# 14 passed (gmail 4, connections 10)
```

## Unsupported or unknown

- Gmail push (`users.watch` with Pub/Sub) needs a hosted Pub/Sub topic;
  syncs are manual (`POST .../gmail/{id}/sync`) or a future scheduler.
- Messages whose sender domain Gmail did not authenticate (no DMARC pass and
  no aligned DKIM pass) are skipped and counted as `unverified_sender`. A bank
  without DKIM would be invisible; whether Dominican banks sign their alerts
  is unknown until real mail is seen.
- Attachments declared as `application/octet-stream` (even real PDFs) are not
  fetched; only declared PDF, CSV, PNG, JPEG, GIF and WebP are.
- A search reads at most 500 matching messages (5 pages of 100, newest first)
  and reports `scan_truncated`; older matches in that window are not read. A
  history sync reads at most 500 history records and resumes next time.
- Deleting or archiving an email does not withdraw its evidence (the fact did
  not change).
- The OAuth state replay ledger is per process; behind several API instances
  replay protection rests on Google's single-use code and PKCE (see
  `state.py`).
- Google Workspace accounts whose admin blocks third-party Gmail access fail
  with `gmail_access_denied`; not exercised against Google.
- In memory persistence mode the sender allowlist is in memory too.

## Proposed wave-0 changes (not made here)

1. `contract.py`: no way to say "evidence kind unknown". Proposed: add
   `"unknown"` to `EvidenceKind` (and require resolution in `unresolved()`), or
   add `"evidence"` to `UncertainField`. Until then Gmail emits
   `evidence="transaction"` with `kind` uncertain, the most demanding value.
2. `secrets.py`: connectors need a keyed digest (Gmail's mailbox
   `external_ref`). `gmail/config.py` re-decodes `ARGUS_INGESTION_SECRET_KEY`
   and derives an HKDF subkey itself. Proposed: `SecretBox.digest(value, *,
   purpose)` so the key is parsed in one place.
3. `hub.py`: connector-local state to delete on disconnect (the sender
   allowlist) is removed inside `SourceAdapter.revoke`, which is about the
   provider. Proposed: an optional `forget(connection)` adapter hook the hub
   calls after the local disconnect.

[gmail-scopes]: https://developers.google.com/workspace/gmail/api/auth/scopes
[restricted]: https://support.google.com/cloud/answer/13464325?hl=en
[granular]: https://developers.google.com/identity/protocols/oauth2/resources/granular-permissions
[audience]: https://support.google.com/cloud/answer/15549945?hl=en
[unverified]: https://support.google.com/cloud/answer/7454865?hl=en
[oauth2]: https://developers.google.com/identity/protocols/oauth2
[casa]: https://support.google.com/cloud/answer/13465431?hl=en
[recert]: https://support.google.com/cloud/answer/13463816?hl=en
[policy]: https://developers.google.com/terms/api-services-user-data-policy
