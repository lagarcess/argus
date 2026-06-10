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

The engine roadmap should prioritize understandable tests:

- compare asset A vs asset B;
- compare an asset, ETF, basket, or crypto against a benchmark;
- test recurring buys over a date window;
- test buy-and-hold windows;
- test simple signal ideas only when the rule is explainable;
- test selected baskets or proxies such as "semiconductors" through supported
  ETFs or selected tickers;
- later, test event or regime windows such as inflation periods, rate cuts,
  recessions, earnings windows, or Bitcoin halvings.

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
- Unsupported candidates can be shown as "not testable yet" only if that helps
  the user understand Argus's boundary; they must never look runnable.
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

### Product Questions

- What makes a broader consumer feel safe asking a naive finance question?
- What is the minimum delightful moment: learning something, getting a good
  test suggestion, seeing a result, or returning to a remembered idea?
- Should the first evidence-aware loop optimize for curious beginners,
  enthusiasts, or finance-literate private-alpha users while still preserving
  consumer simplicity?
- Should Argus name this surface at all, or should the loop simply feel like
  better chat?
- What should Argus never optimize for, even if it increases engagement?

### Lane Questions

- How much of lane selection should be invisible and automatic?
- When should Argus ask the user before spending more time on research?
- What user-facing words feel simple: "quick context", "deeper look",
  "test this", "remember this"?
- When should an education answer offer a test without making learning feel
  transactional?
- How does a user bypass research and go straight to testing?

### Capability Questions

- Which strategy templates are eligible for candidate experiments first:
  buy-and-hold, recurring buys/DCA, signal/indicator strategies, or all current
  supported templates?
- Which simple experiment types should the backtesting engine support next to
  make research-derived ideas useful?
- Which natural consumer prompts are currently impossible because the engine
  lacks event windows, baskets/proxies, or comparison primitives?
- How should Argus handle ideas that are meaningful but not currently testable?
- Should unsupported candidates be shown as educational boundaries or hidden?
- How should Argus represent proxy tests, for example "luxury stocks" requiring
  selected tickers or ETFs?
- What is the line between a supported experiment and a misleading proxy?

### Evidence And Source Questions

- Which Perplexity tools are reliable enough for stocks, ETFs, crypto, currency
  pairs, macro, sectors, and companies?
- What is the shortest evidence payload that increases trust without making the
  chat feel like a report?
- When does a citation help a beginner, and when does it create clutter?
- Should Argus use domain allowlists for some question types?
- How should Argus show source freshness in plain language?
- How should Argus handle conflicting sources?
- What claims require citations, and what claims can be labeled as assumptions?

### Data Questions

- What is the smallest durable "idea object" that creates continuity?
- What should Argus remember that feels useful, not creepy or noisy?
- Do we store research artifacts as concrete tables or message metadata first?
- What citation fields are required for reload, audit, monitoring, and future
  sharing?
- How long should research source snapshots live?
- Do source snippets create copyright or privacy risk?
- How should an idea object link to multiple runs and refinements?
- Should research artifacts be immutable snapshots or regenerable drafts?

### UX Questions

- How can Argus hide complexity while preserving trust?
- What does a candidate experiment card look like compared with a confirmation
  card?
- How do we avoid clutter when showing evidence, citations, candidates, and
  backtest results in one chat?
- Should "Try next" show as chips, cards, or a dedicated follow-up section?
- How do we make unsupported boundaries feel helpful rather than frustrating?
- How should Spanish-language users experience citations and source language?

### Retention Questions

- What makes a user come back tomorrow?
- What is the user expected to do after a brief: read, test, refine, save,
  ignore, or mute?
- How often is helpful: daily, weekly, event-triggered, or user-triggered?
- What kinds of changes are meaningful enough to interrupt someone?
- How does Argus avoid becoming a news feed?
- What does progress look like for a beginner learning finance?
- How should Argus let users pause, mute, or retire an idea?

### Trust And Compliance Questions

- What exact no-advice language belongs on research cards versus result cards?
- Should Argus avoid words like "recommend", "should buy", and "best" in all
  research-to-test surfaces?
- What logs or artifacts must exist to audit a disputed answer?
- When does a cited answer become too close to personalized advice?
- What additional review is needed before public sharing or monitoring?

### Cost And Performance Questions

- What is the acceptable cost per `light` evidence turn?
- What is the acceptable cost per `deep` research turn?
- What latency is acceptable before we need async jobs?
- What quotas should apply per user/day in private alpha?
- Which provider calls can be cached safely without stale or misleading output?
- What telemetry is enough before adding PostHog or a custom event pipeline?

### Evaluation Questions

- What are the first 20 golden prompts?
- What constitutes a good candidate experiment?
- How do we measure whether the user felt less intimidated?
- How do we test that citations support claims without overbuilding an eval
  framework?
- When should we introduce LLM-as-judge?
- Should OpenAI be the future independent judge provider?
- What acceptance gate proves the feature did not regress direct backtests?

### Operational Questions

- Which feature flags gate the lanes?
- How does the canary test direct mode, light evidence mode, and provider
  fallback?
- What route receipts are required to debug research failures?
- How do we distinguish provider outage from unsupported idea?
- What must be visible in Supabase after a successful evidence-backed test?

## Current Non-Decisions

These are intentionally not decided yet:

- exact Perplexity model chain;
- exact Perplexity tool configuration;
- exact schema for research artifacts;
- whether deep research runs inline or through Render Workflows;
- whether public sharing belongs in the next milestone;
- whether pg_jsonschema is worth adding now;
- whether a cache belongs in Supabase only or also in another service;
- whether PostHog is needed before private-alpha research tests.

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

1. the first eligible strategy templates;
2. the evidence-depth UX;
3. the candidate experiment contract;
4. the minimum citation contract;
5. the smallest durable idea/continuity object;
6. the first return/habit hypothesis, without implementing full monitoring;
7. the first private-alpha product test script;
8. the feature flags and success metrics.
