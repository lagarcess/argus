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

Discovery answers follow the same rule: every suggested asset is
resolver-verified and tappable, and the answer always states its grounding.
The default path answers from model knowledge and is plainly marked "from
general knowledge, not a current search"; a source-backed search runs only
when the answer needs current facts (or the user asks), and then shows its
sources and freshness date. A remembered answer and a researched one must
never look alike.

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

1. Enter Argus and sign up (language is chosen at signup and changeable in Settings)
2. Arrive directly in normal chat
3. Interact with **starter prompts** designed to reduce blank-page friction
4. Describe or choose an investing idea
5. Receive AI guidance
6. Run a backtest using supported strategies
7. View results clearly through **high-fidelity metrics cards, AI explanations, and follow-up questions**
8. Revisit the conversation later
9. See prior runs and saved items

There is no separate onboarding flow. Activation begins in normal chat, and
the first successful backtest is the meaningful onboarding milestone.

## Included Product Surfaces

### Primary Surface

- Multi-chat conversations

### Supporting Surfaces

- Recents/history
- Omnisearch and Idea Ledger recall
- Settings / Account

Strategies and Collections remain valid flagged product objects, but they are
not visible private-alpha surfaces.

---

# 6. Language Experience (Alpha)

Argus should feel globally accessible from first launch.

## Supported Languages

- English
- Spanish (Latin America)

## Principles

- Language selection should be intuitive and premium.
- New users should clearly understand multilingual support.
- First use should occur in the selected language.
- Surface UI should reflect selected language.
- AI should mirror user language preference dynamically.

Future languages may be added later.

---

# 7. Recents Surface

Recents are a mixed chronological feed of recent user activity.

Examples:

- Recent chats
- Recent completed backtests
- Prior idea/evidence activity reopened through Omnisearch

Purpose:

- quickly resume prior work
- reduce navigation friction
- reinforce continuity
- help users return repeatedly

Recents distinguishes work in progress from attention. A task may be working
without being unread; terminal activity becomes unseen only beyond the user's
durable read boundary. Registered users may also deliberately mark a task
unread as a reminder. These states come from backend lifecycle and read truth,
never message wording, client timers, or changes to recency ordering.

Private-alpha launch keeps the visible product surface to Chat, Recents/history,
completed result cards, and minimal account/settings/feedback. Dedicated
Strategies and Collections surfaces have been retired. Historical records remain
readable so older runs and history never break, but the product no longer creates
or manages those legacy objects.

---

# 8. Legacy Collections Compatibility

Collections are retired product records. Their tables and owner-scoped history
readers remain for compatibility with historical rows; there is no navigation,
picker, setting, search result, CRUD endpoint, or new write path.

---

# 9. Legacy Strategies Compatibility

The dedicated Strategies surface and result-card Save action are retired.
Completed runs remain revisitable through conversation/history/Recents, while
Refine idea remains available on the result card. Historical Strategy rows and
direct run `strategy_id` reads remain owner-scoped and read-compatible.

Saved-idea recall lives in Omnisearch, not a separate dashboard. Typed search
results and right-panel previews cover Conversation, Backtest, Evidence,
Decision, and Idea, and the Idea Ledger browse groups saved ideas by decision
state (promising, watching, rejected, revisit) with filter chips. Group order
and counts are backend-owned; the frontend renders them without synthesizing
its own groups.

For P2, this durable `Idea` / `IdeaVersion` / `EvidenceArtifact` /
`DecisionNote` recall is the product's "remembering" contract. It is distinct
from personalization memory. Automatic or user-confirmed cross-conversation
personalization memory remains post-PMF and must not be required for the P2
idea/evidence/comparison loop.

## Surface Goals

If the flagged Strategies surface is reactivated later, its goals are:

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

Hidden under private-alpha defaults.

- rename
- pin / unpin
- delete

## Collections

Hidden and indefinitely deferred from the private-alpha UI.

- rename
- pin / unpin
- delete

Deleted and archived surfaces should remain accessible where supported.

---

# 11. Supported AI Responsibilities (Alpha)

The AI assistant should:

- welcome first-time users into ordinary conversation
- explain financial terms simply
- gather requirements for supported backtests
- recommend **localized generic starter prompts**
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

- Buy and hold
- Buy the dip
- RSI mean reversion
- Moving average crossover
- DCA accumulation

Momentum breakout and trend follow are recognized by the interpreter but are not
yet executable. Argus does not present them as runnable strategies to users.

## Asset Class Grouping (Alpha)
Alpha supports:
- Individual symbols
- Grouped same-asset simulations (up to symbol cap)

Examples:
- Equity: `AAPL` + `MSFT` + `NVDA`
- Crypto: `BTC` + `ETH` + `SOL`
- Currency pair: `EURUSD` or a same-class group such as `EURUSD` + `GBPUSD`

Alpha does **NOT** support mixed-asset-class simulations. Equity, crypto, and
currency-pair runs each remain within their own class.

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

Users reach normal chat directly after authentication and complete their
first successful backtest — that first successful backtest is the meaningful
onboarding milestone.

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
- **Currency pairs** compare to the tested pair itself

Example: *Long-only • Equal weight • No fees/slippage • Benchmark: SPY*

The default private-alpha footer discloses no fees or slippage. Execution realism
(fees + slippage modeling) is active by default behind
`ARGUS_ENABLE_EXECUTION_REALISM`, while modeled costs remain opt-in per idea.
Runs without stated fees or slippage stay idealized; when a user states costs,
the assumptions footer reflects them. Set the flag explicitly to
`false|0|off|no` only as a kill switch; that restores the pre-realism path
byte-for-byte.

Result cards and explanations must describe executed backtest behavior, not raw
strategy triggers. A strategy may produce many buy/sell signals, but Argus only
shows trades, markers, trade counts, and win-rate inputs after the execution
layer has applied long-only position state, cash, sizing, and policy constraints.
Ignored signals can be explained in breakdowns when useful, but they are not
presented as real buys or sells.

Freshness and "what changed" explanations must keep two evidence layers
separate:

- canonical run/evidence deltas state what the backtests and mechanically
  verified corporate actions show;
- source-backed news, earnings, regulatory, macro, or other event context may
  explain what coincided with or may have contributed to a change.

Argus must not present contextual correlation as proven causation. Context
should carry sources and freshness, acknowledge uncertainty, and remain
informational. It is not financial advice or a recommendation to buy, sell, or
hold an asset.

## Guest Entry (Default-On Kill Switch)

Guest mode is part of the normal Argus product shape and supersedes the
auth-first landing page by default. A guest is a
real Supabase anonymous authenticated user with one temporary workspace, never
the unauthenticated Postgres `anon` role, the mock developer, or a synthetic
email profile.

The checked-in policy is intentionally asymmetric:

- `ARGUS_GUEST_ACCESS_ENABLED=true`
- `NEXT_PUBLIC_GUEST_ACCESS_ENABLED=true`
- `ARGUS_PUBLIC_ACCOUNT_ACCESS_ENABLED=false`

The frontend presentation flag cannot grant access. The server remains
authoritative. The Guest server and presentation flags default on; explicit
`false` is their emergency rollback kill switch. Public-account access remains
an independent false-by-default gate. While it is off, permanent signup and
login remain allowlist-gated, the guest surface offers **Sign in**, and
unlisted guests cannot create permanent accounts. Existing admin and developer
roles remain unchanged.

Two clocks govern a guest, and they are deliberately distinct. The
**workspace** lives seven fixed days with one conversation: that is how long
the temporary chat survives and the window to claim it to an account.
Activity never extends the expiry. **Allowances** follow the visitor as an
abuse boundary (decision 2026-07-28): ten useful assistant terminals and two
unique simulations per visitor per day, resetting at UTC midnight. The
workspace separately caps the temporary chat at two unique simulations over
its fixed lifetime, plus five feedback submissions. A fresh session cannot
mint a fresh daily allowance—the visitor counter keys on a keyed digest of the
caller—and Start over preserves the workspace counters. Simulations keep a
workspace-keyed reservation as replay identity; the visitor charge beside it
is best-effort past admission, and settlement enforces the cap. The current
landing implementation and its centered auth modal remain intact for
configuration rollback and later conversion work.

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

## Does this make it easier for a normal person to turn curiosity into a grounded investing experiment and continue exploring?

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
