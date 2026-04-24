# PRODUCT.md

## Argus Product Source of Truth (Alpha MVP)

**Status:** Active | **Alpha Product v1 Locked**
**Audience:** Founders, engineers, AI agents, designers
**Purpose:** Define what Argus is, who it serves, what we are building now, and what we are explicitly not building now.

> [!IMPORTANT]
> **Locked Status**: No major scope shifts or target audience changes are allowed without explicit approval. Polish and additive refinements are permitted.

---

# 1. Product Truth

**Argus is the easiest place to speak an investing or trading idea and instantly see how it would have played out.**

**Argus is AI-powered investing and trading idea validation for everyone.**

Argus is a **chat-first, AI-first investing sandbox** where users interact through natural conversation instead of dashboards, technical forms, or intimidating trading tools.

Users describe ideas in plain language.

Argus helps them:

- understand concepts
- refine ideas
- simulate strategies
- inspect outcomes
- learn without risking capital

The backtesting engine is critical infrastructure.

The conversation is the product.

---

# 2. Why Argus Exists

Most investing and backtesting tools are built for experienced users.

They are often:

- cluttered
- technical
- chart-heavy
- jargon-filled
- intimidating for beginners
- slow to learn
- high friction to use casually

Argus exists to make idea validation accessible to anyone.

A user should not need:

- finance background
- coding knowledge
- trading platform experience
- quant skills

They should only need curiosity.

---

# 3. Primary User Segments (Alpha)

## Curious Beginner

A person interested in markets but intimidated by current tools.

Needs:

- education
- guidance
- safe experimentation
- plain language explanations

## Enthusiast

Someone already interested in stocks, crypto, or trading ideas but without advanced tools.

Needs:

- faster testing
- cleaner workflows
- less friction
- actionable feedback

## Casual Learner

Someone exploring markets socially or intellectually.

Needs:

- conversational discovery
- intuitive UX
- low commitment experimentation

---

## Trust Through Clarity

Users should understand assumptions, limits, and outcomes. Results are presented with honest context (e.g., explicit assumptions footers on all cards).

## Chat First

Conversation is the primary interface.

## AI First

The assistant guides the user, asks questions, explains results, and removes friction.

## Simplicity Wins

Avoid complex dashboards, knobs, and enterprise UX.

## Speed Matters

The product should feel immediate and responsive.

## Safe by Default

Users experiment with ideas, not real money.

## Teach Through Use

Learning happens naturally during interaction.

## Honest Boundaries

AI must clearly operate within supported system capabilities.

## Mobile Future

Alpha launches on web/PWA for speed. Long-term direction is mobile + web.

---

# 5. Alpha MVP Scope (What We Are Building Now)

## Core Experience

A new user can:

1. Enter Argus
2. Select preferred language
3. Be onboarded through chat
4. Interact with **starter prompts** designed to reduce blank-page friction
5. Describe or choose an investing idea
6. Receive AI guidance
7. Run a backtest using supported strategies
8. View results clearly through **high-fidelity metrics cards, AI explanations, and follow-up questions**
9. Revisit the conversation later
10. See prior runs and saved items

## Included Product Surfaces

### Primary Surface

- Multi-chat conversations

### Supporting Surfaces

- Recents
- Strategies
- Collections
- Settings / Account

---

# 6. Language Experience (Alpha)

Argus should feel globally accessible from first launch.

## Supported Languages

- English
- Spanish (Latin America)

## Principles

- Language selection should be intuitive and premium.
- New users should clearly understand multilingual support.
- Onboarding should occur in selected language.
- Surface UI should reflect selected language.
- AI should mirror user language preference dynamically.

Future languages may be added later.

---

# 7. Recents Surface

Recents are a mixed chronological feed of recent user activity.

Examples:

- Recent chats
- Recent strategies
- Recent collections

Purpose:

- quickly resume prior work
- reduce navigation friction
- reinforce continuity
- help users return repeatedly

Dedicated surfaces still exist for Strategies and Collections.

---

# 8. Collections (MVP Replacement for Portfolios)

Collections are lightweight saved groupings of related strategies.

Examples:

- Tech Momentum Ideas
- Dividend Experiments
- Crypto Setups
- Retirement Concepts

Collections exist to organize user thinking and repeat testing themes.

Collections are **not** full portfolio simulations in Alpha MVP.

Future portfolio systems may evolve naturally from Collections.

> [!TIP]
> **Global Rule**: Collections may mix asset classes organizationally. Backtest runs may not mix asset classes operationally.

---

# 9. Strategies Surface

Strategies are saved executable ideas backed by supported templates.

The Strategies surface gives users a quick way to evaluate performance at a glance without requiring deep chart interaction.

## Surface Goals

- scan saved strategies quickly
- compare ideas rapidly
- reopen or rerun with low friction
- edit organization state

## Metric Cards

Users may configure visible high-level metrics from supported presets.

Examples:

- total return
- win rate
- max drawdown
- sharpe ratio
- profit factor
- trade count

Metric customization should remain simple and fast.

---

# 10. Object Management (Alpha)

Users should be able to manage their workspace cleanly.

## Chats

- rename
- archive
- delete

## Strategies

- rename
- pin / unpin
- delete

## Collections

- rename
- pin / unpin
- delete

Deleted and archived surfaces should remain accessible where supported.

---

# 11. Supported AI Responsibilities (Alpha)

The AI assistant should:

- onboard new users
- explain financial terms simply
- gather requirements for supported backtests
- recommend **API-driven starter prompts** (personalized by language/goal)
- guide users toward successful flows
- explain results
- suggest next experiments
- remember thread context appropriately
- adapt to preferred language

The AI assistant should **not** pretend unsupported capabilities exist.

---

# 12. Supported Strategy Model (Alpha)

Argus Alpha uses a controlled set of supported strategy templates.

Users may speak naturally, but AI maps requests into supported engine templates.

Examples:

- Buy the dip
- RSI mean reversion
- Moving average crossover
- DCA accumulation
- Momentum breakout
- Trend follow

## Asset Class Grouping (Alpha)
Alpha supports:
- Individual symbols
- Grouped same-asset simulations (up to symbol cap)

Examples:
- Equity: `AAPL` + `MSFT` + `NVDA`
- Crypto: `BTC` + `ETH` + `SOL`

Alpha does **NOT** support mixed equity + crypto simulations.

This ensures reliability and benchmark coherence.

---

# 13. Search Philosophy (Alpha)

Search should reduce friction and help users resume intent instantly.

## Surface Search

Scoped search within each surface:

- Strategies search strategies
- Collections search collections

## Global Search

Navigation search should evolve toward omni-search across:

- chats
- strategies
- collections

Future semantic search is strongly aligned with product direction.

---

# 14. Feedback & User Listening

Users must have a clear way to provide:

- bug reports
- feature requests
- general feedback

Alpha can support:

- settings page feedback entry
- conversational capture via AI
- PostHog surveys later when enabled

Feedback velocity is strategic.

---

# 15. Explicitly Out of Scope (Alpha)

Not priorities now:

- Real brokerage trading
- Complex portfolio optimization
- Native mobile apps deferred until post-Alpha; mobile remains strategic long-term.
- Billing / subscriptions
- Social network features
- Advanced quant tooling
- Full custom scripting
- Dozens of strategy parameters
- Institutional realism modeling
- Heavy journaling systems
- **Stablecoins**: Excluded from Alpha backtesting to prevent misleading outcomes.

---

# 16. Success Metrics (Alpha)

We are optimizing for:

## Activation

Users complete onboarding and run first backtest.

## Delight

Users feel the product is modern, intuitive, and useful.

## Retention

Users return repeatedly to explore new ideas and revisit prior ones.

## Exploration

Users return to test new ideas regularly.

## Continuity

Users resume prior chats and workflows.

## Trust

Results feel clear, reproducible, and honest.

---

# 17. Product Experience Standards

Every user session should feel:

- fast
- intelligent
- elegant
- low friction
- helpful
- confidence-building

# 18. Product Anti-Patterns

Argus should avoid:

- **Spreadsheet Software**: No dense data tables or parameter overload.
- **Broker Terminal**: No dashboard-first UX or blinky, intimidating charts.
- **Toy Chatbot**: No generic, shallow, or purposeless "AI chatter."
- **Generic Finance App**: No "top 10 gainers" lists or generic news content feeds.

**Argus chooses:** Conversational progressive disclosure, simple cards, and focused actions.

# 19. Result Trust Standard

Every result card must include a lightweight assumptions footer to maintain integrity. Benchmark comparisons are class-based:
- **Equities** compare to **SPY**
- **Crypto** compares to **BTC**

Example: *Long-only • Equal weight • No fees/slippage • Benchmark: SPY*

---

# 20. Golden Path (Alpha)

A user opens Argus and says:

> What if I bought Tesla whenever it dipped hard?

Argus responds by:

1. clarifying needed inputs
2. proposing a supported simulation approach
3. running the test
4. showing outcomes
5. explaining what happened
6. suggesting what to test next

If this feels magical and trustworthy, the MVP is working.

---

# 21. Product Decision Filter

When evaluating any feature, ask:

## Does this make it easier for a normal person to test an investing idea through conversation?

If no, it likely should wait.

---

# 22. Current Strategic Focus

We are moving from prototype polish to real product utility.

Priorities now:

1. Working AI chat loop
2. Real backtests
3. Reliable persistence
4. Great web/PWA usability
5. Fast iteration from user feedback

---