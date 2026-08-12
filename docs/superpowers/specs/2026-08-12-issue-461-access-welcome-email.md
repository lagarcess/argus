# Issue #461: Access Welcome Email

Send one transactional welcome email when an access request is promoted from
`requested` to `user`, and retain enough private delivery evidence for support
to answer whether it was sent.

Founder-locked 2026-08-12 in issue #461, building on the single-purpose access
approval sender delivered by PR #319.

## 1. Why

`docs/PRODUCT.md` says Argus is "AI-powered investing and trading idea
validation for everyone," that authentication leads directly into ordinary
chat, and that the first successful backtest is the meaningful onboarding
milestone. A person who requested access should learn that access was granted
and know the first useful thing to try without discovering it by repeatedly
attempting signup.

This is a product capability, not an Auth-template change. Supabase Auth owns
confirmation, recovery, magic-link, and identity-change mail. Argus owns this
one transactional message because it is caused by an Argus access decision.

## 2. Locked decisions

1. Use the existing `send_access_welcome_email` path. There will be one
   sender, one message category, and one promotion operation. No second mail
   client or parallel approval path may be added.
2. The only eligible transition is an active `private_alpha_allowlist` row with
   `role = 'requested'` becoming `role = 'user'`. Admin, developer, disabled,
   missing, and already-active rows do not cause a new send.
3. The protected `POST /internal/access-requests/approve` operation remains the
   application boundary. Before SMTP it durably claims a row-locked,
   revalidated active request. After provider acceptance it consumes that
   claim, records delivery, and completes promotion in one transaction.
4. The database must reject a direct `requested -> user` transition that lacks
   the welcome delivery record. Operational code and the release canary must
   use the protected approval operation instead of patching the role directly.
5. A single-purpose private claim table records the normalized recipient,
   language, fixed content version, subject, opaque claim token, and claim time
   before SMTP. A separate delivery table records the normalized recipient,
   same content identity, Resend acceptance receipt, and accepted timestamp.
   Browser roles have no privileges or policies on either table.
6. A recipient can have at most one access-welcome delivery record. A repeated
   approval that finds the existing record completes any unfinished promotion
   without sending again and returns the same successful approval shape.
7. The Resend SMTP idempotency header is derived from the opaque durable claim.
   Compatible retries inside Resend's 24-hour window reuse that claim and key.
   An unconsumed claim at or beyond 24 hours blocks SMTP and requires manual
   provider reconciliation rather than creating a new claim.
8. The email is multipart with plain-text and HTML alternatives in English and
   `es-419`. Its subject is the existing product phrase "Welcome to Argus" or
   "Bienvenido a Argus."
9. The English product line is the existing `docs/PRODUCT.md` sentence:
   "Argus is AI-powered investing and trading idea validation for everyone."
   The Spanish line is a faithful localization, not new positioning.
10. The first action is one thing: describe an investing idea in plain language
    and run the first historical test. It does not include a tour, feature list,
    sequence, or follow-up message.
11. The primary HTML button uses background `#191c1f` and
    `border-radius: 9999px`. It links to
    `${ARGUS_APP_ORIGIN}/?auth=signup`; neither the Render origin nor
    `arguschat.ai` is hardcoded.
12. The message names `support@get-argus.com`. It contains no unsubscribe link
    because the recipient requested access and this grant message is
    transactional.
13. The consent authority stops here. Product updates, tips, re-engagement,
    follow-up mail, broadcasts, campaigns, onboarding sequences, and any other
    email category are marketing-capability work with a separate legal and
    founder approval boundary.
14. No message body, email address, provider receipt, credential, or ops token
    is logged. Public and browser-facing responses remain enumeration-safe.
15. No copy in either language may contain an em dash.

## 3. Reserved / parked scope

- Broadcasts, campaigns, segments, audiences, and bulk sending: they are not
  needed to notify one person about the access decision they requested.
- A reusable template engine or generic product-mail service: a second email is
  the stop condition that would justify a later capability design.
- Marketing consent, unsubscribe, suppression, bounce, complaint, and
  preference-center machinery: no marketing email is authorized in this lane.
- A scheduler, queue, or general outbox worker: the durable claim permits only
  bounded same-claim retries inside Resend's provider window and otherwise
  fails closed for manual reconciliation.
- Supabase Auth templates: issue #459 owns those snapshots and hosted settings.
- Production-domain reconciliation: another lane owns the release contract.
- A frontend admin or support dashboard: support may use the private database
  record through existing privileged operational access.
- Pre-creating a Supabase Auth user, invite, or password-setup flow.

## 4. Contract gates

- `docs/API_CONTRACT.md`: document idempotent replay, delivery persistence, and
  the rule that the protected operation is the sole requested-user promotion
  boundary.
- `docs/DATA_MODEL.md`: add the single-purpose claim and delivery tables,
  uniqueness, private access, immutable record fields, and transition guards.
- `supabase/migrations/`: create the claim state, RLS and grants, the row-locked
  claim RPC, atomic claim-consume-record-promote RPC, and bypass guards.
- `docs/PRIVATE_LAUNCH_RUNBOOK.md`: replace direct promotion instructions with
  the protected operation and add the support readback fields.
- `.github/canary-render.sh`: stop directly patching requested rows, generate a
  unique `delivered+argus-<run>-<attempt>@resend.dev` identity, and prove the
  same operation used for real promotions.
- `docs/reports/evidence/461/`: commit secret-free exact-head proof and the two
  rendered language screenshots.
- `docs/api/openapi.yaml`: no shape change is expected because the existing
  internal route remains an exact named OpenAPI exclusion. Regenerate only if
  the compatibility gate shows drift.

## 5. Execution contract

- **PR shape:** one worker PR from `codex/issue-461-welcome-email` into
  `codex/private-alpha-next`. Internal TDD slices land as reviewable commits in
  that PR.
- **Deterministic proof:** red-green focused email/route/gateway tests; local
  Postgres migration, RLS, uniqueness, transition-guard, and concurrent/replay
  tests; API/OpenAPI compatibility; environment-contract checks; lint and the
  repository verification gates proportionate to the changed surfaces.
- **Behavioral proof:** promote the same requested row twice and show one
  accepted send plus one durable delivery record. Capture the rendered HTML in
  English and `es-419` at the exact final head.
- **External proof:** send one real message to a real inbox through the Resend
  SMTP path. Read a fresh RAW message and record `spf=pass`, `dkim=pass`,
  `dmarc=pass`, and `multipart/alternative` with a plain-text part. Evidence
  must contain no credential and should redact the recipient where practical.
- **Review proof:** required CI green, zero unresolved review threads, and one
  latest-delta Codex review with a clean verdict on the final PR head.
- **Where it stops:** a posted PR ready for founder review. The founder merges.
  This lane does not merge, deploy, change hosted configuration, or apply a
  shared migration.

## 6. Stop conditions

- If correctness requires a second message category, generic mailer, campaign
  object, marketing consent system, scheduler, queue, or reusable template
  registry, stop and report to the founder.
- If the CTA requires hardcoding `arguschat.ai` or a Render hostname, or editing
  the release integrity contract, stop and leave that work to the domain lane.
- If a direct database webhook, Supabase Edge Function, or new hosted secret is
  required, stop before creating it.
- If a safe requested-user transition cannot be enforced without changing
  admin/developer insertion or existing-user access semantics, stop and report
  the exact conflict.
- If the real send would require displaying, copying, or inspecting the Resend
  credential or SMTP password, stop and request a credential-safe execution
  path.
- If a real inbox, RAW source, or exact-head browser rendering cannot be
  obtained, do not substitute mocks for the missing external evidence.

## Sources

### Argus authority

- GitHub issue #461
- `docs/PRODUCT.md`
- `docs/ARCHITECTURE.md`
- `docs/API_CONTRACT.md`
- `docs/DATA_MODEL.md`
- `.agent/designs/argus/DESIGN.md`
- `docs/specs/argus-active-roadmap.md`
- `docs/specs/private-alpha-next-decision-memo.md`
- `docs/superpowers/specs/2026-07-30-public-alpha-readiness.md`

### External authority

- <https://resend.com/docs/send-with-smtp>
- <https://resend.com/docs/dashboard/emails/idempotency-keys>
- <https://resend.com/docs/dashboard/emails/send-test-emails>
- <https://supabase.com/docs/guides/database/postgres/row-level-security>

### Inference

- A database guard is required because the current canary patches
  `private_alpha_allowlist.role` directly and therefore bypasses the existing
  approval sender. Routing known operational writers through one protected
  transition is the smallest way to make "promotion sends welcome" structural
  instead of relying on operator memory.
