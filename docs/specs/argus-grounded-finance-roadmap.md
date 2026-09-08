# Argus Grounded Finance Roadmap

Status: **ACTIVE — this is the execution board.** Opened 2026-09-05.

Supersedes [`argus-active-roadmap.md`](argus-active-roadmap.md), whose landed
work and secondary tracker state remain valid history. Read
[`docs/PRODUCT.md`](../PRODUCT.md) first; nothing here changes its locked scope
or its audience.

---

## Why this board exists

The previous board opened on 2026-08-06 with the right diagnosis: *users are
lost at the first question, before reaching the thing Argus is actually good
at.* Item 1, "Answer the first question," shipped to production on 2026-08-11.
It worked. Argus answered ordinary finance questions in both languages without
refusing.

**On 2026-08-12 Argus was distributed to roughly twenty people, and they were
refused anyway.**

The fix covered the wrong first question. It was scoped from a competitor
review, which said users arrive wanting a research read. Real users arrived
with their own money: a salary, expenses, a goal with a price on it. The
research rail answers market questions. It has five shapes, all market-facing,
and none of them is "how much should I save for an iPad."

That is the mistake this board exists to not repeat. The last diagnosis came
from a competitor. This one comes from the twenty transcripts.

### What those twenty people actually did

Recorded in
[`2026-08-12-personal-money-questions-and-teaching-the-methodology.md`](../superpowers/specs/2026-08-12-personal-money-questions-and-teaching-the-methodology.md),
founder-authored the same day.

- A user gave Argus a salary, stated expenses, and a priced goal, which is the
  richest input a personal finance product can receive, and Argus declined it
  and described a capability she had not asked about.
- She then wrote two unprompted suggestions, which are the same request twice:
  Argus does not teach people how to talk to it.
- An amount stated in pesos was carried with no currency concept, so thirteen
  thousand Dominican pesos would render as thirteen thousand dollars, wrong by
  a factor of about sixty five, silently, in a product about money.
- Feedback from the cohort: users believe Argus is a finance assistant for
  anything. Savings, bonds, banking products. They are not arriving to run a
  backtest.

Twenty two issues were filed from that one day. **Twenty one are closed.** The
defect debt is paid. What is not paid is the shape debt: the question shapes
Argus still refuses.

Thirty days of production usage since: 111 guest messages, 62 from
`developer@argus.local`, 51 canary, 9 from named humans of which 8 are the
founder's own accounts. **One message from one other person.** Every defect
fixed in that window was found by reading our own code.

### The market evidence

A Dominican finance influencer, 2026-09-05, answering a follower:

> Two million pesos invested for one year in a high yield account, gain of
> about 120,000 at 6 percent. In a *mutuo*, about 210,000 at 10.5 percent. In
> an investment fund, about 170,000 at 8.5 percent. It all depends on the
> instrument, the rate, the term and the conditions. Comment for more
> information.

This is the product, posted by a person instead of a machine. Note what it is
and is not:

- It is a **comparison over local instruments** with the follower's own amount.
- The rates are **asserted, not cited**. Nobody knows where 10.5 percent came
  from or whether it is current.
- The math is **simple interest**, no compounding, no tax treatment, no fees.
- The **risk difference is waved at** rather than shown. A *mutuo* at 10.5 is
  not a bank account at 6.
- There is **no counterfactual**. None of the three is compared to the market.
- The call to action is **comment and wait**.

Argus can answer that question with cited rates, real compounding, the tax and
risk difference named, the counterfactual attached, and no waiting. That is the
whole thesis in one post.

---

## Thesis

**Argus is a grounded finance calculator. The backtest is the first calculation
it learned, and it is where the other answers end up.**

This is a generalization, not a pivot. `PRODUCT.md` stays locked: same north
star, same three segments, same out-of-scope list. Personal money math is not
in that list and never was.

### Enumerate the math, not the questions

The questions are infinite. "How much should I save for an iPad" and "what do I
need to earn for a Porsche" are the same question wearing different clothes:
target amount, cash flow, time horizon, solve for the missing one.

The math underneath is small.

| Primitive | Covers |
| --- | --- |
| **Time value of money**, solved for any unknown | savings goals, affordability, loans, amortization, bonds, CDs, retirement, **DCF and reverse DCF** |
| **Growth and compounding** | projections, real returns |
| **Ratios** | P/E, yield, effective APR, debt to income, expense ratio |
| **Comparison over a set** | product shopping, instrument choice, peer ranking |
| **Historical performance** | the backtest, already built |

Five primitives cover questions nobody has asked yet, including the advanced
end. DCF is time value of money. Reverse DCF is the same equation solved for
growth instead of price.

### Three layers

- **The model maps.** Messy human question onto a primitive; identifies what is
  known and what is missing. This is what models are natively best at, and it
  is the only layer where the surface is open ended.
- **Retrieval supplies facts.** Any parameter, with a citation. A bond's coupon,
  a card's APR, a stock's P/E, an iPad's price in pesos.
- **Our code computes.** Tested, inspectable, in this repository.

### The honesty line

**Nothing is asserted that is not either computed by our own code or cited to a
source.** The model routes and phrases. It never computes and it never claims a
fact.

This is the same rule the engine already lives under, and it is what separates
Argus from a confident chat answer. The founder's boundary from the 2026-08-12
spec still governs the personal cases: **compute what the user gave you, never
prescribe what they should do.**

### Opportunity cost is the universal conversion

Every money question has a counterfactual, and Argus owns the counterfactual.
Every answer can end in "or that money in the market over the same period."
That is what keeps a grounded calculator from being a generic calculator, and
it is why the backtest becomes the destination rather than the entrance.

### We own the entrance and the exit

The brain owns the middle. We control how people learn what to ask and what the
answer looks like when it lands. There is no menu, no skill picker, no
capability catalogue. The classification lives in the model, not in the UI.

---

## Architecture decisions

Locked 2026-09-08. These are the answers agents build against; do not re-derive
them per lane.

**Unchanged.** The runtime spine (interpret, confirm, execute, explain),
Supabase as canonical truth, backend-owned state with the frontend rendering it
rather than inventing it, and the three-service topology.

**A registry layer appears between interpretation and execution.** Today it is
interpret, strategy, engine. It becomes interpret, select a calculation, collect
typed inputs, run a compute kernel, produce an artifact.

**Most calculations run in-process. Only the backtest uses the Workflow.** Time
value of money is microseconds. `argus-backtests` stays the backtest's executor
and new calculations never reach it, so the three-service topology and the
release contract are untouched by everything on this board except item 3's
handoff.

**Artifacts widen past backtest results.** A savings answer has no run and no
job in the backtest sense. The precedent already exists: `chat.research` is a
job kind with no run by design, from #532, and the settle rule has one owner in
`argus.domain.job_settlement`. New calculations follow that seam rather than
minting heavyweight rows for instant work.

**The cheap path inverts the confirm card.** Answer first, inputs shown
underneath and editable, recomputing live. See operating rule 2. This is a new
interaction pattern, not a variant of the confirm card, and `DESIGN.md` owes it
a section.

---

## Vocabulary

Founder-locked for this board. Agents use these words and no synonyms.

- **Primitive** — a tested mathematical relationship. Five of them, listed
  above. Not user facing.
- **Calculation** — a declared unit of work: a name, when to use it, typed
  inputs, a compute function, an output shape. Registered as data.
- **Grounding** — a retrieval that produces cited facts. Costs money per call.
- **Execution** — a backtest run. Costs compute.
- **Compute** — tested arithmetic over inputs already in hand. Costs nothing.
- **The loop** — interpret, collect typed inputs, compute, produce an artifact,
  decide, share. Shared by every calculation.

---

## Operating rules

Founder-locked for this board.

1. **No split brain.** The backtest is the first instance, not an exception.
   Everything general that grew inside it gets lifted into the shared loop
   rather than reimplemented alongside it. A duplicated fact that is tested is
   still duplicated.
2. **Confirmation is earned by cost and ambiguity, never by being a
   calculation.** A backtest confirms because it is expensive and has ambiguous
   parameters. A time-value answer is instant and free, so it answers first and
   shows its inputs underneath, editable, recomputing live. Driving a savings
   question through a confirm card is the friction that killed the funnel the
   first time.
3. **Adding a calculation is one file.** Declaration, compute function, tests.
   If it is more than that, the abstraction failed and the board stops to fix
   it before calculation four.
4. **Retrieval produces typed rows, never prose.** Prose that looks computed is
   the defect class this repo has paid for repeatedly.
5. **Perplexity for facts scattered in prose. APIs for datasets that already
   have structure.** Never use a retriever to reconstruct a table that exists as
   a table.
6. **Money math stays in Python, in this repository, under unit tests.** The
   2026-08-12 math audit found seven arithmetic defects in code we own and can
   test. No remote sandbox. Settled in the spec's section 7.
7. **The interpreter spine is unchanged.** No regex, phrase, or language gate
   before the LLM. Deterministic guardrails after interpretation, recording when
   they fire.

---

## The goalpost

**Pull the real messages from 2026-08-12 out of the database, make them the eval
set, and replay them. When Argus answers them, distribute.**

Not a feeling, a pass or fail, runnable before a single link is sent.

Ten reference answers this board is aimed at. Nine are refused today.

| # | Topic | Question |
| --- | --- | --- |
| 1 | Savings goal | *"¿Cuánto debo ahorrar mensual si gano 38,000 pesos y quiero una iPad?"* |
| 2 | Affordability | *"What do I need to earn to afford a Porsche?"* |
| 3 | Debt payoff | *"I owe 180,000 on the car at 14 percent, is paying extra worth it?"* |
| 4 | Local fixed income | *"¿DOP$1 millón en un bono del Banco Popular?"* |
| 5 | Product shopping | *"Which credit card should I get?"* |
| 6 | Valuation | *"Is Apple expensive at this P/E?"* |
| 7 | Currency | *"¿Ahorro en pesos o en dólares?"* |
| 8 | Inflation | *"Is my savings account actually losing money?"* |
| 9 | Backtest | *"Buy and hold Apple for the last year with $10,000."* Already S-tier. |
| 10 | The boundary | *"Should I put my emergency fund in crypto?"* Compute the drawdown that amount would have taken, show it, stop. No advice. |

Plus the influencer's question, which is number 4 and number 5 combined.

---

## The items

Ordered. The order is load bearing, and each item carries the promotion
checkpoint it ships in.

### 1. Lift the loop — CP4

The loop is proven by one instance and trapped inside it. Extract what is
general; leave what is genuinely backtest-only.

**General, currently trapped in the backtest:**

- the confirm card, as a pattern, not as a required step
- the edit contract, where every requested change is applied or explicitly
  surfaced as not applied, with no third outcome
- field provenance, what the user said versus what we inferred
- the assumptions readout
- the result artifact with the working shown
- Try next, decisions, evidence receipts, sharing

**Genuinely backtest-only:** asset resolution, market calendars, the data fetch,
benchmarks, the engine.

`StrategySummary` becomes what it actually is, the backtest's input type, rather
than the universal one. **Do not force a universal input schema.** The loop is
earned; a universal parameter shape guessed from one example is not.

### 2. The calculation registry — CP4

Data-shaped, the way `capability_registry.py` already works for strategies:
typed data in one home, and the schema, the contract, discovery, and capability
answers all derive from it.

Seven intents collapse to roughly four: explain, calculate, follow up, cannot.
Calculations become data instead of code paths.

**Known cost:** each new calculation moves model-facing surface, so
Never-Violate 12 wants a committed scorecard each time. About $0.20 with the
targeted interleaved A/B, not $1.33 for a suite.

### 3. Time value of money, the first new calculation — CP5

One relationship, solved for any unknown, which is most of consumer finance.
Ships with the inverted shape from operating rule 2: answer first, inputs
visible and editable underneath, recompute live.

Carries currency: **infer the operating currency from geography, let the user
override, and label it in prose.** Cards are out of scope for this item and stay
as they are. At the handoff to a backtest, convert explicitly in the prose, so
the card is honest without being redesigned:

> You would have 45,000 pesos, about $740. Want to see what that would have done
> in an index fund over the same period?

### 4. The refusal log — CP1, live before distribution

Every question the brain cannot map gets recorded, sorted by frequency.

Small, needs no users to build, and it is the difference between the next
distribution writing the roadmap and the founder reading messages by hand. This
board exists because that logging did not.

### 5. Grounded retrieval, local first — CP6

Perplexity domain filtering against a curated list of Dominican finance and bank
sources, plus the location filter that also derives item 3's currency default.

**This is the moat.** A general assistant guesses at a Dominican bank's rate.
Argus cites today's. It is the only item on this board that a larger model
cannot match by being smarter.

Unused capability already paid for: `FRED_API_KEY` is free, present, and has
never run in production. Adding a data source is a tier-2 decision, not an
architecture decision.

### 6. Decisions detach from runs — CP2

Today a decision hangs off a run: `SearchDossierDecision` carries `run_label`,
and the affordance lives in `StrategyResultCard.tsx`, `RunDossierView.tsx`, and
`AssetHistoryRollup.tsx`. All three are backtest objects, so the decision index
can only ever hold backtest decisions.

A decision attaches to a **computation** and carries its inputs, which makes it
re-runnable against reality later:

> You decided in September to put 5,000 a month toward the iPad. It is
> December. Here is where you actually are, and here is what that money would
> have done in the market instead.

A backtest has no follow-up date. A decision does. **This is the retention loop**
the previous board was building as "product memory," keyed to the wrong object,
and it is the best shareable artifact in the product: not "here is a backtest,"
but "here is what I decided and here is the math."

### 7. Sharing, turned on — CP3

Built and dark since 2026-08-10. `ARGUS_EVIDENCE_RECEIPT_SHARING_ENABLED` and
`NEXT_PUBLIC_EVIDENCE_RECEIPT_SHARING_ENABLED` are `false` in `render.yaml` and
the release profile.

**Sharing is the distribution anchor.** Nail the answer, let them send it.
Enabling is a separate founder decision from any merge.

Mobile is a dependency, not a separate pillar: every shared link opens on a
phone. The responsive shell shipped 2026-08-08 in PR #393 and is unconditional,
so this is a verification item rather than a build item. **#422** carries seven
open lower-severity breakpoint findings; check them against a shared receipt
specifically before enabling.

### 8. Teach the methodology — CP6

Both of Johana's suggestions, which are one request stated twice.

- **On arrival**, one line about what Argus does with a question, not only what
  to ask.
- **When a question is too broad**, three specific questions derived from what
  the user actually said, instead of a refusal or one open question.

This is not the menu the roadmap forbids. Three questions derived from their
input are a response to their input. Steal the "try asking" pattern from
competitors' skill cards: one concrete example sentence teaches without becoming
a catalogue.

### 9. Metering follows the new cost shape — CP2

`UsageAllowances` has two hardcoded meters, `messages` and `backtests`. The
windowing underneath is general and good: hour, day, guest session,
`limiting_window`, `available_now`, plus the atomic claim from #544. The
taxonomy is two welded field names.

Both break under this board:

- `messages` becomes the wrong meter. Most calculations are free and instant, so
  metering conversation rebuilds the turn-one wall.
- `backtests` stops being the only expensive thing. **Retrieval becomes the
  dominant variable cost**, because every grounded answer pulls sources. The
  moat and the cost driver are the same thing.

Replace two field names with three operation classes, keeping the windows and
the claim:

| Class | Cost | Metered |
| --- | --- | --- |
| Compute | none | no, unlimited, forever |
| Grounding | per retrieval | yes |
| Execution | per run | yes |

**Positioning that falls out of it: charge for evidence and execution, never for
talking.** A general assistant charges for talking. The free tier gets better
rather than worse, which is an acquisition story instead of a wall.

---

## Promotion checkpoints

The board does not wait for the vision to be complete. Each checkpoint is
cohesive on its own, and cutting them small is cheaper as well as safer:
`eval_measured_code_unchanged` in the promotion gate returns early when a change
cannot reach the measured code, so a checkpoint that does not touch the
interpreter promotes **without a $1.33 live eval run**.

| | Ships | What a user sees | Live eval |
| --- | --- | --- | --- |
| **CP0** | The three fixes already on integration | drawer dates, benchmark gap, retrieval evidence | no |
| **CP1** | Item 4 refusal log, plus #462 | nothing | no |

Checkpoint numbers are cut boundaries, not a running order. The order is in the
rules below.
| **CP2** | Item 9 metering, item 6 decisions detach | nothing, behavior preserving | no |
| **CP3** | Item 7 sharing on, mobile verification | a result can be shared | probably not |
| **CP4** | Item 1 lift the loop, item 2 registry | **nothing, if done right** | yes |
| **CP5** | Item 3 time value of money | the first new capability | yes |
| **CP6** | Item 5 grounding, item 8 teach the method | cited local rates, guided broad questions | yes |

**The ordering rule is distribution, not checkpoint number.** Founder,
2026-09-08: *this initiative is to get Argus outside of its box so I can
distribute again and collect more signal.* Argus has one non-founder message in
thirty days, so nothing on this board earns priority by collecting data sooner.
It earns priority by being required before the next distribution.

That makes **the spine the critical path**: item 1, item 2, item 3, then item 8.
Without them the next distribution repeats 2026-08-12, and the goalpost stays
unreachable.

An earlier draft of this section ranked CP1 first on the grounds that the
refusal log's value scales with how long it has collected. That reasoning is
wrong while nobody is using the product. The refusal log ships **before**
distribution so it is live when signal arrives, not first.

**CP4 ships with nothing else in it.** A pure extraction plus a registry holding
only the calculations that already exist should be invisible. If a user notices
anything at CP4, something went wrong, and that must not be tangled with a new
capability landing in the same promotion.

---

## Canon documents this board changes

To-do items, not background. Each is a real edit owed before or alongside the
item that needs it.

| Document | Change | When |
| --- | --- | --- |
| **`docs/PRODUCT.md`** | Section 1 Product Truth says "speak an investing or trading idea," and section 11 supported AI responsibilities is written around that. Both widen to "bring a money question." **The file is marked locked and only the founder can move it.** The audience does not change, which is what makes this an additive refinement rather than the scope shift the lock forbids. | **Founder-approved 2026-09-08, see decision 7.** The edit itself is still owed before item 1 merges; nothing in the spine ships against the old Product Truth. |
| **`docs/ARCHITECTURE.md`** | The registry layer; in-process versus Workflow execution; artifacts without runs. | With item 2. |
| **`docs/API_CONTRACT.md`** | Calculation request and response shapes; the allowance response going from two meters to three operation classes. | With items 2 and 9. |
| **`docs/DATA_MODEL.md`** | Artifacts beyond backtest results; decisions carrying inputs and detaching from `run_label`. | With items 3 and 6. |
| **`.agent/designs/argus/DESIGN.md`** | The answer-first-then-editable-inputs pattern from operating rule 2. | With item 3. |
| **`AGENTS.md`** | Operating rules 1 through 7 become permanent repository rules rather than board rules. A board is superseded; these should outlive it. | Any time after item 1 proves rule 1 holds. |

---

## Privacy and terms

**The paperwork is end-stage. One decision is not.**

Personal money math means users type **salary, expenses, and debts**. That is
materially more sensitive than "backtest AAPL," and the current posture was
written for market questions.

- **Day one, DECIDED 2026-09-08, see decision 8:** figures a user states about
  their own finances are ephemeral facts. They live in the conversation and
  never reach personalization memory. Item 3 is unblocked. Original framing
  kept below because the reasoning still governs new surfaces. Personalization
  memory already carries a categorical never-store list, covering broker
  credentials and raw conversation. Stated personal financial figures either
  join that list or get an explicit, recorded decision. This changes what gets
  built, so it cannot be deferred to a legal pass.
- **End stage, before distribution:** privacy policy text describing what is
  collected, retained and deleted for personal money questions.
- **One review, not one per feature:** terms. Ranking financial products leans
  harder on the existing not-advice framing than backtesting ever did. Decision
  6 below, rank by a visible computed number and never by a recommendation, is
  what keeps that review short.

The legal cookie and storage inventory work concluded Argus needs no consent
banner. Nothing on this board changes that, because none of these items adds
third-party storage in the browser.

---

## Decisions

Answered 2026-09-08. Recorded here so agents do not re-open them per lane.

**1. Personal money math is neither a sixth rail shape nor a separate surface.**
It is a calculation in the registry, and the rail's five existing shapes become
five more calculations. The question only exists while the backtest and the rail
are two machines; item 2 dissolves it.

**2. Beginner before trader.** Every user Argus has ever had is a non-finance
person. The trader cohort is hypothetical. This costs nothing at the advanced
end later, because time value of money serves the beginner and reverse DCF
serves the trader and they are the same primitive.

**3. Measure latency before setting a budget.** #462 first. Working target,
subject to what the measurement says: compute answers under one second to first
token, grounded answers under four. A backtest is slow and tolerated because it
is visibly working; a time-value answer that takes four seconds breaks the
calculator promise.

**4. When Argus cannot ground something it returns a typed unverified state,
never prose.** The answer shows the computation with the missing input named and
empty: "I could not verify the current rate at Banco Popular. Give me the rate
and I will run it." That obeys the honesty line, is a designed answer rather
than a failure mode, and converts instead of dead-ending. Research was one
hundred percent down for three days in this repository's recent history and
nobody noticed; that must not be reachable again from a path this common.

**5. The registry declares typed facts and copy renders from them.** No
hand-written prose per calculation, in either language, ever. This is operating
rule 4 applied at the output boundary, and it is the only version where the
bilingual cost does not compound across calculations. See #434, #489, #527,
#507.

**6. Rank by a visible computed number, never by a recommendation.** "Lowest
effective annual cost for your stated spend" is arithmetic. "Best card for you"
is advice. A copy rule, not an architecture one, and it is what keeps the terms
review short.

**7. `PRODUCT.md` section 1 and section 11 widen. Founder-approved
2026-09-08.** Section 1's Product Truth becomes, subject to founder wording at
edit time: *Argus is the easiest place to bring a money question and get an
answer you can check. Every answer is computed from real data or cited to a
source, and the ones that can be tested against history end in a backtest.* The
audience does not change, which is what makes this an additive refinement rather
than the scope shift the lock forbids. What this implies for guest mode and the
empty state is deliberately deferred to item 8 rather than settled here.

**8. Stated personal figures are ephemeral facts. Founder-approved
2026-09-08.** A salary, an expense, or a debt the user types lives in the
conversation like any other message, because it is inside a message and dropping
it would break the conversation. It never travels further: it joins the
categorical never-store list for personalization memory, alongside broker
credentials and raw conversation. No new storage, no new retention surface, and
item 3 is unblocked.

### Still open

**Which Dominican sources go in the domain list, and who maintains it.** Founder
supplies these when item 5 starts. The mechanism does not wait on the complete
list: seed it with the banks users actually named, and let the refusal log from
item 4 grow it. Spec section 10, question 3.

---

## Deliberately not doing

- **Voice.** It changes how people talk to Argus before what happens when they
  talk to it is fixed.
- **Memory beyond what is already built and dark.** Bigger surface, real privacy
  weight, two gates. Bundling it with currency delays currency by something ten
  times its size.
- **Congressional trade tracking.** STOCK Act filings are messy PDFs normalized
  by third parties. The tail of a feature, not the feature. SEC EDGAR Form 4 and
  13F are free, structured, and keyless if insider data is wanted first.
- **Bank API integrations.** A thesis, not a lane, per the spec's section 7. It
  brings a regulatory posture, a security surface, a consent model, and a
  support burden that do not exist today.
- **A universal input schema**, until two calculations exist to derive it from.
- **A skill grid or capability menu.** The classification lives in the model.
- **Card currency rendering.** Item 3 covers prose only.
- **Product memory as Idea and IdeaVersion.** The `DecisionNote` is the part
  worth keeping; the scaffolding around it is backtest-shaped.

---

## Carried forward from the previous board

- Landed work and the secondary tracker state in
  [`argus-active-roadmap.md`](argus-active-roadmap.md) remain valid history.
- **Mobile shipped**, 2026-08-08, and is not a gate. It becomes a verification
  dependency of item 7.
- **Sharing is built and dark**, and is promoted from item 5 on that board to
  the distribution anchor on this one.
- **#462** carries forward, and is now decision 3's blocking measurement.
- The five research rail shapes stay. They become five of the calculations,
  not a separate system.
