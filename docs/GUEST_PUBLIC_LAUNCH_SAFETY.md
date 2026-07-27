# Guest Public Launch Safety

Status: deferred public-exposure gate

Last reviewed: 2026-07-27

This checklist applies when Argus is being prepared for an internet-facing
Guest canary or production exposure. It is **not** a prerequisite for merging
the completed Guest experience into `codex/private-alpha-next` while that
surface remains internal.

Guest integration, Guest traffic exposure, and public permanent-account access
remain separate decisions:

- Guest code may integrate without completing this checklist.
- Internet-facing Guest traffic requires this checklist and founder approval.
- `ARGUS_PUBLIC_ACCOUNT_ACCESS_ENABLED` remains a separate policy and stays
  `false` until explicitly approved.

## Algorithm Decision

**Decision:** keep the smallest controls that directly protect the paid Guest
experience, simplify the anonymous-identity promise, keep early monitoring
manual, and automate only after real traffic establishes the need.

**Why:** Guest allowances are attached to an anonymous Supabase Auth UUID, not
to a provably unique human. Without a bot challenge and velocity controls, an
automated client can repeatedly mint new UUIDs and receive fresh allowances.
That creates a direct provider-cost, database-growth, and capacity risk when
Argus opens to the public internet.

**Disposition:**

- Keep free Cloudflare Turnstile at anonymous Guest bootstrap.
- Keep existing server-owned allowances, idempotency, RLS, expiry, cleanup,
  and global backpressure.
- Add a hard provider spending limit before public exposure.
- Keep launch monitoring manual until traffic makes automation worthwhile.
- Defer human deduplication, device fingerprinting, enterprise bot products,
  and a custom abuse platform.
- Do not make these deferred public-exposure operations a Guest integration
  merge gate.

**Smallest next step:** during promotion preparation, configure and prove the
minimum public-launch safety bundle below against the exact canary SHA.

**Stop condition:** do not expose Guest traffic if bot validation, budget
containment, server enforcement, ownership isolation, cleanup, or rollback
cannot be proven.

## What “The Same Guest” Means

Argus recognizes the same valid anonymous Supabase Auth UUID and session. It
does not claim to recognize the same human across browsers or devices.

| Situation | Expected identity behavior |
| --- | --- |
| Refresh, reload, or another tab with the valid session | Same UUID and allowances |
| Exact message or Run replay | Same UUID; no duplicate settlement or job |
| Copied conversation URL without the owning session | No access |
| All site data cleared | Original anonymous workspace becomes unrecoverable |
| New incognito profile, browser, or device | New UUID after bootstrap controls |
| Stolen valid session token | Session impersonation; treat as credential theft |

Therefore the product contract is **one Guest allowance per anonymous Argus
identity**, not one allowance per human. A strict per-human benefit would
require a verified identity before the expensive action.

## Why Turnstile Survived the Algorithm

Turnstile is the bot check at the point where a new Guest UUID is minted. Guest
allowances are the usage tickets attached to that UUID. Protecting UUID
creation is the least intrusive place to make bulk allowance resets expensive.

At the time of this review, Cloudflare documents a free Turnstile plan with up
to 20 widgets, unlimited challenges, and no requirement to proxy Argus traffic
through Cloudflare. Argus needs one production widget. Enterprise Turnstile is
not required for the initial public Guest launch.

`NEXT_PUBLIC_ARGUS_TURNSTILE_SITE_KEY` is intentionally public and identifies
the browser widget. The corresponding secret stays in the hosted Supabase Auth
configuration. A rendered widget is not protection by itself: Supabase must
validate the returned token server-side.

Turnstile should protect anonymous bootstrap. It should not be added to every
message, refinement, feedback submission, or simulation.

## Keep For Public Launch

- Real Supabase anonymous Auth UUIDs; never a mock user or synthetic email.
- Turnstile validation when creating a new anonymous session.
- Provider and Argus anonymous-bootstrap velocity limits.
- Lifetime per-UUID limits for useful messages, unique simulations, feedback,
  and temporary conversations.
- Atomic settlement and idempotency for messages, feedback, and simulations.
- Owner-scoped RLS, active-workspace expiry restrictions, and fixed seven-day
  expiry.
- Global backtest capacity and queue backpressure.
- Bounded request bodies and typed server-side capability enforcement.
- Complete-graph cleanup with converted/permanent-account protection.
- A hard provider-key spending limit for the public environment.
- Guest presentation and server kill switches with the preserved auth landing.
- Metadata-only monitoring for identity volume, usage, cost, capacity, and
  cleanup health.

## Explicitly Defer

Do not add these to the initial public Guest launch unless observed traffic
proves they are necessary:

- A claim that Argus can identify one unique human anonymously.
- Device fingerprinting or cross-device tracking.
- Cloudflare Enterprise Turnstile or Ephemeral IDs.
- A bespoke IP/ASN/reputation risk engine.
- CAPTCHA on every Guest operation.
- Phone, payment-card, or government-identity verification.
- Redis or another distributed abuse system solely for theoretical scale.
- An automated abuse dashboard or adaptive policy engine.
- Public Strategies, Collections, or other deferred product surfaces.

These may be reconsidered if real traffic defeats the minimum controls or if
Argus later promises a strict per-person benefit.

## Minimum Public-Launch Safety Bundle

### 1. Turnstile and anonymous Auth

- [ ] Create one production Turnstile widget on the free plan.
- [ ] Restrict the widget to the approved Argus production hostname.
- [ ] Configure the Turnstile secret in hosted Supabase Auth.
- [ ] Put `NEXT_PUBLIC_ARGUS_TURNSTILE_SITE_KEY` in the exact web build.
- [ ] Enable hosted Supabase anonymous Auth.
- [ ] Confirm a missing or invalid token cannot create an anonymous user.
- [ ] Confirm a used or expired token cannot be replayed.
- [ ] Confirm a valid token creates exactly one anonymous Auth UUID and one
      Guest workspace.
- [ ] Confirm the production site fails closed to the preserved auth landing
      when the public site key is absent.

### 2. Velocity and origin truth

- [ ] Record the hosted Supabase anonymous-signup rate.
- [ ] Verify which IP Supabase Auth actually rate-limits when Argus performs
      server-side anonymous bootstrap.
- [ ] Verify the trusted edge replaces or sanitizes forwarded client-IP
      headers and direct origin bypass is not possible.
- [ ] Verify the Argus short-window Guest bootstrap limit returns `429`.
- [ ] If traffic spans multiple API instances, decide from evidence whether the
      current process-local limiter must move to an edge or shared owner.

Do not add a distributed limiter merely because one might someday be useful.
Add it only if the deployed topology or measured traffic makes the process-local
boundary ineffective.

### 3. Budget and capacity fuse

- [ ] Use a dedicated provider key or public-environment key with a hard USD
      spending limit.
- [ ] Record the maximum acceptable unattended daily loss: `$________`.
- [ ] Disable or bound automatic credit top-up for that key.
- [ ] Confirm provider-limit exhaustion fails safely without inventing an
      Argus answer or settling successful usage.
- [ ] Verify one Guest cannot exceed the message, simulation, feedback, or
      conversation allowance.
- [ ] Verify backtest per-user and global capacity limits reject work before
      provider access or compute admission.

The provider cap is the final financial circuit breaker. Bot controls reduce
abuse probability; the cap bounds the maximum loss when those controls fail.

### 4. Ownership, replay, and cleanup

- [ ] Refresh and reload preserve the same UUID and counters.
- [ ] Exact message, feedback, and Run replays create no duplicate usage, job,
      Run, result, or feedback row.
- [ ] A copied conversation URL reveals nothing to another anonymous or
      registered identity.
- [ ] Expired Guests cannot read product or lifecycle rows.
- [ ] Cleanup dry run and real run select the same candidates.
- [ ] Cleanup deletes the complete expired Guest graph while preserving route
      receipts and cost evidence under their approved retention rules.
- [ ] Converted and permanent accounts remain protected.
- [ ] Schedule bounded cleanup at least daily with an accountable owner.

### 5. Small adversarial canary

Run this against the exact internet-facing canary SHA before opening traffic:

- [ ] No Turnstile token: no anonymous identity.
- [ ] Reused Turnstile token: no second identity.
- [ ] Short bootstrap burst: `429`.
- [ ] Refresh: same identity and no refreshed allowance.
- [ ] Clean incognito context: new identity only after the same challenge and
      velocity controls.
- [ ] Eleventh useful response: conversion gate before provider work.
- [ ] Second unique simulation: conversion gate before admission.
- [ ] Sixth feedback submission: conversion-required response.
- [ ] Copied conversation URL: zero cross-owner results.
- [ ] Replayed expensive action: zero duplicate charge or computation.
- [ ] Guest kill switch: new Guest entry stops and auth landing remains.

### 6. Manual first-traffic monitoring

For the initial public window, record at least daily:

- anonymous Auth users created;
- Guest workspaces created, converted, expired, and cleaned;
- accepted messages, simulations, and feedback;
- provider requests and spend;
- Turnstile failure/solve rate;
- `429` volume by protected route;
- queued and running backtest jobs;
- cleanup failures and oldest eligible expiry;
- cross-owner, duplicate-settlement, or unexpected hosted-write evidence.

Record before exposure:

- [ ] First traffic cohort or exposure size: `________`.
- [ ] Monitoring owner: `________`.
- [ ] Alert destination: `________`.
- [ ] Daily provider budget: `$________`.
- [ ] Cleanup schedule and owner: `________`.
- [ ] Founder exposure approval and exact candidate SHA: `________`.

Automate monitoring only when the manual process is repeated enough to reveal
which signals and thresholds are useful.

## Stop Conditions

Do not begin or continue public Guest exposure when any of these is true:

- Turnstile server validation is absent or unproven.
- An anonymous identity can be created without a valid challenge.
- There is no hard provider spending limit.
- Client-IP/origin behavior is unknown or trivially spoofable.
- Guest limits can be bypassed within one authenticated UUID.
- Replay creates duplicate settlement, provider access, jobs, Runs, or results.
- Cross-owner reads succeed.
- Cleanup fails, lags beyond the accepted window, or risks a converted account.
- Global queue or provider spend approaches the founder-approved boundary.
- The Guest presentation/server kill switches do not restore the auth-first
  entry and stop new anonymous bootstrap.
- Unexpected console, auth, persistence, provider, or hosted-write failures
  appear during the canary.

When a stop condition is reached, disable Guest presentation first, then stop
new Guest bootstrap server-side. Preserve existing records for safe conversion,
expiry, or bounded cleanup; do not reverse migrations or bulk-delete anonymous
users.

## Promotion Boundary

Merging the Guest implementation into the internal integration branch requires
its normal code, database, Auth, frontend, and regression evidence. It does not
require buying or configuring hosted bot products, exposing traffic, scheduling
production cleanup, or completing this checklist.

When preparing promotion for internet exposure:

1. Fill in this checklist with exact environment owners and values.
2. Configure the external controls without changing checked-in product truth.
3. Run the small adversarial canary at the exact candidate SHA.
4. Record evidence in the release manifest.
5. Obtain founder approval before exposing Guest traffic.

## Current External References

- [Cloudflare Turnstile plans](https://developers.cloudflare.com/turnstile/plans/)
- [Cloudflare Turnstile server-side validation](https://developers.cloudflare.com/turnstile/get-started/server-side-validation/)
- [Supabase CAPTCHA protection](https://supabase.com/docs/guides/auth/auth-captcha)
- [Supabase anonymous sign-ins](https://supabase.com/docs/guides/auth/auth-anonymous)
- [Supabase Auth rate limits](https://supabase.com/docs/guides/auth/rate-limits)
- [OpenRouter API-key spending limits](https://openrouter.ai/docs/api/api-reference/api-keys/create-keys)

Reverify external pricing, limits, and configuration instructions during
promotion; they can change independently of this repository.
