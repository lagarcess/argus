# Argus Decision Log

This log records locked product decisions and links to their detailed owner.
The September 26 entries record direct founder approval in the MVEE design
conversation and the subsequent request to publish a docs-only reconciliation.
See [documentation authority](../DOCUMENTATION_AUTHORITY.md) for scope and
supersession rules. These decisions do not assert implementation completion.

## Locked

| Date | Decision | Locked by |
| --- | --- | --- |
| 2026-09-14 | Sharing is shareable by default; refuse only what is private. The privacy boundary is owner selection of turns, an exact preview, and no Argus ids or account enrichment. Earlier refusals for memory use, degraded answers, missing sources, unlisted URLs, credential-shape and value-marker scanning, and length caps were removed in [#632](https://github.com/lagarcess/argus/pull/632) (commit `6054acba`, merge `c8e05b4f`). That reversed the 2026-09-09 filter built in [#574](https://github.com/lagarcess/argus/pull/574) after [#604](https://github.com/lagarcess/argus/issues/604), whose promotion walk found zero selectable answers. A Codex P1 review comment on #632 asking to restore value-marker scanning was declined because it would re-block public company names and URLs. See [conversation-sharing.md](conversation-sharing.md). | Lucas |
| 2026-09-14 | Receiver fork: a person who opens a shared `/r/<id>` link and sends a follow-up gets the frozen shared turns copied into their own new chat. The copy carries no owner note, memory, or profile. Decision commit `675c1f94` reversed the earlier no-fork stance. Built in [#643](https://github.com/lagarcess/argus/pull/643), merged at `0044d79a` on 2026-09-15. See [conversation-sharing.md](conversation-sharing.md). | Lucas |
| 2026-09-24 | The first user is people living in the Dominican Republic, not the diaspora. | Lucas |
| 2026-09-24 | Argus keeps all its existing grounded chat and calculation capability. The pivot adds features around it so Argus isn't just an AI chat, building toward an ecosystem. | Lucas |
| 2026-09-26 | Approve one connected minimum viable ecosystem carrying forward existing Argus capabilities. The earlier one-product-versus-two question is resolved for this experience. Detailed owner: [MVEE sections 1–3 and 7](argus-minimum-viable-ecosystem-experience.md). | Lucas |
| 2026-09-26 | Lock the initial audience and near-term financial emphasis, shared planning picture, and low-effort recording/return loop. Detailed owner: [MVEE section 1.1](argus-minimum-viable-ecosystem-experience.md#11-locked-audience-and-experience-emphasis). | Lucas |
| 2026-09-26 | Approve ingestion experience and its confirmation, correction, provenance, and freshness boundaries; experimental access paths are not provider commitments. Detailed owner: [MVEE sections 4–5](argus-minimum-viable-ecosystem-experience.md#4-information-ingestion-one-destination-several-entry-methods). | Lucas |
| 2026-09-26 | Preserve Argus visual identity and existing chat detail; approve ecosystem navigation and native iOS/Android plus web intent. Detailed owner: [MVEE section 2](argus-minimum-viable-ecosystem-experience.md#2-product-character-and-platforms). | Lucas |
| 2026-09-26 | Include partner invitations and personal/household views in the minimum ecosystem, superseding the earlier deferral. Detailed owner: [MVEE section 12](argus-minimum-viable-ecosystem-experience.md#12-household-collaboration-approved-minimum-capacity). | Lucas |
| 2026-09-26 | Publish approved experience and reconcile older document pointers in a docs-only PR; defer new technical design and implementation sequencing. Owner: [documentation authority](../DOCUMENTATION_AUTHORITY.md). | Lucas |
| 2026-09-26 | Carry production behavior and gates forward unless explicitly changed; distinguish current availability from approved future experience. Owner: [PRODUCT.md availability and transitions](../PRODUCT.md#current-production-availability-and-planned-changes). | Lucas |
| 2026-09-26 | Lock platform-native mobile interfaces and retain the existing web/PWA stack, sharing one Argus backend and canonical financial truth. Accept separate interface maintenance with coordinated agents and platform-specific verification. Detailed stack owner: [ARCHITECTURE.md platform decision](../ARCHITECTURE.md#approved-platform-direction). Client contracts and rollout remain to be defined. | Lucas |
| 2026-09-27 | Approve quick type-specific account setup, optional nicknames and unknown balances, and optional property, vehicle and other asset tracking. Lock the estimate, ownership and linked-debt boundaries; listing-based valuation remains a future candidate capability. Detailed owner: [MVEE quick setup and assets](argus-minimum-viable-ecosystem-experience.md#quick-account-setup-and-optional-assets). | Lucas |
| 2026-09-27 | Accept the simplified account-entry sketch and consistent money-entry treatment as the current design baseline; stop further visual refinement for this pass. Experience owner: [MVEE quick setup](argus-minimum-viable-ecosystem-experience.md#quick-account-setup-and-optional-assets). Interaction owner: [DESIGN money entry](../../.agent/designs/argus/DESIGN.md#money-entry-in-the-ecosystem-sketch). Device verification and production contracts remain separate work. | Lucas |
| 2026-09-27 | Lock distinct account setup, new activity and balance-check actions; require an explicit discrepancy review and traceable adjustment without invented income/spending. Reuse the existing destructive confirmation for removal. Experience owner: [MVEE balance checks](argus-minimum-viable-ecosystem-experience.md#account-activity-and-balance-checks); technical follow-up: [backend handoff](argus-account-balance-reconciliation-handoff.md). | Lucas |
| 2026-09-27 | Lock simplified populated Home, bounded account previews, and inherited Recents/Omnisearch growing-list behavior. Preserve currency-separated net worth; combined conversion remains undefined. Owners: [MVEE Home summary](argus-minimum-viable-ecosystem-experience.md#populated-home-summary-and-list-boundary) and [DESIGN growing lists](../../.agent/designs/argus/DESIGN.md#growing-lists-across-ecosystem-surfaces). | Lucas |
| 2026-09-27 | Lock copy-link household invitations, user-shared WhatsApp links, do-blitz as the short-link integration direction, and Resend email delivery; no incentives. Detailed owner: [MVEE invitation delivery](argus-minimum-viable-ecosystem-experience.md#invitation-delivery-founder-locked-september-27-2026). Contact discovery and implementation contracts are not implied. Narrowed on 2026-10-02: do-blitz no longer handles invite links; see [October 2 lane locks](#october-2-2026-cuadrao-lane-locks). | Lucas |
| 2026-09-28, clarified 2026-09-29 | Revenue, pricing, paywalls and billing remain deferred; existing usage and cost safeguards remain. The current user-trial boundary permits founder dogfooding and physical-phone demonstrations. Detailed owner: [documentation authority — founder deferral](../DOCUMENTATION_AUTHORITY.md#founder-deferral). | Lucas |
| 2026-09-29 | The [private iPhone delivery and execution lock](#september-29-2026-private-iphone-delivery-and-execution-lock) owns the current delivery decision and supersedes the batch instructions below. | Lucas |
| 2026-10-01 | Lock Household permission policy: creator administers invitations/membership and may transfer administration or close before departure; members see the member list and may leave; shared accounts start view-only with editing only via explicit grant; edit grants do not confer ownership, membership administration or resharing; leave/removal revokes membership and that member's account grants while owners retain records/history; invitations are revocable, single-use, seven-day links with safe same-recipient acceptance retries; create ≠ invite ≠ share account and acceptance is membership only. MVEE consent and financial-meaning boundaries remain. Owners: [execution board Household lane](argus-execution-board.md#connected-spaces-and-household-lane), [MVEE section 12](argus-minimum-viable-ecosystem-experience.md#12-household-collaboration-approved-minimum-capacity), [lane contract](lanes/household-permission-policy.md). Narrowed on 2026-10-02: rule 5's departure behavior, and rule 1's admin handoff when the admin deletes their account, now follow the [October 2 lane locks](#october-2-2026-cuadrao-lane-locks). | Lucas (Project orchestrator recorded) |
| 2026-10-02 | Lock the invitation (beta versus household invites, 10 beta invites per user, and a founder group link as the one exception to single-use codes), TestFlight beta-gate, Home comparison, Updates, plan-export, account-move and account-deletion-in-a-household rules for the five Cuadrao lanes, including what happens to a deleted person's part in shared plans (8:53 PM CT). Detailed record: [October 2 lane locks](#october-2-2026-cuadrao-lane-locks). | Lucas |
| 2026-10-04 | Lock the Cuadrao launch shape: consumer iPhone app with personal and household only, a short invite-only TestFlight then a public launch; Cuadrao for Business as a full web service with a thin in-app business space for the first business testers only; cuadrao.ai promoting the whole suite with waitlists; Resend, Render and Supabase kept. Also partner first for live e-invoicing, Plaid kept, market-data providers parked for the pilot, Dominicans in the US added as a consumer segment, and no currency conversion or blended totals. Detailed record: [October 4 Cuadrao launch shape](#october-4-2026-cuadrao-launch-shape). | Lucas |

## Superseded coordination instructions (historical only)

These entries record prior assignments, not active instructions. Their replacement
is the [September 29 delivery lock](#september-29-2026-private-iphone-delivery-and-execution-lock).

| Date | Historical decision | Disposition |
| --- | --- | --- |
| 2026-09-28 | The Project delivery lead and VM serial captain were assigned the three-interface account journey, with named exclusive writers for the surfaces and research/proof PRs. Source: [PR #727 handoff](https://github.com/lagarcess/argus/pull/727#issuecomment-5878051744). | Superseded by the September 29 delivery lock; this row assigns no current owners or work. |
| 2026-09-28 | User trials were parked while core journeys became functional. | Clarified by the [current founder deferral](../DOCUMENTATION_AUTHORITY.md#founder-deferral); this historical pause does not block founder dogfooding or physical-phone demonstrations. |
| 2026-09-28 | [#725](https://github.com/lagarcess/argus/pull/725) landing was held for a narrowed research / selected-file-import scope. | Superseded by the September 29 delivery lock; the old hold is not a pending landing assignment. |

## Wave 1 package-era constraints (not current locks)

These are dated shipping assumptions from the Wave 1 package. They do not
override later MVEE or PRODUCT owners.

| Date | Constraint | Note |
| --- | --- | --- |
| 2026-09-25 | Three-step setup checklist: get a first answer; save a card or create a goal (sign-in at that step); then turn on reminders. | Wave 1 package-era onboarding sketch. [MVEE](argus-minimum-viable-ecosystem-experience.md) leaves account onboarding and exact guest-to-account conversion undecided; [PRODUCT.md](../PRODUCT.md#current-production-availability-and-planned-changes) owns current availability. Do not invent conversion timing from this row. |

## Open (not locked)

Voice and chart direction was subsequently locked on September 28; see the
dated entry below. Sharing growth concepts remain recommendations, not an
approved expansion of the frozen mobile baseline.

The canonical list is [MVEE section 9](argus-minimum-viable-ecosystem-experience.md#9-decisions-deliberately-left-open).
The authority map identifies technical areas still requiring contracts before
implementation. Earlier documents' open-question lists are dated history;
do not treat them as reopening the decisions above.

## September 28, 2026 — UI completion checkpoint

The founder requested closing the Home, connected-plan, household contributor/
permission and financial-recovery experience gaps, including refunds and account
adjustments. The MVEE now owns those behaviors and the private Business-space
boundary. DESIGN owns quiet space navigation versus underlined section tabs.
The account reconciliation handoff records the unresolved posting, matching and
recovery contracts. This freezes a disposable UI reference; it does not authorize
backend implementation, change production contracts or establish release readiness.

## September 28, 2026 — account space reassignment

The founder approved the bounded Manage account journey: move between private
spaces, share separately with Household, preserve financial history, and review
linked records before confirmation. Detailed behavior is owned by the MVEE's
Reassigning accounts between spaces section. Production atomicity and permissions
remain contract work; this approval implements only the disposable UI sketch.


## September 28, 2026 — complete mobile design lock

Founder: “do a full sweep and lock the design for mobile, including your html
reports of full ecosystem … lock it in.” The local template and all six current
reports are frozen as one dated reference. The MVEE now records the final
Settings ownership and single Temporary-chat experience; DESIGN owns its stable
header and composer transitions. The [handoff](../reports/mobile-design-lock-2026-09-28.md)
links the source/evidence archive, checksum and implementation boundary.
This is design acceptance, not release readiness or an assignment to implement
all visible provider-dependent concepts. No backend, API, model prompt, deployment
or production data was changed.

## September 28, 2026 — voice and chart direction

Founder: “Yes, lock it,” approving full voice with xAI and the native chart
shortlist. Detailed technical owner: [architecture direction](../ARCHITECTURE.md#voice-and-chart-direction).
The [MVEE voice experience](argus-minimum-viable-ecosystem-experience.md#43-speak-to-argus)
now explicitly includes full spoken conversation. Vico remains subject to a
representative prototype, and integrated speech-to-speech orchestration remains
subject to preserving Argus's single runtime owner. This does not modify the
frozen HTML archive or authorize provider calls, implementation or deployment.

The founder also requested applying *Contagious* to ecosystem sharing. The
[research note](../research/2026-09-28-ecosystem-sharing.md) records source-backed
principles and a proposed bounded first experience. Specific growth surfaces,
metrics and mechanics in that note are not locked product requirements.

## September 28, 2026 — publication and recording reconciliation

The founder authorized pushing this branch and opening its publication PR, with
continuation prompts to be handed back for the other lanes. The MVEE clarifies
the already-approved confirmed-record exception to historical Decision 8 and
the final template's archive behavior: archived account balances and obligations
remain in the financial picture. Unconfirmed figures in chat retain their
existing conversation policy; no personalization-memory expansion is approved.
The [recording decision response](lanes/financial-recording-decision-response.md)
separates settled experience from remaining recommendations.

The founder parked public growth sharing until there is evidence of what users
want to share. Household invitations and file ingestion remain in scope.

## September 28, 2026 — guest access and ecosystem runtime sequence

The founder locked [guest access](argus-minimum-viable-ecosystem-experience.md#guest-access-and-registration):
guests can see the app and use existing finance chat within current limits;
other ecosystem features require registration across native and web interfaces.
This settles the recording lane's guest-persistence question without changing
existing guest-chat quotas or authorizing a production auth change here.

The founder also confirmed [agentic ecosystem direction and sequence](argus-minimum-viable-ecosystem-experience.md#agentic-ecosystem-direction-and-sequence).
Manual UI and future conversational actions must share the same canonical
operations. The ecosystem runtime lane follows definition of the core workflows
and UI. This is not permission to replace the existing runtime, change its
model-facing instructions, or remove research and historical simulations now.

## September 29, 2026: private iPhone delivery and execution lock

The founder requested publication of the complete discussion in the MVEE and a
single execution manifest. The [MVEE delivery lock](argus-minimum-viable-ecosystem-experience.md#12-private-iphone-delivery-the-immediate-finish-line)
owns the real physical-iPhone/internet outcome, full scope, agent-first direction
with explicit runtime deferral, tester feedback, current Supabase-project/plan
reuse, modular backend and web-remake freeze. These are founder decisions from
this delivery conversation, not claims that the capabilities are implemented.

The [execution manifest](argus-execution-board.md) is the single delivery map,
with dependencies, required ownership, acceptance, evidence and restart rules.
[Documentation authority](../DOCUMENTATION_AUTHORITY.md) points agents to it and
marks the earlier three-interface batch historical. This entry supersedes the
September 28 active-batch and #725 landing-hold instructions: all implementation
is stopped, #723/#724/#725/#726 are closed unmerged, and no prior coordination
instruction restarts them. The founder authorized this documentation PR only.
The manifest's proposed work order is the delivery lead's plan, not an already
accepted technical contract or a new implementation/deployment grant.

## October 2, 2026: Cuadrao lane locks

The founder approved these in the Docs Alignment room while scoping the five
lanes (Home data, Household invitations, Updates, Search, Spaces). Product
Lead (Iris) drafted the recommendations and the founder said yes; Head of
Engineering (Yelena) recorded them for the lane handoff. Two details were
approved by the founder's reaction rather than a written yes; each is marked
below with its time. These are decisions, not claims that anything is built.
Delivery order and review steps are the Head of Engineering's plan in the lane
handoff, not founder locks. The lane handoff links here instead of restating
them.

### Invitations

- An invitation produces a share link, an invite code and a QR code.
  Household email invitations are not in this pass. A Resend adapter
  already exists, sending from the get-argus.com address; what is missing is a
  Cuadrao sending domain.
- The invite link is a universal link on cuadrao.ai that opens the app. The
  current `argus-household://` scheme and the design branch's placeholder
  domain are not the target.
- do-blitz is replaced for invites. Invite links go straight to cuadrao.ai,
  because a redirect through a shortener usually opens Safari instead of the
  app. do-blitz stays an option for marketing and ad links later. This narrows
  the September 27 invitation-delivery lock; its Resend and WhatsApp parts are
  unchanged. (Founder approval by reaction, 5:58 PM CT.)
- Each code works once, except the founder's group link (see the TestFlight
  beta gate below), and records who sent it, so the who-invited-whom
  record exists. This builds on the October 1 single-use, seven-day rule.
- When an account is deleted, an anonymous record that an invite was sent and
  accepted is kept, with no name or identifier. Deleting an account still
  removes the person. (Iris's detail, approved by the founder's reaction at
  5:33 PM CT.)
- The inviter gets an "invitation accepted" entry in Updates. There is no
  "invitation received" entry, because the invitee already has the link or
  code and an invitation has no named recipient before acceptance.

### TestFlight beta gate

This gate and the three network numbers are the founder's October 2 lift of
the [founder deferral](../DOCUMENTATION_AUTHORITY.md#founder-deferral) (no broad
user trials, no new growth analytics), scoped to invites only.

- The cuadrao.ai landing page collects a waitlist, and the founder rolls access
  out personally. He onboards the first users himself.
- There are two kinds of invitation. Any user can send a beta invite; each
  user has 10 for TestFlight, and the founder can add more. Only the household
  admin sends household invites. These don't use any of the 10, and they also
  let the invitee into the beta. This keeps October 1 rule 1: only the
  household admin administers household invitations. (Founder lock, 8:04 PM
  CT; the split is Iris's proposal, with the quota raised from 3 to 10.)
- The founder, and only the founder, can create a group link that many people
  can use. He sets a cap (for example 50) and an expiry date. Redemption is
  atomic, so a burst of taps can't go past the cap. Once the cap is reached,
  anyone who taps the link lands on the cuadrao.ai waitlist and is told so on
  screen. Each group link is its own source in the network numbers, and the
  who-invited-whom record shows the link as the inviter. This is an exception
  to the single-use rule. The group link is beta-only: redeeming it never
  grants household membership. The link can be forwarded beyond the chat it was
  posted in; the cap and the expiry date limit that spread. (Iris's proposal,
  Yelena's build note, founder lock at 8:06 PM CT.)
- A TestFlight public link only installs the app. The in-app invite code is the
  real gate. Anyone without a code is sent to the cuadrao.ai waitlist.
- Three network numbers are tracked from the start: invites sent per user, the
  share of invites accepted, and the share of invitees who go on to invite
  someone. Household invites are counted separately from beta invites.
- Apple's first beta review must be scheduled before the first outside
  distribution.

### Sign-in for TestFlight

- Sign-in for TestFlight is Apple, Google and email. Email works with any
  address and has an in-app confirmation step. The founder added Google because
  people will likely want to sign up with their Gmail address. (Founder
  decision, 10:06 to 10:07 PM CT.)
- Engineering (Yelena) builds Apple and Google sign-in behind default-off flags.
  They stay off until the founder supplies the keys: for Apple, Sign in with
  Apple enabled on the app ID, a Services ID and a .p8 key; for Google, a
  sign-in client.
- Because the app offers Sign in with Apple, deleting an account also revokes
  the person's Apple tokens. Deletion also revokes every Google token Argus
  holds, Gmail source tokens included (Yelena's call, October 2). Native Google
  sign-in exchanges an ID token and stores no Google refresh token, so there is
  nothing to revoke for it. The steps are in the
  [lane handoff](lanes/mvee-five-lane-handoff.md#lane-6-account-deletion).

### Home comparisons

- A month with confirmed complete coverage and no spending is a known zero. It
  shows 0, and the comparison still shows. When the earlier period is zero, the
  difference is shown as an amount (for example "RD$4,500 more than last
  month"), not a percent.
- "Sin datos" (no data) shows only when coverage for the period is missing.
- (Founder clarification, 10:18 PM CT. This restores the wording of design
  commit `fc7650ea`. It replaces the reading in #787 that tied no data to a
  period with no records and called a zero a period whose records add up to
  zero.)

### Updates

- Everything Cuadrao notifies about lands in Updates. Home's Próximamente
  section keeps showing upcoming bills for the Space in focus.
- A bill gets an Updates entry 3 days before its due date and again on the day.
- During TestFlight, Updates uses the in-app inbox plus push for people who
  turn push on. Push never includes amounts; amounts appear only inside the
  app. Updates are not sent by email yet.

### Joint plans

- Exporting joint plans is deferred until after TestFlight. The read-only
  archive from [#773](https://github.com/lagarcess/argus/pull/773) stays until
  its owner deletes it. If the owner deletes their account, the archive passes
  to the plan's longest-standing participant instead (see the section on
  deleting an account below).

### Leaving a household and moving accounts

- When a member leaves, the accounts they own go with them and the household
  loses access right away. Members who had a grant at the cut-off keep that
  account's history up to the move date, greyed out and read-only, with the
  state at the move recorded. Shared plans that relied on it are archived
  read-only for the remaining members. This narrows October 1 rule 5 (leave or
  removal revokes the member's grants and owners retain history).
- Moving an account between Spaces never rewrites past balances or
  settlements. A move is recorded as an event, replaying it changes nothing, and
  access rules block creating, editing or deleting the locked history. Home is
  recomputed from history.

### Deleting an account in a household

- When an owner deletes their account, the household's locked copy of that
  owner's account history is deleted too, and the other members see a short
  note that it was removed. This is the one exception to members keeping
  history after a departure (see the section on leaving a household above).
- When the household admin deletes their account, the admin role passes
  automatically to the longest-standing remaining member. If no one is left,
  the household closes. This narrows October 1 rule 1, where the admin
  transfers administration or closes the household before leaving: account
  deletion does not wait for a manual transfer.
- Both are founder locks (8:04 PM CT) of Iris's proposals.
- Deleting any account also clears that person's email from saved feedback
  and deletes the person in PostHog by distinct id, including their events.
  (Yelena's recommendation, founder lock at 8:04 PM CT. The PostHog wording
  was clarified Oct 2 via #782.)
- When a person deletes their account, in plans other people own their
  amounts keep their values and dates under a nameless placeholder:
  "Exmiembro" in Spanish and "Former member" in English, numbered
  ("Exmiembro 1", "Exmiembro 2") when more than one person leaves a plan. The
  placeholder has no user id, name, avatar or email. Their receipts, photos
  and free-text notes are deleted; amount, date and category stay. Open
  balances with them are frozen: not marked settled and not forgiven. They
  come out of the active totals and show as a closed line, and a member can
  later mark it settled, which is recorded as a new event. Their future
  responsibilities go back to the plan's owner, who gets an Update to reassign
  or re-split them. Past legs stay as they are. Shared plans they owned, and
  the #773 archive, pass to the plan's longest-standing participant; if nobody
  else is in the plan, it is deleted. The plan name stays. The confirmation,
  member-note and new-owner wording in Spanish and English is Iris's, and lives
  in the [lane handoff copy](lanes/mvee-five-lane-handoff.md#copy-founder-locked-iriss-wording).
  This replaces the Head of Engineering's draft to anonymise or delete those
  rows. (Iris's proposal, founder lock at 8:53 PM CT.)
- Implementation note, not a new decision: "no user id" above is implemented
  as "no id tied to the person". The foreign keys require a real `auth.users`
  row, so account deletion creates one nameless, banned placeholder user per
  household or standalone shared group and departed person (Yelena's call,
  October 2). A household is one scope: every plan and membership-keyed row in
  it re-keys to that household's single placeholder, because its members
  already knew it was one person. Every shared plan sits in a household,
  because `household_plan_bindings.household_id` is `not null`. No placeholder
  spans more than one household or group. The "Exmiembro" numbering stays per
  plan, because it is only a label. The steps are in the
  [lane handoff](lanes/mvee-five-lane-handoff.md#lane-6-account-deletion).
- A shared debt plan whose owner deletes their account is not handed over,
  because nobody can own another person's debt account. It is archived
  read-only under the placeholder of the plan's household. Contributions keep
  their values and dates under "Exmiembro" / "Former member", and open
  balances show as a closed line. Participants see Iris's banner on the
  archived plan and get the usual member note. This is the Head of
  Engineering's (Yelena's) call on October 2, not a founder lock. It follows
  decision 17 and Iris's frozen-balance rule. Yelena confirmed it as the one
  exception to the plan handover in the bullet above.

### Outside services

- The universal link and push are not built yet. Each will be built behind a
  default-off flag with a fake and stay off until the founder connects the real
  service, so turning one on later is configuration only. Household email
  invitations and update email are not in this pass, so nothing is built for
  email. The domain, keys and links the founder will supply are not recorded
  here.

## October 4, 2026: Cuadrao launch shape

The founder set these in the room on October 4. Head of Engineering (Yelena)
recorded the launch shape at 12:30 PM CT and the fiscal route correction at
12:39 PM CT in her engineering notes. Product Lead (Iris) relayed the
connector and segment calls at about 12:44 PM CT and the currency rule at
about 12:45 PM CT. The docs seat (Maya)
recorded them here with the [Cuadrao master plan](cuadrao-master-plan.md),
which is a planning roadmap, not a lock. These are decisions, not claims that
anything is built. Everything else in the master plan, including the space
model, the roles matrix and founder calls F1 to F5, stays open until locked.
The source documents are recorded as the
[go to market vision](../research/2026-10-04-cuadrao-gtm-vision-source.md) and
the [product and business architecture](../research/2026-10-04-cuadrao-product-business-architecture-source.md).

### Launch shape

- The consumer iPhone app launches with personal and household spaces only.
  It goes to a short invite-only TestFlight under the October 2 invite rules,
  then to a public launch with fast iteration.
- Cuadrao for Business is a full service on the web. The business space in
  the iPhone app stays thin: capture, quick approvals and where money stands.
  It goes only to the first business testers on TestFlight, and public
  consumers never see it. How to keep it out of the public build is the Head
  of Engineering's call, not a founder lock.
- cuadrao.ai promotes the whole suite and carries the waitlists.
- The stack stays on Resend, Render and Supabase.

### Fiscal route

- Partner first. Connecting to a DGII-certified provider is the route to live
  e-invoicing through Cuadrao. Cuadrao's own DGII backend is the parallel
  track while the founder handles the DGII paperwork. The pilot starts by
  tracking the invoices owners already issue, then issues through Cuadrao
  once the provider connection is live. The founder chooses the provider; no
  provider is chosen yet.

### Connectors, data providers and segments

- Plaid is kept. The Plaid sandbox with generated test data is how financial
  data is stress-tested. Real Plaid serves Dominicans in the US and
  Dominicans with accounts abroad, and manual entry stays available for
  anything Plaid doesn't cover. Production Plaid access goes through Plaid's
  own review on the founder's partner track.
- Dominicans in the US is a named consumer segment. It is added next to the
  September 24 lock that the first user is people living in the Dominican
  Republic; that lock is not replaced.
- Market-data providers (Alpaca, Kraken, BCRD and the others) are parked for
  the pilot, not deleted. BCRD is fully parked. Their keys come out of the
  live setup and the code stays. Perplexity covers general finance questions
  in chat.
- The Gmail import is still an open decision.

### Currency

Cuadrao never converts currencies, because converting would blur the numbers
and make Cuadrao responsible for their accuracy. This decides the September 27
note that combined conversion "remains undefined". The founder's design lane
owns the final screens.

- Every account stays in its own currency. Cuadrao never shows a blended
  total.
- Home shows one total per currency on separate lines, for example
  "RD$ 85,400" and "US$ 1,250". The person's primary currency comes first;
  they set it at onboarding and can change it later.
- Charts and comparisons show one currency at a time, with a switcher when
  the person holds more than one currency.
- Plans keep a fixed currency. When an account in another currency pays
  toward a plan, the person records both amounts exactly as their bank
  charged them. The rate comes from their real transaction, never from
  Cuadrao.
