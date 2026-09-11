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
at.* Its first item, "Answer the first question," shipped to production on
2026-08-11.
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

**Our interpreter is the brain. Perplexity is the eyes. Our Python is the
hands.** Decided 2026-09-08 after the alternative was examined seriously.

Perplexity's Agents API exposes `function` and `mcp` tool types, so its agent
could in principle call our calculators and orchestrate the whole loop. It
should not, for three measured reasons.

- **Cost runs the wrong way.** Tier 3 is `x-ai/grok-4.3` with
  `anthropic/claude-haiku-4.5` behind it, and a structured call there is a
  fraction of a cent. Perplexity Agents runs `openai/gpt-5.6-sol` at up to ten
  steps on `thorough`, priced per token. Moving reasoning to Perplexity moves it
  from the cheap model to the expensive one.
- **It would bill every money question**, including the ones needing no facts at
  all. "If I save 5,000 a month for nine months, what do I have" is one grok
  call and microseconds of Python today. As an agent run it is a loop with
  steps.
- **It breaks decision 3.** Compute answers under one second to first token. An
  agent loop cannot do that; the `thorough` shape already carries a
  600-second background deadline.

The turn already hits the interpreter on every turn, so that cost is the
existing baseline rather than an addition. Retrieval is what is additive, and it
is paid only when a fact is actually needed. Cheap calculations never leave the
process.

Perplexity is still shaped precisely, through `instructions` and
`response_format`. It is simply not paid to think about arithmetic we own.

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
3. **Adding a calculation is a declaration, a compute function, tests, and a
   card.** The 2026-09-08 scout disproved the one-file version: the result
   artifact is backtest by content at every layer, card, readout, explain,
   followups, breakdown and chart, so only the message envelope transfers and a
   time-value answer needs its own card. Four artifacts is the bar. If it grows
   past that, the abstraction failed and the board stops before calculation
   four.
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

### How acceptance is actually checked

Two sets, and the second is the one that counts.

- **The smoke test above is visible.** Anyone building can read it, which means
  it can be gamed by special-casing. It catches obvious failure, not overfit.
- **The held-out set is the real 2026-08-12 transcripts.** Roughly twenty
  people, all guests, all non-finance, and **none of it written by us or for
  this purpose.** It predates the board, so it cannot have been designed
  against. Pull it from the database, replay it, and read what happens.

A release is accepted when its own proof in the item passes **and** the
held-out replay shows no refusal that names a capability the user did not ask
about.

Nobody on a lane writes new acceptance questions. If a lane needs a question
that is not in either set, that is a signal the lane is enumerating.

---

## What is running right now

Dispatched 2026-09-08 from integration `00331188`. Seven lanes, all disjoint
except one pair. **Nothing has landed yet.**

| Lane | Kind | Model | Notes |
| --- | --- | --- | --- |
| Lift the loop, Lane A relocation | build | Opus 5 | sent first; the `confirmation.py` window was open |
| Refusal log | build | GPT Astra | |
| Metering | build | Fable 5.1 | **overlaps decisions on `schemas.py`** |
| Decisions | build | Fable 5.1 | **overlaps metering on `schemas.py`** |
| Retrieval parameters | build | Fable 5.1 | |
| Sharing on | verification | GPT Astra | already built and dark; no build expected |
| #462 latency | measurement | GPT Astra | measure only, optimize nothing |

**Before landing metering and decisions**, do a real
`git merge --no-commit --no-ff` in a throwaway worktree. Do not read the
file-overlap list and do not trust `git merge-tree`: `grep -c` inside `$(...)`
has returned blank rather than 0 in this repo and cost a wrong call.

**Observed 2026-09-08, 21:15Z, at integration `2846b421`.** Only the board doc
has landed since the dispatch base, so every lane is still effectively current
and none needs a rebase.

| Lane | Where it actually is |
| --- | --- |
| Lift the loop, Lane A | **LANDED** `f7c9192b`, PR #560. |
| Refusal log | **LANDED** `fa69466c`, PR #559. |
| Metering | **LANDED** `1db1aa75`, PR #561. Guest compute ceiling is silent and anti-abuse, 300 per UTC day, never projected in `/me/usage`; `PRODUCT.md` §19 amended. |
| Decisions | **LANDED** `67facaf5`, PR #564. Four rounds, each returning one finding at the head; the last two were the same fact-ownership defect at successive layers, the durable stamp then the component copy. `decision_notes` owns both. |
| Retrieval parameters | **LANDED** `41bf9930`, PR #562. The prose-versus-rows verifier was deleted rather than widened, and the row rejection and `_withheld_code` that replaced it were deleted in turn on 2026-09-10 (open the gates): they withheld paid quotes whenever the model's citation was not the page the response retrieved. A retrieved answer publishes, a row keeps the citation the model wrote, and a figure with no citation is named under the answer. #404 and #545 closed. |
| Sharing on | **Done.** Evidence landed on integration. Only the flag flip remains and the founder has deferred it to the next promotion. |
| #462 latency | **LANDED** `76937883`, PR #563. Its measurement produced the Subtract the guardrails item. |

### The finishing bar every build lane owes

Recorded because the first dispatch omitted it and the founder caught it. A PR
existing is not done. Done is:

- focused tests written by the lane, passing, not merely the existing suite
  still green
- CI green on the exact head, all required checks; the clean-checkout baseline
  is 14 pre-existing failures and those are not the lane's to chase
- a Codex review round completed and cleared at the current head. **A 👍
  reaction is not proof a review ran**; the summary comment is edited in place,
  so the reliable signal is a review comment naming the exact commit SHA
- zero unresolved review threads
- browser evidence in both languages if anything user-visible changed

A lane that hits something contradicting this board stops and says so rather
than working around it.

---

## The items

Each item carries what done means, the surface it may touch, what it must not
touch, and the proof it owes. A dispatch is a pointer to the item; the agent
should need nothing else.

Checkpoint tags are cut boundaries. The running order is in the checkpoints
section.

---

### Lift the loop  ·  ships in **The spine**

**Scoped by a read-only scout, 2026-09-08.** Its findings are recorded inline
below rather than in a separate report.

**The thesis was about half right, and the correction narrows the lane.**

- **The envelopes are general and thin:** the pending-artifact lifecycle, the
  edit disclosure channel, applied-or-unapplied bookkeeping, the Try next row
  contract, and the typed-facts-to-client-copy mechanism.
- **The bodies are backtest:** the confirm stage, card rows, the edit target
  vocabulary and applier, the planner prompt, the contextual merge, the display
  fact vocabulary, Try next composition, and the whole result artifact.

**Two things this board called general are out of scope, on evidence.**

- **Field provenance is not a component.** It is a dict key in
  `extra_parameters` that 35 files agree on by convention, with 24 value strings
  and three readers checking different subsets. Lifting it means building a
  typed model across 35 files, six of them fingerprinted. Not this lane.
- **The result artifact is backtest by content at every layer:** card, readout,
  explain, followups, breakdown, chart. Only the message envelope transfers.
  This is why operating rule 3 now says four artifacts rather than one file.

**The seam the board missed, and why it can wait.** The CONFIRM graph node is
hard-wired to `LaunchBacktestRequest`. Nothing scheduled here confirms, because
operating rule 2 has cheap calculations answering first, so this waits for the
first expensive non-backtest calculation.

**Three lanes, in order.**

- **Lane A, pure relocation.** `confirmation.py` splits three ways: card
  builder, pending-artifact lifecycle, research peer rows, with re-exports so
  test edits stay at zero. `next_experiments.py` and `artifact_edit_planner.py`
  optionally split into contract plus composer. One to two rounds.
- **Lane B, parameterize the pending-artifact lifecycle** and give the web card
  a `kind` discriminator. Two to three rounds. **Optional for the spine.**
- **Lane C, the throwaway proof.** A second calculation driven by a unit
  harness, never merged, run before the registry lane so the registry is
  designed from what the throwaway actually needed. One round.

**Lane C ran 2026-09-08 against `6bc3e0ee`, draft PR #566, never to merge.**
Report and evidence under `docs/reports/lift-loop-lane-c/`. Time value of money
solved for any one of five blanks, 93 tests, 31 fresh-process import probes with
guards that refuse backtest imports rather than stubbing them. Three findings
change this board.

**Relocation did not make the loop reusable.** The open containers hold the five
inputs through real Pydantic round trips with no strategy, symbol, date range or
run id. But `state/models.py:16` imports `capability_registry`, which imports
`STRATEGY_CAPABILITIES`, and `api/schemas.py:30` imports it independently, so the
message envelope cannot be reached without loading the strategy catalog. Lane A
moved code; it did not cut that edge. **Verified independently at the head.**

**The four-artifact bar is unproven, not passed.** Lane C produced four runnable
artifacts, and says plainly that counting them as a passing calculation would
conceal the absent work: no product card, no dispatch, no recompute. Rule 3's
stop condition stays live and this spike does not waive it.

**The bill in the registry is now itemized.** Using the loop as it stands needs
changes at six existing owners: dispatch, pending-card assembly and update, edit
application and disclosure, fact projection and localization, result selection
and hydration, and retry and continuity semantics. The sharpest single blocker
is that nothing dispatches to a cheap calculation at all: the graph has one
backtest tool and `stages/execute.py:50-71` always builds a launch payload
first, so answering first without a confirm card has no path today. That is
operating rule 2 with no runtime behind it.

**Almost nothing moves.** `models.py`, `confirm.py`, `contextual_merge.py` and
the web card stay untouched.

**Do not touch.**

- **`api/state.py:76` pins `state.models` class paths by string** in the
  checkpoint serializer. Those classes must never move or rename.
- **`EditOperation.target` is model-facing schema the fingerprint does not
  see.** It must not widen. This is the one trap that would ship an unmeasured
  behavior change.
- **`artifact_assumption_edit.py` was at 72 of its 75 growth lines before Lane
  B, and the budget config does watch it**, which PR #570 verified rather than
  assumed. That lane extracted the response path and the shared edit-outcome
  adapter, taking it from 1,561 to 1,507 lines, so 57 lines are free again.
- No universal input schema. No model-facing text.

**Proof.** `.agent/interpreter_prompt_fingerprint.json` byte-identical before
and after; none of the five files is in the surface, so this is achievable.
Existing backtest suite passes unchanged. Lane C demonstrates the envelopes are
reachable without backtest imports.

**Blast radius.** 57 source files import `StrategySummary`. 65 test files with
1,663 test functions touch the surface. Re-exports keep Lane A test edits at
zero.

**Size: two mergeable lanes plus one throwaway, about five review rounds.**
Smaller than this board originally assumed. The bill moved to the registry.

**Start Lane A now.** `confirmation.py` has 36 commits in 90 days and zero open
PRs against it, so the window is open and closes the moment another lane opens
on that file.

---

### Subtract the guardrails  ·  ships in **The spine**

**This is the subtractive thesis with a latency payoff nobody counted.** It is
scheduled here because operating rule 2 promises that a cheap calculation
answers first since it is instant, and on a 33-second spine that promise is
false. The calculations lane would build on a runtime that cannot keep it, and
the same audits would then fire on the new calculations too, turning a one-file
change into a retrofit across five cards.

**What is known, and what is not.** Known: every audit and repair runs *after*
`LLMInterpretationResponse` and takes it as input, so they are post-hoc rather
than routing, and each is already gated by an existing predicate
(`_response_needs_capability_side_question_audit`,
`_response_needs_context_question_audit`,
`_strategy_extraction_repair_is_allowed`). Known: they fire on plain
conversation, and the repair's own trigger is
`required_strategy_shape_missing`, a backtest shape that a conversation turn
will never have.

**Not known, and this lane's first job: whether those gates can be narrowed
without losing what they catch.** Nobody has read what each predicate actually
tests, why it admits a conversation turn, or what the audit corrects when it
does fire. The fix may be a tighter predicate, a cheaper check, a reordering, or
for one of them, nothing. **The lane diagnoses before it proposes.** A dispatch
that says "narrow the gates" is a guess; the board does not carry guesses.

**Done means.** Each of the four calls has a written answer to: what does it
catch, what admitted this turn, and what is the smallest change that stops it
firing where there is nothing to check. Then the changes that survive that
answer are made, and ordinary chat first token drops materially against the
#563 baseline. No new machinery, no model-facing text, no fingerprint change.

**The second lever, measure before acting.** The interpretation call itself is
9.45s. At the tier model's 95 tokens per second that is roughly 900 output
tokens, so the cost is the size of the structured response, not the model. Grok
4.3 is already the right choice on this tier: 0.58s first-token latency and 95
tok/s against Haiku 4.5's 0.67s and 48 tok/s at twice the output price, which
would make this call take about 19s. **Do not switch models.** Measure what
shrinking the response schema buys before changing it.

**Surface.** `src/argus/agent_runtime/llm_interpreter.py` and
`src/argus/agent_runtime/interpreter/`.

**Do not touch.** Rule 7 stands: no shortcut routing before the LLM. Nothing here
decides anything ahead of interpretation; it only stops running backtest checks
on interpretations that are not backtests.

**Proof.** The #563 harness re-run, same turn types, before and against the
change. **And a live eval scorecard**, because tightening a gate trades latency
for interpretation accuracy at the edges and that trade has to be shown, not
asserted.

---

### The registry  ·  ships in **The spine**

**It is a tool catalog, not a question classifier.** Founder, 2026-09-08: the
model has a brain, eyes, hands, memory and tools. A user asks something, the
model reasons about it, and it calls the grounded calculators Argus owns. It
does not match a question to a named calculation and fill that calculation's
schema; matching is enumeration one level deeper than operating rule 8 removes
it, and it fails the moment a question needs two tools, or one tool twice, or
none.

So a calculation is declared the way a tool is: what it does, typed arguments,
what it returns. `solve_for_unknown(present_value, payment, rate, periods,
future_value)` with one argument left blank. Nobody declares "the savings goal
calculation," and Johana's question never has to match a name.

Data-shaped, the way `capability_registry.py` already works for strategies:
typed data in one home, and the schema, the runtime contract, discovery, and
capability answers all derive from it.

**Done means.** Adding a calculation is a declaration, a compute function,
tests and a card, per operating rule 3. The seven intents collapse to
roughly four: explain, calculate, follow up, cannot. The five existing rail
shapes are registered as calculations rather than a parallel system. The
interpreter's capability text is generated from the registry, extending the
mechanism `unsupported_admission.requested_strategy_template_capability_clause`
already uses, never hand-written per calculation.

**The progress line is part of the declaration.** Today the seven status
strings are keyed on the graph stage and every one of them is backtest prose:
`chat.status.execute` says "Running backtest...", plus `extracting_strategy`,
`running_backtest` and `calculating_metrics`. Ask a savings question today and
you watch three lies in a row.

The fix is not new copy. A tool declares a **progress template with its typed
arguments interpolated**, the way Claude Code and Codex report the tool that is
actually running rather than asking a model what they are doing:

```
fetch_rate(bank="Banco Popular")   -> "Checking Banco Popular's current rate"
solve_for_unknown(target=45000)    -> "Working out your monthly savings"
run_backtest(asset="AAPL")         -> "Running the Apple backtest"
```

It cannot lie, because it names the call that is executing. No extra model call,
so no latency on a path that must feel instant. No fingerprint surface. And it
is bilingual for free: the template is a locale key and the arguments are typed
facts, which is operating rule 4 doing the work again. The stage-keyed strings
are deleted.

**The receipt renders from the card contract, not from backtest fields.**
Founder, 2026-09-08. Sharing is the distribution lever, and today the only
shareable answer is a backtest, because `web/components/receipt/ReceiptBody.tsx`
reads `receiptPlan`, `receiptAssumptions`, `benchmarkReturn` and
`benchmarkVerdict`. Ship the calculations without this and every new answer is
unshareable on the day it lands. Point the receipt at the same contract the card
renders and sharing generalizes for free, which keeps operating rule 3 at four
artifacts instead of a fifth per calculation. This is the same move Lane A made
on the confirmation envelope. It belongs here, in The spine, because after the
calculations ship it is a retrofit across every card.

**Whole-conversation sharing follows from this, and only from this.**
`docs/specs/conversation-sharing.md` section 9 already holds the design the
founder described: the owner selects turns, only eligible ones are selectable,
one link, one tombstone, revocable. It was sequenced, not rejected, and its
unit is the turn. A thread share is a sequence of turn receipts, so it cannot
exist until a turn that is not a backtest can be a receipt. Section 4.5 now
authorizes selected turns inside one conversation in Share the answer;
composition beyond that remains deferred.

**Surface.** `src/argus/domain/capability_registry.py`,
`src/argus/agent_runtime/llm_interpreter_types.py`,
`src/argus/agent_runtime/state/models.py`,
`src/argus/agent_runtime/interpreter/unsupported_admission.py`.

**Do not touch.** `unsupported_admission` keeps its job for strategy templates.
It stops being the catch-all for "Argus does not do that."

**Proof.** A committed scorecard, because `llm_interpreter_types.py` is
fingerprinted. Targeted interleaved A/B where the change is bounded, about
$0.20; a full suite where it is not.

**This lane carries the bill.** The 2026-09-08 scout found lift-the-loop
smaller than the board assumed and this larger: intent collapse under a
scorecard, a second card component, and a compute-to-message path all land
here.

---

### Let the model write the readout  ·  ships in **its own promotion, after the registry**

**The Quick take and Breakdown a user reads are not written by a model.** Since
PR #551 on 2026-09-05 the web renders both from typed facts through fixed
templates, `web/lib/result-readout-display.ts` and the `chat.result_readout`
strings in the locale files: four sentences for the Quick take, and for the
Breakdown the same four plus a few settings lines and a disclaimer. The model
still writes both on every result, `result_summary` on the chat tier and
`result_breakdown` on the context tier, and `artifact_presentation.py` strips
that text on read as private prose. **Argus pays for an answer nobody sees.**
Founder, 2026-09-10, on a DOCN buy-and-hold result beside Perplexity: the
readout is shallow.

**Why #551 did it.** Saved English results rendered under Spanish chrome (#531,
#530, #528). Hiding model prose fixed the language, and it also removed the only
part of the readout that could say something the card does not.

**The drafts are gated too tight to show as they are.** `explain.py` rejects a
Quick take that quotes any percentage other than total return, the benchmark's
return and the gap between them, so it cannot mention the worst drop, and it
rejects one that does not restate the benchmark comparison. The breakdown
carries the same kinds of checks. The Quick take is handed a few figures while
the engine computes more: annualized return, volatility, Sharpe ratio, worst
drop and costs.

**Done means.** The frames stay exactly as they are. Founder, 2026-09-10: *do
not remove the quick take and breakdown format of the frame, my concern was just
what's inside.* Inside them the model's text shows, written in the workspace
language when the result is created, from every figure the run stored. Checks
keep only what catches a false statement: a quoted figure that is not in the
run, a beat or lag that contradicts it, an internal field name. Checks that force
or cap content go. The templates stay as the fallback when the model fails, and
for results saved before this lane or read in a language other than the one they
were written in, so there is still no read-time model call and no rewritten
history.

**This does not reopen decision 5.** Decision 5 forbids hand-written prose per
calculation, and this lane adds none; the fallback templates already exist. It
is decision 9 at the result: the model writes the answer, Argus owns the
numbers.

**Surface.** `src/argus/agent_runtime/stages/explain.py`,
`src/argus/api/chat/breakdown.py`, `src/argus/api/artifact_presentation.py` with
`src/argus/domain/artifact_prose_fields.json`,
`web/__tests__/private-artifact-prose-boundary.test.ts`,
`web/components/chat/ChatMessage.tsx`, `web/lib/result-readout-display.ts`, both
`common.json` locale files, `docs/API_CONTRACT.md`, and the result surface
ownership rules in `AGENTS.md`.

**Do not touch.** The result card, the frames, their labels and order. No causal
claim about why a price moved; that needs a source and is research. No forecast
or advice language.

**Proof.** `explain.py` is fingerprinted, so a change to its model-facing text
owes a committed scorecard: cost stated first, and a targeted interleaved
comparison on result cases before any full run. Bilingual browser proof on a new
result and on one saved before the lane. And the founder's side-by-side: the
same result question to Argus and to a competitor, where Argus's readout says
something the card does not.

**Unblocked 2026-09-10.** #575, which edits `ChatMessage.tsx` and both locale files,
merged as `129ad084`. Prompt written 2026-09-10, not yet sent.

---

### Home country per user  ·  ships in **its own promotion**

**Founder, 2026-09-10:** one server-wide country for every user is a huge issue
and not state of the art. Argus adapts to each user's own home country, and
personalization means stable declared settings, country and currency (decision
9's condition). Scoped 2026-09-11 from the lane brief held on 2026-09-10, whose
wait on the decision 10 lane ended when #589 landed.

**Today.** `home_location()` in `src/argus/domain/research/config.py` reads
`ARGUS_RESEARCH_HOME_COUNTRY`, and `retrieval_spec()` puts it on every research
request, which `src/argus/domain/research/perplexity_agent.py` sends as
`user_location`. No country or currency exists on the profile, `/me` or
Settings. Personalization memory (#386, #392) stores saved decisions and holds
no country. The variable is not declared in `render.yaml`, so production most
likely sends no location at all.

**The rules.**

- Country is a declared profile setting, ISO 3166-1 alpha-2, chosen by the user
  in Settings like language. Nothing else writes it: never inferred from
  conversation, IP or behavior (decision 8). The picker may pre-select from the
  browser's region; nothing saves until the user picks.
- Currency, ISO 4217, is derived from the country, with an optional user
  override stored the same way. The profile exposes the resolved currency.
- Research sends the asking user's country through the provider's location
  parameter, never through prompt text. A user with no country sends no
  location. A guest has no stored country; the lane reports what a session-only
  pick would cost.
- `ARGUS_RESEARCH_HOME_COUNTRY` and `home_location()` are removed, not kept as a
  fallback.

**Done means.** A registered user picks a country in Settings in English or
Spanish, sees the currency it implies and can override it, and both survive a
reload; a refused save rolls back with a visible error, as language does. A
research question from that user, inline or as a thorough job, carries that
country as the location; a question from a user with none carries no location.
The server-wide setting no longer exists anywhere in the tree.

**Surface.** An additive, nullable migration following
`supabase/migrations/20260809140000_add_preferred_name.sql`. `User`,
`ProfilePatch` and `PATCH /me` (`src/argus/api/schemas.py`,
`src/argus/api/routers/profile.py`), not `GuestUser`, and the runtime's
`UserState`. The Settings picker, saved through `saveProfile` in
`web/lib/profile-writes.ts` beside `web/components/settings/LanguageModal.tsx`
and `web/components/sidebar/ProfileSettingsPanels.tsx`, in both locales.
`retrieval_spec()` and both research paths in
`src/argus/agent_runtime/research_grounded.py`: `grounded_result` has the user,
and `retrieval_spec_for_job` rebuilds from the typed job request, which must
therefore carry the country. Removal of the server setting from `config.py`,
`.env.example`, `docs/API_CONTRACT.md` and `tests/research/`, together with the
unused `LOCAL_SOURCE_DOMAINS` and `local_sources` parameter. `docs/DATA_MODEL.md`,
`docs/API_CONTRACT.md` and a regenerated `docs/api/openapi.yaml`.

**Do not touch.** Currency in calculations, cards or any model-facing text; that
use arrives with any grounded math. Prompt text anywhere, including in
`research_grounded.py`, which is fingerprinted. `perplexity_agent.py`, which
already sends the spec's location. `render.yaml` and the release contract, which
never declared the variable.

**Proof.** Focused backend and web tests. A research request built for a user
with country MX carries MX, and one for a user with none carries no location, on
both paths, with no provider calls. Bilingual browser proof in Settings,
including a reload and a refused save. The sanctioned pre-merge live
measurement, because research requests change, compared case by case against
the scorecard named in `.agent/interpreter_prompt_fingerprint.json`, with the
fingerprint unchanged. The founder merges and applies the migration.

---

### The conversation after a result  ·  ships in **its own promotion, after the readout**

**Founder, 2026-09-11, side by side with Perplexity in the live app.** Asked
"what should I try next?", Perplexity answered with a plan grounded in the
conversation: a comparison of candidates, an order to work through, a useful
next prompt and related questions. Argus answered with one fixed sentence and
three generic rows. The founder's bar holds here: the AI writes; Argus supplies
the run's facts, the tested math, what the data can support, and the actions.
One lane owns this whole surface, not one defect at a time.

**Today.**

- "What should I try next?" gets a fixed sentence, "Here is what you can try
  next from this result." or "Esto es lo que puedes probar después a partir de
  este resultado.", from `src/argus/agent_runtime/next_experiments.py`, then the
  rows from `next_experiments_sidecar` (PR #592). The rows are right: they go
  away once used and a tap sends a typed refine action.
- Every equity date question says history starts in 2016. That is the provider
  floor, `ALPACA_EQUITY_HISTORY_START` in `src/argus/domain/market_data/capabilities.py`,
  repeated in `llm_clarifier.py`, `llm_interpreter.py`, `stages/confirm.py`,
  `stages/execute.py` and `src/argus/api/backtest_service.py`. For an asset listed
  later it is false: DOCN began trading in March 2021.
- Questions about a result go through `src/argus/agent_runtime/result_followups.py`
  and `result_followup_answers.py`.

**Done means.** On the same result, side by side with Perplexity, in English and
Spanish, the founder prefers or matches Argus:

- "What should I try next?" is answered by the model from the result, the
  conversation and, when it helps, cited research: what to test and why, in an
  order, with the Try next rows kept as the actions.
- A question about the result, such as why it fell or whether it was good, is
  answered by the model from the run's facts, with cited context when the answer
  needs the world.
- A few next questions built from this conversation are offered to tap, never a
  fixed catalogue.
- Any date or availability statement uses the asset's own first available date,
  never the provider floor.
- No fixed prose answers on these surfaces; fixed text is only the recovery when
  the model is unavailable.

**Surface.** `next_experiments.py`, `result_followup_answers.py`,
`result_followups.py`, the result follow-up paths in `stages/interpret.py` and
`stages/interpret_actions.py`, every history-start statement listed above and
the capability that owns the floor, the web rows and suggested questions, both
locales.

**Do not touch.** The Quick take and Breakdown frames, owned by "Let the model
write the readout". Money math stays in tested code and is never computed in
prose (operating rule 6). No advice and no forecast stated as fact. No template
answer and no question catalogue.

**Proof.** Side-by-side screenshots against Perplexity on DOCN buy and hold, DOCN
DCA and SPY RSI, in English and Spanish. Focused tests. This lane changes
model-facing text, and the fingerprint covers every model-facing string under
`src/argus/agent_runtime`, `src/argus/domain`, `src/argus/llm`, `src/argus/context`
and `src/argus/nlp`, not only the files it last recorded, so the lane owns the
fingerprint: one full live measurement at the end, compared case by case, then
the refreeze. It starts when the readout lane lands, because one lane changes
model-facing text at a time.

---

### Share the answer  ·  ships with **The calculations**

**Promoted from a note under the registry to its own item, founder 2026-09-09.**
Sharing is not a feature on the product, it is the distribution loop, and the
loop is already built: anonymous link, `noindex`, revocable, a tombstone when
the source is gone, a Settings list, and a fixed action bar that lands a reader
on guest entry. All of it verified at 390 and 1280 in both languages.

**It is wired to the one artifact this audience never asks for.** `ShareReceiptAction`
takes a single `evidenceArtifactId` and is mounted in exactly one place,
`StrategyResultCard.tsx:327`. `PublicReceiptPayload` is `strategy_facts`,
`date_range`, `metrics`, `benchmark_symbol` and a `portfolio_equity` series. It
has no shape for an answer that is not a run. Twenty people arrived on
2026-08-12 with salaries and priced goals; had Argus answered one of them well,
there would have been nothing to send.

**Where Argus beats the competitor at its own surface.** A shared page elsewhere
shows that the model thought. Argus can show what it computed and where each
number came from, dated and cited, because the honesty line already forces
that. One is a persuasive essay, the other is a receipt a stranger can check.

**Done means.** Any eligible answer can become a public page, not only a
backtest. The payload carries a `kind` discriminator, version 1 rows stay
readable, and eligibility is keyed on typed metadata rather than on what the
prose looks like. The reader sees the question, the answer, and the evidence
under it. `docs/specs/conversation-sharing.md` section 4 already specifies the
research kind end to end. Section 4.5 authorizes section 9's closed wrapper for
selected turns inside one conversation; composition beyond that stays out of
scope. The four-turn cap written there on 2026-09-09 was withdrawn on 2026-09-10,
with the fast-shape sharing exclusion.

**This ships with the calculations, not after them.** A calculation nobody can
send does not distribute, and the receipt is a retrofit across every card once
they exist.

**Decided 2026-09-09, and written into
[`conversation-sharing.md`](conversation-sharing.md) section 4.5.** This
extends the sharing feature that exists; a parallel conversation-sharing system
has been built wrong. A link glyph sits in the chat header beside the existing
`MoreVertical`, never inside it, and opens per-turn selection. **The selection
screen is the work no competitor has done for us:** they offer "select all"
because every turn is shareable and ours are not, so an ineligible turn renders
unselectable with a reason the owner can read, and "select all" means all
eligible. The header is the only entry point: no message pill, overflow share
item or visible result-card share control remains. A single answer is one ticked
turn in that same selection screen, using the existing creation logic and record.
The public page stays a receipt
rather than a rendered card, derived from the card's typed facts instead of
`receiptPlan` and `benchmarkVerdict`. The action reads **"Continue with
Argus"**.

**Deferred deliberately:** a receipt that offers its own re-run. It is the one
thing a product sharing prose cannot copy, and it contradicts the freeze rule,
so it is a later decision rather than a tweak.

**Do not touch.** No fork, no prefilled prompt, no guest shares, no multi-turn
selection beyond choosing turns in one conversation. Operating rule 3 stays at
four artifacts: if a second calculation needs its own receipt body, the
abstraction failed.

**Proof.** A non-backtest answer shared, opened signed out at 390 and 1280 in
both languages, revoked, and its tombstone rendered. An ineligible turn shown
unselectable with its reason, in both languages. A version 1 backtest receipt
still readable unchanged.

---

### Any grounded math  ·  ships in **The calculations**

**Reframed 2026-09-10, founder: not five calculations.** Argus does any finance
math a question needs, free form. The primitives below are examples of the
math, never a list of what Argus answers. Three rules are fixed: every input is
cited or given by the user; every figure is computed by code, with its inputs
shown and editable; every answer returns to the money decision and offers the
opportunity-cost contrast. **The AI answers first** (decision 10 and the lane
that removes the blocking guardrails); polished cards and graphs for structured
math, such as a valuation matrix, come later. In scope, by analogy to Driven's
official skills without its agent skill: deep research, market pulse, sector
radar, screening, competitor analysis, single-stock analysis and valuation, plus
the consumer finance topics in the smoke test. **Deferred:** portfolio monitor,
quant calculator, insider tracking. No skill store and no picker.

**The original item, kept for its detail:**


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

**Done means.** Each is a declaration, a compute function, tests, and its own
card, per operating rule 3. Each
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

**Do not build a taxonomy.** Record what was asked and what happened, and read
it later. The only question that matters is *could Argus have answered this and
did not*, and that is a judgment made when reading, not a field written at the
time. A bond's past performance refused is a bug. A three-year extrapolation
refused is correct and permanent. Classifying at write time is the enumeration
trap again, one level down.

**Surface.** `src/argus/observability/`, the unsupported path, the recovery
messages surface.

**Do not touch.** No user-visible change. No model-facing text.

**Proof.** A refusal produced in a test appears in the record with its shape.
No live eval required, because nothing reaches the measured code.

**Timing.** Not first for its own sake. It ships before distribution so it is
collecting when signal arrives.

---

### Ask for feedback  ·  ships in **Instrumentation, before the next distribution**

**Founder, 2026-09-11.** People rarely use the feedback Argus already has.
Borrow the pattern that works: ask once, at a good moment, with one tap, and
make "tell us more" optional.

**Today.** Every answer has a thumbs up and down that saves a rating to
`public.feedback` through `POST /api/v1/feedback`
(`src/argus/api/routers/feedback.py`), with conversation context sanitized by
`src/argus/api/feedback_context.py`. `web/components/feedback/FeedbackDialog.tsx`
takes written feedback, and guests can send it without an email. Nothing asks,
and nothing shows the feedback to the founder. In production there are 17
feedback rows between 2026-05-30 and 2026-07-16: 12 thumbs from internal or test
accounts, 2 thumbs from registered users outside the team, 3 written notes with
no account, and nothing since 2026-07-16. No guest feedback milestone has ever
been recorded.

**Done means.**

- After a result lands, at most once per conversation, Argus asks how it is
  doing with three one-tap answers, in English and Spanish. Never while an
  answer is still arriving, and not again in that conversation after a dismissal,
  including after a reload.
- A tap saves the rating through the existing endpoint. "Tell us more" opens the
  existing dialog.
- The new ask attaches the conversation only when the user chooses to. Stated
  personal financial figures follow decision 8.
- Each submission emails the founder at support@get-argus.com through the existing
  Resend sender (the `src/argus/domain/access_approval_email.py` pattern and
  `ARGUS_APPROVAL_EMAIL_SMTP_PASSWORD`), with no new release setting. A failed
  email never fails the submission.
- Guests and signed-in users both work, and the existing feedback quota still
  applies.

**Surface.** A new ask component beside `FeedbackDialog.tsx`, mounted with the
smallest change to the chat screen. `web/lib/feedback-context.ts`.
`FeedbackRequest` in `src/argus/api/schemas.py` and `routers/feedback.py` if a
rating or consent field is needed. An additive migration only if the table's
`type` check must widen. A notification sender following the access email. Both
locales. `docs/API_CONTRACT.md` section 18, `docs/api/openapi.yaml`, and
`docs/DATA_MODEL.md` if the table changes.

**Do not touch.** Model-facing text: the prompt fingerprint scans every prompt
string and `Field(description=...)` under `src/argus/agent_runtime`,
`src/argus/domain`, `src/argus/llm`, `src/argus/context` and `src/argus/nlp`, so new
code there carries none. The readout frames and the result rows. `render.yaml`
and the release contract. No analytics vendor and no third-party widget.

**Proof.** Focused backend and web tests, including a failed email that still
saves the feedback. Bilingual browser proof: the ask appears after a result, a
tap saves, "tell us more" opens the dialog, and a dismissal holds after a reload.
One test email, marked as a test, received at support@get-argus.com from a local
run. No live measurement, because no model-facing text or routing changes.

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

`search_domain_filter` was framed as the local moat; the founder dropped the
source list on 2026-09-10 (see Still open). `user_location` derives the calculations's currency default.

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
domain-filtered call citing a local source. The Dominican
domain list was dropped on 2026-09-10.

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

**The re-run happens when the user opens the decision.** Nothing reaches out.
Email and notifications are a surface Argus does not have, and building one is
not on this board.

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
is verification rather than build.

**Verified 2026-09-08 against `00331188`, evidence-only, no code change.** The
signed-out receipt opens correctly at 390 and 1280 in both languages, eight
loads, zero horizontal overflow, no credential on any request, `noindex` on
every receipt. Evidence lives under
`docs/reports/evidence/sharing-verification-00331188/`. This board's earlier
claim that **#422** carries seven open findings was stale: #422 was closed by PR
#447, and all seven dispositions come back not applicable. Six are on components
the `/r/` route never mounts, omnisearch, row menus, confirmation cards, usage
counts, auth strings and the dossier sheet. The seventh, the clipped first
x-axis label, is unreachable for a different reason: the receipt uses
`ReceiptChart`, which hides both axes, not `ResultEquityChart`. What the
verification did not re-prove, because it seeded the fixture directly, is the
owner's Share button and database persistence; those were driven end to end at
`5d408acf` and no receipt source file has changed in the 94 commits since.
**Founder decision 2026-09-08: the flag flips at the next promotion, not before.**
The four lines are `render.yaml` lines 59 and 182 and
`.github/private-alpha-release-profile.json` lines 23 and 89, all `false` today,
and they are the founder's to author.

---

### Teach the method  ·  ships in **Grounding**

Both of Johana's suggestions, which are one request stated twice.

- **On arrival**, one line about what Argus does with a question, not only what
  to ask.
- **When a question is too broad**, three specific questions derived from what
  the user actually said, instead of a refusal or one open question.

**Done means.** A broad question returns derived follow-ups, never a catalogue.
The guest empty state states the method in one line.

**Solution agreed 2026-09-10, copy not chosen.** One line on arrival stating what
Argus does with a money question, plus one rotating example sentence, never a
grid. A broad question gets three follow-ups built from the user's own words.
The founder rejected the first welcome-line draft; the copy stays open.

**`chat.welcome` is rewritten.** It currently reads *"Tell me an investing idea
in plain language and I will help test it with Alpha-safe assumptions."* That is
the box, stated before the user has typed anything, and it is the single
highest-leverage string in the product.

**Greetings are gated by demonstrated interest, not deleted.** Founder,
2026-09-08. The market-state greetings are genuinely good for someone who cares
about markets and wrong for someone who arrived with a savings question.

- **Generic by default.** Market flavor is earned.
- The signal is **the user's own conversation history**, has this person ever run
  a backtest, do they ask about assets. Not personalization memory, which is
  dark behind two gates and an order of magnitude larger than this.
- **Guests always generic**, because a guest has no history, and guests are the
  2026-08-12 cohort who arrived with money questions and were told about
  backtests.
- This is the same signal the counterfactual choice reads when the model picks
  what to compare against. **One notion of what we know about this person, used
  in two places**, built once rather than as two lookups that drift.

Two copy deletions regardless of gating: the Spanish weekend lines, whose
trailing clause is filler, and `noctámbulo` in `night_a`, a word no Dominican
says out loud. Roughly thirty greeting variants hand-written in two languages is
also a rule 4 problem in miniature; cut the count.

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

**Read the meter labels once before the Plumbing promotion.** Founder,
2026-09-08. The meter is cost recovery by design, so it names only the two
things that cost us money, and the thing Argus actually sells, the computation
and the honesty line, is free and therefore absent from the panel. PR #561's
own strings are already close: "Searches with sources" names the guarantee and
not just the supplier. So this is one reading pass over four locale strings, not
a rework, and it belongs in #561 while that file is open rather than in a later
pass. Pricing is not on this board and should not be decided while production
usage is one non-founder message in thirty days.

**The guest ceiling is not a product meter.** "Never for talking" is a pricing
rule and it stays. It does not say an anonymous endpoint may be unbounded. A
silent abuse ceiling on guest turns protects interpreter spend, never appears in
the Usage panel, and is not promised in `PRODUCT.md` as an allowance. Codex's
open P1 on PR #561 is asking for that distinction, not for the old
ten-terminal meter back.

---

## The refusal we shipped, and reversed

**2026-09-09. The worst defect of this board, caused by this board's own
process, and worth keeping written down.**

PR #562's item said one thing: *"Retrieved facts arrive as typed rows with
citations, never as prose to be re-parsed."* During review it grew a rule the
item never asked for, that an answer whose row could not be tied to a retrieved
URL by exact string match is **withheld whole**. The captain chose that over
trimming the claim, on the grounds that a prose matcher leaks and a withholding
rule cannot. It shipped.

**The result: Argus refused "what's the price of nike today."** Google,
DeepSeek, ChatGPT and Perplexity all answered it in one line. Argus said it
found sources and would not quote them. The founder found it in five minutes on
a local instance, on the first question he asked.

Three things this cost, all in one turn: the user got a refusal, the $0.045
already paid to Perplexity was thrown away, and the invoice was rejected as
`rate_mismatch` so the ledger recorded nothing either.

**Reversed by PR #578, `a404c9a7`.** `_withheld_code` and the exact-string
citation check are gone. A retrieved answer publishes; a row written with no
citation is named under the answer rather than deleting it. The sharing cap of
four, also invented during that spec conflict rather than decided, is withdrawn
along with the `fast` shape exclusion that made every price question
permanently unshareable. The sol rate table now follows the bill: Perplexity
has charged $4 in, $20 out, $5 cache write, $0.40 cache read since 2026-09-03
while its documentation still says $5 and $30.

**Three rules this violated, all already on this board.** Rule 9, loosen before
you build. Rule 4's intent, which was typed rows rather than refusal. And the
subtractive thesis: a change that adds a rule the model could have followed on
its own is probably wrong.

**The acceptance test is now the founder's, and it outranks a green suite.**
Ask Argus and ask a competitor the same question, side by side. **If Argus says
it cannot do something the competitor just did, the work is not done.** A
passing test suite told us this feature was correct for a full day.

---

## Where this board actually stands

**Recorded 2026-09-09 at integration `6fa3f55a`, CI green there. Production is
still `ee9c3491`; nothing below has been promoted.** Landed means merged to
integration and green there, not shipped to a user.

**The overnight batch, 2026-09-09. Three of four landed; one is in review.**

**The deployed log sink renders tracebacks; the note about it is narrower than
it reads.** PR #571 checked and nothing in this repository calls `logger.add`
outside tests, so production runs loguru's default sink. The note repeated
across the codebase, that the deployed sink drops structured extras, is about
**kwargs, not exceptions**: `logger.opt(exception=True)` reaches the log intact
and flattening a traceback by hand duplicates what the sink already does.

**A second CI flake exists and is not the `fromisoformat` one.**
`tests/test_private_alpha_canary_split.py::test_session_tool_provisions_only_a_safe_dedicated_identity`
shells out to `bun e2e/support/private-alpha-canary-session.ts provision`, which
makes a live `fetch`, and it reds `backend-checks` with "the socket connection
was closed unexpectedly". It failed once on integration `6bb73c86` and passed on
a rerun of the same head with no code change. Rerun it; do not chase it.

**The live measurement grades a failing prose judge as a pass when it names no
criterion.** `tests/evals/measurement_eval_harness.py` adds one failed check per
criterion the judge lists, so a verdict of `pass: false` with an empty list adds
nothing and the case passes. It hid one failure in the scorecard the interpreter
fingerprint names: `messy_spanish_future_performance_nvda_cruce_dorado` in
`docs/reports/evidence/411/live-measurement.json` is a judge fail, so that
baseline is 60 passed and 2 failed, not 61 and 1. None of the registry lane's
four full runs hit it. PR #575 found it and its narrowed goal carries the fix.

| Lane | PR | Surface it owns |
| --- | --- | --- |
| Subtract the guardrails | **LANDED** `695d9250`, PR #565 | done; surface released |
| Cut the catalog import edge | **LANDED** `772aa276`, PR #567 | done; surface released |
| Withheld answers keep their sources, and are not paid for twice | **LANDED** `6f7e7354`, PR #568 | done; surface released |
| A turn is billed for every response it read | **LANDED** `06f70908`, PR #571 | done; surface released |
| Lift the edit contract, closing #430 | **LANDED** `0ac96828`, PR #570 | done; surface released |

`llm_interpreter.py` has roughly 19 lines of modularity headroom and belongs to
the guardrail lane alone; every other lane was told to stay out of it.

| Item | Release | State |
| --- | --- | --- |
| Refusal log | Instrumentation | **Landed** `fa69466c`. #314 closed. |
| #462 latency | Instrumentation | **Landed** `76937883`. #462 closed. |
| Ask for feedback | Instrumentation | **LANDED** `98d9f423`, PR #594. After a result lands, Argus asks once per conversation how it is doing, with three one-tap answers in English and Spanish; "Tell us more" opens the existing dialog, and the conversation text attaches only when the user ticks its checkbox. A tap saves the same conversation, message and run pointers a thumbs rating saves, with no text. Every accepted submission emails support@get-argus.com through Resend, and a failed email never fails the save; the test email reached the founder's inbox. No migration, no new setting. The support address having separate web and API owners is deferred as #596. |
| Metering | Plumbing | **Landed** `1db1aa75`. #546 closed. One label pass owed before promotion. |
| Decisions | Plumbing | **Landed** `67facaf5`. |
| Retrieval parameters | Grounding | **Landed** `41bf9930`. #404 and #545 closed. A follow-on, PR #568 `6f7e7354`, made a withheld answer keep the pages it already paid to retrieve, reframed from "sources used to inform this answer" to where Argus looked, and cached the withhold so the same unanswerable question is not billed twice. It filed #569, answered by PR #571: a turn now reports what it paid rather than what it published, so a discarded packet, a retry either kept or thrown away, and a response rejected after its invoice all reach the ledger. Eleven inline degraded turns between 2026-08-13 and 2026-09-02 recorded zero spend, under about $1.50 and not worth a backfill; the three thorough `missing_public_sources` turns on 2026-09-08 were already correct, and no research job has ever failed in production. |
| Sharing on | Sharing | **Verified**, evidence landed `dff703d6`. The flag flip is a founder action at the next promotion. |
| Lift the loop, Lane A | The spine | **Landed** `f7c9192b`. |
| Lift the loop, Lane C | The spine | **Ran, report landed** `6fa3f55a`, docs only. Its finding is that Lane A did not make the loop reusable, and its import probes are the failing test the catalog-edge lane inherits. |
| Subtract the guardrails | The spine | **LANDED** `695d9250`, PR #565. Ordinary chat first outcome went from 35.27s to 15.63s p50 and its guardrail share from 44.2 percent to 2.3 percent, measured head/base/head/base interleaved so provider drift cannot fake it. The compute-shaped probe went 25.85s to 16.14s. Composer starvation went from 9 turns in 2 runs to zero. Its three eval failures were re-run on head and on a lane-free tree: two pass on both, one fails on both and is pre-existing. |
| Lift the loop, Lane B | The spine | **LANDED** `0ac96828`, PR #570, closing #430. Seven silent-reissue classes closed, card `kind` shipped, sixteen bilingual browser cases. `artifact_assumption_edit.py` went 1,561 to 1,507 lines, so 56 of its 75 growth lines are free again. |
| The registry | The spine | **First half landed** as PR #567, `772aa276`. The catalog edge is cut: `state/models.py` now takes `RegisteredStrategyTemplate` from a new `strategy_template_contract.py` that loads the catalog only inside the validator, so a general envelope imports without it. Lane C's probes went from three passing the catalog guard to seven. **Second half LANDED** `129ad084`, PR #575, 2026-09-10, as the declaration half only. One typed declaration per tool owns its input and return validation, cost and confirmation, progress, and versioned result card and recompute binding. All 17 fingerprinted files are byte-identical to integration and no new live eval ran. Before it was narrowed, its interpreter contract rewrite paid for four full live runs, 43/25, 52/16, 49/19 and 58/11 passed/failed, about $10 accounted, plus a 56-run comparison the lane reported at $2.61, and its fourth run failed ten cases that had passed before. That rewrite is parked on `codex/registry-interpreter-rewrite` at `dcde9aff` as evidence for decision 9's reassessment. |
| Profile write path | outside the releases | **LANDED** `499b00ad`, PR #581. Every profile save goes through one queue in `web/lib/profile-writes.ts`, and a refused language save now shows an error and puts the language back, in English and Spanish. A signed-in person changing language on the login page keeps it in that browser only, per API contract section 9. Its browser spec is not in CI, which runs one spec. Retiring the unused `profiles.theme`: Step 1, nothing writes it, **LANDED** `0c45c332` as PR #584, closing #582, and `PATCH /me` ignores a `theme` it no longer declares. Step 2, dropping the column, **LANDED** `f7d25c90` as PR #595, closing #583. By founder decision on 2026-09-11 it landed before Step 1 is live in production. Its destructive migration, `20260911214608_drop_profiles_theme.sql`, is applied at the next promotion in the order #595 states: backup, apply with founder approval, rerun the production migration gate, then deploy. It also removed the last writer, the workflow proof seeder in `workflows/proof.py`. |
| Research publisher honesty | outside the releases | **LANDED** `d6c908d9`, PR #585, closing #579 and #580. A research question is dated by the New York calendar through one owner, `question_date()`, so a survey asked after 20:00 ET keeps same-day pages. A turn that retrieved nothing is withheld with `research_not_grounded` on both the inline and background paths, and the Nike quote #578 fixed still publishes. Codex found that interpretation still dated "today" from the server clock; PR #587 fixed that, below. |
| One owner for today | outside the releases | **LANDED** `e186fc24`, PR #587, closing #586. Every reading of the user's today comes from one New York clock, `src/argus/domain/market_data/new_york_clock.py`, so a question asked after 20:00 ET on a UTC host no longer dates tomorrow. Verified with the clock frozen at 20:17 EDT and 20:17 EST: today, the research question date and "to today" resolve to the New York date. The prompt fingerprint is unchanged. |
| Let the model write the readout | its own promotion | **LANDED** `7ff6df2c`, PR #588. Luna writes the Quick take through OpenRouter's readout tier and the Breakdown through the Perplexity Agent API with web search, in English and Spanish. The card keeps the numbers; a backtest figure the prose cites must match the run, and Argus supplies the derived figures and dates it needs. Sources open in the existing panel, inline links point only to sources the Breakdown returned, a reload keeps a finished Breakdown, and the frame shows one working state. The prompt fingerprint was refrozen on a live run of 67 passed, 3 failed and 1 provider outage, with all four retries passing. |
| What to try next after a result | outside the releases | **LANDED** `aadd70eb`, PR #592, closing #590. Asking what to try next after a result answers with that result's Try next rows and a one-sentence lead-in in the workspace language, on both follow-up paths and for every strategy family, through the one rows owner `next_experiments_sidecar`; the retry message appears only when no row can be built. No model-facing text changed. Its live run was 61 passed and 8 failed against the baseline's 63 and 6; six of the seven flips passed a rerun, and the one that failed twice got no read from the structured tier, so it never reached this code. |
| A clarification reply keeps what the user said | outside the releases | **LANDED** `05196b33`, PR #591. After Argus asks a question, the reply keeps every fact the user already gave (asset, dates, money, costs), an explicit new idea starts clean, money the user typed outranks an audit's guess, and one owner removes em dashes from visible replies. Its full live run on the merged tree was 65 passed and 6 failed; four passed a rerun, and the other two failed outside its code (research publishing on a Spanish forward question, and a discovery answer whose voicing model timed out). On the Haiku fallback it refused a named cap three times out of three where integration lost it once. The founder kept the rule that money the user typed outranks an audit's cap of the same amount. |
| Let the AI answer forward and valuation questions | its own promotion | **LANDED** `4482aaa6`, PR #589, as decision 10. Forward and valuation questions get cited scenarios with shown math instead of the future-performance refusal. It also raised the balanced research timeout to 150 seconds for every question, a latency tradeoff the founder accepted. Its scorecard's three discovery failures were rerun on integration with live market data: two pass, because the lane's driver had kept the `.env`'s synthetic market data, and the third is the older dead end filed as #590. |
| Home country per user | its own promotion | **LANDED** `65bc661b`, PR #593. A registered user picks a country in Settings, sees the currency it implies and can override it, in English and Spanish. Research sends that user's country on the inline path, thorough jobs and the research tool; a user with none sends no location. `ARGUS_RESEARCH_HOME_COUNTRY`, `home_location()`, `LOCAL_SOURCE_DOMAINS` and `local_sources` are gone. Its research-case live run sent no location on any call, matching the baseline. Apply `supabase/migrations/20260911120000_add_profile_home_country.sql` (additive) at promotion. A guest session pick is not built; the lane priced it at about a day. |
| The conversation after a result | its own promotion | **Scoped 2026-09-11 in its item section; can start now that #588 landed.** "What should I try next?" and questions about a result are answered by the model, with the Try next rows kept as actions and a few next questions offered; availability dates use the asset's own first date instead of the 2016 provider floor. Judged side by side with Perplexity. |
| Any grounded math | The calculations | **Not started.** Reframed 2026-09-10 from "the five calculations": any finance math, grounded, never a list. The AI answers first; polished cards later. Portfolio monitor, quant calculator and insider tracking deferred. |
| Teach the method | Grounding | **Not started.** The frozen-text wait ended when #588 landed; the welcome copy is still unchosen. |

**The honest read.** Five of the seven dispatched lanes were plumbing,
instrumentation or verification, and all five landed. **None of them changes
what a user can ask.** The goalpost is that a money question in an unwritten
shape lands on a primitive and gets computed, and today **zero calculations
exist**. Everything shipped so far makes the next work possible; none of it is
the work.

**What stands between here and the goalpost**, in order: finish subtracting the
guardrails, build the registry, build the five calculations. Teach the method
and Lane B are real but neither blocks the goalpost.

**Two findings from today change the estimate.** Lane C proved that relocation
did not make the loop reusable, so the registry has to cut the catalog import
edge and absorb six existing owners before calculation one. And #462 measured
ordinary chat at 33.14s to first token against decision 3's one-second target,
so operating rule 2's promise that a cheap calculation answers first has no
runtime behind it at all.

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
| **Instrumentation** | refusal log, #462 latency, ask for feedback | a one-tap feedback ask after a result | no |

Release names are cut boundaries, not a running order. The order is in the
rules below.
| **Plumbing** | metering, decisions | nothing, behavior preserving | no |
| **Sharing** | sharing on, mobile verification | a result can be shared | probably not |
| **The spine** | lift the loop, the registry | **nothing, if done right** | yes |
| **The calculations** | any grounded math, the AI first, polished cards later | Argus answers money questions it used to refuse | yes |
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

**Measured 2026-09-08, PR #563, 68 real turns. The target is unreachable on
today's spine and the reason is the box.** Ordinary chat reaches first token at
33.14s p50, against a target of one second. Grounded answers land between 12.55s
and 26.17s, against four. Splitting provider time per turn into the two calls
that are the product, the interpretation and the composer, and everything else:
ordinary chat spends 15.60s of 30.13s on guardrails, 52 percent. Confirmation
spends 48 percent, the compute-intent probe 43 percent. The research paths spend
9 to 12 percent, which is why **asking Argus to research something reaches first
token in 12.55s while talking to it takes 33.14s.**

The guardrails are backtest guardrails firing on turns with no backtest:
`CapabilitySideQuestionAudit` at 11.49s on 4 of 10 turns, `ContextQuestionAudit`
at 5.11s on 7, `FocusedAssetDiscoveryRead` at 4.01s on 7, and the repair
`FocusedStrategyExtraction`, whose trigger is `required_strategy_shape_missing`,
16 times across 10 plain-conversation turns. Decision 3 is no longer blocked;
what it now needs is the item below.

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

**9. The models orchestrate; Argus owns the inputs, the math, and what
persists. Founder-approved 2026-09-10.** This revisits the board's earlier
rejection of letting Perplexity orchestrate a turn, and it overturns operating
rule 7, on purpose, rather than letting a lane route around either. Rule 7's
text is rewritten when this direction is confirmed after the registry lands.

**The evidence, from 2026-09-09.** Every defect found in competitor answers was
an input defect: "38,000 pesos" answered for Mexico instead of the Dominican
Republic, off by about four times; a stale previous close quoted as today's
price; entry prices marked as estimates. Their arithmetic held each time it was
checked. Every Argus defect was the reverse: a refusal caused by a rule we
added, and 87 percent of provider spend using an agentic reasoning model as a
JSON parser. The rejection's main argument, that Perplexity cannot answer in one
second, does not hold against an Argus that takes 15.6 seconds.

**The division.** The models understand the question, find the facts, and write
the answer. Argus owns what makes an answer right for this person and what lasts:
personalization, tested money math exposed as tools the model calls, and the
durable layer of decisions, memory, and sharing.

**Two conditions.** Money math stays in tested Python as a tool and is never
computed in prose, per operating rule 6. And personalization means stable
declared settings, country and currency; under decision 8 a stated salary,
expense, or debt stays ephemeral and is never stored.

**Inputs beyond text.** Perplexity's Agent API accepts `input_text` and
`input_image` by URL or base64; file parts are not documented. Grok 4.3 accepts
files. Argus today sends Perplexity a plain string and uses neither.

**Not yet measured, and owed before this is built.** The cost and latency of an
agent-first turn against today's pipeline. And whether a cheaper structured tier
is good enough: PR #129 swapped that tier from mistral-small with a DeepSeek
fallback to Grok 4.3 on 2026-06-28 as one bullet in an unrelated PR, and no
committed scorecard ever compared them. Reassess after the registry lands.
The registry now lands without the interpreter rewrite, which is parked with
its live runs as the first evidence for that reassessment; see the status table.
The registry landed on 2026-09-10 as `129ad084`, so that reassessment is now owed.

**10. Forward-looking and valuation questions are answered, as grounded
scenarios. Founder-approved 2026-09-10.** Argus will have advanced and
professional users who price businesses and assets constantly. Refusing "what
will $10,000 in NVDA be worth in ten years?" or "what price does NVDA need to
grow into?" makes Argus a worse Perplexity. Argus answers them the way
Perplexity's answers to those two questions did: cited forecasts and analyst
targets, the math written out, results given as labeled scenario ranges, never a
single prediction and never advice. Then it adds what Argus owns: what the idea
actually did historically, the opportunity-cost contrast, and polished cards
later.

This reverses the future-performance boundary from issue #241: the clause in
`src/argus/agent_runtime/interpreter/unsupported_admission.py` that tells every
interpretation to classify a future-value question as unsupported, the "I cannot
predict future performance" reply in `clarification_contract.py`, the three
measurement cases that require that refusal (`capability_honesty.yaml` twice,
`messy_spanish.yaml` once), and the instruction in `llm_interpreter.py` that
steers valuation questions toward a backtest proxy. "Compute what the user gave
you, never prescribe what they should do" still stands.

### Still open

**Dropped 2026-09-10, founder: no Dominican source list.** A hand-kept domain
allowlist adds rigidity Argus does not need. Perplexity is a search engine and
finds local sources well once the right guardrails are removed. The #545 probes
agreed: Banco Popular publishes no certificate rate online, and a three-site list
with a one-week window returned nothing. `LOCAL_SOURCE_DOMAINS` and the
`local_sources` parameter in `src/argus/domain/research/config.py` are unused
code to delete in a later cleanup.

**Home country comes from the user, not the deployment.** Founder, 2026-09-10:
Argus must adapt to each user's home country. Today `ARGUS_RESEARCH_HOME_COUNTRY`
is one country for every user, sent to the provider as the reader's location.
Per decision 9's personalization condition, country (and currency) become
declared user settings.

---

## Known gaps, not scheduled

- **The edit planner's 85-line system prompt escapes the fingerprint by
  construction.** It steers every card edit with no scorecard. Pre-existing,
  found by the 2026-09-08 scout, and it is a separate lane rather than part of
  lift the loop.
- **Field provenance has no typed model.** A dict key 35 files agree on by
  convention, 24 value strings, three readers checking different subsets. It
  will have to be typed eventually; it is out of scope for the spine.
- **Research has no fallback model and is a single point of failure.** The
  request body sends `"model": spec.model`, one string, and there is no fallback
  logic anywhere in `src/argus/domain/research/`. The Agents API accepts a
  `models` array of up to five. A provider hiccup on `openai/gpt-5.6-sol` takes
  research down with nothing behind it, while every OpenRouter tier has a
  fallback configured. Adding the array is one line and belongs in the retrieval
  lane. Model costs differ by provider, so the chain is also a cost lever, which
  the founder parked as later tinkering on 2026-09-08.
- **The CONFIRM graph node is hard-wired to `LaunchBacktestRequest`.** Waits for
  the first expensive non-backtest calculation.

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
