# Follow Up On Unfinished Work

Founder-locked 2026-08-09. Spec only. Nothing here is built.

Argus brings a user back by finishing a turn they started and abandoned.

> You compared Costco, Walmart and Target three weeks ago and never tested it.
> Costco reported earnings since. Want to run it now?

Related specs: [`2026-08-07-research-to-test-rail.md`](2026-08-07-research-to-test-rail.md),
[`2026-08-07-compare-your-own-work.md`](2026-08-07-compare-your-own-work.md),
[`2026-08-06-personalization-memory-recall-loop.md`](2026-08-06-personalization-memory-recall-loop.md).
Related issues: #401, #411, #412, #409.

## 0. This cannot be built yet, and that is the most important thing here

The corpus is empty. Not small. Empty.

`research_memory_block()` in
[`research_grounded.py:953`](../../../src/argus/agent_runtime/research_grounded.py:953)
only fires on a research turn. Research is gated by `research_rail_enabled()`
([`conversations.py:830`](../../../src/argus/api/routers/conversations.py:830)),
and `ARGUS_RESEARCH_RAIL_ENABLED` is `false` in `render.yaml`,
`.github/argus-env.sh`, and the release profile. Zero open threads exist in
production. They begin accumulating the day that flag flips, that flip is
gated on #411 and #412 per rail spec section 13b, and then real time has to
pass before any thread is old enough to be worth following up on.

A builder who starts before the conditions below are true is guessing what "a
fact specific to that thing changed" means against zero real examples. That
guess is the whole feature. Section 5 is the part that decides whether an email
is worth sending, and it cannot be designed from an empty table.

### Preconditions, checkable

1. `ARGUS_RESEARCH_RAIL_ENABLED` is `true` in production.
2. #411 (routing provenance) and #412 (stranded research jobs) are closed.
3. Real open threads exist in volume. The floor:
   - at least 50 distinct open threads,
   - across at least 10 distinct registered accounts,
   - at least 15 of them older than 21 days,
   - at least 5 where a qualifying event has actually occurred since the thread
     opened.

   The numbers are a calibration floor, not a success metric. Fifty threads
   across ten accounts is enough variety to see what real unfinished work looks
   like rather than what the founder's own testing looks like. The aged and
   qualified subsets matter more than the total: the feature is entirely about
   time passing and facts changing, so a corpus of fresh threads with no events
   proves nothing.
4. The email capability decision in section 13 has been made by the founder.

If precondition 1 later reverses and the rail is turned off, the follow-up job
stops entirely. Qualification depends on the rail's provider layer, and a
follow-up that cannot check whether anything changed is a reminder, which this
spec does not build.

## 1. What it is

A user asks about something, gets a grounded answer, and does not test it. Weeks
later a fact specific to that thing changes. Argus tells them, once, and offers
the test they never ran.

That is the entire feature. It is not a digest, not an alert, not a monitor, and
not a scheduler.

## 2. Amendment to rail spec section 11: pull on return is replaced

**This amendment is binding and supersedes rail spec section 11's hard boundary.
It is written as its own numbered amendment, in the shape of section 11b,
because a rule this load-bearing must not be revised inside a paragraph
somewhere else.**

Rail spec section 11 says:

> **Hard boundary: pull on return, never push.** Argus notices what changed when
> the user comes back. It does not monitor in the background, and it does not
> notify.

That boundary is retired. The replacement:

> **Argus may follow up only on something the user started and left open, and
> only when a fact specific to that thing changed. If Argus has nothing of yours
> to point at, it sends nothing.**

### Why the replacement holds

The old rule was protecting the fact that the user initiates and Argus responds.
Every other rule in the product descends from that: no menu, no capability list,
no auto-run, no urgency. An unprompted email is genuinely the first time Argus
initiates anything, and that is a real line.

It is safe to cross here because **the initiation is the user's own, deferred**.
They asked about Costco and did not finish. Argus finishing that sentence later
is not Argus picking a subject, it is Argus completing a turn the user opened.

An alerting product requires Argus to choose the topic. Under this rule it
structurally cannot, because the subject is always a record the user created.
"PLTR is down 8 percent" is dead by construction, not by policy. There is no
configuration of this feature that produces it, because no PLTR thread exists in
that user's history for it to attach to.

### What does not move

**Argus never acts without you** is untouched and untouchable. Nothing here
runs, confirms, or executes anything. Every follow-up ends at the ordinary
confirmation card with the ordinary explicit confirmation. A follow-up is an
invitation to a turn, never a turn.

## 3. What it reads: canonical records, and it works with memory off

**This is a reader over the user's own canonical records. It is not a memory
feature and it does not require memory.**

The precedent is exact, from compare-your-own-work section 3:

> **It works with memory off**, because reading your own runs is the product,
> not a memory feature, and requiring consent for it would be absurd.

Reading your own unfinished work is the same thing. A user who researched Costco
and never tested it does not need to consent to Argus knowing that. It is in
their own transcript and their own run history.

Sources, all owner-scoped and all already written:

| Record | What it supplies |
| --- | --- |
| `messages.metadata["research"]["memory"]` | subjects, comparison set, peer suggestions, open thread |
| `backtest_runs` | whether a test happened, by owner and `symbols` |
| `decision_notes` | `revisit_later` as an explicit open state |
| `ideas`, `idea_versions` | lineage, so a follow-up points at the right version |
| `evidence_artifacts` | the frozen numbers a follow-up may quote |

The symbol join is already indexed. `idx_backtest_runs_owner_symbol_{1..5}_prefix`
are owner-first partial expression indexes over completed runs, described in
`DATA_MODEL.md` section 12.1. No new index is assumed; confirm before building.

### Memory's actual role

Memory is a **pre-wired optional sharpener for ranking**, inert when disabled,
never the mechanism and never a second data source. It answers one question and
only one: when three threads qualify in the same week, which one does this user
care about most. With memory off, ranking falls back to the structured signals in
section 4.

**Do not grow `MemoryCategory`.** Founder-locked. The enum in
[`contracts.py:27`](../../../src/argus/memory/contracts.py:27) stays at its four
values. Research subjects, open threads, and comparison sets are not memory
records and must not become them. Requiring a per-thread confirmation before
Argus may follow up would put a consent step in front of a retention feature,
which is backwards.

### The naming defect that caused this confusion, and must not cause it again

`research_memory_block()` writes a sidecar field literally named `"memory"` into
`messages.metadata["research"]`. It is not a memory record, it never passes
through `MemoryService`, it carries no consent receipt, and it is written
whether or not memory is enabled.

That name has already misled one reader into specifying this pillar as a memory
consumer. It will mislead the next one.

**Decision: rename the sidecar key and the function while the corpus is empty.**
`memory` becomes `follow_up`, `research_memory_block()` becomes
`research_follow_up_block()`, and `RESEARCH_SIDECAR_KEYS` updates with it. This
is a documented contract surface, so `docs/API_CONTRACT.md` and the OpenAPI
artifact move with it.

**This is dispatched, not owed by this pillar.** It is being built on
`claude/research-memory-follow-up-rename-43ec89`.

It will never be cheaper than now: production has zero rows carrying the key,
because the flag has never been on. Readers should accept the legacy `memory`
key for non-production rows written during development, and that tolerance
should be removed rather than kept forever. If the rename does not happen before
the flag flips, it does not happen at all, and the doc comment must then say in
one line that this field is not a memory record.

## 4. Eligibility: what counts as unfinished work

Eligible, all three shapes:

1. **A research thread with subjects and no test.** The sidecar carried one or
   more resolved subjects, and no completed `backtest_runs` row owned by that
   user intersects those symbols after the thread's timestamp.
2. **A `decision_notes` row at `revisit_later`.** The user said so themselves.
   This is the strongest signal in the product and it needs no inference.
3. **A confirmed comparison set that was never run.** A built basket the user
   assembled and abandoned.

### What "never tested" means, decided

A thread is closed by a **completed** `backtest_runs` row, owned by the same
user, whose `symbols` intersect the thread's subjects, created after the thread.
Not a confirmation card that was opened. Not a queued or running job. Not a
failed run.

The copy says "never tested," so the bar has to be a real result. A user who
opened a card and walked away has still not tested it, and telling them
otherwise makes the one sentence Argus sends factually wrong.

### Explicitly excluded

- Generic topic digests.
- Price moves, threshold alerts, and any percentage-change trigger.
- Earnings, news, or filing alerts where no prior thread exists.
- Portfolio or holdings monitoring.
- Buy, sell, or hold recommendations of any kind.
- Thesis-invalidation warnings.
- Trending, social, or "what everyone is watching" content.
- Transcript mining for subjects the rail did not resolve.
- Arbitrary reminders and general scheduled tasks.
- SMS, web push, and native push.
- Anything shaped like "PLTR is down 8 percent."

### User-requested follow-up, bounded

"Follow up on this" is accepted as an **unmute on an already-eligible thread**.
It is never a user-authored subject and never a user-authored cadence.

The line matters. The moment a user can say "follow up on this every Monday,"
Argus is building Grok Automations, and section 15 explains why that is the one
thing worth refusing here.

## 5. Qualification: what counts as a fact that changed

This is the part that decides whether an email is worth sending, and it is the
part with no design yet because there is no data yet. Section 0 exists for this
section.

What is known now:

**A qualifying fact is specific to the thread's subjects.** An earnings report
from a company in the thread qualifies. A sector move does not. A market-wide
move never does, because it is not specific to anything the user left open and
it is the shape that turns this into an alerting product.

**Qualification runs on a cheap deterministic pre-filter first, and a provider
call second, only for threads the pre-filter already flagged.**

This is a cost boundary, not an optimization. Deciding whether Costco reported
earnings since a thread opened is a provider call per thread, per user, per
period, running unattended with nobody in the loop. At the scale of every
registered user times every open thread times weekly, that is unbounded
background spend, against a provider whose recorded per-call cost is already
known wrong by roughly 40x (#409).

Free or near-free signals that must be exhausted before any provider call:

- `fetch_alpaca_market_calendar()` and `fetch_alpaca_market_clock()`, already
  present in `src/argus/domain/market_data/capabilities.py`.
- Known earnings dates for the thread's symbols.
- Elapsed time since the thread opened.
- Whether the user has since run anything at all, which closes the thread with
  no provider call.

**A hard spend ceiling on the qualification pass is required**, declared in the
environment contract and default-off with the rest of the feature. A pass that
would exceed it stops and logs rather than degrading silently. Cost is recorded
to `cost_ledger_entries` under its own capability class, so the real number is
visible before anyone raises the ceiling.

**Follow-ups never charge the user's message allowance.** The user did not spend
a turn. The qualification cost is Argus's, and it is metered as Argus's.

## 6. Delivery: email and an in-app row

Both. In-app alone is still pull on return and brings nobody back, which is the
entire point of the pillar. Email alone leaves no durable product record and no
place to act.

- The email carries one to three items and deep-links into the original
  authenticated conversation.
- The conversation gains a row showing the prior work, what changed, its
  sources, and the ordinary path to a confirmation card.
- Numbers in either surface obey section 12's truth boundary.

**At most three items per send, ranked.** If more qualify, the rest wait for the
next period. A longer list is a digest, and the difference between this feature
and a digest is that a person can read the whole thing and act on it.

**Repeat rule, decided.** One follow-up per thread per qualifying event. A
thread surfaced twice with no action from the user is retired permanently and
never surfaces again. This is the exact point where every digest product becomes
spam, and it needs to be a rule rather than a tuning knob.

**Send timing.** `profiles` carries `language` and `locale` but no timezone, so
per-user send timing cannot be honest today. Sends use one fixed hour in one
stated timezone until `profiles` carries a timezone. Do not derive a timezone
from `locale`; it is wrong often enough to be worse than a stated default.

**Language.** Rendered in the user's profile language at send time, English and
es-419, no em dashes in either. Subjects and user-authored content stay verbatim.

## 7. Frequency: at most weekly, and usually silent

Eligibility is evaluated daily. At most one bundled send per period. Never an
empty send.

The default is weekly. The user may choose monthly or off. There is no daily,
no hourly, no cron expression, and no per-event trigger.

**Say plainly in the product that most weeks are silent.** Earnings are
quarterly. A user with two open threads will hear from Argus a few times a year,
not fifty-two. That is the design working, not the feature failing, and it is
the single strongest defense against becoming a digest. Anyone tempted to
increase send volume is proposing a different product.

## 8. Opt-in and controls

- One global opt-in grants email authority. It is separate from memory consent
  in both directions: enabling follow-ups never enables or broadens memory, and
  enabling memory never enables follow-ups.
- The control lives in Data Controls and must be reachable and functional when
  memory is disabled or unavailable by role. Follow-ups do not inherit memory's
  flag or its admin and developer role gate.
- Per-thread mute and permanent dismiss on every item, in both surfaces.
- Off means off, immediately, with no next-send grace.

Per-thread-only opt-in was considered and rejected: it asks the user to schedule
the magic before they know they want it, which defeats the retention value and
recreates the authoring problem in section 15.

## 9. Naming and voice

**The action is "follow up." There is no product noun.**

"Scheduled Searches" is wrong because it names a capability, and naming a
capability builds the menu Argus exists to refuse. It also describes
infrastructure rather than what the user gets.

`open_thread` stays internal contract language. It is already the code's noun
and it should never reach a user; in a chat product "open threads" reads as an
inbox.

User-facing language describes the situation, not the feature: "You left this
open", "Worth revisiting". The settings control is a sentence, not a label:

> Let Argus email you when work you left open is worth revisiting.

Banned as product names: Alerts, Monitors, Watchlist, Digest, Scheduled
anything.

**Voice rules.** No urgency. No percentages in the subject line. No "act now",
no countdown, no market-moving framing. The tone is the pre-flight checklist
noticing you never finished the checklist. State the fact, state what is open,
offer the test.

## 10. Where it lives, and who owns the reader

Two surfaces, no new top-level area. No Scheduled page, no dashboard, no
template gallery, no follow-up workspace.

| Surface | Owner |
| --- | --- |
| Follow-up row in the original conversation | this spec |
| Email and its content | this spec |
| Global opt-in, cadence, off, in Data Controls | this spec |
| Empty-chat greeting that names an open thread | **the empty chat polish lane** |

**The empty-chat greeting is the same reader, and this spec does not own it.**
The active roadmap's sidequest "Empty chat polish, Piece 2" already says so:

> The rail emits research subjects, open threads, and comparison sets, and
> nothing reads them. "You looked at Netflix last week and never tested it" is
> both a greeting and the return hook, and it is the same seam the follow-up
> pillar needs.

Ownership is stated here so two readers do not get built. Whichever lane runs
first builds the reader as a shared service; the second consumes it. If the
empty chat lane runs first, this pillar consumes what it built and adds
qualification, delivery, and controls on top. Neither lane writes its own
eligibility logic.

The reason both surfaces are needed: the original conversation may be weeks old
and buried in the sidebar, so a row inside it is close to invisible on its own.
The greeting is where an in-app follow-up is actually seen.

## 11. Guests

Guests get nothing here, and it is a fact rather than a policy choice.

A guest has no email address and a workspace that lives seven days by database
constraint (`DATA_MODEL.md` section 5.1). There is nothing to send to and
nothing that survives long enough to follow up on.

Conversion does not backfill. A converted account does not inherit follow-up
eligibility from its guest conversations. Work done after conversion is eligible
on the ordinary terms.

## 12. Relationships, stated so they cannot drift

The last pillar shipped with a split brain because its spec named a related
system without stating the relationship. These are stated.

**Memory.** Section 3. A ranking sharpener, inert when off, never the mechanism.
The pillar works with memory disabled and is not gated by memory's flag or its
admin and developer role gate. S10 is untouched: nothing here enters
interpretation, routing, or any simulation parameter.

**The research rail.** Sole producer of the typed follow-up block, sole research
route, sole current-fact source. No second Perplexity client, cache, meter,
router, or taxonomy. Qualification calls go through the rail's provider layer
and its cache, under the section 7 per-class TTLs. The rail being off stops this
feature entirely.

**Comparison.** An independent reader of the same canonical records, also
working with memory off. A follow-up may point at a comparison set the user
built. It never recomputes a comparison and never becomes a source of comparison
truth.

**The truth boundary.** Unchanged and binding. Frozen numbers come from
`evidence_artifacts`. Executable numbers re-ground through Argus providers.
Research supplies sourced context such as "Costco reported earnings" and never a
number presented as simulation truth. A test launched from a follow-up re-fetches
through Argus providers and ends at the ordinary confirmation card.

**Sharing.** Parked and separate. A private authenticated deep link into the
user's own conversation is delivery, not sharing. This pillar creates no public
slug, no snapshot, no forwardable receipt, and reuses none of that pipeline.

**Editing and versioning.** Untouched. A follow-up may reference an
`idea_version`; it never mints one.

## 13. Dependency: the email capability, not approved here

**Widening the single-purpose email guard is not approved by this spec. It is
its own lane and its own founder decision, and this pillar cannot ship without
it.**

Today's capability is one Resend SMTP helper in
[`access_approval_email.py`](../../../src/argus/domain/access_approval_email.py),
sending one waitlist approval message. The readiness spec
(`2026-07-30-public-alpha-readiness.md`) explicitly forbids generalizing it:
"this stays a single-purpose helper for exactly this one email."

A consented recurring mail capability requires, at minimum:

- a sender identity separate from `noreply@get-argus.com`,
- one-click unsubscribe as a `List-Unsubscribe` header, not a footer link,
- a suppression list checked before every send,
- bounce and complaint handling that writes back to suppression,
- per-user per-period send state, so a retry or a double-scheduled run cannot
  double-send.

**Do not design that here.** This spec names it as a hard dependency and stops.
A builder who reaches this section with the capability unbuilt should stop and
report rather than inline a mail subsystem into a follow-up lane.

## 14. Infrastructure

Anything scheduled needs a scheduler, and Argus has one built and unmerged.

`render.yaml` at head defines two `type: web` services and no cron. Branch
`claude/argus-render-cron-service-e18998`, commit `4930298a`, adds
`argus-maintenance` as a `type: cron` service on `*/15 * * * *`, running one
entry point that invokes guest retention and stale-job reconciliation unchanged.
It closes #401 and the scheduled half of #412. It is blocked on a denied `git
push`, so it has no PR and no CI, not on an open decision.

**Render Cron is the answer, and this pillar is a second job on that service,
not a new platform surface.** The reason #401 gives applies identically:
production data work should not require production service-role credentials
sitting in GitHub Actions.

Two things a builder needs to know:

- Adding a Render service touches five files, not four. Beyond `render.yaml`,
  `.github/argus-env.sh`, `.github/private-alpha-release-profile.json`, and
  `.env.example`, the validator `.github/private-alpha-release-profile.py` has a
  hard `SURFACES` tuple and an `expected_names` map that reject a profile whose
  service set differs. Adding a **job** to an existing service avoids this;
  adding a service does not.
- This feature's cadence is not fifteen minutes. Daily evaluation, weekly sends.
  That is a separate schedule on the same service, not a fourth call inside the
  existing maintenance pass, so a slow qualification run cannot delay guest
  retention or job reconciliation.

If the cron branch is still unmerged when this pillar is dispatched, that is a
blocker to report, not a reason to build a second scheduling mechanism.

## 15. The differentiation, and defend it

Every competitor makes the user author the schedule up front.

ChatGPT, Gemini, Grok, Perplexity, and Claude all ask the user to describe a
task and pick a cadence before anything happens. That means predicting at setup
time what you will want later, which most people cannot do. It is why ChatGPT,
Grok, and Perplexity all ship a **template gallery** on the creation surface:
users cannot think of what to automate, so the product hands them a menu.

That gallery is the menu Argus refuses. Not the scheduling, the authoring.

Argus needs no authoring at all. The trigger is work the user already left open
plus a fact that changed. Nobody describes anything, nobody picks a cadence,
nobody learns a feature name, and there is nothing to put in a gallery.

**The first feature request will be "let me schedule my own."** Decline it. The
moment a user can author a subject or a cadence, this becomes the same product
as everyone else's, complete with the empty state that needs templates to fill
it. The correct answer to that request is that Argus already knows what you left
open, and if it does not, there is nothing worth sending.

Two other findings worth keeping from the same review, both against the founder's
first read:

- These are no longer topic digests. By mid-2026 they are general automation
  systems with email triggers and remote execution. Calling them digests
  understates what has to be refused.
- The retention evidence cuts toward building. Chat features are abandoned once
  novelty fades, while features that do work the user would otherwise do
  themselves retain. This is the second kind.

## 16. Non-goals

No scheduled searches, no user-authored subjects or cadences, no template
gallery, no alerts, no monitors, no watchlists, no price triggers, no portfolio
tracking, no push or SMS, no new top-level surface, no second memory system, no
second scheduler, no public sharing, and no urgency in any copy in any language.

## 17. Acceptance

- Every follow-up points at a record the user created. Proven by test: no
  follow-up can be generated for a user with no open threads.
- Works with memory off, proven by test, including ranking degrading to
  structured signals.
- `MemoryCategory` is unchanged.
- A thread closes on a completed owner-scoped run intersecting its symbols, and
  a queued, running, or failed run does not close it.
- One follow-up per thread per qualifying event; a twice-ignored thread never
  surfaces again. Proven by test under a fake clock.
- At most three items per send, and no send when nothing qualifies.
- Qualification exhausts free signals before any provider call, and a pass
  refuses to exceed its declared ceiling.
- Follow-ups charge no message allowance; qualification cost lands in
  `cost_ledger_entries` under its own capability class.
- No `finance_search` number reaches a simulation. A test launched from a
  follow-up re-grounds through Argus providers and ends at the ordinary
  confirmation card.
- Guests generate no follow-up state at any point, and conversion backfills
  nothing.
- Opt-out takes effect with no next-send grace, and unsubscribe works from the
  email without signing in.
- One reader serves both the follow-up row and the empty-chat greeting.
- English and es-419, no em dashes, no urgency framing, browser evidence for
  both languages.
- Flag-off behavior is byte-identical to today.

## 18. Sources

### Argus authority

- `docs/superpowers/specs/2026-08-07-research-to-test-rail.md`, sections 4, 7,
  9b, 11, 11b, and 13b. Section 11's hard boundary is amended by section 2 here.
- `docs/superpowers/specs/2026-08-07-compare-your-own-work.md`, section 3, for
  the works-with-memory-off precedent this spec follows exactly.
- `docs/superpowers/specs/2026-08-06-personalization-memory-recall-loop.md`, for
  S10 and the consent posture this spec deliberately does not extend.
- `docs/superpowers/specs/2026-07-30-public-alpha-readiness.md`, for the
  single-purpose email guard named in section 13.
- `docs/specs/private-alpha-next-decision-memo.md` sections 5.6, 12.3, 16.2, 21.
- `docs/specs/argus-active-roadmap.md`, the five pillars and the empty chat
  polish sidequest whose Piece 2 shares this reader.
- `docs/DATA_MODEL.md` sections 5.1, 12, 12.1, and the owner-symbol prefix
  indexes.
- Issues #401 (nothing schedules ops jobs), #411 and #412 (conditions on the
  rail flag), #409 (recorded research cost understates real cost).

### Prior art, checked 2026-08-09

- https://help.openai.com/en/articles/10291617-scheduled-tasks-in-chatgpt
- https://support.google.com/gemini/answer/16316416
- https://x.ai/news/grok-automations
- https://www.perplexity.ai/help-center/en/articles/11521526-perplexity-tasks
- https://support.claude.com/en/articles/13854387-schedule-recurring-tasks-in-claude-cowork

### Inference, not evidence

- The section 0 floor of 50 threads across 10 accounts is a judgment about how
  much variety is needed to calibrate section 5, not a measured threshold.
- The claim that this retains better than a digest rests on the structural
  argument that the user created the loose end, plus general reporting that
  job-shaped features retain better than chat-shaped ones. It is not Argus user
  data, and it should be instrumented rather than assumed: open-threads-followed
  versus follow-ups-sent, and unsubscribe and mute rates per send.
