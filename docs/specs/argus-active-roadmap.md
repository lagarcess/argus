# Argus Active Roadmap

Status: **ACTIVE — this is the execution board.** Opened 2026-08-06.

Supersedes the two short-lived next-cycle boards and the completed interim
roadmap. `docs/specs/private-alpha-next-roadmap.md` remains as P2 history and
contract reference, not as the active board.

## Why this board exists

A competitor review on 2026-08-06 ([driven.ai](https://driven.ai)) produced one
finding that reorders everything: Driven does not backtest, so it is not chasing
the same job. But its entire first session is a research read, and that is the
same first message Argus gets. Argus currently refuses it.

Users are lost at the first question, before reaching the thing Argus is
actually good at. That is the gap this board closes.

This is a timing change, not a thesis change. Argus stays the pre-flight
checklist: test the idea, see the evidence, remember why. It does not become an
investment command center, an agent marketplace, or a trading surface.

## Vocabulary (founder-locked 2026-08-07)

Two words that were previously conflated, and are not the same thing.

**Memory** is the shipped feature. Argus proposes something worth remembering,
the user confirms, and it is recalled later. Inferred then confirmed. It lives
in `src/argus/memory/`, is opt-in, and is fully inspectable, editable, and
deletable. Call it memory, never "personalization memory".

**Personalization** is declared, not learned: the user tells Argus who they are
and how they want to be spoken to, from options Argus defines. Name, preferred
address, tone, interaction style. It does not exist yet. When it is built it is
a settings surface, not a memory mechanism, and it needs no consent flow because
the user authors every value directly.

The distinction matters because the consent posture differs. Memory stores
Argus's inferences about you and therefore needs earned opt-in. Personalization
stores your own stated preferences and needs none.

The flag `ARGUS_ENABLE_PERSONALIZATION_MEMORY` still carries the old name. It is
live and gating shipped code, so renaming it moves the release contract
(`.env.example`, `render.yaml`, `argus-env.sh`, the release profile, canary, and
QA scripts) together. Do it when something else touches that surface, not as a
standalone edit.

## Operating rules (founder-locked 2026-08-06)

1. **No phases, no incubation.** When a lane is dispatched it is built
   production-ready end to end: implementation, tests, evidence, docs, and
   user-facing polish in one lane. Review checkpoints are not a delivery model.
2. **Flags, not ceremony.** Work that is not ready for users ships behind a
   default-off flag on the same terms memory did. The flag is
   the safety boundary; staged branches are not.
3. **Items 1 and 2 are serial with each other.** Both rewrite the same
   interpreter and confirmation-card surfaces, so they cannot run in parallel
   without fighting. Everything else runs concurrently behind flags.
4. **GitHub issues are secondary.** An open issue earns work when it serves a
   board item, blocks items 1 or 2, or the founder steers it in. Otherwise it
   waits. The board leads, the tracker follows.
5. **Non-overlapping file ownership.** Parallel lanes must not share spine
   files. Where they do, they serialize.
6. **Nothing merges on self-report.** Per-lane founder gate, exact-head
   evidence, browser proof for anything user-facing.

## The five

### 1. Answer the first question — SHIPPED 2026-08-09

Merged as PR #396 at `ef08b25d`, 350 files, behind
`ARGUS_RESEARCH_RAIL_ENABLED` which is `false` in `render.yaml`,
`.github/argus-env.sh`, and the release profile. Closes #377 and #384.

All five question shapes work from an organic typed question in both
languages: market pulse, competitor analysis, screening, sector radar, and
single-stock analysis. Grounded discovery was absorbed rather than left beside
it, so one provider layer, one classifier, one cache, and one meter serve
everything. Guests get their own research allowance of three per day.

**Two conditions on turning the flag on**, recorded in the rail spec §13b and
open as issues. Both are wrong-when-enabled rather than wrong-as-shipped:

- **#411** the routing gate reads which execution field is set, never how it
  was set, so it cannot tell an interpreter-injected `strategy_type` from a
  stated one and hands the decision to a second classifier.
- **#412** a research job whose finalizer dies is settled by a reconciler that
  nothing schedules, so the answer is lost until an operator runs it by hand.

Also left open, none blocking: **#404** the vaguest market phrasings can still
be answered from model knowledge, honestly labelled; **#407** the source list
caps at five by arrival order without deduping by publisher; **#409** recorded
research cost counts tool fees only and understates a thorough turn by roughly
40x, which is why the guest ceiling was set conservatively.

The original scope, kept for the record:

Argus must handle an ordinary finance question without refusing it, then turn
the answer into something runnable.

- A factual or educational turn gets a real answer. No capability refusal, no
  confirmation-card interrogation, no unsupported-strategy rejection on what is
  obviously a knowledge question.
- A research read produces sources, freshness, and candidate entities, then
  offers one to three fully specified, runnable test cards. Tapping one opens
  the normal confirmation card. It never auto-runs.
- Suggestions are prebaked and backend-owned. The model may rank or explain
  closed candidates; it may not mint symbols, strategies, or asks. Every
  candidate passes resolver, asset-class, and coverage checks before it is
  tappable.
- Cover the full question range the founder asked for on 2026-08-07: live
  quotes, single-company reads, cross-company comparison, screening, and market
  stats. An earlier draft of this line restricted the lane to two jobs; that was
  a recommendation the founder overruled the same day, and it should never have
  survived here. No skill store, no menu, no picker: the range is reached
  through natural language, never a capability list.
- **Spec is written and founder-locked:**
  [`2026-08-07-research-to-test-rail.md`](../superpowers/specs/2026-08-07-research-to-test-rail.md).
  It supersedes the narrow competitor-comparison framing: Argus is no longer
  bounded to backtesting. Perplexity `finance_search` at $5 per 1,000
  invocations grounds quotes, fundamentals, segments, earnings, peers, screening
  and ETF constituents, selected by question shape with no menu. Closes #377.
- Peers now come free from the provider, which **retires the deterministic peer
  recommender in PR #384**. Close that lane rather than building it.
- **Follow-up, not in the rail lane:** the rail spec details the signed-in empty
  chat but leaves the guest empty state as placeholder and chips only. A landing
  page was considered on 2026-08-07 and rejected, because a composer that
  carries the typed question into chat makes the landing page and the guest
  entry the same surface with two sets of copy, and a front door with the chat
  behind it rebuilds the lobby this board refuses. The idea worth keeping is the
  inverse: the guest empty state becomes the entry experience, with a hero line,
  a cycling typewriter composer showing the range of questions, and trust
  signals sitting above the composer, collapsing into the conversation on first
  send. Revisit after mobile lands, since the exposure gate comes first.

Absorbs stabilization items formerly ranked Tier 1 #1, #3, #4, and the
knowledge/statistics macro. The interpreter ValueError work is complete and
awaiting review; it removed the dead-end banner but the underlying refusal
remains, which is this item.

Simplicity bar: someone who knows nothing about investing must understand the
answer and the offered tests.

### 2. Master editing (serial, after 1)

The confirmation card carries exactly three actions: **Run backtest**,
**Change/edit assumptions**, **Cancel**.

- Change/edit assumptions is the only entry point to editing anything.
- Compound, multi-parameter edits must work in one turn. "Change this and add
  that" cannot silently drop half the request in any language. This is the
  largest known reliability gap in the existing loop.
- Capital and dates additionally get in-place editing that spends no turn: an
  elegant drawer on the confirmation card, in the spirit of how the profile
  monogram is edited in profile settings. This is in addition to the
  conversational path, never a replacement for it. On web the entry point is a
  small dedicated row, in the shape of "edit costs". On mobile it reuses the
  sheet primitive defined in the mobile spec, so both surfaces share one
  pattern rather than inventing two.
- **Consolidate the confirmation card from five actions to three.** Today it
  shows Run backtest, change dates, change assets, adjust assumptions, and
  Cancel. The end state is Run backtest, Change/edit assumptions, Cancel.

  **This is gated on multi-edit working, and must not ship before it.** Change
  dates and change assets are deterministic entry points that tell Argus
  exactly which field is being edited. Removing them routes every edit through
  the free-form conversational path, which is the path that currently drops
  compound edits. Consolidating first would remove the working escape hatches
  and leave only the broken one.

  Motivating case, observed in alpha testing 2026-08-06: a user tapped change
  dates, then broadened the request mid-sentence to include other changes while
  Argus was waiting on a single field. The lesson is subtler than "fewer
  buttons": even a scoped entry point must accept a broader edit gracefully
  rather than holding the user to the button they pressed.

Absorbs #335, the #141 macro, and the #237 umbrella.

### 3. Mobile PWA (parallel, behind flag)

The public exposure gate. Nothing ships publicly while phones are broken.

**Spec is written and founder-locked:**
[`2026-08-06-mobile-pwa-responsive-shell.md`](../superpowers/specs/2026-08-06-mobile-pwa-responsive-shell.md).
No implementation authorized yet.

Locked shape, in brief:

- Responsive by screen width, not device sniffing, on custom breakpoints
  matching DESIGN.md section 8 rather than Tailwind defaults.
- Two thresholds: below 1024px the dossier becomes an overlay sheet, below
  720px the full mobile treatment applies.
- The sidebar becomes an off-canvas drawer behind a `=` trigger. Web is
  unchanged.
- One sheet primitive at three heights serves the dossier, the discovery
  sources pane, and item 2's capital and dates editor.
- Delivery is responsive PWA polish. The native-shell and full-native options
  are closed, not deferred.
- Prerequisite found while speccing: `layout.tsx` references a manifest that
  does not exist, and there is no apple-touch-icon or theme-color, so
  home-screen install does not look app-like today.
- Desktop and laptop behavior must not regress; it is already strong.

### 4. Compare your own work (parallel, behind flag)

Previously called "product memory". That name was wrong: none of it is a memory
system. The records already exist and are already written; what was missing is
reliable versioning and a way to read them back.

**Spec is written and founder-locked:**
[`2026-08-07-compare-your-own-work.md`](../superpowers/specs/2026-08-07-compare-your-own-work.md).

- Serves three real questions: which of my ideas did best, did my change help,
  should I do A or B.
- Spans three homes deliberately: versioning belongs to editing and mints on
  confirmed run rather than on edit, comparison answers are another question
  shape on the research rail's one router, and the only new surface is a
  multi-select confirmation card.
- **Works with memory off**, because reading your own runs is the product.
  Memory is a pre-wired optional sharpener for conceptual phrasing and personal
  success criteria, never the mechanism.
- Candidate relevance is structured filtering, not semantic search. The set is a
  bounded personal one, so exact beats fuzzy.
- Grounded with market context that explains *why*, under a hard boundary:
  numbers come from your evidence artifacts, Perplexity never restates a
  simulation result.

### 5. Sharing (parallel, behind flag)

Distribution, once there is something worth spreading.

**Spec is written and founder-locked:**
[`2026-08-07-sharing-evidence-receipts.md`](../superpowers/specs/2026-08-07-sharing-evidence-receipts.md).
Complete, all decisions made, dispatchable when the pillar comes up.

- An immutable, sanitized evidence receipt frozen at creation. Not a shared chat
  transcript, and never a live view.
- Owner-created, owner-revocable, stripped of private runtime detail. Memory is
  never shareable under any circumstance.
- Not-advice framing is stronger in a receipt than in the app, because the
  viewer has none of the context an app user has.
- The public view is mobile-first and owns its own layout, since shared links
  are opened from messaging.
- Deliberately last of the five: sharing a broken loop spreads a bad
  impression faster than a good one.

Decided from prior art rather than preference: never indexable with no
discoverability toggle, anonymous with no attribution, results only, no expiry
but a receipt list so revocation is real. ChatGPT exposed roughly 100,000 shared
conversations through a toggle users misread, and Claude shipped share links
with no noindex at all.

## Specced, not yet placed

### Follow up on unfinished work

**Spec is written and founder-locked:**
[`2026-08-09-follow-up-on-unfinished-work.md`](../superpowers/specs/2026-08-09-follow-up-on-unfinished-work.md).
Rank against the five is a founder call and is deliberately not claimed here.

Argus brings a user back by finishing a turn they started and abandoned. "You
compared Costco, Walmart and Target three weeks ago and never tested it. Costco
reported earnings since. Want to run it now?"

- **It amends rail spec section 11.** "Pull on return, never push" is replaced
  by: Argus may follow up only on something the user started and left open, and
  only when a fact specific to that thing changed. The initiation is the user's
  own, deferred, so an alerting product is structurally unreachable: Argus never
  picks the subject.
- **A reader over canonical records, working with memory off**, on the same
  precedent as pillar 4. Memory is a ranking sharpener only, and
  `MemoryCategory` does not grow.
- **It cannot be built yet, and that is the headline.** The rail flag is false,
  so zero open threads exist. The spec's section 0 carries four checkable
  preconditions: rail on in production, #411 and #412 closed, real threads
  accumulated to a stated floor, and the email decision made.
- **Email is a hard dependency and is not approved.** Widening the
  single-purpose Resend helper into a consented mail capability is its own lane
  and its own founder decision.
- **Shares one reader with the empty chat polish sidequest, Piece 2.** Ownership
  is stated in the spec so two do not get built.
- **Scheduler is solved and unmerged.** It rides `argus-maintenance` on branch
  `claude/argus-render-cron-service-e18998` (`4930298a`), as a second job with
  its own daily schedule, not a new Render surface.

## Continuous, not a lane

**Conversational runtime robustness.** Keep exercising the real chat runtime and
fixing what breaks. This runs alongside every lane rather than waiting its turn,
and it is how items 1 and 2 stay honest after they land.

Standing chore work, picked up alongside lanes rather than scheduled:

- **Extend the modularity budget to tests.** `.agent/modularity_budget.json`
  scans only `src` and `web`, and explicitly excludes `web/__tests__/**` and
  `web/e2e/**`. No Python test file is governed at all. The asymmetry is the
  problem: the interpreter lane had to extract a module to change production
  code by 13 lines, while a 2000-line test file lands with no friction. Six
  `tests/memory/` files now exceed 1000 lines, the largest bigger than the
  service it tests. Add `tests` as a scan root with baselines captured from
  current reality so it binds future work without a mass rewrite.
- **Strip the legacy Collections and Strategies code.** Dead ends and surfaces
  no longer exposed, plus any environment plumbing that only served them.
  Follow the onboarding strip-out pattern: remove the surface, keep legacy
  records read-safe, drop the env plumbing. **Not in scope:**
  `ARGUS_ASSET_PROVIDER_MODE`. An earlier draft listed it as a dead alias; it
  is live. It overrides `ARGUS_MARKET_DATA_PROVIDER_MODE` in
  `src/argus/domain/market_data/assets.py` so tests can pin the asset catalog
  independently of market data, and it is used by `tests/evals/` and
  `tests/agent_runtime/`. Leave it. It is worth documenting rather than
  removing, since a silent two-variable fallback chain is the same env-confound
  shape that has produced fake test failures before.
- **Implement the usage allowance meter colors.** `.agent/designs/argus/DESIGN.md`
  section 23 already specifies this completely and it was never built: teal
  at or above 30% remaining, `--rui-color-warning` above 10% and below 30%,
  and `--rui-color-danger` at or below 10% including exhaustion, with the
  lowest normalized active window governing. Color stays supporting information
  only, so the exact remaining count and truthful reset time must survive, with
  no pulsing or terminal-style treatment. Today `UsageModal.tsx` and
  `ProfileMenu.tsx` reference none of those tokens.

## Sidequest lanes

Bounded, dispatchable work that is not one of the five and does not block them.
Each carries a sequencing constraint, because small does not mean parallel. Most
of these touch a file a main lane already owns, and two agents in one file is
how the last split brain happened.

### Empty chat polish

**Sequencing: unblocked 2026-08-09 when pillar 1 merged. Parallel-safe with the mention tags
lane.** It touches `EmptyChatSurface.tsx`, `ChatInterface.tsx`,
`EmptyChatGreeting.tsx`, and both locale files. The rail owns all four today and
created the greeting component. PR #406 touches none of them, so once the rail
lands these two run at the same time.

Three pieces travel together because they share the same surface and the same
two locale files. Split into separate lanes they would have to be serial with
each other anyway, so splitting buys nothing and costs a merge.

#### Piece 1: retire the show/hide suggestions toggle

No major assistant ships this control. ChatGPT, Claude, Gemini, Perplexity, and
Grok all put starter suggestions in the empty state and let them disappear on
first interaction. A toggle is a control for a problem that resolves itself in
one tap, and every control costs the user a decision. That is the no-menu rule
applied to the interface rather than to capabilities.

It also renders below the legal disclaimer, in the phone thumb zone, so the
least important element on the screen occupies the most valuable position.

**Scope:** the toggle button in `EmptyChatSurface.tsx`, its `showSuggestions`
and `onToggleSuggestions` props, the `showSuggestions` state in
`ChatInterface.tsx`, and the `chat.show_suggestions` and `chat.hide_suggestions`
keys in both locale files.

**Behavior after:** suggestions render whenever the empty chat surface renders,
and stop once a conversation has a message, which happens for free because the
surface stops rendering. Nothing replaces the toggle: no dismiss gesture, no
auto-hide timer, no settings entry.

**There is no migration to write.** The state is a plain `useState` with no
localStorage, cookie, or server field behind it, so nothing persists and no user
is stranded. Confirm that before deleting, but do not invent a migration for
state that does not exist.

**One decision to raise, not take.** Two flags gate the same chips.
`NEXT_PUBLIC_CHAT_EXPLORATORY_SUGGESTIONS_ENABLED` is `false` in `render.yaml`,
`.github/argus-env.sh`, `.github/private-alpha-release-profile.json`, and
`.env.example`, while the research rail's own flag governs the same surface and
rail spec section 10 makes prebaked suggestions part of the signed-in empty
chat. That is one flag too many. Retiring an env flag is a release-contract move
and all four files travel together, so it is a founder call.

#### Piece 2: the greeting needs variety it does not have

Four greetings exist, all keyed on time of day, one string per slot:

| Hours | English | Spanish |
| --- | --- | --- |
| 05:00 to 08:59 | Hey, early bird. What should we look at? | Madrugaste hoy. ¿Qué miramos? |
| 09:00 to 17:59 | What should we try today? | ¿Qué probamos hoy? |
| 18:00 to 22:59 | What should we look into tonight? | ¿Qué exploramos esta noche? |
| 23:00 to 04:59 | Hello, night owl. What are you curious about? | Hola, noctámbulo. ¿Qué te da curiosidad? |

Rail spec section 10 asked for time of day, memory, and geography. Only time of
day was built.

**The defect is repetition, not slot count.** The day window is nine hours wide,
so anyone opening Argus during a workday sees one identical sentence forever.
Adding a fifth slot does not fix that.

**Pool size.** Five or six per slot for `day`, since a weekday user lives
entirely in it and three would cycle visibly inside a week. Fewer elsewhere is
fine; nobody is in the 3am slot on a schedule.

**Rotation is day-stable, never per page load.** Refreshing into a different
greeting is exactly what makes these read as generated. Seed from the date so
one line holds all day and changes tomorrow, with no consecutive repeat.

**Market session lines are pool members, not overrides.** Time of day describes
the user, market session describes the market, and they decouple outside Eastern
time: 5am to 9am local overlaps pre-market only for an Eastern user. So when a
session is active its lines become eligible candidates inside the current slot's
pool, and the same day-stable seed picks from the widened set. Nothing overrides
anything, a session line cannot appear outside its session, and the generic lines
stay in play.

Weight them unevenly. Weekend and holiday closure is a two-day state where the
market fact is the most useful thing Argus can say, so it should speak often.
Pre-market and after-hours are transient and mostly irrelevant to backtesting, so
they surface occasionally rather than as a headline. The one place they genuinely
matter is the fast quote shape, which already returns pre and after-hours
figures.

**Closed markets must stay true for every asset class.** Argus supports crypto
and currency pairs, which do not close, so a bare "markets are closed" is wrong
for those users. Say both: stocks are closed for the weekend, crypto does not
stop. That is true for everyone, useful to everyone, and teaches a real
difference between the asset classes Argus actually supports.

**The data already exists, including the part most likely to be faked.**
`src/argus/domain/market_data/capabilities.py` already carries
`fetch_alpaca_market_clock()`, returning `is_open`, `next_open`, `next_close`,
`is_market_day`, and `phase`, and `fetch_alpaca_market_calendar()`, which hits
the real trading calendar. No new integration, credential, or provider.

Two traps: session is computed in Eastern time, never the user's clock, because
someone in London at 2pm is in US pre-market and a local-time calculation gets
that backwards. And holidays come from the calendar endpoint, never a weekday
check. That assumption has already bitten this repo once, where synthetic
fixtures placed bars on weekends and holidays so date logic passed every test and
broke against a real calendar.

**Geography, as named in rail spec section 10, means market session here.**
Location data is a real privacy cost for a cosmetic gain, and knowing someone's
city says nothing about what they should ask. Knowing whether the market is open
does.

**Memory-driven greetings are the highest-value addition and are already half
built.** The rail emits research subjects, open threads, and comparison sets, and
nothing reads them. "You looked at Netflix last week and never tested it" is both
a greeting and the return hook, and it is the same seam the follow-up pillar
needs. A greeting is voicing, so this stays inside the S10 lock. Same rule as the
chips governs: memory-driven when memory has something, the rotating static pool
otherwise, guests always static.

**Keep it warm, not clever.** "Hola, noctámbulo" works because it is warm without
performing. A greeting that tries harder becomes a mascot, and the product
posture is the opposite of a mascot.

#### Piece 3: ask what to call the user, in its own field

Add a profile field, "What should Argus call you?", rather than reusing
`display_name`.

`display_name` exists and is editable, so reuse is free, and it is still wrong.
It is an identity field. People fill it with a legal name or whatever their email
gave them, because it is for the account rather than for being spoken to. "What
is next, Luis Garces?" reads like a form letter.

Being addressed by name is also not universally welcome, and some people find it
presumptuous from software. A dedicated optional field makes it a choice the user
made rather than a side effect of having an account. Blank means the greeting
uses no name, which needs no special handling because most of the pool will not
use one.

**The name appears in some pool members, not all.** Every greeting using someone's
name gets grating in about three days.

**This is a setting, never a memory.** Argus does not infer what to call you from
conversation. Memory infers, settings are stated, and guessing a nickname from
how someone types would be the creepiest thing in the product. Guests have no
profile and fall back to the nameless pool.

### Ticker mention entity tags

**Sequencing: unblocked 2026-08-09 when pillar 1 merged.** PR #406 was held
because it overlapped the research rail on nine files, including
`ChatInput.tsx`, `ChatMessage.tsx`, `StrategyConfirmationCard.tsx`,
`types.ts`, `src/argus/api/schemas.py`, and the API contract and OpenAPI
documents. Merging it mid-flight would have forced a 350-file lane to merge
forward a second time and resolve conflicts in its own active surface. It now
merges forward once, against a landed lane instead of a moving one.

It needs a reconciliation pass against the rail before merging, since those
nine files all changed underneath it.

Its spec is `docs/superpowers/specs/2026-08-09-ticker-mention-entity-tags.md`.

## Landed this cycle

- **Answer the first question** (PR #396, merged 2026-08-09 at `ef08b25d`) —
  350 files behind a default-off flag. Grounded discovery absorbed into one
  rail: one provider layer, one classifier, one cache, one meter. All five
  question shapes proven from organic typed questions in both languages, each
  ending on a runnable next step. Guests carry their own research allowance.
  Two conditions on enabling are open as #411 and #412; see pillar 1 above.


- **PostHog native funnel repair** (PR #405, merged 2026-08-09 at `1b4555e2`) —
  product events were captured server side with the business label at
  `attributes.product_event`, which PostHog SQL can read and its native funnel
  builder cannot filter on, so the activation funnel returned no data while the
  events were present. A closed allowlist of categorical dimensions is now
  projected to top level inside `_posthog_event_properties()`, derived from the
  sanitized attributes in one place rather than written twice, so the copies
  cannot drift. Existing top-level properties win on collision and only scalars
  promote.

  **Two acceptance criteria remain open and are not the lane's to close.** A
  live PostHog event and a real native funnel both need a production promotion.
  Until then the projection is proven by tests only. The urgency was never the
  dashboard: events already sent cannot be backfilled, so every day without it
  was history that will never appear in a native funnel.

- **Memory** (PR #386) — complete loop behind a default-off flag
  scoped to `admin` and `developer` allowlist roles. Propose, confirm, inspect,
  explain, edit, delete, disable, reset, export, and temporary chat. Guests
  denied before any side effect.

  **Follow-up is specced and ready to dispatch, not pending decisions.** The
  recall loop is locked in
  [`2026-08-06-personalization-memory-recall-loop.md`](../superpowers/specs/2026-08-06-personalization-memory-recall-loop.md).
  Four Mem0 parameters
  are ratified: index-only over confirmed content, so Mem0 never sees
  unconfirmed material; storage on the existing Supabase database with no new
  datastore service; Mem0 as the OSS library running in-process inside the API
  service rather than the hosted platform; and its extraction, dedup, and
  conflict-resolution pipeline explicitly unused, because Argus owns extraction
  and the assisted-not-automatic rule forbids it.
- **Canary automation** (PR #385) — API-layer denial probe, deployed-SHA
  evidence binding, and the fix for the canary validating the wrong branch. A
  signup enumeration oracle and a false-evidence path were caught in review.
  Session injection for the browser golden path remains open on #383.
- **Retest current-data windows** (PR #363, in review) — the waste guard moved
  out of the chat turn into the dossier button, computed before any click.

## Deliberately not doing

From the competitor review: no agent marketplace, no model picker, no
multi-hundred-API integration story, no autonomous monitoring, no portfolio
system, no messaging channels, no trading workflow, and no auth-gated marketing
site standing between a visitor and their first test. Guest entry stays the
activation path, because a completed first backtest is activation, not account
creation.

## Secondary tracker state

Open issues serve the board or wait. Currently aligned: #377 (item 1), #335 /
#237 (item 2), #332, #367, #369, #365, #364 (robustness). Currently waiting:
#294, #244, #350, #236, #314, #376, #378, #383.
