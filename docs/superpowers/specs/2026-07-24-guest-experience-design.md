# Argus Guest Experience: Value-Before-Account Design

Status: **FOUNDER-APPROVED DESIGN — implementation remains separately gated by
the serialized plan and release checks below**

Date: 2026-07-24

Authoritative product direction:
[`docs/PRODUCT.md`](../../PRODUCT.md),
[`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md),
[`docs/API_CONTRACT.md`](../../API_CONTRACT.md),
[`docs/DATA_MODEL.md`](../../DATA_MODEL.md), and
[`.agent/designs/argus/DESIGN.md`](../../../.agent/designs/argus/DESIGN.md)

Active roadmap context:
[`docs/specs/private-alpha-next-roadmap.md`](../../specs/private-alpha-next-roadmap.md)
and
[`docs/specs/private-alpha-interim-roadmap.md`](../../specs/private-alpha-interim-roadmap.md)

Strategic context:
[`docs/specs/private-alpha-next-decision-memo.md`](../../specs/private-alpha-next-decision-memo.md)

Parallel runtime dependency:
[`docs/superpowers/specs/2026-07-23-always-progresses-continuity-design.md`](2026-07-23-always-progresses-continuity-design.md)

This is a product and architecture design. It does not claim that guest access,
public signup, Omnisearch discovery, voice, memory, sharing, or the
Always-Progresses runtime has been implemented, deployed, or exposed.

## Outcome

Anyone can understand and try the real Argus product before creating an
account.

A guest enters the normal chat workspace, describes or selects an investing
idea, receives real Argus guidance, and may complete one real historical
simulation. Argus asks for an account only when the user requests durable or
repeat value, such as another simulation, another preserved conversation, or a
saved decision.

Guest mode is not a demo runtime, fixture, fake result, reduced conversational
brain, or separate product. It is an acquisition and learning control plane
around the same owner-scoped chat, confirmation, backtest, result, usage, and
Omnisearch contracts used by registered users.

The shortest description is:

```text
value first
  -> one temporary Argus conversation
  -> one real historical simulation
  -> account at the moment durable or repeat value is requested
```

## Product Thesis

People cannot know whether Argus is useful from a landing page alone. The
product becomes understandable when a user turns a plain-language investing
question into a trustworthy historical result.

The riskiest assumption is not whether people will click Sign up. It is whether
an unregistered visitor will reach a meaningful Argus result and then choose to
preserve or continue the work.

Guest mode therefore optimizes for this sequence:

```text
arrive
  -> understand what Argus does
  -> send a real idea
  -> reach confirmation
  -> run one real backtest
  -> understand the result
  -> request more or durable value
  -> create or enter an account without losing the work
```

The feature is successful only if this loop creates observed activation and
conversion evidence. Public traffic, account creation, compliments, and raw
message volume do not prove product-market fit.

## Roadmap Position

Guest mode is not a seventh interim quality pillar and does not change the
completion definition of Always Progresses, Grounded Discovery, or Full
Omnisearch.

It is a parallel acquisition and feedback track:

- Always Progresses protects the conversation guest mode exposes.
- Grounded Discovery determines which public suggestions are trustworthy.
- Full Omnisearch determines the final guest Search experience.
- Guest mode removes the account wall so those capabilities can be observed by
  more people.

The guest branch may advance in parallel at the shell, auth, policy, quota, and
conversion layers. Public release waits for the three product dependencies
above to reach their named guest-facing gates.

## Founder-Approved Product Decisions

1. Guest mode opens directly into the main Argus chat interface. It does not
   open with the current auth wall, a marketing landing page, a setup wizard, or
   a blocking feature tour.
2. The guest experience looks and behaves like Argus. The interface does not
   label the person as a "guest" except where temporary retention must be
   explained.
3. A guest may have one temporary conversation available for seven days in the
   same browser.
4. A guest receives ten successfully completed assistant turns over the
   lifetime of that temporary conversation.
5. A guest may admit and complete one unique backtest. Exact replay of that
   admitted backtest does not consume a second unit.
6. Failed, interrupted, rejected, or pre-terminal turns do not consume a guest
   message unit. Rejected or failed-before-admission simulations do not consume
   the guest simulation unit.
7. There is no always-visible quota dashboard or usage meter in guest mode.
   Argus explains the boundary only when the user approaches or reaches it.
8. The existing verified starter-action chips are shared by guest and
   registered empty chats. They keep their currently verified auto-send
   behavior.
9. The stale goal-selection onboarding and the disabled exploratory
   "Show suggestions" path are not revived by this slice.
10. `New chat`, Recents/history, Omnisearch, and durable actions remain visible
    when they provide an honest experience or a contextual account-conversion
    moment. Guest mode must not become a museum of generic lock icons.
11. Starting another conversation while the current temporary conversation has
    content gives the user two explicit choices:
    - replace the temporary conversation and start over; or
    - create an account to keep the current conversation and start another.
12. Durable actions such as Add decision remain visible. Selecting one opens a
    contextual auth modal, preserves the pending action, and resumes it after a
    successful conversion.
13. Omnisearch remains visible and usable in guest mode. Public release is
    blocked until its guest-safe current-conversation and grounded-discovery
    behavior is reconciled with the Omnisearch slice.
14. Features that do not exist yet—personalization memory, voice, and public
    sharing—are not advertised as guest locks. When those registered features
    are implemented later, guest access can be reconsidered separately.
15. The bottom-left account/settings surface and the conversation three-dot
    menu are hidden for guests.
16. The top-right guest shell contains:
    - a gear control for theme, language, and feedback only; and
    - one compact Sign in control that opens a centered auth modal.
17. The auth modal borrows the visual language and legal treatment of the
    current landing auth experience. Contextual conversion moments open it in
    create-account-first mode; the header Sign in control opens it in
    sign-in-first mode.
18. Creating a new account preserves the temporary workspace by converting the
    anonymous identity in place.
19. Signing in to an existing account also preserves the temporary workspace
    through an explicit, atomic, one-time claim. The frontend must not silently
    discard it or reconstruct it from prose.
20. Guest mode uses the same LangGraph runtime and backtest engine as registered
    mode. It may not add a second chat brain, guest prompt tier, guest strategy
    taxonomy, fake result path, or frontend-invented artifact.
21. Guest mode may be implemented in parallel with the Always-Progresses pillar
    only because it does not change runtime semantics. It must rebase onto and
    pass exact-head live QA against the completed Always-Progresses integration
    candidate before public exposure.
22. Public enablement is a separate founder decision. Building the slice does
    not authorize deployment or removal of private-alpha protections.

## Non-Goals

This slice does not implement:

- a new conversational runtime;
- new strategy, indicator, forecasting, or market-data capability;
- a separate guest backtest engine or synthetic public demo;
- personalization memory or a memory inspector;
- voice capture or speech-to-text;
- public conversation or evidence sharing;
- billing, subscriptions, credits, or monetization tiers;
- a referral program, waitlist, invitation system, or social feed;
- multiple guest conversations;
- cross-device guest recovery;
- indefinite anonymous history;
- portfolio, brokerage, or trading execution;
- a broad redesign of chat, result cards, Recents, or Omnisearch;
- revived primary-goal onboarding;
- revived exploratory suggestion prompts;
- full logged-in account onboarding redesign;
- production deployment.

## Definitions

### Guest

A Supabase Auth anonymous user with a real UUID, a valid authenticated session,
a minimal Argus profile, owner-scoped product rows, a fixed expiry, and guest
entitlements.

A guest is not the unauthenticated Postgres `anon` role and is not the mock
developer account.

### Permanent account

A non-anonymous Supabase user with a verified sign-in identity and ordinary
registered entitlements.

### Temporary workspace

The guest's one owner-scoped conversation and its dependent messages,
lifecycles, checkpoints, confirmations, backtest job/run, result, and
automatically captured idea/evidence records.

### Conversion

Either:

- linking a new verified identity to the current anonymous user; or
- signing into an existing account and atomically claiming the temporary
  workspace.

### Contextual conversion moment

An action where the product can explain a concrete account benefit, such as
preserving the current conversation, starting another conversation, running a
second simulation, or saving a decision.

## Experience Architecture

```text
Public visitor
  -> server-created Supabase anonymous session
  -> minimal owner-scoped Argus profile
  -> normal ChatInterface
  -> existing LangGraph runtime
  -> existing confirmation and job admission
  -> one real result
  -> contextual conversion
       -> new identity linked in place
       OR
       -> one-time claim into an existing account
```

Guest behavior is enforced by a server-owned capability and entitlement
boundary. Frontend visibility improves the experience but is not authorization.

The guest slice may compose the current runtime. It may not modify
`src/argus/agent_runtime/**`, backtest strategy semantics, provider selection,
interpretation prompts, or result truth. A runtime defect discovered during
guest QA is reported to the owning runtime lane rather than patched inside the
guest branch.

## Feature Access Matrix

| Surface or action | Guest behavior | Registered behavior |
|---|---|---|
| Main chat | Full current chat experience within guest limits | Full current chat experience within account limits |
| Starter actions | Existing three verified chips | Same existing three verified chips |
| Conversation count | One temporary conversation | Multiple durable conversations |
| New chat | Empty chat resets directly; non-empty chat offers Replace or Create account | Creates another durable conversation |
| Recents/history | Visible; shows the current temporary conversation and its expiry, plus an account preservation affordance | Durable owner history |
| Omnisearch | Visible; searches the temporary workspace and guest-safe grounded discovery only | Durable owner artifacts plus grounded discovery |
| Clarification and confirmation | Available | Available |
| Backtests | One unique admitted simulation | Registered allowance |
| Result cards and chart ranges | Available | Available |
| Explain/refine follow-ups | Available within guest message allowance | Available within registered allowance |
| Add decision | Visible; opens contextual account conversion, then resumes | Persists immediately |
| Rename/pin/archive/delete menus | Hidden in guest conversation menu | Available where currently supported |
| Theme and language | Gear menu; browser-local preference | Gear/settings with profile persistence |
| Feedback | Gear menu; guest-safe submission | Existing authenticated submission |
| Account security and sessions | Hidden | Available |
| Memory | Not advertised until implemented | Future registered feature |
| Voice | Not advertised until implemented | Future registered feature |
| Public sharing | Not advertised until implemented | Future registered feature |

Visible controls must be truthful. A guest control either works immediately or
opens a conversion modal that names the exact benefit unlocked by that action.

## First Entry And Onboarding

### No wizard

The current primary-goal onboarding is stale because the product does not yet
use that answer to provide meaningful personalization. Guest mode does not ask
for a goal, risk tolerance, experience level, watchlist, or profile before
value.

Language resolves in this order:

1. browser-local Argus preference;
2. browser language;
3. English fallback.

The gear control lets the user change language and theme at any time.

### Shared empty-chat state

Guest and registered empty chats use the same core entry:

```text
                         argus

         Test an investing idea against history.

 Describe your idea naturally. Argus will clarify the setup,
 show what it can test, and run a historical simulation.

 [ Test Apple vs SPY ]
 [ Test Bitcoin (BTC) hold ]
 [ Test weekly Nvidia buys ]

 ┌────────────────────────────────────────────────────────┐
 │ Describe an investing idea                             │
 └────────────────────────────────────────────────────────┘
```

The three starter actions reuse the current verified labels, payloads, icons,
localization, and `handleSend` path. This slice does not create a second starter
component with different prompts.

The chips disappear after the first message as they do today.

The disabled exploratory suggestions remain disabled. Their ambiguous examples
are not guest onboarding and are not repaired in this slice.

### Contextual teaching

Argus teaches through the first successful task rather than a tour:

- the first confirmation may show one quiet, dismissible hint:
  "Review the assumptions, then run the test";
- the first result may show one quiet, dismissible hint:
  "Change the chart range or ask a follow-up."

Hints appear only when the relevant backend artifact exists. They never use
timers to invent progress and never block interaction. Dismissal is stored in
browser-local UI state and may carry into a newly created account as a
preference hint; it is not product memory.

### Legal and safety copy

Before the first message, the composer footer reads:

> By messaging Argus, you agree to Terms and acknowledge Privacy.

After the first message, the footer reads:

> Argus can make mistakes. For education only. Not financial advice.
> Terms · Privacy.

Terms and Privacy remain reachable throughout the guest session. Legal copy is
localized in English and Spanish and is not hidden by mobile keyboards.

## Guest Shell

### Top right

The guest header contains:

- Gear:
  - Theme
  - Language
  - Feedback
- Sign in

Gear does not expose account security, sessions, usage, archived chats,
recently deleted, notifications, or subscription placeholders.

The Sign in button opens a centered modal. It does not navigate away from the
conversation.

### Bottom left

The registered profile/settings control is hidden. The shell may show a quiet
temporary-session label where Recents normally communicates continuity:

> Temporary chat · available for 7 days in this browser

This is secondary status text, not a warning banner.

### Conversation menu

The top-right three-dot conversation menu is hidden because rename, pin,
archive, delete, and similar owner-workspace actions are not part of the one
temporary guest conversation.

## Temporary Conversation Lifecycle

### Creation

On the first public app request with no valid Argus session:

1. The server checks that guest mode is enabled.
2. Bot protection and short-window abuse controls run.
3. The server creates or reuses one Supabase anonymous session.
4. The server creates a minimal Argus profile with the same UUID.
5. The ordinary chat workspace renders.

The client must not create a new anonymous user on every reload or route
transition.

### Retention

The temporary workspace expires exactly seven days after the anonymous user was
created. Activity does not extend the deadline.

The UI derives its status from a server-provided `expires_at`; it does not
invent the seven-day clock locally.

Clearing browser data, signing out before conversion, changing browsers, or
changing devices may make the anonymous workspace unrecoverable. The product
explains this only where preservation matters.

### Reload

Within the valid browser session and retention window, reload restores:

- the same conversation;
- messages and typed metadata;
- active clarification or confirmation;
- admitted job and completed result state;
- current guest usage truth;
- pending contextual conversion state when safe.

Reload may not reconstruct a strategy or result from visible prose.

### Expiry

After expiry:

- the guest session can no longer read or mutate the workspace;
- the UI starts a fresh guest session only after explaining that the temporary
  conversation expired;
- a scheduled server-owned cleanup removes expired guest product records and
  anonymous Auth users;
- immutable aggregate cost and security evidence may remain only in
  privacy-safe, non-transcript form according to retention policy.

Supabase does not automatically clean up anonymous users, so cleanup is a
required production operation rather than a later optimization.

## New Chat Contract

If the current temporary conversation has no accepted user content, `New chat`
resets the empty state without conversion.

If it contains accepted user content, `New chat` opens:

```text
Start a new chat?

[ Start over ]
Replace this temporary conversation.

[ Create account ]
Keep this conversation and start another.
```

`Start over` requires one confirmation and then deletes or expires the current
temporary conversation before creating the replacement. It does not create a
second guest conversation. It also does not reset the guest identity's expiry,
message allowance, simulation allowance, or feedback allowance.

`Create account` opens the auth modal with the preservation benefit stated
above. After conversion, the old conversation remains and a new registered
conversation opens.

## Recents And History Contract

Recents remains visible because continuity is part of the real product.

For a guest it contains only:

- the one temporary conversation;
- its most recent title/preview where available;
- its exact expiry;
- a quiet "Create account to keep your history" affordance.

It must not render fake historical rows, other users' data, hidden saved
objects, or a generic disabled-state wall.

Selecting the row reopens the same temporary conversation.

## Omnisearch Guest Contract

Omnisearch is visible and usable, but its guest scope is explicit:

1. owner-scoped search across the temporary conversation and artifacts created
   from it;
2. provider-backed asset and capability discovery that is safe for public use;
3. no results from any other user's records;
4. no implied durable memory beyond the temporary workspace;
5. no hidden Strategies or Collections destinations;
6. no raw provider, model, receipt, or runtime metadata.

The guest implementation may compose the current owner-scoped Omnisearch API.
It must reconcile with the Grounded Discovery/Omnisearch pillar before public
release. If grounded discovery is not ready, the branch may be implemented and
tested without public enablement, but the production guest gate remains closed.

Omnisearch must not become a separate guest search product or bypass ordinary
asset/capability validation.

## Contextual Conversion

### Conversion moments

The auth modal opens when the guest:

- selects the second unique simulation;
- reaches the ten-turn message limit and attempts another turn;
- selects Add decision;
- chooses to keep the current conversation while starting another;
- requests durable history beyond the temporary conversation;
- invokes another implemented registered-only durable action.

The modal states the concrete benefit:

- "Create an account to run another simulation."
- "Create an account to save this decision."
- "Create an account to keep this conversation and start another."

It does not use vague upgrade language, pricing language, artificial urgency, or
feature-count marketing.

### Pending action preservation

Opening or canceling the modal does not mutate the conversation, consume usage,
or discard composer input.

When conversion succeeds, the exact pending typed action resumes once:

- a second Run uses a new idempotency identity;
- Add decision uses the current result/evidence artifact id;
- New chat creates one registered conversation;
- no action is inferred from display prose.

If replay is unsafe, Argus returns the user to the unchanged artifact and asks
them to select the action again. It never silently performs a different action.

## Identity And Account Conversion

### Anonymous identity

Guest mode uses Supabase Anonymous Sign-Ins:

- an anonymous user has a real Auth UUID;
- it uses the Postgres `authenticated` role;
- its JWT contains the server-owned `is_anonymous` claim;
- all product records remain owner-scoped to `auth.uid()`.

Authorization must never infer guest status from email, display name,
`user_metadata`, a frontend flag, or the Postgres role alone.

### New account: identity linking

Creating an account links a verified email/password identity to the current
anonymous user.

The Auth UUID stays the same, so profile and product ownership do not move.
Email verification and password creation follow current Supabase Auth
requirements. The modal keeps the workspace visible while verification is
pending and resumes the requested action only after the session is permanent.

After successful linking:

- `is_anonymous` is false;
- guest expiry no longer applies;
- permanent profile language/locale becomes authoritative;
- registered usage and feature entitlements apply;
- the conversation, messages, job, run, result, evidence, and pending action
  remain attached to the same owner UUID.

### Existing account: one-time claim

Signing in to an existing account cannot link two Auth users automatically.
The product uses a one-time server-owned handoff:

1. While the anonymous session is valid, the server creates a short-lived,
   single-use handoff bound to the anonymous owner and temporary workspace.
2. The browser signs in to the existing account.
3. An owner-scoped, transactional claim locks the handoff and workspace.
4. It validates:
   - the source user is anonymous and unexpired;
   - the destination is the authenticated permanent user;
   - the workspace has not already been claimed;
   - every dependent record belongs to the source owner;
   - no second guest conversation exists.
5. It transfers every user-visible product record required to preserve the
   conversation and result coherently.
6. It marks the handoff consumed before returning success.
7. The abandoned anonymous Auth user is deleted through a server-side
   maintenance/admin path after the transferred product graph is safe.

The transaction includes the conversation, messages, turn lifecycles, the
conversation's checkpointer thread identifier and owner metadata, backtest jobs
and runs, automatically captured idea/version/evidence records, and every other
conversation-owned artifact required by current canon.

Guest usage counters do not increase or overwrite the existing account's
registered usage. Immutable cost/security evidence is not rewritten as if the
existing account originally incurred it. The implementation plan must preserve
audit honesty while avoiding foreign-key or deletion conflicts.

Failure leaves the guest workspace under the anonymous owner and leaves the
existing account unchanged. Partial transfer is forbidden.

## Profile And Canonical Account State

Anonymous users require a minimal profile because current product ownership
references `profiles.id`.

The guest profile:

- uses the Auth UUID;
- has no invented or synthetic email address;
- stores browser-selected language, locale, and theme only where needed for
  server rendering;
- is non-admin;
- does not imply onboarding completion or personalization;
- derives guest status from verified Auth truth rather than an editable profile
  field.

The implementation must make `profiles.email` compatible with anonymous users
without creating fake addresses. Permanent-account conversion fills the
verified email.

The stale primary-goal onboarding object remains backward-compatible for
existing profiles but is not collected from guests.

## Public Access And The Private-Alpha Allowlist

Guest implementation and public enablement are separate.

Two server-side controls are required:

- `ARGUS_GUEST_ACCESS_ENABLED=false`;
- `ARGUS_PUBLIC_ACCOUNT_ACCESS_ENABLED=false`.

The web surface uses
`NEXT_PUBLIC_GUEST_ACCESS_ENABLED=false` only to select the entry presentation.
The server flags remain authoritative. A client/server disagreement fails
closed and is a release-profile error.

Both default off outside explicitly configured QA.

While public access is off:

- current private-alpha allowlist behavior remains unchanged for permanent
  signup/login;
- no public traffic can create a guest session.

When the founder enables public access:

- anonymous sessions are permitted;
- standard permanent users may create or enter accounts without a pre-existing
  allowlist row;
- existing allowlist rows continue to own staff roles such as admin/developer;
- an explicitly disabled account remains blocked;
- role elevation never comes from user-editable metadata.

The frontend flag may control visibility but is never the authorization
boundary.

## API And Client Contract Direction

The implementation plan must add or extend typed contracts for:

### Session bootstrap

- create or reuse one anonymous session;
- return ordinary secure browser cookies;
- be idempotent for an existing valid session;
- enforce bot and short-window protections before Auth user creation.

### `/me`

Add server-owned fields equivalent to:

```json
{
  "account_kind": "guest",
  "guest": {
    "expires_at": "2026-07-31T12:00:00Z",
    "conversation_limit": 1,
    "message_limit": 10,
    "simulation_limit": 1
  }
}
```

The implementation uses the field names `account_kind` and `guest` shown above.
The frontend consumes this server truth rather than inferring it.

### Usage

The existing usage contract remains the source for used/remaining truth. Guest
limits must be distinguishable from registered allowances without creating a
monetization plan model.

### Feature capabilities

The client receives explicit server capability truth for guest-safe actions.
It does not derive permissions by scattering `isGuest` checks across arbitrary
components.

### Conversion

Typed operations are required for:

- beginning/completing anonymous-to-permanent identity linking;
- creating and consuming an existing-account handoff;
- reporting an expired, consumed, conflicting, or unsafe handoff without
  leaking owner identity.

Every mutation uses existing request-id, idempotency, same-origin, and
Problem-Details conventions.

### Feedback

Guest feedback uses the current typed feedback model with a guest-safe quota.
It does not require an email address.

Canon updates to `API_CONTRACT.md` and generated/static API guards are required
before the implementation can merge.

## Guest Allowances

### Product limits

Per temporary guest identity:

- one conversation;
- ten successfully completed assistant turns over the seven-day lifetime;
- one unique admitted simulation over the seven-day lifetime;
- five feedback submissions over the seven-day lifetime.

These are acquisition safety limits, not pricing or monetization tiers.

The existing `usage_counters` model gains the additive period
`guest_session`. Its `period_start` is the anonymous profile creation time and
its `period_end` is the fixed guest expiry. The existing atomic settlement
owners write the guest-session counter for completed chat turns, unique
simulation admissions, and feedback; no parallel browser counter or guest-only
ledger is introduced.

### Counting semantics

A message unit settles only when Argus completes a useful assistant response
under the current serialized usage contract.

No message unit settles for:

- validation rejection;
- auth or ownership rejection;
- provider/model failure before a useful terminal response;
- interrupted stream without durable completion;
- durable replay of the same completed turn;
- abandoned or recoverable-failed lifecycle.

A simulation unit settles only through current atomic unique backtest
admission. Exact replay returns the same durable job/run without another unit.
Preflight rejection, capacity rejection, provider-history rejection, failed
admission, and identity collision do not consume it.

### Approaching a limit

The interface does not show a permanent meter.

At two remaining completed turns, Argus may show quiet account-preservation
copy. At zero, the next attempted turn opens the contextual auth modal without
sending the prompt or consuming usage.

After the first admitted simulation, a second Run action opens conversion
before admission. The original confirmation remains visible and unchanged.

### Abuse protection

Anonymous Auth creation and expensive guest operations require:

- invisible CAPTCHA or Cloudflare Turnstile;
- IP-based short-window limits;
- per-anonymous-user limits;
- existing global backpressure;
- idempotency on expensive operations;
- bounded request/body sizes;
- server-side feature flags;
- monitoring for anonymous-user creation volume and cleanup lag.

Browser cookies or local storage alone are not abuse controls.

The design accepts that determined users can change networks or devices. The
goal is to prevent casual abuse and runaway automation without turning the
first-use experience into an obstacle course.

## RLS And Security Contract

Supabase anonymous users use the `authenticated` Postgres role. Therefore:

1. Every user-owned policy keeps the owner predicate
   `(select auth.uid()) = user_id`.
2. `TO authenticated` alone is never sufficient.
3. Guest-restricted writes use a restrictive policy or a server-owned
   transaction that checks the trusted `is_anonymous` JWT claim.
4. Guest status is never read from `raw_user_meta_data`.
5. Update policies use both `USING` and `WITH CHECK`.
6. Security-definer functions are not added merely to bypass RLS. Any privileged
   claim function must live in a non-exposed schema, verify both owners, revoke
   `PUBLIC` execution, and grant only the intended server role.
7. Anonymous users cannot enumerate profiles, allowlist entries, accounts,
   conversations, search rows, jobs, results, feedback, or usage belonging to
   another owner.
8. Service-role and secret keys never enter browser code.
9. Next.js guest routes use dynamic rendering so anonymous session data cannot
   be cached across visitors.
10. Existing same-origin, CORS, secure-cookie, and live-session validation
    remain in force.

The security review must include explicit cross-owner and anonymous/permanent
policy matrices on real Postgres.

## Feedback

Feedback is part of the guest gear menu because public users are the reason to
open guest access.

Guest feedback supports the existing user-facing categories:

- general;
- bug;
- feature;

An optional numeric rating uses the already approved scalar
`context.rating`; it is not a new feedback type.

The guest does not need to enter an email.

Conversation context is attached only after explicit consent. The backend keeps
the current privacy sanitizer:

- no raw URL query;
- no email, token, cookie, header, or Auth data;
- no arbitrary nested browser metadata;
- no raw transcript by default;
- only approved scalar artifact/app context.

Feedback submission never consumes a chat or simulation unit.

## Analytics And Learning Contract

Guest mode is an experiment. It needs enough measurement to answer whether
value-before-account works, but not enough surveillance to recreate the user's
financial conversation in analytics.

Approved guest funnel concepts:

- guest session started;
- starter action selected;
- first useful assistant response completed;
- confirmation reached;
- first simulation admitted;
- first result completed;
- conversion prompt shown, with reason code;
- account creation completed;
- existing-account sign-in completed;
- temporary workspace claimed;
- guest limit reached;
- guest feedback submitted;
- guest session expired.

Events use the existing measurement envelope and privacy sanitizer. They may
include:

- pseudonymous/correlated session identity;
- language;
- surface;
- typed strategy/capability category where privacy-approved;
- conversion reason;
- terminal outcome;
- cost and latency through server-owned ledgers.

They must not include:

- raw prompts or assistant responses;
- exact capital, dates, or personal financial content;
- email or display name;
- cookies, tokens, headers, or IP address in PostHog properties;
- private conversation titles or previews;
- model/provider details in frontend events.

The first decision report should answer:

1. What share of guest sessions sends a first message?
2. What share reaches confirmation?
3. What share completes a first simulation?
4. Which contextual boundary most often produces account creation?
5. How often do guests hit a failure or loop before value?
6. What is the provider-reported cost per completed guest result?
7. How often does conversion preserve the workspace successfully?

No product dashboard is required before the event contract and raw evidence are
proven.

## Error And Recovery Behavior

Guest mode composes the Always-Progresses contract.

### Anonymous bootstrap failure

Keep the user on the entry surface and show one retry. Do not create a fake
local conversation that cannot reach the backend.

### Runtime or provider failure

Show the same honest recoverable behavior registered users receive. Preserve
the temporary workspace and do not charge failed work.

### Quota reached

Open a contextual auth modal. Do not turn the LLM response into a pricing pitch
and do not send a request that the server will reject after spending provider
cost.

### Expired session

Explain that the temporary chat expired. Offer:

- Start a new temporary chat; or
- Sign in.

Do not imply that an expired, deleted workspace can be recovered.

### Conversion failure

Keep the guest workspace unchanged. Preserve the pending action and allow one
retry. Existing account data must never be overwritten by a partial guest
claim.

### Omnisearch unavailable

Keep chat usable and show a scoped Search unavailable state. Do not route the
user to another account's data or fabricate discovery results.

## Localization And Accessibility

All guest chrome, auth copy, limits, legal copy, conversion reasons, expiry
copy, empty states, feedback, and errors ship in English and Spanish
(`es-419`).

The AI continues to mirror resolved language through the ordinary runtime.

Required accessibility behavior:

- 44px minimum hit targets;
- 16px minimum mobile input text;
- visible focus states;
- complete keyboard operation for gear, starter chips, auth modal, New chat
  choice, and feedback;
- focus trapped and restored correctly for centered modals;
- Escape closes non-destructive modals without losing work;
- screen-reader labels for icon-only controls;
- no color-only quota, error, or selected meaning;
- no auto-advancing tour or forced coachmark sequence;
- mobile keyboard must not hide legal copy or Send.

## Implementation Decomposition

This design is one product outcome but should land as four serialized,
revertable implementation blocks on one focused branch or a coordinated branch
stack.

### Block 1 — Guest identity and policy spine

- server feature flags;
- anonymous Auth bootstrap;
- minimal guest profile;
- `/me` account/capability truth;
- RLS and auth middleware;
- fixed expiry and cleanup operation;
- guest allowance configuration and counting;
- public-access/allowlist compatibility.

Stop if anonymous users can reach product data without owner-scoped RLS.

### Block 2 — Guest chat shell and onboarding

- auth-wall replacement behind the guest flag;
- shared starter-chip extraction/reuse;
- headline and explanatory copy;
- guest gear;
- legal footer;
- temporary status;
- hidden account/conversation menus;
- contextual hints;
- reload continuity.

Stop if the frontend requires a fake conversation or changes runtime behavior.

### Block 3 — Conversion and visible capability gates

- centered auth modal;
- new-account identity linking;
- existing-account one-time claim;
- pending typed action resume;
- New chat choice;
- Recents temporary row;
- Add decision and second-run gates;
- guest feedback;
- guest-safe Omnisearch reconciliation.

Stop if a transfer can partially move ownership, double-charge usage, duplicate
an action, or lose the temporary workspace.

### Block 4 — Evidence and public-readiness gate

- deterministic backend/frontend tests;
- real-Postgres RLS and transfer proofs;
- production-parity browser QA;
- abuse and cleanup proof;
- privacy review;
- analytics event proof;
- exact-SHA branch-deployed canary;
- founder go/no-go.

Public flags remain off until this block passes.

## Parallel Work And Dependencies

Guest mode may be implemented in parallel with Always Progresses under these
rules:

```text
Always Progresses runtime --------------------------\
                                                     -> final guest rebase
Guest identity/shell/conversion --------------------/   -> live QA

Grounded Discovery + Omnisearch ---------------------> guest Search release gate
```

The guest branch owns:

- auth/session control plane;
- RLS and guest profile policy;
- guest quotas;
- public shell and conversion UI;
- temporary retention and transfer;
- guest-safe feedback;
- guest entry and action gating.

It does not own:

- runtime progression semantics;
- interpretation or model prompts;
- strategy/capability truth;
- provider behavior;
- backtest engine semantics;
- grounded-discovery ranking;
- Omnisearch's broader registered product design.

Before integration, the branch must:

1. rebase or merge the latest founder-approved integration checkpoint;
2. prove no runtime files changed unless separately authorized;
3. rerun live guest QA on the exact combined head;
4. reconcile Omnisearch with its completed slice;
5. keep public flags disabled.

## Deterministic Verification

The implementation plan must include red-first tests for at least:

### Auth and profile

- one anonymous user is reused across reload;
- anonymous user receives a minimal profile without fake email;
- guest and permanent status come from server truth;
- private-alpha mode still rejects unlisted permanent users;
- public mode permits standard signup without role elevation;
- disabled users remain blocked;
- guest flag off creates no anonymous user.

### Ownership and RLS

- guest can read/write only its own permitted rows;
- guest cannot read another guest or permanent user's rows;
- permanent user cannot claim a guest workspace without a valid handoff;
- handoff is one-time, short-lived, owner-bound, and conflict-safe;
- failed transfer changes no owner;
- successful transfer moves the complete product graph;
- guest usage is not merged into registered allowance;
- cleanup cannot delete a converted permanent user.

### Usage

- exactly ten completed assistant turns settle ten guest units;
- failed/interrupted/replayed turns settle zero extra units;
- one unique simulation settles one unit;
- exact replay settles zero;
- second unique simulation is blocked before admission;
- concurrency and global backpressure remain unchanged.

### UI

- shared chips render for both empty guest and registered chats;
- chips use current verified payloads and auto-send path;
- stale onboarding and exploratory suggestions stay off;
- menu visibility follows server capability truth;
- auth modal preserves composer and pending typed action;
- New chat follows empty/non-empty rules;
- legal copy changes after first message;
- English/Spanish parity;
- keyboard, focus, mobile, light, and dark behavior.

### Expiry and cleanup

- fixed server expiry is not extended by activity;
- reload before expiry restores;
- expired session cannot access rows;
- scheduled cleanup removes expired guest data and anonymous Auth users;
- converted accounts and privacy-safe aggregate evidence survive correctly.

## Founder-Visible Browser Acceptance

Browser QA must use:

- a real anonymous Supabase identity;
- production-parity Supabase/Postgres persistence;
- the real LangGraph interpreter path;
- live provider-backed asset resolution;
- the current backtest execution path;
- the exact candidate SHA;
- no mock-auth developer account;
- no static playground as final evidence.

One visible journey must prove:

1. Public entry opens chat without login.
2. The value statement, legal copy, gear, Sign in, and verified starter chips
   render in English and Spanish.
3. A starter chip sends through the ordinary chat path.
4. Clarification and confirmation preserve the idea.
5. One simulation completes and shows an ordinary result card.
6. Chart range switching works without provider, usage, or persistence writes.
7. The result and message counts agree across UI, API, and database.
8. Reload restores the exact conversation and result.
9. Recents reopens the same temporary conversation and shows truthful expiry.
10. Omnisearch returns only the guest workspace and approved grounded discovery.
11. A second simulation opens conversion before admission and settles no unit.
12. Add decision opens contextual conversion and preserves the typed action.
13. New chat offers Replace versus Create account.
14. Canceling auth loses nothing.
15. Creating a new account keeps the same owner UUID and resumes one pending
    action.
16. A separate existing-account case atomically claims the temporary workspace
    without duplicates or lost artifacts.
17. Feedback submits without email or transcript leakage.
18. A deliberately failed/interrupted turn charges nothing and remains
    recoverable.
19. Expiry and cleanup are proven in an isolated time-controlled environment.
20. No browser console error, cross-owner read, hidden production write, or
    credential exposure occurs.

The agent performing QA must inspect the rendered conversation, not only DOM
assertions or API JSON. Screenshots and sanitized API/database evidence support
the verdict; they do not replace visible product judgment.

## Release Gates

Guest mode is not ready for public exposure until all are true:

- [x] Founder approves this written spec.
- [ ] An implementation plan is written from the approved spec.
- [ ] Always Progresses is integrated and guest QA passes on the combined head.
- [ ] Omnisearch/grounded-discovery guest behavior is implemented and reviewed.
- [ ] Anonymous Auth and manual identity linking are enabled in the isolated QA
      project only.
- [ ] RLS and claim transfer pass a real-Postgres security matrix.
- [ ] Guest cleanup runs successfully without touching permanent accounts.
- [ ] Deterministic backend and frontend suites pass at the exact candidate.
- [ ] Founder-visible production-parity browser QA passes at the exact
      candidate.
- [ ] Independent security and privacy review has no blocking finding.
- [ ] Independent code/product review has no blocking finding.
- [ ] Branch-deployed canary matches the candidate SHA and expected flags.
- [ ] Cost per completed guest result is measured and acceptable.
- [ ] Guest and public-account server flags remain off by default.
- [ ] Rollback is proven.
- [ ] Founder explicitly authorizes public enablement.

No paid live-eval scorecard is required solely for guest-shell changes. If the
implementation touches interpreter/runtime behavior despite this spec, it has
left the lane and must stop for a separately authorized runtime gate.

## Rollback

Rollback is configuration-first:

1. Disable new guest-session creation server-side.
2. Disable the frontend guest entry.
3. Restore the current auth-first landing behavior.
4. Keep existing temporary workspaces readable for a short bounded grace period
   or offer conversion, without accepting new guest work.
5. Continue cleanup until no anonymous workspace remains.

Rollback must not:

- delete permanent accounts;
- revoke registered sessions;
- change runtime behavior;
- expose expired guest rows;
- leave anonymous creation enabled behind a hidden frontend;
- require reverting unrelated Always-Progresses or Omnisearch code.

Each implementation block must be independently revertable or feature-disabled.

## Complexity Guardrail

After every implementation block, reassess:

- Did guest mode create a second runtime or duplicate existing API behavior?
- Did a frontend `isGuest` conditional replace server capability truth?
- Did we add a table, flag, endpoint, or abstraction without protecting
  ownership, conversion, abuse, or rollback?
- Did review expand into speculative edge cases that do not affect public user
  safety, privacy, durable state, cost, or the approved guest journey?
- Can the same result be achieved by composing existing auth, usage, chat,
  admission, feedback, and search contracts?

Remove machinery that does not justify itself.

## Canon And Documentation Work Required During Implementation

Before merge, the implementation must update:

- `docs/PRODUCT.md`:
  public entry, guest scope, onboarding, and activation;
- `docs/ARCHITECTURE.md`:
  anonymous identity, cleanup, conversion, and control-plane boundaries;
- `docs/API_CONTRACT.md`:
  guest bootstrap, `/me`, usage, conversion, feedback, public access, and error
  shapes;
- `docs/DATA_MODEL.md`:
  anonymous-compatible profiles, ownership transfer, cleanup, counters, and
  RLS;
- `.agent/designs/argus/DESIGN.md`:
  guest shell, empty state, modal, legal copy, and responsive behavior;
- active roadmap:
  actual status and dependencies, without claiming public deployment;
- release profile/runbook:
  guest/public flags, canary identity, abuse controls, cleanup, and rollback.

This design remains the decision record. Canon must describe the final shipped
contract rather than link here as a substitute.

## Implementation Handoff Contract

The future implementation agent must:

1. Start from a founder-prepared clean worktree and confirm branch, HEAD,
   cleanliness, and ancestry before edits.
2. Read the mandatory canon, active roadmap, decision memo, this spec, and the
   completed Always-Progresses design/current implementation status.
3. Audit current anonymous-auth, auth-cookie, profile-trigger, RLS, usage,
   feedback, starter-chip, Recents, Omnisearch, and feature-flag surfaces before
   planning.
4. Treat current code and any parked branch as leverage, not proof.
5. Produce a written implementation plan mapped to the four blocks before
   changing code.
6. Use TDD and keep each block revertable.
7. Avoid runtime and provider files.
8. Stop on cross-owner risk, partial-transfer risk, runtime regression, or
   contradictory canon.
9. Perform founder-visible live browser QA before claiming completion.
10. Stop before push, PR mutation, deployment, public enablement, merge, or issue
    closure unless separately authorized.

The current Codex thread remains release captain. It reviews the plan, connects
parallel dependencies, judges evidence, and owns promotion recommendations. It
does not implement the feature in the worker session.

## References

Argus:

- [`docs/PRODUCT.md`](../../PRODUCT.md)
- [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md)
- [`docs/API_CONTRACT.md`](../../API_CONTRACT.md)
- [`docs/DATA_MODEL.md`](../../DATA_MODEL.md)
- [`.agent/designs/argus/DESIGN.md`](../../../.agent/designs/argus/DESIGN.md)
- [`docs/specs/private-alpha-next-roadmap.md`](../../specs/private-alpha-next-roadmap.md)
- [`docs/specs/private-alpha-next-decision-memo.md`](../../specs/private-alpha-next-decision-memo.md)
- [`docs/superpowers/specs/2026-07-23-always-progresses-continuity-design.md`](2026-07-23-always-progresses-continuity-design.md)

External implementation references:

- [Supabase Anonymous Sign-Ins](https://supabase.com/docs/guides/auth/auth-anonymous)
- [Supabase JavaScript `signInAnonymously`](https://supabase.com/docs/reference/javascript/auth-signinanonymously)
- [Supabase JavaScript `updateUser`](https://supabase.com/docs/reference/javascript/auth-updateuser)
- [Supabase Row Level Security](https://supabase.com/docs/guides/database/postgres/row-level-security)
- [Supabase CAPTCHA protection](https://supabase.com/docs/guides/auth/auth-captcha)
- [OpenAI logged-out ChatGPT behavior](https://help.openai.com/en/articles/9125172-the-chatgpt-home-page)
- [Perplexity anonymous-session behavior](https://www.perplexity.ai/help-center/en/articles/10354769-what-is-a-thread)
