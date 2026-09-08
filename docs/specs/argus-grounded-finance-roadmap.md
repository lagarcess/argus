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
at.* Lift the loop, "Answer the first question," shipped to production on 2026-08-11.
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

## The work is subtractive

Argus does not refuse because it lacks intelligence. It refuses because we put
guardrails in front of one that already reasons about money perfectly well. The
guardrails were correct when the product was a backtester. They are what keeps
it in the box now.

**So this board mostly removes things.** Where an item says "build," check first
whether the capability already exists and is being blocked.

What comes off, and what replaces it:

| Guardrail today | Why it exists | What replaces it |
| --- | --- | --- |
| `unsupported_or_out_of_scope` as the catch-all for every non-backtest turn | the only machine was the backtest | a calculation from the registry, or an honest boundary with the computation still shown |
| `unsupported_admission.py`, 598 fingerprinted lines of typed guards | keeping the interpreter from promising strategies the engine cannot run | keeps its job for **strategy templates**; stops standing in for "Argus does not do that" generally |
| The five rail shapes as the only non-backtest answers | the rail was bolted beside the backtest | five calculations in one registry |
| Six Perplexity parameters sent of twenty available | nobody widened it after the first integration | retrieval, which is configuration, not construction |

The capability clause the interpreter reads is already **generated from the
canonical registry** (`unsupported_admission.requested_strategy_template_capability_clause`).
That is the seam: widen the registry and the model-facing text widens with it,
rather than being hand-edited.

**The test for any lane on this board:** if the change adds a rule the model
could have followed on its own, it is probably wrong. We supply math, facts, and
boundaries. The model supplies judgment.

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
release contract are untouched by everything on this board except the calculations's
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
8. **Never enumerate questions.** Enumerate math, and let the model map. A lane
   that adds a branch for a specific question shape, a keyword, or a named
   scenario has built the next refusal. The smoke test in the goalpost is how we
   check the general mechanism, never a list to satisfy one at a time.
9. **Loosen before you build.** Where a capability appears missing, first prove
   it is not simply blocked. See "The work is subtractive."


---

## The goalpost

**Distribute again, to people who are not us, with a product that answers what
they actually bring.**

### Acceptance is behavioral, not a list

The ten questions below are a **smoke test, not the scope.** Building for a list
guarantees the eleventh question, asked in a shape nobody anticipated, breaks
the product. That is the mistake this board already made once: the previous
board scoped turn one from a competitor review and shipped a fix for the wrong
first question.

Acceptance is this:

> A money question in a shape nobody wrote down lands on a primitive, gets
> computed or honestly bounded, and never returns a refusal that names a
> capability the user did not ask about.

The smoke test is how we check it, and every one of the ten must pass. But a
lane that satisfies a listed question by special-casing it has failed, and a
reviewer should reject it on operating rule 8.

### The smoke test

| # | Topic | Question | Primitives |
| --- | --- | --- | --- |
| 1 | Savings goal | *"¿Cuánto debo ahorrar mensual si gano 38,000 pesos y quiero una iPad?"* | TVM + retrieval |
| 2 | Affordability | *"What do I need to earn to afford a Porsche?"* | TVM + retrieval |
| 3 | Debt payoff | *"I owe 180,000 on the car at 14 percent, is paying extra worth it?"* | TVM + comparison |
| 4 | Local fixed income | *"¿DOP$1 millón en un bono del Banco Popular?"* | TVM + retrieval |
| 5 | Product shopping | *"Which credit card should I get?"* | comparison + retrieval |
| 6 | Valuation | *"Is Apple expensive at this P/E?"* | ratios + retrieval |
| 7 | Currency | *"¿Ahorro en pesos o en dólares?"* | growth + comparison + retrieval |
| 8 | Inflation | *"Is my savings account actually losing money?"* | growth + retrieval |
| 9 | Backtest | *"Buy and hold Apple for the last year with $10,000."* | historical |
| 10 | The boundary | *"Should I put my emergency fund in crypto?"* | historical; compute the drawdown, show it, stop |

Plus the influencer's post from the section above, which is 4 and 5 combined
and is the one a real Dominican audience is already asking a human.

**Also replay the real 2026-08-12 transcripts.** They are in the database, they
are what actual users typed, and none of them was written by us.

---

## The items

Each item carries what done means, the surface it may touch, what it must not
touch, and the proof it owes. A dispatch is a pointer to the item; the agent
should need nothing else.

Checkpoint tags are cut boundaries. The running order is in the checkpoints
section.

---

### Lift the loop  ·  ships in **The spine**

The loop is proven by one instance and trapped inside it. Extract what is
general; leave what is genuinely backtest-only.

**General, currently trapped:** the confirm card as a pattern rather than a
required step; the edit contract, where every requested change is applied or
explicitly surfaced as not applied with no third outcome; field provenance, what
the user said versus what we inferred; the assumptions readout; the result
artifact with the working shown; Try next, decisions, evidence receipts,
sharing.

**Genuinely backtest-only:** asset resolution, market calendars, the data fetch,
benchmarks, the engine.

**Done means.** A second calculation can reach confirm, edit, provenance,
disclosure, and artifact rendering without importing anything from the backtest,
and the backtest still routes through the same code with byte-identical
behavior. `StrategySummary` is documented and used as the backtest's input type,
not the universal one.

**Surface.** `src/argus/api/chat/confirmation.py`,
`src/argus/agent_runtime/artifact_edit_planner.py`,
`src/argus/agent_runtime/stages/interpret_internal/`,
`src/argus/agent_runtime/state/models.py`, and the web confirm and result
components.

**Do not touch.** No universal input schema. The loop is earned by one instance;
a parameter shape guessed from one example is not. No model-facing text: this
extraction must leave `.agent/interpreter_prompt_fingerprint.json` unchanged.

**Proof.** The fingerprint is byte-identical before and after. The existing
backtest suite passes unchanged. A throwaway second calculation, not shipped,
demonstrates the loop is reachable without backtest imports.

**Scoping first.** Size is unknown and the extraction is the largest thing on
this board. A read-only pass returns the seam and a number before any code.

---

### The registry  ·  ships in **The spine**

Data-shaped, the way `capability_registry.py` already works for strategies:
typed data in one home, and the schema, the runtime contract, discovery, and
capability answers all derive from it.

A calculation declares four things: a name and when to use it, typed inputs, a
compute function, an output shape. Everything else, extraction, the confirm
surface, the edit contract, provenance, disclosure, localization, reads the
declaration.

**Done means.** Adding a calculation is one file. The seven intents collapse to
roughly four: explain, calculate, follow up, cannot. The five existing rail
shapes are registered as calculations rather than a parallel system. The
interpreter's capability text is generated from the registry, extending the
mechanism `unsupported_admission.requested_strategy_template_capability_clause`
already uses, never hand-written per calculation.

**Surface.** `src/argus/domain/capability_registry.py`,
`src/argus/agent_runtime/llm_interpreter_types.py`,
`src/argus/agent_runtime/state/models.py`,
`src/argus/agent_runtime/interpreter/unsupported_admission.py`.

**Do not touch.** `unsupported_admission` keeps its job for strategy templates.
It stops being the catch-all for "Argus does not do that."

**Proof.** A committed scorecard, because `llm_interpreter_types.py` is
fingerprinted. Targeted interleaved A/B where the change is bounded, about
$0.20; a full suite where it is not. Plus a test that registering a calculation
requires exactly one new file.

---

### The five calculations  ·  ships in **The calculations**

The board schedules all five, not one. Four of the smoke-test questions need
ratios or comparison, and shipping only time value of money leaves the goalpost
unreachable.

| Primitive | Ships |
| --- | --- |
| **Time value of money**, any unknown | first; proves the registry |
| **Growth and compounding** | with TVM; they share inputs |
| **Ratios** | second |
| **Comparison over a set** | second; consumes retrieved rows |
| **Historical performance** | already built; registered, not rebuilt |

**Done means.** Each is one file: declaration, compute function, tests. Each
carries the inverted shape from operating rule 2: answer first, inputs shown
underneath and editable, recomputing live. Each ends with the counterfactual
offer where one applies. Comparison takes retrieved rows and a computed ranking
key; it never ranks by recommendation. See decision 6.

**Currency.** Infer the operating currency from geography, let the user
override, label it in prose. Cards stay as they are. At a handoff to a backtest
the prose converts explicitly, so the card is honest without being redesigned.

**Surface.** New calculation files, the registry, and the compute kernels.
Money math stays in Python in this repository under unit tests; operating rule
6.

**Do not touch.** No branch for a named scenario. A Porsche and an iPad are the
same calculation. Operating rule 8.

**Proof.** Unit tests per primitive against worked examples. The smoke test's
ten questions answered end to end, in both languages, with browser evidence. A
committed scorecard for the model-facing surface.

---

### Refusal log  ·  ships in **Instrumentation**

Every question the model cannot map, and every boundary Argus states, recorded
with what was asked and which primitive was missing.

**Done means.** A refusal is a typed record, not a log line, queryable by
frequency. #314's rejected artifact actions land in the same place; it is the
same instrumentation.

**Surface.** `src/argus/observability/`, the unsupported path, the recovery
messages surface.

**Do not touch.** No user-visible change. No model-facing text.

**Proof.** A refusal produced in a test appears in the record with its shape.
No live eval required, because nothing reaches the measured code.

**Timing.** Not first for its own sake. It ships before distribution so it is
collecting when signal arrives.

---

### Retrieval parameters  ·  ships in **Grounding**

**This item is configuration, not construction.** Argus calls
`https://api.perplexity.ai/v1/agent` with six parameters. The endpoint accepts
twenty.

Unused today: `response_format` with a strict `json_schema`;
`web_search.search_domain_filter`, capped at 20 domains; `user_location` with
city, country, latitude, longitude and region; `search_recency_filter`;
`search_context_size`; `language_preference`; `instructions`; the
`people_search` tool; `skills`, up to 16; `models`, up to 5 for fallback;
`previous_response_id` for continuity.

**The one that matters most is `response_format: json_schema`.** Operating rule
4 says retrieval produces typed rows and never prose. That is a parameter we are
not sending, and #545, publisher URLs stranded in prose with no typed sources,
is what not sending it causes.

`search_domain_filter` is the local moat and its 20-domain ceiling is the real
constraint on the source list. `user_location` derives the calculations's currency default.

**Done means.** Retrieved facts arrive as typed rows with citations, never as
prose to be re-parsed. Domain filtering and location are configured per
question shape. #404 and #545 close.

**Surface.** `src/argus/domain/research/perplexity_agent.py`,
`config.py`, `source_selection.py`, `contracts.py`.

**Do not touch.** The `sandbox` tool. Perplexity offers code execution and the
2026-08-12 spec section 7 already ruled it out: money math stays in Python where
it can be unit tested. There is no SEC tool on the Agents API; `search_mode:
sec` belongs to Sonar chat completions, which we do not use.

**Proof.** A recorded response showing typed rows under a strict schema. A
domain-filtered call citing a local source. Founder supplies the Dominican
domains when this starts; seed from banks users actually named.

---

### Decisions  ·  ships in **Plumbing**

Today a decision hangs off a run: `SearchDossierDecision` carries `run_label`,
and the affordance lives in `StrategyResultCard.tsx`, `RunDossierView.tsx`, and
`AssetHistoryRollup.tsx`. All three are backtest objects, so the decision index
can only ever hold backtest decisions.

**Done means.** A decision attaches to a computation and carries its inputs, so
it can be re-run against reality later. Any computed answer offers it, not only
a result card.

> You decided in September to put 5,000 a month toward the iPad. It is
> December. Here is where you actually are, and here is what that money would
> have done in the market instead.

A backtest has no follow-up date. A decision does. This is the retention loop
the previous board was building as product memory, keyed to the wrong object,
and it is the best shareable artifact in the product.

**Surface.** `src/argus/api/schemas.py`, the memory store, search candidates,
and the web decision components.

**Do not touch.** The Idea and IdeaVersion scaffolding. The `DecisionNote` is
the part worth keeping.

**Proof.** A decision recorded against a non-backtest computation, retrieved,
and re-run with changed inputs. Behavior-preserving for existing decisions.

---

### Sharing on  ·  ships in **Sharing**

Built and dark since 2026-08-10. `ARGUS_EVIDENCE_RECEIPT_SHARING_ENABLED` and
`NEXT_PUBLIC_EVIDENCE_RECEIPT_SHARING_ENABLED` are `false` in `render.yaml` and
the release profile.

**Sharing is the distribution anchor.** Nail the answer, let them send it.

**Done means.** A shared receipt opens correctly for a signed-out visitor on a
phone. Enabling is a separate founder decision from any merge.

**Surface.** Flags and QA. Little or no code.

**Do not touch.** Guest sharing and forking stay out of scope per the sharing
spec.

**Proof.** Browser evidence of a shared receipt at mobile and desktop widths.
The responsive shell shipped 2026-08-08 in PR #393 and is unconditional, so this
is verification rather than build. **#422** carries seven open lower-severity
breakpoint findings; check them against a shared receipt specifically.

---

### Teach the method  ·  ships in **Grounding**

Both of Johana's suggestions, which are one request stated twice.

- **On arrival**, one line about what Argus does with a question, not only what
  to ask.
- **When a question is too broad**, three specific questions derived from what
  the user actually said, instead of a refusal or one open question.

**Done means.** A broad question returns derived follow-ups, never a catalogue.
The guest empty state states the method in one line.

**Surface.** `src/argus/agent_runtime/llm_clarifier.py`, the empty state, the
starter chips.

**Do not touch.** No skill grid, no capability list, no picker. Three questions
derived from the user's input are a response to their input; a menu shown
regardless of input is what `PRODUCT.md` forbids. Borrow the "try asking"
pattern of one concrete example sentence, never the grid.

**Proof.** A committed scorecard; `llm_clarifier.py` is fingerprinted. Browser
evidence in both languages.

---

### Metering  ·  ships in **Plumbing**

`UsageAllowances` has two hardcoded meters, `messages` and `backtests`. The
windowing underneath is general and good: hour, day, guest session,
`limiting_window`, `available_now`, plus the atomic claim from #544. The
taxonomy is two welded field names.

Both break here. `messages` becomes the wrong meter, because most calculations
are free and instant and metering conversation rebuilds the turn-one wall.
`backtests` stops being the only expensive thing: **retrieval becomes the
dominant variable cost**, so the moat and the cost driver are the same thing.

| Class | Cost | Metered |
| --- | --- | --- |
| Compute | none | no, unlimited, forever |
| Grounding | per retrieval | yes |
| Execution | per run | yes |

**Charge for evidence and execution, never for talking.** A general assistant
charges for talking. The free tier gets better rather than worse, which is an
acquisition story instead of a wall.

**Done means.** The meter is keyed by operation class. #546 closes. Existing
guest and daily behavior is preserved for execution.

**Surface.** `src/argus/api/schemas.py`, `src/argus/api/chat/allowance.py`,
`src/argus/api/guest_access.py`, `routers/profile.py`.

**Do not touch.** The windows and the atomic claim. Replace field names, keep
the machinery.

**Proof.** Behavior-preserving for backtests: a guest still gets the same
execution allowance. Compute operations never decrement anything. No live eval
required.

---

## Releases

The board does not wait for the vision to be complete. Each checkpoint is
cohesive on its own, and cutting them small is cheaper as well as safer:
`eval_measured_code_unchanged` in the promotion gate returns early when a change
cannot reach the measured code, so a checkpoint that does not touch the
interpreter promotes **without a $1.33 live eval run**.

| Release | Ships | What a user sees | Live eval |
| --- | --- | --- | --- |
| **The fixes** | three bug fixes already on integration | drawer dates, benchmark gap, retrieval evidence | no |
| **Instrumentation** | refusal log, plus #462 latency | nothing | no |

Release names are cut boundaries, not a running order. The order is in the
rules below.
| **Plumbing** | metering, decisions | nothing, behavior preserving | no |
| **Sharing** | sharing on, mobile verification | a result can be shared | probably not |
| **The spine** | lift the loop, the registry | **nothing, if done right** | yes |
| **The calculations** | the five calculations | Argus answers money questions it used to refuse | yes |
| **Grounding** | retrieval parameters, teach the method | cited local rates, guided broad questions | yes |

**The ordering rule is distribution, not checkpoint number.** Founder,
2026-09-08: *this initiative is to get Argus outside of its box so I can
distribute again and collect more signal.* Argus has one non-founder message in
thirty days, so nothing on this board earns priority by collecting data sooner.
It earns priority by being required before the next distribution.

That makes **the spine the critical path**: lift the loop, the registry, the calculations, then teach the method.
Without them the next distribution repeats 2026-08-12, and the goalpost stays
unreachable.

An earlier draft ranked instrumentation first on the grounds that the
refusal log's value scales with how long it has collected. That reasoning is
wrong while nobody is using the product. The refusal log ships **before**
distribution so it is live when signal arrives, not first.

**The calculations may be two promotions.** Time value of money and growth ship together and
prove the registry; ratios and comparison follow. Splitting them is allowed and
the checkpoint table stays one row, because the cut is cohesive either way: each
half is a set of primitives, not half a primitive.

**The spine ships with nothing else in it.** A pure extraction plus a registry holding
only the calculations that already exist should be invisible. If a user notices
anything in the spine release, something went wrong, and that must not be tangled with a new
capability landing in the same promotion.

---

## Canon documents this board changes

To-do items, not background. Each is a real edit owed before or alongside the
item that needs it.

| Document | Change | When |
| --- | --- | --- |
| **`docs/PRODUCT.md`** | Section 1 Product Truth says "speak an investing or trading idea," and section 11 supported AI responsibilities is written around that. Both widen to "bring a money question." **The file is marked locked and only the founder can move it.** The audience does not change, which is what makes this an additive refinement rather than the scope shift the lock forbids. | **Founder-approved 2026-09-08, see decision 7.** The edit itself is still owed before lift the loop merges; nothing in the spine ships against the old Product Truth. |
| **`docs/ARCHITECTURE.md`** | The registry layer; in-process versus Workflow execution; artifacts without runs. | With the registry. |
| **`docs/API_CONTRACT.md`** | Calculation request and response shapes; the allowance response going from two meters to three operation classes. | With the registry and metering. |
| **`docs/DATA_MODEL.md`** | Artifacts beyond backtest results; decisions carrying inputs and detaching from `run_label`. | With the calculations and decisions. |
| **`.agent/designs/argus/DESIGN.md`** | The answer-first-then-editable-inputs pattern from operating rule 2. | With the calculations. |
| **`AGENTS.md`** | Operating rules 1 through 7 become permanent repository rules rather than board rules. A board is superseded; these should outlive it. | Any time after lift-the-loop proves rule 1 holds. |

---

## Privacy and terms

**The paperwork is end-stage. One decision is not.**

Personal money math means users type **salary, expenses, and debts**. That is
materially more sensitive than "backtest AAPL," and the current posture was
written for market questions.

- **Day one, DECIDED 2026-09-08, see decision 8:** figures a user states about
  their own finances are ephemeral facts. They live in the conversation and
  never reach personalization memory. The calculations are unblocked. Original framing
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
are two machines; the registry dissolves it.

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
empty state is deliberately deferred to teach-the-method rather than settled here.

**8. Stated personal figures are ephemeral facts. Founder-approved
2026-09-08.** A salary, an expense, or a debt the user types lives in the
conversation like any other message, because it is inside a message and dropping
it would break the conversation. It never travels further: it joins the
categorical never-store list for personalization memory, alongside broker
credentials and raw conversation. No new storage, no new retention surface, and
the calculations are unblocked.

### Still open

**Which Dominican sources go in the domain list, and who maintains it.** Founder
supplies these when retrieval starts. The mechanism does not wait on the complete
list: seed it with the banks users actually named, and let the refusal log grow it. Spec section 10, question 3.

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
- **Card currency rendering.** The calculations covers prose only.
- **Product memory as Idea and IdeaVersion.** The `DecisionNote` is the part
  worth keeping; the scaffolding around it is backtest-shaped.

---

## Carried forward from the previous board

- Landed work and the secondary tracker state in
  [`argus-active-roadmap.md`](argus-active-roadmap.md) remain valid history.
- **Mobile shipped**, 2026-08-08, and is not a gate. It becomes a verification
  dependency of sharing.
- **Sharing is built and dark**, and is promoted from retrieval on that board to
  the distribution anchor on this one.
- **#462** carries forward, and is now decision 3's blocking measurement.
- The five research rail shapes stay. They become five of the calculations,
  not a separate system.
