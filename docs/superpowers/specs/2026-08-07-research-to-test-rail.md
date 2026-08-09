# Research to Test Rail

Founder-locked 2026-08-07. Spec only.

Board pillar: **Answer the first question**, on
[`argus-active-roadmap.md`](../../specs/argus-active-roadmap.md). Supersedes the
narrow "competitor comparison" framing. Related issue: #377.

## 1. Why

Argus is bounded to backtesting, and that is the wrong boundary. Users arrive
with questions, not strategies. Many do not know what a backtest is.

The question nobody asked: **how well informed does someone want to be before
running a test, or before acting anywhere else?** Backtesting is one part of
that, not the whole.

Perplexity's `finance_search` closes the gap. It is billed at $5 per 1,000
invocations, a half cent per call, so cost is not the constraint. Latency and
trust are.

Reference material, to be read before building:

- Tool overview and capabilities:
  https://docs.perplexity.ai/docs/agent-api/tools/finance-search
- Recommended configurations:
  https://docs.perplexity.ai/docs/agent-api/tools/finance-search#recommended-configurations
- Live market data and quotes:
  https://docs.perplexity.ai/docs/agent-api/tools/finance-search#live-market-data-and-quotes
- Single-company historical lookups:
  https://docs.perplexity.ai/docs/agent-api/tools/finance-search#single-company-historical-lookups
- Multi-step financial research:
  https://docs.perplexity.ai/docs/agent-api/tools/finance-search#multi-step-financial-research
- Prompt guidance:
  https://docs.perplexity.ai/docs/agent-api/tools/finance-search#prompt-guidance
- Coverage:
  https://docs.perplexity.ai/docs/agent-api/tools/finance-search#coverage
- Background mode:
  https://docs.perplexity.ai/docs/agent-api/background-mode

## 2. The locked shape

**No skills. No menu. No picker. Nothing for the user to learn.**

The user types naturally. The interpreter decides the shape of the question.
The backend picks which `finance_search` operations serve it. The user never
selects a mode and never discovers a capability list.

This is the difference from Driven, which sells a skill catalogue. Market pulse,
competitor analysis, stock screening, sector radar, and single-stock analysis
are not five products in Argus. They are five shapes of question that one rail
answers.

Every answer ends somewhere runnable. A research turn should usually leave the
user one tap from a grounded test.

## 3. Question shapes and configurations

The three documented configurations form a natural cost ladder. The interpreter
selects one from the question shape; the user never sees the choice.

| Shape | Config | Settings |
| --- | --- | --- |
| Live prices, quotes, latest figures, pre and after hours | fast | `max_steps=1`, `max_output_tokens=1024` |
| One company's history, statements, fundamentals, segments | balanced | `max_steps=5`, `max_output_tokens=2048`, plus `web_search` and `fetch_url` |
| Cross-company comparison, screening, multi-year trends, sector work | thorough | `max_steps=10`, `max_output_tokens=4096`, `claude-opus-4-7` |

Follow the documented prompt guidance: lead with the business question and then
the company or ticker, include the time window, let the tool choose report
fields, and state the desired outcome rather than a data structure.

**Thorough runs use background mode.** Chat must never hang. Submit with
`background=true`, poll `GET /v1/agent/{id}` to a terminal state, and surface
progress through the existing queued / running / complete job lifecycle that
already serves backtests. Do not invent a second progress mechanism.

## 4. The truth boundary

`finance_search` returns pricing and OHLCV. So do Alpaca and Kraken. Two sources
of price truth destroys trust, and it is unrecoverable once a user notices.

The rule:

> **Research informs the reader. Argus providers execute the simulation. When
> research becomes a test, the handoff re-grounds in Alpaca or Kraken.**

Concretely: quoting a closing price, a pre-market figure, or a valuation to the
user is correct and encouraged. Feeding any `finance_search` number into a
backtest is forbidden. A test launched from a research answer re-fetches its
data through Argus's own providers.

This has the same standing as the S10 memory lock. Write it into canon.

## 5. Coverage gap, and it is real

The documentation covers **public equities and ETFs only**. Cryptocurrency and
currency pairs are not listed, and Argus supports both.

Required behavior:

- Equities and ETFs route to `finance_search`.
- Crypto and currency pairs must not silently fail and must never fabricate. Use
  `web_search` for context, and Argus's own Kraken data for prices.
- Docs may be stale, so probe actual crypto and FX responses during the build
  and record what really comes back. Let evidence decide, not the doc.
- Any asset where coverage is missing degrades to an honest answer with a
  runnable next step, never a dead end.

## 6. Peers and incremental basket building

`finance_search` returns peers directly. This retires the deterministic peer
recommender in PR #384; close that lane rather than building it.

Peers are **never a browsable list**, which would be a menu.

They surface two ways:

1. **Inline in the answer**, as plain context.
2. **As prebaked runnable rows** on the existing typed Try-next surface.

Tapping a row **adds to the pending confirmation card without spending a turn**,
and further rows offer the remaining peers, individually or in sets, until the
maximum asset count is reached. No researched peer is wasted, and nobody spends
a message to add a ticker.

Naming everywhere uses `<Name> [ticker]`, in plain non-technical language.
"Test Netflix against Disney and Warner Bros", not "equal-weight NFLX/DIS/WBD
basket".

**Adding an asset changes the experiment materially.** The card must disclose
what changed and remain honest that this is now a different test. Update
cleanly; never mutate silently.

## 7. Caching

Shared caching across users is the cost lever, and it is safe here because
`finance_search` returns public market data. **This layer must never be reused
for anything user-scoped.** State that at the seam.

TTL is per data class, not global:

| Class | Tolerance |
| --- | --- |
| Quotes, pre and after hours | seconds to minutes |
| Top gainers, losers, most active | minutes |
| Analyst estimates | days |
| Fundamentals and statements | quarterly |
| Peers, ETF constituents and weights | months |
| Closed historical OHLCV | effectively immutable |
| Earnings transcripts, SEC filings | immutable once published |

The cache key includes the period of interest, so a specific past close is a
different entry from a trailing window.

## 8. Rich output

Prose gets richer. Typed stays typed.

`ReactMarkdown` with `remarkGfm` is already wired in `ChatMessage.tsx`, and
`prose dark:prose-invert` is applied, so tables and lists already render. The
model already authors prose, so letting it produce tables, quotes, and structure
grants no new authority.

What is missing:

- Argus design treatment for markdown elements. `globals.css` styles only
  `.prose p`. Tables especially need it.
- **Wide tables must scroll inside their own container** and never break the
  page, which matters most on narrow screens.

Everything actionable stays backend-typed exactly as today: Try-next rows,
cards, confirmations. **The model formats explanations; it never mints an
action, symbol, or ask.**

Coordinate with the mobile lane, which also rewrites `ChatMessage.tsx`.

## 9. Metering

Research turns count as ordinary turns and messages for now. This is
deliberately simple and deliberately generous: the alpha exists to learn what
users actually do, and a tight faucet produces no signal.

**Instrument by capability class** even though the meter is flat: fast quote,
balanced lookup, thorough research, screening, peer expansion. One gauge for the
user, rich classes underneath. That instrumentation is what makes natural tiers
visible later, and it is the part that is expensive to retrofit.

The existing global daily ceiling was sized for opt-in discovery. Research on
the default path changes the volume profile, so **re-address the ceiling**, and
make ceiling exhaustion an honest, localized message rather than a silent
capability disappearance.

### 9b. Amendment 2026-08-09: a guest's research is its own allowance

Flat metering holds for signed-in users; their message allowance is their
meter. It does not hold for guests. A guest has ten free messages and no
account, so ten thorough comparisons is a bill nobody sized, charged to a
stranger who may never return.

**A guest gets three research questions a day**, keyed to the visitor rather
than the workspace, on the same counters the message and simulation allowances
already use, so a renewed workspace grants nothing new.

- **One ceiling for every shape**, not one per tier. A stranger cannot tell a
  fast lookup from a thorough comparison, and the rail decides the tier, so the
  rail owns that cost rather than the guest.
- **Three is deliberately conservative because the recorded cost is wrong**:
  the ledger's per-call figure is not yet trustworthy (issue #409). Raising the
  number later is cheap; refunding a month of underpriced strangers is not.
- **Exhaustion names the bound that actually closed.** A guest who spent their
  own three is told so and pointed at an account; they are never told the
  shared capacity ran out, and a shared outage is never blamed on them. Either
  way the turn still answers from Argus's own data and still ends on a runnable
  row.
- **Cache hits and signed-in turns never charge it.**

## 10. Signed-in empty chat

Registered accounts only. Guests keep the current entry.

- The muted `A` sits persistently in the background while no message has been
  sent, reusing the treatment in `ConversationRetrievalState.tsx`.
- A typewriter greeting, context aware: time of day, memory, geography.
  "What should we try today?", "Hello, night owl", "Hey, early bird". Translate
  the sentiment, not the words; es-419 must feel native rather than rendered.
- Below it, prebaked suggestions, reusing `chat.show_suggestions`,
  `chat.hide_suggestions`, and `chat.example_queries`. The current q1 to q3
  strings may be stale; verify them.
- Composer at the bottom.

**Every suggestion must be genuinely runnable**, built from memory, recent
context, or safe defaults. A suggestion that fails when tapped is worse than no
suggestion. Prebake for retention, engagement, and conversion, but only what
truly runs.

## 10b. Entry surface copy

The current entry under-promises now that Argus is not bounded to backtesting.

**Composer placeholders.** There are three, and only two change.

| Key | Current | New |
| --- | --- | --- |
| `chat.input_placeholder` | "Describe an investing idea" | **"Ask about any company or idea"** |
| `guest.shell.input_placeholder` | "What do you want to test?" | **"Ask about any company or idea"** |
| `chat.followup_placeholder` | "Add a follow-up" | **unchanged** |

es-419 for both new strings: **"Pregunta sobre cualquier empresa o idea"**.

The two empty-state placeholders instruct rather than invite. "Describe"
assumes the user already has an idea, and both "investing idea" and "test"
exclude questions. Together they tell every arriving user they must show up
with a strategy, which is the exact barrier this rail removes. The guest one
matters most, because guests form the first impression with no memory behind
them.

**Why this wording, and why not "test an idea".** Naming a mechanism creates a
promise that breaks. Argus cannot run every idea: options, shorting, leverage,
an obscure ticker, an exchange without coverage. A placeholder that says "test
an idea" is a broken promise at the worst possible moment, the first message.

"Ask" cannot break the same way. Even when a strategy is unsupportable, Argus
still answers about the subject, so the invitation stays true in the failure
case. "Idea" stays open too: it does not require the idea to be testable,
tradeable, or even fully formed, which is the state most people actually arrive
in.

This still delivers the goal. The old copy under-promised because it implied
Argus only backtests. The new copy signals the capability that is genuinely new,
that Argus answers questions, while the chips beneath it demonstrate the range
including testing. Neither element over-commits.

**Division of labor:** the placeholder's job is to not exclude. The chips
demonstrate breadth. Do not ask the placeholder to do both.

**Both keys carry the same string.** The requirement is identical for guest and
registered, and two ways of saying one thing is copy debt. Diverge only if the
guest shell has a real width constraint.

This reduces exposure rather than eliminating it. Someone asking for an
unsupportable strategy still meets a limit, and Argus must answer about the
subject anyway and offer something runnable. That is the ordinary behavior
section 13 already requires, not a special rule for this copy.

`chat.followup_placeholder` is correct as it stands. Once a conversation is
underway the user knows what Argus does, and "Add a follow-up" is exactly right
for that moment. Do not touch it.

**Starter chips.** `chat.example_queries` currently holds three backtests
(q1-q3), which implies backtesting is all Argus does. Keep three chips, but span
the range, so breadth is inferred from variety rather than from a list:

- a learn-shaped question
- a compare-shaped question
- a test-shaped question

**Phrase every chip as something a user would say, never as a capability name.**
"Compare Costco against Walmart and Target" teaches capability implicitly.
"Competitor Analysis" is a feature label, and labeling capabilities builds the
menu this spec refuses. This is the line that keeps Argus distinct.

Pick companies that are widely recognizable and non-intimidating, in service of
the simplicity bar that someone who knows nothing about investing must
understand the example. Avoid names lifted from a competitor's marketing.
**Prefer evergreen recognizability over trending names**, because hardcoded
copy decays and a stale "trending" example ages badly.

**Animation.** One animated element per screen. The typewriter belongs on the
signed-in greeting, not the composer placeholder. Two competing animations read
as noise, animated placeholders fight users mid-thought, and they degrade
screen-reader behavior. Retire the old composer typewriter rather than reviving
it.

**Audience, and the rule that decides it.**

> Memory-driven suggestions when memory has something to offer. The
> range-spanning static chips otherwise. Guests always get the static ones.

The deciding case is a registered user with no memory yet, a fresh account or
memory left off. They cannot receive personalized suggestions because there is
nothing to personalize from, so they fall back to the static chips.

That means **the static chips are not guest-only code**. They are the fallback
for everyone, and should be built that way rather than as a guest branch.

A signed-in user with real history should never see generic examples. Showing
them "How has Nvidia's revenue changed?" when Argus knows what they actually
follow is a downgrade, not a neutral default.

**Sequencing.** This copy ships with the rail, never ahead of it. A compare
chip that fails on tap is worse than the underwhelming backtest chip it
replaces.

## 11. Memory scope expansion

This changes what memory is for, and the in-flight recall-loop
lane must absorb it.

The decision memo already anticipated this in section 5.6:

> Memory tells Argus what mattered to the user. Web and search tell Argus what
> changed in the world. Backtesting tells what historical evidence says.

`finance_search` is the missing half. Memory alone is a journal. Freshness alone
is a news feed. Together they are the only thing that gives Argus something
genuinely new to say when a user returns.

New categories memory must record, beyond confirmed preferences and saved
decisions:

- **Research subjects** — the interest graph of companies and sectors asked
  about.
- **Open threads** — researched but never tested. The strongest return hook,
  because the user created the loose end themselves.
- **Comparison sets** — a built basket is a durable object, not a one-off.

**Hard boundary: pull on return, never push.** Argus notices what changed when
the user comes back. It does not monitor in the background, and it does not
notify. Driven works while you sleep; Argus does not. Same discipline as
assisted-not-automatic.

Everything already locked still holds: user confirmation before anything
durable, guest denial, the never-store classes, and S10.

## 11b. Amendment 2026-08-07: one rail, not two

**This amendment is binding and supersedes anything above that conflicts with
it.** It exists because the original spec named grounded discovery only in its
Sources list and never stated the relationship between them. That omission
produced two parallel systems.

### The defect

`src/argus/domain/discovery_search/` and `src/argus/domain/research/` both call
Perplexity, both answer question-shaped input, both produce candidate assets,
and `research_answer.py` imports nothing from discovery. They carry separate
caches, separate metering, and separate routing.

The consequence is user-visible: a comparison question such as "Compare Costco
against Walmart and Target", one of this spec's own starter chips, is claimed by
the discovery taxonomy and never reaches the rail. The peer flow could not be
demonstrated from an organic question for the same reason.

Section 2 requires that the user types naturally and the interpreter decides the
shape. That requires **one decision point**. Two systems means two decision
points with a taxonomy arbitrating between them, which is the failure.

### Required

1. **One provider layer for Perplexity**, covering both the direct search path
   and the Agent API with `finance_search`. Not two clients.
2. **One router.** A single classifier owns question shape for everything that
   was previously split between discovery and research. Discovery's
   asset-finding becomes an operation of the rail, alongside quotes,
   fundamentals, peers, screening, and market stats. It is not a sibling
   system.
3. **One cache.** The per-class TTL table in section 7 governs every Perplexity
   result, including anything discovery previously cached separately.
4. **One meter.** The capability classes in section 9 cover every call. The
   separate discovery allowance and its global ceiling fold into that scheme
   rather than running beside it.
5. **Existing discovery behavior must not regress.** Source-backed results,
   resolver and asset-class gating, Guest parity, English and es-419, and the
   typed action contract all survive. This is absorption, not replacement, and
   the user-visible discovery experience should be unchanged or better.
6. **Prove the routing.** Each starter chip, and each question shape in the
   taxonomy, reaches the rail from an organic user question. The peer flow must
   be demonstrated end to end without a server-seeded card.

### Also required, found in the same review

- **Thorough path parity.** The background path is currently second-class: it
  drops `operation_scope` so a completed research job cannot be recognized as
  research, it bypasses the cache entirely with `cache_status` hardcoded to
  miss, and completed jobs return peers that never persist to the checkpoint.
  Caching matters most on the most expensive tier, so this is backwards. Fix as
  one theme, not three patches.
- **Trigger reliability.** At the default turn-call allowance the research
  classifier can be starved by interpreter audit calls and silently fall back to
  pre-rail routing. The rail must fire reliably at default configuration, not
  only with a raised knob.
- **ETF constituents and weights.** Named in section 2, absent from the
  implementation. This is the capability that addresses the exposure-resolution
  limitation accepted in the discovery lane, where true ticker collisions
  dropped exposure ETFs.
- **Memory producer seam.** Section 11 requires memory to record research
  subjects, open threads, and comparison sets. The rail must **emit** those in a
  typed form the memory lane can consume, even though consumption ships
  separately. Without the producer the follow-up lane has to retrofit it.

### Acceptance for this amendment

- No second Perplexity client, cache, meter, or router remains.
- Every starter chip reaches the rail from an organic question, proven in
  browser evidence rather than by seeding.
- Discovery journeys that worked before still work, in both languages, for
  Guest and registered.
- The rail fires at default configuration with no knob raised.
- Research subjects and open threads are emitted in a typed, consumable shape.

## 12. Non-goals

No skill store, model picker, agent marketplace, autonomous monitoring,
portfolio tracking, messaging channels, or trading workflow. No auth wall before
a first test. Argus remains the pre-flight checklist.

## 13. Acceptance

- A natural question of each shape returns a grounded, sourced answer with no
  menu and no capability discovery.
- Every research answer offers at least one genuinely runnable next step, or an
  honest reason none exists.
- Peer rows add to the pending card without spending a turn, up to the asset
  maximum, disclosing the material change each time.
- No `finance_search` number ever reaches a simulation; a test launched from
  research re-grounds in Argus providers. Proven by test.
- Crypto and currency pairs degrade honestly, never fabricate.
- Thorough research runs in background mode without blocking chat.
- Cache hits are demonstrable across users, with per-class TTL respected.
- Tables render with Argus treatment and scroll rather than breaking narrow
  layouts.
- Capability class is recorded per research turn.
- Signed-in empty chat shows the muted mark, greeting, and runnable
  suggestions, in English and es-419.
- Flag-off behavior is byte-identical to today.

### 13b. Conditions on enabling, not on merging

These are wrong-when-enabled, not wrong-as-shipped: the rail is off in
`render.yaml`, `argus-env.sh`, and the release profile, so nothing here
reaches a user while the flag is false. They are recorded as gates on the
**flag decision** rather than the merge, and turning the flag on without
closing them is a decision someone is making against this list.

- **#411, routing provenance.** The rail's clarification gate tests which
  execution-evidence field is set, never how it was set, so it forgives an
  interpreter-injected `strategy_type` and cannot tell that default from a
  stated one. An explicitly interpreted buy-and-hold with no other execution
  field is therefore indistinguishable from a bare comparison and can reach
  research instead of the builder, with the real routing decision falling to
  a second classifier reading the raw message. Default provenance belongs in
  the structured interpreter contract, after which the gate is a deterministic
  check on typed output and the tolerated-defaults set collapses to empty.
- **#412, stranded research jobs.** A research run is finalized by a
  process-local poller, so a restart orphans it. The stale scanner now settles
  such a row as a retryable failure instead of leaving the turn queued
  forever, but nothing in a deployed environment runs that scanner on a
  schedule (the same gap as #401), and the completed answer is discarded
  rather than resumed from the background id already persisted on the job row.
  Enabling the rail without a scheduled reconciler means a deploy can strand a
  user's thorough turn until an operator intervenes.

## 14. Sources

- `docs/specs/private-alpha-next-decision-memo.md` sections 5.6, 10.5, 12.3,
  16.1, 21, and 18.
- `docs/specs/argus-active-roadmap.md`, pillars 1 and 4.
- `.agent/designs/argus/DESIGN.md` sections 8, 17, 18, 19.
- `docs/superpowers/specs/2026-08-06-personalization-memory-recall-loop.md`.
- `docs/superpowers/specs/2026-08-06-mobile-pwa-responsive-shell.md`, for the
  shared `ChatMessage.tsx` surface.
- Existing implementation: `src/argus/agent_runtime/knowledge_answer.py`, the
  answer router from PR #387, `src/argus/agent_runtime/next_experiments.py`,
  `src/argus/domain/discovery_search/`, and the allowance machinery in
  `src/argus/api/chat/discovery_evidence.py` and
  `src/argus/domain/usage_limits.py`.
