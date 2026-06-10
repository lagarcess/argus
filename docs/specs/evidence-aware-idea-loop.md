# Evidence-Aware Idea Loop

**Status:** Draft active product spec  
**Date:** 2026-06-10  
**Branch:** `codex/private-alpha-next`  
**Audience:** Founder, Codex, future implementation agents, reviewers  

## Purpose

This spec defines the product direction after the private-alpha conversation
trust checkpoint. It refines the earlier Research Lab thesis into a flexible,
testable product loop that supports direct backtests, education, lightweight
evidence, and deeper research without forcing every user through the same path.

The goal is not to implement Perplexity immediately. The goal is to align on
the vision, milestone ladder, architecture implications, and open questions so
the first implementation slice can test whether the market actually needs this
product direction.

## Context

Argus is currently a chat-first investing idea validation platform. The hardened
private-alpha system can:

- interpret natural-language investing ideas;
- produce confirmation cards;
- run workflow-backed historical backtests;
- render result cards with Quick take, Explain result, and Try next surfaces;
- persist conversations, messages, jobs, and runs in Supabase;
- preserve a manual deployment and canary workflow for production trust.

The next strategic question is whether Argus should remain a better chat-driven
backtest calculator or evolve into a place where investing thinking accumulates.

## Research Synthesis

Four external research agents produced strategy memos in `temp/`:

- `gpt-research.md`
- `gemini-research.md`
- `deepseek-research.md`
- `grok-research.md`

They broadly reconciled on the following conclusions:

- The Research Lab direction is stronger than "AI backtesting chat" if kept
  narrow and grounded in executable tests.
- Argus should not become a brokerage, a trading terminal, a generic finance
  chatbot, or a broad autonomous analyst.
- Perplexity is best treated as a research/citation provider, not the Argus
  runtime, not the simulation engine, and not the source of final result truth.
- OpenRouter remains the conversational/runtime model provider for Argus voice,
  structured drafting, clarification, result explanations, and refinement.
- Deterministic Argus code must own capability checks, asset resolution,
  same-asset constraints, date windows, benchmark defaults, backtest job
  creation, engine execution, and persisted run truth.
- The strongest product wedge is the bridge from messy curiosity to supported
  experiment candidates, not cited answers by themselves.
- The first implementation must be small, feature-gated, observable, and easy
  to reverse if users do not value it.

They differed on ambition:

- The most disciplined memos recommend an in-chat cited answer or research note
  that can become a confirmation card.
- The more ambitious memos push toward "My Lab" dashboards, public artifacts,
  pg_jsonschema constraints, Redis, regulatory sandbox framing, and richer
  artifact systems.
- This spec adopts the disciplined core and defers the heavy surfaces until
  private-alpha behavior proves the loop matters.

## Refined Thesis

Argus should become the place where investing thinking becomes testable,
explainable, and durable.

Not:

- a chatbot that answers finance questions;
- a backtest calculator with chat;
- a Bloomberg-lite terminal;
- a generic research workspace;
- a brokerage or execution platform.

The durable product loop is:

```text
observe -> learn/research -> form hypothesis -> test -> explain -> refine -> remember -> monitor/share later
```

The practical private-alpha promise is:

> Bring Argus a messy investing thought. Argus helps you understand it, ground
> it at the right evidence depth, turn it into something testable when possible,
> show what happened historically, and preserve the reasoning so your thinking
> compounds over time.

## Consumer Simplicity Standard

The user must not feel the machinery behind this spec.

Argus targets broader consumers who may be financially curious but unfamiliar
with finance language, market structure, backtesting terminology, or strategy
design. The product must bridge that literacy gap with simplicity, elegance,
intuition, and speed.

The user should experience:

```text
ask naturally -> learn quickly -> test simply -> understand clearly -> come back later
```

The user should not experience:

- choosing internal lanes;
- configuring research depth by default;
- reading provider/tool explanations;
- being forced through research before a direct test;
- navigating a dashboard or terminal before the chat has earned it;
- reviewing raw strategy JSON;
- feeling like Argus turned learning into homework.

Complexity can exist internally if it keeps the experience simple. It should
not leak into the primary chat unless the user explicitly asks for more depth.

## Core Product Principle

Argus should support multiple entry speeds into the same durable idea loop.
Research is optional, not mandatory.

Users who already know what to test should stay on the fast path. Users who
need education or grounding should get help forming a testable idea. Users who
ask for deeper research should be able to spend more time and cost deliberately,
without slowing down the direct-test experience.

The internal product architecture can use lanes and evidence-depth labels, but
the user-facing experience should feel like natural pacing:

- "I can test that now."
- "Here is the simple version."
- "I found a little context and two ways to test it."
- "This is broader; I can do a deeper pass if you want."
- "I will remember this idea and tell you when something relevant changes."

## Decision Algorithm

Use this filter to keep the milestone small and fast:

1. Question every requirement against the real user goal.
2. Remove or defer anything that does not help the next private-alpha learning
   loop.
3. Simplify or optimize the requirements that remain.
4. Accelerate cycle time with the smallest observable slice.
5. Automate only the signals that protect learning speed or trust.

The practical test:

> Does this help a user move from curiosity to a supported test, a clearer
> explanation, or a remembered idea faster?

If not, defer it. If it leaks unsupported capability, remove it from the
user-facing surface.

### Default Decision Bias

- Prefer one strong loop over many half-supported surfaces.
- Prefer direct test speed over research ceremony.
- Prefer executable candidate experiments over broad strategy breadth.
- Prefer short cited context over report-like answers.
- Prefer message/job/run metadata before new durable tables, unless reload or
  audit breaks.
- Prefer hiding unsupported inventory over showing users what Argus cannot run.
- Prefer explicit user consent before slow/deep research.

## Evidence Lanes

### Lane 1: Direct Test

For users who already know what they want to test.

Example:

> Backtest AAPL vs MSFT from 2020 to today.

Behavior:

- no Perplexity call;
- no citations required;
- existing interpretation, confirmation, workflow backtest, result readout, and
  refinement path remain unchanged.

Evidence depth: `none`

### Lane 2: Education

For users asking about finance concepts, market mechanics, or investing
language.

Example:

> Explain yield curve inversion.

Behavior:

- Argus answers in beginner-friendly language;
- citations are optional unless the answer makes external/current factual
  claims;
- Argus can offer to turn the concept into one or more supported historical
  tests.

Evidence depth: `conceptual`

### Lane 3: Light Evidence

For users with a rough market idea who need quick grounding before testing.

Example:

> Are semiconductors still outperforming gold?

Behavior:

- Argus performs bounded cited research;
- summarizes only the evidence needed to form testable candidates;
- produces one to three candidate experiments;
- filters candidates through deterministic capability checks;
- only executable candidates can become confirmation cards.

Evidence depth: `light`

### Lane 4: Deep Research

For users exploring a broader thesis where deeper evidence is useful.

Example:

> I am trying to understand whether semiconductor cyclicality is changing
> because of AI capex.

Behavior:

- Argus performs deeper cited research with explicit time/cost expectations;
- may run asynchronously if latency is high;
- produces a thesis summary and candidate experiments;
- stores a durable research artifact;
- defers monitoring, shareable pages, and dashboards until later milestones.

Evidence depth: `deep`

### Lane 5: Monitoring And Inbox Later

For saved ideas that should stay alive over time.

Example:

> Tell me when something changes that affects this idea.

Behavior:

- deferred until the first evidence-to-experiment loop proves demand;
- should be tied to user-owned ideas, not generic market news;
- likely uses scheduled jobs, saved ideas, source updates, updated market data,
  and inbox-style notifications;
- must remain educational and non-advisory.

Evidence depth: `monitor`

Retention promise:

> Argus remembers what I am exploring and tells me when something relevant
> changes.

Potential future notifications:

- "Your semiconductor vs gold idea has new evidence this week."
- "The ETF you used as a proxy changed meaningfully."
- "This saved idea may be worth retesting with updated data."
- "A source related to your thesis changed; want a quick update?"
- "Your recurring-buy idea now has another month of data."

## Unified Loop Contract

All lanes converge on the same Argus-owned structure:

```text
user input
  -> interpreted intent
  -> evidence depth
  -> evidence packet when needed
  -> candidate experiments
  -> deterministic capability result
  -> confirmation card
  -> workflow-backed backtest
  -> result card
  -> explanation
  -> next experiment
  -> durable idea memory
```

The product must not fork into separate "research mode" and "backtest mode"
brains. The chat runtime remains one coherent Argus experience.

This is a loop, not a straight line. A user may enter through education,
testing, light evidence, or deep research; after a result they may ask a new
question, refine the test, save the idea, ignore the update, or return later.
Argus should preserve continuity without forcing a rigid wizard.

## Architecture Implications

### Runtime

- Add an explicit evidence-depth concept to the runtime contract.
- Do not add regex gates before LLM interpretation.
- The interpreter may infer likely lane, but Argus can ask the user when the
  evidence depth is ambiguous or expensive.
- Direct-test behavior must remain fast and unchanged.

### Providers

- OpenRouter owns conversation, interpretation, structured drafting,
  clarification, result explanation, and refinement.
- Perplexity owns fresh external research and citations when evidence depth is
  `light`, `deep`, or a current factual education answer needs sources.
- Alpaca, Kraken, and future deterministic data providers own executable market
  data availability and historical data used in simulations.
- FRED remains a structured macro provider candidate when deterministic macro
  series are needed.
- No provider decides whether a backtest is executable except Argus capability
  code.

### Backtesting Engine

The evidence-aware loop does not require the engine to become a professional
quant platform. It requires the engine to cover the simple experiment types that
normal people naturally ask for after learning or researching.

The engine roadmap should prioritize understandable tests that strengthen the
evidence-to-experiment loop:

- compare asset A vs asset B;
- compare an asset, ETF, basket, or crypto against a benchmark;
- test recurring buys over a date window;
- test buy-and-hold windows;
- test selected baskets or proxies such as "semiconductors" through supported
  ETFs or selected tickers;
- later, test event or regime windows such as inflation periods, rate cuts,
  recessions, earnings windows, or Bitcoin halvings.

Signal/indicator strategies are not the near-term product wedge. Keep them as
advanced executable tests only when they already work and the user explicitly
asks for a rule-based idea. Do not surface a discoverable indicator if Argus
cannot execute it.

This changes the engine's role from "run any strategy the user imagines" to
"maintain a library of honest, understandable experiment types." When evidence
suggests an idea, Argus must know whether it can express that idea as a fair
historical test. If it cannot, Argus should explain the gap and offer a simpler
proxy only when the proxy is not misleading.

### Data

First-class future objects may include:

- `evidence_packet`: cited external context used for one assistant turn;
- `research_source`: normalized source/citation metadata;
- `candidate_experiment`: a proposed hypothesis and capability status;
- `idea_thread`: durable grouping of evidence, candidates, runs, and
  refinements;
- `idea_memory_link`: relationships between source evidence, confirmation card,
  backtest job, run, result readout, and next experiments.

Do not start with a giant generic artifact table unless implementation pressure
proves the concrete objects are too rigid.

### UI

- Stay chat-first.
- Direct tests should not show research ceremony.
- Evidence-backed prompts should show compact source context and candidate
  experiment cards.
- Unsupported ideas can be explained as boundaries in prose, but should not
  render as candidate experiment cards or buttons. If a card exists, it should
  point to a supported next step.
- Avoid a new dashboard in the first milestone.
- Hide internal labels such as `evidence_depth`, `candidate_experiment`, or
  `capability_status` from the primary user experience.
- Prefer one clear next action over many technically correct options.
- Let users ask for depth, but default to the shortest useful answer that
  preserves trust.

### Cost And Latency

- Evidence depth controls cost.
- `none` and `conceptual` should stay cheap.
- `light` should optimize for speed and candidate formation.
- `deep` can spend more time, but must be explicit and feature-gated.
- Route receipts must record provider, model, tools, latency, source count,
  candidate count, rejected candidate reasons, and cost/usage when available.

## Milestone Ladder

### Milestone 0: Spec And Product Test Design

Goal:

- Align on the vision, lanes, architecture, and learning questions.

Outputs:

- this spec;
- success/failure metrics;
- private-alpha interview/test script;
- first-slice scope and non-goals.

### Milestone 1: Evidence-Aware Intent Contract

Goal:

- Add the concept of evidence depth and candidate experiments without changing
  the direct backtest path.

Possible implementation shape:

- internal contract/types for evidence depth;
- no Perplexity required yet;
- deterministic tests for routing/capability labels;
- fixture-backed examples of direct test, education, light evidence, and deep
  research prompts.

Learning question:

- Can Argus correctly distinguish "test this now" from "help me understand or
  form a test" without slowing direct users?

### Milestone 2: Light Evidence To Candidate Experiments

Goal:

- Use bounded cited research to turn broad market curiosity into supported
  candidate experiments.

Scope:

- feature flag;
- Perplexity provider adapter;
- compact cited evidence packet;
- one to three candidate experiments;
- capability labels: `testable_now`, `needs_clarification`, `unsupported`;
- confirmation cards only for `testable_now`.

Learning question:

- Do users value Argus more when it helps them decide what to test?

### Milestone 3: Research-Backed Backtest Loop

Goal:

- Link evidence, candidate, confirmation card, job, run, and result readout.

Scope:

- persisted source/citation metadata;
- candidate-to-run linkage;
- result card references originating evidence when helpful;
- Quick take and Explain result remain Argus-owned, not Perplexity prose.

Learning question:

- Does cited context make backtests more understandable and trustworthy, or
  does it add latency/noise?

### Milestone 4: Refinement Loop

Goal:

- Make Try next genuinely useful by generating supported next experiments.

Scope:

- next experiments are grounded in the prior result and capability contract;
- no generic investment advice;
- no unsupported next-step buttons;
- track whether users run a second experiment.

Learning question:

- Do users iterate after seeing a result?

### Milestone 5: Idea Memory

Goal:

- Let user thinking accumulate beyond isolated chat turns.

Scope:

- durable idea object or equivalent linked artifacts;
- recents/history surfaces that show prior ideas clearly;
- no public sharing yet;
- no vector memory unless a concrete retrieval gap is proven.

Learning question:

- Do users return to prior ideas, or is Argus mostly a one-shot tool?

### Milestone 6: Deep Research

Goal:

- Support deliberate, slower, source-rich research when the user asks for it.

Scope:

- explicit depth controls;
- larger source budget;
- asynchronous execution if needed;
- clear cost/latency guardrails.

Learning question:

- Do users need deeper research inside Argus, or do they prefer external
  research plus direct tests?

### Milestone 7: Monitoring And Inbox

Goal:

- Build retention by keeping selected ideas alive over time.

Scope:

- scheduled or user-triggered updates;
- inbox-style notifications;
- only updates tied to user-owned ideas;
- no generic news feed;
- educational framing;
- no brokerage or personalized recommendation behavior.

Learning question:

- Does recurring relevance drive retention without becoming noisy or
  intimidating?

### Milestone 8: Shareable Artifacts

Goal:

- Let users share sanitized, immutable snapshots once privacy and trust design
  are mature.

Scope:

- owner-only create/revoke;
- unguessable public slugs;
- no source conversation IDs, provider metadata, route receipts, or private
  retry payloads;
- no unauthenticated access to source tables.

Learning question:

- Does sharing help distribution without compromising trust or privacy?

## Early Market Test Plan

Before building the full lab, private alpha should test one core behavior:

> Do users value Argus more when it helps them decide what to test, not just run
> what they already know to test?

### Test Method

Use five to ten private-alpha sessions with intentionally broad prompts:

- "Is the semiconductor industry outperforming gold?"
- "Do rate cuts usually help long-duration bonds?"
- "Explain yield curve inversion and what I could test historically."
- "Is Bitcoin behaving more like tech stocks lately?"
- "What is a simple way to test whether monthly buying beats lump sum?"

For each prompt, observe:

- whether the user accepts Argus's candidate experiment;
- whether they edit it;
- whether they run the backtest;
- whether they ask a follow-up;
- whether they say the candidate captured their intent;
- whether citations improved trust or felt like noise;
- whether latency was acceptable.

### Success Signals

- Users ask broad questions and accept at least one candidate experiment.
- Users run a backtest from an Argus-proposed candidate.
- Users ask follow-up/refinement questions after the result.
- Users say Argus helped them frame the idea, not merely calculate it.
- Users return to prior ideas.
- Users describe Argus as easy, approachable, or clarifying rather than
  technical.
- Users understand what Argus can and cannot test.

### Failure Signals

- Users ignore candidate experiments and only want direct backtests.
- Research/citations slow the experience without increasing trust.
- Candidate experiments feel generic or obvious.
- Users compare Argus to ChatGPT/Perplexity instead of seeing a unique loop.
- The product repeatedly suggests tests Argus cannot support.
- Users feel the flow is too much work.
- Users feel briefs or updates are generic market noise.

### Pivot Implications

If direct tests dominate, focus on expert-speed backtests, asset discovery, and
result interpretation before deeper research.

If broad questions convert into backtests, continue the evidence-aware loop.

If users like research but do not run tests, Argus may need a stronger
education/research product or clearer conversion actions.

If users want alerts and monitoring, move the inbox milestone earlier, but only
after trust and non-advice boundaries are designed.

## Questions We Need To Answer

These are the alignment questions that should shape the first implementation
plan. The most important questions are loop questions: what makes the user
return, what helps them make progress, and what should Argus remember.

Question IDs are stable handles for future discussion and implementation plans:

- `P` = Product
- `L` = Lane / flow
- `C` = Capability
- `E` = Evidence and sources
- `D` = Data / persistence
- `UX` = Experience
- `R` = Retention
- `T` = Trust and compliance
- `CP` = Cost and performance
- `EV` = Evaluation
- `O` = Operations

The raw questions below are intentionally retained for traceability. Current
answers and remaining unknowns live in the **Decision Ledger After The
Algorithm** section.

### Product Questions

- **P1.** What makes a broader consumer feel safe asking a naive finance
  question?
- **P2.** What is the minimum delightful moment: learning something, getting a good
  test suggestion, seeing a result, or returning to a remembered idea?
- **P3.** Should the first evidence-aware loop optimize for curious beginners,
  enthusiasts, or finance-literate private-alpha users while still preserving
  consumer simplicity?
- **P4.** Should Argus name this surface at all, or should the loop simply feel like
  better chat?
- **P5.** What should Argus never optimize for, even if it increases engagement?

### Lane Questions

- **L1.** How much of lane selection should be invisible and automatic?
- **L2.** When should Argus ask the user before spending more time on research?
- **L3.** What user-facing words feel simple: "quick context", "deeper look",
  "test this", "remember this"?
- **L4.** When should an education answer offer a test without making learning feel
  transactional?
- **L5.** How does a user bypass research and go straight to testing?

### Capability Questions

- **C1.** Which strategy templates are eligible for candidate experiments first:
  buy-and-hold, recurring buys/DCA, signal/indicator strategies, or all current
  supported templates?
- **C2.** Which simple experiment types should the backtesting engine support next to
  make research-derived ideas useful?
- **C3.** Which natural consumer prompts are currently impossible because the engine
  lacks event windows, baskets/proxies, or comparison primitives?
- **C4.** How should Argus handle ideas that are meaningful but not currently
  testable?
- **C5.** How should unsupported ideas be explained, hidden, or mapped to
  supported alternatives without making them look runnable?
- **C6.** How should Argus represent proxy tests, for example "luxury stocks" requiring
  selected tickers or ETFs?
- **C7.** What is the line between a supported experiment and a misleading proxy?

### Evidence And Source Questions

- **E1.** Which Perplexity tools are reliable enough for stocks, ETFs, crypto, currency
  pairs, macro, sectors, and companies?
- **E2.** What is the shortest evidence payload that increases trust without making the
  chat feel like a report?
- **E3.** When does a citation help a beginner, and when does it create clutter?
- **E4.** Should Argus use domain allowlists for some question types?
- **E5.** How should Argus show source freshness in plain language?
- **E6.** How should Argus handle conflicting sources?
- **E7.** What claims require citations, and what claims can be labeled as
  assumptions?

### Data Questions

- **D1.** What is the smallest durable "idea object" that creates continuity?
- **D2.** What should Argus remember that feels useful, not creepy or noisy?
- **D3.** Do we store research artifacts as concrete tables or message metadata first?
- **D4.** What citation fields are required for reload, audit, monitoring, and future
  sharing?
- **D5.** How long should research source snapshots live?
- **D6.** Do source snippets create copyright or privacy risk?
- **D7.** How should an idea object link to multiple runs and refinements?
- **D8.** Should research artifacts be immutable snapshots or regenerable drafts?

### UX Questions

- **UX1.** How can Argus hide complexity while preserving trust?
- **UX2.** What does a candidate experiment card look like compared with a confirmation
  card?
- **UX3.** How do we avoid clutter when showing evidence, citations, candidates, and
  backtest results in one chat?
- **UX4.** Should "Try next" show as chips, cards, or a dedicated follow-up section?
- **UX5.** How do we make unsupported boundaries feel helpful rather than frustrating?
- **UX6.** How should Spanish-language users experience citations and source language?

### Retention Questions

- **R1.** What makes a user come back tomorrow?
- **R2.** What is the user expected to do after a brief: read, test, refine, save,
  ignore, or mute?
- **R3.** How often is helpful: daily, weekly, event-triggered, or user-triggered?
- **R4.** What kinds of changes are meaningful enough to interrupt someone?
- **R5.** How does Argus avoid becoming a news feed?
- **R6.** What does progress look like for a beginner learning finance?
- **R7.** How should Argus let users pause, mute, or retire an idea?

### Trust And Compliance Questions

- **T1.** What exact no-advice language belongs on research cards versus result cards?
- **T2.** Should Argus avoid words like "recommend", "should buy", and "best" in all
  research-to-test surfaces?
- **T3.** What logs or artifacts must exist to audit a disputed answer?
- **T4.** When does a cited answer become too close to personalized advice?
- **T5.** What additional review is needed before public sharing or monitoring?

### Cost And Performance Questions

- **CP1.** What is the acceptable cost per `light` evidence turn?
- **CP2.** What is the acceptable cost per `deep` research turn?
- **CP3.** What latency is acceptable before we need async jobs?
- **CP4.** What quotas should apply per user/day in private alpha?
- **CP5.** Which provider calls can be cached safely without stale or misleading
  output?
- **CP6.** What telemetry is enough before adding PostHog or a custom event pipeline?

### Evaluation Questions

- **EV1.** What are the first 20 golden prompts?
- **EV2.** What constitutes a good candidate experiment?
- **EV3.** How do we measure whether the user felt less intimidated?
- **EV4.** How do we test that citations support claims without overbuilding an eval
  framework?
- **EV5.** When should we introduce LLM-as-judge?
- **EV6.** Should OpenAI be the future independent judge provider?
- **EV7.** What acceptance gate proves the feature did not regress direct backtests?

### Operational Questions

- **O1.** Which feature flags gate the lanes?
- **O2.** How does the canary test direct mode, light evidence mode, and provider
  fallback?
- **O3.** What route receipts are required to debug research failures?
- **O4.** How do we distinguish provider outage from unsupported idea?
- **O5.** What must be visible in Supabase after a successful evidence-backed test?

## Codebase-Derived Answers So Far

This section only answers questions that can be answered confidently from the
current codebase and canon docs. Product desirability, market fit, and
research-provider quality questions remain open until tested with users.

### Product Answers

- **P3. Current baseline:** canon docs preserve both truths: private alpha users
  can be finance-literate, but the Alpha product direction is broader consumer
  simplicity. The first evidence-aware loop should not fork the product into an
  expert mode. It should keep direct tests fast while making broad questions
  approachable.
- **P5. Current guardrail:** Argus should not optimize for engagement at the cost
  of advice boundaries, trust, clarity, or simplicity. It should not become a
  generic market-news feed, a trading terminal, or a provider wrapper.

### Lane Answers

- **L1. Current runtime constraint:** lane selection should be mostly invisible.
  The chat brain is still LangGraph; normal language reaches LLM interpretation
  first, then deterministic validation/capability checks. Do not add regex gates
  or a second chat orchestrator for research lanes.
- **L2. Current spending rule:** direct executable tests should stay direct.
  Argus should ask or visibly choose only when a request implies a slower,
  deeper, or more expensive research path.
- **L5. Current bypass:** the direct backtest loop already exists. The evidence
  loop must not require Perplexity/research for users who already know the
  ticker, strategy, dates, and assumptions they want to test.

### Capability Answers

- **C1. First eligible templates:** current executable launch strategy types are
  `buy_and_hold`, `dca_accumulation`, `indicator_threshold`, and
  `signal_strategy`. Candidate experiments should start here. Older or broader
  API strategy-template names should not be advertised as runnable unless the
  capability contract maps them into one of these executable paths.
- **C2. Current supported experiment families:** the engine supports buy-and-hold,
  recurring buys/DCA, indicator-threshold entries/exits, and signal-strategy
  rules. DCA cadence supports daily, weekly, biweekly, monthly, and quarterly.
- **C2a. Current asset and indicator support:** current launch requests support
  `equity`, `crypto`, and `currency_pair`, with same-asset-class runs only and
  a max of five symbols per run. Executable indicators are RSI, SMA, EMA, MACD,
  and Bollinger Bands. ATR, VWAP, OBV, and stochastic currently exist as
  catalog/discovery inventory but are not executable strategy triggers. Product
  decision: hide non-executable indicators from user-facing discovery until they
  either become executable or are removed. Showing draft-only indicator inventory
  is not aligned with Argus principles.
- **C2b. Current provider and benchmark defaults:** Alpaca is primary for equity
  and crypto availability; Kraken complements crypto and currency-pair coverage.
  Alpha benchmark defaults are `SPY` for equities, `BTC` for crypto, and the
  tested pair itself for currency pairs.
- **C3. Currently impossible or fragile prompt classes:** mixed asset-class runs,
  personalized portfolio advice, real-money trading, unsupported indicators,
  broad sectors without explicit tickers/ETFs, event-window questions, complex
  baskets/proxies, macro-causal claims, and deep research claims are outside the
  current execution contract. Cohesive expansions that fit the proposed vision:
  comparison primitives, explicit ETF/ticker proxy mapping, selected baskets
  within one asset class, and later event/regime windows. Remove or defer:
  personalized advice, real-money trading, broad unsupported indicator exposure,
  and mixed-asset execution until benchmark/allocation complexity is designed.
- **C4. Current failure shape:** meaningful-but-not-testable ideas should be
  handled as clarified or blocked product-language boundaries, not hidden engine
  failures. The backend already distinguishes invalid, unsupported, provider,
  and data-availability failures.
- **C5. Unsupported candidates:** users can ask anything, especially once Argus
  can send research agents outward. The LLM brain may map a broad thesis to
  capability-adjacent candidates, but deterministic capability code must filter
  the result. Unsupported ideas may be explained as educational boundaries or
  transformed into clearly labeled supported proxies, but they must not appear
  as runnable candidate actions.
- **C6. Proxy tests:** proxy tests are not first-class yet. Today they must be
  explicit selected tickers/ETFs that pass the same asset-class, symbol, date,
  timeframe, and benchmark validation as any other run.
- **C7. Supported vs misleading proxy:** a proxy becomes supportable only when
  Argus names the chosen instruments, states that they are a proxy, and keeps
  the runnable action inside current engine constraints.

### Evidence And Source Answers

- **E7. Current citation boundary:** engine-generated simulation metrics do not
  need external citations because they come from `backtest_runs`. Current market,
  company, macro, news, or sector claims do need source grounding once the
  evidence loop exists. Assumptions should be labeled as assumptions, not cited
  as facts.

### Data Answers

- **D1. Existing durable atoms:** Argus already has conversations, messages,
  `backtest_jobs`, `backtest_runs`, feedback, profiles, allowlist rows, and
  optional strategies/collections. There is no durable research/idea table yet.
- **D3. Current schema implication:** storing research artifacts as new concrete
  tables would be a new data-model decision. The safest first slice is to avoid
  schema sprawl until the minimum idea/evidence object is designed.
- **D7. Existing link path:** today, runs link through conversation/message/job
  metadata and `backtest_runs`. A future idea object should link to messages,
  candidate experiments, jobs, runs, and refinements rather than reconstructing
  state from frontend prose.
- **D8. Current immutability pattern:** `backtest_runs` are canonical immutable
  result truth. Evidence snapshots that justify a candidate or monitoring alert
  should likely follow snapshot semantics; drafts can be regenerable until they
  are used to create a runnable candidate or shared artifact.

### UX Answers

- **UX2. Current UI pattern:** candidate experiment cards should reuse the
  confirmation/job/result artifact lifecycle instead of creating a separate
  card system. The frontend should render backend-provided artifacts and actions.
- **UX6. Current language support:** canon docs and UI code support English and
  Spanish Latin America (`en`, `en-US`, `es-419`). Static UI strings need
  translations; AI responses should respect the user's language preference.
  Citation source language behavior is still open.

### Trust And Compliance Answers

- **T1. Current baseline:** result surfaces already use educational/no-advice
  language. Research cards need their own exact copy, but should preserve the
  same boundary: educational context, historical simulation, and no financial
  advice.
- **T2. Current guardrail:** research-to-test surfaces should avoid telling users
  what they "should buy", what is "best", or what Argus "recommends" as an
  investment. It can suggest supported historical tests and explain tradeoffs.
- **T3. Existing audit artifacts:** relevant existing audit artifacts include
  persisted messages, structured metadata, `backtest_jobs`, `backtest_runs`,
  route receipts, workflow run IDs, result readout provenance, failure codes,
  timing metadata, and fallback flags.
- **T5. Current public-sharing boundary:** public excerpts require a separate
  privacy/revocation/auth/sanitization design. Do not expose source conversation
  IDs, route receipts, provider metadata, retry payloads, or direct anon table
  access.

### Cost And Performance Answers

- **CP3. Current async boundary:** long-running or variable-latency work should
  cross the durable job boundary. Backtests now have `backtest_jobs` and Render
  workflow execution; evidence/deep research should use a similar boundary if it
  cannot reliably complete inside the chat turn.
- **CP5. Current cache boundary:** market-data/provider catalog caches are
  acceptable when they have explicit keys, freshness, and invalidation. Cached
  data is not source-of-truth; Supabase remains durable truth for product
  records. Research/evidence caches are not designed yet.
- **CP6. Current telemetry baseline:** before PostHog, route receipts, service
  logs, Supabase rows, workflow metadata, and canary output are enough for
  private-alpha debugging. Product analytics can be added later once the product
  loop is clearer.

### Evaluation Answers

- **EV2. Candidate quality floor:** a good candidate experiment must be
  executable by the capability contract, use supported assets/indicators/dates,
  preserve user intent, state assumptions clearly, avoid unsupported causality,
  and produce a runnable confirmation card.
- **EV7. Direct-backtest regression gate:** the evidence loop must preserve the
  existing direct backtest path. Acceptance should include at least one direct
  backtest canary, one async workflow-backed result, persisted messages/jobs/runs,
  and result readout provenance that proves the normal Argus result path was used.

### Operational Answers

- **O1. Current flags:** existing feature flags gate strategies, collections,
  exploratory suggestions, onboarding, context packets, and backtest workflow
  modes. Dedicated evidence/research flags do not exist yet; future work should
  add explicit backend and frontend gates before enabling research lanes.
- **O2. Current canary coverage:** the existing Render canary covers the direct
  chat/backtest loop and async workflow result path. It does not yet cover light
  evidence mode, deep evidence mode, or evidence-provider fallback.
- **O3. Required debug receipts:** research failures should include request ID,
  lane/depth, provider/tool/model, latency, cache hit/miss if applicable,
  citations/source IDs when present, fallback reason, surfaced user message,
  and linked conversation/message/job/run IDs.
- **O4. Provider outage vs unsupported idea:** unsupported ideas should resolve
  to capability/failure codes; provider outages should resolve to provider or
  upstream failure codes. These need different user copy and retry behavior.
- **O5. Current Supabase visibility:** a successful evidence-backed test should
  at minimum leave persisted conversation/message records, any future evidence
  artifact metadata, a durable job row if async work was used, a linked
  `backtest_run` if executed, and enough route metadata to audit the path.

## Decision Ledger After The Algorithm

The full question list remains useful as a reference, but the next milestone
should only resolve the requirements below. Each row keeps the answer next to
the requirement so future agents can see what is settled and what still needs
design or implementation detail.

### First Evidence-Aware Slice Decisions

| IDs | Requirement | Answer / current decision | Still open |
| --- | --- | --- | --- |
| **P1, P2** | Define the first delightful moment. | **Answered.** The first delightful moment is not "Argus ran a backtest." It is "Argus helped me decide what to test, then closed the loop with a result." A complete result means the user got what they needed through any flexible lane: direct test, education, light evidence, or later deeper research. | Exact private-alpha interview wording and success threshold. |
| **L2, L3, L4** | Decide how much research UX to expose. | **Partially answered.** Do not force research. Keep direct tests direct. Add an explicit, polished composer affordance such as a globe/Search control or "Deep research" control so users can choose when they want research and Argus can protect resources. | Final control design, labels, defaults, and whether the first launch exposes one `Search` control or two levels: `Search` and `Deep research`. |
| **C2, C3, C6, C7** | Pick the first capability expansion. | **Partially answered.** Move cautiously toward comparisons and explicit proxies because they fit broad consumer questions and Argus's evidence loop. Use vectorbt's power for richer comparisons only when the output is simple and trustworthy. Possible examples: sector ETF vs ETF, selected basket vs benchmark, broad thesis mapped to explicit tickers/ETFs, or "winners inside a supported set" when the set is transparent. | Exact v1 experiment types, how Argus chooses proxies, how many instruments are allowed, and what chart/storytelling surface is simple enough for Alpha. |
| **E1, E2, E3, E7** | Define the minimum evidence packet. | **Partially answered.** Use Perplexity as a configurable evidence provider, not Argus's voice. Start with reasonable presets rather than raw user-visible knobs. Let users control depth through simple product language while Argus controls cost and complexity internally. | Exact preset mapping, source count, citation rendering, recency/domain filters, and whether finance-specific tools are enabled in the first slice. |
| **D1, D3, D4, D7, D8** | Choose persistence shape. | **Needs clarification.** "Message metadata first" is an implementation tactic, not the user experience. The user should still see polished evidence, candidate, and result surfaces. Internally, the first slice can store the evidence packet, candidate experiment summary, source IDs, selected proxy, and capability result inside assistant message/job/run metadata instead of creating new first-class tables immediately. This avoids schema drag until the loop proves value. | Whether reload/audit/sharing needs force a concrete `evidence_packet` or `candidate_experiment` table earlier. |
| **UX2, UX3, UX4, UX5** | Design candidate/result surfaces. | **Answered.** Reuse the confirmation/artifact lifecycle. Candidate experiments should feel like polished Argus cards. Unsupported content stays prose, not cards. Quick Take, Explain result, and Try next remain distinct. | Exact card copy and interaction details during implementation. |
| **T1, T2, T4** | Set research-to-test advice boundary. | **Answered.** Use strict non-advice language. Avoid "recommend", "should buy", and "best" in research-to-test surfaces. Argus can suggest supported historical tests, not investments. | Exact copy, especially for Spanish, and later legal review before broader exposure. |
| **CP1, CP2, CP3, CP4** | Set cost/latency knobs. | **Partially answered.** Cost is founder-controlled for now; do not let premature cost anxiety weaken the loop. Focus on creating a cohesive, attractive experience that gets users to value quickly. Latency should be acceptable in the first pass, then optimized. Cache aggressively where safe once data freshness rules are clear. | Initial request timeouts, depth limits, caching policy, and private-alpha quotas. |
| **EV1, EV2, EV4, EV7** | Define acceptance harness. | **Partially answered.** The harness should accelerate development and learning while catching regressions before production. Start with deterministic golden prompts and canaries. Evaluate whether LangSmith, LangFuse, DeepEval, or similar tooling buys speed without workflow drag. | Tool choice, first golden prompt set, and whether any external eval service is worth adding before PMF signal. |
| **O1, O2, O3, O4, O5** | Add operational guardrails. | **Answered directionally.** Build sequentially and release slices as they are ready: flags, route receipts, canaries, provider failure taxonomy, and Supabase visibility. Keep ops lean and useful. | Exact implementation sequence and field names. |

### Perplexity Control Surface Notes

The product should expose simple controls while the backend maps them to
Perplexity parameters and presets:

- **No visible control / automatic:** direct tests and simple conceptual answers.
- **Search:** a quick cited pass for current facts or broad evidence. Candidate
  backend shape: `fast-search` or a low/medium `web_search` budget.
- **Deeper research:** explicit user-chosen slower pass. Candidate backend shape:
  `pro-search` or `deep-research`, higher `max_steps`, larger search context,
  and `fetch_url` for important sources.

Perplexity Agent API supports:

- presets such as `fast-search`, `pro-search`, `deep-research`, and
  `advanced-deep-research`;
- model/tool overrides, `max_steps`, `max_output_tokens`, reasoning controls,
  and tool selection;
- `web_search` with `search_context_size`, domain/date/recency/location filters,
  and explicit token budgets;
- `fetch_url` for known URLs, bounded by `max_urls`;
- `finance_search` for structured public-equity and ETF data, including quotes,
  financials, earnings, peers, analyst coverage, ownership, corporate actions,
  and ETF/index constituents.

Argus should turn these into a small number of product presets instead of
exposing raw API knobs to users.

### Explicitly Deferred Or Removed For This Milestone

- **Non-executable indicator discovery:** hide from user-facing discovery. Either
  implement execution later or remove the inventory.
- **Mixed-asset backtests:** defer until benchmark/allocation semantics are
  designed.
- **Personalized portfolio advice and real-money trading:** remove from product
  scope.
- **Public sharing:** defer until privacy, revocation, and sanitization are
  designed.
- **Daily briefs/inbox:** defer until users prove they return to ideas.
- **Deep research by default:** defer. Users must explicitly choose slower/deeper
  work.
- **New durable research schema:** defer until message/job/run metadata proves
  insufficient.
- **LLM-as-judge:** defer until Argus has human-approved examples of good voice
  and candidate quality.
- **Vector/embedding semantic search:** defer until provider-backed discovery or
  text search fails a concrete user workflow.

### Clarified Ambiguities

- "Unsupported candidate" no longer means a visible disabled card by default.
  It means a prose boundary or a supported alternative. Runnable-looking cards
  are only for supported next steps.
- "Signal strategy" is not the core research-lab wedge. It remains an advanced
  executable path when explicitly requested.
- "Research Lab" is not a new dashboard or mode in the next milestone. It is a
  better chat loop: evidence-aware answer, supported candidate, confirmation,
  backtest, result, refinement.
- Perplexity does not own Argus voice or final result prose. It supplies cited
  context. Argus owns interpretation, capability mapping, execution, and result
  explanation.
- The next implementation should prove one loop, not build the whole ladder.

## Current Non-Decisions

These are intentionally not decided yet:

- exact Perplexity preset/model/tool mapping behind the product controls;
- exact schema for research artifacts, if message metadata proves insufficient;
- whether deep research later runs inline or through Render Workflows;
- which later milestone should revisit public sharing after privacy and
  revocation design exists;
- whether pg_jsonschema is worth adding now;
- whether a cache belongs in Supabase only or also in another service;
- when PostHog becomes worth adding after route receipts and canaries are
  insufficient.

## Guardrails

- Keep the user-facing experience simple, elegant, intuitive, and fast.
- Hide internal architecture from the user.
- Do not force research before direct backtests.
- Do not implement a second chat brain.
- Do not add regex NLU gates before interpretation.
- Do not let Perplexity produce final backtest result prose.
- Do not show unsupported ideas as runnable actions.
- Do not turn daily briefs into a generic news feed.
- Do not add vector search/RAG until a specific retrieval failure is proven.
- Do not add public sharing before privacy, revocation, and artifact sanitation
  are designed.
- Do not make provider/model names user-facing unless they are source metadata.

## Next Spec Step

The next refinement should answer enough of the open questions to define
Milestone 1 and Milestone 2 precisely, while preserving the loop thesis:

1. evidence-depth contract with direct-test bypass preserved;
2. candidate experiment contract for comparison/proxy-first tests;
3. minimum citation contract for short cited context;
4. message-metadata-first persistence plan;
5. unsupported-boundary copy and capability filtering;
6. private-alpha test script focused on broad question -> candidate -> run;
7. feature flags, route receipts, and canary requirements;
8. golden prompt harness for direct tests plus first evidence-aware examples.

The next natural product-design discussion should focus on the two still-fuzzy
areas that shape implementation:

1. the chat-composer research control: no button, one `Search` button, or
   `Search` plus `Deep research`;
2. the first comparison/proxy experiment shape: ETF-vs-ETF, explicit basket vs
   benchmark, or supported-set winner/loser scan.
