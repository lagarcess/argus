# Guest Account Signup Handoff Design

**Issue:** #480

**Base:** `codex/private-alpha-next` at `e61707bfb85946f8fc6a3495faa587a3ff829cb1`

**Status:** Founder-approved implementation design

**Migration required:** Yes. Promotion must apply the migration manually under #449 before deploying the runtime change.

## Problem

Guest registration currently updates the existing anonymous Supabase Auth user
with an email and password. Supabase correctly classifies that mutation as an
email change, so it sends the email-change confirmation even though the person
is creating their first permanent Argus account.

The original link approach had one valuable property: the Auth UUID did not
change, so every conversation, message, run, and evidence row kept its owner
without a transfer. The cost was false Auth history. This design keeps the data
safety but removes the false history by using the existing guest handoff as the
single transfer boundary.

## Decision

Guest registration creates a new, non-anonymous Supabase Auth user through the
ordinary password signup operation. It never updates the anonymous user.

The guest workspace remains owned by the anonymous UUID until one of these
events occurs:

1. Supabase immediately returns a permanent session. Argus creates the profile
   and claims the handoff in the signup request.
2. Supabase requires email confirmation. Argus leaves the guest workspace and
   a cookie-bound handoff intact. After confirmation, the person's first login
   claims the handoff before returning the permanent session.

In both cases, `claim_guest_workspace_handoff_by_email` remains the only
operation that rewrites product ownership.

## API Flow

### `POST /api/v1/auth/guest/signup`

The request combines ordinary signup fields with the guest source and optional
typed pending action:

```json
{
  "email": "person@example.com",
  "password": "strong-password",
  "captcha_token": "fresh-turnstile-token",
  "language": "en",
  "display_name": "Alex",
  "username": null,
  "source_conversation_id": "conversation-uuid",
  "pending_action": {
    "reason": "keep_history",
    "conversation_id": "conversation-uuid",
    "action_id": "opaque-action-id"
  }
}
```

The endpoint requires the current verified guest session and the same
permanent-account access policy as ordinary signup. It serializes the normalized
email and optional username, prepares or reuses one signup handoff, then calls
Supabase password signup with a server-only one-time handoff proof.

The response uses the existing Auth response shape. `session: null` means the
existing localized check-your-email state. An immediate session also carries
the existing additive `guest_claim` object.

The old `POST /api/v1/auth/guest/link` endpoint and anonymous-user update are
removed. Expired guests use ordinary signup because their expired work is not
recoverable.

## Durable Handoff State

`guest_workspace_handoffs` gains a `handoff_kind`:

- `existing_account`: the current ten-minute sign-in handoff.
- `new_account_signup`: a registration handoff that expires with the fixed
  guest workspace, never later than seven days after workspace creation.

Preparing a signup handoff is one locked database operation. For the same guest
and normalized email it reuses the pending row and rotates the secret. If a
new Auth UUID has already been bound, the destination cannot change. This keeps
double clicks, ambiguous responses, and same-email retries on one account and
one transfer record.

The handoff destination foreign key points to `auth.users(id)` rather than
`profiles(id)`. This lets an Auth insert trigger bind the newly created UUID in
the same transaction that creates it, before the API creates the Argus profile.
Claim still requires both a permanent Auth user and its profile.

## Atomic Signup Binding

Argus adds a nested `argus_guest_signup` object to Supabase signup metadata. It
contains the handoff id and SHA-256 proof already held by the server. The raw
opaque handoff secret remains only in the HttpOnly cookie and is never sent to
the browser or stored in Auth metadata.

An `AFTER INSERT` trigger on `auth.users` validates all of the following before
binding the destination UUID:

- the new Auth user is non-anonymous and has an email;
- the handoff id, proof hash, normalized email hash, source guest, conversation,
  status, kind, and expiry all match;
- the source workspace is still active and unexpired; and
- no different destination UUID is already bound.

The trigger then removes `argus_guest_signup` from Auth user metadata in the
same transaction. Invalid proof aborts Auth creation. This closes the crash
window between provider signup and Argus recording which new identity owns the
handoff.

## Idempotency and Existing Emails

The guest signup route always checks `auth.users` under the normalized-email
advisory lock before calling Supabase signup.

- No Auth user exists: call password signup once. The insert trigger binds the
  returned UUID.
- The Auth user is the unconfirmed UUID already bound to this handoff: resend
  the signup confirmation without changing the stored password or creating a
  second account.
- The email belongs to any other Auth user: raise
  `EmailAlreadyRegisteredError`, return `409 account_exists_use_login`, and do
  not call signup. Transfer to an existing account still requires its password.
- A provider response that is not bound by the trigger is treated as an
  existing-email conflict, never as a new account.

An abandoned signup therefore leaves one source workspace, one pending
handoff, and at most one destination Auth user. A retry inside the workspace's
fixed seven-day lifetime resumes that state. No request silently merges into an
account proved only by email.

## Ownership and Evidence

The existing atomic claim preserves ids and moves the guest-owned mutable
graph: conversations, messages, chat-turn lifecycles, strategies, backtest
runs and jobs, Ideas and IdeaVersions, EvidenceArtifacts, DecisionNotes, and
context links. `conversation_read_states` follows the conversation owner through
its composite foreign key with `ON UPDATE CASCADE`.

Guest allowances and feedback remain with the anonymous source, as already
documented. Immutable cost, provider, security, route, and Auth audit evidence
is not rewritten.

## Verification Gates

Deterministic and disposable-database proof must cover:

- no guest-registration path calls the authenticated Auth user-update endpoint;
- signup creates a different permanent Auth UUID and the handoff moves the full
  guest graph exactly once;
- the signup insert trigger binds only the correct id, email, and proof and
  scrubs its metadata marker;
- same-email retry reuses the bound Auth user and resends confirmation without
  calling signup again;
- a different existing account returns `account_exists_use_login` before any
  provider mutation;
- the signup handoff cannot outlive the guest workspace; and
- concurrent attempts produce one destination account and one claim.

Hosted acceptance at the exact PR head must then run the real English and
Spanish guest journeys, each with a confirmation card and completed backtest.
For each journey, verify the Supabase Auth audit action is `user_signedup`, the
confirm-signup email has the correct address, and all guest conversation and
result artifacts appear after confirmation and login. Finally, change the
email on an existing account and verify the correct email-change template and
old address remain intact.

## Scope Boundaries

Do not modify `render.yaml`, `.env.example`, `.github/argus-env.sh`, any release
profile, `.env`, `web/.env.local`, or Supabase dashboard email templates. Do not
apply the migration to a hosted environment from this lane. Production deploys
remain founder-directed.
